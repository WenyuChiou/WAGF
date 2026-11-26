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
    # R5 walk finding 13: written even though this case has no rules
    health = (output / "validator_health.csv").read_text(encoding="utf-8-sig")
    assert health.splitlines()[0].startswith("rule_id,")
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
        "memory": {"engine": "window", "window_size": None, "retrieval_top_k": {"agent": 3}},
        "reflection": {"enabled": False},
        "rejection_line_style": {"agent": "executed"},
        "memory_writes_by_origin": {"world": 0, "decision": 2, "reflection": 0, "social": 0, "seed": 0},
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
    data["global_config"]["coupling"] = {"enable": True}
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


def _write_coupled_world(config):
    (config.parents[1] / "coupled.py").write_text(dedent('''
        from broker.run import Coupled

        def world(ctx):
            return Coupled("contract", "sources", domain="case_without_pack")
    '''), encoding="utf-8")


@pytest.mark.parametrize("coupling, pack_default, why", [
    (None, None, "enable is not set and no 'case_without_pack' domain pack is registered"),
    (None, False, "enable is not set and the 'case_without_pack' domain pack defaults to off"),
    ({"enable": False}, True, "enable is false"),
])
def test_coupled_world_with_coupling_off_is_refused(case, monkeypatch, capsys, coupling,
                                                    pack_default, why):
    """R5 walk finding 3: a Coupled world with the flag off used to run the
    model unwrapped after an info-level log line, so no coupled check ran."""
    from broker.domains.default import DefaultDomainPack
    from broker.domains.registry import DomainPackRegistry

    config, data = case
    _write_coupled_world(config)
    if coupling is not None:
        data["global_config"]["coupling"] = coupling
    if pack_default is not None:
        pack = DefaultDomainPack()
        pack.coupling_enabled_default = lambda: pack_default
        monkeypatch.setitem(DomainPackRegistry._packs, "case_without_pack", pack)
    data["global_config"]["run"] = {"world": "coupled:world"}
    _write_yaml(config, data)
    calls = []
    monkeypatch.setattr(_entry.ExperimentBuilder, "with_coupling", lambda *a, **k: calls.append(a))
    assert main([str(config), "--model", "mock"]) == 2
    err = capsys.readouterr().err
    assert "Coupled(...) but coupling is off (global_config.coupling." + why + ")" in err
    assert "global_config.coupling.enable: true" in err
    assert calls == []


def test_coupled_world_uses_the_domain_pack_default(case, monkeypatch):
    """With no YAML flag, a registered pack whose default is on is enough."""
    from broker.domains.default import DefaultDomainPack
    from broker.domains.registry import DomainPackRegistry

    class OnPack(DefaultDomainPack):
        name = "case_pack_on"

        def coupling_enabled_default(self):
            return True

    config, data = case
    (config.parents[1] / "coupled.py").write_text(dedent('''
        from broker.run import Coupled

        def world(ctx):
            return Coupled("contract", "sources", domain="case_pack_on")
    '''), encoding="utf-8")
    data["global_config"]["run"] = {"world": "coupled:world"}
    _write_yaml(config, data)
    monkeypatch.setitem(DomainPackRegistry._packs, "case_pack_on", OnPack())
    calls = []

    def capture(builder, contract, sources, domain=None):
        calls.append(domain)
        return builder.with_simulation(_entry.StepWorld())

    monkeypatch.setattr(_entry.ExperimentBuilder, "with_coupling", capture)
    monkeypatch.setattr("broker.core.experiment_runner.ExperimentRunner.run", lambda runner: None)
    assert main([str(config), "--model", "mock"]) == 0
    assert calls == ["case_pack_on"]


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


FILE_PROMPT = "Read this file prompt first.\nAvailable actions\n{options_text}\n\n{response_format}"


def _write_prompt_file(config):
    prompts = config.parent / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / "agent.txt").write_text(FILE_PROMPT, encoding="utf-8")


def _use_prompt_file(case, ref):
    config, data = case
    _write_prompt_file(config)
    data["global_config"]["run"] = {"world": "world:build"}
    del data["agent"]["prompt_template"]
    data["agent"]["prompt_template_file"] = ref
    _write_yaml(config, data)
    return config


def test_prompt_template_file_not_found_from_yaml_folder_is_refused(case, tmp_path, capsys):
    # A path written from the case folder passes validate_prompt, which walks
    # up parent folders, but broker.run resolves it from the YAML folder only.
    # Before this check the run went on with the built-in default prompt.
    config = _use_prompt_file(case, "config/prompts/agent.txt")
    assert main([str(config), "--model", "mock", "--output", str(tmp_path / "out")]) == 2
    err = capsys.readouterr().err
    assert "agent.prompt_template_file 'config/prompts/agent.txt' was not found" in err
    assert "for example prompts/agent.txt" in err


