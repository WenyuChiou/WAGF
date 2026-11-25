import csv
import json
import sys
from textwrap import dedent
from uuid import uuid4

import pytest
import yaml

from broker.core.experiment_runner import ExperimentRunner
from broker.run import _entry, main


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
            assert ctx.world is None and ctx.agents is None
            return World()
    '''), encoding="utf-8")
    _write_yaml(config_path.with_name("skill_registry.yaml"), {
        "default_skill": "wait",
        "skills": [
            {"skill_id": "wait", "description": "Wait for the next year"},
            {"skill_id": "inspect", "description": "Inspect the site", "eligible_agent_types": ["agent"]},
            {"skill_id": "repair", "eligible_agent_types": ["other"]},
        ],
    })
    data = {
        "global_config": {},
        "agent": {
            "psychological_framework": "generic",
            "prompt_template": "Available actions\n{options_text}\n\n{response_format}",
            "actions": [
                {"id": "wait", "aliases": ["1"]},
                {"id": "inspect", "aliases": ["2"]},
            ],
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


def _audit_rows(output):
    with (output / "agent_governance_audit.csv").open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _first_decision(output):
    lines = (output / "raw" / "agent_traces.jsonl").read_text(encoding="utf-8").splitlines()
    return next(record for record in map(json.loads, lines) if "step_id" in record)


def _manifest(output):
    return json.loads((output / "broker_run.json").read_text(encoding="utf-8"))


def test_mock_run_renders_menu_and_records_provenance(case, tmp_path):
    config, data = case
    data["global_config"]["run"] = {"world": "world:build"}
    _write_yaml(config, data)
    output = tmp_path / "output"
    argv = [str(config), "--model", "mock", "--years", "1", "--agents", "2", "--output", str(output)]
    assert main(argv) == 0
    assert len(_audit_rows(output)) == 2
    prompt = _first_decision(output)["input"]
    options = prompt.split("Available actions\n", 1)[1].split("\n\n", 1)[0]
    assert "1. " in options and "2. " in options
    assert "[N/A]" not in options
    assert "repair" not in options
    assert "<<<DECISION_START>>>" in prompt
    assert (output / "reproducibility_manifest.json").is_file()
    case_dir = config.parents[1].resolve()
    record = _manifest(output)
    for key in ("strict_provenance", "provenance_checks", "provenance_problems"):  # see test_broker_run_strict_provenance.py
        record.pop(key)
    assert record == {
        "status": "completed",
        "config": str(config.resolve()), "case_dir": str(case_dir),
        "slots": {"world": "world:build"}, "slot_sources": {"world": "yaml"},
        "slot_files": {"world": str(case_dir / "world.py")},
        "allow_modules": [], "model": "mock",
        "thinking_mode": _entry.LLM_CONFIG.thinking_mode, "years": 1, "agent_count": 2,
        "seed": 42, "governance": "default", "workers": 1, "phase_order": None,
        "skill_registry": str(config.with_name("skill_registry.yaml").resolve()),
        "output_dir": str(output.resolve()),
        "argv": argv,
    }


def test_run_record_is_written_before_the_run(case, tmp_path, monkeypatch):
    config, data = case
    _write_yaml(config, data)
    output = tmp_path / "output"

    def failing_run(self, llm_invoke=None):
        raise RuntimeError("run failed")

    monkeypatch.setattr(ExperimentRunner, "run", failing_run)
    with pytest.raises(RuntimeError, match="run failed"):
        main([str(config), "--output", str(output)])
    assert _manifest(output)["status"] == "started"


def test_completed_output_dir_is_refused_before_anything_is_written(case, tmp_path, capsys):
    config, data = case
    _write_yaml(config, data)
    output = tmp_path / "output"
    assert main([str(config), "--output", str(output)]) == 0
    record = (output / "broker_run.json").read_bytes()
    capsys.readouterr()
    # Refused before any case code runs.
    (config.parents[1] / "boom.py").write_text(
        'def build(ctx):\n    raise AssertionError("slot code ran")\n', encoding="utf-8")
    assert main([str(config), "--output", str(output), "--seed", "7",
                 "--slot", "world=boom:build"]) == 2
    assert "already holds a completed run" in capsys.readouterr().err
    assert (output / "broker_run.json").read_bytes() == record


def test_self_referencing_yaml_alias_does_not_recurse_forever():
    node = {"decider": {"name": "rule"}}
    node["self"] = node
    node["items"] = [node, {"nested": node}]
    assert _entry._vet_decider_targets(node, None, []) is None


@pytest.mark.parametrize("skills", [
    [{"description": "no id"}], ["wait"], [{"skill_id": "wait", "eligible_agent_types": None}],
    {"wait": {}},
])
def test_malformed_registry_items_return_2(case, tmp_path, capsys, skills):
    config, data = case
    _write_yaml(config, data)
    _write_yaml(config.with_name("skill_registry.yaml"), {"skills": skills})
    assert main([str(config), "--output", str(tmp_path / "out")]) == 2
    assert "string skill_id" in capsys.readouterr().err


def _write_decider(config, data, target):
    data["agent"]["decider"] = {"name": "parametric", "params": {"target": target}}
    _write_yaml(config, data)


def test_decider_target_outside_case_is_refused_before_it_runs(case, tmp_path, monkeypatch, capsys):
    config, data = case
    outside = tmp_path / "outside"
    outside.mkdir()
    name = f"outside_decider_{uuid4().hex}"
    (outside / f"{name}.py").write_text(
        'raise AssertionError("outside decider module executed")\n', encoding="utf-8")
    monkeypatch.syspath_prepend(str(outside))
    _write_decider(config, data, f"{name}:Decider")
    assert main([str(config), "--output", str(tmp_path / "out")]) == 2
    error = capsys.readouterr().err
    assert "decider.params.target" in error and f"--allow-module {name}" in error
    assert name not in sys.modules


def test_decider_target_in_case_folder_is_loaded_through_the_vetted_path(case, tmp_path):
    config, data = case
    folder = config.parents[1]
    (folder / "deciders.py").write_text(dedent('''
        class Decider:
            def decide(self, **kwargs):
                return "inspect"
    '''), encoding="utf-8")
    _write_decider(config, data, f" {folder.name}.deciders : Decider ")
    _entry.prepare([str(config), "--output", str(tmp_path / "out")])
    module = sys.modules[f"{folder.name}.deciders"]
    assert module.__file__ == str((folder / "deciders.py").resolve())


def test_decider_target_bare_case_name_is_refused(case, tmp_path, capsys):
    config, data = case
    folder = config.parents[1]
    (folder / "deciders.py").write_text("class Decider: pass\n", encoding="utf-8")
    _write_decider(config, data, "deciders:Decider")
    assert main([str(config), "--output", str(tmp_path / "out")]) == 2
    assert f"{folder.name}.<module>" in capsys.readouterr().err


def test_cli_overrides_yaml_and_yaml_output_is_case_relative(case):
    config, data = case
    data["global_config"]["run"] = {"years": 3, "output": "results/x", "world": "unused:build"}
    _write_yaml(config, data)
    assert main([str(config), "--years", "1", "--slot", "world=world:build"]) == 0
    output = config.parents[1] / "results" / "x"
    assert len(_audit_rows(output)) == 1
    assert _manifest(output)["slot_sources"] == {"world": "cli"}
    assert _manifest(output)["slots"] == {"world": "world:build"}


def test_cli_paths_are_cwd_relative_and_thinking_mode_is_applied(case, tmp_path, monkeypatch):
    config, data = case
    data["global_config"]["run"] = {"skill_registry": "absent.yaml", "output": "unused"}
    _write_yaml(config, data)
    registry = config.with_name("skill_registry.yaml").read_bytes()
    (tmp_path / "registry.yaml").write_bytes(registry)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(_entry.LLM_CONFIG, "thinking_mode", "auto")

    assert main([str(config), "--skill-registry", "registry.yaml", "--output", "out",
                 "--thinking-mode", "disabled"]) == 0
    assert len(_audit_rows(tmp_path / "out")) == 1
    assert _entry.LLM_CONFIG.thinking_mode == "disabled"


def test_defaults_without_run_block(case):
    config, data = case
    _write_yaml(config, data)
    assert main([str(config)]) == 0
    output = config.parents[1] / "results" / config.stem
    assert len(_audit_rows(output)) == 1
    assert _first_decision(output)["execution_result"]["success"] is True
    assert _manifest(output)["slots"] == {}


def test_multiple_agent_types_require_factory(case, capsys):
    config, data = case
    data["other"] = {"psychological_framework": "generic"}
    _write_yaml(config, data)
    assert main([str(config)]) == 2
    error = capsys.readouterr().err
    assert "agent, other" in error and "run.agents" in error


def test_phase_order_reaches_runner(case, monkeypatch):
    config, data = case
    data["global_config"]["run"] = {"phase_order": [["agent"]]}
    _write_yaml(config, data)
    actual = []

    def record_phase_order(runner):
        actual.append(runner.config.phase_order)

    monkeypatch.setattr("broker.core.experiment_runner.ExperimentRunner.run", record_phase_order)
    assert main([str(config)]) == 0
    assert actual == [[["agent"]]]


def test_hooks_receive_built_world_and_agents(case):
    config, data = case
    (config.parents[1] / "hooks.py").write_text(dedent('''
        def build(ctx):
            assert ctx.world is not None
            assert list(ctx.agents) == ["agent_1"]
            years = []

            def pre_year(year, env, agents):
                assert env["current_year"] == year
                assert agents is ctx.agents
                years.append(year)

            def after_run(output_dir):
                assert output_dir == ctx.output_dir
                assert (output_dir / "reproducibility_manifest.json").is_file()
                with (output_dir / "hook_calls.txt").open("a", encoding="utf-8") as file:
                    file.write(str(years) + "\\n")

            return {"pre_year": pre_year, "after_run": after_run}
    '''), encoding="utf-8")
    data["global_config"]["run"] = {"hooks": "hooks:build", "years": 2}
    _write_yaml(config, data)
    assert main([str(config)]) == 0
    output = config.parents[1] / "results" / config.stem
    assert (output / "hook_calls.txt").read_text(encoding="utf-8") == "[1, 2]\n"


def test_scripted_mock_is_used_for_agent_type(case):
    config, data = case
    (config.parents[1] / "scripted.py").write_text(dedent('''
        from broker.utils.llm_utils import LLMStats

        def build(ctx):
            assert ctx.world is not None and ctx.agents

            def invoke(prompt):
                return '{"decision": 2}', LLMStats(success=True)

            return {"agent": invoke}
    '''), encoding="utf-8")
    data["global_config"]["run"] = {"model": "mock-scripted", "mock": "scripted:build"}
    _write_yaml(config, data)
    assert main([str(config)]) == 0
    record = _first_decision(config.parents[1] / "results" / config.stem)
    assert record["approved_skill"]["status"] == "APPROVED"
    assert record["approved_skill"]["skill_name"] == "inspect"


def test_real_model_skips_mock_slot_without_import(case):
    config, data = case
    package = config.parents[1]
    (package / "scripted.py").write_text('raise AssertionError("mock slot imported")\n', encoding="utf-8")
    data["global_config"]["run"] = {"mock": "scripted:build"}
    _write_yaml(config, data)
    context, slots, _phase_order, _args = _entry._prepare_run([str(config), "--model", "real-model"])
    assert _entry._slot_factory("mock", context, slots, [], {}) is None
    assert f"{package.name}.scripted" not in sys.modules


def test_coupled_factory_sources_and_other_slots_reach_builder(case, monkeypatch):
    config, data = case
    package = config.parents[1]
    (package / "factories.py").write_text(dedent('''
        from broker.agents import AgentConfig, BaseAgent
        from broker.run import Coupled
        from broker.utils.llm_utils import LLMStats

        def world(ctx):
            return Coupled("contract", "sources", domain="case")

        def agents(ctx):
            assert ctx.world == "sources" and ctx.agents is None and ctx.agent_count == 5
            return {
                name: BaseAgent(AgentConfig(name, name, [], [], [], []))
                for name in ("agent", "other")
            }

        def validate(*args):
            return []

        def validators(ctx):
            assert list(ctx.agents) == ["agent", "other"]
            return (validate,)

        def mock(ctx):
            assert list(ctx.agents) == ["agent", "other"]
            return lambda prompt: ("{}", LLMStats(success=True))
    '''), encoding="utf-8")
    data["other"] = {"psychological_framework": "generic"}
    data["global_config"]["run"] = {
        "world": "factories:world", "agents": "factories:agents",
        "validators": "factories:validators", "mock": "factories:mock", "agent_count": 5,
    }
    _write_yaml(config, data)
    coupling_calls = []
    observed = []

    def capture_coupling(builder, contract, sources, domain=None):
        coupling_calls.append((contract, sources, domain))
        return builder.with_simulation(_entry.StepWorld())

    def inspect_runner(runner):
        observed.append(runner)
        assert list(runner.agents) == ["agent", "other"]
        assert [validator.__name__ for validator in runner.broker.custom_validators] == ["validate"]
        assert runner.get_llm_invoke("agent") is runner.get_llm_invoke("other")
        assert runner.get_llm_invoke("agent")("prompt")[0] == "{}"

    monkeypatch.setattr(_entry.ExperimentBuilder, "with_coupling", capture_coupling)
    monkeypatch.setattr("broker.core.experiment_runner.ExperimentRunner.run", inspect_runner)
    assert main([str(config)]) == 0
    assert coupling_calls == [("contract", "sources", "case")]
    assert len(observed) == 1


@pytest.mark.parametrize("run, key", [
    ({"unknown": 1}, "unknown"), ({"years": "x"}, "years"),
    ({"agent_count": True}, "agent_count"), ({"phase_order": ["agent"]}, "phase_order"),
    (None, "run"),
])
def test_invalid_run_block(case, capsys, run, key):
    config, data = case
    data["global_config"]["run"] = run
    _write_yaml(config, data)
    assert main([str(config)]) == 2
    error = capsys.readouterr().err
    assert error.startswith("broker.run: ") and key in error


@pytest.mark.parametrize("args, key", [
    (["--agents", "0"], "--agents"), (["--years", "x"], "--years"),
    (["--slot", "bogus=world:build"], "bogus"), (["--allow-module", ".world"], "--allow-module"),
])
def test_bad_cli_value_returns_two(case, capsys, args, key):
    config, data = case
    _write_yaml(config, data)
    assert main([str(config), *args]) == 2
    error = capsys.readouterr().err
    assert error.startswith("broker.run: ") and key in error


def test_builder_configuration_error_returns_2_with_its_message(case, capsys):
    """A config the builder refuses (here a none agent with an appraisal field)
    is reported as a broker.run error, not a traceback."""
    config, data = case
    data["agent"]["psychological_framework"] = "none"
    data["agent"]["response_format"]["fields"].insert(
        0, {"key": "risk_appraisal", "type": "appraisal", "required": True})
    _write_yaml(config, data)
    assert main([str(config), "--model", "mock"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("broker.run: the case could not be built:")
    assert "psychological_framework: none" in err and "risk_appraisal" in err


def test_prepare_builds_without_running(case, tmp_path):
    from broker.run import prepare

    config, data = case
    _write_yaml(config, data)
    output = tmp_path / "prepared"
    prepared = prepare([str(config), "--agents", "3", "--output", str(output)])
    assert len(prepared.ctx.agents) == 3
    assert prepared.runner.config.output_dir == output
    assert not (output / "agent_governance_audit.csv").exists()


def test_case_parent_is_appended_not_prepended(case, tmp_path):
    """The case's parent folder joins sys.path at the end, once."""
    config, data = case
    data["global_config"]["run"] = {"world": "world:build"}
    _write_yaml(config, data)
    parent = str(config.parents[2])
    first = sys.path[0]
    for n in range(2):
        assert main([str(config), "--output", str(tmp_path / f"out{n}")]) == 0
    assert sys.path[0] == first
    assert [p for p in sys.path if p == parent] == [parent]
    assert sys.path[-1] == parent


# --- strict keys ----------------------------------------------------------------

def _with_unknown_key(config, data, run=None):
    data["global_config"]["unread_flag"] = True
    if run is not None:
        data["global_config"]["run"] = run
    _write_yaml(config, data)


def test_strict_keys_is_off_by_default(case, capsys):
    config, data = case
    _with_unknown_key(config, data)
    assert main([str(config)]) == 0
    assert _manifest(config.parents[1] / "results" / config.stem)["status"] == "completed"


def test_strict_keys_flag_refuses_a_yaml_with_an_unknown_key(case, capsys):
    config, data = case
    _with_unknown_key(config, data)
    assert main([str(config), "--strict-keys"]) == 2
    error = capsys.readouterr().err
    assert error.startswith("broker.run: ") and "global_config.unread_flag" in error
    assert not (config.parents[1] / "results" / config.stem).exists()


def test_run_strict_keys_true_does_the_same(case, capsys):
    config, data = case
    _with_unknown_key(config, data, run={"strict_keys": True})
    assert main([str(config)]) == 2
    assert "global_config.unread_flag" in capsys.readouterr().err


def test_no_strict_keys_overrides_a_yaml_true(case):
    config, data = case
    _with_unknown_key(config, data, run={"strict_keys": True})
    assert main([str(config), "--no-strict-keys"]) == 0


def test_strict_keys_passes_a_clean_yaml(case):
    config, data = case
    _write_yaml(config, data)
    assert main([str(config), "--strict-keys"]) == 0


def test_run_strict_keys_must_be_a_bool(case, capsys):
    config, data = case
    data["global_config"]["run"] = {"strict_keys": "yes"}
    _write_yaml(config, data)
    assert main([str(config)]) == 2
    assert "strict_keys" in capsys.readouterr().err


# --- strict keys: the action number is on [0, 1] -----------------------------------

def _with_magnitude_field(config, data, **field):
    data["agent"]["response_format"]["fields"].append(
        {"key": "magnitude", "type": "numeric", "min": 0, **field})
    _write_yaml(config, data)


def test_strict_keys_refuses_a_magnitude_with_max_100(case, capsys):
    config, data = case
    _with_magnitude_field(config, data, max=100)
    assert main([str(config), "--strict-keys"]) == 2
    error = capsys.readouterr().err
    assert error.startswith("broker.run: ") and "'magnitude'" in error and "'agent'" in error
    assert "[0, 1]" in error
    assert not (config.parents[1] / "results" / config.stem).exists()


def test_without_strict_keys_the_same_magnitude_case_runs(case):
    config, data = case
    _with_magnitude_field(config, data, max=100)
    assert main([str(config)]) == 0


def test_strict_keys_accepts_a_magnitude_on_zero_to_one(case):
    config, data = case
    _with_magnitude_field(config, data, max=1)
    assert main([str(config), "--strict-keys"]) == 0
