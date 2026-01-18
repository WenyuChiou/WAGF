# Agent Pipeline Specification

## 1. Context → Reasoning → Action Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AGENT DECISION PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        1. CONTEXT (Input)                           │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │   A. State (Read-only)                                              │   │
│  │      ├── Static: agent_id, mg, tenure, region_id                    │   │
│  │      └── Dynamic: elevated, has_insurance, cumulative_damage        │   │
│  │                                                                     │   │
│  │   B. Memory (State) → Retrieval (Tool)                              │   │
│  │      ├── memory.retrieve(top_k=5)  ← Tool invocation                │   │
│  │      └── Returns: List[str] of past experiences                     │   │
│  │                                                                     │   │
│  │   C. Environment (Read-only)                                        │   │
│  │      ├── year, flood_occurred                                       │   │
│  │      ├── subsidy_rate, premium_rate                                 │   │
│  │      └── neighbor_actions (optional, limited visibility)            │   │
│  │                                                                     │   │
│  │   OUTPUT: Prompt (text for LLM)                                     │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       2. REASONING (LLM)                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │   INPUT: Prompt                                                     │   │
│  │                                                                     │   │
│  │   PROCESSING: LLM generates structured response                     │   │
│  │      ├── Evaluate: TP, CP, SP, SC, PA (level + explanation)         │   │
│  │      ├── Decide: decision_number                                    │   │
│  │      └── Justify: justification                                     │   │
│  │                                                                     │   │
│  │   OUTPUT: Raw text response                                         │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        3. ACTION (Output)                           │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │   A. Parser                                                         │   │
│  │      ├── Input: Raw LLM response                                    │   │
│  │      └── Output: HouseholdOutput dataclass                          │   │
│  │                                                                     │   │
│  │   B. Validator                                                      │   │
│  │      ├── Input: HouseholdOutput + State                             │   │
│  │      ├── Check: R1-R9 rules                                         │   │
│  │      └── Output: ValidationResult (errors, warnings)                │   │
│  │                                                                     │   │
│  │   C. Executor                                                       │   │
│  │      ├── If valid: Apply state changes                              │   │
│  │      └── If invalid: Log error, no state change                     │   │
│  │                                                                     │   │
│  │   D. Audit                                                          │   │
│  │      └── Log: Complete trace (regardless of validation)             │   │
│  │                                                                     │   │
│  │   E. Memory Update                                                  │   │
│  │      └── memory.add_experience(decision, year)                      │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Audit Log Specification

### 2.1 Household Audit Trace (`household_audit.jsonl`)

每一行是一個 JSON 物件，記錄一次決策：

```json
{
  "timestamp": "2026-01-05T03:45:00.123456",
  "year": 3,
  
  "agent": {
    "agent_id": "H001",
    "mg": true,
    "tenure": "Owner",
    "region_id": "NJ"
  },
  
  "state_before": {
    "elevated": false,
    "has_insurance": true,
    "cumulative_damage": 50000.0,
    "relocated": false
  },
  
  "context": {
    "subsidy_rate": 0.5,
    "premium_rate": 0.05,
    "flood_occurred": true,
    "memory_retrieved": [
      "Year 2: Flood caused $30,000 damage",
      "Year 2: Purchased insurance"
    ]
  },
  
  "reasoning": {
    "constructs": {
      "TP": {"level": "HIGH", "explanation": "Experienced significant damage"},
      "CP": {"level": "MODERATE", "explanation": "Limited income but subsidy helps"},
      "SP": {"level": "HIGH", "explanation": "Government offers 50% subsidy"},
      "SC": {"level": "MODERATE", "explanation": "Believe I can act with support"},
      "PA": {"level": "PARTIAL", "explanation": "Have insurance but not elevated"}
    },
    "justification": "Given high threat and available subsidy, elevation is best choice."
  },
  
  "action": {
    "decision_number": 2,
    "decision_skill": "elevate_house"
  },
  
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": ["R5: LOW coping but chose elevate_house"],
    "rules_checked": ["R1", "R2", "R3", "R5", "R6", "R7", "R8"]
  },
  
  "state_after": {
    "elevated": true,
    "has_insurance": true,
    "cumulative_damage": 50000.0,
    "relocated": false
  }
}
```

