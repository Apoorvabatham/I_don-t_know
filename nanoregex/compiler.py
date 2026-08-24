"""AST -> linear instruction program (shared by both matchers).

Instruction tuples (pc-addressed):
    ('char', c)            match literal character
    ('any',)               match any char except '\\n'
    ('cls', negated, items)  character class, items from CharClass AST
    ('short', kind)        \\d \\w \\s \\D \\W \\S
    ('save', slot)         record pos into capture slot (2i / 2i+1 per group;
                           slots 0/1 are the overall match)
    ('split', x, y)        try pc=x first; y is the pushed backtrack choice
    ('jmp', x)
    ('setp', k)            save current pos into scratch register k
    ('loopchk', k, x)      if pos == reg[k] jump x (zero-progress guard),
                           else fall through
    ('bol',) ('eol',)      '^' / '$'  ('$': at end OR before trailing '\\n')
    ('wordb', negated)     \\b / \\B
    ('match',)
    ('endcheck',)          fullmatch-only: absolute end of string

Quantifier compilation (greedy shown; lazy swaps split arms):
    X*   L: split(L+1, EXIT); L+1: setp(k); L+2: X; L+3: loopchk(k, EXIT);
         jmp L; EXIT:
    X{n} n independent copies of X (fresh instructions, shared save slots).
    X{m,n} = m copies + (n-m) nested optionals: split(BODY_i, EXIT-chain)
    X{m,}  = m copies + star.

The zero-progress guard is what makes (a*)* terminate like CPython's sre:
an iteration that consumed nothing falls straight through to the exit arm.

Scratch registers and save slots are allocated uniquely per compiled loop /
group; the program carries ngroups and a hard instruction cap (M5 tightens
this into the documented degenerate-pattern guard).
"""

from nanoregex.ast_nodes import (
    Alt, Anchor, Cat, CharClass, Dot, Group, Lit, Rep, Shorthand,
)
from nanoregex.errors import UnsupportedPattern

MAX_PROGRAM_LEN = 20000       # degenerate-pattern guard (huge {m,n} nests)

_WORD = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")
_DIGIT = frozenset("0123456789")
_SPACE = frozenset(" \t\n\r\f\v")

SHORT_CLASSES = {
    "d": _DIGIT, "D": _DIGIT,
    "w": _WORD, "W": _WORD,
    "s": _SPACE, "S": _SPACE,
}


def short_matches(kind, ch):
    member = ch in SHORT_CLASSES[kind]
    return member if kind.islower() else not member


def cls_char_matches(items, ch):
    """Does one class item set match ch (ignoring negation)?"""
    for it in items:
        tag = it[0]
        if tag == "ch":
            if ch == it[1]:
                return True
        elif tag == "range":
            if it[1] <= ch <= it[2]:
                return True
        else:  # ('short', kind)
            if short_matches(it[1], ch):
                return True
    return False


class Program:
    def __init__(self, code, ngroups, regs):
        self.code = code
        self.ngroups = ngroups
        self.regs = regs          # scratch progress-register count


