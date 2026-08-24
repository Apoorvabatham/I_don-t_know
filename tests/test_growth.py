"""Growth assertions in the oracle (charter milestone M4).

The benchmark lab REPORTS growth curves; this suite ASSERTS them, so a
regression that quietly turns the Pike VM quadratic fails the build
instead of waiting for a human to notice a slow benchmark.

Bounded for CI safety: three sizes (8k -> 32k), pikevm only, single
repeat. The full 128k schedule with all engines belongs to
bench/run_bench.py (charter criterion #3).

Noise policy: wall-clock timings on this WSL2 laptop carry occasional
multi-x outliers (a single 32k measurement jumped 3.4x once), so each
size is measured REPS times and the MINIMUM kept — the least-noise
estimator for microbenchmarks — after an untimed warmup pass, with GC
quiesced. We fit the growth EXPONENT log(t_max/t_min)/log(size_max/
size_min): linear measures ~0.9-1.3 here, quadratic ~2.0; the bound is
1.6. If this ever fails on an idle machine, investigate — never raise
the bound silently; journal it if it must move.
"""

import gc
import math
import unittest

from bench.evil import EVIL_PATTERNS
from bench.run_bench import CaseTimeout, timed_call

from nanoregex import compile as ncompile

SIZES = [8000, 16000, 32000]
REPS = 3
TIMEOUT_S = 15.0
MAX_EXPONENT = 1.6


class TestPikeVMLinearGrowth(unittest.TestCase):
    def test_every_evil_pattern_stays_linear(self):
        for ep in EVIL_PATTERNS:
            with self.subTest(pattern=ep["pattern"]):
                subject_fn = ep["subject"]
                search = ncompile(ep["pattern"], engine="pikevm").search
                subjects = {n: subject_fn(n) for n in SIZES}
                # warmup: exercise the engine once so first-call effects
                # (bytecode, caches) don't poison the smallest size
                search(subjects[SIZES[0]])
                times = []
                gc_was = gc.isenabled()
                gc.disable()
                try:
                    for n in SIZES:
                        best = None
                        for _ in range(REPS):
                            try:
                                dt = timed_call(
                                    lambda: search(subjects[n]), TIMEOUT_S)
                            except CaseTimeout:
                                self.fail(
                                    f"{ep['id']} exceeded {TIMEOUT_S}s at "
                                    f"n={n} — Pike VM lost linearity")
                            best = dt if best is None else min(best, dt)
                        times.append(best)
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

