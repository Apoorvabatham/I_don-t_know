"""Public API surface for nanoregex.

All functions are stubs until their milestone lands:
  - M1: parser (AST)          — internal, exercised via compile()
  - M2: backtracking matcher  — search/match/fullmatch/findall/finditer
  - M3: Thompson NFA + Pike VM — same surface, selected explicitly by tests/bench

The stub raises NotImplementedError AT CALL TIME (not import time) so that the
test suite imports cleanly and fails at runtime — the Phase 1 "red against
stub" contract.
"""


class UnsupportedPattern(Exception):
    """Pattern uses syntax outside the documented subset.

    Deliberately distinct from error so the differential oracle can tell
    'engine bug' from 'out of charter scope' — though within the subset the
    oracle requires exact parity with re, so this must never fire on subset
    patterns.
    """


def _stub(name):
    def _raise(*args, **kwargs):
        raise NotImplementedError(
            f"nanoregex.{name} is a Phase 1 stub — implemented in a later milestone"
        )

    return _raise


compile = _stub("compile")
search = _stub("search")
match = _stub("match")
fullmatch = _stub("fullmatch")
findall = _stub("findall")
finditer = _stub("finditer")
