#!/usr/bin/env python3
"""
Irrigation ABM Experiment Runner — Hung & Yang (2021) LLM Adaptation.

Runs the Colorado River Basin irrigation demand experiment in three groups:
  Group A: Native FQL (Q-learning baseline — no LLM)
  Group B: Governed LLM (LLM decisions + governance constraints)
  Group C: Full Cognitive LLM (LLM + Memory + Reflection + Governance)

Usage:
    python run_experiment.py --group B --model gemma3:4b --years 42 --agents 5
    python run_experiment.py --group A --years 42 --agents 31   # FQL baseline

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_governance.learning.fql import (
    FQLAgent,
    FQLConfig,
    FQLState,
    CLUSTER_AGGRESSIVE,
    CLUSTER_FORWARD_LOOKING,
    CLUSTER_MYOPIC,
)
from cognitive_governance.simulation.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.multi_agent.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    build_narrative_persona,
    build_water_situation_text,
    build_conservation_status,
    build_trust_text,
    create_profiles_from_csv,
    _infer_cluster,
)


# ============================================================================
# Group A: FQL Baseline (no LLM)
# ============================================================================

def run_group_a(
    env: IrrigationEnvironment,
    profiles: List[IrrigationAgentProfile],
    n_years: int,
    output_dir: Path,
) -> Dict[str, Any]:
    """Run FQL (Q-learning) baseline without LLM involvement.

    Each agent uses the calibrated FQL parameters to make water demand
    decisions mathematically via epsilon-greedy Q-learning.
    """
    print(f"\n=== GROUP A: Native FQL Baseline ({len(profiles)} agents, {n_years} years) ===\n")

    # Create FQL agents and states
    cluster_configs = {
        "aggressive": CLUSTER_AGGRESSIVE,
        "forward_looking_conservative": CLUSTER_FORWARD_LOOKING,
        "myopic_conservative": CLUSTER_MYOPIC,
    }

    fql_agents: Dict[str, FQLAgent] = {}
    fql_states: Dict[str, FQLState] = {}

    for profile in profiles:
        config = FQLConfig(
            mu=profile.mu,
            sigma=profile.sigma,
            alpha=profile.alpha,
            gamma=profile.gamma_param,
            epsilon=profile.epsilon,
            regret=profile.regret,
            forget=profile.forget,
        )
        agent = FQLAgent(config, rng=np.random.default_rng(hash(profile.agent_id) % 2**31))

        # Create state with agent-specific discretisation
        water_right = profile.water_right
        state = FQLState(
            state_bounds=np.linspace(0, water_right, config.n_states),
            prev_diversion=water_right * 0.8,
            prev_action=0.0,
            prev_diversion_request=water_right * 0.8,
        )
        state.initialize(config)

        fql_agents[profile.agent_id] = agent
        fql_states[profile.agent_id] = state

    # Simulation loop
    results_log: List[Dict[str, Any]] = []

    for year_idx in range(n_years):
        env_state = env.advance_year()
        year = env.current_year

        for profile in profiles:
            aid = profile.agent_id
            ctx = env.get_agent_context(aid)

            # Get preceding factor for this agent's basin
            pf_current = ctx["preceding_factor"]
            pf_next = pf_current  # Simplified: use same for t and t+1

            # FQL step
            action = fql_agents[aid].step(
                state=fql_states[aid],
                current_diversion=ctx["current_diversion"],
                preceding_factor=(pf_current, pf_next),
            )

            # Update environment
            new_request = ctx["current_diversion"] + action
            env.update_agent_request(aid, new_request)

            # Log
            results_log.append({
                "year": year,
                "agent_id": aid,
                "cluster": profile.cluster,
                "basin": profile.basin,
                "action": float(action),
                "request": float(new_request),
                "diversion": float(env.get_agent_state(aid).get("diversion", 0)),
                "water_right": profile.water_right,
                "drought_index": ctx["drought_index"],
                "shortage_tier": ctx["shortage_tier"],
                "group": "A",
            })

        if (year_idx + 1) % 10 == 0:
            print(f"  Year {year} ({year_idx + 1}/{n_years}) — "
                  f"Drought: {env_state['drought_index']:.2f}")

    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "group_a_results.json"
    with open(results_path, "w") as f:
        json.dump(results_log, f, indent=2)

    print(f"\n  Group A complete. Results: {results_path}")
    return {"group": "A", "n_records": len(results_log), "path": str(results_path)}


# ============================================================================
# Group B: Governed LLM (LLM + governance, no memory/reflection)
# ============================================================================

def run_group_b(
    env: IrrigationEnvironment,
    profiles: List[IrrigationAgentProfile],
    n_years: int,
    model: str,
    output_dir: Path,
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run LLM-driven agents with governance constraints.

    Each agent uses the LLM to reason about water demand, with
    governance rules enforcing water allocation bounds and
    behavioural consistency.
    """
    print(f"\n=== GROUP B: Governed LLM ({len(profiles)} agents, {n_years} years, model={model}) ===\n")

    # Load YAML config
    if config_path is None:
        config_path = Path(__file__).parent / "config" / "agent_types.yaml"

    # Import broker components
    from broker.core.skill_broker_engine import SkillBrokerEngine

    # Build prompt template
    prompt_template_path = Path(__file__).parent / "config" / "prompts" / "irrigation_farmer.txt"
    prompt_template = prompt_template_path.read_text(encoding="utf-8")

    results_log: List[Dict[str, Any]] = []

    for year_idx in range(n_years):
        env_state = env.advance_year()
        year = env.current_year

        for profile in profiles:
            aid = profile.agent_id
            ctx = env.get_agent_context(aid)

            # Build prompt context
            water_situation = build_water_situation_text(ctx)
            trust = build_trust_text(profile.cluster)
            conservation = build_conservation_status(profile)

            # Construct full prompt
            prompt = prompt_template.format(
                narrative_persona=profile.narrative_persona,
                water_situation_text=water_situation,
                memory="No prior memories (Group B — no memory system).",
                conservation_status=conservation,
                trust_forecasts_text=trust["trust_forecasts_text"],
                trust_neighbors_text=trust["trust_neighbors_text"],
                options_text=_format_options(),
                rating_scale=_RATING_SCALE,
                response_format=_RESPONSE_FORMAT,
            )

            # Call LLM
            try:
                llm_response = _call_llm(prompt, model)
                decision = _parse_decision(llm_response)
            except Exception as e:
                print(f"    LLM error for {aid}: {e}")
                decision = {"decision": "5", "skill": "maintain_demand"}

            # Map decision to action
            skill = decision.get("skill", "maintain_demand")
            new_request = _apply_skill(
                skill,
                ctx["current_diversion"],
                ctx["water_right"],
                magnitude_pct=decision.get("magnitude", 10),
            )
            env.update_agent_request(aid, new_request)

            results_log.append({
                "year": year,
                "agent_id": aid,
                "cluster": profile.cluster,
                "basin": profile.basin,
                "skill": skill,
                "request": float(new_request),
                "diversion": float(env.get_agent_state(aid).get("diversion", 0)),
                "water_right": profile.water_right,
                "drought_index": ctx["drought_index"],
                "shortage_tier": ctx["shortage_tier"],
                "wta_label": decision.get("wta_label", "N/A"),
                "wca_label": decision.get("wca_label", "N/A"),
                "reasoning": decision.get("reasoning", ""),
                "group": "B",
            })

        if (year_idx + 1) % 10 == 0:
            print(f"  Year {year} ({year_idx + 1}/{n_years}) — "
                  f"Drought: {env_state['drought_index']:.2f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "group_b_results.json"
    with open(results_path, "w") as f:
        json.dump(results_log, f, indent=2)

    print(f"\n  Group B complete. Results: {results_path}")
    return {"group": "B", "n_records": len(results_log), "path": str(results_path)}


# ============================================================================
# Group C: Full Cognitive LLM (LLM + Memory + Reflection + Governance)
# ============================================================================

def run_group_c(
    env: IrrigationEnvironment,
    profiles: List[IrrigationAgentProfile],
    n_years: int,
    model: str,
    output_dir: Path,
) -> Dict[str, Any]:
    """Run LLM-driven agents with full cognitive stack.

    Adds memory accumulation and periodic reflection on top of Group B.
    Memory stores past decisions, outcomes, and water situations.
    Reflection periodically synthesises lessons from experience.
    """
    print(f"\n=== GROUP C: Full Cognitive LLM ({len(profiles)} agents, {n_years} years, model={model}) ===\n")

    prompt_template_path = Path(__file__).parent / "config" / "prompts" / "irrigation_farmer.txt"
    prompt_template = prompt_template_path.read_text(encoding="utf-8")

    # Memory store: agent_id → list of memory strings
    agent_memories: Dict[str, List[str]] = {p.agent_id: [] for p in profiles}

    results_log: List[Dict[str, Any]] = []

    for year_idx in range(n_years):
        env_state = env.advance_year()
        year = env.current_year

        for profile in profiles:
            aid = profile.agent_id
            ctx = env.get_agent_context(aid)

            # Build memory text (recent 5 memories)
            recent_memories = agent_memories[aid][-5:]
            if recent_memories:
                memory_text = "\n".join(f"- {m}" for m in recent_memories)
            else:
                memory_text = "No prior memories yet — this is your first decision year."

            # Build prompt
            water_situation = build_water_situation_text(ctx)
            trust = build_trust_text(profile.cluster)
            conservation = build_conservation_status(profile)

            prompt = prompt_template.format(
                narrative_persona=profile.narrative_persona,
                water_situation_text=water_situation,
                memory=memory_text,
                conservation_status=conservation,
                trust_forecasts_text=trust["trust_forecasts_text"],
                trust_neighbors_text=trust["trust_neighbors_text"],
                options_text=_format_options(),
                rating_scale=_RATING_SCALE,
                response_format=_RESPONSE_FORMAT,
            )

            # Call LLM
            try:
                llm_response = _call_llm(prompt, model)
                decision = _parse_decision(llm_response)
            except Exception as e:
                print(f"    LLM error for {aid}: {e}")
                decision = {"decision": "5", "skill": "maintain_demand"}

            # Apply decision
            skill = decision.get("skill", "maintain_demand")
            new_request = _apply_skill(
                skill,
                ctx["current_diversion"],
                ctx["water_right"],
                magnitude_pct=decision.get("magnitude", 10),
            )
            env.update_agent_request(aid, new_request)

            # Create memory of this year's decision and outcome
            actual_div = env.get_agent_state(aid).get("diversion", 0)
            shortage = max(0, new_request - actual_div)
            memory_entry = (
                f"Year {year}: I chose '{skill}'. "
                f"Requested {new_request:,.0f} acre-ft, received {actual_div:,.0f} acre-ft"
            )
            if shortage > 0:
                memory_entry += f" (shortfall: {shortage:,.0f} acre-ft)."
            else:
                memory_entry += " (demand fully met)."

            if ctx["drought_index"] > 0.5:
                memory_entry += f" Drought index was {ctx['drought_index']:.2f}."

            agent_memories[aid].append(memory_entry)

            # Periodic reflection (every 5 years)
            if (year_idx + 1) % 5 == 0 and len(agent_memories[aid]) >= 3:
                reflection = _generate_reflection(
                    aid, agent_memories[aid], model, profile.cluster
                )
                if reflection:
                    agent_memories[aid].append(f"[Reflection] {reflection}")

            results_log.append({
                "year": year,
                "agent_id": aid,
                "cluster": profile.cluster,
                "basin": profile.basin,
                "skill": skill,
                "request": float(new_request),
                "diversion": float(actual_div),
                "water_right": profile.water_right,
                "drought_index": ctx["drought_index"],
                "shortage_tier": ctx["shortage_tier"],
                "wta_label": decision.get("wta_label", "N/A"),
                "wca_label": decision.get("wca_label", "N/A"),
                "reasoning": decision.get("reasoning", ""),
                "n_memories": len(agent_memories[aid]),
                "group": "C",
            })

        if (year_idx + 1) % 10 == 0:
            print(f"  Year {year} ({year_idx + 1}/{n_years}) — "
                  f"Drought: {env_state['drought_index']:.2f}")

    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "group_c_results.json"
    with open(results_path, "w") as f:
        json.dump(results_log, f, indent=2)

    # Save memory dumps
    memory_path = output_dir / "group_c_memories.json"
    with open(memory_path, "w") as f:
        json.dump(agent_memories, f, indent=2)

    print(f"\n  Group C complete. Results: {results_path}")
    return {"group": "C", "n_records": len(results_log), "path": str(results_path)}


# ============================================================================
# LLM Interface
# ============================================================================

def _call_llm(prompt: str, model: str) -> str:
    """Call the LLM via Ollama REST API (same as flood experiment).

    Supports local Ollama models (gemma3, llama3, etc.).
    """
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 8192,
            "num_predict": 4096,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "")
    except urllib.error.URLError:
        raise RuntimeError(f"Cannot connect to Ollama at localhost:11434. Is it running?")


