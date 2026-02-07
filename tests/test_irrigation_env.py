"""
Tests for the Irrigation Environment and Governance Validators.
"""

import numpy as np
import pytest

from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.validators.irrigation_validators import (
    water_right_cap_check,
    non_negative_diversion_check,
    curtailment_awareness_check,
    drought_severity_check,
    compact_allocation_check,
    magnitude_cap_check,
    supply_gap_block_increase,
    minimum_utilisation_check,
    demand_floor_stabilizer,
    consecutive_increase_cap_check,
    zero_escape_check,
    reset_consecutive_tracker,
    update_consecutive_tracker,
    irrigation_governance_validator,
    IRRIGATION_PHYSICAL_CHECKS,
    ALL_IRRIGATION_CHECKS,
)
import examples.irrigation_abm.validators.irrigation_validators as irr_validators


class TestWaterSystemConfig:
    """Test configuration defaults."""

    def test_default_allocations(self):
        c = WaterSystemConfig()
        assert c.upper_basin_allocation == 7_500_000
        assert c.lower_basin_allocation == 7_500_000
        assert c.mexico_allocation == 1_500_000

    def test_simulation_timeline(self):
        c = WaterSystemConfig()
        assert c.sim_start_year == 2019
        assert c.sim_end_year == 2060

    def test_shortage_tiers_descending(self):
        c = WaterSystemConfig()
        assert c.mead_normal > c.mead_shortage_tier1
        assert c.mead_shortage_tier1 > c.mead_shortage_tier2
        assert c.mead_shortage_tier2 > c.mead_shortage_tier3


class TestIrrigationEnvironment:
    """Test environment lifecycle and water signal generation."""

    @pytest.fixture
    def env(self):
        config = WaterSystemConfig(seed=42)
        env = IrrigationEnvironment(config)
        env.initialize_synthetic(n_agents=5, basin_split=(2, 3))
        return env

    def test_initial_year(self, env):
        assert env.current_year == 2019

    def test_agent_count(self, env):
        assert len(env.agent_ids) == 5

    def test_advance_year_increments(self, env):
        env.advance_year()
        assert env.current_year == 2020

    def test_advance_year_returns_global_state(self, env):
        state = env.advance_year()
        assert "year" in state
        assert "drought_index" in state
        assert "total_available_water" in state

    def test_drought_index_bounded(self, env):
        for _ in range(50):
            env.advance_year()
            di = env.global_state["drought_index"]
            assert 0.0 <= di <= 1.0

    def test_preceding_factors_binary(self, env):
        env.advance_year()
        for basin_name, basin in env.local_states.items():
            pf = basin.get("preceding_factor", -1)
            assert pf in (0, 1), f"Preceding factor must be 0 or 1, got {pf}"

    def test_get_agent_context(self, env):
        env.advance_year()
        aid = env.agent_ids[0]
        ctx = env.get_agent_context(aid)
        assert "agent_id" in ctx
        assert "basin" in ctx
        assert "current_diversion" in ctx
        assert "drought_index" in ctx
        assert "preceding_factor" in ctx

    def test_update_agent_request(self, env):
        env.advance_year()
        aid = env.agent_ids[0]
        env.update_agent_request(aid, 50_000)
        state = env.get_agent_state(aid)
        assert state["request"] == 50_000

    def test_request_capped_at_water_right(self, env):
        env.advance_year()
        aid = env.agent_ids[0]
        wr = env.get_agent_state(aid)["water_right"]
        env.update_agent_request(aid, wr * 2)
        assert env.get_agent_state(aid)["request"] <= wr

    def test_request_cannot_go_negative(self, env):
        env.advance_year()
        aid = env.agent_ids[0]
        env.update_agent_request(aid, -5000)
        assert env.get_agent_state(aid)["request"] == 0

    def test_curtailment_applies(self, env):
        """Force shortage conditions and verify curtailment."""
        # Manually set low lake level to trigger shortage
        env._basins["lower_basin"]["lake_mead_level"] = 1020
        env._apply_curtailment()

        for aid in env.agent_ids:
            state = env.get_agent_state(aid)
            if state.get("basin") == "lower_basin" or True:
                assert state["curtailment_ratio"] > 0

    def test_shortage_tier_computation(self, env):
        env._basins["lower_basin"]["lake_mead_level"] = 1100
        assert env._compute_shortage_tier() == 0

        env._basins["lower_basin"]["lake_mead_level"] = 1060
        assert env._compute_shortage_tier() == 1

        env._basins["lower_basin"]["lake_mead_level"] = 1030
        assert env._compute_shortage_tier() == 2

        env._basins["lower_basin"]["lake_mead_level"] = 1000
        assert env._compute_shortage_tier() == 3

    def test_get_observable_global(self, env):
        env.advance_year()
        year = env.get_observable("global.year")
        assert isinstance(year, int)

    def test_get_observable_local(self, env):
        env.advance_year()
        level = env.get_observable("local.lower_basin.lake_mead_level")
        assert isinstance(level, float)

    def test_get_observable_missing(self, env):
        result = env.get_observable("nonexistent.path", default="fallback")
        assert result == "fallback"

    def test_to_dict(self, env):
        d = env.to_dict()
        assert "global" in d
        assert "basins" in d
        assert "institutions" in d
        assert "n_agents" in d

    def test_institutions_compact(self, env):
        inst = env.institutions
        assert "colorado_compact" in inst
        compact = inst["colorado_compact"]
        assert compact["upper_allocation"] == 7_500_000
        assert compact["lower_allocation"] == 7_500_000

    def test_maintain_demand_preserves_request_under_curtailment(self, env):
        """maintain_demand should keep request unchanged even when curtailment
        reduces diversion.  Previously used diversion as the new request
        (double-curtailment bug)."""
        from types import SimpleNamespace
        env.advance_year()
        aid = env.agent_ids[0]
        agent = env._agents[aid]
        wr = agent["water_right"]
        # Set request to 80% of water right and apply 10% curtailment
        target_request = wr * 0.80
        env.update_agent_request(aid, target_request)
        agent["curtailment_ratio"] = 0.10
        agent["diversion"] = target_request * 0.90  # curtailed diversion

        skill = SimpleNamespace(
            skill_name="maintain_demand",
            agent_id=aid,
            parameters={},
        )
        result = env.execute_skill(skill)
        assert result.success
        # Request must stay at target_request, NOT drop to diversion
        assert abs(agent["request"] - target_request) < 1.0
        assert abs(result.state_changes["request"] - target_request) < 1.0


