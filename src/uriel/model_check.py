"""Model and equation checks: is the equation well formed, and does it claim what it can support?

Two different questions are asked of every model recorded in
``uriel.project.json`` under ``models``:

1. **Is it properly articulated?**  Every symbol must be defined with a
   meaning and a unit, the equation must parse, and it must be dimensionally
   consistent: both sides carry the same dimension, only like quantities are
   added, and the arguments of ``exp``, ``log``, trigonometric functions, and
   symbolic exponents are dimensionless.
2. **Does it describe what it claims to?**  A model must declare its ``role``:
   ``descriptive_fit`` (it reproduces the observations, with no claim that its
   terms are physically real, the stance of the anonymous preface to
   Copernicus' *De revolutionibus*), ``predictive`` (it forecasts new
   observations), or ``mechanistic`` (its terms correspond to real causes).
   Predictive and mechanistic models need validation on data they were not
   fitted to and a comparison with at least one rival model. A manuscript may
   not describe a ``descriptive_fit`` as a mechanism or law, and may not state
   a model as settled when a rival fits the data equally well.

Dimensional consistency is checked exactly.  Whether the model is the right
model is not something a checker can decide; it can only insist that the
paper says what kind of claim it makes and shows the evidence that claim needs.
"""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

MODEL_ROLES = ("descriptive_fit", "predictive", "mechanistic")
RIVAL_OUTCOMES = ("favoured", "not_distinguished", "disfavoured")
VERIFICATION_METHODS = (
    "dimensional_analysis",
    "independent_derivation",
    "symbolic_check",
    "numerical_check",
    "code_test",
    "limiting_case",
    "literature_check",
)
BASE_DIMENSIONS = ("L", "M", "T", "I", "Theta", "N", "J")
Dim = Tuple[Tuple[str, Fraction], ...]

_DIMENSIONLESS: Dict[str, Fraction] = {}


def _dim(**exponents: Any) -> Dict[str, Fraction]:
    return {key: Fraction(value) for key, value in exponents.items() if value}


_UNITS: Dict[str, Dict[str, Fraction]] = {
    "1": {}, "dimensionless": {}, "rad": {}, "sr": {}, "%": {}, "ppm": {}, "ppb": {}, "count": {},
    "m": _dim(L=1), "g": _dim(M=1), "s": _dim(T=1), "A": _dim(I=1), "K": _dim(Theta=1),
    "mol": _dim(N=1), "cd": _dim(J=1),
    "N": _dim(M=1, L=1, T=-2), "J": _dim(M=1, L=2, T=-2), "W": _dim(M=1, L=2, T=-3),
    "Pa": _dim(M=1, L=-1, T=-2), "Hz": _dim(T=-1), "C": _dim(I=1, T=1),
    "V": _dim(M=1, L=2, T=-3, I=-1), "ohm": _dim(M=1, L=2, T=-3, I=-2), "\u03a9": _dim(M=1, L=2, T=-3, I=-2),
    "F": _dim(M=-1, L=-2, T=4, I=2), "Wb": _dim(M=1, L=2, T=-2, I=-1), "T": _dim(M=1, T=-2, I=-1),
    "H": _dim(M=1, L=2, T=-2, I=-2), "S": _dim(M=-1, L=-2, T=3, I=2),
    "L": _dim(L=3), "l": _dim(L=3), "min": _dim(T=1), "h": _dim(T=1), "d": _dim(T=1), "day": _dim(T=1),
    "yr": _dim(T=1), "year": _dim(T=1), "eV": _dim(M=1, L=2, T=-2), "cal": _dim(M=1, L=2, T=-2),
    "bar": _dim(M=1, L=-1, T=-2), "atm": _dim(M=1, L=-1, T=-2), "degC": _dim(Theta=1),
    "\u00b0C": _dim(Theta=1), "au": _dim(L=1), "pc": _dim(L=1), "ly": _dim(L=1), "M": _dim(N=1, L=-3),
}
_PREFIXABLE = {"m", "g", "s", "A", "K", "mol", "N", "J", "W", "Pa", "Hz", "C", "V", "F", "T", "L", "l", "eV", "ohm", "\u03a9", "M", "bar", "cal", "Wb", "H", "S"}
_PREFIXES = ("da", "k", "M", "G", "T", "P", "h", "d", "c", "m", "u", "\u00b5", "\u03bc", "n", "p", "f")
_FUNCTIONS_DIMENSIONLESS = {"exp", "log", "ln", "log10", "log2", "sin", "cos", "tan", "sinh", "cosh", "tanh",
                            "asin", "acos", "atan", "logit", "expit", "sigmoid", "Phi", "erf"}
