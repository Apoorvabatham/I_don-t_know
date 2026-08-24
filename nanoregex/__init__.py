"""nanoregex — clean-room regex engine (documented subset) + benchmark lab.

Public API intentionally mirrors the small slice of ``re`` that the charter's
differential oracle exercises: compile / search / match / fullmatch /
findall / finditer over the documented syntax subset (see CHARTER.md).

Two engines ship behind one interface:
  * pikevm (default)  — breadth-first Thompson/Pike simulation, linear time
  * backtracker       — iterative choice-point VM, exponential by design

Both are differential-tested against CPython ``re`` (exact spans incl.
capture groups) over thousands of seeded cases per release.
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
__version__ = "1.0.0"

