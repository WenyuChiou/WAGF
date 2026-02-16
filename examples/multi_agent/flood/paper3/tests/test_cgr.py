"""Tests for Construct Grounding Rate (CGR) module."""

import sys
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
ANALYSIS_DIR = SCRIPT_DIR.parent / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import pytest
from validation.metrics.cgr import (
    ground_tp_from_state,
    ground_cp_from_state,
    compute_cgr,
    _is_adjacent,
    _cohens_kappa,
    _weighted_kappa,
)


# =============================================================================
# TP Grounding Tests
# =============================================================================

class TestGroundTP:
    def test_high_zone_flooded_now(self):
        state = {"flood_zone": "HIGH", "flooded_this_year": True, "flood_count": 1}
        assert ground_tp_from_state(state) == "VH"

    def test_high_zone_past_floods(self):
        state = {"flood_zone": "HIGH", "flooded_this_year": False, "flood_count": 2}
        assert ground_tp_from_state(state) == "H"

    def test_moderate_zone_recent_flood(self):
        state = {"flood_zone": "MODERATE", "flooded_this_year": True, "flood_count": 1}
        assert ground_tp_from_state(state) == "H"

    def test_moderate_zone_within_2yr(self):
        state = {"flood_zone": "MODERATE", "years_since_flood": 1, "flood_count": 1}
        assert ground_tp_from_state(state) == "H"

    def test_moderate_zone_no_recent(self):
        state = {"flood_zone": "MODERATE", "flood_count": 0}
        assert ground_tp_from_state(state) == "M"

    def test_low_zone_some_history(self):
        state = {"flood_zone": "LOW", "flood_count": 1}
        assert ground_tp_from_state(state) == "L"

    def test_low_zone_no_history(self):
        state = {"flood_zone": "LOW", "flood_count": 0}
        assert ground_tp_from_state(state) == "VL"

    def test_missing_fields_defaults(self):
        assert ground_tp_from_state({}) == "VL"  # LOW zone, 0 flood_count


# =============================================================================
# CP Grounding Tests
# =============================================================================

class TestGroundCP:
    def test_nmg_high_income(self):
        state = {"mg": False, "income": 80000}
        assert ground_cp_from_state(state) == "VH"

    def test_nmg_medium_income(self):
        state = {"mg": False, "income": 55000}
        assert ground_cp_from_state(state) == "H"

    def test_nmg_lower_income(self):
        state = {"mg": False, "income": 42000}
        assert ground_cp_from_state(state) == "M"

    def test_mg_moderate_income(self):
        state = {"mg": True, "income": 45000}
        assert ground_cp_from_state(state) == "L"

    def test_mg_very_low_income(self):
        state = {"mg": True, "income": 25000}
        assert ground_cp_from_state(state) == "VL"

    def test_elevated_nmg(self):
        state = {"mg": False, "income": 40000, "elevated": True}
        assert ground_cp_from_state(state) == "VH"


# =============================================================================
# Adjacency Tests
# =============================================================================

class TestAdjacency:
    def test_exact_match(self):
        assert _is_adjacent("H", "H") is True

    def test_one_level_apart(self):
        assert _is_adjacent("H", "VH") is True
        assert _is_adjacent("M", "H") is True

    def test_two_levels_apart(self):
        assert _is_adjacent("VL", "M") is False
        assert _is_adjacent("VH", "M") is False

    def test_unknown_level(self):
        assert _is_adjacent("UNKNOWN", "M") is False


# =============================================================================
# CGR Computation Tests
# =============================================================================

class TestComputeCGR:
    def _make_trace(self, tp_llm, cp_llm, state_before):
        return {
            "skill_proposal": {
                "reasoning": {"TP_LABEL": tp_llm, "CP_LABEL": cp_llm},
                "skill_name": "do_nothing",
            },
            "state_before": state_before,
        }

    def test_perfect_agreement(self):
        traces = [
            self._make_trace("VH", "VL", {"flood_zone": "HIGH", "flooded_this_year": True, "flood_count": 1, "mg": True, "income": 25000}),
            self._make_trace("VL", "VH", {"flood_zone": "LOW", "flood_count": 0, "mg": False, "income": 80000}),
        ]
        result = compute_cgr(traces)
        assert result["cgr_tp_exact"] == 1.0
        assert result["cgr_cp_exact"] == 1.0
        assert result["n_grounded"] == 2
        assert result["n_skipped"] == 0

    def test_no_agreement(self):
        traces = [
            self._make_trace("VL", "VH", {"flood_zone": "HIGH", "flooded_this_year": True, "flood_count": 1, "mg": True, "income": 25000}),
        ]
        result = compute_cgr(traces)
        assert result["cgr_tp_exact"] == 0.0
        assert result["cgr_cp_exact"] == 0.0

    def test_adjacent_agreement(self):
        # Grounded TP=H, LLM TP=VH → adjacent
        traces = [
            self._make_trace("VH", "L", {"flood_zone": "HIGH", "flood_count": 1, "mg": True, "income": 45000}),
        ]
        result = compute_cgr(traces)
        assert result["cgr_tp_adjacent"] == 1.0  # H vs VH = adjacent

    def test_missing_state_before(self):
        traces = [
            {"skill_proposal": {"reasoning": {"TP_LABEL": "H", "CP_LABEL": "M"}}, "state_before": {}},
        ]
        result = compute_cgr(traces)
        # Empty state_before → skipped
        assert result["n_skipped"] == 1
        assert result["n_grounded"] == 0

    def test_unknown_llm_labels_skipped(self):
        traces = [
            {
                "skill_proposal": {"reasoning": {"TP_LABEL": "UNKNOWN", "CP_LABEL": "M"}},
                "state_before": {"flood_zone": "HIGH", "flood_count": 1, "mg": False, "income": 60000},
            },
        ]
        result = compute_cgr(traces)
        assert result["n_skipped"] == 1

    def test_empty_traces(self):
        result = compute_cgr([])
        assert result["cgr_tp_exact"] == 0.0
        assert result["n_grounded"] == 0

    def test_kappa_output(self):
        traces = [
            self._make_trace("VH", "VL", {"flood_zone": "HIGH", "flooded_this_year": True, "flood_count": 1, "mg": True, "income": 25000}),
            self._make_trace("VL", "VH", {"flood_zone": "LOW", "flood_count": 0, "mg": False, "income": 80000}),
        ]
        result = compute_cgr(traces)
        # With perfect agreement, kappa should be positive
        assert result["kappa_tp"] > 0
        assert result["kappa_cp"] > 0

    def test_confusion_keys_are_strings(self):
        """Confusion matrix keys must be JSON-serializable strings."""
        traces = [
            self._make_trace("VH", "VL", {"flood_zone": "HIGH", "flooded_this_year": True, "flood_count": 1, "mg": True, "income": 25000}),
        ]
        result = compute_cgr(traces)
        for key in result["tp_confusion"]:
            assert isinstance(key, str)
        for key in result["cp_confusion"]:
            assert isinstance(key, str)


