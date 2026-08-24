#!/usr/bin/env python3
"""Adversarial benchmark lab: what does linear-time matching actually buy?

Races CPython ``re`` and nanoregex's engines over the five charter evil
patterns (bench/evil.py) at doubling input sizes, with a hard per-case wall
timeout (SIGALRM). Writes results/bench.md + results/bench.csv.

Charter done-criterion #3 this script implements:
  * Pike VM completes EVERY tested size with median doubling-growth ratio < 3.0
  * stdlib re records DNF (10 s per-case timeout) on at least 3 of the 5
    (an observation the table reports; if reality disagrees, the table wins —
    that would itself be the finding)

Exit code: nonzero iff a REQUIRED-green cell fails, i.e. the pikevm engine is
missing/incomplete or its growth ratio violates < 3.0. `re` DNF and
backtracker blowups are legitimate measured results (half the point of the
lab), never failures. Red at Phase 1 = pikevm still a stub.

Usage:
    python3 bench/run_bench.py                     # full charter run
    python3 bench/run_bench.py --smoke             # bounded ~60s (make check)
    python3 bench/run_bench.py --engines re,pikevm --sizes 1000,2000

Timing notes: each cell is --repeats independently-timed runs of
pat.search(subject); the table reports their median. Growth ratio for a
pattern = median over consecutive size pairs of median_time(2n)/median_time(n);
linear time gives ~2.0, exponential >> 10.
Timeout machinery deliberately lives here rather than being imported from
tests/compare.py: measurement has different needs (per-repeat timing,
float budgets) than pass/fail comparison, and keeping them separate keeps
the oracle and the lab independently reviewable.
"""

import argparse
import csv
import os
import platform
import signal
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import re as re_ref          # noqa: E402

from bench.evil import EVIL_PATTERNS, FULL_SIZES   # noqa: E402


class CaseTimeout(Exception):
    """A single timed call exceeded its budget."""


def timed_call(fn, seconds):
    """Run fn() once under a SIGALRM budget. Returns elapsed seconds."""
    def _handler(signum, frame):
        raise CaseTimeout(f"exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    t0 = time.perf_counter()
    try:
        fn()
        return time.perf_counter() - t0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def make_matcher(engine, pattern):
    """Compile one pattern for one engine. Returns search callable or None.

    None means 'unavailable': either an unimplemented engine (raises at
    CALL time since M1, hence the probe) or an out-of-subset rejection.
    """
    if engine == "re":
        return re_ref.compile(pattern).search
    import nanoregex
    try:
        pat = nanoregex.compile(pattern, engine=engine)
        pat.search("x")            # probe: stub engines raise here
    except NotImplementedError:
        return None
    except nanoregex.UnsupportedPattern as e:
        print(f"WARNING: {engine} rejects charter pattern {pattern!r}: {e}",
              file=sys.stderr)
        return None
    return pat.search


def measure(search, subject, timeout_s, repeats):
    """Time one cell: list of per-run seconds, or ('dnf'|'unavailable')."""
    if search is None:
        return "unavailable", []
    times = []
    for _ in range(repeats):
        try:
            times.append(timed_call(lambda: search(subject), timeout_s))
        except CaseTimeout:
            return "dnf", []
    return "ok", times


def growth_ratios(median_by_size):
    """Consecutive doubling ratios from {size: median_seconds} (ok sizes only)."""
    sizes = sorted(s for s, m in median_by_size.items() if m is not None)
    return [median_by_size[b] / median_by_size[a]
            for a, b in zip(sizes, sizes[1:])]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engines", default="re,pikevm,backtracker",
                    help="comma list from: re,pikevm,backtracker")
    ap.add_argument("--sizes", default=None,
                    help=f"comma list; default full charter schedule "
                         f"({FULL_SIZES[0]}..{FULL_SIZES[-1]})")
    ap.add_argument("--timeout", type=float, default=10.0,
                    help="per-case seconds before DNF (default 10)")
    ap.add_argument("--repeats", type=int, default=3,
                    help="timed runs per cell, median reported")
    ap.add_argument("--smoke", action="store_true",
                    help="bounded smoke run for make check (~60s): small "
                         "sizes, short timeout, 1 repeat")
    args = ap.parse_args(argv)

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    if args.smoke:
        sizes = FULL_SIZES[:3]
        timeout_s, repeats = min(args.timeout, 2.0), 1
    else:
        sizes = ([int(x) for x in args.sizes.split(",")] if args.sizes
                 else list(FULL_SIZES))
        timeout_s, repeats = args.timeout, max(1, args.repeats)

    csv_rows = []              # raw per-run rows -> bench.csv
    results = {}               # (engine, pid, n) -> (status, median|None)
    started = time.time()

    for ep in EVIL_PATTERNS:
        subjects = {n: ep["subject"](n) for n in sizes}
        for engine in engines:
            search = make_matcher(engine, ep["pattern"])
            for n in sizes:
                status, times = measure(search, subjects[n], timeout_s, repeats)
                med = statistics.median(times) if status == "ok" else None
                results[(engine, ep["id"], n)] = (status, med)
                for rep, t in enumerate(times):
                    csv_rows.append({
                        "engine": engine, "pattern": ep["id"],
                        "regex": ep["pattern"], "size": n, "repeat": rep,
                        "status": status, "time_s": f"{t:.6f}",
                    })
                if status != "ok" or times[-1] > 0.05:
                    shown = {"dnf": "DNF", "unavailable": "-"}[status] \
                        if status != "ok" else f"{times[-1] * 1000:.0f} ms"
                    print(f"  {ep['id']} {ep['pattern']:<12} {engine:<12} "
                          f"n={n:>7}  {shown}", flush=True)

    write_outputs(csv_rows, results, engines, sizes, timeout_s, repeats, started)

    # Charter verdicts — programmatic, no judgement calls.
    failures = []
    if "pikevm" in engines:
        for ep in EVIL_PATTERNS:
            cells = {n: results.get(("pikevm", ep["id"], n)) for n in sizes}
            missing = [n for n, v in cells.items() if v is None or v[0] != "ok"]
            gr = growth_ratios({n: v[1] for n, v in cells.items() if v})
            med_gr = statistics.median(gr) if gr else None
            if missing:
                failures.append(
                    f"pikevm incomplete on {ep['id']} at sizes {missing}")
            elif med_gr is None or med_gr >= 3.0:
                failures.append(
                    f"pikevm growth on {ep['id']}: median ratio {med_gr}")
            print(f"growth {ep['id']}: ratios="
                  f"{['%.2f' % r for r in gr]} median={med_gr}")
        dnf_count = sum(
            1 for ep in EVIL_PATTERNS
            if any(results.get(("re", ep["id"], n), ("ok",))[0] == "dnf"
                   for n in sizes))
        print(f"stdlib re DNF on {dnf_count}/5 evil patterns "
              f"(charter expectation: >=3)")
        if failures:
            print("BENCH RED:\n  " + "\n  ".join(failures), file=sys.stderr)
            return 1
        print("BENCH GREEN: pikevm completed every size on every pattern.")
        return 0

    print("BENCH: ran without pikevm; no charter verdict computed.")
    return 0


