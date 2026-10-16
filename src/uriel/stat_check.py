"""Deterministic statistical-consistency checks for manuscript text.

The checker recomputes what can be recomputed from the reported numbers
alone.  It never decides whether a test was appropriate, whether assumptions
hold, or whether a result is scientifically meaningful.  It only reports
numbers that cannot all be true at the same time:

- a p-value that does not match its reported test statistic and degrees of
  freedom (t, F, chi-square, correlation r, z), using the rounding interval of
  the reported statistic, in the spirit of published consistency checkers;
- a significance decision that flips at alpha = .05 after recomputation
  (a *decision* inconsistency);
- impossible values: p outside [0, 1], |r| > 1, negative dispersion, a
  confidence interval whose lower bound exceeds its upper bound, an estimate
  outside its own interval, "k of n" with k > n, or "X% of" above 100;
- a percentage that does not match its own count and denominator;
- GRIM-inconsistent means for integer-valued data (structured callers only).

All distribution functions use the Python standard library.  Results are
review leads with exact locations, not a statistical audit.
"""
from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

STAT_CHECK_VERSION = "uriel-stat-check-1.0.0"
ALPHA = 0.05

_NUM = r"[-\u2212]?(?:\d+(?:\.\d+)?|\.\d+)"
_UNUM = r"(?:\d+(?:\.\d+)?|\.\d+)"
_CMP = r"(?:<=|>=|=|<|>|\u2264|\u2265)"

_TEST_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<stat>t|F|r|z|Z|\u03c7\s*\u00b2|\u03c7\s*\^?\s*2|chi\s*\^?\s*2|chi-square|X\s*\^?\s*2)"
    r"\s*"
    r"(?:\(\s*(?P<df1>\d+(?:\.\d+)?)\s*(?:,\s*(?P<df2>\d+(?:\.\d+)?))?"
    r"(?:\s*[,;]\s*[Nn]\s*=\s*[\d,]+)?\s*\))?"
    r"\s*=\s*(?P<value>" + _NUM + r")"
    r"\s*[,;]\s*"
    r"p\s*(?P<cmp>" + _CMP + r")\s*(?P<p>" + _UNUM + r")",
)
_P_RE = re.compile(r"(?<![A-Za-z0-9_])p\s*(?P<cmp>" + _CMP + r")\s*(?P<p>" + _NUM + r")(?!\d)(?!\.\d)")
_R_RE = re.compile(
    r"(?<![A-Za-z0-9_])r\s*(?:\(\s*\d+\s*\))?\s*=\s*(?P<value>" + _NUM + r")(?=\s*[,;)]\s*(?:p\b|95|9\d\s*%|\d))"
)
_R_DF_RE = re.compile(r"(?<![A-Za-z0-9_])r\s*\(\s*\d+\s*\)\s*=\s*(?P<value>" + _NUM + r")")
_DISPERSION_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?P<name>SD|SE|SEM|s\.d\.|variance|Var)\s*=\s*(?P<value>-|\u2212)\s*(?:\d|\.\d)"
)
_CI_RE = re.compile(
    r"(?P<level>\d{1,3}(?:\.\d+)?)\s*%\s*"
    r"(?:CI|C\.I\.|CrI|confidence interval|credible interval)"
    r"\s*[:=,]?\s*(?P<open>[\[(])?\s*"
    r"(?P<lo>" + _NUM + r")\s*(?:,|;|\bto\b|\u2013|\u2014)\s*(?P<hi>" + _NUM + r")"
    r"\s*[\])]?"
)
_ESTIMATE_BEFORE_CI_RE = re.compile(
    r"(?P<name>[A-Za-z\u0370-\u03ff][A-Za-z0-9_\u0370-\u03ff']{0,15})\s*=\s*(?P<est>" + _NUM + r")"
    r"\s*[,;]?\s*[\[(]?\s*$"
)
_COUNT_PERCENT_RE = re.compile(
    r"(?<![\d.])(?P<k>\d{1,9})\s*(?:/|\bof\b|\bout of\b)\s*(?P<n>\d{1,9})(?!\d)(?!\.\d)"
    r"(?:\s+[A-Za-z][\w-]*){0,3}\s*\(\s*(?P<pct>" + _UNUM + r")\s*%\s*\)"
)
_PERCENT_OF_RE = re.compile(r"(?<![\d.])(?P<pct>" + _UNUM + r")\s*%\s+of\b")
_ONE_TAILED_RE = re.compile(r"\b(?:one[- ]tailed|one[- ]sided|directional)\b", re.IGNORECASE)


