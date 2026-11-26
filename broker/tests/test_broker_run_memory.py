"""broker.run builds the memory engine and runs reflection the YAML asks for.

global_config.memory.engine_type picks window (default) or humancentric;
window_size caps the window engine only when written; reflection runs only
with global_config.reflection.enabled: true. With none of these keys a run is
as before (the mock byte-identity check in the PR covers that).
"""
from __future__ import annotations

import json
import sys
from textwrap import dedent
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.components.memory.engines.window import WindowMemoryEngine
from broker.run import _entry, _memory, main


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.fixture
def case(tmp_path, monkeypatch):
    folder = tmp_path / f"case_{uuid4().hex}"
    config_path = folder / "config" / "agent_types.yaml"
    config_path.parent.mkdir(parents=True)
    (folder / "__init__.py").touch()
    (folder / "world.py").write_text(dedent('''
        from broker.interfaces.skill_types import ExecutionResult

        class World:
            year = 0

            def advance_step(self):
                self.year += 1
                return {"current_year": self.year}

            def execute_skill(self, approved_skill):
                return ExecutionResult(success=True, state_changes={})

        def build(ctx):
            return World()
    '''), encoding="utf-8")
    _write_yaml(config_path.with_name("skill_registry.yaml"), {
        "default_skill": "wait",
        "skills": [
            {"skill_id": "wait", "description": "Wait for the next year"},
            {"skill_id": "inspect", "description": "Inspect the site"},
        ],
    })
    data = {
        "global_config": {"run": {"world": "world:build"}},
        "agent": {
            "psychological_framework": "generic",
            "prompt_template": "Memory:\n{memory}\n\nAvailable actions\n{options_text}\n\n{response_format}",
            "actions": [{"id": "wait", "aliases": ["1"]}, {"id": "inspect", "aliases": ["2"]}],
            "parsing": {"skill_map": {"1": "wait", "2": "inspect"}},
            "response_format": {
                "delimiter_start": "<<<DECISION_START>>>",
                "delimiter_end": "<<<DECISION_END>>>",
                "fields": [{"key": "decision", "type": "choice", "required": True}],
            },
        },
    }
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    yield config_path, data
    for name in list(sys.modules):
        if name == folder.name or name.startswith(f"{folder.name}."):
            sys.modules.pop(name, None)


def _argv(config, output, years=3):
    return [str(config), "--model", "mock", "--years", str(years), "--agents", "1", "--output", str(output)]


def _prepare(case, tmp_path, years=3, memory=None, reflection=None):
    config, data = case
    if memory is not None:
        data["global_config"]["memory"] = memory
    if reflection is not None:
        data["global_config"]["reflection"] = reflection
    _write_yaml(config, data)
    output = tmp_path / "output"
    return _entry.prepare(_argv(config, output, years)), output


def _decisions(output):
    lines = (output / "raw" / "agent_traces.jsonl").read_text(encoding="utf-8").splitlines()
    return [record for record in map(json.loads, lines) if "step_id" in record]


def _prompt(output, year):
    return next(r["input"] for r in _decisions(output) if r["year"] == year)


def _record(output):
    return json.loads((output / "broker_run.json").read_text(encoding="utf-8"))


def _run(case, tmp_path, years=3, memory=None, reflection=None):
    config, data = case
    if memory is not None:
        data["global_config"]["memory"] = memory
    if reflection is not None:
        data["global_config"]["reflection"] = reflection
    _write_yaml(config, data)
    output = tmp_path / "output"
    assert main(_argv(config, output, years)) == 0
    return output


# --- memory engine choice ---------------------------------------------------

def test_no_memory_keys_builds_the_uncapped_window_engine_and_records_it(case, tmp_path):
    prepared, _ = _prepare(case, tmp_path)
    engine = prepared.runner.memory_engine
    assert type(engine) is WindowMemoryEngine
    assert engine.enforce_window is False and engine.window_size == _entry.DEFAULT_WINDOW_SIZE
    output = _run(case, tmp_path)
    assert _record(output)["memory"] == {"engine": "window", "window_size": None,
                                         "retrieval_top_k": {"agent": 3}}


def test_window_size_written_in_the_yaml_caps_what_the_prompt_holds(case, tmp_path):
    output = _run(case, tmp_path, years=3, memory={"engine_type": "window", "window_size": 1})
    memory_lines = [line for line in _prompt(output, 3).split("Available actions")[0].splitlines()
                    if "Year " in line]
    assert len(memory_lines) == 1 and "Year 2" in memory_lines[0]
    assert _record(output)["memory"] == {"engine": "window", "window_size": 1,
                                         "retrieval_top_k": {"agent": 3}}


