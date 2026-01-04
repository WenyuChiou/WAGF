# Validator Design Documentation

## Overview

This document describes the **literature-backed validator design** for the Governed Broker Framework, covering both **single-agent** (v2_skill_governed) and **multi-agent** (exp3) experiments.

All validator rules are empirically supported by peer-reviewed research (2010-2024).

---

## Literature Foundation

### BibTeX Files (Zotero Import Ready)

| File | Entries | Scope |
|------|---------|-------|
| `docs/references/pmt_flood_literature.bib` | 14 | PMT Global (2006-2024) |
| `docs/references/us_flood_literature.bib` | 20 | 🇺🇸 US Flood (2012-2024) |

**Total: 34 verified studies with DOIs**

---

## Single-Agent Validators (v2_skill_governed)

### Location: `validators/skill_validators.py`

### Enabled Validators

```python
def create_default_validators():
    return [
        SkillAdmissibilityValidator(),      # Technical
        ContextFeasibilityValidator(),       # Technical
        InstitutionalConstraintValidator(),  # Technical
        EffectSafetyValidator(),             # Technical
        PMTConsistencyValidator(),           # Theory-based ← LITERATURE BACKED
    ]
```

### PMTConsistencyValidator Rules

| Rule | Logic | Error Message |
|------|-------|---------------|
| **R1** | HIGH_THREAT + HIGH_EFFICACY + do_nothing | PMT inconsistency |
| **R2** | LOW_THREAT + relocate | Claims low threat but chose relocate |
| **R3** | Flood occurred + claims safe | Flood Response: Claims safe despite flood |
| **R4** | CANNOT_AFFORD + expensive | Claims cannot afford but chose expensive |

---

## Rule → Literature Mapping

### Rule 1: HIGH TP + HIGH CP + do_nothing = Error

**Theory**: PMT predicts high threat + high coping → protection motivation → action

| Study | Year | N | DOI | Key Finding |
|-------|------|---|-----|-------------|
| **Bamberg et al.** | 2017 | 35,419 | 10.1016/j.jenvp.2017.08.001 | Meta: CP r=0.30, TP r=0.23 |
| Babcicky & Seebauer | 2019 | 2,007 | 10.1080/13669877.2018.1485175 | SEM: Protective vs non-protective routes |
| Bubeck et al. | 2018 | 1,600+ | 10.1111/risa.12938 | CP > TP as predictor |
| Botzen et al. | 2019 | 1,000+ | 10.1111/risa.13318 | High efficacy → action (NYC) |
| Bubeck et al. | 2023 | 2,680 | 10.1177/00139165231176069 | Panel: longitudinal confirmation |

**Verdict**: ★★★★★ VERY STRONG (meta-analytic + multi-national)

---

### Rule 2: LOW TP + relocate = Error

**Theory**: Relocation is extreme action requiring high threat perception

| Study | Year | N | DOI | Key Finding |
|-------|------|---|-----|-------------|
| **Weyrich et al.** | 2020 | 1,019 | 10.5194/nhess-20-287-2020 | Avoidance requires highest threat |
| Rogers | 1983 | - | Book | TP necessary for action initiation |
| Bukvic & Barnett | 2023 | 1,450 | 10.1016/j.jenvman.2022.116429 | Place attachment barriers (US East Coast) |

**Verdict**: ★★★★☆ STRONG (theoretical + empirical)

---

### Rule 3: Flood occurred + claims safe = Error

**Theory**: Flood experience → increased threat perception (salience effect)

| Study | Year | N | DOI | Key Finding |
|-------|------|---|-----|-------------|
| **Choi et al.** | 2024 | County | 10.1029/2023EF004110 | +7% insurance post-flood (US) |
| Bubeck et al. | 2012 | 2,200+ | 10.1111/j.1539-6924.2011.01783.x | Experience → TP increase |
| Reynaud et al. | 2013 | N/A | 10.1057/gpp.2013.16 | Vietnam: experience → perception |
| Botzen et al. | 2024 | 871 | 10.1111/risa.14314 | Hurricane Dorian real-time survey |

