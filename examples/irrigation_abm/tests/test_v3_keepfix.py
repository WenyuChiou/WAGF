"""Item 47 exact texts, truth checks and independent log read-back (mock only)."""
import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from broker.components.analytics.feedback import AgentMetricsTracker, FeedbackDashboardProvider
from examples.irrigation_abm.analysis import v3_metrics as vm
from examples.irrigation_abm.irrigation_env import (
    WaterSystemConfig, _load_lb_priority_split_table,
)
from examples.irrigation_abm.irrigation_personas import (
    K6_SENIOR_TIER_TEXT, FULL_SUPPLY_RATIO, is_routine_outcome, land_need_text,
    increase_expectation_text, _sharing_sentence,
)
from examples.irrigation_abm.tests.test_v3_prompt import ScriptedLLM, _run, CONFIG
from examples.irrigation_abm.tests.test_v3_lb_priority import _lb_env, _ample_supply_snapshot
from examples.irrigation_abm.validators import irrigation_validators as validators


@pytest.fixture(scope='module')
def pilots(tmp_path_factory):
    runs = []
    for mode in ('strict', 'disabled'):
        out = tmp_path_factory.mktemp('keepfix_'+mode)
        llm = ScriptedLLM(lambda agent, year, attempt: ('M', 'M', 'Keep'))
        with pytest.MonkeyPatch.context() as mp:
            _run(mp, out, llm, '--real', '--years', '4', '--seed', '42',
                 '--memory-seed', '42', '--governance-mode', mode)
        runs.append(vm.load_run(out, keep_prompts=True))
        runs[-1]._test_llm = llm
    return runs


@pytest.mark.parametrize('change', [{}, {'was_fallback': True}, {'skill_name': 'increase_demand'},
                                  {'year': 1}, {'magnitude_pct': 0}])
def test_routine_marking_reads_executed_decision(change):
    action = dict(year=2, skill_name='maintain_demand', was_fallback=False, **{})
    action.update(change)
    snapshot = dict(year=2, request=100., diversion=100., previous_request=100., shortage_tier=0)
    assert is_routine_outcome(action, snapshot, 'lower_basin') is (not change)
    assert not is_routine_outcome(None, snapshot, 'upper_basin')
    for field, value in [('previous_request', 101.), ('diversion', 99.), ('shortage_tier', 1)]:
        assert not is_routine_outcome(action, dict(snapshot, **{field: value}), 'lower_basin')


@pytest.mark.parametrize('scope,tier_affects_agent,expected', [
    ('any_tier', False, False),
    ('any_tier', True, False),
    ('affects_agent', False, True),
    ('affects_agent', True, False),
])
def test_routine_tier_scope_distinguishes_senior_and_junior_agents(
    scope, tier_affects_agent, expected,
):
    action = dict(year=2, skill_name='maintain_demand', was_fallback=False,
                  magnitude_pct=None)
    snapshot = dict(year=2, request=100., diversion=100., previous_request=100.,
                    shortage_tier=1)
    assert is_routine_outcome(
        action, snapshot, 'lower_basin', routine_tier_scope=scope,
        tier_affects_agent=tier_affects_agent,
    ) is expected
    # A Lower Basin tier does not make an Upper Basin outcome eventful.
    assert is_routine_outcome(
        action, snapshot, 'upper_basin', routine_tier_scope=scope,
        tier_affects_agent=tier_affects_agent,
    )


def test_routine_tier_scope_rejects_unknown_value():
    action = dict(year=2, skill_name='maintain_demand', was_fallback=False,
                  magnitude_pct=None)
    snapshot = dict(year=2, request=100., diversion=100., previous_request=100.,
                    shortage_tier=1)
    with pytest.raises(ValueError, match='routine_tier_scope'):
        is_routine_outcome(
            action, snapshot, 'lower_basin', routine_tier_scope='unknown',
            tier_affects_agent=False,
        )


def test_unread_outcome_is_eventful_without_accessing_missing_tier():
    snapshot = dict(year=2, request=100., diversion=100., previous_request=100.)
    assert not is_routine_outcome(None, snapshot, 'lower_basin')
    assert not is_routine_outcome({'year': 1}, snapshot, 'lower_basin')


