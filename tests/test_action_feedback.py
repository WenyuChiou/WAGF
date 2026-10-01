"""Tests for the universal action→outcome feedback mechanism.

Covers:
- ExecutionResult.action_context field
- build_action_outcome_feedback() in irrigation domain
- _apply_state_changes() stores _last_action_context on agent
"""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from broker.interfaces.skill_types import ExecutionResult
from examples.irrigation_abm.irrigation_personas import (
    build_action_outcome_feedback,
)


# ── ExecutionResult tests ─────────────────────────────────────────────

class TestExecutionResultActionContext:
    """Verify action_context field on ExecutionResult."""

    def test_default_empty(self):
        r = ExecutionResult(success=True)
        assert r.action_context == {}

    def test_set_action_context(self):
        r = ExecutionResult(
            success=True,
            action_context={"skill_name": "increase_demand", "magnitude_pct": 15},
        )
        assert r.action_context["skill_name"] == "increase_demand"
        assert r.action_context["magnitude_pct"] == 15

    def test_to_dict_includes_action_context(self):
        r = ExecutionResult(
            success=True,
            action_context={"skill_name": "decrease_demand"},
        )
        d = r.to_dict()
        assert "action_context" in d
        assert d["action_context"]["skill_name"] == "decrease_demand"

    def test_to_dict_omits_empty_action_context(self):
        r = ExecutionResult(success=True)
        d = r.to_dict()
        assert "action_context" not in d

    def test_backward_compat_no_action_context(self):
        """Existing code that doesn't pass action_context should still work."""
        r = ExecutionResult(success=True, state_changes={"elevated": True})
        assert r.success is True
        assert r.state_changes == {"elevated": True}
        assert r.action_context == {}


# ── build_action_outcome_feedback tests ───────────────────────────────

class TestBuildActionOutcomeFeedback:
    """Test irrigation combined action + outcome feedback."""

    def test_with_action_and_magnitude(self):
        ctx = {"skill_name": "increase_demand", "magnitude_pct": 15}
        result = build_action_outcome_feedback(
            action_ctx=ctx, year=3,
            request=120_000, diversion=100_000,
            preceding_factor=0,
        )
        assert "You chose to increase demand (by 15%)" in result
        assert "120,000 acre-ft" in result
        assert "100,000 acre-ft" in result
        assert "Shortfall: 20,000" in result

    def test_with_action_no_magnitude(self):
        ctx = {"skill_name": "adopt_efficiency"}
        result = build_action_outcome_feedback(
            action_ctx=ctx, year=5,
            request=80_000, diversion=80_000,
            preceding_factor=1,
        )
        assert "You chose to adopt efficiency" in result
        assert "by" not in result.split("efficiency")[1].split(".")[0]  # no "(by X%)"
        assert "Demand fully met." in result

    def test_with_action_zero_magnitude(self):
        ctx = {"skill_name": "decrease_demand", "magnitude_pct": 0}
        result = build_action_outcome_feedback(
            action_ctx=ctx, year=2,
            request=90_000, diversion=90_000,
            preceding_factor=1,
        )
        # magnitude_pct=0 is not None, so it should appear
        assert "(by 0%)" in result

    def test_fallback_no_action_ctx(self):
        """Year 1 has no action context — should produce outcome-only."""
        result = build_action_outcome_feedback(
            action_ctx=None, year=1,
            request=100_000, diversion=95_000,
            preceding_factor=0,
        )
        assert result.startswith("Year 1:")
        assert "You chose" not in result
        assert "100,000 acre-ft" in result

    def test_fallback_empty_action_ctx(self):
        result = build_action_outcome_feedback(
            action_ctx={}, year=2,
            request=50_000, diversion=50_000,
            preceding_factor=1,
        )
        assert "You chose" not in result
        assert "Demand fully met." in result

    def test_maintain_demand_no_magnitude(self):
        ctx = {"skill_name": "maintain_demand"}
        result = build_action_outcome_feedback(
            action_ctx=ctx, year=4,
            request=70_000, diversion=70_000,
            preceding_factor=1,
        )
        assert "You chose to maintain demand" in result
        assert "Demand fully met." in result

    def test_basin_selects_precipitation_vs_lake_mead_wording(self):
        """F15 (2026-09-25 audit): Lower Basin agents get the Lake Mead
        trend, not a precipitation claim (preceding_factor there is the
        Mead rising/declining flag, not a precipitation signal)."""
        ctx = {"skill_name": "maintain_demand"}
        upper = build_action_outcome_feedback(
            action_ctx=ctx, year=1,
            request=80_000, diversion=80_000,
            preceding_factor=1, basin="upper_basin",
        )
        lower = build_action_outcome_feedback(
            action_ctx=ctx, year=1,
            request=80_000, diversion=80_000,
            preceding_factor=1, basin="lower_basin",
        )
        # WP4 (spec 4.5): the agent's own sub-basin precipitation, and Lake
        # Mead on 1 January against a year earlier.
        assert "That winter's precipitation in your sub-basin was above the previous winter's." in upper
        assert "On 1 January that year Lake Mead was higher than a year earlier." in lower
        assert "precipitation" not in lower.lower()
        assert "Lake Mead" not in upper

    def test_basin_defaults_to_upper_basin_wording(self):
        """Callers that predate the F15 basin parameter get the Upper Basin
        wording (WP4, spec 4.5)."""
        result = build_action_outcome_feedback(
            action_ctx=None, year=1,
            request=100_000, diversion=95_000,
            preceding_factor=0,
        )
        assert "That winter's precipitation in your sub-basin was below the previous winter's." in result
        assert "Drought index" not in result