_FUNCTIONS_SAME = {"abs", "min", "max"}
_TOKEN = re.compile(
    r"\s*(?:(?P<number>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)|"
    r"(?P<name>[A-Za-z\u0370-\u03ff\u0394][A-Za-z0-9_\u0370-\u03ff'\u0394]*)|"
    r"(?P<op>\*\*|\^|\*|/|\+|-|\u2212|\u00b7|\u00d7|\(|\)|,|=))"
)


class ModelSyntaxError(ValueError):
    """The equation or unit string cannot be parsed."""


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

def _lookup_unit(token: str) -> Optional[Dict[str, Fraction]]:
    if token in _UNITS:
        return dict(_UNITS[token])
    if token.startswith("[") and token.endswith("]") and len(token) > 2:
        return {token: Fraction(1)}  # a declared custom base dimension such as [score] or [USD]
    for prefix in _PREFIXES:
        if token.startswith(prefix) and token[len(prefix):] in _PREFIXABLE:
            return dict(_UNITS[token[len(prefix):]])
    return None


def parse_unit(text: str) -> Dict[str, Fraction]:
    """Parse a unit such as ``kg*m/s^2``, ``m s^-1``, ``1``, or ``[score]/s``."""
    source = str(text).strip()
    if not source:
        raise ModelSyntaxError("empty unit")
    tokens = re.findall(r"\[[^\]\s]+\]|[A-Za-z\u00b0\u00b5\u03a9\u03bc%]+|-?\d+(?:/\d+)?|[*/^()\u00b7. ]", source)
    if "".join(tokens).replace(" ", "") != source.replace(" ", ""):
        raise ModelSyntaxError("unrecognized characters in unit '{0}'".format(source))
    position = 0
    tokens = [token for token in tokens if token.strip()]

    def factor() -> Dict[str, Fraction]:
        nonlocal position
        if position >= len(tokens):
            raise ModelSyntaxError("unit ends unexpectedly")
        token = tokens[position]
        position += 1
        if token == "(":
            value = product()
            if position >= len(tokens) or tokens[position] != ")":
                raise ModelSyntaxError("unbalanced parentheses in unit")
            position += 1
        elif re.fullmatch(r"-?\d+(?:/\d+)?", token):
            if token != "1":
                raise ModelSyntaxError("numbers other than 1 cannot stand alone in a unit")
            value = {}
        else:
            found = _lookup_unit(token)
            if found is None:
                raise ModelSyntaxError("unknown unit '{0}' (use [name] for a custom dimension)".format(token))
            value = found
        if position < len(tokens) and tokens[position] == "^":
            position += 1
            if position >= len(tokens) or not re.fullmatch(r"-?\d+(?:/\d+)?", tokens[position]):
                raise ModelSyntaxError("unit exponents must be integers or fractions")
            power = Fraction(tokens[position])
            position += 1
            value = {key: exponent * power for key, exponent in value.items()}
        elif position < len(tokens) and re.fullmatch(r"-?\d+", tokens[position]) and token not in ("(",):
            power = Fraction(tokens[position])  # m2, s-1
            position += 1
            value = {key: exponent * power for key, exponent in value.items()}
        return value

    def product() -> Dict[str, Fraction]:
        nonlocal position
        value = factor()
        while position < len(tokens) and tokens[position] not in (")",):
            operator = tokens[position]
            if operator in ("*", "\u00b7", "."):
                position += 1
                value = _combine(value, factor(), 1)
            elif operator == "/":
                position += 1
                value = _combine(value, factor(), -1)
            else:
                value = _combine(value, factor(), 1)  # implicit product: "kg m s^-2"
        return value

    result = product()
    if position != len(tokens):
        raise ModelSyntaxError("trailing tokens in unit '{0}'".format(source))
    return {key: value for key, value in result.items() if value}


def _combine(left: Mapping[str, Fraction], right: Mapping[str, Fraction], sign: int) -> Dict[str, Fraction]:
    result = dict(left)
    for key, value in right.items():
        result[key] = result.get(key, Fraction(0)) + sign * value
    return {key: value for key, value in result.items() if value}


def render_dimension(value: Mapping[str, Fraction]) -> str:
    if not value:
        return "dimensionless"
    parts = []
    for key in sorted(value):
        exponent = value[key]
        parts.append(key if exponent == 1 else "{0}^{1}".format(key, exponent))
    return "\u00b7".join(parts)


