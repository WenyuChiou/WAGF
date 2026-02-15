#!/usr/bin/env python3
"""
Ungoverned Irrigation ABM — Baseline for Nature Water governance ablation.

Identical to run_experiment.py EXCEPT:
  - Governance profile = "disabled" (no YAML thinking/identity rules)
  - Custom validators = [] (no irrigation physical/social/behavioral checks)
  - No consecutive tracker updates (no Phase C/D validators)
  - Output directory auto-prefixed with "ungoverned_"

Design rationale (Option 3 from experiment gap analysis):
  LLM freely picks any skill → magnitude still Gaussian-sampled (same as
  governed) → update_agent_request() clamps to [0, water_right] → physical
  bounds maintained without governance intervention.

  The ONLY difference vs governed runs is which SKILL gets executed.
  Raw LLM skill proposals are logged in governance audit for post-hoc IBR.

Usage:
    python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 42
    python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 43
    python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 44
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

# Reuse ALL shared components from the governed experiment
from examples.irrigation_abm.run_experiment import (
    _profiles_to_agents,
    _create_synthetic_profiles,
    IrrigationLifecycleHooks,
    IRRIGATION_SKILLS,
)
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (
    build_narrative_persona,
    build_water_situation_text,
    build_conservation_status,
    build_aca_hint,
    build_trust_text,
    build_action_outcome_feedback,
)
from broker.core.experiment import ExperimentBuilder
from broker.components.memory.engine import HumanCentricMemoryEngine
from broker.components.cognitive.reflection import ReflectionEngine
from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
from broker.components.governance.registry import SkillRegistry
from broker.components.context.builder import TieredContextBuilder
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor


class UngovernedLifecycleHooks(IrrigationLifecycleHooks):
    """Lifecycle hooks for ungoverned runs — skips consecutive tracker."""

    def post_step(self, agent, result):
        """Record decision but do NOT update consecutive tracker."""
        year = getattr(self.runner, '_current_year', self.env.current_year)
        skill_name = None
        appraisals = {}

        if result and result.skill_proposal and result.skill_proposal.reasoning:
            r = result.skill_proposal.reasoning
            appraisals["wsa_label"] = next(
                (r[k] for k in ["WSA_LABEL", "water_scarcity_assessment",
                                "water_scarcity"] if k in r),
                "N/A",
            )
            appraisals["aca_label"] = next(
                (r[k] for k in ["ACA_LABEL", "adaptive_capacity_assessment",
                                "adaptive_capacity"] if k in r),
                "N/A",
            )

        if result and result.approved_skill:
            skill_name = result.approved_skill.skill_name
            exec_result = result.execution_result
            state_changes = exec_result.state_changes if exec_result else {}
            appraisals["magnitude_pct"] = state_changes.get("magnitude_pct_applied")
            appraisals["is_exploration"] = state_changes.get("is_exploration", False)
            params = result.approved_skill.parameters or {}
            appraisals["magnitude_fallback"] = params.get("magnitude_fallback", False)

        self.yearly_decisions[(agent.id, year)] = {
            "skill": skill_name,
            "appraisals": appraisals,
        }
        # NOTE: No update_consecutive_tracker() — ungoverned has no Phase C/D


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
        from examples.irrigation_abm.irrigation_personas import create_profiles_from_data
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

    # --- Set persona-specific magnitude parameters from config ---
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

    # --- Create environment and initialize ---
    config = WaterSystemConfig(seed=seed)
    env = IrrigationEnvironment(config)
    env.initialize_from_profiles(profiles)

    if args.real:
        precip_csv = ref_dir / "CRSS_DB" / "CRSS_DB" / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
        if precip_csv.exists():
            env.load_crss_precipitation(str(precip_csv))
            print(f"[Data] Loaded real CRSS precipitation projections (2017-2060)")

    # --- Convert profiles → BaseAgent instances ---
    agents = _profiles_to_agents(profiles)

    # --- Memory engine (same as governed) ---
    irr_cfg = cfg_data.get("irrigation_farmer", {})
    irr_mem = irr_cfg.get("memory", {})
    gm = global_cfg.get("memory", {})
    rw = irr_mem.get("retrieval_weights", {})

    irrigation_adapter = IrrigationAdapter()
    adapter_rw = irrigation_adapter.retrieval_weights

    memory_engine = HumanCentricMemoryEngine(
        window_size=args.window_size,
        top_k_significant=gm.get("top_k_significant", 2),
        consolidation_prob=gm.get("consolidation_probability", 0.7),
        consolidation_threshold=gm.get("consolidation_threshold", 0.6),
        decay_rate=gm.get("decay_rate", 0.1),
        emotional_weights=irr_mem.get("emotional_weights"),
        source_weights=irr_mem.get("source_weights"),
        W_recency=rw.get("recency", adapter_rw.get("W_recency", 0.3)),
        W_importance=rw.get("importance", adapter_rw.get("W_importance", 0.4)),
        W_context=rw.get("context", adapter_rw.get("W_context", 0.3)),
        ranking_mode=irr_mem.get("ranking_mode", "weighted"),
        seed=args.memory_seed,
    )
    print(f"[Memory] HumanCentricMemoryEngine (window={args.window_size})")

    # --- Context builder ---
    ctx_builder = TieredContextBuilder(
        agents=agents,
        hub=None,
        skill_registry=registry,
        prompt_templates={
            "irrigation_farmer": prompt_template,
            "default": prompt_template,
        },
        yaml_path=str(agent_config_path),
        memory_engine=memory_engine,
    )

    # --- Feedback dashboard ---
    feedback_cfg = irr_cfg.get("feedback", {})
    _metrics_tracker = None
    if feedback_cfg.get("tracked_metrics"):
        from broker.components.analytics.feedback import (
            AgentMetricsTracker,
            FeedbackDashboardProvider,
        )
        metric_names = [m["name"] for m in feedback_cfg["tracked_metrics"]]
        _metrics_tracker = AgentMetricsTracker(
            metric_names, window=feedback_cfg.get("trend_window", 5)
        )
        ctx_builder.providers.append(
            FeedbackDashboardProvider(_metrics_tracker, feedback_cfg)
        )

    # --- Output directory (isolated from governed results) ---
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = base / "results" / f"ungoverned_v20_42yr_seed{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Performance tuning ---
    from broker.utils.performance_tuner import get_optimal_config, apply_to_llm_config
    perf = get_optimal_config(args.model)
    apply_to_llm_config(perf, num_ctx_override=args.num_ctx, num_predict_override=args.num_predict)

    # ═══════════════════════════════════════════════════════════════════
    # KEY DIFFERENCE: governance="disabled" + NO custom validators
    # ═══════════════════════════════════════════════════════════════════
    builder = (
        ExperimentBuilder()
        .with_model(args.model)
        .with_years(args.years)
        .with_agents(agents)
        .with_simulation(env)
        .with_context_builder(ctx_builder)
        .with_skill_registry(registry)
        .with_memory_engine(memory_engine)
        .with_governance("disabled", str(agent_config_path))  # No YAML rules
        .with_custom_validators([])                            # No irrigation validators
        .with_exact_output(str(output_dir))
        .with_workers(args.workers)
        .with_seed(seed)
    )
    runner = builder.build()

    # --- Reflection engine (same as governed) ---
    refl_cfg = global_cfg.get("reflection", {})
    reflection_engine = ReflectionEngine(
        reflection_interval=refl_cfg.get("interval", 1),
        max_insights_per_reflection=2,
        insight_importance_boost=refl_cfg.get("importance_boost", 0.9),
        output_path=str(output_dir / "reflection_log.jsonl"),
        adapter=irrigation_adapter,
    )

    # --- Inject lifecycle hooks (ungoverned variant) ---
    hooks = UngovernedLifecycleHooks(env, runner, profiles, reflection_engine, output_dir)
    hooks.metrics_tracker = _metrics_tracker
    hooks.feedback_config = feedback_cfg
    runner.hooks.update({
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year,
    })

    # --- Run ---
    n_real = "real" if args.real else "synthetic"
    print(
        f"--- UNGOVERNED Irrigation ABM | {args.model} | {len(profiles)} agents ({n_real}) "
        f"| {args.years} years | seed={seed} ---"
    )
    print(f"--- Governance: DISABLED | Custom validators: NONE ---")
    runner.run(llm_invoke=create_llm_invoke(args.model, verbose=False))

    # Finalize audit
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save simulation log
    if hooks.logs:
        sanitized_logs = []
        for log in hooks.logs:
            sanitized_log = {
                k: (v.replace('\n', ' ').replace('\r', ' ').strip() if isinstance(v, str) else v)
                for k, v in log.items()
            }
            sanitized_logs.append(sanitized_log)
        pd.DataFrame(sanitized_logs).to_csv(output_dir / "simulation_log.csv", index=False)

    GovernanceAuditor().print_summary()
    print(f"--- Complete! Ungoverned results in {output_dir} ---")


def parse_args():
    p = argparse.ArgumentParser(
        description="UNGOVERNED Irrigation ABM — Governance ablation baseline"
    )
    p.add_argument("--model", default="gemma3:4b")
    p.add_argument("--years", type=int, default=42)
    p.add_argument("--agents", type=int, default=5, help="Synthetic agents (ignored with --real)")
    p.add_argument("--real", action="store_true", help="Use real 78-agent CRSS data")
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