def test_prompt_template_file_from_yaml_folder_is_rendered(case, tmp_path):
    config = _use_prompt_file(case, "prompts/agent.txt")
    output = tmp_path / "out"
    assert main([str(config), "--model", "mock", "--years", "1", "--output", str(output)]) == 0
    assert "Read this file prompt first." in _first_decision(output)["input"]


def test_unreadable_prompt_template_file_is_refused(case, tmp_path, capsys):
    # get_prompt_template only logs a failed read and falls back.
    config = _use_prompt_file(case, "prompts/agent.txt")
    (config.parent / "prompts" / "agent.txt").write_bytes(b"\xff\xfe\xfa not utf-8")
    assert main([str(config), "--model", "mock", "--output", str(tmp_path / "out")]) == 2
    err = capsys.readouterr().err
    assert "agent.prompt_template_file" in err
    assert "could not be read" in err


def test_inline_and_file_prompt_together_are_refused(case, tmp_path, capsys):
    # get_prompt_template prefers the file; ExperimentBuilder puts the inline
    # template in the context builder, so the rendered prompt would not be
    # the file the manifest names.
    config, data = case
    _write_prompt_file(config)
    data["agent"]["prompt_template_file"] = "prompts/agent.txt"
    _write_yaml(config, data)
    assert main([str(config), "--model", "mock", "--output", str(tmp_path / "out")]) == 2
    assert "set prompt_template or prompt_template_file, not both" in capsys.readouterr().err


def _magnitude_case(case, field_skills, number=0.4):
    """A case whose mock answers wait in year 1 and inspect in year 2, both
    with the number 0.4 (or ``number``), and whose world records the
    parameters it gets."""
    config, data = case
    (config.parents[1] / "recording.py").write_text(dedent('''
        import json
        from broker.interfaces.skill_types import ExecutionResult
        from broker.utils.llm_utils import LLMStats

        SEEN = []

        class World:
            year = 0

            def advance_step(self):
                self.year += 1
                return {"current_year": self.year}

            def execute_skill(self, approved_skill):
                SEEN.append((approved_skill.skill_name, dict(approved_skill.parameters)))
                return ExecutionResult(success=True, state_changes={})

        def build(ctx):
            return World()

        def mock(ctx):
            answers = iter(["1", "2"])

            def respond(prompt):
                payload = {"decision": next(answers), "magnitude": NUMBER}
                text = "<<<DECISION_START>>>" + json.dumps(payload) + "<<<DECISION_END>>>"
                return text, LLMStats(success=True)
            return respond
    ''').replace("NUMBER", json.dumps(number)), encoding="utf-8")
    field = {"key": "magnitude", "type": "numeric", "min": 0, "max": 1, "required": True}
    if field_skills is not None:
        field["skills"] = field_skills
    data["agent"]["response_format"]["fields"].insert(0, field)
    data["global_config"]["run"] = {"world": "recording:build", "mock": "recording:mock", "years": 2,
                                    "agent_count": 1}
    _write_yaml(config, data)
    return config


def _seen(config):
    return sys.modules[f"{config.parents[1].name}.recording"].SEEN


def test_number_is_dropped_for_a_skill_the_field_does_not_list(case):
    """R5 walk finding 2: maintain + 0.75 used to change the world's control."""
    config = _magnitude_case(case, ["inspect"])
    assert main([str(config), "--model", "mock"]) == 0
    seen = _seen(config)
    assert [name for name, _ in seen] == ["wait", "inspect"]
    assert "magnitude_pct" not in seen[0][1]
    assert seen[1][1]["magnitude_pct"] == 0.4
    record = _first_decision(config.parents[1] / "results" / "agent_types")
    assert any("magnitude=0.4 dropped: wait does not take it" in w
               for w in record["skill_proposal"]["parsing_warnings"])


def test_dropping_initial_primary_field_selects_remaining_scoped_field(case):
    """Codex P2 on #136: dropping `magnitude` (wait-only) on `inspect` must
    select the remaining valid field (`inspect_share`) as `magnitude_pct`."""
    config = _magnitude_case(case, ["wait"])
    _, data = case
    data["agent"]["response_format"]["fields"].insert(1, {
        "key": "inspect_share", "type": "numeric", "min": 0, "max": 1,
        "required": True, "skills": ["inspect"]})
    _write_yaml(config, data)
    recording = config.parents[1] / "recording.py"
    recording.write_text(recording.read_text(encoding="utf-8").replace(
        '{"decision": next(answers), "magnitude": 0.4}',
        '{"decision": next(answers), "magnitude": 0.2, "inspect_share": 0.4}'), encoding="utf-8")
    assert main([str(config), "--model", "mock"]) == 0
    seen = _seen(config)
    assert [(n, p.get("magnitude_pct")) for n, p in seen] == [("wait", 0.2), ("inspect", 0.4)]