# ---------------------------------------------------------------------------
# Equations
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[Tuple[str, str]]:
    tokens: List[Tuple[str, str]] = []
    position = 0
    stripped = text.strip()
    while position < len(stripped):
        match = _TOKEN.match(stripped, position)
        if not match or match.end() == position:
            raise ModelSyntaxError("unexpected character '{0}' at position {1}".format(stripped[position], position))
        position = match.end()
        for kind in ("number", "name", "op"):
            if match.group(kind) is not None:
                value = match.group(kind)
                if kind == "op":
                    value = {"**": "^", "\u2212": "-", "\u00b7": "*", "\u00d7": "*"}.get(value, value)
                tokens.append((kind, value))
                break
    return tokens


class _Node:
    __slots__ = ("kind", "value", "children")

    def __init__(self, kind: str, value: Any = None, children: Sequence["_Node"] = ()) -> None:
        self.kind = kind
        self.value = value
        self.children = list(children)


class _Parser:
    def __init__(self, tokens: List[Tuple[str, str]]) -> None:
        self.tokens = tokens
        self.position = 0

    def peek(self) -> Tuple[str, str]:
        return self.tokens[self.position] if self.position < len(self.tokens) else ("end", "")

    def take(self, value: Optional[str] = None) -> Tuple[str, str]:
        token = self.peek()
        if value is not None and token[1] != value:
            raise ModelSyntaxError("expected '{0}' but found '{1}'".format(value, token[1] or "end of equation"))
        if token[0] == "end":
            raise ModelSyntaxError("equation ends unexpectedly")
        self.position += 1
        return token

    def equation(self) -> Tuple[_Node, _Node]:
        left = self.expression()
        self.take("=")
        right = self.expression()
        if self.peek()[0] != "end":
            raise ModelSyntaxError("unexpected '{0}' after the equation".format(self.peek()[1]))
        return left, right

    def expression(self) -> _Node:
        node = self.term()
        while self.peek()[1] in ("+", "-"):
            operator = self.take()[1]
            node = _Node("add", operator, [node, self.term()])
        return node

    def term(self) -> _Node:
        node = self.power()
        while True:
            kind, value = self.peek()
            if value in ("*", "/"):
                self.take()
                node = _Node("mul", value, [node, self.power()])
            elif kind in ("number", "name") or value == "(":
                node = _Node("mul", "*", [node, self.power()])  # implicit multiplication: 2 x, a (b + c)
            else:
                return node

    def power(self) -> _Node:
        base = self.unary()
        if self.peek()[1] == "^":
            self.take()
            exponent = self.power()
            return _Node("pow", None, [base, exponent])
        return base

    def unary(self) -> _Node:
        if self.peek()[1] in ("-", "+"):
            self.take()
            return _Node("neg", None, [self.unary()])
        return self.atom()

    def atom(self) -> _Node:
        kind, value = self.peek()
        if kind == "number":
            self.take()
            return _Node("number", Fraction(value) if "e" not in value.lower() else float(value))
        if kind == "name":
            self.take()
            if self.peek()[1] == "(" and (value in _FUNCTIONS_DIMENSIONLESS or value in _FUNCTIONS_SAME or value == "sqrt"):
                self.take("(")
                args = [self.expression()]
                while self.peek()[1] == ",":
                    self.take()
                    args.append(self.expression())
                self.take(")")
                return _Node("call", value, args)
            return _Node("symbol", value)
        if value == "(":
            self.take()
            node = self.expression()
            self.take(")")
            return node
        raise ModelSyntaxError("unexpected '{0}'".format(value or "end of equation"))


def parse_equation(text: str) -> Tuple[_Node, _Node]:
    return _Parser(_tokenize(text)).equation()


def equation_symbols(text: str) -> List[str]:
    left, right = parse_equation(text)
    found: List[str] = []

    def walk(node: _Node) -> None:
        if node.kind == "symbol" and node.value not in found:
            found.append(node.value)
        for child in node.children:
            walk(child)

    walk(left)
    walk(right)
    return found


def _numeric_value(node: _Node) -> Optional[Fraction]:
    if node.kind == "number":
        return Fraction(node.value) if not isinstance(node.value, float) else Fraction(node.value).limit_denominator(1000)
    if node.kind == "neg":
        inner = _numeric_value(node.children[0])
        return -inner if inner is not None else None
    if node.kind == "mul":
        left, right = (_numeric_value(child) for child in node.children)
        if left is None or right is None:
            return None
        if node.value == "/":
            return left / right if right != 0 else None
        return left * right
    if node.kind == "add":
        left, right = (_numeric_value(child) for child in node.children)
        if left is None or right is None:
            return None
        return left + right if node.value == "+" else left - right
    return None


