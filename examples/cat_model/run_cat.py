"""Runnable catastrophe-model coupling experiment (Phase 6V increment 1b).

A governed LLM insurer decides whether to pay flood claims from a SHARED pool.
The world-mutating payout is coupled to a hazard->exposure->vulnerability->
financial chain through the generic ``broker.coupling`` adapter, and governed by
``insurer_payout_solvency_check`` (a physical builtin check) INSIDE the
governance retry loop: an over-pool / lapsed-policy ``approve_payout`` is BLOCKED
and the insurer is re-prompted.

The coupling layer is injected via the two-layer flag
(``global_config.coupling.enable``). With the flag OFF the raw engine is used and
nothing in ``broker.coupling`` is touched (paper-3 isolation).

Usage:
  python examples/cat_model/run_cat.py --model llama3.1:8b --years 3 --pool 50000
  python examples/cat_model/run_cat.py --model mock --years 3      # no GPU, wiring smoke
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

# Importing the package registers the cat_model validators + DomainPack.
import examples.cat_model  # noqa: E402,F401
from examples.cat_model.coupling_modules import (  # noqa: E402
    CatBundle,
    FloodFootprintSource,
    PortfolioLedger,
)

from broker.agents import AgentConfig, BaseAgent  # noqa: E402
from broker.agents.base import Skill  # noqa: E402
from broker.components.context.builder import TieredContextBuilder  # noqa: E402
from broker.components.memory.engine import WindowMemoryEngine  # noqa: E402
from broker.coupling import (  # noqa: E402
    CouplingContract,
    VarSpec,
    resolve_coupling_enabled,
)
from broker.core.experiment import ExperimentBuilder  # noqa: E402
from broker.domains.registry import DomainPackRegistry  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config"


def _build_contract() -> CouplingContract:
    """The cat-model contract: world->agent observations + the agent->world input.
    owed_payout is diagnostic-only (consumer_of_record=False) so it can be both
    surfaced and acted on without tripping the double-count guard."""
    return CouplingContract(
        observations=(
            VarSpec("flood_depth_ft", float, "ft", lo=0.0, hi=100.0),
            VarSpec("agent_ground_up_loss", float, "USD_2020", lo=0.0),
            VarSpec("policy_deductible", float, "USD_2020", lo=0.0),
            VarSpec("policy_limit", float, "USD_2020", lo=0.0),
            VarSpec("pool_budget_remaining", float, "USD_2020", lo=0.0),
            VarSpec("policy_in_force_before_event", bool, "", consumer_of_record=False),
            VarSpec("owed_payout", float, "USD_2020", lo=0.0, consumer_of_record=False),
        ),
        inputs=(
            VarSpec("payout", float, "USD_2020", direction="agent_to_world", consumer_of_record=False),
        ),
        decision_cadence="annual",
        solver_cadence="event_set",
        operation_order=("hazard", "exposure", "vulnerability", "financial"),
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Catastrophe-model coupling experiment")
    ap.add_argument("--model", default="llama3.1:8b", help="LLM (ollama) or 'mock'")
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--pool", type=float, default=50_000.0, help="shared pool budget")
    ap.add_argument("--lapsed-policy", action="store_true",
                    help="policy NOT in force before the event — approve is then "
                         "invalid (forces a governance lapse-block + re-prompt)")
    ap.add_argument("--output", default=str(HERE / "results"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    # --- agent: a single insurer ---
    insurer_cfg = AgentConfig(
        name="INSURER",
        agent_type="insurer",
        state_params=[],
        objectives=[],
        constraints=[],
        skills=[
            Skill("approve_payout", "Pay the flood claim from the shared pool", None, "none"),
            Skill("deny_payout", "Deny the claim (pay nothing)", None, "none"),
        ],
    )
    agents = {"INSURER": BaseAgent(insurer_cfg)}

    # --- world: hazard -> exposure -> vulnerability -> financial, behind the bundle ---
    # Depths chosen so year 1 is solvent (approve OK) but later floods exceed the
    # remaining pool (approve -> governance block -> re-prompt).
    footprint = FloodFootprintSource({1: 2.0, 2: 8.0, 3: 3.0})
    ledger = PortfolioLedger(pool_budget=args.pool)
    bundle = CatBundle(footprint, ledger, exposure_value=250_000.0,
                       deductible=5_000.0, limit=200_000.0,
                       policy_in_force=not args.lapsed_policy)

    # --- two-layer coupling flag (gating contract: cat REQUIRES coupling) ---
    # The adapter wrap itself moved into the builder (.with_coupling below,
    # Wave 3 item 3-1) — this pre-check only keeps run_cat's loud-failure
    # contract when someone turns the flag off.
    with open(CONFIG / "agent_types.yaml", encoding="utf-8") as fh:
        yaml_cfg = yaml.safe_load(fh)
    pack = DomainPackRegistry.get("cat_model")
    enabled, source = resolve_coupling_enabled(yaml_cfg, pack)
    if not enabled:  # pragma: no cover - cat config always enables
        raise SystemExit("cat_model requires global_config.coupling.enable: true")
    print(f"[coupling] enable=True (source={source}); adapter injected by the builder")

    # Explicit TieredContextBuilder (hub=None), matching
    # examples/vaccination_demo / examples/irrigation_abm's L3-1B fix
    # (2026-05-23) and broker/tools/scaffold_domain.py's generated runner
    # (2026-09 round 3): ExperimentBuilder.build()'s DEFAULT context
    # builder (create_context_builder() with no hub -> plain
    # BaseAgentContextBuilder) never reads context["personal"] at all, so
    # {options_text} (written there by _inject_options_text) rendered
    # "[N/A]" — a 2026-09 options-text-parity POST-RENDER check caught
    # this as a real, pre-existing gap. examples/cat_model/run_cat_ma.py
    # and examples/reservoir_control/run_reservoir_ops.py already work
    # around the same gap with a STATIC agent.dynamic_state["options_text"]
    # override (safe there because those menus never get RAG-reranked);
    # run_cat.py had neither that workaround nor this one. Pinning
    # TieredContextBuilder is the more robust fix: it renders the LIVE
    # {options_text} correctly on every call, RAG re-rank or not, rather
    # than adding a third copy of a static string that could drift.
    mem_engine = WindowMemoryEngine(window_size=3)
    insurer_prompt_template = yaml_cfg["insurer"]["prompt_template"]
    ctx_builder = TieredContextBuilder(
        agents=agents,
        hub=None,
        prompt_templates={"insurer": insurer_prompt_template},
        yaml_path=str(CONFIG / "agent_types.yaml"),
        memory_engine=mem_engine,
    )

    # --- diagnostic hooks (wired via the builder so __init__ validates signatures) ---
    def on_pre_year(year, env, _agents):
        print(f"\n--- Year {year} --- depth={env.get('flood_depth_ft')}ft "
              f"owed=${env.get('owed_payout')} pool=${env.get('pool_budget_remaining')}")

    def on_post_step(agent, result):
        appr = getattr(result, "approved_skill", None)
        name = appr.skill_name if appr else "?"
        status = appr.approval_status if appr else "N/A"
        retries = getattr(result, "retry_count", 0)
        mark = f"  [governance re-prompted {retries}x]" if retries > 0 else ""
        print(f"  {agent.name}: {name} ({status}){mark}")

    # --- build + run ---
    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        # Builder-level coupling (Wave 3): resolves the two-layer flag at
        # build() and wraps the (absent -> None) sim engine in the adapter.
        .with_coupling(_build_contract(), bundle, domain="cat_model")
        .with_skill_registry(str(CONFIG / "skill_registry.yaml"))
        .with_memory_engine(mem_engine)
        .with_context_builder(ctx_builder)
        .with_governance("strict", str(CONFIG / "agent_types.yaml"))
        # No custom_validators bridge needed: cat_model's registry PHYSICAL check
        # (insurer_payout_solvency_check) is dispatched by the engine because the
        # config sets global_config.governance.dispatch_domain_physical: true.
        .with_lifecycle_hooks(pre_year=on_pre_year, post_step=on_post_step)
        .with_exact_output(args.output)
        .with_workers(1)
        .with_seed(args.seed)
    ).build()

    print(f"Catastrophe-model coupling run | model={args.model} years={args.years} pool=${args.pool}")
    print("=" * 64)
    runner.run()
    print(f"\nDone. Audit + traces under: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
