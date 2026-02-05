"""
Directional Validator — Generic Sensitivity Testing Framework.

Tests whether LLM agents respond in the expected direction when
stimulus conditions change.  Generalizes persona sensitivity and
prompt sensitivity analyses into a callback-based engine that works
for any domain.

Two test types:

    :class:`DirectionalTest` — vary a single stimulus (e.g., flood depth)
        and verify the LLM response moves in the expected direction
        (e.g., TP increases).  Uses Mann-Whitney U for ordinal responses
        and chi-squared for categorical responses.

    :class:`SwapTest` — swap one or more persona fields and verify that
        the LLM's output distribution changes significantly.  Uses
        chi-squared test of independence.

Callback protocols:

    Callers register ``prompt_builder_fn`` and ``parse_fn`` callbacks.
    The validator uses these to construct prompts and parse responses
    without importing any domain-specific code.

Usage::

    from broker.validators.calibration.directional_validator import (
        DirectionalValidator, DirectionalTest, SwapTest,
    )

    validator = DirectionalValidator()
    validator.add_test(DirectionalTest(
        name="flood_depth_increases_threat",
        stimulus_field="flood_depth_ft",
        stimulus_values={"low": "0.5 ft", "high": "6.0 ft"},
        expected_response_field="TP_LABEL",
        expected_direction="increase",
        ordinal_map={"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5},
    ))
    validator.register_prompt_builder(my_prompt_builder)
    validator.register_parse_fn(my_parse_fn)

    report = validator.run_all(invoke_fn=my_llm_invoke, replicates=10)
    print(f"Pass rate: {report.pass_rate:.2f}")

Part of SAGE Calibration Protocol.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test specification dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DirectionalTest:
    """Specification for a single directional sensitivity test.

    Parameters
    ----------
    name : str
        Test identifier.
    stimulus_field : str
        Which variable is changed between conditions.
    stimulus_values : dict
        Mapping ``{"low": ..., "high": ...}`` providing the two
        stimulus levels.
    expected_response_field : str
        Which output field to check (e.g., "TP_LABEL", "decision").
    expected_direction : str
        ``"increase"`` or ``"decrease"`` — the expected direction of
        change in the response when stimulus goes from low to high.
    ordinal_map : dict, optional
        Maps categorical labels to numeric values for ordinal tests
        (e.g., ``{"VL": 1, ..., "VH": 5}``).  If provided,
        Mann-Whitney U is used; otherwise chi-squared.
    construct : str
        Psychological construct name (for reporting).
    description : str
        Human-readable description of the test.
    """

    name: str
    stimulus_field: str
    stimulus_values: Dict[str, str]
    expected_response_field: str
    expected_direction: str
    ordinal_map: Dict[str, int] = field(default_factory=dict)
    construct: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.expected_direction not in ("increase", "decrease"):
            raise ValueError(
                f"DirectionalTest '{self.name}': expected_direction must be "
                f"'increase' or 'decrease', got '{self.expected_direction}'"
            )
        if "low" not in self.stimulus_values or "high" not in self.stimulus_values:
            raise ValueError(
                f"DirectionalTest '{self.name}': stimulus_values must have "
                f"'low' and 'high' keys"
            )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> DirectionalTest:
        """Construct from a dictionary (e.g., parsed from YAML)."""
        ordinal_map = d.get("ordinal_map", {})
        # Ensure numeric values
        if ordinal_map:
            ordinal_map = {str(k): int(v) for k, v in ordinal_map.items()}
        return cls(
            name=d["name"],
            stimulus_field=d["stimulus_field"],
            stimulus_values=d["stimulus_values"],
            expected_response_field=d["expected_response_field"],
            expected_direction=d["expected_direction"],
            ordinal_map=ordinal_map,
            construct=d.get("construct", ""),
            description=d.get("description", ""),
        )


@dataclass
class SwapTest:
    """Specification for a persona swap test.

    Parameters
    ----------
    name : str
        Test identifier.
    description : str
        Human-readable description.
    base_persona : dict
        Base persona configuration fields.
    swap_fields : dict
        Fields to swap (key → new value).
    expected_effect : str
        ``"significant_change"`` or ``"no_change"`` — what is expected.
    """

    name: str
    description: str = ""
    base_persona: Dict[str, Any] = field(default_factory=dict)
    swap_fields: Dict[str, Any] = field(default_factory=dict)
    expected_effect: str = "significant_change"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> SwapTest:
        """Construct from a dictionary (e.g., parsed from YAML)."""
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            base_persona=d.get("base_persona", {}),
            swap_fields=d.get("swap_fields", {}),
            expected_effect=d.get("expected_effect", "significant_change"),
        )


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DirectionalTestResult:
    """Result of a single directional or swap test."""

    test_name: str
    passed: bool
    p_value: float
    effect_size: float
    direction_observed: str  # "increase", "decrease", "none"
    direction_expected: str
    low_distribution: Dict[str, int] = field(default_factory=dict)
    high_distribution: Dict[str, int] = field(default_factory=dict)
    test_type: str = "directional"  # "directional" or "swap"
    statistic_name: str = ""  # "mann_whitney_u" or "chi_squared"
    statistic_value: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "test_name": self.test_name,
            "passed": self.passed,
            "p_value": round(self.p_value, 6),
            "effect_size": round(self.effect_size, 4),
            "direction_observed": self.direction_observed,
            "direction_expected": self.direction_expected,
            "low_distribution": self.low_distribution,
            "high_distribution": self.high_distribution,
            "test_type": self.test_type,
            "statistic_name": self.statistic_name,
            "statistic_value": round(self.statistic_value, 4),
        }


@dataclass
class DirectionalReport:
    """Complete directional validation report."""

    results: List[DirectionalTestResult] = field(default_factory=list)
    n_tests: int = 0
    n_passed: int = 0
    pass_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "n_tests": self.n_tests,
            "n_passed": self.n_passed,
            "pass_rate": round(self.pass_rate, 4),
            "results": [r.to_dict() for r in self.results],
        }

    def save_json(self, path: Union[str, Path]) -> None:
        """Save report to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