@pytest.mark.parametrize('basin,history', [
    ('lower_basin', 'the most water you have diverted in any year from 1971 to 2018'),
    ('upper_basin', "about the most water you have used in any year from 1971 to 2018, estimated from your sub-basin's records")])
def test_L_exact_text_X_and_P(basin, history):
    assert land_need_text(basin, 123456.2, 61728.1) == (
        'Your fields can use about 123,456 acre-ft of water a year: that is '+history+
        '. Water beyond that would have no fields to irrigate. Last year\'s delivery was 50% of that amount.')


@pytest.mark.parametrize('count,sharing', [
    (1, 'When water is short, a larger request would not add water.'),
    (2, 'When water is short it is shared in proportion to requests, so a larger request would raise your share only by lowering the deliveries of other users in your sub-basin; it would not add water to your sub-basin.')])
def test_S1_short_sharing_is_validator_sentence(count, sharing):
    ctx = dict(basin='upper_basin', current_request=100., current_diversion=80.,
               supply_physical_ratio=.8, gap_reason='ub_subbasin_supply', ub_subbasin_member_count=count,
               increase_request_af=110., increase_delivery_af=85.,
               increase_settlement={'gap_reason': 'ub_subbasin_supply'},
               supply_keep_request_af=100., supply_expected_at_keep_af=80., supply_ratio=.8)
    text = increase_expectation_text(ctx)
    assert text == 'If you increase your request to about 110 acre-ft, you can expect 85 acre-ft (77.3%) this year, for the same reason. '+sharing
    assert validators._sharing_sentence is _sharing_sentence
    assert text.endswith(validators._sharing_sentence(ctx))
    result = validators.supply_gap_block_increase('increase_demand', [], ctx)
    assert len(result) == 1 and result[0].errors[0].endswith(sharing)


def test_S1_zero_water_sharing_matches_validator():
    ctx = dict(basin='upper_basin', current_request=100., current_diversion=0.,
               supply_physical_ratio=0., supply_ratio=0.,
               supply_keep_request_af=100., supply_expected_at_keep_af=0.,
               gap_reason='ub_subbasin_supply', ub_subbasin_member_count=2,
               increase_request_af=110., increase_delivery_af=0.,
               increase_settlement={'gap_reason': 'ub_subbasin_supply'})
    sharing = 'When water is short, a larger request would not add water.'
    assert increase_expectation_text(ctx).endswith(sharing)
    result = validators.supply_gap_block_increase('increase_demand', [], ctx)
    assert result[0].errors[0].endswith(sharing)


@pytest.mark.parametrize('keep,expected', [(100., 80.), (105., 84.)])
def test_S1_physical_shortage_at_or_below_junior_ceiling_pins_retry_message(
    keep, expected,
):
    ctx = dict(basin='lower_basin', current_request=keep, current_diversion=expected,
               supply_physical_ratio=.8, supply_ratio=.8,
               supply_keep_request_af=keep, supply_expected_at_keep_af=expected,
               gap_reason='lb_mead_availability', lb_tier_ceiling_af=105.,
               increase_request_af=110., increase_delivery_af=84.,
               increase_settlement={'gap_reason': 'lb_mead_availability+lb_junior_tier_cut',
                                    'lb_junior_ceiling_af': 105.,
                                    'lb_junior_entitlement_af': 117.})
    sharing = _sharing_sentence(ctx)
    assert sharing == (
        "Lake Mead's physical shortage applies after the tier ceiling and is shared "
        "in proportion to requests capped by that ceiling: any increase above your "
        "105 acre-ft tier ceiling would add no deliverable water; within the ceiling, "
        "a larger request would raise your share only by lowering the deliveries of "
        "other users in the Lower Basin; it would not add water to the Lower Basin."
    )
    assert increase_expectation_text(ctx).endswith(sharing)
    result = validators.supply_gap_block_increase('increase_demand', [], ctx)
    assert result[0].errors == [
        "Demand increase blocked under the shortage-sharing rule: if you request the "
        f"{keep:,.0f} acre-ft you received last year, you can expect {expected:,.0f} "
        "acre-ft this year (80.0%), because Lake Mead cannot meet all Lower Basin "
        "withdrawals without falling below its minimum pool, so all Lower Basin "
        "deliveries are reduced in proportion to requests after any tier ceiling is "
        f"applied. {sharing}"
    ]