def check_dimensions(equation: str, units: Mapping[str, Mapping[str, Fraction]]) -> List[str]:
    """Return human-readable dimensional inconsistencies (empty when consistent)."""
    left, right = parse_equation(equation)
    problems: List[str] = []

    def dims(node: _Node) -> Optional[Dict[str, Fraction]]:
        if node.kind == "number":
            return {}
        if node.kind == "symbol":
            return dict(units[node.value]) if node.value in units else None
        if node.kind == "neg":
            return dims(node.children[0])
        if node.kind == "add":
            first, second = dims(node.children[0]), dims(node.children[1])
            if first is not None and second is not None and first != second:
                problems.append("'{0}' adds {1} to {2}".format(
                    node.value, render_dimension(first), render_dimension(second)))
            return first if first is not None else second
        if node.kind == "mul":
            first, second = dims(node.children[0]), dims(node.children[1])
            if first is None or second is None:
                return None
            return _combine(first, second, 1 if node.value == "*" else -1)
        if node.kind == "pow":
            base, exponent_node = node.children
            base_dims = dims(base)
            exponent_dims = dims(exponent_node)
            if exponent_dims:
                problems.append("an exponent has dimension {0}; exponents must be dimensionless".format(
                    render_dimension(exponent_dims)))
            power = _numeric_value(exponent_node)
            if base_dims is None:
                return None
            if power is None:
                if base_dims:
                    problems.append("a quantity with dimension {0} is raised to a symbolic power".format(
                        render_dimension(base_dims)))
                return {}
            return {key: value * power for key, value in base_dims.items() if value * power}
        if node.kind == "call":
            arguments = [dims(child) for child in node.children]
            if node.value in _FUNCTIONS_DIMENSIONLESS:
                for argument in arguments:
                    if argument:
                        problems.append("{0}() is applied to a quantity with dimension {1}; its argument must be "
                                        "dimensionless".format(node.value, render_dimension(argument)))
                return {}
            if node.value == "sqrt":
                if arguments[0] is None:
                    return None
                return {key: value / 2 for key, value in arguments[0].items()}
            known = [argument for argument in arguments if argument is not None]
            if len({render_dimension(argument) for argument in known}) > 1:
                problems.append("{0}() combines arguments with different dimensions".format(node.value))
            return known[0] if known else None
        return None

    left_dims, right_dims = dims(left), dims(right)
    if left_dims is not None and right_dims is not None and left_dims != right_dims:
        problems.append("the left side has dimension {0} but the right side has {1}".format(
            render_dimension(left_dims), render_dimension(right_dims)))
    return problems


# ---------------------------------------------------------------------------
# Model records
# ---------------------------------------------------------------------------

PROJECT_CODES = frozenset({
    "MODEL_RECORD_INVALID",
    "MODEL_EQUATION_MISSING",
    "MODEL_EQUATION_UNPARSEABLE",
    "MODEL_SYMBOL_UNDEFINED",
    "MODEL_SYMBOL_UNUSED",
    "MODEL_UNIT_MISSING",
    "MODEL_UNIT_UNKNOWN",
    "MODEL_DIMENSIONS_INCONSISTENT",
    "MODEL_ROLE_UNDECLARED",
    "MODEL_ASSUMPTIONS_MISSING",
    "MODEL_DOMAIN_MISSING",
    "MODEL_SOURCE_UNDECLARED",
    "MODEL_UNVERIFIED",
    "MODEL_IMPLEMENTATION_UNTESTED",
    "MODEL_NOT_VALIDATED",
    "MODEL_NO_RIVAL",
    "MODEL_UNDERDETERMINED",
})
DESIGN_CODES = frozenset({
    "MODEL_RECORD_INVALID", "MODEL_EQUATION_MISSING", "MODEL_EQUATION_UNPARSEABLE", "MODEL_SYMBOL_UNDEFINED",
    "MODEL_UNIT_MISSING", "MODEL_UNIT_UNKNOWN", "MODEL_DIMENSIONS_INCONSISTENT", "MODEL_ROLE_UNDECLARED",
    "MODEL_ASSUMPTIONS_MISSING", "MODEL_DOMAIN_MISSING", "MODEL_SOURCE_UNDECLARED",
})
EVIDENCE_CODES = frozenset({"MODEL_UNVERIFIED", "MODEL_IMPLEMENTATION_UNTESTED"})

