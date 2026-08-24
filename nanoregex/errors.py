"""Exception hierarchy for nanoregex.

Two failure modes are deliberately distinct (charter decision D1):

* :class:`NanoregexParseError` — the pattern is MALFORMED even inside the
  documented subset. Parity target: CPython raises ``re.error`` on the same
  input (message text may differ; error-vs-success must not).
* :class:`UnsupportedPattern` — well-formed but OUTSIDE the documented
  subset (lookaround, backreferences, named groups, inline flags, unicode
  escapes). These are charter NOT-doing items, rejected explicitly rather
  than misparsed.

Both carry the 0-based ``pos`` where the problem was detected.
"""


class NanoregexError(Exception):
    """Base class for all nanoregex errors."""


class NanoregexParseError(NanoregexError):
    def __init__(self, message, pos=None):
        self.pos = pos
        super().__init__(f"{message} (position {pos})" if pos is not None
                         else message)


class UnsupportedPattern(NanoregexError):
    def __init__(self, message, pos=None):
        self.pos = pos
        super().__init__(f"{message} (position {pos})" if pos is not None
                         else message)
