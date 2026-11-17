"""Focused regressions for the generic-module review (no model services)."""
import hashlib
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from broker.utils.agent_config import AgentTypeConfig


@pytest.mark.parametrize("label", ["Extreme"])
def test_invalid_appraisal_is_a_format_error(label):
    from broker.tests.test_grounded_governance_pr6 import _config, _validator, _run
    cfg = _config({"operator_agent": {"governance": {"default": {"thinking_rules": [
        {"id": "r", "construct": "TP_LABEL", "expected_levels": ["VH"],
         "blocked_skills": ["stand_by"], "message": "blocked"}
    ]}}}})
    findings = _run(_validator(cfg), "stand_by", {"TP_LABEL": label})
    fmt = [r for r in findings if not r.valid and r.metadata.get("category") == "format"]
    assert fmt
    # A bad label is a format problem, not an expected hard block in the
    # terminal taxonomy; constraint_type "hard" still declines keep_proposal.
    assert fmt[0].metadata["expected_terminal"] is False
    assert fmt[0].metadata["constraint_type"] == "hard"


@pytest.mark.parametrize("label", ["VERY HIGH", "VH"])
def test_valid_appraisal_still_blocks(label):
    from broker.tests.test_grounded_governance_pr6 import _config, _validator, _run
    cfg = _config({"operator_agent": {"governance": {"default": {"thinking_rules": [
        {"id": "r", "conditions": [{"construct": "TP_LABEL", "values": ["VH"]}],
         "blocked_skills": ["stand_by"], "message": "blocked"}
    ]}}}})
    assert any(not r.valid for r in _run(_validator(cfg), "stand_by", {"TP_LABEL": label}))


@pytest.mark.parametrize("policy", ["default", "keep_proposal"])
@pytest.mark.parametrize("blocked", [False, True])
@pytest.mark.parametrize("success", [False, True])
def test_execution_success_reaches_csv(policy, blocked, success):
    from broker.tests.test_retry_exhaustion_policy import _engine, _run
    from broker.interfaces.skill_types import ExecutionResult
    from broker.components.analytics.audit import trace_to_csv_row
    eng, sim, writer = _engine(policy)
    eng._corrected_status_columns = True
    if not blocked:
        eng.validators = []
    sim.execute_skill = lambda skill: ExecutionResult(success=success, state_changes={})
    _run(eng)
    assert trace_to_csv_row(writer.traces[0])["execution_success"] is success


def test_no_engine_has_blank_execution_success():
    from broker.tests.test_retry_exhaustion_policy import _engine, _run
    eng, _, writer = _engine("default")
    eng._corrected_status_columns = True
    eng.simulation_engine = None
    eng.validators = []
    _run(eng)
    assert writer.traces[0]["execution_success"] == ""


def test_disabled_audit_flag_omits_execution_success():
    from broker.tests.test_retry_exhaustion_policy import _engine, _run
    eng, _, writer = _engine("default")
    eng._corrected_status_columns = False
    _run(eng)
    assert "execution_success" not in writer.traces[0]


def test_manifest_defaults_and_launch_sources(tmp_path, monkeypatch):
    from broker.tests.test_manifest_llm_params import _make_finalize_runner
    from broker.components.governance.registry import SkillRegistry
    path = tmp_path / "skills.yaml"
    path.write_text("default_skill: hold\nskills:\n- skill_id: hold\n", encoding="utf-8")
    reg = SkillRegistry()
    reg.register_from_yaml(str(path))
    runner = _make_finalize_runner(tmp_path)
    runner.broker.skill_registry = reg
    runner.broker.context_builder = SimpleNamespace(prompt_templates={"agent": "inline template"})
    runner._git_dirty_files_at_launch = [" M dirty.py"]
    runner._git_dirty_files_truncated_at_launch = False
    monkeypatch.setattr("sys.argv", ["run.py", "--model", "mock"])
    # Input bytes are retained at load; later file changes must not rewrite provenance.
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_text("changed", encoding="utf-8")
    m = runner._collect_reproducibility_metadata()
    assert m["default_skill"] == "hold"
    assert m["default_skill_checked_by_validators"] is False
    assert m["git_dirty_files"] == [" M dirty.py"]
    assert m["git_dirty_files_truncated"] is False
    assert m["launch_command"] == "run.py --model mock"
    assert m["skill_registry_sha256"] == expected
    assert m["prompt_template_sha256"] == {"agent": hashlib.sha256(b"inline template").hexdigest()}


