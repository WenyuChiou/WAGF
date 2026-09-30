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
    demand_ceiling_stabilizer,
    consecutive_increase_cap_check,
    zero_escape_check,
    reset_consecutive_tracker,
    update_consecutive_tracker,
    irrigation_governance_validator,
    IRRIGATION_PHYSICAL_CHECKS,
    ALL_IRRIGATION_CHECKS,
    assert_validator_inputs_have_producers,
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
        # F12 follow-up (2026-09-25 code review): pre-loop current_year is
        # sim_start_year - 1 (2018, the initial-conditions year), not 2019
        # (loop year 1's value) -- they must differ so the first
        # advance_year() call actually re-keys _decision_rng's draw. See
        # test_advance_year_increments below and TestCalendarYearAlignment
        # for the loop-year checks.
        assert env.current_year == 2018

    def test_agent_count(self, env):
        assert len(env.agent_ids) == 5

    def test_advance_year_increments(self, env):
        # F12 (2026-09-25 audit): loop year 1 must be calendar year 2019
        # (sim_start_year), not 2020 -- see TestCalendarYearAlignment below
        # for the full 3-year and 42-year checks.
        env.advance_year()
        assert env.current_year == 2019

    def test_advance_year_returns_global_state(self, env):
        state = env.advance_year()
        assert "year" in state
        assert "drought_index" in state
        assert "total_available_water" in state

    def test_drought_index_bounded(self, env):
        # v3 (spec 1.1, 2026-09-28): natural flow (and, via it, nothing
        # here directly, but the simulation horizon it defines) comes from
        # the committed 42-row USBR hydrology table (sim years 2019-2060),
        # which raises for a year outside that range rather than falling
        # back to a synthetic extrapolation -- so this loop no longer runs
        # past the table's 42 years.
        for _ in range(42):
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
        """Force shortage conditions and verify curtailment. Supply-side
        redesign (2026-09-25, decision Q2): the declared shortage binds
        Lower Basin agents only; Upper Basin agents carry ratio 0."""
        # Manually set low lake level to trigger shortage
        env._basins["lower_basin"]["lake_mead_level"] = 1020
        env._apply_curtailment()

        for aid in env.agent_ids:
            state = env.get_agent_state(aid)
            if state.get("basin") == "lower_basin":
                assert state["curtailment_ratio"] > 0
            else:
                assert state["curtailment_ratio"] == 0.0

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


class TestCalendarYearAlignment:
    """F12 (2026-09-25 audit): loop year 1 must be calendar year 2019 and
    loop year 42 must be 2060, so every loop year lands inside the CRSS
    PRISM CSV's real 2017-2060 coverage instead of the last year of every
    42-year run silently using synthetic precipitation."""

    def test_three_year_mock_run_logs_2019_2020_2021(self):
        config = WaterSystemConfig(seed=42)
        env = IrrigationEnvironment(config)
        env.initialize_synthetic(n_agents=3, basin_split=(2, 1))
        years = [env.advance_year()["year"] for _ in range(3)]
        assert years == [2019, 2020, 2021]

    def test_42_loop_years_stay_inside_real_crss_coverage_no_synthetic_fallback(self):
        """Reads the REAL CRSS PRISM CSV from the primary clone (read-only;
        not checked into this worktree; the audit's own smoke run uses
        synthetic profiles instead). Skips on any machine where that path
        is absent rather than fabricating fixture data for it."""
        import os

        primary_csv = (
            r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
            r"\ref\CRSS_DB\CRSS_DB\HistoricalData\PrismWinterPrecip_ST_NOAA_Future.csv"
        )
        if not os.path.exists(primary_csv):
            pytest.skip(f"real CRSS PRISM CSV not present at {primary_csv}")

        config = WaterSystemConfig(seed=42)
        env = IrrigationEnvironment(config)
        env.initialize_synthetic(n_agents=3, basin_split=(2, 1))
        env.load_crss_precipitation(primary_csv)

        years = [env.advance_year()["year"] for _ in range(42)]

        assert years[0] == 2019
        assert years[-1] == 2060
        assert env._precip_synthetic_fallback_years == [], (
            "all 42 loop years should land inside the real CRSS CSV's "
            "2017-2060 coverage; synthetic fallback was used for "
            f"{env._precip_synthetic_fallback_years}"
        )


