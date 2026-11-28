"""Reservoir continuous-control factories for the broker.run entry point.

DECISION TIMING (hindcast-then-set): each year the runner first advances the
solver 12 monthly sub-steps under the LAST committed release target, THEN the
operator decides. The decision therefore governs the COMING year, so the
dead-pool projection feeds on (a) storage at the end of the year just run and
(b) the NEXT year's inflow forecast — `inflow_forecast_for_year(year + 1)`
(review C1: feeding the just-consumed year's inflow as the "forecast" made
the wall fire for the wrong physical reason).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from broker.utils.retry_prompt import PLAIN_RETRY_HEADER
from broker.agents import AgentConfig, BaseAgent
from broker.agents.base import Skill
from broker.coupling import (
    CouplingContract,
    FeasibilityBound,
    Relation,
    VarSpec,
    resolve_coupling_enabled,
)
from broker.domains.registry import DomainPackRegistry
from broker.run import Coupled, RunContext
from broker.utils.llm_utils import LLMStats

from .ops_modules import (
    ReservoirOpsBundle,
    ToyLinearEvapReservoir,
    ToyMassBalanceReservoir,
)

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "reservoir_agent_types.yaml"
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

# Keep the static prompt menu in lockstep with parsing.skill_map in the YAML.
_OPTION_LABELS = {
    "set_release": (
        "set_release — set the coming year's monthly release target as a "
        "fraction of demand (provide magnitude from 0 to 1, e.g. 0.6)"
    ),
    "maintain_release": "maintain_release — keep the previously committed release target",
}
OPTIONS_TEXT = "\n".join(
    f"{i}. {label}" for i, label in enumerate(_OPTION_LABELS.values(), 1)
)


def decision_payload(decision: str, **fields: Any):
    payload = dict(fields)
    payload["decision"] = decision
    payload.setdefault("reasoning", f"scripted mock chose {decision}")
    return (
        f"<<<DECISION_START>>>\n{json.dumps(payload)}\n<<<DECISION_END>>>",
        LLMStats(),
    )


def scripted_operator(prompt: str):
    # 0.5 clears the year-3 wall (passing threshold about 0.536 — see the
    # ops_modules docstring arithmetic); review C2: 0.6 also projected below
    # dead pool, so the retry never resolved and the insurer-pattern
    # narrative (wall -> retry -> APPROVED) was broken.
    magnitude = 0.5 if prompt.startswith(PLAIN_RETRY_HEADER) else 1.0
    return decision_payload(
        "set_release",
        magnitude=magnitude,
        reasoning=f"scripted reservoir release at {magnitude} of demand",
    )


def sync_prompt_env(agent: BaseAgent, env: Dict[str, Any]) -> None:
    for key in PROMPT_ENV_KEYS:
        if key in env:
            agent.dynamic_state[key] = env[key]
    agent.dynamic_state["options_text"] = OPTIONS_TEXT


def make_operator() -> BaseAgent:
    cfg = AgentConfig(
        name="OPERATOR",
        agent_type="operator",
        state_params=[],
        objectives=[],
        constraints=[],
        skills=[
            Skill("set_release", "Set monthly release as a fraction of demand", None, "none"),
            Skill("maintain_release", "Maintain previous release", None, "none"),
        ],
    )
    agent = BaseAgent(cfg)
    # The broker numbers these labels using the same order as the live skill map.
    agent.custom_attributes["option_text_overrides"] = _OPTION_LABELS.copy()
    return agent


def build_contract() -> CouplingContract:
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
            # Published so the water balance below can be checked: this
            # month's inflow and the evaporation actually removed.
            VarSpec(
                "inflow",
                float,
                "maf",
                lo=0.0,
                cadence="per_solver_step",
                observation_reduce="sum",
                consumer_of_record=False,
            ),
            VarSpec(
                "evaporation",
                float,
                "maf",
                lo=0.0,
                cadence="per_solver_step",
                observation_reduce="sum",
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
        # The toy solver's own water balance, checked every month on the raw
        # sub-step values (maf; release_actual is maf per month = maf per step).
        relations=(
            Relation(
                name="storage_balance",
                residual=(
                    "storage - (prev_storage + inflow - release_actual"
                    " - evaporation - spill)"
                ),
                tolerance=1e-9,
            ),
        ),
        # The dead-pool limit, judged before a release is approved on the toy
        # model's own what-if run: the coming year's 12 months with the forecast
        # the operator saw. storage_unclamped is the storage before the clamp
        # to [0, capacity], so a request that would empty the reservoir cannot
        # hide behind the clamped value. The id stays dead_pool_violation: the
        # scripted mock retries at 0.5 when the prompt carries it. The bound
        # judges every skill: maintain_release keeps the last release target
        # running all year, so it can empty the reservoir too.
        feasibility=(
            FeasibilityBound(
                name="dead_pool_violation",
                must_hold=f"storage_unclamped >= {ToyMassBalanceReservoir.DEAD_POOL}",
            ),
        ),
    )


def make_solver(model: str):
    if "linear" in model.lower():
        return ToyLinearEvapReservoir()
    return ToyMassBalanceReservoir()


def build_world(ctx: RunContext) -> Coupled:
    pack = DomainPackRegistry.get("reservoir_control")
    enabled, source = resolve_coupling_enabled(ctx.raw, pack)
    if not enabled:
        raise SystemExit("reservoir_control requires global_config.coupling.enable: true")
    print(f"[coupling] enable=True (source={source}); adapter injected by the builder")

    contract = build_contract()
    bundle = ReservoirOpsBundle(contract=contract, solver=make_solver(ctx.model))
    return Coupled(contract, bundle, domain="reservoir_control")


def build_agents(ctx: RunContext) -> dict[str, BaseAgent]:
    return {"OPERATOR": make_operator()}


def build_hooks(ctx: RunContext):
    solver = ctx.world.solver
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
            # The old hub-less builder did not retrieve generic decision lines
            # and this prompt uses only the reservoir's observed outcomes.
            agent.memory_config = {**agent.memory_config, "runner_decision_line": False}
            sync_prompt_env(agent, env)
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

    def after_run(output_dir):
        print(f"\nDone. Audit + traces under: {output_dir}")
        summary = summarize_block_and_repair(output_dir)
        print("\nBlock and repair in this run:" if summary else "\nNo decision was blocked in this run.")
        for line in summary:
            print(line)

    return {
        "pre_year": on_pre_year,
        "post_step": on_post_step,
        "post_step_end": on_post_step_end,
        "after_run": after_run,
    }


def operator_mock(ctx: RunContext):
    return {"operator": scripted_operator}


def summarize_block_and_repair(output_dir) -> list:
    """Plain-text summary of each blocked-then-repaired decision in a finished run.

    Reads the operator's audit trace (one record per agent and year). A record
    with ``retry_count > 0`` is a decision the dead-pool rule blocked and the
    operator then repaired; its ``validation_issues`` hold the block reason and
    ``execution_result`` holds the change that was applied to the toy reservoir.
    """
    trace = Path(output_dir) / "raw" / "operator_traces.jsonl"
    if not trace.is_file():
        return [f"(no trace file at {trace}, so no block/repair summary)"]
    records = {}
    for line in trace.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if "step_id" in rec:
            records[rec["step_id"]] = rec
    lines = []
    for step_id in sorted(records):
        rec = records[step_id]
        if not rec.get("retry_count"):
            continue
        reasons = [
            err
            for issue in rec.get("validation_issues") or []
            for err in issue.get("errors", [])
        ]
        year = rec["year"]
        env = rec.get("environment_context") or {}
        # A retried decision can end without a parsable proposal (skill_proposal
        # null) or without an approved skill, e.g. when a live model's retries
        # end in unparsable output; describe that instead of failing here.
        proposal = rec.get("skill_proposal") or {}
        repaired = (proposal.get("reasoning") or {}).get("magnitude")
        approved = rec.get("approved_skill") or {}
        change = (rec.get("execution_result") or {}).get("action_context") or {}
        new_target = ((change.get("world_delta") or {}).get("world_changes") or {}).get("release_target")
        retries = int(rec["retry_count"])
        blocked = "attempt 1 " if retries == 1 else f"attempts 1-{retries}"
        lines.append(f"Year {year}, agent {rec['agent_id']}:")
        lines.append(f"  {blocked} BLOCKED: " + (" ".join(reasons) or "validation failed"))
        if proposal and approved:
            outcome = f"{approved.get('skill_name')} at {repaired} of demand"
        else:
            outcome = "no parsable proposal after the retries; see the trace for the fallback"
        lines.append(f"  attempt {retries + 1}  {approved.get('status', 'NO DECISION')}: {outcome}")
        if new_target is not None and env.get("release_actual") is not None:
            lines.append(
                f"  executed   toy reservoir release target: {env['release_actual']:.3f} -> "
                f"{new_target:.3f} maf/month"
            )
        after_env = (records.get(step_id + 1) or {}).get("environment_context") or {}
        if None not in (after_env.get("storage"), env.get("storage"), env.get("dead_pool")):
            lines.append(
                f"  effect     storage {env['storage']:.3f} maf at year {year}, "
                f"{after_env['storage']:.3f} maf at year {year + 1} "
                f"(dead pool {env['dead_pool']:.3f} maf)"
            )
    return lines
