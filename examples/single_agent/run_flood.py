import sys
import yaml
import random
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker.core.experiment import ExperimentBuilder, ExperimentRunner
from broker.components.social_graph import NeighborhoodGraph
from broker.components.interaction_hub import InteractionHub
from broker.components.context_builder import TieredContextBuilder
from broker.components.skill_registry import SkillRegistry
from broker.components.memory_engine import WindowMemoryEngine, ImportanceMemoryEngine, HumanCentricMemoryEngine
from broker.interfaces.skill_types import ExecutionResult
from plot_results import plot_adaptation_results
from broker.utils.llm_utils import create_legacy_invoke as create_llm_invoke
from broker.utils.agent_config import GovernanceAuditor

# --- 1. Research Constants (Parity with LLMABMPMT-Final.py) ---
FLOOD_PROBABILITY = 0.2
GRANT_PROBABILITY = 0.5
RANDOM_MEMORY_RECALL_CHANCE = 0.2
PAST_EVENTS = [
    "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
    "Some residents reported delays when processing their flood insurance claims",
    "A few households in the area elevated their homes before recent floods",
    "The city previously introduced a program offering elevation support to residents",
    "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
]

# --- 2. Custom Components for Perception Parity ---

class FinalContextBuilder(TieredContextBuilder):
    """Subclass of TieredContextBuilder to verbalize floats and format memory into string."""
    
    def _verbalize_trust(self, trust_value: float, category: str = "insurance") -> str:
        if category == "insurance":
            if trust_value >= 0.8: return "strongly trust"
            elif trust_value >= 0.5: return "moderately trust"
            elif trust_value >= 0.2: return "have slight doubts about"
            else: return "deeply distrust"
        elif category == "neighbors":
            if trust_value >= 0.8: return "highly rely on"
            elif trust_value >= 0.5: return "generally trust"
            elif trust_value >= 0.2: return "are skeptical of"
            else: return "completely ignore"
        return "trust"

    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        # 1. Gather base context
        # We manually retrieve more memories (top_k=3) for parity
        agent = self.agents[agent_id]
        if hasattr(self.hub, 'memory_engine') and self.hub.memory_engine:
            personal_memory = self.hub.memory_engine.retrieve(agent, top_k=5)
        else:
            personal_memory = []
            
        context = super().build(agent_id, **kwargs)
        personal = context.get('personal', {})
        personal['memory'] = personal_memory # Override the default top_k=3 from hub
        
        # 2. Extract state for verbalization
        elevated = personal.get('elevated', False)
        has_insurance = personal.get('has_insurance', False)
        trust_ins = personal.get('trust_in_insurance', 0.5)
        trust_nb = personal.get('trust_in_neighbors', 0.5)
        
        # 3. Inject Verbalized Variables (Standardized for flattened template usage)
        personal['elevation_status_text'] = (
            "Your house is already elevated, which provides very good protection."
            if elevated else "You have not elevated your home."
        )
        personal['insurance_status'] = "have" if has_insurance else "do not have"
        personal['trust_insurance_text'] = self._verbalize_trust(trust_ins, "insurance")
        personal['trust_neighbors_text'] = self._verbalize_trust(trust_nb, "neighbors")
        
        # 4. Format memory list/dict into a bulleted string
        mem_val = personal.get('memory', [])
        if isinstance(mem_val, dict):
            # Flatten tiered memory for prompt
            lines = []
            if mem_val.get("core"):
                core_str = " ".join([f"{k}={v}" for k, v in mem_val["core"].items()])
                lines.append(f"CORE: {core_str}")
            if mem_val.get("semantic"):
                lines.append("HISTORIC:")
                lines.extend([f"  - {m}" for m in mem_val["semantic"]])
            if mem_val.get("episodic"):
                lines.append("RECENT:")
                lines.extend([f"  - {m}" for m in mem_val["episodic"]])
            personal['memory'] = "\n".join(lines) if lines else "No memory available"
        elif isinstance(mem_val, list):
            personal['memory'] = "\n".join([f"- {m}" for m in mem_val])
        
        # 5. Options Text Formatting (with Shuffling to reduce positional bias)
        agent = self.agents[agent_id]
        available = agent.get_available_skills()
        
        # Build option list with skill_id -> description mapping
        option_items = []  # List of (skill_id, description)
        for skill_item in available:
            skill_id = skill_item.split(": ", 1)[0] if ": " in skill_item else skill_item
            skill_def = self.skill_registry.get(skill_id) if self.skill_registry else None
            desc = skill_def.description if skill_def else (skill_item.split(": ", 1)[1] if ": " in skill_item else skill_item)
            option_items.append((skill_id, desc))
        
        # SHUFFLE options to reduce positional bias (changes per step/year for each agent)
        step_id = kwargs.get('step_id', 0)
        agent_seed = hash(f"{agent_id}_{step_id}") % 10000
        rng = random.Random(agent_seed)
        rng.shuffle(option_items)
        
        # Build numbered options text and dynamic skill_map
        options = []
        dynamic_skill_map = {}  # Maps "1", "2", "3", "4" to shuffled skill IDs
        for i, (skill_id, desc) in enumerate(option_items, 1):
            options.append(f"{i}. {desc}")
            dynamic_skill_map[str(i)] = skill_id
        
        # INJECT INTO PERSONAL to ensure template_vars flattening picks it up early
        personal['options_text'] = "\n".join(options)
        personal['skills'] = personal['options_text'] # Alias
        
        # Pass dynamic skill_map to context for parser to use
        personal['dynamic_skill_map'] = dynamic_skill_map
        
        # Valid choices text (e.g., "1, 2, or 3")
        if len(options) > 1:
            choices = [str(x) for x in range(1, len(options) + 1)]
            personal['valid_choices_text'] = f"{', '.join(choices[:-1])}, or {choices[-1]}"
        else:
            personal['valid_choices_text'] = "1"
        
        # 6. Set variant for adapter
        context["skill_variant"] = "elevated" if elevated else "non_elevated"
            
        return context




