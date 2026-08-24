"""Public API surface for nanoregex.

Milestone status:
  - M1 DONE: compile() parses into an AST (nanoregex.parser/printer).
  - M2/M3 PENDING: search/match/fullmatch/findall/finditer raise
    NotImplementedError at CALL time so the Phase-1 oracle stays RED
    against this module until a real matcher lands behind them.
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
    """Compiled pattern: AST + engine choice + group count.

    Matching methods are stubs until M2 (backtracker) / M3 (Pike VM).
    """

    def __init__(self, pattern, ast, ngroups, engine):
        self.pattern = pattern
        self.ast = ast
        self.groups = ngroups
        self.engine = engine

    def pretty(self):
        return print_pattern(self.ast)

    def _stub(self, *args, **kwargs):
        raise NotImplementedError(
            f"nanoregex {self.engine} matching is not implemented yet "
            f"(M2/M3); compile() works")

    search = _stub
    match = _stub
    fullmatch = _stub
    findall = _stub
    finditer = _stub


def compile(pattern, engine="pikevm"):
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
