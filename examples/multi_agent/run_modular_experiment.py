"""
Multi-Agent Modular Experiment

Uses modular broker components (like building blocks):
- ExperimentBuilder: Configure experiment pipeline
- HumanCentricMemoryEngine: Emotional encoding for households
- TieredContextBuilder: Build prompts with state + memory
- SkillRegistry: Define available skills per agent type
- AuditWriter: Log decisions + validation

Agent Types:
- Household (4 subtypes): MG_Owner, MG_Renter, NMG_Owner, NMG_Renter
- Government (FEMA): Adjust subsidies
- Insurance (NFIP): Adjust premiums

5 Constructs: TP, CP, SP, SC, PA (Place Attachment)
"""

import sys
import random
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Modular Components
from broker.components.memory_engine import (
    HumanCentricMemoryEngine, 
    ImportanceMemoryEngine,
    WindowMemoryEngine
)
from broker.components.context_builder import TieredContextBuilder
from broker.components.skill_registry import SkillRegistry
from broker.components.audit_writer import AuditWriter, AuditConfig
from broker.utils.llm_utils import create_llm_invoke
from broker.utils.model_adapter import UnifiedAdapter

# Local imports
MULTI_AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(MULTI_AGENT_DIR))
from generate_agents import generate_agents, HouseholdProfile
from ma_validators.multi_agent_validators import MultiAgentValidator, ValidationResult

# Import from config submodule
from examples.multi_agent.config.schemas import FIVE_CONSTRUCTS, CONSTRUCT_DECISION_MAP

# =============================================================================
# CONFIGURATION
# =============================================================================
SEED = 42
DEFAULT_YEARS = 10
DEFAULT_MODEL = "llama3.2:3b"
DEFAULT_N_AGENTS = 100
FLOOD_PROBABILITY = 0.3

random.seed(SEED)

# =============================================================================
# AGENT WRAPPER (State + Memory)
# =============================================================================