def test_unknown_config_keys_warn_once(tmp_path, caplog):
    path = tmp_path / "agent_types.yaml"
    path.write_text("globl_config: {}\nagent:\n  actions: []\n  parsng: {}\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        AgentTypeConfig.load(str(path), force_reload=True)
        AgentTypeConfig.load(str(path), force_reload=True)
    for key in ("globl_config", "parsng"):
        assert sum("Unknown" in r.message and key in r.message for r in caplog.records) == 1


def test_builder_refuses_undeclared_profile(tmp_path):
    from broker.core.experiment_builder import ExperimentBuilder
    path = tmp_path / "agent_types.yaml"
    path.write_text("agent:\n  governance:\n    strict: {}\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="not declared"):
        ExperimentBuilder().with_governance("strcit", str(path))


PARAMETERS = ["decay_rate", "consolidation_prob", "consolidation_probability",
              "consolidation_threshold", "forgetting_threshold",
              "W_recency", "W_importance", "W_context", "importance_boost", "base_importance"]


@pytest.mark.parametrize("key", PARAMETERS)
@pytest.mark.parametrize("value", [1.5, -0.1, "abc", True])
def test_supplied_memory_fraction_rejected(key, value):
    from broker.components.memory.factory import create_memory_engine
    with pytest.raises(ValueError, match=key):
        create_memory_engine("window", {key: value})


@pytest.mark.parametrize("value", [1.5, -0.1, "abc", True])
def test_retrieval_fraction_rejected(tmp_path, value):
    path = tmp_path / "agent_types.yaml"
    path.write_text(yaml.safe_dump({"global_config": {"governance": {"retrieval": {"min_score": value}}}}), encoding="utf-8")
    with pytest.raises(ValueError, match="min_score"):
        AgentTypeConfig.load(str(path), force_reload=True)


@pytest.mark.parametrize("value", [0, 1, 0.5])
@pytest.mark.parametrize("key", PARAMETERS)
def test_memory_fraction_boundaries_allowed(key, value):
    from broker.components.memory.factory import create_memory_engine
    create_memory_engine("window", {key: value})


def test_scaffold_enables_full_audit_columns():
    from broker.tools.scaffold_domain import gen_agent_types_yaml
    data = yaml.safe_load(gen_agent_types_yaml("energy", ["hold"], "pmt"))
    audit = data["global_config"]["audit"]
    assert all(audit[key] is True for key in
               ("initial_proposal_columns", "attempt_columns", "corrected_status_columns"))


@pytest.mark.parametrize("final_digest", [None, "sha256:recovered"])
def test_model_digest_retries_without_network(monkeypatch, final_digest):
    from broker.core.experiment_runner import ExperimentRunner
    from broker.utils import llm_utils
    runner = ExperimentRunner.__new__(ExperimentRunner)
    runner.config = SimpleNamespace(model="test-local-model")
    calls, sleeps = [], []

    def metadata(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            return None
        return {"digest": final_digest if len(calls) == 4 else None}

    monkeypatch.setattr(llm_utils, "get_ollama_show_metadata", metadata)
    monkeypatch.setattr("requests.get", lambda *a, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {"models": []}))
    monkeypatch.setattr("time.sleep", sleeps.append)
    runner._capture_model_metadata_at_launch()
    assert len(calls) == 4
    assert sleeps == [0.1, 0.1, 0.1]
    assert runner._model_metadata_at_launch["model_digest"] == final_digest
    assert ("model_digest_error" in runner._model_metadata_at_launch) is (final_digest is None)


def test_dirty_files_capped_at_launch(monkeypatch, tmp_path):
    from broker.core.experiment_runner import ExperimentRunner, ExperimentConfig
    monkeypatch.setattr("subprocess.check_output", lambda command, **kw:
                        b"abc123\n" if "rev-parse" in command else
                        "\n".join(f" M file_{n}.py" for n in range(201)).encode())
    broker = SimpleNamespace(context_builder=SimpleNamespace(prompt_templates={}))
    runner = ExperimentRunner(broker, None, {}, ExperimentConfig(model="mock", output_dir=tmp_path))
    assert len(runner._git_dirty_files_at_launch) == 200
    assert runner._git_dirty_files_at_launch[0] == " M file_0.py"
    assert runner._git_dirty_files_truncated_at_launch is True


def test_prompt_file_hash_retains_loaded_bytes(tmp_path):
    from broker.tests.test_manifest_llm_params import _make_finalize_runner
    prompt = tmp_path / "prompt.txt"
    prompt.write_bytes(b"first line\r\nsecond line\r\n")
    path = tmp_path / "agent_types.yaml"
    path.write_text("agent:\n  prompt_template_file: prompt.txt\n", encoding="utf-8")
    runner = _make_finalize_runner(tmp_path)
    runner.broker.config = AgentTypeConfig.load(str(path))
    runner.broker.context_builder = SimpleNamespace(prompt_templates={"agent": prompt.read_text()})
    runner._prompt_template_sha256_at_launch = runner._prompt_template_hashes()
    expected = hashlib.sha256(prompt.read_bytes()).hexdigest()
    prompt.write_text("changed after launch", encoding="utf-8")
    assert runner._collect_reproducibility_metadata()["prompt_template_sha256"] == {"agent": expected}


def test_unknown_blocked_skill_warns_once(tmp_path, caplog):
    from broker.components.governance.registry import SkillRegistry
    path = tmp_path / "agent_types.yaml"
    path.write_text(yaml.safe_dump({"agent": {"thinking_rules": [
        {"id": "r", "blocked_skills": ["typo_skill"], "message": "blocked"}
    ]}}), encoding="utf-8")
    cfg = AgentTypeConfig.load(str(path))
    with caplog.at_level(logging.WARNING):
        cfg.warn_unknown_blocked_skills(SkillRegistry())
        cfg.warn_unknown_blocked_skills(SkillRegistry())
    assert sum("blocked_skills" in r.message and "typo_skill" in r.message for r in caplog.records) == 1


@pytest.mark.parametrize("config_dir", ["examples/single_agent", "examples/irrigation_abm/config",
                                      "examples/irrigation_abm/config_variants/simple"])
def test_paper_configs_have_no_new_warnings(config_dir, caplog):
    from broker.components.governance.registry import SkillRegistry
    from broker.components.memory.factory import create_memory_engine
    config_dir = Path(config_dir)
    with caplog.at_level(logging.WARNING):
        cfg = AgentTypeConfig.load(str(config_dir / "agent_types.yaml"), force_reload=True)
        registry = SkillRegistry()
        registry.register_from_yaml(str(config_dir / "skill_registry.yaml"))
        cfg.warn_unknown_blocked_skills(registry)
        create_memory_engine("humancentric", cfg.get_global_memory_config())
    assert not [r.message for r in caplog.records if "Unknown key" in r.message or "Unknown blocked_skills" in r.message]


def test_flood_rejected_proposal_logs_executed_default():
    from examples.single_agent.tests.test_runner_changes import _FakeAgent, _make_sim, _make_hook
    from broker.interfaces.skill_types import SkillOutcome, ExecutionResult
    agent = _FakeAgent("A1")
    hook = _make_hook(_make_sim({agent.id: agent}))
    result = SimpleNamespace(
        skill_proposal=SimpleNamespace(skill_name="elevate_house", reasoning={}),
        approved_skill=SimpleNamespace(skill_name="elevate_house", validation_results=[]),
        executed_skill="do_nothing", outcome=SkillOutcome.REJECTED,
        execution_result=ExecutionResult(success=True, state_changes={}), retry_count=3,
    )
    hook.post_step(agent, result)
    hook.post_year(1, {agent.id: agent})
    assert hook.logs[0]["yearly_decision"] == "elevate_house"
    assert hook.logs[0]["executed_decision"] == "do_nothing"


def test_irrigation_rejected_proposal_logs_executed_default(tmp_path, monkeypatch):
    import csv
    from examples.irrigation_abm import run_experiment
    monkeypatch.setattr("sys.argv", ["run_experiment.py", "--model", "mock",
                        "--agents", "1", "--years", "1", "--seed", "42",
                        "--governance-mode", "strict", "--config-dir",
                        "examples/irrigation_abm/config_variants/simple", "--output", str(tmp_path / "run")])
    run_experiment.main()
    with (tmp_path / "run/simulation_log.csv").open(newline="", encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    with (tmp_path / "run/irrigation_farmer_governance_audit.csv").open(newline="", encoding="utf-8-sig") as f:
        audit = next(csv.DictReader(f))
    assert audit["status"] == "REJECTED"
    assert row["executed_decision"] == audit["executed_skill"] == "maintain_demand"


@pytest.mark.parametrize("threshold", [2.0, 99.0])
@pytest.mark.parametrize("config", [
    {"engine": "universal", "stimulus_key": "flood_depth_m"},
    {"engine": "humancentric"},
])
def test_arousal_threshold_is_not_a_fraction(config, threshold):
    # The universal engine compares it with an absolute surprise score
    # (default 2.0; 99.0 documented for always-System-1 runs).
    from broker.components.memory.factory import create_memory_engine
    params = {k: v for k, v in config.items() if k != "engine"}
    engine = create_memory_engine(config["engine"], {**params, "arousal_threshold": threshold})
    assert engine is not None
