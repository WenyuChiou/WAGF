"""Spec 45p/45q: a tier-only exception with the ordinary H&Y increase."""
from pathlib import Path
import pytest
from broker.interfaces.skill_types import ApprovedSkill
from broker.validators import AgentValidator
from broker.utils.agent_config import AgentTypeConfig
from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
from examples.irrigation_abm.junior_restore import restoration_available, tr1_violation
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

@pytest.mark.parametrize('wsa,step,expected,used', [
    ('H', 1200, 5026, True), ('VH', 46, 3872, True),
    ('M', 1200, 5026, False), ('L', 1200, 5026, False),
    ('H', 3000, 6000, True),
])
def test_strict_excepted_increase_uses_ordinary_step_and_water_right_cap(monkeypatch, wsa, step, expected, used):
    monkeypatch.setenv('GOVERNANCE_PROFILE', 'strict')
    AgentTypeConfig.clear_cache()
    env = IrrigationEnvironment(WaterSystemConfig())
    env._agents['HopiTribe'] = dict(water_right=6000., request=4798., diversion=3826.,
                                  gap_reason='lb_junior_tier_cut', mu=1., sigma=0.,
                                  step_bin_af=step)
    env._reset_requests_to_base()
    state = env._agents['HopiTribe']
    validation = AgentValidator(config_path=str(CONFIG)).validate_thinking(
        agent_type='irrigation_farmer', agent_id='HopiTribe', decision='increase_demand',
        state=state, reasoning={'WSA_LABEL': wsa, 'ACA_LABEL': 'M'})
    assert all(v.valid for v in validation)
    result = env.execute_skill(ApprovedSkill('increase_demand', 'HopiTribe', 'APPROVED', validation))
    assert result.state_changes['request'] == expected
    assert result.state_changes['magnitude_af'] == expected - 3826
    assert result.action_context['magnitude_pct'] == pytest.approx(100 * (expected - 3826) / 3826)
    assert bool(result.action_context.get('rule_exceptions_used')) == used
    assert 'rule_exceptions_used' in result.action_context
    assert not tr1_violation('increase_demand', wsa, previous_gap_reason='lb_junior_tier_cut',
                             previous_request_af=4798, base_af=3826)

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
def test_e2e_tier_restore_is_audited_and_counted(monkeypatch, tmp_path, coupling):
    import csv
    import json
    from examples.irrigation_abm.tests.test_v3_governance import (
        _REAL_REF_AVAILABLE, _run_main, ScriptedIrrigationLLM,
    )
    if not _REAL_REF_AVAILABLE:
        pytest.skip('CRSS reference data unavailable')
    llm = ScriptedIrrigationLLM(lambda a, y, attempt, menu: (
        'H', 'M', 'Increase' if attempt == 0 else 'Keep'))
    out = _run_main(monkeypatch, tmp_path / 'restore', llm, '--real', '--years', '3', '--seed', '42',
                    *(['--coupling'] if coupling else []))
    with (out / 'irrigation_farmer_governance_audit.csv').open(encoding='utf-8-sig', newline='') as fh:
        rows = list(csv.DictReader(fh))
    uses = [r for r in rows if r.get('rule_exceptions_used') == 'high_scarcity_no_increase']
    assert uses
    manifest = json.loads((out / 'reproducibility_manifest.json').read_text(encoding='utf-8'))
    tally = manifest['tier_cut_restore']
    assert tally['total_uses'] == len(uses) == sum(tally['uses_per_year'].values())
    run = vm.load_run(out, keep_prompts=True)
    for row in uses:
        key = (row['agent_id'], int(row['year']))
        d = run.decisions[key]
        assert not d.tr1(d.executed_skill, d.first_wsa, executed=True)
        assert run.sim.num(d.agent_id, d.year, 'request') <= run.sim.num(d.agent_id, d.year, 'water_right')
        assert row['rules_triggered'] == row['rules_self_report'] == ''
        assert int(row['rules_thinking_hit']) == 0
        assert 'high_scarcity_no_increase' not in row['attempt_failed_rules'].split('|')[0]
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

def test_irrigation_startup_rejects_unpublished_exception_flag(monkeypatch):
    from examples.irrigation_abm.run_experiment import _validate_exception_state_fields
    monkeypatch.setenv('GOVERNANCE_PROFILE', 'strict')
    config = AgentTypeConfig.load(str(CONFIG))
    with pytest.raises(ValueError, match='tier_cut_restore_available.*not published'):
        _validate_exception_state_fields(config, {})
    _validate_exception_state_fields(config, {'tier_cut_restore_available': False})

@pytest.mark.parametrize('failure', ['malformed', 'write'])
def test_restore_provenance_failure_never_fails_the_run(tmp_path, monkeypatch, capsys, failure):
    from examples.irrigation_abm.run_experiment import _record_tier_cut_restore_provenance
    manifest = tmp_path / 'reproducibility_manifest.json'
    manifest.write_text('{' if failure == 'malformed' else '{}', encoding='utf-8')
    if failure == 'write':
        original = Path.write_text
        def fail_write(path, *args, **kwargs):
            if path == manifest:
                raise OSError('read-only provenance')
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, 'write_text', fail_write)
    _record_tier_cut_restore_provenance(tmp_path, {'2021': 1})
    assert 'WARNING: could not record tier_cut_restore' in capsys.readouterr().out
