# State

START_EPOCH = 1787581169  (run `date -u +%s`; elapsed_h = (now - START_EPOCH) / 3600)

## Current phase
Phase 0 COMPLETE (project chosen: nanoregex — see CHARTER.md). Next: Phase 1 oracle.

## Next concrete action
Build Phase 1 oracle BEFORE any feature code:
- tests/ harness: seeded generator of pattern/input pairs, differential runner vs stdlib `re`
  (search/match/fullmatch/findall + group spans), unittest integration.
- tools/fuzz_diff.py standalone sweep CLI (--cases N, --seed S).
- bench/run_bench.py skeleton + bench/evil.py with the five charter evil patterns,
  doubling sizes, SIGALRM timeout. Must run red against a matcher stub
  (stub raises NotImplementedError → suite reports failure = expected red).
- Makefile with `check`, `test`, `bench` targets.
Commit when harness demonstrably detects a stub as red and self-validates on `re` itself.

## Milestone status
- M1 parser: not started
- M2 backtracker: not started
- M3 pike VM: not started
- M4 benchmark lab: skeleton in Phase 1
- M5 hardening/docs: not started

## Environment facts (verified)
- NO python venv possible (ensurepip missing). Dependency mechanism:
  `python3 -m pip install --target ./pylibs <pkg>` + PYTHONPATH=$PWD/pylibs. (numpy test ok.)
- nanoregex itself is ZERO-dependency by charter; pylibs/ currently holds an unused numpy —
  delete before commit; keep pylibs/ in .gitignore.
- Network: only pypi.org/github.com/npm reachable. No GPU. 20 cores, 7.6 GiB RAM.
- WSL2 bubblewrap sandbox: writes confined to project dir + $TMPDIR. Reads outside denied.

## Known blockers
None.

## Key decisions log
- D0: Project = regex engine (candidate B) over compressor (A) and optimizer shootout (C).
  Reasons in JOURNAL.md block 0. Decision closed at ~0.4h; do not revisit.
- Conformance is DEFINED operationally: differential equality vs stdlib `re` on the documented
  subset. If a mismatch appears: either it's a real bug (fix), or a deliberate divergence
  (whitelist entry with written reason). Never weaken the test silently.
