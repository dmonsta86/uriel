"""Framing checks: does the conclusion follow from the data, or from one reading of it?

A datapoint does not interpret itself.  When more than one explanation could
produce the same observation, an honest paper names the rivals, says which
ones the evidence rules out and how, and keeps the conclusion no stronger than
what is left standing.  These checks make that routine.

Two layers:

- **Record-linked** (``paper check``): alternative explanations in
  ``uriel.project.json`` may name the claims they compete with
  (``claim_ids``), carry a ``status`` (``open``, ``partially_addressed``,
  ``not_distinguishable``, ``ruled_out``), the ``evidence_ids`` / ``test_ids``
  that support that status, and a ``discriminating_observation``.  The
  manuscript anchors them with ``[alt:ID]``.  A claim with no recorded rival,
  an alternative "ruled out" without evidence, an alternative the paper never
  mentions, a conclusion that states a claim as settled while a rival is still
  open, and a sentence that dismisses a rival the record has not ruled out are
  reported.
- **Text-only** (``paper lint`` on any manuscript): single-explanation
  assertions, dismissals with no support in the sentence, and a document that
  draws conclusions without ever considering another explanation.

Every rule is a fixed pattern over declared structure.  None decides which
explanation is true; they decide whether the paper has earned its framing.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

ALTERNATIVE_STATUSES = ("open", "partially_addressed", "not_distinguishable", "ruled_out")
_I = re.IGNORECASE

INTERPRETIVE = re.compile(
    r"\b(?:indicat(?:es|ed|ing)|suggest(?:s|ed|ing)|means? that|meant that|reflect(?:s|ed|ing)?|"
    r"(?:is|are|was|were) (?:due|attributable|attributed) to|(?:is|are|was|were) (?:driven|caused|explained|produced) by|"
    r"because|demonstrat(?:es|ed) that|show(?:s|ed|n)? that|reveal(?:s|ed)? that|confirm(?:s|ed)? that|"
    r"impl(?:ies|ied)|points? to|evidence (?:of|for))\b",
    _I,
)
SETTLED = re.compile(
    r"\b(?:shows?|showed|shown|demonstrat(?:e|es|ed|ing)|establish(?:es|ed)?|confirm(?:s|ed)?|prove[sdn]?|"
    r"reveal(?:s|ed)?|(?:is|are|was|were) (?:due|attributable) to|(?:is|are|was|were) (?:caused|driven|explained) by|"
    r"causes?|leads? to|results? in|we conclude|clearly|definitely|undoubtedly|certainly)\b",
    _I,
)
QUALIFIED = re.compile(
    r"\b(?:may|might|could|possibly|perhaps|consistent with|compatible with|suggest(?:s|ed|ing)?|"
    r"one (?:possible )?(?:explanation|interpretation)|alternatively|alternative|cannot (?:yet )?(?:rule out|exclude|distinguish)|"
    r"not (?:able to )?distinguish|another explanation|rival|confound(?:s|ed|ing)?|tentative(?:ly)?|provisional(?:ly)?|"
    r"in this sample|within (?:this|the) (?:sample|fixture|study|setting))\b",
    _I,
)
SINGLE_EXPLANATION = re.compile(
    r"\b(?:the only (?:possible |plausible |reasonable |likely )?(?:explanation|cause|interpretation|account)|"
    r"can only be (?:explained|attributed|interpreted|due)|(?:must|can only) (?:be )?(?:due to|caused by|the result of|attributed to)|"
    r"no other (?:explanation|interpretation|cause|account)|there is no (?:other|alternative|competing) (?:explanation|interpretation|account)|"
    r"necessarily (?:reflects?|means?|implies?|indicates?)|unambiguously (?:shows?|demonstrates?|indicates?|reflects?))\b",
    _I,
)
DISMISSAL = re.compile(
    r"\b(?:rules? out|ruled out|ruling out|excludes? the possibility|excluded the possibility|"
    r"(?:is|are) (?:highly )?(?:unlikely|implausible) (?:to|as an) (?:explain|explanation)|"
    r"can (?:be )?(?:safely )?(?:dismissed|discounted|ignored|excluded)|eliminat(?:es|ed) (?:the|this|that) "
    r"(?:possibility|alternative|explanation)|cannot (?:be )?(?:explained|accounted for) by)\b",
    _I,
)
_NEGATED_BEFORE = re.compile(
    r"\b(?:cannot|can ?not|could not|did not|does not|do not|unable to|not|no way to|fail(?:s|ed)? to|yet to)\s+(?:\w+\s+){0,2}$",
    _I,
)
ALTERNATIVE_LANGUAGE = re.compile(
    r"\b(?:alternative(?:ly)?|another (?:explanation|possibility|interpretation|account)|other (?:explanations|possibilities|"
    r"interpretations|accounts)|could also (?:be|reflect|explain|arise)|might also (?:be|reflect|explain|arise)|"
    r"rival|confound(?:s|ed|ing|er|ers)?|cannot (?:rule out|exclude)|not (?:be )?ruled out|competing (?:explanation|hypothes\w*|account)|"
    r"we cannot exclude|is also consistent with|are also consistent with|third variable|reverse causation|selection bias)\b",
    _I,
)
CONCLUDING = re.compile(r"\b(?:therefore|thus|hence|consequently|we conclude|in conclusion|this means)\b", _I)
GENERALIZING = re.compile(
    r"\b(?:always|universally|in general|generally|across all|for everyone|in all (?:contexts|settings|populations|cases)|"
    r"humans|human beings|people in general|regardless of|in every)\b",
    _I,
)
SUPPORT_PRESENT = re.compile(r"\[@[^\]]+\]|\{\{dp:[^}]+\}\}|\[alt:[^\]]+\]|\[\d+(?:\s*[,\u2013-]\s*\d+)*\]|\((?:[A-Z][\w'-]+(?: et al\.)?,? (?:19|20)\d{2})")
ALT_ANCHOR = re.compile(r"\[alt:([A-Za-z0-9][A-Za-z0-9._-]{0,63})\]")
CLAIM_ANCHOR = re.compile(r"\[claim:([A-Za-z0-9][A-Za-z0-9._-]{0,63})\]")
DP_MARKER = re.compile(r"\{\{dp:([A-Za-z][A-Za-z0-9_.-]{0,63})\}\}")

PROJECT_CODES = frozenset({
    "CLAIM_WITHOUT_ALTERNATIVE",
    "ALTERNATIVE_STATUS_INVALID",
    "ALTERNATIVE_RULED_OUT_WITHOUT_EVIDENCE",
    "ALTERNATIVE_NO_DISCRIMINATING_OBSERVATION",
    "ALTERNATIVE_UNKNOWN_CLAIM",
})


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _objects(value: Any) -> List[Mapping[str, Any]]:
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _sentences(text: str) -> Iterable[Tuple[int, int, str]]:
    """Yield (start, end, sentence) using '.', '!' or '?' followed by space, and blank lines."""
    start = 0
    for match in re.finditer(r"[.!?](?=[\s\])\"'\u201d]|$)|\n[ \t]*\n", text):
        end = match.end()
        piece = text[start:end]
        if piece.strip():
            yield start, end, piece
        start = end
    if text[start:].strip():
        yield start, len(text), text[start:]


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _excerpt(sentence: str) -> str:
    return " ".join(sentence.split())[:200]


def _issue(code: str, level: str, subject: str, message: str, *, line: Optional[int] = None,
           excerpt: str = "", **detail: Any) -> Dict[str, Any]:
    return {"code": code, "level": level, "subject": subject, "message": message,
            "line": line, "excerpt": excerpt, "detail": detail}


def _dismissals(sentence: str) -> List["re.Match[str]"]:
    found = []
    for match in DISMISSAL.finditer(sentence):
        if _NEGATED_BEFORE.search(sentence[max(0, match.start() - 40): match.start()]):
            continue  # "cannot rule out" acknowledges a rival; it does not dismiss it
        found.append(match)
    return found


# ---------------------------------------------------------------------------
# Record-linked checks
# ---------------------------------------------------------------------------

def alternative_table(project: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Resolve every recorded alternative to its claims, effective status, and support."""
    claims = {str(row.get("id")) for row in _objects(project.get("claims")) if row.get("id")}
    evidence = {str(row.get("id")) for row in _objects(project.get("evidence")) if row.get("id")}
    tests = {
        str(row.get("id")): str(row.get("status", "")).strip().casefold()
        for row in _objects(project.get("adversarial_tests")) if row.get("id")
    }
    table: Dict[str, Dict[str, Any]] = {}
    for row in _objects(project.get("alternative_explanations")):
        identifier = str(row.get("id", "")).strip()
        if not identifier:
            continue
        status = str(row.get("status", "open") or "open").strip()
        linked = [str(item) for item in row.get("claim_ids", [])] if isinstance(row.get("claim_ids"), list) else []
        evidence_ids = [str(item) for item in row.get("evidence_ids", [])] if isinstance(row.get("evidence_ids"), list) else []
        test_ids = [str(item) for item in row.get("test_ids", [])] if isinstance(row.get("test_ids"), list) else []
        valid_support = [item for item in evidence_ids if item in evidence] + [
            item for item in test_ids if tests.get(item) in {"pass", "passed", "complete", "failed_as_expected"}
        ]
        effective = status if status in ALTERNATIVE_STATUSES else "open"
        if effective == "ruled_out" and not valid_support:
            effective = "open"
        table[identifier] = {
            "id": identifier,
            "statement": _text(row.get("statement") or row.get("description") or row.get("explanation")),
            "declared_status": status,
            "status": effective,
            "claim_ids": linked,
            "applies_to_all_claims": not linked,
            "unknown_claim_ids": [item for item in linked if item not in claims],
            "support": valid_support,
            "unverified_support": [item for item in evidence_ids + test_ids if item not in valid_support],
            "discriminating_observation": _text(row.get("discriminating_observation")),
        }
    return table