class TestIrrigationValidators:
    """Test irrigation governance validators."""

    def _make_context(self, **overrides):
        base = {
            "at_allocation_cap": False,
            "current_diversion": 80_000,
            "current_request": 100_000,
            "water_right": 100_000,
            "curtailment_ratio": 0.0,
            "shortage_tier": 0,
            "has_efficient_system": False,
            "drought_index": 0.3,
            "basin": "lower_basin",
            "total_basin_demand": 5_000_000,
            "basin_allocation": 7_500_000,
        }
        base.update(overrides)
        return base

    def test_water_right_cap_allows_normal(self):
        results = water_right_cap_check("increase_demand", [], self._make_context())
        assert len(results) == 0

    def test_water_right_cap_blocks_at_cap(self):
        ctx = self._make_context(at_allocation_cap=True)
        results = water_right_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_water_right_cap_ignores_other_skills(self):
        ctx = self._make_context(at_allocation_cap=True)
        results = water_right_cap_check("decrease_demand", [], ctx)
        assert len(results) == 0

    def test_non_negative_allows_positive(self):
        results = non_negative_diversion_check("decrease_demand", [], self._make_context())
        assert len(results) == 0

    def test_non_negative_warns_curtailment_zero(self):
        """Diversion=0 but request>0 (curtailment-caused) → WARNING, not ERROR."""
        ctx = self._make_context(current_diversion=0, current_request=100_000)
        results = non_negative_diversion_check("decrease_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert len(results[0].warnings) == 1

    def test_non_negative_blocks_truly_zero(self):
        """Diversion=0 AND request=0 → still ERROR."""
        ctx = self._make_context(current_diversion=0, current_request=0)
        results = non_negative_diversion_check("decrease_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_curtailment_blocks_tier2_increase(self):
        """P4: Tier 2+ shortage triggers hard BLOCK on increase_demand."""
        ctx = self._make_context(curtailment_ratio=0.10, shortage_tier=2)
        results = curtailment_awareness_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid  # P4: Tier 2+ → BLOCK
        assert len(results[0].errors) == 1

    def test_curtailment_warns_tier1_increase(self):
        """Tier 0-1 remains WARNING only (original behaviour)."""
        ctx = self._make_context(curtailment_ratio=0.05, shortage_tier=1)
        results = curtailment_awareness_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # Tier 1 → WARNING
        assert len(results[0].warnings) == 1

    def test_curtailment_silent_when_none(self):
        results = curtailment_awareness_check("increase_demand", [], self._make_context())
        assert len(results) == 0

    def test_drought_blocks_increase_at_severe(self):
        ctx = self._make_context(drought_index=0.9)
        results = drought_severity_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_drought_allows_increase_at_normal(self):
        ctx = self._make_context(drought_index=0.3)
        results = drought_severity_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_compact_warns_on_overshoot(self):
        ctx = self._make_context(
            total_basin_demand=8_000_000,
            basin_allocation=7_500_000,
        )
        results = compact_allocation_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # Warning only

    def test_compact_silent_when_within(self):
        results = compact_allocation_check("increase_demand", [], self._make_context())
        assert len(results) == 0

    def test_magnitude_cap_allows_aggressive_within(self):
        ctx = self._make_context(proposed_magnitude=18, cluster="aggressive")
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_magnitude_cap_warns_forward_looking(self):
        """v12: magnitude_cap is WARNING (not ERROR) since execute_skill uses Gaussian."""
        ctx = self._make_context(
            proposed_magnitude=25,
            cluster="forward_looking_conservative",
        )
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert len(results[0].warnings) == 1

    def test_magnitude_cap_warns_myopic(self):
        """v12: magnitude_cap is WARNING (not ERROR) since execute_skill uses Gaussian."""
        ctx = self._make_context(proposed_magnitude=12, cluster="myopic_conservative")
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert len(results[0].warnings) == 1

    def test_supply_gap_blocks_low_fulfilment(self):
        """P3: Block increase when fulfilment < 70%."""
        ctx = self._make_context(current_request=100_000, current_diversion=50_000)
        results = supply_gap_block_increase("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_supply_gap_allows_high_fulfilment(self):
        """P3: Allow increase when fulfilment >= 70%."""
        ctx = self._make_context(current_request=100_000, current_diversion=80_000)
        results = supply_gap_block_increase("increase_demand", [], ctx)
        assert len(results) == 0

    def test_supply_gap_allows_zero_baseline(self):
        """P3: Allow increase from zero baseline (Y1 new agent)."""
        ctx = self._make_context(current_request=0, current_diversion=0)
        results = supply_gap_block_increase("increase_demand", [], ctx)
        assert len(results) == 0

    def test_supply_gap_blocks_zero_delivery(self):
        """P3: Block increase when request > 0 but delivery = 0."""
        ctx = self._make_context(current_request=100_000, current_diversion=0)
        results = supply_gap_block_increase("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_supply_gap_skips_tier2(self):
        """P3: Skip when Tier 2+ (P4 handles it)."""
        ctx = self._make_context(
            current_request=100_000, current_diversion=30_000, shortage_tier=2
        )
        results = supply_gap_block_increase("increase_demand", [], ctx)
        assert len(results) == 0  # Deferred to P4

    def test_aggregated_check_list_length(self):
        assert len(IRRIGATION_PHYSICAL_CHECKS) == 7  # removed efficiency_already_adopted
        assert len(ALL_IRRIGATION_CHECKS) == 11  # 7 physical + 2 social + 1 temporal + 1 behavioral

    def test_all_checks_callable(self):
        for check in ALL_IRRIGATION_CHECKS:
            assert callable(check)


# =====================================================================
# Domain dispatch via validate_all(domain=...)
# =====================================================================

class TestDomainDispatch:
    """Verify validate_all() correctly dispatches domain-specific checks."""

    def _make_rules(self):
        """Return empty rule list (builtin checks don't need YAML rules)."""
        return []

    def test_irrigation_domain_blocks_at_cap(self):
        """domain='irrigation' activates water_right_cap_check."""
        from broker.validators.governance import validate_all
        ctx = {
            "at_allocation_cap": True,
            "water_right": 100_000,
        }
        results = validate_all("increase_demand", self._make_rules(), ctx, domain="irrigation")
        errors = [r for r in results if not r.valid]
        assert len(errors) >= 1
        assert any("water right" in e.errors[0].lower() for e in errors)

    def test_irrigation_domain_blocks_severe_drought(self):
        """domain='irrigation' activates drought_severity_check."""
        from broker.validators.governance import validate_all
        ctx = {"drought_index": 0.95}
        results = validate_all("increase_demand", self._make_rules(), ctx, domain="irrigation")
        errors = [r for r in results if not r.valid]
        assert len(errors) >= 1
        assert any("drought" in e.errors[0].lower() for e in errors)

    def test_irrigation_domain_no_flood_checks(self):
        """domain='irrigation' does NOT trigger flood-specific checks."""
        from broker.validators.governance import validate_all
        ctx = {"state": {"elevated": True}}
        results = validate_all("elevate_house", self._make_rules(), ctx, domain="irrigation")
        # Flood check would block "elevate_house" when state.elevated=True
        errors = [r for r in results if not r.valid]
        assert len(errors) == 0

    def test_flood_domain_no_irrigation_checks(self):
        """domain='flood' does NOT trigger irrigation-specific checks."""
        from broker.validators.governance import validate_all
        ctx = {"at_allocation_cap": True, "drought_index": 0.95}
        results = validate_all("increase_demand", self._make_rules(), ctx, domain="flood")
        # Irrigation checks would block; flood checks don't know about irrigation skills
        irrigation_errors = [
            r for r in results if not r.valid
            and r.metadata.get("rule_id", "").startswith(("water_right", "drought"))
        ]
        assert len(irrigation_errors) == 0

    def test_none_domain_no_builtin_checks(self):
        """domain=None triggers YAML rules only — no builtin checks at all."""
        from broker.validators.governance import validate_all
        ctx = {
            "at_allocation_cap": True,
            "drought_index": 0.95,
            "state": {"elevated": True},
        }
        # Without YAML rules, nothing should fire
        results = validate_all("increase_demand", self._make_rules(), ctx, domain=None)
        assert len(results) == 0

    def test_irrigation_compact_warning_fires(self):
        """domain='irrigation' activates compact_allocation_check (social)."""
        from broker.validators.governance import validate_all
        ctx = {
            "total_basin_demand": 8_000_000,
            "basin_allocation": 7_500_000,
        }
        results = validate_all("increase_demand", self._make_rules(), ctx, domain="irrigation")
        warnings = [r for r in results if r.valid and r.warnings]
        assert len(warnings) >= 1
        assert any("compact" in w.warnings[0].lower() for w in warnings)

    def test_irrigation_curtailment_blocks_tier2(self):
        """P4: domain='irrigation' blocks increase_demand at Tier 2+ shortage."""
        from broker.validators.governance import validate_all
        ctx = {
            "curtailment_ratio": 0.15,
            "shortage_tier": 2,
        }
        results = validate_all("increase_demand", self._make_rules(), ctx, domain="irrigation")
        errors = [r for r in results if not r.valid and r.errors]
        assert len(errors) >= 1
        assert any("curtailment" in e.errors[0].lower() or "conservation" in e.errors[0].lower()
                    for e in errors)

    def test_irrigation_curtailment_warns_tier1(self):
        """Tier 1 shortage remains WARNING via domain dispatch."""
        from broker.validators.governance import validate_all
        ctx = {
            "curtailment_ratio": 0.05,
            "shortage_tier": 1,
        }
        results = validate_all("increase_demand", self._make_rules(), ctx, domain="irrigation")
        warnings = [r for r in results if r.valid and r.warnings]
        assert len(warnings) >= 1
        assert any("curtailment" in w.warnings[0].lower() for w in warnings)


# =====================================================================
# Custom validator adapter for SkillBrokerEngine
# =====================================================================

class TestIrrigationGovernanceAdapter:
    """Test the irrigation_governance_validator adapter function."""

    def test_adapter_blocks_at_allocation_cap(self):
        """Adapter should block increase_demand at allocation cap."""
        from types import SimpleNamespace
        proposal = SimpleNamespace(skill_name="increase_demand")
        ctx = {"at_allocation_cap": True, "water_right": 100_000}
        results = irrigation_governance_validator(proposal, ctx)
        errors = [r for r in results if not r.valid]
        assert len(errors) >= 1

    def test_adapter_passes_normal_conditions(self):
        """Adapter should return no errors under normal conditions."""
        from types import SimpleNamespace
        proposal = SimpleNamespace(skill_name="maintain_demand")
        ctx = {"drought_index": 0.3, "curtailment_ratio": 0}
        results = irrigation_governance_validator(proposal, ctx)
        errors = [r for r in results if not r.valid]
        assert len(errors) == 0

    def test_adapter_returns_list(self):
        """Adapter must return a list (SkillBrokerEngine contract)."""
        from types import SimpleNamespace
        proposal = SimpleNamespace(skill_name="decrease_demand")
        results = irrigation_governance_validator(proposal, {})
        assert isinstance(results, list)


# =====================================================================
# Stage 1: Demand Floor Stabilizer Tests
# =====================================================================

class TestDemandFloorStabilizer:
    """Test the demand_floor_stabilizer validator (50% floor)."""

    def _make_context(self, **overrides):
        base = {
            "water_right": 100_000,
            "current_request": 50_000,
        }
        base.update(overrides)
        return base

    def test_blocks_decrease_below_50pct(self):
        """Utilisation 45% + decrease → ERROR."""
        ctx = self._make_context(current_request=45_000)
        results = demand_floor_stabilizer("decrease_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert results[0].metadata["rule_id"] == "demand_floor_stabilizer"

    def test_allows_decrease_above_50pct(self):
        """Utilisation 60% + decrease → pass."""
        ctx = self._make_context(current_request=60_000)
        results = demand_floor_stabilizer("decrease_demand", [], ctx)
        assert len(results) == 0

    def test_allows_decrease_at_exactly_50pct(self):
        """Utilisation exactly 50% → pass (boundary)."""
        ctx = self._make_context(current_request=50_000)
        results = demand_floor_stabilizer("decrease_demand", [], ctx)
        assert len(results) == 0

    def test_ignores_non_decrease(self):
        """Utilisation 30% + maintain → pass (only checks decrease)."""
        ctx = self._make_context(current_request=30_000)
        results = demand_floor_stabilizer("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_ignores_increase(self):
        """Utilisation 30% + increase → pass."""
        ctx = self._make_context(current_request=30_000)
        results = demand_floor_stabilizer("increase_demand", [], ctx)
        assert len(results) == 0


# =====================================================================
# Stage 1: Minimum Utilisation Check Tests
# =====================================================================

class TestMinimumUtilisationCheck:
    """Test the minimum_utilisation_check validator (10% hard floor)."""

    def _make_context(self, **overrides):
        base = {
            "below_minimum_utilisation": False,
            "water_right": 100_000,
            "request": 50_000,
        }
        base.update(overrides)
        return base

    def test_blocks_decrease_below_10pct(self):
        """below_minimum=True + decrease → ERROR."""
        ctx = self._make_context(below_minimum_utilisation=True, request=8_000)
        results = minimum_utilisation_check("decrease_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert "economic hallucination" in results[0].errors[0].lower()

    def test_allows_decrease_above_floor(self):
        """below_minimum=False + decrease → pass."""
        ctx = self._make_context(below_minimum_utilisation=False)
        results = minimum_utilisation_check("decrease_demand", [], ctx)
        assert len(results) == 0

    def test_allows_maintain_below_floor(self):
        """below_minimum=True + maintain → pass (only checks decrease)."""
        ctx = self._make_context(below_minimum_utilisation=True, request=8_000)
        results = minimum_utilisation_check("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_allows_increase_below_floor(self):
        """below_minimum=True + increase → pass."""
        ctx = self._make_context(below_minimum_utilisation=True, request=8_000)
        results = minimum_utilisation_check("increase_demand", [], ctx)
        assert len(results) == 0


# =====================================================================
# Stage 1: Consecutive Increase Cap Tests
# =====================================================================

class TestConsecutiveIncreaseCap:
    """Test the consecutive_increase_cap_check validator (Phase C)."""

    def _make_context(self, **overrides):
        base = {
            "agent_id": "test_agent",
            "drought_index": 0.5,
        }
        base.update(overrides)
        return base

    def setup_method(self):
        """Reset state before each test."""
        reset_consecutive_tracker()
        # Save original flag
        self._orig_flag = irr_validators.ENABLE_CONSECUTIVE_CAP

    def teardown_method(self):
        """Restore flag after each test."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = self._orig_flag
        reset_consecutive_tracker()

    def test_blocks_4th_consecutive_increase(self):
        """3 consecutive increases + drought>=0.3 → 4th blocked."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        # Simulate 3 prior increases
        for _ in range(3):
            update_consecutive_tracker("test_agent", "increase_demand")
        ctx = self._make_context(drought_index=0.5)
        results = consecutive_increase_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert results[0].metadata["rule_id"] == "consecutive_increase_cap"

    def test_allows_3rd_increase(self):
        """Only 2 prior increases → 3rd allowed."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        for _ in range(2):
            update_consecutive_tracker("test_agent", "increase_demand")
        ctx = self._make_context(drought_index=0.5)
        results = consecutive_increase_cap_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_allows_wet_period_exemption(self):
        """3+ increases but drought<0.3 → pass (wet period exemption)."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        for _ in range(4):
            update_consecutive_tracker("test_agent", "increase_demand")
        ctx = self._make_context(drought_index=0.1)
        results = consecutive_increase_cap_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_resets_on_non_increase(self):
        """Decrease resets counter → next increase allowed."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        for _ in range(3):
            update_consecutive_tracker("test_agent", "increase_demand")
        # Interrupt with a decrease
        update_consecutive_tracker("test_agent", "decrease_demand")
        ctx = self._make_context(drought_index=0.5)
        results = consecutive_increase_cap_check("increase_demand", [], ctx)
        assert len(results) == 0  # Counter reset to 0

    def test_disabled_without_flag(self):
        """ENABLE_CONSECUTIVE_CAP=False → skip entirely."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = False
        for _ in range(5):
            update_consecutive_tracker("test_agent", "increase_demand")
        ctx = self._make_context(drought_index=0.9)
        results = consecutive_increase_cap_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_ignores_non_increase_skill(self):
        """decrease_demand → skip (only checks increase)."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        for _ in range(5):
            update_consecutive_tracker("test_agent", "increase_demand")
        results = consecutive_increase_cap_check("decrease_demand", [], self._make_context())
        assert len(results) == 0


# =====================================================================
# Stage 1: Zero Escape Check Tests
# =====================================================================

class TestZeroEscapeCheck:
    """Test the zero_escape_check validator (Phase D)."""

    def _make_context(self, **overrides):
        base = {
            "current_request": 50_000,
            "water_right": 100_000,
        }
        base.update(overrides)
        return base

    def setup_method(self):
        self._orig_flag = irr_validators.ENABLE_ZERO_ESCAPE

    def teardown_method(self):
        irr_validators.ENABLE_ZERO_ESCAPE = self._orig_flag

    def test_blocks_maintain_at_zero_util(self):
        """Utilisation <15% + maintain → ERROR."""
        irr_validators.ENABLE_ZERO_ESCAPE = True
        ctx = self._make_context(current_request=10_000)  # 10% < 15%
        results = zero_escape_check("maintain_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert results[0].metadata["rule_id"] == "zero_escape_floor"

    def test_allows_maintain_normal_util(self):
        """Utilisation 50% + maintain → pass."""
        irr_validators.ENABLE_ZERO_ESCAPE = True
        ctx = self._make_context(current_request=50_000)
        results = zero_escape_check("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_allows_maintain_at_boundary(self):
        """Utilisation exactly 15% → pass (boundary)."""
        irr_validators.ENABLE_ZERO_ESCAPE = True
        ctx = self._make_context(current_request=15_000)
        results = zero_escape_check("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_disabled_without_flag(self):
        """ENABLE_ZERO_ESCAPE=False → skip."""
        irr_validators.ENABLE_ZERO_ESCAPE = False
        ctx = self._make_context(current_request=5_000)  # 5% < 15%
        results = zero_escape_check("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_ignores_increase(self):
        """increase_demand → skip."""
        irr_validators.ENABLE_ZERO_ESCAPE = True
        ctx = self._make_context(current_request=5_000)
        results = zero_escape_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_ignores_decrease(self):
        """decrease_demand → skip."""
        irr_validators.ENABLE_ZERO_ESCAPE = True
        ctx = self._make_context(current_request=5_000)
        results = zero_escape_check("decrease_demand", [], ctx)
        assert len(results) == 0


# =====================================================================
# Stage 1: Cold-Start Grace Period Tests
# =====================================================================

class TestColdStartGracePeriod:
    """Test Y1-3 Tier 2 cold-start grace period in curtailment_awareness_check."""

    def _make_context(self, **overrides):
        base = {
            "curtailment_ratio": 0.10,
            "shortage_tier": 2,
            "loop_year": 1,
        }
        base.update(overrides)
        return base

    def test_tier2_y1_grace_period(self):
        """Year 1 + Tier 2 + increase → WARNING (grace period)."""
        ctx = self._make_context(loop_year=1)
        results = curtailment_awareness_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert results[0].metadata.get("cold_start_grace") is True

    def test_tier2_y3_grace_period(self):
        """Year 3 + Tier 2 → still grace period."""
        ctx = self._make_context(loop_year=3)
        results = curtailment_awareness_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING

    def test_tier2_y4_blocks(self):
        """Year 4 + Tier 2 → no grace, ERROR."""
        ctx = self._make_context(loop_year=4)
        results = curtailment_awareness_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid  # ERROR

    def test_tier3_y1_no_grace(self):
        """Year 1 + Tier 3 → no grace (Tier 3 never exempted)."""
        ctx = self._make_context(shortage_tier=3, curtailment_ratio=0.20, loop_year=1)
        results = curtailment_awareness_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid  # ERROR even in Y1


# =====================================================================
# Stage 1: Validator Interaction (Double-Bind Prevention) Tests
# =====================================================================

class TestValidatorInteraction:
    """Test that no validator combination creates all-skills-blocked traps."""

    def _run_all_checks(self, skill_name, context):
        """Run all 11 validators on a skill and return blocking errors."""
        results = []
        for check in ALL_IRRIGATION_CHECKS:
            results.extend(check(skill_name, [], context))
        return [r for r in results if not r.valid]

    def test_low_util_decrease_blocked_but_others_open(self):
        """Utilisation 8% → decrease blocked, but increase+maintain open."""
        ctx = {
            "below_minimum_utilisation": True,
            "water_right": 100_000,
            "request": 8_000,
            "current_request": 8_000,
            "current_diversion": 8_000,
            "at_allocation_cap": False,
            "curtailment_ratio": 0.0,
            "shortage_tier": 0,
            "drought_index": 0.3,
        }
        decrease_errors = self._run_all_checks("decrease_demand", ctx)
        assert len(decrease_errors) >= 1  # blocked by minimum_utilisation + demand_floor

        increase_errors = self._run_all_checks("increase_demand", ctx)
        assert len(increase_errors) == 0  # open

        maintain_errors = self._run_all_checks("maintain_demand", ctx)
        assert len(maintain_errors) == 0  # open

    def test_at_cap_drought_increase_blocked_but_others_open(self):
        """At cap + severe drought → increase blocked, decrease+maintain open."""
        ctx = {
            "at_allocation_cap": True,
            "water_right": 100_000,
            "request": 100_000,
            "current_request": 100_000,
            "current_diversion": 80_000,
            "below_minimum_utilisation": False,
            "curtailment_ratio": 0.0,
            "shortage_tier": 0,
            "drought_index": 0.9,
        }
        increase_errors = self._run_all_checks("increase_demand", ctx)
        assert len(increase_errors) >= 1  # blocked by water_right_cap + drought

        decrease_errors = self._run_all_checks("decrease_demand", ctx)
        assert len(decrease_errors) == 0  # open

        maintain_errors = self._run_all_checks("maintain_demand", ctx)
        assert len(maintain_errors) == 0  # open

    def test_curtailment_zero_diversion_is_warning_not_error(self):
        """Curtailment → diversion=0 but request>0 → WARNING (not ERROR)."""
        ctx = {
            "current_diversion": 0,
            "current_request": 50_000,
            "water_right": 100_000,
        }
        results = non_negative_diversion_check("decrease_demand", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, allowing agent to proceed
        assert results[0].metadata["level"] == "WARNING"
