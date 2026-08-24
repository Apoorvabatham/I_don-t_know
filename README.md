# nanoregex

A clean-room regular-expression engine in pure Python (zero dependencies,
no C extensions), plus an adversarial benchmark lab that measures what
linear-time matching is actually worth.

Two independent matchers live behind one API:

- **`pikevm`** (default) — a Thompson-NFA / breadth-first Pike VM.
  Runs in time linear in the input length. On the classic
  catastrophic-backtracking patterns it finishes at input sizes where
  CPython's `re` exceeds a 10-second budget — measured, not folklore
  (see [RESULTS.md](RESULTS.md)).
- **`backtracker`** — an iterative backtracking VM with explicit
  choice points: faithful exponential semantics, used as the control
  group and as a reference for capture edge cases.

Both engines pass a differential test suite of thousands of seeded cases
against CPython's `re` with exact agreement — including capture-group
spans, greedy/lazy priority, and `findall`/`finditer` zero-width rules.

## Quickstart

```bash
git clone https://github.com/Apoorvabatham/I_don-t_know.git
cd I_don-t_know

make check          # byte-compile + full test suite + ~60s bench smoke
```

A first demo in code:

```python
>>> import re, time
>>> from nanoregex import compile
>>>
>>> evil = "a" * 100000 + "b"        # non-matching worst case
>>>
>>> t0 = time.perf_counter()
>>> m = compile(r"^(a+)+$", engine="pikevm").search(evil)
>>> f"{time.perf_counter()-t0:.2f}s, match={m is not None}"
'1.42s, match=False'                 # your number will differ; it is linear
>>>
>>> t0 = time.perf_counter()
>>> re.search(r"^(a+)+$", "a" * 350 + "b")   # 350 chars is enough for re
# ...this call was still running after 20s when we cut it loose. Ctrl-C.
```

The benchmark lab:

```bash
python3 bench/run_bench.py           # full charter run (~14 min; DNF cells burn their timeout)
python3 bench/run_bench.py --smoke   # bounded subset used by make check
```

Writes `results/bench.md` (human table + growth ratios) and
`results/bench.csv` (raw timings). Numbers and their caveats:
[RESULTS.md](RESULTS.md).

The differential oracle:

```bash
python3 -m unittest discover -s tests -q     # full suite incl. 2500 differential cases
python3 tools/fuzz_diff.py --cases 5000      # independent seeded sweep; prints its seed
python3 tools/fuzz_diff.py --cases 2000 --seed 7 --engine backtracker
```

## Documented syntax subset

Literals; `.` (never matches `\n`); character classes `[...]` with ranges,
negation, escapes (`\]`, `\\`, `\^`) and shorthand members (`[\d]`);
`\d \w \s \D \W \S`; anchors `^ $ \b \B`; groups `(...)` and `(?:...)`;
alternation `|`; greedy and lazy quantifiers `* + ? {m} {m,} {m,n}` and
`{,n}`; literal-escape sequences (`\t`, `\x41`, `\.`, `\\`, ...).

CPython-quirk parity is deliberate and tested: `$` matches just before a
trailing newline; a `]` in first position inside a class is a literal;
malformed braces fall back to literal `{` (`a{2` matches `"a{2"`); `\B`
never matches an empty subject; unknown escapes of ASCII letters are
rejected (`\q` raises, like CPython — only punctuation may be escaped);
unmatched groups report `(-1, -1)` spans.

## What does NOT work (by design)

- Lookaround `(?!...)`, backreferences `\1`, named groups, inline flags,
  POSIX classes — anything whose semantics require backtracking or config
  (that exclusion is what makes a linear-time engine possible).
- Unicode: ASCII inputs only.
- No `sub`/`split`, no drop-in `import nanoregex as re`.
- Degenerate patterns are rejected with `UnsupportedPattern`: bounded
  repeats expanding beyond 20,000 program instructions (`a{30000}`) or
  nesting deeper than 120 levels.
- The Pike VM resolves capture groups lazily on first access; on huge
  grouped matches against adversarial patterns, reading `.group(1)` can be
  expensive (span-only queries never are). This trade-off is why the whole
  benchmark lab runs capture-free.
- Pure Python forever: expect ~5–20 µs per character for pikevm on this
  class of patterns. The claim is linearity, not absolute speed.

## Layout

    nanoregex/       lexer -> parser -> AST -> compiler -> {backtracker, pikevm}
    tests/           corpus generator, differential oracle, self-checks, growth assertions
    tools/           fuzz_diff.py — standalone seeded sweep vs stdlib re
    bench/           evil.py (the five charter patterns) + run_bench.py
    results/         bench output (generated, gitignored)

## Status / honest notes

Built in one autonomous 24-hour session; milestones M1–M5 all green at
~T+4h of wall time. See REPORT.md for the close-out (what shipped, what
was cut, where time went). Known sharp edges are listed above rather than
hidden: if you find a pattern in the documented subset where nanoregex
disagrees with CPython `re`, that is a bug — the whitelist policy in
`tests/compare.py` is empty by design.