### 2.2 Institutional Audit Trace (`institutional_audit.jsonl`)

```json
{
  "timestamp": "2026-01-05T03:46:00.123456",
  "year": 3,
  "agent_type": "insurance",
  "agent_id": "InsuranceCo",
  
  "state_before": {
    "loss_ratio": 0.85,
    "total_policies": 15,
    "risk_pool": 500000,
    "premium_rate": 0.05
  },
  
  "reasoning": {
    "analysis": "Loss ratio is concerning at 85%",
    "justification": "Raise premium to maintain solvency"
  },
  
  "action": {
    "decision": "RAISE",
    "adjustment_pct": 0.08
  },
  
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  },
  
  "state_after": {
    "premium_rate": 0.054
  }
}
```

### 2.3 Audit Summary (`audit_summary.json`)

```json
{
  "experiment_name": "exp3_multi_agent",
  "simulation_config": {
    "years": 10,
    "n_households": 25,
    "seed": 42,
    "llm_model": "llama3.2:3b",
    "llm_temperature": 0.7
  },
  
  "totals": {
    "household_decisions": 250,
    "institutional_decisions": 20
  },
  
  "decision_distribution": {
    "buy_insurance": {"count": 82, "pct": "32.8%"},
    "elevate_house": {"count": 35, "pct": "14.0%"},
    "relocate": {"count": 53, "pct": "21.2%"},
    "do_nothing": {"count": 80, "pct": "32.0%"}
  },
  
  "construct_distribution": {
    "TP": {"LOW": 40, "MODERATE": 180, "HIGH": 30},
    "CP": {"LOW": 140, "MODERATE": 90, "HIGH": 20},
    "SP": {"LOW": 15, "MODERATE": 170, "HIGH": 65},
    "SC": {"LOW": 60, "MODERATE": 175, "HIGH": 15},
    "PA": {"NONE": 130, "PARTIAL": 80, "FULL": 40}
  },
  
  "validation_summary": {
    "total_errors": 5,
    "total_warnings": 75,
    "error_rate": "2.0%",
    "warning_rate": "30.0%",
    "by_rule": {
      "R1": {"errors": 0, "warnings": 12},
      "R4": {"errors": 3, "warnings": 0},
      "R5": {"errors": 0, "warnings": 45},
      "R8": {"errors": 2, "warnings": 18}
    }
  },
  
  "outcome_metrics": {
    "final_elevated": 23,
    "final_insured": 12,
    "final_relocated": 8,
    "total_damage": 1250000.0,
    "total_claims_paid": 320000.0
  },
  
  "finalized_at": "2026-01-05T03:50:00.000000"
}
```

---

## 3. Validator Log Specification

### 3.1 ValidationResult Structure

```python
@dataclass
class ValidationResult:
    valid: bool                        # True if no errors
    errors: List[str]                  # List of error messages (blocking)
    warnings: List[str]                # List of warning messages (non-blocking)
    rule_checks: Dict[str, bool]       # Which rules were checked and passed
```

### 3.2 Rule Output Format

每個 rule 返回固定格式的訊息：

```
[RULE_ID]: [Description of violation/concern]
```

例如：
```
R1: HIGH threat + HIGH coping but chose do_nothing - possible irrational behavior
R4: Renters cannot elevate property they don't own
R5: LOW coping perception but chose elevate_house - may face affordability issues
R8: PA=NONE doesn't match actual state (elevated=True, insured=False) -> expected PARTIAL
```

### 3.3 Validation Output in Audit

