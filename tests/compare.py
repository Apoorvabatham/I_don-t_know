"""Differential comparison machinery: nanoregex vs CPython re.

Shared by tests/test_differential.py (unittest) and tools/fuzz_diff.py (CLI).
The comparison is purely behavioral: for each generated case and each API,
both engines run and their results are normalized to comparable structures.
Any difference is a mismatch unless a whitelist entry claims it with a reason.

Whitelist policy: EMPTY at Phase 1. An entry may only be added with a written
justification in code, and every fired entry is reported. Never weaken the
oracle silently (charter hard rule).
"""

import signal
import threading

import re as re_ref

import nanoregex


class EngineUnavailable(Exception):
    """Engine raised NotImplementedError (stub) or UnsupportedPattern."""


class CaseTimeout(Exception):
    """A case exceeded its per-case wall budget."""


PER_CASE_TIMEOUT_S = 5


# ---------------------------------------------------------------------------
# Whitelist — intentional, documented divergences from re. MUST STAY EMPTY
# unless a divergence is deliberate AND argued here in a comment.
# ---------------------------------------------------------------------------

WHITELIST = []  # each entry: fn(case, api, ref_result, act_result) -> reason str | None


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def norm_search_result(m, ngroups):
    """Match object -> tuple of spans for groups 0..n, or None."""
    if m is None:
        return None
    return tuple(m.span(i) for i in range(ngroups + 1))


def norm_findall(res):
    """re.findall returns strings or tuples of strings; normalize as-is."""
    return [tuple(x) if isinstance(x, tuple) else x for x in res]


def norm_finditer(matches, ngroups):
    out = []
    for m in matches:
        out.append(tuple(m.span(i) for i in range(ngroups + 1)))
    return out


APIS = ("search", "match", "fullmatch", "findall", "finditer")


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def _with_timeout(fn, seconds=PER_CASE_TIMEOUT_S):
    main_thread = threading.current_thread() is threading.main_thread()
    if not main_thread:
        return fn()

    def _handler(signum, frame):
        raise CaseTimeout(f"exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def run_ref(case):
    """Run CPython re on one case across all APIs -> {api: normalized}."""
    pat = re_ref.compile(case["pattern"])
    s = case["subject"]
    ng = pat.groups
    out = {
        "ngroups": ng,
        "search": norm_search_result(pat.search(s), ng),
        "match": norm_search_result(pat.match(s), ng),
        "fullmatch": norm_search_result(pat.fullmatch(s), ng),
        "findall": norm_findall(pat.findall(s)),
        "finditer": norm_finditer(pat.finditer(s), ng),
    }
    return out


def run_nanoregex(case, engine="pikevm"):
    """Run nanoregex on one case; engine selects the backend under test.

    Raises EngineUnavailable while backends are stubs.
    """
    try:
        pat = nanoregex.compile(case["pattern"], engine=engine)
        s = case["subject"]
        ng = pat.groups
        return {
            "ngroups": ng,
            "search": norm_search_result(pat.search(s), ng),
            "match": norm_search_result(pat.match(s), ng),
            "fullmatch": norm_search_result(pat.fullmatch(s), ng),
            "findall": norm_findall(pat.findall(s)),
            "finditer": norm_finditer(pat.finditer(s), ng),
        }
    except NotImplementedError as e:
        raise EngineUnavailable(str(e)) from e
    except nanoregex.UnsupportedPattern as e:
        raise EngineUnavailable(f"unsupported: {e}") from e


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_case(ref, act):
    """Return list of (api, ref_val, act_val) where results differ."""
    diffs = []
    if ref["ngroups"] != act["ngroups"]:
        diffs.append(("ngroups", ref["ngroups"], act["ngroups"]))
        return diffs
    for api in APIS:
        if ref[api] != act[api]:
            diffs.append((api, ref[api], act[api]))
    return diffs


def check_one(case, engine="pikevm"):
    """Full check of one case. Returns (status, detail).

    status: 'ok' | 'mismatch' | 'whitelisted' | 'unavailable'
    """
    ref = _with_timeout(lambda: run_ref(case))
    try:
        act = _with_timeout(lambda: run_nanoregex(case, engine))
    except EngineUnavailable:
        return "unavailable", None
    except CaseTimeout as t:
        return "mismatch", [("timeout", f"<{t}>", "nanoregex timed out")]
    diffs = compare_case(ref, act)
    if not diffs:
        return "ok", None
    for api, rv, av in diffs:
        for w in WHITELIST:
            reason = w(case, api, rv, av)
            if reason:
                return "whitelisted", [(api, rv, av, reason)]
    return "mismatch", diffs


def fmt_mismatch(case, diffs):
    lines = [
        f"pattern={case['pattern']!r} subject={case['subject']!r} "
        f"bucket={case['bucket']}"
    ]
    for d in diffs:
        lines.append(f"  {d[0]}:\n    re        = {d[1]!r}\n    nanoregex = {d[2]!r}")
    return "\n".join(lines)
