# Paper 3: LLM-Governed Multi-Agent Flood Adaptation Simulation

## Passaic River Basin Household Flood Risk Decision-Making under WAGF Framework

**Target Journal**: Water Resources Research (WRR)

**Status**: Implementation complete. Awaiting ICC probing and experiment execution.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Research Questions and Hypotheses](#2-research-questions-and-hypotheses)
3. [Simulation Architecture](#3-simulation-architecture)
4. [Agent Design and Initialization](#4-agent-design-and-initialization)
5. [Memory Architecture](#5-memory-architecture)
6. [Decision Loop and Skills](#6-decision-loop-and-skills)
7. [Institutional Agents](#7-institutional-agents)
8. [Social Network and Information Channels](#8-social-network-and-information-channels)
9. [Hazard and Depth-Damage Model](#9-hazard-and-depth-damage-model)
10. [Validation Framework](#10-validation-framework)
11. [Empirical Benchmarks](#11-empirical-benchmarks)
12. [ICC Probing Protocol](#12-icc-probing-protocol)
13. [How to Run](#13-how-to-run)
14. [Output Structure](#14-output-structure)
15. [Computational Requirements](#15-computational-requirements)
16. [Key Differences from Traditional ABM](#16-key-differences-from-traditional-abm)
17. [File Inventory](#17-file-inventory)
18. [Glossary](#18-glossary)
19. [Citations](#19-citations)

---

## 1. Project Overview

This repository contains the implementation for Paper 3, a **Water Resources Research (WRR)** submission investigating LLM-governed multi-agent flood adaptation simulation in the **Passaic River Basin (PRB), New Jersey**.

### Core Framework

The simulation operates on the **WAGF (Water Agent Governance Framework)** framework with **WAGF 3-Tier (WAGF Agent Governance Architecture) 3-tier ordering**. WAGF provides a structured approach to governing LLM agent behavior through configurable rules that ensure psychological coherence while preserving emergent heterogeneity.

### Study Area

- **Location**: Passaic River Basin, New Jersey
- **Coverage**: 27 census tracts
- **Hazard Data**: 13 real ASCII raster files (2011-2023)
- **Grid Resolution**: ~457 x 411 cells (~30m at 40.9N latitude)
- **Coordinate System**: WGS84

### Core Claim

We claim **structural plausibility**, not predictive accuracy. The LLM-ABM produces individually heterogeneous adaptation trajectories that fall within empirically defensible aggregate ranges. This is something traditional equation-based ABMs cannot achieve without drastically more complex specification. Each agent develops unique memories, reasoning patterns, and decision histories, while governance ensures psychological coherence with Protection Motivation Theory (PMT).

### What This Simulation Demonstrates

1. **Memory-mediated threat perception**: Individual flood experiences accumulate and decay through cognitive mechanisms rather than parametric equations
2. **Emergent construct heterogeneity**: PMT constructs (TP, CP, SP, SC, PA) emerge from LLM reasoning rather than being pre-initialized
3. **Endogenous institutional feedback**: Government and insurance agents respond adaptively to household behavior
4. **Multi-channel social influence**: Information propagates through observation, gossip, news, and social media with distinct dynamics
5. **Governance-validated coherence**: WAGF 3-Tier rules ensure construct-action pairs conform to psychological theory

---

## 2. Research Questions and Hypotheses

All three research questions are answered from a **single unified experiment** with all modules active. The narrative progresses from **Individual -> Institutional -> Collective** dynamics.

### RQ1: Individual Memory and Pathway Divergence

> How does differential accumulation of personal flood damage memories create within-group divergence in adaptation timing, and does this divergence disproportionately delay adaptation among financially constrained households?

**Hypothesis H1**: Households that accumulate personal flood damage memories will exhibit faster adaptation uptake than households with equivalent initial profiles but only vicarious exposure. This "experience-adaptation gap" will be wider for marginalized (MG) households due to financial constraints.

**Falsification Criteria**: Cox proportional hazards interaction term (personal_damage x MG_status) significant at alpha=0.05; hazard ratio for MG >= 1.5x NMG. If H1 is falsified, the memory-adaptation pathway is not MG-moderated.

**Key Metrics**:
- Intra-group TP variance per year (traditional ABM = 0 by construction)
- Cox PH survival analysis (time-to-first-adaptation)
- Pathway entropy (Shannon entropy of action sequences)
- Memory salience score (top-k memories at decision time)

**Key Figure**: Adaptation trajectory spaghetti plot showing individual TP trajectories over 13 years, color-coded by MG/NMG status.

### RQ2: Institutional Feedback and Protection Inequality

> Do reactive institutional policies (subsidy adjustments and CRS-mediated premium discounts) narrow or widen the cumulative protection gap between marginalized and non-marginalized households over decadal timescales?

**Hypothesis H2a**: Government subsidy increases following high-MG-damage flood events arrive too late to prevent widening of the cumulative damage gap.

**Falsification Criteria**: If subsidy-adaptation lag < 2 years AND MG-NMG gap narrows.

**Hypothesis H2b**: CRS discount reductions following high-loss years produce an "affordability spiral" for low-income households.

**Falsification Criteria**: 1 percentage point effective premium increase leads to >= 5% increase in P(lapse) for lowest income quartile.

**Key Metrics**:
- Subsidy-adaptation lag (cross-correlation, lag in years)
- Premium-dropout correlation (panel regression)
- Cumulative damage Gini coefficient
- Protection gap (fraction MG without insurance or elevation vs NMG, per year)

**Key Figure**: Dual-axis time series showing subsidy/premium rates overlaid with MG/NMG adaptation rates, annotated with flood event markers.

### RQ3: Social Information and Adaptation Diffusion

> Which information channels most effectively accelerate sustained protective action diffusion in flood-prone communities?

**Hypothesis H3a**: Communities with active social media will exhibit faster initial adaptation uptake but slower sustained adoption compared to observation + news channels.

**Falsification Criteria**: Uptake at year 3 exceeds observation-only by >10%; by year 10 the difference reverses.

**Hypothesis H3b**: Gossip-mediated reasoning propagation produces stronger adaptation clustering than simple observation.

**Key Metrics**:
- Information-action citation rate (fraction of reasoning texts citing each channel)
- Adaptation clustering (Moran's I on social network)
- Social contagion half-life (time for 50% of flooded agent's neighbors to adapt)
- Reasoning propagation depth (trace phrases through gossip chains)

**Key Figure**: Network visualization at years 1, 5, 9, and 13 showing adaptation state (node color) and gossip flow (edges).

---

## 3. Simulation Architecture

### High-Level Architecture

```
                    +------------------+
                    |  WAGF 3-Tier 3-Tier     |
                    |  Orchestrator    |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
         v                   v                   v
  +-----------+      +-----------+      +---------------+
  |   NJ Gov  |      |  FEMA/CRS |      |  Households   |
  | (NJDEP)   |      |           |      | (400 agents)  |
  +-----------+      +-----------+      +---------------+
         |                   |                   |
         |    Subsidy Rate   |   CRS Discount    |
         +--------->---------+---------->--------+
                             |
                    +--------v---------+
                    |  Environment     |
                    |  - Hazard Module |
                    |  - Social Network|
                    |  - Memory System |
                    +------------------+
```

### WAGF 3-Tier 3-Tier Ordering

Each simulation year proceeds in strict order:
1. **Government First**: NJ Government (NJDEP) decides on subsidy rate adjustments
2. **Insurance Second**: FEMA/NFIP CRS Administrator decides on CRS discount adjustments
3. **Households Third**: All 400 household agents make adaptation decisions

This ordering ensures institutional decisions affect household prompts within the same simulation year.

### Simulation Timeline

- **Years**: 2011-2023 (13 years)
- **Hazard Events**: Real flood depth data from PRB ASCII rasters
- **Seeds**: 10 random seeds for stochastic robustness (42, 123, 456, 789, 1024, 2048, 3072, 4096, 5120, 6144)

---

## 4. Agent Design and Initialization

### Population Composition

The simulation uses a **balanced 4-cell design** with 400 agents for statistical power:

| Cell | MG Status | Tenure | N | Flood-Prone % | Purpose |
|------|-----------|--------|---|---------------|---------|
| A | Marginalized | Owner | 100 | ~70% | Core equity analysis |
| B | Marginalized | Renter | 100 | ~70% | Vulnerable renter dynamics |
| C | Non-Marginalized | Owner | 100 | ~50% | Baseline comparison |
| D | Non-Marginalized | Renter | 100 | ~50% | Mobility effects |

### Initialization Pipeline

The agent initialization follows a 5-step pipeline:

```
Qualtrics CSV (920 raw)
    |  process_qualtrics_full.py
    v
cleaned_survey_full.csv (755 valid NJ respondents)
    |  BalancedSampler (stratified by MG/NMG x Owner/Renter)
    v
100 profiles per cell (400 total)
    |  generate_rcv() - lognormal / normal distributions
    v
HouseholdProfile objects (with RCV)
    |  assign_flood_zones() - real PRB ASCII raster
    v
agent_profiles_balanced.csv  +  initial_memories_balanced.json
```

#### Step 1: Survey Cleaning

**Script**: `paper3/process_qualtrics_full.py`

- Input: Raw Qualtrics export (920 respondents)
- Cleans PMT construct scores (TP, CP, SP, SC, PA) to 1-5 scale
- Derives demographics: income bracket, tenure, household size, flood experience
- Classifies MG/NMG via MGClassifier (income < $50K OR housing cost burden OR no vehicle)
- Output: `data/cleaned_survey_full.csv` (755 valid respondents after exclusions)

#### Step 2: Balanced Sampling

**Class**: `survey/balanced_sampler.py::BalancedSampler`

```python
BalancedSampler(n_per_cell=100, seed=42, allow_oversample=True)
```

- Stratum >= 100: `rng.sample(available, 100)` (without replacement)
- Stratum < 100 with `allow_oversample=True`: `rng.choices(available, k=100)` (with replacement, flagged)

#### Step 3: RCV Generation

**Function**: `generate_agents.py::generate_rcv(tenure, income, mg)`

| Agent Type | Distribution | Parameters | Bounds |
|------------|--------------|------------|--------|
| MG Owner (Building) | Lognormal | mu=$280K, sigma=0.3 | [$100K, $1M] |
| NMG Owner (Building) | Lognormal | mu=$400K, sigma=0.3 | [$100K, $1M] |
| Owner (Contents) | Uniform | 30-50% of building RCV | - |
| Renter (Building) | Fixed | $0 | - |
| Renter (Contents) | Normal | $20K + (income/$100K)*$40K, sigma=$5K | [$10K, $80K] |

#### Step 4: Spatial Assignment

**Function**: `paper3/prepare_balanced_agents.py::assign_flood_zones()`

Depth categories from PRB rasters:

| Category | Depth Range | % of Grid (2021) |
|----------|-------------|-------------------|
| DRY | 0 m | 76.93% |
| SHALLOW | 0 - 0.5 m | 2.51% |
| MODERATE | 0.5 - 1.0 m | 2.93% |
| DEEP | 1.0 - 2.0 m | 8.95% |
| VERY_DEEP | 2.0 - 4.0 m | 7.41% |
| EXTREME | > 4.0 m | 1.27% |

Assignment logic:
- Agents WITH flood experience (freq >= 2) -> deep/very_deep/extreme cells
- Agents WITH flood experience (freq < 2) -> shallow/moderate cells
- Agents WITHOUT experience: MG 70% / NMG 50% probability in flood-prone cells

Zone labels for prompts:
- depth = 0 -> LOW
- depth <= 0.5m -> MEDIUM
- depth > 0.5m -> HIGH

#### Step 5: Initial Memory Generation

Each agent receives 6 canonical memories derived from survey responses:

| # | Category | Importance | Example |
|---|----------|------------|---------|
| 1 | `flood_experience` | 0.3-0.8 | "I experienced flooding 3 times causing $85K damage" |
| 2 | `insurance_history` | 0.5-0.6 | "I have NFIP flood insurance for structure and contents" |
| 3 | `social_connections` | 0.4-0.7 | "I have strong connections with my neighbors" |
| 4 | `government_trust` | 0.5-0.7 | "I believe government agencies can help with flood protection" |
| 5 | `place_attachment` | 0.3-0.7 | "I've lived here for 20+ years; cannot imagine living elsewhere" |
| 6 | `flood_zone` | 0.3-0.7 | "My property is in a HIGH flood risk zone" |

---

## 5. Memory Architecture

### UnifiedCognitiveEngine

The memory system uses `UnifiedCognitiveEngine`, which replaces the parametric TP decay equations from traditional ABMs (e.g., the SCC paper).

**Key Design Principle**: Constructs (TP, CP, SP, SC, PA) are **outputs** of LLM reasoning, not inputs. The LLM receives persona + retrieved memories + environment context and *reasons* about threat/coping levels. Governance validates the resulting construct-action pairs.

### Memory Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Importance decay | 0.1/year | Annual decay rate for memory importance |
| Emotional weight (critical) | 1.0 | Weight for critical events |
| Emotional weight (fear) | 1.2 | Weight for threat-related events |
| Emotional weight (major) | 0.9 | Weight for major events |
| Emotional weight (positive) | 0.8 | Weight for positive outcomes |
| Source weight (personal) | 1.0 | Own experience |
| Source weight (neighbor) | 0.7 | Gossip/observation |
| Source weight (news) | 0.5 | Media channels |
| Source weight (social_media) | 0.3 | Social media |
| Window size | 5 years | Memory retrieval window |
| Consolidation threshold | 0.6 | Threshold for memory consolidation |
| Arousal threshold (household) | 1.0 m | Flood depth triggering crisis memory encoding |
| Ranking mode | weighted | Importance-weighted memory retrieval |

### Emotion Keywords

The system detects emotional valence through keywords:

- **Fear**: flood, damage, loss, destroy, water, inundation
- **Hope**: subsidy, elevated, safe, protected, insurance, grant
- **Anxiety**: premium, cost, afford, expense, budget

---

## 6. Decision Loop and Skills

### Annual Decision Loop

For each household agent, each simulation year:

1. **Memory Retrieval**: Top-k memories by importance-weighted relevance
2. **Prompt Construction**: Persona + memories + environment (flood depth, damage) + policy (subsidy rate, premium) + social info (neighbor actions, gossip, news, social media)
3. **LLM Call**: Gemma 3 4B, temperature=0.7, num_ctx=8192
4. **Parse Response**: Extract TP_LABEL, CP_LABEL, SP_LABEL, SC_LABEL, PA_LABEL, decision, reasoning
5. **Governance Validation**: WAGF 3-Tier rules check construct-action coherence
6. **Retry if Needed**: Up to 3 retries with intervention messages
7. **Audit Logging**: All decisions written to governance audit CSV
8. **Memory Encoding**: Decision + outcome stored as new memory

### Owner Skills

| Skill | Description | Sub-options |
|-------|-------------|-------------|
| `buy_insurance` | Purchase NFIP flood insurance | Structure+contents or contents-only |
| `elevate_house` | Elevate structure above BFE | 3ft, 5ft, or 8ft (with cost shown) |
| `buyout_program` | Accept NJ Blue Acres buyout | Irreversible, amount shown in prompt |
| `do_nothing` | Take no protective action | - |

### Renter Skills

| Skill | Description |
|-------|-------------|
| `buy_contents_insurance` | Contents-only NFIP policy |
| `relocate` | Move within PRB or out of basin |
| `do_nothing` | Take no protective action |

### Multi-Skill Support

Owners and renters can take up to 2 actions per year (e.g., buy_insurance AND elevate_house) with conflict resolution:
- `elevate_house` conflicts with `buyout_program`
- `buyout_program` conflicts with `elevate_house` and `buy_insurance`
- `relocate` conflicts with `buy_contents_insurance`

### Financial Information in Prompts

Agents receive decision-relevant financial context:
- Insurance premium ($/year from RCV + zone + CRS discount)
- Elevation cost ($/ft by foundation type)
- Buyout offer (% of pre-flood RCV)
- Current subsidy rate
- Deductible ($1K-$2K)
- Coverage limits (structure $250K, contents $100K)

---

## 7. Institutional Agents

### NJ Government (NJDEP) - Blue Acres Administrator

**Engine**: Window memory with `stimulus_key=adaptation_gap`

**Actions**:
- `increase_subsidy`: Raise elevation subsidy by 5%
- `decrease_subsidy`: Reduce subsidy by 5%
- `maintain_subsidy`: Keep current rate

**Context Received**:
- Flood damage reports
- MG/NMG adoption rates
- Budget status
- Community adaptation statistics

### FEMA/NFIP CRS Administrator

**Engine**: Window memory with `stimulus_key=loss_ratio`

**Actions**:
- `improve_crs`: Increase CRS discount by 5% (invest in community mitigation)
- `reduce_crs`: Reduce CRS discount by 5%
- `maintain_crs`: Keep current CRS class

**Mechanism**:
```
Effective premium = base_risk_rating_2_premium * (1 - crs_discount)
```
CRS discount range: 0-45%

**Context Received**:
- Claims history
- Uptake rates
- Program solvency
- Community mitigation score

---

## 8. Social Network and Information Channels

### Network Structure

- **Neighbors per agent**: 5
- **Same-region weighting**: 70%
- **Construction**: `SocialNetwork` class with geographic clustering

### Information Channels

| Channel | Delay | Reliability | Max Items | Content |
|---------|-------|-------------|-----------|---------|
| Observation | 0 | 1.0 | 5 neighbors | Elevated/insured/relocated status |
| Gossip | 0 | varies | 2 | Decision reasoning + experience |
| News Media | 1 year | 0.9 | - | Community-wide adaptation rates |
| Social Media | 0 | 0.4-0.8 | 3 posts | Sampled posts (exaggeration_factor=0.3) |

### Gossip Parameters

- `gossip_enabled`: true
- `max_gossip`: 2 per year
- `gossip_categories`: decision_reasoning, flood_experience, adaptation_outcome
- `gossip_importance_threshold`: 0.5

---

## 9. Hazard and Depth-Damage Model

### Hazard Input

- **Source**: 13 real PRB ASCII raster files (2011-2023)
- **Module**: `HazardModule`
- **Path**: `examples/multi_agent/flood/input/PRB/`
- **Format**: ESRI ASCII Grid

### Depth-Damage Functions

The simulation uses **HAZUS-MH** residential depth-damage curves (FEMA, 2022):

- 20-point piecewise-linear functions
- Separate curves for structure and contents
- Structure types: 1-story with basement, 2-story, split-level
- Contents typically 50-70% of structure RCV

**Damage Calculation**:
```
damage_$ = damage_pct(depth_above_FFE) * RCV
```

### FFE Adjustment

First Floor Elevation (FFE) accounts for elevated structures:
```
FFE = ground_elevation + elevation_ft
```
An agent who elevated by 5ft experiences zero damage for floods <= 5ft above BFE.

### NFIP Coverage Limits

- Structure: $250,000 maximum
- Contents: $100,000 maximum
- Deductible: $1,000-$2,000

---

## 10. Validation Framework

The validation framework implements 7 metrics across 3 levels, following Pattern-Oriented Modeling (Grimm et al., 2005).

### Core Argument

> We do not claim predictive accuracy. We demonstrate structural plausibility: LLM agent reasoning conforms to psychological theory, aggregate behavior falls within empirical ranges, and behavior is driven by persona content rather than LLM priors.

### Metric Summary

| # | Metric | Level | Threshold | What It Tests | LLM Needed |
|---|--------|-------|-----------|---------------|:----------:|
| 1 | CACR | L1 Micro | >= 0.80 | Construct-action coherence per PMT | No |
| 2 | R_H | L1 Micro | <= 0.10 | Physical hallucination rate | No |
| 3 | EBE | L1 Micro | > 0 (qualitative) | Behavioral diversity | No |
| 4 | EPI | L2 Macro | >= 0.60 | 8 benchmarks within empirical range | No |
| 5 | ICC(2,1) | L3 Cognitive | >= 0.60 | Test-retest reliability | Yes (2,700) |
| 6 | eta-sq | L3 Cognitive | >= 0.25 | Between-archetype effect size | Yes (same) |
| 7 | Directional | L3 Sensitivity | >= 75% pass | Persona/stimulus drives behavior | Yes (~5,000) |

### L1 Micro Metrics

**CACR (Construct-Action Coherence Rate)**

For each agent-year observation, checks whether reported TP/CP labels are consistent with the chosen action according to PMT theory.

- Example: TP=VH, CP=H, action=do_nothing -> INCOHERENT (fails)
- Example: TP=VH, CP=H, action=buy_insurance -> COHERENT (passes)
- CACR = coherent_count / total_count
- Threshold: >= 0.80

**R_H (Hallucination Rate)**

Detects physically impossible decisions:
- Agent already elevated -> proposes elevate again
- Agent already relocated -> makes any decision
- Thinking rule violations (construct label coherence)
- Threshold: <= 0.10

**EBE (Effective Behavioral Entropy)**

Shannon entropy of action distributions. Ensures the LLM has not collapsed into fixed patterns.
- Threshold: Qualitative (> 0 and not maximum)

### L2 Macro Metrics

**EPI (Empirical Plausibility Index)**

Weighted fraction of 8 empirical benchmarks where simulated aggregate rate falls within empirical range (with tolerance).

- Tolerance: +/- 30% range expansion
- Threshold: >= 0.60

### L3 Cognitive Metrics

**ICC(2,1) (Intraclass Correlation Coefficient)**

Test-retest reliability: same persona + same scenario, asked 30 times.
- ICC(2,1) two-way random effects model
- Subjects = (archetype x vignette) = 15 x 6 = 90
- Raters = 30 replicates
- Threshold: >= 0.60 for both TP and CP

**eta-squared (Between-Archetype Effect Size)**

Whether different archetypes produce meaningfully different behaviors.
- eta_sq = SS_between / (SS_between + SS_error)
- Threshold: >= 0.25 (large effect)

**Directional Sensitivity**

Whether stimuli changes produce expected behavioral changes.
- 4 directional tests: flood_depth -> TP, income -> CP, neighbor_adoption -> SC, subsidy -> decision
- 3 persona swap tests: income_swap, zone_swap, history_swap
- Pass if p < 0.05 AND direction matches expected
- Threshold: >= 75% of tests pass

---

## 11. Empirical Benchmarks

The simulation is validated against 8 empirical benchmarks spanning 4 categories.

### Benchmark Summary Table

| # | Metric Key | Range | Weight | Source | Category |
|---|------------|-------|--------|--------|----------|
| B1 | `insurance_rate` | 0.30 - 0.50 | 1.0 | Kousky (2017); FEMA NFIP | AGGREGATE |
| B2 | `insurance_rate_all` | 0.15 - 0.40 | 0.8 | Kousky & Michel-Kerjan (2017); Gallagher (2014) | AGGREGATE |
| B3 | `elevation_rate` | 0.03 - 0.12 | 1.0 | Haer et al. (2017); de Ruig et al. (2022) | AGGREGATE |
| B4 | `buyout_rate` | 0.02 - 0.15 | 0.8 | NJ DEP Blue Acres Program | AGGREGATE |
| B5 | `do_nothing_rate_postflood` | 0.35 - 0.65 | 1.5 | Grothmann & Reusswig (2006); Brody et al. (2017) | CONDITIONAL |
| B6 | `mg_adaptation_gap` | 0.10 - 0.30 | 2.0 | Choi et al. (2024); Collins et al. (2018) | DEMOGRAPHIC |
| B7 | `rl_uninsured_rate` | 0.15 - 0.40 | 1.0 | FEMA RL statistics | CONDITIONAL |
| B8 | `insurance_lapse_rate` | 0.05 - 0.15 | 1.0 | Gallagher (2014, AER); Michel-Kerjan et al. (2012) | TEMPORAL |

### Computation Methods

| Method | Benchmarks | How |
|--------|-----------|-----|
| End-year snapshot | B1, B2, B3, B4 | Agent state at year 13 |
| Event-conditional | B5, B7 | Filter agent-years where flood_depth > 0 or flood_count >= 2 |
| Annual flow | B8 | Year-over-year insured -> uninsured transitions |
| Group difference | B6 | NMG adapted rate - MG adapted rate at year 13 |

### Benchmark Notes

**B5 (Inaction Post-Flood)** receives the highest weight (1.5) because it tests the "risk perception paradox" - high threat combined with inaction.

**B6 (MG-NMG Gap)** receives weight 2.0 as the core equity metric for RQ2. If the model cannot reproduce this gap, RQ2 analysis is not meaningful.

**B8 (Lapse Rate)** is the most reliable benchmark based on NFIP policy panel data with millions of records.

---

## 12. ICC Probing Protocol

ICC probing is an **independent** validation that does not require experiment data. It tests whether the LLM produces consistent, persona-driven responses.

### Protocol Design

**Structure**: 15 archetypes x 6 vignettes x 30 replicates = **2,700 LLM calls**

### 15 Archetypes

| # | ID | Profile |
|---|-----|---------|
| 1 | `mg_owner_floodprone` | MG owner, AE zone, 2 floods, $25K-$45K |
| 2 | `mg_renter_floodprone` | MG renter, AE zone, 1 flood, $15K-$25K |
| 3 | `nmg_owner_floodprone` | NMG owner, AE zone, 1 flood, $75K-$100K |
| 4 | `nmg_renter_safe` | NMG renter, Zone X, 0 floods, $45K-$75K |
| 5 | `resilient_veteran` | NMG owner, 4 floods, elevated+insured, $100K+ |
| 6 | `vulnerable_newcomer` | MG renter, 6 months, 0 floods, <$15K |
| 7 | `mg_owner_safe` | MG owner, Zone X, 0 floods, moderate income |
| 8 | `nmg_renter_floodprone` | NMG renter, AE zone, 1 flood |
| 9 | `elderly_longterm` | NMG owner, 70+, 40yr residence, 3 floods |
| 10 | `young_firsttime_owner` | NMG, 28, first home, AE zone, 0 floods |
| 11 | `single_parent_renter` | MG, single parent, 2 kids, AE zone, 1 flood |
| 12 | `high_income_denier` | NMG owner, $150K+, AE zone, "doesn't believe in insurance" |
| 13 | `disabled_owner` | MG owner, mobility limitation, AE zone |
| 14 | `community_leader` | NMG owner, HOA president, high social capital |
| 15 | `recently_flooded` | MG renter, flooded 3 months ago, FEMA IA pending |

### 6 Vignettes

| # | ID | Severity | Expected TP |
|---|-----|----------|-------------|
| 1 | `high_severity_flood` | High | H or VH |
| 2 | `medium_severity_flood` | Medium | M |
| 3 | `low_severity_flood` | Low | VL or L |
| 4 | `extreme_compound` | Extreme | VH |
| 5 | `contradictory_signals` | Mixed | M to H |
| 6 | `post_adaptation` | Post | L to M |

### Statistical Tests

| Test | Target |
|------|--------|
| ICC(2,1) for TP | >= 0.60 |
| ICC(2,1) for CP | >= 0.60 |
| eta-squared for TP | >= 0.25 |
| eta-squared for CP | >= 0.25 |
| Cronbach's alpha | Reported |
| Fleiss' kappa | Reported |
| Convergent validity (Spearman TP vs severity) | Positive rho |
| TP-CP discriminant validity | r < 0.80 |

### Sensitivity Tests

**Persona Sensitivity (3 swap tests)**:
1. Income swap: MG persona gets NMG income and vice versa
2. Zone swap: Flood-experienced agent placed in Zone X
3. History swap: Never-flooded agent given 3-flood history

**Prompt Sensitivity (2 tests)**:
1. Option reordering: Reverse action option order
2. Framing removal: Remove "CRITICAL RISK ASSESSMENT" section

Pass criteria: Distributions change significantly (p < 0.05) for persona swaps; do NOT change significantly for prompt reordering.

---

## 13. How to Run

### Prerequisites

1. **Ollama** installed and running
2. Model downloaded:
   ```bash
   ollama pull gemma3:4b
   ```
3. PRB raster data in `examples/multi_agent/flood/input/PRB/` (13 .asc files)
4. Survey data processed: `data/cleaned_survey_full.csv`
5. Agent profiles generated: `data/agent_profiles_balanced.csv` + `data/initial_memories_balanced.json`

### Step 1: ICC Probing (Independent Validation)

```bash
# Navigate to project directory
cd examples/multi_agent/flood

# Run ICC probing (standalone, no experiment needed)
python paper3/run_cv.py --mode icc --model gemma3:4b --replicates 30
```

**Check**:
- ICC(2,1) >= 0.60 for TP and CP
- eta-squared >= 0.25
- If FAIL: adjust archetypes/prompts, re-run

### Step 2: Persona and Prompt Sensitivity

```bash
python paper3/run_cv.py --mode persona_sensitivity --model gemma3:4b
python paper3/run_cv.py --mode prompt_sensitivity --model gemma3:4b
```

**Check**: >= 75% pass rate. If FAIL, persona is not driving behavior; need prompt redesign.

### Step 3: Primary Experiment (10 Seeds)

```bash
# Run all seeds
for seed in 42 123 456 789 1024 2048 3072 4096 5120 6144; do
    python paper3/run_paper3.py --config paper3/configs/primary_experiment.yaml --seed $seed
done
```

Or in PowerShell:
```powershell
@(42, 123, 456, 789, 1024, 2048, 3072, 4096, 5120, 6144) | ForEach-Object {
    python paper3/run_paper3.py --config paper3/configs/primary_experiment.yaml --seed $_
}
```

### Step 4: Post-hoc Validation (Per Seed)

```bash
for seed in 42 123 456 789 1024 2048 3072 4096 5120 6144; do
    python paper3/run_cv.py --mode posthoc --trace-dir paper3/results/seed_$seed/
done
```

**Check**:
- CACR >= 0.80
- R_H <= 0.10
- EPI >= 0.60

### Step 5: Aggregate Validation

```bash
python paper3/run_cv.py --mode aggregate --results-dir paper3/results/
```

### Step 6: Baseline Traditional (Optional Comparison)

```bash
for seed in 42 123 456 789 1024; do
    python paper3/run_paper3.py --config paper3/configs/baseline_traditional.yaml --seed $seed
done
```

### Step 7: SI Ablations (Optional)

```bash
python paper3/run_paper3.py --config paper3/configs/si_ablations.yaml --ablation si1_window_memory --all-seeds
```

---

## 14. Output Structure

```
paper3/results/
  cv/                                    # ICC probing results
    icc_report.json                      # ICC, eta-squared, Cronbach's alpha
    icc_responses.csv                    # Raw LLM responses (2,700 rows)
    persona_sensitivity_report.json      # Persona swap test results
    prompt_sensitivity_report.json       # Prompt reordering test results
    aggregate_cv_table.csv               # Mean +/- std across seeds

  paper3_primary/
    seed_42/
      gemma3_4b_strict/
        raw/
          household_owner_traces.jsonl   # Owner decision traces
          household_renter_traces.jsonl  # Renter decision traces
          government_traces.jsonl        # NJDEP policy decisions
          insurance_traces.jsonl         # FEMA/CRS decisions
        household_owner_governance_audit.csv  # Owner validation audit
        household_renter_governance_audit.csv # Renter validation audit
        cv/
          posthoc_report.json            # CACR, R_H, EBE, EPI
    seed_123/
      ...
    seed_456/
      ...
```

### Key Output Files

| File | Description |
|------|-------------|
| `*_traces.jsonl` | Raw LLM responses with full reasoning |
| `*_governance_audit.csv` | Per-decision construct labels, action, validity |
| `posthoc_report.json` | L1/L2 metrics per seed |
| `icc_report.json` | L3 psychometric results |
| `aggregate_cv_table.csv` | Cross-seed statistics |

---

## 15. Computational Requirements

### LLM Call Estimates

| Component | LLM Calls | Time Estimate |
|-----------|-----------|---------------|
| Primary experiment (400 x 13 x 10 seeds) | 52,000 | ~7.2 hours |
| Baseline traditional (no LLM) | 0 | ~minutes |
| SI ablations (200 agents, 3 seeds each, 10 configs) | 83,200 | ~11.6 hours |
| ICC probing (15 x 6 x 30) | 2,700 | ~22 minutes |
| Persona + prompt sensitivity | ~5,000 | ~42 minutes |
| **Grand total** | **~169,000** | **~23.5 hours** |

### Hardware Configuration

- **Inference**: Local Ollama server
- **Model**: Gemma 3 4B (quantization and SHA-256 hash logged for reproducibility)
- **Context**: num_ctx = 8192 tokens (16384 for extended prompts)
- **Temperature**: 0.7 (harmonized across ICC probing and experiments)
- **Max Retries**: 3 for governance validation

### Memory Requirements

- Minimum: 8GB RAM for Gemma 3 4B
- Recommended: 16GB RAM for parallel processing
- GPU: Optional but recommended for faster inference

---

## 16. Key Differences from Traditional ABM

| Capability | Traditional ABM (SCC Paper) | LLM-ABM (Paper 3) |
|------------|------------------------------|-------------------|
| TP decay | Parametric equation (tract-level, MG/NMG uniform) | Memory-mediated (individual, experience-dependent) |
| Decision-making | Bayesian regression lookup | LLM reasoning with persona + memory |
| Constructs | Pre-initialized from Beta distributions | Emergent from reasoning (output, not input) |
| Social influence | Aggregate % observation (tract-level) | Direct neighbor observation + gossip + media |
| Institutional agents | Exogenous (fixed subsidies/premiums) | Endogenous LLM agents (NJDEP + FEMA) |
| Action granularity | Binary (adopt/not) | Sub-options (elevation amount, insurance type) |
| Individual heterogeneity | Within-group agents identical | Each agent has unique memory, reasoning, history |
| Validation | Aggregate statistics only | 3-level framework (micro, macro, cognitive) |
| Reasoning transparency | Black box | Full reasoning traces for every decision |

### Specification Burden

The LLM approach achieves individual heterogeneity with lower specification burden. A single natural-language persona and memory system replaces dozens of parametric equations. The trade-off is computational cost (LLM inference) versus analytical tractability (closed-form equations).

---

## 17. File Inventory

### broker/validators/calibration/ (Generic Framework Layer)

| File | Lines | Key Exports |
|------|-------|-------------|
| `benchmark_registry.py` | 493 | `BenchmarkRegistry`, `Benchmark`, `BenchmarkReport` |
| `directional_validator.py` | 757 | `DirectionalValidator`, `DirectionalTest`, `SwapTest` |
| `calibration_protocol.py` | 737 | `CalibrationProtocol`, `CalibrationConfig` |
| `cv_runner.py` | 562 | `CVRunner`, `CVReport` |
| `micro_validator.py` | 611 | `MicroValidator`, `MicroReport` |
| `distribution_matcher.py` | 625 | `DistributionMatcher`, `MacroReport` |
| `temporal_coherence.py` | 426 | `TemporalCoherenceValidator` |
| `validation_router.py` | 807 | `ValidationRouter`, `ValidationPlan` |
| `psychometric_battery.py` | 1327 | `PsychometricBattery`, `ICCResult` |

### paper3/ Root Scripts

| File | Purpose | CLI |
|------|---------|-----|
| `run_cv.py` | Master C&V runner | `--mode {icc,posthoc,aggregate}` |
| `launch_icc.py` | Standalone ICC launcher | `--model, --replicates` |
| `run_paper3.py` | Experiment runner | `--config, --seed, --all-seeds` |
| `prepare_balanced_agents.py` | Survey -> balanced agents | `--seed, --n-per-cell` |
| `process_qualtrics_full.py` | Raw Qualtrics -> cleaned CSV | - |

### paper3/analysis/

| File | Purpose |
|------|---------|
| `audit_to_cv.py` | Audit CSV -> CVRunner DataFrame adapter |
| `calibration_hooks.py` | Domain callbacks for CalibrationProtocol |
| `empirical_benchmarks.py` | 8 flood benchmarks + aggregate rate computation |
| `persona_sensitivity.py` | 3 persona swap tests |
| `prompt_sensitivity.py` | Option reordering + framing tests |
| `memory_causal_test.py` | Offline memory-decision correlation |

### paper3/configs/

| File | Purpose |
|------|---------|
| `primary_experiment.yaml` | Full-featured experiment (400 agents, 13 years, 10 seeds) |
| `baseline_traditional.yaml` | SCC replication baseline (no LLM) |
| `si_ablations.yaml` | 10 supplementary ablation configs |
| `calibration.yaml` | Three-stage calibration protocol thresholds |
| `icc_archetypes.yaml` | 15 archetype definitions |
| `vignettes/*.yaml` | 6 vignette scenarios |

### tests/

| File | Tests | What It Tests |
|------|-------|---------------|
| `test_benchmark_registry.py` | 45 | Registry, EPI, weighted scoring |
| `test_directional_validator.py` | 33 | Statistical tests, mock LLM |
| `test_calibration_protocol.py` | 26 | Three-stage protocol |

---

## 18. Glossary

| Term | Definition |
|------|------------|
| ABM | Agent-Based Model |
| BFE | Base Flood Elevation |
| CACR | Construct-Action Coherence Rate |
| CP | Coping Perception (PMT construct) |
| CRS | Community Rating System (NFIP discount program) |
| EBE | Effective Behavioral Entropy |
| EPI | Empirical Plausibility Index |
| FFE | First Floor Elevation |
| ICC | Intraclass Correlation Coefficient |
| MG | Marginalized (household demographic group) |
| NFIP | National Flood Insurance Program |
| NMG | Non-Marginalized (household demographic group) |
| PA | Place Attachment (PMT construct) |
| PMT | Protection Motivation Theory |
| POM | Pattern-Oriented Modeling |
| PRB | Passaic River Basin |
| R_H | Hallucination Rate |
| RCV | Replacement Cost Value |
| RL | Repetitive Loss |
| RQ | Research Question |
| WAGF 3-Tier | WAGF Agent Governance Architecture |
| WAGF | Water Agent Governance Framework |
| SC | Social Capital (PMT construct) |
| SFHA | Special Flood Hazard Area |
| SI | Supplementary Information |
| SP | Stakeholder Perception (PMT construct) |
| TP | Threat Perception (PMT construct) |
| WRR | Water Resources Research (journal) |

---

## 19. Citations

### Flood Adaptation and Risk Perception

- Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. *Natural Hazards*, 38(1-2), 101-120.
- Brody, S. D., et al. (2017). Examining the impact of flood risk on residential property values in the Harris County, Texas. *Journal of the American Planning Association*, 83(4), 428-445.
- Gallagher, J. (2014). Learning about an infrequent event: Evidence from flood insurance take-up in the United States. *American Economic Review*, 104(11), 3606-3634.
- Kousky, C. (2017). Disasters as learning experiences or disasters as policy opportunities: The role of learning in flood insurance demand. *Journal of Risk and Uncertainty*, 55(1), 77-98.
- Kousky, C., & Michel-Kerjan, E. (2017). Examining flood insurance claims in the United States: Six key findings. *Journal of Risk and Insurance*, 84(3), 819-850.

### Environmental Justice and Vulnerability

- Chakraborty, J., et al. (2014). Social vulnerability and climate change: A framework for flood risk reduction. *Environmental Hazards*, 13(4), 265-286.
- Choi, J., et al. (2024). Inequality in flood adaptation: Evidence from New Jersey. *Environmental Research Letters*, 19(3), 034041.
- Collins, T. W., et al. (2018). Mapping social vulnerability to climate change impacts in the US Southwest. *Applied Geography*, 91, 22-33.

### Agent-Based Modeling

- Haer, T., et al. (2017). The safe development paradox: An agent-based model for flood risk under climate change in the European Union. *Global Environmental Change*, 42, 79-91.
- de Ruig, L. T., et al. (2022). An agent-based model for evaluating the efficacy of the managed retreat strategy in flood risk management. *Risk Analysis*, 42(8), 1690-1710.
- Grimm, V., et al. (2005). Pattern-oriented modeling of agent-based complex systems: Lessons from ecology. *Science*, 310(5750), 987-991.

### NFIP and Insurance

- Michel-Kerjan, E., et al. (2012). The National Flood Insurance Program: Past, present, and future. *Journal of Economic Perspectives*, 26(2), 21-46.
- FEMA (2022). HAZUS-MH Flood Model Technical Manual.

### Memory and Cognition

- McEwen, B. S., et al. (2017). Mechanisms of stress in the brain. *Nature Neuroscience*, 18(10), 1353-1363.
- Park, J. S., et al. (2023). Generative agents: Interactive simulacra of human behavior. *arXiv preprint arXiv:2304.03442*.

### Survey Sampling

- Kish, L. (1965). *Survey Sampling*. John Wiley & Sons.
- Cochran, W. G. (1977). *Sampling Techniques* (3rd ed.). John Wiley & Sons.

---

## License

This project is part of academic research. Please cite appropriately if using components of this framework.

## Contact

For questions about this implementation, please refer to the paper or contact the corresponding author through the Water Resources Research submission system.
