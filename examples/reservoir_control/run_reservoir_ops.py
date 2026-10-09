"""Runnable reservoir continuous-control experiment.

Usage:
  python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4

DECISION TIMING (hindcast-then-set): each year the runner first advances the
solver 12 monthly sub-steps under the LAST committed release target, THEN the
operator decides. The decision therefore governs the COMING year, so the
dead-pool projection feeds on (a) storage at the end of the year just run and
(b) the NEXT year's inflow forecast — `inflow_forecast_for_year(year + 1)`
(review C1: feeding the just-consumed year's inflow as the "forecast" made
the wall fire for the wrong physical reason).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

import examples.reservoir_control  # noqa: E402,F401
from broker.agents import AgentConfig, BaseAgent  # noqa: E402
from broker.agents.base import Skill  # noqa: E402
from broker.components.memory.engine import WindowMemoryEngine  # noqa: E402
from broker.coupling import CouplingContract, VarSpec, resolve_coupling_enabled  # noqa: E402
from broker.core.experiment import ExperimentBuilder  # noqa: E402
from broker.domains.registry import DomainPackRegistry  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402
from examples.reservoir_control.ops_modules import (  # noqa: E402
    ReservoirOpsBundle,
    ToyLinearEvapReservoir,
    ToyMassBalanceReservoir,
)

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config"
PROMPT_ENV_KEYS = (
    "current_year",
    "storage",
    "spill",
    "shortfall",
    "release_actual",
    "inflow_forecast_year",
    "dead_pool",
    "capacity",
    "demand_year",
    "storage_now",
)

# {options_text} menu, injected via dynamic_state (real-LLM e4b finding,
# 2026-06-10): the hub-less builder path (BaseAgentContextBuilder) does not
# populate options_text, so the placeholder rendered "[N/A]" and the format
# example's hardcoded default claimed "choose ONE from: 1, 2, or 3" for a
# 2-action menu — the LLM was deciding blind. Keep numbering in lockstep
# with parsing.skill_map in reservoir_agent_types.yaml.
OPTIONS_TEXT = (
    "1. set_release — set the coming year's monthly release target as a "
    "percentage of demand (provide magnitude 0-100)\n"
    "2. maintain_release — keep the previously committed release target"
)


def _decision_payload(decision: str, **fields: Any):
    payload = dict(fields)
    payload["decision"] = decision
    payload.setdefault("reasoning", f"scripted mock chose {decision}")
    return (
        f"<<<DECISION_START>>>\n{json.dumps(payload)}\n<<<DECISION_END>>>",
        LLMStats(),
    )


def _operator_mock(prompt: str):
    # 50% clears the year-3 wall (passing threshold ~53.8% — see the
    # ops_modules docstring arithmetic); review C2: 60% also projected below
    # dead pool, so the retry never resolved and the insurer-pattern
    # narrative (wall -> retry -> APPROVED) was broken.
    magnitude = 50 if "BLOCKED" in prompt or "dead_pool_violation" in prompt else 100
    return _decision_payload(
        "set_release",
        magnitude=magnitude,
        reasoning=f"scripted reservoir release at {magnitude}% of demand",
    )


def _install_scripted_mock(runner) -> None:
    runner._llm_cache["operator"] = _operator_mock


def _sync_prompt_env(agent: BaseAgent, env: Dict[str, Any]) -> None:
    for key in PROMPT_ENV_KEYS:
        if key in env:
            agent.dynamic_state[key] = env[key]
    agent.dynamic_state["options_text"] = OPTIONS_TEXT


def _make_operator() -> BaseAgent:
    cfg = AgentConfig(
        name="OPERATOR",
        agent_type="operator",
        state_params=[],
        objectives=[],
        constraints=[],
        skills=[
            Skill("set_release", "Set monthly release percentage", None, "none"),
            Skill("maintain_release", "Maintain previous release", None, "none"),
        ],
    )
    return BaseAgent(cfg)


def _build_contract() -> CouplingContract:
    return CouplingContract(
        observations=(
            # Cadence vocabulary (review W4): "per_decision" here describes
            # the DELIVERED cadence — the agent receives exactly ONE storage
            # value per decision (the post-reduce year-end value), which is
            # the semantics check_cadence accepts as explicit. The underlying
            # solver series is still monthly; ContinuousBundle collects all
            # 12 sub-step values and reduces with "last". If check_cadence
            # ever learns to accept per_solver_step+last as explicit, prefer
            # that declaration.
            VarSpec(
                "storage",
                float,
                "maf",
                lo=0.0,
                hi=ToyMassBalanceReservoir.CAPACITY,
                cadence="per_decision",
                observation_reduce="last",
            ),
            VarSpec(
                "spill",
                float,
                "maf",
                lo=0.0,
                cadence="per_solver_step",
                observation_reduce="sum",
                consumer_of_record=False,
            ),
            VarSpec(
                "shortfall",
                float,
                "maf",
                lo=0.0,
                cadence="per_solver_step",
                observation_reduce="sum",
                consumer_of_record=False,
            ),
            VarSpec(
                "release_actual",
                float,
                "maf_per_month",
                lo=0.0,
                hi=1.125,
                cadence="per_solver_step",
                observation_reduce="mean",
                consumer_of_record=False,
            ),
        ),
        inputs=(
            VarSpec(
                "release_target",
                float,
                "maf_per_month",
                lo=0.0,
                hi=1.125,
                direction="agent_to_world",
                # Contract disagreement: the brief asks for value_source="proposal",
                # but the shipped adapter compares proposal-sourced inputs against
                # the original ApprovedSkill parameters before this domain bundle
                # can derive release_target from magnitude_pct. The bundle enforces
                # the same range before mutation; report this until derived
                # proposal inputs are supported generically.
                value_source="world_deterministic",
            ),
        ),
        decision_cadence="annual",
        solver_cadence="sub_step",
        control_hold_policy="constant",
        substeps_per_decision=12,
    )


def _make_solver(model: str):
    if "linear" in model.lower():
        return ToyLinearEvapReservoir()
    return ToyMassBalanceReservoir()


def _build_runner(args):
    agents = {"OPERATOR": _make_operator()}
    solver = _make_solver(args.model)
    bundle = ReservoirOpsBundle(contract=_build_contract(), solver=solver)

    with open(CONFIG / "reservoir_agent_types.yaml", encoding="utf-8") as fh:
        yaml_cfg = yaml.safe_load(fh)
    pack = DomainPackRegistry.get("reservoir_control")
    enabled, source = resolve_coupling_enabled(yaml_cfg, pack)
    if not enabled:
        raise SystemExit("reservoir_control requires global_config.coupling.enable: true")
    print(f"[coupling] enable=True (source={source}); adapter injected by the builder")

    env_holder: Dict[str, Dict[str, Any]] = {}

    def on_pre_year(year, env, all_agents):
        # year + 1: the decision being made now governs the COMING year's
        # release (hindcast-then-set — see module docstring / review C1).
        forecast = solver.inflow_forecast_for_year(year + 1)
        env.update(
            {
                "storage_now": env.get("storage"),
                "inflow_forecast_year": forecast,
                "demand_year": ToyMassBalanceReservoir.DEMAND_YEAR,
                "dead_pool": ToyMassBalanceReservoir.DEAD_POOL,
                "capacity": ToyMassBalanceReservoir.CAPACITY,
            }
        )
        env_holder["env"] = env
        for agent in all_agents.values():
            _sync_prompt_env(agent, env)
        print(
            f"\n--- Year {year} --- storage={env.get('storage'):.3f} maf "
            f"spill={env.get('spill'):.3f} shortfall={env.get('shortfall'):.3f} "
            f"release_actual={env.get('release_actual'):.3f} "
            f"forecast={forecast:.3f}"
        )

    def on_post_step(agent, result):
        appr = getattr(result, "approved_skill", None)
        skill_name = appr.skill_name if appr else "?"
        status = appr.approval_status if appr else getattr(result, "outcome", "N/A")
        retries = getattr(result, "retry_count", 0)
        errors = getattr(result, "validation_errors", []) or []
        wall = " wall_events=" + "; ".join(errors) if errors else ""
        mark = f" [governance re-prompted {retries}x]" if retries else ""
        env = env_holder.get("env") or {}
        print(
            f"  {agent.name}: {skill_name} ({status}){mark}{wall} | "
            f"storage={env.get('storage'):.3f} spill={env.get('spill'):.3f} "
            f"shortfall={env.get('shortfall'):.3f} "
            f"release_actual={env.get('release_actual'):.3f}"
        )

    def on_post_step_end(year, all_agents):
        return None

    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_coupling(bundle.contract, bundle, domain="reservoir_control")
        .with_governance("strict", str(CONFIG / "reservoir_agent_types.yaml"))
        .with_skill_registry(str(CONFIG / "reservoir_skill_registry.yaml"))
        .with_memory_engine(WindowMemoryEngine(window_size=3))
        .with_lifecycle_hooks(
            pre_year=on_pre_year,
            post_step=on_post_step,
            post_step_end=on_post_step_end,
        )
        .with_exact_output(args.output)
        # workers=1 is a HARD requirement here (INVARIANTS.md AR-3): hooks
        # mutate the shared env dict for prompt/governance visibility.
        .with_workers(1)
        .with_seed(args.seed)
    ).build()
    return runner, bundle


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reservoir continuous-control experiment")
    ap.add_argument("--model", default="mock", help="LLM model or 'mock'")
    ap.add_argument("--thinking-mode", choices=["auto", "disabled", "enabled"],
                    default=None, help="Ollama thinking policy (default: framework setting)")
    ap.add_argument("--years", type=int, default=4)
    ap.add_argument("--output", default=str(HERE / "results_ops"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    if args.thinking_mode is not None:
        from broker.utils.llm_utils import LLM_CONFIG
        LLM_CONFIG.thinking_mode = args.thinking_mode

    runner, _bundle = _build_runner(args)
    if args.model.lower().startswith("mock"):
        _install_scripted_mock(runner)

    print(
        "Reservoir continuous-control run | "
        f"model={args.model} years={args.years}"
    )
    print("=" * 72)
    runner.run()
    print(f"\nDone. Audit + traces under: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
