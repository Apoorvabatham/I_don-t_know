"""M1 oracle: parser correctness.

Layers:
  1. Roundtrip property over the ENTIRE generated corpus:
     parse(print(parse(p))) == parse(p). The printer is the inverse of the
     parser; any drift breaks this loudly and reproducibly.
  2. Cross-engine invariant: nanoregex parses every pattern CPython re
     accepts (over the subset corpus) AND counts capturing groups
     identically — ngroups parity on thousands of generated patterns.
  3. Hand-written AST shape checks (structure, not just acceptance).
  4. Malformed patterns raise NanoregexParseError with a position.
  5. Out-of-subset extensions raise UnsupportedPattern (charter NOT-doing).

The differential matcher suite stays red-vs-stub until M2; nothing here
weakens that (matching still raises NotImplementedError).
"""

import re as re_ref
import unittest

from nanoregex import (
    NanoregexParseError,
    UnsupportedPattern,
    compile as ncompile,
)
from nanoregex.ast_nodes import (
    Alt, Anchor, Cat, CharClass, Dot, Group, Lit, Rep, Shorthand,
)
from nanoregex.parser import parse
from nanoregex.printer import print_pattern

from tests.gen_corpus import generate

ROUNDTRIP_SEEDS = [(20260824, 700), (1, 500), (2, 500), (3, 400), (4, 400)]


class TestRoundtripProperty(unittest.TestCase):
    def test_corpus_roundtrips_exactly(self):
        total = 0
        for seed, n in ROUNDTRIP_SEEDS:
            cases, _ = generate(seed, n)
            for c in cases:
                ast, ng = parse(c["pattern"])
                printed = print_pattern(ast)
                ast2, ng2 = parse(printed)
                self.assertEqual(
                    (ast, ng), (ast2, ng2),
                    f"roundtrip broke for {c['pattern']!r} -> {printed!r}")
                total += 1
        self.assertGreaterEqual(total, 2000)

    def test_hand_quirks_roundtrip(self):
        # probed CPython quirks the generator never emits; '{2}' is absent
        # because it is REJECTED (nothing to repeat) — covered in malformed.
        for pat in [r"a{", "a{2,", "}", "]", "a{,3}", "(?:a|)",
                    "|a", "a||b", "[^]]", "[]]", "[-a]", "[a-]", r"[\]\-]"]:
            ast, _ = parse(pat)
            printed = print_pattern(ast)
            self.assertEqual(
                parse(pat), parse(printed),
                f"quirk pattern {pat!r} -> {printed!r} not stable")


class TestGroupCountParity(unittest.TestCase):
    def test_ngroups_matches_re_on_corpus(self):
        checked = 0
        for seed, n in ROUNDTRIP_SEEDS[:2]:
            cases, _ = generate(seed, n)
            for c in cases:
                expected = re_ref.compile(c["pattern"]).groups
                _, ng = parse(c["pattern"])
                self.assertEqual(ng, expected,
                                 f"group count differs on {c['pattern']!r}")
                checked += 1
        self.assertGreaterEqual(checked, 1000)


class TestAstShapes(unittest.TestCase):
    def test_alternation_with_groups(self):
        ast, ng = parse("(a|b)c*")
        self.assertEqual(ng, 1)
        self.assertIsInstance(ast, Cat)
        g, rep = ast.parts
        self.assertEqual(g, Group(1, Alt([Lit("a"), Lit("b")])))
        self.assertEqual(rep, Rep(Lit("c"), 0, None, False))

    def test_lazy_counted_repeat(self):
        # (?:...) is its own Group node wrapping the shorthand
        ast, ng = parse(r"(?:\d){2,4}?")
        self.assertEqual((ast.body, ast.min, ast.max, ast.lazy),
                         (Group(None, Shorthand("d")), 2, 4, True))
        self.assertEqual(ng, 0)

    def test_nested_capture_numbering(self):
        _, ng = parse("((a)(b))(c)")
        self.assertEqual(ng, 4)
        ast, _ = parse("((a)(b))")
        outer = ast
        self.assertEqual(outer.index, 1)
        inner_parts = outer.body.parts
        self.assertEqual(inner_parts[0].index, 2)
        self.assertEqual(inner_parts[1].index, 3)

    def test_negated_class_with_range_and_short(self):
        ast, _ = parse(r"[^\dab-c]")
        self.assertTrue(ast.negated)
        self.assertEqual(ast.items,
                         [("short", "d"), ("ch", "a"), ("range", "b", "c")])

    def test_empty_pattern_and_branches(self):
        self.assertEqual(parse("")[0], Cat([]))
        ast, ng = parse("(|a)")          # capturing group wrapping the alt
        self.assertEqual((ng, ast.index), (1, 1))
        self.assertEqual(ast.body.branches[0], Cat([]))


class TestMalformedPatterns(unittest.TestCase):
    CASES = [
        ("[", "unterminated"),
        ("[]", "unterminated"),
        ("[^]", "unterminated"),
        ("(", "unterminated"),
        ("(a", "unterminated"),
        (")", "unbalanced"),
        ("a)", "unbalanced"),
        ("*a", "nothing to repeat"),
        ("+a", "nothing to repeat"),
        ("?a", "nothing to repeat"),
        ("{2}", "nothing to repeat"),
        ("a**", "multiple repeat"),
        ("a*+", "multiple repeat"),
        ("a??*", "multiple repeat"),
        ("a{2,1}", "min repeat greater than max"),
        ("[z-a]", "bad character range"),
        (r"[\d-a]", "bad character range"),
        ("\\", "backslash"),
        (r"\x4", "incomplete escape"),
        ("(?", "group extension"),
    ]

    def test_malformed_raise_parse_error_with_position(self):
        for pat, why in self.CASES:
            with self.assertRaises(NanoregexParseError,
                                   msg=f"{pat!r} ({why})"):
                try:
                    parse(pat)
                except NanoregexParseError as e:
                    self.assertIn("position", str(e))
                    raise


class TestUnsupportedExtensions(unittest.TestCase):
    CASES = [
        "(?=a)", "(?!a)", "(?<=a)b", "(?<!a)b",
        "(?P<name>a)", "(?P=name)", "(?i)a", "(?x) a", "(?#comment)a",
        r"(a)\1", r"\2", r"[a\b]",
        r"\A", r"\Z", r"\U00000041", r"\N{LATIN SMALL LETTER A}",
        r"\012",
    ]

    def test_out_of_subset_raises_unsupported(self):
        for pat in self.CASES:
            with self.assertRaises(UnsupportedPattern,
                                   msg=f"{pat!r} should be rejected"):
                ncompile(pat)

    def test_noncapturing_group_is_supported(self):
        ncompile("(?:abc)")          # must NOT raise


class TestCompileSurface(unittest.TestCase):
    def test_compile_reports_groups_and_pretty(self):
        pat = ncompile(r"(a)\db")
        self.assertEqual(pat.groups, 1)
        self.assertEqual(pat.pretty(), r"(a)\db")

    def test_compile_rejects_unknown_engine(self):
        with self.assertRaises(ValueError):
            ncompile("a", engine="turbo")

    def test_both_engines_match(self):
        # retired the Phase-1 'matching still stubbed' assertion: M2/M3
        # replaced the stubs, so the contract is now that BOTH engines
        # answer through the same compile() surface.
        for eng in ("pikevm", "backtracker"):
            m = ncompile("a", engine=eng).search("bab")
            self.assertEqual(m.span(), (1, 2), eng)


if __name__ == "__main__":
    unittest.main()
