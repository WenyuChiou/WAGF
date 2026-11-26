"""Twin-run check for Invariant 7 (broker/tools/check_governance_carryover.py)."""
import json
import sys
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

import pytest
import yaml

from broker.tools import check_governance_carryover as twin

REPO = Path(__file__).resolve().parents[2]

WORLD = '''
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


def block_inspect(proposal, context, registry):
    if proposal.skill_name != "inspect":
        return []
    return [ValidationResult(valid=False, validator_name="no_inspect",
                             errors=["inspect is not allowed"],
                             metadata={"rule_id": "no_inspect", "level": "ERROR"})]


def validators(ctx):
    return (block_inspect,)


def mock(ctx):
    # Year 1: inspect on every attempt, so the default runs. Year 2: inspect,
    # then wait once the retry prompt says inspect is not allowed. Year 3: wait.
    def invoke(prompt):
        if "Year 2:" in prompt:
            return '{"decision": 1}', LLMStats(success=True)
        if "Year 1:" in prompt and (RETRY and "not allowed" in prompt):
            return '{"decision": 1}', LLMStats(success=True)
        return '{"decision": 2}', LLMStats(success=True)
    return invoke
'''


@pytest.fixture
def make_case(tmp_path, monkeypatch):
    """``make_case(style=None, retry=True)`` -> path of a one-type case's YAML."""
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    folders = []

    def make(style=None, retry=True):
        folder = tmp_path / f"case_{uuid4().hex}"
        folders.append(folder.name)
        config = folder / "config" / "agent_types.yaml"
        config.parent.mkdir(parents=True)
        (folder / "__init__.py").touch()
        (folder / "world.py").write_text(f"RETRY = {retry}\n" + dedent(WORLD), encoding="utf-8")
        config.with_name("skill_registry.yaml").write_text(yaml.safe_dump({
            "default_skill": "wait",
            "skills": [{"skill_id": "wait", "description": "Wait for the next year"},
                       {"skill_id": "inspect", "description": "Inspect the site"}],
        }), encoding="utf-8")
        agent = {
            "psychological_framework": "generic",
            "prompt_template": "Memory:\n{memory}\n\nAvailable actions\n{options_text}\n\n{response_format}",
            "actions": [{"id": "wait", "aliases": ["1"]}, {"id": "inspect", "aliases": ["2"]}],
            "parsing": {"skill_map": {"1": "wait", "2": "inspect"}, "default_skill": "wait"},
            "response_format": {
                "delimiter_start": "<<<DECISION_START>>>", "delimiter_end": "<<<DECISION_END>>>",
                "fields": [{"key": "decision", "type": "choice", "required": True}],
            },
        }
        if style is not None:
            agent["memory"] = {"rejection_line_style": style}
        config.write_text(yaml.safe_dump({
            "global_config": {"run": {"world": "world:build", "validators": "world:validators",
                                      "mock": "world:mock"}},
            "agent": agent,
        }), encoding="utf-8")
        return config

    yield make
    for name in list(sys.modules):
        if any(name == f or name.startswith(f"{f}.") for f in folders):
            sys.modules.pop(name, None)


ARGS = ["--years", "3", "--agents", "2"]


def _check(config, tmp_path, name="twin", **kw):
    return twin.check(config, years=3, agents=2, output=tmp_path / name, **kw)


def test_executed_style_passes(make_case, tmp_path):
    report = _check(make_case(), tmp_path)
    assert report["run_a"]["default_rows"] == 2
    assert report["run_a"]["approved_after_retry_rows"] == 2
    assert report["run_b"] == {"rows": 6, "default_rows": 0, "approved_after_retry_rows": 0}
    assert report["status"] == "pass", report.get("differences")
    # Run B really was the unblocked twin: every row approved at the first try.
    out_b = Path(report["output"]) / "run_b"
    assert {e["origin"] for e in twin._read_jsonl(out_b / "memory_log.jsonl")} == {"decision"}


def test_explicit_style_fails_and_names_the_line(make_case, tmp_path, capsys):
    config = make_case(style="explicit")
    assert twin.main([str(config), *ARGS, "--output", str(tmp_path / "twin")]) == 1
    out = capsys.readouterr().out
    assert "FAIL:" in out
    assert "memory_log.jsonl | agent agent_1 period 1 | content" in out
    assert "was rejected" in out


def test_a_hook_that_writes_was_rejected_fails(make_case, tmp_path, monkeypatch):
    """The must-fail case: the runner's own line is clean, a case hook leaks."""
    prepare = twin._entry.prepare

    def leaky_prepare(argv):
        prepared = prepare(argv)
        runner = prepared.runner

        def post_step(agent, result):
            if getattr(getattr(result, "outcome", None), "name", "") == "REJECTED":
                runner.memory_engine.add_memory(
                    agent.id, "Your proposal was rejected.", {"origin": "world"})

        runner.hooks["post_step"] = post_step
        return prepared

    monkeypatch.setattr(twin._entry, "prepare", leaky_prepare)
    report = _check(make_case(), tmp_path)
    assert report["status"] == "fail"
    files = {d["file"] for d in report["differences"]}
    assert {"memory_log.jsonl", "raw traces"} <= files
    assert any(d["a"] == "Your proposal was rejected." or "was rejected" in json.dumps(d["a"])
               for d in report["differences"] if d["file"] == "memory_log.jsonl")


def test_a_run_without_a_retry_row_proves_nothing(make_case, tmp_path, capsys):
    config = make_case(retry=False)
    assert twin.main([str(config), *ARGS, "--output", str(tmp_path / "twin")]) == 3
    assert "INCONCLUSIVE" in capsys.readouterr().out
    assert not (tmp_path / "twin" / "run_b").exists()
    # --require any accepts the default rows alone.
    report = _check(config, tmp_path, "twin_any", require="any")
    assert report["status"] == "pass", report.get("differences")


def test_missing_files_in_both_runs_do_not_pass(make_case, tmp_path, monkeypatch):
    """Empty memory logs and traces on both sides compare equal; that is no pass."""
    monkeypatch.setattr(twin, "_read_jsonl", lambda path: [])
    report = _check(make_case(), tmp_path)
    assert report["status"] == "inconclusive"
    assert "memory_log.jsonl" in report["reason"]
    assert "raw traces" in report["reason"]


def test_a_default_without_a_number_compares_equal_to_no_numbers():
    assert twin._world_parameters({"magnitude_pct": None, "magnitude_fallback": True}) == {}
    assert twin._world_parameters({"magnitude_pct": 0.5, "magnitude_fallback": False, "x": 1}) == {
        "magnitude_pct": 0.5, "magnitude_fallback": False, "x": 1}


def test_a_used_output_folder_is_refused(make_case, tmp_path, capsys):
    (tmp_path / "twin" / "run_a").mkdir(parents=True)
    (tmp_path / "twin" / "run_a" / "old.txt").write_text("x", encoding="utf-8")
    assert twin.main([str(make_case()), *ARGS, "--output", str(tmp_path / "twin")]) == 2
    assert "not empty" in capsys.readouterr().err


def test_reservoir_control_passes(tmp_path, monkeypatch):
    """The coupled example: one row is approved after a retry, none falls back."""
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.chdir(tmp_path)
    config = REPO / "examples" / "reservoir_control" / "config" / "reservoir_agent_types.yaml"
    report = twin.check(config, output=tmp_path / "twin", require="any")
    assert report["run_a"]["approved_after_retry_rows"] == 1
    assert report["status"] == "pass", report.get("differences")
