"""
Run Skill-Governed Flood Adaptation Experiment (v2 - Framework Edition)

This version uses governed_broker_framework instead of local copies.

This experiment demonstrates the Skill-Governed Architecture where:
- LLM agents propose SKILLS (abstract behaviors), not actions/tools
- Broker validates skills through SkillRegistry and validators
- Execution happens ONLY through simulation engine (system-only)
- MCP (if used) is strictly execution substrate, not governance

Three-layer architecture preserved:
  LLM Agent → Governed Broker → Simulation/World
"""
import sys
import json
import argparse
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# Add governed_broker_framework to path (this file is inside the framework)
FRAMEWORK_PATH = Path(__file__).parent.parent.parent
sys.path.insert(0, str(FRAMEWORK_PATH))

# Import from framework (direct import, no package prefix needed since FRAMEWORK_PATH is in sys.path)
from broker.skill_types import SkillProposal, ApprovedSkill, ExecutionResult, SkillOutcome
from broker.skill_registry import SkillRegistry
from broker.model_adapter import UnifiedAdapter
from broker.skill_broker_engine import SkillBrokerEngine
from broker.audit_writer import GenericAuditWriter as SkillAuditWriter, AuditConfig as GenericAuditConfig
from validators import AgentValidator
from plot_results import plot_adaptation_results




# =============================================================================
# CONSTANTS (loaded from config or defaults)
# =============================================================================

# These will be loaded from agent_types.yaml at runtime
# Defaults are provided for standalone testing
DEFAULT_PAST_EVENTS = [
    "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
    "Some residents reported delays when processing their flood insurance claims",
    "A few households in the area elevated their homes before recent floods",
    "The city previously introduced a program offering elevation support to residents",
    "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
]

DEFAULT_MEMORY_WINDOW = 5
DEFAULT_RANDOM_MEMORY_RECALL_CHANCE = 0.2
DEFAULT_NUM_AGENTS = 100
DEFAULT_GRANT_PROBABILITY = 0.5

def load_simulation_config():
    """Load simulation constants from local agent_types.yaml"""
    import yaml
    config_path = Path(__file__).parent / "agent_types.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        household = config.get("household", {})
        sim_cfg = household.get("simulation", {})
        return {
            "PAST_EVENTS": household.get("past_events", DEFAULT_PAST_EVENTS),
            "MEMORY_WINDOW": sim_cfg.get("memory_window", DEFAULT_MEMORY_WINDOW),
            "RANDOM_MEMORY_RECALL_CHANCE": sim_cfg.get("random_memory_recall_chance", DEFAULT_RANDOM_MEMORY_RECALL_CHANCE),
            "NUM_AGENTS": sim_cfg.get("num_agents_default", DEFAULT_NUM_AGENTS),
            "GRANT_PROBABILITY": sim_cfg.get("grant_probability", DEFAULT_GRANT_PROBABILITY)
        }
    return {
        "PAST_EVENTS": DEFAULT_PAST_EVENTS,
        "MEMORY_WINDOW": DEFAULT_MEMORY_WINDOW,
        "RANDOM_MEMORY_RECALL_CHANCE": DEFAULT_RANDOM_MEMORY_RECALL_CHANCE,
        "NUM_AGENTS": DEFAULT_NUM_AGENTS,
        "GRANT_PROBABILITY": DEFAULT_GRANT_PROBABILITY
    }

# Load config at module level
_SIM_CONFIG = load_simulation_config()
PAST_EVENTS = _SIM_CONFIG["PAST_EVENTS"]
MEMORY_WINDOW = _SIM_CONFIG["MEMORY_WINDOW"]
RANDOM_MEMORY_RECALL_CHANCE = _SIM_CONFIG["RANDOM_MEMORY_RECALL_CHANCE"]
NUM_AGENTS = _SIM_CONFIG["NUM_AGENTS"]
GRANT_PROBABILITY = _SIM_CONFIG["GRANT_PROBABILITY"]


# =============================================================================
# SIMULATION LAYER (System-only execution)
# =============================================================================

