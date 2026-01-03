"""
Run Skill-Governed Flood Adaptation Example

This example demonstrates the Skill-Governed Architecture (v0.2) where:
- LLM agents propose SKILLS (abstract behaviors), not actions/tools
- Broker validates skills through SkillRegistry and validators
- Execution happens ONLY through simulation engine (system-only)

This example is aligned with the latest MCP framework updates.
"""
import sys
import json
import argparse
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# Add parent path to allow importing governed_broker_framework if running from examples
# Alternatively, install the package with pip install -e .
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from governed_broker_framework.broker.skill_types import ApprovedSkill, ExecutionResult
from governed_broker_framework.broker.skill_registry import create_flood_adaptation_registry
from governed_broker_framework.broker.model_adapter import get_adapter
from governed_broker_framework.broker.skill_broker_engine import SkillBrokerEngine
from governed_broker_framework.broker.audit_writer import AuditWriter, AuditConfig
from governed_broker_framework.validators.skill_validators import create_default_validators

# =============================================================================
# CONSTANTS
# =============================================================================

PAST_EVENTS = [
    "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
    "Some residents reported delays when processing their flood insurance claims",
    "A few households in the area elevated their homes before recent floods",
    "The city previously introduced a program offering elevation support to residents",
    "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
]

MEMORY_WINDOW = 5
RANDOM_MEMORY_RECALL_CHANCE = 0.2
NUM_AGENTS = 100
GRANT_PROBABILITY = 0.5


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
        
        # Try to load from CSV files (relative to script or project root)
        # Assuming run from examples/flood_adaptation or root
        import pandas as pd
        
        # Look for CSVs in likely locations
        possible_paths = [
            Path(__file__).parent,
            Path(__file__).parent.parent.parent
        ]
        
        agent_file = None
        flood_file = None
        
        for p in possible_paths:
            if (p / "agent_initial_profiles.csv").exists():
                agent_file = p / "agent_initial_profiles.csv"
                flood_file = p / "flood_years.csv"
                break
        
        if agent_file and agent_file.exists() and flood_file.exists():
            print(f"📂 Loading from CSV files: {agent_file}")
            df = pd.read_csv(agent_file)
            flood_df = pd.read_csv(flood_file)
            self.flood_years = sorted(flood_df['Flood_Years'].tolist())
            
            for _, row in df.iterrows():
                if 'memory' in row and pd.notna(row['memory']):
                    memory = row['memory'].split(' | ')
                else:
                    memory = random.sample(PAST_EVENTS, k=random.randint(2, 3))
                
                self.agents[row['id']] = FloodAgent(
                    id=row['id'],
                    elevated=bool(row['elevated']),
                    has_insurance=bool(row['has_insurance']),
                    relocated=bool(row.get('relocated', False)),
                    memory=memory,
                    trust_in_insurance=float(row['trust_in_insurance']),
                    trust_in_neighbors=float(row['trust_in_neighbors']),
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
        """Execute an approved skill - SYSTEM ONLY."""
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
            agent.has_insurance = False
            state_changes["has_insurance"] = False
        elif skill == "relocate":
            if not agent.relocated:
                agent.relocated = True
                state_changes["relocated"] = True
        elif skill == "do_nothing":
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
    
    def __init__(self, simulation: FloodSimulation):
        self.simulation = simulation
    
    def build(self, agent_id: str) -> Dict[str, Any]:
        """Build read-only context for agent."""
        agent = self.simulation.agents.get(agent_id)
        if not agent:
            return {}
        
        return {
            "agent_id": agent_id,
            "elevated": agent.elevated,
            "has_insurance": agent.has_insurance,
            "trust_in_insurance": agent.trust_in_insurance,
            "trust_in_neighbors": agent.trust_in_neighbors,
            "memory": agent.memory.copy(),
            "flood_event": self.simulation.environment.flood_event,
            "year": self.simulation.environment.year
        }
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into LLM prompt with skill-based options."""
        elevation_status = (
            "Your house is already elevated, which provides very good protection."
            if context.get("elevated") else 
            "You have not elevated your home."
        )
        
        insurance_status = "have" if context.get("has_insurance") else "do not have"
        
        trust_ins = context.get("trust_in_insurance", 0.3)
        trust_neighbors = context.get("trust_in_neighbors", 0.4)
        
        trust_ins_text = self._verbalize_trust(trust_ins, "insurance")
        trust_neighbors_text = self._verbalize_trust(trust_neighbors, "neighbors")
        
        memory = "\n".join(f"- {m}" for m in context.get("memory", [])) or "No past events recalled."
        
        if context.get("elevated"):
            options = """1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)
2. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)
3. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"""
            valid_choices = "1, 2, or 3"
        else:
            options = """1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)
2. Elevate your house (High upfront cost but can prevent most physical damage.)
3. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)
4. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"""
            valid_choices = "1, 2, 3, or 4"
        
        flood_status = (
            "A flood occurred this year."
            if context.get("flood_event") else 
            "No flood occurred this year."
        )
        
        return f"""You are a homeowner in a city, with a strong attachment to your community. {elevation_status}
Your memory includes:
{memory}

You currently {insurance_status} flood insurance.
You {trust_ins_text} the insurance company. You {trust_neighbors_text} your neighbors' judgment.