# ---------------------------------------------------------------------------
# Statistical tests (static — reusable without instantiation)
# ---------------------------------------------------------------------------

def chi_squared_test(
    dist_a: Dict[str, int],
    dist_b: Dict[str, int],
) -> Dict[str, Any]:
    """Chi-squared test of independence between two distributions.

    Parameters
    ----------
    dist_a, dist_b : dict
        Mappings of category label -> count.

    Returns
    -------
    dict
        Keys: chi2, p_value, cramers_v, df.
    """
    try:
        from scipy import stats as sp_stats
    except ImportError:
        logger.warning("scipy not available — returning trivial chi-squared result")
        return {"chi2": 0.0, "p_value": 1.0, "cramers_v": 0.0, "df": 0}

    all_labels = sorted(set(dist_a.keys()) | set(dist_b.keys()))
    if len(all_labels) < 2:
        return {"chi2": 0.0, "p_value": 1.0, "cramers_v": 0.0, "df": 0}

    observed = np.array(
        [
            [int(dist_a.get(lbl, 0)) for lbl in all_labels],
            [int(dist_b.get(lbl, 0)) for lbl in all_labels],
        ],
        dtype=int,
    )

    # Remove columns with all zeros
    col_sums = observed.sum(axis=0)
    observed = observed[:, col_sums > 0]

    if observed.shape[1] < 2:
        return {"chi2": 0.0, "p_value": 1.0, "cramers_v": 0.0, "df": 0}

    chi2, p_val, df, _ = sp_stats.chi2_contingency(observed)
    n = observed.sum()
    k = min(observed.shape) - 1
    cramers_v = float(np.sqrt(chi2 / (n * k))) if n * k > 0 else 0.0

    return {
        "chi2": float(chi2),
        "p_value": float(p_val),
        "cramers_v": cramers_v,
        "df": int(df),
    }