# --- 3. Simulation Environment ---
class ResearchSimulation:
    def __init__(self, agents: Dict[str, Any], flood_years: List[int] = None):
        self.agents = agents
        self.flood_years = flood_years or []
        self.current_year = 0
        self.flood_event = False
        self.grant_available = False

    def advance_year(self):
        self.current_year += 1
        self.flood_event = self.current_year in self.flood_years
        self.grant_available = random.random() < GRANT_PROBABILITY
        return {"flood_event": self.flood_event, "grant_available": self.grant_available}

    def execute_skill(self, approved_skill) -> ExecutionResult:
        skill = approved_skill.skill_name
        state_changes = {}
        if skill == "buy_insurance": 
            state_changes["has_insurance"] = True
        elif skill == "elevate_house": 
            state_changes["elevated"] = True
            state_changes["has_insurance"] = False # Insurance expires
        elif skill == "relocate": 
            state_changes["relocated"] = True
        else: # do_nothing
            state_changes["has_insurance"] = False # Insurance expires
        return ExecutionResult(success=True, state_changes=state_changes)

def classify_adaptation_state(agent):
    if getattr(agent, "relocated", False): return "Relocate"
    elevated = getattr(agent, "elevated", False)
    has_insurance = getattr(agent, "has_insurance", False)
    if elevated and has_insurance: return "Both Flood Insurance and House Elevation"
    elif elevated: return "Only House Elevation"
    elif has_insurance: return "Only Flood Insurance"
    else: return "Do Nothing"