# =============================================================================
# Cohen's Kappa Tests
# =============================================================================

class TestCohensKappa:
    def test_perfect_agreement(self):
        confusion = {("H", "H"): 50, ("L", "L"): 50}
        labels = ["VL", "L", "M", "H", "VH"]
        kappa = _cohens_kappa(confusion, labels)
        assert kappa == 1.0

    def test_no_agreement(self):
        # All off-diagonal
        confusion = {("H", "L"): 50, ("L", "H"): 50}
        labels = ["VL", "L", "M", "H", "VH"]
        kappa = _cohens_kappa(confusion, labels)
        assert kappa < 0  # Worse than chance

    def test_empty(self):
        kappa = _cohens_kappa({}, ["H", "L"])
        assert kappa == 0.0


# =============================================================================
# Weighted Kappa Tests (Ordinal)
# =============================================================================

class TestWeightedKappa:
    LABELS = ["VL", "L", "M", "H", "VH"]

    def test_perfect_agreement(self):
        confusion = {("H", "H"): 50, ("L", "L"): 50}
        kw = _weighted_kappa(confusion, self.LABELS)
        assert kw == 1.0

    def test_empty(self):
        assert _weighted_kappa({}, self.LABELS) == 0.0

    def test_adjacent_disagreement_penalized_less(self):
        """Adjacent errors (H→VH) should yield higher kappa than distant (H→VL)."""
        # Spread across categories; some adjacent errors
        adjacent = {("H", "H"): 40, ("L", "L"): 40, ("H", "VH"): 10, ("L", "M"): 10}
        # Same base; distant errors instead
        distant = {("H", "H"): 40, ("L", "L"): 40, ("H", "VL"): 10, ("L", "VH"): 10}
        kw_adj = _weighted_kappa(adjacent, self.LABELS)
        kw_dist = _weighted_kappa(distant, self.LABELS)
        assert kw_adj > kw_dist

    def test_weighted_ge_unweighted_for_adjacent(self):
        """Weighted kappa >= unweighted when errors are adjacent (ordinal advantage)."""
        # Mix of exact + adjacent disagreements
        confusion = {("H", "H"): 40, ("H", "VH"): 10, ("L", "L"): 40, ("L", "M"): 10}
        kw = _weighted_kappa(confusion, self.LABELS)
        ku = _cohens_kappa(confusion, self.LABELS)
        assert kw >= ku

    def test_quadratic_weights(self):
        """Quadratic weights penalize distant errors even more."""
        distant = {("VH", "VL"): 50, ("M", "M"): 50}
        kw_linear = _weighted_kappa(distant, self.LABELS, weight_type="linear")
        kw_quad = _weighted_kappa(distant, self.LABELS, weight_type="quadratic")
        # Quadratic penalizes VH→VL more, so kappa is lower
        assert kw_quad <= kw_linear

    def test_single_label_returns_one(self):
        assert _weighted_kappa({("M", "M"): 100}, ["M"]) == 1.0

    def test_cgr_output_has_both_kappas(self):
        """compute_cgr() now outputs both weighted and unweighted kappa."""
        traces = [{
            "skill_proposal": {
                "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "VL"},
                "skill_name": "do_nothing",
            },
            "state_before": {
                "flood_zone": "HIGH", "flooded_this_year": True,
                "flood_count": 1, "mg": True, "income": 25000,
            },
        }]
        result = compute_cgr(traces)
        assert "kappa_tp" in result
        assert "kappa_tp_unweighted" in result
        assert "kappa_cp" in result
        assert "kappa_cp_unweighted" in result