```json
"validation": {
  "valid": false,
  "errors": [
    "R4: Renters cannot elevate property they don't own",
    "R9: Renter cannot elevate_house - valid actions: buy_insurance, relocate, do_nothing"
  ],
  "warnings": [
    "R5: LOW coping perception but chose elevate_house - may face affordability issues"
  ],
  "rules_checked": ["R1", "R2", "R4", "R5", "R6", "R7", "R8", "R9"]
}
```

---

## 4. Implementation Mapping

| Component | File | Function/Class |
|-----------|------|----------------|
| Context Builder | `prompts.py` | `build_household_prompt()` |
| Memory Retrieval | `broker/memory.py` | `CognitiveMemory.retrieve()` |
| LLM Call | `run_experiment.py` | `call_llm()` |
| Parser | `parsers.py` | `parse_household_response()` |
| Validator | `validators.py` | `RuleRegistry.validate()` |
| Executor | `run_experiment.py` | `apply_household_decision()` |
| Audit Writer | `audit_writer.py` | `AuditWriter.write_household_trace()` |
| Memory Update | `broker/memory.py` | `CognitiveMemory.update_after_decision()` |

---

## 5. Data Flow Summary

```
Year Loop:
│
├── For each Household Agent:
│   │
│   ├── 1. CONTEXT
│   │   ├── Read: agent.state.*
│   │   ├── Tool: memory.retrieve(top_k=5)
│   │   ├── Read: environment.*
│   │   └── Build: prompt = build_household_prompt(...)
│   │
│   ├── 2. REASONING
│   │   ├── Call: response = call_llm(prompt)
│   │   └── (LLM generates TP/CP/SP/SC/PA + decision)
│   │
│   └── 3. ACTION
│       ├── Parse: output = parse_household_response(response)
│       ├── Validate: result = validator.validate(output, state)
│       ├── Execute: if result.valid → apply_decision(agent, output)
│       ├── Audit: audit.write_household_trace(output, state, context)
│       └── Memory: agent.memory.update_after_decision(...)
│
├── For Insurance Agent:
│   └── (Similar flow with InsuranceOutput)
│
├── For Government Agent:
│   └── (Similar flow with GovernmentOutput)
│
├── Environment Update:
│   ├── Process: flood_event()
│   ├── Process: calculate_damage()
│   └── Process: insurance_claims()
│
└── End Year
```

---

## 6. Behavior → State Changes

### 6.1 Household State Changes

| Decision | State Changes | Type |
|----------|---------------|------|
| `buy_insurance` | `has_insurance = True` | Annual (resets each year) |
| `elevate_house` | `elevated = True` | Permanent |
| `relocate` | `relocated = True` | Permanent |
| `do_nothing` | (no change) | - |

```python
def apply_household_decision(agent: HouseholdAgent, output: HouseholdOutput):
    """Apply validated decision to agent state."""
    
    if output.decision_skill == "buy_insurance":
        agent.state.has_insurance = True
        # Cost: property_value * premium_rate
        
    elif output.decision_skill == "elevate_house":
        agent.state.elevated = True
        # Cost: ELEVATION_COST * (1 - subsidy_rate)
        
    elif output.decision_skill == "relocate":
        agent.state.relocated = True
        # Remove from active population
        
    # do_nothing: no state change
```

### 6.2 Insurance State Changes

| Decision | State Changes |
|----------|---------------|
| `RAISE` | `premium_rate += adjustment_pct` |
| `LOWER` | `premium_rate -= adjustment_pct` |
| `MAINTAIN` | (no change) |

```python
def apply_insurance_decision(ins: InsuranceAgent, output: InsuranceOutput):
    if output.decision == "RAISE":
        ins.state.premium_rate *= (1 + output.adjustment_pct)
    elif output.decision == "LOWER":
        ins.state.premium_rate *= (1 - output.adjustment_pct)
```

### 6.3 Government State Changes

