# State

START_EPOCH = 1787581169  (run `date -u +%s`; elapsed_h = (now - START_EPOCH) / 3600)

## Current phase
Phase 1 COMPLETE (~T+1.4h): oracle built, validated red-vs-stub AND self-validated,
committed. Next: Phase 2 / M1 parser.

## Next concrete action
M1 — Parser (target T+5h):
- nanoregex/lexer.py + nanoregex/parser.py: recursive-descent parse of the full
  documented charter subset (literals, `.`, classes with ranges/negation,
  `\d\w\s\D\W\S` + literal escapes, `^ $\b\B`, `(...)`, `(?:...)`, `|`,
  `* + ? {m} {m,n}` greedy+lazy) -> AST.
- Precise errors on malformed patterns (position included). Out-of-subset syntax
  (lookaround, backrefs, named groups, inline flags) -> UnsupportedPattern.
- AST pretty-printer roundtrip property added to tests/ (parse(serialize(ast)) == ast).
- Keep the oracle red only on missing MATCHERS: differential suite must stay
  red-vs-stub until M2; do not let parser work touch tests/compare.py semantics.

## Milestone status
- M1 parser: IN PROGRESS (started ~T+1.4h)
- M2 backtracker: not started (oracle ready, drives it via NANOREGEX_ENGINE=backtracker)
- M3 pike VM: not started (same oracle via NANOREGEX_ENGINE=pikevm)
- M4 benchmark lab: harness DONE in Phase 1 (bench/run_bench.py + bench/evil.py);
  remaining for M4 = growth assertions in oracle + full 128k run + results analysis
- M5 hardening/docs: not started

## Environment facts (verified)
- NO python venv possible (ensurepip missing). Dependency mechanism:
  `python3 -m pip install --target ./pylibs <pkg>` + PYTHONPATH=$PWD/pylibs. (numpy test ok.)
- nanoregex is ZERO-dependency by charter. pylibs/ gitignored; delete before any commit.
- Network allowlist: pypi.org/github.com/npm etc. No GPU. 20 cores, 7.6 GiB RAM.
- WSL2 bubblewrap sandbox: writes confined to project dir + $TMPDIR; reads outside denied.
- SIGALRM per-case timeout verified working against real sre blowups (bench smoke DNFs).

## Known blockers
None.

## Key decisions log
- D0: Project = regex engine (candidate B). Closed at ~0.4h; see JOURNAL.md block 0.
- D1: Conformance DEFINED operationally = exact differential equality vs stdlib `re`
  on the documented subset incl. group spans; mismatches are bugs or whitelisted-with-reason.
- D2 (Phase 1): timeout code deliberately duplicated between tests/compare.py (pass/fail,
  fixed budget) and bench/run_bench.py (per-repeat timing, float budgets) — keeps oracle
  and lab independently reviewable; revisit only if they drift semantically.
- D3 (Phase 1): fuzz_diff with no --seed draws fresh SystemRandom seed and PRINTS it —
  independent sweeps stay reproducible from the printed line.
- D4 (Phase 1): E5 evil subject = "a"*n + "b" — bare "a"*n trivially matches ^(a+)+$
  (caught by own smoke run); every evil subject must be non-matchable by construction.

## Phase 1 acceptance evidence (all demonstrated before commit)
- `python3 -m unittest discover -s tests -q` -> exit 1, exactly one failure
  (test_differential_all_seeds vs stub), 9/9 self-validation green.
- Green-path validation: nanoregex.compile aliased to re -> fuzz_diff --cases 2500
  reports PASS 2500/2500 across all 11 buckets (comparator plumbing sound).
- `tools/fuzz_diff.py --cases 1500 --seed 42` vs stub -> exit 2 RED as designed.
- `bench/run_bench.py --smoke` -> 24s (<60s bound), re column measured live,
  stdlib re DNF 5/5 evil patterns at n<=4000 w/ 2s timeout, nanoregex cells
  unavailable -> BENCH RED exit 1. results/bench.{md,csv} written.
- `make check` runs compileall + unittest + smoke; fails only at the by-design red.