@dataclass
class FloodAgent:
    """Agent in flood adaptation simulation."""
    id: str
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    memory: List[str] = field(default_factory=list)
    trust_in_insurance: float = 0.3
    trust_in_neighbors: float = 0.4
    flood_threshold: float = 0.5
    
    @property
    def is_active(self) -> bool:
        return not self.relocated
    
    def get_adaptation_state(self) -> str:
        """Classify adaptation state (aligned with MCP framework)."""
        if self.relocated:
            return "Relocate"
        elif self.elevated and self.has_insurance:
            return "Both Flood Insurance and House Elevation"
        elif self.elevated:
            return "Only House Elevation"
        elif self.has_insurance:
            return "Only Flood Insurance"
        else:
            return "Do Nothing"


@dataclass
class FloodEnvironment:
    """Environment state."""
    year: int = 0
    flood_event: bool = False
    flood_severity: float = 0.0


class FloodSimulation:
    """Flood adaptation simulation - System-only execution layer."""
    
    def __init__(self, num_agents: int = 100, seed: int = 42, flood_years: List[int] = None):
        self.seed = seed
        random.seed(seed)
        
        self.agents: Dict[str, FloodAgent] = {}
        self.environment = FloodEnvironment()
        self.grant_available = False
        
        # Try to load from CSV files (aligned with MCP framework)
        import os
        import pandas as pd
        base_dir = Path(__file__).parent  # Local directory
        agent_file = base_dir / "agent_initial_profiles.csv"
        flood_file = base_dir / "flood_years.csv"
        
        if agent_file.exists() and flood_file.exists():
            print(f"📂 Loading from CSV files...")
            df = pd.read_csv(agent_file)
            flood_df = pd.read_csv(flood_file)
            self.flood_years = sorted(flood_df['Flood_Years'].tolist())
            
            for _, row in df.iterrows():
                # Parse memory from CSV
                if 'memory' in row and pd.notna(row['memory']):
                    memory = row['memory'].split(' | ')
                else:
                    memory = random.sample(PAST_EVENTS, k=random.randint(2, 3))
                
                # Check mapping for keys in CSV vs FloodAgent fields
                # Mapping 'id' -> 'id'
                # Defaulting other fields if missing
                
                self.agents[row['agent_id']] = FloodAgent(
                    id=row['agent_id'],
                    elevated=bool(row.get('elevated', False)),
                    has_insurance=bool(row.get('has_insurance', False)),
                    relocated=bool(row.get('relocated', False)),
                    memory=memory,
                    trust_in_insurance=float(row.get('trust_ins', 0.3)),
                    trust_in_neighbors=float(row.get('trust_neighbors', 0.4)),
                    flood_threshold=float(row.get('flood_threshold', 0.5))
                )
            print(f"✅ Loaded {len(self.agents)} agents, flood years: {self.flood_years}")

        else:
            print(f"📂 No CSV files found, using random initialization")
            for i in range(1, num_agents + 1):
                initial_memory = random.sample(PAST_EVENTS, k=random.randint(2, 3))
                self.agents[f"Agent_{i}"] = FloodAgent(
                    id=f"Agent_{i}",
                    memory=initial_memory,
                    has_insurance=random.choice([True, False]),
                    trust_in_insurance=round(random.uniform(0.2, 0.5), 2),
                    trust_in_neighbors=round(random.uniform(0.35, 0.55), 2),
                    flood_threshold=round(random.uniform(0.4, 0.9), 2)
                )
            self.flood_years = flood_years or [3, 4, 9]
    
    def advance_year(self) -> FloodEnvironment:
        self.environment.year += 1
        self.environment.flood_event = self.environment.year in self.flood_years
        if self.environment.flood_event:
            self.environment.flood_severity = random.uniform(0.5, 1.0)
        return self.environment
    
    def execute_skill(self, approved_skill: ApprovedSkill) -> ExecutionResult:
        """
        Execute an approved skill - SYSTEM ONLY.
        
        This is the ONLY place where state changes happen.
        LLM agents cannot call this directly.
        """
        agent = self.agents.get(approved_skill.agent_id)
        if not agent or agent.relocated:
            return ExecutionResult(success=False, error="Agent not found or relocated")
        
        state_changes = {}
        skill = approved_skill.skill_name
        
        if skill == "buy_insurance":
            agent.has_insurance = True
            state_changes["has_insurance"] = True
        elif skill == "elevate_house":
            if not agent.elevated:
                agent.elevated = True
                state_changes["elevated"] = True
                # --- 80% RISK REDUCTION due to house elevation (Restored from Legacy) ---
                agent.flood_threshold = round(agent.flood_threshold * 0.2, 2)
                agent.flood_threshold = max(0.001, agent.flood_threshold)
            # Insurance expires if choosing elevation
            agent.has_insurance = False
            state_changes["has_insurance"] = False
        elif skill == "relocate":
            if not agent.relocated:
                agent.relocated = True
                state_changes["relocated"] = True
        elif skill == "do_nothing":
            # Insurance expires if not renewed (original NSF logic)
            agent.has_insurance = False
            state_changes["has_insurance"] = False
        
        return ExecutionResult(success=True, state_changes=state_changes)

    
    def get_community_action_rate(self) -> float:
        total = len(self.agents)
        actions = sum(1 for a in self.agents.values() if a.elevated or a.relocated)
        return actions / total if total > 0 else 0