def _to_float(token: str) -> float:
    return float(token.replace("\u2212", "-"))


def decimals_of(token: str) -> int:
    """Number of reported decimal places in a numeric token."""
    clean = token.replace("\u2212", "").replace("-", "").strip()
    if "." not in clean:
        return 0
    return len(clean.split(".", 1)[1])


def _half_unit(token: str) -> float:
    return 0.5 * (10.0 ** (-decimals_of(token)))


# ---------------------------------------------------------------------------
# Distribution functions (standard library only)
# ---------------------------------------------------------------------------

def _betacf(a: float, b: float, x: float) -> float:
    fpmin = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-16:
            break
    return h


def regularized_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta function I_x(a, b)."""
    if a <= 0 or b <= 0:
        raise ValueError("beta parameters must be positive")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _gamma_series(a: float, x: float) -> float:
    total = 1.0 / a
    term = total
    ap = a
    for _ in range(1000):
        ap += 1.0
        term *= x / ap
        total += term
        if abs(term) < abs(total) * 3e-16:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_cf(a: float, x: float) -> float:
    fpmin = 1e-300
    b = x + 1.0 - a
    c = 1.0 / fpmin
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-16:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def regularized_gamma_upper(a: float, x: float) -> float:
    """Regularized upper incomplete gamma function Q(a, x)."""
    if a <= 0:
        raise ValueError("gamma parameter must be positive")
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gamma_series(a, x)
    return _gamma_cf(a, x)


def p_from_t(t: float, df: float) -> float:
    """Two-tailed p-value for Student's t."""
    if df <= 0:
        raise ValueError("df must be positive")
    return regularized_beta(df / 2.0, 0.5, df / (df + t * t))


def p_from_f(f: float, df1: float, df2: float) -> float:
    """Upper-tail p-value for an F statistic."""
    if df1 <= 0 or df2 <= 0:
        raise ValueError("df must be positive")
    if f <= 0:
        return 1.0
    return regularized_beta(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * f))


def p_from_chi2(x: float, df: float) -> float:
    """Upper-tail p-value for a chi-square statistic."""
    if df <= 0:
        raise ValueError("df must be positive")
    return regularized_gamma_upper(df / 2.0, max(x, 0.0) / 2.0)


def p_from_z(z: float) -> float:
    """Two-tailed p-value for a standard normal statistic."""
    return math.erfc(abs(z) / math.sqrt(2.0))


def p_from_r(r: float, df: float) -> float:
    """Two-tailed p-value for a Pearson correlation with df = n - 2."""
    if abs(r) >= 1.0:
        return 0.0
    return p_from_t(r * math.sqrt(df / (1.0 - r * r)), df)


# ---------------------------------------------------------------------------
# GRIM
# ---------------------------------------------------------------------------

def grim_consistent(mean_token: str, n: int, items: int = 1) -> bool:
    """Return True when a reported mean is achievable from integer data.

    ``mean_token`` keeps its reported decimals (``"3.47"``).  The data are
    assumed to be integer sums over ``n`` respondents and ``items`` items.  Both
    half-up and half-even rounding are accepted to avoid false alarms.
    """
    if n <= 0 or items <= 0:
        raise ValueError("n and items must be positive")
    try:
        reported = Decimal(mean_token.replace("\u2212", "-"))
    except InvalidOperation as exc:
        raise ValueError("mean is not numeric") from exc
    places = decimals_of(mean_token)
    quantum = Decimal(1).scaleb(-places)
    denominator = Decimal(n * items)
    centre = int((reported * denominator).to_integral_value())
    for total in range(centre - 2, centre + 3):
        candidate = Decimal(total) / denominator
        for rounding in (ROUND_HALF_UP, ROUND_HALF_EVEN):
            if candidate.quantize(quantum, rounding=rounding) == reported:
                return True
    return False


