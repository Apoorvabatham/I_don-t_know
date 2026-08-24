"""Charter done-criterion #1: differential suite, nanoregex vs CPython re.

Selects the engine under test via env NANOREGEX_ENGINE (default 'pikevm') so
M2 (backtracker) and M3 (pike VM) can be driven through the same oracle.

RED at Phase 1 by construction: every case reports EngineUnavailable against
the stub. Green means: >=2000 seeded cases across all APIs with zero
unexplained mismatches for the selected engine.
"""

import os
import unittest

from tests.gen_corpus import generate
from tests.compare import (
    check_one,
    fmt_mismatch,
    EngineUnavailable,
)

ENGINE = os.environ.get("NANOREGEX_ENGINE", "pikevm")

# (seed, n_cases) — total generated volume must satisfy charter's >=2000.
SEEDS = [(20260824, 700), (1, 500), (2, 500), (3, 400), (4, 400)]
TOTAL = sum(n for _, n in SEEDS)
assert TOTAL >= 2000

MAX_REPORTED = 5


class TestDifferentialVsRe(unittest.TestCase):
    def _run_seed(self, seed, n_cases):
        cases, coverage = generate(seed, n_cases)
        bad = []
        unavailable = 0
        whitelisted = 0
        for c in cases:
            status, detail = check_one(c, engine=ENGINE)
            if status == "ok":
                continue
            if status == "whitelisted":
                whitelisted += 1
                bad.append((c, detail))
            elif status == "unavailable":
                unavailable += 1
                if unavailable == 1:
                    bad.append((c, [("unavailable", "re ok", "nanoregex stub")]))
            else:
                bad.append((c, detail))
        return cases, bad, unavailable, whitelisted

    def test_total_volume_meets_charter(self):
        self.assertGreaterEqual(TOTAL, 2000)

    def test_differential_all_seeds(self):
        total_bad = []
        any_unavailable = 0
        total_whitelisted = 0
        for seed, n in SEEDS:
            cases, bad, unavailable, whitelisted = self._run_seed(seed, n)
            self.assertEqual(
                len(cases), n, f"generator volume broken for seed {seed}"
            )
            total_bad.extend((seed,) + b for b in bad[:MAX_REPORTED])
            any_unavailable += unavailable
            total_whitelisted += whitelisted
        msg_parts = [f"engine={ENGINE}"]
        if any_unavailable:
            msg_parts.append(f"{any_unavailable} cases hit stub/unimplemented engine")
        if total_whitelisted:
            msg_parts.append(f"{total_whitelisted} whitelisted divergences (must each "
                             f"have a written reason; see tests/compare.py WHITELIST)")
        detail_lines = [
            f"seed {b[0]}: " + fmt_mismatch(b[1], b[2]) for b in total_bad[:MAX_REPORTED]
        ]
        self.assertEqual(
            len(total_bad), 0,
            "; ".join(msg_parts) + "\n" + "\n".join(detail_lines),
        )


if __name__ == "__main__":
    unittest.main()
