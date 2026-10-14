"""Round-2 startup, recording and cross-arm text invariants (mock only)."""
import csv
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from examples.irrigation_abm import irrigation_personas as text
from examples.irrigation_abm import run_experiment as runner
from examples.irrigation_abm.tests.test_v3_prompt import CONFIG, ScriptedLLM, _run

VARIANTS = CONFIG.parent.parent / 'config_variants'


def test_checker_scans_simulation_memory_and_reports_feedback_families(tmp_path, capsys):
    from examples.irrigation_abm.analysis.simple_prompt_check import check_run, main
    (tmp_path / 'raw').mkdir()
    (tmp_path / 'raw/irrigation_farmer_traces.jsonl').write_text(
        json.dumps({'agent_id': 'A', 'year': 2020, 'input': 'Clean decision.'}) + '\n')
    removed = 'When water is short, a larger request would not add water.'
    with (tmp_path / 'simulation_log.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['agent_id', 'year', 'memory'])
        writer.writeheader()
        writer.writerow({'agent_id': 'A', 'year': 2020, 'memory': removed})
    assert {hit.family for hit in check_run(tmp_path).occurrences} == {'sharing_sentence'}
    with (tmp_path / 'irrigation_farmer_governance_audit.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['agent_id', 'year', 'error_messages'])
        writer.writeheader()
        writer.writerow({'agent_id': 'A', 'year': 2020, 'error_messages': removed})
    assert main([str(tmp_path)]) == 1
    assert 'retry feedback (unchanged by design)\tsharing_sentence\t1' in capsys.readouterr().out


def test_reflection_log_failure_preserves_call_and_reply(tmp_path, capsys):
    (tmp_path / 'reflection_prompts.jsonl').mkdir()
    hooks = runner.IrrigationLifecycleHooks(SimpleNamespace(), None, [], None, tmp_path)
    seen = []
    reply = object()
    invoke = hooks._record_reflection_call(lambda prompt: seen.append(prompt) or reply, ['A'], 2029)
    assert invoke('exact prompt') is reply
    assert invoke('retry prompt') is reply
    assert seen == ['exact prompt', 'retry prompt']
    assert hooks.reflection_prompt_log_complete is False
    assert capsys.readouterr().out.count('WARNING') == 1


def test_reflection_log_failure_reaches_manifest(tmp_path, monkeypatch):
    original = Path.open

    def fail_recorder(path, mode='r', *args, **kwargs):
        if path.name == 'reflection_prompts.jsonl' and mode == 'a':
            raise PermissionError('test recorder failure')
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', fail_recorder)
    llm = ScriptedLLM(lambda *args: ('M', 'M', 'Keep'))
    out = _run(monkeypatch, tmp_path / 'run', llm, '--years', '1', '--agents', '2')
    assert llm.reflections
    manifest = json.loads((out / 'reproducibility_manifest.json').read_text())
    assert manifest['reflection_prompt_log_complete'] is False


def test_missing_applied_memory_config_fails_before_calls(tmp_path, monkeypatch):
    original = runner.ExperimentBuilder.build

    def without_memory_config(builder):
        result = original(builder)
        for agent in builder.agents.values():
            agent.memory_config = {}
        return result

    monkeypatch.setattr(runner.ExperimentBuilder, 'build', without_memory_config)
    llm = ScriptedLLM(lambda *args: ('M', 'M', 'Keep'))
    with pytest.raises(RuntimeError, match=r'memory_config.*composed_retrieval'):
        _run(monkeypatch, tmp_path / 'run', llm, '--years', '1', '--agents', '2')
    assert not llm.decisions and not llm.reflections


@pytest.mark.parametrize('key', ['window_size', 'top_k_significant', 'ranking_mode',
                                 'runner_decision_line', 'rejection_line_style'])
def test_memory_config_guard_checks_text_affecting_keys(key):
    cfg = yaml.safe_load(CONFIG.read_text())['irrigation_farmer']['memory']
    applied = dict(cfg)
    applied.pop(key)
    with pytest.raises(RuntimeError, match=key):
        runner._validate_agent_memory_config({'A': SimpleNamespace(memory_config=applied)}, cfg)


@pytest.mark.parametrize('level', [None, 'full'])
def test_full_level_rejects_simple_template(tmp_path, monkeypatch, level):
    config_dir = tmp_path / 'mixed'
    shutil.copytree(CONFIG.parent, config_dir)
    config = yaml.safe_load((config_dir / 'agent_types.yaml').read_text())
    if level is not None:
        config['irrigation_farmer']['prompt_information'] = level
    (config_dir / 'agent_types.yaml').write_text(yaml.safe_dump(config), encoding='utf-8')
    (config_dir / 'prompts/irrigation_farmer.txt').write_text(runner.SIMPLE_PROMPT_TEMPLATE, encoding='utf-8')
    llm = ScriptedLLM(lambda *args: ('M', 'M', 'Keep'))
    with pytest.raises(ValueError, match='prompt_information'):
        _run(monkeypatch, tmp_path / 'run', llm, '--years', '1', '--config-dir', str(config_dir))
    assert not llm.decisions and not llm.reflections


@pytest.mark.parametrize('builder,args', [
    (text.build_water_situation_text, ({},)),
    (text._lower_basin_tier_text, ({},)),
    (text.build_option_notes, (True, True, None)),
    (text.build_action_outcome_feedback, (None, 2019, 1, 1, 1)),
])
def test_text_builders_reject_unknown_level(builder, args):
    with pytest.raises(ValueError, match='prompt_information'):
        builder(*args, prompt_information='Simple')


@pytest.mark.parametrize('level', ['full', 'simple'])
def test_all_keep_memory_and_reflection_inputs_match_between_arms(tmp_path, level):
    outputs = {}
    for mode in ('strict', 'disabled'):
        llm = ScriptedLLM(lambda *args: ('M', 'M', 'Keep'))
        with pytest.MonkeyPatch.context() as mp:
            args = ['--years', '4', '--agents', '4', '--seed', '42', '--memory-seed', '42',
                    '--governance-mode', mode]
            if level == 'simple':
                args += ['--config-dir', str(VARIANTS / 'simple')]
            out = _run(mp, tmp_path / mode, llm, *args)
        with (out / 'simulation_log.csv').open(newline='') as stream:
            memories = {(row['agent_id'], row['year']): row['memory'] for row in csv.DictReader(stream)}
        rows = [json.loads(line) for line in (out / 'reflection_checks.jsonl').read_text().splitlines()]
        inputs = {(r['agent_id'], r['period'], r['attempt']): r['reflection_input'] for r in rows}
        assert memories and inputs
        outputs[mode] = memories, inputs, llm.reflections
    assert outputs['strict'] == outputs['disabled']