# --- 4. Parity Hook ---
class FinalParityHook:
    def __init__(self, sim: ResearchSimulation, runner: ExperimentRunner):
        self.sim = sim
        self.runner = runner
        self.logs = []
        self.prompt_inspected = False

    def pre_year(self, year, env, agents):
        year = year
        flood_event = self.sim.flood_event
        
        # 0. Global stats for social observation (Matching Baseline PHASES 1 & 3)
        active_agents = [a for a in self.sim.agents.values() if not getattr(a, 'relocated', False)]
        total_elevated = sum(1 for a in active_agents if getattr(a, 'elevated', False))
        total_relocated = len(self.sim.agents) - len(active_agents)
        
        for agent in self.sim.agents.values():
            if getattr(agent, 'relocated', False): 
                if len(agent.flood_history) < year: agent.flood_history.append(False)
                continue
            flooded = False
            if flood_event:
                damage = 10000 * (0.1 if agent.elevated else 1.0)
                if random.random() < agent.flood_threshold:
                    flooded = True
                    mem = f"Year {year}: Despite elevation, got flooded with ${damage:,.0f} damage." if agent.elevated else f"Year {year}: Got flooded with ${damage:,.0f} damage on my house."
                else:
                    mem = f"Year {year}: A flood occurred, but my house was protected by its elevation." if agent.elevated else f"Year {year}: A flood occurred, but my house was spared damage."
            else: mem = f"Year {year}: No flood occurred this year."
            agent.flood_history.append(flooded)
            self.runner.memory_engine.add_memory(agent.id, mem)
            
            # Social Observation Memory (Parity with run_experiment.py)
            num_others = len(self.sim.agents) - 1
            if num_others > 0:
                elev_pct = round(((total_elevated - (1 if agent.elevated else 0)) / num_others) * 100)
                reloc_pct = round((total_relocated / num_others) * 100)
                self.runner.memory_engine.add_memory(agent.id, f"Year {year}: I observe {elev_pct}% of my neighbors have elevated homes.")
                self.runner.memory_engine.add_memory(agent.id, f"Year {year}: I observe {reloc_pct}% of my neighbors have relocated.")

            if self.sim.grant_available: self.runner.memory_engine.add_memory(agent.id, f"Year {year}: Elevation grants are available.")
            if random.random() < RANDOM_MEMORY_RECALL_CHANCE: self.runner.memory_engine.add_memory(agent.id, f"Suddenly recalled: '{random.choice(PAST_EVENTS)}'.")

    def post_step(self, agent, result):
        if result.approved_skill and result.approved_skill.skill_name == "elevate_house":
            agent.flood_threshold = round(agent.flood_threshold * 0.2, 2)
            agent.flood_threshold = max(0.001, agent.flood_threshold)

    def post_year(self, year, agents):
        total_elevated = sum(1 for a in agents.values() if getattr(a, 'elevated', False))
        total_relocated = sum(1 for a in agents.values() if getattr(a, 'relocated', False))
        community_action_rate = (total_elevated + total_relocated) / len(agents)

        for agent in agents.values():
            if not getattr(agent, 'relocated', False):
                last_flood = agent.flood_history[-1] if agent.flood_history else False
                has_ins = getattr(agent, 'has_insurance', False)
                trust_ins = getattr(agent, 'trust_in_insurance', 0.5)
                if has_ins: trust_ins += ( -0.10 if last_flood else 0.02 )
                else: trust_ins += ( 0.05 if last_flood else -0.02 )
                agent.trust_in_insurance = max(0.0, min(1.0, trust_ins))
                trust_nb = getattr(agent, 'trust_in_neighbors', 0.5)
                if community_action_rate > 0.30: trust_nb += 0.04
                elif last_flood and community_action_rate < 0.10: trust_nb -= 0.05
                else: trust_nb -= 0.01
                agent.trust_in_neighbors = max(0.0, min(1.0, trust_nb))

            self.logs.append({
                "agent_id": agent.id, "year": year, "cumulative_state": classify_adaptation_state(agent),
                "elevated": getattr(agent, 'elevated', False), "has_insurance": getattr(agent, 'has_insurance', False),
                "relocated": getattr(agent, 'relocated', False), "trust_insurance": getattr(agent, 'trust_in_insurance', 0),
                "trust_neighbors": getattr(agent, 'trust_in_neighbors', 0)
            })

        df_year = pd.DataFrame([l for l in self.logs if l['year'] == year])
        stats = df_year['cumulative_state'].value_counts()
        categories = ["Do Nothing", "Only Flood Insurance", "Only House Elevation", "Both Flood Insurance and House Elevation", "Relocate"]
        stats_str = " | ".join([f"{cat}: {stats.get(cat, 0)}" for cat in categories])
        print(f"[Year {year}] Stats: {stats_str}")

