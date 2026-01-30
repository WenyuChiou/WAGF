"""
Household Agent (Exp3)

The Household Agent works in Phase 2 (Household Decisions).
Responsibility:
- Evaluate flood risk (Threat Appraisal)
- Evaluate mitigation options (Coping Appraisal)
- Make decisions: Do Nothing, Buy Insurance, Elevate, Relocate

Output Format follows PMT 5 Constructs:
- TP: Threat Perception
- CP: Coping Perception
- SP: Subsidy Perception
- SC: Self-Confidence (in adaptation)
- PA: Prior Adaptation (history)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal, TYPE_CHECKING
import random

from broker.components.memory import CognitiveMemory
from broker.utils.agent_config import AgentTypeConfig

if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.memory import SymbolicMemory

@dataclass
class HouseholdAgentState:
    id: str
    
    # Demographics (SPLIT: MG + Tenure)
    mg: bool = False                 # Marginalized Group (True = MG, False = NMG)
    tenure: str = "Owner"            # "Owner" or "Renter"
    region_id: str = "NJ"            # For multi-government mapping
    
    income: float = 50_000
    property_value: float = 300_000
    
    # Social Demographics (New)
    generations: int = 1             # Place attachment proxy
    household_size: int = 3          # Dependents proxy
    has_vehicle: bool = True         # Evacuation capability
    
    # Adaptation Status
    elevated: bool = False           # Cumulative (permanent)
    has_insurance: bool = False      # NOT cumulative (renewed yearly)
    relocated: bool = False          # Cumulative (permanent)
    
    # Trust & Perception (0.0 - 1.0)
    trust_in_government: float = 0.5
    trust_in_insurance: float = 0.5
    trust_in_neighbors: float = 0.5
    
    # Financial Tracking
    cumulative_damage: float = 0.0
    cumulative_oop: float = 0.0      # Out-of-pocket costs
    
    # Memory
    memory: Optional[CognitiveMemory] = None

    def get_all_state(self) -> Dict[str, Any]:
        """Get flattened 0-1 normalized state for context builder."""
        return {
            "mg": self.mg,
            "tenure": self.tenure,
            "income_norm": self.income / 150000,
            "property_value_norm": self.property_value / 500000,
            "trust_gov": self.trust_in_government,
            "trust_ins": self.trust_in_insurance,
            "trust_neighbors": self.trust_in_neighbors,
            "cumulative_damage": self.cumulative_damage / (self.property_value if self.property_value > 0 else 1.0),
            "elevated": float(self.elevated),
            "insured": float(self.has_insurance),
            "household_size": self.household_size,
            "generations": self.generations,
            "has_vehicle": self.has_vehicle
        }

    def get_all_state_raw(self) -> Dict[str, Any]:
        """Get original raw values."""
        return {
            "income": self.income,
            "property_value": self.property_value,
            "household_size": self.household_size,
            "generations": self.generations,
            "has_vehicle": self.has_vehicle,
            "mg": self.mg,
            "tenure": self.tenure
        }

@dataclass
class HouseholdOutput:
    """LLM Output for Household Agent (PMT 5 Constructs)"""
    agent_id: str
    mg: bool
    tenure: str
    year: int
    
    # PMT Constructs (Level + Explanation)
    tp_level: Literal["LOW", "MODERATE", "HIGH"]
    tp_explanation: str
    cp_level: Literal["LOW", "MODERATE", "HIGH"]
    cp_explanation: str
    sp_level: Literal["LOW", "MODERATE", "HIGH"]
    sp_explanation: str
    sc_level: Literal["LOW", "MODERATE", "HIGH"]
    sc_explanation: str
    pa_level: Literal["NONE", "PARTIAL", "FULL"]
    pa_explanation: str
    
    # Decision
    decision_number: int
    decision_skill: str  # buy_insurance, elevate_house, do_nothing, relocate
    
    # Validation
    validated: bool = True
    validation_errors: List[str] = field(default_factory=list)

class HouseholdAgent:
    """
    Household Agent implementation.
    """
    
    def __init__(self, agent_id: str, mg: bool, tenure: str, 
                 income: float, property_value: float, region_id: str = "NJ",
                 generations: int = 1, household_size: int = 3, has_vehicle: bool = True):
        self.state = HouseholdAgentState(
            id=agent_id, 
            mg=mg,
            tenure=tenure,
            region_id=region_id,
            income=income,
            property_value=property_value,
            generations=generations,
            household_size=household_size,
            has_vehicle=has_vehicle,
            # Randomize initial trust (0.3 - 0.8)
            trust_in_government=random.uniform(0.3, 0.8),
            trust_in_insurance=random.uniform(0.3, 0.8),
            trust_in_neighbors=random.uniform(0.3, 0.8)
        )
        self.memory = CognitiveMemory(agent_id)
        self.state.memory = self.memory
        
        # Load config parameters
        self.config_loader = AgentTypeConfig.load()
        self.params = self.config_loader.get_parameters("household")

    def _init_memory_v4(self, config: dict):
        """Initialize V4 symbolic memory if configured."""
        if config.get("engine") == "symbolic":
            from cognitive_governance.v1_prototype.memory.symbolic import SymbolicMemory
            sensors = config.get("sensors", [])
            arousal = config.get("arousal_threshold", 0.5)
            return SymbolicMemory(sensors, arousal_threshold=arousal)
        return None


    def reset_insurance(self):
        """Called at start of year: Insurance NOT cumulative."""
        self.state.has_insurance = False

    def make_decision(self, year: int, context: Dict[str, Any]) -> HouseholdOutput:
        """
        Phase 2 Decision: Choose adaptation action.
        Each agent makes exactly ONE decision per year.
        
        Returns HouseholdOutput with PMT constructs.
        """
        s = self.state  # Shortcut
        
        # Skip if already relocated
        if s.relocated:
            return self._create_output(year, "NONE", "Already relocated", 4, "do_nothing")
        
        # ===== Evaluate PMT Constructs (Heuristic) =====
        # In LLM mode, these would come from LLM parsing
        
        # TP: Threat Perception (based on damage history)
        tp_level = "LOW"
        if s.cumulative_damage > s.property_value * self.params.get("tp_threshold_high", 0.20):
            tp_level = "HIGH"
        elif s.cumulative_damage > s.property_value * self.params.get("tp_threshold_moderate", 0.05):
            tp_level = "MODERATE"
        tp_exp = f"Cumulative damage: ${s.cumulative_damage:,.0f}"
        
        # CP: Coping Perception (based on income vs action cost)
        elevation_cost = self.params.get("elevation_cost", 150_000)
        insurance_cost = s.property_value * context.get("insurance_premium_rate", 0.05)
        
        income_low = self.params.get("income_threshold_low", 35000)
        income_mod = self.params.get("income_threshold_mod", 60000)
        
        if s.income > income_mod:
            cp_level = "HIGH"
        elif s.income > income_low:
            cp_level = "MODERATE"
        else:
            cp_level = "LOW"
            
        cp_exp = f"Income ${s.income:,.0f}, Elev cost ${elevation_cost:,.0f}"
        
        # SP: Subsidy Perception
        subsidy_rate = context.get("government_subsidy_rate", 0.5)
        sp_level = "HIGH" if subsidy_rate >= 0.7 else ("MODERATE" if subsidy_rate >= 0.5 else "LOW")
        sp_exp = f"Subsidy rate {subsidy_rate:.0%}"
        
        # SC: Self-Confidence 
        sc_level = "MODERATE"  # Placeholder
        sc_exp = f"Trust in govt: {s.trust_in_government:.2f}"
        
        # PA: Prior Adaptation
        pa_level = "NONE"
        if s.elevated:
            pa_level = "FULL"
        elif s.has_insurance:
            pa_level = "PARTIAL"
        pa_exp = f"Elevated: {s.elevated}, Insured: {s.has_insurance}"
        
        # ===== Decision Logic =====
        decision_num = 4  # Default: do_nothing
        decision_skill = "do_nothing"
        
        # 1. Insurance logic: Buy if damaged OR high trust (and not already insured this year)
        if not s.has_insurance:
            if tp_level in ["MODERATE", "HIGH"] or s.trust_in_insurance > self.params.get("trust_threshold_ins", 0.65):
                decision_num = 1
                decision_skill = "buy_insurance"
        
        # 2. Elevation logic: Owner + Subsidy available + Damaged
        if decision_skill == "do_nothing" and not s.elevated and s.tenure == "Owner":
            if sp_level in ["MODERATE", "HIGH"] and tp_level in ["MODERATE", "HIGH"]:
                if s.trust_in_government > self.params.get("trust_threshold_gov", 0.40):
                    decision_num = 2
                    decision_skill = "elevate_house"
        
        # 3. Relocation logic (rare): Extreme damage + Low income
        if decision_skill == "do_nothing" and s.cumulative_damage > s.property_value * self.params.get("damage_threshold_relocate", 0.50):
            if s.income < income_mod: # Using MOD threshold for relocation logic
                decision_num = 3
                decision_skill = "relocate"
        
        return HouseholdOutput(
            agent_id=s.id,
            mg=s.mg,
            tenure=s.tenure,
            year=year,
            tp_level=tp_level, tp_explanation=tp_exp,
            cp_level=cp_level, cp_explanation=cp_exp,
            sp_level=sp_level, sp_explanation=sp_exp,
            sc_level=sc_level, sc_explanation=sc_exp,
            pa_level=pa_level, pa_explanation=pa_exp,
            decision_number=decision_num,
            decision_skill=decision_skill
        )

    def _create_output(self, year: int, pa: str, pa_exp: str, 
                       dec_num: int, dec_skill: str) -> HouseholdOutput:
        """Helper to create output for edge cases like already relocated."""
        return HouseholdOutput(
            agent_id=self.state.id,
            mg=self.state.mg,
            tenure=self.state.tenure,
            year=year,
            tp_level="LOW", tp_explanation="N/A",
            cp_level="LOW", cp_explanation="N/A",
            sp_level="LOW", sp_explanation="N/A",
            sc_level="LOW", sc_explanation="N/A",
            pa_level=pa, pa_explanation=pa_exp,
            decision_number=dec_num,
            decision_skill=dec_skill
        )

    def apply_decision(self, output: HouseholdOutput):
        """Updates state based on decision execution."""
        decision = output.decision_skill
        year = output.year
        
        if decision == "buy_insurance":
            self.state.has_insurance = True
            
        elif decision == "elevate_house":
            self.state.elevated = True
            
        elif decision == "relocate":
            self.state.relocated = True
            
        # Log to memory
        self.memory.add_episodic(
            f"Year {year}: Decided to {decision}",
            importance=0.5 if decision == "do_nothing" else 0.7,
            year=year,
            tags=["decision"]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state for ContextBuilder."""
        return {
            "id": self.state.id,
            "mg": self.state.mg,
            "tenure": self.state.tenure,
            "region_id": self.state.region_id,
            "elevated": self.state.elevated,
            "has_insurance": self.state.has_insurance,
            "income": self.state.income,
            "generations": self.state.generations_in_area,
            "household_size": self.state.household_size,
            "has_vehicle": self.state.has_vehicle,
            "trust_gov": self.state.trust_in_government,
            "trust_ins": self.state.trust_in_insurance,
            "cumulative_damage": self.state.cumulative_damage,
            "memory": self.memory.format_for_prompt()
        }

    # =========================================================================
    # BaseAgent Compatibility Interface
    # =========================================================================
    
    @property
    def agent_type(self) -> str:
        return "household_mg" if self.state.mg else "household_nmg"
    
    @property
    def name(self) -> str:
        return self.state.id

    def get_all_state(self) -> Dict[str, float]:
        """Normalized state (0-1)."""
        # Heuristic normalization ranges
        max_income = 150_000
        max_prop = 1_000_000
        max_damage = 500_000
        
        def norm(v, mx): return max(0.0, min(1.0, v / mx))
        
        return {
            "income_norm": norm(self.state.income, max_income),
            "property_value_norm": norm(self.state.property_value, max_prop),
            "cumulative_damage": norm(self.state.cumulative_damage, max_damage),
            "trust_gov": self.state.trust_in_government,
            "trust_ins": self.state.trust_in_insurance,
            "trust_neighbors": self.state.trust_in_neighbors,
            "elevated": 1.0 if self.state.elevated else 0.0,
            "insured": 1.0 if self.state.has_insurance else 0.0,
            "relocated": 1.0 if self.state.relocated else 0.0,
            "household_size": self.state.household_size,
            "generations": self.state.generations,
            "has_vehicle": float(self.state.has_vehicle),
            # Synthetics for PMT
            "threat_perception": norm(self.state.cumulative_damage, 100_000), 
            "coping_capacity": norm(self.state.income, 80_000),
            "available_skills": self.get_available_skills()
        }

    def get_all_state_raw(self) -> Dict[str, Any]:
        """Raw state values."""
        return {
            "income": self.state.income,
            "property_value": self.state.property_value,
            "cumulative_damage": self.state.cumulative_damage,
            "trust_gov": self.state.trust_in_government,
            "trust_ins": self.state.trust_in_insurance,
            "tenure": self.state.tenure,
            "mg": self.state.mg,
            "household_size": self.state.household_size,
            "generations": self.state.generations,
            "has_vehicle": self.state.has_vehicle
        }

    def evaluate_objectives(self) -> Dict[str, Dict]:
        """Household objectives: Safety and Financial Stability."""
        return {
            "safety": {
                "current": 1.0 if self.state.elevated or self.state.relocated else 0.0,
                "target": (0.8, 1.0),
                "in_range": self.state.elevated or self.state.relocated
            },
            "financial": {
                "current": 1.0 if self.state.has_insurance else 0.0,
                "target": (0.8, 1.0),
                "in_range": self.state.has_insurance
            }
        }

    def get_available_skills(self) -> List[str]:
        if self.state.relocated:
            return ["do_nothing"]
        
        skills = ["do_nothing", "buy_insurance"]
        if self.state.tenure == "Renter":
            skills.append("buy_contents_insurance")
            skills.append("relocate")
        else:
            if not self.state.elevated:
                skills.append("elevate_house")
            skills.append("buyout_program")
        return skills
    
    def observe(self, environment: Dict[str, float], agents: Dict[str, Any]) -> Dict[str, float]:
        """Observe environment."""
        # Map environment vars to 0-1
        obs = {}
        if "government_subsidy_rate" in environment:
            obs["subsidy_rate"] = environment["government_subsidy_rate"]
        if "insurance_premium_rate" in environment:
            obs["premium_rate"] = environment["insurance_premium_rate"] * 10 # Normalize 0.05 -> 0.5
        if "flood_occurred" in environment:
            obs["flood"] = 1.0 if environment["flood_occurred"] else 0.0
        return obs