# ---------------------------------------------------------------------------
# Text scanning
# ---------------------------------------------------------------------------

def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _excerpt(text: str, start: int, end: int) -> str:
    return " ".join(text[start:end].split())[:200]


def _issue(code: str, text: str, start: int, end: int, message: str, *, grave: bool, **detail: Any) -> Dict[str, Any]:
    return {
        "code": code,
        "line": _line_of(text, start),
        "excerpt": _excerpt(text, start, end),
        "message": message,
        "grave": grave,
        "detail": detail,
    }


def _context(text: str, start: int, end: int) -> str:
    left = text.rfind("\n", 0, start)
    right = text.find("\n", end)
    return text[left + 1: right if right >= 0 else len(text)]


def _p_range(stat: str, value_token: str, df1: Optional[float], df2: Optional[float]) -> Optional[Tuple[float, float, float]]:
    value = abs(_to_float(value_token))
    half = _half_unit(value_token)
    lower = max(value - half, 0.0)
    upper = value + half
    if stat == "t":
        if df1 is None:
            return None
        fn = lambda v: p_from_t(v, df1)  # noqa: E731
    elif stat == "F":
        if df1 is None or df2 is None:
            return None
        value = _to_float(value_token)
        lower = max(value - half, 0.0)
        upper = value + half
        fn = lambda v: p_from_f(v, df1, df2)  # noqa: E731
    elif stat == "chi2":
        if df1 is None:
            return None
        fn = lambda v: p_from_chi2(v, df1)  # noqa: E731
    elif stat == "r":
        if df1 is None or value > 1.0:
            return None
        upper = min(upper, 0.999999999)
        lower = min(lower, upper)
        fn = lambda v: p_from_r(v, df1)  # noqa: E731
    elif stat == "z":
        fn = p_from_z
    else:
        return None
    return fn(upper), fn(lower), fn(value)


def _normalize_stat(raw: str) -> str:
    compact = re.sub(r"[\s^\u00b2]", "", raw).lower()
    if raw in ("t", "F", "r"):
        return raw
    if raw in ("z", "Z"):
        return "z"
    if compact.startswith(("\u03c7", "chi", "x")):
        return "chi2"
    return raw


def _reported_significant(cmp: str, p: float) -> Optional[bool]:
    if cmp in ("=", "<", "<=", "\u2264"):
        return p <= ALPHA
    if cmp in (">", ">=", "\u2265"):
        return False if p >= ALPHA else None
    return None


def _consistent(cmp: str, reported: float, reported_token: str, lo: float, hi: float) -> bool:
    eps = 1e-12
    if cmp == "=":
        half = _half_unit(reported_token)
        return not (hi < reported - half - eps or lo > reported + half + eps)
    if cmp in ("<", "<=", "\u2264"):
        return lo < reported + eps
    return hi > reported - eps


