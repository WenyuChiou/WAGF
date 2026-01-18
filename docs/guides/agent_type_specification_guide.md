# Agent Type Specification Guide

This document provides templates and guidelines for defining agent types in the BaseAgent framework.
All parameters must be 0-1 normalized with documented sources.

---

## Template: Agent Specification YAML

```yaml
# =============================================================================
# AGENT TYPE: [Name]
# Domain: [flood/healthcare/supply_chain/etc.]
# Literature: [Primary citation]
# =============================================================================

agents:
  - name: "[AgentName]"
    type: "[agent_type_id]"
    
    # -------------------------------------------------------------------------
    # ROLE & PERSONA
    # -------------------------------------------------------------------------
    role: "[One-line role description]"
    persona: |
      [Multi-line persona for LLM prompts]
      
      OBJECTIVES (by priority):
      1. [Primary objective]
      2. [Secondary objective]
      
      CONSTRAINTS:
      - [Key constraint 1]
      - [Key constraint 2]
    
    # -------------------------------------------------------------------------
    # STATE PARAMETERS
    # Each parameter must have:
    # - name: Unique identifier
    # - raw_range: [min, max] in original units
    # - initial: Starting value in raw scale
    # - description: What it represents
    # - literature: Citation for calibration
    # -------------------------------------------------------------------------
    state:
      - name: "[param_name]"
        raw_range: [min, max]
        initial: value
        description: "[What this measures]"
        literature: "[Author Year - specific finding]"
    
    # -------------------------------------------------------------------------
    # OBJECTIVES
    # Each objective must have:
    # - target: [min, max] in 0-1 scale
    # - weight: Importance (sum should = 1.0)
    # - literature: Why this target range
    # -------------------------------------------------------------------------
    objectives:
      - name: "[objective_name]"
        param: "[which_state_param]"
        target: [0.4, 0.6]
        weight: 0.5
        literature: "[Author Year - target justification]"
    
    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # Institutional/regulatory limits on actions
    # -------------------------------------------------------------------------
    constraints:
      - name: "[constraint_name]"
        param: "[which_param]"
        max_change: 0.15  # Max change per period (0-1 scale)
        bounds: [0, 1]    # Hard limits
        literature: "[Regulation or norm source]"
    
    # -------------------------------------------------------------------------
    # SKILLS (Actions)
    # -------------------------------------------------------------------------
    skills:
      - id: "[skill_id]"
        description: "[What this action does]"
        affects: "[param_name]"
        direction: "increase|decrease|none"
        literature: "[Decision rule source]"
    
    # -------------------------------------------------------------------------
    # PERCEPTION (What agent observes)
    # -------------------------------------------------------------------------
    perception:
      - type: "environment|agent"
        source: "[source_name]"
        params: ["param1", "param2"]
```

---

## Flood Domain Agent Specifications

### 1. Household Agent

| Parameter | Raw Range | Initial | 0-1 | Literature |
|-----------|-----------|---------|-----|------------|
| income | $20K-$200K | $60K | 0.22 | Census ACS 2020 |
| property_value | $50K-$1M | $300K | 0.26 | Zillow ZHVI 2023 |
| cumulative_damage | $0-$500K | $0 | 0.0 | FEMA claims data |
| threat_perception | 0-1 | varies | - | Bubeck 2012 (PMT) |
| coping_capacity | 0-1 | varies | - | Grothmann 2006 |
| trust_gov | 0-1 | 0.5 | - | Wachinger 2013 |
| trust_ins | 0-1 | 0.5 | - | Kousky 2018 |

**Objectives:**
| Objective | Target (0-1) | Weight | Literature |
|-----------|-------------|--------|------------|
| minimize_damage | 0.0-0.2 | 0.40 | Botzen 2009 |
| maintain_affordability | 0.3-0.7 | 0.35 | de Moel 2014 |
| preserve_place_attachment | 0.5-1.0 | 0.25 | Bonaiuto 2016 |

---

### 2. Insurance Agent

| Parameter | Raw Range | Initial | 0-1 | Literature |
|-----------|-----------|---------|-----|------------|
| loss_ratio | 0-150% | 60% | 0.40 | NFIP Annual Report |
| solvency | $0-$2M | $1M | 0.50 | Dong 1996 |
| premium_rate | 2%-15% | 5% | 0.23 | Risk Rating 2.0 |
| market_share | 0-100% | 30% | 0.30 | Kousky 2017 |

**Objectives:**
| Objective | Target (0-1) | Weight | Literature |
|-----------|-------------|--------|------------|
| maintain_solvency | 0.50-1.0 | 0.40 | Cummins 1988 |
| target_loss_ratio | 0.40-0.53 | 0.35 | NFIP 60-80% |
| grow_market | 0.30-0.60 | 0.25 | Kousky 2017 |

**Constraints:**
| Constraint | Max Change | Bounds | Literature |
|------------|------------|--------|------------|
| rate_change_limit | ±15%/yr | 0-100% | Risk Rating 2.0 |
| solvency_floor | - | 25%-100% | State regulations |

---

### 3. Government Agent

| Parameter | Raw Range | Initial | 0-1 | Literature |
|-----------|-----------|---------|-----|------------|
| budget_used | $0-$500K | $0 | 0.0 | FEMA HMGP |
| subsidy_rate | 20%-95% | 50% | 0.40 | HMGP cost-share |
| mg_adoption | 0-100% | 0% | 0.0 | Siders 2019 |
| equity_gap | 0-100% | 0% | 0.0 | Emrich 2022 |

**Objectives:**
| Objective | Target (0-1) | Weight | Literature |
|-----------|-------------|--------|------------|
| increase_mg_adoption | 0.40-0.70 | 0.40 | Siders 2021 |
| reduce_equity_gap | 0.0-0.15 | 0.35 | Emrich 2022 |
| budget_efficiency | 0.70-0.90 | 0.25 | FEMA metrics |

**Constraints:**
| Constraint | Max Change | Bounds | Literature |
|------------|------------|--------|------------|
| subsidy_change | ±15%/yr | 20%-95% | Policy stability |
| emergency_reserve | - | 0%-90% | FEMA rules |

---

## Adding a New Agent Type

1. **Identify Literature**: Find 3-5 key papers calibrating your agent's behavior
2. **Define State**: List measurable quantities with real-world ranges
3. **Set Objectives**: What does this agent optimize? With what priorities?
4. **Add Constraints**: What institutional rules limit actions?
5. **Create Skills**: What decisions can this agent make?
6. **Write Persona**: How should LLM reason as this agent?
7. **Validate**: Run simulation, compare to empirical data

---

## Key Literature References

| Topic | Citation | Key Finding |
|-------|----------|-------------|
| PMT Framework | Bubeck 2012 | Threat/Coping appraisal model |
| Insurance Behavior | Kousky 2017 | NFIP uptake determinants |
| Equity in Adaptation | Siders 2021 | MG community barriers |
| Loss Ratio Targets | NFIP 2023 | 60-80% actuarial target |
| Subsidy Effects | Gourevitch 2025 | Takeup elasticity |
| Place Attachment | Bonaiuto 2016 | Relocation resistance |
