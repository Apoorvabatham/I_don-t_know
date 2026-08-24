"""Recursive-descent parser: token stream -> AST.

Grammar (documented subset):

    alt    := cat ('|' cat)*
    cat    := quant*
    quant  := atom [('*'|'+'|'?'|REPEAT) ['?' lazy-marker]]
    atom   := LIT | DOT | SHORT | ANCHOR | CLASS
            | LPAREN(capture) alt RPAREN      -> Group(n)
            | LPAREN(noncap)   alt RPAREN     -> Group(None)

Parity decisions (probed against CPython 3.10 re):
  * Singleton Alt/Cat collapse to their child — the printer emits them
    identically, which is what makes the roundtrip property exact.
  * A second quantifier directly after one is an error ("multiple repeat",
    like re on 'a**'); laziness consumes exactly one '?'.
  * Quantifying an anchor ('^*') or a bare Rep is a parse error — CPython
    3.10 only deprecates this and modern versions reject it outright; the
    generator never emits it. Deliberately stricter, documented.
  * '{m,n}' bounds are validated here: min > max is a parse error like
    re's "min repeat greater than max repeat".
  * Group indices are assigned in left-to-right order of '(' occurrence,
    counting capturing groups only.
"""

from nanoregex.ast_nodes import (
    Alt, Anchor, Cat, CharClass, Dot, Group, Lit, Rep, Shorthand,
    QUANTIFIABLE,
)
from nanoregex.errors import NanoregexParseError
from nanoregex.lexer import tokenize

_QUANT_KINDS = ("STAR", "PLUS", "QMARK", "REPEAT")

#: Maximum nesting depth (groups/alternations/repeats). Recursive-descent
#: parsing and the matchers' split-arm walks both scale with nesting, so
#: pathological inputs are rejected here instead of blowing the stack.
MAX_DEPTH = 120


class _Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0
        self.ngroups = 0
        self.depth = 0

    def peek(self):
        return self.toks[self.i]

    def advance(self):
        tok = self.toks[self.i]
        self.i += 1
        return tok

    def _enter(self, pos):
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise NanoregexParseError(
                f"pattern nests more than {MAX_DEPTH} levels deep", pos)

    def parse_pattern(self):
        ast = self.parse_alt()
        tok = self.peek()
        if tok.kind != "EOF":
            if tok.kind == "RPAREN":
                raise NanoregexParseError("unbalanced parenthesis", tok.pos)
            raise NanoregexParseError(f"unexpected {tok.kind}", tok.pos)
        return ast

    def parse_alt(self):
        branches = [self.parse_cat()]
        while self.peek().kind == "ALT":
            self.advance()
            branches.append(self.parse_cat())
        if len(branches) == 1:
            return branches[0]
        return Alt(branches)

    def parse_cat(self):
        parts = []
        while self.peek().kind not in ("ALT", "RPAREN", "EOF"):
            parts.append(self.parse_quant())
        if len(parts) == 1:
            return parts[0]
        return Cat(parts)

    def parse_quant(self):
        atom = self.parse_atom()
        tok = self.peek()
        if tok.kind not in _QUANT_KINDS:
            return atom
        self.advance()
        if tok.kind == "STAR":
            lo, hi = 0, None
        elif tok.kind == "PLUS":
            lo, hi = 1, None
        elif tok.kind == "QMARK":
            lo, hi = 0, 1
        else:
            lo, hi = tok.value
            if hi is not None and lo > hi:
                raise NanoregexParseError(
                    f"min repeat greater than max repeat ({lo} > {hi})",
                    tok.pos)
        lazy = False
        if self.peek().kind == "QMARK":
            self.advance()
            lazy = True
        nxt = self.peek()
        if nxt.kind in _QUANT_KINDS:
            raise NanoregexParseError(
                "multiple repeat (quantifier applied twice)", nxt.pos)
        if not isinstance(atom, QUANTIFIABLE):
            raise NanoregexParseError(
                "nothing to repeat (quantifier on an anchor or empty)", tok.pos)
        return Rep(atom, lo, hi, lazy)

    def parse_atom(self):
        tok = self.advance()
        kind = tok.kind
        if kind == "LIT":
            return Lit(tok.value)
        if kind == "DOT":
            return Dot()
        if kind == "SHORT":
            return Shorthand(tok.value)
        if kind == "ANCHOR":
            return Anchor(tok.value)
        if kind == "CLASS":
            negated, items = tok.value
            return CharClass(negated, items)
        if kind == "LPAREN":
            self._enter(tok.pos)
            capture = tok.value
            index = None
            if capture:
                self.ngroups += 1
                index = self.ngroups
            body = self.parse_alt()
            closing = self.advance()
            if closing.kind != "RPAREN":
                raise NanoregexParseError(
                    "missing ), unterminated subpattern", tok.pos)
            self.depth -= 1
            return Group(index, body)
        if kind == "RPAREN":
            raise NanoregexParseError("unbalanced parenthesis", tok.pos)
        if kind in _QUANT_KINDS:
            raise NanoregexParseError(
                f"nothing to repeat at start of pattern", tok.pos)
        raise NanoregexParseError(f"unexpected token {kind}", tok.pos)


def parse(pattern):
    """Parse a subset pattern string. Returns (ast, ngroups).

    Raises NanoregexParseError for malformed input and UnsupportedPattern
    for well-formed but out-of-subset syntax (see errors.py).
    """
    parser = _Parser(tokenize(pattern))
    ast = parser.parse_pattern()
    return ast, parser.ngroups