# TestF11bPowellCapReapplication was retired with the supply-side
# redesign (2026-09-25): _apply_powell_constraint no longer exists. The F11b
# contract it pinned (rebuild from requests, exactly-once, even split between
# an executed and an un-executed agent) is now tested against settle_year()
# in tests/test_irrigation_supply_side.py (TestSettleIdempotence).


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
            # Re-review 2026-09-29 round 4 (LOW 2): curtailment_awareness_check
            # now direct-indexes this (no silent 0 fallback) whenever
            # curtailment_ratio > 0, which several tests below set via
            # overrides.
            "lb_shortage_volume_maf": 0.417,
        }
        base.update(overrides)
        return base

    def test_water_right_cap_allows_normal(self):
        results = water_right_cap_check("increase_large", [], self._make_context())
        assert len(results) == 0

    def test_water_right_cap_blocks_at_cap(self):
        ctx = self._make_context(at_allocation_cap=True)
        results = water_right_cap_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_water_right_cap_blocks_small_at_cap(self):
        ctx = self._make_context(at_allocation_cap=True)
        results = water_right_cap_check("increase_small", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_water_right_cap_ignores_other_skills(self):
        ctx = self._make_context(at_allocation_cap=True)
        results = water_right_cap_check("decrease_large", [], ctx)
        assert len(results) == 0

    def test_non_negative_allows_positive(self):
        results = non_negative_diversion_check("decrease_large", [], self._make_context())
        assert len(results) == 0

    def test_non_negative_warns_curtailment_zero(self):
        """Diversion=0 but request>0 (curtailment-caused) → WARNING, not ERROR."""
        ctx = self._make_context(current_diversion=0, current_request=100_000)
        results = non_negative_diversion_check("decrease_small", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert len(results[0].warnings) == 1

    def test_non_negative_blocks_truly_zero(self):
        """Diversion=0 AND request=0 → still ERROR."""
        ctx = self._make_context(current_diversion=0, current_request=0)
        results = non_negative_diversion_check("decrease_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_curtailment_blocks_tier2_increase(self):
        """P4: Tier 2+ shortage triggers hard BLOCK on all increases."""
        ctx = self._make_context(curtailment_ratio=0.10, shortage_tier=2)
        results = curtailment_awareness_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert len(results[0].errors) == 1

    def test_curtailment_blocks_tier2_increase_small(self):
        """P4: Tier 2+ blocks increase_small too."""
        ctx = self._make_context(curtailment_ratio=0.10, shortage_tier=2)
        results = curtailment_awareness_check("increase_small", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_curtailment_tier1_blocks_large(self):
        """v17: Tier 1 blocks increase_large (differential governance)."""
        ctx = self._make_context(curtailment_ratio=0.05, shortage_tier=1)
        results = curtailment_awareness_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid  # ERROR
        assert len(results[0].errors) == 1

    def test_curtailment_tier1_warns_small(self):
        """v17: Tier 1 warns increase_small (differential governance)."""
        ctx = self._make_context(curtailment_ratio=0.05, shortage_tier=1)
        results = curtailment_awareness_check("increase_small", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING
        assert len(results[0].warnings) == 1

    def test_curtailment_silent_when_none(self):
        results = curtailment_awareness_check("increase_large", [], self._make_context())
        assert len(results) == 0

    def test_drought_blocks_large_at_extreme(self):
        """Drought >= 0.85 blocks all increases."""
        ctx = self._make_context(drought_index=0.9)
        results = drought_severity_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_drought_blocks_small_at_extreme(self):
        """Drought >= 0.85 blocks increase_small too."""
        ctx = self._make_context(drought_index=0.9)
        results = drought_severity_check("increase_small", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_drought_moderate_blocks_large(self):
        """v17: Drought 0.7-0.84 blocks increase_large."""
        ctx = self._make_context(drought_index=0.75)
        results = drought_severity_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_drought_moderate_warns_small(self):
        """v17: Drought 0.7-0.84 warns increase_small."""
        ctx = self._make_context(drought_index=0.75)
        results = drought_severity_check("increase_small", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING

    def test_drought_allows_increase_at_normal(self):
        ctx = self._make_context(drought_index=0.3)
        results = drought_severity_check("increase_large", [], ctx)
        assert len(results) == 0

    def test_compact_warns_on_overshoot(self):
        ctx = self._make_context(
            total_basin_demand=8_000_000,
            basin_allocation=7_500_000,
        )
        results = compact_allocation_check("increase_large", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # Warning only

    def test_compact_silent_when_within(self):
        results = compact_allocation_check("increase_large", [], self._make_context())
        assert len(results) == 0

    def test_magnitude_cap_allows_aggressive_within(self):
        ctx = self._make_context(proposed_magnitude=18, cluster="aggressive")
        results = magnitude_cap_check("increase_large", [], ctx)
        assert len(results) == 0

    def test_magnitude_cap_warns_forward_looking(self):
        """v12: magnitude_cap is WARNING (not ERROR) since execute_skill uses Gaussian."""
        ctx = self._make_context(
            proposed_magnitude=25,
            cluster="forward_looking_conservative",
        )
        results = magnitude_cap_check("increase_large", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert len(results[0].warnings) == 1

    def test_magnitude_cap_warns_myopic(self):
        """v12: magnitude_cap is WARNING (not ERROR) since execute_skill uses Gaussian."""
        ctx = self._make_context(proposed_magnitude=12, cluster="myopic_conservative")
        results = magnitude_cap_check("increase_small", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert len(results[0].warnings) == 1

    # WP3 (2026-09-29, spec 3.3, PI item 2): the v3 supply rule blocks an
    # increase exactly when the PHYSICAL expected share at the keep request
    # (supply_physical_ratio, from supply_rule_fields) is below
    # FULL_SUPPLY_RATIO. The 0.70 cutoff, the Tier 2+ skip and the separate
    # zero-delivery branch are gone (test_v3_governance.py has the full
    # truth table and the real-environment cases).
    def _supply_context(self, *, keep, expected, phi=1.0, gap_reason=None, **overrides):
        from examples.irrigation_abm.validators.irrigation_validators import (
            supply_rule_fields,
        )
        ctx = self._make_context(current_request=keep, current_diversion=expected, **overrides)
        ctx.update(supply_rule_fields(ctx, {"lb_phys_ratio": phi}))
        ctx["gap_reason"] = gap_reason or (
            "lb_mead_availability" if ctx["supply_physical_ratio"] < 1.0 else "none")
        return ctx

    def test_supply_gap_blocks_short_physical_supply(self):
        ctx = self._supply_context(keep=100_000, expected=50_000, phi=0.5)
        results = supply_gap_block_increase("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_supply_gap_allows_full_supply(self):
        ctx = self._supply_context(keep=100_000, expected=99_900, phi=0.999)
        assert supply_gap_block_increase("increase_large", [], ctx) == []

    def test_supply_gap_allows_zero_baseline(self):
        """A zero keep request is never short (r = 1), even under phi < 1."""
        ctx = self._supply_context(keep=0, expected=0, phi=0.5)
        assert supply_gap_block_increase("increase_small", [], ctx) == []

    def test_supply_gap_blocks_zero_delivery(self):
        """No separate zero-delivery branch: r_phys = 0 < FULL_SUPPLY_RATIO."""
        ctx = self._supply_context(keep=100_000, expected=0, phi=0.0)
        results = supply_gap_block_increase("increase_large", [], ctx)
        assert len(results) == 1 and not results[0].valid

    def test_supply_gap_no_longer_skips_tier2(self):
        """The Tier 2+ skip is gone: a Lower Basin agent under a declared
        Tier 2 AND a physical shortage is blocked by the supply rule."""
        ctx = self._supply_context(keep=100_000, expected=30_000, phi=0.3,
                                   shortage_tier=2, curtailment_ratio=0.10)
        results = supply_gap_block_increase("increase_large", [], ctx)
        assert len(results) == 1 and not results[0].valid

    def test_supply_gap_ignores_a_declared_tier_alone(self):
        """A declared Tier 2 with Lake Mead physically full never blocks."""
        ctx = self._supply_context(keep=100_000, expected=100_000, phi=1.0,
                                   shortage_tier=2, curtailment_ratio=0.10)
        assert supply_gap_block_increase("increase_large", [], ctx) == []

    def test_aggregated_check_list_length(self):
        # F04 (2026-09-25 audit): drought_severity_check, compact_allocation_check
        # and magnitude_cap_check were removed from these lists: each read a
        # context key nothing in the pipeline produces (or a threshold the real
        # data never reaches) and fired zero times across 49,140 audited rows.
        # The functions are still defined and directly testable above.
        # Supply-side redesign (2026-09-25): demand_floor_stabilizer and
        # demand_ceiling_stabilizer are retired from dispatch as well.
        # WP3 (2026-09-29, spec 3.2): the supply rule is the ONLY dispatched
        # check -- the cap and the floor are YAML identity rules, and
        # curtailment_awareness / consecutive_cap / zero_escape /
        # non_negative_diversion are retired.
        assert len(IRRIGATION_PHYSICAL_CHECKS) == 1
        assert len(ALL_IRRIGATION_CHECKS) == 1

    def test_stabilizers_retired_from_dispatch(self, monkeypatch):
        """T15: neither stabilizer is dispatched, so a governed irrigation run
        can never emit either rule id, while both functions still exist."""
        assert demand_ceiling_stabilizer not in ALL_IRRIGATION_CHECKS
        assert demand_floor_stabilizer not in ALL_IRRIGATION_CHECKS
        # A context where both WOULD fire if dispatched.
        ctx = {
            "at_allocation_cap": False, "below_minimum_utilisation": False,
            "water_right": 100_000, "current_request": 20_000,
            "current_diversion": 20_000, "curtailment_ratio": 0.0,
            "shortage_tier": 0, "loop_year": 5, "agent_id": "A",
            "total_basin_demand": 9_000_000, "drought_index": 0.1,
            # WP3: the dispatched supply rule's inputs (a full supply).
            "supply_keep_request_af": 20_000, "supply_expected_at_keep_af": 20_000,
            "supply_ratio": 1.0, "supply_physical_ratio": 1.0,
            "full_supply_ratio": 0.999,
        }
        for skill in ("increase_large", "decrease_large"):
            rule_ids = {
                r.metadata.get("rule_id")
                for r in irrigation_governance_validator(type("P", (), {"skill_name": skill})(), ctx)
            }
            assert "demand_ceiling_stabilizer" not in rule_ids
            assert "demand_floor_stabilizer" not in rule_ids
        monkeypatch.setattr(irr_validators, "ENABLE_DEMAND_CEILING", True)
        assert demand_ceiling_stabilizer("increase_large", [], ctx)
        assert demand_floor_stabilizer("decrease_large", [], ctx)

    def test_all_checks_callable(self):
        for check in ALL_IRRIGATION_CHECKS:
            assert callable(check)

    def test_assert_validator_inputs_have_producers_passes_on_dispatched_set(self):
        """F04 code review (2026-09-25): the default call (checks=None ->
        ALL_IRRIGATION_CHECKS) must not raise -- this is exactly what runs
        at module import time."""
        assert_validator_inputs_have_producers()

    def test_assert_validator_inputs_have_producers_catches_dead_key(self):
        """F04 code review (2026-09-25): proves the self-check actually
        catches the F04 class of bug -- compact_allocation_check and
        magnitude_cap_check are excluded from ALL_IRRIGATION_CHECKS
        precisely because they read a key nothing produces, and this
        confirms the self-check would raise if either were re-added
        without also wiring a producer. Passing them explicitly (rather
        than relying on the default) is what the two docstrings in
        irrigation_validators.py point at."""
        with pytest.raises(RuntimeError, match="basin_allocation"):
            assert_validator_inputs_have_producers([compact_allocation_check])
        with pytest.raises(RuntimeError, match="proposed_magnitude"):
            assert_validator_inputs_have_producers([magnitude_cap_check])
        # drought_severity_check is excluded on a threshold-calibration
        # ground, not a missing-producer one: drought_index DOES have a
        # producer, so the self-check correctly does NOT flag it.
        assert_validator_inputs_have_producers([drought_severity_check])


# =====================================================================
# Domain dispatch via validate_all(domain=...)
# =====================================================================

def _supply_inputs(keep=100_000.0, physical=1.0, basin="lower_basin"):
    """WP3: the v3 supply rule's inputs (supply_rule_fields' keys) plus the
    message fields -- a full supply by default."""
    return {
        "basin": basin,
        "gap_reason": "none" if physical >= 1.0 else "lb_mead_availability",
        "supply_keep_request_af": keep, "supply_expected_at_keep_af": keep * physical,
        "supply_ratio": physical, "supply_physical_ratio": physical,
        "full_supply_ratio": 0.999,
    }


class TestDomainDispatch:
    """Verify validate_all() correctly dispatches domain-specific checks."""

    def _make_rules(self):
        """Return empty rule list (builtin checks don't need YAML rules)."""
        return []

    def test_irrigation_domain_dispatches_the_supply_rule_only(self):
        """WP3 (spec 3.2): domain='irrigation' dispatches the v3 supply rule
        alone. At the cap with a full supply nothing blocks here (the cap is
        the YAML identity rule, a menu filter); a short physical supply
        blocks an increase."""
        from broker.validators.governance import validate_all
        at_cap = {"at_allocation_cap": True, "water_right": 100_000, **_supply_inputs()}
        results = validate_all("increase_large", self._make_rules(), at_cap, domain="irrigation")
        assert [r for r in results if not r.valid] == []
        short = _supply_inputs(physical=0.5)
        results = validate_all("increase_large", self._make_rules(), short, domain="irrigation")
        errors = [r for r in results if not r.valid]
        assert [e.metadata["rule_id"] for e in errors] == ["supply_gap_block_increase"]

    def test_irrigation_domain_drought_severity_not_dispatched(self):
        """F04 (2026-09-25 audit): drought_severity_check is intentionally
        excluded from IRRIGATION_PHYSICAL_CHECKS (the real drought index
        never reaches its 0.7 threshold), so domain dispatch does NOT block
        on drought_index alone any more. The function itself still works;
        see the direct drought_severity_check calls in TestIrrigationValidators above."""
        from broker.validators.governance import validate_all
        ctx = {"drought_index": 0.95, **_supply_inputs()}
        results = validate_all("increase_large", self._make_rules(), ctx, domain="irrigation")
        errors = [
            r for r in results
            if not r.valid and r.metadata.get("rule_id") == "drought_severity"
        ]
        assert len(errors) == 0

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

    def test_irrigation_domain_compact_allocation_not_dispatched(self):
        """F04 (2026-09-25 audit): compact_allocation_check is intentionally
        excluded from IRRIGATION_SOCIAL_CHECKS (nothing in the pipeline ever
        writes basin_allocation), so domain dispatch does NOT warn on it any
        more. The function itself still works; see the direct
        compact_allocation_check calls in TestIrrigationValidators above."""
        from broker.validators.governance import validate_all
        ctx = {
            "total_basin_demand": 8_000_000,
            "basin_allocation": 7_500_000,
            **_supply_inputs(),
        }
        results = validate_all("increase_large", self._make_rules(), ctx, domain="irrigation")
        compact_warnings = [
            r for r in results
            if r.valid and r.warnings and r.metadata.get("rule_id") == "compact_allocation"
        ]
        assert len(compact_warnings) == 0

    @pytest.mark.parametrize("tier,volume", [(1, 0.333), (2, 0.417), (3, 0.5)])
    def test_irrigation_declared_tier_alone_never_blocks(self, tier, volume):
        """WP3 (spec 3.2, PI item 2): curtailment_awareness_check -- the
        declared-tier increase block, its Tier 1 differential and its grace
        years -- is no longer dispatched. A declared tier with Lake Mead
        physically full blocks nothing and warns nothing; the function
        itself is still tested directly in TestIrrigationValidators."""
        from broker.validators.governance import validate_all
        ctx = {"curtailment_ratio": 0.1, "shortage_tier": tier,
               "lb_shortage_volume_maf": volume, **_supply_inputs()}
        for skill in ("increase_large", "increase_small", "increase_demand"):
            results = validate_all(skill, self._make_rules(), ctx, domain="irrigation")
            assert [r for r in results if not r.valid or r.warnings] == []


# =====================================================================
# Custom validator adapter for SkillBrokerEngine
# =====================================================================

class TestIrrigationGovernanceAdapter:
    """Test the irrigation_governance_validator adapter function."""

    def test_adapter_blocks_increase_on_short_supply(self):
        """WP3: the adapter runs the v3 supply rule (the cap is a YAML
        identity rule now): it blocks an increase on a short physical supply
        and leaves an at-cap increase with a full supply to the menu filter."""
        from types import SimpleNamespace
        proposal = SimpleNamespace(skill_name="increase_large")
        short = _supply_inputs(physical=0.5)
        errors = [r for r in irrigation_governance_validator(proposal, short) if not r.valid]
        assert [e.metadata["rule_id"] for e in errors] == ["supply_gap_block_increase"]
        at_cap = {"at_allocation_cap": True, "water_right": 100_000, **_supply_inputs()}
        assert irrigation_governance_validator(proposal, at_cap) == []

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
        proposal = SimpleNamespace(skill_name="decrease_large")
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

    def test_blocks_decrease_large_below_50pct(self):
        """Utilisation 45% + decrease_large → ERROR."""
        ctx = self._make_context(current_request=45_000)
        results = demand_floor_stabilizer("decrease_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert results[0].metadata["rule_id"] == "demand_floor_stabilizer"

    def test_blocks_decrease_small_below_50pct(self):
        """Utilisation 45% + decrease_small → also ERROR."""
        ctx = self._make_context(current_request=45_000)
        results = demand_floor_stabilizer("decrease_small", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_allows_decrease_above_50pct(self):
        """Utilisation 60% + decrease → pass."""
        ctx = self._make_context(current_request=60_000)
        results = demand_floor_stabilizer("decrease_large", [], ctx)
        assert len(results) == 0

    def test_allows_decrease_at_exactly_50pct(self):
        """Utilisation exactly 50% → pass (boundary)."""
        ctx = self._make_context(current_request=50_000)
        results = demand_floor_stabilizer("decrease_small", [], ctx)
        assert len(results) == 0

    def test_ignores_non_decrease(self):
        """Utilisation 30% + maintain → pass (only checks decrease)."""
        ctx = self._make_context(current_request=30_000)
        results = demand_floor_stabilizer("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_ignores_increase(self):
        """Utilisation 30% + increase → pass."""
        ctx = self._make_context(current_request=30_000)
        results = demand_floor_stabilizer("increase_large", [], ctx)
        assert len(results) == 0


# =====================================================================
# Stage 1: Demand Ceiling Stabilizer Tests
# =====================================================================

class TestDemandCeilingStabilizer:
    """Test the demand_ceiling_stabilizer validator (6.0 MAF ceiling)."""

    def _make_context(self, **overrides):
        base = {
            "total_basin_demand": 5_000_000,  # 5.0 MAF (below ceiling)
        }
        base.update(overrides)
        return base

    def test_blocks_increase_large_above_ceiling(self):
        """Basin demand 7.0 MAF + increase_large -> ERROR."""
        ctx = self._make_context(total_basin_demand=7_000_000)
        results = demand_ceiling_stabilizer("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert results[0].metadata["rule_id"] == "demand_ceiling_stabilizer"

    def test_blocks_increase_small_above_ceiling(self):
        """Basin demand 7.0 MAF + increase_small -> also ERROR."""
        ctx = self._make_context(total_basin_demand=7_000_000)
        results = demand_ceiling_stabilizer("increase_small", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_allows_increase_below_ceiling(self):
        """Basin demand 5.0 MAF + increase -> pass."""
        ctx = self._make_context(total_basin_demand=5_000_000)
        results = demand_ceiling_stabilizer("increase_large", [], ctx)
        assert len(results) == 0

    def test_allows_increase_at_exactly_ceiling(self):
        """Basin demand exactly 6.0 MAF -> pass (boundary)."""
        ctx = self._make_context(total_basin_demand=6_000_000)
        results = demand_ceiling_stabilizer("increase_small", [], ctx)
        assert len(results) == 0

    def test_ignores_maintain_above_ceiling(self):
        """Basin demand 7.0 MAF + maintain -> pass (only checks increase)."""
        ctx = self._make_context(total_basin_demand=7_000_000)
        results = demand_ceiling_stabilizer("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_ignores_decrease_above_ceiling(self):
        """Basin demand 7.0 MAF + decrease -> pass."""
        ctx = self._make_context(total_basin_demand=7_000_000)
        results = demand_ceiling_stabilizer("decrease_large", [], ctx)
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
        results = minimum_utilisation_check("decrease_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert "economic hallucination" in results[0].errors[0].lower()

    def test_blocks_decrease_small_below_10pct(self):
        """below_minimum=True + decrease_small → also ERROR."""
        ctx = self._make_context(below_minimum_utilisation=True, request=8_000)
        results = minimum_utilisation_check("decrease_small", [], ctx)
        assert len(results) == 1
        assert not results[0].valid

    def test_allows_decrease_above_floor(self):
        """below_minimum=False + decrease → pass."""
        ctx = self._make_context(below_minimum_utilisation=False)
        results = minimum_utilisation_check("decrease_large", [], ctx)
        assert len(results) == 0

    def test_allows_maintain_below_floor(self):
        """below_minimum=True + maintain → pass (only checks decrease)."""
        ctx = self._make_context(below_minimum_utilisation=True, request=8_000)
        results = minimum_utilisation_check("maintain_demand", [], ctx)
        assert len(results) == 0

    def test_allows_increase_below_floor(self):
        """below_minimum=True + increase → pass."""
        ctx = self._make_context(below_minimum_utilisation=True, request=8_000)
        results = minimum_utilisation_check("increase_large", [], ctx)
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
        # Simulate 3 prior increases (mix of large and small)
        update_consecutive_tracker("test_agent", "increase_large")
        update_consecutive_tracker("test_agent", "increase_small")
        update_consecutive_tracker("test_agent", "increase_large")
        ctx = self._make_context(drought_index=0.5)
        results = consecutive_increase_cap_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid
        assert results[0].metadata["rule_id"] == "consecutive_increase_cap"

    def test_allows_3rd_increase(self):
        """Only 2 prior increases → 3rd allowed."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        update_consecutive_tracker("test_agent", "increase_large")
        update_consecutive_tracker("test_agent", "increase_small")
        ctx = self._make_context(drought_index=0.5)
        results = consecutive_increase_cap_check("increase_small", [], ctx)
        assert len(results) == 0

    def test_allows_wet_period_exemption(self):
        """3+ increases but drought<0.3 → pass (wet period exemption)."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        for _ in range(4):
            update_consecutive_tracker("test_agent", "increase_large")
        ctx = self._make_context(drought_index=0.1)
        results = consecutive_increase_cap_check("increase_large", [], ctx)
        assert len(results) == 0

    def test_resets_on_non_increase(self):
        """Decrease resets counter → next increase allowed."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        for _ in range(3):
            update_consecutive_tracker("test_agent", "increase_large")
        # Interrupt with a decrease
        update_consecutive_tracker("test_agent", "decrease_small")
        ctx = self._make_context(drought_index=0.5)
        results = consecutive_increase_cap_check("increase_large", [], ctx)
        assert len(results) == 0  # Counter reset to 0

    def test_disabled_without_flag(self):
        """ENABLE_CONSECUTIVE_CAP=False → skip entirely."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = False
        for _ in range(5):
            update_consecutive_tracker("test_agent", "increase_large")
        ctx = self._make_context(drought_index=0.9)
        results = consecutive_increase_cap_check("increase_large", [], ctx)
        assert len(results) == 0

    def test_ignores_non_increase_skill(self):
        """decrease_large → skip (only checks increase)."""
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        for _ in range(5):
            update_consecutive_tracker("test_agent", "increase_large")
        results = consecutive_increase_cap_check("decrease_large", [], self._make_context())
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
        """increase_large → skip."""
        irr_validators.ENABLE_ZERO_ESCAPE = True
        ctx = self._make_context(current_request=5_000)
        results = zero_escape_check("increase_large", [], ctx)
        assert len(results) == 0

    def test_ignores_decrease(self):
        """decrease_large → skip."""
        irr_validators.ENABLE_ZERO_ESCAPE = True
        ctx = self._make_context(current_request=5_000)
        results = zero_escape_check("decrease_large", [], ctx)
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
            # Re-review 2026-09-29 round 4 (LOW 2): no silent 0 fallback
            # any more in curtailment_awareness_check.
            "lb_shortage_volume_maf": 0.417,
        }
        base.update(overrides)
        return base

    def test_tier2_y1_grace_period(self):
        """Year 1 + Tier 2 + increase → WARNING (grace period)."""
        ctx = self._make_context(loop_year=1)
        results = curtailment_awareness_check("increase_large", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, not ERROR
        assert results[0].metadata.get("cold_start_grace") is True

    def test_tier2_y3_grace_period(self):
        """Year 3 + Tier 2 → still grace period."""
        ctx = self._make_context(loop_year=3)
        results = curtailment_awareness_check("increase_large", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING

    def test_tier2_y4_blocks(self):
        """Year 4 + Tier 2 → no grace, ERROR."""
        ctx = self._make_context(loop_year=4)
        results = curtailment_awareness_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid  # ERROR

    def test_tier3_y1_no_grace(self):
        """Year 1 + Tier 3 → no grace (Tier 3 never exempted)."""
        ctx = self._make_context(shortage_tier=3, curtailment_ratio=0.20, loop_year=1)
        results = curtailment_awareness_check("increase_large", [], ctx)
        assert len(results) == 1
        assert not results[0].valid  # ERROR even in Y1


# =====================================================================
# Stage 1: Validator Interaction (Double-Bind Prevention) Tests
# =====================================================================

class TestValidatorInteraction:
    """Test that no validator combination creates all-skills-blocked traps."""

    def _run_all_checks(self, skill_name, context):
        """Run the dispatched validators on a skill and return blocking errors."""
        results = []
        for check in ALL_IRRIGATION_CHECKS:
            results.extend(check(skill_name, [], context))
        return [r for r in results if not r.valid]

    def test_low_util_decrease_left_to_the_floor_identity_rule(self):
        """WP3 (spec 3.2): at 8% utilisation the dispatched checks block
        nothing -- the minimum-use floor is the YAML identity rule, which
        hides the decrease option in every profile -- and keep stays open."""
        ctx = {
            "below_minimum_utilisation": True, "water_right": 100_000,
            "request": 8_000, "current_request": 8_000, "current_diversion": 8_000,
            "at_allocation_cap": False, "curtailment_ratio": 0.0,
            "shortage_tier": 0, "drought_index": 0.3, **_supply_inputs(keep=8_000),
        }
        for skill in ("decrease_large", "increase_large", "maintain_demand"):
            assert self._run_all_checks(skill, ctx) == []

    def test_short_supply_blocks_only_an_increase(self):
        """At the cap with a short physical supply: the supply rule blocks an
        increase; decrease and keep stay open (no all-blocked trap)."""
        ctx = {
            "at_allocation_cap": True, "water_right": 100_000,
            "request": 100_000, "current_request": 100_000, "current_diversion": 80_000,
            "below_minimum_utilisation": False, "curtailment_ratio": 0.0,
            "shortage_tier": 0, "drought_index": 0.9,
            **_supply_inputs(keep=100_000, physical=0.8),
        }
        increase_errors = self._run_all_checks("increase_large", ctx)
        assert [e.metadata["rule_id"] for e in increase_errors] == ["supply_gap_block_increase"]
        assert self._run_all_checks("decrease_large", ctx) == []
        assert self._run_all_checks("maintain_demand", ctx) == []

    def test_curtailment_zero_diversion_is_warning_not_error(self):
        """Curtailment → diversion=0 but request>0 → WARNING (not ERROR)."""
        ctx = {
            "current_diversion": 0,
            "current_request": 50_000,
            "water_right": 100_000,
        }
        results = non_negative_diversion_check("decrease_large", [], ctx)
        assert len(results) == 1
        assert results[0].valid  # WARNING, allowing agent to proceed
        assert results[0].metadata["level"] == "WARNING"


# =====================================================================
# v17: Five-Skill Execution Tests
# =====================================================================

class TestFiveSkillExecution:
    """Test execute_skill with all 5 skill names and per-skill Gaussian params."""

    @pytest.fixture
    def env(self):
        config = WaterSystemConfig(seed=42)
        env = IrrigationEnvironment(config)
        env.initialize_synthetic(n_agents=3, basin_split=(1, 2))
        return env

    def _make_skill(self, skill_name, agent_id):
        from types import SimpleNamespace
        return SimpleNamespace(
            skill_name=skill_name,
            agent_id=agent_id,
            parameters={},
        )

    def test_increase_large_above_median_step(self, env):
        """increase_large draws a Hung and Yang step above the agent's
        median step T (2026-09-26 action model)."""
        from examples.irrigation_abm.irrigation_env import hy_threshold_af
        env.advance_year()
        aid = env.agent_ids[0]
        a = env._agents[aid]
        old = a["request"]
        result = env.execute_skill(self._make_skill("increase_large", aid))
        assert result.success
        assert result.state_changes["magnitude_class"] == "large"
        step = result.state_changes["request"] - old
        capped = result.state_changes["request"] == a["water_right"]
        assert capped or step > hy_threshold_af(a["mu"], a["sigma"], a["bin_size_af"])

    def test_increase_small_at_or_below_median_step(self, env):
        from examples.irrigation_abm.irrigation_env import hy_threshold_af
        env.advance_year()
        aid = env.agent_ids[0]
        a = env._agents[aid]
        old = a["request"]
        result = env.execute_skill(self._make_skill("increase_small", aid))
        assert result.success
        assert result.state_changes["magnitude_class"] == "small"
        assert result.state_changes["request"] - old <= hy_threshold_af(
            a["mu"], a["sigma"], a["bin_size_af"]) + 1e-9

    def test_decrease_large_reduces_request(self, env):
        """decrease_large should reduce request."""
        env.advance_year()
        aid = env.agent_ids[0]
        old_req = env.get_agent_state(aid)["request"]
        skill = self._make_skill("decrease_large", aid)
        result = env.execute_skill(skill)
        assert result.success
        new_req = result.state_changes["request"]
        assert new_req <= old_req

    def test_decrease_small_reduces_request(self, env):
        """decrease_small should reduce request."""
        env.advance_year()
        aid = env.agent_ids[0]
        old_req = env.get_agent_state(aid)["request"]
        skill = self._make_skill("decrease_small", aid)
        result = env.execute_skill(skill)
        assert result.success
        new_req = result.state_changes["request"]
        assert new_req <= old_req

    def test_maintain_demand_preserves_request(self, env):
        """maintain_demand should keep request unchanged."""
        env.advance_year()
        aid = env.agent_ids[0]
        old_req = env.get_agent_state(aid)["request"]
        skill = self._make_skill("maintain_demand", aid)
        result = env.execute_skill(skill)
        assert result.success
        assert abs(result.state_changes["request"] - old_req) < 1.0

    def test_unknown_skill_fails(self, env):
        """Unknown skill name should return failure."""
        env.advance_year()
        aid = env.agent_ids[0]
        skill = self._make_skill("teleport_water", aid)
        result = env.execute_skill(skill)
        assert not result.success

    def test_synthetic_agents_carry_hy_action_parameters(self, env):
        """Synthetic agents carry the Hung and Yang fallback parameters
        (CSV medians, bin = water_right / 25); persona_scale and
        skill_magnitude are gone."""
        from examples.irrigation_abm.irrigation_env import (
            SYNTHETIC_BIN_DIVISOR, SYNTHETIC_HY_MU, SYNTHETIC_HY_SIGMA)
        for aid in env.agent_ids:
            agent = env._agents[aid]
            assert agent["mu"] == SYNTHETIC_HY_MU
            assert agent["sigma"] == SYNTHETIC_HY_SIGMA
            assert agent["bin_size_af"] == pytest.approx(agent["water_right"] / SYNTHETIC_BIN_DIVISOR)
            for gone in ("persona_scale", "skill_magnitude", "magnitude_default",
                         "magnitude_sigma", "magnitude_min", "magnitude_max", "exploration_rate"):
                assert gone not in agent