class _Compiler:
    def __init__(self, ast, ngroups):
        self.ast = ast
        self.ngroups = ngroups
        self.code = []
        self.regs = 0              # count of scratch progress registers

    def emit(self, *ins):
        self.code.append(ins)
        if len(self.code) > MAX_PROGRAM_LEN:
            raise UnsupportedPattern(
                "pattern expands beyond the supported program size "
                f"(>{MAX_PROGRAM_LEN} instructions)")

    def new_reg(self):
        r = self.regs
        self.regs += 1
        return r

    # -- structure ---------------------------------------------------------

    def compile(self):
        # slots 0/1 are the overall match: start recorded per attempt,
        # end just before 'match'
        self.emit("save", 0)
        self._node(self.ast)
        self.emit("save", 1)
        self.emit("match")
        return Program(self.code, self.ngroups, self.regs)

    def _node(self, n):
        if isinstance(n, Lit):
            self.emit("char", n.ch)
        elif isinstance(n, Dot):
            self.emit("any")
        elif isinstance(n, Shorthand):
            self.emit("short", n.kind)
        elif isinstance(n, CharClass):
            self.emit("cls", n.negated, n.items)
        elif isinstance(n, Anchor):
            if n.kind == "^":
                self.emit("bol")
            elif n.kind == "$":
                self.emit("eol")
            else:
                self.emit("wordb", n.kind == "B")
        elif isinstance(n, Group):
            if n.index is not None:
                self.emit("save", 2 * n.index)
                self._node(n.body)
                self.emit("save", 2 * n.index + 1)
            else:
                self._node(n.body)
        elif isinstance(n, Cat):
            for p in n.parts:
                self._node(p)
        elif isinstance(n, Alt):
            self._alt(n.branches)
        elif isinstance(n, Rep):
            self._rep(n)
        else:
            raise TypeError(f"not an AST node: {n!r}")

    def _alt(self, branches):
        """Chained splits: prefer earlier branches.

        split_0 tries branch 0, falling back to split_1; ... the last
        split falls back straight into the final branch (its START, not
        the chain end — landing mid-chain would skip branch bodies and,
        under a quantifier, loop).
        """
        jmp_pcs = []
        split_pcs = []
        for br in branches[:-1]:
            sp = len(self.code)
            self.emit("split", sp + 1, None)   # x = this branch's body
            split_pcs.append(sp)
            self._node(br)
            self.emit("jmp", None)             # patched to chain end
            jmp_pcs.append(len(self.code) - 1)
        last_start = len(self.code)
        self._node(branches[-1])               # last branch: fall through
        end = len(self.code)
        for j in jmp_pcs:
            self.code[j] = ("jmp", end)
        for k, sp in enumerate(split_pcs):
            nxt = split_pcs[k + 1] if k + 1 < len(split_pcs) else last_start
            self.code[sp] = ("split", sp + 1, nxt)

    def _rep(self, n):
        lo, hi, lazy = n.min, n.max, n.lazy
        for _ in range(lo):
            self._node(n.body)
        if hi is None:
            self._star(n.body, lazy)
        else:
            self._optionals(n.body, hi - lo, lazy)

    def _star(self, body, lazy):
        top = len(self.code)
        reg = self.new_reg()
        if lazy:
            self.emit("split", None, top + 1)      # prefer exit
        else:
            self.emit("split", top + 1, None)      # prefer body
        self.emit("setp", reg)
        self._node(body)
        # zero-progress guard: an iteration that consumed nothing goes
        # straight to the exit arm instead of looping forever
        self.emit("loopchk", reg, None)            # x patched below
        self.emit("jmp", top)
        exit_pc = len(self.code)
        if lazy:
            self.code[top] = ("split", exit_pc, top + 1)
        else:
            self.code[top] = ("split", top + 1, exit_pc)
        self.code[exit_pc - 2] = ("loopchk", reg, exit_pc)

    def _optionals(self, body, count, lazy):
        splits = []
        for _ in range(count):
            sp = len(self.code)
            if lazy:
                self.emit("split", None, sp + 1)   # prefer skipping body
            else:
                self.emit("split", sp + 1, None)   # prefer taking body
            splits.append(sp)
            self._node(body)
        # NOTE: bodies fall through into the NEXT optional (nested semantics:
        # a{0,3} == (?:a(?:a(?:a)?)?)? ), so each split's exit arm targets the
        # common end, patched now.
        end = len(self.code)
        for sp in splits:
            if lazy:
                self.code[sp] = ("split", end, sp + 1)
            else:
                self.code[sp] = ("split", sp + 1, end)


def compile_ast(ast, ngroups):
    return _Compiler(ast, ngroups).compile()


def wrap_for_search(prog):
    """Program for unanchored search: implicit lazy any-char loop.

    Instruction 0 is a ('scan', x, y) branch behaving like split but
    semantically meaning 'begin the match here' (x, preferred, bit 0) vs
    'consume one char and reconsider' (y, bit 1) — ONE linear walk tries
    candidate starts in increasing order (the leftmost rule) instead of
    re-running the machine from every offset (O(n^2)). Span-only
    execution recovers the chosen start by replaying the winner's choice
    chain (see pikevm._replay_start); capture-mode passes simply record
    slot 0 normally at the x branch.
    """
    shift = 3                       # prologue length
    code = [("scan", 3, 1),
            ("anyraw",),
            ("jmp", 0)]
    for ins in prog.code:
        tag = ins[0]
        if tag == "split":
            code.append((tag, ins[1] + shift, ins[2] + shift))
        elif tag == "jmp":
            code.append((tag, ins[1] + shift))
        elif tag == "loopchk":
            code.append(("loopchk", ins[1], ins[2] + shift))
        else:
            code.append(ins)
    return Program(code, prog.ngroups, prog.regs)
