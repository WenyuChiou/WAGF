"""energy experiment entry point - minimal runnable smoke.

Replace SyntheticEnvironment with your real ABM as the domain matures.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Path setup + package import below are guarded/checked on purpose --
# see scaffold_domain.py's "Generated runner: sys.path / import
# safety" docstring section for the rationale.
_PKG_DIR = Path(__file__).resolve().parent
_CONTAINER_DIR = _PKG_DIR.parent  # e.g. examples/, for the default output layout
sys.path.insert(0, str(_CONTAINER_DIR))
_REPO_ROOT = _CONTAINER_DIR.parent
if (_REPO_ROOT / "broker" / "__init__.py").exists():
    sys.path.insert(0, str(_REPO_ROOT))

import yaml  # noqa: E402

import importlib  # noqa: E402
_pkg = importlib.import_module(_PKG_DIR.name)  # noqa: E402
_pkg_file = getattr(_pkg, "__file__", None)  # noqa: E402
if _pkg_file is None or Path(_pkg_file).resolve().parent != _PKG_DIR:
    raise SystemExit(
        f"Imported '{_PKG_DIR.name}' from {_pkg_file}, not "
        f"{_PKG_DIR}. Rename the scaffold directory to something unique."
    )

from broker.agents import AgentConfig, BaseAgent, Skill  # noqa: E402
from broker.components.context.builder import TieredContextBuilder  # noqa: E402
from broker.components.memory.engine import WindowMemoryEngine  # noqa: E402
from broker.core.experiment import ExperimentBuilder  # noqa: E402
from broker.interfaces.skill_types import ExecutionResult  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config"


class SyntheticEnvironment:
    """Small stand-in for the domain ABM used by scaffold smoke runs."""

    def __init__(self):
        self.current_year = 0

    def advance_step(self):
        self.current_year += 1
        return {
            "current_year": self.current_year,
            # TODO: replace with a domain variable from your ABM.
            "domain_signal": 0.5,
        }

    def execute_skill(self, approved_skill):
        return ExecutionResult(success=True, state_changes={})


def load_declared_skills():
    data = yaml.safe_load(
        (CONFIG / "skill_registry.yaml").read_text(encoding="utf-8")
    ) or {}
    return [
        Skill(
            skill_id=item["skill_id"],
            description=item.get("description", item["skill_id"]),
            affected_param=None,
            direction="none",
        )
        for item in data.get("skills", [])
    ]


def build_agents(count, skills):
    return {
        f"agent_{i}": BaseAgent(
            AgentConfig(
                name=f"agent_{i}",
                agent_type="agent",
                state_params=[],
                objectives=[],
                constraints=[],
                skills=skills,
            )
        )
        for i in range(1, count + 1)
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--agents", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="results/smoke")
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = HERE / output_path

    skills = load_declared_skills()
    if not skills:
        raise SystemExit("No skills found in config/skill_registry.yaml")
    agents = build_agents(args.agents, skills)

    # Explicit TieredContextBuilder (hub=None), matching
    # examples/irrigation_abm's L3-1B
    # fix (2026-05-23): ExperimentBuilder.build()'s DEFAULT context
    # builder (create_context_builder() with no hub) is a plain
    # BaseAgentContextBuilder, which does NOT render {options_text}
    # or {response_format} at all -- both fall through to
    # SafeFormatter's "[N/A]" default, leaving the LLM with no menu
    # and no JSON schema example. Pinning TieredContextBuilder here
    # is what makes prompts/agent.txt's {options_text} placeholder
    # (see gen_prompt()) actually render the live skill list.
    mem_engine = WindowMemoryEngine(window_size=3)
    agent_types_path = CONFIG / "agent_types.yaml"
    prompt_template = (CONFIG / "prompts" / "agent.txt").read_text(encoding="utf-8")
    ctx_builder = TieredContextBuilder(
        agents=agents,
        hub=None,
        prompt_templates={"agent": prompt_template, "default": prompt_template},
        yaml_path=str(agent_types_path),
        memory_engine=mem_engine,
    )

    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(SyntheticEnvironment())
        .with_skill_registry(str(CONFIG / "skill_registry.yaml"))
        .with_memory_engine(mem_engine)
        .with_context_builder(ctx_builder)
        .with_governance("default", str(agent_types_path))
        .with_exact_output(str(output_path))
        .with_workers(1)
        .with_seed(args.seed)
    ).build()

    print(
        f"[energy] smoke run | model={args.model} "
        f"years={args.years} agents={args.agents}"
    )
    runner.run()
    print(f"Done. Audit + traces under: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
