"""Regression tests for the multi-agent catastrophe settlement example."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

import examples.cat_model  # noqa: F401 - registers cat_model and cat_model_ma
from broker.components.governance.registry import SkillRegistry
from broker.components.governance.validator_registry import ValidatorRegistry
from broker.components.memory.engine import WindowMemoryEngine
from broker.core.experiment import ExperimentBuilder
from broker.core.skill_broker_engine import SkillBrokerEngine
from broker.domains.registry import DomainPackRegistry
from broker.interfaces.skill_types import SkillProposal
from broker.utils.llm_utils import LLMStats
from examples.cat_model import run_cat_ma
from examples.cat_model.coupling_modules import PortfolioLedger, depth_damage_ratio
from examples.cat_model.ma_modules import MaCatBundle, MaFootprintSource
from examples.cat_model.ma_validators import (
    insurer_settlement_check,
    policyholder_claim_check,
)


REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "examples" / "cat_model" / "config"
POLICYHOLDER_IDS = ("PH1", "PH2", "PH3", "PH4")
ZONE_MULTIPLIERS = {"PH1": 1.0, "PH2": 0.6, "PH3": 1.4, "PH4": 1.0}
DEFAULT_EXPOSURES = {
    "PH1": 250_000.0,
    "PH2": 180_000.0,
    "PH3": 320_000.0,
    "PH4": 200_000.0,
}


@dataclass
class ScriptedRun:
    runner: Any
    bundle: MaCatBundle
    agents: dict[str, Any]
    output_dir: Path
    settlements: list[dict[str, Any]]
    env_snapshots: list[dict[str, Any]]
    premium_snapshots: list[dict[str, float]]


def _households(
    *,
    exposures: dict[str, float] | None = None,
    deductible: float = 5_000.0,
    limit: float = 200_000.0,
) -> dict[str, dict[str, Any]]:
    exposures = exposures or DEFAULT_EXPOSURES
    return {
        aid: {
            "exposure": exposures[aid],
            "deductible": deductible,
            "limit": limit,
            "in_force": aid != "PH4",
            "zone_multiplier": ZONE_MULTIPLIERS[aid],
        }
        for aid in POLICYHOLDER_IDS
    }


def _bundle(
    *,
    pool: float = 60_000.0,
    gov_budget: float = 30_000.0,
    depths: dict[int, float] | None = None,
    households: dict[str, dict[str, Any]] | None = None,
    premium_per_period: float = 1_200.0,
) -> MaCatBundle:
    return MaCatBundle(
        MaFootprintSource(depths or {1: 2.0, 2: 8.0}, ZONE_MULTIPLIERS),
        PortfolioLedger(pool_budget=pool),
        households=households or _households(),
        gov_budget=gov_budget,
        premium_per_period=premium_per_period,
    )


def _decision_payload(decision: str, **fields: Any) -> tuple[str, LLMStats]:
    payload = dict(fields)
    payload["decision"] = decision
    payload.setdefault("reasoning", f"scripted test chose {decision}")
    return (
        f"<<<DECISION_START>>>\n{json.dumps(payload)}\n<<<DECISION_END>>>",
        LLMStats(),
    )


def _insurer_prorata(prompt: str) -> tuple[str, LLMStats]:
    return _decision_payload(
        "settle_prorata",
        RISK_APPETITE="C",
        reasoning="scripted pro-rata settlement",
    )


def _insurer_full_then_prorata(prompt: str) -> tuple[str, LLMStats]:
    if "BLOCKED" in prompt or "settle_full is invalid" in prompt:
        return _insurer_prorata(prompt)
    return _decision_payload(
        "settle_full",
        RISK_APPETITE="A",
        reasoning="scripted first attempt at full settlement",
    )


def _government_no_action(prompt: str) -> tuple[str, LLMStats]:
    return _decision_payload(
        "no_action",
        BUDGET_UTIL="M",
        reasoning="scripted reserve public budget",
    )


def _government_relief(prompt: str) -> tuple[str, LLMStats]:
    return _decision_payload(
        "fund_shortfall_relief",
        BUDGET_UTIL="H",
        reasoning="scripted relief funding",
    )


def _script_llm_cache(
    runner: Any,
    *,
    insurer: Callable[[str], tuple[str, LLMStats]] = _insurer_prorata,
    government: Callable[[str], tuple[str, LLMStats]] = _government_no_action,
) -> None:
    """Inject scripted per-agent-type mocks via the PRODUCTION seam.

    ``run_cat_ma._install_scripted_mock`` seeds ``runner._llm_cache`` keyed by
    agent_type; ``get_llm_invoke()`` returns cache hits without ever calling
    ``create_llm_invoke``. Using the same seam here means no frame inspection
    and no monkeypatch — immune to refactors of the llm_utils import site
    (review C1: the previous frame-sniffing approach worked only because
    ``get_llm_invoke``'s frame happens to hold an ``agent_type`` local).
    """
    runner._llm_cache.update(
        {
            "default": run_cat_ma._policyholder_mock,
            "policyholder": run_cat_ma._policyholder_mock,
            "insurer_ma": insurer,
            "government_ma": government,
        }
    )


def _run_scripted_ma(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    years: int = 1,
    pool: float = 60_000.0,
    gov_budget: float = 30_000.0,
    depths: dict[int, float] | None = None,
    insurer: Callable[[str], tuple[str, LLMStats]] = _insurer_prorata,
    government: Callable[[str], tuple[str, LLMStats]] = _government_no_action,
) -> ScriptedRun:
    households = _households()
    agents = {
        aid: run_cat_ma._make_policyholder(aid, terms)
        for aid, terms in households.items()
    }
    agents["INSURER"] = run_cat_ma._make_institutional_agent(
        "INSURER",
        "insurer_ma",
        [
            run_cat_ma.Skill(
                "settle_prorata", "Settle claims pro-rata if needed", None, "none"
            ),
            run_cat_ma.Skill("settle_full", "Settle all claims in full", None, "none"),
        ],
    )
    agents["GOV"] = run_cat_ma._make_institutional_agent(
        "GOV",
        "government_ma",
        [
            run_cat_ma.Skill("no_action", "Reserve public relief budget", None, "none"),
            run_cat_ma.Skill(
                "fund_shortfall_relief", "Fund shortfall relief", None, "none"
            ),
        ],
    )

    bundle = _bundle(
        pool=pool,
        gov_budget=gov_budget,
        depths=depths or {1: 2.0, 2: 8.0},
        households=households,
    )
    env_holder: dict[str, dict[str, Any]] = {}
    settlements: list[dict[str, Any]] = []
    env_snapshots: list[dict[str, Any]] = []
    premium_snapshots: list[dict[str, float]] = []
    runner_holder: dict[str, Any] = {}

    def on_pre_year(year, env, all_agents):
        env_holder["env"] = env
        for agent in all_agents.values():
            run_cat_ma._sync_prompt_env(agent, env)
        last = bundle.last_settlement or {}
        paid = last.get("per_agent_paid", {}) or {}
        relief = last.get("per_agent_relief", {}) or {}
        premium_snapshot: dict[str, float] = {}
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
            premium = round(bundle.premium_per_period if terms["in_force"] else 0.0, 2)
            premium_snapshot[aid] = premium
            agent.dynamic_state.update(
                {
                    "own_ground_up_loss": ground,
                    "your_loss": ground,
                    "your_owed": owed,
                    "policy_in_force_self": bool(terms["in_force"]),
                    "your_policy_status": "in_force"
                    if terms["in_force"]
                    else "not_in_force",
                    "your_premium": premium,
                    "your_last_payout": round(last_paid + last_relief, 2),
                    "your_last_payout_ratio": round(agent_ratio, 6),
                }
            )
        premium_snapshots.append(premium_snapshot)
        env_snapshots.append(dict(env))

    def on_post_step(agent, result):
        env = env_holder.get("env")
        if env is None:
            return
        if getattr(agent, "agent_type", "") == "policyholder":
            env["total_claims_owed"] = round(sum(bundle.pending_claims.values()), 2)
            env["n_claims"] = len(bundle.pending_claims)
            run_cat_ma._sync_prompt_env(agents["INSURER"], env)
            run_cat_ma._sync_prompt_env(agents["GOV"], env)
        elif getattr(agent, "agent_type", "") == "insurer_ma":
            env["settlement_disposition"] = bundle.disposition or "undecided"
            run_cat_ma._sync_prompt_env(agents["GOV"], env)

    def on_post_step_end(year, all_agents):
        settlement = bundle.settle_period()
        settlements.append(settlement)
        claims = settlement.get("claims", {}) or {}
        for aid in POLICYHOLDER_IDS:
            owed = float(claims.get(aid, 0.0) or 0.0)
            paid = float((settlement.get("per_agent_paid", {}) or {}).get(aid, 0.0) or 0.0)
            relief = float((settlement.get("per_agent_relief", {}) or {}).get(aid, 0.0) or 0.0)
            if owed <= 0.0 and paid <= 0.0 and relief <= 0.0:
                continue
            runner_holder["runner"].memory_engine.add_memory(
                aid,
                (
                    f"Insurance settlement: received ${paid:.2f} of ${owed:.2f} "
                    f"owed (rule: {settlement['rule']}); government relief ${relief:.2f}"
                ),
                {
                    "emotion": "major",
                    "importance": 0.8,
                    "significance": 0.8,
                    "source": "settlement",
                },
            )

    output_dir = tmp_path / "ma_results"
    runner = (
        ExperimentBuilder()
        .with_model("scripted-test")
        .with_years(years)
        .with_agents(agents)
        .with_coupling(run_cat_ma._build_contract(), bundle, domain="cat_model_ma")
        .with_governance("strict", str(CONFIG / "ma_cat_agent_types.yaml"))
        .with_skill_registry(str(CONFIG / "ma_cat_skill_registry.yaml"))
        .with_phase_order([["policyholder"], ["insurer_ma"], ["government_ma"]])
        .with_memory_engine(WindowMemoryEngine(window_size=5))
        .with_lifecycle_hooks(
            pre_year=on_pre_year,
            post_step=on_post_step,
            post_step_end=on_post_step_end,
        )
        .with_exact_output(str(output_dir))
        .with_workers(1)
        .with_seed(42)
    ).build()
    _script_llm_cache(runner, insurer=insurer, government=government)
    runner_holder["runner"] = runner
    runner.run()
    return ScriptedRun(
        runner=runner,
        bundle=bundle,
        agents=agents,
        output_dir=output_dir,
        settlements=settlements,
        env_snapshots=env_snapshots,
        premium_snapshots=premium_snapshots,
    )


def _engine(dispatch):
    cfg = MagicMock()
    cfg.get_log_fields.return_value = []
    cfg.get_base_type.side_effect = lambda agent_type: agent_type
    return SkillBrokerEngine(
        skill_registry=SkillRegistry(),
        model_adapter=MagicMock(),
        validators=[],
        simulation_engine=MagicMock(),
        context_builder=MagicMock(),
        config=cfg,
        domain_physical_dispatch=dispatch,
    )


def _proposal(skill_name: str, agent_type: str, agent_id: str) -> SkillProposal:
    return SkillProposal(
        skill_name=skill_name,
        agent_id=agent_id,
        reasoning={},
        agent_type=agent_type,
        parse_layer="test",
    )


def _jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            record = json.loads(line)
            if "_metadata" not in record:
                records.append(record)
    return records


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _money_from_prompt(prompt: str, label: str) -> float:
    match = re.search(rf"{re.escape(label)}:\s*\$?([0-9.,-]+)", prompt)
    assert match, prompt
    return float(match.group(1).replace(",", ""))


def test_settlement_math_prorata_and_conservation():
    bundle = _bundle(pool=100.0, gov_budget=0.0, premium_per_period=0.0)
    bundle.pending_claims = {"PH1": 50.0, "PH2": 150.0}
    bundle.disposition = "settle_prorata"

    record = bundle.settle_period()

    assert record["rule"] == "pro_rata"
    assert record["per_agent_paid"]["PH1"] == pytest.approx(25.0, abs=0.01)
    assert record["per_agent_paid"]["PH2"] == pytest.approx(75.0, abs=0.01)
    assert sum(record["per_agent_paid"].values()) == pytest.approx(100.0, abs=1e-6)
    assert record["pool_remaining"] == 0.0

    second = bundle.settle_period()
    assert second["rule"] == "already_settled"
    assert bundle.ledger.pool_budget == 0.0


def test_settlement_order_independence():
    claims = {"PH1": 50.0, "PH2": 150.0, "PH3": 100.0}
    forward = _bundle(pool=120.0, gov_budget=0.0, premium_per_period=0.0)
    reverse = _bundle(pool=120.0, gov_budget=0.0, premium_per_period=0.0)
    forward.pending_claims = dict(claims)
    reverse.pending_claims = dict(reversed(list(claims.items())))
    forward.disposition = "settle_prorata"
    reverse.disposition = "settle_prorata"

    assert forward.settle_period()["per_agent_paid"] == reverse.settle_period()["per_agent_paid"]


def test_aggregate_governance_wall():
    engine = _engine("cat_model_ma")
    insolvent = {
        "agent_type": "insurer_ma",
        "env_state": {"total_claims_owed": 200.0, "pool_budget_remaining": 100.0},
    }

    blocked = engine._run_validators(
        _proposal("settle_full", "insurer_ma", "INSURER"),
        dict(insolvent),
    )
    assert any(
        not r.valid and r.metadata.get("rule_id") == "pool_insolvent_aggregate"
        for r in blocked
    ), [getattr(r, "metadata", r) for r in blocked]

    allowed = engine._run_validators(
        _proposal("settle_prorata", "insurer_ma", "INSURER"),
        dict(insolvent),
    )
    assert all(r.valid for r in allowed)


def test_lapsed_policyholder_cannot_file():
    engine = _engine("cat_model_ma")

    lapsed = engine._run_validators(
        _proposal("file_claim", "policyholder", "PH4"),
        {
            "agent_type": "policyholder",
            "env_state": {
                "policy_in_force_self": False,
                "own_ground_up_loss": 10_000.0,
            },
        },
    )
    assert any(
        not r.valid and r.metadata.get("rule_id") == "policy_not_in_force"
        for r in lapsed
    )

    no_loss = engine._run_validators(
        _proposal("file_claim", "policyholder", "PH1"),
        {
            "agent_type": "policyholder",
            "env_state": {
                "policy_in_force_self": True,
                "own_ground_up_loss": 0.0,
            },
        },
    )
    assert any(
        not r.valid and r.metadata.get("rule_id") == "no_loss_to_claim"
        for r in no_loss
    )

    valid = engine._run_validators(
        _proposal("file_claim", "policyholder", "PH1"),
        {
            "agent_type": "policyholder",
            "env_state": {
                "policy_in_force_self": True,
                "own_ground_up_loss": 10_000.0,
            },
        },
    )
    assert all(r.valid for r in valid)


def test_phase_visibility_pin(tmp_path, monkeypatch):
    run = _run_scripted_ma(tmp_path, monkeypatch, years=1, insurer=_insurer_prorata)
    insurer_records = _jsonl_records(run.output_dir / "raw" / "insurer_ma_traces.jsonl")

    owed_from_prompt = _money_from_prompt(
        insurer_records[0]["input"],
        "Queued legitimate claims owed",
    )
    # Exact pinned arithmetic (review C1 strengthening): year-1 depth 2.0 ft,
    # zone multipliers 1.0/0.6/1.4 -> PH1 owed 47,500 + PH2 21,280 +
    # PH3 82,680 = 151,460 (PH4 out of force). The same-year total MUST be
    # visible in the insurer's rendered prompt — the live-channel pin.
    assert owed_from_prompt == pytest.approx(151_460.0)
    assert insurer_records[0]["environment_context"]["total_claims_owed"] == pytest.approx(
        151_460.0
    )


def test_government_relief_capped():
    bundle = _bundle(pool=100.0, gov_budget=40.0, premium_per_period=0.0)
    bundle.pending_claims = {"PH1": 50.0, "PH2": 150.0}
    bundle.disposition = "settle_prorata"
    bundle.relief_intent = True

    record = bundle.settle_period()

    assert record["rule"] == "pro_rata"
    assert record["per_agent_relief"]["PH1"] == pytest.approx(10.0, abs=0.01)
    assert record["per_agent_relief"]["PH2"] == pytest.approx(30.0, abs=0.01)
    assert sum(record["per_agent_relief"].values()) == pytest.approx(40.0, abs=1e-6)
    assert record["gov_budget_remaining"] == 0.0
    for aid, owed in record["claims"].items():
        assert record["per_agent_paid"][aid] + record["per_agent_relief"][aid] <= owed

    no_relief = _bundle(pool=100.0, gov_budget=40.0, premium_per_period=0.0)
    no_relief.pending_claims = {"PH1": 50.0, "PH2": 150.0}
    no_relief.disposition = "settle_prorata"
    no_relief.relief_intent = False
    assert sum(no_relief.settle_period()["per_agent_relief"].values()) == 0.0


def test_audit_conservation_ma(tmp_path, monkeypatch):
    run = _run_scripted_ma(tmp_path, monkeypatch, years=2, insurer=_insurer_prorata)
    # Per-file breakdown (review W3): a total-only assertion would pass if a
    # routing bug dumped all 12 rows into one agent-type CSV.
    ph_rows = _csv_rows(run.output_dir / "policyholder_governance_audit.csv")
    ins_rows = _csv_rows(run.output_dir / "insurer_ma_governance_audit.csv")
    gov_rows = _csv_rows(run.output_dir / "government_ma_governance_audit.csv")
    assert len(ph_rows) == 4 * 2
    assert len(ins_rows) == 1 * 2
    assert len(gov_rows) == 1 * 2
    assert len(ph_rows) + len(ins_rows) + len(gov_rows) == 6 * 2


def test_settlement_reaches_audit_plane(tmp_path, monkeypatch):
    run = _run_scripted_ma(tmp_path, monkeypatch, years=1, insurer=_insurer_prorata)
    insurer_rows = _csv_rows(run.output_dir / "insurer_ma_governance_audit.csv")
    policyholder_rows = _csv_rows(run.output_dir / "policyholder_governance_audit.csv")

    assert insurer_rows[0]["final_skill"] == "settle_prorata"
    assert insurer_rows[0]["world_disposition"] == "settle_prorata"
    assert insurer_rows[0]["world_contention_rule"] == "pending_settlement"

    ph1 = next(row for row in policyholder_rows if row["agent_id"] == "PH1")
    assert float(ph1["world_claim_filed"]) == pytest.approx(
        run.bundle.period_losses["PH1"][1]
    )


def test_per_agent_intensity():
    event_src = MaFootprintSource({1: 2.0}, ZONE_MULTIPLIERS)
    bundle = _bundle(
        pool=0.0,
        gov_budget=0.0,
        depths={1: 2.0},
        households=_households(
            exposures={aid: 100_000.0 for aid in POLICYHOLDER_IDS},
            deductible=0.0,
            limit=1_000_000.0,
        ),
        premium_per_period=0.0,
    )
    event = event_src.draw_events(1)[0]
    bundle.run_pipeline({"current_year": 1}, [event], ())

    ph2_ground = bundle.period_losses["PH2"][0]
    ph1_ground = bundle.period_losses["PH1"][0]
    ph3_ground = bundle.period_losses["PH3"][0]
    assert ph2_ground < ph1_ground < ph3_ground
    assert ph3_ground == pytest.approx(
        depth_damage_ratio(2.0 * 1.4) * 100_000.0,
        abs=0.01,
    )


def test_e2e_two_year_scenario(tmp_path, monkeypatch):
    run = _run_scripted_ma(
        tmp_path,
        monkeypatch,
        years=2,
        gov_budget=150_000.0,
        insurer=_insurer_full_then_prorata,
        government=_government_relief,
    )

    assert len(run.settlements) == 2
    assert [s["rule"] for s in run.settlements] == ["pro_rata", "pro_rata"]
    assert all(s["total_relief"] > 0.0 for s in run.settlements)
    assert (run.output_dir / "audit_summary.json").exists()

    insurer_rows = _csv_rows(run.output_dir / "insurer_ma_governance_audit.csv")
    year1 = next(row for row in insurer_rows if row["year"] == "1")
    # AND, not OR (review W2): a pool_insolvent_aggregate block MUST produce a
    # retry — these are complementary evidence, not alternatives. Split for
    # clearer failure messages.
    assert int(year1["retry_count"]) >= 1
    assert "pool_insolvent_aggregate" in year1.get("failed_rules", "")

    ph1_memories = run.runner.memory_engine.retrieve(run.agents["PH1"], top_k=10)
    # Review W1: pin the settlement RULE inside the memory text too, so a
    # corrupted-path string starting with the same prefix cannot pass.
    assert any(
        "Insurance settlement:" in memory and "pro_rata" in memory
        for memory in ph1_memories
    )


def test_registration_isolation():
    import examples.cat_model.ma_validators  # noqa: F401
    from examples.cat_model.cat_validators import insurer_payout_solvency_check

    cat_checks = ValidatorRegistry.get_checks("cat_model", "physical")
    ma_checks = ValidatorRegistry.get_checks("cat_model_ma", "physical")

    assert insurer_payout_solvency_check in cat_checks
    assert policyholder_claim_check in ma_checks
    assert insurer_settlement_check in ma_checks
    # Review S4: no cross-contamination in EITHER direction — the single-agent
    # check must not bleed into the MA bucket nor vice versa.
    assert insurer_payout_solvency_check not in ma_checks
    assert policyholder_claim_check not in cat_checks
    assert insurer_settlement_check not in cat_checks
    assert DomainPackRegistry.get("cat_model") is not None
    assert DomainPackRegistry.get("cat_model_ma") is not None


def test_premiums_only_in_force_and_augmented_pool_settlement():
    bundle = _bundle(pool=60_000.0, gov_budget=0.0)
    env = bundle.run_pipeline(
        {"current_year": 1},
        bundle.event_src.draw_events(1),
        (),
    )
    claims = {
        aid: owed
        for aid, (_ground, owed) in bundle.period_losses.items()
        if owed > 0.0
    }
    bundle.pending_claims = claims
    bundle.disposition = "settle_prorata"

    assert env["premiums_collected"] == 3_600.0
    assert env["pool_budget_remaining"] == 63_600.0
    assert bundle.period_losses["PH4"][1] == 0.0

    record = bundle.settle_period()
    expected_total_owed = sum(claims.values())
    # Review S3: guard the precondition — pro-rata only fires when owed
    # exceeds the premium-augmented pool.
    assert expected_total_owed > 63_600.0
    assert record["rule"] == "pro_rata"
    assert record["total_paid"] == pytest.approx(63_600.0)
    assert record["payout_ratio"] == pytest.approx(63_600.0 / expected_total_owed)