@pytest.mark.parametrize("name", ["humancentric", "human_centric", "HumanCentric"])
def test_humancentric_engine_type_builds_humancentric_with_broker_run_defaults(case, tmp_path, name):
    prepared, _ = _prepare(case, tmp_path, memory={"engine_type": name})
    engine = prepared.runner.memory_engine
    assert isinstance(engine, HumanCentricMemoryEngine)
    assert (engine.window_size, engine.top_k_significant, engine.ranking_mode) == (3, 2, "legacy")
    assert engine.seed == 42  # the run seed, so consolidation repeats run to run


def test_humancentric_yaml_values_win_and_reach_the_run_record(case, tmp_path):
    memory = {"engine_type": "humancentric", "window_size": 4, "top_k_significant": 1,
              "consolidation_threshold": 0.5, "seed": 7, "ranking_mode": "weighted"}
    prepared, _ = _prepare(case, tmp_path, memory=memory)
    engine = prepared.runner.memory_engine
    assert (engine.window_size, engine.top_k_significant, engine.consolidation_threshold,
            engine.seed, engine.ranking_mode) == (4, 1, 0.5, 7, "weighted")
    output = _run(case, tmp_path, years=1, memory=memory)
    assert _record(output)["memory"] == {
        "engine": "humancentric", "window_size": 4, "top_k_significant": 1, "ranking_mode": "weighted",
        "seed": 7, "consolidation_threshold": 0.5, "retrieval_top_k": {"agent": 3},
    }


@pytest.mark.parametrize("memory, message", [
    ({"engine_type": "universal"}, "research engine"),
    ({"engine_type": "hierarchical"}, "deprecated"),
    ({"engine_type": "importance"}, "deprecated"),
    ({"engine_type": "vector"}, "not a memory engine"),
    ({"engine_type": 3}, "must be a string"),
    ({"window_size": 0}, "window_size must be an integer >= 1"),
    ({"window_size": "5"}, "window_size must be an integer >= 1"),
    ({"engine_type": "humancentric", "ranking_mode": "fast"}, "legacy or weighted"),
    ({"engine_type": "humancentric", "top_k_significant": -1}, "top_k_significant"),
    ({"engine_type": "humancentric", "window_size": 0}, "window_size must be an integer >= 1"),
    ({"engine_type": "humancentric", "decay_rate": 2}, "decay_rate"),
    # The decision memories ExperimentRunner writes carry no year, so the
    # engine would raise on the year-2 retrieval; refused before the run.
    ({"engine_type": "humancentric", "decay_by_calendar_year": True},
     "decay_by_calendar_year needs a year on every memory"),
])
def test_memory_settings_broker_run_cannot_honour_are_refused(case, tmp_path, capsys, memory, message):
    config, data = case
    data["global_config"]["memory"] = memory
    _write_yaml(config, data)
    assert main(_argv(config, tmp_path / "output")) == 2
    assert message in capsys.readouterr().err


def test_window_engine_cap_is_opt_in():
    agent = SimpleNamespace(id="a", memory=[])
    uncapped, capped = WindowMemoryEngine(window_size=2), WindowMemoryEngine(window_size=2, enforce_window=True)
    for engine in (uncapped, capped):
        for year in range(1, 6):
            engine.add_memory("a", f"Year {year}")
    assert uncapped.retrieve(agent, top_k=4) == ["Year 2", "Year 3", "Year 4", "Year 5"]
    assert capped.retrieve(agent, top_k=4) == ["Year 4", "Year 5"]
    assert capped.storage["a"] == ["Year 4", "Year 5"]
    with pytest.raises(ValueError, match="window_size"):
        WindowMemoryEngine(window_size=0, enforce_window=True)


# --- reflection on and off ---------------------------------------------------

def test_reflection_block_without_enabled_runs_no_reflection(case, tmp_path):
    output = _run(case, tmp_path, reflection={"interval": 1, "batch_size": 5,
                                              "triggers": {"periodic_interval": 2}})
    assert not (output / "reflection_log.jsonl").exists()
    assert "Reflection (year" not in _prompt(output, 3)
    assert _record(output)["reflection"] == {"enabled": False}