# --- 5. Main Runner ---
def run_parity_benchmark(model: str = "llama3.2:3b", years: int = 10, agents_count: int = 100, custom_output: str = None, verbose: bool = False, memory_engine_type: str = "window", workers: int = 1):
    print(f"--- Llama {agents_count}-Agent {years}-Year Benchmark (Final Parity Edition) ---")
    
    # 1. Load Registry & Prompt Template
    base_path = Path(__file__).parent
    registry_path = base_path / "skill_registry.yaml"
    registry = SkillRegistry()
    registry.register_from_yaml(str(registry_path))
    
    agent_config_path = base_path / "agent_types.yaml"
    with open(agent_config_path, 'r', encoding='utf-8') as f:
        agent_cfg_data = yaml.safe_load(f)
        household_template = agent_cfg_data.get('household', {}).get('prompt_template', '')

    # 2. Load Profiles
    from broker import load_agents_from_csv
    profiles_path = base_path / "agent_initial_profiles.csv"
    agents = load_agents_from_csv(str(profiles_path), {
        "id": "id", "elevated": "elevated", "has_insurance": "has_insurance", 
        "relocated": "relocated", "trust_in_insurance": "trust_in_insurance", 
        "trust_in_neighbors": "trust_in_neighbors", "flood_threshold": "flood_threshold",
        "memory": "memory"
    })
    import re
    def natural_key(string_):
        """Helper for natural sorting (Agent_1, Agent_2, Agent_10...)"""
        return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]

    agents = {aid: agents[aid] for aid in sorted(agents.keys(), key=natural_key)[:agents_count]}
    for a in agents.values(): 
        a.flood_history = []
        a.agent_type = "household"
        # Synchronize Registry IDs - Include full global suite for disclosure parity
        a.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
        for k, v in a.custom_attributes.items(): setattr(a, k, v)

    # 3. Load Flood Years
    df_years = pd.read_csv(base_path / "flood_years.csv")
    flood_years = sorted(df_years['Flood_Years'].tolist())
    print(f" Flood Years scheduled: {flood_years}")

    # 4. Setup Components
    sim = ResearchSimulation(agents, flood_years)
    graph = NeighborhoodGraph(list(agents.keys()), k=4)
    hub = InteractionHub(graph)
    ctx_builder = FinalContextBuilder(
        agents=agents, 
        hub=hub, 
        skill_registry=registry,
        prompt_templates={"household": household_template, "default": household_template},
        yaml_path=str(agent_config_path)
    )

    # Select memory engine based on CLI argument
    if memory_engine_type == "importance":
        # Domain-specific categories for Flood scenario
        flood_categories = {
            "critical": ["flood", "flooded", "damage", "severe", "destroyed"],
            "high": ["grant", "elevation", "insurance", "protected"],
            "medium": ["neighbor", "relocated", "observed", "pct%"]
        }
        memory_engine = ImportanceMemoryEngine(
            window_size=3,
            top_k_significant=2,
            categories=flood_categories # Injecting domain keywords without touching base module
        )
        print(f" Using ImportanceMemoryEngine (active retrieval with flood-specific keywords)")
    elif memory_engine_type == "humancentric":
        memory_engine = HumanCentricMemoryEngine(
            window_size=3,
            top_k_significant=2,
            consolidation_prob=0.7,
            decay_rate=0.1,
            seed=42  # For reproducibility
        )
        print(f" Using HumanCentricMemoryEngine (emotional encoding + stochastic consolidation)")
    elif memory_engine_type == "hierarchical":
        from broker.components.memory_engine import HierarchicalMemoryEngine
        memory_engine = HierarchicalMemoryEngine(window_size=5, semantic_top_k=3)
        print(f" Using HierarchicalMemoryEngine (Tiered: Core, Episodic, Semantic)")
    else:
        memory_engine = WindowMemoryEngine(window_size=3)
        print(f" Using WindowMemoryEngine (sliding window)")
    
    # 5. Setup ExperimentBuilder and Runner
    from broker import ExperimentBuilder
    
    builder = (
        ExperimentBuilder()
        .with_model(model)
        .with_years(years)
        .with_agents(agents)
        .with_simulation(sim)
        .with_context_builder(ctx_builder)
        .with_skill_registry(registry)
        .with_memory_engine(memory_engine)
        .with_governance("strict", agent_config_path)
        .with_output(custom_output if custom_output else "results_modular")
        .with_workers(workers)
    )
    
    runner = builder.build()
    
    # Inject Parity Hooks manually after build
    parity = FinalParityHook(sim, runner)
    runner.hooks = {
        "pre_year": parity.pre_year, 
        "post_step": parity.post_step, 
        "post_year": parity.post_year
    }
    
    # Enable detailed broker logging if verbose is on
    runner.broker.log_prompt = verbose

    # 5. Execute Run
    # This uses the enhanced llm_invoke in llm_utils.py with 3-attempt LLM-level retry
    # Passing verbose=False here to hide raw prompt/output dumps as requested,
    # but runner.broker.log_prompt=verbose above ensures Adapter/Validator results are still shown.
    runner.run(llm_invoke=create_llm_invoke(model, verbose=False))
    
    # Finalize Audit (Generates CSVs and Summary)
    if runner.broker.audit_writer:
        runner.broker.audit_writer.finalize()
    
    # 6. Save Simulation Log (Parity with baseline simulation_log.csv)
    # We must ensure every agent is represented in every year for the stacked plot
    final_logs = []
    for year in range(1, years + 1):
        for agent_id, agent in agents.items():
            # Find log from hook
            entry = next((l for l in parity.logs if l['agent_id'] == agent_id and l['year'] == year), None)
            if entry:
                final_logs.append(entry)
            else:
                # If agent relocated, they are missing from active logs but needed for cumulative plot
                was_relocated = any(l for l in parity.logs if l['agent_id'] == agent_id and l['year'] < year and l.get('relocated'))
                if was_relocated:
                    final_logs.append({
                        "agent_id": agent_id,
                        "year": year,
                        "decision": "Relocate",
                        "cumulative_state": "Relocate",
                        "elevated": True,
                        "has_insurance": False,
                        "relocated": True
                    })

    if custom_output:
        # If absolute, use as is; if relative, make it relative to CWD
        output_path = Path(custom_output)
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        output_dir = output_path / f"{model.replace(':','_').replace('.','_')}_strict"
    else:
        # Default to examples/single_agent/results
        base_dir = Path(__file__).parent / "results"
        output_dir = base_dir / f"{model.replace(':','_')}_strict"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "simulation_log.csv"
    pd.DataFrame(final_logs).to_csv(csv_path, index=False)
    print(f"--- Benchmark Complete! Results in {output_dir} ---")
    
    # 7. Print Governance Summary
    auditor = GovernanceAuditor()
    auditor.print_summary()
    
    # 8. Generate Plot
    plot_adaptation_results(csv_path, output_dir)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="llama3.2:3b")
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--agents", type=int, default=100)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--verbose", action="store_true", help="Enable verbose LLM logging")
    parser.add_argument("--memory-engine", type=str, default="window", 
                        choices=["window", "importance", "humancentric", "hierarchical"], 
                        help="Memory retrieval strategy: window (sliding), importance (active retrieval), humancentric (emotional), or hierarchical (tiered)")
    parser.add_argument("--workers", type=int, default=1, help="Number of parallel workers for LLM calls")
    args = parser.parse_args()
    run_parity_benchmark(
        model=args.model, 
        years=args.years, 
        agents_count=args.agents, 
        custom_output=args.output,
        verbose=args.verbose,
        memory_engine_type=args.memory_engine
    )
