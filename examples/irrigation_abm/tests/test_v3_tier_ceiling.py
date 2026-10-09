"""Spec item 46: a tier limits entitlements, with physical shortage afterwards."""
import pytest

from examples.irrigation_abm.irrigation_env import (
    WaterSystemConfig, _lb_junior_tier_fraction, _load_lb_priority_split_table,
)
from examples.irrigation_abm.tests.test_v3_lb_priority import (
    _lb_env, _ample_supply_snapshot, _planned_snapshot,
)


def _ceiling(aid, tier, p56_mode='zero'):
    row = _load_lb_priority_split_table()[aid]
    f = _lb_junior_tier_fraction(tier)
    p56 = row['p56_entitlement_af']
    return row['senior_entitlement_af'] + (1-f)*(row['junior_entitlement_af']-p56) + (
        (1-f)*p56 if p56_mode == 'proportional' else 0)


def test_fully_junior_below_ceiling_is_not_cut():
    env = _lb_env({'NorthBajaLLC': 200.})
    rec = env._settle(_ample_supply_snapshot(env, 2))['agents']['NorthBajaLLC']
    assert rec['delivered'] == 200.
    assert rec['lb_junior_cut_af'] == 0.
    assert rec['gap_reason'] == 'none'


def test_above_ceiling_is_held_at_entitlement_limit():
    env = _lb_env({'NorthBajaLLC': 567.})
    rec = env._settle(_ample_supply_snapshot(env, 2))['agents']['NorthBajaLLC']
    expected = 480*(1-_lb_junior_tier_fraction(2))
    assert rec['delivered'] == pytest.approx(expected)
    assert rec['lb_junior_cut_af'] == pytest.approx(567-expected)


def test_constant_request_in_consecutive_tiers_does_not_compound():
    env = _lb_env({'NorthBajaLLC': 567.})
    values = []
    for year in range(3):
        env._current_year = 2019+year
        rec = env._settle(_ample_supply_snapshot(env, 2))['agents']['NorthBajaLLC']
        values.append(rec['delivered'])
    assert values == pytest.approx([480*(1-_lb_junior_tier_fraction(2))]*3)
    # A keep uses the prior delivery: at exactly this limit it is fully met.
    env._agents['NorthBajaLLC']['request'] = values[-1]
    assert env._settle(_ample_supply_snapshot(env, 2))['agents']['NorthBajaLLC']['lb_junior_cut_af'] == 0.


def test_partly_junior_senior_part_is_untouched():
    env = _lb_env({'MohaveValleyIDD': 40000.})
    rec = env._settle(_ample_supply_snapshot(env, 3))['agents']['MohaveValleyIDD']
    assert rec['lb_senior_af'] == 5940.
    assert rec['delivered'] == pytest.approx(5940+35060*(1-_lb_junior_tier_fraction(3)))


@pytest.mark.parametrize('aid,p56', [('HopiTribe', 1750.), ('CibolaValleyIDD', 3500.), ('GilaMonsterFarms', 656.)])
@pytest.mark.parametrize('mode', ['zero', 'proportional'])
def test_p56_availability_is_sourced_and_switchable(aid, p56, mode):
    row = _load_lb_priority_split_table()[aid]
    assert row['p56_entitlement_af'] == p56
    env = _lb_env({aid: row['senior_entitlement_af']+row['junior_entitlement_af']})
    env.config.lb_p56_in_tier = mode
    rec = env._settle(_ample_supply_snapshot(env, 1))['agents'][aid]
    assert rec['delivered'] == pytest.approx(_ceiling(aid, 1, mode))


def test_no_tier_preserves_request_above_published_entitlement():
    env = _lb_env({'CibolaValleyIDD': 43236.2})
    rec = env._settle(_ample_supply_snapshot(env, 0))['agents']['CibolaValleyIDD']
    assert rec['delivered'] == 43236.2
    assert rec['lb_junior_cut_af'] == 0.


