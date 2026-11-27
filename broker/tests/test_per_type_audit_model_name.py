"""Tests that per-agent_type llm_params.model is stamped on audit & aborted traces."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from broker.agents import AgentConfig, BaseAgent, Skill
from broker.components.analytics.audit import AuditConfig, GenericAuditWriter
from broker.components.context.builder import BaseAgentContextBuilder
from broker.components.governance.registry import SkillRegistry
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.interfaces.skill_types import ExecutionResult, SkillDefinition, SkillProposal
from broker.utils.agent_config import AgentTypeConfig


class _SimpleSim:
    def advance_year(self):
        return {"current_year": 1}

    def execute_skill(self, approved_skill):
        return ExecutionResult(success=True, state_changes={})


class _SimpleAdapter:
    def __init__(self, cfg: AgentTypeConfig):
        self.agent_config = cfg
        self.last_parse_warnings = []

    def parse_output(self, raw_output, ctx):
        return SkillProposal(
            skill_name="hold",
            agent_id=ctx["agent_id"],
            reasoning={"reasoning": "ok"},
            agent_type=ctx.get("agent_type", "default"),
        )

    def format_retry_prompt(self, prompt, errors):
        return prompt


def _make_config(tmp_path: Path) -> AgentTypeConfig:
    yaml_path = tmp_path / "agent_types.yaml"
    yaml_path.write_text(
        yaml.safe_dump({
            "global_config": {},
            "household": {
                "agent_type": "household",
                "llm_params": {"model": "mock-household-4b"},
                "actions": [{"id": "hold", "description": "Hold"}],
            },
            "insurer": {
                "agent_type": "insurer",
                "llm_params": {"model": "mock-insurer-27b"},
                "actions": [{"id": "hold", "description": "Hold"}],
            },
            "regulator": {
                "agent_type": "regulator",
                "actions": [{"id": "hold", "description": "Hold"}],
            },
        }),
        encoding="utf-8",
    )
    AgentTypeConfig.clear_cache()
    return AgentTypeConfig.load(str(yaml_path), force_reload=True)


def test_per_agent_type_model_written_to_audit_traces(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "broker.utils.llm_utils.create_llm_invoke",
        lambda model_name, verbose=False, overrides=None: (lambda _prompt: "hold"),
    )
    cfg = _make_config(tmp_path)
    reg = SkillRegistry()
    reg.register(SkillDefinition(
        skill_id="hold",
        description="Hold",
        eligible_agent_types=["*"],
        preconditions=[],
        institutional_constraints={},
        allowed_state_changes=[],
        implementation_mapping="sim.hold",
    ))

    agents = {
        "h1": BaseAgent(AgentConfig(
            name="h1", agent_type="household", state_params=[], objectives=[], constraints=[],
            skills=[Skill(skill_id="hold", description="Hold", affected_param=None, direction="none")],
        )),
        "i1": BaseAgent(AgentConfig(
            name="i1", agent_type="insurer", state_params=[], objectives=[], constraints=[],
            skills=[Skill(skill_id="hold", description="Hold", affected_param=None, direction="none")],
        )),
        "r1": BaseAgent(AgentConfig(
            name="r1", agent_type="regulator", state_params=[], objectives=[], constraints=[],
            skills=[Skill(skill_id="hold", description="Hold", affected_param=None, direction="none")],
        )),
    }
    out_dir = tmp_path / "out"
    audit_writer = GenericAuditWriter(AuditConfig(output_dir=str(out_dir)))
    broker = SkillBrokerEngine(
        skill_registry=reg,
        model_adapter=_SimpleAdapter(cfg),
        validators=[],
        simulation_engine=_SimpleSim(),
        context_builder=BaseAgentContextBuilder(agents=agents),
        config=cfg,
        audit_writer=audit_writer,
    )
    runner = ExperimentRunner(
        broker=broker,
        sim_engine=_SimpleSim(),
        agents=agents,
        config=ExperimentConfig(
            model="mock-default",
            num_years=1,
            workers=1,
            output_dir=out_dir,
            seed=42,
        ),
    )
    runner.run()

    models_by_agent = {}
    for trace_file in (out_dir / "raw").glob("*.jsonl"):
        for line in trace_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if "_metadata" in rec:
                continue
            models_by_agent[rec["agent_id"]] = rec["model"]

    assert models_by_agent == {
        "h1": "mock-household-4b",
        "i1": "mock-insurer-27b",
        "r1": "mock-default",
    }

    # Verify _write_aborted_trace also records the per-type model name
    runner._write_aborted_trace(agents["i1"], "run_abort", {"current_year": 1}, RuntimeError("boom"))
    audit_writer.finalize()
    insurer_lines = [
        json.loads(line)
        for line in (out_dir / "raw" / "insurer_traces.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert insurer_lines[-1]["model"] == "mock-insurer-27b"