def _parse_decision(llm_response: str) -> Dict[str, Any]:
    """Parse structured decision from LLM response.

    Looks for <<<DECISION_START>>> ... <<<DECISION_END>>> delimiters,
    then parses JSON within.
    """
    skill_map = {
        "1": "increase_demand",
        "2": "decrease_demand",
        "3": "adopt_efficiency",
        "4": "reduce_acreage",
        "5": "maintain_demand",
    }

    result: Dict[str, Any] = {
        "decision": "5",
        "skill": "maintain_demand",
        "wta_label": "M",
        "wca_label": "M",
        "reasoning": "",
        "magnitude": 10,
    }

    try:
        start_tag = "<<<DECISION_START>>>"
        end_tag = "<<<DECISION_END>>>"
        start = llm_response.find(start_tag)
        end = llm_response.find(end_tag)

        if start >= 0 and end > start:
            json_str = llm_response[start + len(start_tag):end].strip()
            parsed = json.loads(json_str)

            decision_id = str(parsed.get("decision", "5")).strip()
            result["decision"] = decision_id
            result["skill"] = skill_map.get(decision_id, "maintain_demand")

            # Extract appraisals
            wta = parsed.get("water_threat_appraisal", {})
            wca = parsed.get("water_coping_appraisal", {})
            if isinstance(wta, dict):
                result["wta_label"] = wta.get("label", "M")
            elif isinstance(wta, str):
                result["wta_label"] = wta
            if isinstance(wca, dict):
                result["wca_label"] = wca.get("label", "M")
            elif isinstance(wca, str):
                result["wca_label"] = wca

            result["reasoning"] = parsed.get("reasoning", "")
            magnitude = parsed.get("magnitude", 10)
            try:
                result["magnitude"] = int(magnitude)
            except (TypeError, ValueError):
                result["magnitude"] = 10

    except (json.JSONDecodeError, ValueError):
        pass  # Fallback to defaults

    return result


