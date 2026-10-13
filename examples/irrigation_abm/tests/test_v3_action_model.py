"""Irrigation case study v3, Work Package 2 (Action model and options).

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md (WP2, section
"Work packages, in implementation order" -> "WP2 Action model and
options"). Companion: irrigation_v3_design_record_2026-09-29.md ("Action
model (spec 2.1 to 2.6)"); irrigation_v3_design_provenance_2026-09-28.md
(rows B1-B10).

Every test here fails on the pre-WP2 code (HEAD af4b9378, WP1 + WP1b only):
``IrrigationEnvironment._reset_requests_to_base`` does not exist,
``IrrigationAgentProfile.demand_per_grid_unit`` / ``step_bin_af`` /
``step_bin_source`` do not exist, ``irrigation_personas.build_option_texts``
does not exist, and the registry/config still carry the five-skill
increase_large/increase_small/maintain_demand/decrease_small/decrease_large
menu instead of the three-skill increase_demand/maintain_demand/
decrease_demand one.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from examples.irrigation_abm.irrigation_env import (
    MIN_UTIL,
    IrrigationEnvironment,
    WaterSystemConfig,
    hy_threshold_af,
)
from examples.irrigation_abm.irrigation_personas import (
    build_option_texts,
    create_profiles_from_data,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CRSS_PARAMS_CSV = REPO_ROOT / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
CRSS_DB_DIR = REPO_ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()
_real_ref = pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not present")

AGENT_TYPES_YAML = REPO_ROOT / "examples" / "irrigation_abm" / "config" / "agent_types.yaml"
SKILL_REGISTRY_YAML = REPO_ROOT / "examples" / "irrigation_abm" / "config" / "skill_registry.yaml"

# The full agent id "NIIP" (spec 2.4/2.6 shorthand) resolves to in the 58
# expanded Upper Basin slots (Group_Agt/UB_ABM_Groups_and_Agents.csv).
NIIP = "NavajoIndianIrrigationProjectNIIPandExports_NIIP"

# spec 2.4 acceptance: exactly these 8 agents' step bin is rescaled to 10
# percent of 2018 use (bin_size_af, already UB-converted, exceeds 20
# percent of that use).
EXPECTED_RESCALED_AGENTS = frozenset({
    "ArizonaMiscUses_PLArizonaAgriculture",
    "ArizonaMiscUses_PLArizonaAdditionalAg",
    "ArizonaMiscUses_UnidentifiedUse",
    "CocopahIndRes",
    "CRIR CA",
    "Chemehuevi Ind Res",
    "Powers",
    "CibolaValleyIDD",
})


@pytest.fixture(scope="module")
def real_profiles():
    if not _REAL_REF_AVAILABLE:
        pytest.skip("CRSS reference data not present")
    return create_profiles_from_data(
        str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR), rng=np.random.default_rng(1),
    )


@pytest.fixture(scope="module")
def real_profiles_by_id(real_profiles):
    return {p.agent_id: p for p in real_profiles}


# ===========================================================================
# 2.1 Step base: keep = last committed delivery, never last carried request
# ===========================================================================

def _one_agent_env(request: float, diversion: float, water_right: float = 1_000_000.0,
                    basin: str = "lower_basin", mu: float = 0.3, sigma: float = 1.1,
                    step_bin_af: float = 5_000.0, config=None) -> IrrigationEnvironment:
    """A minimal, hand-built one-agent environment -- no CRSS data needed --
    with ``request`` (whatever was carried from a prior decision) and
    ``diversion`` (last COMMITTED delivery) set independently, exactly the
    shape ``_reset_requests_to_base`` must tell apart. ``config`` (2026-10-06
    CPU rerun finding): the WaterSystemConfig to build the environment with,
    default WaterSystemConfig(seed=1) -- a caller can pass one with a
    non-default min_utilisation_fraction to prove the floor follows it."""
    env = IrrigationEnvironment(config or WaterSystemConfig(seed=1))
    env._agents["A"] = {
        "basin": basin, "diversion": diversion, "request": request,
        "water_right": water_right, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
        "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
        "below_minimum_utilisation": False, "cluster": "x",
        "mu": mu, "sigma": sigma, "bin_size_af": step_bin_af, "step_bin_af": step_bin_af,
    }
    return env


def test_keep_requests_last_delivery():
    """After a year delivered at 0.8 R (R = the carried request), the keep
    request is 0.8 R, not R (f3aa2d87 / pre-WP2 gives R)."""
    R = 100_000.0
    delivered = 0.8 * R
    env = _one_agent_env(request=R, diversion=delivered)
    env._reset_requests_to_base()
    assert env._agents["A"]["request"] == pytest.approx(delivered)
    assert env._agents["A"]["base_af"] == pytest.approx(delivered)

    result = env.execute_skill(SimpleNamespace(
        skill_name="maintain_demand", agent_id="A", parameters={},
    ))
    assert result.state_changes["request"] == pytest.approx(delivered)


def test_increase_from_delivery_base():
    """An increase applied AFTER the reset adds the step to the DELIVERED
    base, not to the higher carried request the agent ended last year on."""
    R = 100_000.0
    delivered = 0.8 * R
    env = _one_agent_env(request=R, diversion=delivered, mu=0.3, sigma=1.1, step_bin_af=5_000.0)
    env._reset_requests_to_base()

    rng = env._decision_rng("A", "increase_demand")
    from examples.irrigation_abm.irrigation_env import hy_step_af
    expected_step = hy_step_af(rng, 0.3, 1.1, 5_000.0, "any")

    result = env.execute_skill(SimpleNamespace(
        skill_name="increase_demand", agent_id="A", parameters={},
    ))
    assert result.success
    assert result.state_changes["request"] == pytest.approx(
        min(delivered + expected_step, 1_000_000.0)
    )
    # Never the OLD (higher, pre-reset) carried request plus the step.
    assert result.state_changes["request"] != pytest.approx(R + expected_step)


def test_below_minimum_utilisation_uses_1pct_tolerance():
    """spec 2.1/C7: below_minimum_utilisation = base <= 1.01 F, the SAME
    tolerance as at_allocation_cap's 0.99 W -- a base strictly between F
    and 1.01 F is still treated as AT the floor."""
    W = 1_000_000.0
    F = W * MIN_UTIL
    just_inside = F * 1.005  # between F and 1.01 F
    env = _one_agent_env(request=just_inside, diversion=just_inside, water_right=W)
    env._reset_requests_to_base()
    assert env._agents["A"]["below_minimum_utilisation"] is True

    just_outside = F * 1.02  # clearly above 1.01 F
    env2 = _one_agent_env(request=just_outside, diversion=just_outside, water_right=W)
    env2._reset_requests_to_base()
    assert env2._agents["A"]["below_minimum_utilisation"] is False


def test_decrease_never_raises_a_request_that_starts_below_the_floor():
    """spec 2.1: decrease = max(base - s, F) ONLY when base > 1.01 F; a
    request that starts AT or below the floor is a no-op, never lifted
    toward F (the bug a bare max(base - s, F) would reintroduce)."""
    W = 1_000_000.0
    F = W * MIN_UTIL
    below_floor = F * 0.5  # well below F
    env = _one_agent_env(request=below_floor, diversion=below_floor, water_right=W)
    env._reset_requests_to_base()
    result = env.execute_skill(SimpleNamespace(
        skill_name="decrease_demand", agent_id="A", parameters={},
    ))
    assert result.success
    assert result.state_changes["request"] == pytest.approx(below_floor)


def test_decrease_floor_follows_the_config_not_the_default():
    """2026-10-06 CPU rerun finding (spec item 36k): execute_skill's
    decrease branch reads config.min_utilisation_fraction, not the
    module-level MIN_UTIL constant -- a large decrease step from well
    above both floors stops at the DEFAULT floor (10% W) under a default
    config, but at a RAISED floor (20% W) under a config that sets
    min_utilisation_fraction=0.20, never going below it either way."""
    W = 1_000_000.0
    start = 0.30 * W  # above both the default (10% W) and raised (20% W) floors
    huge_step = 0.5 * W  # large enough that an unclamped decrease would undershoot both

    default_env = _one_agent_env(
        request=start, diversion=start, water_right=W, mu=10.0, sigma=0.0, step_bin_af=huge_step,
    )
    default_env._reset_requests_to_base()
    default_result = default_env.execute_skill(SimpleNamespace(
        skill_name="decrease_demand", agent_id="A", parameters={},
    ))
    assert default_result.success
    assert default_result.state_changes["request"] == pytest.approx(0.10 * W)

    raised_floor_env = _one_agent_env(
        request=start, diversion=start, water_right=W, mu=10.0, sigma=0.0, step_bin_af=huge_step,
        config=WaterSystemConfig(seed=1, min_utilisation_fraction=0.20),
    )
    raised_floor_env._reset_requests_to_base()
    raised_result = raised_floor_env.execute_skill(SimpleNamespace(
        skill_name="decrease_demand", agent_id="A", parameters={},
    ))
    assert raised_result.success
    assert raised_result.state_changes["request"] == pytest.approx(0.20 * W)


def test_reset_precedes_release_plan():
    """WP1 re-review ordering requirement: after a year with a real
    physical shortfall, the NEXT year's 1 January snapshot sums the
    BASES (last year's deliveries) for BOTH basins, not the carried
    (pre-reset) requests -- so the Powell release plan and the
    provisional settlement both see the keep request. Fails if the reset
    is removed, or moved after the snapshot sums this year's projected
    requests for either basin (review round 1, MEDIUM 3: a reset moved to
    run between the Upper Basin and Lower Basin sums would still pass an
    LB-only check, so both are asserted independently here).
    """
    config = WaterSystemConfig(seed=11)
    env = IrrigationEnvironment(config)
    # Water rights far beyond anything the basin can physically deliver in
    # one year, so settle_year() curtails every agent hard and
    # predictably -- the exact ratio does not matter, only that
    # delivered != request for every agent.
    env.initialize_synthetic(n_agents=4, basin_split=(2, 2), base_water_right=50_000_000.0)
    env.advance_year()  # year 1 (2019): no prior commit, establishes _snapshot

    for a in env._agents.values():
        a["request"] = a["water_right"]
    settlement_y1 = env.settle_year()
    y1_request = {aid: env._agents[aid]["request"] for aid in env._agents}
    y1_delivered = {
        aid: rec["delivered"] for aid, rec in settlement_y1["agents"].items()
    }
    assert any(
        y1_delivered[aid] < y1_request[aid] - 1e-6 for aid in y1_request
    ), "fixture did not produce a real shortfall -- fix the setup, not the code under test"

    env.advance_year()  # year 2: commits year 1, must reset, THEN sum/plan

    for aid, base in y1_delivered.items():
        assert env._agents[aid]["request"] == pytest.approx(base), (
            f"{aid}: request was not reset to last year's delivered amount "
            f"before year 2's advance_year() returned"
        )

    expected_lb_maf = sum(
        y1_delivered[aid] for aid, a in env._agents.items() if a["basin"] == "lower_basin"
    ) / 1e6
    expected_ub_maf = sum(
        y1_delivered[aid] for aid, a in env._agents.items() if a["basin"] == "upper_basin"
    ) / 1e6
    assert env._snapshot["lb_request_projected_maf"] == pytest.approx(expected_lb_maf), (
        "lb_request_projected_maf reflects last year's CARRIED requests, "
        "not the reset bases -- the reset ran after the LB snapshot sum, "
        "or not at all"
    )
    assert env._snapshot["ub_request_projected_maf"] == pytest.approx(expected_ub_maf), (
        "ub_request_projected_maf reflects last year's CARRIED requests, "
        "not the reset bases -- the reset ran after the UB snapshot sum "
        "(e.g. moved to between the UB and LB sums), or not at all"
    )
    # The Powell release plan is a function of (among other things) these
    # same projected sums; asserting it is FINITE and was actually
    # (re)computed this year is a cheap way to confirm the plan step ran
    # AFTER the reset without re-deriving the whole balancing formula here.
    # test_release_plan_recomputes_from_frozen_projected_sums below checks
    # the plan step itself, with a fixture where the Upper Basin base
    # actually moves the projected DELIVERY (this one saturates both
    # basins at their capacity backstops, so the plan cannot be sensitive
    # to the exact projected-sum value here).
    assert np.isfinite(env._snapshot["powell_release_planned_maf"])


def test_release_plan_recomputes_from_frozen_projected_sums():
    """WP2 review round 2 (LOW 1): the frozen Powell plan must equal
    ``_plan_powell_release`` recomputed from the SAME frozen inputs the
    snapshot records, AND that plan must differ measurably from what
    the SAME recompute gives using the stale, carried (pre-reset) Upper
    Basin sum -- not just be *some* finite number. Round 1's fixture
    failed this: its plan sat at the 7.0 MAF band floor for any Upper
    Basin sum from 0 to 4.95 MAF, so a mutant that froze the fresh Upper
    Basin sum while the plan itself read the stale one still passed (both
    clamp to the same floor). Storage here (s_p=15, s_m=10 MAF, set
    directly -- this test cares about plan SENSITIVITY, not about the
    settlement dynamics that would normally produce a given storage) puts
    the correctly-reset plan at ~9.36 MAF and the stale-sum plan at
    ~8.84 MAF, both strictly inside (7.0, 9.5) and clearly different: the
    reviewer's stale-sum mutant (freezing ub_request_projected_maf from
    the carried request rather than the reset base, or moving the reset
    to run between the Upper Basin and Lower Basin sums) now fails both
    assertions below, not just the first.

    Exercises _reset_requests_to_base/advance_year's FIRST-EVER call
    (``self._snapshot is None`` beforehand): the reset, the projected
    sums and the plan all run unconditionally on that call too (only the
    commit step is skipped), so a hand-set ``diversion`` (the base) and
    ``request`` (a deliberately different, stale carried value) exercise
    the exact same ordering a second-or-later year's call does, without
    needing a real settlement to produce the storage/shortfall."""
    # Spec items 26/27: pinned to storage_balancing explicitly -- this
    # test's docstring numbers (~9.36 / ~8.84 MAF, "strictly inside the
    # balancing band") are that rule's own algebra; the v3-default
    # ig2007_tiers rule would classify this scenario into one of its
    # named tiers instead, a different (and not necessarily "clearly
    # different between a fresh and a stale Upper Basin sum") release.
    config = WaterSystemConfig(seed=3, ub_supply_mode="lees_ferry_pool",
                                powell_release_mode="storage_balancing")
    env = IrrigationEnvironment(config)
    env._powell_storage = 15.0
    env._mead_storage = [10.0]
    base_maf = 3.0
    carried_maf = 4.0  # the stale, pre-reset request a mutant would use instead
    env._agents["UB1"] = {
        "basin": "upper_basin", "diversion": base_maf * 1e6, "request": carried_maf * 1e6,
        "water_right": 4_950_000.0, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
        "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
        "below_minimum_utilisation": False, "cluster": "x", "mu": 0.2, "sigma": 0.5,
        "bin_size_af": 10_000.0, "step_bin_af": 10_000.0, "supply_group": None,
        "ub_subbasin_member_count": None, "ub_subbasin_ratio": None,
        "ub_subbasin_sole_bound": 0.0,
    }
    env._agents["LB1"] = {
        "basin": "lower_basin", "diversion": 100_000.0, "request": 100_000.0,
        "water_right": 500_000.0, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
        "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
        "below_minimum_utilisation": False, "cluster": "x", "mu": 0.2, "sigma": 0.5,
        "bin_size_af": 10_000.0, "step_bin_af": 10_000.0,
    }

    env.advance_year()  # first-ever call: no commit, but reset/sums/plan all run

    assert env._snapshot["ub_request_projected_maf"] == pytest.approx(base_maf), (
        "ub_request_projected_maf is not the reset base -- the reset did "
        "not run before the Upper Basin sum, or used the wrong field"
    )

    frozen_plan = env._snapshot["powell_release_planned_maf"]
    common_kwargs = dict(
        nf=env._snapshot["natural_flow"],
        s_p=env._snapshot["powell_storage"],
        s_m=env._snapshot["mead_storage"],
        trib=env._snapshot["lb_tributary"],
        shortage_volume=env._snapshot["lb_shortage_volume_maf"],
        mexico=env._snapshot["mexico"],
        lb_requested_maf=env._snapshot["lb_request_projected_maf"],
        year=env._current_year,
    )
    recomputed_from_frozen = env._plan_powell_release(
        ub_requested_maf=env._snapshot["ub_request_projected_maf"], **common_kwargs
    )
    recomputed_from_carried = env._plan_powell_release(
        ub_requested_maf=carried_maf, **common_kwargs
    )

    for value in (frozen_plan, recomputed_from_frozen, recomputed_from_carried):
        assert 7.0 < value < 9.5, (
            f"{value} is not strictly inside the balancing band -- a "
            "boundary value cannot show the plan is sensitive to which "
            "Upper Basin sum was used"
        )
    assert frozen_plan == pytest.approx(recomputed_from_frozen), (
        "the frozen Powell release plan does not equal _plan_powell_release "
        "recomputed from the SAME frozen projected sums -- the plan step "
        "is not consuming what advance_year() actually froze"
    )
    assert frozen_plan != pytest.approx(recomputed_from_carried), (
        "the frozen plan equals what the STALE, carried (pre-reset) Upper "
        "Basin sum would have given -- the reset is not actually reaching "
        "the plan (a stale-sum mutant would silently pass)"
    )


# ===========================================================================
# 2.2 / 2.3 / 2.4: three skills, registry, UB unit conversion, rescale
# ===========================================================================

def test_three_skill_registry_and_map():
    """spec 2.2: increase_demand/maintain_demand/decrease_demand only;
    skill_map 1/2/3; output enum [1, 2, 3]; default_skill maintain_demand."""
    reg = yaml.safe_load(SKILL_REGISTRY_YAML.read_text(encoding="utf-8"))
    ids = [s["skill_id"] for s in reg["skills"]]
    assert ids == ["increase_demand", "maintain_demand", "decrease_demand"]
    assert reg["default_skill"] == "maintain_demand"
    for s in reg["skills"]:
        assert s["output_schema"]["properties"]["decision"]["enum"] == [1, 2, 3]
    increase = next(s for s in reg["skills"] if s["skill_id"] == "increase_demand")
    assert increase["preconditions"] == ["not at_allocation_cap", "not at_beneficial_use_limit"]
    decrease = next(s for s in reg["skills"] if s["skill_id"] == "decrease_demand")
    assert decrease["preconditions"] == ["not below_minimum_utilisation"]

    cfg = yaml.safe_load(AGENT_TYPES_YAML.read_text(encoding="utf-8"))
    irr = cfg["irrigation_farmer"]
    action_ids = [a["id"] for a in irr["actions"]]
    assert action_ids == ["increase_demand", "maintain_demand", "decrease_demand"]
    assert irr["parsing"]["skill_map"] == {
        "1": "increase_demand", "2": "maintain_demand", "3": "decrease_demand",
    }
    assert irr["parsing"]["global_skills"] == ["maintain_demand"]
    assert irr["parsing"]["default_skill"] == "maintain_demand"


@_real_ref
def test_ub_bin_is_half_grid_step(real_profiles_by_id):
    """spec 2.3 (L1-02, L2 H3): bin_size_af = k x (grid[2] - grid[1]),
    k = 0.5 for an Upper Basin agent (NIIP)."""
    import pandas as pd
    p = real_profiles_by_id[NIIP]
    assert p.basin == "upper_basin"
    ub = pd.read_csv(CRSS_DB_DIR / "Div_States" / "UB_discrete_states.csv")
    raw_step = float(ub[NIIP].iloc[2] - ub[NIIP].iloc[1])
    assert p.demand_per_grid_unit == pytest.approx(0.5)
    assert p.bin_size_af == pytest.approx(0.5 * raw_step)
    assert p.bin_size_af == pytest.approx(raw_step / 2.0)


@_real_ref
def test_step_rescale_set(real_profiles):
    """spec 2.4 acceptance: exactly the 8 named agents (0.20 percent of
    2018 use) have their step bin rescaled to 10 percent of 2018 use."""
    rescaled = {p.agent_id for p in real_profiles if p.step_bin_source == "rescaled"}
    assert rescaled == EXPECTED_RESCALED_AGENTS
    for p in real_profiles:
        if p.agent_id in EXPECTED_RESCALED_AGENTS:
            assert p.step_bin_af == pytest.approx(0.10 * p.actual_2018_diversion)
        else:
            assert p.step_bin_source == "grid"
            assert p.step_bin_af == pytest.approx(p.bin_size_af)


@_real_ref
def test_water_rights_sum_unchanged_by_wp2(real_profiles):
    """Acceptance: WP2 touches bin_size_af / step_bin_af only -- the water
    rights it does NOT touch are unaffected BY WP2. Item 36f/36g
    (2026-10-05 design-basis audit + fix proposals, spec item 36, a
    LATER change than WP2) moved the sums themselves: UB 4.932 -> 4.950
    MAF (dropping the grid-top term, item 36g, raises the one agent it
    used to bind); LB 4.177 -> 4.266 MAF (grid top alone, item 36f, no
    longer scaled down by the margin for 10 agents)."""
    ub_total = sum(p.water_right for p in real_profiles if p.basin == "upper_basin")
    lb_total = sum(p.water_right for p in real_profiles if p.basin == "lower_basin")
    assert ub_total / 1e6 == pytest.approx(4.950, abs=5e-4)
    assert lb_total / 1e6 == pytest.approx(4.266, abs=5e-4)


@_real_ref
def test_typical_step_share_of_2018_use_matches_spec_medians(real_profiles):
    """Acceptance (spec 2.5): after 2.3 and 2.4, typical step / 2018 use
    has median 0.101 (UB) / 0.040 (LB), maximum 0.144 (UB) / 0.128 (LB),
    to three decimals."""
    import statistics
    ub_ratios, lb_ratios = [], []
    for p in real_profiles:
        s = hy_threshold_af(p.mu, p.sigma, p.step_bin_af)
        ratio = s / p.actual_2018_diversion
        (ub_ratios if p.basin == "upper_basin" else lb_ratios).append(ratio)
    assert round(statistics.median(ub_ratios), 3) == 0.101
    assert round(max(ub_ratios), 3) == 0.144
    assert round(statistics.median(lb_ratios), 3) == 0.040
    assert round(max(lb_ratios), 3) == 0.128


@_real_ref
def test_floor_does_not_lift_keep(real_profiles_by_id):
    """spec 2.1/2.4 acceptance: CocopahIndRes's 2019 keep request is its
    2018 use, 550 AF -- already below its own 10 percent floor -- and a
    decrease never raises it toward that floor."""
    p = real_profiles_by_id["CocopahIndRes"]
    assert p.actual_2018_diversion == pytest.approx(550.0)
    floor = p.water_right * MIN_UTIL
    assert p.actual_2018_diversion < floor  # genuinely below its own floor

    env = IrrigationEnvironment(WaterSystemConfig(seed=1))
    env.initialize_from_profiles([p])
    env.advance_year()  # year 1: request/diversion start at actual_2018_diversion
    assert env._agents["CocopahIndRes"]["request"] == pytest.approx(550.0)

    result = env.execute_skill(SimpleNamespace(
        skill_name="decrease_demand", agent_id="CocopahIndRes", parameters={},
    ))
    assert result.success
    assert result.state_changes["request"] == pytest.approx(550.0)


# ===========================================================================
# 2.6 Option texts
# ===========================================================================

def _expected_option_texts(profile, base: float, water_right: float, floor: float) -> dict:
    """Re-derive the spec 2.6 template independently of build_option_texts,
    from the same inputs, so the test is not just build_option_texts
    checking itself. Mirrors review round 1's two fixes: LOW 9 (round the
    parts BEFORE computing each target, so base + step == target exactly)
    and MEDIUM 5 (omit decrease_demand once base <= 1.01 F -- the menu
    never offers it in any arm, so the text must not describe it)."""
    s = hy_threshold_af(profile.mu, profile.sigma, profile.step_bin_af)
    base_r, s_r, w_r, f_r = round(base), round(s), round(water_right), round(floor)

    increase_to = min(base_r + s_r, w_r)
    inc = (
        f"Increase your request to about {increase_to:,.0f} acre-ft: the "
        f"{base_r:,.0f} acre-ft you received last year plus your typical "
        f"step of about {s_r:,.0f} acre-ft"
    )
    if base_r + s_r > w_r:
        inc += f" (your water right stops it at {w_r:,.0f} acre-ft)"
    inc += "."

    maintain = f"Keep your request at {base_r:,.0f} acre-ft, the amount you received last year."

    expected = {"increase_demand": inc, "maintain_demand": maintain}
    if base > 1.01 * floor:
        decrease_to = max(base_r - s_r, f_r)
        dec = (
            f"Decrease your request to about {decrease_to:,.0f} acre-ft: the "
            f"{base_r:,.0f} acre-ft you received last year minus your typical "
            f"step of about {s_r:,.0f} acre-ft"
        )
        if base_r - s_r < f_r:
            dec += f" (the minimum-use floor stops it at {f_r:,.0f} acre-ft)"
        dec += "."
        expected["decrease_demand"] = dec
    return expected


@_real_ref
def test_option_text_exact(real_profiles_by_id):
    """WP2 review round 1 (MEDIUM 7): a REAL golden test with hard-coded
    2019 strings (base = actual_2018_diversion) -- one Upper Basin agent
    (NIIP), one Lower Basin agent (WelltonMohawkIDD) and one rescaled
    agent (CibolaValleyIDD, spec 2.4: its own base sits comfortably above
    its floor, unlike CocopahIndRes -- see
    test_cocopah_decrease_omitted_below_floor for that case). Also checked
    against the independent re-derivation in _expected_option_texts."""
    golden = {
        NIIP: {
            "increase_demand": (
                "Increase your request to about 163,803 acre-ft: the "
                "148,797 acre-ft you received last year plus your "
                "typical step of about 15,006 acre-ft."
            ),
            "maintain_demand": (
                "Keep your request at 148,797 acre-ft, the amount you "
                "received last year."
            ),
            "decrease_demand": (
                "Decrease your request to about 133,791 acre-ft: the "
                "148,797 acre-ft you received last year minus your "
                "typical step of about 15,006 acre-ft."
            ),
        },
        "WelltonMohawkIDD": {
            "increase_demand": (
                "Increase your request to about 378,544 acre-ft: the "
                "373,081 acre-ft you received last year plus your "
                "typical step of about 5,463 acre-ft."
            ),
            "maintain_demand": (
                "Keep your request at 373,081 acre-ft, the amount you "
                "received last year."
            ),
            "decrease_demand": (
                "Decrease your request to about 367,618 acre-ft: the "
                "373,081 acre-ft you received last year minus your "
                "typical step of about 5,463 acre-ft."
            ),
        },
        "CibolaValleyIDD": {
            "increase_demand": (
                "Increase your request to about 8,385 acre-ft: the "
                "7,432 acre-ft you received last year plus your typical "
                "step of about 953 acre-ft."
            ),
            "maintain_demand": (
                "Keep your request at 7,432 acre-ft, the amount you "
                "received last year."
            ),
            "decrease_demand": (
                "Decrease your request to about 6,479 acre-ft: the "
                "7,432 acre-ft you received last year minus your typical "
                "step of about 953 acre-ft."
            ),
        },
    }
    for agent_id, expected_text in golden.items():
        p = real_profiles_by_id[agent_id]
        base = p.actual_2018_diversion
        w = p.water_right
        f = w * MIN_UTIL
        actual = build_option_texts(p, base, w, f)
        assert actual == expected_text, agent_id
        assert actual == _expected_option_texts(p, base, w, f), agent_id
        # Numbers are formatted ,.0f (spec): no decimal point anywhere.
        for text in actual.values():
            assert "." not in text.rstrip(".").replace(",", "")

    # NIIP, WelltonMohawkIDD and CibolaValleyIDD are all well inside
    # [F, 0.99 W] this year, so neither clamp clause fires -- pin that
    # explicitly (the clamped branches are covered by
    # test_option_text_exact_hits_both_clamp_clauses and
    # test_cocopah_decrease_omitted_below_floor instead).
    for agent_id in golden:
        p = real_profiles_by_id[agent_id]
        texts = build_option_texts(p, p.actual_2018_diversion, p.water_right, p.water_right * MIN_UTIL)
        assert "water right stops it" not in texts["increase_demand"]
        assert "minimum-use floor stops it" not in texts["decrease_demand"]


@_real_ref
def test_cocopah_decrease_omitted_below_floor(real_profiles_by_id):
    """WP2 review round 1 (MEDIUM 5, PI decision): the minimum-use floor
    is a menu filter in every arm, so decrease is never offered when
    base <= 1.01 F. CocopahIndRes's 2018 use (550 AF) is already below
    its own floor (1,272.6 AF, spec/provenance C6) -- build_option_texts
    must omit "decrease_demand" entirely rather than describe a
    "decrease" that would actually RAISE the request toward the floor."""
    p = real_profiles_by_id["CocopahIndRes"]
    base = p.actual_2018_diversion
    w = p.water_right
    f = w * MIN_UTIL
    assert base <= 1.01 * f  # the exact condition build_option_texts gates on
    texts = build_option_texts(p, base, w, f)
    assert "decrease_demand" not in texts
    assert set(texts) == {"increase_demand", "maintain_demand"}
    assert texts == _expected_option_texts(p, base, w, f)


def test_option_text_exact_hits_both_clamp_clauses():
    """The increase/decrease clamp clauses (spec 2.6) DO fire when the
    typical step would cross the water right / floor -- synthetic profile,
    no CRSS data needed."""
    from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile

    profile = IrrigationAgentProfile(
        agent_id="synthetic", basin="lower_basin", cluster="aggressive",
        mu=1.0, sigma=0.0, step_bin_af=10_000.0,
    )
    base = 95_000.0
    w = 100_000.0
    f = w * MIN_UTIL
    texts = build_option_texts(profile, base, w, f)
    s = hy_threshold_af(1.0, 0.0, 10_000.0)
    assert base + s > w
    assert f"(your water right stops it at {w:,.0f} acre-ft)." in texts["increase_demand"]

    base2 = 12_000.0
    texts2 = build_option_texts(profile, base2, w, f)
    assert base2 - s < f
    assert f"(the minimum-use floor stops it at {f:,.0f} acre-ft)." in texts2["decrease_demand"]


def test_option_texts_use_step_bin_af_not_raw_bin_size_af():
    """build_option_texts must read the FINAL step_bin_af (spec 2.3/2.4),
    not a raw/unconverted bin_size_af, when the profile carries both."""
    from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile

    profile = IrrigationAgentProfile(
        agent_id="synthetic", basin="upper_basin", cluster="aggressive",
        mu=0.3, sigma=0.5, bin_size_af=20_000.0, step_bin_af=4_000.0,
    )
    texts = build_option_texts(profile, base=100_000.0, water_right=1_000_000.0, floor=10_000.0)
    s_correct = hy_threshold_af(0.3, 0.5, 4_000.0)
    s_wrong = hy_threshold_af(0.3, 0.5, 20_000.0)
    assert f"{s_correct:,.0f} acre-ft" in texts["increase_demand"]
    assert f"{s_wrong:,.0f} acre-ft" not in texts["increase_demand"]


def test_hy_threshold_af_clamps_negative_mu():
    """spec 2.5: typical_step_af = (max(0, mu) + 0.6745 sigma) x
    step_bin_af -- a negative mu must not pull the shown typical step (or
    the small/large threshold) below the sigma-only term."""
    negative = hy_threshold_af(-5.0, 1.0, 1_000.0)
    zero = hy_threshold_af(0.0, 1.0, 1_000.0)
    assert negative == pytest.approx(zero)
    assert negative > 0


# ===========================================================================
# WP2 review round 1 (HIGH 1): hold_requests_fixed
# ===========================================================================

def test_hold_requests_fixed_defaults_false_and_is_validated():
    assert WaterSystemConfig().hold_requests_fixed is False
    with pytest.raises(ValueError):
        WaterSystemConfig(hold_requests_fixed="yes")  # type: ignore[arg-type]


def test_hold_requests_fixed_skips_the_reset_end_to_end():
    """The switch's own contract, exercised through advance_year() itself
    (not by calling _reset_requests_to_base directly): with the switch
    on, a request set once (here, right after year 1) stays fixed through
    year 2's advance_year() even after a real delivery shortfall; with it
    off (default), the SAME setup lets the reset overwrite it."""
    def _two_year_request_after_shortfall(hold_requests_fixed: bool) -> float:
        config = WaterSystemConfig(seed=13, hold_requests_fixed=hold_requests_fixed)
        env = IrrigationEnvironment(config)
        env.initialize_synthetic(n_agents=2, basin_split=(1, 1), base_water_right=50_000_000.0)
        env.advance_year()  # year 1: establishes _snapshot, no prior commit
        for a in env._agents.values():
            a["request"] = a["water_right"]  # a target far beyond physical delivery
        fixed_target = next(iter(env._agents.values()))["request"]
        env.settle_year()  # a real shortfall: delivered < fixed_target
        env.advance_year()  # year 2: commits year 1; the switch decides what happens next
        return next(iter(env._agents.values()))["request"], fixed_target

    held_request, held_target = _two_year_request_after_shortfall(True)
    assert held_request == pytest.approx(held_target), (
        "hold_requests_fixed=True must leave the request exactly as set, "
        "even after a real shortfall"
    )

    reset_request, reset_target = _two_year_request_after_shortfall(False)
    assert reset_request != pytest.approx(reset_target), (
        "hold_requests_fixed=False (default) must still reset the request "
        "to last year's delivery -- this fixture's shortfall is real"
    )


def test_hold_requests_fixed_never_passed_to_watersystemconfig_by_a_runner():
    """WP2 review round 1 (HIGH 1): hold_requests_fixed is for replays and
    CPU diagnostics only -- no runner may ever construct WaterSystemConfig
    with it set, so a real LLM or FQL run always gets the WP2
    keep-tracks-delivery behaviour.

    Review round 2 (LOW 3) narrowed this from a bare substring check: both
    runners now LEGITIMATELY mention "hold_requests_fixed" (the defense-
    in-depth ``assert config.hold_requests_fixed is False`` right after
    construction, and recording the -- already-verified -- value in the
    manifest); what must never appear is the switch being PASSED IN as a
    WaterSystemConfig constructor keyword. Parsed with ast, not text
    matching, so it survives reformatting; test_run_experiment_refuses_
    hold_requests_fixed_true and test_run_fql_baseline_refuses_
    hold_requests_fixed_true below exercise the runtime assertion itself.
    """
    import ast

    for rel in ("run_experiment.py", "run_fql_baseline.py"):
        src = (REPO_ROOT / "examples" / "irrigation_abm" / rel).read_text(encoding="utf-8")
        tree = ast.parse(src, filename=rel)
        offending = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "WaterSystemConfig"
            ):
                offending.extend(
                    kw.arg for kw in node.keywords if kw.arg == "hold_requests_fixed"
                )
        assert not offending, (
            f"{rel} must never pass hold_requests_fixed to WaterSystemConfig()"
        )


def test_run_experiment_refuses_hold_requests_fixed_true(tmp_path, monkeypatch):
    """WP2 review round 2 (LOW 3): the defense-in-depth assertion right
    after WaterSystemConfig construction in run_experiment.py's main()
    actually fires if the switch is ever True -- simulates a future
    change threading an override through, since there is no CLI flag to
    set it today."""
    import examples.irrigation_abm.run_experiment as run_experiment

    def _forced_true(*args, **kwargs):
        cfg = WaterSystemConfig(*args, **kwargs)
        cfg.hold_requests_fixed = True
        return cfg

    monkeypatch.setattr(run_experiment, "WaterSystemConfig", _forced_true)
    argv = [
        "run_experiment.py", "--model", "mock", "--agents", "3",
        "--years", "1", "--seed", "1", "--output", str(tmp_path),
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(AssertionError, match="hold_requests_fixed"):
            run_experiment.main()
    finally:
        sys.argv = old_argv


def test_run_fql_baseline_refuses_hold_requests_fixed_true(tmp_path, monkeypatch):
    """WP2 review round 2 (LOW 3): same guard, run_fql_baseline.py."""
    import examples.irrigation_abm.run_fql_baseline as run_fql_baseline

    def _forced_true(*args, **kwargs):
        cfg = WaterSystemConfig(*args, **kwargs)
        cfg.hold_requests_fixed = True
        return cfg

    monkeypatch.setattr(run_fql_baseline, "WaterSystemConfig", _forced_true)
    argv = [
        "run_fql_baseline.py", "--agents", "3", "--years", "1", "--seed", "1",
        "--output", str(tmp_path), "--fql-init", "zero",
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(AssertionError, match="hold_requests_fixed"):
            run_fql_baseline.main()
    finally:
        sys.argv = old_argv


def test_run_experiment_manifest_records_hold_requests_fixed_false(tmp_path):
    """WP2 review round 2 (LOW 3): an ordinary (synthetic, fast) run's
    manifest shows hold_requests_fixed: false -- the value main()'s own
    assertion just verified, not a stale literal."""
    import json
    import examples.irrigation_abm.run_experiment as run_experiment

    argv = [
        "run_experiment.py", "--model", "mock", "--agents", "3",
        "--years", "1", "--seed", "1", "--output", str(tmp_path),
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        run_experiment.main()
    finally:
        sys.argv = old_argv

    manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["hold_requests_fixed"] is False


@_real_ref
def test_run_fql_baseline_manifest_records_step_bin_source_and_hold_requests_fixed(tmp_path):
    """WP2 review round 2 (LOW 2, spec 7.2 + LOW 3): run_fql_baseline.py's
    OWN manifest (it has no ExperimentRunner/broker manifest behind it)
    must ALSO carry step_bin_source (70 grid / 8 rescaled, spec 2.4's own
    count, on a --real run) and hold_requests_fixed: false, the same as
    run_experiment.py's."""
    import json
    import examples.irrigation_abm.run_fql_baseline as run_fql_baseline

    argv = [
        "run_fql_baseline.py", "--real", "--years", "1", "--seed", "1",
        "--fql-init", "zero", "--output", str(tmp_path),
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        run_fql_baseline.main()
    finally:
        sys.argv = old_argv

    manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["hold_requests_fixed"] is False
    assert manifest["step_bin_source_applied"] is True
    step_bin_source = manifest["step_bin_source"]
    assert len(step_bin_source) == 78
    counts = {v: list(step_bin_source.values()).count(v) for v in ("grid", "rescaled")}
    assert counts == {"grid": 70, "rescaled": 8}