@dataclass
class HouseholdAgentState:
    """Runtime state for a household agent."""
    profile: HouseholdProfile
    memory: List[str]
    
    # Dynamic state
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    cumulative_damage: float = 0.0
    cumulative_oop: float = 0.0
    
    @property
    def id(self):
        return self.profile.agent_id
    
    @property
    def agent_type(self):
        mg = "MG" if self.profile.mg else "NMG"
        return f"{mg}_{self.profile.tenure}"
    
    def get_available_skills(self) -> List[str]:
        """Get skills available based on tenure and state."""
        if self.relocated:
            return ["already_relocated"]
        
        skills = []
        if self.profile.tenure == "Owner":
            skills.append("buy_insurance: Purchase flood insurance (building + contents)")
            if not self.elevated:
                skills.append("elevate_house: Elevate house structure (+5 ft)")
            skills.append("buyout_program: Accept government buyout")
        else:  # Renter
            skills.append("buy_contents_insurance: Purchase contents-only insurance")
            skills.append("relocate: Move to lower-risk area")
        
        skills.append("do_nothing: Maintain current status")
        return skills
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for context builder."""
        return {
            "agent_id": self.id,
            "agent_type": self.agent_type,
            "mg": self.profile.mg,
            "tenure": self.profile.tenure,
            "income": self.profile.income,
            "household_size": self.profile.household_size,
            "generations": self.profile.generations,
            "has_vehicle": self.profile.has_vehicle,
            "has_children": self.profile.has_children,
            "has_elderly": self.profile.has_elderly,
            "rcv_building": self.profile.rcv_building,
            "rcv_contents": self.profile.rcv_contents,
            "trust_gov": self.profile.trust_gov,
            "trust_ins": self.profile.trust_ins,
            "trust_neighbors": self.profile.trust_neighbors,
            "elevated": self.elevated,
            "has_insurance": self.has_insurance,
            "relocated": self.relocated,
            "cumulative_damage": self.cumulative_damage,
            "memory": self.memory
        }

    def get_all_state_raw(self) -> Dict[str, Any]:
        """Validator-compatible raw state."""
        return self.to_dict()


class InstitutionalAgent:
    """Base class for Government and Insurance agents."""
    def __init__(self, agent_id: str, agent_type: str):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.memory = []
    
    @property
    def id(self):
        return self.agent_id


class StateGovernmentAgent(InstitutionalAgent):
    """
    State Government agent (FEMA partner).
    
    Manages adaptation subsidies for households, particularly MG households.
    
    References:
    - FEMA Individual Assistance grants: ~75% federal / 25% state cost share
    - Hazard Mitigation Grant Program (HMGP): up to 75% federal funding
    - Increased Cost of Compliance (ICC): up to $30,000 for elevation
    """
    def __init__(self, agent_id: str = "NJ_STATE"):
        super().__init__(agent_id, "government")
        self.subsidy_rate = 0.50  # Initial 50% subsidy (literature: 20-75%)
        self.annual_budget = 500_000  # State allocation
        self.budget_remaining = self.annual_budget
    
    def get_available_skills(self) -> List[str]:
        return [
            "increase_subsidy: Raise subsidy rate for MG households",
            "decrease_subsidy: Lower subsidy rate due to budget constraints",
            "maintain_subsidy: Keep current subsidy rate"
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "subsidy_rate": self.subsidy_rate,
            "budget_remaining": self.budget_remaining
        }


class FEMAInsuranceAgent(InstitutionalAgent):
    """
    FEMA/NFIP Insurance agent.
    
    National Flood Insurance Program - manages flood insurance policies.
    
    References:
    - NFIP premium rates: typically 1-3% of coverage value
    - Maximum coverage: $250K building, $100K contents
    - Average claim payout: ~$52,000 (FEMA data 2019)
    - Risk Rating 2.0: actuarially sound pricing (2021+)
    """
    def __init__(self, agent_id: str = "FEMA_NFIP"):
        super().__init__(agent_id, "insurance")
        self.premium_rate = 0.02  # 2% of coverage (literature range: 1-3%)
        self.loss_ratio = 0.0
        self.claims_paid = 0.0
        self.policies_count = 0
        self.max_building_coverage = 250_000  # NFIP limit
        self.max_contents_coverage = 100_000  # NFIP limit
    
    def get_available_skills(self) -> List[str]:
        return [
            "raise_premium: Increase premium rate (Risk Rating 2.0)",
            "lower_premium: Decrease premium rate for affordability",
            "maintain_premium: Keep current premium rate"
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "premium_rate": self.premium_rate,
            "loss_ratio": self.loss_ratio,
            "policies_count": self.policies_count
        }


# Legacy aliases for backward compatibility
GovernmentAgent = StateGovernmentAgent
InsuranceAgent = FEMAInsuranceAgent


# =============================================================================
# CONTEXT BUILDER (Multi-Agent)
# =============================================================================

class MultiAgentContextBuilder(TieredContextBuilder):
    """Context builder for multi-agent simulation."""
    
    def __init__(self, agents: Dict[str, Any], memory_engine, environment: Dict):
        self.agents = agents
        self.memory_engine = memory_engine
        self.environment = environment
    
    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        agent = self.agents.get(agent_id)
        if not agent:
            return {}
        
        # Get memory
        memory = []
        if self.memory_engine and hasattr(agent, 'id'):
            # Create a mock agent object for memory engine
            class MockAgent:
                def __init__(self, aid, mem):
                    self.id = aid
                    self.memory = mem
            mock = MockAgent(agent.id, getattr(agent, 'memory', []))
            memory = self.memory_engine.retrieve(mock, top_k=3)
        
        # Build context
        context = {
            "agent": agent.to_dict(),
            "memory": memory,
            "environment": self.environment,
            "skills": agent.get_available_skills() if hasattr(agent, 'get_available_skills') else []
        }
        
        return context
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """Format context into LLM prompt."""
        agent = context.get("agent", {})
        memory = context.get("memory", [])
        env = context.get("environment", {})
        skills = context.get("skills", [])
        
        # Format memory
        memory_text = "\n".join([f"- {m}" for m in memory]) if memory else "No significant memories."
        
        # Format skills
        skills_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(skills)])
        
        prompt = f"""You are a household in a flood-prone area making an adaptation decision.

