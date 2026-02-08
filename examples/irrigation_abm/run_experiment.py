#!/usr/bin/env python3
"""
Irrigation ABM Experiment Runner — Hung & Yang (2021) LLM Adaptation.

Single production pipeline using the Water Agent Governance Framework (WAGF):
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
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (
    IrrigationAgentProfile,
    build_narrative_persona,
    build_water_situation_text,
    build_conservation_status,
    build_aca_hint,
    build_trust_text,
    build_action_outcome_feedback,
    create_profiles_from_csv,
    rebalance_clusters,
)
from broker.core.experiment import ExperimentBuilder
from broker.components.memory_engine import HumanCentricMemoryEngine
from broker.components.reflection_engine import ReflectionEngine
from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
from broker.components.skill_registry import SkillRegistry
from broker.components.context_builder import TieredContextBuilder
from broker.interfaces.skill_types import ExecutionResult
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor
from examples.irrigation_abm.validators.irrigation_validators import (
    irrigation_governance_validator,
    reset_consecutive_tracker,
    update_consecutive_tracker,
)
import examples.irrigation_abm.validators.irrigation_validators as irr_validators

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IRRIGATION_SKILLS = [
    "increase_large", "increase_small", "maintain_demand",
    "decrease_small", "decrease_large",
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
            "below_minimum_utilisation": False,
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
    from examples.irrigation_abm.learning.fql import (
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
        # Feedback dashboard (attached after construction by main())
        self.metrics_tracker = None
        self.feedback_config: Dict = {}

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
            agent.aca_hint = build_aca_hint(profile.cluster)
            agent.trust_forecasts_text = trust["trust_forecasts_text"]
            agent.trust_neighbors_text = trust["trust_neighbors_text"]

            # Sync ALL validator-relevant fields from environment → agent
            # These flow through custom_attributes → context["state"] → validation_context
            agent_state = self.env.get_agent_state(aid)
            validator_fields = {
                "agent_id": aid,  # Phase C: needed by consecutive_increase_cap_check
                "at_allocation_cap": agent_state.get("at_allocation_cap", False),
                "has_efficient_system": agent_state.get("has_efficient_system", False),
                "below_minimum_utilisation": agent_state.get("below_minimum_utilisation", False),
                "water_right": ctx.get("water_right", 0),
                "current_diversion": ctx.get("current_diversion", 0),
                "current_request": ctx.get("current_request", 0),
                "curtailment_ratio": ctx.get("curtailment_ratio", 0),
                "shortage_tier": ctx.get("shortage_tier", 0),
                "drought_index": ctx.get("drought_index", 0.5),  # Phase C: wet-period exemption
                "cluster": ctx.get("cluster", "unknown"),
                "basin": ctx.get("basin", "unknown"),
                "loop_year": year,  # use "loop_year" to avoid collision with env_context["year"] (CRSS calendar year)
            }
            for key, value in validator_fields.items():
                setattr(agent, key, value)
            if hasattr(agent, "custom_attributes"):
                agent.custom_attributes.update(validator_fields)

            # Record metrics for feedback dashboard (if configured).
            # NOTE: Year 1 has no prior history → dashboard shows only
            # assertions, not the trend table.  This is intentional.
            if self.metrics_tracker is not None:
                fb_metrics = {}
                for m_cfg in self.feedback_config.get("tracked_metrics", []):
                    fb_metrics[m_cfg["name"]] = float(ctx.get(m_cfg["source"], 0))
                self.metrics_tracker.record(aid, year, fb_metrics)

            # Inject combined action + outcome feedback from last year
            if year > 1:
                prev_request = agent_state.get("request", 0)
                prev_diversion = agent_state.get("diversion", 0)
                action_ctx = getattr(agent, '_last_action_context', None)
                feedback = build_action_outcome_feedback(
                    action_ctx=action_ctx,
                    year=year - 1,
                    request=prev_request,
                    diversion=prev_diversion,
                    drought_index=ctx.get("drought_index", 0),
                    preceding_factor=ctx.get("preceding_factor", 0),
                )
                self.runner.memory_engine.add_memory(aid, feedback)

    # -- post_step: record each agent's decision --
    def post_step(self, agent, result):
        # Use the runner's internal year counter (1-based), not env.current_year
        # which is the simulation year (e.g. 2020). The post_year hook receives
        # the same 1-based step counter from ExperimentRunner.
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
            # ═══ v12 FIX: Read magnitude from environment state_changes, not LLM params ═══
            # The environment generates magnitude_pct using bounded Gaussian sampling.
            # params.get("magnitude_pct") would be the LLM's discrete choice (wrong!).
            # state_changes["magnitude_pct_applied"] is the actual value used by the environment.
            exec_result = result.execution_result
            state_changes = exec_result.state_changes if exec_result else {}
            appraisals["magnitude_pct"] = state_changes.get("magnitude_pct_applied")
            appraisals["is_exploration"] = state_changes.get("is_exploration", False)

            # Keep magnitude_fallback for debugging (indicates LLM didn't provide magnitude)
            params = result.approved_skill.parameters or {}
            appraisals["magnitude_fallback"] = params.get("magnitude_fallback", False)

        self.yearly_decisions[(agent.id, year)] = {
            "skill": skill_name,
            "appraisals": appraisals,
        }

        # Update consecutive increase tracker for Phase C/D validators
        if skill_name:
            update_consecutive_tracker(agent.id, skill_name)

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
                "wsa_label": appr.get("wsa_label", "N/A"),
                "aca_label": appr.get("aca_label", "N/A"),
                "request": agent_state.get("request", 0),
                "diversion": agent_state.get("diversion", 0),
                "water_right": agent_state.get("water_right", 0),
                "curtailment_ratio": agent_state.get("curtailment_ratio", 0),
                "drought_index": self.env.global_state.get("drought_index", 0),
                "shortage_tier": self.env.institutions.get("colorado_compact", {}).get("shortage_tier", 0),
                "lake_mead_level": self.env.get_local("lower_basin", "lake_mead_level", 0),
                "mead_storage_maf": self.env._mead_storage[-1] if self.env._mead_storage else 0,
                "has_efficient_system": agent_state.get("has_efficient_system", False),
                "below_minimum_utilisation": agent_state.get("below_minimum_utilisation", False),
                "utilisation_pct": (
                    agent_state.get("request", 0) / agent_state.get("water_right", 1) * 100
                    if agent_state.get("water_right", 0) > 0 else 0
                ),
                "magnitude_pct": appr.get("magnitude_pct"),
                "magnitude_fallback": appr.get("magnitude_fallback", False),
                "is_exploration": appr.get("is_exploration", False),  # v12: Track ε-exploration
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
        drought = self.env.global_state.get("drought_index", 0)
        print(f"[Year {year}] {summary} (drought={drought:.2f})")

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
                # Build domain context for adapter-based importance scoring
                attrs = getattr(agent, "custom_attributes", {})
                agent_ctx = {
                    "water_right_pct": attrs.get("water_right", 0.5),
                    "supply_ratio": self.env.get_supply_ratio() if hasattr(self.env, "get_supply_ratio") else 1.0,
                    "years_farming": attrs.get("years_farming", 0),
                    "has_efficient_system": attrs.get("has_efficient_system", False),
                    "recent_decision": attrs.get("last_decision", ""),
                    "drought_count": attrs.get("drought_count", 0),
                    "cluster": attrs.get("cluster", ""),
                }
                candidates.append({
                    "agent_id": aid,
                    "memories": mems,
                    "context": agent_ctx,
                })

        if not candidates:
            return

        llm_call = self.runner.get_llm_invoke("irrigation_farmer")
        print(f"  [Reflection] {len(candidates)} agents in batches of {batch_size}...")
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i: i + batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(
                batch,
                year,
                reflection_questions=cfg.get("questions", []),
                persona_instruction=cfg.get("persona_instruction")
            )
            try:
                raw = llm_call(prompt)
                text = raw[0] if isinstance(raw, tuple) else raw
                insights = self.reflection_engine.parse_batch_reflection_response(
                    text, batch_ids, year
                )
                for aid, insight in insights.items():
                    if insight:
                        # Use adapter for dynamic importance instead of hardcoded 0.9
                        ctx_item = next((c for c in batch if c["agent_id"] == aid), None)
                        if ctx_item and ctx_item.get("context") and self.reflection_engine.adapter:
                            dynamic_imp = self.reflection_engine.compute_dynamic_importance(
                                ctx_item["context"]
                            )
                            insight.importance = dynamic_imp

                        self.reflection_engine.store_insight(aid, insight)
                        emotion = "major"
                        if self.reflection_engine.adapter and ctx_item and ctx_item.get("context"):
                            decision = ctx_item["context"].get("recent_decision", "")
                            emotion = self.reflection_engine.adapter.classify_emotion(
                                decision, ctx_item["context"]
                            )
                        self.runner.memory_engine.add_memory(
                            aid,
                            f"Consolidated Reflection: {insight.summary}",
                            {
                                "significance": insight.importance,
                                "emotion": emotion,
                                "source": "personal",
                                "type": "reflection",
                            },
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

    # --- Load config YAML (pilot phase selects config file) ---
    pilot_phase = args.pilot_phase

    # Reset module-level flags (safe for multi-run in same process)
    irr_validators.ENABLE_CONSECUTIVE_CAP = False
    irr_validators.ENABLE_ZERO_ESCAPE = False

    # Always use main config (pilot config merged into agent_types.yaml)
    agent_config_path = config_dir / "agent_types.yaml"
    if pilot_phase:
        print(f"[Pilot] Phase {pilot_phase}: using main config (governance levels set in agent_types.yaml)")

    # Enable Phase C/D validators via module-level flags
    if pilot_phase in ("C", "D"):
        if args.workers > 1:
            print("[Pilot] WARNING: Phase C/D consecutive tracker is not thread-safe, forcing --workers 1")
            args.workers = 1
        irr_validators.ENABLE_CONSECUTIVE_CAP = True
        print("[Pilot] Phase C validator enabled: consecutive_increase_cap")
    if pilot_phase == "D":
        irr_validators.ENABLE_ZERO_ESCAPE = True
        print("[Pilot] Phase D validator enabled: zero_escape")

    with open(agent_config_path, "r", encoding="utf-8") as f:
        cfg_data = yaml.safe_load(f)
    global_cfg = cfg_data.get("global_config", {})

    # --- Optional: strip magnitude_pct from schema to reduce context size ---
    if args.no_magnitude:
        shared_fields = cfg_data.get("shared", {}).get("response_format", {}).get("fields", [])
        cfg_data["shared"]["response_format"]["fields"] = [
            f for f in shared_fields if f.get("key") != "magnitude_pct"
        ]
        print("[Config] magnitude_pct field removed from response schema (--no-magnitude)")

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

    # --- Optional cluster rebalancing ---
    if args.rebalance_clusters:
        from collections import Counter
        before = Counter(p.cluster for p in profiles)

        # Phase 1 + CRSS: Target 50%-30%-20% distribution
        from examples.irrigation_abm.irrigation_personas import rebalance_to_target
        target_dist = {
            "aggressive": 0.50,
            "forward_looking_conservative": 0.30,
            "myopic_conservative": 0.20,
        }

        # Runtime assertion: Verify target_dist matches synthetic initialization in irrigation_env.py
        # (Lines 251-254: clusters = ["aggressive"] * (n // 2) + ["forward"] * (n * 3 // 10) + ["myopic"] * (n * 2 // 10))
        synthetic_dist = {"aggressive": 0.50, "forward_looking_conservative": 0.30, "myopic_conservative": 0.20}
        assert target_dist == synthetic_dist, \
            f"target_dist {target_dist} must match synthetic initialization percentages {synthetic_dist}"

        rebalance_to_target(profiles, target_dist, rng=np.random.default_rng(seed))

        after = Counter(p.cluster for p in profiles)
        print(f"[Rebalance] Clusters: {dict(before)} → {dict(after)} (target: 50%-30%-20%)")

    # --- Set persona-specific magnitude parameters from config ---
    personas_cfg = cfg_data.get("personas", {})
    skill_mag_cfg = cfg_data.get("skill_magnitude", {})
    for p in profiles:
        persona = personas_cfg.get(p.cluster, {})
        # v17: persona_scale + per-skill Gaussian params
        p.persona_scale = persona.get("persona_scale", 1.0) or 1.0
        p.skill_magnitude = dict(skill_mag_cfg)  # copy base params
        # Legacy per-persona params (v12 fallback)
        p.magnitude_default = persona.get("magnitude_default", 10) or 10
        p.magnitude_sigma = persona.get("magnitude_sigma", 0.0) or 0.0
        p.magnitude_min = persona.get("magnitude_min", 1.0) or 1.0
        p.magnitude_max = persona.get("magnitude_max", 30.0) or 30.0
        p.exploration_rate = persona.get("exploration_rate", 0.0) or 0.0

    # --- Create environment and initialize ---
    config = WaterSystemConfig(seed=seed)
    env = IrrigationEnvironment(config)
    env.initialize_from_profiles(profiles)

    # Load real CRSS precipitation projections when available
    if args.real:
        precip_csv = ref_dir / "CRSS_DB" / "CRSS_DB" / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
        if precip_csv.exists():
            env.load_crss_precipitation(str(precip_csv))
            print(f"[Data] Loaded real CRSS precipitation projections (2017-2060)")

    # --- Convert profiles → BaseAgent instances ---
    agents = _profiles_to_agents(profiles)

    # --- Memory engine (Pillar 2) --- must be created before ctx_builder
    irr_cfg = cfg_data.get("irrigation_farmer", {})
    irr_mem = irr_cfg.get("memory", {})
    gm = global_cfg.get("memory", {})
    rw = irr_mem.get("retrieval_weights", {})

    # --- Domain adapter (literature-informed reflection + memory) ---
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
    print(f"[Pillar 2] HumanCentricMemoryEngine (window={args.window_size}, mode={memory_engine.ranking_mode})")

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
        memory_engine=memory_engine,
    )

    # --- Feedback dashboard (config-driven env feedback for agents) ---
    feedback_cfg = irr_cfg.get("feedback", {})
    _metrics_tracker = None  # set below if feedback is configured
    if feedback_cfg.get("tracked_metrics"):
        from broker.components.feedback_provider import (
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
        print(f"[Feedback] Dashboard enabled: metrics={metric_names}, "
              f"assertions={len(feedback_cfg.get('assertions', []))}")

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
        adapter=irrigation_adapter,
    )
    print(f"[Pillar 2] ReflectionEngine (interval={reflection_engine.reflection_interval}, adapter=IrrigationAdapter)")

    # --- Inject lifecycle hooks ---
    hooks = IrrigationLifecycleHooks(env, runner, profiles, reflection_engine, output_dir)
    # Attach feedback tracker so pre_year can record metrics
    hooks.metrics_tracker = _metrics_tracker
    hooks.feedback_config = feedback_cfg
    runner.hooks.update({
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year,
    })

    # --- Reset pilot state ---
    reset_consecutive_tracker()

    # --- Run ---
    n_real = "real" if args.real else "synthetic"
    phase_str = f" | pilot={pilot_phase}" if pilot_phase else ""
    print(
        f"--- Irrigation ABM | {args.model} | {len(profiles)} agents ({n_real}) "
        f"| {args.years} years | seed={seed}{phase_str} ---"
    )
    runner.run(llm_invoke=create_llm_invoke(args.model, verbose=False))

    # Finalize audit
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save simulation log
    if hooks.logs:
        # Sanitize text for CSV compatibility
        sanitized_logs = []
        for log in hooks.logs:
            sanitized_log = {
                k: (v.replace('\n', ' ').replace('\r', ' ').strip() if isinstance(v, str) else v)
                for k, v in log.items()
            }
            sanitized_logs.append(sanitized_log)
        pd.DataFrame(sanitized_logs).to_csv(output_dir / "simulation_log.csv", index=False)

    GovernanceAuditor().print_summary()
    print(f"--- Complete! Results in {output_dir} ---")


def parse_args():
    p = argparse.ArgumentParser(
        description="Irrigation ABM Experiment (Hung 2021 — WAGF Pipeline)"
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
    p.add_argument("--rebalance-clusters", action="store_true",
                   help="Rebalance cluster assignment so each cluster has ≥15%% of agents")
    p.add_argument("--no-magnitude", action="store_true",
                   help="Disable magnitude_pct output (reduces context size)")
    p.add_argument("--pilot-phase", type=str, default=None,
                   choices=["A", "B", "C", "D"],
                   help="Pilot phase: A=baseline, B=BLOCK+retry, C=+consecutive_cap, D=+zero_escape")
    return p.parse_args()


if __name__ == "__main__":
    main()
