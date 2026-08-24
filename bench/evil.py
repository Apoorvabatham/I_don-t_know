"""The five charter-fixed catastrophic-backtracking patterns + input builder.

Subject construction (documented choice, used per pattern): n copies of the
pattern's dominant literal char, arranged so the pattern CANNOT match and a
backtracking engine must exhaust an exponentially large match space before
concluding failure. That non-matching worst case is the honest ReDoS
measurement — matching inputs let an engine stop at the first success.

Caught by this lab's own first smoke run: E5 `^(a+)+$` against bare
"a" * n TRIVIALLY MATCHES (greedy arm consumes everything, `$` is
satisfied) in ~0 ms. Its subject therefore carries a failing tail
("a"*n + "b") so the anchored failure case actually fails.

Sizes follow the charter: n = 1,000 * 2^k for k = 0..7 (1,000 .. 128,000).
"""

FULL_SIZES = [1000 * 2 ** k for k in range(8)]


def _chars(n):
    return "a" * n


def _xs(n):
    return "x" * n


def _as_then_b(n):
    # "a"*n + "b": the b forces failure through the full partition space.
    # Bare "a"*n would match instantly and measure nothing (see module doc).
    return "a" * n + "b"


EVIL_PATTERNS = [
    {"id": "E1", "pattern": r"(a|a)*b", "subject": _chars,
     "note": "duplicate alternation arm inside a star"},
    {"id": "E2", "pattern": r"(a|aa)+b", "subject": _chars,
     "note": "ambiguous-length alternation arms"},
    {"id": "E3", "pattern": r"(x+x+)+y", "subject": _xs,
     "note": "nested quantifiers over adjacent classes"},
    {"id": "E4", "pattern": r"(a*)*b", "subject": _chars,
     "note": "star nested in star (nullable inner)"},
    {"id": "E5", "pattern": r"^(a+)+$", "subject": _as_then_b,
     "note": "anchored (a+)+ classic exponential failure case"},
]

assert len(EVIL_PATTERNS) == 5
