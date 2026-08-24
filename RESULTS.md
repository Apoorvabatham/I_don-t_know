# RESULTS

## The headline

On the five canonical catastrophic-backtracking patterns (charter-fixed),
with worst-case non-matching inputs:

| pattern | stdlib `re`, n=1000 | backtracker, n=1000 | **pikevm, n=1000** | **pikevm, n=128000** | median doubling ratio |
|---|---|---|---|---|---|
| `(a\|a)*b` | DNF (>10 s) | DNF | 6.8 ms | ~1.0 s | 1.97 |
| `(a\|aa)+b` | DNF | DNF | 12.5 ms | ~1.6 s | 2.05 |
| `(x+x+)+y` | DNF | DNF | 15.9 ms | ~2.4 s | 2.16 |
| `(a*)*b` | DNF | DNF | 12.4 ms | ~1.4 s | 2.06 |
| `^(a+)+$` | DNF | DNF | 12.9 ms | ~1.5 s | 1.84 |

Read the table as: the same input size where CPython's engine exceeds a
10-second budget, nanoregex's Pike VM finishes in tens of milliseconds and
keeps going to 128,000 characters with clean linear scaling (doubling ratio
~2.0 = exactly linear; the charter threshold was < 3.0). The project's own
backtracker — deliberately a faithful exponential design — DNFs everywhere,
which is what makes it an honest control group rather than a strawman.

Reproduce: `python3 bench/run_bench.py` (writes `results/bench.md`,
`results/bench.csv`; ~14 min because the DNF cells burn their full 10 s
timeouts). A bounded smoke version runs via `make check`.

## Method

- Machine: i7-13700H laptop under WSL2 (Ubuntu 22.04), CPython 3.10.12,
  pure Python 3, no extensions anywhere.
- Sizes: n = 1,000 · 2^k for k = 0..7. Per-case wall timeout 10 s (SIGALRM);
  each cell is the median of 3 independently timed runs of
  `pat.search(subject)`.
- Subject construction: n copies of the dominant literal character, built so
  the pattern CANNOT match and a backtracking engine must exhaust its match
  space before concluding failure. Matching inputs would measure nothing —
  see surprises below for how we learned this twice.
- Growth ratio: consecutive pairs median_t(2n)/median_t(n); the per-pattern
  number is the median over the 7 ratios.
- Correctness context: both engines pass a 2500-case differential suite vs
  `re` (exact spans incl. capture groups across search/match/fullmatch/
  findall/finditer), plus seeded fuzz sweeps of 5,000–20,000 cases at
  0 mismatches. The benchmark compares engines that demonstrably agree on
  semantics; only speed differs.

## What surprised me

1. **The lab caught its own subject bug before it lied to us.** First smoke
   run showed `^(a+)+$` completing in ~0 ms with growth ratio 0.53 — because
   bare `"a"*n` trivially MATCHES that pattern (greedy arm eats everything,
   `$` is satisfied). An "evil pattern" whose subject matches measures
   nothing. E5 now carries a failing tail (`"a"*n + "b"`); after the fix all
   five patterns blow up `re`. Lesson recorded in JOURNAL.md as decision D4:
   evil subjects must be non-matchable by construction.
2. **CPython `re` DNFs on ALL FIVE patterns, not the expected three.**
   Charter anticipated ≥3 of 5; reality is 5/5 already at n=1000 within 10 s.
   There is no partial protection in `sre` against any of these shapes —
   including the anchored one everyone quotes in blog posts.
3. **The exponential cliff is immediate, not gradual.** Our own backtracker
   — semantically identical, passing the same differential suite — DNFs at
   n=1000 on every pattern. There is no usable middle ground: either you
   simulate breadth-first or you lose.
4. **Capture tracking cannot ride along for free.** Naively threading
   capture slots into the BFS state space explodes combinatorially on
   `(a+)+`: every distinct partition of the prefix into iterations is a
   distinct capture history and dedup can no longer merge states. The fix
   was architectural: a span-only first pass (routing provably never depends
   on captures), with groups resolved lazily by a second full-fidelity pass
   only when someone actually reads them. Capture-free queries — which
   includes this entire lab — never pay.

## What I'd distrust about these numbers

- Single machine, single run session. Absolute times move with WSL2 load,
  thermals and GC timing; medians-of-3 damp but do not eliminate that. The
  DEFENSIBLE claim is the shape (ratios ~2.0 vs DNF), not any millisecond.
- The growth test uses GC-quiesced timings and an exponent bound (see
  tests/test_growth.py); raw ratios near 3.0 flaked once during development,
  which is why the oracle asserts an exponent < 1.4 instead (linear ≈ 1).
- `re`'s DNF cells are timed out, not extrapolated; its true cost could be
  far higher (or astronomically lower on inputs where its optimizations
  fire — e.g. matching subjects, which we deliberately exclude).
- Pure-Python throughput (~7–17 µs/char for pikevm here) says nothing about
  a C implementation of the same algorithm; RE2 exists. The comparison that
  matters is between engines under identical interpreter constraints.
- The corpus generator explores the documented subset broadly but is still
  a finite probe; parity claims extend exactly as far as 20k+ generated and
  hand-probed cases carry them.