def write_outputs(csv_rows, results, engines, sizes, timeout_s, repeats, started):
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    csv_path = os.path.join(ROOT, "results", "bench.csv")
    md_path = os.path.join(ROOT, "results", "bench.md")

    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "engine", "pattern", "regex", "size", "repeat", "status", "time_s"])
        w.writeheader()
        w.writerows(csv_rows)

    lines = [
        "# nanoregex adversarial benchmark",
        "",
        f"- generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}"
        f" (run took {time.time() - started:.0f}s)",
        f"- python {platform.python_version()} on {platform.platform()}",
        f"- per-case timeout {timeout_s}s, median of {repeats} run(s), "
        f"sizes {sizes[0]}..{sizes[-1]} ({len(sizes)} doublings)"
        + (", SMOKE subset" if len(sizes) < len(FULL_SIZES)
           else ", full charter schedule"),
        "- subject construction: worst-case non-matching inputs "
        "(see bench/evil.py)",
        "",
    ]
    for ep in EVIL_PATTERNS:
        lines += [f"## {ep['id']} `{ep['pattern']}` — {ep['note']}", "",
                  "| size | " + " | ".join(f"{e} median" for e in engines) + " |",
                  "|" + "---|" * (len(engines) + 1)]
        for n in sizes:
            cells = []
            for e in engines:
                st, med = results.get((e, ep["id"], n), ("missing", None))
                cells.append("DNF" if st == "dnf"
                             else ("-" if st != "ok" else f"{med * 1000:.1f} ms"))
            lines.append(f"| {n} | " + " | ".join(cells) + " |")
        gr_bits = []
        for e in engines:
            med_map = {n: results[(e, ep["id"], n)][1] for n in sizes
                       if results.get((e, ep["id"], n), (None, None))[1]}
            gr = growth_ratios(med_map)
            if gr:
                gr_bits.append(f"{e} median doubling ratio "
                               f"{statistics.median(gr):.2f}")
        if gr_bits:
            lines += ["", "growth — " + "; ".join(gr_bits)]
        lines.append("")
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {csv_path}\nwrote {md_path}")


if __name__ == "__main__":
    sys.exit(main())
