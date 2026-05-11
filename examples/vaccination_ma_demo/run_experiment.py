"""Multi-agent vaccination demo — Phase 6E entry point.

Three agent types: health_authority (1) → community_org (2) → individual (N).
Cross-agent state via env-dict-whitelist pattern (Phase 1 verdict).

Smoke target: 3 agent types × N individuals × Y years = 1 + 2 + N decisions/year
= (3 + N) × Y traces total. Default 3 individuals × 3 years = (3 + 3) × 3 = 18.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# CRITICAL: package import triggers HBM registration + DomainPack registration
# + validator registration BEFORE the experiment is constructed.
import examples.vaccination_ma_demo  # noqa: F401  side-effect

from broker.agents import BaseAgent, AgentConfig
from broker.agents.base import Skill, StateParam
from broker.components.memory.engine import WindowMemoryEngine
from broker.components.context.tiered import TieredContextBuilder, load_prompt_templates
from broker.core.experiment import ExperimentBuilder
from examples.vaccination_ma_demo.lifecycle_hooks import VaccinationMAHooks


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_YAML = SCRIPT_DIR / "config" / "agent_types.yaml"
SKILL_YAML = SCRIPT_DIR / "config" / "skill_registry.yaml"


# Cross-agent state keys that lifecycle_hooks writes and prompts read.
# These MUST match the env-dict keys in lifecycle_hooks.py and the
# {placeholder} names in config/prompts/*.txt.
# (Phase 1 verdict: this list is the abstraction point; everything else
# generic in broker.)
DYNAMIC_WHITELIST = [
    "year",
    "advisory_strength_label",
    "advisory_text",
    "outbreak_severity_label",
    "outbreak_severity",
    "vaccination_rate_text",
    "vaccination_rate",
    "community_activity_label",
    "community_support_text",
]


# ─────────────────────────────────────────────────────────────────────
# Synthetic agents
# ─────────────────────────────────────────────────────────────────────


def _make_skills(skill_ids: list[str]) -> list[Skill]:
    """Minimal Skill objects (broker uses YAML for full definitions)."""
    return [Skill(s, s, None, "none") for s in skill_ids]


def build_synthetic_agents(n_individuals: int, seed: int) -> Dict[str, BaseAgent]:
    rng = random.Random(seed)
    agents: Dict[str, BaseAgent] = {}

    # --- 1× health_authority -----------------------------------------
    ha_cfg = AgentConfig(
        name="HA_01",
        agent_type="health_authority",
        state_params=[
            StateParam("budget_pct", (0, 100), 100.0, "Budget remaining percent"),
        ],
        objectives=[],
        constraints=[],
        skills=_make_skills(["advisory_none", "advisory_mild", "advisory_strong"]),
    )
    ha = BaseAgent(ha_cfg)
    ha.narrative_persona = (
        "You serve as the public health authority for this region. Your "
        "mission is to protect the population from vaccine-preventable illness "
        "while preserving public trust in your office's recommendations."
    )
    agents[ha_cfg.name] = ha

    # --- 2× community_org --------------------------------------------
    for i in range(2):
        co_cfg = AgentConfig(
            name=f"CO_{i+1:02d}",
            agent_type="community_org",
            state_params=[
                StateParam("budget", (0, 100), 100.0, "Annual outreach budget pct"),
            ],
            objectives=[],
            constraints=[],
            skills=_make_skills(["org_none", "org_education", "org_clinic"]),
        )
        co = BaseAgent(co_cfg)
        focus = rng.choice(["family-focused", "elderly-focused", "general"])
        co.narrative_persona = (
            f"You direct a {focus} community organization. You have a fixed "
            "annual budget for outreach and must decide each year whether to "
            "spend it on education, mobile clinics, or save it."
        )
        agents[co_cfg.name] = co

    # --- N× individual -----------------------------------------------
    for i in range(n_individuals):
        age_bracket = rng.choice(["18-34", "35-54", "55-74", "75+"])
        trust = round(rng.uniform(0.2, 0.95), 2)
        high_risk = age_bracket in ("55-74", "75+") or rng.random() < 0.15
        ind_cfg = AgentConfig(
            name=f"IND_{i+1:03d}",
            agent_type="individual",
            state_params=[
                StateParam("vaccinated", (0, 1), 0.0, "Received dose this cycle"),
                StateParam("weeks_since_dose", (0, 999), 999.0, "Weeks since last dose"),
            ],
            objectives=[],
            constraints=[],
            skills=_make_skills(["get_vaccinated", "delay", "refuse"]),
        )
        ind = BaseAgent(ind_cfg)
        ind.narrative_persona = (
            f"You are a {age_bracket}-year-old. You "
            f"{'are' if high_risk else 'are not'} in a high-risk medical group. "
            f"Your trust in public health is "
            f"{'high' if trust > 0.6 else 'moderate' if trust > 0.4 else 'low'}."
        )
        ind.is_high_risk_group = high_risk
        ind.trust_in_authority = trust
        agents[ind_cfg.name] = ind

    return agents


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(description="vaccination_ma_demo PoC")
    p.add_argument("--model", default="gemma3:1b")
    p.add_argument("--years", type=int, default=3)
    p.add_argument(
        "--agents",
        type=int,
        default=3,
        help="Number of individual citizen agents (1 HA + 2 CO + N individuals)",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--output",
        default=str(SCRIPT_DIR / "results" / "smoke"),
    )
    p.add_argument("--num-ctx", type=int, default=4096)
    p.add_argument("--num-predict", type=int, default=1024)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    # ---- Agents -----------------------------------------------------
    agents = build_synthetic_agents(args.agents, args.seed)

    # ---- Environment + lifecycle hooks ------------------------------
    env: Dict[str, Any] = {}
    memory_engine = WindowMemoryEngine(window_size=4)
    hooks = VaccinationMAHooks(environment=env, memory_engine=memory_engine)

    # ---- Context builder with dynamic whitelist ---------------------
    # This is the Phase 1 verdict's abstraction point — env keys named
    # below reach every agent's prompt as {placeholder} substitutions.
    ctx_builder = TieredContextBuilder(
        agents=agents,
        # hub omitted — no InteractionHub means no spatial gossip / neighbor
        # sharing; the env-dict-whitelist below is the cross-agent channel.
        memory_engine=memory_engine,
        yaml_path=str(CONFIG_YAML),
        dynamic_whitelist=DYNAMIC_WHITELIST,
        prompt_templates=load_prompt_templates(str(CONFIG_YAML)),
    )

    # ---- ExperimentBuilder ------------------------------------------
    # `with_phase_order` ensures health_authority decides before
    # community_org, before individual — so each tier's prompt reads
    # the previous tier's most recent env state.
    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_skill_registry(str(SKILL_YAML))
        .with_memory_engine(memory_engine)
        .with_lifecycle_hooks(
            pre_year=hooks.pre_year,
            post_step=hooks.post_step,
            post_year=lambda year, ags: hooks.post_year(year, ags, memory_engine),
        )
        .with_context_builder(ctx_builder)
        .with_phase_order(
            [["health_authority"], ["community_org"], ["individual"]]
        )
        .with_governance("strict", str(CONFIG_YAML))
        .with_exact_output(args.output)
        .with_workers(1)
        .with_seed(args.seed)
        .with_verbose(args.verbose)
    ).build()

    n_ha = 1
    n_co = 2
    n_ind = args.agents
    print(
        f"--- vaccination_ma_demo PoC | {args.model} | "
        f"{n_ha} HA + {n_co} CO + {n_ind} individuals | "
        f"{args.years} years | seed={args.seed} ---"
    )
    runner.run()
    print(f"--- Complete! Results in {args.output} ---")


if __name__ == "__main__":
    main()
