"""Seeded generator of (pattern, input) pairs over nanoregex's documented subset.

This generator lives in tests/, NOT in the package under test: it builds
pattern STRINGS by construction (random AST -> independent serializer), so no
nanoregex code is involved in producing test cases. Both CPython ``re`` and
nanoregex must consume the same strings; agreement is behavioral only.

Determinism: everything flows from one ``random.Random(seed)``. Same seed ->
byte-identical corpus, forever.
"""

import random

# ---------------------------------------------------------------------------
# Generator-side AST. Deliberately independent of any parser implementation.
# ---------------------------------------------------------------------------

ALPHABETS = ["ab", "abc", "ab0", "a b", "aab", "ab_", "xy01", "a"]


class Node:
    pass


class Lit(Node):
    def __init__(self, ch):
        self.ch = ch


class Dot(Node):
    pass


class Class(Node):
    def __init__(self, items, negated):
        self.items = items  # list of ('ch', c) or ('range', lo, hi)
        self.negated = negated


class EscClass(Node):
    def __init__(self, kind):
        self.kind = kind  # one of d w s D W S


class Anchor(Node):
    def __init__(self, kind):
        self.kind = kind  # '^' '$' 'b' 'B'


class Group(Node):
    def __init__(self, idx, body):  # idx=None -> non-capturing
        self.idx = idx
        self.body = body


class Alt(Node):
    def __init__(self, branches):
        self.branches = branches


class Cat(Node):
    def __init__(self, parts):
        self.parts = parts


class Rep(Node):
    def __init__(self, body, lo, hi, lazy):  # hi=None -> unbounded
        self.body = body
        self.lo = lo
        self.hi = hi
        self.lazy = lazy


LITERAL_CHARS = "abx0 _"  # chars safe to emit literally (all non-meta)
CLASS_CHARS = "abcx0 _"  # chars safe inside [...]


def _serialize(node, out):
    if isinstance(node, Lit):
        out.append(_escape_literal(node.ch))
    elif isinstance(node, Dot):
        out.append(".")
    elif isinstance(node, Class):
        out.append("[")
        if node.negated:
            out.append("^")
        for it in node.items:
            if it[0] == "ch":
                out.append(_escape_class_char(it[1]))
            else:
                out.append(_escape_class_char(it[1]) + "-" + _escape_class_char(it[2]))
        out.append("]")
    elif isinstance(node, EscClass):
        out.append("\\" + node.kind)
    elif isinstance(node, Anchor):
        out.append({"^": "^", "$": "$", "b": r"\b", "B": r"\B"}[node.kind])
    elif isinstance(node, Group):
        out.append("(" if node.idx is not None else "(?:")
        _serialize(node.body, out)
        out.append(")")
    elif isinstance(node, Alt):
        for i, br in enumerate(node.branches):
            if i:
                out.append("|")
            _serialize(br, out)
        # caller wraps alternatives needing grouping via Group
    elif isinstance(node, Cat):
        for p in node.parts:
            _serialize(p, out)
    elif isinstance(node, Rep):
        _serialize_quantified(node, out)
    else:
        raise AssertionError(f"unknown node {node!r}")


def _escape_literal(ch):
    return ch if ch.isalnum() or ch in " _" else "\\" + ch


def _escape_class_char(ch):
    if ch == "]":
        return r"\]"
    if ch == "\\":
        return r"\\"
    if ch == "^":
        return r"\^"
    return ch


def _serialize_quantified(node, out):
    body_needs_group = isinstance(node.body, (Alt,)) or (
        isinstance(node.body, Rep)  # a** is an error; wrap nested reps
    ) or (
        isinstance(node.body, Anchor)  # ^* is an error in modern Python
    )
    if body_needs_group:
        out.append("(?:")
        _serialize(node.body, out)
        out.append(")")
    else:
        _serialize(node.body, out)
    if node.lo == 0 and node.hi is None:
        out.append("*")
    elif node.lo == 1 and node.hi is None:
        out.append("+")
    elif node.lo == 0 and node.hi == 1:
        out.append("?")
    elif node.hi is None:
        out.append("{%d,}" % node.lo)
    elif node.lo == node.hi:
        out.append("{%d}" % node.lo)
    else:
        out.append("{%d,%d}" % (node.lo, node.hi))
    if node.lazy:
        out.append("?")


# ---------------------------------------------------------------------------
# Random AST construction
# ---------------------------------------------------------------------------

BUCKETS = [
    "lit", "dot", "class", "esc_class", "anchor",
    "group", "alt", "quant_greedy", "quant_lazy", "quant_counted",
    "nullable_star",
]

MAX_DEPTH = 4