def rivals_for(claim_id: str, table: Mapping[str, Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    return [row for row in table.values() if row["applies_to_all_claims"] or claim_id in row["claim_ids"]]


def project_issues(project: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Issues in the project record itself, independent of any manuscript."""
    issues: List[Dict[str, Any]] = []
    table = alternative_table(project)
    for row in _objects(project.get("alternative_explanations")):
        identifier = str(row.get("id", "")).strip()
        if not identifier or identifier not in table:
            continue
        entry = table[identifier]
        subject = "Alternative {0}".format(identifier)
        if entry["declared_status"] not in ALTERNATIVE_STATUSES:
            issues.append(_issue("ALTERNATIVE_STATUS_INVALID", "submission", subject,
                                 "status must be one of {0}.".format(", ".join(ALTERNATIVE_STATUSES)),
                                 status=entry["declared_status"]))
        for claim_id in entry["unknown_claim_ids"]:
            issues.append(_issue("ALTERNATIVE_UNKNOWN_CLAIM", "grave", subject,
                                 "The alternative names claim {0}, which is not in the project.".format(claim_id)))
        if entry["declared_status"] == "ruled_out" and entry["status"] != "ruled_out":
            issues.append(_issue(
                "ALTERNATIVE_RULED_OUT_WITHOUT_EVIDENCE", "submission", subject,
                "The alternative is marked ruled out, but no registered evidence or passed adversarial test supports that.",
                unverified_support=entry["unverified_support"],
            ))
        if entry["status"] != "ruled_out" and len(entry["discriminating_observation"]) < 12:
            issues.append(_issue(
                "ALTERNATIVE_NO_DISCRIMINATING_OBSERVATION", "submission", subject,
                "No observation is recorded that would tell this explanation apart from the preferred one.",
            ))
    for claim in _objects(project.get("claims")):
        claim_id = str(claim.get("id", "")).strip()
        statement = _text(claim.get("statement"))
        if not claim_id or len(statement) < 16 or claim.get("importance", "major") != "major":
            continue
        if not rivals_for(claim_id, table):
            issues.append(_issue(
                "CLAIM_WITHOUT_ALTERNATIVE", "submission", "Claim {0}".format(claim_id),
                "No alternative explanation is recorded for this claim, so its data are being read one way only.",
            ))
    return issues


def manuscript_issues(
    project: Mapping[str, Any],
    sections: Sequence[Tuple[Mapping[str, Any], str]],
    datapoint_claims: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[Dict[str, Any]]:
    """Record-linked checks over manuscript sections (``(section, masked_text)`` pairs)."""
    issues: List[Dict[str, Any]] = []
    table = alternative_table(project)
    claims = {str(row.get("id")): row for row in _objects(project.get("claims")) if row.get("id")}
    datapoint_claims = datapoint_claims or {}
    anchored: Dict[str, Set[str]] = {}
    for section, text in sections:
        kind = str(section.get("kind"))
        file_label = section.get("file_label")
        for start, end, sentence in _sentences(text):
            line = _line_of(text, start)
            alt_ids = ALT_ANCHOR.findall(sentence)
            claim_ids = CLAIM_ANCHOR.findall(sentence)
            for identifier in alt_ids:
                anchored.setdefault(identifier, set()).add(kind)
                if identifier not in table:
                    issues.append(_issue("ALTERNATIVE_ANCHOR_UNKNOWN", "grave", "Alternative {0}".format(identifier),
                                         "The anchor names an alternative that is not in uriel.project.json.",
                                         line=line, excerpt=_excerpt(sentence), file=file_label))
            if kind in ("methods", "statements"):
                continue
            for match in _dismissals(sentence):
                for identifier in alt_ids:
                    entry = table.get(identifier)
                    if entry and entry["status"] != "ruled_out":
                        issues.append(_issue(
                            "ALTERNATIVE_DISMISSED_WITHOUT_EVIDENCE", "submission", "Alternative {0}".format(identifier),
                            "The text dismisses this alternative ('{0}'), but the record does not show it ruled out "
                            "by registered evidence or a passed test.".format(match.group(0)),
                            line=line, excerpt=_excerpt(sentence), file=file_label,
                        ))
            if kind in ("abstract", "conclusion", "discussion"):
                for claim_id in claim_ids:
                    open_rivals = [row["id"] for row in rivals_for(claim_id, table) if row["status"] != "ruled_out"]
                    if not open_rivals or not SETTLED.search(sentence) or QUALIFIED.search(sentence):
                        continue
                    if set(alt_ids) & set(open_rivals):
                        continue
                    issues.append(_issue(
                        "CONCLUSION_IGNORES_OPEN_ALTERNATIVE", "submission", "Claim {0}".format(claim_id),
                        "The sentence states the claim as settled while recorded alternative(s) {0} remain open.".format(
                            ", ".join(open_rivals)),
                        line=line, excerpt=_excerpt(sentence), file=file_label, open_alternatives=open_rivals,
                    ))
                for claim_id in claim_ids:
                    claim = claims.get(claim_id)
                    if not claim or kind not in ("abstract", "conclusion"):
                        continue
                    scope = claim.get("scope") if isinstance(claim.get("scope"), Mapping) else {}
                    scope_text = " ".join(_text(value) for value in scope.values()).casefold()
                    for match in GENERALIZING.finditer(sentence):
                        if match.group(0).casefold() not in scope_text:
                            issues.append(_issue(
                                "CONCLUSION_EXCEEDS_SCOPE", "submission", "Claim {0}".format(claim_id),
                                "'{0}' generalizes beyond the claim's recorded scope ({1}).".format(
                                    match.group(0), "; ".join(_text(value) for value in scope.values()) or "none recorded"),
                                line=line, excerpt=_excerpt(sentence), file=file_label,
                            ))
            if kind in ("results", "discussion", "conclusion", "abstract") and INTERPRETIVE.search(sentence):
                linked = set(claim_ids)
                for identifier in DP_MARKER.findall(sentence):
                    linked.update(datapoint_claims.get(identifier, ()))
                if not linked and not DP_MARKER.search(sentence):
                    continue
                targets = sorted(linked) or [""]
                if not any(rivals_for(claim_id, table) if claim_id else table for claim_id in targets):
                    issues.append(_issue(
                        "INTERPRETATION_WITHOUT_ALTERNATIVE", "submission",
                        "Claim {0}".format(", ".join(sorted(linked))) if linked else "Results interpretation",
                        "The sentence reads the data one way, but the project records no alternative reading of it.",
                        line=line, excerpt=_excerpt(sentence), file=file_label,
                    ))
                elif kind == "results" and not alt_ids:
                    issues.append(_issue(
                        "INTERPRETATION_IN_RESULTS", "style", "Results interpretation",
                        "Interpretive wording in Results; describe the data here and weigh explanations in the Discussion.",
                        line=line, excerpt=_excerpt(sentence), file=file_label,
                    ))
    for identifier, entry in sorted(table.items()):
        if not entry["statement"] or len(entry["statement"]) < 8:
            continue
        if not anchored.get(identifier):
            issues.append(_issue(
                "ALTERNATIVE_NOT_ADDRESSED", "submission", "Alternative {0}".format(identifier),
                "The manuscript never addresses this recorded alternative explanation ({0}).".format(entry["statement"][:120]),
                status=entry["status"],
            ))
        elif entry["status"] != "ruled_out" and not (anchored[identifier] & {"discussion", "limitations", "conclusion"}):
            issues.append(_issue(
                "ALTERNATIVE_NOT_ADDRESSED", "submission", "Alternative {0}".format(identifier),
                "This open alternative is mentioned, but not in the Discussion, Limitations, or Conclusion where the "
                "interpretation is weighed.",
                status=entry["status"],
            ))
    return issues


# ---------------------------------------------------------------------------
# Text-only checks (any manuscript)
# ---------------------------------------------------------------------------

def text_issues(text: str, *, document_level: bool = True) -> List[Dict[str, Any]]:
    """Framing checks that need no project record; ``text`` should already be masked."""
    issues: List[Dict[str, Any]] = []
    concluding = 0
    for start, end, sentence in _sentences(text):
        line = _line_of(text, start)
        stripped = sentence.strip()
        if not stripped or stripped.startswith(("#", "|")):
            continue
        for match in SINGLE_EXPLANATION.finditer(sentence):
            if ALT_ANCHOR.search(sentence):
                continue
            issues.append(_issue(
                "SINGLE_EXPLANATION_ASSERTED", "submission", "Framing",
                "'{0}' asserts that no other explanation exists without showing the others were tested.".format(match.group(0)),
                line=line, excerpt=_excerpt(sentence),
            ))
        for match in _dismissals(sentence):
            if SUPPORT_PRESENT.search(sentence):
                continue
            issues.append(_issue(
                "DISMISSAL_WITHOUT_SUPPORT", "submission", "Framing",
                "'{0}' dismisses a possibility with no data, test, or citation in the same sentence.".format(match.group(0)),
                line=line, excerpt=_excerpt(sentence),
            ))
        if SETTLED.search(sentence) or INTERPRETIVE.search(sentence) or CONCLUDING.search(sentence):
            concluding += 1
    if document_level and concluding >= 3 and not ALTERNATIVE_LANGUAGE.search(text):
        issues.append(_issue(
            "NO_ALTERNATIVES_CONSIDERED", "submission", "Framing",
            "The text draws {0} interpretive or concluding statements but never considers another explanation, "
            "confound, or reading of the data.".format(concluding),
            line=1, concluding_sentences=concluding,
        ))
    return issues


REPAIRS: Dict[str, List[str]] = {
    "CLAIM_WITHOUT_ALTERNATIVE": [
        "Add the strongest rival explanation for this claim to /alternative_explanations with claim_ids and a discriminating_observation.",
        "Ask what else would produce the same data (confound, selection, measurement artefact, reverse direction) and record it.",
        "If no rival can be named, narrow the claim to a description of what was observed.",
    ],
    "ALTERNATIVE_STATUS_INVALID": [
        "Use one of: open, partially_addressed, not_distinguishable, ruled_out.",
        "Use open until registered evidence or a passed adversarial test rules the alternative out.",
        "Record the reasoning in the alternative's statement rather than in the status field.",
    ],
    "ALTERNATIVE_UNKNOWN_CLAIM": [
        "Correct claim_ids to existing claim IDs.",
        "Add the claim to /claims if the alternative competes with an unrecorded claim.",
        "Remove claim_ids to make the alternative apply to every claim.",
    ],
    "ALTERNATIVE_RULED_OUT_WITHOUT_EVIDENCE": [
        "Link the evidence_ids or passed test_ids that actually rule the alternative out.",
        "Set the status back to open or partially_addressed until that evidence exists.",
        "Design an adversarial test whose result would distinguish the explanations, run it, and link it.",
    ],
    "ALTERNATIVE_NO_DISCRIMINATING_OBSERVATION": [
        "Record the observation that would be more likely under this alternative than under the preferred account.",
        "If no observation could tell them apart, set status not_distinguishable and say so in the paper.",
        "Plan the measurement or analysis that would produce the discriminating observation.",
    ],
    "ALTERNATIVE_ANCHOR_UNKNOWN": [
        "Use an ID that exists in /alternative_explanations.",
        "Add the alternative to the project record first.",
        "Remove the anchor if the sentence is not about a recorded alternative.",
    ],
    "ALTERNATIVE_NOT_ADDRESSED": [
        "Discuss the alternative in the Discussion or Limitations and tag the sentence with [alt:ID].",
        "State what evidence would distinguish it and whether this study has that evidence.",
        "If it is ruled out, cite the evidence or test that rules it out in the same sentence.",
    ],
    "ALTERNATIVE_DISMISSED_WITHOUT_EVIDENCE": [
        "Replace the dismissal with what the data can and cannot distinguish.",
        "Link the evidence or passed test that rules it out in the project record, then keep the wording.",
        "Move the alternative to Limitations as unresolved.",
    ],
    "CONCLUSION_IGNORES_OPEN_ALTERNATIVE": [
        "Qualify the conclusion ('is consistent with', 'in this sample') and name the open alternative with [alt:ID].",
        "Rule the alternative out with registered evidence or a passed test before stating the claim as settled.",
        "Narrow the conclusion to what holds under every open explanation.",
    ],
    "CONCLUSION_EXCEEDS_SCOPE": [
        "Restrict the conclusion to the population, setting, and time window recorded in the claim's scope.",
        "Widen the recorded scope only if the evidence actually covers it.",
        "Move the generalization to clearly labelled speculation in the Discussion.",
    ],
    "INTERPRETATION_WITHOUT_ALTERNATIVE": [
        "Record at least one rival reading of these data in /alternative_explanations (linked by claim_ids).",
        "Rewrite the sentence as a description of what was observed.",
        "Discuss in the Discussion what else could produce the same numbers.",
    ],
    "INTERPRETATION_IN_RESULTS": [
        "Describe the result here and move the interpretation to the Discussion.",
        "Keep interpretation only where the alternatives are weighed in the same place.",
        "This is advisory; some journals combine Results and Discussion.",
    ],
    "SINGLE_EXPLANATION_ASSERTED": [
        "Name the alternatives considered and the evidence that rules each out.",
        "Replace 'the only explanation' with 'the explanation best supported here' and say why.",
        "If alternatives were not tested, state that they remain possible.",
    ],
    "DISMISSAL_WITHOUT_SUPPORT": [
        "Add the data, test, or citation that supports the dismissal in the same sentence.",
        "Soften to what the evidence shows ('we found no sign of X in Y').",
        "Move the possibility to Limitations as untested.",
    ],
    "NO_ALTERNATIVES_CONSIDERED": [
        "Add a paragraph on the strongest alternative explanations and what the data say about each.",
        "Name likely confounds, selection effects, measurement artefacts, and reverse causation where relevant.",
        "Narrow the conclusions to descriptions if no alternative can be assessed.",
    ],
}


def repairs_for(code: str) -> List[str]:
    return list(REPAIRS.get(code, REPAIRS["NO_ALTERNATIVES_CONSIDERED"]))


__all__ = [
    "ALTERNATIVE_STATUSES",
    "PROJECT_CODES",
    "REPAIRS",
    "alternative_table",
    "manuscript_issues",
    "project_issues",
    "repairs_for",
    "rivals_for",
    "text_issues",
]