def check_reported_tests(text: str) -> List[Dict[str, Any]]:
    """Recompute every reported test statistic with an exact p-value."""
    issues: List[Dict[str, Any]] = []
    for match in _TEST_RE.finditer(text):
        stat = _normalize_stat(match.group("stat"))
        df1 = float(match.group("df1")) if match.group("df1") else None
        df2 = float(match.group("df2")) if match.group("df2") else None
        value_token = match.group("value")
        p_token = match.group("p")
        cmp = match.group("cmp").replace("\u2264", "<=").replace("\u2265", ">=")
        reported_p = _to_float(p_token)
        if stat == "F" and df2 is None:
            continue
        if stat in ("t", "chi2", "r") and df1 is None:
            continue
        if reported_p > 1.0:
            continue  # reported separately as an impossible p-value
        if stat == "r" and abs(_to_float(value_token)) > 1.0:
            continue  # reported separately as an impossible correlation
        try:
            computed = _p_range(stat, value_token, df1, df2)
        except (ValueError, OverflowError, ZeroDivisionError):
            continue
        if computed is None:
            continue
        lo, hi, point = computed
        candidates = [(lo, hi, False)]
        if _ONE_TAILED_RE.search(_context(text, match.start(), match.end())) and stat in ("t", "z", "r"):
            candidates.append((lo / 2.0, hi / 2.0, True))
        if any(_consistent(cmp, reported_p, p_token, a, b) for a, b, _ in candidates):
            continue
        reported_sig = _reported_significant(cmp, reported_p)
        computed_sig: Optional[bool]
        if all(b < ALPHA for _, b, _ in candidates):
            computed_sig = True
        elif all(a >= ALPHA for a, _, _ in candidates):
            computed_sig = False
        else:
            computed_sig = None
        grave = reported_sig is not None and computed_sig is not None and reported_sig != computed_sig
        detail = {
            "statistic": stat,
            "value": value_token.replace("\u2212", "-"),
            "df": [value for value in (df1, df2) if value is not None],
            "reported_p": "{0} {1}".format(cmp, p_token),
            "recomputed_p": round(point, 6),
            "recomputed_p_range": [round(lo, 6), round(hi, 6)],
            "alpha": ALPHA,
            "tails": "two-tailed (one-tailed also tried)" if len(candidates) > 1 else "two-tailed",
        }
        if grave:
            issues.append(_issue(
                "STAT_DECISION_INCONSISTENT", text, match.start(), match.end(),
                "The reported p-value and the recomputed p-value fall on opposite sides of alpha = .05, "
                "so the stated significance decision cannot follow from these numbers.",
                grave=True, **detail,
            ))
        else:
            issues.append(_issue(
                "STAT_P_INCONSISTENT", text, match.start(), match.end(),
                "The reported p-value does not match the p-value recomputed from the reported statistic "
                "and degrees of freedom, even allowing for rounding.",
                grave=False, **detail,
            ))
    return issues


