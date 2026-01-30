#!/usr/bin/env python3
"""
Irrigation ABM Experiment Runner — Hung & Yang (2021) LLM Adaptation.

Single production pipeline using the Governed Broker Framework (GBF):
  Pillar 1 — Strict Governance  (water rights, curtailment, magnitude caps)
  Pillar 2 — Cognitive Memory   (HumanCentric engine + year-end reflection)
  Pillar 3 — Priority Schema    (important attributes enter context first)

Usage:
    python run_experiment.py                                        # defaults: gemma3:1b, 5yr, synthetic
    python run_experiment.py --model gemma3:4b --years 42 --real    # 78 CRSS agents, 42 years
    python run_experiment.py --model gemma3:4b --years 10 --agents 10  # 10 synthetic agents

References:
    Hung, F., & Yang, Y. C. E. (2021). WRR, 57, e2020WR029262.
"""
from __future__ import annotations

import argparse
import random
import sys
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_governance.agents import BaseAgent, AgentConfig
from cognitive_governance.simulation.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    build_narrative_persona,
    build_water_situation_text,
    build_conservation_status,
    build_trust_text,
    build_regret_feedback,
    create_profiles_from_csv,
)
from broker.core.experiment import ExperimentBuilder
from broker.components.memory_engine import HumanCentricMemoryEngine
from broker.components.reflection_engine import ReflectionEngine
from broker.components.skill_registry import SkillRegistry
from broker.components.context_builder import TieredContextBuilder
from broker.interfaces.skill_types import ExecutionResult
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor
from broker.validators.governance.irrigation_validators import (
    irrigation_governance_validator,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IRRIGATION_SKILLS = [
    "increase_demand", "decrease_demand", "adopt_efficiency",
    "reduce_acreage", "maintain_demand",
]


# ---------------------------------------------------------------------------
# Profile → BaseAgent conversion
# ---------------------------------------------------------------------------
def _profiles_to_agents(
    profiles: List[IrrigationAgentProfile],
) -> Dict[str, BaseAgent]:
    """Convert IrrigationAgentProfile list to BaseAgent dict for ExperimentBuilder."""
    agents: Dict[str, BaseAgent] = {}
    for p in profiles:
        config = AgentConfig(
            name=p.agent_id,
            agent_type="irrigation_farmer",
            state_params=[],
            objectives=[],
            constraints=[],
            skills=IRRIGATION_SKILLS,
        )
        agent = BaseAgent(config)

        # Set custom attributes used by context builder and prompt template
        attrs = {
            "narrative_persona": p.narrative_persona,
            "basin": p.basin,
            "cluster": p.cluster,
            "water_right": p.water_right,
            "farm_size_acres": p.farm_size_acres,
            "crop_type": p.crop_type,
            "years_farming": p.years_farming,
            "has_efficient_system": p.has_efficient_system,
            "at_allocation_cap": False,
        }
        agent.custom_attributes = attrs
        for k, v in attrs.items():
            setattr(agent, k, v)

        agents[p.agent_id] = agent
    return agents


# ---------------------------------------------------------------------------
# Synthetic profile builder (for quick testing without CRSS data)
# ---------------------------------------------------------------------------
def _create_synthetic_profiles(
    n_agents: int,
    seed: int = 42,
) -> List[IrrigationAgentProfile]:
    """Create synthetic agent profiles with balanced cluster distribution."""
    from cognitive_governance.learning.fql import (
        CLUSTER_AGGRESSIVE,
        CLUSTER_FORWARD_LOOKING,
        CLUSTER_MYOPIC,
    )

    rng = np.random.default_rng(seed)
    clusters = ["aggressive", "forward_looking_conservative", "myopic_conservative"]
    ref_configs = {
        "aggressive": CLUSTER_AGGRESSIVE,
        "forward_looking_conservative": CLUSTER_FORWARD_LOOKING,
        "myopic_conservative": CLUSTER_MYOPIC,
    }

    profiles = []
    for i in range(n_agents):
        basin = "upper_basin" if i < n_agents // 3 else "lower_basin"
        cluster = clusters[i % 3]
        ref = ref_configs[cluster]

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


# ---------------------------------------------------------------------------
# Lifecycle Hooks
# ---------------------------------------------------------------------------
class IrrigationLifecycleHooks:
    """Hooks that wire water state, memory injection, and reflection."""

    def __init__(
        self,
        env: IrrigationEnvironment,
        runner,  # ExperimentRunner (set after build)
        profiles: List[IrrigationAgentProfile],
        reflection_engine: Optional[ReflectionEngine],
        output_dir: Path,
    ):
        self.env = env
        self.runner = runner
        self.profiles = {p.agent_id: p for p in profiles}
        self.reflection_engine = reflection_engine
        self.output_dir = output_dir
        self.logs: List[Dict] = []
        self.yearly_decisions: Dict = {}

    # -- pre_year: inject water situation context and regret feedback --
    def pre_year(self, year: int, env_state: Dict, agents: Dict):
        for aid, agent in agents.items():
            if not getattr(agent, "is_active", True):
                continue

            ctx = self.env.get_agent_context(aid)
            profile = self.profiles.get(aid)
            if profile is None:
                continue

            # Build dynamic context attributes for prompt template
            water_situation = build_water_situation_text(ctx)
            trust = build_trust_text(profile.cluster)
            conservation = build_conservation_status(profile)

            agent.water_situation_text = water_situation
            agent.conservation_status = conservation
            agent.trust_forecasts_text = trust["trust_forecasts_text"]
            agent.trust_neighbors_text = trust["trust_neighbors_text"]

            # Sync physical state flags from environment → agent
            agent_state = self.env.get_agent_state(aid)
            agent.at_allocation_cap = agent_state.get("at_allocation_cap", False)
            agent.has_efficient_system = agent_state.get("has_efficient_system", False)

            # Inject regret feedback from last year's outcome into memory
            if year > 1:
                prev_request = agent_state.get("request", 0)
                prev_diversion = agent_state.get("diversion", 0)
                feedback = build_regret_feedback(
                    year=year - 1,
                    request=prev_request,
                    diversion=prev_diversion,
                    drought_index=ctx.get("drought_index", 0),
                    preceding_factor=ctx.get("preceding_factor", 0),
                )
                self.runner.memory_engine.add_memory(aid, feedback)

    # -- post_step: record each agent's decision --
    def post_step(self, agent, result):
        year = self.env.current_year
        skill_name = None
        appraisals = {}

        if result and result.skill_proposal and result.skill_proposal.reasoning:
            r = result.skill_proposal.reasoning
            appraisals["wta_label"] = next(
                (r[k] for k in ["WTA_LABEL", "water_threat_appraisal", "water_threat"] if k in r),
                "N/A",
            )
            appraisals["wca_label"] = next(
                (r[k] for k in ["WCA_LABEL", "water_coping_appraisal", "water_coping"] if k in r),
                "N/A",
            )

        if result and result.approved_skill:
            skill_name = result.approved_skill.skill_name

        self.yearly_decisions[(agent.id, year)] = {
            "skill": skill_name,
            "appraisals": appraisals,
        }

    # -- post_year: logging, reflection --
    def post_year(self, year: int, agents: Dict):
        for aid, agent in agents.items():
            agent_state = self.env.get_agent_state(aid)
            dec = self.yearly_decisions.get((aid, year), {})
            skill = dec.get("skill") if isinstance(dec, dict) else dec
            appr = dec.get("appraisals", {}) if isinstance(dec, dict) else {}

            # Retrieve memory for logging
            mem_items = self.runner.memory_engine.retrieve(agent, top_k=5)
            mem_str = " | ".join(mem_items) if isinstance(mem_items, list) else str(mem_items)

            profile = self.profiles.get(aid)
            self.logs.append({
                "agent_id": aid,
                "year": year,
                "cluster": profile.cluster if profile else "unknown",
                "basin": profile.basin if profile else "unknown",
                "yearly_decision": skill or "N/A",
                "wta_label": appr.get("wta_label", "N/A"),
                "wca_label": appr.get("wca_label", "N/A"),
                "request": agent_state.get("request", 0),
                "diversion": agent_state.get("diversion", 0),
                "water_right": agent_state.get("water_right", 0),
                "curtailment_ratio": agent_state.get("curtailment_ratio", 0),
                "drought_index": self.env._drought_index,
                "shortage_tier": self.env._shortage_tier,
                "has_efficient_system": agent_state.get("has_efficient_system", False),
                "memory": mem_str,
            })

        # Print yearly summary
        n_agents = len(agents)
        decisions = [
            self.yearly_decisions.get((aid, year), {}).get("skill", "N/A")
            for aid in agents
        ]
        from collections import Counter
        counts = Counter(decisions)
        summary = " | ".join(f"{k}: {v}" for k, v in counts.most_common())
        print(f"[Year {year}] {summary} (drought={self.env._drought_index:.2f})")

        # Batch year-end reflection
        if self.reflection_engine and self.reflection_engine.should_reflect("any", year):
            self._batch_reflect(year)

    def _batch_reflect(self, year: int):
        cfg = self.runner.broker.config.get_reflection_config()
        batch_size = cfg.get("batch_size", 10)
        candidates = []
        for aid, agent in self.runner.agents.items():
            if not getattr(agent, "is_active", True):
                continue
            mems = self.runner.memory_engine.retrieve(agent, top_k=10)
            if mems:
                candidates.append({"agent_id": aid, "memories": mems})

        if not candidates:
            return

        llm_call = self.runner.get_llm_invoke("irrigation_farmer")
        print(f"  [Reflection] {len(candidates)} agents in batches of {batch_size}...")
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i: i + batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(batch, year)
            try:
                raw = llm_call(prompt)
                text = raw[0] if isinstance(raw, tuple) else raw
                insights = self.reflection_engine.parse_batch_reflection_response(
                    text, batch_ids, year
                )
                for aid, insight in insights.items():
                    if insight:
                        self.reflection_engine.store_insight(aid, insight)
                        self.runner.memory_engine.add_memory(
                            aid,
                            f"Consolidated Reflection: {insight.summary}",
                            {"significance": 0.9, "emotion": "major", "source": "personal"},
                        )
            except Exception as e:
                print(f"  [Reflection:Error] Batch {i // batch_size + 1}: {e}")
        print(f"  [Reflection] Year {year} complete.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    args = parse_args()
    base = Path(__file__).parent
    config_dir = base / "config"
    ref_dir = PROJECT_ROOT / "ref"

    # --- Random seed ---
    seed = args.seed if args.seed is not None else random.randint(0, 1_000_000)
    random.seed(seed)
    np.random.seed(seed)

    # --- LLM config overrides ---
    from broker.utils.llm_utils import LLM_CONFIG
    if args.num_ctx:
        LLM_CONFIG.num_ctx = args.num_ctx
    if args.num_predict:
        LLM_CONFIG.num_predict = args.num_predict

    # --- Load config YAML ---
    agent_config_path = config_dir / "agent_types.yaml"
    with open(agent_config_path, "r", encoding="utf-8") as f:
        cfg_data = yaml.safe_load(f)
    global_cfg = cfg_data.get("global_config", {})

    # --- Load prompt template ---
    prompt_template_path = config_dir / "prompts" / "irrigation_farmer.txt"
    prompt_template = prompt_template_path.read_text(encoding="utf-8")

    # --- Load skill registry ---
    registry = SkillRegistry()
    registry.register_from_yaml(str(config_dir / "skill_registry.yaml"))

    # --- Create agent profiles ---
    if args.real:
        # Real 78-agent CRSS data
        from examples.irrigation_abm.irrigation_personas import (
            create_profiles_from_data,
        )
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

    # --- Create environment and initialize ---
    config = WaterSystemConfig(seed=seed)
    env = IrrigationEnvironment(config)
    env.initialize_from_profiles(profiles)

    # --- Convert profiles → BaseAgent instances ---
    agents = _profiles_to_agents(profiles)

    # --- Context builder ---
    ctx_builder = TieredContextBuilder(
        agents=agents,
        hub=None,  # No social graph for irrigation
        skill_registry=registry,
        prompt_templates={
            "irrigation_farmer": prompt_template,
            "default": prompt_template,
        },
        yaml_path=str(agent_config_path),
    )

    # --- Memory engine (Pillar 2) ---
    irr_cfg = cfg_data.get("irrigation_farmer", {})
    irr_mem = irr_cfg.get("memory", {})
    gm = global_cfg.get("memory", {})
    rw = irr_mem.get("retrieval_weights", {})

    memory_engine = HumanCentricMemoryEngine(
        window_size=args.window_size,
        top_k_significant=gm.get("top_k_significant", 2),
        consolidation_prob=gm.get("consolidation_probability", 0.7),
        consolidation_threshold=gm.get("consolidation_threshold", 0.6),
        decay_rate=gm.get("decay_rate", 0.1),
        emotional_weights=irr_mem.get("emotional_weights"),
        source_weights=irr_mem.get("source_weights"),
        W_recency=rw.get("recency", 0.3),
        W_importance=rw.get("importance", 0.5),
        W_context=rw.get("context", 0.2),
        ranking_mode="legacy",
        seed=args.memory_seed,
    )
    print(f"[Pillar 2] HumanCentricMemoryEngine (window={args.window_size})")

    # --- Output ---
    output_dir = Path(args.output) if args.output else base / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Performance tuning ---
    from broker.utils.performance_tuner import get_optimal_config, apply_to_llm_config
    perf = get_optimal_config(args.model)
    apply_to_llm_config(perf, num_ctx_override=args.num_ctx, num_predict_override=args.num_predict)

    # --- Build experiment ---
    builder = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(env)
        .with_context_builder(ctx_builder)
        .with_skill_registry(registry)
        .with_memory_engine(memory_engine)
        .with_governance("strict", str(agent_config_path))
        .with_custom_validators([irrigation_governance_validator])
        .with_exact_output(str(output_dir))
        .with_workers(args.workers)
        .with_seed(seed)
    )
    runner = builder.build()

    # --- Reflection engine (Pillar 2) ---
    refl_cfg = global_cfg.get("reflection", {})
    reflection_engine = ReflectionEngine(
        reflection_interval=refl_cfg.get("interval", 1),
        max_insights_per_reflection=2,
        insight_importance_boost=refl_cfg.get("importance_boost", 0.9),
        output_path=str(output_dir / "reflection_log.jsonl"),
    )
    print(f"[Pillar 2] ReflectionEngine (interval={reflection_engine.reflection_interval})")

    # --- Inject lifecycle hooks ---
    hooks = IrrigationLifecycleHooks(env, runner, profiles, reflection_engine, output_dir)
    runner.hooks = {
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year,
    }

    # --- Run ---
    n_real = "real" if args.real else "synthetic"
    print(
        f"--- Irrigation ABM | {args.model} | {len(profiles)} agents ({n_real}) "
        f"| {args.years} years | seed={seed} ---"
    )
    runner.run(llm_invoke=create_llm_invoke(args.model, verbose=False))

    # Finalize audit
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save simulation log
    if hooks.logs:
        pd.DataFrame(hooks.logs).to_csv(output_dir / "simulation_log.csv", index=False)

    GovernanceAuditor().print_summary()
    print(f"--- Complete! Results in {output_dir} ---")


def parse_args():
    p = argparse.ArgumentParser(
        description="Irrigation ABM Experiment (Hung 2021 — GBF Pipeline)"
    )
    p.add_argument("--model", default="gemma3:1b")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--agents", type=int, default=5, help="Number of synthetic agents (ignored if --real)")
    p.add_argument("--real", action="store_true", help="Use real 78-agent CRSS data from paper")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--memory-seed", type=int, default=42)
    p.add_argument("--window-size", type=int, default=5)
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--num-ctx", type=int, default=None)
    p.add_argument("--num-predict", type=int, default=None)
    return p.parse_args()


if __name__ == "__main__":
    main()
