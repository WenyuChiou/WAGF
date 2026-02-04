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
    efficiency_already_adopted_check,
    drought_severity_check,
    compact_allocation_check,
    magnitude_cap_check,
    supply_gap_block_increase,
    irrigation_governance_validator,
    IRRIGATION_PHYSICAL_CHECKS,
    ALL_IRRIGATION_CHECKS,
)


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

    def test_non_negative_blocks_zero(self):
        ctx = self._make_context(current_diversion=0)
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

    def test_efficiency_blocks_already_adopted(self):
        ctx = self._make_context(has_efficient_system=True)
        results = efficiency_already_adopted_check("adopt_efficiency", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_efficiency_allows_new_adoption(self):
        results = efficiency_already_adopted_check("adopt_efficiency", [], self._make_context())
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
        ctx = self._make_context(proposed_magnitude=25, cluster="aggressive")
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 0

    def test_magnitude_cap_blocks_forward_looking(self):
        ctx = self._make_context(
            proposed_magnitude=25,
            cluster="forward_looking_conservative",
        )
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_magnitude_cap_blocks_myopic(self):
        ctx = self._make_context(proposed_magnitude=12, cluster="myopic_conservative")
        results = magnitude_cap_check("increase_demand", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

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
        assert len(IRRIGATION_PHYSICAL_CHECKS) == 7  # P3 added supply_gap
        assert len(ALL_IRRIGATION_CHECKS) == 9

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
