"""Public API surface for nanoregex.

Milestone status:
  - M1 DONE: compile() parses into an AST (nanoregex.parser/printer).
  - M2 DONE: engine='backtracker' runs the full match API.
  - M3 PENDING: engine='pikevm' raises NotImplementedError at CALL time so
    the oracle stays red for that engine until the Pike VM lands.
"""

from nanoregex.errors import (
    NanoregexError,
    NanoregexParseError,
    UnsupportedPattern,
)
from nanoregex.parser import parse
from nanoregex.printer import print_pattern

ENGINES = ("pikevm", "backtracker")


class RegexPattern:
    """Compiled pattern: AST + program + engine choice + group count."""

    def __init__(self, pattern, ast, ngroups, engine):
        self.pattern = pattern
        self.ast = ast
        self.groups = ngroups
        self.engine = engine
        self._matcher = None

    def pretty(self):
        return print_pattern(self.ast)

    def _matcher_for(self):
        if self._matcher is None:
            if self.engine == "backtracker":
                from nanoregex.backtracker import bind
                self._matcher = bind(self)
            elif self.engine == "pikevm":
                from nanoregex.pikevm import bind
                self._matcher = bind(self)
            else:
                raise ValueError(f"unknown engine {self.engine!r}")
        return self._matcher

    def search(self, string):
        return self._matcher_for().search(string)

    def match(self, string):
        return self._matcher_for().match(string)

    def fullmatch(self, string):
        return self._matcher_for().fullmatch(string)

    def findall(self, string):
        return self._matcher_for().findall(string)

    def finditer(self, string):
        return self._matcher_for().finditer(string)


def compile(pattern, engine="pikevm"):
    """Parse `pattern` and bind it to `engine`.

    Raises NanoregexParseError / UnsupportedPattern at parse time; a
    not-yet-implemented engine raises NotImplementedError on first USE.
    """
    if engine not in ENGINES:
        raise ValueError(
            f"unknown engine {engine!r}; choose from {ENGINES}")
    ast, ngroups = parse(pattern)
    return RegexPattern(pattern, ast, ngroups, engine)


def search(pattern, string, engine="pikevm"):
    return compile(pattern, engine).search(string)


def match(pattern, string, engine="pikevm"):
    return compile(pattern, engine).match(string)


def fullmatch(pattern, string, engine="pikevm"):
    return compile(pattern, engine).fullmatch(string)


def findall(pattern, string, engine="pikevm"):
    return compile(pattern, engine).findall(string)


def finditer(pattern, string, engine="pikevm"):
    return compile(pattern, engine).finditer(string)
