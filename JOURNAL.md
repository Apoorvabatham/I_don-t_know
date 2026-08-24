# Journal — append-only

## Block 0 — Phase 0 survey + project selection (elapsed ~0.2h, START_EPOCH=1787581169)

### Environment survey
- OS: Ubuntu 22.04.4 LTS on WSL2, x86_64, kernel 6.18.33.2-microsoft-standard-WSL2
- CPU/RAM: i7-13700H, 20 cores, 7.6 GiB RAM. Disk: 210 GiB free on project mount.
- Python 3.10.12 system-wide (`/usr/bin/python3`), pip 22.0.2. **No numpy/scipy/etc. preinstalled.**
- `python3 -m venv` FAILS: ensurepip missing (python3.10-venv apt pkg absent, cannot install system pkgs).
  - WORKING ALTERNATIVE (tested): `python3 -m pip install --target ./pylibs <pkg>` + `PYTHONPATH=$PWD/pylibs`.
    Verified with numpy 2.2.6. This is the sanctioned dependency mechanism.
- Node v24.19.0, npm 11.17.0 available (unused so far).
- gcc/g++ 11.4.0, make 4.3. No cargo/go/java.
- Network: default-deny; pypi.org → HTTP 200 ✓, github.com → HTTP 200 ✓.
- git 2.34.1, identity configured. Repo has initial commit; working tree has System_prompt.md (modified, untracked-by-design changes mine to leave alone).

### Candidate projects (exactly 3, scored against charter rubric)

MUSTs common to all three: script-verifiable ✓, no accounts/OAuth ✓, no GPU/training/big-data ✓,
single-command run ✓, deps ≤ 10 ✓ (all zero-dependency, stdlib only). Scored on PREFERs + risk:

**A. Lossless compressor from scratch (context-mixing/PPM + arithmetic coding), raced vs gzip/bzip2/lzma**
- Unpredictable outcome: strong — genuinely unsure a from-scratch model beats lzma on ratio.
- Depth: high. Risk: HIGH — arithmetic-coder bit-fiddling bugs historically eat days; pure-Python
  throughput (~100 KB/s) makes the headline finding "Python is slow", which is a boring result.

**B. Regex engine: Thompson NFA + Pike VM + reference backtracker, differential-tested against `re`**
- Unpredictable outcome: good — exact growth curves, crossover sizes, and how much of `re`'s
  semantics a clean-room subset reproduces are unknown; catastrophic-backtracking comparison is
  quantitative, not folklore.
- Depth: very high (parser → two independent matchers → adversarial benchmark).
- Oracle quality: EXCEPTIONAL — differential testing vs `re` gives continuous programmatic
  pass/fail on thousands of generated cases; every milestone moves a measured number.
- Risk: low-medium — scope contained by a documented syntax subset; failure mode (semantic
  mismatch) is exactly what the oracle catches early.
- Negative-result-worth-reading: yes ("NFA did not help because X" is publishable to the reader).

**C. Black-box optimizer shootout (DE vs SA vs CMA-lite vs random search, equal eval budgets)**
- Unpredictable: weak — DE dominating random search is near-certain; only magnitudes unknown.
- Depth: medium. Risk: low. Boring-risk: high — result known before starting, violating the
  spirit of the PREFER clause.

Scores (1-5):            A      B      C
- Unpredictable outcome   5      4      2
- Depth                   4      5      3
- Readable-if-negative    4      4      2
- Schedule safety         2      4      5
- TOTAL                  15     17     12

### Decision
**Pick B: the regex engine.** Rationale: strongest oracle (the whole point of Phase 1), deepest
single artifact, schedule-safe, and its benchmark question (what does linear-time matching
actually buy, measured) has an answer I do not know in advance.

Project name: **nanoregex** — clean-room engine + adversarial benchmark lab, zero dependencies.

Phase 0 completed at ~0.4h elapsed. CHARTER.md written and committed; decision closed.