MECHANISM_LANGUAGE = re.compile(
    r"\b(?:mechanism(?:s)?|mechanistic|underlying|governs?|governed by|(?:the|a) (?:physical |natural )?law|"
    r"explains? why|describes? how|true (?:model|process|relationship)|real(?:ly)? (?:is|are)|causal(?:ly)?|"
    r"causes?|generat(?:es|ed) by|physical(?:ly)? meaning(?:ful)?)\b",
    re.IGNORECASE,
)
_SETTLED_MODEL = re.compile(
    r"\b(?:show(?:s|ed|n)?|demonstrat(?:e|es|ed)|establish(?:es|ed)?|confirm(?:s|ed)?|prove[sdn]?|the correct model|is correct|"
    r"best (?:describes|explains)|(?:is|are) (?:the )?true|outperforms)\b",
    re.IGNORECASE,
)
MODEL_ANCHOR = re.compile(r"\[model:([A-Za-z0-9][A-Za-z0-9._-]{0,63})\]")
_MATH_EQUATION = re.compile(r"\$\$[^$]*=[^$]*\$\$|(?<!\$)\$[^$\n]*=[^$\n]*\$(?!\$)|\\begin\{(?:equation|align)\*?\}")


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _strings(value: Any) -> List[str]:
    return [_text(item) for item in value if _text(item)] if isinstance(value, list) else []


def _issue(code: str, level: str, subject: str, message: str, **detail: Any) -> Dict[str, Any]:
    return {"code": code, "level": level, "subject": subject, "message": message, "detail": detail,
            "line": detail.pop("line", None), "excerpt": detail.pop("excerpt", "")}