=== YOUR SITUATION ===
- Agent ID: {agent.get('agent_id', 'Unknown')}
- Type: {agent.get('agent_type', 'Unknown')}
- Income: ${agent.get('income', 0):,.0f}/year
- Property Value (Building): ${agent.get('rcv_building', 0):,.0f}
- Property Value (Contents): ${agent.get('rcv_contents', 0):,.0f}
- Elevated: {'Yes' if agent.get('elevated') else 'No'}
- Has Insurance: {'Yes' if agent.get('has_insurance') else 'No'}
- Cumulative Damage: ${agent.get('cumulative_damage', 0):,.0f}

=== TRUST LEVELS (0-1) ===
- Trust in Government: {agent.get('trust_gov', 0.5):.2f}
- Trust in Insurance: {agent.get('trust_ins', 0.5):.2f}
- Trust in Neighbors: {agent.get('trust_neighbors', 0.5):.2f}

=== YOUR MEMORIES ===
{memory_text}

=== ENVIRONMENT ===
- Year: {env.get('year', 1)}
- Flood this year: {'YES' if env.get('flood_occurred') else 'NO'}
- Government Subsidy Rate: {env.get('subsidy_rate', 0.5):.0%}
- Insurance Premium Rate: {env.get('premium_rate', 0.05):.1%}

=== YOUR OPTIONS ===
{skills_text}

=== EVALUATION INSTRUCTIONS ===
Evaluate each of the 5 constructs (LOW/MODERATE/HIGH):
1. TP (Threat Perception): How threatened do you feel by floods?
2. CP (Coping Perception): Can you afford/manage protective actions?
3. SP (Stakeholder Perception): Do you trust government/insurers?
4. SC (Social Capital): Do neighbors support your decisions?
5. PA (Place Attachment): How attached are you to this home?

