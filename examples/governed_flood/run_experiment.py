"""
Governed Flood Adaptation Experiment — Standalone Example.

Demonstrates the full cognitive governance pipeline (Group C):
  Pillar 1 — Strict Governance  (PMT-based rules block inconsistent decisions)
  Pillar 2 — Cognitive Memory   (HumanCentric engine + year-end reflection)
  Pillar 3 — Priority Schema    (important attributes enter context first)

Usage:
    python run_experiment.py                           # defaults: gemma3:1b, 10yr, 100 agents
    python run_experiment.py --model gemma3:4b --years 5 --agents 50
"""
import sys
import random
import argparse
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from broker.core.experiment import ExperimentBuilder
from broker.components.memory_engine import HumanCentricMemoryEngine
from broker.components.reflection_engine import ReflectionEngine
from broker.components.skill_registry import SkillRegistry
from broker.components.social_graph import NeighborhoodGraph
from broker.components.interaction_hub import InteractionHub
from broker.components.context_builder import TieredContextBuilder, PrioritySchemaProvider
from broker.interfaces.skill_types import ExecutionResult
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor
from broker import load_agents_from_csv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FLOOD_PROBABILITY = 0.2
GRANT_PROBABILITY = 0.5
RANDOM_MEMORY_RECALL_CHANCE = 0.2
PAST_EVENTS = [
    "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
    "Some residents reported delays when processing their flood insurance claims",
    "A few households in the area elevated their homes before recent floods",
    "The city previously introduced a program offering elevation support to residents",
    "News outlets have reported a possible trend of increasing flood frequency and severity in recent years",
]


# ---------------------------------------------------------------------------
# Simplified Flood Simulation
# ---------------------------------------------------------------------------
class FloodSimulation:
    """Minimal flood environment that satisfies ExperimentRunner's sim_engine interface."""

    def __init__(self, agents: Dict, flood_years: List[int],
                 flood_mode: str = "fixed", flood_probability: float = FLOOD_PROBABILITY):
        self.agents = agents
        self.flood_years = flood_years
        self.flood_mode = flood_mode
        self.flood_probability = flood_probability
        self.current_year = 0
        self.flood_event = False
        self.grant_available = False

    # -- ExperimentRunner calls this each step --
    def advance_year(self) -> Dict[str, Any]:
        self.current_year += 1
        if self.flood_mode == "prob":
            self.flood_event = random.random() < self.flood_probability
        else:
            self.flood_event = self.current_year in self.flood_years
        self.grant_available = random.random() < GRANT_PROBABILITY
        return {
            "flood_event": self.flood_event,
            "grant_available": self.grant_available,
            "current_year": self.current_year,
        }

    # -- Skill execution mappings (called by SkillBrokerEngine) --
    def execute_skill(self, approved_skill) -> ExecutionResult:
        agent = self.agents[approved_skill.agent_id]
        skill = approved_skill.skill_name
        state_changes: Dict[str, Any] = {}

        if skill == "elevate_house":
            if getattr(agent, "elevated", False):
                return ExecutionResult(success=False, error="Already elevated.")
            state_changes["elevated"] = True
        elif skill == "buy_insurance":
            state_changes["has_insurance"] = True
        elif skill == "relocate":
            state_changes["relocated"] = True
            agent.is_active = False

        # Insurance expires if not renewed
        if skill != "buy_insurance":
            state_changes["has_insurance"] = False

        return ExecutionResult(success=True, state_changes=state_changes)


# ---------------------------------------------------------------------------
# Adaptation state classifier (for simulation_log.csv)
# ---------------------------------------------------------------------------
def classify_state(agent) -> str:
    if getattr(agent, "relocated", False):
        return "Relocate"
    e = getattr(agent, "elevated", False)
    i = getattr(agent, "has_insurance", False)
    if e and i:
        return "Both Flood Insurance and House Elevation"
    if e:
        return "Only House Elevation"
    if i:
        return "Only Flood Insurance"
    return "Do Nothing"