def mann_whitney_u(
    values_a: List[float],
    values_b: List[float],
) -> Dict[str, Any]:
    """Mann-Whitney U test for ordinal data.

    Parameters
    ----------
    values_a, values_b : list of float
        Numeric values (converted from ordinal labels via ordinal_map).

    Returns
    -------
    dict
        Keys: u_statistic, p_value, effect_size (rank-biserial r),
        mean_a, mean_b, direction.
    """
    if not values_a or not values_b:
        return {
            "u_statistic": 0.0,
            "p_value": 1.0,
            "effect_size": 0.0,
            "mean_a": 0.0,
            "mean_b": 0.0,
            "direction": "none",
        }

    try:
        from scipy import stats as sp_stats
    except ImportError:
        logger.warning("scipy not available — returning trivial Mann-Whitney result")
        mean_a = float(np.mean(values_a))
        mean_b = float(np.mean(values_b))
        return {
            "u_statistic": 0.0,
            "p_value": 1.0,
            "effect_size": 0.0,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "direction": "none",
        }

    mean_a = float(np.mean(values_a))
    mean_b = float(np.mean(values_b))

    # All values identical → no difference
    if np.std(values_a + values_b) == 0:
        return {
            "u_statistic": 0.0,
            "p_value": 1.0,
            "effect_size": 0.0,
            "mean_a": mean_a,
            "mean_b": mean_b,
            "direction": "none",
        }

    u_stat, p_val = sp_stats.mannwhitneyu(
        values_a, values_b, alternative="two-sided"
    )

    # Rank-biserial effect size: r = 1 - (2U)/(n1*n2)
    n1, n2 = len(values_a), len(values_b)
    effect_size = 1 - (2 * u_stat) / (n1 * n2) if n1 * n2 > 0 else 0.0

    if mean_b > mean_a + 1e-9:
        direction = "increase"
    elif mean_a > mean_b + 1e-9:
        direction = "decrease"
    else:
        direction = "none"

    return {
        "u_statistic": float(u_stat),
        "p_value": float(p_val),
        "effect_size": float(effect_size),
        "mean_a": mean_a,
        "mean_b": mean_b,
        "direction": direction,
    }


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

# Type aliases for callback protocols
PromptBuilderFn = Callable[[Dict[str, Any], str], str]
"""(context_dict, stimulus_value) -> prompt_string"""

ParseFn = Callable[[str], Dict[str, str]]
"""(raw_llm_output) -> parsed_dict with response field values"""

InvokeFn = Callable[[str], Tuple[str, bool]]
"""(prompt) -> (raw_output, success)"""