| Decision | State Changes |
|----------|---------------|
| `INCREASE` | `subsidy_rate += adjustment_pct` |
| `DECREASE` | `subsidy_rate -= adjustment_pct` |
| `MAINTAIN` | (no change) |

```python
def apply_government_decision(gov: GovernmentAgent, output: GovernmentOutput):
    if output.decision == "INCREASE":
        gov.state.subsidy_rate = min(1.0, gov.state.subsidy_rate + output.adjustment_pct)
    elif output.decision == "DECREASE":
        gov.state.subsidy_rate = max(0.0, gov.state.subsidy_rate - output.adjustment_pct)
    
    gov.state.priority_group = output.priority  # "MG" or "ALL"
```

### 6.4 Annual Resets

```python
def annual_reset(households: List[HouseholdAgent]):
    """Reset non-permanent states at year start."""
    for agent in households:
        if not agent.state.relocated:
            # Insurance is annual - resets unless renewed
            agent.state.has_insurance = False
```

---

## 7. Environment Modules (Disaster Risk Framework)

### 7.1 Module Order: Hazard → Exposure → Vulnerability → Finance

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DISASTER RISK FRAMEWORK                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  1. HAZARD                                                          │  │
│   │     - Flood event occurrence (probabilistic)                        │  │
│   │     - Flood characteristics (depth, extent, duration)               │  │
│   │     OUTPUT: FloodEvent                                              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  2. EXPOSURE                                                        │  │
│   │     - Which agents are in flood zone                                │  │
│   │     - Property value at risk                                        │  │
│   │     - Exposure type (building, contents, infrastructure)            │  │
│   │     OUTPUT: ExposureProfile per agent                               │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  3. VULNERABILITY                                                   │  │
│   │     - Building characteristics (elevated, type, age)                │  │
│   │     - Social vulnerability (MG status)                              │  │
│   │     - Damage functions: hazard × exposure → physical damage         │  │
│   │     OUTPUT: DamageEstimate per agent                                │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│                                    ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  4. FINANCE                                                         │  │
│   │     - Insurance claims processing                                   │  │
│   │     - Out-of-pocket costs                                           │  │
│   │     - Buyout program evaluation                                     │  │
│   │     - Government recovery assistance                                │  │
│   │     OUTPUT: FinancialOutcome per agent                              │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   Risk = Hazard × Exposure × Vulnerability                                  │
│   Loss = Risk → Finance (mediated by insurance/government)                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### 7.2 Module 1: HAZARD

**Purpose:** Generate flood events with physical characteristics

```python
@dataclass
class FloodEvent:
    year: int
    occurred: bool
    
    # Physical characteristics
    depth_ft: float = 0.0          # Flood depth in feet
    extent: str = "none"           # "none", "minor", "moderate", "major"
    duration_days: int = 0         # Duration of flooding
    affected_regions: List[str] = field(default_factory=list)
    
    # Derived severity (0.0 - 1.0)
    @property
    def severity(self) -> float:
        if not self.occurred:
            return 0.0
        # Depth-based severity: 1ft=0.2, 3ft=0.5, 6ft=0.8, 10ft+=1.0
        return min(1.0, self.depth_ft / 10.0)


class HazardModule:
    """Generate flood hazard events."""
    
    def __init__(self, config: HazardConfig):
        self.annual_prob = config.annual_probability  # e.g., 0.3
        self.depth_dist = config.depth_distribution   # e.g., Lognormal(2, 1)
    
    def generate(self, year: int) -> FloodEvent:
        """Generate flood event for the year."""
        if random.random() >= self.annual_prob:
            return FloodEvent(year=year, occurred=False)
        
        depth = max(0.5, self.depth_dist.sample())  # Min 0.5 ft
        
        return FloodEvent(
            year=year,
            occurred=True,
            depth_ft=depth,
            extent=self._classify_extent(depth),
            duration_days=int(depth * 2),
            affected_regions=["NJ", "NY"]
        )
    
    def _classify_extent(self, depth: float) -> str:
        if depth < 1: return "minor"
        if depth < 3: return "moderate"
        return "major"
```

