# REPORT

The run went well: nanoregex shipped complete, every charter done-criterion
verified from a fresh clone, roughly four hours into a 24-hour budget.

## What shipped

- **Two matchers behind one API**, both passing a 2,500-case differential
  suite against CPython `re` with exact agreement on spans (including
  capture groups), greedy/lazy priority, and findall/finditer zero-width
  rules — plus independent seeded sweeps of 5k–20k cases at zero
  mismatches, with an empty divergence whitelist:
  - `pikevm` (default): breadth-first simulation, linear time. All five
    charter evil patterns complete at n=128,000 in 1–2.3 s (median doubling
    ratios 1.84–2.16) where stdlib `re` exceeds 10 s at n=1,000.
  - `backtracker`: iterative choice-point VM, faithful exponential
    semantics — the control group that makes the comparison honest.
- **A benchmark lab** (`bench/run_bench.py`) with SIGALRM timeouts,
  median-of-repeats, growth-ratio computation, md+csv output, and
  programmatic pass/fail verdicts; plus growth assertions living inside the
  unit suite (`tests/test_growth.py`), not just in reports.
- **An oracle-first development record**: the corpus generator, comparator,
  self-checks (determinism, coverage floors, planted-bug detection) were
  built before any matcher code and stayed red against stubs until M2.
- Hardening guards (nesting depth, program-size caps) with tests; README;
  RESULTS.md; this report.

## What is PARTIAL or cut

Nothing from the charter is partial. The honest cuts are inside scope
boundaries rather than across them:

- The documented subset excludes lookaround/backreferences/named groups/
  inline flags/unicode by charter design — these are rejections with
  distinct exceptions, not silent gaps, but they mean nanoregex is not a
  general-purpose `re` replacement.
- Capture resolution in pikevm is lazy and can be expensive on huge
  adversarial grouped matches. A production system would want RE2-style
  bounded one-pass submatch extraction instead of a second full pass.
- No performance work was spent on constants: ~7–17 µs/char is fine for a
  lab, slow for production.

## Where the time actually went

Roughly: Phase 1 oracle + M1 parser ~2h; backtracker ~1h; **the Pike VM's
leftmost-first capture semantics ~1h of pure debugging across four design
iterations** (global rank counters broke priority inheritance; per-pc dedup
merged capture-distinct histories; inert loopchk erased the continue-vs-
exit decision); linear-time architecture (two-pass captures, wrapped scan)
~30min; docs and fresh-clone verification ~45min.

Two of those iterations were found by the oracle within minutes of writing
them — which is exactly the argument for building the oracle first, and the
reason the whitelist policy stayed empty the whole run.

## Phase 0 assumptions that proved wrong

- I expected `re` to DNF on ≥3 of 5 evil patterns at some size up to
  128,000. Reality: all five DNF at n=1000 already. The cliff is immediate.
- I assumed the benchmark harness would be routine scaffolding. In fact the
  lab caught its own first bug (E5's subject trivially matched, measuring
  nothing) and later caught a statistical flaw in my own growth test
  (raw doubling ratios flaking under scheduler noise). Measurement code
  needs testing as much as engines do.
- I assumed BFS thread priority could be handled with positional
  bookkeeping ("first to arrive wins"). Leftmost-first semantics genuinely
  require comparing full choice sequences; that was the single deepest
  technical problem of the build.

## Slop check, revisited

My Phase 0 slop-check paragraph argued nanoregex clears the bar because of
(a) exact-agreement differential testing as the spec, (b) measurements
nobody had handed me for CPython specifically, and (c) a stated trade-off
(dropping backtracking features to make linearity possible).

Plain verdict: **it cleared the bar, but not by the margin I predicted.**
The bare engine — lexer, parser, recursive matcher — is tutorial-shaped;
Russ Cox's 2007 article covers that ground better than any repo I could
write. What is NOT in any post I have seen: an engine whose conformance
target is *exact span-level parity with CPython `re` quirks* ($-before-
newline, \B-on-empty, empty-final-iteration captures), enforced by
thousands of generated cases with an empty exception whitelist; a
choice-chain priority mechanism reproducing Perl leftmost-first ordering
in a breadth-first machine; and the finding that capture tracking cannot
ride along in the NFA state space at all (combinatorial blow-up) — hence
the two-pass lazy design. The lab's numbers are new only in their setting;
its methodological bugs (non-matchable subjects, flaky thresholds) are the
part worth reading.

If the run had stopped after M2, the slop verdict would have been guilty
as charged. M3's semantics work and M4's measurement discipline are what
make this a project instead of a tutorial.

## Post-ship review (same day)

An adversarial recheck after the initial ship found one real, user-visible
bug and three blind spots:

- **Unknown letter escapes diverged silently.** `\q`, `\z`, `\c`, … are
  errors in CPython (`bad escape`) but nanoregex matched them as literal
  characters — 32 silent divergences across a systematic probe of every
  ASCII letter. Fixed; probe now reports zero. The instructive part: the
  20k-case fuzz sweeps could never have caught this, because the corpus
  generator never emitted letter-escapes either. A fuzzer's blind spots
  cap what its clean bill of health is worth.
- Three construct families were generator-blind: lazy counted repeats
  (`a{2,3}?` — parity rested on a single hand-written case), shorthand
  members inside classes (`[\da-c]`), and empty alternation branches.
  All three are now generated; suite re-verified green on both engines
  with the reshaped corpora, plus fresh 8k-case sweeps per engine.
- An apparent 15x performance regression was bisected with interleaved
  A/B runs against a clone of the pre-M5 commit: identical timings. The
  slowdown was WSL2-wide CPU contention (a raw interpreter loop degraded
  equally). No code change needed — and the noise-robust growth-exponent
  oracle kept passing under exactly that load.

## What I'd do next

- Bound the lazy-capture cost (one-pass/two-pass hybrid with a state cap).
- Add a literal-prefilter (Boyer–Moore-ish skip table) for search; most
  real patterns have a mandatory first character.
- Property-test the compiler directly (program invariants: split arms
  ordered, loopchk dominated by setp), not just behavior.
