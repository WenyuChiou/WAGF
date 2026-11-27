"""Tests that CouplingViolation inside execute_skill fails loud in ExperimentRunner."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from broker.agents import AgentConfig, BaseAgent, Skill
from broker.components.context.tiered import TieredContextBuilder
from broker.components.governance.registry import SkillRegistry
from broker.core.experiment_runner import ExperimentConfig, ExperimentRunner
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.coupling import (
    CouplingContract,
    CouplingViolation,
    EnvironmentCouplingAdapter,
    InterfaceBundle,
    VarSpec,
    WorldDelta,
)
from broker.interfaces.skill_types import SkillDefinition, SkillProposal
from broker.utils.agent_config import AgentTypeConfig


class _DummyRealEngine:
    def advance_year(self):
        return {"current_year": 1, "level": 0.5}


class _BrokenCommitBundle(InterfaceBundle):
    """Coupled bundle whose commit triggers CouplingViolation pre- or post-commit."""

    def __init__(self, *, mode: str):
        super().__init__(event_src=None)
        self._mode = mode

    def run_pipeline(self, base_env, events, operation_order, control_hold_policy="constant"):
        env = dict(base_env)
        env["level"] = 0.5
        return env

    def commit_world_delta(self, approved_skill):
        if self._mode == "post_range":
            return WorldDelta(world_changes={"release_rate": 5.0})
        return WorldDelta(world_changes={"release_rate": 0.5})


class _StubAdapter:
    def __init__(self, cfg: AgentTypeConfig, *, propose_release: float):
        self.agent_config = cfg
        self.last_parse_warnings = []
        self._propose_release = propose_release

    def parse_output(self, raw_output, ctx):
        return SkillProposal(
            skill_name="set_release",
            agent_id=ctx["agent_id"],
            reasoning={"reasoning": "ok"},
            agent_type=ctx.get("agent_type", "op"),
            parameters={"release_rate": self._propose_release},
        )

    def format_retry_prompt(self, prompt, errors):
        return prompt


def _skill_def(skill_id: str, description: str) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        description=description,
        eligible_agent_types=["op"],
        preconditions=[],
        institutional_constraints={},
        allowed_state_changes=[],
        implementation_mapping=f"sim.{skill_id}",
    )


def _build_coupled_runner(tmp_path: Path, *, mode: str, workers: int) -> ExperimentRunner:
    yaml_path = tmp_path / "agent_types.yaml"
    yaml_path.write_text(
        yaml.safe_dump({
            "global_config": {"coupling": {"enable": True}},
            "op": {
                "agent_type": "op",
                "prompt_template": "Decide {options_text}",
                "actions": [
                    {"id": "set_release", "description": "Set release"},
                    {"id": "hold", "description": "Hold"},
                ],
                "parsing": {"skill_map": {"1": "set_release", "2": "hold"}},
                "governance": {"strict": {"thinking_rules": [], "identity_rules": []}},
            },
        }),
        encoding="utf-8",
    )
    AgentTypeConfig.clear_cache()
    cfg = AgentTypeConfig.load(str(yaml_path), force_reload=True)

    contract = CouplingContract(
        observations=(
            VarSpec(name="level", dtype=float, unit="m", lo=0.0, hi=1.0, direction="world_to_agent"),
        ),
        inputs=(
            VarSpec(
                name="release_rate",
                dtype=float,
                unit="m3/s",
                lo=0.0,
                hi=1.0,
                direction="agent_to_world",
                value_source="proposal",
            ),
        ),
    )
    adapter_env = EnvironmentCouplingAdapter(
        _DummyRealEngine(),
        contract,
        _BrokenCommitBundle(mode=mode),
    )

    reg = SkillRegistry()
    reg.register(_skill_def("set_release", "Set release"))
    reg.register(_skill_def("hold", "Hold"))

    agent_ids = ["a1"] if workers == 1 else ["a1", "a2"]
    agents = {
        aid: BaseAgent(AgentConfig(
            name=aid,
            agent_type="op",
            state_params=[],
            objectives=[],
            constraints=[],
            skills=[
                Skill(skill_id="set_release", description="Set release", affected_param=None, direction="none"),
                Skill(skill_id="hold", description="Hold", affected_param=None, direction="none"),
            ],
        ))
        for aid in agent_ids
    }
    propose_val = 9.0 if mode == "pre_range" else 0.5
    context_builder = TieredContextBuilder(
        agents=agents,
        yaml_path=str(yaml_path),
        prompt_templates={"op": "Decide between options:\n{options_text}"},
    )
    broker = SkillBrokerEngine(
        skill_registry=reg,
        model_adapter=_StubAdapter(cfg, propose_release=propose_val),
        validators=[],
        simulation_engine=adapter_env,
        context_builder=context_builder,
        config=cfg,
    )
    return ExperimentRunner(
        broker=broker,
        sim_engine=adapter_env,
        agents=agents,
        config=ExperimentConfig(
            model="mock",
            num_years=1,
            workers=workers,
            output_dir=tmp_path / f"out_{mode}_{workers}",
            seed=42,
        ),
    )


@pytest.mark.parametrize("mode", ["pre_range", "post_range"])
@pytest.mark.parametrize("workers", [1, 2])
def test_coupling_violation_in_execute_skill_aborts_run_loudly(tmp_path, mode, workers, monkeypatch):
    monkeypatch.setattr(
        "broker.utils.llm_utils.create_llm_invoke",
        lambda model_name, verbose=False, overrides=None: (lambda _prompt: "set_release"),
    )
    runner = _build_coupled_runner(tmp_path, mode=mode, workers=workers)
    with pytest.raises(CouplingViolation, match="input contract violations"):
        runner.run()
    assert isinstance(runner._generic_abort, CouplingViolation)
