import sys
import yaml
import random
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Add single_agent to path for local utilities
sys.path.insert(0, str(Path(__file__).parent))

from broker.core.experiment import ExperimentBuilder, ExperimentRunner
from broker.components.social_graph import NeighborhoodGraph
from broker.components.interaction_hub import InteractionHub
from broker.components.context_builder import TieredContextBuilder, PrioritySchemaProvider
from broker.components.skill_registry import SkillRegistry
from broker.components.memory_engine import WindowMemoryEngine, ImportanceMemoryEngine, HumanCentricMemoryEngine
from broker.interfaces.skill_types import ExecutionResult
from analysis.plot_results import plot_adaptation_results
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

# Schema Definition for Group C (Pillar 3)
FLOOD_PRIORITY_SCHEMA = {
    "flood_depth": 1.0,      # Physical reality (Highest)
    "flood_threshold": 0.9,  # Physical vulnerability
    "savings": 0.8,          # Financial Reality
    "income_level": 0.7,     # Socio-economic Constaint
    "risk_tolerance": 0.5    # Psychological preference (Lower priority)
}

# --- 2. Custom Components for Perception Parity ---

class FinalContextBuilder(TieredContextBuilder):
    """Subclass of TieredContextBuilder to verbalize floats and format memory into string."""
    def __init__(self, *args, memory_top_k: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        self.memory_top_k = memory_top_k
    
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
        # We manually retrieve more memories for parity with baseline
        agent = self.agents[agent_id]
        if hasattr(self.hub, 'memory_engine') and self.hub.memory_engine:
            personal_memory = self.hub.memory_engine.retrieve(agent, top_k=self.memory_top_k)
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
        
        # 5. Options Text Formatting (STRICT PARITY MODE)
        # We override the dynamic registry lookup to match LLMABMPMT-Final.py exactly.
        
        dynamic_skill_map = {}
        if elevated:
             personal['options_text'] = (
                 "1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                 "2. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                 "3. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"
             )
             personal['valid_choices_text'] = "1, 2, or 3"
             # Map for parser: 1->buy, 2->relocate, 3->do_nothing
             dynamic_skill_map = {
                 "1": "buy_insurance",
                 "2": "relocate", 
                 "3": "do_nothing"
             }
        else:
             personal['options_text'] = (
                 "1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                 "2. Elevate your house (High upfront cost but can prevent most physical damage.)\n"
                 "3. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                 "4. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"
             )
             personal['valid_choices_text'] = "1, 2, 3, or 4"
             # Map for parser: 1->buy, 2->elevate, 3->relocate, 4->do_nothing
             dynamic_skill_map = {
                 "1": "buy_insurance",
                 "2": "elevate_house",
                 "3": "relocate",
                 "4": "do_nothing"
             }

        personal['skills'] = personal['options_text'] # Alias for template compatibility
        personal['dynamic_skill_map'] = dynamic_skill_map
        
        # 6. Set variant for adapter
        context["skill_variant"] = "elevated" if elevated else "non_elevated"
            
        return context


# --- 2b. Parity Memory Filter ---
class DecisionFilteredMemoryEngine:
    """Proxy memory engine that drops decision memories to match baseline."""
    def __init__(self, inner):
        self.inner = inner

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        if "Decided to:" in content:
            return
        return self.inner.add_memory(agent_id, content, metadata)

    def add_memory_for_agent(self, agent, content: str, metadata: Optional[Dict[str, Any]] = None):
        if "Decided to:" in content:
            return
        if hasattr(self.inner, 'add_memory_for_agent'):
            return self.inner.add_memory_for_agent(agent, content, metadata)
        return self.inner.add_memory(agent.id, content, metadata)

    def retrieve(self, agent, query: Optional[str] = None, top_k: int = 3):
        return self.inner.retrieve(agent, query=query, top_k=top_k)

    def clear(self, agent_id: str):
        return self.inner.clear(agent_id)




# --- 3. Simulation Environment ---
class ResearchSimulation:
    def __init__(
        self,
        agents: Dict[str, Any],
        flood_years: List[int] = None,
        flood_mode: str = "fixed",
        flood_probability: float = FLOOD_PROBABILITY
    ):
        self.agents = agents
        self.flood_years = flood_years or []
        self.flood_mode = flood_mode
        self.flood_probability = flood_probability
        self.current_year = 0
        self.flood_event = False
        self.grant_available = False

    def advance_year(self):
        self.current_year += 1
        if self.flood_mode == "prob":
            self.flood_event = random.random() < self.flood_probability
        else:
            self.flood_event = self.current_year in self.flood_years
        self.grant_available = random.random() < GRANT_PROBABILITY
        return {"flood_event": self.flood_event, "grant_available": self.grant_available}

    def execute_skill(self, approved_skill) -> ExecutionResult:
        skill = approved_skill.skill_name
        state_changes = {}
        if skill == "buy_insurance": 
            state_changes["has_insurance"] = True
        else:
            # All other decisions (elevate, relocate, do_nothing) result in insurance expiration
            state_changes["has_insurance"] = False
            if skill == "elevate_house": 
                state_changes["elevated"] = True
            elif skill == "relocate": 
                state_changes["relocated"] = True
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
        self.yearly_decisions = {}

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
                if not agent.elevated:
                    if random.random() < agent.flood_threshold:
                        flooded = True
                        mem = f"Year {year}: Got flooded with $10,000 damage on my house."
                    else:
                        mem = f"Year {year}: A flood occurred, but my house was spared damage."
                else: # agent.elevated
                    if random.random() < agent.flood_threshold:
                        flooded = True
                        mem = f"Year {year}: Despite elevation, the flood was severe enough to cause damage."
                    else:
                        mem = f"Year {year}: A flood occurred, but my house was protected by its elevation."
            else:
                mem = f"Year {year}: No flood occurred this year."
            agent.flood_history.append(flooded)
            yearly_memories = []
            yearly_memories.append(mem)
            
            # Grant memory (baseline order)
            if self.sim.grant_available:
                yearly_memories.append(f"Year {year}: Elevation grants are available.")

            # Social Observation Memory (baseline order)
            num_others = len(self.sim.agents) - 1
            if num_others > 0:
                elev_pct = round(((total_elevated - (1 if agent.elevated else 0)) / num_others) * 100)
                reloc_pct = round((total_relocated / num_others) * 100)
                yearly_memories.append(f"Year {year}: I observe {elev_pct}% of neighbors elevated and {reloc_pct}% relocated.")

            # Stochastic recall (baseline order)
            if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
                yearly_memories.append(f"Suddenly recalled: '{random.choice(PAST_EVENTS)}'.")
            
            # Consolidate and Add ONCE to preserve window history
            consolidated_mem = " | ".join(yearly_memories)
            self.runner.memory_engine.add_memory(agent.id, consolidated_mem)

    def post_step(self, agent, result):
        year = self.sim.current_year
        skill_name = None
        if result and result.approved_skill:
            skill_name = result.approved_skill.skill_name
        self.yearly_decisions[(agent.id, year)] = skill_name
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

            # Retrieve memory for logging (Parity)
            mem_items = self.runner.memory_engine.retrieve(agent, top_k=5)
            # Memory engine returns list of strings. Join with | for CSV parity.
            mem_str = " | ".join(mem_items)
            yearly_decision = self.yearly_decisions.get((agent.id, year))
            if yearly_decision is None and getattr(agent, "relocated", False):
                yearly_decision = "relocated"

            self.logs.append({
                "agent_id": agent.id, "year": year, "cumulative_state": classify_adaptation_state(agent),
                "yearly_decision": yearly_decision if yearly_decision else "N/A",
                "elevated": getattr(agent, 'elevated', False), "has_insurance": getattr(agent, 'has_insurance', False),
                "relocated": getattr(agent, 'relocated', False), "trust_insurance": getattr(agent, 'trust_in_insurance', 0),
                "trust_neighbors": getattr(agent, 'trust_in_neighbors', 0),
                "memory": mem_str
            })

        df_year = pd.DataFrame([l for l in self.logs if l['year'] == year])
        stats = df_year['cumulative_state'].value_counts()
        categories = ["Do Nothing", "Only Flood Insurance", "Only House Elevation", "Both Flood Insurance and House Elevation", "Relocate"]
        stats_str = " | ".join([f"{cat}: {stats.get(cat, 0)}" for cat in categories])
        
        # Calculate Trust Stats for Observability
        avg_trust_ins = df_year['trust_insurance'].mean()
        avg_trust_nb = df_year['trust_neighbors'].mean()
        
        print(f"[Year {year}] Stats: {stats_str}")
        print(f"[Year {year}] Avg Trust: Ins={avg_trust_ins:.3f}, Nb={avg_trust_nb:.3f}")

        # Intermediate Save for Validation
        pd.DataFrame(self.logs).to_csv("simulation_log_interim.csv", index=False)

# --- 5. Survey-Based Agent Initialization ---
def load_agents_from_survey(
    survey_path: Path,
    max_agents: int = 100,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Load and initialize agents from real survey data.

    Uses the survey module to:
    1. Parse Excel survey data
    2. Classify MG/NMG status
    3. Assign flood zones based on experience
    4. Generate RCV values

    Returns dict of Agent objects compatible with the experiment runner.
    """
    from broker.modules.survey.agent_initializer import initialize_agents_from_survey
    from agents.base_agent import BaseAgent, AgentConfig

    profiles, stats = initialize_agents_from_survey(
        survey_path=survey_path,
        max_agents=max_agents,
        seed=seed,
        include_hazard=True,
        include_rcv=True
    )

    print(f"[Survey] Loaded {stats['total_agents']} agents from survey")
    print(f"[Survey] MG: {stats['mg_count']} ({stats['mg_ratio']:.1%}), NMG: {stats['nmg_count']}")
    print(f"[Survey] Owners: {stats['owner_count']}, Renters: {stats['renter_count']}")
    print(f"[Survey] With flood experience: {stats['flood_experience_count']}")

    agents = {}
    for profile in profiles:
        # Map survey profile to agent attributes
        config = AgentConfig(
            name=profile.agent_id,
            agent_type="household",
            state_params=[],
            objectives=[],
            constraints=[],
            skills=[],  # Skills are set via config.skills list below
        )

        # Calculate flood threshold from base depth
        # Higher depth = higher flood probability threshold
        base_threshold = 0.3 if profile.base_depth_m > 0 else 0.1
        if profile.flood_zone in ("deep", "very_deep", "extreme"):
            base_threshold = 0.5
        elif profile.flood_zone == "moderate":
            base_threshold = 0.4
        elif profile.flood_zone == "shallow":
            base_threshold = 0.3

        agent = BaseAgent(config)
        agent.id = profile.agent_id
        agent.agent_type = "household"
        # Set skills as string list for skill registry lookup
        agent.config.skills = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]

        # Set custom attributes from survey profile
        agent.custom_attributes = {
            # Core state
            "elevated": False,
            "has_insurance": False,
            "relocated": False,

            # Trust values (can be adjusted based on survey responses)
            "trust_in_insurance": 0.5,
            "trust_in_neighbors": 0.5,

            # Flood exposure
            "flood_threshold": base_threshold,

            # Survey-derived attributes
            "identity": profile.identity,  # "owner" or "renter"
            "is_mg": profile.is_mg,
            "group": profile.group_label,  # "MG" or "NMG"
            "family_size": profile.family_size,
            "income_bracket": profile.income_bracket,
            "income_midpoint": profile.income_midpoint,
            "flood_zone": profile.flood_zone,
            "base_depth_m": profile.base_depth_m,
            "flood_probability": profile.flood_probability,
            "building_rcv_usd": profile.building_rcv_usd,
            "contents_rcv_usd": profile.contents_rcv_usd,
            "has_children": profile.has_children,
            "has_elderly": profile.has_elderly,
            "prior_flood_experience": profile.flood_experience,
            "prior_financial_loss": profile.financial_loss,

            # Narrative for LLM context
            "narrative_persona": profile.generate_narrative_persona(),
            "flood_experience_summary": profile.generate_flood_experience_summary(),

            # Empty memory to be populated during simulation
            "memory": "",
        }

        # Copy custom attributes to agent object
        for k, v in agent.custom_attributes.items():
            setattr(agent, k, v)

        agent.flood_history = []
        agents[agent.id] = agent

    return agents


# --- 6. Main Runner ---
def run_parity_benchmark(model: str = "llama3.2:3b", years: int = 10, agents_count: int = 100, custom_output: str = None, verbose: bool = False, memory_engine_type: str = "window", workers: int = 1, window_size: int = 5, seed: Optional[int] = None, flood_mode: str = "fixed", survey_mode: bool = False, governance_mode: str = "strict", use_priority_schema: bool = False):
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

    # 2. Load Profiles (Survey Mode or CSV Mode)
    import re
    def natural_key(string_):
        """Helper for natural sorting (Agent_1, Agent_2, Agent_10...)"""
        return [int(s) if s.isdigit() else s for s in re.split(r'(\d+)', string_)]

    if survey_mode:
        # Survey-based initialization from real household data
        survey_path = base_path.parent / "multi_agent" / "input" / "initial_household data.xlsx"
        if not survey_path.exists():
            raise FileNotFoundError(
                f"Survey file not found: {survey_path}\n"
                "Survey mode requires 'initial_household data.xlsx' in examples/multi_agent/input/"
            )
        agents = load_agents_from_survey(survey_path, max_agents=agents_count, seed=seed or 42)
        print(f"[Survey Mode] Initialized {len(agents)} agents from real survey data")
    else:
        # Legacy CSV-based initialization
        from broker import load_agents_from_csv
        profiles_path = base_path / "agent_initial_profiles.csv"
        agents = load_agents_from_csv(str(profiles_path), {
            "id": "id", "elevated": "elevated", "has_insurance": "has_insurance",
            "relocated": "relocated", "trust_in_insurance": "trust_in_insurance",
            "trust_in_neighbors": "trust_in_neighbors", "flood_threshold": "flood_threshold",
            "memory": "memory"
        }, agent_type="household")

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
    sim = ResearchSimulation(agents, flood_years, flood_mode=flood_mode)
    graph = NeighborhoodGraph(list(agents.keys()), k=4)
    hub = InteractionHub(graph)
    ctx_builder = FinalContextBuilder(
        agents=agents, 
        hub=hub, 
        skill_registry=registry,
        prompt_templates={"household": household_template, "default": household_template},
        yaml_path=str(agent_config_path),
        memory_top_k=window_size
    )

    # Inject PrioritySchemaProvider if enabled (Separation for Group C)
    if use_priority_schema:
        print("[Experimental] Injecting PrioritySchemaProvider (Pillar 3)")
        # Insert at index 1 (after Dynamic, before Attribute) to prioritize in context filtering if needed
        schema_provider = PrioritySchemaProvider(FLOOD_PRIORITY_SCHEMA)
        ctx_builder.providers.insert(1, schema_provider)

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
            window_size=window_size,
            top_k_significant=2,
            consolidation_prob=0.7,
            decay_rate=0.1,
            seed=42  # For reproducibility
        )
        print(f" Using HumanCentricMemoryEngine (emotional encoding + stochastic consolidation, window={window_size})")
    elif memory_engine_type == "hierarchical":
        from broker.components.memory_engine import HierarchicalMemoryEngine
        memory_engine = HierarchicalMemoryEngine(window_size=window_size, semantic_top_k=3)
        print(f" Using HierarchicalMemoryEngine (Tiered: Core, Episodic, Semantic)")
    else:
        memory_engine = WindowMemoryEngine(window_size=window_size)
        print(f" Using WindowMemoryEngine (sliding window, size={window_size})")

    # Filter decision memories for parity with baseline
    memory_engine = DecisionFilteredMemoryEngine(memory_engine)
    
    # 5. Determine output directory (Let ExperimentBuilder handle subfolders)
    if custom_output:
        output_base = Path(custom_output)
        if not output_base.is_absolute():
            output_base = Path.cwd() / output_base
    else:
        output_base = Path(__file__).parent / "results"
    
    # Pre-calculate what ExperimentBuilder will use for cleanup
    model_folder = f"{model.replace(':','_').replace('-','_').replace('.','_')}_{governance_mode}"
    output_dir = output_base / model_folder
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- CLEANUP TRACES (Crucial for Analysis) ---
    raw_dir = output_dir / "raw"
    traces_file = raw_dir / "household_traces.jsonl"
    if traces_file.exists():
        print(f"Cleaning up old traces: {traces_file}")
        try: traces_file.unlink()
        except: pass

    # 6. Setup ExperimentBuilder and Runner
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
        .with_governance(governance_mode, agent_config_path)
        .with_output(str(output_base))
        .with_workers(workers)
        .with_seed(seed)
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
                        "yearly_decision": "relocated", # Consistent filler
                        "elevated": True,
                        "has_insurance": False,
                        "relocated": True
                    })

    
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
    parser.add_argument("--window-size", type=int, default=5, help="Size of memory window (years/events) to retain")
    parser.add_argument("--flood-mode", type=str, default="fixed", choices=["fixed", "prob"], help="Flood schedule: fixed (use flood_years.csv) or prob (use FLOOD_PROBABILITY)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility. If None, uses system time.")
    parser.add_argument("--governance-mode", type=str, default="strict", choices=["strict", "relaxed", "disabled"], help="Governance strictness profile")
    # LLM sampling parameters (None = use Ollama default)
    parser.add_argument("--temperature", type=float, default=None, help="LLM temperature (e.g., 0.8, 1.0). None=Ollama default")
    parser.add_argument("--top-p", type=float, default=None, help="Top-p sampling (e.g., 0.9, 0.95). None=Ollama default")
    parser.add_argument("--top-k", type=int, default=None, help="Top-k sampling (e.g., 40, 50). None=Ollama default")
    parser.add_argument("--use-chat-api", action="store_true", help="Use ChatOllama instead of OllamaLLM")
    parser.add_argument("--survey-mode", action="store_true",
                        help="Initialize agents from real survey data instead of CSV profiles. "
                             "Uses MG/NMG classification, flood zone assignment, and RCV generation.")
    parser.add_argument("--use-priority-schema", action="store_true", help="Enable Pillar 3: Priority Schema (Group C)")
    args = parser.parse_args()

    # Apply LLM config from command line
    from broker.utils.llm_utils import LLM_CONFIG
    if args.temperature is not None:
        LLM_CONFIG.temperature = args.temperature
    if args.top_p is not None:
        LLM_CONFIG.top_p = args.top_p
    if args.top_k is not None:
        LLM_CONFIG.top_k = args.top_k
    if args.use_chat_api:
        LLM_CONFIG.use_chat_api = True
    
    # Generate random seed if not specified
    actual_seed = args.seed if args.seed is not None else random.randint(0, 1000000)
    random.seed(actual_seed)
    
    run_parity_benchmark(
        model=args.model,
        years=args.years,
        agents_count=args.agents,
        custom_output=args.output,
        verbose=args.verbose,
        memory_engine_type=args.memory_engine,
        window_size=args.window_size,
        seed=actual_seed,
        flood_mode=args.flood_mode,
        survey_mode=args.survey_mode,
        governance_mode=args.governance_mode,
        use_priority_schema=args.use_priority_schema
    )