=== OUTPUT FORMAT ===
TP Assessment: [LOW/MODERATE/HIGH] - [reason]
CP Assessment: [LOW/MODERATE/HIGH] - [reason]
SP Assessment: [LOW/MODERATE/HIGH] - [reason]
SC Assessment: [LOW/MODERATE/HIGH] - [reason]
PA Assessment: [LOW/MODERATE/HIGH] - [reason]
Final Decision: [number from options above]
Reasoning: [brief explanation]
"""
        return prompt


# =============================================================================
# MAIN SIMULATION
# =============================================================================

def run_multi_agent_experiment(
    model: str = DEFAULT_MODEL,
    n_agents: int = DEFAULT_N_AGENTS,
    years: int = DEFAULT_YEARS,
    memory_engine_type: str = "humancentric",
    output_dir: str = "examples/multi_agent/results"
):
    """Run multi-agent simulation with modular components."""
    
    print("=" * 60)
    print(f"Multi-Agent Modular Experiment")
    print(f"Model: {model} | Agents: {n_agents} | Years: {years}")
    print(f"Memory Engine: {memory_engine_type}")
    print("=" * 60)
    
    # 1. Generate agents
    profiles = generate_agents(n_agents=n_agents)
    households = [HouseholdAgentState(profile=p, memory=[]) for p in profiles]
    
    # Initialize dynamic state from profile
    for hh in households:
        hh.has_insurance = hh.profile.has_insurance
        hh.elevated = hh.profile.elevated
    
    # 2. Create institutional agents
    government = StateGovernmentAgent("NJ_STATE")
    insurance = FEMAInsuranceAgent("FEMA_NFIP")
    
    # 3. Build agent map
    all_agents = {hh.id: hh for hh in households}
    all_agents[government.id] = government
    all_agents[insurance.id] = insurance
    
    # 4. Initialize memory engine
    if memory_engine_type == "humancentric":
        memory_engine = HumanCentricMemoryEngine(
            window_size=3,
            top_k_significant=2,
            consolidation_prob=0.7,
            decay_rate=0.1,
            seed=SEED
        )
        print(f" Using HumanCentricMemoryEngine (emotional + consolidation)")
    elif memory_engine_type == "importance":
        memory_engine = ImportanceMemoryEngine(window_size=3, top_k_significant=2)
        print(f" Using ImportanceMemoryEngine")
    else:
        memory_engine = WindowMemoryEngine(window_size=3)
        print(f" Using WindowMemoryEngine")
    
    # 5. Initialize environment
    environment = {
        "year": 0,
        "flood_occurred": False,
        "subsidy_rate": government.subsidy_rate,
        "premium_rate": insurance.premium_rate
    }
    
    # 6. Create context builder
    context_builder = MultiAgentContextBuilder(all_agents, memory_engine, environment)
    
    # 7. Initialize LLM and Adapter
    llm_invoke = create_llm_invoke(model)
    
    # Load multi-agent specific configuration
    ma_config_path = MULTI_AGENT_DIR / "ma_agent_types.yaml"
    adapter = UnifiedAdapter(agent_type="household", config_path=str(ma_config_path))
    validator = MultiAgentValidator()
    
    # 8. Initialize audit
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Results tracking
    results = []
    flood_years = [y for y in range(1, years + 1) if random.random() < FLOOD_PROBABILITY]
    print(f" Flood years scheduled: {flood_years}")
    
    # ==========================================================================
    # SIMULATION LOOP
    # ==========================================================================
    
    for year in range(1, years + 1):
        print(f"\n--- Year {year} ---")
        
        flood_occurred = year in flood_years
        environment["year"] = year
        environment["flood_occurred"] = flood_occurred
        environment["subsidy_rate"] = government.subsidy_rate
        environment["premium_rate"] = insurance.premium_rate
        
        year_actions = {}
        
        # Process each household
        active_households = [hh for hh in households if not hh.relocated]
        
        for i, hh in enumerate(active_households):
            # Build context
            context = context_builder.build(hh.id)
            prompt = context_builder.format_prompt(context)
            
            # Validation & Retry Loop
            max_retries = 2
            attempts = 0
            final_decision = "do_nothing"
            final_constructs = {}
            validated = False
            error_msg = ""
            
            while attempts <= max_retries and not validated:
                # Add error feedback to prompt if retry
                current_prompt = prompt
                if attempts > 0:
                    current_prompt = adapter.format_retry_prompt(prompt, [error_msg])
                
                # Get LLM response
                try:
                    result = llm_invoke(current_prompt)
                    # llm_invoke returns (content, LLMStats) tuple
                    raw_response = result[0] if isinstance(result, tuple) else result
                except Exception as e:
                    raw_response = ""
                
                # Parse using central adapter
                proposal = adapter.parse_output(raw_response, {"agent_type": "household", "agent_id": hh.id, "elevation_status": "elevated" if hh.elevated else "non_elevated"})
                
                if proposal:
                    decision = proposal.skill_name
                    constructs = proposal.reasoning  # TP_LABEL, CP_LABEL, etc.
                    
                    # Map constructs for validator (TP_LABEL -> TP)
                    val_constructs = {
                        "TP": constructs.get("TP_LABEL", "MODERATE"),
                        "CP": constructs.get("CP_LABEL", "MODERATE"),
                        "SP": constructs.get("SP_LABEL", "MODERATE"),
                        "SC": constructs.get("SC_LABEL", "MODERATE"),
                        "PA": constructs.get("PA_LABEL", "MODERATE")
                    }
                    
                    # Validate
                    res = validator.validate(decision, hh.get_all_state_raw(), val_constructs)
                    
                    if res.valid:
                        final_decision = decision
                        final_constructs = val_constructs
                        validated = True
                    else:
                        error_msg = "; ".join(res.errors)
                        attempts += 1
                else:
                    error_msg = "Could not parse decision format"
                    attempts += 1
            
            # Application
            decision = final_decision
            if decision == "buy_insurance" or decision == "buy_contents_insurance":
                hh.has_insurance = True
                memory_engine.add_memory(hh.id, f"Year {year}: I purchased flood insurance")
            elif decision == "elevate_house" and not hh.elevated:
                hh.elevated = True
                memory_engine.add_memory(hh.id, f"Year {year}: I elevated my house (+5 ft)")
            elif decision == "buyout_program" or decision == "relocate":
                hh.relocated = True
                memory_engine.add_memory(hh.id, f"Year {year}: I left this area")
            else:
                memory_engine.add_memory(hh.id, f"Year {year}: I maintained current status")
            
            year_actions[decision] = year_actions.get(decision, 0) + 1
            
            # Record result
            results.append({
                "year": year,
                "agent_id": hh.id,
                "agent_type": hh.agent_type,
                "decision": decision,
                "tp_level": final_constructs.get("TP", "MODERATE"),
                "cp_level": final_constructs.get("CP", "MODERATE"),
                "validated": validated,
                "retries": attempts,
                "elevated": hh.elevated,
                "has_insurance": hh.has_insurance,
                "relocated": hh.relocated
            })
        
        # Apply flood damage if occurred
        if flood_occurred:
            damage_factor = random.uniform(0.05, 0.20)
            total_damage = 0
            for hh in active_households:
                if not hh.relocated:
                    base_damage = (hh.profile.rcv_building + hh.profile.rcv_contents) * damage_factor
                    if hh.elevated:
                        base_damage *= 0.3  # 70% reduction
                    if hh.has_insurance:
                        hh.cumulative_oop += base_damage * 0.2  # 20% OOP
                    else:
                        hh.cumulative_oop += base_damage
                    hh.cumulative_damage += base_damage
                    total_damage += base_damage
                    memory_engine.add_memory(hh.id, f"Year {year}: Flood caused ${base_damage:,.0f} damage to my property", 
                                            metadata={"emotion": "fear", "source": "personal"})
            
            print(f" [FLOOD] Total damage: ${total_damage:,.0f}")
        
        print(f" Actions: {year_actions}")
    
    # ==========================================================================
    # SAVE RESULTS
    # ==========================================================================
    
    df = pd.DataFrame(results)
    csv_path = output_path / f"{model.replace(':', '_')}_simulation_log.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n[OK] Results saved to {csv_path}")
    
    # Summary
    print("\n=== SUMMARY ===")
    print(f"Total decisions: {len(results)}")
    print(f"Final elevated: {sum(1 for hh in households if hh.elevated)}/{n_agents}")
    print(f"Final insured: {sum(1 for hh in households if hh.has_insurance)}/{n_agents}")
    print(f"Final relocated: {sum(1 for hh in households if hh.relocated)}/{n_agents}")
    
    return df


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-Agent Modular Experiment")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="LLM model")
    parser.add_argument("--agents", type=int, default=DEFAULT_N_AGENTS, help="Number of agents")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS, help="Simulation years")
    parser.add_argument("--memory-engine", type=str, default="humancentric",
                       choices=["window", "importance", "humancentric"],
                       help="Memory engine type")
    parser.add_argument("--output", type=str, default="examples/multi_agent/results")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    
    random.seed(args.seed)
    
    run_multi_agent_experiment(
        model=args.model,
        n_agents=args.agents,
        years=args.years,
        memory_engine_type=args.memory_engine,
        output_dir=args.output
    )
