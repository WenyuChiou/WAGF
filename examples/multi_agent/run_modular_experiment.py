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
from broker.utils.agent_config import AgentTypeConfig
from validators.agent_validator import AgentValidator, ValidationLevel

# Local imports
MULTI_AGENT_DIR = Path(__file__).parent
sys.path.insert(0, str(MULTI_AGENT_DIR))
from generate_agents import generate_agents, HouseholdProfile


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
    
    def format_prompt(self, context: Dict[str, Any], template: str) -> str:
        """Format context into the provided YAML template."""
        # Standard placeholder cleaning
        agent_data = context.get("agent", {})
        memory = context.get("memory", [])
        env = context.get("environment", {})
        
        # Prepare template variables
        residency = agent_data.get("generations", 1)
        income = agent_data.get("income", 50000)
        
        # Format memory
        memory_text = "\n".join([f"- {m}" for m in memory]) if memory else "No significant memories."
        
        # Format insurance status
        ins_status = "HAVE" if agent_data.get("has_insurance") else "DO NOT have"
        
        # Format elevation status
        elev_text = "is elevated (+5 ft)" if agent_data.get("elevated") else "is NOT elevated"
        
        # Build mapping for template
        fmt_map = {
            "agent_id": agent_data.get("agent_id", "Unknown"),
            "narrative_persona": f"You are a {agent_data.get('tenure')} in a flood-prone area.",
            "residency_generations": residency,
            "household_size": agent_data.get("household_size", 2),
            "income_range": f"${income:,.0f}/year",
            "historical_damage": agent_data.get("cumulative_damage", 0),
            "historical_payout": agent_data.get("cumulative_damage", 0) * 0.8 if agent_data.get("has_insurance") else 0,
            "memory": memory_text,
            "elevation_status_text": elev_text,
            "insurance_status": ins_status,
            "current_premium": income * 0.02,
            "premium_change_pct": 0.05,
            "subsidy_rate": env.get("subsidy_rate", 0.5),
            "options_text": context.get("options_text", ""), # Pre-shuffled options
            "rating_scale": "VL = Very Low | L = Low | M = Medium | H = High | VH = Very High",
        }
        
        try:
            return template.format(**fmt_map)
        except KeyError as e:
            # Fallback for missing keys
            return template


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
    
    # Prepare Adapters for different types
    adapters = {
        "household_owner": UnifiedAdapter("household_owner", config_path=str(ma_config_path)),
        "household_renter": UnifiedAdapter("household_renter", config_path=str(ma_config_path))
    }
    
    # Unified Validator (Generic)
    validator = AgentValidator(str(ma_config_path))
    
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
            # Target Agent Type
            atype = f"household_{hh.profile.tenure.lower()}"
            adapter = adapters.get(atype)
            if not adapter: continue
            
            # 1. OPTION SHUFFLING (Mitigate Gemma Position Bias)
            # Use seed based on agent_id and year for reproducibility
            rng = random.Random(hash(f"{hh.id}_{year}_{SEED}"))
            available_skills = hh.get_available_skills()
            
            # Map skills to short IDs or keep names
            skill_ids = [s.split(":")[0].strip() for s in available_skills]
            skill_desc = [s.strip() for s in available_skills]
            
            indices = list(range(len(skill_ids)))
            rng.shuffle(indices)
            
            shuffled_ids = [skill_ids[i] for i in indices]
            shuffled_desc = [skill_desc[i] for i in indices]
            
            # Create numbered option text
            options_text = "\n".join([f"{i+1}. {desc}" for i, desc in enumerate(shuffled_desc)])
            
            # Create mapping for the adapter
            dynamic_skill_map = {str(i+1): s_id for i, s_id in enumerate(shuffled_ids)}
            
            # 2. Build context
            context = context_builder.build(hh.id)
            context["options_text"] = options_text
            
            # Get template from the agent-specific config root
            agent_conf = adapter.agent_config.get(atype)
            template = agent_conf.get("prompt_template", "")
            prompt = context_builder.format_prompt(context, template)
            
            # 3. Validation & Retry Loop
            max_retries = 2
            attempts = 0
            final_decision = "do_nothing"
            final_constructs = {}
            validated = False
            error_msgs = []
            
            while attempts <= max_retries and not validated:
                # Add error feedback to prompt if retry
                current_prompt = prompt
                if error_msgs:
                    current_prompt = adapter.format_retry_prompt(prompt, error_msgs)
                
                # Get LLM response
                try:
                    result = llm_invoke(current_prompt)
                    raw_response = result[0] if isinstance(result, tuple) else result
                except Exception as e:
                    raw_response = ""
                
                # Parse using adapter with dynamic skill map
                proposal = adapter.parse_output(
                    raw_response, 
                    context={
                        "agent_id": hh.id,
                        "dynamic_skill_map": dynamic_skill_map
                    }
                )
                print(f" DEBUG: Raw LLM Output for {hh.id}:\n{raw_response[:150]}...")
                if proposal:
                    print(f" DEBUG: Parsed constructs for {hh.id}: {list(proposal.reasoning.keys())}")
                
                if proposal:
                    decision = proposal.skill_name
                    final_constructs = proposal.reasoning
                    
                    # Validate using Global AgentValidator (Generic)
                    # We pass the full agent state + the parsed constructs (TP_LABEL, etc.)
                    v_results = validator.validate(
                        agent_type=atype,
                        agent_id=hh.id,
                        decision=decision,
                        state=hh.get_all_state_raw(),
                        reasoning=final_constructs
                    )
                    
                    errors = [m for r in v_results for m in r.errors]
                    if not errors:
                        final_decision = decision
                        validated = True
                    else:
                        error_msgs = errors
                        attempts += 1
                else:
                    error_msgs = ["Format Error: Could not parse decision. Ensure 'Final Decision: [number]' is present."]
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
