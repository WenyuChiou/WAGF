# LLM-Governed Multi-Agent Flood Adaptation Simulation (Paper 3)

> **Target Journal**: Water Resources Research (WRR)
> **Framework**: SAGE (Simulated Agent Governance Engine) with SAGA 3-tier ordering
> **Study Area**: Passaic River Basin (PRB), New Jersey
> **Status**: ICC validation complete (TP ICC=0.964, CP ICC=0.947), primary experiments in progress

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Theoretical Foundations](#2-theoretical-foundations)
3. [Research Questions & Hypotheses](#3-research-questions--hypotheses)
4. [Simulation Architecture](#4-simulation-architecture)
5. [Agent Initialization Pipeline](#5-agent-initialization-pipeline)
6. [PMT Construct Design](#6-pmt-construct-design)
7. [Memory Architecture](#7-memory-architecture)
8. [Governance Framework](#8-governance-framework)
9. [Institutional Agents](#9-institutional-agents)
10. [Social Network & Information Channels](#10-social-network--information-channels)
11. [Hazard & Depth-Damage Model](#11-hazard--depth-damage-model)
12. [Validation Framework](#12-validation-framework)
13. [Empirical Benchmarks](#13-empirical-benchmarks)
14. [ICC Probing Protocol](#14-icc-probing-protocol)
15. [How to Run](#15-how-to-run)
16. [Output Structure](#16-output-structure)
17. [Key Differences from Traditional ABM](#17-key-differences-from-traditional-abm)
18. [Computational Requirements](#18-computational-requirements)
19. [Glossary](#19-glossary)
20. [References](#20-references)

---

## 1. Project Overview

### Core Claim

We claim **structural plausibility**, not predictive accuracy. The LLM-ABM produces individually heterogeneous adaptation trajectories that fall within empirically defensible aggregate ranges—something traditional equation-based ABMs cannot achieve without drastically more complex specification.

### What This Framework Demonstrates

1. **Memory-mediated cognition** replaces parametric threat perception (TP) decay equations
2. **Emergent constructs** — PMT appraisals are LLM outputs, not pre-specified inputs
3. **Individual heterogeneity** — each agent accumulates unique experiences and memories
4. **Endogenous institutions** — government and insurance agents are LLM-driven
5. **Multi-channel social influence** — observation, gossip, news media, social media

### Study Area

- **Passaic River Basin (PRB)**, New Jersey
- 27 census tracts covering urban, suburban, and rural flood-prone areas
- Real flood hazard data: 13 ESRI ASCII raster files (2011-2023)
- Grid size: ~457 × 411 cells, 30m resolution
- Historical events: Hurricane Irene (2011), Superstorm Sandy (2012), Ida (2021)

---

## 2. Theoretical Foundations

### Protection Motivation Theory (PMT)

Our framework is grounded in **Protection Motivation Theory** (Rogers, 1983; Grothmann & Reusswig, 2006), which posits that protective behavior emerges from two cognitive appraisal processes:

| Appraisal | Constructs | What It Assesses |
|-----------|------------|------------------|
| **Threat Appraisal** | TP (Threat Perception) | Perceived probability and severity of flood damage |
| **Coping Appraisal** | CP (Coping Perception) | Self-efficacy and response efficacy for protective actions |

We extend PMT with three additional constructs from the literature:

| Construct | Source | Role in Framework |
|-----------|--------|-------------------|
| **SP (Stakeholder Perception)** | PADM (Lindell & Perry, 2012) | Trust in institutions (NJDEP, FEMA) |
| **SC (Social Capital)** | Adger (2003); Aldrich (2012) | Social network resources and community ties |
| **PA (Place Attachment)** | Bonaiuto et al. (2016) | Emotional bond to home/neighborhood |

### Protective Action Decision Model (PADM)

The framework also incorporates concepts from **PADM** (Lindell & Perry, 2012):

- **Information-seeking behavior**: Agents receive information through multiple channels
- **Stakeholder perception**: Trust in government/insurance affects action uptake
- **Social cues**: Neighbor actions influence risk perception

### How PMT/PADM Integrate

```
                    ┌─────────────────────────────────────────┐
                    │         INFORMATION CHANNELS            │
                    │  Observation | Gossip | News | Social   │
                    └─────────────────┬───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM REASONING                              │
│  Persona + Memories + Environment Context + Policy Info         │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Threat      │  │ Coping      │  │ Stakeholder │             │
│  │ Appraisal   │  │ Appraisal   │  │ Perception  │             │
│  │ (TP)        │  │ (CP)        │  │ (SP)        │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│  ┌──────┴──────┐  ┌──────┴──────┐                              │
│  │ Social      │  │ Place       │                              │
│  │ Capital     │  │ Attachment  │                              │
│  │ (SC)        │  │ (PA)        │                              │
│  └─────────────┘  └─────────────┘                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   GOVERNANCE LAYER    │
              │  Validate TP×CP→Action│
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   DECISION OUTPUT     │
              │  buy_insurance,       │
              │  elevate_house, etc.  │
              └───────────────────────┘
```

---

## 3. Research Questions & Hypotheses

All three RQs are answered from a **single unified experiment** (full-featured LLM-ABM). The narrative progresses: **Individual → Institutional → Collective**.

### RQ1: Individual Memory & Pathway Divergence

> **How does differential accumulation of personal flood damage memories create within-group divergence in adaptation timing, and does this divergence disproportionately delay adaptation among financially constrained households?**

**Important Clarification**: RQ1 is about **different agents within the same demographic group** diverging due to different personal experiences—NOT about running the same agent multiple times.

**Example**:
- H0023 (MG-Owner) lives in high-risk zone → experiences $85K damage in Year 1 → TP increases → buys insurance
- H0047 (MG-Owner) lives in low-risk zone → no flood damage → TP unchanged → do_nothing
- Both are MG-Owners with similar initial profiles, but their **individual flood experiences** (determined by spatial location) create divergent adaptation trajectories

**Hypothesis H1**: Households that accumulate personal flood damage memories exhibit faster adaptation uptake than households with equivalent initial profiles but only vicarious exposure. This "experience-adaptation gap" is wider for MG households due to financial constraints.

**Falsification Criteria**:
- Cox PH interaction term (personal_damage × MG_status) significant at α=0.05
- Hazard ratio for MG ≥ 1.5× NMG
- If falsified: memory-adaptation pathway is not MG-moderated

**Key Metrics**:
- Intra-group TP variance per year (traditional ABM = 0 by construction)
- Cox PH survival analysis (time-to-first-adaptation)
- Pathway entropy (Shannon entropy of action sequences)
- Memory salience score (top-k memories at decision time)

### RQ2: Institutional Feedback & Protection Inequality

> **Do reactive institutional policies—subsidy adjustments and CRS-mediated premium discounts—narrow or widen the cumulative protection gap between marginalized and non-marginalized households over decadal timescales?**

**Hypothesis H2a**: Government subsidy increases following high-MG-damage flood events arrive too late to prevent widening of the cumulative damage gap.
- Falsification: subsidy-adaptation lag < 2 years AND MG-NMG gap narrows

**Hypothesis H2b**: CRS discount reductions following high-loss years produce an "affordability spiral" for lowest-income households.
- Falsification: 1pp effective premium increase → ≥5% increase in P(lapse) for lowest income quartile

**Key Metrics**:
- Subsidy-adaptation lag (cross-correlation, lag in years)
- Premium-dropout correlation (panel regression)
- Cumulative damage Gini coefficient
- Protection gap (fraction MG without adaptation vs NMG, per year)

### RQ3: Social Information & Adaptation Diffusion

> **Which information channels most effectively accelerate sustained protective action diffusion in flood-prone communities?**

**Hypothesis H3a**: Communities with active social media exhibit faster initial adaptation uptake but slower sustained adoption compared to observation + news.
- Falsification: Uptake at year 3 exceeds observation-only by >10%; by year 10 the difference reverses

**Hypothesis H3b**: Gossip-mediated reasoning propagation produces stronger adaptation clustering than simple observation.

**Key Metrics**:
- Information-action citation rate (fraction of reasoning texts citing each channel)
- Adaptation clustering (Moran's I on social network)
- Social contagion half-life (time for 50% of flooded agent's neighbors to adapt)
- Reasoning propagation depth (trace phrases through gossip chains)

---

## 4. Simulation Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAGE GOVERNANCE FRAMEWORK                    │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: PROMPT        │  Persona + Memory + Context           │
│  Layer 2: LLM           │  Gemma 3 4B (temp=0.7, ctx=8192)     │
│  Layer 3: GOVERNANCE    │  SAGA rules + financial constraints   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    SAGA 3-TIER ORDERING                         │
├─────────────────────────────────────────────────────────────────┤
│  Tier 1: Government     │  NJDEP Blue Acres (subsidy decisions) │
│  Tier 2: Insurance      │  FEMA/NFIP CRS (premium decisions)    │
│  Tier 3: Households     │  400 agents (owner/renter decisions)  │
└─────────────────────────────────────────────────────────────────┘
```

### Simulation Timeline

- **Duration**: 13 years (2011-2023)
- **Hazard**: Real PRB flood raster data for each year
- **Agent count**: 400 (balanced 4-cell design)
- **Seeds**: 10 independent runs for stochastic robustness

### Annual Cycle

```
Pre-Year Hook:
  1. Load flood raster for current year
  2. Resolve pending actions (elevation completion, buyout finalization)
  3. Calculate per-agent flood depths

SAGA Tier 1 (Government):
  4. NJDEP receives: damage reports, MG/NMG adoption rates, budget
  5. NJDEP decides: increase/decrease/maintain subsidy (±5%)

SAGA Tier 2 (Insurance):
  6. FEMA receives: claims history, uptake rates, loss ratio
  7. FEMA decides: improve/reduce/maintain CRS discount (±5%)

SAGA Tier 3 (Households):
  8. For each household agent:
     a. Retrieve relevant memories
     b. Construct prompt with persona + context + policy info
     c. LLM generates decision + PMT construct labels
     d. Governance validates construct-action coherence
     e. Retry if validation fails (up to 3 times)
     f. Log to audit CSV
     g. Encode decision as new memory

Post-Year Hook:
  9. Calculate flood damage using HAZUS curves
  10. Process insurance claims and payouts
  11. Generate flood experience memories
  12. Propagate gossip through social network
  13. Run annual reflection for each agent
```

---

## 5. Agent Initialization Pipeline

### Overview

The pipeline transforms raw survey data into 400 simulation-ready agents with realistic personas, spatial assignments, and initial memories.

```
977 Qualtrics responses
        │
        ▼ (NJ zip code filter: 07xxx, 08xxx)
755 NJ respondents
        │
        ▼ (BalancedSampler: 100 per cell)
400 agents (balanced 4-cell design)
        │
        ▼ (RCV generation + spatial assignment)
400 agents with properties + locations
        │
        ▼ (Memory seeding: 6 templates × 400)
2,400 initial memories
```

### Step 1: Survey Cleaning

**Script**: `paper3/process_qualtrics_full.py`

**Input**: `cleaned_complete_data_977.xlsx` (920 valid rows after Qualtrics cleaning)

**Process**:
1. Filter to NJ residents by zip code (07xxx, 08xxx)
2. Parse PMT construct items (Likert 1-5 scale):
   - SC: 6 items (Q21_1-6) — Social Capital
   - PA: 9 items (Q21_7-15) — Place Attachment
   - TP: 11 items (Q22_1-11) — Threat Perception
   - CP: 8 items (Q24_1-2, Q25_1-2,4-5,7-8) — Coping Perception
   - SP: 3 items (Q25_3,6,9) — Stakeholder Perception
3. Classify MG status (2+ of 3 criteria)
4. Extract demographics, flood history, insurance status

**Output**: `data/cleaned_survey_full.csv` (~755 NJ respondents)

**Why 755 not 920?** The original Qualtrics data included respondents from multiple states. We filter to NJ-only because the study area is the Passaic River Basin.

### Step 2: Balanced Sampling

**Script**: `paper3/prepare_balanced_agents.py`

**Design**: 4-cell factorial (MG × Tenure)

| Cell | MG Status | Tenure | N | Flood-Prone % |
|------|-----------|--------|---|---------------|
| A | MG | Owner | 100 | 70% |
| B | MG | Renter | 100 | 70% |
| C | NMG | Owner | 100 | 50% |
| D | NMG | Renter | 100 | 50% |

**Why 100 per cell?** Statistical power analysis for Cox PH survival analysis with interaction terms requires N≥50 per subgroup. 100 per cell provides margin for dropouts (relocation, buyout).

**Sampling method**: Stratified random sampling with replacement if stratum < 100.

### Step 3: RCV Generation

**Replacement Cost Value (RCV)** determines flood damage magnitude and insurance coverage.

**Owner Building RCV**:
```python
# Lognormal distribution
mu_MG = $280,000   # MG owners: lower property values
mu_NMG = $400,000  # NMG owners: higher property values
sigma = 0.3        # Log-scale standard deviation

rcv = np.random.lognormal(np.log(mu), sigma)
rcv = np.clip(rcv, 100_000, 1_000_000)  # Bounds
```

**Owner Contents RCV**: 30-50% of building RCV (uniform distribution)

**Renter**: No building RCV (structure owned by landlord)
```python
# Contents only, scaled by income
base = 20_000
income_factor = income / 100_000 * 40_000
rcv_contents = np.random.normal(base + income_factor, 5_000)
rcv_contents = np.clip(rcv_contents, 10_000, 80_000)
```

### Step 4: Spatial Assignment

**Data**: Real PRB ESRI ASCII rasters (2021 reference year)

**Assignment logic**:
1. Parse grid metadata: `ncols`, `nrows`, `xllcorner`, `yllcorner`, `cellsize`
2. Stratify cells by flood depth:
   - `dry`: depth = 0
   - `shallow`: 0 < depth ≤ 0.3m
   - `moderate`: 0.3m < depth ≤ 1.0m
   - `deep`: 1.0m < depth ≤ 4.0m
   - `very_deep`: depth > 4.0m
3. Assign agents based on flood history:
   - Survey flood_experience=True + flood_freq≥2 → deep/very_deep cells
   - Survey flood_experience=True + flood_freq<2 → shallow/moderate cells
   - Survey flood_experience=False → MG 70% / NMG 50% in flood-prone, remainder dry
4. Convert grid (row, col) to lat/lon:
   ```python
   lon = xllcorner + col * cellsize
   lat = yllcorner + (nrows - 1 - row) * cellsize
   ```

**Output columns**: `grid_x`, `grid_y`, `latitude`, `longitude`, `zone_label` (LOW/MEDIUM/HIGH)

### Step 5: Memory Seeding

**6 canonical templates per agent** (total: 2,400 initial memories):

| Template | Content Pattern | Source |
|----------|-----------------|--------|
| `flood_experience` | "I experienced [N] flood(s) in the past [X] years..." | Survey Q14, Q17 |
| `insurance_history` | "I [have/don't have] flood insurance because..." | Survey Q26 |
| `social_connections` | "My neighbors [description based on SC score]..." | Survey Q21_1-6 |
| `government_trust` | "I [trust/distrust] government flood programs because..." | Survey Q25_3,6,9 |
| `place_attachment` | "I've lived here for [X] years and feel [attached/ready to leave]..." | Survey Q21_7-15 |
| `flood_zone` | "My property is in [zone] with [X]% annual flood probability..." | Spatial assignment |

**Output**: `data/initial_memories_balanced.json`

---

## 6. PMT Construct Design

### Constructs as Outputs, Not Inputs

**Critical design principle**: In traditional ABMs, PMT constructs are **inputs** (pre-initialized from distributions). In our LLM-ABM, constructs are **outputs** of reasoning.

```
Traditional ABM:
  TP_initial ~ Beta(α, β)  →  Decision = f(TP, CP, ...)

LLM-ABM:
  Persona + Memories + Context  →  LLM Reasoning  →  TP, CP, SP, SC, PA labels
                                                  →  Decision
```

### Five PMT Constructs

| Construct | Label Scale | Governance Role | Analysis Role |
|-----------|-------------|-----------------|---------------|
| **TP** (Threat Perception) | VL/L/M/H/VH | **Enforced** via thinking_rules | RQ1: Memory-TP pathway |
| **CP** (Coping Perception) | VL/L/M/H/VH | **Enforced** via thinking_rules | RQ1: Financial constraints |
| **SP** (Stakeholder Perception) | VL/L/M/H/VH | Recorded, not enforced | RQ2: Institutional trust |
| **SC** (Social Capital) | VL/L/M/H/VH | Recorded, not enforced | RQ3: Social influence |
| **PA** (Place Attachment) | VL/L/M/H/VH | Recorded, not enforced | RQ3: Relocation resistance |

### Why SC and PA Are Not Governance-Enforced

**Design rationale**:
1. **TP + CP are PMT core drivers** — directly determine protection motivation
2. **SC modulates social influence** — affects how agents weight neighbor information, but shouldn't block decisions
3. **PA modulates relocation reluctance** — contextual moderator, not a hard constraint

**What happens to SC and PA**:
- Parsed from every LLM response (required constructs)
- Recorded in audit CSV for every agent-year
- Used in ICC validation (reliability testing)
- Analyzed in RQ3 (do high-SC agents adopt faster due to social influence?)

### Governance Rules (TP/CP Only)

**Owner thinking_rules**:

| Rule ID | Condition | Blocked Skills | Level |
|---------|-----------|----------------|-------|
| `owner_inaction_high_threat` | TP∈{H,VH} AND CP∈{M,H,VH} | do_nothing | ERROR |
| `owner_fatalism_allowed` | TP∈{H,VH} AND CP∈{VL,L} | do_nothing | WARNING |
| `owner_complex_action_low_coping` | CP∈{VL,L} | elevate_house, buyout_program | ERROR |

**Renter thinking_rules**:

| Rule ID | Condition | Blocked Skills | Level |
|---------|-----------|----------------|-------|
| `renter_inaction_high_threat` | TP∈{H,VH} AND CP∈{M,H,VH} | do_nothing | ERROR |
| `renter_fatalism_allowed` | TP∈{H,VH} AND CP∈{VL,L} | do_nothing | WARNING |
| `renter_complex_action_low_coping` | CP∈{VL,L} | relocate | ERROR |

**The "fatalism_allowed" rule preserves the risk perception paradox**: Agents with high threat perception but low coping may rationally choose inaction due to resource constraints. This is a WARNING (logged) not an ERROR (blocked).

---

## 7. Memory Architecture

### UnifiedCognitiveEngine

Replaces parametric TP decay equations from traditional ABMs.

**Key parameters** (from `ma_agent_types.yaml`):

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `importance_decay` | 0.1/year | Memories fade over time |
| `window_size` | 5 years | Retrieval window for prompt |
| `consolidation_threshold` | 0.6 | Merge similar memories |
| `ranking_mode` | weighted | Importance × recency × relevance |

**Emotional weights**:

| Category | Weight | Examples |
|----------|--------|----------|
| Major threat | 1.2 | Flood damage, financial loss |
| Minor positive | 0.8 | Subsidy received, neighbor elevated |
| Neutral | 0.3 | Policy announcement, no flood |

**Source weights**:

| Source | Weight | Rationale |
|--------|--------|-----------|
| Personal experience | 1.0 | Direct experience most salient |
| Neighbor (gossip) | 0.7 | Social proof, but secondhand |
| News media | 0.5 | Aggregate info, less personal |
| Social media | 0.4-0.8 | Variable reliability |

### Memory-Mediated TP (vs. Parametric Decay)

**Traditional ABM** (SCC paper):
```python
# All agents in same tract have identical TP trajectory
TP(t) = tau_inf + (tau_0 - tau_inf) * exp(-alpha * t)
```

**LLM-ABM**:
```python
# Each agent has unique TP based on personal memories
memories = retrieve_top_k(agent_id, k=5)
prompt = construct_prompt(persona, memories, context)
response = llm.generate(prompt)
TP_label = parse_construct(response, "TP")  # Emergent from reasoning
```

**Result**: Within-group TP variance > 0 (impossible in traditional ABM by construction).

---

## 8. Governance Framework

### SAGA (SAGE Agent Governance Architecture)

**Three-tier ordering** ensures institutional decisions affect household prompts in the same year:

```
Year N:
  1. Government agent decides subsidy_rate
  2. Insurance agent decides crs_discount
  3. Household agents receive updated rates in their prompts
```

### Validation Pipeline

For each household decision:

```
LLM Response
     │
     ▼
┌─────────────────────────────────────────┐
│         STRUCTURAL VALIDATION           │
│  - JSON format correct?                 │
│  - All required fields present?         │
│  - Construct labels valid (VL/L/M/H/VH)?│
└─────────────────┬───────────────────────┘
                  │ Pass
                  ▼
┌─────────────────────────────────────────┐
│         IDENTITY RULES                  │
│  - Already elevated? Block elevate      │
│  - Already relocated? Block all         │
│  - Renter? Block elevate/buyout         │
└─────────────────┬───────────────────────┘
                  │ Pass
                  ▼
┌─────────────────────────────────────────┐
│         THINKING RULES                  │
│  - High TP + High CP + do_nothing?      │
│  - Low CP + expensive action?           │
└─────────────────┬───────────────────────┘
                  │ Pass
                  ▼
┌─────────────────────────────────────────┐
│         FINANCIAL CONSTRAINTS           │
│  - Can afford elevation cost?           │
│  - Can afford insurance premium?        │
└─────────────────┬───────────────────────┘
                  │ Pass
                  ▼
            DECISION ACCEPTED
```

### Retry Mechanism

If validation fails:
1. Generate intervention message explaining the error
2. Append to prompt and re-query LLM
3. Up to 3 retries
4. If all retries fail: log as "REJECTED" and proceed (preserved for analysis)

---

## 9. Institutional Agents

### NJ Government (NJDEP Blue Acres Administrator)

**Role**: Manage flood buyout subsidies

**Context received**:
- Community flood damage reports (total $, by MG/NMG)
- Current adaptation rates (by cell)
- Budget status and utilization
- Historical subsidy effectiveness

**Actions**:
| Action | Effect | Trigger Logic |
|--------|--------|---------------|
| `increase_subsidy` | +5% subsidy rate | High MG damage, low MG adoption |
| `decrease_subsidy` | -5% subsidy rate | Budget constraints, high adoption |
| `maintain_subsidy` | No change | Stable conditions |

**Subsidy range**: 20%-95%

### FEMA/NFIP CRS Administrator

**Role**: Manage Community Rating System discounts

**Context received**:
- Claims history and loss ratio
- Insurance uptake rates
- CRS activity scores
- Solvency indicators

**Actions**:
| Action | Effect | Trigger Logic |
|--------|--------|---------------|
| `improve_crs` | +5% CRS discount | Good loss ratio, capacity for investment |
| `reduce_crs` | -5% CRS discount | High loss ratio, solvency concerns |
| `maintain_crs` | No change | Stable conditions |

**Effective premium**: `base_premium × (1 - crs_discount)`

**CRS discount range**: 0%-45%

---

## 10. Social Network & Information Channels

### Network Structure

- **Neighbors per agent**: 5
- **Same-region weighting**: 70% (agents more likely to connect within their flood zone)
- **Network type**: Small-world (high clustering, short path length)

### Four Information Channels

| Channel | Delay | Reliability | Max Items | Content |
|---------|-------|-------------|-----------|---------|
| **Observation** | 0 | 1.0 | 5 neighbors | Elevated/insured/relocated status |
| **Gossip** | 0 | Varies | 2 messages | Decision reasoning + flood experience |
| **News Media** | 1 year | 0.9 | — | Community-wide adaptation rates, policy changes |
| **Social Media** | 0 | 0.4-0.8 | 3 posts | Sampled posts with exaggeration factor=0.3 |

### Gossip Filtering

Not all information propagates:
- **Importance threshold**: 0.5 (only significant experiences shared)
- **Categories**: decision_reasoning, flood_experience, adaptation_outcome
- **Decay**: Gossip importance decays with network distance

### Information in Prompt

Agents receive a structured information section:

```
## SOCIAL INFORMATION

### What You've Observed
- Neighbor H0042 elevated their house last year
- Neighbor H0089 purchased flood insurance

### What You've Heard (Gossip)
- "My neighbor elevated because the flood last year damaged their basement.
   They said the subsidy made it affordable." (from H0042)

### Recent News
- Community-wide: 35% of households now have flood insurance (up from 28%)
- Government announced 5% increase in elevation subsidies

### Social Media (Reliability: Variable)
- Post: "Another flood warning! When will they fix the drainage?" (12 likes)
- Post: "Just got my insurance payout, took 3 months but worth it" (8 likes)
```

---

## 11. Hazard & Depth-Damage Model

### Hazard Data

**Source**: 13 ESRI ASCII raster files (2011-2023) from PRB flood modeling

**Format**: `.asc` files with header:
```
ncols         457
nrows         411
xllcorner     -74.5
yllcorner     40.6
cellsize      0.00027778
NODATA_value  -9999
```

**Per-agent depth**: Each agent's flood depth is read from their (grid_x, grid_y) cell.

### HAZUS-MH Depth-Damage Curves

**Source**: FEMA HAZUS-MH Technical Manual (2022)

**Curve type**: 20-point piecewise-linear for residential structures

**Structure types**:
- 1-story with basement
- 2-story with basement
- Split-level
- 1-story no basement
- 2-story no basement

**Sample curve** (1-story with basement, structure):

| Depth (ft) | Damage % |
|------------|----------|
| -2 | 8% |
| 0 | 16% |
| 1 | 23% |
| 2 | 33% |
| 4 | 47% |
| 8 | 68% |
| 12+ | 75% |

### First Floor Elevation (FFE) Adjustment

```python
effective_depth = flood_depth - elevation_ft

if effective_depth <= 0:
    damage = 0  # Flood below first floor
else:
    damage = hazus_curve(effective_depth) * RCV
```

**Example**: Agent elevated 5ft, flood depth is 4ft → effective_depth = -1ft → $0 damage

### Insurance Payout Calculation

```python
# NFIP coverage limits
STRUCTURE_LIMIT = 250_000
CONTENTS_LIMIT = 100_000
DEDUCTIBLE = 2_000  # Default

# Calculate covered amounts
covered_structure = min(structure_damage, STRUCTURE_LIMIT)
covered_contents = min(contents_damage, CONTENTS_LIMIT)
gross_claim = covered_structure + covered_contents

# Apply deductible
payout = max(0, gross_claim - DEDUCTIBLE)
out_of_pocket = total_damage - payout
```

---

## 12. Validation Framework

### Three-Level Validation

| Level | Focus | When | LLM Needed? |
|-------|-------|------|:-----------:|
| **L1 Micro** | Per-decision coherence | Post-hoc | No |
| **L2 Macro** | Aggregate plausibility | Post-hoc | No |
| **L3 Cognitive** | LLM reliability | Pre-experiment | Yes |

### L1 Micro Metrics

| Metric | Threshold | What It Tests |
|--------|-----------|---------------|
| **CACR** (Construct-Action Coherence Rate) | ≥ 0.80 | Do TP/CP labels match chosen action per PMT? |
| **R_H** (Hallucination Rate) | ≤ 0.10 | Physical impossibilities (elevate twice, etc.) |
| **EBE** (Effective Behavioral Entropy) | > 0 | Are decisions diverse or collapsed? |

**CACR computation**:
```python
for each (agent, year) observation:
    if PMT_coherent(TP_label, CP_label, action):
        coherent_count += 1
CACR = coherent_count / total_observations
```

### L2 Macro Metrics

| Metric | Threshold | What It Tests |
|--------|-----------|---------------|
| **EPI** (Empirical Plausibility Index) | ≥ 0.60 | Fraction of 8 benchmarks within empirical range |

**EPI computation**:
```python
for each benchmark in 8_benchmarks:
    observed = compute_from_audit_csv(benchmark)
    if within_range(observed, benchmark.low, benchmark.high, tolerance=0.30):
        score += benchmark.weight
EPI = score / total_weight
```

### L3 Cognitive Metrics

| Metric | Threshold | What It Tests |
|--------|-----------|---------------|
| **ICC(2,1)** | ≥ 0.60 | Test-retest reliability (same persona, 30 replicates) |
| **eta-squared** | ≥ 0.25 | Between-archetype effect size |
| **Directional pass rate** | ≥ 75% | Persona/stimulus drives behavior |

#### ICC(2,1) Computation

**Intraclass Correlation Coefficient (Two-Way Random, Single Measures)**:

```python
# Data structure: 15 archetypes × 6 vignettes × 30 replicates = 2,700 responses
# For each (archetype, vignette) cell: 30 repeated measurements

# Convert TP/CP labels to numeric: VL=1, L=2, M=3, H=4, VH=5
def label_to_numeric(label):
    return {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}[label]

# Two-way ANOVA decomposition
# Y_ijk = μ + α_i + β_j + ε_ijk
# where: i = archetype×vignette cell, j = replicate, k = observation

MS_between = variance_between_cells      # Between (archetype×vignette) variance
MS_within = variance_within_replicates   # Within-cell (residual) variance

# ICC(2,1) formula: consistency of single rater
ICC_21 = (MS_between - MS_within) / (MS_between + (k-1)*MS_within)
# where k = number of replicates (30)

# 95% CI via F-distribution
F_value = MS_between / MS_within
df_between = n_cells - 1      # 90 - 1 = 89
df_within = n_cells * (k - 1) # 90 * 29 = 2610
```

**Interpretation thresholds** (Koo & Li, 2016):

- ICC < 0.50: Poor reliability
- 0.50 ≤ ICC < 0.75: Moderate reliability
- 0.75 ≤ ICC < 0.90: Good reliability
- ICC ≥ 0.90: Excellent reliability

**Our results**: TP ICC = 0.964, CP ICC = 0.947 → **Excellent reliability**

#### Eta-Squared (η²) Computation

**Effect size measuring between-archetype variance**:

```python
# One-way ANOVA: Does archetype explain TP/CP variance?
# Group by archetype (ignoring vignette for this test)

SS_between = sum(n_i * (mean_i - grand_mean)^2)  # Between-archetype sum of squares
SS_total = sum((Y_ij - grand_mean)^2)            # Total sum of squares

eta_squared = SS_between / SS_total

# Interpretation:
# η² ≥ 0.01: Small effect
# η² ≥ 0.06: Medium effect
# η² ≥ 0.14: Large effect
# η² ≥ 0.25: Very large effect (our threshold)
```

**Our results**: TP η² = 0.330, CP η² = 0.544 → **Very large effect sizes**

This confirms that archetype differences (MG vs NMG, owner vs renter, flood history) drive meaningful variation in LLM outputs.

#### Persona Sensitivity Test

**Purpose**: Verify that changing persona attributes changes LLM behavior in expected directions.

```python
# Design: 4 swap tests, each with 2 archetypes × 10 replicates = 80 LLM calls

swap_tests = {
    "income_swap": {
        "base": "mg_owner_floodprone",
        "swap": {"income": "$75K-$100K"},  # MG → NMG income
        "expected": "CP increases"          # Higher income → better coping
    },
    "zone_swap": {
        "base": "mg_owner_floodprone",
        "swap": {
            "flood_zone": "X (minimal risk)",
            "flood_count": 0,
            "years_since_flood": -1,
            "memory_seed": "I've lived here 10 years, never flooded..."
        },
        "expected": "TP decreases"          # Safe zone → lower threat
    },
    "history_swap": {
        "base": "nmg_renter_safe",
        "swap": {
            "flood_count": 3,
            "years_since_flood": 1,
            "memory_seed": "We've been flooded 3 times..."
        },
        "expected": "TP increases"          # Flood history → higher threat
    }
}

# Pass criterion: ≥75% of swap pairs show expected directional change
pass_rate = passed_tests / total_tests
```

**Our results**: 75% (3/4 tests passed) → **Meets threshold**

#### Prompt Sensitivity Test

**Purpose**: Ensure LLM is not biased by superficial prompt features.

```python
# Test 1: Option Reordering (40 LLM calls)
# Shuffle action options in prompt, check if decision changes

for archetype in ["mg_owner", "nmg_renter", "vulnerable"]:
    original_order = ["do_nothing", "buy_insurance", "elevate", ...]
    shuffled_order = random.shuffle(original_order)

    response_original = llm.generate(prompt_with(original_order))
    response_shuffled = llm.generate(prompt_with(shuffled_order))

    # FAIL if decision differs due to option position
    positional_bias = (response_original != response_shuffled)

# Test 2: Framing Effect (80 LLM calls)
# Reframe flood probability: "10% chance" vs "1 in 10 years"

for archetype in sample_archetypes:
    neutral_frame = "Your property has a 10% annual flood probability"
    loss_frame = "Your property floods roughly once every 10 years"

    tp_neutral = llm.generate(prompt_with(neutral_frame))["TP"]
    tp_loss = llm.generate(prompt_with(loss_frame))["TP"]

    # WARNING if TP inflates >1 level with loss framing
    framing_effect = abs(label_to_numeric(tp_loss) - label_to_numeric(tp_neutral))
```

**Our results**: No systematic positional bias, framing effect within acceptable range → **OK**

---

## 13. Empirical Benchmarks

### 8 Benchmarks Across 4 Categories

| # | Metric | Range | Weight | Category | Source |
|---|--------|-------|--------|----------|--------|
| B1 | NFIP Insurance (SFHA) | 0.30-0.50 | 1.0 | AGGREGATE | Kousky (2017) |
| B2 | Insurance (All Zones) | 0.15-0.40 | 0.8 | AGGREGATE | Gallagher (2014) |
| B3 | Elevation Rate | 0.03-0.12 | 1.0 | AGGREGATE | Haer et al. (2017) |
| B4 | Buyout Rate | 0.02-0.15 | 0.8 | AGGREGATE | NJ DEP Blue Acres |
| B5 | Inaction Post-Flood | 0.35-0.65 | 1.5 | CONDITIONAL | Grothmann & Reusswig (2006) |
| B6 | MG-NMG Gap | 0.10-0.30 | 2.0 | DEMOGRAPHIC | Choi et al. (2024) |
| B7 | RL Uninsured | 0.15-0.40 | 1.0 | CONDITIONAL | FEMA RL statistics |
| B8 | Lapse Rate | 0.05-0.15 | 1.0 | TEMPORAL | Gallagher (2014, AER) |

### Computation Methods

| Method | Benchmarks | How |
|--------|-----------|-----|
| **End-year snapshot** | B1, B2, B3, B4 | Agent state at year 13 |
| **Event-conditional** | B5, B7 | Filter to agents who experienced flood |
| **Annual flow** | B8 | Year-over-year insured → uninsured |
| **Group difference** | B6 | NMG adapted rate - MG adapted rate |

### Benchmark Weights Rationale

- **B5 (Inaction Post-Flood)**: Weight 1.5 — tests the risk perception paradox
- **B6 (MG-NMG Gap)**: Weight 2.0 — core equity metric for RQ2

---

## 14. ICC Probing Protocol

### Design

**Purpose**: Validate LLM reliability BEFORE running experiments

**Protocol**: 15 archetypes × 6 vignettes × 30 replicates = **2,700 LLM calls**

### 15 Archetypes

| # | ID | Profile |
|---|-----|---------|
| 1 | `mg_owner_floodprone` | MG owner, AE zone, 2 floods, $25K-$45K |
| 2 | `mg_renter_floodprone` | MG renter, AE zone, 1 flood, $15K-$25K |
| 3 | `nmg_owner_floodprone` | NMG owner, AE zone, 1 flood, $75K-$100K |
| 4 | `nmg_renter_safe` | NMG renter, Zone X, 0 floods, $45K-$75K |
| 5 | `resilient_veteran` | NMG owner, 4 floods, elevated+insured, $100K+ |
| 6 | `vulnerable_newcomer` | MG renter, 6 months, 0 floods, <$15K |
| 7-15 | ... | Additional edge cases and demographic variations |

### 6 Vignettes

| # | ID | Severity | Expected TP |
|---|-----|----------|-------------|
| 1 | `high_severity_flood` | 4.5 ft flood, $42K damage | H or VH |
| 2 | `medium_severity_flood` | 1.2 ft minor flood | M |
| 3 | `low_severity_flood` | Zone X, no flooding in 30 years | VL or L |
| 4 | `extreme_compound` | 8ft + budget exhausted + lapsed | VH |
| 5 | `contradictory_signals` | FEMA says low risk but just flooded | M to H |
| 6 | `post_adaptation` | Already elevated + insured | L to M |

### ICC Results (Completed)

| Construct | ICC(2,1) | Interpretation |
|-----------|----------|----------------|
| TP | **0.964** | Excellent reliability |
| CP | **0.947** | Excellent reliability |

Both exceed the 0.60 threshold, validating that the LLM produces consistent, persona-driven responses.

---

## 15. How to Run

### Prerequisites

```bash
# 1. Install Ollama and pull model
ollama pull gemma3:4b

# 2. Verify PRB raster data exists
ls examples/multi_agent/flood/input/PRB/*.asc
# Should show 13 files (2011-2023)

# 3. Verify agent profiles generated
ls examples/multi_agent/flood/data/agent_profiles_balanced.csv
ls examples/multi_agent/flood/data/initial_memories_balanced.json
```

### Step 1: ICC Probing (Validate LLM First)

```bash
python paper3/run_cv.py --mode icc --model gemma3:4b --replicates 30
```

**Check**: ICC(2,1) ≥ 0.60 for TP and CP

### Step 2: Primary Experiment

```bash
# Single seed
python paper3/run_paper3.py \
    --config paper3/configs/primary_experiment.yaml \
    --seed 42

# All 10 seeds
python paper3/run_paper3.py \
    --config paper3/configs/primary_experiment.yaml \
    --all-seeds
```

### Step 3: Post-hoc Validation

```bash
python paper3/run_cv.py \
    --mode posthoc \
    --trace-dir paper3/results/paper3_primary/seed_42/
```

**Check**: CACR ≥ 0.80, R_H ≤ 0.10, EPI ≥ 0.60

### Step 4: Ablation Studies (SI)

```bash
python paper3/run_paper3.py \
    --config paper3/configs/si_ablations.yaml \
    --ablation si1_window_memory \
    --all-seeds
```

---

## 16. Output Structure

```
paper3/results/
├── cv/                                    # ICC probing results
│   ├── icc_report.json                   # ICC(2,1), eta-squared, etc.
│   ├── icc_responses.csv                 # All 2,700 responses
│   ├── persona_sensitivity_report.json   # Swap test results
│   └── prompt_sensitivity_report.json    # Reordering test results
│
└── paper3_primary/
    └── seed_42/
        └── gemma3_4b_strict/
            └── raw/
                ├── household_owner_traces.jsonl   # 200 owners × 13 years
                ├── household_renter_traces.jsonl  # 200 renters × 13 years
                ├── government_traces.jsonl        # 1 agent × 13 years
                └── insurance_traces.jsonl         # 1 agent × 13 years
```

### Trace File Format (JSONL)

Each line is a JSON object:

```json
{
  "run_id": "paper3_primary_seed42",
  "year": 3,
  "agent_id": "H0042",
  "agent_type": "household_owner",
  "validated": true,
  "input": "...(full prompt)...",
  "raw_output": "...(LLM response)...",
  "skill_proposal": "buy_insurance",
  "approved_skill": "buy_insurance",
  "TP_LABEL": "H",
  "CP_LABEL": "M",
  "SP_LABEL": "L",
  "SC_LABEL": "M",
  "PA_LABEL": "H",
  "retry_count": 0,
  "validation_issues": [],
  "memory_pre": ["...", "..."],
  "memory_post": ["...", "...", "(new decision memory)"],
  "state_before": {"insured": false, "elevated": false},
  "state_after": {"insured": true, "elevated": false}
}
```

---

## 17. Key Differences from Traditional ABM

| Capability | Traditional ABM (SCC Paper) | LLM-ABM (Paper 3) |
|------------|----------------------------|-------------------|
| **TP decay** | Parametric equation (tract-level, MG/NMG uniform) | Memory-mediated (individual, experience-dependent) |
| **Decision-making** | Bayesian regression lookup | LLM reasoning with persona + memory |
| **Constructs** | Pre-initialized from Beta distributions (inputs) | Emergent from reasoning (outputs) |
| **Social influence** | Aggregate % observation (tract-level) | Direct neighbor observation + gossip + media |
| **Institutional agents** | Exogenous (fixed subsidies/premiums) | Endogenous LLM agents (NJDEP + FEMA) |
| **Action granularity** | Binary (adopt/not) | Sub-options (elevation ft, insurance type) |
| **Individual heterogeneity** | Within-group agents identical | Each agent has unique memory + reasoning + history |
| **Specification burden** | Dozens of parametric equations | Single natural-language persona + memory system |
| **Interpretability** | Coefficients | Natural-language reasoning traces |

---

## 18. Computational Requirements

### LLM Call Estimates

| Component | LLM Calls | Time Estimate |
|-----------|-----------|---------------|
| Primary experiment (400 × 13 × 10 seeds) | 52,000 | ~7.2 hours |
| ICC probing (15 × 6 × 30) | 2,700 | ~22 minutes |
| Persona + prompt sensitivity | ~5,000 | ~42 minutes |
| SI ablations (200 × 13 × 3 × 10 configs) | 78,000 | ~10.8 hours |
| **Total** | **~138,000** | **~19 hours** |

### Hardware Configuration

- **Inference**: Local Ollama server
- **Model**: Gemma 3 4B (specific quantization logged)
- **Context window**: 8,192 tokens
- **Temperature**: 0.7 (harmonized across ICC and experiments)
- **GPU**: NVIDIA RTX 3090 or equivalent recommended

### Memory Requirements

- **Model**: ~4GB VRAM
- **Simulation state**: ~500MB RAM per seed
- **Output traces**: ~50MB per seed (compressed)

---

## 19. Glossary

| Term | Definition |
|------|-----------|
| **ABM** | Agent-Based Model |
| **BFE** | Base Flood Elevation |
| **CACR** | Construct-Action Coherence Rate |
| **CP** | Coping Perception (PMT construct) |
| **CRS** | Community Rating System (NFIP discount program) |
| **EBE** | Effective Behavioral Entropy |
| **EPI** | Empirical Plausibility Index |
| **FFE** | First Floor Elevation |
| **ICC** | Intraclass Correlation Coefficient |
| **MG** | Marginalized Group (meets 2+ of 3 vulnerability criteria) |
| **NFIP** | National Flood Insurance Program |
| **NMG** | Non-Marginalized Group |
| **PA** | Place Attachment (PMT construct) |
| **PADM** | Protective Action Decision Model (Lindell & Perry, 2012) |
| **PMT** | Protection Motivation Theory (Rogers, 1983) |
| **PRB** | Passaic River Basin |
| **R_H** | Hallucination Rate |
| **RCV** | Replacement Cost Value |
| **RL** | Repetitive Loss (≥2 floods) |
| **SAGA** | SAGE Agent Governance Architecture (3-tier) |
| **SAGE** | Simulated Agent Governance Engine |
| **SC** | Social Capital (PMT construct) |
| **SFHA** | Special Flood Hazard Area |
| **SP** | Stakeholder Perception (PMT/PADM construct) |
| **TP** | Threat Perception (PMT construct) |
| **WRR** | Water Resources Research (journal) |

---

## 20. References

### Flood Adaptation & PMT
- Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. *Natural Hazards*, 38(1-2), 101-120.
- Lindell, M. K., & Perry, R. W. (2012). The protective action decision model: Theoretical modifications and additional evidence. *Risk Analysis*, 32(4), 616-632.
- Rogers, R. W. (1983). Cognitive and psychological processes in fear appeals and attitude change: A revised theory of protection motivation. *Social Psychophysiology: A Sourcebook*, 153-176.

### Environmental Justice
- Choi, D., et al. (2024). Flood adaptation disparities among marginalized communities in New Jersey. *Environmental Research Letters*.
- Collins, T. W., et al. (2018). Environmental injustice and flood risk: A conceptual model and case study. *Environmental Science & Policy*, 83, 74-83.

### NFIP & Insurance
- Gallagher, J. (2014). Learning about an infrequent event: Evidence from flood insurance take-up in the United States. *American Economic Review*, 104(11), 3484-3508.
- Kousky, C. (2017). Disasters as learning experiences or disasters as policy opportunities: Examining flood insurance purchases after hurricanes. *Risk Analysis*, 37(3), 517-530.

### Agent-Based Modeling
- Haer, T., et al. (2017). Integrating household risk mitigation behavior in flood risk analysis: An agent-based model approach. *Risk Analysis*, 37(10), 1977-1992.
- de Ruig, L. T., et al. (2022). An agent-based model for evaluating reforms of the National Flood Insurance Program. *Risk Analysis*, 42(5), 1112-1127.

### LLM Agents
- Park, J. S., et al. (2023). Generative agents: Interactive simulacra of human behavior. *UIST 2023*.
- Horton, J. J. (2023). Large language models as simulated economic agents: What can we learn from homo silicus? *NBER Working Paper*.
- Vezhnevets, A. S., et al. (2023). Generative agent-based modeling with actions grounded in physical, social, or digital space using Concordia. *arXiv preprint*.

---

*Last updated: 2026-02-05*