Using the Protection Motivation Theory, evaluate your current situation by considering the following factors:
- Perceived Severity: How serious the consequences of flooding feel to you.
- Perceived Vulnerability: How likely you think you are to be affected.
- Response Efficacy: How effective you believe each action is.
- Self-Efficacy: Your confidence in your ability to take that action.
- Response Cost: The financial and emotional cost of the action.
- Maladaptive Rewards: The benefit of doing nothing immediately.

Now, choose one of the following actions:
{options}
Note: If no flood occurred this year, since no immediate threat, most people would choose "Do Nothing."
{flood_status}

Please respond using the exact format below. Do NOT include any markdown symbols:
Threat Appraisal: [One sentence summary of how threatened you feel by any remaining flood risks.]
Coping Appraisal: [One sentence summary of how well you think you can cope or act.]
Final Decision: [Choose {valid_choices} only]"""
    
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


# =============================================================================
# LLM INTERFACE
# =============================================================================

def create_llm_invoke(model: str):
    """Create LLM invoke function."""
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=model, temperature=0.3)
        
        def invoke(prompt: str) -> str:
            response = llm.invoke(prompt)
            return response.content
        
        return invoke
    except ImportError:
        print("Warning: langchain_ollama not installed. Using mock LLM.")
        return lambda p: "Threat Appraisal: I feel moderately at risk.\nCoping Appraisal: I can manage.\nFinal Decision: 4 - Do Nothing"


# =============================================================================
# MAIN EXPERIMENT
# =============================================================================

def run_experiment(args):
    """Run the skill-governed flood adaptation experiment."""
    print("=" * 60)
    print("Skill-Governed Flood Adaptation Example")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Agents: {args.num_agents}, Years: {args.num_years}")
    print("=" * 60)
    
    sim = FloodSimulation(num_agents=args.num_agents, seed=args.seed)
    context_builder = FloodContextBuilder(sim)
    skill_registry = create_flood_adaptation_registry()
    model_adapter = get_adapter(args.model)
    validators = create_default_validators()
    
    output_dir = Path(args.output_dir) / args.model.replace(":", "_")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Use Framework AuditWriter
    audit_config = AuditConfig(
        output_dir=str(output_dir),
        log_level="full",
        max_entries_per_file=10000
    )
    audit_writer = AuditWriter(audit_config)
    
    broker = SkillBrokerEngine(
        skill_registry=skill_registry,
        model_adapter=model_adapter,
        validators=validators,
        simulation_engine=sim,
        context_builder=context_builder,
        audit_writer=audit_writer,
        max_retries=2
    )
    
    llm_invoke = create_llm_invoke(args.model)
    
    run_id = f"skill_example_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    step_counter = 0
    logs = []
    
    for year in range(1, args.num_years + 1):
        env = sim.advance_year()
        sim.grant_available = random.random() < GRANT_PROBABILITY
        
        print(f"\n--- Year {year} ---")
        if env.flood_event:
            print("🌊 FLOOD EVENT!")
        
        active_agents = [a for a in sim.agents.values() if a.is_active]
        total_elevated = sum(1 for a in active_agents if a.elevated)
        total_relocated = NUM_AGENTS - len(active_agents)
        print(f"Active agents: {len(active_agents)}")
        
        # Memory Update (MCP Logic)
        for agent in active_agents:
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
            
            if sim.grant_available:
                agent.memory.append(f"Year {year}: Elevation grants are available.")
            
            num_neighbors = NUM_AGENTS - 1
            if num_neighbors > 0:
                elevated_pct = round(((total_elevated - (1 if agent.elevated else 0)) / num_neighbors) * 100)
                agent.memory.append(f"Year {year}: I observe {elevated_pct}% of my neighbors have elevated homes.")
                relocated_pct = round((total_relocated / num_neighbors) * 100)
                agent.memory.append(f"Year {year}: I observe {relocated_pct}% of my neighbors have relocated.")
            
            if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
                agent.memory.append(f"Suddenly recalled: '{random.choice(PAST_EVENTS)}'.")
            
            agent.memory = agent.memory[-MEMORY_WINDOW:]
        
        # Process Decisions
        for agent in active_agents:
            step_counter += 1
            result = broker.process_step(
                agent_id=agent.id,
                step_id=step_counter,
                run_id=run_id,
                seed=args.seed + step_counter,
                llm_invoke=llm_invoke
            )
            
            logs.append({
                "agent_id": agent.id,
                "year": year,
                "decision": agent.get_adaptation_state(),
                "raw_skill": result.approved_skill.skill_name if result.approved_skill else None,
                "outcome": result.outcome.value,
                "elevated": agent.elevated,
                "has_insurance": agent.has_insurance,
                "relocated": agent.relocated
            })
        
        import pandas as pd
        pd.DataFrame(logs).to_csv(output_dir / "simulation_log.csv", index=False)
        print(f"[Year {year}] Log saved with {len(logs)} entries")
    
    summary = audit_writer.finalize()
    broker_stats = broker.get_stats()
    
    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)
    print(f"Total decisions: {broker_stats['total']}")
    print(f"Approval rate: {broker_stats['approval_rate']}")
    print(f"Results saved to: {output_dir}")
    
    return broker_stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skill-Governed Flood Adaptation")
    parser.add_argument("--model", default="llama3.2:3b", help="LLM model (e.g. llama3.2:3b)")
    parser.add_argument("--num-agents", type=int, default=10)
    parser.add_argument("--num-years", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="results")
    
    args = parser.parse_args()
    run_experiment(args)
