from __future__ import annotations

import unittest

from uriel.framing import alternative_table, manuscript_issues, project_issues, text_issues


def base_project(**alternative):
    project = {
        "claims": [{
            "id": "C1",
            "statement": "A short nap shortens reaction time in the sampled adults.",
            "importance": "major",
            "scope": {"population": "healthy adults aged 18 to 40", "setting": "laboratory", "timeframe": "one session"},
        }],
        "evidence": [{"id": "E1"}],
        "adversarial_tests": [{"id": "T1", "status": "pass"}, {"id": "T2", "status": "pending"}],
        "alternative_explanations": [],
    }
    if alternative:
        row = {"id": "X1", "statement": "Practice on the task, not the nap, shortened reaction time."}
        row.update(alternative)
        project["alternative_explanations"].append(row)
    return project


def codes(issues):
    return [row["code"] for row in issues]


def section(kind, text):
    return ({"id": kind, "kind": kind, "file_label": "paper/sections/" + kind + ".md"}, text)


class ProjectRecordTests(unittest.TestCase):
    def test_claim_without_any_rival_is_reported(self) -> None:
        self.assertIn("CLAIM_WITHOUT_ALTERNATIVE", codes(project_issues(base_project())))

    def test_global_alternative_covers_every_claim(self) -> None:
        project = base_project(discriminating_observation="Practice would also shorten times in the no-nap control group.")
        self.assertNotIn("CLAIM_WITHOUT_ALTERNATIVE", codes(project_issues(project)))

    def test_ruled_out_needs_linked_evidence_or_a_passed_test(self) -> None:
        unsupported = base_project(status="ruled_out")
        self.assertIn("ALTERNATIVE_RULED_OUT_WITHOUT_EVIDENCE", codes(project_issues(unsupported)))
        self.assertEqual("open", alternative_table(unsupported)["X1"]["status"])
        pending = base_project(status="ruled_out", test_ids=["T2"])
        self.assertEqual("open", alternative_table(pending)["X1"]["status"])
        supported = base_project(status="ruled_out", test_ids=["T1"])
        self.assertEqual("ruled_out", alternative_table(supported)["X1"]["status"])
        self.assertEqual([], [c for c in codes(project_issues(supported)) if c.startswith("ALTERNATIVE_")])

    def test_open_alternative_needs_a_discriminating_observation(self) -> None:
        self.assertIn("ALTERNATIVE_NO_DISCRIMINATING_OBSERVATION", codes(project_issues(base_project(status="open"))))

    def test_unknown_claim_link_is_grave(self) -> None:
        issues = project_issues(base_project(claim_ids=["C9"]))
        self.assertIn(("ALTERNATIVE_UNKNOWN_CLAIM", "grave"), [(row["code"], row["level"]) for row in issues])