# ---------------------------------------------------------------------------
# Lifecycle Hooks
# ---------------------------------------------------------------------------
class LifecycleHooks:
    """Simplified hooks that wire flood events, trust updates, and reflection."""

    def __init__(self, sim: FloodSimulation, runner, reflection_engine: Optional[ReflectionEngine], output_dir: Path):
        self.sim = sim
        self.runner = runner
        self.reflection_engine = reflection_engine
        self.output_dir = output_dir
        self.logs: List[Dict] = []
        self.yearly_decisions: Dict = {}

    # -- pre_year: inject flood / grant / social memories --
    def pre_year(self, year, env, agents):
        sim = self.sim
        active = [a for a in sim.agents.values() if not getattr(a, "relocated", False)]
        total_elevated = sum(1 for a in active if getattr(a, "elevated", False))
        total_relocated = len(sim.agents) - len(active)

        for agent in sim.agents.values():
            if getattr(agent, "relocated", False):
                if len(agent.flood_history) < year:
                    agent.flood_history.append(False)
                continue

            parts: List[str] = []
            flooded = False
            if sim.flood_event:
                if not agent.elevated:
                    if random.random() < agent.flood_threshold:
                        flooded = True
                        parts.append(f"Year {year}: Got flooded with $10,000 damage on my house.")
                    else:
                        parts.append(f"Year {year}: A flood occurred, but my house was spared damage.")
                else:
                    if random.random() < agent.flood_threshold:
                        flooded = True
                        parts.append(f"Year {year}: Despite elevation, the flood was severe enough to cause damage.")
                    else:
                        parts.append(f"Year {year}: A flood occurred, but my house was protected by its elevation.")
            else:
                parts.append(f"Year {year}: No flood occurred this year.")
            agent.flood_history.append(flooded)

            if sim.grant_available:
                parts.append(f"Year {year}: Elevation grants are available.")

            num_others = len(sim.agents) - 1
            if num_others > 0:
                elev_pct = round(((total_elevated - (1 if agent.elevated else 0)) / num_others) * 100)
                reloc_pct = round((total_relocated / num_others) * 100)
                parts.append(f"Year {year}: I observe {elev_pct}% of neighbors elevated and {reloc_pct}% relocated.")

            if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
                parts.append(f"Suddenly recalled: '{random.choice(PAST_EVENTS)}'.")

            # Action feedback from last year's decision
            if year > 1:
                action_ctx = getattr(agent, '_last_action_context', None)
                if action_ctx and action_ctx.get("skill_name"):
                    skill = action_ctx["skill_name"].replace("_", " ")
                    act_year = action_ctx.get("year", year - 1)
                    parts.append(f"Year {act_year}: You chose to {skill}.")

            self.runner.memory_engine.add_memory(agent.id, " | ".join(parts))

    # -- post_step: record each agent's decision --
    def post_step(self, agent, result):
        year = self.sim.current_year
        skill_name = None
        appraisals = {}

        if result and result.skill_proposal and result.skill_proposal.reasoning:
            r = result.skill_proposal.reasoning
            appraisals["threat_appraisal"] = next((r[k] for k in ["threat_appraisal", "THREAT_APPRAISAL_LABEL", "threat"] if k in r), "N/A")
            appraisals["coping_appraisal"] = next((r[k] for k in ["coping_appraisal", "COPING_APPRAISAL_LABEL", "coping"] if k in r), "N/A")

        if result and result.approved_skill:
            skill_name = result.approved_skill.skill_name

        self.yearly_decisions[(agent.id, year)] = {"skill": skill_name, "appraisals": appraisals}

        if result and result.approved_skill and result.approved_skill.skill_name == "elevate_house":
            agent.flood_threshold = max(0.001, round(agent.flood_threshold * 0.2, 2))

    # -- post_year: trust dynamics, logging, reflection --
    def post_year(self, year, agents):
        total_elevated = sum(1 for a in agents.values() if getattr(a, "elevated", False))
        total_relocated = sum(1 for a in agents.values() if getattr(a, "relocated", False))
        community_rate = (total_elevated + total_relocated) / len(agents)

        for agent in agents.values():
            if not getattr(agent, "relocated", False):
                last_flood = agent.flood_history[-1] if agent.flood_history else False
                has_ins = getattr(agent, "has_insurance", False)

                # Trust dynamics
                t_ins = getattr(agent, "trust_in_insurance", 0.5)
                t_ins += -0.10 if (has_ins and last_flood) else (0.02 if has_ins else (0.05 if last_flood else -0.02))
                agent.trust_in_insurance = max(0.0, min(1.0, t_ins))

                t_nb = getattr(agent, "trust_in_neighbors", 0.5)
                if community_rate > 0.30:
                    t_nb += 0.04
                elif last_flood and community_rate < 0.10:
                    t_nb -= 0.05
                else:
                    t_nb -= 0.01
                agent.trust_in_neighbors = max(0.0, min(1.0, t_nb))

            # Retrieve memory for logging (research reproducibility)
            mem_items = self.runner.memory_engine.retrieve(agent, top_k=5)
            mem_str = " | ".join(mem_items)

            dec = self.yearly_decisions.get((agent.id, year), {})
            skill = dec.get("skill") if isinstance(dec, dict) else dec
            appr = dec.get("appraisals", {}) if isinstance(dec, dict) else {}
            if skill is None and getattr(agent, "relocated", False):
                skill = "relocated"

            self.logs.append({
                "agent_id": agent.id, "year": year,
                "cumulative_state": classify_state(agent),
                "yearly_decision": skill or "N/A",
                "threat_appraisal": appr.get("threat_appraisal", "N/A"),
                "coping_appraisal": appr.get("coping_appraisal", "N/A"),
                "elevated": getattr(agent, "elevated", False),
                "has_insurance": getattr(agent, "has_insurance", False),
                "relocated": getattr(agent, "relocated", False),
                "trust_insurance": getattr(agent, "trust_in_insurance", 0),
                "trust_neighbors": getattr(agent, "trust_in_neighbors", 0),
                "memory": mem_str,
            })

        # Print yearly summary
        df_year = pd.DataFrame([l for l in self.logs if l["year"] == year])
        cats = ["Do Nothing", "Only Flood Insurance", "Only House Elevation",
                "Both Flood Insurance and House Elevation", "Relocate"]
        stats = df_year["cumulative_state"].value_counts()
        print(f"[Year {year}] {' | '.join(f'{c}: {stats.get(c, 0)}' for c in cats)}")

        # --- Pillar 2: Batch year-end reflection ---
        if self.reflection_engine and self.reflection_engine.should_reflect("any", year):
            self._batch_reflect(year)

    def _batch_reflect(self, year):
        cfg = self.runner.broker.config.get_reflection_config()
        batch_size = cfg.get("batch_size", 10)
        candidates = []
        for aid, agent in self.sim.agents.items():
            if getattr(agent, "relocated", False):
                continue
            mems = self.runner.memory_engine.retrieve(agent, top_k=10)
            if mems:
                candidates.append({"agent_id": aid, "memories": mems})

        if not candidates:
            return

        llm_call = self.runner.get_llm_invoke("household")
        print(f"  [Reflection] {len(candidates)} agents in batches of {batch_size}...")
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i : i + batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(
                batch, year, reflection_questions=cfg.get("questions", [])
            )
            try:
                raw = llm_call(prompt)
                text = raw[0] if isinstance(raw, tuple) else raw
                insights = self.reflection_engine.parse_batch_reflection_response(text, batch_ids, year)
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
    data_dir = base / "data"

    # --- Random seed ---
    seed = args.seed if args.seed is not None else random.randint(0, 1_000_000)
    random.seed(seed)

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
    household_template = cfg_data.get("household", {}).get("prompt_template", "")
    global_cfg = cfg_data.get("global_config", {})

    # --- Load skill registry ---
    registry = SkillRegistry()
    registry.register_from_yaml(str(config_dir / "skill_registry.yaml"))

    # --- Load agents from CSV ---
    agents = load_agents_from_csv(
        str(data_dir / "agent_initial_profiles.csv"),
        {"id": "id", "elevated": "elevated", "has_insurance": "has_insurance",
         "relocated": "relocated", "trust_in_insurance": "trust_in_insurance",
         "trust_in_neighbors": "trust_in_neighbors", "flood_threshold": "flood_threshold",
         "memory": "memory"},
        agent_type="household",
    )
    for a in agents.values():
        a.flood_history = []
        a.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
        for k, v in a.custom_attributes.items():
            if k not in ("id", "agent_type"):
                setattr(a, k, v)
        if not getattr(a, "narrative_persona", None):
            a.narrative_persona = "You are a homeowner in a city, with a strong attachment to your community."
            a.custom_attributes["narrative_persona"] = a.narrative_persona

    # --- Load flood schedule ---
    flood_years = sorted(pd.read_csv(config_dir / "flood_years.csv")["Flood_Years"].tolist())
    print(f"Flood years: {flood_years}")

    # --- Build simulation ---
    sim = FloodSimulation(agents, flood_years)

    # --- Context builder (with social graph) ---
    graph = NeighborhoodGraph(list(agents.keys()), k=4)
    hub = InteractionHub(graph)
    ctx_builder = TieredContextBuilder(
        agents=agents, hub=hub,
        skill_registry=registry,
        prompt_templates={"household": household_template, "default": household_template},
        yaml_path=str(agent_config_path),
    )

    # Pillar 3: Priority Schema
    hh_cfg = cfg_data.get("household", {})
    schema = hh_cfg.get("priority_schema", {})
    if schema:
        ctx_builder.providers.insert(1, PrioritySchemaProvider(schema))
        print("[Pillar 3] PrioritySchemaProvider injected")

    # --- Memory engine (Pillar 2) ---
    hh_mem = hh_cfg.get("memory", {})
    shared_mem = cfg_data.get("shared", {}).get("memory_config", {})
    merged = {**shared_mem, **hh_mem}
    rw = merged.get("retrieval_weights", {})
    gm = global_cfg.get("memory", {})

    memory_engine = HumanCentricMemoryEngine(
        window_size=args.window_size,
        top_k_significant=gm.get("top_k_significant", 2),
        consolidation_prob=gm.get("consolidation_probability", 0.7),
        consolidation_threshold=gm.get("consolidation_threshold", 0.6),
        decay_rate=gm.get("decay_rate", 0.1),
        emotional_weights=merged.get("emotional_weights"),
        source_weights=merged.get("source_weights"),
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
        .with_simulation(sim)
        .with_context_builder(ctx_builder)
        .with_skill_registry(registry)
        .with_memory_engine(memory_engine)
        .with_governance("strict", str(agent_config_path))
        .with_exact_output(str(output_dir))
        .with_workers(args.workers)
        .with_seed(seed)
    )
    runner = builder.build()

    # --- Reflection engine (Pillar 2) ---
    refl_cfg = cfg_data.get("shared", {}).get("reflection_config", {})
    reflection_engine = ReflectionEngine(
        reflection_interval=refl_cfg.get("interval", 1),
        max_insights_per_reflection=2,
        insight_importance_boost=refl_cfg.get("importance_boost", 0.9),
        output_path=str(output_dir / "reflection_log.jsonl"),
    )
    print(f"[Pillar 2] ReflectionEngine (interval={reflection_engine.reflection_interval})")

    # --- Inject lifecycle hooks ---
    hooks = LifecycleHooks(sim, runner, reflection_engine, output_dir)
    runner.hooks = {
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year,
    }

    # --- Run ---
    print(f"--- Governed Flood Experiment | {args.model} | {args.agents} agents | {args.years} years | seed={seed} ---")
    runner.run(llm_invoke=create_llm_invoke(args.model, verbose=False))

    # Finalize audit
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()

    # Save simulation log
    final_logs = []
    for year in range(1, args.years + 1):
        for aid, agent in agents.items():
            entry = next((l for l in hooks.logs if l["agent_id"] == aid and l["year"] == year), None)
            if entry:
                final_logs.append(entry)
            elif any(l for l in hooks.logs if l["agent_id"] == aid and l["year"] < year and l.get("relocated")):
                final_logs.append({"agent_id": aid, "year": year, "decision": "Relocate",
                                   "cumulative_state": "Relocate", "yearly_decision": "relocated",
                                   "elevated": True, "has_insurance": False, "relocated": True})

    pd.DataFrame(final_logs).to_csv(output_dir / "simulation_log.csv", index=False)
    GovernanceAuditor().print_summary()
    print(f"--- Complete! Results in {output_dir} ---")


def parse_args():
    p = argparse.ArgumentParser(description="Governed Flood Adaptation Experiment (Group C)")
    p.add_argument("--model", default="gemma3:1b")
    p.add_argument("--years", type=int, default=10)
    p.add_argument("--agents", type=int, default=100)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--memory-seed", type=int, default=42)
    p.add_argument("--window-size", type=int, default=5)
    p.add_argument("--output", type=str, default=None)
    p.add_argument("--num-ctx", type=int, default=None)
    p.add_argument("--num-predict", type=int, default=None)
    return p.parse_args()


if __name__ == "__main__":
    main()
