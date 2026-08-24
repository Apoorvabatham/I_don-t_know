#!/usr/bin/env python3
"""Standalone large-scale differential sweep: nanoregex vs CPython re.

Charter done-criterion #2:
    python3 tools/fuzz_diff.py --cases 5000   ->  exit 0, 0 mismatches

Independent of the unittest suite: draws its own seed, prints it, runs the
generated corpus through tests.compare.check_one (same comparator, so a
mismatch here and a suite failure are comparable events).

Exit codes:
    0  clean — every case agreed (or was whitelisted with a reason)
    1  at least one unexplained mismatch (engine bug or oracle gap: investigate)
    2  engine unavailable — stub raises NotImplementedError / UnsupportedPattern
       (expected red during Phase 1; red is this tool working as designed)
    3  harness error (bad args, generator failure)

Examples:
    python3 tools/fuzz_diff.py --cases 5000 --seed 20260824 --engine pikevm
    python3 tools/fuzz_diff.py --cases 2000 --seed 7 --engine backtracker
"""

import argparse
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.gen_corpus import generate          # noqa: E402
from tests.compare import check_one            # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", type=int, default=5000,
                    help="corpus size incl. bedrock edge cases (default 5000)")
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed; default = fresh entropy, printed either way")
    ap.add_argument("--engine", default="pikevm",
                    choices=["pikevm", "backtracker"],
                    help="nanoregex backend under test")
    ap.add_argument("--timeout", type=float, default=None,
                    help="per-case seconds; default = tests.compare value")
    args = ap.parse_args(argv)

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(2**31)
    print(f"fuzz_diff: cases={args.cases} seed={seed} engine={args.engine}", flush=True)

    if args.timeout is not None:
        import tests.compare as _cmp
        _cmp.PER_CASE_TIMEOUT_S = args.timeout

    try:
        cases, coverage = generate(seed, args.cases)
    except Exception as e:  # noqa: BLE001 - report and exit, never traceback-dump
        print(f"harness error in generator: {e!r}", file=sys.stderr)
        return 3

    n = {"ok": 0, "whitelisted": 0, "unavailable": 0, "mismatch": 0}
    first_mismatches = []
    first_unavailable = None
    for i, case in enumerate(cases):
        status, detail = check_one(case, engine=args.engine)
        n[status] += 1
        if status == "mismatch" and len(first_mismatches) < 10:
            from tests.compare import fmt_mismatch
            first_mismatches.append(fmt_mismatch(case, detail))
        elif status == "unavailable" and first_unavailable is None:
            first_unavailable = case
        if (i + 1) % 1000 == 0:
            print(f"  ... {i + 1}/{len(cases)} "
                  f"(ok={n['ok']} mismatch={n['mismatch']} "
                  f"unavail={n['unavailable']})", flush=True)

    cov_line = " ".join(f"{b}={c}" for b, c in sorted(coverage.items()) if c)
    print(f"coverage (generated buckets): {cov_line}")
    print(f"result: ok={n['ok']} whitelisted={n['whitelisted']} "
          f"mismatch={n['mismatch']} unavailable={n['unavailable']}")

    for m in first_mismatches:
        print("MISMATCH:\n" + m, file=sys.stderr)
    if n["mismatch"]:
        print(f"FAIL: {n['mismatch']} unexplained mismatch(es); seed={seed}",
              file=sys.stderr)
        return 1
    if n["unavailable"]:
        print(f"RED (expected at Phase 1): engine={args.engine} unavailable "
              f"on {n['unavailable']} cases; e.g. "
              f"pattern={first_unavailable['pattern']!r} "
              f"subject={first_unavailable['subject']!r}")
        return 2
    note = ""
    if n["whitelisted"]:
        note = f" ({n['whitelisted']} whitelisted divergences, see tests/compare.py)"
    print(f"PASS: 0 mismatches across {len(cases)} cases{note}; seed={seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
