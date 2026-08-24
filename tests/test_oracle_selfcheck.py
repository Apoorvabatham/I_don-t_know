"""The oracle must be able to detect wrongness, not just confirm agreement.

These tests validate the harness itself:
  1. generator determinism (same seed -> identical corpus)
  2. coverage floors (every feature bucket actually exercised)
  3. the comparator catches a planted bug (off-by-one span)
  4. re-vs-re sanity through the normalization path
  5. every bedrock EDGE_CASE pattern compiles under CPython re
"""

import re as re_ref
import unittest

from tests.gen_corpus import generate, EDGE_CASES, BUCKETS
from tests.compare import run_ref, compare_case


class TestGeneratorDeterminism(unittest.TestCase):
    def test_same_seed_identical_corpus(self):
        a = generate(20260824, 300)
        b = generate(20260824, 300)
        self.assertEqual(a[0], b[0])
        self.assertEqual(a[1], b[1])

    def test_different_seed_different_corpus(self):
        a, _ = generate(1, 200)
        b, _ = generate(2, 200)
        self.assertNotEqual(
            [(c["pattern"], c["subject"]) for c in a],
            [(c["pattern"], c["subject"]) for c in b],
        )


class TestCoverage(unittest.TestCase):
    def test_every_bucket_well_represented(self):
        _, cov = generate(7, 3000)
        # Floor is deliberately conservative at Phase 1; raise with evidence,
        # never lower to make a run pass.
        for bucket in BUCKETS:
            self.assertGreaterEqual(
                cov[bucket], 50, f"bucket {bucket} under-covered: {cov[bucket]}"
            )


class TestComparatorDetectsWrongness(unittest.TestCase):
    CASES = [
        {"pattern": "(a|ab)(c|bcd)(d*)", "subject": "abcd"},
        {"pattern": r"\w+\s\w+", "subject": "foo bar"},
        {"pattern": "a{2,3}", "subject": "aaaa"},
    ]

    def test_planted_off_by_one_span_is_caught(self):
        for case in self.CASES:
            ref = run_ref(case)
            broken = {k: v for k, v in ref.items()}
            # plant: shift group-0 end by one on the search result
            s = broken["search"]
            if s is not None:
                shifted = list(s)
                shifted[0] = (s[0][0], s[0][1] + 1)
                broken["search"] = tuple(shifted)
                diffs = compare_case(ref, broken)
                self.assertTrue(
                    any(d[0] == "search" for d in diffs),
                    f"comparator missed planted span bug on {case}",
                )

    def test_planted_group_count_is_caught(self):
        case = self.CASES[0]
        ref = run_ref(case)
        broken = dict(ref)
        broken["ngroups"] = ref["ngroups"] + 1
        diffs = compare_case(ref, broken)
        self.assertTrue(any(d[0] == "ngroups" for d in diffs))

    def test_re_against_itself_agrees(self):
        for case in self.CASES:
            ref = run_ref(case)
            self.assertEqual(compare_case(ref, ref), [])


class TestBedrockCasesAreValid(unittest.TestCase):
    def test_every_edge_pattern_compiles_under_re(self):
        for pat, inputs in EDGE_CASES:
            try:
                compiled = re_ref.compile(pat)
            except re_ref.error as e:
                self.fail(f"bedrock pattern {pat!r} invalid under re: {e}")
            for s in inputs:
                compiled.search(s)  # must not raise

    def test_edge_volume_present_in_generated_corpus(self):
        cases, _ = generate(11, 100)
        n_edge = sum(1 for c in cases if c["bucket"] == "edge")
        self.assertGreaterEqual(n_edge, len(EDGE_CASES) * 2 - 1)


if __name__ == "__main__":
    unittest.main()
