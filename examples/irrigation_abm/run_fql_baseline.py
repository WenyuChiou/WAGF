#!/usr/bin/env python3
"""
FQL Baseline Runner — Hung & Yang (2021) Q-Learning for Nature Water comparison.

Runs the same 78-agent × 42-year irrigation simulation as run_experiment.py,
but replaces LLM skill selection with FQL Q-learning.  Everything else is
identical: same IrrigationEnvironment, same execute_skill() Gaussian magnitude
sampling, same 12 governance validators.

This produces a published rule-based baseline for comparison with governed
and ungoverned LLM agents in the Nature Water paper.

Usage:
    # Smoke test (5 agents, 5 years)
    python run_fql_baseline.py --years 5 --agents 5 --seed 42

    # Full production (78 CRSS agents, 42 years, 3 seeds)
    python run_fql_baseline.py --years 42 --real --seed 42 --rebalance-clusters
    python run_fql_baseline.py --years 42 --real --seed 43 --rebalance-clusters
    python run_fql_baseline.py --years 42 --real --seed 44 --rebalance-clusters

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.learning.fql import (
    FQLAgent,
    FQLConfig,
    FQLState,
    CLUSTER_AGGRESSIVE,
    CLUSTER_FORWARD_LOOKING,
    CLUSTER_MYOPIC,
)
from examples.irrigation_abm.learning.fql_skill_mapper import (
    fql_action_to_skill,
    compute_wsa_label,
    compute_aca_label,
)
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    create_profiles_from_data,
    rebalance_to_target,
)
from examples.irrigation_abm.validators.irrigation_validators import (
    ALL_IRRIGATION_CHECKS,
    INCREASE_SKILLS,
    DECREASE_SKILLS,
    reset_consecutive_tracker,
    update_consecutive_tracker,
)
from broker.interfaces.skill_types import ApprovedSkill

# ── Constants ──
# FQL has only 2 actions (Hung & Yang 2021): increase and decrease.
# No large/small distinction — that is an LLM-path concept.
FQL_SKILLS = ["increase_demand", "decrease_demand", "maintain_demand"]

CLUSTER_CONFIGS = {
    "aggressive": CLUSTER_AGGRESSIVE,
    "forward_looking_conservative": CLUSTER_FORWARD_LOOKING,
    "myopic_conservative": CLUSTER_MYOPIC,
}


# ─────────────────────────────────────────────────────────────────────
# FQL agent factory
# ─────────────────────────────────────────────────────────────────────

def create_fql_agents(
    profiles: List[IrrigationAgentProfile],
    seed: int = 42,
) -> Dict[str, Tuple[FQLAgent, FQLState]]:
    """Create FQL agent + state pairs from irrigation profiles.

    Each agent gets:
    - FQLConfig from its cluster's canonical parameters
    - FQLState with state_bounds = linspace(0, water_right, 21)
    - prev_diversion initialized from actual_2018_diversion (or 80% of water_right)

    Args:
        profiles: List of IrrigationAgentProfile with cluster and water_right.
        seed: Base random seed (each agent gets seed + index for reproducibility).

    Returns:
        Dict mapping agent_id → (FQLAgent, FQLState).
    """
    agents: Dict[str, Tuple[FQLAgent, FQLState]] = {}

    for i, p in enumerate(profiles):
        config = CLUSTER_CONFIGS.get(p.cluster, CLUSTER_FORWARD_LOOKING)

        # Per-agent FQL config using the profile's actual calibrated params
        agent_config = FQLConfig(
            mu=p.mu,
            sigma=p.sigma,
            alpha=p.alpha,
            gamma=p.gamma_param,
            epsilon=p.epsilon,
            regret=p.regret,
            forget=p.forget,
        )

        state = FQLState(
            state_bounds=np.linspace(0, p.water_right, 21),
        )
        state.initialize(agent_config)

        # Initialize prev_diversion from historical 2018 value
        init_div = p.actual_2018_diversion if p.actual_2018_diversion else p.water_right * 0.8
        state.prev_diversion = init_div

        rng = np.random.default_rng(seed + i)
        agent = FQLAgent(agent_config, rng=rng)

        agents[p.agent_id] = (agent, state)

    return agents


# ─────────────────────────────────────────────────────────────────────
# Validator integration
# ─────────────────────────────────────────────────────────────────────

def validate_skill(
    skill_name: str,
    context: Dict[str, Any],
) -> Tuple[bool, str]:
    """Run all 12 irrigation validators on a proposed skill.

    NOTE: The LLM path uses broker's RejectionHandler which re-invokes the LLM
    on rejection. Since FQL has no LLM, we use a deterministic 2-tier fallback:
    1. maintain_demand (neutral fallback, matches LLM REJECTED default)
    2. decrease_demand (last resort, always physically valid)

    Args:
        skill_name: Proposed skill name.
        context: Validation context (from env.get_agent_context + extras).

    Returns:
        (is_valid, final_skill_name) — if blocked, tries fallback.
    """
    results = []
    for check in ALL_IRRIGATION_CHECKS:
        results.extend(check(skill_name, [], context))

    blocked = any(not r.valid for r in results)
    if not blocked:
        return True, skill_name

    # Fallback 1: maintain_demand (always valid except at zero escape)
    results2 = []
    for check in ALL_IRRIGATION_CHECKS:
        results2.extend(check("maintain_demand", [], context))
    if all(r.valid for r in results2):
        return True, "maintain_demand"

    # Last resort: decrease_demand (should always pass)
    return True, "decrease_demand"


# ─────────────────────────────────────────────────────────────────────
# Simulation loop
# ─────────────────────────────────────────────────────────────────────

def run_simulation(
    env: IrrigationEnvironment,
    fql_agents: Dict[str, Tuple[FQLAgent, FQLState]],
    profiles: Dict[str, IrrigationAgentProfile],
    n_years: int,
    output_dir: Path,
    seed: int = 42,
    no_governance: bool = False,
) -> List[Dict[str, Any]]:
    """Run FQL baseline simulation.

    Mirrors the LLM runner's lifecycle:
    1. advance_year() — generate water signals
    2. For each agent: FQL step → skill mapping → (optionally validate) → execute
    3. Log results in identical CSV format

    Args:
        env: Initialized IrrigationEnvironment.
        fql_agents: Dict from create_fql_agents().
        profiles: Dict of agent_id → IrrigationAgentProfile.
        n_years: Number of simulation years.
        output_dir: Directory for output files.
        seed: Random seed.
        no_governance: If True, skip all validators (raw FQL behavior).

    Returns:
        List of log dicts (one per agent per year).
    """
    logs: List[Dict[str, Any]] = []
    agent_ids = env.agent_ids

    reset_consecutive_tracker()

    for year_idx in range(1, n_years + 1):
        # Advance environment (generates precipitation, Mead level, curtailment)
        env.advance_year()
        sim_year = env.current_year

        year_skills = {}
        year_blocked = 0

        for aid in agent_ids:
            if aid not in fql_agents:
                continue

            fql_agent, fql_state = fql_agents[aid]
            profile = profiles.get(aid)
            if profile is None:
                continue

            # Get agent context (same as LLM pre_year hook)
            ctx = env.get_agent_context(aid)
            agent_state = env.get_agent_state(aid)
            current_diversion = ctx["current_diversion"]

            # ── FQL step: get continuous action ──
            # Preceding factor: use persistence assumption f_next = f_t
            pf = ctx["preceding_factor"]
            preceding = (pf, pf)

            action = fql_agent.step(fql_state, current_diversion, preceding)

            # ── Map to 2-action model (faithful to FQL) ──
            raw_skill = fql_action_to_skill(action)

            # ── Validate and fallback (skip if --no-governance) ──
            if no_governance:
                final_skill = raw_skill
                was_blocked = False
            else:
                val_context = {
                    "agent_id": aid,
                    "at_allocation_cap": agent_state.get("at_allocation_cap", False),
                    "has_efficient_system": agent_state.get("has_efficient_system", False),
                    "below_minimum_utilisation": agent_state.get("below_minimum_utilisation", False),
                    "water_right": ctx.get("water_right", 0),
                    "current_diversion": ctx.get("current_diversion", 0),
                    "current_request": ctx.get("current_request", 0),
                    "curtailment_ratio": ctx.get("curtailment_ratio", 0),
                    "shortage_tier": ctx.get("shortage_tier", 0),
                    "drought_index": ctx.get("drought_index", 0.5),
                    "cluster": ctx.get("cluster", "unknown"),
                    "basin": ctx.get("basin", "unknown"),
                    "total_basin_demand": ctx.get("total_basin_demand", 0),
                    "loop_year": year_idx,
                }
                was_valid, final_skill = validate_skill(raw_skill, val_context)
                was_blocked = (final_skill != raw_skill)
                if was_blocked:
                    year_blocked += 1

            # ── Execute skill via environment (same Gaussian magnitude) ──
            approved = ApprovedSkill(
                skill_name=final_skill,
                agent_id=aid,
                approval_status="APPROVED",
            )
            exec_result = env.execute_skill(approved)
            state_changes = exec_result.state_changes if exec_result else {}

            # ── Update consecutive tracker (same as LLM post_step) ──
            update_consecutive_tracker(aid, final_skill)

            # ── Logging (identical columns to LLM output) ──
            new_agent_state = env.get_agent_state(aid)
            logs.append({
                "agent_id": aid,
                "year": year_idx,
                "cluster": profile.cluster,
                "basin": profile.basin,
                "yearly_decision": final_skill,
                "fql_raw_skill": raw_skill,
                "fql_action": action,
                "fql_blocked": was_blocked,
                "wsa_label": compute_wsa_label(ctx["drought_index"]),
                "aca_label": compute_aca_label(profile.cluster),
                "request": new_agent_state.get("request", 0),
                "diversion": new_agent_state.get("diversion", 0),
                "water_right": new_agent_state.get("water_right", 0),
                "curtailment_ratio": new_agent_state.get("curtailment_ratio", 0),
                "drought_index": ctx["drought_index"],
                "shortage_tier": ctx["shortage_tier"],
                "lake_mead_level": env.get_local("lower_basin", "lake_mead_level", 0),
                "mead_storage_maf": env._mead_storage[-1] if env._mead_storage else 0,
                "has_efficient_system": new_agent_state.get("has_efficient_system", False),
                "below_minimum_utilisation": new_agent_state.get("below_minimum_utilisation", False),
                "utilisation_pct": (
                    new_agent_state.get("request", 0) / new_agent_state.get("water_right", 1) * 100
                    if new_agent_state.get("water_right", 0) > 0 else 0
                ),
                "magnitude_pct": state_changes.get("magnitude_pct_applied"),
                "magnitude_fallback": False,
                "is_exploration": state_changes.get("is_exploration", False),
                "memory": "FQL_BASELINE",
            })

            year_skills[final_skill] = year_skills.get(final_skill, 0) + 1

        # Year summary
        n_agents = len(agent_ids)
        skill_summary = ", ".join(f"{k}={v}" for k, v in sorted(year_skills.items()))
        mead = env.get_local("lower_basin", "lake_mead_level", 0)
        drought = env.global_state.get("drought_index", 0)
        print(
            f"  Year {year_idx:3d} (sim {sim_year}) | "
            f"Mead={mead:.1f}ft | drought={drought:.2f} | "
            f"blocked={year_blocked}/{n_agents} | {skill_summary}"
        )

    return logs


# ─────────────────────────────────────────────────────────────────────
# Synthetic profile builder (for smoke tests without CRSS data)
# ─────────────────────────────────────────────────────────────────────

def _create_synthetic_profiles(
    n_agents: int,
    seed: int = 42,
) -> List[IrrigationAgentProfile]:
    """Create synthetic profiles with balanced cluster distribution."""
    from examples.irrigation_abm.irrigation_personas import build_narrative_persona

    rng = np.random.default_rng(seed)
    clusters = ["aggressive", "forward_looking_conservative", "myopic_conservative"]

    profiles = []
    for i in range(n_agents):
        basin = "upper_basin" if i < n_agents // 3 else "lower_basin"
        cluster = clusters[i % 3]
        ref = CLUSTER_CONFIGS[cluster]

        profile = IrrigationAgentProfile(
            agent_id=f"Agent_{i:03d}",
            basin=basin,
            cluster=cluster,
            mu=ref.mu + rng.normal(0, 0.02),
            sigma=ref.sigma + rng.normal(0, 0.1),
            alpha=ref.alpha + rng.normal(0, 0.02),
            gamma_param=ref.gamma + rng.normal(0, 0.02),
            epsilon=ref.epsilon + rng.normal(0, 0.01),
            regret=ref.regret + rng.normal(0, 0.1),
            forget=True,
            farm_size_acres=rng.uniform(200, 2000),
            water_right=rng.uniform(50_000, 200_000),
            crop_type=str(rng.choice(["alfalfa", "cotton", "vegetables", "corn"])),
            years_farming=int(rng.integers(5, 40)),
        )
        profile.narrative_persona = build_narrative_persona(profile, rng)
        profiles.append(profile)

    return profiles


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()
    base = Path(__file__).parent
    ref_dir = PROJECT_ROOT / "ref"

    # Random seed
    seed = args.seed
    random.seed(seed)
    np.random.seed(seed)

    # Feature flags: enable demand_ceiling by default (matches LLM production)
    import examples.irrigation_abm.validators.irrigation_validators as irr_validators
    irr_validators.ENABLE_CONSECUTIVE_CAP = False
    irr_validators.ENABLE_ZERO_ESCAPE = False
    irr_validators.ENABLE_DEMAND_CEILING = True

    # Create profiles
    if args.real:
        params_csv = str(ref_dir / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv")
        crss_db = str(ref_dir / "CRSS_DB" / "CRSS_DB")
        profiles = create_profiles_from_data(
            params_csv_path=params_csv,
            crss_db_dir=crss_db,
            rng=np.random.default_rng(seed),
        )
        print(f"[Data] Loaded {len(profiles)} real CRSS agents from paper data")
    else:
        profiles = _create_synthetic_profiles(args.agents, seed)
        print(f"[Data] Created {len(profiles)} synthetic agents")

    # Optional cluster rebalancing (matches LLM experiment)
    if args.rebalance_clusters:
        from collections import Counter
        before = Counter(p.cluster for p in profiles)

        target_dist = {
            "aggressive": 0.50,
            "forward_looking_conservative": 0.30,
            "myopic_conservative": 0.20,
        }
        rebalance_to_target(profiles, target_dist, rng=np.random.default_rng(seed))

        after = Counter(p.cluster for p in profiles)
        print(f"[Rebalance] Clusters: {dict(before)} → {dict(after)} (target: 50%-30%-20%)")

    # Set persona-specific magnitude parameters from config (for execute_skill)
    config_dir = base / "config"
    agent_config_path = config_dir / "agent_types.yaml"
    if agent_config_path.exists():
        import yaml
        with open(agent_config_path, "r", encoding="utf-8") as f:
            cfg_data = yaml.safe_load(f)
        personas_cfg = cfg_data.get("personas", {})
        skill_mag_cfg = cfg_data.get("skill_magnitude", {})
        for p in profiles:
            persona = personas_cfg.get(p.cluster, {})
            p.persona_scale = persona.get("persona_scale", 1.0) or 1.0
            p.skill_magnitude = dict(skill_mag_cfg)
            p.magnitude_default = persona.get("magnitude_default", 10) or 10
            p.magnitude_sigma = persona.get("magnitude_sigma", 0.0) or 0.0
            p.magnitude_min = persona.get("magnitude_min", 1.0) or 1.0
            p.magnitude_max = persona.get("magnitude_max", 30.0) or 30.0
            p.exploration_rate = persona.get("exploration_rate", 0.0) or 0.0

    # Create environment
    config = WaterSystemConfig(seed=seed)
    env = IrrigationEnvironment(config)
    env.initialize_from_profiles(profiles)

    # Load CRSS precipitation if available
    if args.real:
        precip_csv = ref_dir / "CRSS_DB" / "CRSS_DB" / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
        if precip_csv.exists():
            env.load_crss_precipitation(str(precip_csv))
            print("[Data] Loaded real CRSS precipitation projections (2017-2060)")

    # Create FQL agents
    fql_agents = create_fql_agents(profiles, seed=seed)

    # Output directory — per-seed subdirectory under fql_raw/
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = base / "results" / "fql_raw" / f"seed{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Profile dict for fast lookup
    profiles_dict = {p.agent_id: p for p in profiles}

    # Run
    n_real = "real" if args.real else "synthetic"
    gov_mode = "NO governance" if args.no_governance else "WITH governance"
    print(
        f"\n--- FQL Baseline ({gov_mode}) | {len(profiles)} agents ({n_real}) "
        f"| {args.years} years | seed={seed} ---\n"
    )

    logs = run_simulation(
        env=env,
        fql_agents=fql_agents,
        profiles=profiles_dict,
        n_years=args.years,
        output_dir=output_dir,
        seed=seed,
        no_governance=args.no_governance,
    )

    # Save simulation log
    if logs:
        df = pd.DataFrame(logs)
        csv_path = output_dir / "simulation_log.csv"
        df.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"\n[Output] Saved {len(logs)} rows to {csv_path}")

        # Quick summary stats
        n_agents = df["agent_id"].nunique()
        n_years = df["year"].nunique()
        skill_dist = df["yearly_decision"].value_counts()
        block_rate = df["fql_blocked"].mean() * 100
        final_mead = df[df["year"] == df["year"].max()]["lake_mead_level"].iloc[0]
        mean_util = df["utilisation_pct"].mean()
        demand_ratio = (df["request"] / df["water_right"]).mean()

        print(f"\n--- Summary ---")
        print(f"  Agents: {n_agents}, Years: {n_years}")
        print(f"  Block rate: {block_rate:.1f}%")
        print(f"  Final Mead level: {final_mead:.1f} ft")
        print(f"  Mean utilisation: {mean_util:.1f}%")
        print(f"  Mean demand ratio: {demand_ratio:.3f}")
        print(f"  Skill distribution:")
        for skill, count in skill_dist.items():
            print(f"    {skill}: {count} ({count/len(df)*100:.1f}%)")

    print(f"\n--- FQL Baseline Complete! Results in {output_dir} ---")


def parse_args():
    p = argparse.ArgumentParser(
        description="FQL Baseline Runner — Hung & Yang (2021) for Nature Water comparison"
    )
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--agents", type=int, default=5,
                   help="Number of synthetic agents (ignored if --real)")
    p.add_argument("--real", action="store_true",
                   help="Use real 78-agent CRSS data from paper")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--rebalance-clusters", action="store_true",
                   help="Rebalance cluster assignment to 50%%-30%%-20%%")
    p.add_argument("--no-governance", action="store_true",
                   help="Skip all governance validators (raw FQL behavior)")
    return p.parse_args()


if __name__ == "__main__":
    main()
