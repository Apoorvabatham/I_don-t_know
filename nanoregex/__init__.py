"""nanoregex — clean-room regex engine (documented subset) + benchmark lab.

Public API intentionally mirrors the small slice of ``re`` that the charter's
differential oracle exercises: compile / search / match / fullmatch /
findall / finditer over the documented syntax subset (see CHARTER.md).

STATUS: M1 parser complete — compile() parses and validates patterns.
Matching (search/match/...) raises NotImplementedError until M2/M3 land;
the Phase-1 oracle is red against those stubs by design.
"""

from nanoregex.api import (
    ENGINES,
    RegexPattern,
    compile,
    search,
    match,
    fullmatch,
    findall,
    finditer,
)
from nanoregex.errors import (
    NanoregexError,
    NanoregexParseError,
    UnsupportedPattern,
)

__all__ = [
    "ENGINES",
    "RegexPattern",
    "compile",
    "search",
    "match",
    "fullmatch",
    "findall",
    "finditer",
    "NanoregexError",
    "NanoregexParseError",
    "UnsupportedPattern",
]
__version__ = "0.1.0+m1.parser"