@pytest.mark.parametrize('aid,requested_af', [('CocopahIndRes', 14000.), ('CibolaValleyIDD', 46000.)])
def test_no_tier_has_no_logged_or_context_ceiling(aid, requested_af):
    env = _lb_env({aid: requested_af})
    st = env._settle(_ample_supply_snapshot(env, 0))
    for key in ('lb_junior_ceiling_af', 'lb_tier_ceiling_af'):
        assert st['agents'][aid][key] is None
        assert env.get_agent_context(aid)[key] is None


def test_new_run_does_not_compute_legacy_restore_state():
    from broker.interfaces.skill_types import ApprovedSkill
    env = _lb_env({'HopiTribe': 4798.})
    env._reset_requests_to_base()
    assert 'previous_gap_reason' not in env._agents['HopiTribe']
    assert 'previous_request_af' not in env._agents['HopiTribe']
    result = env.execute_skill(ApprovedSkill('maintain_demand', 'HopiTribe', 'APPROVED', []))
    assert 'rule_exceptions_used' not in result.action_context


@pytest.mark.parametrize('tier', [1, 2, 3])
def test_above_entitlement_credit_stays_within_declared_volume(tier):
    table = _load_lb_priority_split_table()
    requests = {aid: row['water_right_af'] for aid, row in table.items()
                if row['junior_entitlement_af'] > 0}
    env = _lb_env(requests)
    st = env._settle(_ample_supply_snapshot(env, tier))
    # Item46 credits req-ceiling, including model rights above legal rights.
    cuts = st['lb_junior_cut_total_maf']
    assert .072 < cuts < .078  # 72.13--77.36 kaf (rounds to about 72--77).
    reduction = env.config.lb_non_ag_total_maf - st['lb_non_ag_delivered_maf']
    assert 0 <= reduction <= env.config.lb_non_ag_total_maf
    assert cuts + reduction == pytest.approx(env._tier_shortage_volume_maf(tier))


@pytest.mark.parametrize('invalid', ['negative_reduction', 'reduction_exceeds_bucket'])
def test_non_ag_reduction_outside_bucket_fails_loud(invalid):
    env = _lb_env({'HopiTribe': 4798.})
    if invalid == 'negative_reduction':
        # Malformed input credits more agricultural cuts than the tier V.
        env._agents['HopiTribe']['request'] = 1_000_000.
        env._agents['HopiTribe']['water_right'] = 1_000_000.
    else:
        env.config.lb_non_ag_total_maf = .01
    with pytest.raises(ValueError, match='non-agricultural reduction'):
        env._settle(_ample_supply_snapshot(env, 1))


def test_volume_conserved_when_non_ag_bucket_allows():
    env = _lb_env({'HopiTribe': 4798., 'MohaveValleyIDD': 40000.})
    st = env._settle(_ample_supply_snapshot(env, 2))
    assert env.config.lb_non_ag_total_maf-st['lb_non_ag_delivered_maf']+st['lb_junior_cut_total_maf'] == pytest.approx(.417)


def test_mead_physical_shortage_applies_after_ceiling():
    env = _lb_env({'HopiTribe': 5900.})
    snap = dict(powell_storage=3., mead_storage=3.5, natural_flow=.5,
                lb_shortage_volume_maf=.417, lb_shortage_tier=2, mexico=.1,
                lb_tributary=.05, lb_request_projected_maf=.0059)
    st = env._settle(_planned_snapshot(env, snap))
    assert st['lb_phys_ratio'] < 1
    assert st['agents']['HopiTribe']['delivered'] == pytest.approx(_ceiling('HopiTribe', 2)*st['lb_phys_ratio'])
    assert st['agents']['HopiTribe']['gap_reason'] == 'lb_junior_tier_cut+lb_mead_availability'


def test_p56_config_validated_and_recorded():
    assert WaterSystemConfig().lb_p56_in_tier == 'zero'
    assert WaterSystemConfig(lb_p56_in_tier='proportional').lb_p56_in_tier == 'proportional'
    with pytest.raises(ValueError, match='lb_p56_in_tier'):
        WaterSystemConfig(lb_p56_in_tier='guess')
    env = _lb_env({'HopiTribe': 4798.})
    assert env.get_coupling_retrofit_metadata()['water_system_lb_p56_in_tier'] == 'zero'
