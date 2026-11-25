from __future__ import annotations

import unittest

from uriel.model_check import (
    ModelSyntaxError,
    check_dimensions,
    equation_symbols,
    manuscript_issues,
    parse_unit,
    project_issues,
)


def units(**declared):
    return {name: parse_unit(text) for name, text in declared.items()}


def complete_model(**overrides):
    model = {
        "id": "M1",
        "name": "Exponential decay of recall",
        "equation": "p = p_0 * exp(-k * t)",
        "symbols": {
            "p": {"meaning": "probability of recall", "unit": "1"},
            "p_0": {"meaning": "initial recall probability", "unit": "1"},
            "k": {"meaning": "decay rate", "unit": "1/s"},
            "t": {"meaning": "time since study", "unit": "s"},
        },
        "role": "descriptive_fit",
        "assumptions": ["Forgetting rate is constant over the retention interval."],
        "domain": "Retention intervals between 1 minute and 7 days in adult participants.",
        "source": {"kind": "fitted", "evidence_ids": ["E1"]},
        "verification": [{"method": "numerical_check", "evidence_ids": ["E1"]}],
        "rivals": [{"name": "power-law decay", "outcome": "not_distinguished", "comparison": "AIC difference below 2"}],
    }
    model.update(overrides)
    return {"evidence": [{"id": "E1"}, {"id": "E2"}], "models": [model]}


def codes(issues):
    return [row["code"] for row in issues]


class UnitTests(unittest.TestCase):
    def test_units_reduce_to_base_dimensions(self) -> None:
        self.assertEqual(parse_unit("N"), parse_unit("kg*m/s^2"))
        self.assertEqual(parse_unit("kg m s^-2"), parse_unit("N"))
        self.assertEqual(parse_unit("m s-1"), parse_unit("m/s"))
        self.assertEqual({}, parse_unit("1"))
        self.assertEqual(parse_unit("ms"), parse_unit("s"))
        self.assertEqual(parse_unit("mm"), parse_unit("m"))
        self.assertEqual(parse_unit("J"), parse_unit("N*m"))
        self.assertIn("[score]", parse_unit("[score]/s"))
        with self.assertRaises(ModelSyntaxError):
            parse_unit("furlong")


class DimensionTests(unittest.TestCase):
    def test_consistent_physics(self) -> None:
        self.assertEqual([], check_dimensions("F = m * a", units(F="N", m="kg", a="m/s^2")))
        self.assertEqual([], check_dimensions("E = m * c^2", units(E="J", m="kg", c="m/s")))
        self.assertEqual([], check_dimensions("v = sqrt(2 * g * h)", units(v="m/s", g="m/s^2", h="m")))
        self.assertEqual([], check_dimensions("x = x_0 + v * t + a * t^2 / 2", units(x="m", x_0="m", v="m/s", t="s", a="m/s^2")))

    def test_inconsistencies_are_named(self) -> None:
        problems = check_dimensions("x = v * t + a", units(x="m", v="m/s", t="s", a="m/s"))
        self.assertTrue(any("adds" in problem for problem in problems))
        problems = check_dimensions("E = m * c", units(E="J", m="kg", c="m/s"))
        self.assertTrue(any("left side" in problem for problem in problems))
        problems = check_dimensions("y = A * exp(-k * t)", units(y="1", A="1", k="1", t="s"))
        self.assertTrue(any("exp()" in problem for problem in problems))

    def test_symbolic_power_of_a_dimensioned_quantity(self) -> None:
        # A common way an equation is not properly articulated: t^(-b) has no fixed unit unless t is scaled.
        problems = check_dimensions("y = a * t^(-b)", units(y="1", a="1", t="s", b="1"))
        self.assertTrue(any("symbolic power" in problem for problem in problems))
        self.assertEqual([], check_dimensions("y = a * (t / t_0)^(-b)", units(y="1", a="1", t="s", t_0="s", b="1")))

    def test_parser_handles_implicit_products_and_reports_errors(self) -> None:
        self.assertEqual(["F", "m", "a"], equation_symbols("F = m a"))
        self.assertEqual(["\u0394x", "v", "\u0394t"], equation_symbols("\u0394x = v \u0394t"))
        with self.assertRaises(ModelSyntaxError):
            equation_symbols("F = m *")
        with self.assertRaises(ModelSyntaxError):
            equation_symbols("F m a")


