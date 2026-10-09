"""Item 46: plain TR1 in new runs, historical 45p/45q scoring retained."""
from pathlib import Path
import pytest
from broker.interfaces.skill_types import ApprovedSkill
from broker.validators import AgentValidator
from broker.utils.agent_config import AgentTypeConfig
from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
from examples.irrigation_abm.analysis.v3_metrics import restoration_available, tr1_violation
from examples.irrigation_abm.analysis import v3_metrics as vm
from dataclasses import replace
from examples.irrigation_abm.validators.irrigation_validators import supply_gap_block_increase

CONFIG = Path(__file__).resolve().parents[1] / 'config' / 'agent_types.yaml'

@pytest.mark.parametrize('cause,available', [
    ('lb_junior_tier_cut', True), ('lb_mead_availability', False),
    ('lb_junior_tier_cut+lb_mead_availability', False),
    ('ub_subbasin_supply', False), ('none', False),
])
def test_restore_cause_is_exact(cause, available):
    assert restoration_available(cause, 4798, 3826) == available

@pytest.mark.parametrize('wsa,blocked', [('H', True), ('VH', True), ('M', False), ('L', False)])
def test_tier_only_cut_no_longer_exempts_high_scarcity_increase(monkeypatch, wsa, blocked):
    monkeypatch.setenv('GOVERNANCE_PROFILE', 'strict')
    AgentTypeConfig.clear_cache()
    env = IrrigationEnvironment(WaterSystemConfig())
    env._agents['HopiTribe'] = dict(water_right=6000., request=4798., diversion=3826.,
                                  gap_reason='lb_junior_tier_cut', mu=1., sigma=0., step_bin_af=1200.)
    env._reset_requests_to_base()
    state = env._agents['HopiTribe']
    assert 'tier_cut_restore_available' not in state
    validation = AgentValidator(config_path=str(CONFIG)).validate_thinking(
        agent_type='irrigation_farmer', agent_id='HopiTribe', decision='increase_demand',
        state=state, reasoning={'WSA_LABEL': wsa, 'ACA_LABEL': 'M'})
    assert any(not v.valid and v.metadata.get('rule_id') == 'high_scarcity_no_increase'
               for v in validation) == blocked
    if not blocked:
        result = env.execute_skill(ApprovedSkill('increase_demand', 'HopiTribe', 'APPROVED', validation))
        assert result.state_changes['request'] == 5026.
        assert 'rule_exceptions_used' not in result.action_context

@pytest.mark.parametrize('cause', ['ub_subbasin_supply', 'lb_mead_availability',
                                  'lb_junior_tier_cut+lb_mead_availability'])
def test_high_scarcity_still_blocks_after_physical_shortfall(monkeypatch, cause):
    monkeypatch.setenv('GOVERNANCE_PROFILE', 'strict')
    AgentTypeConfig.clear_cache()
    env = IrrigationEnvironment(WaterSystemConfig())
    env._agents['A'] = dict(water_right=6000., request=4798., diversion=3826., gap_reason=cause)
    env._reset_requests_to_base()
    results = AgentValidator(config_path=str(CONFIG)).validate_thinking(
        agent_type='irrigation_farmer', agent_id='A', decision='increase_demand',
        state=env._agents['A'], reasoning={'WSA_LABEL': 'H', 'ACA_LABEL': 'M'})
    assert any(not r.valid and r.metadata.get('rule_id') == 'high_scarcity_no_increase' for r in results)

def test_posthoc_exception_uses_previous_shortfall_without_resulting_request():
    kwargs = dict(previous_gap_reason='lb_junior_tier_cut', previous_request_af=4798, base_af=3826)
    assert not tr1_violation('increase_demand', 'H', **kwargs)
    assert tr1_violation('increase_demand', 'H', previous_gap_reason='lb_junior_tier_cut',
                         previous_request_af=3826, base_af=3826)
    assert not tr1_violation('increase_demand', 'M', **kwargs)

