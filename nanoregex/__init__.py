"""nanoregex — clean-room regex engine (documented subset) + benchmark lab.

Public API intentionally mirrors the small slice of ``re`` that the charter's
differential oracle exercises: compile / search / match / fullmatch /
findall / finditer over the documented syntax subset (see CHARTER.md).

PHASE 1 STATUS: every public entry point is a stub raising NotImplementedError.
The oracle in tests/ must be RED against this stub — that is its acceptance
test for Phase 1. Milestones M1-M3 replace these stubs one engine at a time.
"""

from nanoregex.api import (
    compile,
    search,
    match,
    fullmatch,
    findall,
    finditer,
)

__all__ = [
    "compile",
    "search",
    "match",
    "fullmatch",
    "findall",
    "finditer",
]
__version__ = "0.0.0+phase1.stub"