def test_reflection_enabled_stores_each_lesson_as_a_memory_the_next_prompt_shows(case, tmp_path):
    output = _run(case, tmp_path, reflection={"enabled": True})
    assert "Reflection (year 1): (mock model) Year 1 reflection over 1 memories." in _prompt(output, 2)
    log = [json.loads(line) for line in (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["year_created"] for entry in log] == [1, 2, 3]
    assert all(entry["importance"] == 0.9 for entry in log)
    # The year-2 reflection read the year memories, not the year-1 reflection.
    assert not any(line.startswith("Reflection") for line in log[1]["reflection_input"])
    assert _record(output)["reflection"] == {
        "enabled": True, "interval": 1, "importance_boost": 0.9, "decision_types": [],
        "keep_latest_only": False, "persona_instruction": None,
        "reflections_stored": 3, "replies_not_stored": 0, "failed_calls": 0,
    }
    integrity = json.loads((output / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity["reflection_engine_wired"] is True


def test_reflection_interval_skips_the_years_in_between(case, tmp_path):
    output = _run(case, tmp_path, years=4, reflection={"enabled": True, "interval": 2})
    log = (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["year_created"] for line in log] == [2, 4]
    assert "Reflection (year" not in _prompt(output, 2)
    assert "Reflection (year 2)" in _prompt(output, 3)


def test_decision_types_trigger_reflects_in_the_year_the_listed_skill_ran(case, tmp_path):
    prepared, output = _prepare(case, tmp_path, years=2, reflection={
        "enabled": True, "interval": 50, "triggers": {"decision_types": ["wait"], "crisis": False},
    })
    prepared.runner.run()
    years = [json.loads(line)["year_created"]
             for line in (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert years == [1, 2]  # the mock's decision (or the default) runs "wait" every year


def test_decision_types_trigger_skips_a_year_with_another_skill(case, tmp_path):
    prepared, output = _prepare(case, tmp_path, years=2, reflection={
        "enabled": True, "interval": 50, "triggers": {"decision_types": ["inspect"]},
    })
    prepared.runner.run()
    assert not (output / "reflection_log.jsonl").exists()


def test_humancentric_keeps_a_reflection_in_long_term_memory(case, tmp_path):
    prepared, _ = _prepare(case, tmp_path, years=2,
                           memory={"engine_type": "humancentric", "deterministic_consolidation": True},
                           reflection={"enabled": True, "keep_latest_only": True})
    prepared.runner.run()
    engine = prepared.runner.memory_engine
    longterm = [m for m in engine.longterm["agent_1"] if m["content"].startswith("Reflection (year")]
    # keep_latest_only removed the year-1 reflection when year 2's was stored.
    assert [m["content"].split(":")[0] for m in longterm] == ["Reflection (year 2)"]
    assert longterm[0]["importance"] == 0.9


def test_reflection_runs_after_the_cases_own_post_year_hook(case, tmp_path):
    config, data = case
    folder = config.parents[1]
    (folder / "hooks.py").write_text(dedent('''
        def build(ctx):
            def post_year(year, agents):
                ctx.raw["post_year_years"] = ctx.raw.get("post_year_years", []) + [year]
            return {"post_year": post_year}
    '''), encoding="utf-8")
    data["global_config"]["run"]["hooks"] = "hooks:build"
    prepared, _ = _prepare(case, tmp_path, years=1, reflection={"enabled": True})
    hook = prepared.reflection_hook
    case_hook, calls = hook.inner, []
    assert case_hook is not None

    def recording(year, agents):
        calls.append((year, hook.counts["reflections_stored"]))  # reflections stored before the case hook
        case_hook(year, agents)

    hook.inner = recording
    prepared.runner.run()
    assert calls == [(1, 0)]
    assert prepared.ctx.raw["post_year_years"] == [1]
    assert hook.counts["reflections_stored"] == 1


def test_reflection_prompt_and_reply_under_a_real_model(case, tmp_path):
    prepared, _ = _prepare(case, tmp_path, years=1, reflection={
        "enabled": True, "persona_instruction": "Speak as the site manager.",
        "questions": ["What did the inspection show?"],
    })
    hook, agent = prepared.reflection_hook, prepared.runner.agents["agent_1"]
    hook.memory_engine.add_memory(agent.id, "Year 1: you waited")
    prompts = []

    def invoke(prompt):
        prompts.append(prompt)
        return "Waiting kept the site safe this year.", {"tokens": 1}

    hook.model = "some-real-model"
    hook.runner = SimpleNamespace(get_llm_invoke=lambda agent_type: invoke)
    hook(1, {agent.id: agent})
    assert prompts[0].startswith("Speak as the site manager.\n\n")
    assert "What did the inspection show?" in prompts[0] and "Year 1: you waited" in prompts[0]
    assert hook.memory_engine.retrieve(agent, top_k=3)[-1] == \
        "Reflection (year 1): Waiting kept the site safe this year."

    def failing(prompt):
        raise ConnectionError("model offline")

    hook.runner = SimpleNamespace(get_llm_invoke=lambda agent_type: failing)
    hook(2, {agent.id: agent})
    assert hook.counts == {"reflections_stored": 1, "replies_not_stored": 0, "failed_calls": 1}


def test_an_agent_type_with_its_own_real_model_reflects_with_that_model(case, tmp_path, monkeypatch):
    # The run model is mock, but llm_params.model gives this agent type a real
    # model: its decisions use that model, so its reflection must too.
    from broker.utils import llm_utils
    mock_invoke, models, reflection_prompts = llm_utils.create_llm_invoke("mock"), [], []

    def fake_create_llm_invoke(model, verbose=False, overrides=None):
        models.append(model)

        def invoke(prompt):
            if "What did the inspection show?" in prompt:
                reflection_prompts.append(prompt)
                return "Waiting kept the site safe this year.", {"tokens": 1}
            return mock_invoke(prompt)
        return invoke

    monkeypatch.setattr(llm_utils, "create_llm_invoke", fake_create_llm_invoke)
    case[1]["agent"]["llm_params"] = {"model": "openai:site-model"}
    prepared, output = _prepare(case, tmp_path, years=1, reflection={
        "enabled": True, "questions": ["What did the inspection show?"],
    })
    prepared.runner.run()
    assert "openai:site-model" in models  # the decisions' invoke for this agent type
    assert len(reflection_prompts) == 1
    log = [json.loads(line) for line in (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["summary"] for entry in log] == ["Waiting kept the site safe this year."]


def test_an_agent_type_on_the_mock_model_under_a_real_run_model_gets_the_fixed_reflection(
        case, tmp_path, monkeypatch):
    from broker.utils import llm_utils
    mock_invoke = llm_utils.create_llm_invoke("mock")
    monkeypatch.setattr(llm_utils, "create_llm_invoke", lambda model, verbose=False, overrides=None: mock_invoke)
    config, data = case
    data["agent"]["llm_params"] = {"model": "mock"}
    data["global_config"]["reflection"] = {"enabled": True}
    _write_yaml(config, data)
    output = tmp_path / "output"
    argv = _argv(config, output, years=1)
    argv[argv.index("--model") + 1] = "openai:site-model"
    _entry.prepare(argv).runner.run()
    log = [json.loads(line) for line in (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["summary"] for entry in log] == ["(mock model) Year 1 reflection over 1 memories."]


def test_an_agent_type_answered_by_the_run_mock_slot_gets_the_fixed_reflection(case, tmp_path):
    config, data = case
    (config.parents[1] / "scripted.py").write_text(dedent('''
        from broker.utils.llm_utils import create_llm_invoke

        def build(ctx):
            return create_llm_invoke("mock")
    '''), encoding="utf-8")
    data["global_config"]["run"]["mock"] = "scripted:build"
    data["agent"]["llm_params"] = {"model": "openai:site-model"}  # the slot answers instead
    prepared, output = _prepare(case, tmp_path, years=1, reflection={"enabled": True})
    prepared.runner.run()
    log = [json.loads(line) for line in (output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [entry["summary"] for entry in log] == ["(mock model) Year 1 reflection over 1 memories."]


def test_a_failed_reflection_log_write_stops_the_run_and_is_not_counted(case, tmp_path):
    prepared, output = _prepare(case, tmp_path, years=1, reflection={"enabled": True})
    (output / "reflection_log.jsonl").mkdir(parents=True)  # opening it for append fails
    with pytest.raises(OSError):
        prepared.runner.run()
    assert prepared.reflection_hook.counts["reflections_stored"] == 0


def test_failed_reflection_calls_are_reported_on_stderr(case, tmp_path, capsys, monkeypatch):
    def offline(self, agent_type, prompt, year, count):
        raise ConnectionError("model offline")

    monkeypatch.setattr(_memory.ReflectionHook, "_call", offline)
    output = _run(case, tmp_path, years=2, reflection={"enabled": True})
    assert "reflection: 0 stored, 2 model calls failed" in capsys.readouterr().err
    assert _record(output)["reflection"]["failed_calls"] == 2


@pytest.mark.parametrize("reflection, message", [
    ({"enabled": "yes"}, "reflection.enabled must be true or false"),
    ({"enabled": True, "interval": 0}, "reflection.interval"),
    ({"enabled": True, "importance_boost": 1.5}, "importance_boost"),
    ({"enabled": True, "batch_size": 5}, "one agent per call"),
    ({"enabled": True, "triggers": {"periodic_interval": 2}}, "reflection.interval"),
    ({"enabled": True, "triggers": {"crisis": True}}, "crisis signal"),
    ({"enabled": True, "triggers": {"institutional_threshold": 0.1}}, "policy-change signal"),
    ({"enabled": True, "triggers": {"decision_types": "wait"}}, "list of skill names"),
    ({"enabled": True, "year_outcome": True}, "grounded reflection"),
    ({"enabled": True, "keep_latest_only": True}, "engine_type to humancentric"),
    ({"enabled": True, "persona_instruction": ""}, "persona_instruction"),
])
def test_reflection_settings_broker_run_cannot_honour_are_refused(case, tmp_path, capsys, reflection, message):
    config, data = case
    data["global_config"]["reflection"] = reflection
    _write_yaml(config, data)
    assert main(_argv(config, tmp_path / "output")) == 2
    assert message in capsys.readouterr().err
