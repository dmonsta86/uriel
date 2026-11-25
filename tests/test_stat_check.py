from __future__ import annotations

import unittest

from uriel.stat_check import (
    check_impossible_values,
    check_reported_tests,
    check_text,
    grim_consistent,
    normalize_extracted_text,
    p_from_chi2,
    p_from_f,
    p_from_r,
    p_from_t,
    p_from_z,
)


def codes(text: str):
    return [row["code"] for row in check_text(text)["issues"]]


class DistributionTests(unittest.TestCase):
    def test_critical_values_reproduce_alpha_point_zero_five(self) -> None:
        self.assertAlmostEqual(p_from_t(2.228, 10), 0.05, places=3)
        self.assertAlmostEqual(p_from_f(4.965, 1, 10), 0.05, places=3)
        self.assertAlmostEqual(p_from_chi2(3.841, 1), 0.05, places=3)
        self.assertAlmostEqual(p_from_z(1.96), 0.05, places=3)
        self.assertAlmostEqual(p_from_r(0.576, 10), 0.05, places=3)

    def test_f_with_one_numerator_df_equals_squared_t(self) -> None:
        self.assertAlmostEqual(p_from_f(2.5 ** 2, 1, 30), p_from_t(2.5, 30), places=9)

    def test_chi_square_with_large_df_and_tail(self) -> None:
        self.assertAlmostEqual(p_from_chi2(67.505, 50), 0.05, places=3)
        self.assertLess(p_from_chi2(100, 50), 0.0001)
        self.assertEqual(p_from_chi2(0, 3), 1.0)


class ReportedTestTests(unittest.TestCase):
    def test_consistent_reports_are_not_flagged(self) -> None:
        text = (
            "t(28) = 2.20, p = .036. F(1, 10) = 4.97, p = .05. chi2(1) = 3.84, p = .05. "
            "z = 1.96, p = .05. r(10) = .58, p = .048. t(40) = 6.10, p < .001."
        )
        self.assertEqual([], check_reported_tests(text))

    def test_decision_flip_is_grave(self) -> None:
        issues = check_reported_tests("The difference was reliable, t(28) = 2.20, p = .36.")
        self.assertEqual(["STAT_DECISION_INCONSISTENT"], [row["code"] for row in issues])
        self.assertTrue(issues[0]["grave"])
        self.assertAlmostEqual(issues[0]["detail"]["recomputed_p"], 0.0362, places=3)

    def test_inequality_that_cannot_hold_is_grave(self) -> None:
        issues = check_reported_tests("F(2, 57) = 1.03, p < .05")
        self.assertEqual("STAT_DECISION_INCONSISTENT", issues[0]["code"])

    def test_small_mismatch_without_decision_flip_is_not_grave(self) -> None:
        issues = check_reported_tests("t(28) = 2.20, p = .021")
        self.assertEqual(["STAT_P_INCONSISTENT"], [row["code"] for row in issues])
        self.assertFalse(issues[0]["grave"])

    def test_one_tailed_report_is_accepted_when_declared(self) -> None:
        self.assertEqual([], check_reported_tests("A one-tailed test gave t(20) = 1.80, p = .043."))
        self.assertTrue(check_reported_tests("A test gave t(20) = 1.80, p = .043."))

    def test_rounding_of_the_statistic_is_respected(self) -> None:
        # t(10) = 2.2 spans 2.15..2.25; p = .054 lies inside that interval.
        self.assertEqual([], check_reported_tests("t(10) = 2.2, p = .054"))

    def test_unicode_minus_and_chi_square_spelling(self) -> None:
        self.assertEqual([], check_reported_tests("t(28) = \u22122.20, p = .036 and \u03c7\u00b2(1) = 3.84, p = .05"))


