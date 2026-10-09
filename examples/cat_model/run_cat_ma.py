"""Runnable multi-agent catastrophe-model coupling experiment.

Four policyholders, one insurer, and one government share a single claims
pool. Claims enter a period queue when filed; the pool mutates exactly once at
period-end settlement, where ``PortfolioLedger.settle()`` provides the audited
full/pro-rata resolution.

TIMING DELTA vs FLOODABM (deliberate — do not "fix" back): FLOODABM files and
pays each claim instantly within the same annual tick
(``main.py:run_finance_for_year``); WAGF defers ALL payouts to period-end
settlement so the shared pool mutates once, order-independently, with the
contention rule audited (E4). The deferral IS the multi-agent contribution —
instant per-claim payment would reintroduce the joint-overdraw race this
example exists to demonstrate the answer to.

Usage:
  python examples/cat_model/run_cat_ma.py --model mock --years 2
  python examples/cat_model/run_cat_ma.py --model llama3.1:8b --years 2
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

import examples.cat_model.ma_validators  # noqa: E402,F401
from examples.cat_model.coupling_modules import PortfolioLedger  # noqa: E402
from examples.cat_model.ma_modules import MaCatBundle, MaFootprintSource  # noqa: E402

from broker.agents import AgentConfig, BaseAgent  # noqa: E402
from broker.agents.base import Skill  # noqa: E402
from broker.components.memory.engine import WindowMemoryEngine  # noqa: E402
from broker.coupling import CouplingContract, VarSpec, resolve_coupling_enabled  # noqa: E402
from broker.core.experiment import ExperimentBuilder  # noqa: E402
from broker.domains.registry import DomainPackRegistry  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config"
POLICYHOLDER_IDS = ("PH1", "PH2", "PH3", "PH4")
PROMPT_ENV_KEYS = (
    "current_year",
    "flood_depth_ft",
    "total_ground_up_loss",
    "n_agents_with_loss",
    "pool_budget_remaining",
    "gov_budget_remaining",
    "last_settlement_rule",
    "last_payout_ratio",
    "total_claims_owed",
    "n_claims",
    "settlement_disposition",
)


def _parse_mapping(raw: str, default: Dict[str, float]) -> Dict[str, float]:
    if not raw:
        return dict(default)
    out: Dict[str, float] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            key, value = item.split(":", 1)
            out[key.strip()] = float(value)
        except ValueError:
            raise SystemExit(
                f"Malformed mapping entry {item!r} (expected KEY:NUMBER, "
                f"e.g. PH1:250000). Full argument: {raw!r}"
            )
    return out


# NOTE: the two prompt-scraping helpers below are MOCK-PATH ONLY and
# intentionally fragile (they re-parse the rendered prompt so the scripted
# mock reacts to exactly what a real LLM would see). Never reuse for the
# governed path.
def _money_from_prompt(prompt: str, label: str, default: float = 0.0) -> float:
    match = re.search(rf"{re.escape(label)}:\s*\$?([0-9.,-]+)", prompt)
    if not match:
        return default
    return float(match.group(1).replace(",", ""))


def _number_from_prompt(prompt: str, label: str, default: float = 0.0) -> float:
    match = re.search(rf"{re.escape(label)}:\s*([0-9.,-]+)", prompt)
    if not match:
        return default
    return float(match.group(1).replace(",", ""))


def _decision_payload(decision: str, **fields):
    payload = dict(fields)
    payload["decision"] = decision
    payload.setdefault("reasoning", f"scripted mock chose {decision}")
    return f"<<<DECISION_START>>>\n{json.dumps(payload)}\n<<<DECISION_END>>>", LLMStats()


def _policyholder_mock(prompt: str):
    owed = _money_from_prompt(prompt, "Your covered amount before pool settlement")
    in_force = "Policy status: in_force" in prompt
    decision = "file_claim" if in_force and owed > 0.0 else "absorb_loss"
    label = "H" if decision == "file_claim" else "L"
    return _decision_payload(
        decision,
        primary_assessment={
            "label": label,
            "reason": "covered in-force loss" if decision == "file_claim" else "no covered claim",
        },
        reasoning=f"{decision}: in_force={in_force}, owed={owed:.2f}",
    )


def _insurer_mock(prompt: str):
    total_owed = _money_from_prompt(prompt, "Queued legitimate claims owed")
    pool = _money_from_prompt(prompt, "Pool budget remaining before settlement")
    decision = "settle_full" if total_owed <= pool else "settle_prorata"
    return _decision_payload(
        decision,
        RISK_APPETITE="M" if decision == "settle_full" else "C",
        reasoning=f"{decision}: total_owed={total_owed:.2f}, pool={pool:.2f}",
    )


def _government_mock(prompt: str):
    year = int(_number_from_prompt(prompt, "Year", 1))
    n_claims = int(_number_from_prompt(prompt, "Number of queued claims", 0))
    budget = _money_from_prompt(prompt, "Government relief budget remaining")
    decision = "fund_shortfall_relief" if year >= 2 and n_claims > 0 and budget > 0.0 else "no_action"
    return _decision_payload(
        decision,
        BUDGET_UTIL="H" if decision == "fund_shortfall_relief" else "M",
        reasoning=f"{decision}: year={year}, n_claims={n_claims}, budget={budget:.2f}",
    )


def _install_scripted_mock(runner) -> None:
    runner._llm_cache["policyholder"] = _policyholder_mock
    runner._llm_cache["insurer_ma"] = _insurer_mock
    runner._llm_cache["government_ma"] = _government_mock


# {options_text} menus per agent type, injected via dynamic_state (real-LLM
# e4b finding 2026-06-10, shared with examples/reservoir_control): the
# hub-less BaseAgentContextBuilder path does not populate options_text, so
# the placeholder rendered "[N/A]" and the format example's hardcoded
# default claimed "choose ONE from: 1, 2, or 3" regardless of the actual
# menu size (this run survived because the static parsing.skill_map still
# resolved the numbers). Numbering MUST stay in lockstep with
# parsing.skill_map in ma_cat_agent_types.yaml.
OPTIONS_TEXT_BY_TYPE = {
    "policyholder": (
        "1. file_claim — file a legitimate covered claim into the settlement queue\n"
        "2. absorb_loss — do not file; absorb this period's loss\n"
        "3. lapse_policy — let the policy lapse for future periods"
    ),
    "insurer_ma": (
        "1. settle_prorata — use the audited pro-rata settlement rule if the pool is short\n"
        "2. settle_full — pay all queued legitimate claims in full"
    ),
    "government_ma": (
        "1. no_action — do not fund relief this period\n"
        "2. fund_shortfall_relief — use available public budget to reduce settlement shortfalls"
    ),
}


def _sync_prompt_env(agent: BaseAgent, env: Dict) -> None:
    for key in PROMPT_ENV_KEYS:
        if key in env:
            agent.dynamic_state[key] = env[key]
    menu = OPTIONS_TEXT_BY_TYPE.get(getattr(agent, "agent_type", ""))
    if menu:
        agent.dynamic_state["options_text"] = menu


def _build_contract() -> CouplingContract:
    return CouplingContract(
        observations=(
            VarSpec(
                "total_ground_up_loss",
                float,
                "USD_2020",
                lo=0.0,
                consumer_of_record=False,
            ),
            VarSpec("pool_budget_remaining", float, "USD_2020", lo=0.0),
            VarSpec("gov_budget_remaining", float, "USD_2020", lo=0.0),
            VarSpec(
                "total_claims_owed",
                float,
                "USD_2020",
                lo=0.0,
                consumer_of_record=False,
            ),
        ),
        inputs=(),
        decision_cadence="annual",
        solver_cadence="event_set",
        operation_order=("hazard", "exposure", "vulnerability", "financial"),
    )


def _make_policyholder(aid: str, terms: Dict[str, float]) -> BaseAgent:
    cfg = AgentConfig(
        name=aid,
        agent_type="policyholder",
        state_params=[],
        objectives=[],
        constraints=[],
        skills=[
            Skill("file_claim", "File a covered claim", None, "none"),
            Skill("absorb_loss", "Absorb loss without filing", None, "none"),
            Skill("lapse_policy", "Lapse the policy for future periods", None, "none"),
        ],
    )
    agent = BaseAgent(cfg)
    agent.dynamic_state.update(
        {
            "exposure": float(terms["exposure"]),
            "deductible": float(terms["deductible"]),
            "limit": float(terms["limit"]),
            "zone_multiplier": float(terms["zone_multiplier"]),
            "policy_in_force_self": bool(terms["in_force"]),
            "your_policy_status": "in_force" if terms["in_force"] else "not_in_force",
            "own_ground_up_loss": 0.0,
            "your_loss": 0.0,
            "your_owed": 0.0,
            "your_last_payout": 0.0,
            "your_last_payout_ratio": 1.0,
        }
    )
    return agent


def _make_institutional_agent(aid: str, agent_type: str, skills: list[Skill]) -> BaseAgent:
    return BaseAgent(
        AgentConfig(
            name=aid,
            agent_type=agent_type,
            state_params=[],
            objectives=[],
            constraints=[],
            skills=skills,
        )
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Multi-agent catastrophe-model coupling experiment")
    ap.add_argument("--model", default="mock", help="LLM model or 'mock'")
    ap.add_argument("--thinking-mode", choices=["auto", "disabled", "enabled"],
                    default=None, help="Ollama thinking policy (default: framework setting)")
    ap.add_argument("--years", type=int, default=2)
    ap.add_argument("--pool", type=float, default=60_000.0)
    ap.add_argument("--gov-budget", type=float, default=30_000.0)
    ap.add_argument("--deductible", type=float, default=5_000.0)
    ap.add_argument("--limit", type=float, default=200_000.0)
    ap.add_argument("--exposures", default="PH1:250000,PH2:180000,PH3:320000,PH4:200000")
    ap.add_argument("--depths", default="1:2.0,2:8.0")
    ap.add_argument("--output", default=str(HERE / "results_ma"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    if args.thinking_mode is not None:
        from broker.utils.llm_utils import LLM_CONFIG
        LLM_CONFIG.thinking_mode = args.thinking_mode

    exposures = _parse_mapping(args.exposures, {})
    depths = _parse_mapping(args.depths, {})
    zone_multipliers = {"PH1": 1.0, "PH2": 0.6, "PH3": 1.4, "PH4": 1.0}
    households = {
        aid: {
            "exposure": exposures[aid],
            "deductible": args.deductible,
            "limit": args.limit,
            "in_force": aid != "PH4",
            "zone_multiplier": zone_multipliers[aid],
        }
        for aid in POLICYHOLDER_IDS
    }

    agents = {
        aid: _make_policyholder(aid, terms)
        for aid, terms in households.items()
    }
    agents["INSURER"] = _make_institutional_agent(
        "INSURER",
        "insurer_ma",
        [
            Skill("settle_prorata", "Settle claims pro-rata if needed", None, "none"),
            Skill("settle_full", "Settle all claims in full", None, "none"),
        ],
    )
    agents["GOV"] = _make_institutional_agent(
        "GOV",
        "government_ma",
        [
            Skill("no_action", "Reserve public relief budget", None, "none"),
            Skill("fund_shortfall_relief", "Fund shortfall relief", None, "none"),
        ],
    )

    footprint = MaFootprintSource(depths, zone_multipliers)
    ledger = PortfolioLedger(pool_budget=args.pool)
    bundle = MaCatBundle(footprint, ledger, households=households, gov_budget=args.gov_budget)

    with open(CONFIG / "ma_cat_agent_types.yaml", encoding="utf-8") as fh:
        yaml_cfg = yaml.safe_load(fh)
    pack = DomainPackRegistry.get("cat_model_ma")
    enabled, source = resolve_coupling_enabled(yaml_cfg, pack)
    if not enabled:
        raise SystemExit("cat_model_ma requires global_config.coupling.enable: true")
    print(f"[coupling] enable=True (source={source}); adapter injected by the builder")

    env_holder: Dict[str, Dict] = {}

    def on_pre_year(year, env, all_agents):
        env_holder["env"] = env
        for agent in all_agents.values():
            _sync_prompt_env(agent, env)
        last = bundle.last_settlement or {}
        paid = last.get("per_agent_paid", {}) or {}
        relief = last.get("per_agent_relief", {}) or {}
        for aid in POLICYHOLDER_IDS:
            agent = all_agents[aid]
            ground, owed = bundle.period_losses.get(aid, (0.0, 0.0))
            terms = bundle.households[aid]
            last_paid = float(paid.get(aid, 0.0) or 0.0)
            last_relief = float(relief.get(aid, 0.0) or 0.0)
            if year == 1:
                agent_ratio = 1.0
            else:
                prior_claim = float((last.get("claims", {}) or {}).get(aid, 0.0) or 0.0)
                agent_ratio = last_paid / prior_claim if prior_claim > 0.0 else 1.0
            agent.dynamic_state.update(
                {
                    "own_ground_up_loss": ground,
                    "your_loss": ground,
                    "your_owed": owed,
                    "policy_in_force_self": bool(terms["in_force"]),
                    "your_policy_status": "in_force" if terms["in_force"] else "not_in_force",
                    # FLOODABM amendment 2: what staying insured costs this
                    # period — the economic stake behind lapse_policy.
                    "your_premium": round(
                        bundle.premium_per_period if terms["in_force"] else 0.0, 2),
                    "your_last_payout": round(last_paid + last_relief, 2),
                    "your_last_payout_ratio": round(agent_ratio if agent_ratio is not None else 1.0, 6),
                }
            )
        print(
            f"\n--- Year {year} --- depth={env.get('flood_depth_ft')}ft "
            f"ground_up=${env.get('total_ground_up_loss')} "
            f"pool=${env.get('pool_budget_remaining')} gov=${env.get('gov_budget_remaining')}"
        )

    def on_post_step(agent, result):
        env = env_holder.get("env")
        appr = getattr(result, "approved_skill", None)
        skill_name = appr.skill_name if appr else "?"
        status = appr.approval_status if appr else getattr(result, "outcome", "N/A")
        retries = getattr(result, "retry_count", 0)
        mark = f" [governance re-prompted {retries}x]" if retries else ""
        print(f"  {agent.name}: {skill_name} ({status}){mark}")
        if env is None:
            return
        if getattr(agent, "agent_type", "") == "policyholder":
            env["total_claims_owed"] = round(sum(bundle.pending_claims.values()), 2)
            env["n_claims"] = len(bundle.pending_claims)
            _sync_prompt_env(agents["INSURER"], env)
            _sync_prompt_env(agents["GOV"], env)
        elif getattr(agent, "agent_type", "") == "insurer_ma":
            env["settlement_disposition"] = bundle.disposition or "undecided"
            _sync_prompt_env(agents["GOV"], env)

    def on_post_step_end(year, all_agents):
        settlement = bundle.settle_period()
        print(
            f"  settlement: rule={settlement['rule']} "
            f"owed=${settlement['total_owed']} paid=${settlement['total_paid']} "
            f"relief=${settlement['total_relief']} "
            f"pool=${settlement['pool_remaining']} gov=${settlement['gov_budget_remaining']}"
        )
        claims = settlement.get("claims", {}) or {}
        for aid in POLICYHOLDER_IDS:
            owed = float(claims.get(aid, 0.0) or 0.0)
            paid = float((settlement.get("per_agent_paid", {}) or {}).get(aid, 0.0) or 0.0)
            relief = float((settlement.get("per_agent_relief", {}) or {}).get(aid, 0.0) or 0.0)
            if owed <= 0.0 and paid <= 0.0 and relief <= 0.0:
                continue
            text = (
                f"Insurance settlement: received ${paid:.2f} of ${owed:.2f} "
                f"owed (rule: {settlement['rule']}); government relief ${relief:.2f}"
            )
            metadata = {
                "emotion": "major",
                "importance": 0.8,
                "significance": 0.8,
                "source": "settlement",
            }
            runner.memory_engine.add_memory(aid, text, metadata)

    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_coupling(_build_contract(), bundle, domain="cat_model_ma")
        .with_governance("strict", str(CONFIG / "ma_cat_agent_types.yaml"))
        .with_skill_registry(str(CONFIG / "ma_cat_skill_registry.yaml"))
        .with_phase_order([["policyholder"], ["insurer_ma"], ["government_ma"]])
        .with_memory_engine(WindowMemoryEngine(window_size=3))
        .with_lifecycle_hooks(
            pre_year=on_pre_year,
            post_step=on_post_step,
            post_step_end=on_post_step_end,
        )
        .with_exact_output(args.output)
        # workers=1 is a HARD requirement here (review W1 / INVARIANTS.md
        # AR-3): on_post_step mutates the shared env dict (claim aggregates),
        # so parallel same-phase steps would race. There is deliberately no
        # --workers CLI flag for this example.
        .with_workers(1)
        .with_seed(args.seed)
    ).build()

    if args.model.lower().startswith("mock"):
        _install_scripted_mock(runner)

    print(
        "Multi-agent catastrophe-model run | "
        f"model={args.model} years={args.years} pool=${args.pool} gov=${args.gov_budget}"
    )
    print("=" * 72)
    runner.run()
    print(f"\nDone. Audit + traces under: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
