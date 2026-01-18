# Institutional Agent Behavior Specification

Each agent type must define:
1. **Role** - What this agent represents
2. **Behavior Pattern** - Decision rules and responses
3. **Environment Effects** - How actions change the world
4. **Audit Requirements** - What to log for analysis
5. **Validation Rules** - Constraints on valid behavior

---

## Insurance Agent (InsuranceCo)

### 1. Role Definition

| Aspect | Description |
|--------|-------------|
| **Entity** | Regional flood insurance company |
| **Responsibility** | Manage risk pool, price policies, ensure solvency |
| **Decision Frequency** | Annual (Phase 1, before households decide) |
| **Stakeholders** | Policyholders, shareholders, regulators |

### 2. Behavior Pattern

| Trigger | Condition | Action | Magnitude |
|---------|-----------|--------|-----------|
| Loss spike | loss_ratio > 0.8 | RAISE_PREMIUM | +5% to +15% |
| Profitable | loss_ratio < 0.4 AND market_share < 0.4 | LOWER_PREMIUM | -5% to -10% |
| Stable | 0.4 ≤ loss_ratio ≤ 0.8 | MAINTAIN | 0% |
| Solvency crisis | solvency < 0.3 | RAISE_PREMIUM | +10% to +20% |

**Literature Basis:**
- Dong 1996: Solvency-based pricing
- Kousky 2017: NFIP 60-80% loss ratio target
- Risk Rating 2.0: Annual adjustment limits

### 3. Environment/Policy Effects

| Action | Effect on Environment | Effect on Households |
|--------|----------------------|---------------------|
| RAISE_PREMIUM | - | ↓ Uptake (MG: -15%, NMG: -5%) |
| LOWER_PREMIUM | - | ↑ Uptake (MG: +10%, NMG: +5%) |
| MAINTAIN | - | Stable uptake |

**Feedback Loop:**
```
Premium ↑ → Uptake ↓ → Premium Revenue ↓ → Solvency ↓ (if claims continue)
Premium ↓ → Uptake ↑ → Premium Revenue ↑ → Can absorb more claims
```

### 4. Audit Requirements

| Field | Type | Description |
|-------|------|-------------|
| `year` | int | Simulation year |
| `loss_ratio` | float | Claims / Premiums (pre-decision) |
| `solvency` | float | Normalized capital reserve |
| `premium_rate` | float | Current rate (0-1 normalized) |
| `decision` | str | RAISE / LOWER / MAINTAIN |
| `adjustment_pct` | float | Percentage change applied |
| `market_share` | float | Policies / Eligible HH |
| `justification` | str | LLM or rule-based reasoning |

**Audit File:** `institutional_audit.jsonl`

### 5. Validation Rules

| Rule | Condition | Error Level |
|------|-----------|-------------|
| Rate bounds | 0.02 ≤ premium_rate ≤ 0.15 | ERROR |
| Max change | \|Δrate\| ≤ 0.15 per year | WARNING |
| Solvency floor | solvency > 0 | ERROR |
| Decision valid | decision ∈ {RAISE, LOWER, MAINTAIN} | ERROR |

---

## Government Agent (StateGov)

### 1. Role Definition

| Aspect | Description |
|--------|-------------|
| **Entity** | State hazard mitigation office (FEMA-funded) |
| **Responsibility** | Subsidize adaptation, reduce equity gap |
| **Decision Frequency** | Annual (Phase 1, before households decide) |
| **Stakeholders** | MG communities, taxpayers, federal oversight |

### 2. Behavior Pattern

| Trigger | Condition | Action | Magnitude |
|---------|-----------|--------|-----------|
| Post-flood + low MG | flood_prev AND mg_adoption < 0.3 | INCREASE_SUBSIDY | +10% |
| Budget tight | budget_remaining < 0.1 | DECREASE_SUBSIDY | -10% |
| Equity gap high | equity_gap > 0.2 | TARGET_MG_OUTREACH | trust +0.1 |
| Stable | else | MAINTAIN | 0% |

**Literature Basis:**
- Siders 2021: Equity in managed retreat
- Emrich 2022: Distributive inequity metrics
- FEMA HMGP: 75% federal cost-share baseline

### 3. Environment/Policy Effects

| Action | Effect on Environment | Effect on Households |
|--------|----------------------|---------------------|
| INCREASE_SUBSIDY | budget_used ↑ | MG elevation ↑ 15-25% |
| DECREASE_SUBSIDY | budget_used ↓ | MG elevation ↓ 10-15% |
| TARGET_MG_OUTREACH | - | MG trust_gov ↑ 0.1 |
| MAINTAIN | - | Stable |

**Feedback Loop:**
```
Subsidy ↑ → MG Adoption ↑ → Equity Gap ↓ → Budget depletes faster
Subsidy ↓ → MG Adoption ↓ → Equity Gap ↑ → Budget conserved
```

### 4. Audit Requirements

| Field | Type | Description |
|-------|------|-------------|
| `year` | int | Simulation year |
| `budget_used` | float | Normalized (0-1) |
| `subsidy_rate` | float | Current rate (0-1) |
| `mg_adoption` | float | MG protection rate |
| `nmg_adoption` | float | NMG protection rate |
| `equity_gap` | float | NMG - MG adoption |
| `decision` | str | INCREASE / DECREASE / MAINTAIN / OUTREACH |
| `adjustment_pct` | float | Percentage change |
| `flood_prev_year` | bool | Context trigger |
| `justification` | str | Reasoning |

**Audit File:** `institutional_audit.jsonl`

### 5. Validation Rules

| Rule | Condition | Error Level |
|------|-----------|-------------|
| Subsidy bounds | 0.2 ≤ subsidy_rate ≤ 0.95 | ERROR |
| Max change | \|Δsubsidy\| ≤ 0.15 per year | WARNING |
| Emergency reserve | budget_used ≤ 0.9 | WARNING |
| Decision valid | decision ∈ {INCREASE, DECREASE, MAINTAIN, OUTREACH} | ERROR |
| MG priority | if mg_adoption < nmg_adoption, favor MG | WARNING |

---

## Validation Pipeline

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Decision                       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│            Constraint Validation (BaseAgent)            │
│  - Check max_change per param                           │
│  - Check bounds                                         │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│           Institutional Rules (Validator)               │
│  - Insurance: solvency floor, rate limits               │
│  - Government: budget reserve, MG priority              │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Audit Logging (AuditWriter)                │
│  - Log decision + context                               │
│  - Flag validation warnings                             │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Checklist

- [x] Define role for each agent type
- [x] Specify behavior triggers and actions
- [x] Document environment effects
- [ ] Create InstitutionalValidator class
- [ ] Add audit fields to AuditWriter
- [ ] Integrate validation into run_experiment.py