class Gen:
    def __init__(self, rng):
        self.rng = rng
        self.next_group = 1

    def atom(self, depth, alphabet):
        r = self.rng.random()
        if depth >= MAX_DEPTH or r < 0.35:
            pool = LITERAL_CHARS + alphabet
            return Lit(self.rng.choice(pool))
        if r < 0.45:
            return Dot()
        if r < 0.58:
            return self.cls()
        if r < 0.68:
            return EscClass(self.rng.choice("dwsDWS"))
        if r < 0.76:
            return Anchor(self.rng.choice("^$bB"))
        return None  # signal caller to build compound

    def cls(self):
        items = []
        for _ in range(self.rng.randint(1, 3)):
            if self.rng.random() < 0.4:
                lo = self.rng.choice(CLASS_CHARS)
                hi = chr(min(ord(lo) + self.rng.randint(0, 4), ord("~")))
                items.append(("range", lo, hi))
            else:
                items.append(("ch", self.rng.choice(CLASS_CHARS)))
        return Class(items, self.rng.random() < 0.3)

    def node(self, depth, bucket, alphabet):
        """Build a node steering toward `bucket` when shallow."""
        if bucket == "lit":
            return Lit(self.rng.choice(LITERAL_CHARS + alphabet))
        if bucket == "dot":
            return Dot()
        if bucket == "class":
            return self.cls()
        if bucket == "esc_class":
            return EscClass(self.rng.choice("dwsDWS"))
        if bucket == "anchor":
            return Anchor(self.rng.choice("^$bB"))

        # compound buckets
        if bucket == "group":
            idx = self.next_group
            self.next_group += 1
            inner = self.node(depth + 1, self.rng.choice(BUCKETS[:5]), alphabet)
            return Group(idx, inner)
        if bucket == "alt":
            n = self.rng.randint(2, 3)
            branches = [self.seq(depth + 1, None, alphabet) for _ in range(n)]
            return Group(None, Alt(branches))
        if bucket in ("quant_greedy", "quant_lazy"):
            lazy = bucket == "quant_lazy"
            body = self.quantifiable(depth + 1, alphabet)
            lo, hi = self._rep_bounds()
            return Rep(body, lo, hi, lazy)
        if bucket == "quant_counted":
            body = self.quantifiable(depth + 1, alphabet)
            lo = self.rng.randint(0, 3)
            hi = lo + self.rng.randint(0, 3) if self.rng.random() < 0.7 else None
            return Rep(body, lo, hi, False)
        if bucket == "nullable_star":
            inner_bucket = self.rng.choice(["lit", "class", "group"])
            body = self.node(depth + 1, inner_bucket, alphabet)
            # make body plausibly nullable: optional-wrap or starred inner
            if isinstance(body, Lit) and self.rng.random() < 0.5:
                body = Group(None, Alt([body, Cat([])]))
            return Rep(body, 0, None, self.rng.random() < 0.3)
        raise AssertionError(bucket)

    def quantifiable(self, depth, alphabet):
        n = self.node(depth, self.rng.choice(BUCKETS[:6]), alphabet)
        if isinstance(n, (Rep, Anchor)):
            n = Group(None, n)
        return n

    def _rep_bounds(self):
        r = self.rng.random()
        if r < 0.5:
            return 0, None
        if r < 0.75:
            return 1, None
        return 0, 1

    def seq(self, depth, bucket, alphabet):
        parts = []
        for _ in range(self.rng.randint(1, 4)):
            if bucket is not None and self.rng.random() < 0.6:
                parts.append(self.node(depth, bucket, alphabet))
            else:
                n = self.atom(depth, alphabet)
                parts.append(n if n is not None else self.node(
                    depth, self.rng.choice(BUCKETS[2:]), alphabet))
        return Cat(parts)

    def pattern(self, bucket):
        """One full pattern: optional anchors around a sequence."""
        alphabet = self.rng.choice(ALPHABETS)
        core = self.seq(0, bucket, alphabet)
        if isinstance(core, Cat) and len(core.parts) > 1 and self.rng.random() < 0.25:
            core = Group(self._maybe_capture(), core)
        parts = []
        if self.rng.random() < 0.3:
            parts.append(Anchor(self.rng.choice("^b")))
        parts.append(core)
        if self.rng.random() < 0.3:
            parts.append(Anchor(self.rng.choice("$b")))
        cat = Cat(parts)
        out = []
        _serialize(cat, out)
        return "".join(out)

    def _maybe_capture(self):
        if self.rng.random() < 0.5:
            idx = self.next_group
            self.next_group += 1
            return idx
        return None

    def subject(self, alphabet):
        n = self.rng.choices([0, 1, 2, 4, 6, 8, 12], weights=[6, 10, 14, 20, 18, 16, 8])[0]
        s = "".join(self.rng.choice(alphabet) for _ in range(n))
        if self.rng.random() < 0.15:
            s += self.rng.choice("zZ9.")  # adversarial char outside most alphabets
        return s


