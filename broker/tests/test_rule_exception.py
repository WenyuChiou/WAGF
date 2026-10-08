"""Generic thinking-rule exception flag is opt-in and requires bool True."""
import copy
import pytest
import yaml
from broker.utils.agent_config import AgentTypeConfig
from broker.validators import AgentValidator
from broker.components.analytics.audit import trace_to_csv_row, GenericAuditWriter, AuditConfig
from broker.core._audit_helpers import _safe_triggered_rules, _safe_rules_by_grounding
from broker.validators.governance import get_rule_breakdown, _infer_category
from broker.interfaces.skill_types import ValidationResult

CONFIG = {'test_agent': {'governance': {'strict': {'thinking_rules': [{
    'id': 'test_rule', 'conditions': [{'construct': 'TEST_LABEL', 'values': ['H']}],
    'blocked_skills': ['increase'], 'level': 'ERROR', 'message': 'blocked',
}]}}}}

@pytest.mark.parametrize('configured,flag,blocked', [
    (False, True, True), (True, True, False), (True, False, True),
    (True, 'true', True), (True, 1, True), (True, None, True),
])
def test_rule_exception_is_opt_in_boolean(monkeypatch, tmp_path, configured, flag, blocked):
    raw = copy.deepcopy(CONFIG)
    rule = raw['test_agent']['governance']['strict']['thinking_rules'][0]
    if configured:
        rule['exception_precondition'] = 'restoration_available'
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(raw), encoding='utf-8')
    monkeypatch.setenv('GOVERNANCE_PROFILE', 'strict')
    AgentTypeConfig.clear_cache()
    results = AgentValidator(config_path=str(path)).validate_thinking(
        agent_type='test_agent', agent_id='A', decision='increase',
        state={'restoration_available': flag}, reasoning={'TEST_LABEL': 'H'})
    assert any(not r.valid for r in results) == blocked
    exceptions = [r for r in results if r.metadata.get('exception_used')]
    assert bool(exceptions) == (configured and flag is True)
    if exceptions:
        assert exceptions[0].errors == exceptions[0].warnings == []

def test_exception_audit_column_is_key_gated():
    trace = {'execution_result': {'action_context': {'rule_exceptions_used': ['a_rule']}}}
    assert trace_to_csv_row(trace)['rule_exceptions_used'] == 'a_rule'
    assert 'rule_exceptions_used' not in trace_to_csv_row({})
    assert trace_to_csv_row({'execution_result': {'action_context': {
        'rule_exceptions_used': []}}})['rule_exceptions_used'] == ''

def test_exception_does_not_count_as_a_rule_hit_or_health_observation(tmp_path):
    result = ValidationResult(valid=True, validator_name='AgentValidator:thinking_exception',
        metadata={'rule_id': 'test_rule', 'exception_used': True, 'category': 'thinking'})
    assert _safe_triggered_rules([[result]]) == []
    assert _safe_rules_by_grounding([[result]]) == ([], [])
    assert get_rule_breakdown([result])['thinking'] == 0
    assert get_rule_breakdown([result], allow_metadata_fallback=True)['thinking'] == 0
    assert _infer_category(result.metadata, result.validator_name) == ''
    writer = GenericAuditWriter(AuditConfig(output_dir=tmp_path))
    writer.write_trace('test_agent', {'agent_id': 'A', 'year': 1}, [result])
    assert writer.summary['validator_health'] == {}
    assert getattr(writer, '_validator_health_by_type', {}) == {}
    row = trace_to_csv_row({'triggered_rules': _safe_triggered_rules([[result]]),
        'rules_world_grounded': '',
        'rule_breakdown': get_rule_breakdown([result], allow_metadata_fallback=True),
        'rules_self_report': '|'.join(_safe_rules_by_grounding([[result]])[1])})
    assert row['rules_triggered'] == row['rules_self_report'] == ''
    assert row['rules_thinking_hit'] == 0

@pytest.mark.parametrize('kind', ['identity_rules', 'personal_rules', 'social_rules', 'physical_rules'])
def test_unsupported_rule_exception_fails_at_config_load(tmp_path, kind):
    raw = {'test_agent': {'governance': {'strict': {kind: [{
        'id': 'test_rule', 'exception_precondition': 'available'}]}}}}
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(raw), encoding='utf-8')
    with pytest.raises(ValueError, match='exception_precondition.*thinking_rules'):
        AgentTypeConfig.load(str(path))

def test_non_exception_results_keep_existing_audit_semantics():
    result = ValidationResult(valid=False, validator_name='AgentValidator:thinking',
        metadata={'rule_id': 'test_rule', 'category': 'thinking'})
    assert _safe_triggered_rules([[result]]) == ['test_rule']
    assert _safe_rules_by_grounding([[result]]) == ([], ['test_rule'])
    assert get_rule_breakdown([result])['thinking'] == 1
