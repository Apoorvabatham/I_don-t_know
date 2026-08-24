"""Backtracking matcher: an iterative VM over compiled instructions.

Design note (M2): a classic recursive backtracker in Python hits the
recursion ceiling on long inputs, which would make the benchmark lab
measure RecursionError instead of exponential TIME. This matcher is
therefore written as an explicit choice-point stack over the linear
program from compiler.py: same leftmost-first backtracking SEMANTICS as
PCRE/sre, but iteration, not recursion — blowups on evil patterns cost
time (and are honestly measured by bench/), not stack depth.

Semantics reproduced (differential-oracle-enforced):
  * leftmost-first search; greedy prefers more iterations, lazy fewer;
  * capture slots record the LAST successful path's positions;
  * unmatched groups span (-1, -1);
  * '$' matches at end of string or just before a trailing newline;
  * '.' never matches '\\n';
  * zero-width star iterations terminate via the program's loopchk guard.
"""

from nanoregex.compiler import (
    compile_ast, wrap_for_search, cls_char_matches, short_matches,
)

_WORD = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


class Match:
    """Match result. Group 0 spans are always present; groups >= 1 may be
    resolved lazily by the Pike VM's second pass (resolver callable) so
    that capture-free queries never pay for capture tracking."""

    __slots__ = ("_subject", "_spans", "_resolver")

    def __init__(self, subject, spans, resolver=None):
        self._subject = subject
        self._spans = list(spans)    # list of (start, end); slot 0 = overall
        self._resolver = resolver

    def _ensure_resolved(self):
        if self._resolver is not None:
            self._spans = self._resolver()
            self._resolver = None

    @property
    def re_groups(self):
        self._ensure_resolved()
        return len(self._spans) - 1

    def span(self, group=0):
        if group >= len(self._spans):
            self._ensure_resolved()
        return self._spans[group]

    def group(self, group=0):
        s, e = self.span(group)
        return None if s < 0 else self._subject[s:e]

    def start(self, group=0):
        return self.span(group)[0]

    def end(self, group=0):
        return self.span(group)[1]

    def __repr__(self):
        return f"<nanoregex.Match span={self.span(0)}>"


def _at_word_boundary(s, pos):
    before = pos > 0 and s[pos - 1] in _WORD
    after = pos < len(s) and s[pos] in _WORD
    return before != after


