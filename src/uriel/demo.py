"""Build the bounded public demo project used by examples and tests.

The demo proves Uriel's implemented workflow can issue and verify a Blessing for
one deliberately small software claim. It is not evidence for unrelated work.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from uriel.core import initialize_project, load_project, run_workload, save_project, sha256_file


def make_passing_project(root: Path) -> Dict[str, Any]:
    """Create a small, fully bounded software fixture that can earn a Blessing."""

    initialize_project(
        root,
        title="Deterministic manifest verifier",
        question="Does exact membership verification detect an unexpected project file in a confined software fixture?",
    )
    artifact = root / "artifacts" / "result.json"
    artifact.write_text(
        json.dumps({"unexpected_file_detected": True, "expected_error_code": "SOURCE_UNEXPECTED"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (root / "analysis.py").write_text(
        "from __future__ import annotations\n\n"
        "def detect(expected, actual):\n"
        "    return sorted(set(actual) - set(expected))\n",
        encoding="utf-8",
    )
    tests = root / "fixture_tests"
    tests.mkdir()
    (tests / "test_analysis.py").write_text(
        "import unittest\n"
        "from analysis import detect\n\n"
        "class TestDetect(unittest.TestCase):\n"
        "    def test_unexpected(self):\n"
        "        self.assertEqual(detect(['a'], ['a', 'b']), ['b'])\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )

    project = load_project(root)
    project.update(
        {
            "title": "Deterministic manifest verifier",
            "kind": "software",
            "question": "Does exact membership verification detect an unexpected project file in a confined software fixture?",
        }
    )
    project["hypothesis"] = {
        "statement": "For the declared fixture, exact source-manifest membership comparison reports an added unrecorded file before accepting verification.",
        "falsifier": "The claim fails if the fixture adds an unrecorded file and verification still reports a clean exact membership match.",
        "operational_definitions": {
            "unexpected file": "A regular project-local file whose relative path is absent from the recorded manifest.",
            "detect": "Return the SOURCE_UNEXPECTED finding and a non-passing verification result.",
        },
        "success_criteria": [
            "The unit test passes and exact verification reports SOURCE_UNEXPECTED for a deliberately added path."
        ],
    }
    project["framing_review"] = {
        "neutral_restatement": "Compare a recorded finite path set with the current finite path set and report any current path absent from the record.",
        "competing_frames": [
            "The behavior may be described as change detection rather than tamper detection because an added file can be benign."
        ],
        "loaded_terms_reviewed": ["tamper"],
        "scope_boundaries": [
            "This claim covers project-local regular files and does not cover undisclosed remote state or linked paths."
        ],
    }
    project["novelty_review"] = {
        "status": "complete",
        "search_date": "2026-08-06",
        "databases": ["Python standard-library documentation", "GitHub code search"],
        "queries": [
            "content addressed manifest exact membership verification unexpected file",
            "root confined research provenance ledger source manifest",
        ],
        "nearest_prior_work": [
            "Build systems and package managers compare recorded file sets; the fixture tests the behavior in a research-audit workflow."
        ],
        "differentiators": [
            "The contribution is the integrated fail-closed research audit policy and durable repair record, not the set-difference operation alone."
        ],
        "negative_searches": [
            "Searched for tools combining exact local membership, claim-evidence mapping, sequential integrity gates, and a content-addressed certificate."
        ],
        "scope_limitations": [
            "Search was limited to the declared English-language documentation and GitHub queries on 2026-08-06."
        ],
    }
    project["claims"] = [
        {
            "id": "C1",
            "statement": "In the declared unit fixture, the verifier identifies path b as unexpected when the recorded set contains only path a.",
            "type": "empirical",
            "importance": "major",
            "scope": {
                "population": "The two-element software fixture",
                "setting": "Python standard-library unit test",
                "timeframe": "Repository version 1.0.0",
            },
            "falsifier": "The claim is rejected if the returned unexpected-path list is empty or differs from [b].",
            "reasoning": "The function computes current paths minus recorded paths; the preserved test output directly checks the resulting list.",
            "evidence_ids": ["E1"],
            "counterevidence_ids": [],
            "assumption_ids": ["A1"],
            "adversarial_test_ids": ["T1"],
            "reconciliation": "No contrary observation is declared in this bounded fixture.",
        }
    ]
    project["evidence"] = [
        {
            "id": "E1",
            "kind": "software-test",
            "description": "Preserved machine-readable result and passing unit-test receipt for the exact finite fixture.",
            "artifact_path": "artifacts/result.json",
            "sha256": sha256_file(artifact),
            "source_locator": "local:artifacts/result.json#unexpected_file_detected",
            "source_type": "primary",
            "directness": "direct",
            "primary": True,
            "extraction": "unexpected_file_detected = true; expected_error_code = SOURCE_UNEXPECTED",
            "data_location": "JSON keys unexpected_file_detected and expected_error_code",
            "interpretation": "The fixture records that exact set comparison detected the added path under the declared test conditions.",
            "limitations": "A two-element fixture does not establish performance, filesystem race resistance, or behavior on every platform.",
            "supports_claims": ["C1"],
            "counterevidence_for_claims": [],
        }
    ]
    project["methods"] = {
        "design": "Deterministic unit test over a finite recorded set and a finite current set with one deliberately added path.",
        "population": "The declared two-list software fixture, not arbitrary operating-system state.",
        "sampling": "Exhaustive evaluation of every element in the finite fixture.",
        "sample_size": None,
        "analysis_plan": "Compute set(actual) minus set(expected), sort the result, and compare it with the predeclared list containing b.",
        "effect_size_metric": "Exact equality of the returned unexpected-path list.",
        "uncertainty_method": "No sampling uncertainty applies; implementation and platform limits are handled as explicit limitations.",
        "causal_identification": "not_applicable: the claim is deterministic software behavior, not a causal population claim.",
        "controls": [
            "A matching fixture [a] versus [a] is the negative control; [a] versus [a,b] is the positive fixture."
        ],
        "exclusions": ["none: every element in each finite fixture is included."],
        "missing_data_plan": "The test fails if either declared fixture list or expected result is unavailable.",
        "preregistration": "The expected result is encoded in fixture_tests/test_analysis.py before the audit run.",
        "reproducibility_command": "python -m unittest discover -s fixture_tests",
    }
    project["assumptions"] = [
        {
            "id": "A1",
            "statement": "Input path strings are already normalized within the synthetic fixture.",
            "risk": "Different spellings of one path could be treated as different elements.",
            "test": "Add case and separator normalization fixtures before claiming filesystem-wide behavior.",
        }
    ]
    project["alternative_explanations"] = [
        {
            "id": "X1",
            "statement": "The passing result could arise from a hard-coded answer rather than set comparison; source inspection and control fixtures distinguish that case.",
        }
    ]
    project["contradictions"] = []
    project["adversarial_tests"] = [
        {
            "id": "T1",
            "target": "Claim C1 and the set-difference implementation",
            "procedure": "Run the unit test with one recorded path and one additional current path.",
            "failure_condition": "Any result other than the one-item list [b], or a nonzero test exit status.",
            "result": "The preserved unit test returned [b] and completed with exit status zero.",
            "status": "pass",
        }
    ]
    project["reviewer_objections"] = [
        {
            "id": "R1",
            "statement": "The fixture is too small to support claims about scale or operating-system races.",
            "response": "The claim is explicitly limited to the finite fixture; scale and race resistance are listed outside scope.",
        }
    ]
    project["limitations"] = [
        {
            "id": "L1",
            "statement": "The result is a bounded software fixture and does not establish million-file performance or race-free observation during concurrent writes.",
        }
    ]
    project["ethics"] = {
        "review_status": "not_applicable: no human, animal, personal, or hazardous data is used.",
        "risks": ["A certificate could be misread as proof of universal correctness."],
        "mitigations": ["The certificate and package state the bounded scope and non-claims prominently."],
    }
    project["disclosures"] = {
        "funding": ["No external funding declared for this fixture."],
        "conflicts": ["No conflict declared for this fixture."],
        "known_counterevidence": ["No contrary result is known for the exact committed fixture."],
        "omitted_data": ["No fixture element was omitted."],
        "negative_results": ["No failed final run; earlier development errors are not used as evidence."],
        "attestations": {
            "all_known_material_data_declared": True,
            "null_and_negative_results_declared": True,
            "citations_checked_against_sources": True,
            "no_claim_relies_only_on_another_authors_conclusion": True,
        },
    }
    project["submission"] = {
        "field": "research software engineering",
        "article_type": "software note",
        "target_venues": ["A venue selected after checking its current official scope and policies"],
        "author_names": ["Example Maintainer"],
        "corresponding_author": "maintainer@example.invalid",
        "data_availability": "All non-sensitive fixture data is stored in artifacts/result.json in the repository.",
        "code_availability": "The source and unit test are included in analysis.py and fixture_tests/test_analysis.py.",
    }
    project["privacy"] = {"classification": "public", "external_ai": "ask", "redaction_notes": []}
    project["workloads"] = [
        {
            "id": "unit-tests",
            "command": ["{python}", "-m", "unittest", "discover", "-s", "fixture_tests"],
            "timeout_seconds": 120,
        }
    ]
    project["external_reviews"] = []
    project["waivers"] = []
    save_project(root, project, event="fixture.completed", details={"fixture": "passing"})
    receipt = run_workload(
        root,
        [sys.executable, "-m", "unittest", "discover", "-s", "fixture_tests"],
        timeout=120,
        workload_id="unit-tests",
    )
    if receipt["status"] != "PASS":
        raise AssertionError("fixture workload failed")
    return project
