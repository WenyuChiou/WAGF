# Validator Design Documentation

## Overview

This document describes the validator design for the Governed Broker Framework, covering both **single-agent** (v2_skill_governed) and **multi-agent** (exp3) experiments.

---

## Single-Agent Validators (v2_skill_governed)

### Enabled Validators

```python
def create_default_validators():
    return [
        SkillAdmissibilityValidator(),      # Technical
        ContextFeasibilityValidator(),       # Technical
        InstitutionalConstraintValidator(),  # Technical
        EffectSafetyValidator(),             # Technical
        PMTConsistencyValidator(),           # Theory-based ← REQUIRES LITERATURE
    ]
```

### PMTConsistencyValidator Rules

Based on Protection Motivation Theory (Rogers, 1983; Grothmann & Reusswig, 2006).

| Rule | Logic | Error Message |
|------|-------|---------------|
| R1 | HIGH_THREAT + HIGH_EFFICACY + do_nothing | PMT inconsistency |
| R2 | LOW_THREAT + relocate | Claims low threat but chose relocate |
| R3 | Flood occurred + claims safe | Flood Response: Claims safe despite flood |
| R4 | CANNOT_AFFORD + expensive | Claims cannot afford but chose expensive |

### Empirical Support (2010-2024)

**10 studies with verified DOIs across 5+ countries:**

| Rule | Primary Study | N | DOI |
|------|--------------|---|-----|
| R1 | Bamberg et al. (2017) | 35,419 | 10.1016/j.jenvp.2017.08.001 |
| R2 | Weyrich et al. (2020) | 1,019 | 10.5194/nhess-20-287-2020 |
| R3 | Choi et al. (2024) | County | 10.1029/2023EF004110 |
| R4 | Bamberg et al. (2017) | 35,419 | 10.1016/j.jenvp.2017.08.001 |

**Key Findings:**
- Coping appraisal (r=0.30) > Threat appraisal (r=0.23) as predictor
- Flood experience increases threat perception (+7% insurance uptake)
- Self-efficacy required for expensive measure adoption

---

## Multi-Agent Validators (exp3)

### Proposed Validators

| Validator | Agent Types | Purpose |
|-----------|-------------|---------|
| AgentTypeAdmissibilityValidator | All | Skill ↔ agent type match |
| **ConstructConsistencyValidator** | Household | TP/CP/SP/SC/PA consistency |
| MGSubsidyConsistencyValidator | Household | MG status ↔ subsidy access |
| InsurancePolicyValidator | Insurance | Premium/coverage constraints |
| GovernmentBudgetValidator | Government | Budget allocation rules |

### ConstructConsistencyValidator Rules (Multi-Agent)

| Rule | Logic | Severity | Literature |
|------|-------|----------|------------|
| R1 | HIGH TP + HIGH CP + do_nothing | Error | Grothmann (2006), Bamberg (2017) |
| R2 | LOW CP + expensive action | Error | Bamberg (2017), Botzen (2019) |
| R3 | LOW TP + extreme action | Error | Rogers (1983), Weyrich (2020) |
| R4 | LOW SP + LOW TP + insurance | Error | Lindell & Perry (2012) PADM |
| R5 | LOW SP + insurance (with threat) | Warning | Trust literature |
| VALID | HIGH TP + LOW CP + do_nothing | OK | Grothmann (2006) fatalism pathway |

---

## Constructs Definition

### Single-Agent (v2)
PMT 6-factor model from prompt:
- Perceived Severity, Vulnerability
- Response Efficacy, Self-Efficacy
- Response Cost, Maladaptive Rewards

### Multi-Agent (exp3)
5 explicit constructs with levels:
- **TP** (Threat Perception): LOW/MODERATE/HIGH
- **CP** (Coping Perception): LOW/MODERATE/HIGH
- **SP** (Stakeholder Perception): LOW/MODERATE/HIGH
- **SC** (Self-Confidence): LOW/MODERATE/HIGH
- **PA** (Previous Adaptation): NONE/PARTIAL/FULL

---

## Literature Files

| File | Contents |
|------|----------|
| `docs/references/claude_code_search_results.md` | 10 PMT studies (2010-2024) |
| `docs/references/pmt_validator_study_mapping.md` | Rule → Study mapping |
| `docs/references/pmt_validator_references.md` | APA citations + DOIs |

---

## References

### Core Theoretical
1. Rogers, R. W. (1983). PMT Original. *In Social psychophysiology*.
2. Grothmann, T., & Reusswig, F. (2006). *Natural Hazards*, 38, 101-120.
3. Bamberg, S., et al. (2017). *J. Environmental Psychology*, 54, 116-126.
4. Lindell, M. K., & Perry, R. W. (2012). *Risk Analysis*, 32, 616-632.

### Recent Empirical (2019-2024)
5. Babcicky & Seebauer (2019). *J. Risk Research*, 22, 1503-1521.
6. Botzen et al. (2019). *Risk Analysis*, 39, 2143-2159.
7. Bubeck et al. (2023). *Environment and Behavior*, 55, 211-235.
8. Choi et al. (2024). *Earth's Future*, 12, e2023EF004110.
9. Rufat et al. (2024). *Risk Analysis*, 44, 141-154.

All DOIs verified via https://doi.org/
