"""Opt-in memory/dashboard contracts for spec item 47."""
import json
from types import SimpleNamespace

import pytest

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.components.analytics.feedback import AgentMetricsTracker, FeedbackDashboardProvider


def engine(**kwargs):
    e = HumanCentricMemoryEngine(window_size=3, top_k_significant=2,
                                deterministic_consolidation=True, seed=42, **kwargs)
    for text, routine in [('old routine', True), ('old event', False),
                          ('recent routine', True), ('recent event', False),
                          ('lesson', False)]:
        e.add_memory('a', text, {'importance': .8, 'routine': routine})
    return e


def test_memory_skip_default_byte_identity_and_reflection_override():
    a = SimpleNamespace(id='a')
    baseline = engine().retrieve(a)
    assert json.dumps(engine(recall_skip_key=None).retrieve(a)) == json.dumps(baseline)
    filtered = engine(recall_skip_key='routine')
    assert [m['content'] for m in filtered.retrieve(a)] == ['old event', 'recent event', 'lesson']
    assert json.dumps(filtered.retrieve(a, reflection_slot=None, recall_skip_key=None)) == json.dumps(baseline)
    assert filtered.recall_skip_key == 'routine'


def test_memory_skip_empty_fallback_and_weighted_fail_loud():
    e = HumanCentricMemoryEngine(recall_skip_key='routine')
    e.add_memory('a', 'record exists', {'routine': True})
    assert e.retrieve(SimpleNamespace(id='a'))[0]['content'] == 'record exists'
    with pytest.raises(ValueError, match='weighted'):
        HumanCentricMemoryEngine(recall_skip_key='routine', ranking_mode='weighted')


def test_dashboard_options_default_bytes_and_missing_values():
    cfg = {'tracked_metrics': [{'name': 'request', 'unit': 'AF', 'format': ',.0f'}],
           'show_trend': False}
    tracker = AgentMetricsTracker(['request'])
    base = FeedbackDashboardProvider(tracker, cfg)
    tracker.record('a', 2020, {'request': 100})
    before = base._render_table('a', {})
    explicit = FeedbackDashboardProvider(tracker, {'tracked_metrics': [
        dict(cfg['tracked_metrics'][0], only_if_recorded=False, value_labels={})]})
    assert explicit._render_table('a', {}).encode() == before.encode()
    cfg['tracked_metrics'].append({'name': 'signal', 'label': 'winter precipitation',
        'unit': 'vs previous winter', 'only_if_recorded': True,
        'value_labels': {0: 'below', 1: 'above'}})
    tracker = AgentMetricsTracker(['request', 'signal'])
    dashboard = FeedbackDashboardProvider(tracker, cfg)
    tracker.record('upper', 2020, {'request': 100, 'signal': 0})
    tracker.record('lower', 2020, {'request': 100})
    assert 'below' in dashboard._render_table('upper', {})
    assert 'signal' not in tracker.get_history('lower')[0]
    assert dashboard._render_table('lower', {}) == before


def test_optional_trends_use_only_recorded_samples_and_hide_absent_metrics():
    tracker = AgentMetricsTracker(['request', 'signal'])
    dashboard = FeedbackDashboardProvider(tracker, {'tracked_metrics': [
        {'name': 'request'}, {'name': 'signal', 'only_if_recorded': True}]})
    tracker.record('a', 2020, {'request': 100, 'signal': 10})
    tracker.record('a', 2021, {'request': 100})
    tracker.record('a', 2022, {'request': 100, 'signal': 10})
    tracker.record('b', 2020, {'request': 100})
    tracker.record('b', 2021, {'request': 100})
    assert tracker.compute_trends('a')['signal'] == 'stable'
    assert 'signal' not in tracker.compute_trends('b')
    context = {}
    dashboard.provide('b', {}, context)
    assert context['feedback_dashboard'].endswith('TREND: request STABLE')
    assert 'signal' not in context['feedback_dashboard']


@pytest.mark.parametrize('skip_key', [None, 'different'])
def test_MB_requires_routine_skip_key_at_startup(skip_key):
    from examples.irrigation_abm import run_experiment as runner
    config = {'irrigation_farmer': {'keepfix_package': {'MB': True}},
              'global_config': {'memory': {'recall_skip_key': skip_key}}}
    with pytest.raises(ValueError, match='recall_skip_key.*routine'):
        runner._validate_keepfix_config(config)


def test_keepfix_rejects_unknown_keys_and_invalid_tier_scope():
    from examples.irrigation_abm import run_experiment as runner
    for package in [{'typo': True}, {'routine_tier_scope': 'unknown'}]:
        with pytest.raises(ValueError, match='keepfix_package'):
            runner._validate_keepfix_config({'irrigation_farmer': {'keepfix_package': package}})
    resolved = runner._validate_keepfix_config({})
    assert resolved['routine_tier_scope'] == 'any_tier'


