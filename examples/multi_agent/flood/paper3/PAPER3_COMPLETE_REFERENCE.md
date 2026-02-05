# Paper 3: Complete Project Reference

> **Purpose**: Master context document for all agents working on the Paper 3 LLM-governed multi-agent flood adaptation simulation. Covers everything from research design to validation to execution.
>
> **Last updated**: 2026-02-04
>
> **Status**: All code implemented. Awaiting ICC probing + experiment execution.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Research Questions & Hypotheses](#2-research-questions--hypotheses)
3. [Simulation Architecture](#3-simulation-architecture)
4. [Validation Framework (7 Metrics)](#4-validation-framework-7-metrics)
5. [Empirical Benchmarks (8 Benchmarks)](#5-empirical-benchmarks-8-benchmarks)
6. [ICC Probing Protocol](#6-icc-probing-protocol)
7. [Experiment Configurations](#7-experiment-configurations)
8. [Execution Order](#8-execution-order)
9. [Complete File Inventory](#9-complete-file-inventory)
10. [Key Parameters & Thresholds](#10-key-parameters--thresholds)

---

## 1. Project Overview

### Target

Paper 3 targets **Water Resources Research (WRR)**. The SAGE governance framework is the tool; the story is about **flood adaptation science** in the Passaic River Basin (PRB), New Jersey.

### Core Claim

We claim **structural plausibility**, not predictive accuracy. The LLM-ABM produces individually heterogeneous adaptation trajectories that fall within empirically defensible aggregate ranges, something traditional equation-based ABMs cannot achieve without drastically more complex specification.

### What Traditional ABMs Have Not Done

| Capability | Traditional ABM (SCC Paper) | LLM-ABM (Paper 3) |
|---|---|---|
| TP decay | Parametric equation (tract-level, MG/NMG uniform) | Memory-mediated (individual, experience-dependent) |
| Decision-making | Bayesian regression lookup | LLM reasoning with persona + memory |
| Constructs | Pre-initialized from Beta distributions | Emergent from reasoning (output, not input) |
| Social influence | Aggregate % observation (tract-level) | Direct neighbor observation + gossip + media |
| Institutional agents | Exogenous (fixed subsidies/premiums) | Endogenous LLM agents (NJDEP + FEMA) |
| Action granularity | Binary (adopt/not) | Sub-options (elevation amount, insurance type) |
| Individual heterogeneity | Within-group agents identical | Each agent has unique memory, reasoning, history |

The LLM approach achieves these features with lower specification burden -- a single natural-language persona and memory system replaces dozens of parametric equations -- and generates qualitative reasoning traces that reveal *why* agents decide as they do.

### Study Area

- **Passaic River Basin (PRB)**, New Jersey
- 27 census tracts
- Real flood hazard data: 13 ASCII raster files (2011-2023)
- Grid size: ~457 x 411 cells
- Raster path: `examples/multi_agent/flood/input/PRB/`

---

## 2. Research Questions & Hypotheses

All three RQs are answered from a **single unified experiment** (full-featured LLM-ABM, all modules active). The narrative progresses from **Individual -> Institutional -> Collective**.

### RQ1: Individual Memory & Pathway Divergence

> How does differential accumulation of personal flood damage memories create within-group divergence in adaptation timing, and does this divergence disproportionately delay adaptation among financially constrained households?

**H1**: Households that accumulate personal flood damage memories will exhibit faster adaptation uptake than households with equivalent initial profiles but only vicarious exposure; this "experience-adaptation gap" will be wider for MG households due to financial constraints.

**Falsification**: Cox PH interaction term (personal_damage x MG_status) significant at alpha=0.05; hazard ratio for MG >= 1.5x NMG. If H1 is falsified: the memory-adaptation pathway is not MG-moderated.

**Key metrics**:

- Intra-group TP variance per year (traditional ABM = 0 by construction)
- Cox PH survival analysis (time-to-first-adaptation)
- Pathway entropy (Shannon entropy of action sequences)
- Memory salience score (top-k memories at decision time)

**Key figure**: Adaptation trajectory spaghetti plot -- individual TP trajectories over 13 years, color-coded MG/NMG.

### RQ2: Institutional Feedback & Protection Inequality

> Do reactive institutional policies -- subsidy adjustments and CRS-mediated premium discounts -- narrow or widen the cumulative protection gap between marginalized and non-marginalized households over decadal timescales?

**H2a**: Government subsidy increases following high-MG-damage flood events arrive too late to prevent widening of the cumulative damage gap. Falsification: If subsidy-adaptation lag < 2 years AND MG-NMG gap narrows.

**H2b**: CRS discount reductions following high-loss years produce an "affordability spiral". Falsification: 1pp effective premium increase -> >=5% increase in P(lapse) for lowest income quartile.

**Key metrics**:

- Subsidy-adaptation lag (cross-correlation, lag in years)
- Premium-dropout correlation (panel regression)
- Cumulative damage Gini coefficient
- Protection gap (fraction MG without insurance or elevation vs NMG, per year)

**Key figure**: Dual-axis time series -- subsidy/premium rates overlaid with MG/NMG adaptation rates, annotated with flood markers.

### RQ3: Social Information & Adaptation Diffusion

> Which information channels most effectively accelerate sustained protective action diffusion in flood-prone communities?

**H3a**: Communities with active social media will exhibit faster initial adaptation uptake but slower sustained adoption, compared to observation + news. Falsification: Uptake at year 3 exceeds observation-only by >10%; by year 10 the difference reverses.

**H3b**: Gossip-mediated reasoning propagation produces stronger adaptation clustering than simple observation.

**Key metrics**:

- Information-action citation rate (fraction of reasoning texts citing each channel)
- Adaptation clustering (Moran's I on social network)
- Social contagion half-life (time for 50% of flooded agent's neighbors to adapt)
- Reasoning propagation depth (trace phrases through gossip chains)

**Key figure**: Network visualization at years 1, 5, 9, 13 -- adaptation state (node color), gossip flow (edges).

---

## 3. Simulation Architecture

### 3.1 Agent Design

**Composition**: 400 agents, balanced 4-cell design for statistical power:

| Cell | MG Status | Tenure | N | Flood-Prone % |
|------|-----------|--------|---|---------------|
| A | MG | Owner | 100 | ~70% |
| B | MG | Renter | 100 | ~70% |
| C | NMG | Owner | 100 | ~50% |
| D | NMG | Renter | 100 | ~50% |

**Initialization pipeline** (see `paper3/AGENT_INITIALIZATION.md` for full details):

1. **Survey cleaning**: `process_qualtrics_full.py` -- Raw Qualtrics CSV (920 respondents) -> cleaned PMT constructs + demographics -> `cleaned_survey_full.csv`
2. **Balanced sampling**: `prepare_balanced_agents.py` -- `BalancedSampler` stratifies by MG/NMG x Owner/Renter, draws 100 per cell (with replacement if stratum < 100)
3. **RCV generation**: `generate_agents.py::generate_rcv()` -- Lognormal distributions for building RCV, income-scaled normal for contents
   - Owner building: `np.random.lognormal(ln(mu), 0.3)`, mu=$280K (MG) / $400K (NMG), bounded [$100K, $1M]
   - Owner contents: 30-50% of building RCV (uniform)
   - Renter building: $0; Renter contents: `Normal($20K + income/$100K x $40K, $5K)`, bounded [$10K, $80K]
4. **Spatial assignment**: `assign_flood_zones()` -- Real PRB ASCII raster data (2021 reference year, 457x411 grid)
   - Agents WITH flood experience + freq >= 2 -> deep/very_deep cells (1-4m+)
   - Agents WITH flood experience + freq < 2 -> shallow/moderate cells (0-1m)
   - Agents WITHOUT experience: MG 70% / NMG 50% probability in flood-prone cells, remainder in dry cells
   - Grid (row, col) -> lat/lon via ESRI metadata (`yllcorner + (nrows-1-row) x cellsize`)
   - Zone labels: depth=0 -> LOW, depth<=0.5m -> MEDIUM, depth>0.5m -> HIGH
5. **Output**: `data/agent_profiles_balanced.csv` (400 rows x 70+ columns) + `data/initial_memories_balanced.json` (2,400 memories)

**Memory seeding**: 6 canonical templates per agent:

1. `flood_experience` -- personal flood history
2. `insurance_history` -- insurance awareness/status
3. `social_connections` -- neighbor interactions (from SC score)
4. `government_trust` -- institutional confidence (from SP score)
5. `place_attachment` -- home attachment (from PA score)
6. `flood_zone` -- risk awareness

### 3.2 Memory Architecture

**Engine**: `UnifiedCognitiveEngine` (replaces parametric TP decay from SCC paper)

| Parameter | Value | File |
|-----------|-------|------|
| Importance decay | 0.1 per year | `ma_agent_types.yaml` global_config.memory |
| Emotional weights | major=1.2, minor=0.8, neutral=0.3 | `ma_agent_types.yaml` memory_config.household |
| Source weights | personal=1.0, neighbor=0.7, news=0.5 | `ma_agent_types.yaml` memory_config.household |
| Window size | 5 years | `ma_agent_types.yaml` global_config.memory |
| Consolidation threshold | 0.6 | `ma_agent_types.yaml` global_config.memory |
| Arousal threshold (household) | 1.0 m flood depth | `ma_agent_types.yaml` cognitive_config |
| Ranking mode | weighted | `ma_agent_types.yaml` global_config.memory |
| Emotion keywords | fear: [flood, damage, loss, destroy]; hope: [subsidy, elevated, safe] | `ma_agent_types.yaml` memory_config.household |

**Key mechanism**: Constructs (TP, CP, SP, SC, PA) are **outputs** of LLM reasoning, not inputs. The LLM receives persona + retrieved memories + environment context and *reasons* about threat/coping levels. Governance validates the resulting construct-action pairs.

### 3.3 Household Decision Loop

Each year, for each household agent:

1. **Memory retrieval**: Top-k memories by importance-weighted relevance
2. **Prompt construction**: Persona + memories + environment (flood depth, damage) + policy (subsidy rate, premium) + social info (neighbor actions, gossip, news, social media)
3. **LLM call**: Gemma 3 4B, temp=0.7, num_ctx=8192
4. **Parse response**: Extract TP_LABEL, CP_LABEL, SP_LABEL, SC_LABEL, PA_LABEL, decision, reasoning
5. **Governance validation**: SAGA rules check construct-action coherence
6. **Retry if needed**: Up to 3 retries with intervention messages
7. **Audit logging**: All decisions written to `household_*_governance_audit.csv`
8. **Memory encoding**: Decision + outcome stored as new memory

**Owner skills**:

| Skill | Description | Sub-options |
|-------|-------------|-------------|
| `buy_insurance` | Purchase NFIP flood insurance | structure+contents or contents-only |
| `elevate_house` | Elevate structure above BFE | 3ft, 5ft, or 8ft (with cost shown) |
| `buyout_program` | Accept Blue Acres buyout | irreversible, amount shown in prompt |
| `do_nothing` | Take no protective action | -- |

**Renter skills**:

| Skill | Description |
|-------|-------------|
| `buy_contents_insurance` | Contents-only NFIP policy |
| `relocate` | Move within PRB or out of basin |
| `do_nothing` | Take no protective action |

**Financial information shown in prompt**: Insurance premium ($/year from RCV + zone + CRS), elevation cost ($/ft by foundation type), buyout offer (% of pre-flood RCV), current subsidy rate, deductible ($1K-$2K), coverage limits (structure $250K, contents $100K).

### 3.4 Institutional Agents

**NJ Government (NJDEP) -- Blue Acres Administrator**:

- Engine: Window memory, stimulus_key=adaptation_gap
- Actions: increase_subsidy / decrease_subsidy / maintain_subsidy (5% steps)
- Receives: flood damage reports, MG/NMG adoption rates, budget status
- LLM-driven with governance (strict profile)

**FEMA/NFIP CRS Administrator**:

- Engine: Window memory, stimulus_key=loss_ratio
- Actions: improve_crs / reduce_crs / maintain_crs (adjusts CRS class discount by 5%)
- Mechanism: Effective premium = base_risk_rating_2_premium x (1 - crs_discount). CRS range: 0-45%
- Receives: claims history, uptake rates, solvency, mitigation score

**SAGA 3-tier ordering**: Government first -> Insurance second -> Households third (each year). Government and insurance decisions affect household prompts in the same year.

### 3.5 Social Network & Information Channels

**Network**: 5 neighbors/agent, 70% same-region weighting (`SocialNetwork`)

| Channel | Delay | Reliability | Max Items | What Agents See |
|---------|-------|-------------|-----------|-----------------|
| Observation | 0 | 1.0 | 5 neighbors | Elevated/insured/relocated status |
| Gossip | 0 | varies | max 2 | Decision reasoning + experience |
| News media | 1 year | 0.9 | -- | Community-wide adaptation rates |
| Social media | 0 | 0.4-0.8 | max 3 posts | Sampled posts (with exaggeration_factor=0.3) |

**Gossip filtering**: importance_threshold=0.5, categories: decision_reasoning, flood_experience, adaptation_outcome.

### 3.6 Hazard & Depth-Damage Model

**Hazard input**: 13 real PRB ASCII raster files (2011-2023), loaded by `HazardModule`

**Depth-damage**: HAZUS-MH residential curves (FEMA, 2022):

- 20-point piecewise-linear depth-damage functions
- Separate curves for structure and contents
- Structure types: 1-story with basement, 2-story, split-level
- Contents typically 50-70% of structure RCV
- `damage_$ = damage_pct(depth_above_FFE) x RCV`

**FFE adjustment**: First Floor Elevation = ground + elevation_ft. An agent who elevated by 5ft reduces damage to zero for floods <= 5ft above BFE.

**Implementation**: `examples/multi_agent/flood/environment/vulnerability.py` -- `VulnerabilityCalculator`

### 3.7 Governance (SAGA)

**Profile**: Strict for households

**Thinking rules (construct-action coherence)**:

- `owner_inaction_high_threat`: VH/H TP + M/H/VH CP -> BLOCK do_nothing (ERROR level)
- `owner_fatalism_warning`: VH/H TP + VL/L CP -> do_nothing allowed (WARNING only) -- preserves risk perception paradox
- Similar rules for renters
- Low CP -> BLOCK expensive actions (elevate, buyout)

**Identity rules (state preconditions)**:

- Already elevated -> can't elevate again
- Already relocated -> no further decisions
- Renter -> can't elevate or buyout

**Financial constraints**: Enforced in governance -- agents can't choose actions they can't afford.

**Retry mechanism**: Up to 3 retries with intervention messages explaining why the action was blocked.

### 3.8 Computational Requirements

| Component | LLM Calls | Time Estimate |
|-----------|-----------|---------------|
| Primary experiment (400 x 13 x 10 seeds) | 52,000 | ~7.2 hours |
| Baseline traditional (no LLM) | 0 | ~minutes |
| SI ablations (200 agents, 3 seeds each, 10 configs) | 83,200 | ~11.6 hours |
| ICC probing (15 x 6 x 30) | 2,700 | ~22 minutes |
| Persona + prompt sensitivity | ~5,000 | ~42 minutes |
| **Grand total** | **~169,000** | **~23.5 hours** |

**Hardware**: Local Ollama inference server
**Model**: Gemma 3 4B (specific quantization + SHA-256 hash to be logged)
**Context**: num_ctx = 8192 tokens
**Temperature**: 0.7 (harmonized across ICC probing and experiments)

---

## 4. Validation Framework (7 Metrics)

### Core Argument

> We do not claim predictive accuracy. We demonstrate structural plausibility: LLM agent reasoning conforms to psychological theory, aggregate behavior falls within empirical ranges, and behavior is driven by persona content rather than LLM priors.

### Metric Summary Table

| # | Metric | Level | Threshold | What It Tests | Data Source | LLM Needed? |
|---|--------|-------|-----------|---------------|-------------|:-----------:|
| 1 | CACR | L1 Micro | >= 0.80 | Construct-action coherence per PMT | Audit CSV | No |
| 2 | R_H | L1 Micro | <= 0.10 | Physical hallucination rate | Audit CSV | No |
| 3 | EBE | L1 Micro | > 0 (qualitative) | Behavioral diversity (not all-same) | Audit CSV | No |
| 4 | EPI | L2 Macro | >= 0.60 | 8 benchmarks within empirical range | Audit CSV + literature | No |
| 5 | ICC(2,1) | L3 Cognitive | >= 0.60 | Test-retest reliability across archetypes | Independent probing | **Yes** (2,700) |
| 6 | eta-sq | L3 Cognitive | >= 0.25 | Between-archetype effect size | Independent probing | **Yes** (same) |
| 7 | Directional | L3 Sensitivity | >= 75% pass | Persona/stimulus drives behavior | Independent probing | **Yes** (~5,000) |

### 4.1 CACR (Construct-Action Coherence Rate)

**What**: For each agent-year observation, checks whether the reported TP/CP labels are consistent with the chosen action according to PMT theory.

**How computed**: `MicroValidator.compute_cacr(df)` in `broker/validators/calibration/micro_validator.py`

- Uses `PMTFramework.validate(appraisals, action)` to check each observation
- Example: TP=VH, CP=H, action=do_nothing -> INCOHERENT (fails)
- Example: TP=VH, CP=H, action=buy_insurance -> COHERENT (passes)
- CACR = coherent_count / total_count

**Threshold**: >= 0.80 (at least 80% of 5,200 agent-year observations are coherent)

**Observations**: ~5,200 per seed (400 agents x 13 years)

### 4.2 R_H (Hallucination Rate)

**What**: Detects physically impossible decisions -- LLM "hallucinations" that violate state constraints.

**How computed**: `compute_hallucination_rate()` in `broker/validators/posthoc/unified_rh.py`

- **Physical hallucinations**: Agent already elevated -> proposes elevate again. Agent already relocated -> makes any decision. Checks irreversible state columns.
- **Thinking rule violations**: Post-hoc check of construct label coherence (V3 rules)
- R_H = (n_physical + n_thinking) / n_active_observations

**Threshold**: <= 0.10 (at most 10% hallucination rate)

### 4.3 EBE (Effective Behavioral Entropy)

**What**: Measures behavioral diversity. If all 400 agents choose the same action every year, EBE ~ 0, indicating the LLM collapsed into a fixed pattern.

**How computed**: Yearly Shannon entropy of action distributions across agents. Reported alongside R_H.

**Threshold**: Qualitative -- EBE > 0 and not near theoretical maximum (which would indicate pure randomness). Reported but no hard pass/fail.

### 4.4 EPI (Empirical Plausibility Index)

**What**: Weighted fraction of 8 empirical benchmarks where the simulated aggregate rate falls within the empirical range (with tolerance).

**How computed**:

1. `compute_aggregate_rates(df)` in `paper3/analysis/empirical_benchmarks.py` extracts 8 metrics from audit CSV
2. `BenchmarkRegistry.compare(observed, tolerance=0.3)` in `broker/validators/calibration/benchmark_registry.py` checks each metric against its empirical range
3. Range check: `observed in [rate_low * (1-tolerance), rate_high * (1+tolerance)]`
4. EPI = sum(weight_i * within_range_i) / sum(weight_i) for all evaluated benchmarks

**Threshold**: >= 0.60 (at least 60% weighted benchmarks within range)

**See Section 5 for detailed benchmark descriptions.**

### 4.5 ICC(2,1) (Intraclass Correlation Coefficient)

**What**: Test-retest reliability. Same persona + same scenario, asked 30 times -- how consistent are the responses?

**How computed**: `compute_icc_2_1()` in `broker/validators/calibration/psychometric_battery.py`

- ICC(2,1) two-way random effects model
- Subjects = (archetype x vignette) combinations = 15 x 6 = 90
- Raters = 30 replicates
- Computed separately for TP and CP ordinal labels

**Threshold**: >= 0.60 for both TP and CP (moderate-to-good reliability)

### 4.6 eta-squared (Between-Archetype Effect Size)

**What**: Do different archetypes produce meaningfully different behaviors? Or does the LLM give similar answers regardless of persona?

**How computed**: `compute_effect_size()` in `psychometric_battery.py`

- eta_sq = SS_between / (SS_between + SS_error)
- SS_between from ANOVA decomposition of construct labels across archetypes

**Threshold**: >= 0.25 (large effect -- archetypes explain at least 25% of behavioral variance)

### 4.7 Directional Sensitivity (Pass Rate)

**What**: When a stimulus changes (e.g., flood depth increases), does the LLM output change in the expected direction (TP increases)?

**How computed**: `DirectionalValidator.run_all()` in `broker/validators/calibration/directional_validator.py`

- 4 directional tests: flood_depth -> TP, income -> CP, neighbor_adoption -> SC, subsidy -> decision
- 3 persona swap tests: income_swap, zone_swap, history_swap
- Statistical tests: Mann-Whitney U (ordinal), chi-squared (categorical)
- Pass if p < 0.05 AND direction matches expected

**Threshold**: >= 75% of tests pass (at least 5 out of 7)

---

## 5. Empirical Benchmarks (8 Benchmarks)

### Overview

8 benchmarks across 4 categories, following Pattern-Oriented Modeling (Grimm et al., 2005). Four different computation methods from audit CSV data.

### Computation Methods

| Method | Benchmarks | How |
|--------|-----------|-----|
| **End-year snapshot** | insurance_rate, insurance_rate_all, elevation_rate, buyout_rate | Agent state at year 13 |
| **Event-conditional** | do_nothing_rate_postflood, rl_uninsured_rate | Filter agent-years where flood_depth > 0 or flood_count >= 2 |
| **Annual flow** | insurance_lapse_rate | Year-over-year insured -> uninsured transitions |
| **Group difference** | mg_adaptation_gap | NMG adapted rate - MG adapted rate at year 13 |

### Benchmark Details

#### B1: NFIP Insurance Uptake (SFHA)

| Field | Value |
|-------|-------|
| Metric key | `insurance_rate` |
| Range | 0.30 - 0.50 |
| Category | AGGREGATE |
| Weight | 1.0 |
| Source | Kousky (2017); FEMA NFIP statistics |
| Computation | Last-year snapshot: `last_df["insured"].mean()` |
| Data quality | B (FEMA statistics, denominator uncertainty) |
| Known bias | FEMA flood maps may undercount structures in SFHA, potentially **overestimating** uptake rate. Wing et al. (2018) suggest true rate may be ~25%. |

#### B2: Insurance Uptake (All Zones)

| Field | Value |
|-------|-------|
| Metric key | `insurance_rate_all` |
| Range | 0.15 - 0.40 |
| Category | AGGREGATE |
| Weight | 0.8 |
| Source | Kousky & Michel-Kerjan (2017); Gallagher (2014) |
| Computation | Same as B1 but includes all agents (not just SFHA) |
| Data quality | B (limited data outside SFHA) |
| Known bias | Overlaps with B1 but broader scope; weight reduced to 0.8 for partial redundancy |

#### B3: Elevation Adoption (Cumulative)

| Field | Value |
|-------|-------|
| Metric key | `elevation_rate` |
| Range | 0.03 - 0.12 |
| Category | AGGREGATE |
| Weight | 1.0 |
| Source | Haer et al. (2017); de Ruig et al. (2022) |
| Computation | Last-year snapshot: `owners[owners["elevated"]].count() / len(owners)` |
| Data quality | C (model-calibrated values, not direct observations) |
| Known bias | Range from other ABM calibrations (Netherlands, Louisiana), not direct US census data. No national elevation rate statistics exist. |

#### B4: Blue Acres Buyout Participation

| Field | Value |
|-------|-------|
| Metric key | `buyout_rate` |
| Range | 0.02 - 0.15 |
| Category | AGGREGATE |
| Weight | 0.8 |
| Source | NJ DEP Blue Acres Program reports; Greer & Brokopp Binder (2017) |
| Computation | Last-year snapshot: `last_df["relocated"].mean()` |
| Data quality | B (NJ-specific program data, but range is our interpretation) |
| Known bias | Highly event-dependent (Sandy: ~40% in Woodbridge, <10% elsewhere). Weight 0.8 because buyout may be 0 in some years (normal). |

#### B5: Inaction Rate (Post-Flood)

| Field | Value |
|-------|-------|
| Metric key | `do_nothing_rate_postflood` |
| Range | 0.35 - 0.65 |
| Category | CONDITIONAL |
| Weight | 1.5 (highest priority) |
| Source | Grothmann & Reusswig (2006); Brody et al. (2017) |
| Computation | All (agent, year) where flood_depth > 0: `(action == "do_nothing").mean()` |
| Data quality | B (survey data, but definition of "action" varies across studies) |
| Known bias | Grothmann & Reusswig is German; Brody is US. Social desirability bias may **underestimate** true inaction. This is the most critical benchmark -- tests the risk perception paradox (high threat + inaction). |

#### B6: MG-NMG Adaptation Gap

| Field | Value |
|-------|-------|
| Metric key | `mg_adaptation_gap` |
| Range | 0.10 - 0.30 |
| Category | DEMOGRAPHIC |
| Weight | 2.0 (highest weight) |
| Source | Choi et al. (2024); Collins et al. (2018) |
| Computation | Last-year: NMG_adapted_rate - MG_adapted_rate (adapted = insured OR elevated OR relocated) |
| Data quality | B (our own survey + literature) |
| Known bias | Selection bias in survey respondents. Weight 2.0 because this is the core equity metric for RQ2 -- if the model can't reproduce the gap, RQ2 analysis is meaningless. |

#### B7: Repetitive Loss Uninsured Rate

| Field | Value |
|-------|-------|
| Metric key | `rl_uninsured_rate` |
| Range | 0.15 - 0.40 |
| Category | CONDITIONAL |
| Weight | 1.0 |
| Source | FEMA RL statistics; Kousky & Michel-Kerjan (2010) |
| Computation | Agents flooded >= 2 times who are NOT insured at last year |
| Data quality | A (FEMA administrative data, but definition of RL changed over time) |
| Known bias | Only records agents who filed claims -- truly uninsured RL properties may not appear in FEMA data at all, potentially **underestimating** the true rate. |

#### B8: Insurance Annual Lapse Rate

| Field | Value |
|-------|-------|
| Metric key | `insurance_lapse_rate` |
| Range | 0.05 - 0.15 |
| Category | TEMPORAL |
| Weight | 1.0 |
| Source | Gallagher (2014, AER); Michel-Kerjan et al. (2012) |
| Computation | Year-over-year: insured_year_N but not insured_year_N+1, divided by insured_year_N, averaged across all year pairs |
| Data quality | A (NFIP policy panel data, millions of records) |
| Known bias | Data from 1978-2007; Risk Rating 2.0 (2021) changed fee structure. NJ post-Sandy lapse dynamics may differ from national average. **Most reliable benchmark**. |

### Benchmark Limitations (for Methods section)

> Our 8 empirical benchmarks span four categories and draw on NFIP administrative records, post-disaster survey data, and prior ABM calibration targets. We acknowledge three limitations: (1) most benchmarks derive from national-level or non-PRB studies; local post-Sandy dynamics may differ systematically; (2) some benchmarks (elevation, buyout) lack direct observational data and rely on model-calibrated values; (3) the tolerance parameter (+/-30%) reflects uncertainty, not a statistically derived confidence interval. EPI is a plausibility check, not a claim of predictive accuracy.

---

## 6. ICC Probing Protocol

### Design

ICC probing is an **independent** validation -- it does not require experiment data. It tests whether the LLM produces consistent, persona-driven responses.

**Protocol**: 15 archetypes x 6 vignettes x 30 replicates = **2,700 LLM calls**

### 15 Archetypes

| # | ID | Profile | Rationale |
|---|-----|---------|-----------|
| 1 | `mg_owner_floodprone` | MG owner, AE zone, 2 floods, $25K-$45K | Core cell A |
| 2 | `mg_renter_floodprone` | MG renter, AE zone, 1 flood, $15K-$25K | Core cell B |
| 3 | `nmg_owner_floodprone` | NMG owner, AE zone, 1 flood, $75K-$100K | Core cell C |
| 4 | `nmg_renter_safe` | NMG renter, Zone X, 0 floods, $45K-$75K | Core cell D |
| 5 | `resilient_veteran` | NMG owner, 4 floods, elevated+insured, $100K+ | Extreme resilience |
| 6 | `vulnerable_newcomer` | MG renter, 6 months, 0 floods, <$15K | Extreme vulnerability |
| 7 | `mg_owner_safe` | MG owner, Zone X, 0 floods, moderate income | MG + low risk |
| 8 | `nmg_renter_floodprone` | NMG renter, AE zone, 1 flood | NMG + renter + risk |
| 9 | `elderly_longterm` | NMG owner, 70+, 40yr residence, 3 floods | Age/attachment |
| 10 | `young_firsttime_owner` | NMG, 28, first home, AE zone, 0 floods | Youth + naivety |
| 11 | `single_parent_renter` | MG, single parent, 2 kids, AE zone, 1 flood | Caregiving constraint |
| 12 | `high_income_denier` | NMG owner, $150K+, AE zone, "doesn't believe in insurance" | Adversarial persona |
| 13 | `disabled_owner` | MG owner, mobility limitation, AE zone | Accessibility barrier |
| 14 | `community_leader` | NMG owner, HOA president, high social capital | Social influence |
| 15 | `recently_flooded` | MG renter, flooded 3 months ago, FEMA IA pending | Acute crisis |

Config file: `paper3/configs/icc_archetypes.yaml` (453 lines)

### 6 Vignettes

| # | ID | Severity | Scenario | Expected TP |
|---|-----|----------|----------|-------------|
| 1 | `high_severity_flood` | High | 4.5 ft flood, $42K damage, 65% 10yr prob | H or VH |
| 2 | `medium_severity_flood` | Medium | 1.2 ft minor flood, Zone B, 15-20yr return | M |
| 3 | `low_severity_flood` | Low | Zone X, no flooding in 30 years | VL or L |
| 4 | `extreme_compound` | Extreme | Catastrophic 8ft + budget exhausted + lapsed insurance | VH |
| 5 | `contradictory_signals` | Mixed | FEMA says low risk but agent just experienced 2ft flood | M to H |
| 6 | `post_adaptation` | Post | Already elevated + insured, faces moderate flood | L to M |

Config files: `paper3/configs/vignettes/*.yaml` (6 files, 371 lines total)

### Statistical Tests Computed

| Test | What It Measures | Target |
|------|-----------------|--------|
| ICC(2,1) for TP | TP label consistency across replicates | >= 0.60 |
| ICC(2,1) for CP | CP label consistency across replicates | >= 0.60 |
| eta-squared for TP | Archetype effect on TP labels | >= 0.25 |
| eta-squared for CP | Archetype effect on CP labels | >= 0.25 |
| Cronbach's alpha | Internal consistency of responses | reported |
| Fleiss' kappa | Nominal agreement on decisions | reported |
| Convergent validity | Spearman(TP_ordinal, vignette_severity) | positive rho |
| TP-CP discriminant | TP-CP cross-correlation | r < 0.80 |

### Sensitivity Tests (run alongside ICC)

**Persona sensitivity** (3 swap tests):

1. Income swap: MG persona gets NMG income ($75K-$100K) and vice versa
2. Zone swap: Flood-experienced agent placed in Zone X (minimal risk)
3. History swap: Never-flooded agent given 3-flood history

**Prompt sensitivity** (2 tests):

1. Option reordering: Reverse action option order (do_nothing first for owners)
2. Framing removal: Remove "CRITICAL RISK ASSESSMENT" section

Both use chi-squared test of independence. Pass if distributions change significantly (p < 0.05) for persona swaps, and do NOT change significantly for prompt reordering.

### Execution

```bash
# ICC probing (standalone, no experiment needed)
python paper3/launch_icc.py --model gemma3:4b --replicates 30

# Or via run_cv.py
python paper3/run_cv.py --mode icc --model gemma3:4b --replicates 30
```

Output: `paper3/results/cv/icc_report.json` + `icc_responses.csv`

---

## 7. Experiment Configurations

### 7.1 Primary Experiment

**File**: `paper3/configs/primary_experiment.yaml` (75 lines)

```
Model:          gemma3:4b
Agents:         400 (balanced 4-cell, 100/cell)
Years:          13 (2011-2023)
Seeds:          10 (42, 123, 456, 789, 1024, 2048, 3072, 4096, 5120, 6144)
Memory:         UnifiedCognitiveEngine (importance decay, emotional weighting)
Institutions:   LLM-driven government + insurance
Social:         All channels ON (observation, gossip, news, social media)
Governance:     Strict profile
Hazard:         Real PRB rasters
Temperature:    0.7
```

### 7.2 Baseline Traditional

**File**: `paper3/configs/baseline_traditional.yaml` (69 lines)

```
Model:          none (no LLM)
Agents:         400 (same balanced design)
Years:          13
Seeds:          5 (42, 123, 456, 789, 1024)
Memory:         Parametric TP decay (SCC parameters: alpha, beta, tau_0, tau_inf, k)
Institutions:   Exogenous/fixed (no LLM)
Social:         All OFF (isolated agents)
Governance:     Disabled
```

Purpose: Framing (show traditional all-identical trajectories) + sanity check (aggregate rates in same ballpark).

### 7.3 SI Ablations

**File**: `paper3/configs/si_ablations.yaml` (150 lines)

| SI | Description | Key Override | Agents | Seeds |
|----|-------------|-------------|--------|-------|
| SI-1 | Window memory (no importance) | memory.engine=window | 200 | 3 |
| SI-2 | Exogenous institutions | institutions.*.llm_driven=false | 200 | 3 |
| SI-3a | No gossip | social.gossip=false | 200 | 3 |
| SI-3b | No social media | social.social_media=false | 200 | 3 |
| SI-3c | Isolated (no social) | social.*=false | 200 | 3 |
| SI-4a | Gemma 3 12B | model.name=gemma3:12b | 200 | 3 |
| SI-4b | Mistral 7B | model.name=mistral | 200 | 3 |
| SI-7 | Governance OFF | governance.profile=disabled | 200 | 3 |
| SI-8 | PRB-proportional demographics | balanced=false (80/80/160/80) | 400 | 1 |
| SI-9 | Climate scaling | hazard.depth_multiplier=1.2 for years 10-13 | 400 | 3 |

### 7.4 Calibration Protocol

**File**: `paper3/configs/calibration.yaml` (226 lines)

Three-stage protocol managed by `CalibrationProtocol` class:

| Stage | Agents | Years | Seeds | EPI Threshold | Purpose |
|-------|--------|-------|-------|---------------|---------|
| Pilot | 25 | 3 | 1 | 0.50 | Fast iteration on prompt design |
| Sensitivity | -- | -- | -- | 75% pass | Directional + swap tests |
| Full | 400 | 13 | 10 | 0.60 | Production validation |

---

## 8. Execution Order

### Prerequisites

1. Ollama installed and running
2. `ollama pull gemma3:4b` completed
3. PRB raster data in `examples/multi_agent/flood/input/PRB/` (13 .asc files)
4. Survey data processed: `data/cleaned_survey_full.csv` exists
5. Agent profiles generated: `data/agent_profiles_balanced.csv` + `data/initial_memories_balanced.json`

### Step-by-Step

```
STEP 0: Git commit (Section 14 changes still uncommitted)
  git add [files] && git commit

STEP 1: ICC Probing (independent, no experiment needed)
  python paper3/launch_icc.py --model gemma3:4b --replicates 30
  -> Output: paper3/results/cv/icc_report.json
  -> CHECK: ICC(2,1) >= 0.60 for TP and CP
  -> CHECK: eta-squared >= 0.25
  -> If FAIL: adjust archetypes/prompts, re-run

STEP 2: Persona & Prompt Sensitivity
  python paper3/run_cv.py --mode persona_sensitivity --model gemma3:4b
  python paper3/run_cv.py --mode prompt_sensitivity --model gemma3:4b
  -> CHECK: >= 75% pass rate
  -> If FAIL: persona not driving behavior, need prompt redesign

STEP 3: Primary Experiment (10 seeds)
  for seed in 42 123 456 789 1024 2048 3072 4096 5120 6144:
    python paper3/run_paper3.py --config paper3/configs/primary_experiment.yaml --seed $seed
  -> Output: paper3/results/seed_$seed/household_*_governance_audit.csv

STEP 4: Post-hoc C&V (per seed, no LLM)
  for seed in 42 123 456 789 1024 2048 3072 4096 5120 6144:
    python paper3/run_cv.py --mode posthoc --trace-dir paper3/results/seed_$seed/
  -> Output: paper3/results/seed_$seed/cv/posthoc_report.json
  -> CHECK: CACR >= 0.80, R_H <= 0.10, EPI >= 0.60

STEP 5: Aggregate C&V
  python paper3/run_cv.py --mode aggregate --results-dir paper3/results/
  -> Output: paper3/results/cv/aggregate_cv_table.csv (mean +/- std per metric)

STEP 6: Baseline Traditional (5 seeds)
  for seed in 42 123 456 789 1024:
    python paper3/run_paper3.py --config paper3/configs/baseline_traditional.yaml --seed $seed

STEP 7: SI Ablations
  python paper3/run_paper3.py --config paper3/configs/si_ablations.yaml --ablation si1_window_memory --all-seeds
  [repeat for each SI config]

STEP 8: Analysis Scripts (figures, tables)
  [Phase E/F - not yet implemented]
```

### Decision Points

- **After Step 1**: If ICC < 0.60, do NOT proceed to Step 3. Fix prompts first.
- **After Step 2**: If directional pass < 75%, the LLM is not persona-sensitive enough. Consider different model or prompt structure.
- **After Step 4**: If CACR < 0.80 for any seed, investigate which agent types are problematic. If EPI < 0.60, compare against benchmarks to see which are out of range.

---

## 9. Complete File Inventory

### broker/validators/calibration/ (Generic Framework Layer)

| File | Lines | Purpose | Key Exports |
|------|-------|---------|-------------|
| `benchmark_registry.py` | 493 | Domain-agnostic benchmark comparison + EPI | `BenchmarkRegistry`, `Benchmark`, `BenchmarkReport`, `BenchmarkCategory` |
| `directional_validator.py` | 757 | Generic sensitivity testing | `DirectionalValidator`, `DirectionalTest`, `SwapTest`, `chi_squared_test`, `mann_whitney_u` |
| `calibration_protocol.py` | 737 | Three-stage calibration orchestrator | `CalibrationProtocol`, `CalibrationConfig`, `CalibrationReport`, `AdjustmentRecommendation` |
| `cv_runner.py` | 562 | Three-level C&V orchestrator | `CVRunner`, `CVReport` |
| `micro_validator.py` | 611 | L1: CACR, BRC, EGS | `MicroValidator`, `MicroReport`, `BRCResult` |
| `distribution_matcher.py` | 625 | L2: KS, Wasserstein, chi-sq, PEBA | `DistributionMatcher`, `MacroReport`, `PEBAFeatures` |
| `temporal_coherence.py` | 426 | TCS + action stability | `TemporalCoherenceValidator`, `ActionStabilityValidator` |
| `validation_router.py` | 807 | Auto-detect features -> validation plan | `ValidationRouter`, `FeatureProfile`, `ValidationPlan`, `ValidatorType` |
| `psychometric_battery.py` | 1327 | L3: ICC, Cronbach, convergent validity | `PsychometricBattery`, `Vignette`, `ProbeResponse`, `ICCResult` |
| `__init__.py` | 124 | Central exports | All public symbols from above modules |

**Total**: ~6,469 lines

### broker/validators/posthoc/

| File | Lines | Purpose |
|------|-------|---------|
| `unified_rh.py` | 238 | R_H + EBE computation (domain-agnostic with configurable irreversible states) |

### paper3/ Root Scripts

| File | Lines | Purpose | CLI |
|------|-------|---------|-----|
| `run_cv.py` | 798 | Master C&V runner (icc / posthoc / aggregate modes) | `--mode {icc,posthoc,aggregate}` |
| `launch_icc.py` | 111 | Standalone ICC launcher with Ollama model management | `--model, --replicates` |
| `run_paper3.py` | 198 | Experiment runner (translates YAML -> CLI args -> subprocess) | `--config, --seed, --all-seeds, --ablation` |
| `prepare_balanced_agents.py` | 370 | Survey -> balanced 4-cell agents + memories | `--survey, --n-per-cell, --seed` |
| `process_qualtrics_full.py` | 417 | Raw Qualtrics -> cleaned survey CSV | -- |

### paper3/analysis/

| File | Lines | Purpose | Broker Dependency |
|------|-------|---------|-------------------|
| `audit_to_cv.py` | 297 | Audit CSV -> CVRunner DataFrame adapter | CVRunner format |
| `calibration_hooks.py` | 309 | Domain callbacks for CalibrationProtocol | BenchmarkRegistry, DirectionalValidator |
| `empirical_benchmarks.py` | 324 | 8 flood benchmarks + compute_aggregate_rates | BenchmarkRegistry |
| `persona_sensitivity.py` | 356 | 3 persona swap tests | chi_squared_test from directional_validator |
| `prompt_sensitivity.py` | 476 | Option reordering + framing tests | chi_squared_test from directional_validator |
| `memory_causal_test.py` | 368 | Offline memory-decision correlation | None (standalone) |

### paper3/configs/

| File | Lines | Purpose |
|------|-------|---------|
| `primary_experiment.yaml` | 75 | Full-featured experiment config |
| `baseline_traditional.yaml` | 69 | SCC replication baseline |
| `si_ablations.yaml` | 150 | 10 supplementary ablation configs |
| `calibration.yaml` | 226 | Three-stage calibration protocol thresholds |
| `icc_archetypes.yaml` | 453 | 15 archetype definitions for ICC probing |
| `vignettes/high_severity.yaml` | 63 | High severity vignette |
| `vignettes/medium_severity.yaml` | 62 | Medium severity vignette |
| `vignettes/low_severity.yaml` | 59 | Low severity vignette |
| `vignettes/extreme_compound.yaml` | 61 | Catastrophic scenario |
| `vignettes/contradictory_signals.yaml` | 63 | Cognitive dissonance scenario |
| `vignettes/post_adaptation.yaml` | 63 | Post-adaptation scenario |

### tests/

| File | Lines | Tests | What It Tests |
|------|-------|-------|---------------|
| `test_benchmark_registry.py` | 646 | 45 | Registry, EPI computation, weighted scoring, YAML loading |
| `test_directional_validator.py` | 621 | 33 | Chi-squared, Mann-Whitney U, mock LLM directional tests |
| `test_calibration_protocol.py` | 683 | 26 | Three-stage protocol with mock simulate_fn |
| **Total** | **1,950** | **104** | -- |

---

## 10. Key Parameters & Thresholds

### Validation Thresholds

| Parameter | Value | Source | File |
|-----------|-------|--------|------|
| CACR threshold | >= 0.80 | PMT coherence standard | `calibration.yaml` full.cacr_threshold |
| R_H threshold | <= 0.10 | Max acceptable hallucination | Convention |
| EPI threshold | >= 0.60 | 60% benchmarks plausible | `calibration.yaml` full.epi_threshold |
| ICC(2,1) threshold | >= 0.60 | Moderate reliability | `calibration.yaml` full.icc_threshold |
| eta-squared threshold | >= 0.25 | Large effect size | `icc_archetypes.yaml` protocol.eta_squared |
| Directional pass rate | >= 0.75 | 75% sensitivity tests pass | `calibration.yaml` sensitivity.directional_pass_threshold |
| EPI tolerance | 0.30 | +/-30% range expansion | `calibration.yaml` tolerance |

### Simulation Parameters

| Parameter | Value | Source | File |
|-----------|-------|--------|------|
| Agents | 400 (100/cell) | Statistical power for Cox PH | `primary_experiment.yaml` |
| Years | 13 (2011-2023) | Real PRB flood history | `primary_experiment.yaml` |
| Seeds | 10 | Stochastic robustness | `primary_experiment.yaml` |
| Temperature | 0.7 | Harmonized with ICC | `ma_agent_types.yaml` global_config.llm |
| num_ctx | 8192 | Context window | `ma_agent_types.yaml` |
| max_retries (governance) | 3 | Governance retry limit | `ma_agent_types.yaml` global_config.governance |

### Memory Parameters

| Parameter | Value | Source | File |
|-----------|-------|--------|------|
| Importance decay | 0.1 | Per-year decay rate | `ma_agent_types.yaml` global_config.memory |
| Emotional weight (major) | 1.2 | Threat/fear events | `ma_agent_types.yaml` memory_config.household |
| Emotional weight (minor) | 0.8 | Positive/hope events | `ma_agent_types.yaml` memory_config.household |
| Source weight (personal) | 1.0 | Own experience | `ma_agent_types.yaml` memory_config.household |
| Source weight (neighbor) | 0.7 | Gossip/observation | `ma_agent_types.yaml` memory_config.household |
| Source weight (news) | 0.5 | Media channels | `ma_agent_types.yaml` memory_config.household |
| Window size | 5 years | Memory retrieval window | `ma_agent_types.yaml` global_config.memory |
| Arousal threshold (household) | 1.0 m | Crisis memory encoding | `ma_agent_types.yaml` cognitive_config |

### Agent Initialization Parameters

| Parameter | Value | Source | File |
|-----------|-------|--------|------|
| MG flood-prone % | 70% | Balanced design | `primary_experiment.yaml` |
| NMG flood-prone % | 50% | Balanced design | `primary_experiment.yaml` |
| Homeowner RCV (mu, sigma) | (12.46, 0.63) | Lognormal | `prepare_balanced_agents.py` |
| Renter RCV (mu, sigma) | (12.82, 1.20) | Lognormal | `prepare_balanced_agents.py` |
| Neighbors per agent | 5 | Social network | `primary_experiment.yaml` |
| Same-region weight | 0.70 | Network construction | `primary_experiment.yaml` |
| Gossip max | 2 | Per-year gossip messages | -- |
| Gossip importance threshold | 0.5 | Minimum importance to share | -- |
| News reliability | 0.9 | News media channel | -- |
| Social media reliability | 0.4-0.8 | Social media channel | -- |
| Social media exaggeration | 0.3 | Noise factor | -- |

### Benchmark Weights

| Benchmark | Weight | Rationale |
|-----------|--------|-----------|
| NFIP Insurance (SFHA) | 1.0 | Core behavior metric |
| Insurance (All Zones) | 0.8 | Partially redundant with SFHA |
| Elevation | 1.0 | Core structural adaptation |
| Buyout | 0.8 | Event-dependent, may be 0 |
| Inaction (Post-Flood) | 1.5 | Tests risk perception paradox |
| MG-NMG Gap | 2.0 | Core equity metric for RQ2 |
| RL Uninsured | 1.0 | Insurance retention dynamics |
| Lapse Rate | 1.0 | Memory decay -> behavior |

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| ABM | Agent-Based Model |
| BFE | Base Flood Elevation |
| BRC | Behavioral Reference Concordance (renamed to GCR for Paper 3) |
| CACR | Construct-Action Coherence Rate |
| CP | Coping Perception (PMT construct) |
| CRS | Community Rating System (NFIP discount program) |
| EBE | Effective Behavioral Entropy |
| EPI | Empirical Plausibility Index |
| FFE | First Floor Elevation |
| GCR | Governance Concordance Rate (= BRC, renamed to avoid circularity concern) |
| ICC | Intraclass Correlation Coefficient |
| MG | Marginalized (household demographic group) |
| NFIP | National Flood Insurance Program |
| NMG | Non-Marginalized (household demographic group) |
| PA | Place Attachment (PMT construct) |
| PEBA | Pattern-oriented Empirical Bayesian Approach |
| PMT | Protection Motivation Theory |
| POM | Pattern-Oriented Modeling |
| PRB | Passaic River Basin |
| R_H | Hallucination Rate |
| RCV | Replacement Cost Value |
| RL | Repetitive Loss |
| RQ | Research Question |
| SAGA | SAGE Agent Governance Architecture (3-tier) |
| SAGE | Simulated Agent Governance Engine |
| SC | Social Capital (PMT construct) |
| SCC | Social Capital and Cohesion (prior paper) |
| SFHA | Special Flood Hazard Area |
| SI | Supplementary Information |
| SP | Stakeholder Perception (PMT construct) |
| TCS | Temporal Consistency Score |
| TP | Threat Perception (PMT construct) |
| WRR | Water Resources Research (journal) |

---

## Appendix B: Module Dependency Graph

```
CalibrationProtocol
  |-- BenchmarkRegistry (EPI computation)
  |-- DirectionalValidator (sensitivity tests)
  |-- CVRunner (post-hoc validation)
        |-- MicroValidator (CACR, BRC, EGS)
        |     |-- PMTFramework (construct-action rules)
        |     |-- KeywordClassifier (EGS)
        |-- DistributionMatcher (KS, Wasserstein, PEBA)
        |-- TemporalCoherenceValidator (TCS)
        |-- ActionStabilityValidator (entropy)
        |-- compute_hallucination_rate (R_H, EBE)
        |-- PsychometricBattery (ICC, eta-sq)
        |-- BenchmarkRegistry (EPI, via parameter)
        |-- ValidationRouter (auto-detect features)

Domain Layer (paper3/):
  empirical_benchmarks.py --> BenchmarkRegistry
  persona_sensitivity.py --> chi_squared_test (from directional_validator)
  prompt_sensitivity.py  --> chi_squared_test (from directional_validator)
  calibration_hooks.py   --> CalibrationProtocol callbacks
  audit_to_cv.py         --> CVRunner DataFrame format
  run_cv.py              --> CVRunner + PsychometricBattery + empirical_benchmarks
```