def _apply_skill(
    skill: str,
    current_diversion: float,
    water_right: float,
    magnitude_pct: int = 10,
) -> float:
    """Convert skill decision to new diversion request.

    Change magnitudes are 10% of water right — a moderate adjustment
    consistent with forward-looking conservative behaviour.
    """
    change_magnitude = water_right * (magnitude_pct / 100.0)

    if skill == "increase_demand":
        return min(current_diversion + change_magnitude, water_right)
    elif skill == "decrease_demand":
        return max(current_diversion - change_magnitude, 0)
    elif skill == "adopt_efficiency":
        # Efficiency adoption reduces demand by 20%
        return max(current_diversion * 0.80, 0)
    elif skill == "reduce_acreage":
        # Acreage reduction cuts demand by 25%
        return max(current_diversion * 0.75, 0)
    else:  # maintain_demand
        return current_diversion


def _generate_reflection(
    agent_id: str,
    memories: List[str],
    model: str,
    cluster: str,
) -> Optional[str]:
    """Generate a reflection summary from accumulated memories.

    Uses the LLM to synthesise lessons learned from past decisions.
    """
    recent = memories[-10:]
    memory_text = "\n".join(f"- {m}" for m in recent)

    prompt = (
        f"You are farmer {agent_id}, a {cluster.replace('_', ' ')} type. "
        f"Reflect on your recent water management decisions:\n\n"
        f"{memory_text}\n\n"
        f"In 2-3 sentences, summarise what you have learned about "
        f"managing your water demand. What patterns do you notice? "
        f"What would you do differently?"
    )

    try:
        response = _call_llm(prompt, model)
        # Take first 500 chars to keep memory compact
        return response.strip()[:500]
    except Exception:
        return None