@pytest.mark.parametrize('model', ['mock', 'MOCK:custom', 'openai:gpt-test', 'anthropic:claude-test'])
def test_keepfix_version_never_queries_mock_or_cloud(model, monkeypatch):
    import urllib.request
    from examples.irrigation_abm import run_experiment as runner
    def forbidden(*args, **kwargs):
        pytest.fail('mock/cloud version query reached network')
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    assert runner._read_ollama_server_version(model) is None


def test_keepfix_provenance_uses_launch_version_and_guards_each_file(tmp_path, monkeypatch, capsys):
    import yaml
    from pathlib import Path
    from examples.irrigation_abm import run_experiment as runner
    manifest = tmp_path / 'reproducibility_manifest.json'
    snapshot = tmp_path / 'config_snapshot.yaml'
    manifest.write_text('{}', encoding='utf-8')
    snapshot.write_text('{}', encoding='utf-8')
    runner._record_keepfix_provenance(tmp_path, {'MB': True, 'routine_tier_scope': 'affects_agent'}, 'launch-version')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    metadata = yaml.safe_load(snapshot.read_text(encoding='utf-8'))['metadata']
    assert data['ollama_server_version'] == metadata['ollama_server_version'] == 'launch-version'
    assert data['keepfix_package']['routine_tier_scope'] == 'affects_agent'
    original = Path.write_text
    def fail_manifest(self, *args, **kwargs):
        if self == manifest:
            raise OSError('manifest blocked')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', fail_manifest)
    runner._record_keepfix_provenance(tmp_path, {}, None)
    assert 'WARNING' in capsys.readouterr().out
    assert yaml.safe_load(snapshot.read_text(encoding='utf-8'))['metadata']['ollama_server_version'] is None


def test_memory_provenance_records_resolved_skip_key(tmp_path):
    import yaml
    from examples.irrigation_abm.run_experiment import _record_memory_options_provenance
    (tmp_path / 'reproducibility_manifest.json').write_text('{}', encoding='utf-8')
    (tmp_path / 'config_snapshot.yaml').write_text('{}', encoding='utf-8')
    _record_memory_options_provenance(tmp_path, engine(recall_skip_key='routine'))
    assert json.loads((tmp_path / 'reproducibility_manifest.json').read_text())['recall_skip_key'] == 'routine'
    assert yaml.safe_load((tmp_path / 'config_snapshot.yaml').read_text())['metadata']['recall_skip_key'] == 'routine'


def test_routine_tier_scope_controls_visible_lines_and_csv_stays_unfiltered(tmp_path):
    import csv
    import re
    import shutil
    import yaml
    from examples.irrigation_abm.tests.test_v3_prompt import CONFIG, ScriptedLLM, _run, _REAL_REF_AVAILABLE
    if not _REAL_REF_AVAILABLE:  # CI has no CRSS data under ref/ (same skip as test_v3_prompt's needs_ref)
        pytest.skip("CRSS reference data not found under ref/")
    runs = {}
    for scope in ('any_tier', 'affects_agent'):
        config = tmp_path / scope / 'config'
        shutil.copytree(CONFIG.parent, config)
        path = config / 'agent_types.yaml'
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
        data['irrigation_farmer']['keepfix_package']['routine_tier_scope'] = scope
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
        llm = ScriptedLLM(lambda agent, year, attempt: ('M', 'M', 'Keep'))
        with pytest.MonkeyPatch.context() as mp:
            _run(mp, tmp_path / scope / 'run', llm, '--real', '--years', '4',
                 '--seed', '42', '--memory-seed', '42', '--config-dir', str(config))
        runs[scope] = llm
    senior = ('WelltonMohawkIDD', 2021, 0)
    line = r'^- Year 2020:.*$'
    assert re.search(line, runs['any_tier'].decisions[senior], re.M)
    assert not re.search(line, runs['affects_agent'].decisions[senior], re.M)
    junior = ('NorthBajaLLC', 2021, 0)
    assert re.findall(line, runs['any_tier'].decisions[junior], re.M) == re.findall(
        line, runs['affects_agent'].decisions[junior], re.M)
    assert re.search(line, runs['affects_agent'].decisions[junior], re.M)
    with (tmp_path / 'affects_agent/run/simulation_log.csv').open(encoding='utf-8') as stream:
        row = next(r for r in csv.DictReader(stream) if r['agent_id'] == senior[0] and r['year'] == '3')
    assert 'Year 2020:' in row['memory']