class ImpossibleValueTests(unittest.TestCase):
    def test_impossible_values_are_grave(self) -> None:
        found = codes(
            "p = 1.3. r(48) = 1.20, p < .001. SD = -1.2. d = 0.90, 95% CI [0.20, 0.60]. "
            "Reversed 95% CI [0.6, 0.2]. 45 of 40 (112%)."
        )
        for code in (
            "STAT_IMPOSSIBLE_P",
            "STAT_IMPOSSIBLE_CORRELATION",
            "STAT_NEGATIVE_DISPERSION",
            "STAT_ESTIMATE_OUTSIDE_CI",
            "STAT_CI_BOUNDS_REVERSED",
            "STAT_COUNT_EXCEEDS_TOTAL",
        ):
            self.assertIn(code, found)
        self.assertTrue(all(row["grave"] for row in check_impossible_values("p = 1.3. SD = -1.2.")))

    def test_p_outside_statistical_context_is_not_a_p_value(self) -> None:
        # Regression: a transcription of pi as "p = 3.14" in Einstein's Relativity was read as an impossible p-value.
        self.assertEqual([], check_text("he will not obtain the familiar number p = 3.14 . . ., but a larger number")["issues"])
        self.assertEqual([], check_text("The particle had momentum p = 0 at rest.")["issues"])
        self.assertIn("STAT_IMPOSSIBLE_P", codes("The difference was significant, p = 1.3."))
        self.assertIn("STAT_P_REPORTED_AS_ZERO", codes("M = 3.1, SD = 0.4, p = .000."))

    def test_percent_count_mismatch_and_match(self) -> None:
        self.assertIn("STAT_PERCENT_COUNT_MISMATCH", codes("12 of 40 participants (35%) agreed."))
        self.assertNotIn("STAT_PERCENT_COUNT_MISMATCH", codes("12 of 40 participants (30%) agreed."))
        self.assertNotIn("STAT_PERCENT_COUNT_MISMATCH", codes("1/3 (33.3%) agreed."))

    def test_zero_p_and_ratio_wording_are_advisory(self) -> None:
        issues = check_text("The effect was significant, p = .000. Output reached 150% of baseline.")["issues"]
        self.assertEqual({"STAT_P_REPORTED_AS_ZERO", "STAT_PERCENT_OF_EXCEEDS_100"}, {row["code"] for row in issues})
        self.assertFalse(any(row["grave"] for row in issues))

    def test_estimate_inside_interval_is_clean(self) -> None:
        self.assertEqual([], check_text("d = 0.42, 95% CI [0.10, 0.70]")["issues"])

    def test_line_numbers_are_reported(self) -> None:
        issues = check_text("first line\n\nt(28) = 2.20, p = .36")["issues"]
        self.assertEqual(3, issues[0]["line"])


class ExtractionDamageTests(unittest.TestCase):
    """Regression: strings copied from PDF text of published papers (statcheck's hand-coded
    test material). Before normalization, 78% of these results were silently skipped."""

    def found(self, text: str):
        return [row["code"] for row in check_text(text)["issues"]]

    def test_damaged_but_consistent_results_are_parsed_and_pass(self) -> None:
        for text in (
            "F(1, 127) p 6.36, p ! .05",                    # publisher font: "=" -> p, "<" -> !
            "F(2, 726)=7.20, pb.001",                       # "<" -> b
            "Fs(1, 248)b1.16, psN.28",                      # plural, statistic below bound, ">" -> N
            "t(191) <bc> 8.22, p < . 001, h2 <bc> .26",     # "=" -> <bc>, split decimal
            "B \x01= -\x070.36, t(261.38) \x01= -2.27, p \x01= .024",  # control bytes, Welch df
            "?2(37, N = 310) = 45.13, ns",                  # lost chi, "ns" instead of p
            "\u03c72(374, N = 488) = 1,224.08, p < .001",  # thousands separator
            "F(2, 70) = 4.48, MSE = 6.61, p <.02",          # MSE between statistic and p
            "F(l, 76) = 23.95, p <.001",                    # letter l for digit 1
            "QWithin(16) = 26.05, p = .053",                # Q is chi-square distributed
        ):
            normalized = normalize_extracted_text(text)
            self.assertEqual(1, check_text(text)["reported_tests_found"], (text, normalized))
            self.assertEqual([], self.found(text), text)

    def test_damaged_inconsistent_results_are_flagged(self) -> None:
        self.assertEqual(["STAT_DECISION_INCONSISTENT"], self.found("t(14) = 2.0, p <.03"))
        self.assertEqual(["STAT_DECISION_INCONSISTENT"], self.found("BF(2,56) = 1.203, p < .001"))
        self.assertEqual(["STAT_P_INCONSISTENT"], self.found("F(1, 186) <bc> 5.73, p <bc> .01"))
        self.assertEqual(["STAT_DECISION_INCONSISTENT"], self.found("t(68) = ?2.15, ns"))

    def test_normalization_keeps_line_numbers(self) -> None:
        text = "a\x01b\nline two\n\nt(14) = 2.0, p <.03"
        self.assertEqual(text.count("\n"), normalize_extracted_text(text).count("\n"))
        self.assertEqual(4, check_text(text)["issues"][0]["line"])


class GrimTests(unittest.TestCase):
    def test_known_consistent_and_inconsistent_means(self) -> None:
        self.assertTrue(grim_consistent("3.47", 15))
        self.assertFalse(grim_consistent("3.48", 15))
        self.assertFalse(grim_consistent("5.19", 28))
        self.assertTrue(grim_consistent("2.50", 4, 3))

    def test_large_samples_are_always_consistent_at_two_decimals(self) -> None:
        self.assertTrue(grim_consistent("3.14", 250))

    def test_invalid_sample_size_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            grim_consistent("3.1", 0)


if __name__ == "__main__":
    unittest.main()
