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

## Block 1 — Phase 1 oracle complete (elapsed ~1.4h)

Resumed from STATE.md's next action. Found partial Phase 1 work already on disk
(nanoregex stub API, tests/gen_corpus.py, tests/compare.py, both test files) —
reviewed line by line before building the missing pieces on top.

### Built this block
- tools/fuzz_diff.py: standalone sweep CLI (--cases/--seed/--engine/--timeout),
  prints seed (fresh SystemRandom seed when not given — D3), exit 0/1/2/3 contract.
- bench/evil.py + bench/run_bench.py: five charter evil patterns, doubling sizes
  1000..128000, per-case SIGALRM timeout, median-of-repeats, consecutive-doubling
  growth ratios, results/bench.{md,csv}. Charter verdict logic is programmatic:
  pikevm must complete every size with median ratio <3.0; re/backtracker DNF is a
  measured result, never a failure. --smoke bounds a run for make check.
- Makefile: check (compileall + unittest + ~60s smoke), test, bench, fuzz, clean.

### What broke (and was caught by the harness itself)
E5 `^(a+)+$` vs bare "a"*n TRIVIALLY MATCHES in sre (~0ms): greedy arm eats
everything and `$` is satisfied, so there is no failure to backtrack through.
First smoke run reported growth ratio 0.53 on a "catastrophic" pattern — the lab
refused to lie. Fix (D4): E5 subject = "a"*n + "b". After fix all 5/5 patterns
DNF stdlib re at n<=4000 under a 2s budget. Lesson recorded: an evil-pattern
subject must be non-matchable by construction or it measures nothing.

### Validation evidence (before commit)
- Suite: exactly one red = differential-vs-stub; 9/9 self-validation green.
- Green path: aliased nanoregex.compile -> re, ran real pipeline, 2500/2500 PASS
  across all 11 buckets — comparator plumbing has no false positives.
- fuzz_diff vs stub: exit 2 RED as designed. make check: fails only at that red.

### Decisions logged (see STATE.md D2-D4)
Timeout code duplicated between compare.py and run_bench.py on purpose;
fuzz_diff prints fresh seeds for reproducibility; evil subjects non-matchable
by construction.

Phase 1 done at ~1.4h elapsed, ahead of the T+3h gate. Next: M1 parser.

## Block 2 — M1 parser complete (elapsed ~2.0h)

### Built
- nanoregex/errors.py: NanoregexParseError (malformed-in-subset; re.error parity
  target) vs UnsupportedPattern (well-formed but charter-NOT-doing: lookaround,
  backrefs, named groups, inline flags, \A\Z, octal/unicode escapes). Both carry pos.
- nanoregex/lexer.py: tokens incl. fully-scanned classes (class syntax is its own
  mini-grammar); malformed { bounds fall back to literal '{' per CPython.
- nanoregex/parser.py: recursive descent; singleton Alt/Cat collapse so the printer
  is an exact inverse; "multiple repeat" + "nothing to repeat" + min>max errors;
  capture indices by open order.
- nanoregex/printer.py: AST -> subset pattern; roundtrip contract.
- nanoregex/api.py: compile() now real (AST + groups + engine choice); matchers
  still NotImplementedError at call time — oracle stays red until M2.
- tests/test_parser.py: roundtrip property over the whole 2500-case corpus,
  ngroups parity vs re on 1000+ patterns, AST shape checks, malformed/unsupported
  tables. gen_corpus EDGE_CASES extended with probed CPython quirks ([]] first-]
  literal, a{2 literal-brace fallback, $ before trailing newline, empty branch,
  {,3}, [\d], \t\n, \x41).

