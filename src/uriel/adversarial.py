"""Adversarial mode: an opt-in, harder standard for the claims a paper makes.

Submission checks ask whether the record is complete and the manuscript is
faithful to it.  Adversarial mode assumes the conclusion is wrong and asks
whether the paper has done the work to show otherwise:

- every major claim faces at least two claim-specific rival explanations, a
  passed adversarial test, and a documented counterevidence search;
- a causal claim faces a confound-type rival (common cause, selection, reverse
  direction, expectation, regression to the mean, attrition ...);
- every unresolved rival is disclosed in Limitations, and a concluding
  sentence that touches an open claim must name a rival or qualify itself;
- confirmatory framing must be earned: analyses not locked before the first
  passing run are labelled exploratory, one-tailed tests appear in the locked
  plan, and plan deviations made after results are disclosed;
- every assumption's test has actually been run (a recorded result);
- every model is verified two independent ways and compared with a rival, and
  any rival the data cannot distinguish is named in the paper.

The mode is recorded in ``uriel.project.json`` (``assurance_mode``).  Turning
it off requires a written reason and is appended to the hash-chained ledger,
because relaxing scrutiny before submission is itself worth recording.  It
changes no Gate, Data Readiness, or Blessing rule; it adds blockers to
``paper check --profile adversarial`` and ``uriel next --target adversarial``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from .core import Refusal, load_project, paths_for, save_project
from .framing import ALT_ANCHOR, CLAIM_ANCHOR, QUALIFIED, alternative_table, rivals_for

MODE_FIELD = "assurance_mode"
MODES = ("standard", "adversarial")
MIN_DISABLE_REASON = 16
PASSED_TEST_STATUSES = frozenset({"pass", "passed", "complete", "failed_as_expected"})
ESCALATED_CODES = frozenset({"INTERPRETATION_IN_RESULTS", "MODEL_NO_RIVAL", "PLAN_NOT_LOCKED"})
PROJECT_CODES = frozenset({
    "ADV_CLAIM_NEEDS_TWO_RIVALS",
    "ADV_CLAIM_NOT_ATTACKED",
    "ADV_COUNTEREVIDENCE_UNSEARCHED",
    "ADV_CAUSAL_CLAIM_WITHOUT_CONFOUND_RIVAL",
    "ADV_ASSUMPTION_UNTESTED",
    "ADV_MODEL_SINGLE_VERIFICATION",
})
_CAUSAL = re.compile(
    r"\b(?:causes?|caused|causal(?:ly)?|leads? to|led to|results? in|produces?|prevents?|drives?|"
    r"effect of|impact of|improves?|reduces?|increases?|decreases?|because)\b",
    re.IGNORECASE,
)
_CONFOUND_RIVAL = re.compile(
    r"\b(?:confound\w*|third variable|common cause|selection|self-selection|reverse(?:d)? (?:causation|direction|causality)|"
    r"regression to the mean|placebo|expectation|demand characteristics?|hawthorne|history effect|maturation|"
    r"attrition|survivorship|collider|instrument(?:ation)? effect|measurement artefact|measurement artifact)\b",
    re.IGNORECASE,
)
_ONE_TAILED = re.compile(r"\b(?:one[- ]tailed|one[- ]sided|directional (?:test|hypothesis))\b", re.IGNORECASE)
_EXPLORATORY = re.compile(r"\bexploratory\b", re.IGNORECASE)
_DEVIATION = re.compile(r"\bdeviat(?:ion|ions|ed|ing)\b", re.IGNORECASE)


def _text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _objects(value: Any) -> List[Mapping[str, Any]]:
    return [row for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _issue(code: str, subject: str, message: str, **detail: Any) -> Dict[str, Any]:
    return {"code": code, "level": "adversarial", "subject": subject, "message": message,
            "line": detail.pop("line", None), "excerpt": detail.pop("excerpt", ""), "detail": detail}


def mode(project: Mapping[str, Any]) -> str:
    value = project.get(MODE_FIELD, "standard")
    return value if value in MODES else "standard"


def set_mode(root: Union[str, Path], *, enabled: bool, reason: str = "") -> Dict[str, Any]:
    """Turn adversarial mode on, or off with a recorded reason."""
    paths = paths_for(root)
    project = load_project(paths.root)
    previous = mode(project)
    target = "adversarial" if enabled else "standard"
    if previous == target:
        return {"mode": target, "changed": False}
    clean = reason.strip()
    if not enabled and len(clean) < MIN_DISABLE_REASON:
        raise Refusal(
            "Turning adversarial mode off needs a written reason of at least {0} characters; it is recorded in the "
            "ledger.".format(MIN_DISABLE_REASON),
            code="ADVERSARIAL_DISABLE_REASON_REQUIRED",
            repairs=[
                "Rerun with --reason explaining why the stricter standard no longer applies.",
                "Keep adversarial mode on and repair the blockers it reports instead.",
                "Use `uriel next --target submission` for a one-off look at the lighter standard without changing the mode.",
            ],
        )
    project[MODE_FIELD] = target
    save_project(paths.root, project, event="assurance.mode_changed",
                 details={"from": previous, "to": target, "reason": clean})
    return {"mode": target, "changed": True, "previous": previous, "reason": clean}


def project_issues(project: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Adversarial requirements on the project record."""
    issues: List[Dict[str, Any]] = []
    table = alternative_table(project)
    tests = {str(row.get("id")): str(row.get("status", "")).strip().casefold()
             for row in _objects(project.get("adversarial_tests")) if row.get("id")}
    methods = project.get("methods") if isinstance(project.get("methods"), Mapping) else {}
    identification = _text(methods.get("causal_identification"))
    for claim in _objects(project.get("claims")):
        claim_id = _text(claim.get("id"))
        statement = _text(claim.get("statement"))
        if not claim_id or len(statement) < 16 or claim.get("importance", "major") != "major":
            continue
        subject = "Claim {0}".format(claim_id)
        specific = [row for row in table.values() if claim_id in row["claim_ids"]]
        if len(specific) < 2:
            issues.append(_issue(
                "ADV_CLAIM_NEEDS_TWO_RIVALS", subject,
                "Adversarial mode needs at least two rival explanations recorded specifically for this claim "
                "(found {0}); explanations that apply to every claim do not count.".format(len(specific)),
            ))
        attack_ids = [str(item) for item in claim.get("adversarial_test_ids", [])] \
            if isinstance(claim.get("adversarial_test_ids"), list) else []
        if not any(tests.get(item) in PASSED_TEST_STATUSES for item in attack_ids):
            issues.append(_issue(
                "ADV_CLAIM_NOT_ATTACKED", subject,
                "No completed adversarial test targets this claim; it has not faced an attempt to break it.",
            ))
        counter = claim.get("counterevidence_ids") if isinstance(claim.get("counterevidence_ids"), list) else []
        if not counter and len(_text(claim.get("reconciliation"))) < 24:
            issues.append(_issue(
                "ADV_COUNTEREVIDENCE_UNSEARCHED", subject,
                "No counterevidence is linked and no counterevidence search is documented in the reconciliation.",
            ))
        causal = _text(claim.get("type")).casefold() == "causal" or bool(_CAUSAL.search(statement))
        if causal:
            confound_rivals = [row for row in rivals_for(claim_id, table) if _CONFOUND_RIVAL.search(row["statement"])]
            if not confound_rivals or len(identification) < 16:
                issues.append(_issue(
                    "ADV_CAUSAL_CLAIM_WITHOUT_CONFOUND_RIVAL", subject,
                    "A causal claim must face a confound-type rival (common cause, selection, reverse direction, "
                    "expectation, regression to the mean, attrition ...) and a recorded identification strategy.",
                    confound_rivals=[row["id"] for row in confound_rivals],
                ))
    for row in _objects(project.get("assumptions")):
        identifier = _text(row.get("id")) or "?"
        if len(_text(row.get("result"))) < 8:
            issues.append(_issue(
                "ADV_ASSUMPTION_UNTESTED", "Assumption {0}".format(identifier),
                "The assumption's test is described but no result is recorded; it has not actually been checked.",
            ))
    models = project.get("models") if isinstance(project.get("models"), list) else []
    for row in _objects(models):
        identifier = _text(row.get("id")) or "?"
        methods_used = {
            str(item.get("method")) for item in (row.get("verification") if isinstance(row.get("verification"), list) else [])
            if isinstance(item, Mapping) and item.get("method")
        }
        if len(methods_used) < 2:
            issues.append(_issue(
                "ADV_MODEL_SINGLE_VERIFICATION", "Model {0}".format(identifier),
                "Adversarial mode needs the equation verified two independent ways (found {0}).".format(len(methods_used)),
            ))
    return issues


