"""Thompson-NFA / Pike-VM matcher: breadth-first simulation, linear time.

Same instruction set as the backtracker (compiler.py), executed WITHOUT
backtracking: at every input position there is one ordered set of live
threads; each either consumes the character and moves on or dies.
Worst case O(len(s) * |program|) states — catastrophic patterns cannot
blow up because there is no exponential path space to walk.

Leftmost-first (Perl priority) semantics are tracked exactly:

* Thread lists stay in priority order: the epsilon-closure walks splits
  preferring the x arm, the char-step scans the parent list in order,
  and first-claim dedup keeps the highest-priority path per state.
* Every split decision appends a bit to an immutable parent-linked NODE
  chain carried by the thread. A chain read root->leaf is the thread's
  choice sequence; lexicographic order of choice sequences IS leftmost-
  first priority. When threads reach 'match', chains decide whether a
  later-finished result overrides an earlier-recorded one — positional
  heuristics cannot distinguish (?:aa|a) on 'aa' (override needed:
  answer (0,2)) from (|a)* on 'aaa' (no override: answer (0,0)).
* loopchk participates as a branch: continuing the loop is bit 0,
  exiting is bit 1. Its clean/dirty slot test reproduces the
  backtracker's pos==regs[k] check without storing positions.

Capture handling is TWO-PASS so capture bookkeeping never feeds the
state space: pass 1 (span mode) dedups on (pc, bits) — routing never
depends on captures — and yields the overall span; groups >= 1 resolve
lazily on first access through a full-fidelity second pass whose dedup
key includes caps ((pc, caps, bits): merging capture-distinct histories
is unsound — it loses (a*)*'s empty-final-iteration capture). Queries
that never touch groups (the benchmark lab) pay nothing extra.

Unanchored search wraps the program in an implicit lazy any-char loop
(compiler.wrap_for_search): one linear walk tries candidate starts in
increasing order instead of re-running the machine from every offset.
"""

import sys

from nanoregex.compiler import (
    compile_ast, wrap_for_search, cls_char_matches, short_matches,
)
from nanoregex.backtracker import Match

_WORD = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _at_word_boundary(s, pos):
    before = pos > 0 and s[pos - 1] in _WORD
    after = pos < len(s) and s[pos] in _WORD
    return before != after


def _chain_bits(node):
    """Root-to-leaf decision bits of a parent-linked chain (iterative)."""
    bits = []
    while node is not None:
        node, bit = node
        bits.append(bit)
    bits.reverse()
    return bits


def _chain_less(a, b):
    """True if choice-sequence a has strictly higher priority than b."""
    return _chain_bits(a) < _chain_bits(b)