def model_table(project: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    rows = project.get("models")
    if not isinstance(rows, list):
        return {}
    return {str(row.get("id")): row for row in rows if isinstance(row, Mapping) and row.get("id")}


def project_issues(
    project: Mapping[str, Any],
    *,
    tested_pairs: Optional[Set[Tuple[str, str]]] = None,
    current_digests: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Issues in the recorded models; ``tested_pairs`` holds (path, sha256) left by verified passing runs."""
    issues: List[Dict[str, Any]] = []
    models = project.get("models")
    if models is None:
        return issues
    if not isinstance(models, list):
        return [_issue("MODEL_RECORD_INVALID", "grave", "Models", "/models must be an array of model records.")]
    evidence = {str(row.get("id")) for row in project.get("evidence", []) if isinstance(row, Mapping) and row.get("id")} \
        if isinstance(project.get("evidence"), list) else set()
    seen: Set[str] = set()
    for index, row in enumerate(models):
        if not isinstance(row, Mapping) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", str(row.get("id", ""))):
            issues.append(_issue("MODEL_RECORD_INVALID", "grave", "models[{0}]".format(index),
                                 "Each model needs a portable id."))
            continue
        identifier = str(row["id"])
        subject = "Model {0}".format(identifier)
        if identifier in seen:
            issues.append(_issue("MODEL_RECORD_INVALID", "grave", subject, "The model id is used more than once."))
            continue
        seen.add(identifier)
        equation = _text(row.get("equation"))
        symbols = row.get("symbols") if isinstance(row.get("symbols"), Mapping) else {}
        if not equation:
            issues.append(_issue("MODEL_EQUATION_MISSING", "submission", subject,
                                 "The model has no equation, so its terms cannot be checked."))
        used: List[str] = []
        parsed = False
        if equation:
            try:
                used = equation_symbols(equation)
                parsed = True
            except ModelSyntaxError as exc:
                issues.append(_issue("MODEL_EQUATION_UNPARSEABLE", "submission", subject,
                                     "The equation cannot be parsed: {0}.".format(exc), equation=equation))
        units: Dict[str, Dict[str, Fraction]] = {}
        unit_problem = False
        for name in used:
            definition = symbols.get(name) if isinstance(symbols.get(name), Mapping) else None
            if definition is None or len(_text(definition.get("meaning"))) < 3:
                issues.append(_issue("MODEL_SYMBOL_UNDEFINED", "submission", subject,
                                     "Symbol '{0}' is used in the equation but has no recorded meaning.".format(name),
                                     symbol=name))
                unit_problem = True
                continue
            unit_text = definition.get("unit")
            if unit_text is None or not str(unit_text).strip():
                issues.append(_issue("MODEL_UNIT_MISSING", "submission", subject,
                                     "Symbol '{0}' has no unit (use \"1\" for dimensionless).".format(name), symbol=name))
                unit_problem = True
                continue
            try:
                units[name] = parse_unit(str(unit_text))
            except ModelSyntaxError as exc:
                issues.append(_issue("MODEL_UNIT_UNKNOWN", "submission", subject,
                                     "Symbol '{0}' has a unit that cannot be read: {1}.".format(name, exc), symbol=name))
                unit_problem = True
        for name in sorted(set(symbols) - set(used)) if parsed else []:
            issues.append(_issue("MODEL_SYMBOL_UNUSED", "style", subject,
                                 "Symbol '{0}' is defined but does not appear in the equation.".format(name), symbol=name))
        if parsed and not unit_problem:
            for problem in check_dimensions(equation, units):
                issues.append(_issue("MODEL_DIMENSIONS_INCONSISTENT", "grave", subject,
                                     "The equation is dimensionally inconsistent: {0}.".format(problem), equation=equation))
        role = str(row.get("role", "") or "")
        if role not in MODEL_ROLES:
            issues.append(_issue(
                "MODEL_ROLE_UNDECLARED", "submission", subject,
                "Declare whether the model is a descriptive_fit (reproduces the data, no claim its terms are real), "
                "predictive (forecasts new data), or mechanistic (its terms are real causes).",
            ))
        if not _strings(row.get("assumptions")):
            issues.append(_issue("MODEL_ASSUMPTIONS_MISSING", "submission", subject,
                                 "No assumptions are recorded for the model."))
        if len(_text(row.get("domain"))) < 8:
            issues.append(_issue("MODEL_DOMAIN_MISSING", "submission", subject,
                                 "The range of conditions in which the model is claimed to hold is not recorded."))
        source = row.get("source") if isinstance(row.get("source"), Mapping) else {}
        if source.get("kind") not in ("derived_here", "cited", "fitted") or not (
            _strings(source.get("evidence_ids")) or _text(source.get("reference_key")) or len(_text(source.get("note"))) >= 12
        ):
            issues.append(_issue("MODEL_SOURCE_UNDECLARED", "submission", subject,
                                 "Record whether the equation was derived here, fitted, or cited, and where."))
        verifications = [
            item for item in (row.get("verification") if isinstance(row.get("verification"), list) else [])
            if isinstance(item, Mapping) and item.get("method") in VERIFICATION_METHODS
            and (any(str(value) in evidence for value in _strings(item.get("evidence_ids"))) or len(_text(item.get("note"))) >= 12)
        ]
        if not verifications:
            issues.append(_issue(
                "MODEL_UNVERIFIED", "submission", subject,
                "Nothing records that the equation itself was checked (independent derivation, limiting cases, "
                "symbolic or numerical check, or a test of its implementation).",
            ))
        implementation = row.get("implementation") if isinstance(row.get("implementation"), Mapping) else {}
        artifact = _text(implementation.get("artifact_path"))
        if artifact and tested_pairs is not None:
            digest = (current_digests or {}).get(artifact)
            if digest is None or (artifact, digest) not in tested_pairs:
                issues.append(_issue(
                    "MODEL_IMPLEMENTATION_UNTESTED", "submission", subject,
                    "The code implementing the model ({0}) was not present, unchanged, in any verified passing "
                    "`uriel run`.".format(artifact), artifact_path=artifact,
                ))
        rivals = [item for item in (row.get("rivals") if isinstance(row.get("rivals"), list) else []) if isinstance(item, Mapping)]
        complete_rivals = [
            item for item in rivals
            if _text(item.get("name")) and item.get("outcome") in RIVAL_OUTCOMES and len(_text(item.get("comparison"))) >= 8
        ]
        validation = row.get("validation") if isinstance(row.get("validation"), Mapping) else {}
        validated = any(str(value) in evidence for value in _strings(validation.get("evidence_ids"))) and \
            validation.get("kind") in ("out_of_sample", "independent_dataset", "prediction_test", "experimental_test")
        if role in ("predictive", "mechanistic"):
            if not validated:
                issues.append(_issue(
                    "MODEL_NOT_VALIDATED", "submission", subject,
                    "A {0} model needs evidence from data it was not fitted to (out-of-sample, independent dataset, "
                    "prediction or experimental test).".format(role),
                ))
            if not complete_rivals:
                issues.append(_issue(
                    "MODEL_NO_RIVAL", "submission", subject,
                    "A {0} model must be compared with at least one rival model; fitting the data does not show "
                    "that another model would not fit as well.".format(role),
                ))
        elif role == "descriptive_fit" and not complete_rivals:
            issues.append(_issue("MODEL_NO_RIVAL", "style", subject,
                                 "Consider recording a rival functional form and how it compared."))
        undecided = [_text(item.get("name")) for item in complete_rivals if item.get("outcome") == "not_distinguished"]
        if undecided and role in ("predictive", "mechanistic"):
            issues.append(_issue(
                "MODEL_UNDERDETERMINED", "style", subject,
                "The data do not distinguish this model from {0}; the paper must say so.".format(", ".join(undecided)),
                rivals=undecided,
            ))
    return issues


def manuscript_issues(
    project: Mapping[str, Any],
    sections: Sequence[Tuple[Mapping[str, Any], str]],
) -> List[Dict[str, Any]]:
    """Model anchors, declared equations, and model wording in manuscript sections."""
    issues: List[Dict[str, Any]] = []
    table = model_table(project)
    anchored: Set[str] = set()
    for section, text in sections:
        file_label = section.get("file_label")
        for paragraph_match in re.finditer(r"(?:[^\n]+\n?)+", text):
            paragraph = paragraph_match.group(0)
            base = paragraph_match.start()
            ids = MODEL_ANCHOR.findall(paragraph)
            anchored.update(ids)
            line = text.count("\n", 0, base) + 1
            if _MATH_EQUATION.search(paragraph) and not ids:
                issues.append(_issue(
                    "MODEL_UNDECLARED_EQUATION", "submission", "Section {0}".format(section.get("id")),
                    "An equation appears without a [model:ID] anchor, so its symbols, units, role, and validation "
                    "are not on record.", line=line, excerpt=" ".join(_MATH_EQUATION.search(paragraph).group(0).split())[:160],
                    file=file_label,
                ))
            for identifier in ids:
                row = table.get(identifier)
                if row is None:
                    issues.append(_issue("MODEL_ANCHOR_UNKNOWN", "grave", "Model {0}".format(identifier),
                                         "The anchor names a model that is not in /models.", line=line, file=file_label))
                    continue
                for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
                    if "[model:{0}]".format(identifier) not in sentence:
                        continue
                    role = row.get("role")
                    if role == "descriptive_fit":
                        match = MECHANISM_LANGUAGE.search(sentence)
                        if match:
                            issues.append(_issue(
                                "MODEL_REALISM_OVERCLAIM", "submission", "Model {0}".format(identifier),
                                "The model is recorded as a descriptive fit, but the text calls it a mechanism or law "
                                "('{0}').".format(match.group(0)),
                                line=line, excerpt=" ".join(sentence.split())[:200], file=file_label,
                            ))
                    rivals = row.get("rivals") if isinstance(row.get("rivals"), list) else []
                    undecided = [str(item.get("name")) for item in rivals
                                 if isinstance(item, Mapping) and item.get("outcome") == "not_distinguished"]
                    if undecided and _SETTLED_MODEL.search(sentence) and not any(
                        name.casefold() in sentence.casefold() for name in undecided
                    ):
                        issues.append(_issue(
                            "MODEL_STATED_AS_SETTLED", "submission", "Model {0}".format(identifier),
                            "The text states the model as established although the data do not distinguish it from "
                            "{0}.".format(", ".join(undecided)),
                            line=line, excerpt=" ".join(sentence.split())[:200], file=file_label,
                        ))
    for identifier in sorted(set(table) - anchored):
        issues.append(_issue("MODEL_NOT_IN_MANUSCRIPT", "submission", "Model {0}".format(identifier),
                             "A recorded model is never anchored in the manuscript with [model:ID]."))
    return issues


REPAIRS: Dict[str, List[str]] = {
    "MODEL_RECORD_INVALID": [
        "Give each entry in /models a unique id such as M1.",
        "Keep /models an array of objects.",
        "See docs/RESEARCH_PROTOCOL.md for the model record fields.",
    ],
    "MODEL_EQUATION_MISSING": [
        "Write the equation in plain text, for example \"y = a * exp(-k * t)\".",
        "If the model has no closed form, describe the algorithm and link its implementation.",
        "Remove the model record if no model is used.",
    ],
    "MODEL_EQUATION_UNPARSEABLE": [
        "Use one '=', explicit operators (+ - * / ^), parentheses, and named functions such as exp() and log().",
        "Write subscripts into the symbol name (b_0, x_i) and declare each symbol.",
        "Split a system of equations into separate model records.",
    ],
    "MODEL_SYMBOL_UNDEFINED": [
        "Add the symbol to the model's symbols with a meaning and unit.",
        "Rename the symbol in the equation to match its definition.",
        "Replace a named constant with its value if it is not a parameter.",
    ],
    "MODEL_SYMBOL_UNUSED": [
        "Remove the unused definition.",
        "Check whether the equation was simplified and the term dropped by mistake.",
        "This is advisory only.",
    ],
    "MODEL_UNIT_MISSING": [
        "Record the unit of the symbol, using \"1\" for dimensionless quantities.",
        "Use [name] for a domain unit such as [score] or [USD].",
        "Record the unit of each fitted parameter implied by the equation.",
    ],
    "MODEL_UNIT_UNKNOWN": [
        "Write units with SI symbols and operators, for example kg*m/s^2 or m s^-1.",
        "Use [name] for a custom dimension that has no SI symbol.",
        "Use \"1\" for a dimensionless quantity.",
    ],
    "MODEL_DIMENSIONS_INCONSISTENT": [
        "Check the derivation: an added term or a missing constant usually carries the unit mismatch.",
        "Correct the recorded units if a symbol was declared with the wrong unit.",
        "Make the argument of exp/log/powers dimensionless by dividing by a reference scale.",
    ],
    "MODEL_ROLE_UNDECLARED": [
        "Set role to descriptive_fit if the model only reproduces the observations.",
        "Set role to predictive or mechanistic only if you will show validation on new data and a rival comparison.",
        "Write the role into the Methods so readers know what kind of claim the model makes.",
    ],
    "MODEL_ASSUMPTIONS_MISSING": [
        "List the assumptions that, if false, would change the model's output or meaning.",
        "Pair each assumption with how it was checked or why it is believed.",
        "Note which assumptions are only needed for the fit and which for the interpretation.",
    ],
    "MODEL_DOMAIN_MISSING": [
        "State the range of inputs, conditions, and populations in which the model was checked.",
        "Say what is known to fail outside that range.",
        "Do not apply the model beyond that range in the Discussion.",
    ],
    "MODEL_SOURCE_UNDECLARED": [
        "Set source.kind to derived_here, fitted, or cited, and link the derivation, fit output, or reference.",
        "For a cited equation, record the reference key and check it against the source.",
        "For a derived equation, store the derivation as an artifact and link its evidence ID.",
    ],
    "MODEL_UNVERIFIED": [
        "Record an independent derivation, limiting-case check, or numerical check of the equation with its evidence.",
        "Test the implementation against hand-computed cases and run it with `uriel run`.",
        "Have a second person re-derive the equation and record their note.",
    ],
    "MODEL_IMPLEMENTATION_UNTESTED": [
        "Run the implementation's tests with `uriel run` after the final change.",
        "Correct implementation.artifact_path to the file that actually computes the model.",
        "Add a test comparing the code against hand-computed values of the equation.",
    ],
    "MODEL_NOT_VALIDATED": [
        "Validate on data not used to fit the model (held-out, independent dataset, or a new experiment) and link it.",
        "Change the role to descriptive_fit and drop predictive or mechanistic language.",
        "State in Limitations that the model is unvalidated outside the fitted data.",
    ],
    "MODEL_NO_RIVAL": [
        "Compare against at least one rival model and record the comparison and outcome.",
        "Choose a rival that a skeptical reader would propose, not a strawman.",
        "If no rival can be fitted, say so and treat the model as a descriptive fit.",
    ],
    "MODEL_UNDERDETERMINED": [
        "Say in the paper that the data do not distinguish the models.",
        "Propose the observation that would distinguish them.",
        "Keep conclusions that hold under every undistinguished model.",
    ],
    "MODEL_UNDECLARED_EQUATION": [
        "Record the equation in /models and anchor the paragraph with [model:ID].",
        "If it is a definition rather than a model, record it as a model with role descriptive_fit and its units.",
        "Move standard textbook identities to a cited source.",
    ],
    "MODEL_ANCHOR_UNKNOWN": [
        "Use an ID that exists in /models.",
        "Add the model record first.",
        "Remove the anchor if no model is meant.",
    ],
    "MODEL_REALISM_OVERCLAIM": [
        "Describe the model as a fit to the observations, not as a mechanism or law.",
        "Change the role to mechanistic only with validation on new data and a rival comparison.",
        "Separate what the model reproduces from what it would mean if its terms were real.",
    ],
    "MODEL_STATED_AS_SETTLED": [
        "Say that the data do not distinguish this model from its rival(s), and name them.",
        "Report the observation that would distinguish them.",
        "Keep only the conclusions that hold under every undistinguished model.",
    ],
    "MODEL_NOT_IN_MANUSCRIPT": [
        "State the model in Methods and tag the paragraph with [model:ID].",
        "Remove the model from the project record if the paper does not use it.",
        "Move it to the supplement and anchor it there.",
    ],
}


def repairs_for(code: str) -> List[str]:
    return list(REPAIRS.get(code, REPAIRS["MODEL_UNVERIFIED"]))


__all__ = [
    "DESIGN_CODES",
    "EVIDENCE_CODES",
    "MODEL_ROLES",
    "ModelSyntaxError",
    "PROJECT_CODES",
    "REPAIRS",
    "check_dimensions",
    "equation_symbols",
    "manuscript_issues",
    "model_table",
    "parse_equation",
    "parse_unit",
    "project_issues",
    "render_dimension",
    "repairs_for",
]