---

### 7.3 Module 2: EXPOSURE

**Purpose:** Determine what is at risk for each agent

```python
@dataclass
class ExposureProfile:
    agent_id: str
    
    # Is agent exposed?
    in_flood_zone: bool = True
    
    # Assets at risk
    building_value: float = 0.0    # Structure value
    contents_value: float = 0.0    # Belongings value
    
    # Exposure type
    occupancy_type: str = "residential"  # residential, commercial
    floor_elevation_ft: float = 0.0      # Base floor elevation
    
    # Total exposure
    @property
    def total_exposure(self) -> float:
        return self.building_value + self.contents_value


class ExposureModule:
    """Calculate exposure for each agent."""
    
    def calculate_exposure(
        self, 
        agent: HouseholdAgent, 
        flood: FloodEvent
    ) -> ExposureProfile:
        """Determine agent's exposure to flood event."""
        
        # Check if agent is exposed
        if agent.state.relocated:
            return ExposureProfile(agent_id=agent.state.id, in_flood_zone=False)
        
        if not flood.occurred:
            return ExposureProfile(agent_id=agent.state.id, in_flood_zone=False)
        
        # Calculate floor elevation (elevated houses are higher)
        floor_elevation = 0.0
        if agent.state.elevated:
            floor_elevation = 3.0  # Elevated 3 feet above base
        
        return ExposureProfile(
            agent_id=agent.state.id,
            in_flood_zone=True,
            building_value=agent.state.property_value,
            contents_value=agent.state.property_value * 0.3,  # Contents ~30% of building
            floor_elevation_ft=floor_elevation
        )
```

---

### 7.4 Module 3: VULNERABILITY

**Purpose:** Convert hazard + exposure into physical damage

```python
@dataclass
class DamageEstimate:
    agent_id: str
    
    # Damage amounts
    building_damage: float = 0.0
    contents_damage: float = 0.0
    
    # Damage factors
    damage_ratio: float = 0.0      # Damage / Value (0.0 - 1.0)
    depth_above_floor: float = 0.0  # Water depth above first floor
    
    @property
    def total_damage(self) -> float:
        return self.building_damage + self.contents_damage


class VulnerabilityModule:
    """Calculate damage based on hazard and exposure."""
    
    # FEMA depth-damage functions (simplified)
    DEPTH_DAMAGE_TABLE = {
        # depth_ft: (building_ratio, contents_ratio)
        0: (0.0, 0.0),
        1: (0.15, 0.30),
        2: (0.25, 0.50),
        3: (0.35, 0.65),
        4: (0.45, 0.75),
        6: (0.55, 0.85),
        8: (0.65, 0.90),
        10: (0.75, 0.95),
    }
    
    def calculate_damage(
        self,
        flood: FloodEvent,
        exposure: ExposureProfile,
        agent: HouseholdAgent
    ) -> DamageEstimate:
        """Calculate physical damage."""
        
        if not exposure.in_flood_zone:
            return DamageEstimate(agent_id=exposure.agent_id)
        
        # Calculate depth above floor
        depth_above_floor = max(0, flood.depth_ft - exposure.floor_elevation_ft)
        
        if depth_above_floor <= 0:
            return DamageEstimate(agent_id=exposure.agent_id)
        
        # Look up damage ratios
        bldg_ratio, contents_ratio = self._lookup_damage_ratio(depth_above_floor)
        
        # Apply MG vulnerability factor (housing quality)
        if agent.state.mg:
            bldg_ratio *= 1.2  # 20% higher vulnerability
        
        # Calculate damages
        building_damage = exposure.building_value * min(1.0, bldg_ratio)
        contents_damage = exposure.contents_value * min(1.0, contents_ratio)
        
        return DamageEstimate(
            agent_id=exposure.agent_id,
            building_damage=building_damage,
            contents_damage=contents_damage,
            damage_ratio=bldg_ratio,
            depth_above_floor=depth_above_floor
        )
    
    def _lookup_damage_ratio(self, depth: float) -> Tuple[float, float]:
        """Linear interpolation of depth-damage function."""
        depths = sorted(self.DEPTH_DAMAGE_TABLE.keys())
        for i, d in enumerate(depths):
            if depth <= d:
                if i == 0:
                    return self.DEPTH_DAMAGE_TABLE[d]
                prev_d = depths[i-1]
                ratio = (depth - prev_d) / (d - prev_d)
                prev_val = self.DEPTH_DAMAGE_TABLE[prev_d]
                curr_val = self.DEPTH_DAMAGE_TABLE[d]
                return (
                    prev_val[0] + ratio * (curr_val[0] - prev_val[0]),
                    prev_val[1] + ratio * (curr_val[1] - prev_val[1])
                )
        return self.DEPTH_DAMAGE_TABLE[depths[-1]]
```

