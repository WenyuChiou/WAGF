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
from agents.base_agent import BaseAgent, AgentConfig, PerceptionSource
from validators import AgentValidator
from plot_results import plot_adaptation_results
from simulation.base_simulation_engine import BaseSimulationEngine
from simulation.state_manager import SharedState
from broker.context_builder import create_context_builder, BaseAgentContextBuilder

class FloodContextBuilder(BaseAgentContextBuilder):
    """Custom Context Builder to ensure exact prompt parity with Baseline."""
    
    def __init__(self, skill_registry, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skill_registry = skill_registry

    def _verbalize_trust(self, trust_value: float, category: str = "insurance") -> str:
        """Converts a float (0-1) into a natural language description."""
        if category == "insurance":
            if trust_value >= 0.8:
                return "strongly trust"
            elif trust_value >= 0.5:
                return "moderately trust"
            elif trust_value >= 0.2:
                return "have slight doubts about"
            else:
                return "deeply distrust"
        elif category == "neighbors":
            if trust_value >= 0.8:
                return "highly rely on"
            elif trust_value >= 0.5:
                return "generally trust"
            elif trust_value >= 0.2:
                return "are skeptical of"
            else:
                return "completely ignore"
        return "trust"

    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        # Get standard context
        context = super().build(agent_id, **kwargs)
        
        # No separate perception_text in baseline prompt - it's in memory

        
        # --- 1. Synthesize Baseline-Parity Attributes ---
        # (Previously done in update_agent_dynamic_context, now properly encapsulated)
        
        elevated = context.get('elevated', False)
        has_insurance = context.get('has_insurance', False)
        trust_ins = context.get('trust_in_insurance', 0.5)
        trust_neighbors = context.get('trust_in_neighbors', 0.5)
        
        # Elevation status text
        context['elevation_status_text'] = (
            "Your house is already elevated, which provides very good protection."
            if elevated else 
            "You have not elevated your home."
        )
        
        # Insurance status text
        context['insurance_status_text'] = "have" if has_insurance else "do not have"
        
        # Trust verbalization (baseline has separate descriptions)
        context['trust_ins_text'] = self._verbalize_trust(trust_ins, "insurance")
        context['trust_neighbors_text'] = self._verbalize_trust(trust_neighbors, "neighbors")
        
        # --- 2. Format Skills List ---
        # Override 'available_skills' formatting to match LLMABMPMT-Final.py
        # Baseline uses: "1. Skill (Desc)\n2. Skill (Desc)..."
        if "available_skills" in context:
            skill_ids = context["available_skills"]
            formatted_list = []
            for i, skill_id in enumerate(skill_ids, 1):
                # Look up full description
                skill_def = self.skill_registry.get_skill(skill_id)
                desc = skill_def.description if skill_def else skill_id
                
                # Baseline parity adjustment:
                # If agent is elevated, remove duplicate "elevate" option if filtered list didn't catch it
                # (Though standard logic handles filtering, the text formatting here is final)
                formatted_list.append(f"{i}. {desc}")
            
            # Hack: BaseAgentContextBuilder does ", ".join(skills).
            # We want newlines. So we join them with \n and pass as single item list.
            context["available_skills"] = ["\n".join(formatted_list)]
            context["skill_variant"] = "elevated" if elevated else "non_elevated"
            
        return context




# =============================================================================
# CONSTANTS (aligned with MCP framework / LLMABMPMT-Final.py)
# =============================================================================

PAST_EVENTS = [
    "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
    "Some residents reported delays when processing their flood insurance claims",
    "A few households in the area elevated their homes before recent floods",
    "The city previously introduced a program offering elevation support to residents",
    "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
]

MEMORY_WINDOW = 3  # Number of recent memories an agent retains
RANDOM_MEMORY_RECALL_CHANCE = 0.2  # 20% chance to recall a random past event
NUM_AGENTS = 100  # For neighbor percentage calculation
GRANT_PROBABILITY = 0.5  # 50% chance of grant being available


# =============================================================================
# SIMULATION LAYER (System-only execution)
# =============================================================================

def get_adaptation_state(agent: BaseAgent) -> str:
    """Helper: Classify adaptation state (aligned with MCP framework)."""
    # Access attributes directly from agent's dynamic state
    relocated = getattr(agent, 'relocated', False)
    elevated = getattr(agent, 'elevated', False)
    has_insurance = getattr(agent, 'has_insurance', False)
    
    if relocated:
        return "Relocate"
    elif elevated and has_insurance:
        return "Both Flood Insurance and House Elevation"
    elif elevated:
        return "Only House Elevation"
    elif has_insurance:
        return "Only Flood Insurance"
    else:
        return "Do Nothing"


class FloodSimulation(BaseSimulationEngine):
    """Flood adaptation simulation - System-only execution layer."""
    
    def __init__(self, num_agents: int = 100, seed: int = 42, flood_years: List[int] = None):
        self.seed = seed
        random.seed(seed)
        
        self.agents: Dict[str, BaseAgent] = {}
        # Use simple dict for environment state
        self.environment = {
            'year': 0, 
            'flood_event': False, 
            'flood_severity': 0.0
        }
        self.grant_available = False
        
        # Try to load from CSV files (aligned with MCP framework)
        import os
        import pandas as pd
        base_dir = Path(__file__).parent  # Local directory
        agent_file = base_dir / "agent_initial_profiles.csv"
        flood_file = base_dir / "flood_years.csv"
        
        if agent_file.exists() and flood_file.exists():
            print(f" Loading from CSV files...")
            df = pd.read_csv(agent_file)
            flood_df = pd.read_csv(flood_file)
            self.flood_years = sorted(flood_df['Flood_Years'].tolist())
            
            # Slice to requested number of agents
            df = df.head(num_agents)
            
            for _, row in df.iterrows():
                # Parse memory from CSV
                if 'memory' in row and pd.notna(row['memory']):
                    memory = row['memory'].split(' | ')
                else:
                    memory = random.sample(PAST_EVENTS, k=random.randint(2, 3))
                
                # Check mapping for keys in CSV vs FloodAgent fields
                # Mapping 'id' -> 'id'
                # Identify unknown columns for dynamic context
                known_fields = {'agent_id', 'elevated', 'has_insurance', 'relocated', 
                              'memory', 'trust_ins', 'trust_neighbors', 'flood_threshold'}
                custom_attrs = {k: v for k, v in row.to_dict().items() if k not in known_fields}

                
                # Create BaseAgent directly with config + kwargs (Composition)
                # Support both 'id' and 'agent_id' column names
                agent_id = row.get('agent_id', row.get('id', f'Agent_{_+1}'))
                
                config = AgentConfig(
                    name=agent_id,
                    agent_type="household",
                    state_params=[],
                    objectives=[],
                    constraints=[],
                    skills=[],
                    perception=[
                        PerceptionSource(source_type="environment", source_name="system", params=["flood_event", "flood_severity", "year"])
                    ]
                )
                
                agent = BaseAgent(config=config, memory=memory)
                agent.id = agent_id  # Explicitly set ID
                # Add flood-specific attributes via setattr
                agent.elevated = bool(row.get('elevated', False))
                agent.has_insurance = bool(row.get('has_insurance', False))
                agent.relocated = bool(row.get('relocated', False))
                agent.trust_in_insurance = float(row.get('trust_in_insurance', row.get('trust_ins', 0.3)))
                agent.trust_in_neighbors = float(row.get('trust_in_neighbors', row.get('trust_neighbors', 0.4)))
                agent.flood_threshold = float(row.get('flood_threshold', 0.5))
                agent.custom_attributes = custom_attrs
                self.agents[agent_id] = agent
            print(f" Loaded {len(self.agents)} agents, flood years: {self.flood_years}")

        else:
            print(f" No CSV files found, using random initialization")
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
    
    def advance_step(self) -> Any:
        """Satisfy BaseSimulationEngine interface."""
        return self.advance_year()

    def advance_year(self) -> FloodEnvironment:
        self.environment['year'] += 1
        self.environment['flood_event'] = self.environment['year'] in self.flood_years
        if self.environment['flood_event']:
            self.environment['flood_severity'] = random.uniform(0.5, 1.0)
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
            agent.has_insurance = False  # Insurance expires if not renewed
            state_changes["has_insurance"] = False
        elif skill == "relocate":
            if not agent.relocated:
                agent.relocated = True
                state_changes["relocated"] = True
        elif skill == "do_nothing":
            # Insurance expires if not renewed
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

# Helper functions moved to FloodContextBuilder



# Framework's GenericAuditWriter is used instead.


# =============================================================================
# LLM INTERFACE
# =============================================================================

def create_llm_invoke(model: str):
    """Create LLM invoke function."""
    if model.lower() == "mock":
        import random as _mock_random
        def mock_invoke(p):
            # Randomly return different threat levels to test validation
            threat_level = _mock_random.choice(["Low", "Medium", "High"])
            coping_level = _mock_random.choice(["Low", "Medium", "High"])
            
            # If High threat, sometimes (but not always) choose do_nothing -> should trigger validation
            if threat_level == "High":
                decision = _mock_random.choice(["do_nothing", "buy_insurance", "elevate_house"])
            elif threat_level == "Low":
                decision = _mock_random.choice(["do_nothing", "relocate"])  # relocate while Low -> should trigger
            else:
                decision = _mock_random.choice(["do_nothing", "buy_insurance"])
            
            return f"""Threat Appraisal: {threat_level} because I feel {threat_level.lower()} threat from flood risks.
Coping Appraisal: {coping_level} because I feel {coping_level.lower()} ability to cope.
Final Decision: {decision}"""
        return mock_invoke
    
    try:
        from langchain_ollama import ChatOllama
        # Remove temperature=0.3 to match Baseline (which uses model default)
        # Increase num_predict for DeepSeek models to accommodate <think> tags
        num_predict = 2048 if "deepseek" in model.lower() or "gpt-oss" in model.lower() else 512
        llm = ChatOllama(model=model, num_predict=num_predict)
        
        def invoke(prompt: str) -> str:
            response = llm.invoke(prompt)
            return response.content
        
        return invoke
    except (ImportError, Exception) as e:
        print(f"Warning: Falling back to mock LLM due to: {e}")
        return lambda p: """Threat Appraisal: Medium because I feel moderate threat.
Coping Appraisal: Medium because I can manage.
Final Decision: do_nothing"""


# =============================================================================
# GOVERNANCE LAYER SETUP
# =============================================================================

def setup_governance(
    simulation: FloodSimulation,
    context_builder: FloodContextBuilder,
    model_name: str,
    output_dir: Path,
    skill_registry: Optional[SkillRegistry] = None
) -> SkillBrokerEngine:
    """
    Setup the Governance Layer (Skill Broker).
    
    Layers:
    1. The Simulation (World)
    2. The Experiment Loop (Control)
    3. The Governance Layer (Broker) - Added here
    """
    # 1. Skill Registry (Loads domains-specific skills)
    if skill_registry is None:
        skill_registry = SkillRegistry()
        registry_path = Path(__file__).parent / "skill_registry.yaml"
        skill_registry.register_from_yaml(registry_path)
        print(f" Loaded Skill Registry from {registry_path.name}")
    else:
        print(f" Using provided Skill Registry")
    
    # 2. Local Configuration (Experiment-Specific Settings)
    # This separates the experiment's domain rules from the global default.
    local_config_path = Path(__file__).parent / "agent_types.yaml"
    print(f" Loaded Agent Config from {local_config_path.name}")
    
    # Resetting config singleton to ensure local config is loaded (crucial if running in shared process)
    # In a fresh script run, this is safe.
    from broker.agent_config import AgentTypeConfig
    AgentTypeConfig._instance = None
    
    # Detect DeepSeek preprocessor
    preprocessor = None
    if "deepseek" in model_name.lower():
        from broker.model_adapter import deepseek_preprocessor
        preprocessor = deepseek_preprocessor
        print(f" Using DeepSeek Preprocessor for {model_name}")

    # 3. Model Adapter (Interprets LLM output using local config)
    model_adapter = UnifiedAdapter(
        agent_type="household",
        preprocessor=preprocessor,
        config_path=str(local_config_path)
    )
    
    # 4. Validator (Enforces coherence & constraints from local config)
    validators = AgentValidator(config_path=str(local_config_path))
    
    # 5. Audit Writer (Logs traces - configurable from YAML)
    # Load audit settings from config
    agent_config_obj = AgentTypeConfig.load(str(local_config_path))
    household_cfg = agent_config_obj.get("household") or {}
    audit_cfg = household_cfg.get("audit", {})
    log_prompt = audit_cfg.get("log_prompt", True)
    
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
        validators=[validators],
        simulation_engine=simulation,
        context_builder=context_builder,
        audit_writer=audit_writer,
        max_retries=2,
        log_prompt=log_prompt
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
    
    # Initialize Skill Registry first (needed for Context Builder)
    skill_registry = SkillRegistry()
    registry_path = Path(__file__).parent / "skill_registry.yaml"
    skill_registry.register_from_yaml(registry_path)
    print(f" Loaded Skill Registry from {registry_path.name}")

    # Load config for Context Builder
    from broker.agent_config import AgentTypeConfig
    AgentTypeConfig._instance = None # Ensure fresh load
    config_path = Path(__file__).parent / "agent_types.yaml"
    full_config = AgentTypeConfig.load(str(config_path))
    
    # Use Custom FloodContextBuilder for Baseline Parity
    household_config = full_config.get("household")  # AgentTypeConfig handles defaults
    prompt_template = household_config.get("prompt_template", "")
    if not prompt_template:
        print(" WARNING: prompt_template is EMPTY!")
    else:
        print(f" Loaded prompt_template ({len(prompt_template)} chars)")
    
    # Instantiate custom builder manually (bypassing factory to inject skill_registry)
    # Note: FloodContextBuilder inherits from BaseAgentContextBuilder so API matches
    context_builder = FloodContextBuilder(
        skill_registry=skill_registry,
        agents=sim.agents,
        environment=sim.environment.to_dict() if hasattr(sim.environment, 'to_dict') else {},
        prompt_templates={"household": prompt_template, "default": prompt_template}  # Support both agent_type values
    )
    
    # Initialize output directory
    output_dir = Path(args.output_dir) / args.model.replace(":", "_")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize Governance Layer (Broker)
    broker = setup_governance(sim, context_builder, args.model, output_dir, skill_registry=skill_registry)
    
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
        if env['flood_event']:
            print(" FLOOD EVENT!")
        
        active_agents = [a for a in sim.agents.values() if not getattr(a, 'relocated', False)]
        total_elevated = sum(1 for a in active_agents if getattr(a, 'elevated', False))
        total_relocated = NUM_AGENTS - len(active_agents)
        print(f"Active agents: {len(active_agents)}")
        
        # PHASE 1: Update memory for all agents BEFORE decision making (aligned with MCP)
        for agent in active_agents:
            # 1. Flood exposure memory (detailed like MCP)
            if env['flood_event'] and not agent.elevated:
                if random.random() < agent.flood_threshold:
                    agent.memory.append(f"Year {year}: Got flooded with $10,000 damage on my house.")
                else:
                    agent.memory.append(f"Year {year}: A flood occurred, but my house was spared damage.")
            elif env['flood_event'] and agent.elevated:
                if random.random() < agent.flood_threshold:
                    agent.memory.append(f"Year {year}: Despite elevation, the flood was severe enough to cause damage.")
                else:
                    agent.memory.append(f"Year {year}: A flood occurred, but my house was protected by its elevation.")
            elif not env['flood_event']:
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
        
        # PHASE 2: Process decisions for all agents
        for agent in active_agents:
            step_counter += 1
            
            # Process through skill broker
            result = broker.process_step(
                agent_id=agent.id,
                step_id=step_counter,
                run_id=run_id,
                seed=args.seed + step_counter,
                llm_invoke=llm_invoke,
                agent_type="household"
            )
            
            # Store skill for persistent logging in PHASE 3
            agent.last_skill = result.approved_skill.skill_name if result.approved_skill else None

        # PHASE 3: Log all agents per year (including those who already relocated)
        # This ensuring the stacked bar charts always sum to the same total agent count.
        for agent_id, agent in sim.agents.items():
            log_context = {
                "agent_id": agent.id,
                "year": year,
                "decision": get_adaptation_state(agent),  # Cumulative adaptation state
                "flood": env['flood_event'], 
                "cumulative_state": get_adaptation_state(agent) if agent else "Do Nothing",
                "elevated": getattr(agent, 'elevated', False),
                "has_insurance": getattr(agent, 'has_insurance', False),
                "relocated": getattr(agent, 'relocated', False),
                "raw_skill": getattr(agent, 'last_skill', None), # We'll need to store this on agent
                "outcome": "LOGGED",
            }

            # Inject dynamic custom attributes (e.g. income from CSV)
            if agent and hasattr(agent, 'custom_attributes') and agent.custom_attributes:
                log_context.update(agent.custom_attributes)

            logs.append(log_context)
        
        # Save log after each year (aligned with original LLMABMPMT-Final.py)
        import pandas as pd
        df_log = pd.DataFrame(logs)
        df_log.to_csv(output_dir / "simulation_log.csv", index=False)
        
        # Calculate and print yearly stats
        current_year_df = df_log[df_log['year'] == year]
        stats = current_year_df['cumulative_state'].value_counts()
        stats_str = " | ".join([f"{k}: {v}" for k, v in stats.items()])
        print(f"[Year {year}] Stats: {stats_str}")
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
    print(" Generating comparison results plot...")
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