# =============================================================================
# CONTEXT BUILDER (Read-only observation)
# =============================================================================

class FloodContextBuilder:
    """Builds bounded context for LLM - READ ONLY."""
    
    def __init__(self, simulation: FloodSimulation, agent_config: Dict[str, Any] = None):
        self.simulation = simulation
        self.agent_config = agent_config or {}
        
        # Load template from local config
        from broker.agent_config import AgentTypeConfig
        config_path = Path(__file__).parent / "agent_types.yaml"
        self.config_obj = AgentTypeConfig.load(str(config_path))
        self.template = self.config_obj.get_prompt_template("household")
        
        # Fallback if config fails
        if not self.template:
            print("WARNING: using fallback template in FloodContextBuilder")
            self.template = "CONTEXT:{state} ACT:{skills} DECIDE:[action]"
    
    def build(self, agent_id: str) -> Dict[str, Any]:
        """Build read-only context for agent."""
        agent = self.simulation.agents.get(agent_id)
        if not agent:
            return {}
        
        # Mock demographic data for V2-2 (Clean) experiment compatibility
        # In a real scenario, these would come from Agent attributes
        import random
        r = random.Random(agent_id) # Deterministic mock based on ID
        tenure = r.randint(2, 30)
        income = r.randint(40000, 120000)
        mg = r.randint(500, 3000)
        
        return {
            "agent_id": agent_id,
            "agent_name": agent_id, # explicit name
            "elevated": agent.elevated,
            "has_insurance": agent.has_insurance,
            "trust_in_insurance": agent.trust_in_insurance,
            "trust_in_neighbors": agent.trust_in_neighbors,
            "memory": agent.memory.copy(),
            "flood": self.simulation.environment.flood_event, # Boolean
            "year": self.simulation.environment.year,
            "subsidy_rate": 0.0, # V2-2 has no subsidy mechanism active?
            "premium_rate": 0.0, # Mock
            "cumulative_state": agent.get_adaptation_state(), # For audit mapping
            # Mock demographics
            "tenure": tenure,
            "income": income,
            "mg": mg
        }
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into LLM prompt using YAML template."""
        
        # PREPARE VARIABLES FOR TEMPLATE
        
        # 1. Perception/Observations
        obs_lines = []
        obs_lines.append(f"Year {context.get('year')}")
        if context.get('flood'):
            obs_lines.append("CRITICAL: A flood event occurred this year!")
        else:
            obs_lines.append("No flood occurred this year.")
        
        trust_ins = context.get("trust_in_insurance", 0.3)
        trust_neighbors = context.get("trust_in_neighbors", 0.4)
        obs_lines.append(f"Trust in Insurance: {trust_ins:.2f}")
        obs_lines.append(f"Trust in Neighbors: {trust_neighbors:.2f}")
        
        perception_str = "\n".join(obs_lines)
        
        # 2. Memory
        mems = context.get("memory", [])
        memory_str = "\n".join(f"- {m}" for m in mems) if mems else "No usage memory."
        
        # 3. Actions/Skills
        # Helper to format available choices
        skills_str = """
