"""Lexer: pattern string -> token stream.

Token kinds and payloads:
    LIT(ch)                 literal character (incl. escaped meta, \t, \x41...)
    SHORT(kind)             \d \w \s \D \W \S  (outside classes)
    ANCHOR(kind)            ^ $ \b \B   ('^'/'$' lexed here too)
    DOT STAR PLUS QMARK     quantifier punctuation
    REPEAT(min, max)        {m} {m,} {m,n} {,n}; malformed braces fall back
                            to LIT('{') — CPython parity (probed: a{2 and
                            a{2, are literal-brace matches in re)
    LPAREN(capture)         '(' / '(?:' ; any other '(?...' -> UnsupportedPattern
    RPAREN ALT              structure
    CLASS(negated, items)   fully-scanned [...] contents (class syntax is a
                            self-contained mini-grammar; scanning it here
                            keeps the main parser context-free)
    LBRACE-AS-LIT etc. folded into LIT
    EOF

Parity quirks encoded here (each probed against CPython 3.10 re):
  * ']' first inside a class is a LITERAL member; '[]' is unterminated.
  * '[\d-a]' is an error ("bad character range"), not dash-literal.
  * '\0' is NUL; octal continuation '\01' is out of subset.
  * ']' and '}' at top level are literals; '{2}' with nothing to repeat is a
    parse error raised later by the parser, not the lexer.
"""

from nanoregex.errors import NanoregexParseError, UnsupportedPattern

SHORT_KINDS = set("dwsDWS")

_CONTROL_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "f": "\f",
                    "v": "\v", "a": "\a"}

_HEX = set("0123456789abcdefABCDEF")
_DIGITS = set("0123456789")


class Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind, value, pos):
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, @{self.pos})"


def tokenize(src):
    tokens = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\\":
            i = _lex_escape(src, i, tokens)
        elif c == ".":
            tokens.append(Token("DOT", None, i))
            i += 1
        elif c == "*":
            tokens.append(Token("STAR", None, i))
            i += 1
        elif c == "+":
            tokens.append(Token("PLUS", None, i))
            i += 1
        elif c == "?":
            tokens.append(Token("QMARK", None, i))
            i += 1
        elif c == "{":
            nxt = _try_repeat(src, i)
            if nxt is None:
                tokens.append(Token("LIT", "{", i))   # malformed brace = literal
                i += 1
            else:
                lo, hi, j = nxt
                tokens.append(Token("REPEAT", (lo, hi), i))
                i = j
        elif c == "}":
            tokens.append(Token("LIT", "}", i))
            i += 1
        elif c == "]":
            tokens.append(Token("LIT", "]", i))
            i += 1
        elif c == "^":
            tokens.append(Token("ANCHOR", "^", i))
            i += 1
        elif c == "$":
            tokens.append(Token("ANCHOR", "$", i))
            i += 1
        elif c == "|":
            tokens.append(Token("ALT", None, i))
            i += 1
        elif c == "(":
            j = _lex_paren(src, i, tokens)
            i = j
        elif c == ")":
            tokens.append(Token("RPAREN", None, i))
            i += 1
        elif c == "[":
            tok_end = _lex_class(src, i, tokens)
            i = tok_end
        else:
            tokens.append(Token("LIT", c, i))
            i += 1
    tokens.append(Token("EOF", None, n))
    return tokens


# ---------------------------------------------------------------------------
# escapes (shared by outside-class and inside-class lexing)
# ---------------------------------------------------------------------------

def _read_escape(src, i, in_class):
    """Decode the escape starting at src[i] == '\\'.

    Returns (payload_kind, payload, next_i) where payload_kind is
    'lit' | 'short' | 'anchor'. `in_class` rejects anchors and maps them
    differently per parity rules.
    """
    n = len(src)
    if i + 1 >= n:
        raise NanoregexParseError("pattern ends with a bare backslash", i)
    c = src[i + 1]
    if c in SHORT_KINDS:
        return "short", c, i + 2
    if not in_class and c in "bB":
        return "anchor", c, i + 2
    if in_class and c == "b":
        # CPython treats [\b] as backspace; that is outside our documented
        # subset, so we reject instead of silently diverging.
        raise UnsupportedPattern(
            r"\b inside a character class (backspace escape) is not in the "
            r"documented subset", i)
    if c in "123456789":
        raise UnsupportedPattern(
            f"backreference \\{c} requires backtracking semantics; excluded "
            f"by charter (linear-time engine)", i)
    if c == "0":
        if i + 2 < n and src[i + 2] in _DIGITS:
            raise UnsupportedPattern(
                "octal escapes beyond \\0 are not in the documented subset", i)
        return "lit", "\0", i + 2
    if c == "x":
        if i + 3 >= n or src[i + 2] not in _HEX or src[i + 3] not in _HEX:
            raise NanoregexParseError(r"incomplete escape \x (need 2 hex digits)", i)
        return "lit", chr(int(src[i + 2:i + 4], 16)), i + 4
    if c in "uUN":
        raise UnsupportedPattern(
            f"unicode escape \\{c} is not in the ASCII-documented subset", i)
    if c in _CONTROL_ESCAPES:
        return "lit", _CONTROL_ESCAPES[c], i + 2
    if c == "A" or c == "Z":
        raise UnsupportedPattern(
            f"\\{c} absolute anchor is not in the documented subset "
            f"(use ^/$)", i)
    if c.isascii() and c.isalpha():
        # CPython parity: unknown escapes of ASCII letters are errors
        # ("bad escape \q"), not silent literals
        raise NanoregexParseError(f"bad escape \\{c} (unknown escape)", i)
    return "lit", c, i + 2