**Verdict**: ★★★★★ VERY STRONG (US + cross-cultural)

---

### Rule 4: CANNOT_AFFORD + expensive = Error

**Theory**: Financial capacity (self-efficacy) required for expensive measures

| Study | Year | N | DOI | Key Finding |
|-------|------|---|-----|-------------|
| **Bamberg et al.** | 2017 | 35,419 | 10.1016/j.jenvp.2017.08.001 | Response cost in CP |
| Botzen et al. | 2019 | 1,000+ | 10.1111/risa.13318 | Self-efficacy predicts adoption |
| Rufat et al. | 2024 | 1,000+ | 10.1111/risa.14130 | Financial capacity affects measures |
| Billings et al. | 2022 | Credit | 10.1016/j.jfineco.2021.11.006 | Hurricane Harvey financial impact |

**Verdict**: ★★★★★ VERY STRONG (meta-analytic + US empirical)

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

### ConstructConsistencyValidator Rules (Multi-Agent Extension)

| Rule | Logic | Severity | Literature |
|------|-------|----------|------------|
| R1 | HIGH TP + HIGH CP + do_nothing | Error | Bamberg 2017, Babcicky 2019 |
| R2 | LOW CP + expensive action | Error | Bamberg 2017, Botzen 2019 |
| R3 | LOW TP + extreme action | Error | Weyrich 2020, Rogers 1983 |
| R4 | LOW SP + LOW TP + insurance | Error | Lindell & Perry 2012 (PADM) |
| R5 | LOW SP + insurance (with threat) | Warning | Trust literature |
| VALID | HIGH TP + LOW CP + do_nothing | OK | Grothmann 2006 (fatalism) |

### Additional Literature for Multi-Agent

| Construct | Study | Key Finding |
|-----------|-------|-------------|
| Social Capital | Alaniz et al. 2024 | Binghamton NY: Bonding SC → mitigation |
| Place Attachment | Bukvic et al. 2022 | 16-indicator index; rural > urban |
| Managed Retreat | Mach et al. 2019 | 40,000+ FEMA buyouts analyzed |
| Climate Migration | Shu et al. 2023 | Flood → population decline |

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

## References

### Core Theoretical
1. Rogers, R. W. (1983). PMT Original. *In Social psychophysiology*.
2. Grothmann, T., & Reusswig, F. (2006). *Natural Hazards*, 38, 101-120. DOI: 10.1007/s11069-005-8604-6
3. Bamberg, S., et al. (2017). *J. Environmental Psychology*, 54, 116-126. DOI: 10.1016/j.jenvp.2017.08.001
4. Lindell, M. K., & Perry, R. W. (2012). *Risk Analysis*, 32, 616-632. DOI: 10.1111/j.1539-6924.2011.01647.x

### US Empirical (2019-2024)
5. Botzen et al. (2019). *Risk Analysis*, 39, 2143-2159. DOI: 10.1111/risa.13318
6. Choi et al. (2024). *Earth's Future*, 12, e2023EF004110. DOI: 10.1029/2023EF004110
7. Rufat et al. (2024). *Risk Analysis*, 44, 141-154. DOI: 10.1111/risa.14130
8. Mach et al. (2019). *Science Advances*, 5, eaax8995. DOI: 10.1126/sciadv.aax8995
9. Bukvic & Barnett (2023). *J. Environ. Management*, 325, 116429. DOI: 10.1016/j.jenvman.2022.116429

### BibTeX Import
```
Import to Zotero: File > Import > Select .bib file
- docs/references/pmt_flood_literature.bib (14 entries)
- docs/references/us_flood_literature.bib (20 entries)
```

---

*Last Updated: 2026-01-04*
*All DOIs verified via https://doi.org/*