def test_keyword_parsed_number_keeps_the_scope_of_the_field_it_matched(case):
    """Codex P2 on #136: a number the keyword fallback found was scoped by the
    first declared numeric field (magnitude, wait only), not by the field it
    matched (inspect_share, inspect), so inspect lost its number."""
    config, data = case
    (config.parents[1] / "recording.py").write_text(dedent('''
        from broker.interfaces.skill_types import ExecutionResult
        from broker.utils.llm_utils import LLMStats

        SEEN = []

        class World:
            year = 0

            def advance_step(self):
                self.year += 1
                return {"current_year": self.year}

            def execute_skill(self, approved_skill):
                SEEN.append((approved_skill.skill_name, dict(approved_skill.parameters)))
                return ExecutionResult(success=True, state_changes={})

        def build(ctx):
            return World()

        def mock(ctx):
            def respond(prompt):
                return "Decision: 2\\ninspect_share: 0.4", LLMStats(success=True)
            return respond
    '''), encoding="utf-8")
    fields = data["agent"]["response_format"]["fields"]
    fields.insert(0, {"key": "inspect_share", "type": "numeric", "min": 0, "max": 1,
                      "skills": ["inspect"]})
    fields.insert(0, {"key": "magnitude", "type": "numeric", "min": 0, "max": 1,
                      "skills": ["wait"]})
    data["global_config"]["run"] = {"world": "recording:build", "mock": "recording:mock", "years": 1,
                                    "agent_count": 1}
    _write_yaml(config, data)
    assert main([str(config), "--model", "mock"]) == 0
    seen = _seen(config)
    assert [name for name, _ in seen] == ["inspect"]
    assert seen[0][1]["magnitude_pct"] == 0.4


def test_without_field_skills_every_skill_gets_the_number(case):
    config = _magnitude_case(case, None)
    assert main([str(config), "--model", "mock"]) == 0
    assert [params.get("magnitude_pct") for _, params in _seen(config)] == [0.4, 0.4]


def _two_action_case(case, primary, secondary):
    """Multi-skill on: one year, the mock picks ``primary`` (number 0.4) and
    ``secondary`` (number 40); both number fields list only inspect."""
    config = _magnitude_case(case, ["inspect"])
    _, data = case
    data["agent"]["multi_skill"] = {"enabled": True, "secondary_field": "secondary_decision",
                                    "secondary_magnitude_field": "secondary_magnitude"}
    fields = data["agent"]["response_format"]["fields"]
    # The secondary is checked against the required fields with the reply's
    # primary keys only, so a required primary number would block it.
    next(f for f in fields if f["key"] == "magnitude")["required"] = False
    fields.insert(1, {
        "key": "secondary_magnitude", "type": "numeric", "min": 1, "max": 100,
        "required": False, "skills": ["inspect"]})
    data["global_config"]["run"]["years"] = 1
    _write_yaml(config, data)
    recording = config.parents[1] / "recording.py"
    text = recording.read_text(encoding="utf-8")
    old = 'payload = {"decision": next(answers), "magnitude": 0.4}'
    assert text.count(old) == 1
    recording.write_text(text.replace(old, (
        f'payload = {{"decision": "{primary}", "magnitude": 0.4, '
        f'"secondary_decision": "{secondary}", "secondary_magnitude": 40}}')), encoding="utf-8")
    return config


def test_the_secondary_action_drops_a_number_its_field_does_not_list(case):
    """Codex P2 on #136: the secondary hold kept the 40 its field excludes."""
    config = _two_action_case(case, primary="2", secondary="1")  # inspect, then wait
    assert main([str(config), "--model", "mock"]) == 0
    seen = _seen(config)
    assert [name for name, _ in seen] == ["inspect", "wait"]
    assert seen[0][1]["magnitude_pct"] == 0.4
    assert "magnitude_pct" not in seen[1][1]
    record = _first_decision(config.parents[1] / "results" / "agent_types")
    assert any("secondary_magnitude=40.0 dropped: the secondary action wait does not take it" in w
               for w in record["skill_proposal"]["parsing_warnings"])


def test_a_secondary_action_the_field_lists_keeps_its_number(case):
    config = _two_action_case(case, primary="1", secondary="2")  # wait, then inspect
    assert main([str(config), "--model", "mock"]) == 0
    seen = _seen(config)
    assert [name for name, _ in seen] == ["wait", "inspect"]
    assert "magnitude_pct" not in seen[0][1]
    assert seen[1][1]["magnitude_pct"] == 40.0


