"""AST node types for the documented nanoregex subset.

Structural equality (__eq__) is part of the M1 contract: the parser
roundtrip property (parse(print(ast)) == ast) and several oracle checks
compare trees directly.

Class invariants:
  * Lit.ch            — exactly one character.
  * CharClass.items   — list of ('ch', c) | ('range', lo, hi) | ('short', k)
                        with ord(lo) <= ord(hi) for ranges; no empty classes.
  * Shorthand.kind    — one of 'd w s D W S'.
  * Anchor.kind       — '^', '$', 'b' (word boundary), 'B' (non-boundary).
  * Group.index       — int (1-based, capturing) or None (non-capturing);
                        indices are assigned by the parser in left-to-right
                        open order across the whole pattern.
  * Rep.min/max       — ints, max >= min >= 0, max may be None (unbounded);
                        body is always a quantifiable node (never Anchor,
                        never another bare Rep).
  * Alt.branches      — >= 2 branches (singleton alternatives collapse).
  * Cat.parts         — any length incl. 0 (empty pattern / empty branch).
"""


class Node:
    def _fields(self):
        return tuple(sorted(self.__dict__.items()))

    def __eq__(self, other):
        return (type(self) is type(other)
                and self._fields() == other._fields())

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((type(self).__name__,) + self._fields())

    def __repr__(self):
        args = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
        return f"{type(self).__name__}({args})"


class Lit(Node):
    def __init__(self, ch):
        self.ch = ch


class Dot(Node):
    pass


class CharClass(Node):
    def __init__(self, negated, items):
        self.negated = negated
        self.items = items


class Shorthand(Node):
    def __init__(self, kind):
        self.kind = kind


class Anchor(Node):
    def __init__(self, kind):
        self.kind = kind


class Group(Node):
    def __init__(self, index, body):
        self.index = index
        self.body = body


class Alt(Node):
    def __init__(self, branches):
        self.branches = branches


class Cat(Node):
    def __init__(self, parts):
        self.parts = parts


class Rep(Node):
    def __init__(self, body, min, max, lazy):
        self.body = body
        self.min = min
        self.max = max
        self.lazy = lazy


#: Node types that may carry a quantifier (parser enforces this).
QUANTIFIABLE = (Lit, Dot, CharClass, Shorthand, Group)
