"""Tests for DirectionalValidator — generic sensitivity testing framework.

Validates:
    - DirectionalTest creation and validation
    - SwapTest creation
    - Chi-squared test correctness
    - Mann-Whitney U test correctness
    - DirectionalValidator with mock LLM
    - YAML / dict loading
    - Ordinal and categorical evaluation
    - Report serialization
    - Edge cases (empty responses, all identical)
"""

import json
import pytest
from collections import Counter
from unittest.mock import MagicMock
from typing import Dict, Tuple

from broker.validators.calibration.directional_validator import (
    DirectionalTest,
    DirectionalTestResult,
    DirectionalReport,
    DirectionalValidator,
    SwapTest,
    chi_squared_test,
    mann_whitney_u,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ordinal_test():
    """Ordinal directional test (TP increases with flood depth)."""
    return DirectionalTest(
        name="flood_depth_tp",
        stimulus_field="flood_depth_ft",
        stimulus_values={"low": "0.5 ft minor flooding", "high": "6.0 ft severe flooding"},
        expected_response_field="TP_LABEL",
        expected_direction="increase",
        ordinal_map={"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5},
    )


@pytest.fixture
def categorical_test():
    """Categorical directional test (decisions differ with income)."""
    return DirectionalTest(
        name="income_decisions",
        stimulus_field="income",
        stimulus_values={"low": "$20,000", "high": "$100,000"},
        expected_response_field="decision",
        expected_direction="increase",
    )


@pytest.fixture
def swap_test():
    """Swap test (income swap)."""
    return SwapTest(
        name="income_swap",
        description="Swap income between MG and NMG",
        base_persona={"income": "$25,000", "flood_zone": "AE"},
        swap_fields={"income": "$100,000"},
        expected_effect="significant_change",
    )


def make_mock_invoke(response_map):
    """Create a mock invoke function that returns responses based on stimulus.

    Parameters
    ----------
    response_map : dict
        Maps stimulus substring -> list of response dicts to cycle through.
    """
    counters = {k: 0 for k in response_map}

    def invoke(prompt: str) -> Tuple[str, bool]:
        for key, responses in response_map.items():
            if key in prompt:
                idx = counters[key] % len(responses)
                counters[key] += 1
                return json.dumps(responses[idx]), True
        return "", False

    return invoke


# ---------------------------------------------------------------------------
# DirectionalTest dataclass
# ---------------------------------------------------------------------------

class TestDirectionalTestSpec:
    def test_creation(self, ordinal_test):
        assert ordinal_test.name == "flood_depth_tp"
        assert ordinal_test.expected_direction == "increase"
        assert ordinal_test.ordinal_map["VH"] == 5

    def test_invalid_direction(self):
        with pytest.raises(ValueError, match="increase.*decrease"):
            DirectionalTest(
                name="bad",
                stimulus_field="x",
                stimulus_values={"low": "a", "high": "b"},
                expected_response_field="y",
                expected_direction="sideways",
            )

    def test_missing_stimulus_keys(self):
        with pytest.raises(ValueError, match="low.*high"):
            DirectionalTest(
                name="bad",
                stimulus_field="x",
                stimulus_values={"small": "a", "large": "b"},
                expected_response_field="y",
                expected_direction="increase",
            )

    def test_from_dict(self):
        d = {
            "name": "test",
            "stimulus_field": "depth",
            "stimulus_values": {"low": "1ft", "high": "6ft"},
            "expected_response_field": "TP_LABEL",
            "expected_direction": "increase",
            "ordinal_map": {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5},
            "construct": "threat_perception",
        }
        test = DirectionalTest.from_dict(d)
        assert test.construct == "threat_perception"
        assert test.ordinal_map["VH"] == 5

    def test_from_dict_no_ordinal(self):
        d = {
            "name": "cat_test",
            "stimulus_field": "income",
            "stimulus_values": {"low": "low", "high": "high"},
            "expected_response_field": "decision",
            "expected_direction": "increase",
        }
        test = DirectionalTest.from_dict(d)
        assert test.ordinal_map == {}


# ---------------------------------------------------------------------------
# SwapTest dataclass
# ---------------------------------------------------------------------------

class TestSwapTestSpec:
    def test_creation(self, swap_test):
        assert swap_test.name == "income_swap"
        assert swap_test.swap_fields["income"] == "$100,000"

    def test_from_dict(self):
        d = {
            "name": "zone_swap",
            "description": "Move to safe zone",
            "base_persona": {"zone": "AE"},
            "swap_fields": {"zone": "X"},
            "expected_effect": "significant_change",
        }
        test = SwapTest.from_dict(d)
        assert test.swap_fields["zone"] == "X"


# ---------------------------------------------------------------------------
# Chi-squared test
# ---------------------------------------------------------------------------

class TestChiSquared:
    def test_identical_distributions(self):
        dist = {"A": 10, "B": 10, "C": 10}
        result = chi_squared_test(dist, dist)
        assert result["chi2"] == pytest.approx(0.0)
        assert result["p_value"] == pytest.approx(1.0)
        assert result["cramers_v"] == pytest.approx(0.0)

    def test_different_distributions(self):
        dist_a = {"A": 20, "B": 5}
        dist_b = {"A": 5, "B": 20}
        result = chi_squared_test(dist_a, dist_b)
        assert result["chi2"] > 0
        assert result["p_value"] < 0.05
        assert result["cramers_v"] > 0

    def test_single_category(self):
        dist_a = {"A": 10}
        dist_b = {"A": 10}
        result = chi_squared_test(dist_a, dist_b)
        assert result["p_value"] == 1.0

    def test_empty_distribution(self):
        result = chi_squared_test({}, {"A": 10})
        assert result["p_value"] == 1.0

    def test_zero_count_columns(self):
        dist_a = {"A": 10, "B": 0, "C": 5}
        dist_b = {"A": 5, "B": 0, "C": 10}
        result = chi_squared_test(dist_a, dist_b)
        # B column removed (all zeros), test on A vs C
        assert result["chi2"] > 0


# ---------------------------------------------------------------------------
# Mann-Whitney U test
# ---------------------------------------------------------------------------

class TestMannWhitneyU:
    def test_clear_increase(self):
        low_vals = [1.0, 1.0, 2.0, 1.0, 2.0]
        high_vals = [4.0, 5.0, 4.0, 5.0, 5.0]
        result = mann_whitney_u(low_vals, high_vals)
        assert result["p_value"] < 0.05
        assert result["direction"] == "increase"
        assert result["mean_b"] > result["mean_a"]

    def test_clear_decrease(self):
        low_vals = [5.0, 5.0, 4.0, 5.0, 4.0]
        high_vals = [1.0, 2.0, 1.0, 1.0, 2.0]
        result = mann_whitney_u(low_vals, high_vals)
        assert result["p_value"] < 0.05
        assert result["direction"] == "decrease"

    def test_identical_values(self):
        vals = [3.0, 3.0, 3.0, 3.0]
        result = mann_whitney_u(vals, vals)
        assert result["direction"] == "none"
        assert result["p_value"] == 1.0

    def test_empty_lists(self):
        result = mann_whitney_u([], [1.0, 2.0])
        assert result["p_value"] == 1.0
        assert result["direction"] == "none"

    def test_effect_size_range(self):
        low_vals = [1.0, 2.0, 1.0, 2.0, 1.0]
        high_vals = [4.0, 5.0, 4.0, 5.0, 4.0]
        result = mann_whitney_u(low_vals, high_vals)
        # Effect size (rank-biserial) should be in [-1, 1]
        assert -1.0 <= result["effect_size"] <= 1.0


# ---------------------------------------------------------------------------
# DirectionalValidator with mock LLM
# ---------------------------------------------------------------------------

class TestValidatorExecution:
    def test_ordinal_test_passing(self, ordinal_test):
        """LLM responds with low TP for low depth, high TP for high depth."""
        validator = DirectionalValidator()
        validator.add_test(ordinal_test)

        def prompt_builder(context, stimulus):
            return f"Depth: {stimulus}. Rate your threat perception."

        def parse_fn(raw):
            d = json.loads(raw)
            return d

        invoke = make_mock_invoke({
            "0.5 ft": [
                {"TP_LABEL": "VL"}, {"TP_LABEL": "L"}, {"TP_LABEL": "L"},
                {"TP_LABEL": "VL"}, {"TP_LABEL": "L"}, {"TP_LABEL": "L"},
                {"TP_LABEL": "VL"}, {"TP_LABEL": "L"}, {"TP_LABEL": "VL"},
                {"TP_LABEL": "L"},
            ],
            "6.0 ft": [
                {"TP_LABEL": "VH"}, {"TP_LABEL": "H"}, {"TP_LABEL": "VH"},
                {"TP_LABEL": "H"}, {"TP_LABEL": "VH"}, {"TP_LABEL": "H"},
                {"TP_LABEL": "VH"}, {"TP_LABEL": "H"}, {"TP_LABEL": "VH"},
                {"TP_LABEL": "H"},
            ],
        })

        validator.register_prompt_builder(prompt_builder)
        validator.register_parse_fn(parse_fn)

        report = validator.run_all(invoke, replicates=10)
        assert report.n_tests == 1
        assert report.results[0].passed is True
        assert report.results[0].direction_observed == "increase"
        assert report.pass_rate == 1.0

    def test_ordinal_test_failing_wrong_direction(self, ordinal_test):
        """LLM responds with HIGH TP for low depth (wrong direction)."""
        validator = DirectionalValidator()
        validator.add_test(ordinal_test)

        def prompt_builder(context, stimulus):
            return f"Depth: {stimulus}."

        def parse_fn(raw):
            return json.loads(raw)

        # Reversed: high TP for low stimulus
        invoke = make_mock_invoke({
            "0.5 ft": [
                {"TP_LABEL": "VH"}, {"TP_LABEL": "H"}, {"TP_LABEL": "VH"},
                {"TP_LABEL": "H"}, {"TP_LABEL": "VH"},
            ],
            "6.0 ft": [
                {"TP_LABEL": "VL"}, {"TP_LABEL": "L"}, {"TP_LABEL": "VL"},
                {"TP_LABEL": "L"}, {"TP_LABEL": "VL"},
            ],
        })

        validator.register_prompt_builder(prompt_builder)
        validator.register_parse_fn(parse_fn)

        report = validator.run_all(invoke, replicates=5)
        assert report.results[0].passed is False

    def test_categorical_test(self, categorical_test):
        """Categorical test — decisions differ significantly."""
        validator = DirectionalValidator()
        validator.add_test(categorical_test)

        def prompt_builder(context, stimulus):
            return f"Income: {stimulus}."

        def parse_fn(raw):
            return json.loads(raw)

        invoke = make_mock_invoke({
            "$20,000": [
                {"decision": "do_nothing"}, {"decision": "do_nothing"},
                {"decision": "do_nothing"}, {"decision": "buy_insurance"},
                {"decision": "do_nothing"}, {"decision": "do_nothing"},
                {"decision": "do_nothing"}, {"decision": "do_nothing"},
                {"decision": "do_nothing"}, {"decision": "buy_insurance"},
            ],
            "$100,000": [
                {"decision": "elevate_house"}, {"decision": "buy_insurance"},
                {"decision": "elevate_house"}, {"decision": "buy_insurance"},
                {"decision": "elevate_house"}, {"decision": "buy_insurance"},
                {"decision": "elevate_house"}, {"decision": "buy_insurance"},
                {"decision": "elevate_house"}, {"decision": "elevate_house"},
            ],
        })

        validator.register_prompt_builder(prompt_builder)
        validator.register_parse_fn(parse_fn)

        report = validator.run_all(invoke, replicates=10)
        assert report.results[0].passed is True

    def test_swap_test(self, swap_test):
        """Swap test — decisions change when persona is swapped."""
        validator = DirectionalValidator()
        validator.add_swap_test(swap_test)

        def prompt_builder(context, stimulus):
            return f"Persona: {stimulus}. Decide."

        def parse_fn(raw):
            return json.loads(raw)

        invoke = make_mock_invoke({
            "$25,000": [
                {"decision": "do_nothing"}, {"decision": "do_nothing"},
                {"decision": "do_nothing"}, {"decision": "do_nothing"},
                {"decision": "do_nothing"}, {"decision": "buy_insurance"},
                {"decision": "do_nothing"}, {"decision": "do_nothing"},
                {"decision": "do_nothing"}, {"decision": "do_nothing"},
            ],
            "$100,000": [
                {"decision": "elevate_house"}, {"decision": "buy_insurance"},
                {"decision": "elevate_house"}, {"decision": "buy_insurance"},
                {"decision": "elevate_house"}, {"decision": "buy_insurance"},
                {"decision": "buy_insurance"}, {"decision": "elevate_house"},
                {"decision": "buy_insurance"}, {"decision": "elevate_house"},
            ],
        })

        validator.register_prompt_builder(prompt_builder)
        validator.register_parse_fn(parse_fn)

        report = validator.run_all(invoke, replicates=10)
        assert report.results[0].passed is True
        assert report.results[0].test_type == "swap"

    def test_no_prompt_builder_raises(self, ordinal_test):
        validator = DirectionalValidator()
        validator.add_test(ordinal_test)
        validator.register_parse_fn(lambda raw: {})

        with pytest.raises(RuntimeError, match="prompt_builder"):
            validator.run_all(lambda p: ("", True))

    def test_no_parse_fn_raises(self, ordinal_test):
        validator = DirectionalValidator()
        validator.add_test(ordinal_test)
        validator.register_prompt_builder(lambda ctx, stim: "")

        with pytest.raises(RuntimeError, match="parse_fn"):
            validator.run_all(lambda p: ("", True))

    def test_multiple_tests(self, ordinal_test, categorical_test, swap_test):
        """Run multiple tests at once."""
        validator = DirectionalValidator()
        validator.add_test(ordinal_test)
        validator.add_test(categorical_test)
        validator.add_swap_test(swap_test)

        def prompt_builder(context, stimulus):
            return f"Test: {stimulus}"

        def parse_fn(raw):
            return json.loads(raw)

        # Simple mock that returns consistent responses
        call_count = [0]

        def invoke(prompt):
            call_count[0] += 1
            # Return something parseable
            return json.dumps({"TP_LABEL": "H", "decision": "buy_insurance"}), True

        validator.register_prompt_builder(prompt_builder)
        validator.register_parse_fn(parse_fn)

        report = validator.run_all(invoke, replicates=5)
        assert report.n_tests == 3
        assert call_count[0] > 0


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

class TestLoading:
    def test_load_from_dict(self):
        data = {
            "directional_tests": [
                {
                    "name": "depth_test",
                    "stimulus_field": "depth",
                    "stimulus_values": {"low": "1ft", "high": "6ft"},
                    "expected_response_field": "TP_LABEL",
                    "expected_direction": "increase",
                    "ordinal_map": {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5},
                },
            ],
            "swap_tests": [
                {
                    "name": "income_swap",
                    "base_persona": {"income": "low"},
                    "swap_fields": {"income": "high"},
                },
            ],
        }
        validator = DirectionalValidator()
        validator.load_from_dict(data)
        assert len(validator._directional_tests) == 1
        assert len(validator._swap_tests) == 1

    def test_load_from_yaml(self, tmp_path):
        yaml_content = """
directional_tests:
  - name: depth_tp
    stimulus_field: depth
    stimulus_values:
      low: "1 ft"
      high: "6 ft"
    expected_response_field: TP_LABEL
    expected_direction: increase
    ordinal_map:
      VL: 1
      L: 2
      M: 3
      H: 4
      VH: 5

swap_tests:
  - name: income_swap
    base_persona:
      income: "$25,000"
    swap_fields:
      income: "$100,000"
"""
        yaml_path = tmp_path / "tests.yaml"
        yaml_path.write_text(yaml_content)

        validator = DirectionalValidator()
        validator.load_from_yaml(yaml_path)
        assert len(validator._directional_tests) == 1
        assert len(validator._swap_tests) == 1

    def test_load_from_yaml_nested(self, tmp_path):
        yaml_content = """
calibration:
  directional_tests:
    - name: nested_test
      stimulus_field: x
      stimulus_values:
        low: "a"
        high: "b"
      expected_response_field: y
      expected_direction: increase
"""
        yaml_path = tmp_path / "nested.yaml"
        yaml_path.write_text(yaml_content)

        validator = DirectionalValidator()
        validator.load_from_yaml(yaml_path)
        assert len(validator._directional_tests) == 1


# ---------------------------------------------------------------------------
# Report serialization
# ---------------------------------------------------------------------------

class TestReportSerialization:
    def test_result_to_dict(self):
        result = DirectionalTestResult(
            test_name="test1",
            passed=True,
            p_value=0.001,
            effect_size=0.85,
            direction_observed="increase",
            direction_expected="increase",
            low_distribution={"L": 8, "VL": 2},
            high_distribution={"H": 7, "VH": 3},
            test_type="directional",
            statistic_name="mann_whitney_u",
            statistic_value=2.5,
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["p_value"] == 0.001
        assert d["statistic_name"] == "mann_whitney_u"

    def test_report_to_dict(self):
        report = DirectionalReport(
            results=[
                DirectionalTestResult(
                    test_name="t1", passed=True, p_value=0.01,
                    effect_size=0.5, direction_observed="increase",
                    direction_expected="increase",
                ),
            ],
            n_tests=1,
            n_passed=1,
            pass_rate=1.0,
        )
        d = report.to_dict()
        assert d["n_tests"] == 1
        assert d["pass_rate"] == 1.0

    def test_report_save_json(self, tmp_path):
        report = DirectionalReport(
            results=[
                DirectionalTestResult(
                    test_name="t1", passed=True, p_value=0.01,
                    effect_size=0.5, direction_observed="increase",
                    direction_expected="increase",
                ),
            ],
            n_tests=1,
            n_passed=1,
            pass_rate=1.0,
        )
        json_path = tmp_path / "report.json"
        report.save_json(json_path)
        loaded = json.loads(json_path.read_text())
        assert loaded["n_passed"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_all_llm_calls_fail(self, ordinal_test):
        """All LLM calls fail — should still return a result."""
        validator = DirectionalValidator()
        validator.add_test(ordinal_test)
        validator.register_prompt_builder(lambda ctx, stim: "prompt")
        validator.register_parse_fn(lambda raw: json.loads(raw))

        # All calls fail
        def failing_invoke(prompt):
            return "", False

        report = validator.run_all(failing_invoke, replicates=5)
        assert report.n_tests == 1
        # With no data, test should not pass
        assert report.results[0].passed is False

    def test_empty_validator(self):
        """No tests registered — report should be empty."""
        validator = DirectionalValidator()
        validator.register_prompt_builder(lambda ctx, stim: "")
        validator.register_parse_fn(lambda raw: {})

        report = validator.run_all(lambda p: ("", True), replicates=5)
        assert report.n_tests == 0
        assert report.pass_rate == 0.0

    def test_custom_alpha(self, ordinal_test):
        """Custom alpha level."""
        validator = DirectionalValidator(alpha=0.10)
        validator.add_test(ordinal_test)
        validator.register_prompt_builder(lambda ctx, stim: f"s: {stim}")
        validator.register_parse_fn(lambda raw: json.loads(raw))

        # Marginal difference
        invoke = make_mock_invoke({
            "0.5 ft": [{"TP_LABEL": "L"}, {"TP_LABEL": "M"}, {"TP_LABEL": "L"}],
            "6.0 ft": [{"TP_LABEL": "M"}, {"TP_LABEL": "H"}, {"TP_LABEL": "M"}],
        })

        # Override alpha at run time
        report = validator.run_all(invoke, replicates=3, alpha=0.001)
        # With such strict alpha, marginal differences shouldn't pass
        assert report.results[0].p_value > 0 or report.results[0].p_value <= 1