def check_impossible_values(text: str) -> List[Dict[str, Any]]:
    """Report values that cannot be true regardless of the analysis."""
    issues: List[Dict[str, Any]] = []
    for match in _P_RE.finditer(text):
        token = match.group("p")
        value = _to_float(token)
        if value > 1.0 or value < 0.0:
            issues.append(_issue(
                "STAT_IMPOSSIBLE_P", text, match.start(), match.end(),
                "A p-value must lie between 0 and 1.", grave=True, value=token,
            ))
        elif value == 0.0 and match.group("cmp") == "=":
            issues.append(_issue(
                "STAT_P_REPORTED_AS_ZERO", text, match.start(), match.end(),
                "A p-value is never exactly zero; a rounded zero should be reported as an inequality such as p < .001.",
                grave=False, value=token,
            ))
    seen_r = set()
    for pattern in (_R_DF_RE, _R_RE):
        for match in pattern.finditer(text):
            if match.start() in seen_r:
                continue
            seen_r.add(match.start())
            token = match.group("value")
            if abs(_to_float(token)) > 1.0:
                issues.append(_issue(
                    "STAT_IMPOSSIBLE_CORRELATION", text, match.start(), match.end(),
                    "A correlation coefficient must lie between -1 and 1.", grave=True, value=token,
                ))
    for match in _DISPERSION_RE.finditer(text):
        issues.append(_issue(
            "STAT_NEGATIVE_DISPERSION", text, match.start(), match.end(),
            "A standard deviation, standard error, or variance cannot be negative.",
            grave=True, name=match.group("name"),
        ))
    for match in _CI_RE.finditer(text):
        level = float(match.group("level"))
        lo_token, hi_token = match.group("lo"), match.group("hi")
        lo, hi = _to_float(lo_token), _to_float(hi_token)
        if not 0.0 < level < 100.0:
            issues.append(_issue(
                "STAT_IMPOSSIBLE_CI_LEVEL", text, match.start(), match.end(),
                "An interval's coverage level must be strictly between 0% and 100%.",
                grave=True, level=match.group("level"),
            ))
            continue
        if lo > hi:
            issues.append(_issue(
                "STAT_CI_BOUNDS_REVERSED", text, match.start(), match.end(),
                "The interval's lower bound is larger than its upper bound.",
                grave=True, lower=lo_token, upper=hi_token,
            ))
            continue
        before = text[max(0, match.start() - 48): match.start()]
        estimate = _ESTIMATE_BEFORE_CI_RE.search(before)
        if estimate:
            est_token = estimate.group("est")
            est = _to_float(est_token)
            tolerance = max(_half_unit(est_token), _half_unit(lo_token), _half_unit(hi_token)) + 1e-12
            if est < lo - tolerance or est > hi + tolerance:
                start = match.start() - (len(before) - estimate.start())
                issues.append(_issue(
                    "STAT_ESTIMATE_OUTSIDE_CI", text, start, match.end(),
                    "The point estimate lies outside its own reported interval.",
                    grave=True, estimate=est_token, lower=lo_token, upper=hi_token,
                    name=estimate.group("name"),
                ))
    for match in _COUNT_PERCENT_RE.finditer(text):
        k, n = int(match.group("k")), int(match.group("n"))
        pct_token = match.group("pct")
        if n == 0:
            continue
        if k > n:
            issues.append(_issue(
                "STAT_COUNT_EXCEEDS_TOTAL", text, match.start(), match.end(),
                "The count is larger than its own denominator.", grave=True, count=k, total=n,
            ))
            continue
        expected = 100.0 * k / n
        tolerance = _half_unit(pct_token) + 1e-9
        reported = _to_float(pct_token)
        if abs(reported - expected) > tolerance:
            issues.append(_issue(
                "STAT_PERCENT_COUNT_MISMATCH", text, match.start(), match.end(),
                "The percentage does not equal the count divided by the denominator at the reported precision.",
                grave=False, count=k, total=n, reported_percent=pct_token,
                recomputed_percent=round(expected, 4),
            ))
    for match in _PERCENT_OF_RE.finditer(text):
        value = _to_float(match.group("pct"))
        if value > 100.0:
            issues.append(_issue(
                "STAT_PERCENT_OF_EXCEEDS_100", text, match.start(), match.end(),
                "A share \"X% of\" a group cannot exceed 100%; if this is a ratio to a reference value, "
                "name the reference explicitly so readers cannot misread it as a share.",
                grave=False, value=match.group("pct"),
            ))
    return issues


def check_text(text: str) -> Dict[str, Any]:
    """Run every text-level statistical consistency check."""
    issues = check_reported_tests(text) + check_impossible_values(text)
    issues.sort(key=lambda row: (row["line"], row["code"], row["excerpt"]))
    return {
        "version": STAT_CHECK_VERSION,
        "issue_count": len(issues),
        "grave_count": sum(1 for row in issues if row["grave"]),
        "reported_tests_found": len(list(_TEST_RE.finditer(text))),
        "issues": issues,
        "boundaries": {
            "method_appropriateness_decided": False,
            "assumptions_checked": False,
            "scientific_truth_decided": False,
        },
    }


__all__ = [
    "ALPHA",
    "STAT_CHECK_VERSION",
    "check_impossible_values",
    "check_reported_tests",
    "check_text",
    "decimals_of",
    "grim_consistent",
    "p_from_chi2",
    "p_from_f",
    "p_from_r",
    "p_from_t",
    "p_from_z",
    "regularized_beta",
    "regularized_gamma_upper",
]