def test_S1_full_and_keep_full_increase_short_and_absent():
    ctx = dict(basin='upper_basin', current_request=100., current_diversion=100.,
               supply_physical_ratio=1., gap_reason='none', ub_subbasin_member_count=2,
               increase_request_af=110., increase_delivery_af=110.,
               increase_settlement={'gap_reason': 'none'})
    assert increase_expectation_text(ctx) == 'If you increase your request to about 110 acre-ft, you can expect full delivery this year.'
    ctx.update(increase_delivery_af=105., increase_settlement={'gap_reason': 'ub_subbasin_supply'})
    assert increase_expectation_text(ctx).endswith('because the water your sub-basin can draw this year would then be below the combined requests of its users.')
    assert increase_expectation_text(dict(ctx, increase_request_af=None)) == ''


def test_S1_junior_ceiling_states_actual_settlement_without_physical_sharing():
    env = _lb_env({'NorthBajaLLC': 200.})
    snap = _ample_supply_snapshot(env, 2)
    keep = env._settle(snap)['agents']['NorthBajaLLC']
    increased = env._settle(snap, requests={'NorthBajaLLC': 567.})['agents']['NorthBajaLLC']
    ctx = {**env.get_agent_context('NorthBajaLLC'), **keep,
           'current_request': 200., 'current_diversion': keep['delivered'],
           'supply_physical_ratio': 1., 'increase_request_af': 567.,
           'increase_delivery_af': increased['delivered'], 'increase_settlement': increased}
    text = increase_expectation_text(ctx)
    assert f"expect {increased['delivered']:,.0f} acre-ft" in text
    assert 'tier limits your junior-priority water' in text
    assert 'for the same reason' not in text
    assert 'shared' not in text


@pytest.mark.parametrize('tier', [0, 1, 2, 3])
def test_K6_current_ceiling_truth_and_volume_conservation(tier):
    table = _load_lb_priority_split_table()
    seniors = {aid: row['water_right_af'] for aid, row in table.items() if row['junior_entitlement_af'] == 0}
    assert len(seniors) == 16
    env = _lb_env({aid: row['water_right_af'] for aid, row in table.items()})
    state = env._settle(_ample_supply_snapshot(env, tier))
    for aid, request in seniors.items():
        assert state['agents'][aid]['delivered'] == request
        assert state['agents'][aid]['lb_junior_cut_af'] == 0
    reduction = env.config.lb_non_ag_total_maf - state['lb_non_ag_delivered_maf']
    assert state['lb_junior_cut_total_maf'] + reduction == pytest.approx(env._tier_shortage_volume_maf(tier))


def test_MB_basin_table_headers_and_cells():
    cfg = yaml.safe_load(CONFIG.read_text(encoding='utf-8'))['irrigation_farmer']['feedback']
    tracker = AgentMetricsTracker([m['name'] for m in cfg['tracked_metrics']])
    dashboard = FeedbackDashboardProvider(tracker, cfg)
    tracker.record('upper', 2031, dict(request=99129, supply=99129, ub_flow_share=.81, ub_winter_trend=0))
    tracker.record('lower', 2031, dict(request=188, supply=188, lb_mead_trend=1))
    upper = dashboard._render_table('upper', {}).splitlines()
    lower = dashboard._render_table('lower', {}).splitlines()
    assert upper[1] == 'Year | request (AF) | received (AF) | sub-basin river flow (% of 1971-2018 average) | sub-basin winter precipitation (vs previous winter)'
    assert lower[1] == 'Year | request (AF) | received (AF) | Lake Mead on 1 January (vs a year earlier)'
    assert [cell.strip() for cell in upper[3].split('|')] == ['2031', '99,129', '99,129', '81%', 'below']
    assert [cell.strip() for cell in lower[3].split('|')] == ['2031', '188', '188', 'higher']


def test_package_mock_prompts_match_arms_and_K6_membership(pilots):
    strict, disabled = pilots
    priority = _load_lb_priority_split_table()
    for key in strict.traces:
        prompt = strict.traces[key].prompt
        assert prompt == disabled.traces[key].prompt
        senior = key[0] in priority and priority[key[0]]['junior_entitlement_af'] == 0
        assert (K6_SENIOR_TIER_TEXT in prompt) == senior
        assert 'Your fields can use about ' in prompt
    manifest = strict.info.manifest
    assert manifest['keepfix_package']['spec_item'] == 47
    assert manifest['ollama_server_version'] is None


