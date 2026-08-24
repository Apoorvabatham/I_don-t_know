"""Growth assertions in the oracle (charter milestone M4).

The benchmark lab REPORTS growth curves; this suite ASSERTS them, so a
regression that quietly turns the Pike VM quadratic fails the build
instead of waiting for a human to notice a slow benchmark.

Bounded for CI safety: three doubling sizes (8k -> 32k), pikevm only,
single repeat. The full 128k schedule with all engines belongs to
bench/run_bench.py (charter criterion #3); here we only need enough
resolution to catch polynomial drift: linear time gives consecutive
doubling ratios ~2.0, and the assertion threshold is 3.0 — a quadratic
engine blows past it immediately (t(2n)/t(n) ~ 4).

Timing-noise policy: ratios near the threshold would be flaky, so the
test asserts < 3.0 on the MEDIAN of two consecutive ratios per pattern.
If this ever fails spuriously on a loaded machine, rerun before
investigating — but never raise the threshold silently; document why in
the journal if it must move.
"""

import statistics
import unittest

from bench.evil import EVIL_PATTERNS
from bench.run_bench import CaseTimeout, timed_call

from nanoregex import compile as ncompile

SIZES = [8000, 16000, 32000]
TIMEOUT_S = 15.0
MAX_MEDIAN_RATIO = 3.0


class TestPikeVMLinearGrowth(unittest.TestCase):
    def test_every_evil_pattern_stays_linear(self):
        for ep in EVIL_PATTERNS:
            subject_fn = ep["subject"]
            compiled = ncompile(ep["pattern"], engine="pikevm")
            search = compiled.search
            times = []
            for n in SIZES:
                subj = subject_fn(n)
                try:
                    dt = timed_call(lambda: search(subj), TIMEOUT_S)
                except CaseTimeout:
                    self.fail(
                        f"{ep['id']} {ep['pattern']!r} exceeded "
                        f"{TIMEOUT_S}s at n={n} — Pike VM lost linearity")
                times.append(dt)
            ratios = [b / a for a, b in zip(times, times[1:])]
            med = statistics.median(ratios)
            self.assertLess(
                med, MAX_MEDIAN_RATIO,
                f"{ep['id']} {ep['pattern']!r}: median doubling ratio "
                f"{med:.2f} >= {MAX_MEDIAN_RATIO} (times={times})")

    def test_span_mode_matches_caps_mode_endpoints(self):
        # the lazy-capture design must not change WHO wins: overall span
        # from the cheap pass has to agree with the capture-resolution
        # pass on a nontrivial grouped pattern
        compiled = ncompile(r"(a|ab)(c|bcd)(d*)", engine="pikevm")
        m = compiled.search("abcd")
        self.assertEqual(m.span(0), (0, 4))
        self.assertEqual(m.group(1), "a")
        self.assertEqual(m.group(3), "")


if __name__ == "__main__":
    unittest.main()