- buy_insurance (FI): Purchase flood insurance
- elevate_house (HE): Elevate house structure
- relocate (RL): Relocate to safer area
- do_nothing (DN): Take no action
"""
        # Filter based on state? e.g. if Elevated, can't Elevate
        if context.get("elevated"):
             skills_str = skills_str.replace("- elevate_house (HE): Elevate house structure\n", "")
        
        # 4. Fill Template
        # Ensure all keys in template are present
        params = {
            "agent_name": context.get("agent_name"),
            "tenure": context.get("tenure"),
            "income": context.get("income"),
            "mg": context.get("mg"),
            "elevated": str(context.get("elevated")),
            "has_insurance": str(context.get("has_insurance")),
            "perception": perception_str,
            "memory": memory_str,
            "flood": str(context.get("flood")),
            "subsidy_rate": context.get("subsidy_rate"),
            "premium_rate": context.get("premium_rate"),
            "skills": skills_str
        }
        
        return self.template.format(**params)
    
    def _verbalize_trust(self, trust_value: float, trust_type: str) -> str:
        """Converts a float (0-1) into a natural language description (aligned with MCP)."""
        if trust_type == "insurance":
            if trust_value >= 0.8:
                return "strongly trust"
            elif trust_value >= 0.5:
                return "moderately trust"
            elif trust_value >= 0.2:
                return "have slight doubts about"
            else:
                return "deeply distrust"
        else:
            if trust_value >= 0.8:
                return "highly rely on"
            elif trust_value >= 0.5:
                return "generally trust"
            elif trust_value >= 0.2:
                return "are skeptical of"
            else:
                return "completely ignore"
    
    def get_memory(self, agent_id: str) -> List[str]:
        agent = self.simulation.agents.get(agent_id)
        return agent.memory.copy() if agent else []


# Framework's GenericAuditWriter is used instead.


# =============================================================================
# LLM INTERFACE
# =============================================================================

def create_llm_invoke(model: str):
    """Create LLM invoke function."""
    if model.lower() == "mock":
        return lambda p: """Threat Appraisal: I feel moderately threatened by potential flood risks in my area.
Coping Appraisal: I believe I can manage by monitoring the situation without immediate action.
Final Decision: "do_nothing\""""
    
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=model, temperature=0.3, num_predict=256)
        
        def invoke(prompt: str) -> str:
            response = llm.invoke(prompt)
            return response.content
        
        return invoke
    except (ImportError, Exception) as e:
        print(f"Warning: Falling back to mock LLM due to: {e}")
        return lambda p: """Threat Appraisal: I feel moderately threatened by potential flood risks.
Coping Appraisal: I can manage by monitoring the situation.
Final Decision: "do_nothing\""""


# =============================================================================
# GOVERNANCE LAYER SETUP
# =============================================================================

def setup_governance(
    simulation: FloodSimulation,
    context_builder: FloodContextBuilder,
    model_name: str,
    output_dir: Path
) -> SkillBrokerEngine:
    """
    Initialize the Governance Layer (Registry, Adapter, Validators, Audit).
    
    This function encapsulates all "Governed Broker" settings, separating them from:
    1. The Simulation (World)
    2. The Experiment Loop (Control)
    """
    # 1. Skill Registry (Loads domains-specific skills)
    skill_registry = SkillRegistry()
    registry_path = Path(__file__).parent / "skill_registry.yaml"
    skill_registry.register_from_yaml(registry_path)
    print(f"✅ Loaded Skill Registry from {registry_path.name}")
    
    # 2. Local Configuration (Experiment-Specific Settings)
    # This separates the experiment's domain rules from the global default.
    local_config_path = Path(__file__).parent / "agent_types.yaml"
    print(f"✅ Loaded Agent Config from {local_config_path.name}")
    
    # Resetting config singleton to ensure local config is loaded (crucial if running in shared process)
    # In a fresh script run, this is safe.
    from broker.agent_config import AgentTypeConfig
    AgentTypeConfig._instance = None
    
    # 3. Model Adapter (Interprets LLM output using local config)
    model_adapter = UnifiedAdapter(
        agent_type="household",
        config_path=str(local_config_path)
    )
    
    # 4. Validator (Enforces coherence & constraints from local config)
    validators = AgentValidator(config_path=str(local_config_path))
    
    # 5. Audit Writer (Logs traces - configurable from YAML)
    # Load audit settings from config
    agent_config_obj = AgentTypeConfig.load(str(local_config_path))
    household_cfg = agent_config_obj.get("household") or {}
    audit_cfg = household_cfg.get("audit", {})
    
    # Build output path: base_output_dir / model_name
    base_output = audit_cfg.get("output_dir", "results")
    final_output = Path(output_dir) if output_dir else Path(base_output) / model_name.replace(":", "_")
    
    audit_config = GenericAuditConfig(
        output_dir=str(final_output),
        experiment_name=audit_cfg.get("experiment_name", f"v2_{model_name.replace(':', '_')}")
    )
    audit_writer = SkillAuditWriter(audit_config)
    
    # 5. Broker Engine (Orchestrates the layers)
    broker = SkillBrokerEngine(
        skill_registry=skill_registry,
        model_adapter=model_adapter,
        validator=validators,
        simulation_engine=simulation,
        context_builder=context_builder,
        audit_writer=audit_writer,
        max_retries=2
    )
    
    return broker


