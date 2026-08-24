"""M5 hardening oracle: degenerate-pattern guards and first-contact errors.

Guards exist so a hostile or careless caller gets a precise nanoregex
error instead of a RecursionError, a multi-GB allocation, or a hang:
  * nesting depth cap (parser recursion + matcher split-walk recursion)
  * program-size cap (bounded {m,n} expansion)
Both caps are documented divergences from CPython re (which accepts
deeper nesting and larger expansions); they are charter M5 scope.
"""

import unittest

from nanoregex import (
    NanoregexParseError,
    UnsupportedPattern,
    compile as ncompile,
)

from tests.gen_corpus import EDGE_CASES


class TestDepthGuard(unittest.TestCase):
    def test_deep_nesting_rejected_with_position(self):
        pat = "(" * 500 + "a" + ")" * 500
        with self.assertRaises(NanoregexParseError) as ctx:
            ncompile(pat)
        self.assertIn("deep", str(ctx.exception))

    def test_reasonable_nesting_still_works(self):
        pat = "(?:" * 50 + "a" + ")" * 50
        compiled = ncompile(pat)
        self.assertEqual(compiled.groups, 0)


class TestProgramSizeGuard(unittest.TestCase):
    def test_huge_counted_expansion_rejected(self):
        # {m,n} expands to copies; 20000-instruction cap must fire long
        # before any allocation blowup
        with self.assertRaises(UnsupportedPattern):
            ncompile("a{30000}")

    def test_nested_counted_expansion_rejected(self):
        with self.assertRaises(UnsupportedPattern):
            ncompile("(?:a{200}){200}")

    def test_moderate_counts_fine(self):
        compiled = ncompile("a{100}")
        m = compiled.fullmatch("a" * 100)
        self.assertIsNotNone(m)


class TestDegenerateEdges(unittest.TestCase):
    def test_empty_and_whitespace_patterns(self):
        for eng in ("pikevm", "backtracker"):
            p = ncompile("", engine=eng)
            self.assertEqual(p.search("").span(), (0, 0))
            self.assertEqual(p.findall("ab"), ["", "", ""])
            ws = ncompile(r"[ \t]+", engine=eng)
            self.assertEqual(ws.findall("a b\tc"), [" ", "\t"])

    def test_unmatched_group_is_none_spans(self):
        for eng in ("pikevm", "backtracker"):
            m = ncompile("(a)|(b)", engine=eng).search("b")
            self.assertEqual(m.span(1), (-1, -1))
            self.assertIsNone(m.group(1))
            self.assertEqual(m.group(2), "b")

    def test_all_bedrock_cases_both_engines_quick(self):
        # belt-and-braces: no bedrock case may hang or crash either engine
        # (the differential suite checks parity; this checks liveness)
        for pat, inputs in EDGE_CASES:
            for s in inputs:
                for eng in ("pikevm", "backtracker"):
                    ncompile(pat, engine=eng).search(s)


if __name__ == "__main__":
    unittest.main()
