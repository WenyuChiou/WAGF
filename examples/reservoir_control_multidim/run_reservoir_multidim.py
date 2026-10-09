"""Runnable reservoir MULTI-DIMENSIONAL control experiment (Phase 6W-B7).

The operator sets THREE bounded setpoints in one decision — release_rate_cms,
hydropower_target_mw, flood_pool_pct — exercising the multi-dimensional-action
chain (B1-B6) end-to-end: propose 3 setpoints -> per-field ParameterBoundsValidator
(reject-and-retry) -> commit each named setpoint to the hosted ToyMultiReservoir
via a plain ContinuousBundle (B5 applies each named setpoint directly; no
derive/override) -> proposed_param_* + world_* audit columns.

Usage:
  python examples/reservoir_control_multidim/run_reservoir_multidim.py --model mock --years 4
  python examples/reservoir_control_multidim/run_reservoir_multidim.py --model gemma4:e4b --years 4

This is a MOCK-validated skeleton; the real gemma4:e4b worked run + its own
byte-identity baseline are a separate ollama task. See
.research/wagf_coupling_IMPLEMENTATION_PLAN_2026-06-12.md (B7).
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

import examples.reservoir_control_multidim  # noqa: E402,F401  registers pack + ParameterBoundsValidator
from broker.agents import AgentConfig, BaseAgent  # noqa: E402
from broker.agents.base import Skill  # noqa: E402
from broker.components.memory.engine import WindowMemoryEngine  # noqa: E402
from broker.coupling import (  # noqa: E402
    ContinuousBundle,
    CouplingContract,
    VarSpec,
    resolve_coupling_enabled,
)
from broker.core.experiment import ExperimentBuilder  # noqa: E402
from broker.domains.registry import DomainPackRegistry  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402
from examples.reservoir_control_multidim.ops_modules_multidim import ToyMultiReservoir  # noqa: E402

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

# {options_text} menu (injected via dynamic_state — the hub-less builder path does
# not populate it). Numbering MUST stay in lockstep with parsing.skill_map in
# multidim_agent_types.yaml.
OPTIONS_TEXT = (
    "1. set_release_multi — set three setpoints for the coming period: release "
    "rate (cms), hydropower target (MW), flood-pool allocation (%)\n"
    "2. maintain_release — keep the previously committed setpoints"
)

# Scripted in-bounds setpoints (release<=850, hydropower<=2000, flood_pool<=100).
_MOCK_SETPOINTS = {
    "release_rate_cms": 400.0,
    "hydropower_target_mw": 900.0,
    "flood_pool_pct": 20.0,
}


def _decision_payload(decision_id: int, **fields: Any):
    payload = dict(fields)
    payload["decision"] = decision_id
    payload.setdefault("reasoning", f"scripted mock chose decision {decision_id}")
    return (
        f"<<<DECISION_START>>>\n{json.dumps(payload)}\n<<<DECISION_END>>>",
        LLMStats(),
    )


def _operator_mock(prompt: str):
    # decision=1 -> set_release_multi with three in-bounds setpoints.
    return _decision_payload(
        1,
        reasoning="scripted multi-setpoint release",
        **_MOCK_SETPOINTS,
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
            Skill("set_release_multi", "Set three reservoir setpoints", None, "none"),
            Skill("maintain_release", "Maintain previous setpoints", None, "none"),
        ],
    )
    return BaseAgent(cfg)


def _build_contract() -> CouplingContract:
    # Same shape as broker/tests/test_reservoir_multidim_skeleton.py: one storage
    # observation + three proposal-sourced setpoint inputs. value_source="proposal"
    # (the names match the proposal params, so no derive — unlike single-dim).
    return CouplingContract(
        observations=(
            VarSpec(
                "storage", float, "maf", lo=0.0, hi=1e9,
                cadence="per_decision", observation_reduce="last",
            ),
        ),
        inputs=(
            VarSpec("release_rate_cms", float, "cms", lo=0.0, hi=850.0,
                    direction="agent_to_world", value_source="proposal"),
            VarSpec("hydropower_target_mw", float, "MW", lo=0.0, hi=2000.0,
                    direction="agent_to_world", value_source="proposal"),
            VarSpec("flood_pool_pct", float, "pct", lo=0.0, hi=100.0,
                    direction="agent_to_world", value_source="proposal"),
        ),
        decision_cadence="annual",
        solver_cadence="sub_step",
        control_hold_policy="constant",
        substeps_per_decision=12,
    )


def _build_runner(args):
    agents = {"OPERATOR": _make_operator()}
    solver = ToyMultiReservoir()
    bundle = ContinuousBundle(contract=_build_contract(), solver=solver)

    with open(CONFIG / "multidim_agent_types.yaml", encoding="utf-8") as fh:
        yaml_cfg = yaml.safe_load(fh)
    pack = DomainPackRegistry.get("reservoir_control_multidim")
    enabled, source = resolve_coupling_enabled(yaml_cfg, pack)
    if not enabled:
        raise SystemExit("reservoir_control_multidim requires global_config.coupling.enable: true")
    print(f"[coupling] enable=True (source={source}); adapter injected by the builder")

    env_holder: Dict[str, Dict[str, Any]] = {}

    def on_pre_year(year, env, all_agents):
        # ToyMultiReservoir is a trivial mass balance with no spill/shortfall
        # channel, so those prompt vars are toy zeros — the storage observation
        # is the live one (populated by the coupling advance before the decision).
        env.setdefault("spill", 0.0)
        env.setdefault("shortfall", 0.0)
        env.setdefault("release_actual", 0.0)
        env.update({
            "current_year": year,
            "storage_now": env.get("storage"),
            "inflow_forecast_year": 15.0,
            "demand_year": 12.0,
            "dead_pool": ToyMultiReservoir.DEAD_POOL,
            "capacity": ToyMultiReservoir.CAPACITY,
        })
        env_holder["env"] = env
        for agent in all_agents.values():
            _sync_prompt_env(agent, env)
        s = env.get("storage")
        print(f"\n--- Year {year} --- storage={s if s is None else round(s, 3)} maf")

    def on_post_step(agent, result):
        appr = getattr(result, "approved_skill", None)
        skill_name = appr.skill_name if appr else "?"
        status = appr.approval_status if appr else getattr(result, "outcome", "N/A")
        retries = getattr(result, "retry_count", 0)
        params = getattr(appr, "parameters", {}) if appr else {}
        setpoints = " ".join(f"{k}={v}" for k, v in params.items()) or "(none)"
        mark = f" [governance re-prompted {retries}x]" if retries else ""
        print(f"  {agent.name}: {skill_name} ({status}){mark} | {setpoints}")

    def on_post_step_end(year, all_agents):
        return None

    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_coupling(bundle.contract, bundle, domain="reservoir_control_multidim")
        .with_governance("strict", str(CONFIG / "multidim_agent_types.yaml"))
        .with_skill_registry(str(CONFIG / "multidim_skill_registry.yaml"))
        .with_memory_engine(WindowMemoryEngine(window_size=3))
        .with_lifecycle_hooks(
            pre_year=on_pre_year,
            post_step=on_post_step,
            post_step_end=on_post_step_end,
        )
        .with_exact_output(args.output)
        # workers=1 is a HARD requirement (INVARIANTS.md AR-3): hooks mutate the
        # shared env dict for prompt/governance visibility.
        .with_workers(1)
        .with_seed(args.seed)
    ).build()
    return runner, bundle


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reservoir multi-dimensional control experiment")
    ap.add_argument("--model", default="mock", help="LLM model or 'mock'")
    ap.add_argument("--thinking-mode", choices=["auto", "disabled", "enabled"],
                    default=None, help="Ollama thinking policy (default: framework setting)")
    ap.add_argument("--years", type=int, default=4)
    ap.add_argument("--output", default=str(HERE / "results_multidim"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    if args.thinking_mode is not None:
        from broker.utils.llm_utils import LLM_CONFIG
        LLM_CONFIG.thinking_mode = args.thinking_mode

    runner, _bundle = _build_runner(args)
    if args.model.lower().startswith("mock"):
        _install_scripted_mock(runner)

    print(
        "Reservoir multi-dimensional control run | "
        f"model={args.model} years={args.years}"
    )
    print("=" * 72)
    runner.run()
    print(f"\nDone. Audit + traces under: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