@pytest.mark.parametrize("number", ["1", "0"])
def test_a_number_written_as_text_stays_a_number_in_the_audit(case, number):
    """R5 walk finding 17: the label map turned the text "1" into True."""
    config = _magnitude_case(case, None, number=number)
    assert main([str(config), "--model", "mock"]) == 0
    assert [params.get("magnitude_pct") for _, params in _seen(config)] == [float(number)] * 2
    rows = _audit_rows(config.parents[1] / "results" / "agent_types")
    assert [row["reason_magnitude"] for row in rows] == [number, number]


@pytest.mark.parametrize("skills, message", [
    (["inspekt"], "lists skills ['inspekt'] that the skill registry does not have"),
    ("inspect", "skills must be a non-empty list of skill names"),
    ([], "skills must be a non-empty list of skill names"),
])
def test_bad_field_skills_are_refused_at_build(case, capsys, skills, message):
    config = _magnitude_case(case, skills)
    assert main([str(config), "--model", "mock"]) == 2
    assert message in capsys.readouterr().err


def test_physical_only_run_has_no_cognitive_audit_warning(case, caplog):
    """R5 walk finding 10: a psychological_framework: none case has no
    appraisal, so the missing cognitive_audit is not worth a warning."""
    import logging

    config, data = case
    data["agent"]["psychological_framework"] = "none"
    data["global_config"]["run"] = {"world": "world:build", "years": 1, "agent_count": 1}
    _write_yaml(config, data)
    with caplog.at_level(logging.WARNING):
        assert main([str(config), "--model", "mock"]) == 0
    assert not [r for r in caplog.records if "[AuditInvariant]" in r.getMessage()]


def _cap_case(case, attempt_magnitude_columns):
    """One decision: the mock proposes inspect 0.9, a Python check blocks any
    number above 0.5, and the retry proposes inspect 0.3."""
    config, data = case
    (config.parents[1] / "capped.py").write_text(dedent('''
        import json
        from broker.interfaces.skill_types import ExecutionResult, ValidationResult
        from broker.utils.llm_utils import LLMStats

        class World:
            year = 0

            def advance_step(self):
                self.year += 1
                return {"current_year": self.year}

            def execute_skill(self, approved_skill):
                return ExecutionResult(success=True, state_changes={})

        def build(ctx):
            return World()

        def cap(proposal, context, registry):
            number = proposal.magnitude_pct
            ok = number is None or number <= 0.5
            return ValidationResult(
                valid=ok, validator_name="cap", errors=[] if ok else ["above 0.5"],
                metadata={"rule_id": "cap"},
            )

        def validators(ctx):
            return (cap,)

        def mock(ctx):
            numbers = iter([0.9, 0.3])

            def respond(prompt):
                payload = {"decision": "2", "magnitude": next(numbers)}
                text = "<<<DECISION_START>>>" + json.dumps(payload) + "<<<DECISION_END>>>"
                return text, LLMStats(success=True)
            return respond
    '''), encoding="utf-8")
    data["agent"]["response_format"]["fields"].insert(
        0, {"key": "magnitude", "type": "numeric", "min": 0, "max": 1, "required": True})
    data["global_config"]["run"] = {"world": "capped:build", "mock": "capped:mock",
                                    "validators": "capped:validators",
                                    "years": 1, "agent_count": 1}
    if attempt_magnitude_columns is not None:
        data["global_config"]["audit"] = {"attempt_magnitude_columns": attempt_magnitude_columns}
    _write_yaml(config, data)
    return config


def test_attempt_magnitude_columns_keep_the_blocked_number(case):
    """R5 walk finding 6: on a repaired row reason_magnitude is the approved
    0.3; the blocked 0.9 was nowhere in the row."""
    config = _cap_case(case, True)
    assert main([str(config), "--model", "mock"]) == 0
    [row] = _audit_rows(config.parents[1] / "results" / "agent_types")
    assert (row["status"], row["retry_count"]) == ("APPROVED", "1")
    assert row["reason_magnitude"] == "0.3"
    assert row["initial_magnitude"] == "0.9"
    assert row["attempt_magnitudes"] == "0.9|0.3"


@pytest.mark.parametrize("flag", [None, False])
def test_attempt_magnitude_columns_off_add_no_column(case, flag):
    config = _cap_case(case, flag)
    assert main([str(config), "--model", "mock"]) == 0
    [row] = _audit_rows(config.parents[1] / "results" / "agent_types")
    assert "initial_magnitude" not in row and "attempt_magnitudes" not in row