def manuscript_issues(
    project: Mapping[str, Any],
    sections: Sequence[Tuple[Mapping[str, Any], str]],
    plan_status: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Adversarial requirements on the manuscript (``(section, masked_text)`` pairs)."""
    issues: List[Dict[str, Any]] = []
    table = alternative_table(project)
    limitations_anchors: Set[str] = set()
    methods_text = " ".join(text for section, text in sections if section.get("kind") == "methods")
    all_text = "\n".join(text for _, text in sections)
    for section, text in sections:
        kind = section.get("kind")
        file_label = section.get("file_label")
        if kind == "limitations":
            limitations_anchors.update(ALT_ANCHOR.findall(text))
        if kind not in ("abstract", "conclusion"):
            continue
        for match in re.finditer(r"[^.!?\n]+[.!?]?", text):
            sentence = match.group(0)
            for claim_id in CLAIM_ANCHOR.findall(sentence):
                open_rivals = [row["id"] for row in rivals_for(claim_id, table) if row["status"] != "ruled_out"]
                if open_rivals and not (set(ALT_ANCHOR.findall(sentence)) & set(open_rivals)) and not QUALIFIED.search(sentence):
                    issues.append(_issue(
                        "ADV_CONCLUSION_SILENT_ON_OPEN_RIVAL", "Claim {0}".format(claim_id),
                        "A concluding sentence about this claim neither names an open rival ({0}) nor qualifies "
                        "itself.".format(", ".join(open_rivals)),
                        line=text.count("\n", 0, match.start()) + 1, excerpt=" ".join(sentence.split())[:200],
                        file=file_label,
                    ))
    for identifier, row in sorted(table.items()):
        if row["status"] != "ruled_out" and row["statement"] and identifier not in limitations_anchors:
            issues.append(_issue(
                "ADV_RIVAL_NOT_IN_LIMITATIONS", "Alternative {0}".format(identifier),
                "An unresolved rival explanation must be disclosed in the Limitations section with [alt:{0}].".format(identifier),
            ))
    if plan_status.get("lock_count") and not plan_status.get("first_lock_preceded_passing_results") \
            and not _EXPLORATORY.search(methods_text):
        issues.append(_issue(
            "ADV_CONFIRMATORY_FRAMING_NOT_EARNED", "Analysis plan",
            "The plan was locked only after passing results existed, but Methods does not label the analyses exploratory.",
        ))
    if plan_status.get("state") == "UNLOCKED" and not _EXPLORATORY.search(methods_text):
        issues.append(_issue(
            "ADV_CONFIRMATORY_FRAMING_NOT_EARNED", "Analysis plan",
            "No plan was ever locked, but Methods does not label the analyses exploratory.",
        ))
    late = [row for row in plan_status.get("deviations", []) if row.get("after_passing_results")]
    if late and not _DEVIATION.search(methods_text):
        issues.append(_issue(
            "ADV_DEVIATION_UNDISCLOSED", "Analysis plan",
            "The plan was revised after passing results ({0} time(s)), but Methods never mentions a deviation.".format(len(late)),
        ))
    if _ONE_TAILED.search(all_text):
        methods = project.get("methods") if isinstance(project.get("methods"), Mapping) else {}
        planned = _text(methods.get("analysis_plan"))
        if not _ONE_TAILED.search(planned) or plan_status.get("state") != "CURRENT":
            issues.append(_issue(
                "ADV_ONE_TAILED_NOT_PLANNED", "Analysis plan",
                "The manuscript reports one-tailed or directional tests, but the current locked analysis plan does not "
                "declare them.",
            ))
    models = project.get("models") if isinstance(project.get("models"), list) else []
    for row in _objects(models):
        rivals = row.get("rivals") if isinstance(row.get("rivals"), list) else []
        for rival in _objects(rivals):
            name = _text(rival.get("name"))
            if rival.get("outcome") == "not_distinguished" and name and name.casefold() not in all_text.casefold():
                issues.append(_issue(
                    "ADV_UNDERDETERMINED_UNDISCLOSED", "Model {0}".format(_text(row.get("id"))),
                    "The data do not distinguish this model from '{0}', and the manuscript never names that rival.".format(name),
                ))
    return issues


REPAIRS: Dict[str, List[str]] = {
    "ADV_CLAIM_NEEDS_TWO_RIVALS": [
        "Record at least two rival explanations for this claim with claim_ids set to it.",
        "Ask what a hostile reviewer would propose: confounds, selection, measurement artefacts, reverse direction.",
        "If only one rival is plausible, record why the others were rejected as a second, ruled-out entry with its evidence.",
    ],
    "ADV_CLAIM_NOT_ATTACKED": [
        "Design an adversarial test whose failure would reject the claim, run it, and link it in adversarial_test_ids.",
        "Record the result honestly; a failed attack narrows the claim instead of hiding it.",
        "Narrow the claim to what has survived an attack.",
    ],
    "ADV_COUNTEREVIDENCE_UNSEARCHED": [
        "Search for contrary results and link any found as counterevidence_ids.",
        "Document the search (where, when, terms, what was found) in the claim's reconciliation.",
        "Treat an empty search as a limitation, not as support.",
    ],
    "ADV_CAUSAL_CLAIM_WITHOUT_CONFOUND_RIVAL": [
        "Record the strongest confound-type rival (common cause, selection, reverse direction, expectation) for the claim.",
        "Record the identification strategy in /methods/causal_identification and how it addresses that rival.",
        "Downgrade the claim to an association.",
    ],
    "ADV_ASSUMPTION_UNTESTED": [
        "Run the assumption's test and record its result.",
        "If the test cannot be run, record that as the result and add the assumption to Limitations.",
        "Remove the dependency on the assumption by narrowing the claim.",
    ],
    "ADV_MODEL_SINGLE_VERIFICATION": [
        "Add a second, independent verification (re-derivation, limiting cases, numerical check, implementation test).",
        "Have a second person derive the equation and record their note.",
        "Check the model against a known special case with a closed-form answer.",
    ],
    "ADV_CONCLUSION_SILENT_ON_OPEN_RIVAL": [
        "Name the open rival in the same sentence with [alt:ID].",
        "Qualify the sentence ('is consistent with', 'in this sample').",
        "Rule the rival out with linked evidence or a passed test first.",
    ],
    "ADV_RIVAL_NOT_IN_LIMITATIONS": [
        "Add a sentence on the rival to the Limitations section and tag it [alt:ID].",
        "Say what observation would settle it.",
        "Rule it out with linked evidence or a passed test if the study can.",
    ],
    "ADV_CONFIRMATORY_FRAMING_NOT_EARNED": [
        "Label the analyses exploratory in Methods and soften confirmatory wording throughout.",
        "Run a fresh confirmatory analysis on new data under a plan locked before it.",
        "Record an external registration in /methods/preregistration if one preceded the analysis.",
    ],
    "ADV_DEVIATION_UNDISCLOSED": [
        "Add a 'Deviations from the locked plan' paragraph to Methods with each change and its reason.",
        "Report the originally planned analysis alongside the revised one.",
        "Label analyses introduced after results as exploratory.",
    ],
    "ADV_ONE_TAILED_NOT_PLANNED": [
        "Report two-tailed tests.",
        "Show the directional hypothesis in the analysis plan that was locked before results.",
        "Label the one-tailed tests as an exploratory deviation in Methods.",
    ],
    "ADV_UNDERDETERMINED_UNDISCLOSED": [
        "Name the rival model in the paper and say the data do not distinguish them.",
        "Propose the observation that would distinguish them.",
        "Limit conclusions to what holds under both models.",
    ],
}


def repairs_for(code: str) -> List[str]:
    return list(REPAIRS.get(code, REPAIRS["ADV_CLAIM_NOT_ATTACKED"]))


__all__ = [
    "ESCALATED_CODES",
    "MODES",
    "MODE_FIELD",
    "PROJECT_CODES",
    "REPAIRS",
    "manuscript_issues",
    "mode",
    "project_issues",
    "repairs_for",
    "set_mode",
]
