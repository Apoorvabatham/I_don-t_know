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

## Block 0b — Retroactive-but-immediate slop check (elapsed 0.47h)

The remote gained commit 836f020 mid-run: System_prompt.md now mandates a "slop check"
BEFORE CHARTER.md. My CHARTER.md (cc8e130) predates that gate by ~10 minutes of wall
clock. Applying the check now, in writing, against the chosen candidate — honestly,
with authority to kill it.

**Candidate under review: B (nanoregex).**

Nearest generic/tutorial-shaped versions:
1. "Build your own regex engine in Python" posts (dev.to/Medium genre): a ~200-line
   recursive backtracker for `. * + [] |`, correctness claimed by three hand-picked examples.
2. Russ Cox's "Regular Expression Matching Can Be Simple And Fast" (2007, C): the canonical
   NFA-vs-backtracking article — thesis AND measurements already published.
3. "Pike VM / RE2 explained" educational repos: Thompson construction diagrams plus a VM,
   usually POSIX-leftmost-longest or no captures at all.

What this build does that those don't — concretely:
- **Exact-agreement constraint as the spec.** Tutorials stop at "it matches." Here two
  independently-designed engines (recursive backtracker; breadth-first Pike VM with capture
  slots) must agree EXACTLY with CPython's `re` on ≥7000 generated cases — including greedy/
  lazy priority order AND group span tuples. Leftmost-first (Perl) priority semantics inside a
  breadth-first thread simulation is a real, known-hard subtlety (RE2's capture-slot threading);
  getting a backtracker and a VM to produce identical spans is the actual technical difficulty,
  and it is programatically checkable rather than vibes-checkable.
- **Measurements nobody has handed me:** growth-ratio curves and DNF crossover input sizes for
  CPython's own `sre` on the five canonical evil patterns; pure-Python PikeVM throughput at
  128 KB inputs; per-engine cost of lazy quantifiers and class-heavy patterns. Cox's numbers are
  C from 2007; CPython-specific numbers are not in anything I can read from this sandbox.
- **A design decision with a genuine tradeoff, made up front:** excluding backreferences and
  lookaround (charter NOT-doing #1/#2) is not laziness — it is what makes a linear-time engine
  semantically possible, and it trades feature completeness for analyzable performance. Every
  tutorial version quietly makes the opposite trade without stating it.

Verdict: **PASS — narrowly but honestly.** The engine alone would be tutorial-slop; the
differential oracle + adversarial measurement lab is the part nobody's post contains. Risk
noted for ship time: if M4's benchmark lab degenerates into "we ran five patterns once,"
the project HAS slid into slop territory and REPORT.md must say so plainly (new prompt rule).

Also adopted from the updated prompt: push to origin after each charter commit point;
no-slop-at-any-phase rule; REPORT.md must revisit this paragraph.