class _Attempt:
    """One anchored attempt of the VM against s from `start`.

    track_caps=False (span mode): saves are inert, dedup key is
    (pc, bits), results carry only the overall span.
    track_caps=True (capture mode): dedup key is (pc, caps, bits) and a
    full spans list is produced. Recursion depth of the split walk is
    bounded by pattern nesting (guarded at parse/M5), not input length.
    """

    __slots__ = ("code", "s", "n", "nregs", "ncaps", "track_caps",
                 "require_end", "forbid_empty", "start",
                 "best_spans", "best_node", "cutoff")

    def __init__(self, prog, s, start, require_end, forbid_empty,
                 track_caps):
        self.code = prog.code
        self.s = s
        self.n = len(s)
        self.nregs = prog.regs
        self.ncaps = 2 * (prog.ngroups + 1)
        self.track_caps = track_caps
        self.require_end = require_end
        self.forbid_empty = forbid_empty
        self.start = start
        self.best_spans = None
        self.best_node = None
        self.cutoff = False

    def _expand(self, out, claimed, pos, pc, caps, bits, node):
        """Walk epsilon transitions from the current state at `pos`."""
        if self.cutoff:
            return
        code = self.code
        s, n = self.s, self.n
        while True:
            state = (pc, caps, bits) if self.track_caps else (pc, bits)
            if state in claimed:
                return
            claimed[state] = True
            op = code[pc]
            tag = op[0]
            if tag == "char" or tag == "any" or tag == "cls" \
                    or tag == "short" or tag == "anyraw":
                out.append((pc, caps, bits, node))
                return
            if tag == "jmp":
                pc = op[1]
            elif tag == "split" or tag == "scan":
                self._expand(out, claimed, pos, op[1], caps, bits,
                             (node, 0))           # preferred arm: bit 0
                pc = op[2]                        # fallback arm: bit 1
                node = (node, 1)
            elif tag == "save":
                if self.track_caps:
                    slot = op[1]
                    if caps[slot] != pos:
                        caps = caps[:slot] + (pos,) + caps[slot + 1:]
                pc += 1
            elif tag == "setp":
                k = op[1]
                if not bits[k]:
                    bits = bits[:k] + (1,) + bits[k + 1:]
                pc += 1
            elif tag == "loopchk":
                if bits[op[1]]:                   # clean -> zero progress
                    pc = op[2]
                    node = (node, 1)
                else:                             # progressed -> continue
                    pc += 1
                    node = (node, 0)
            elif tag == "bol":
                if pos != 0:
                    return
                pc += 1
            elif tag == "eol":
                if not (pos == n or (pos == n - 1 and s[n - 1] == "\n")):
                    return
                pc += 1
            elif tag == "wordb":
                if (n > 0 or not op[1]) and \
                        _at_word_boundary(s, pos) != op[1]:
                    pc += 1
                else:
                    return
            elif tag == "endcheck":
                if pos != n:
                    return
                pc += 1
            elif tag == "match":
                if (not self.require_end or pos == n) and \
                        (not self.forbid_empty or pos != self.start):
                    better = self.best_spans is None or \
                        _chain_less(node, self.best_node)
                    if better:
                        if self.track_caps:
                            spans = [(caps[2 * i], caps[2 * i + 1])
                                     for i in range(self.ncaps // 2)]
                        else:
                            spans = [(self.start, pos)]
                        self.best_spans = spans
                        self.best_node = node
                    self.cutoff = True
                return

    def run(self):
        s, n = self.s, self.n
        caps0 = (-1,) * self.ncaps if self.track_caps else ()
        bits0 = (1,) * self.nregs          # everything starts clean
        pos = self.start
        current = []
        self._expand(current, {}, pos, 0, caps0, bits0, None)
        while current and pos < n:
            ch = s[pos]
            nxt = []
            claimed = {}
            # cutoff applies WITHIN a step; it resets per step because
            # surviving threads may still override with a better choice
            # sequence (see module docstring).
            self.cutoff = False
            dirty = (0,) * self.nregs      # consuming dirties every loop
            for pc, caps, bits, node in current:
                op = self.code[pc]
                tag = op[0]
                hit = False
                if tag == "char":
                    hit = ch == op[1]
                elif tag == "any":
                    hit = ch != "\n"
                elif tag == "anyraw":
                    hit = True
                elif tag == "cls":
                    hit = cls_char_matches(op[2], ch) != op[1]
                else:                  # short
                    hit = short_matches(op[1], ch)
                if hit:
                    self._expand(nxt, claimed, pos + 1, pc + 1, caps,
                                 dirty, node)
            current = nxt
            pos += 1
        return self.best_spans


def _replay_start(prog, s, start, node):
    """Recover the true match start from a winning choice chain.

    Span-mode passes don't track slot 0 (saves inert), so after a wrapped
    search the recorded span is (scan-start, end). The winner's choice
    bits replay deterministically through the program; each time the
    prologue's 'scan' branch takes its 'begin here' arm, the candidate
    start moves to the current position. The last such move on the
    successful path is the match's actual start. O(chain length).
    """
    bits = _chain_bits(node)
    i = 0
    pos = start
    cand = start
    pc = 0
    code = prog.code
    n = len(s)
    while True:
        op = code[pc]
        tag = op[0]
        if tag == "char" or tag == "any" or tag == "anyraw" \
                or tag == "cls" or tag == "short":
            pos += 1
            pc += 1
        elif tag == "jmp":
            pc = op[1]
        elif tag == "split":
            pc = op[1] if bits[i] == 0 else op[2]
            i += 1
        elif tag == "scan":
            if bits[i] == 0:
                cand = pos
                pc = op[1]
            else:
                pc = op[2]
            i += 1
        elif tag == "loopchk":
            if bits[i] == 0:
                pc += 1
            else:
                pc = op[2]
            i += 1
        elif tag == "match":
            return cand
        else:                          # save/setp/bol/eol/wordb/endcheck
            pc += 1
        assert i <= len(bits) and pos <= n


class PikeVM:
    """Compiled pattern bound to the breadth-first engine."""

    def __init__(self, pattern_obj):
        self.pattern = pattern_obj.pattern
        self.prog = pattern_obj.prog          # built eagerly by compile()
        self.prog_scan = wrap_for_search(self.prog)

    def _run_attempt(self, prog, s, start, require_end, forbid_empty,
                     track_caps):
        att = _Attempt(prog, s, start, require_end, forbid_empty,
                       track_caps)
        return att.run(), att.best_node

    def _attempt(self, s, start, require_end=False, forbid_empty=False,
                 scan=False):
        prog = self.prog_scan if scan else self.prog
        spans, best_node = self._run_attempt(prog, s, start, require_end,
                                             forbid_empty,
                                             track_caps=False)
        if spans is None:
            return None
        if scan:
            # span mode doesn't track slot 0; recover the real match
            # start by replaying the winner's choice chain
            end = spans[0][1]
            real_start = _replay_start(self.prog_scan, s, start, best_node)
            spans = [(real_start, end)]
        if self.prog.ngroups == 0:
            return Match(s, spans)
        resolver = self._make_resolver(prog, s, start, require_end,
                                       forbid_empty)
        return Match(s, spans, resolver)

    def _make_resolver(self, prog, s, start, require_end, forbid_empty):
        def resolve():
            spans, _ = self._run_attempt(prog, s, start, require_end,
                                         forbid_empty, track_caps=True)
            if spans is None:
                raise AssertionError(
                    "capture resolution lost the pass-1 match")
            return spans
        return resolve

    def search(self, s, pos=0):
        return self._attempt(s, pos, scan=True)

    def match(self, s, pos=0):
        return self._attempt(s, pos)

    def fullmatch(self, s, pos=0):
        return self._attempt(s, pos, require_end=True)

    def finditer(self, s):
        n = len(s)
        i = 0
        retry_nonempty = False
        while i <= n:
            if retry_nonempty:
                m = self._attempt(s, i, forbid_empty=True)
                if m is None:
                    retry_nonempty = False
                    i += 1
                    continue
                yield m
                i = m.end()
                retry_nonempty = False
            else:
                m = self.search(s, pos=i)
                if m is None:
                    return
                yield m
                i = m.end()
                retry_nonempty = m.end() == m.start()

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
    # split-arm recursion in _expand nests per pattern structure, not per
    # input character; give deeply nested (legal) programs headroom.
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    return PikeVM(pattern_obj)