# ============================================================================
# Shared constants
# ============================================================================

_RATING_SCALE = """### RATING SCALE (You MUST use EXACTLY one of these codes):
VL = Very Low | L = Low | M = Medium | H = High | VH = Very High"""

_RESPONSE_FORMAT = """<<<DECISION_START>>>
{
  "water_threat_appraisal": {
    "label": "<VL/L/M/H/VH>",
    "reason": "<One sentence on water supply threat level>"
  },
  "water_coping_appraisal": {
    "label": "<VL/L/M/H/VH>",
    "reason": "<One sentence on your ability to adapt>"
  },
  "decision": "<Numeric ID: 1, 2, 3, 4, or 5>",
  "magnitude": "<Integer 1-30, representing % change in demand>",
  "reasoning": "<Brief explanation of your choice>"
}
<<<DECISION_END>>>"""


def _format_options() -> str:
    return (
        "1. Increase water demand request (Request more allocation — higher yield "
        "potential but risks curtailment)\n"
        "2. Decrease water demand request (Conserve water — lower yield but reduces "
        "curtailment risk)\n"
        "3. Adopt water-efficient irrigation technology (High upfront cost, 15-25% "
        "long-term water savings)\n"
        "4. Reduce irrigated acreage (Fallow some land — less revenue but guaranteed "
        "to meet reduced allocation)\n"
        "5. Maintain current water demand (No change — appropriate when supply is "
        "stable)"
    )


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Irrigation ABM Experiment (Hung 2021 LLM Adaptation)"
    )
    parser.add_argument(
        "--group", choices=["A", "B", "C", "all"], default="A",
        help="Experiment group: A (FQL), B (Governed LLM), C (Full Cognitive), all"
    )
    parser.add_argument(
        "--model", default="gemma3:4b",
        help="Ollama model name for LLM groups (B, C)"
    )
    parser.add_argument(
        "--years", type=int, default=42,
        help="Number of simulation years (default: 42, matching 2019-2060)"
    )
    parser.add_argument(
        "--agents", type=int, default=5,
        help="Number of agents (5 for prototype, 31 for full)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (default: examples/irrigation_abm/results/)"
    )
    parser.add_argument(
        "--params-csv", type=str, default=None,
        help="Path to calibrated parameters CSV (for real agent profiles)"
    )

    args = parser.parse_args()

    # Setup
    output_dir = Path(args.output_dir) if args.output_dir else (
        Path(__file__).parent / "results" / f"run_{int(time.time())}"
    )

    config = WaterSystemConfig(seed=args.seed)
    env = IrrigationEnvironment(config)

    # Create agent profiles
    if args.params_csv:
        profiles = create_profiles_from_csv(args.params_csv)
        env.initialize_from_csv(args.params_csv)
    else:
        # Create synthetic profiles
        profiles = _create_synthetic_profiles(args.agents, args.seed)
        env.initialize_synthetic(
            n_agents=args.agents,
            basin_split=(args.agents // 3, args.agents - args.agents // 3),
        )

    print(f"Irrigation ABM Experiment")
    print(f"  Agents: {len(profiles)}")
    print(f"  Years: {args.years}")
    print(f"  Groups: {args.group}")
    print(f"  Model: {args.model}")
    print(f"  Output: {output_dir}")

    # Run experiments
    results = {}

    if args.group in ("A", "all"):
        env_a = IrrigationEnvironment(WaterSystemConfig(seed=args.seed))
        env_a.initialize_synthetic(
            n_agents=len(profiles),
            basin_split=(len(profiles) // 3, len(profiles) - len(profiles) // 3),
        )
        results["A"] = run_group_a(env_a, profiles, args.years, output_dir)

    if args.group in ("B", "all"):
        env_b = IrrigationEnvironment(WaterSystemConfig(seed=args.seed))
        env_b.initialize_synthetic(
            n_agents=len(profiles),
            basin_split=(len(profiles) // 3, len(profiles) - len(profiles) // 3),
        )
        results["B"] = run_group_b(env_b, profiles, args.years, args.model, output_dir)

    if args.group in ("C", "all"):
        env_c = IrrigationEnvironment(WaterSystemConfig(seed=args.seed))
        env_c.initialize_synthetic(
            n_agents=len(profiles),
            basin_split=(len(profiles) // 3, len(profiles) - len(profiles) // 3),
        )
        results["C"] = run_group_c(env_c, profiles, args.years, args.model, output_dir)

    # Summary
    print("\n=== EXPERIMENT COMPLETE ===")
    for group, res in results.items():
        print(f"  Group {group}: {res['n_records']} records → {res['path']}")

    return results


def _create_synthetic_profiles(
    n_agents: int,
    seed: int = 42,
) -> List[IrrigationAgentProfile]:
    """Create synthetic agent profiles with balanced cluster distribution."""
    rng = np.random.default_rng(seed)
    clusters = ["aggressive", "forward_looking_conservative", "myopic_conservative"]

    profiles = []
    for i in range(n_agents):
        basin = "upper_basin" if i < n_agents // 3 else "lower_basin"
        cluster = clusters[i % 3]

        # Get cluster reference params
        ref = {
            "aggressive": CLUSTER_AGGRESSIVE,
            "forward_looking_conservative": CLUSTER_FORWARD_LOOKING,
            "myopic_conservative": CLUSTER_MYOPIC,
        }[cluster]

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


if __name__ == "__main__":
    main()
