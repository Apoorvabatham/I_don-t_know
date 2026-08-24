"""Growth assertions in the oracle (charter milestone M4).

The benchmark lab REPORTS growth curves; this suite ASSERTS them, so a
regression that quietly turns the Pike VM quadratic fails the build
instead of waiting for a human to notice a slow benchmark.

Bounded for CI safety: three sizes (8k -> 32k), pikevm only, single
repeat. The full 128k schedule with all engines belongs to
bench/run_bench.py (charter criterion #3).

Noise policy: wall-clock timings on a shared laptop jitter (a GC pause
or WSL2 scheduling hiccup can double one sample). Raw doubling RATIOS
therefore flake near any interesting threshold; instead we fit the
growth EXPONENT log(t_max/t_min)/log(size_max/size_min) with GC quiesced.
Linear measures ~0.9-1.2 here; quadratic measures ~2.0. The bound 1.4 is
far from both. If this ever fails, rerun once on an idle machine before
investigating — and never raise the bound silently; journal it if it
must move.
"""

import gc
import math
import unittest

from bench.evil import EVIL_PATTERNS
from bench.run_bench import CaseTimeout, timed_call

from nanoregex import compile as ncompile

SIZES = [8000, 16000, 32000]
TIMEOUT_S = 15.0
MAX_EXPONENT = 1.4


class TestPikeVMLinearGrowth(unittest.TestCase):
    def test_every_evil_pattern_stays_linear(self):
        for ep in EVIL_PATTERNS:
            with self.subTest(pattern=ep["pattern"]):
                subject_fn = ep["subject"]
                search = ncompile(ep["pattern"], engine="pikevm").search
                times = []
                gc_was = gc.isenabled()
                gc.disable()
                try:
                    for n in SIZES:
                        subj = subject_fn(n)
                        try:
                            dt = timed_call(lambda: search(subj), TIMEOUT_S)
                        except CaseTimeout:
                            self.fail(
                                f"{ep['id']} exceeded {TIMEOUT_S}s at "
                                f"n={n} — Pike VM lost linearity")
                        times.append(dt)
                finally:
                    if gc_was:
                        gc.enable()
                span = SIZES[-1] / SIZES[0]
                exponent = math.log(times[-1] / times[0]) / math.log(span)
                self.assertLess(
                    exponent, MAX_EXPONENT,
                    f"{ep['id']} {ep['pattern']!r}: growth exponent "
                    f"{exponent:.2f} >= {MAX_EXPONENT} (times={times})")

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