class ManuscriptTests(unittest.TestCase):
    def test_unaddressed_alternative(self) -> None:
        project = base_project(status="open")
        issues = manuscript_issues(project, [section("discussion", "Naps helped the participants.")])
        self.assertIn("ALTERNATIVE_NOT_ADDRESSED", codes(issues))
        addressed = manuscript_issues(project, [section("discussion", "Practice could also explain the change [alt:X1].")])
        self.assertNotIn("ALTERNATIVE_NOT_ADDRESSED", codes(addressed))

    def test_conclusion_cannot_settle_a_claim_with_an_open_rival(self) -> None:
        project = base_project(status="open")
        settled = manuscript_issues(project, [section("conclusion", "A nap causes faster reactions [claim:C1].")])
        self.assertIn("CONCLUSION_IGNORES_OPEN_ALTERNATIVE", codes(settled))
        for ok in (
            "Faster reactions after a nap are consistent with the hypothesis [claim:C1].",
            "A nap causes faster reactions unless practice explains it [claim:C1] [alt:X1].",
        ):
            self.assertNotIn("CONCLUSION_IGNORES_OPEN_ALTERNATIVE", codes(manuscript_issues(project, [section("conclusion", ok)])), ok)
        ruled_out = base_project(status="ruled_out", test_ids=["T1"])
        self.assertNotIn("CONCLUSION_IGNORES_OPEN_ALTERNATIVE",
                         codes(manuscript_issues(ruled_out, [section("conclusion", "A nap causes faster reactions [claim:C1].")])))

    def test_dismissal_requires_the_record_to_rule_the_rival_out(self) -> None:
        project = base_project(status="open")
        dismissed = manuscript_issues(project, [section("discussion", "We rule out practice effects [alt:X1].")])
        self.assertIn("ALTERNATIVE_DISMISSED_WITHOUT_EVIDENCE", codes(dismissed))
        acknowledged = manuscript_issues(project, [section("discussion", "We cannot rule out practice effects [alt:X1].")])
        self.assertNotIn("ALTERNATIVE_DISMISSED_WITHOUT_EVIDENCE", codes(acknowledged))
        supported = base_project(status="ruled_out", test_ids=["T1"])
        self.assertNotIn("ALTERNATIVE_DISMISSED_WITHOUT_EVIDENCE",
                         codes(manuscript_issues(supported, [section("discussion", "We rule out practice effects [alt:X1].")])))

    def test_reading_data_one_way_without_any_recorded_rival(self) -> None:
        text = "The difference of {{dp:diff}} ms indicates that naps restore alertness [claim:C1]."
        issues = manuscript_issues(base_project(), [section("results", text)], {"diff": ["C1"]})
        self.assertIn("INTERPRETATION_WITHOUT_ALTERNATIVE", codes(issues))
        with_rival = manuscript_issues(base_project(status="open"), [section("results", text)], {"diff": ["C1"]})
        self.assertNotIn("INTERPRETATION_WITHOUT_ALTERNATIVE", codes(with_rival))
        self.assertIn("INTERPRETATION_IN_RESULTS", codes(with_rival))

    def test_conclusion_beyond_recorded_scope(self) -> None:
        issues = manuscript_issues(
            base_project(status="ruled_out", test_ids=["T1"]),
            [section("conclusion", "Naps always improve reaction time in humans [claim:C1].")],
        )
        flagged = [row["message"] for row in issues if row["code"] == "CONCLUSION_EXCEEDS_SCOPE"]
        self.assertEqual(2, len(flagged))
        self.assertIn("healthy adults aged 18 to 40", flagged[0])

    def test_unknown_alternative_anchor_is_grave(self) -> None:
        issues = manuscript_issues(base_project(), [section("discussion", "Something else [alt:X7].")])
        self.assertIn(("ALTERNATIVE_ANCHOR_UNKNOWN", "grave"), [(row["code"], row["level"]) for row in issues])


class TextOnlyTests(unittest.TestCase):
    def test_single_explanation_and_bare_dismissal(self) -> None:
        issues = text_issues("The only explanation is reduced fatigue. Order effects can be dismissed.")
        self.assertEqual({"SINGLE_EXPLANATION_ASSERTED", "DISMISSAL_WITHOUT_SUPPORT"}, set(codes(issues)))
        self.assertEqual([], codes(text_issues("Order effects can be dismissed because counterbalancing removed them [@lee2020].")))
        self.assertEqual([], codes(text_issues("We cannot rule out order effects.")))
        # Regression (Einstein, Relativity): a practical constraint is not a single-explanation claim about data.
        self.assertEqual([], codes(text_issues("The only reason why we must wait for a total eclipse is the bright sky.")))

    def test_document_that_never_considers_another_explanation(self) -> None:
        text = ("Naps shorten reaction time. This shows that sleep restores alertness. "
                "The effect is due to recovered attention. Therefore schools should schedule naps.")
        self.assertIn("NO_ALTERNATIVES_CONSIDERED", codes(text_issues(text)))
        considered = text + " Practice effects could also explain part of the difference."
        self.assertNotIn("NO_ALTERNATIVES_CONSIDERED", codes(text_issues(considered)))
        self.assertNotIn("NO_ALTERNATIVES_CONSIDERED", codes(text_issues(text, document_level=False)))


if __name__ == "__main__":
    unittest.main()