def test_K6_is_hidden_when_priority_mode_is_senior_all(tmp_path, monkeypatch):
    from examples.irrigation_abm import run_experiment
    real_config = WaterSystemConfig

    def senior_all_config(*args, **kwargs):
        return real_config(*args, lb_priority_mode='senior_all', **kwargs)

    monkeypatch.setattr(run_experiment, 'WaterSystemConfig', senior_all_config)
    llm = ScriptedLLM(lambda agent, year, attempt: ('M', 'M', 'Keep'))
    _run(monkeypatch, tmp_path/'senior_all', llm, '--real', '--years', '1',
         '--seed', '42', '--memory-seed', '42')
    assert llm.decisions
    assert all(K6_SENIOR_TIER_TEXT not in prompt for prompt in llm.decisions.values())


def test_S1_mock_run_uses_menu_rounded_increase_target(pilots):
    checked = 0
    for run in pilots:
        for trace in run.traces.values():
            menu = re.search(
                r'^1\. Increase your request to about ([\d,]+) acre-ft:',
                trace.prompt, re.M,
            )
            s1 = re.search(
                r'^If you increase your request to about ([\d,]+) acre-ft,',
                trace.prompt, re.M,
            )
            if menu is None:
                assert s1 is None
                continue
            assert s1 is not None
            assert s1.group(1) == menu.group(1)
            checked += 1
    assert checked > 100


def test_reflection_inputs_and_lessons_byte_identical_with_package_off(pilots, tmp_path):
    config = tmp_path/'config'
    shutil.copytree(CONFIG.parent, config)
    path = config/'agent_types.yaml'
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    data['irrigation_farmer']['keepfix_package'].update({k: False for k in ('MB', 'table', 'S1', 'L', 'K6')})
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    llm = ScriptedLLM(lambda agent, year, attempt: ('M', 'M', 'Keep'))
    with pytest.MonkeyPatch.context() as mp:
        _run(mp, tmp_path/'off', llm, '--real', '--years', '4', '--seed', '42',
             '--memory-seed', '42', '--config-dir', str(config))
    assert llm.reflections == pilots[0]._test_llm.reflections
    off = vm.load_run(tmp_path/'off', keep_prompts=True)
    for key, trace in off.traces.items():
        before = re.findall(r'^- Consolidated Reflection.*$', trace.prompt, re.M)
        after = re.findall(r'^- Consolidated Reflection.*$', pilots[0].traces[key].prompt, re.M)
        assert before == after
    key = next(k for k in off.traces if k[1] == 4 and off.sim.basin[k[0]] == 'upper_basin')
    assert re.search(r'^- Year ', off.traces[key].prompt, re.M)
    assert not re.search(r'^- Year ', pilots[0].traces[key].prompt, re.M)


def test_P5b_mock_passes_and_tampered_new_text_fails(pilots):
    for run in pilots:
        checker = vm.PromptChecker(run, vm.analysis_config(), 'recommended')
        out = vm.PromptAudit()
        for key, trace in run.traces.items():
            checker.audit(key, trace.prompt, out)
        assert out.prompts == 312
        assert out.mismatches == []
        assert out.unchecked == []
        # Exercise all new independent read-back paths with current log/profile inputs.
        key = next(k for k in run.traces if k[1] == 4 and run.sim.basin[k[0]] == 'upper_basin')
        prompt = run.traces[key].prompt
        for old, new in [('Last year\'s delivery was ', 'Last year\'s delivery was 9'),
                         ('If you increase your request to about ', 'If you increase your request to about 9'),
                         ('below', 'higher'),
                         ('sub-basin river flow (% of 1971-2018 average)', 'river flow')]:
            audit = vm.PromptAudit()
            checker.audit(key, prompt.replace(old, new, 1), audit)
            assert audit.mismatches or audit.unchecked
        key = next(k for k in run.traces if K6_SENIOR_TIER_TEXT in run.traces[k].prompt)
        audit = vm.PromptAudit()
        checker.audit(key, run.traces[key].prompt.replace(K6_SENIOR_TIER_TEXT, ''), audit)
        assert audit.mismatches
