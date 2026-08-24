# State

START_EPOCH = 1787581169  (run `date -u +%s`; elapsed_h = (now - START_EPOCH) / 3600)

## Current phase
Phase 2 / M3 Pike VM IN PROGRESS (~T+1.9h). M1+M2 COMPLETE and committed.

## Next concrete action
M3 — Thompson NFA + Pike VM (target T+11h):
- nanoregex/pikevm.py: breadth-first simulation of the SAME compiled program
  (compiler.py is engine-neutral already): list-of-live-threads by pc,
  epsilon-closure via save-instruction threading, capture slots carried per
  thread with leftmost-FIRST priority preserved.
  KEY subtlety (RE2-style): in a BFS VM, 'first to reach match wins' gives
  LEFTMOST-LONGEST, but re is LEFTMOST-FIRST — thread spawn order from split
  must encode priority, and a matched thread only kills threads that started
  LATER at the same position; earlier-priority threads still win.
  Approach: process one input position per step set; maintain capture arrays
  per thread copied on enqueue; on match, record result but keep draining
  lower-priority threads only until their priority index exceeds the winner's.
- Same public API through RegexPattern (engine='pikevm' default).
- Oracle green for DEFAULT engine: python3 -m unittest discover -s tests -q -> OK
  (this unlocks charter criterion #1 verbatim); fuzz_diff --cases 5000 exit 0.
- Then bench smoke shows pikevm column real; expect linear growth, BENCH GREEN.

## Milestone status
- M1 parser: DONE ~T+1.5h (roundtrip property + ngroups parity + error tables)
- M2 backtracker: DONE ~T+1.9h — suite 24/24 + fuzz 5000 PASS + independent
  20000-case sweep PASS; three real bugs fixed along the way (JOURNAL block 3)
- M3 pike VM: IN PROGRESS
- M4 benchmark lab: harness DONE (Phase 1); remaining = full 128k run +
  growth assertions + RESULTS.md analysis
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