# =============================================================================
# MAIN EXPERIMENT
# =============================================================================

def run_experiment(args):
    """Run the skill-governed flood adaptation experiment."""
    print("=" * 60)
    print("Skill-Governed Flood Adaptation Experiment")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Agents: {args.num_agents}, Years: {args.num_years}")
    print("=" * 60)
    
    # Initialize simulation (World Layer)
    sim = FloodSimulation(num_agents=args.num_agents, seed=args.seed)
    
    # Load config for Context Builder
    from broker.agent_config import AgentTypeConfig
    AgentTypeConfig._instance = None # Ensure fresh load
    config_path = Path(__file__).parent / "agent_types.yaml"
    full_config = AgentTypeConfig.load(str(config_path))
    # We pass the household config dict
    context_builder = FloodContextBuilder(sim, agent_config=full_config.get("household")) # Observation Layer
    
    # Initialize output directory
    output_dir = Path(args.output_dir) / args.model.replace(":", "_")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize Governance Layer (Broker)
    broker = setup_governance(sim, context_builder, args.model, output_dir)
    
    # LLM
    llm_invoke = create_llm_invoke(args.model)
    
    run_id = f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    step_counter = 0
    logs = []
    
    # Main simulation loop
    for year in range(1, args.num_years + 1):
        env = sim.advance_year()
        
        # Determine grant availability (aligned with MCP)
        sim.grant_available = random.random() < GRANT_PROBABILITY
        
        print(f"\n--- Year {year} ---")
        if env.flood_event:
            print("🌊 FLOOD EVENT!")
        
        active_agents = [a for a in sim.agents.values() if a.is_active]
        total_elevated = sum(1 for a in active_agents if a.elevated)
        total_relocated = NUM_AGENTS - len(active_agents)
        print(f"Active agents: {len(active_agents)}")
        
        # PHASE 1: Update memory for all agents BEFORE decision making (aligned with MCP)
        for agent in active_agents:
            # 1. Flood exposure memory (detailed like MCP)
            if env.flood_event and not agent.elevated:
                if random.random() < agent.flood_threshold:
                    agent.memory.append(f"Year {year}: Got flooded with $10,000 damage on my house.")
                else:
                    agent.memory.append(f"Year {year}: A flood occurred, but my house was spared damage.")
            elif env.flood_event and agent.elevated:
                if random.random() < agent.flood_threshold:
                    agent.memory.append(f"Year {year}: Despite elevation, the flood was severe enough to cause damage.")
                else:
                    agent.memory.append(f"Year {year}: A flood occurred, but my house was protected by its elevation.")
            elif not env.flood_event:
                agent.memory.append(f"Year {year}: No flood occurred this year.")
            
            # 2. Grant availability memory
            if sim.grant_available:
                agent.memory.append(f"Year {year}: Elevation grants are available.")
            
            # 3. Neighborhood stats memory
            num_neighbors = NUM_AGENTS - 1
            if num_neighbors > 0:
                elevated_pct = round(((total_elevated - (1 if agent.elevated else 0)) / num_neighbors) * 100)
                agent.memory.append(f"Year {year}: I observe {elevated_pct}% of my neighbors have elevated homes.")
                relocated_pct = round((total_relocated / num_neighbors) * 100)
                agent.memory.append(f"Year {year}: I observe {relocated_pct}% of my neighbors have relocated.")
            
            # 4. Stochastic memory recall
            if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
                agent.memory.append(f"Suddenly recalled: '{random.choice(PAST_EVENTS)}'.")
            
            # 5. Trim memory to window
            agent.memory = agent.memory[-MEMORY_WINDOW:]
            
            # 6. Trust Update Logic (Legacy restoration)
            # Insurance Trust
            if agent.has_insurance:
                if env.flood_event and not agent.elevated: # Insured + Flooded (Hassle)
                    agent.trust_in_insurance = max(0.0, agent.trust_in_insurance - 0.10)
                elif not env.flood_event: # Insured + Safe (Peace of mind)
                    agent.trust_in_insurance = min(1.0, agent.trust_in_insurance + 0.02)
            else:
                if env.flood_event: # Not Insured + Flooded (Regret/Hard Lesson)
                    # Note: Legacy logic said +0.05 (maybe realizing value), or -0.05? 
                    # YAML said: not_insured_flooded: delta: +0.05. Using legacy rule.
                    agent.trust_in_insurance = min(1.0, agent.trust_in_insurance + 0.05)
                else: # Not Insured + Safe (Gambler's Reward)
                    agent.trust_in_insurance = max(0.0, agent.trust_in_insurance - 0.02)
            
            # Neighbor Trust (Social Proof)
            if num_neighbors > 0:
                elevated_pct = (total_elevated - (1 if agent.elevated else 0)) / num_neighbors
                if elevated_pct > 0.3: # High action threshold
                    agent.trust_in_neighbors = min(1.0, agent.trust_in_neighbors + 0.04)
                elif env.flood_event and elevated_pct < 0.1: # Low action during flood
                    agent.trust_in_neighbors = max(0.0, agent.trust_in_neighbors - 0.05)
                else: # Default decay
                    agent.trust_in_neighbors = max(0.0, agent.trust_in_neighbors - 0.01)
        
        # PHASE 2: Process decisions for active agents
        agent_actions = {} # Track this year's action for logging
        for agent in active_agents:
            step_counter += 1
            
            # Process through skill broker
            result = broker.process_step(
                agent_id=agent.id,
                step_id=step_counter,
                run_id=run_id,
                seed=args.seed + step_counter,
                llm_invoke=llm_invoke
            )
            agent_actions[agent.id] = result.approved_skill.skill_name if result.approved_skill else "unknown"
        
        # Log ALL agents (including relocated ones) after decisions
        for agent in sim.agents.values():
            logs.append({
                "agent_id": agent.id,
                "year": year,
                "current_action": agent_actions.get(agent.id, "none"), # Action taken this year
                "cumulative_state": agent.get_adaptation_state(), # Resulting total state
                "elevated": agent.elevated,
                "has_insurance": agent.has_insurance,
                "relocated": agent.relocated,
                "outcome": "SAMPLED"
            })
        
        # Save log after each year (aligned with original LLMABMPMT-Final.py)
        import pandas as pd
        pd.DataFrame(logs).to_csv(output_dir / "simulation_log.csv", index=False)
        print(f"[Year {year}] Log saved with {len(logs)} entries")
    
    # Finalize
    if broker.audit_writer:
        summary = broker.audit_writer.finalize()
    else:
        summary = {}
    broker_stats = broker.get_stats()
    
    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)
    print(f"Total decisions: {broker_stats['total']}")
    print(f"First-pass approved: {broker_stats['approved']}")
    print(f"Retry success: {broker_stats['retry_success']}")
    print(f"Rejected/Uncertain: {broker_stats['rejected']}")
    print(f"Approval rate: {broker_stats['approval_rate']}")
    
    # Save logs
    import pandas as pd
    csv_path = output_dir / "simulation_log.csv"
    pd.DataFrame(logs).to_csv(csv_path, index=False)
    print(f"\nResults saved to: {output_dir}")
    
    # Generate Comparison Plot (Reproducibility)
    print("📊 Generating comparison results plot...")
    plot_adaptation_results(csv_path, output_dir)
    
    return broker_stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skill-Governed Flood Adaptation")
    parser.add_argument("--model", default="llama3.2:3b", help="LLM model")
    parser.add_argument("--num-agents", type=int, default=100)
    parser.add_argument("--num-years", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="results")
    
    args = parser.parse_args()
    run_experiment(args)