### Probed CPython parity facts now encoded as permanent bedrock cases
[]] = class of ']' ( [] unterminated); ] } lone = literals; a{2 / a{2, = literals;
a{,3} == {0,3}; [\d-a] = bad-range error; $ matches before trailing \n;
\0 = NUL; a** = multiple-repeat error.

### Broke during the block (all mine, all in tests not engine)
Wrote wrong expectations twice: forgot (?:...) parses to a Group node; put {2}
in the accepted-quirks list though it IS rejected ("nothing to repeat"); left a
stray valid literal 'A' in the unsupported table. Parser itself was right each
time — tests fixed, no weakening of anything.

### Evidence before commit
23/24 suite green; single red = differential-vs-stub (by design).
Extra one-off: printed patterns compiled under re with equal group counts AND
equal search spans on 1200 corpus pairs (printer->re behavioral parity).
fuzz_diff --seed 99 -> exit 2 RED intact after api rewrite.

M1 landed ~3h ahead of its T+5h gate. Next: M2 backtracker (oracle goes green).

## Block 3 — M2 backtracker complete (elapsed ~1.9h)

### Built
- nanoregex/compiler.py: AST -> linear instruction program (char/any/cls/short/
  save/split/jmp/setp/loopchk/bol/eol/wordb/match), shared by future Pike VM.
  Quantifiers expand to star + optional-chain; {m,n} unrolled with a documented
  program-size cap. Zero-progress guard (setp/loopchk) makes (a*)* terminate.
- nanoregex/backtracker.py: ITERATIVE backtracking VM (explicit choice-point
  stack, no recursion) — recursion depth would have made the lab measure
  RecursionError instead of exponential time. Match object with span/group;
  search/match/fullmatch/findall/finditer wired through api.py by engine.

### Three real bugs the oracle caught (in order)
1. Compiler never emitted overall-match save slots 0/1 -> group(0)=(-1,-1),
   and finditer's empty-match advance then rewound i to 0 forever (the hang).
2. Alternation compilation pointed every split fallback at the CHAIN END,
   skipping later branches ((a|b) could match 'a' or nothing) and looping
   under quantifiers — (a|b)*c hung on 'abc'. Fix: fallback arms target the
   NEXT alternative's entry; last split targets the last branch START.
3. Progress registers were global across backtracks: a restored empty-branch
   choice saw a STALE reg, loopchk misread it as progress, star re-entered
   forever (18,750-deep stack at instrument cap on (?: |)*x). Fix: choice
   points snapshot the FULL machine state (pc,pos,caps,regs).

### CPython quirks probed and encoded
- finditer scanner: an empty match is yielded, then the SAME position is
  retried demanding non-empty (yielded too when found); failing that advance
  one char. Constraint does NOT persist across positions (b?? on 'xb').
- \B in 3.10 = pure \b-negation EXCEPT it never matches an empty subject.

### Evidence before commit
- Suite 24/24 OK in 0.76s under NANOREGEX_ENGINE=backtracker (2500 differential
  cases, zero mismatches, zero whitelist entries).
- Charter criterion #2 shape: fuzz_diff --cases 5000 --seed 20260824 -> PASS.
- Independent sweep: --cases 20000 --seed 777777 -> PASS 20000/20000.
- bench smoke: re DNF 5/5 evil patterns; backtracker column measures real DNFs;
  pikevm correctly red until M3. Fixed make_matcher stub-probe (call-time raise).

## Block 4 — M3 Pike VM complete (elapsed ~3.1h at block start; suite green both engines)

### Built
- nanoregex/pikevm.py: breadth-first thread simulation over the shared program.
  The hard part was not speed — it was EXACT CPython leftmost-first capture
  semantics in a BFS machine. Four design iterations, each forced by the oracle:
  v2 global rank counters broke priority inheritance ((?:aa|a) on 'aa' gave
  (0,1) not (0,2)); v3 per-pc dedup merged capture-distinct histories
  ((a*)* gave g1=(0,3) not (3,3)); v5-without-loopchk-bits erased the
  continue-vs-exit decision. Final design: threads carry immutable
  parent-linked CHOICE CHAINS (split arms append bits; loopchk contributes
  continue=0/exit=1); match events compare chains lexicographically — exact
  leftmost-first order, no heuristics. Dedup key (pc,caps,bits).
- Two-pass captures: span pass ignores saves entirely (key (pc,bits)) so
  capture bookkeeping never feeds the state space — this is what keeps
  (a+)+ linear where naive caps-tracking explodes combinatorially. Groups >=1
  resolve lazily on first .span(i>0)/.group(i>0) access via a full-fidelity
  second pass; queries that never touch groups (the whole benchmark lab)
  never pay.
- Unanchored search via compiler.wrap_for_search: implicit lazy any-char
  prologue ('scan' opcode) tries candidate starts left-to-right in ONE walk
  — replaces O(n^2) per-offset re-runs. Span-mode recovers the true match
  start by replaying the winner's choice chain (deterministic, O(n)).
- backtracker.py switched to the same wrapped scan for search() (identical
  semantics, one walk); Match gained lazy-resolver support (backtracker
  passes eager spans, resolver=None).

### Bugs caught by own tests during the block
- forgot wrap_for_search import in backtracker; dropped _chain_less helper in
  a rewrite; prog.regs attribute missing on _Attempt (slots rename). All
  mechanical, all caught instantly by the suite.

### Evidence before commit
- Suite 24/24 OK with DEFAULT pikevm AND NANOREGEX_ENGINE=backtracker.
- fuzz --cases 5000 --seed 20260824 PASS (pikevm); --cases 15000 --seed 777
  PASS (backtracker).
- Linearity: all five evil patterns at n=128000 complete in 0.99-2.30s
  (pure Python), doubling ratios ~2.5-3.0 measured informally; stdlib re
  DNFs at 10s on these sizes. Full charter bench run launched separately.

## Block 5 — M5 + ship verification complete (elapsed ~4.0h)

### Built
- Hardening: parser MAX_DEPTH=120 nesting cap; program-size cap (20k
  instructions) now enforced at compile() — RegexPattern builds the program
  eagerly and both matchers reuse it (previously the guard fired only on
  first use, which tests/test_hardening.py caught immediately).
- tests/test_growth.py: growth assertions in the oracle. First version used
  raw doubling ratios <3.0; flaked twice under scheduler noise (once in
  dev, once in the FRESH-CLONE ship check: exponent 1.62, single 32k sample
  jumped 3.4x). Final metric: untimed warmup + min-of-3 per size with GC
  quiesced, growth exponent bound 1.6 (linear ~1.0-1.3, quadratic ~2.0).
- bench --smoke semantics fixed after the same fresh-clone failure exposed
  it: smoke cells are 1-4ms single-repeats where strict ratio gating is
  statistically meaningless — smoke enforces liveness (completion, no DNF),
  the charter <3.0 gate stays with the full schedule (median-of-3 over ~1s
  cells) and with test_growth's exponent.
- README.md + RESULTS.md. Demo snippets verified verbatim before commit.

### Ship verification (fresh clone of HEAD into empty dir)
- make check -> exit 0
- python3 -m unittest discover -s tests -q -> exit 0 (34 tests; 2500
  differential cases vs re, zero mismatches, whitelist EMPTY throughout run)
- tools/fuzz_diff.py --cases 5000 -> exit 0, PASS, prints seed
- bench/run_bench.py --smoke -> BENCH GREEN
- full charter bench earlier today: exit 0; pikevm all sizes to 128000,
  median doubling ratios 1.84/1.97/2.05/2.06/2.16 across E5/E1/E2/E4/E3;
  stdlib re DNF 5/5 at 10s; backtracker DNF everywhere (control group).
- README demo verified: pikevm n=100k in ~1s; re still running at n=350
  after 20s.

All five charter done-criteria green from a fresh clone at ~T+4h.
REPORT.md written including the mandated slop-check revisit (verdict:
cleared, but only via M3/M4 work — the bare engine alone is tutorial-
shaped and the report says so plainly).

## Block 6 — post-ship adversarial recheck (elapsed ~4.6h)

User asked to recheck and find bugs. Hunted with targeted hammers instead of
re-running the same suite.

### BUG FOUND AND FIXED (real, user-visible)
Unknown escapes of ASCII letters (\q \z \c ... 33 letters probed): CPython
raises re.error("bad escape"); nanoregex silently treated them as literal
characters — 32 silent divergences on input users actually hit. Fixed in
lexer._read_escape: unknown ASCII-letter escapes now raise
NanoregexParseError like re; punctuation escapes stay literals (verified).
Probe now reports 0 divergences.

### COVERAGE GAPS FOUND IN THE FUZZER (fixed)
- Lazy counted repeats (a{2,3}?) were NEVER generated — parity rested on
  one hand-written case. quant_counted bucket now emits lazy 30% of the time.
- Shorthand members inside classes ([\da-c] shapes) were never generated;
  cls() items now include them + serializer support.
- Empty alternation branches (a||b / x|) only existed in EDGE_CASES; alt
  bucket inserts one 20% of the time.
Corpus changed => all seeds' corpora changed; suite re-run green both engines,
plus fresh 8k-case sweeps per engine (seeds 4711/90210) all PASS.

### HAMMERS RUN (all clean)
- exhaustive-ish lazy counted repeats: 1080 checks vs re fullmatch spans.
- odd classes [\d][^\W]... x dash placements: 864 checks.
- long-subject hammer: 1200 corpus patterns x subjects up to ~130 chars x
  search/fullmatch/findall/finditer x both engines: 0 problems.

### NON-BUG investigated: apparent 15x slowdown
test_growth went from ~3s to ~30s and evil-pattern timings looked 10-15x
worse than the morning bench. Bisected via interleaved A/B against a clone
of 581e789 (pre-M5): old and new IDENTICAL (~0.48s E1@32k each). Raw Python
loop also ~3-4x slower machine-wide -> WSL2 CPU contention/throttling, not
code. The exponent-based growth metric kept passing under this load, which
is exactly why it was designed noise-robust. No action needed.