class _VM:
    """One execution attempt of prog against s starting at `start`.

    require_end: fullmatch — 'match' only accepts pos == len(s).
    forbid_empty: zero-width-advance rule — 'match' rejects pos == start,
    forcing backtracking to explore longer paths (used by the finditer
    scanner right after an empty match).
    """

    def __init__(self, prog, s, require_end=False, forbid_empty=False):
        self.prog = prog.code
        self.s = s
        self.n = len(s)
        self.require_end = require_end
        self.forbid_empty = forbid_empty
        self.ncaps = 2 * (prog.ngroups + 1)
        self.regs = [0] * prog.regs

    def run(self, start):
        code = self.prog
        s, n = self.s, self.n
        regs = self.regs
        caps = [-1] * self.ncaps
        # A choice point snapshots the FULL machine state (pc, pos, caps,
        # regs). Registers must be restored too: loopchk compares against
        # THIS thread's iteration-start position, and a stale global reg
        # makes a backtracked empty-branch choice look like progress —
        # an infinite star re-entry (found empirically, see JOURNAL).
        stack = []                    # (alt_pc, pos, caps_snap, regs_snap)
        pc, pos = 0, start
        start_pos = start

        while True:
            op = code[pc]
            tag = op[0]
            ok = False
            if tag == "char":
                if pos < n and s[pos] == op[1]:
                    pos += 1
                    pc += 1
                    ok = True
            elif tag == "any":
                if pos < n and s[pos] != "\n":
                    pos += 1
                    pc += 1
                    ok = True
            elif tag == "anyraw":
                if pos < n:
                    pos += 1
                    pc += 1
                    ok = True
            elif tag == "cls":
                if pos < n and cls_char_matches(op[2], s[pos]) != op[1]:
                    pos += 1
                    pc += 1
                    ok = True
            elif tag == "short":
                if pos < n and short_matches(op[1], s[pos]):
                    pos += 1
                    pc += 1
                    ok = True
            elif tag == "save":
                caps[op[1]] = pos
                pc += 1
                ok = True
            elif tag == "split" or tag == "scan":
                stack.append((op[2], pos, tuple(caps), tuple(regs)))
                pc = op[1]
                ok = True
            elif tag == "jmp":
                pc = op[1]
                ok = True
            elif tag == "setp":
                regs[op[1]] = pos
                pc += 1
                ok = True
            elif tag == "loopchk":
                # zero-progress guard: jump to exit when this iteration
                # consumed nothing; otherwise continue into the next pass
                pc = op[2] if pos == regs[op[1]] else pc + 1
                ok = True
            elif tag == "bol":
                if pos == 0:
                    pc += 1
                    ok = True
            elif tag == "eol":
                if pos == n or (pos == n - 1 and s[n - 1] == "\n"):
                    pc += 1
                    ok = True
            elif tag == "wordb":
                # CPython 3.10 parity quirk: \B never matches an empty
                # subject string, though it is otherwise pure \b-negation
                if (n > 0 or not op[1]) and _at_word_boundary(s, pos) != op[1]:
                    pc += 1
                    ok = True
            elif tag == "endcheck":
                if pos == n:
                    pc += 1
                    ok = True
            elif tag == "match":
                short = self.require_end and pos != n
                empty = self.forbid_empty and pos == start_pos
                if not (short or empty):
                    return Match(s, [(caps[2 * i], caps[2 * i + 1])
                                     for i in range(self.ncaps // 2)])
                # rejected: keep backtracking for a longer/different path
            else:
                raise AssertionError(f"unknown instruction {tag}")

            if not ok:
                if not stack:
                    return None
                pc, pos, caps_snap, regs_snap = stack.pop()
                caps = list(caps_snap)
                regs = list(regs_snap)


class BacktrackMatcher:
    """Compiled pattern bound to the backtracking engine."""

    def __init__(self, pattern_obj):
        self.pattern = pattern_obj.pattern
        self.prog = pattern_obj.prog          # built eagerly by compile()
        self.prog_scan = wrap_for_search(self.prog)

    # -- single-position attempts -----------------------------------------

    def _attempt(self, s, start, require_end=False, forbid_empty=False,
                 scan=False):
        prog = self.prog_scan if scan else self.prog
        return _VM(prog, s, require_end, forbid_empty).run(start)

    def search(self, s, pos=0):
        # one walk of the lazy-any-char-wrapped program tries candidate
        # starts left-to-right; identical results to per-offset re-runs
        return self._attempt(s, pos, scan=True)

    def match(self, s, pos=0):
        return self._attempt(s, pos)

    def fullmatch(self, s, pos=0):
        return self._attempt(s, pos, require_end=True)

    def finditer(self, s):
        """Scanner reproducing CPython's zero-width rules exactly:

        A match is yielded; if it was EMPTY, the scanner stays at that
        position and retries ONCE demanding a non-empty path (yielded too
        when found); failing that, it advances one character. The demand
        never persists to later positions.
        """
        n = len(s)
        i = 0
        retry_nonempty = False       # just yielded empty at i; demand progress
        while i <= n:
            if retry_nonempty:
                m = self._attempt(s, i, forbid_empty=True)
                if m is None:
                    retry_nonempty = False
                    i += 1
                    continue
                yield m              # non-empty by construction
                i = m.end()
                retry_nonempty = False
            else:
                m = self.search(s, pos=i)
                if m is None:
                    return
                yield m
                if m.end() == m.start():
                    i = m.end()      # stay put...
                    retry_nonempty = True   # ...but demand progress next
                else:
                    i = m.end()

    def findall(self, s):
        ng = self.prog.ngroups
        out = []
        for m in self.finditer(s):
            groups = [m.group(i) if m.group(i) is not None else ""
                      for i in range(1, ng + 1)]
            if ng == 0:
                out.append(m.group(0))
            elif ng == 1:
                out.append(groups[0])
            else:
                out.append(tuple(groups))
        return out


def bind(pattern_obj):
    return BacktrackMatcher(pattern_obj)