# Hand-written bedrock cases: (pattern, [inputs]). Independent of the RNG;
# every engine must handle these before any generated case runs.
EDGE_CASES = [
    ("", ["", "a", "aa"]),
    ("a", ["", "a", "b", "aa"]),
    (".", ["", "a", "\n"]),
    ("^$", ["", "a"]),
    ("^", ["", "a"]),
    ("$", ["", "a"]),
    ("a*", ["", "a", "aaa", "baaa"]),
    ("a*?", ["", "a", "aaa", "baaa"]),
    ("a+", ["", "a", "aaa"]),
    ("a+?", ["aa"]),
    ("a?", ["", "a", "aa"]),
    ("a??", ["", "a", "aa"]),
    ("a{2}", ["", "a", "aa", "aaa"]),
    ("a{2,}", ["", "a", "aaaa"]),
    ("a{2,3}", ["", "a", "aa", "aaa", "aaaa"]),
    ("a{0,2}", ["aaa"]),
    ("a{2,3}?", ["aaaa"]),
    ("(?:ab)+", ["abab", "ababx", "x"]),
    ("(ab)+", ["abab", "xababy"]),
    ("(a|b)*c", ["ababc", "abc", "c", "abd"]),
    ("(a|b)*?c", ["ababc", "abc"]),
    ("[abc]+", ["cab", "xd"]),
    ("[^abc]+", ["xyz", "abcxyz"]),
    ("[a-c]{2}", ["abcab", "ad"]),
    (r"\d+", ["a123b", "", "42"]),
    (r"\w+\s\w+", ["foo bar", "foo   ", " x"]),
    (r"\D+", ["ab12cd", "12"]),
    (r"a\b", ["xa x", "xaa", "a b"]),
    (r"\Ba", ["xaa", "xa x"]),
    ("(a)(b)?", ["a", "ab", "b"]),
    ("((a)b)c", ["abc", "ac"]),
    ("(a*)(a*)", ["aa", "", "aab"]),
    ("(a+)(a+)", ["aa", "aaaa"]),
    ("(a|ab)(c|bcd)", ["abcd"]),          # classic leftmost-first priority case
    ("(a|ab)(c|bcd)(d*)", ["abcd", "abcdddd"]),
    ("(a*)*", ["aaa", "b", ""]),
    ("(a*)+", ["aaa", "b", ""]),
    ("(a?)*", ["aaa", ""]),
    ("((a)*)*b", ["aaab", "b"]),
    ("(|a)*", ["aaa", ""]),
    ("x.*y", ["xaybz", "xy", "x\ny"]),    # . does not match newline
    ("[.]*", ["..", "ab"]),               # dot inside a class is literal
    (r"[\]]", ["]]", "x"]),               # escaped ] in class
    (r"[\\]", ["\\", "x"]),               # escaped backslash in class
    ("(a)|(b)", ["a", "b", "ab"]),
    (r"(?:\ba)\b", ["a b", "xab"]),
    # --- probed CPython quirks (see JOURNAL block 2 / M1 probes) ---
    ("a{2", ["aa{2"]),                    # malformed brace = literal brace
    ("a{2,", ["xa{2,y"]),                 # ditto, open-ended form
    ("}", ["x}y"]),                       # lone } literal
    ("]", ["x]y"]),                       # lone ] literal
    ("a{,3}", ["aaa", "aaaa"]),           # {,n} == {0,n}
    ("[]]", ["]]", "x"]),                 # first ] in class is literal
    ("[^]]", ["xyz"]),                    # negated variant of same
    ("[-a]", ["-b", "xb"]),               # leading dash literal
    ("[a-]", ["ba-", "x"]),               # trailing dash literal
    (r"[\d]+", ["ab12de"]),               # shorthand inside class
    (r"[^\d]+", ["12ab34"]),
    (r"\t\n", ["\t\n", "\t"]),
    (r"\x41+", ["xAAB"]),                 # hex escape
    ("(|a)", ["b", "ab"]),                # empty alternation branch + findall('')
    (r"a$", ["za\n", "za"]),              # $ matches before trailing newline
]


def generate(seed, n_cases):
    """Return (cases, coverage). Each case: dict(pattern, subject, bucket, alphabet).

    Deterministic given seed. Roughly half the volume comes from EDGE_CASES
    expansion so bedrock behavior dominates early milestones.
    """
    rng = random.Random(seed)
    gen = Gen(rng)
    cases = []
    for pat, inputs in EDGE_CASES:
        for s in inputs:
            cases.append({
                "pattern": pat,
                "subject": s,
                "bucket": "edge",
                "alphabet": ALPHABETS[0],
            })
    n_gen = max(0, n_cases - len(cases))
    buckets_seen = {b: 0 for b in BUCKETS}
    while len(cases) < n_cases:
        bucket = rng.choice(BUCKETS)
        pat = gen.pattern(bucket)
        alpha = ALPHABETS[0]  # subjects drawn from same alphabet family as pattern used
        # recover a plausible subject alphabet: union of all declared ones is safe
        subj = gen.subject(rng.choice(ALPHABETS))
        cases.append({"pattern": pat, "subject": subj, "bucket": bucket, "alphabet": alpha})
        buckets_seen[bucket] += 1
    return cases, buckets_seen
