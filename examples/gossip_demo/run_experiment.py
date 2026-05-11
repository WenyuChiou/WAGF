"""gossip_demo — Phase 6F multi-agent social-media smoke runner.

Three agent types:
  1× platform_moderator (institutional)
  K× influencer (intermediary content producers)
  N× casual_user (citizen consumers)

Cadence: "year" reinterpreted as "day". 5-day smoke default. Daily
LLM cost with gemma3:1b ~= cheap; with larger models the cost scales
linearly so keep small for development.

Mirror of examples/vaccination_ma_demo/run_experiment.py — proven
pattern for non-water multi-agent demos.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# CRITICAL: package import triggers DomainPack registration +
# register_social_spec BEFORE the experiment is constructed.
import examples.gossip_demo  # noqa: F401  side-effect

from broker.agents import BaseAgent, AgentConfig
from broker.agents.base import Skill, StateParam
from broker.components.memory.engine import WindowMemoryEngine
from broker.components.context.tiered import TieredContextBuilder, load_prompt_templates
from broker.core.experiment import ExperimentBuilder
from examples.gossip_demo.lifecycle_hooks import GossipHooks


SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_YAML = SCRIPT_DIR / "config" / "agent_types.yaml"
SKILL_YAML = SCRIPT_DIR / "config" / "skill_registry.yaml"


# Cross-agent state keys — lifecycle_hooks writes these, prompts read.
DYNAMIC_WHITELIST = [
    "year",
    "trending_topic_text",
    "sentiment_trend_label",
    "moderator_warning_active",
    "prior_moderation_label",
    "focus_post_summary",
    "pending_reports_label",
]


def _make_skills(skill_ids: list[str]) -> list[Skill]:
    return [Skill(s, s, None, "none") for s in skill_ids]


def build_synthetic_agents(n_users: int, n_influencers: int, seed: int) -> Dict[str, BaseAgent]:
    rng = random.Random(seed)
    agents: Dict[str, BaseAgent] = {}

    # --- 1× platform_moderator -------------------------------------
    mod_cfg = AgentConfig(
        name="MOD_01",
        agent_type="platform_moderator",
        state_params=[
            StateParam("trust_capital", (0, 100), 75.0, "Community trust in moderation"),
        ],
        objectives=[],
        constraints=[],
        skills=_make_skills(["boost_signal", "demote_misinfo", "warn_community", "do_nothing"]),
    )
    mod = BaseAgent(mod_cfg)
    mod.narrative_persona = (
        "You serve as the platform's community moderator. Your duty is to "
        "preserve healthy discourse without overreach. You see all reports "
        "and trending signals."
    )
    agents[mod_cfg.name] = mod

    # --- K× influencer ---------------------------------------------
    for i in range(n_influencers):
        style = rng.choice(["activist", "lifestyle", "civic", "humorist"])
        grid_x = rng.randint(0, 9)
        grid_y = rng.randint(0, 9)
        inf_cfg = AgentConfig(
            name=f"INF_{i+1:02d}",
            agent_type="influencer",
            state_params=[
                StateParam("reach", (0, 1000), float(rng.randint(200, 800)), "Followers"),
                StateParam("reputation", (0, 100), float(rng.randint(40, 90)), "Reputation"),
            ],
            objectives=[],
            constraints=[],
            skills=_make_skills(["post_neutral", "post_polarizing", "share_trending", "stay_silent"]),
        )
        inf = BaseAgent(inf_cfg)
        inf.narrative_persona = (
            f"You are a {style}-focused influencer in this community. You "
            "balance reach versus reputation; polarizing content gets more "
            "engagement but invites moderation."
        )
        inf.dynamic_state["grid_x"] = grid_x
        inf.dynamic_state["grid_y"] = grid_y
        agents[inf_cfg.name] = inf

    # --- N× casual_user --------------------------------------------
    for i in range(n_users):
        age_bracket = rng.choice(["18-34", "35-54", "55+"])
        trust_in_platform = round(rng.uniform(0.3, 0.9), 2)
        grid_x = rng.randint(0, 9)
        grid_y = rng.randint(0, 9)
        usr_cfg = AgentConfig(
            name=f"USR_{i+1:03d}",
            agent_type="casual_user",
            state_params=[
                StateParam("engagement_streak", (0, 999), 0.0, "Consecutive days active"),
            ],
            objectives=[],
            constraints=[],
            skills=_make_skills(["share", "like", "ignore", "report"]),
        )
        usr = BaseAgent(usr_cfg)
        usr.narrative_persona = (
            f"You are a {age_bracket} regular user. Your trust in this "
            f"platform's moderation is "
            f"{'high' if trust_in_platform > 0.6 else 'moderate' if trust_in_platform > 0.4 else 'low'}."
        )
        usr.dynamic_state["grid_x"] = grid_x
        usr.dynamic_state["grid_y"] = grid_y
        agents[usr_cfg.name] = usr

    return agents


def main() -> None:
    p = argparse.ArgumentParser(description="gossip_demo Phase 6F PoC")
    p.add_argument("--model", default="gemma3:1b")
    p.add_argument("--days", type=int, default=5,
                   help="Simulation days (reinterpreted as the 'years' arg)")
    p.add_argument("--users", type=int, default=3,
                   help="Number of casual_user agents")
    p.add_argument("--influencers", type=int, default=2,
                   help="Number of influencer agents")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output",
                   default=str(SCRIPT_DIR / "results" / "smoke"))
    p.add_argument("--num-ctx", type=int, default=4096)
    p.add_argument("--num-predict", type=int, default=1024)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    # ---- Agents -----------------------------------------------------
    agents = build_synthetic_agents(args.users, args.influencers, args.seed)

    # ---- Environment + lifecycle hooks ------------------------------
    env: Dict[str, Any] = {}
    memory_engine = WindowMemoryEngine(window_size=7)
    hooks = GossipHooks(environment=env, memory_engine=memory_engine)

    # ---- Context builder with dynamic whitelist ---------------------
    ctx_builder = TieredContextBuilder(
        agents=agents,
        # Phase 6E: hub=None is now the default; broadcast via dynamic_whitelist.
        # Tier 2 (InteractionHub + SpatialNeighborhoodGraph) is a future
        # extension if per-user neighbor feed visibility is needed.
        memory_engine=memory_engine,
        yaml_path=str(CONFIG_YAML),
        dynamic_whitelist=DYNAMIC_WHITELIST,
        prompt_templates=load_prompt_templates(str(CONFIG_YAML)),
    )

    # ---- ExperimentBuilder ------------------------------------------
    runner = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.days)                     # "year" = day for gossip
        .with_agents(agents)
        .with_skill_registry(str(SKILL_YAML))
        .with_memory_engine(memory_engine)
        .with_lifecycle_hooks(
            pre_year=hooks.pre_year,
            post_step=hooks.post_step,
            post_year=lambda y, ags: hooks.post_year(y, ags, memory_engine),
        )
        .with_context_builder(ctx_builder)
        .with_phase_order(
            [["platform_moderator"], ["influencer"], ["casual_user"]]
        )
        .with_governance("strict", str(CONFIG_YAML))
        .with_exact_output(args.output)
        .with_workers(1)
        .with_seed(args.seed)
        .with_verbose(args.verbose)
    ).build()

    print(
        f"--- gossip_demo PoC | {args.model} | "
        f"1 MOD + {args.influencers} INF + {args.users} USR | "
        f"{args.days} days | seed={args.seed} ---"
    )
    runner.run()
    print(f"--- Complete! Results in {args.output} ---")


if __name__ == "__main__":
    main()
