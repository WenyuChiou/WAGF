"""
Tests for FQL baseline runner and skill mapper.

Verifies:
1. fql_action_to_skill mapping correctness (2-action model)
2. WSA/ACA label computation
3. Validator fallback logic
4. Smoke test: 5 agents × 5 years produces valid output
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.learning.fql_skill_mapper import (
    fql_action_to_skill,
    compute_wsa_label,
    compute_aca_label,
)
from examples.irrigation_abm.run_fql_baseline import (
    create_fql_agents,
    validate_skill,
    _create_synthetic_profiles,
    run_simulation,
    FQL_SKILLS,
)
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)


# ── fql_action_to_skill tests ──

class TestFQLActionToSkill:
    """Test the FQL action → 2-action mapping (Hung & Yang 2021)."""

    def test_positive_is_increase(self):
        """Any positive action → increase_demand."""
        assert fql_action_to_skill(1.0) == "increase_demand"
        assert fql_action_to_skill(100) == "increase_demand"
        assert fql_action_to_skill(50000) == "increase_demand"
        assert fql_action_to_skill(0.001) == "increase_demand"

    def test_negative_is_decrease(self):
        """Any negative action → decrease_demand."""
        assert fql_action_to_skill(-1.0) == "decrease_demand"
        assert fql_action_to_skill(-100) == "decrease_demand"
        assert fql_action_to_skill(-50000) == "decrease_demand"
        assert fql_action_to_skill(-0.001) == "decrease_demand"

    def test_exact_zero_is_maintain(self):
        """Only action == 0.0 exactly → maintain_demand (degenerate case)."""
        assert fql_action_to_skill(0.0) == "maintain_demand"

    def test_no_large_small_distinction(self):
        """FQL has no large/small — all positive → increase_demand."""
        # These would have been increase_small vs increase_large in 5-skill
        assert fql_action_to_skill(100) == "increase_demand"    # 0.1% of 100k
        assert fql_action_to_skill(50000) == "increase_demand"  # 50% of 100k
        assert fql_action_to_skill(-100) == "decrease_demand"
        assert fql_action_to_skill(-50000) == "decrease_demand"


# ── WSA/ACA label tests ──

class TestLabels:
    """Test WSA and ACA label computation."""

    def test_wsa_labels(self):
        assert compute_wsa_label(0.0) == "VL"
        assert compute_wsa_label(0.1) == "VL"
        assert compute_wsa_label(0.3) == "L"
        assert compute_wsa_label(0.5) == "M"
        assert compute_wsa_label(0.7) == "H"
        assert compute_wsa_label(0.9) == "VH"

    def test_aca_labels(self):
        assert compute_aca_label("aggressive") == "H"
        assert compute_aca_label("forward_looking_conservative") == "M"
        assert compute_aca_label("myopic_conservative") == "L"
        assert compute_aca_label("unknown") == "M"  # default


# ── Validator fallback tests ──

class TestValidatorFallback:
    """Test validate_skill fallback logic."""

    def test_valid_skill_passes(self):
        """A valid skill in normal conditions passes through."""
        ctx = {
            "agent_id": "test",
            "at_allocation_cap": False,
            "has_efficient_system": False,
            "below_minimum_utilisation": False,
            "water_right": 100_000,
            "current_diversion": 50_000,
            "current_request": 50_000,
            "curtailment_ratio": 0,
            "shortage_tier": 0,
            "drought_index": 0.3,
            "cluster": "aggressive",
            "basin": "lower_basin",
            "total_basin_demand": 5_000_000,
            "loop_year": 5,
        }
        valid, skill = validate_skill("maintain_demand", ctx)
        assert valid
        assert skill == "maintain_demand"

    def test_increase_blocked_at_cap(self):
        """Increase at allocation cap → fallback to maintain_demand."""
        ctx = {
            "agent_id": "test",
            "at_allocation_cap": True,
            "has_efficient_system": False,
            "below_minimum_utilisation": False,
            "water_right": 100_000,
            "current_diversion": 99_000,
            "current_request": 100_000,
            "curtailment_ratio": 0,
            "shortage_tier": 0,
            "drought_index": 0.3,
            "cluster": "aggressive",
            "basin": "lower_basin",
            "total_basin_demand": 5_000_000,
            "loop_year": 5,
        }
        valid, skill = validate_skill("increase_demand", ctx)
        assert valid
        assert skill != "increase_demand"

    def test_decrease_blocked_at_floor(self):
        """Decrease at minimum utilisation → fallback."""
        ctx = {
            "agent_id": "test",
            "at_allocation_cap": False,
            "has_efficient_system": False,
            "below_minimum_utilisation": True,
            "water_right": 100_000,
            "current_diversion": 5_000,
            "current_request": 5_000,
            "curtailment_ratio": 0,
            "shortage_tier": 0,
            "drought_index": 0.3,
            "cluster": "myopic_conservative",
            "basin": "lower_basin",
            "total_basin_demand": 5_000_000,
            "loop_year": 5,
        }
        valid, skill = validate_skill("decrease_demand", ctx)
        assert valid
        assert skill != "decrease_demand"


# ── FQL agent creation tests ──

class TestFQLAgentCreation:
    """Test create_fql_agents from profiles."""

    def test_creates_agents(self):
        profiles = _create_synthetic_profiles(5, seed=42)
        agents = create_fql_agents(profiles, seed=42)
        assert len(agents) == 5
        for aid, (agent, state) in agents.items():
            assert state.q_table is not None
            assert state.prev_diversion > 0


# ── Smoke test ──

class TestSmokeRun:
    """Smoke test: 5 agents × 5 years."""

    def test_smoke_run(self):
        """Full pipeline: profiles → env → FQL agents → simulate → CSV."""
        seed = 42
        np.random.seed(seed)

        profiles = _create_synthetic_profiles(5, seed=seed)

        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)

        fql_agents = create_fql_agents(profiles, seed=seed)
        profiles_dict = {p.agent_id: p for p in profiles}

        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            logs = run_simulation(
                env=env,
                fql_agents=fql_agents,
                profiles=profiles_dict,
                n_years=5,
                output_dir=output_dir,
                seed=seed,
            )

        # Basic checks
        assert len(logs) == 25  # 5 agents × 5 years
        assert all(log["yearly_decision"] in FQL_SKILLS for log in logs
                   if log["yearly_decision"] is not None)

        # Check columns match expected
        expected_cols = {
            "agent_id", "year", "cluster", "basin", "yearly_decision",
            "request", "diversion", "water_right", "drought_index",
            "shortage_tier", "lake_mead_level", "utilisation_pct",
        }
        actual_cols = set(logs[0].keys())
        assert expected_cols.issubset(actual_cols), f"Missing columns: {expected_cols - actual_cols}"

        # Mead level should be plausible
        final_mead = logs[-1]["lake_mead_level"]
        assert 800 < final_mead < 1300, f"Mead level {final_mead} out of plausible range"

        # All agents should have positive water_right
        for log in logs:
            assert log["water_right"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