---

### 7.5 Module 4: FINANCE

**Purpose:** Process financial outcomes (insurance, out-of-pocket, buyout)

```python
@dataclass
class FinancialOutcome:
    agent_id: str
    year: int
    
    # Damage (from vulnerability module)
    total_damage: float = 0.0
    
    # Insurance
    has_insurance: bool = False
    claim_filed: bool = False
    claim_approved: bool = False
    insurance_payout: float = 0.0
    deductible_paid: float = 0.0
    
    # Out-of-pocket
    out_of_pocket: float = 0.0
    
    # Buyout (if applicable)
    buyout_eligible: bool = False
    buyout_offer: Optional[float] = None
    
    # Government assistance
    fema_ia_received: float = 0.0  # FEMA Individual Assistance


class FinanceModule:
    """Process financial outcomes for damaged households."""
    
    NFIP_BUILDING_LIMIT = 250_000
    NFIP_CONTENTS_LIMIT = 100_000
    DEFAULT_DEDUCTIBLE = 1_000
    
    def process(
        self,
        agent: HouseholdAgent,
        damage: DamageEstimate,
        insurance: InsuranceAgent
    ) -> FinancialOutcome:
        """Process financial outcome for agent."""
        
        outcome = FinancialOutcome(
            agent_id=agent.state.id,
            year=damage.year if hasattr(damage, 'year') else 0,
            total_damage=damage.total_damage,
            has_insurance=agent.state.has_insurance
        )
        
        if damage.total_damage <= 0:
            return outcome
        
        # Process insurance claim
        if agent.state.has_insurance:
            outcome = self._process_claim(outcome, damage, insurance)
        
        # Calculate out-of-pocket
        outcome.out_of_pocket = max(0, 
            outcome.total_damage - outcome.insurance_payout
        )
        
        # Check buyout eligibility (future)
        # outcome = self._check_buyout(outcome, agent, government)
        
        return outcome
    
    def _process_claim(
        self,
        outcome: FinancialOutcome,
        damage: DamageEstimate,
        insurance: InsuranceAgent
    ) -> FinancialOutcome:
        """Process insurance claim."""
        outcome.claim_filed = True
        
        # NFIP limits
        building_payout = min(damage.building_damage, self.NFIP_BUILDING_LIMIT)
        contents_payout = min(damage.contents_damage, self.NFIP_CONTENTS_LIMIT)
        
        gross_payout = building_payout + contents_payout
        
        # Apply deductible
        outcome.deductible_paid = min(self.DEFAULT_DEDUCTIBLE, gross_payout)
        outcome.insurance_payout = max(0, gross_payout - outcome.deductible_paid)
        outcome.claim_approved = True
        
        # Update insurance metrics
        insurance.state.total_claims += 1
        insurance.state.total_payout += outcome.insurance_payout
        
        return outcome
```