class ModelRecordTests(unittest.TestCase):
    def test_complete_descriptive_model_has_no_blocking_issue(self) -> None:
        issues = project_issues(complete_model())
        self.assertEqual([], [row for row in issues if row["level"] != "style"], issues)

    def test_articulation_gaps(self) -> None:
        model = complete_model(symbols={"p": {"meaning": "probability of recall", "unit": "1"}}, role="")
        found = codes(project_issues(model))
        self.assertIn("MODEL_SYMBOL_UNDEFINED", found)
        self.assertIn("MODEL_ROLE_UNDECLARED", found)
        bad_units = complete_model()
        bad_units["models"][0]["symbols"]["k"]["unit"] = "1"
        self.assertIn(("MODEL_DIMENSIONS_INCONSISTENT", "grave"),
                      [(row["code"], row["level"]) for row in project_issues(bad_units)])

    def test_mechanistic_claims_need_validation_and_a_rival(self) -> None:
        found = codes(project_issues(complete_model(role="mechanistic", rivals=[])))
        self.assertIn("MODEL_NOT_VALIDATED", found)
        self.assertIn("MODEL_NO_RIVAL", found)
        validated = complete_model(
            role="mechanistic",
            validation={"kind": "independent_dataset", "evidence_ids": ["E2"]},
            rivals=[{"name": "power-law decay", "outcome": "disfavoured", "comparison": "held-out error 30% higher"}],
        )
        self.assertNotIn("MODEL_NOT_VALIDATED", codes(project_issues(validated)))
        self.assertNotIn("MODEL_NO_RIVAL", codes(project_issues(validated)))

    def test_untested_implementation(self) -> None:
        model = complete_model(implementation={"artifact_path": "analysis/model.py"})
        issues = project_issues(model, tested_pairs=set(), current_digests={"analysis/model.py": "a" * 64})
        self.assertIn("MODEL_IMPLEMENTATION_UNTESTED", codes(issues))
        tested = project_issues(model, tested_pairs={("analysis/model.py", "a" * 64)},
                                current_digests={"analysis/model.py": "a" * 64})
        self.assertNotIn("MODEL_IMPLEMENTATION_UNTESTED", codes(tested))


class ModelManuscriptTests(unittest.TestCase):
    def section(self, text):
        return [({"id": "methods", "kind": "methods", "file_label": "paper/sections/02_methods.md"}, text)]

    def test_descriptive_fit_described_as_a_law(self) -> None:
        found = codes(manuscript_issues(complete_model(), self.section("This law governs forgetting [model:M1].")))
        self.assertIn("MODEL_REALISM_OVERCLAIM", found)
        ok = codes(manuscript_issues(complete_model(), self.section("The curve reproduces the observed recall [model:M1].")))
        self.assertNotIn("MODEL_REALISM_OVERCLAIM", ok)

    def test_settled_wording_when_a_rival_fits_equally(self) -> None:
        found = codes(manuscript_issues(complete_model(), self.section("The data confirm exponential decay [model:M1].")))
        self.assertIn("MODEL_STATED_AS_SETTLED", found)
        named = codes(manuscript_issues(
            complete_model(), self.section("The data confirm decay but cannot separate it from power-law decay [model:M1].")))
        self.assertNotIn("MODEL_STATED_AS_SETTLED", named)

    def test_equations_must_be_declared_and_models_reported(self) -> None:
        found = codes(manuscript_issues({"models": []}, self.section("We use $E = m c^2$ throughout.")))
        self.assertIn("MODEL_UNDECLARED_EQUATION", found)
        self.assertIn("MODEL_NOT_IN_MANUSCRIPT", codes(manuscript_issues(complete_model(), self.section("No model here."))))
        self.assertIn("MODEL_ANCHOR_UNKNOWN", codes(manuscript_issues(complete_model(), self.section("See [model:M9]."))))


if __name__ == "__main__":
    unittest.main()