def test_supply_rule_still_blocks_with_restoration_available():
    from examples.irrigation_abm.tests.test_v3_governance import _supply_ctx
    context = _supply_ctx(basin='lower_basin', physical=.85)
    context['tier_cut_restore_available'] = True
    assert supply_gap_block_increase('increase_demand', [], context)

@pytest.mark.parametrize('coupling', [False, True])
def test_new_run_records_ceiling_sensitivity_and_no_restore_exception(monkeypatch, tmp_path, coupling):
    import csv
    import json
    from examples.irrigation_abm.tests.test_v3_governance import (
        _REAL_REF_AVAILABLE, _run_main, ScriptedIrrigationLLM,
    )
    if not _REAL_REF_AVAILABLE:
        pytest.skip('CRSS reference data unavailable')
    llm = ScriptedIrrigationLLM(lambda a, y, attempt, menu: (
        'H', 'M', 'Increase' if attempt == 0 else 'Keep'))
    out = _run_main(monkeypatch, tmp_path/'ceiling', llm, '--real', '--years', '3', '--seed', '42',
                    *(['--coupling'] if coupling else []))
    with (out/'irrigation_farmer_governance_audit.csv').open(encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    assert not any(r.get('rule_exceptions_used') for r in rows)
    assert all('state_tier_cut_restore_available' not in r for r in rows)
    assert all('state_previous_gap_reason' not in r and 'state_previous_request_af' not in r
               for r in rows)
    manifest = json.loads((out/'reproducibility_manifest.json').read_text())
    assert 'tier_cut_restore' not in manifest
    assert manifest['lb_p56_in_tier'] == 'zero'
    run = vm.load_run(out, keep_prompts=True)
    assert all(not d.tier_cut_restore_enabled for d in run.decisions.values())
    assert vm.rule_agreement(run)['high_scarcity_no_increase']['disagreements'] == 0

@pytest.mark.parametrize('previous_request,violations', [(4798., 0), (3826., 1)])
def test_all_ibr_variants_use_restoration_helper(previous_request, violations):
    d = vm.Decision(agent_id='HopiTribe', year=3, status='APPROVED', execution_path='approved',
        executed_skill='increase_demand', proposed_skill='increase_demand',
        attempts=(vm.Attempt('increase_demand', {'WSA_LABEL': 'H'}, ()),), retry_count=0,
        format_retries=0, llm_success=True, keep_request_af=3826., expected_at_keep_af=3000.,
        supply_ratio=.8, physical_ratio=1., first_wsa='H', first_aca='M', final_wsa='H',
        wsa_relabeled=False, error_messages='', timestamp='', previous_gap_reason='lb_junior_tier_cut',
        previous_request_af=previous_request,
        tier_cut_restore_enabled=True)
    metrics = vm.ibr_metrics([d])
    for key in ('ibr_tr1_count', 'ibr_first_proposal_tr1_count', 'ibr_executed_tr1_count'):
        assert metrics[key] == violations
    assert metrics['ibr_final_label_tr1_pct'] == 100 * violations
    assert d.tr1('increase_demand', 'H') == tr1_violation('increase_demand', 'H',
        previous_gap_reason='lb_junior_tier_cut', previous_request_af=previous_request, base_af=3826.)
    stepped = replace(d, attempts=(*d.attempts, vm.Attempt(None, None, None)), retry_count=1, final_wsa=None)
    assert vm.ibr_metrics([stepped])['ibr_stepback_violations_n'] == violations

def test_new_tr1_config_needs_no_exception_flag(monkeypatch):
    from examples.irrigation_abm.run_experiment import _validate_exception_state_fields
    monkeypatch.setenv('GOVERNANCE_PROFILE', 'strict')
    AgentTypeConfig.clear_cache()
    config = AgentTypeConfig.load(str(CONFIG))
    _validate_exception_state_fields(config, {})
