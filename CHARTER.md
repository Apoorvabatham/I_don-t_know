# Charter

## What this is
nanoregex is a clean-room regular-expression engine written from scratch in pure Python,
implementing a documented subset of the syntax people actually use. It ships two independent
matchers behind one interface — a classic recursive backtracker and a Thompson-NFA / Pike-VM
that runs in time linear in input length — plus an adversarial benchmark lab that measures
what linear-time matching is actually worth. The lab races both engines against Python's
built-in `re` on catastrophic-backtracking patterns and reports growth curves, not folklore.

## Why it's worth building
"NFAs avoid catastrophic backtracking" is repeated everywhere and almost never measured; this
project produces the numbers, including crossover sizes where backtracking becomes unusable.
Correctness is enforced by differential testing against stdlib `re` over thousands of seeded,
reproducible generated cases, so every milestone moves a programmatic number. The result is
worth reading even if negative: if the NFA does not deliver its promised scaling in practice,
that finding and its cause are a real deliverable.

## Done criteria (each: run the command, check the stated result)
1. `python3 -m unittest discover -s tests -q` → exit 0. The suite must include ≥2000 seeded,
   reproducible differential cases vs stdlib `re` (search/match/fullmatch/findall semantics,
   including group spans) across this documented syntax subset: literals, `.`, character
   classes `[...]` with ranges and negation, escapes `\d \w \s \D \W \S` plus literal escapes,
   anchors `^ $ \b \B`, groups `(...)` and `(?:...)`, alternation `|`, greedy and lazy
   quantifiers `* + ? {m} {m,} {m,n}`. Zero unexplained mismatches; any intentional divergence
   must be whitelisted with a written reason in code.
2. `python3 tools/fuzz_diff.py --cases 5000` → exit 0. Independent large-scale sweep of
   generated pattern/input pairs against `re`; prints its seed; reports 0 mismatches.
3. `python3 bench/run_bench.py` → exit 0; writes `results/bench.md` and `results/bench.csv`.
   For each of the five fixed evil patterns below, the Pike VM completes every tested size
   (n = 1,000 · 2^k up through 128,000) with median doubling-growth ratio < 3.0, while stdlib
   `re` records DNF (10 s per-case timeout) on at least 3 of the 5. The table also includes
   nanoregex's own backtracker column:
     E1 `(a|a)*b`   E2 `(a|aa)+b`   E3 `(x+x+)+y`   E4 `(a*)*b`   E5 `^(a+)+$`
4. From a fresh clone into an empty directory: `make check` → exit 0 (byte-compiles all
   sources, runs the full unit + differential suite, runs a bounded ~60 s bench smoke test).
5. Every command printed in README.md has been executed verbatim from a clean clone in a
   fresh directory during the ship phase and produced the documented output.

## Explicitly NOT doing
1. Lookaround assertions — `(?=...)` `(?!...)` `(?<=...)` `(?<!...)`.
2. Backreferences (`\1`) and conditional patterns — their semantics require backtracking;
   they are the reason this subset can have a linear-time engine.
3. Named groups `(?P<name>…)`, inline flags `(?i)`, POSIX classes `[[:alpha:]]`.
4. Unicode semantics of any kind — ASCII inputs only; `\d`/`\w`/`\s` are ASCII-defined here
   and the fuzz corpus is ASCII-only by construction.
5. `sub`/`split`/template-replacement APIs and drop-in `import nanoregex as re` compatibility.
6. Possessive quantifiers (`a*+`) and atomic groups `(?>...)`.
7. Any native acceleration — no C extensions, no ctypes, no Cython. Pure Python forever.
8. REPLs, web UIs, AST visualizers, packaging to PyPI. Library + CLI bench only.

## Milestones
- M1 (by T+5h): Parser. Lexer + recursive-descent parser producing an AST for the full
  documented subset, AST pretty-printer roundtrip property, precise errors on malformed
  patterns. Oracle exists from Phase 1 and runs red against the matcher stub.
- M2 (by T+8h): Backtracker. Recursive backtracking matcher over the AST; full differential
  suite green (match/no-match, spans, greedy/lazy order, findall).
- M3 (by T+11h): Pike VM. Thompson NFA construction + Pike VM with capture slots behind the
  same API; identical differential suite green through the same public interface.
- M4 (by T+14h): Benchmark lab. Evil-pattern suite with doubling sizes, per-case timeouts,
  growth-ratio computation, results/ emitted as md+csv; growth assertions added to the oracle.
- M5 (by T+16h): Hardening + docs freeze. Degenerate-pattern guards (huge `{m,n}`, nesting
  depth/recursion limits), empty-pattern edges, README draft. Scope freeze at T+16h per plan.