def _lex_escape(src, i, tokens):
    kind, payload, nxt = _read_escape(src, i, in_class=False)
    if kind == "short":
        tokens.append(Token("SHORT", payload, i))
    elif kind == "anchor":
        tokens.append(Token("ANCHOR", payload, i))
    else:
        tokens.append(Token("LIT", payload, i))
    return nxt


def _lex_paren(src, i, tokens):
    n = len(src)
    if i + 1 < n and src[i + 1] == "?":
        if i + 2 >= n:
            raise NanoregexParseError("unterminated group extension", i)
        c = src[i + 2]
        if c == ":":
            tokens.append(Token("LPAREN", False, i))
            return i + 3
        if c in "=!":
            raise UnsupportedPattern(
                "lookahead (?= / (?!) is excluded by charter", i)
        if c == "<":
            raise UnsupportedPattern(
                "lookbehind (?<= / (?<!) is excluded by charter", i)
        raise UnsupportedPattern(
            f"group extension (?{c} (named groups, inline flags, ...) is "
            f"not in the documented subset", i)
    tokens.append(Token("LPAREN", True, i))
    return i + 1


# ---------------------------------------------------------------------------
# character-class scanning
# ---------------------------------------------------------------------------

def _class_member(src, i):
    """One class member at src[i].

    Returns (item, next_i) where item is ('ch', c) or ('short', kind).
    """
    c = src[i]
    if c == "\\":
        kind, payload, nxt = _read_escape(src, i, in_class=True)
        if kind == "short":
            return ("short", payload), nxt
        return ("ch", payload), nxt
    return ("ch", c), i + 1


def _lex_class(src, start, tokens):
    """Scan '[...]' beginning at start. Returns index just past ']'.

    Parity: a ']' in first-member position is a literal member ('[]]'
    matches a single ']' in CPython); only '[]'/'[^]' (nothing before the
    closing bracket slot) is unterminated.
    """
    n = len(src)
    i = start + 1
    negated = False
    if i < n and src[i] == "^":
        negated = True
        i += 1
    items = []
    first = True
    while True:
        if i >= n:
            raise NanoregexParseError(
                "unterminated character set (missing '])", start)
        if src[i] == "]" and not first:
            i += 1
            break
        first = False
        member, i = _class_member(src, i)
        # range? '-' must have a right side that is not ']' to be a range;
        # otherwise it is a literal dash ([a-], [-a], [a-\]] all fine)
        if (i < n and src[i] == "-"
                and i + 1 < n and src[i + 1] != "]"):
            rhs, i2 = _class_member(src, i + 1)
            if member[0] == "short" or rhs[0] == "short":
                raise NanoregexParseError(
                    "bad character range around a shorthand class", i)
            lo, hi = member[1], rhs[1]
            if ord(lo) > ord(hi):
                raise NanoregexParseError(
                    f"bad character range {lo}-{hi} (lo > hi)", i - 1)
            items.append(("range", lo, hi))
            i = i2
        else:
            items.append(member)
    tokens.append(Token("CLASS", (negated, items), start))
    return i


def _try_repeat(src, i):
    """Parse '{{m}}', '{{m,}}', '{{m,n}}', '{{,n}}' at src[i] == '{'.

    Returns (min, max, next_i) or None when it is NOT valid bound syntax
    (caller emits a literal '{' — CPython parity for 'a{{2').
    """
    n = len(src)
    j = i + 1
    lo_digits = 0
    while j < n and src[j] in _DIGITS:
        j += 1
        lo_digits += 1
    lo = int(src[i + 1:j]) if lo_digits else 0
    if j < n and src[j] == "}":
        if not lo_digits:
            return None          # '{}' is a literal brace pair in CPython
        return lo, lo, j + 1
    if j < n and src[j] == ",":
        j += 1
        hi_start = j
        while j < n and src[j] in _DIGITS:
            j += 1
        has_hi = j > hi_start
        if j < n and src[j] == "}" and (lo_digits or has_hi):
            hi = int(src[hi_start:j]) if has_hi else None
            return lo, hi, j + 1
    return None
