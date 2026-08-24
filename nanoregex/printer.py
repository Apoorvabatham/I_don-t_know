"""AST -> pattern string (pretty-printer).

Contract: parse(print(ast)) == ast for every AST the parser can produce
(the M1 roundtrip property, tested over the whole generated corpus).
The emitted string is always inside the documented subset and therefore
also valid CPython re — but this serializer is written from the AST side,
independent of tests/gen_corpus.py's generator-side serializer; their
agreement is differential evidence, not shared code.

Escaping rules:
  * Outside classes: alphanumerics, '_' and ' ' go bare; everything else
    that is ASCII-printable gets a backslash (harmless for non-meta);
    control characters use named escapes when available, else \\xHH.
  * Inside classes: ']', '\\' and '^' are escaped; '-' is emitted as a
    range separator only in ('range', lo, hi) items and as '\\-' otherwise;
    shorthand members re-emit as \\d etc. ('[' needs no escape in class).
"""

from nanoregex.ast_nodes import (
    Alt, Anchor, Cat, CharClass, Dot, Group, Lit, Rep, Shorthand,
)

_NAMED = {"\n": r"\n", "\t": r"\t", "\r": r"\r", "\f": r"\f",
          "\v": r"\v", "\a": r"\a", "\0": r"\0"}


def _lit_body(ch):
    if ch.isalnum() or ch in "_ ":
        return ch
    if ch in _NAMED:
        return _NAMED[ch]
    if 32 <= ord(ch) < 127:
        return "\\" + ch
    return "\\x%02x" % ord(ch)


def _class_char(ch):
    if ch in "]\\^":
        return "\\" + ch
    if ch == "-":
        return "\\-"
    if ch.isalnum() or ch in "_ ":
        return ch
    if ch in _NAMED:
        return _NAMED[ch]
    if 32 <= ord(ch) < 127:
        return "\\" + ch
    return "\\x%02x" % ord(ch)


def print_pattern(node):
    return _emit(node)


def _emit(node):
    if isinstance(node, Lit):
        return _lit_body(node.ch)
    if isinstance(node, Dot):
        return "."
    if isinstance(node, Shorthand):
        return "\\" + node.kind
    if isinstance(node, Anchor):
        return {"^": "^", "$": "$", "b": r"\b", "B": r"\B"}[node.kind]
    if isinstance(node, CharClass):
        out = ["["]
        if node.negated:
            out.append("^")
        for item in node.items:
            if item[0] == "ch":
                out.append(_class_char(item[1]))
            elif item[0] == "short":
                out.append("\\" + item[1])
            else:
                _, lo, hi = item
                out.append(_class_char(lo) + "-" + _class_char(hi))
        out.append("]")
        return "".join(out)
    if isinstance(node, Group):
        inner = _emit(node.body)
        if node.index is None:
            return "(?:" + inner + ")"
        return "(" + inner + ")"
    if isinstance(node, Alt):
        return "|".join(_emit(b) for b in node.branches)
    if isinstance(node, Cat):
        return "".join(_emit(p) for p in node.parts)
    if isinstance(node, Rep):
        # body is always quantifiable (parser invariant), so it never needs
        # wrapping: Lit/Dot/CharClass/Shorthand emit as one atom, Group
        # already carries its own parens.
        body = _emit(node.body)
        if node.min == 0 and node.max is None:
            op = "*"
        elif node.min == 1 and node.max is None:
            op = "+"
        elif node.min == 0 and node.max == 1:
            op = "?"
        elif node.max is None:
            op = "{%d,}" % node.min
        elif node.min == node.max:
            op = "{%d}" % node.min
        else:
            op = "{%d,%d}" % (node.min, node.max)
        return body + op + ("?" if node.lazy else "")
    raise TypeError(f"not an AST node: {node!r}")