class DirectionalValidator:
    """Generic sensitivity testing framework.

    Manages a collection of :class:`DirectionalTest` and
    :class:`SwapTest` specifications.  When ``run_all`` is called,
    it probes an LLM via the registered callbacks and computes
    statistical tests on the response distributions.

    Parameters
    ----------
    alpha : float
        Significance level for statistical tests (default 0.05).
    """

    def __init__(self, alpha: float = 0.05) -> None:
        self._directional_tests: List[DirectionalTest] = []
        self._swap_tests: List[SwapTest] = []
        self._prompt_builder: Optional[PromptBuilderFn] = None
        self._parse_fn: Optional[ParseFn] = None
        self._alpha = alpha

    # -------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------

    def add_test(self, test: DirectionalTest) -> None:
        """Add a directional test."""
        self._directional_tests.append(test)

    def add_tests(self, tests: List[DirectionalTest]) -> None:
        """Add multiple directional tests."""
        self._directional_tests.extend(tests)

    def add_swap_test(self, test: SwapTest) -> None:
        """Add a swap test."""
        self._swap_tests.append(test)

    def add_swap_tests(self, tests: List[SwapTest]) -> None:
        """Add multiple swap tests."""
        self._swap_tests.extend(tests)

    def register_prompt_builder(self, fn: PromptBuilderFn) -> None:
        """Register the prompt builder callback.

        The function signature must be::

            def builder(context: dict, stimulus_value: str) -> str

        where ``context`` is a dict with test metadata (name,
        stimulus_field, base_persona, etc.) and ``stimulus_value``
        is the current stimulus string.
        """
        self._prompt_builder = fn

    def register_parse_fn(self, fn: ParseFn) -> None:
        """Register the response parser callback.

        The function signature must be::

            def parser(raw_output: str) -> dict

        returning a dict with keys matching ``expected_response_field``
        in the test specs.
        """
        self._parse_fn = fn

    def load_from_dict(self, data: Dict[str, Any]) -> None:
        """Load tests from an already-parsed config dict.

        Supports keys ``directional_tests`` and ``swap_tests``.
        """
        for td in data.get("directional_tests", []):
            self.add_test(DirectionalTest.from_dict(td))
        for st in data.get("swap_tests", []):
            self.add_swap_test(SwapTest.from_dict(st))

    def load_from_yaml(self, path: Union[str, Path]) -> None:
        """Load tests from a YAML file.

        Supports top-level or nested under ``calibration``.
        """
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML loading: pip install pyyaml"
            )
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if isinstance(data, dict) and "calibration" in data:
            data = data["calibration"]
        self.load_from_dict(data)

    # -------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------

    def run_all(
        self,
        invoke_fn: InvokeFn,
        replicates: int = 10,
        alpha: Optional[float] = None,
    ) -> DirectionalReport:
        """Run all registered tests and return a report.

        Parameters
        ----------
        invoke_fn : callable
            ``(prompt: str) -> (raw_output: str, success: bool)``
        replicates : int
            Number of LLM calls per condition.
        alpha : float, optional
            Override significance level (default: instance alpha).

        Returns
        -------
        DirectionalReport
        """
        if self._prompt_builder is None:
            raise RuntimeError(
                "No prompt_builder registered. Call "
                "register_prompt_builder() first."
            )
        if self._parse_fn is None:
            raise RuntimeError(
                "No parse_fn registered. Call register_parse_fn() first."
            )

        if alpha is None:
            alpha = self._alpha

        results: List[DirectionalTestResult] = []

        # Run directional tests
        for test in self._directional_tests:
            result = self._run_directional(
                test, invoke_fn, replicates, alpha
            )
            results.append(result)

        # Run swap tests
        for test in self._swap_tests:
            result = self._run_swap(test, invoke_fn, replicates, alpha)
            results.append(result)

        n_passed = sum(1 for r in results if r.passed)
        n_tests = len(results)

        return DirectionalReport(
            results=results,
            n_tests=n_tests,
            n_passed=n_passed,
            pass_rate=n_passed / n_tests if n_tests > 0 else 0.0,
        )

    # -------------------------------------------------------------------
    # Internal — directional test execution
    # -------------------------------------------------------------------

    def _run_directional(
        self,
        test: DirectionalTest,
        invoke_fn: InvokeFn,
        replicates: int,
        alpha: float,
    ) -> DirectionalTestResult:
        """Run a single directional test."""
        context = {
            "test_name": test.name,
            "stimulus_field": test.stimulus_field,
            "construct": test.construct,
            "description": test.description,
        }

        low_responses = self._collect_responses(
            context, test.stimulus_values["low"],
            test.expected_response_field, invoke_fn, replicates,
        )
        high_responses = self._collect_responses(
            context, test.stimulus_values["high"],
            test.expected_response_field, invoke_fn, replicates,
        )

        low_dist = dict(Counter(low_responses))
        high_dist = dict(Counter(high_responses))

        logger.info(
            "DirectionalTest '%s': low=%s, high=%s",
            test.name, low_dist, high_dist,
        )

        # Choose statistical test based on ordinal_map
        if test.ordinal_map:
            result = self._evaluate_ordinal(
                test, low_responses, high_responses,
                low_dist, high_dist, alpha,
            )
        else:
            result = self._evaluate_categorical(
                test, low_dist, high_dist, alpha,
            )

        return result

    def _collect_responses(
        self,
        context: Dict[str, Any],
        stimulus_value: str,
        response_field: str,
        invoke_fn: InvokeFn,
        replicates: int,
    ) -> List[str]:
        """Collect LLM responses for one stimulus condition."""
        responses = []
        for _ in range(replicates):
            prompt = self._prompt_builder(context, stimulus_value)
            raw, ok = invoke_fn(prompt)
            if ok and raw:
                parsed = self._parse_fn(raw)
                value = parsed.get(response_field, "")
                if value:
                    responses.append(str(value).upper())
        return responses

    def _evaluate_ordinal(
        self,
        test: DirectionalTest,
        low_responses: List[str],
        high_responses: List[str],
        low_dist: Dict[str, int],
        high_dist: Dict[str, int],
        alpha: float,
    ) -> DirectionalTestResult:
        """Evaluate using Mann-Whitney U for ordinal responses."""
        omap = test.ordinal_map
        # Convert to numeric, defaulting to median of map if unknown
        default_val = float(np.median(list(omap.values()))) if omap else 0
        low_vals = [float(omap.get(r, default_val)) for r in low_responses]
        high_vals = [float(omap.get(r, default_val)) for r in high_responses]

        mwu = mann_whitney_u(low_vals, high_vals)

        # Check direction
        direction_correct = (
            (test.expected_direction == "increase" and mwu["direction"] == "increase")
            or (test.expected_direction == "decrease" and mwu["direction"] == "decrease")
        )
        passed = mwu["p_value"] < alpha and direction_correct

        return DirectionalTestResult(
            test_name=test.name,
            passed=passed,
            p_value=mwu["p_value"],
            effect_size=abs(mwu["effect_size"]),
            direction_observed=mwu["direction"],
            direction_expected=test.expected_direction,
            low_distribution=low_dist,
            high_distribution=high_dist,
            test_type="directional",
            statistic_name="mann_whitney_u",
            statistic_value=mwu["u_statistic"],
        )

    def _evaluate_categorical(
        self,
        test: DirectionalTest,
        low_dist: Dict[str, int],
        high_dist: Dict[str, int],
        alpha: float,
    ) -> DirectionalTestResult:
        """Evaluate using chi-squared for categorical responses."""
        chi2_result = chi_squared_test(low_dist, high_dist)
        passed = chi2_result["p_value"] < alpha

        return DirectionalTestResult(
            test_name=test.name,
            passed=passed,
            p_value=chi2_result["p_value"],
            effect_size=chi2_result["cramers_v"],
            direction_observed="different" if passed else "none",
            direction_expected=test.expected_direction,
            low_distribution=low_dist,
            high_distribution=high_dist,
            test_type="directional",
            statistic_name="chi_squared",
            statistic_value=chi2_result["chi2"],
        )

    # -------------------------------------------------------------------
    # Internal — swap test execution
    # -------------------------------------------------------------------

    def _run_swap(
        self,
        test: SwapTest,
        invoke_fn: InvokeFn,
        replicates: int,
        alpha: float,
    ) -> DirectionalTestResult:
        """Run a single swap test."""
        # Base context
        base_context = {
            "test_name": test.name,
            "stimulus_field": "persona",
            "description": test.description,
            "base_persona": test.base_persona,
        }

        # Build base and swap stimulus descriptions
        base_stimulus = json.dumps(test.base_persona, default=str)
        swap_persona = {**test.base_persona, **test.swap_fields}
        swap_stimulus = json.dumps(swap_persona, default=str)

        # Collect responses for both conditions
        # For swap tests, we check all response fields
        base_raw = self._collect_all_responses(
            base_context, base_stimulus, invoke_fn, replicates,
        )
        swap_raw = self._collect_all_responses(
            base_context, swap_stimulus, invoke_fn, replicates,
        )

        # Compare the most common response field — use "decision" if available
        base_decisions = [r.get("decision", r.get("DECISION", "")) for r in base_raw]
        swap_decisions = [r.get("decision", r.get("DECISION", "")) for r in swap_raw]
        base_dist = dict(Counter(d for d in base_decisions if d))
        swap_dist = dict(Counter(d for d in swap_decisions if d))

        chi2_result = chi_squared_test(base_dist, swap_dist)
        significant = chi2_result["p_value"] < alpha

        if test.expected_effect == "significant_change":
            passed = significant
        else:
            passed = not significant

        return DirectionalTestResult(
            test_name=test.name,
            passed=passed,
            p_value=chi2_result["p_value"],
            effect_size=chi2_result["cramers_v"],
            direction_observed="changed" if significant else "unchanged",
            direction_expected=test.expected_effect,
            low_distribution=base_dist,
            high_distribution=swap_dist,
            test_type="swap",
            statistic_name="chi_squared",
            statistic_value=chi2_result["chi2"],
        )

    def _collect_all_responses(
        self,
        context: Dict[str, Any],
        stimulus_value: str,
        invoke_fn: InvokeFn,
        replicates: int,
    ) -> List[Dict[str, str]]:
        """Collect all parsed response dicts for one stimulus condition."""
        responses = []
        for _ in range(replicates):
            prompt = self._prompt_builder(context, stimulus_value)
            raw, ok = invoke_fn(prompt)
            if ok and raw:
                parsed = self._parse_fn(raw)
                if parsed:
                    responses.append(parsed)
        return responses
