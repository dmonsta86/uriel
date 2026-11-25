"""A complete, small manuscript project used by Paper Builder and protocol tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

from uriel import datapoints as dpm
from uriel import paper_builder
from uriel.core import load_project, run_workload, save_project, sha256_file
from uriel.demo import make_passing_project
from uriel.plan_lock import lock_plan

SOURCE_TEXT = (
    "Exact membership checks are a standard part of build systems. "
    "They compare recorded file sets with current ones.\n"
)

SECTIONS: Dict[str, str] = {
    "00_abstract.md": (
        "We asked whether exact membership verification detects an unexpected file in a confined software "
        "fixture. In a deterministic unit test with {{dp:n_total}} recorded comparisons, the verifier reported "
        "the added path, t({{dp:df}}) = {{dp:t_stat}}, {{dp:p_main}} [claim:C1]. The fixture is small, so the "
        "result does not establish behavior at scale.\n"
    ),
    "01_introduction.md": (
        "Build systems compare recorded file sets with current ones [@smith2020]. As Smith and Lee put it, "
        "\"They compare recorded file sets with current ones\" [@smith2020]. We test whether the same comparison, "
        "embedded in a research audit workflow, detects an unexpected file before verification is accepted.\n"
    ),
    "02_methods.md": (
        "We used a deterministic unit test over a finite recorded set and a finite current set with one "
        "deliberately added path. The analysis plan was locked with Uriel before the summary was produced. "
        "The reproduction command is python -m unittest discover -s fixture_tests.\n"
    ),
    "03_results.md": (
        "Across {{dp:n_total}} comparisons ({{dp:n_a}} in arm A and {{dp:n_b}} in arm B), the verifier "
        "identified path b as unexpected [claim:C1]. The test statistic was t({{dp:df}}) = {{dp:t_stat}}, "
        "{{dp:p_main}}.\n"
    ),
    "04_discussion.md": (
        "The verifier behaved as specified within this fixture [claim:C1]. Because the fixture is deliberately "
        "small, it says nothing about performance with many files or about concurrent writes. A hard-coded answer "
        "could also pass the positive fixture [alt:X1]; the negative control, which must return an empty list, is the "
        "observation that tells the two apart.\n"
    ),
    "05_limitations.md": (
        "The result is a bounded software fixture. It does not establish performance with many files or race-free "
        "observation during concurrent writes, and other platforms were not tested in this run.\n"
    ),
    "06_conclusion.md": (
        "Within the declared fixture, exact membership verification reported the unexpected path, consistent with "
        "the locked hypothesis; broader behavior remains untested.\n"
    ),
    "07_statements.md": (
        "Data availability: all fixture data are in the artifacts folder. Code availability: the code is available "
        "in analysis.py and fixture_tests. Funding: no funding was received. Competing interests: none. Ethics: not "
        "applicable, because no human or animal data were used. Use of AI tools: no AI tools were used to write "
        "this text.\n"
    ),
}

SUMMARY_SCRIPT = (
    "rows = [('n_total', '40'), ('n_a', '18'), ('n_b', '22'), ('t_stat', '2.20'), ('df', '38'), ('p_main', '0.0339')]\n"
    "with open('artifacts/summary.csv', 'w', encoding='utf-8', newline='\\n') as handle:\n"
    "    handle.write('metric,value\\n')\n"
    "    for key, value in rows:\n"
    "        handle.write(key + ',' + value + '\\n')\n"
)


def make_paper_project(root: Path, *, write_sections: bool = True) -> Path:
    """Create a project whose manuscript passes the submission-profile paper check."""
    make_passing_project(root)
    project = load_project(root)
    project["alternative_explanations"][0].update({
        "status": "partially_addressed",
        "discriminating_observation": "A hard-coded answer would also return [b] for the negative control; "
                                      "an empty result there distinguishes real set comparison.",
    })
    save_project(root, project, event="fixture.alternatives", details={"fixture": "paper"})
    (root / "analysis_summary.py").write_text(SUMMARY_SCRIPT, encoding="utf-8")
    lock_plan(root)
    receipt = run_workload(root, [sys.executable, "analysis_summary.py"], timeout=60, workload_id="summary")
    if receipt["status"] != "PASS":
        raise AssertionError("summary workload failed")
    paper_builder.init_paper(root)
    for key, kind, fmt in (
        ("n_total", "count", None),
        ("n_a", "count", None),
        ("n_b", "count", None),
        ("t_stat", "statistic", ".2f"),
        ("df", "count", None),
        ("p_main", "p_value", "apa_p"),
    ):
        dpm.add_datapoint(
            root,
            datapoint_id=key,
            artifact_path="artifacts/summary.csv",
            locator=dpm.locator_from_arguments(csv_column="value", csv_row=["metric=" + key]),
            description="Summary value " + key + " from the fixture analysis",
            kind=kind,
            fmt=fmt,
            claim_ids=["C1"],
        )
    registry = dpm.load_registry(root)
    registry["relations"] = [{"type": "sum", "parts": ["n_a", "n_b"], "total": "n_total"}]
    (root / "paper" / "datapoints.json").write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    source = root / "sources" / "smith2020.txt"
    source.write_text(SOURCE_TEXT, encoding="utf-8")
    references = {
        "schema": "uriel.references.v1",
        "schema_version": 1,
        "references": [
            {
                "key": "smith2020",
                "authors": ["Smith, J.", "Lee, K."],
                "year": 2020,
                "title": "File sets in build systems",
                "venue": "Journal of Builds",
                "doi": "10.1234/jb.2020.1",
                "artifact_path": "sources/smith2020.txt",
                "sha256": sha256_file(source),
                "verification": {
                    "status": "held",
                    "checked_on": "2026-10-01",
                    "note": "A co-author opened the published article and saved the quoted page text.",
                },
            }
        ],
    }
    (root / "paper" / "references.json").write_text(json.dumps(references, indent=2) + "\n", encoding="utf-8")
    if write_sections:
        for name, text in SECTIONS.items():
            append_section(root, name, text)
    return root


def append_section(root: Path, name: str, text: str) -> None:
    path = root / "paper" / "sections" / name
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def finalize_for_submission(root: Path) -> None:
    """Rerun the reproduction after the final edit, record the audit, and build."""
    from uriel.audit import audit_project

    receipt = run_workload(
        root, [sys.executable, "-m", "unittest", "discover", "-s", "fixture_tests"], timeout=120, workload_id="unit-tests"
    )
    if receipt["status"] != "PASS":
        raise AssertionError("fixture workload failed")
    report = audit_project(root, profile="submission")
    if report.status != "PASS":
        raise AssertionError([f.code for gate in report.gates for f in gate.findings if f.severity == "blocker"])
    paper_builder.build_paper(root, profile="submission")