---

### 7.6 Module Integration Flow

```python
def process_flood_year(
    year: int,
    households: List[HouseholdAgent],
    insurance: InsuranceAgent,
    government: GovernmentAgent
) -> Dict[str, FinancialOutcome]:
    """Process a flood year through all modules."""
    
    # 1. HAZARD
    hazard = HazardModule(config)
    flood = hazard.generate(year)
    
    if not flood.occurred:
        return {}  # No flood, no processing
    
    outcomes = {}
    
    # 2-4. For each agent: Exposure → Vulnerability → Finance
    exposure_mod = ExposureModule()
    vuln_mod = VulnerabilityModule()
    finance_mod = FinanceModule()
    
    for agent in households:
        # 2. EXPOSURE
        exposure = exposure_mod.calculate_exposure(agent, flood)
        
        # 3. VULNERABILITY
        damage = vuln_mod.calculate_damage(flood, exposure, agent)
        
        # 4. FINANCE
        outcome = finance_mod.process(agent, damage, insurance)
        
        # Update agent state
        agent.state.cumulative_damage += damage.total_damage
        agent.state.cumulative_oop += outcome.out_of_pocket
        
        # Update memory
        if damage.total_damage > 0:
            agent.memory.update_after_flood(damage.total_damage, year)
        
        outcomes[agent.state.id] = outcome
    
    return outcomes
```

---

### 7.7 Agent Observable Outputs

**What Household agents CAN see (after flood):**

| Field | Description | Source |
|-------|-------------|--------|
| `flood_occurred` | Was there a flood? | Hazard |
| `my_damage` | My total damage | Vulnerability |
| `claim_approved` | Was my claim approved? | Finance |
| `insurance_payout` | How much did I receive? | Finance |
| `out_of_pocket` | How much do I pay? | Finance |
| `buyout_eligible` | Am I eligible for buyout? | Finance (future) |

**What Household agents CANNOT see:**

| Field | Description | Reason |
|-------|-------------|--------|
| `neighbor_damage` | Others' damage | Information asymmetry |
| `total_claims` | Number of claims filed | Private |
| `insurance_reserves` | Insurance finances | Private |
| `government_budget` | Remaining budget | Not public |
---

## 8. Insurance Type Configuration

```python
@dataclass
class InsuranceAgentState:
    agent_id: str = "InsuranceCo"
    
    # Type configuration
    insurance_type: str = "NFIP"  # "NFIP", "private", "mixed"
    
    # NFIP: Government-backed
    #   - Regulated rates
    #   - Universal coverage
    #   - Federal reinsurance
    
    # Private: Market-based
    #   - Risk-based pricing
    #   - May deny coverage
    #   - Higher limits available
    
    # Metrics
    premium_rate: float = 0.05
    loss_ratio: float = 0.0
    total_policies: int = 0
    total_claims: int = 0
    total_payout: float = 0.0
    risk_pool: float = 1_000_000
```

---

## 9. Future: Buyout Program (Relocation)

> **Note:** 待後續實作

```python
class BuyoutProgram:
    """Government buyout/acquisition program."""
    
    def check_eligibility(
        self, 
        agent: HouseholdAgent,
        government: GovernmentAgent
    ) -> BuyoutEligibility:
        """
        Eligibility factors:
        - Repetitive loss (2+ floods)
        - Severe repetitive loss
        - Government budget available
        - Priority group
        """
        is_repetitive = agent.state.flood_count >= 2
        priority_match = (
            government.state.priority_group == "ALL" or
            (government.state.priority_group == "MG" and agent.state.mg)
        )
        budget_available = government.state.buyout_budget > 0
        
        return BuyoutEligibility(
            eligible=is_repetitive and priority_match and budget_available,
            reason=...
        )
```

**Household 可見：**
- `buyout_eligible: bool`
- `buyout_offer: Optional[float]`
