# Paper 3: Writing Plan for Water Resources Research

## Publication Unit Budget

WRR formula: **PU = words/500 + figures + tables** (max 25 PU)

| Component | Count | PU |
|-----------|------:|---:|
| Body text | ~7,500 words | 15 |
| Main figures | 6 | 6 |
| Main tables | 3 | 3 |
| **Total** | | **24** |

Excluded from word count: title, authors, Key Points, keywords, text inside tables, Open Research section, references, SM.

---

## 1. Manuscript Structure (WRR-Conforming)

### Front Matter

#### Title
> LLM-Governed Multi-Agent Simulation of Heterogeneous Flood Adaptation: Memory, Institutional Feedback, and Social Information in the Passaic River Basin

#### Key Points (exactly 3, each ≤ 140 characters)
1. `Memory-mediated threat perception generates within-group adaptation heterogeneity invisible to parametric agent-based models` (126 chars)
2. `Endogenous government and insurance feedbacks produce subsidy-lag and premium-spiral patterns that widen protection inequality` (124 chars)
3. `Gossip with reasoning propagation drives stronger adaptation clustering than observation or media channels alone` (112 chars)

#### Abstract (< 250 words, single paragraph)
Theme: Traditional ABMs treat agents within demographic groups as identical, producing zero within-group variance. We develop an LLM-governed multi-agent simulation using the SAGE (Structured Agent Governance Engine) framework where 100 household agents in the Passaic River Basin, NJ develop unique adaptation trajectories through personal flood memory, institutional feedback, and social information channels over 13 years.

Structure: (1) Gap — parametric ABM limitations; (2) Approach — SAGE framework with memory-mediated cognition, endogenous institutions, multi-channel social information; (3) Key findings for RQ1/RQ2/RQ3; (4) Implication for flood risk management and policy.

#### Plain Language Summary (≤ 200 words, no jargon)
Theme: Accessible explanation of why individual flood experiences matter for community-level adaptation, and how government/insurance policies interact with personal decisions. Written for non-specialist audience.

---

### Section Plan

#### 1. Introduction (~1,500 words, 3 PU)

**Paragraph flow:**

1. **Opening hook**: Flood losses in the US continue to rise despite mitigation investments. The Passaic River Basin, NJ exemplifies this challenge — repeated flooding, socioeconomic disparities, contested buyout programs. (Set the water resources problem.)

2. **ABM state of the art**: Agent-based models have advanced coupled human-water systems research (Haer et al., 2017; de Ruig et al., 2022). Protection Motivation Theory provides a behavioral foundation (Rogers, 1983; Grothmann & Reusswig, 2006). However, conventional ABMs parameterize threat perception decay identically for all agents within a demographic group, assume exogenous institutional policies, and represent social influence as a single aggregate scalar.

3. **Three specific gaps**: (a) Within-group homogeneity — agents with identical demographics produce identical trajectories, masking the most vulnerable individuals behind group means; (b) No institutional feedback — subsidies and premiums are fixed parameters, preventing coupled human-institutional dynamics; (c) Impoverished social information — a single adoption percentage replaces the rich information ecology of real communities.

4. **LLM-agent opportunity**: Recent advances in LLM-based agents (Park et al., 2023; Huang et al., 2025) demonstrate that language models can simulate heterogeneous cognitive processes. When governed by domain rules, LLM agents can produce behavior that is both diverse and theoretically coherent. This paper introduces a governed LLM-ABM approach to flood adaptation.

5. **Three RQs + contribution statement**:
   - **RQ1**: How does flood memory heterogeneity shape the divergence of household adaptation pathways across socioeconomic groups?
   - **RQ2**: How do endogenous institutional feedbacks create or mitigate emergent patterns of protection inequality?
   - **RQ3**: How do social information channels with different temporal and reliability properties influence the speed and spatial pattern of protective action diffusion?

   Contribution: First LLM-governed ABM for flood adaptation with (a) memory-mediated cognition replacing parametric equations, (b) endogenous institutional agents, (c) multi-channel social information, validated through a 5-metric calibration and validation protocol.

---

#### 2. Background (~1,200 words, 2.4 PU)

**2.1 Protection Motivation Theory for Flood Adaptation** (~400 words)
- PMT theory: threat appraisal (TP, SP) and coping appraisal (CP, SC, PA) (Rogers, 1983)
- Application to flood adaptation: Grothmann & Reusswig (2006), Bamberg et al. (2017)
- TP decay problem: parametric exponential or Bayesian updating (Haer et al., 2017)
- Key limitation: all agents within a group share identical decay parameters

**2.2 Agent-Based Models in Flood Risk Research** (~400 words)
- Evolution from simple rule-based to PMT-informed (Haer et al., 2017; de Ruig et al., 2022; Michaelis et al., 2020)
- Social influence mechanisms: observation-based, threshold models (Bruch & Atwell, 2015)
- Institutional coupling: mostly exogenous (fixed policies) or simplified feedback rules
- Calls for more realistic cognitive architectures (An, 2012; Schlüter et al., 2017)

**2.3 LLM Agents for Sociotechnical Simulation** (~400 words)
- Generative Agents: Park et al. (2023) — memory, reflection, planning
- LLM agents in social science: Huang et al. (2025 Nature MI), AgentTorch (Chopra et al., 2024)
- Governance challenge: LLMs can hallucinate, violate domain rules, produce incoherent behavior
- SAGE framework: governance middleware that constrains LLM outputs to domain-valid actions while preserving reasoning diversity

---

#### 3. Methods (~3,000 words, 6 PU) — Core of the paper

**3.1 Study Area and Data** (~400 words)
- Passaic River Basin, NJ: geography, flood history, socioeconomic context
- 27 census tracts, MG/NMG classification via NJDEP environmental justice criteria
- NJ flood preparedness survey (755 responses) for agent initialization
- 13 years of ASCII flood hazard raster data (2011-2023)
- **→ Figure 1: Study area map**

**3.2 SAGE Governance Framework** (~500 words)
- Architecture overview: LLM reasoning → Governance validation → Memory storage → Action execution
- Three-tier agent ordering: Government → Insurance → Households (sequential phases)
- Governance profiles: strict validation ensures PMT-coherent decisions
- Key innovation: constructs as outputs (not inputs) — LLM reasons from memory to produce construct labels + decision
- **→ Figure 2: Framework architecture diagram**

**3.3 Agent Design** (~500 words)
- **Households** (100 agents, balanced 4-cell design):
  - 25 MG-Owner, 25 MG-Renter, 25 NMG-Owner, 25 NMG-Renter
  - Persona from survey data; location via DepthSampler (MG: 70% flood-prone; NMG: 50%)
  - Skills: buy_insurance (structure+contents / contents-only), elevate_house (3/5/8 ft), buyout_program, relocate, do_nothing
  - Financial information injected into prompts (costs, subsidies, premiums)
- **NJ Government** (1 agent): Blue Acres administrator; adjusts subsidy rate ±5%
- **FEMA/NFIP Insurance** (1 agent): Risk Rating 2.0; adjusts premium rate based on loss ratio
- **→ Table 1: Agent configuration**

**3.4 Memory Architecture** (~400 words)
- HumanCentric memory engine: importance decay (λ=0.1), emotional weighting (fear=1.2, hope=0.8), source weighting (personal=1.0, neighbor=0.7)
- Surprise-based encoding: unexpected events get higher importance
- Memory-mediated TP: no parametric decay equation — TP emerges from retrieved memories at decision time
- Flood memories: damage amount, emotional tag, source attribution
- No-flood memories: decreasing importance (0.3→0.2→0.15) — mimics TP decay through forgetting
- Institutional agents: window-based memory (last 3 years of metrics)

**3.5 Social Information Channels** (~300 words)
- Social network: 5 neighbors/agent, 70% same-region weighting
- Four channels: (a) Direct observation — see neighbors' adaptation status; (b) Gossip — receive reasoning behind decisions (max 2, importance threshold 0.5); (c) News media — delayed 1 year, high reliability (0.9); (d) Social media — immediate, variable reliability (0.4-0.8), exaggeration factor 0.3
- Information visibility matrix: what each agent type sees (Table in SM)

**3.6 Calibration and Validation Protocol** (~500 words)
- **Rationale**: LLM-ABMs lack established validation standards; we propose a 3-level protocol
- **Level 1 — Internal Coherence** (micro): CACR (construct-action coherence ≥ 0.80); R_H (hallucination rate ≤ 0.10)
- **Level 2 — External Validity** (macro): BRC (behavioral realism vs. empirical benchmarks ≥ 0.60); compared against NFIP uptake data, Blue Acres participation rates, post-flood adaptation surveys
- **Level 3 — Cognitive Reliability**: ICC(2,1) (test-retest reliability ≥ 0.60 across 6 archetypes × 3 vignettes × 30 reps); EBE (effective behavioral entropy — diversity × correctness)
- **→ Table 2: C&V protocol results**

**3.7 Experiment Design** (~400 words)
- Primary experiment: full-featured LLM-ABM, all modules active, 10 seeds
- Traditional ABM baseline: parametric TP decay, fixed institutions, aggregate social influence, 5 seeds
- SI ablations: (SI-1) memory engine ablation, (SI-2) fixed institutions, (SI-3) social channel toggle, (SI-4) LLM model comparison
- Analysis metrics by RQ (listed concisely; details in SM)

---

#### 4. Results (~1,200 words, 2.4 PU)

**4.1 RQ1: Memory Heterogeneity and Adaptation Pathways** (~400 words)
- Within-group TP variance emerges: traditional ABM = 0, LLM-ABM = significant (quantify)
- **→ Figure 3: Adaptation trajectory spaghetti plot** (multi-panel: traditional vs LLM-ABM, MG vs NMG)
- Experience-adaptation gap: Cox PH hazard ratio for personal flood damage
- **→ Figure 4: Survival curves** (time-to-first-adaptation by flood experience × MG status)
- Pathway entropy: Shannon entropy of adaptation sequences
- Memory salience: top-k retrieved memories at decision time predict adaptation better than demographics

**4.2 RQ2: Institutional Feedback and Protection Inequality** (~400 words)
- Government responds to damage events but with lag (subsidy-adaptation cross-correlation)
- Premium spiral: rising rates → insurance lapse → higher uninsured losses → higher rates
- **→ Figure 5: Institutional feedback dual-axis plot** (subsidy/premium rates + MG/NMG adaptation)
- Cumulative damage Gini coefficient diverges over time
- Protection gap (fraction with neither insurance nor elevation): MG gap widens despite targeted subsidies

**4.3 RQ3: Social Information and Adaptation Diffusion** (~400 words)
- Channel citation rates: gossip cited most in adaptation decisions (>50%), followed by observation
- Adaptation clustering: Moran's I significantly above random baseline, increases over time
- **→ Figure 6: Network diffusion** (4 snapshots + Moran's I + channel citation rates)
- Gossip with reasoning > observation alone: adaptation half-life is shorter when reasoning propagates
- Social media: accelerates initial response but introduces noise (lower sustained adoption)

---

#### 5. Discussion (~1,200 words, 2.4 PU)

**5.1 Emergent Individual Heterogeneity** (~250 words)
- Within-group variance is not noise — it reveals structurally important differences masked by group means
- Implications: adaptation assistance should target individuals with specific experience profiles, not demographic groups alone
- Connection to sociohydrology: human memory as a hydrological variable (Di Baldassarre et al., 2015)

**5.2 Coupled Human-Institutional Dynamics** (~250 words)
- Subsidy lag and premium spiral as emergent properties of coupled system
- Policy timing matters more than policy magnitude (connect to NFIP Risk Rating 2.0 debate)
- Blue Acres targeting: MG prioritization helps but cannot overcome structural barriers

**5.3 Information Ecology and Risk Communication** (~250 words)
- Gossip as reasoning propagation: why hearing "my neighbor elevated because she remembered the 2011 flood" is more persuasive than observing elevation
- Implications for post-disaster risk communication strategy
- Social media's dual role: speed vs. noise

**5.4 Methodological Contributions** (~200 words)
- SAGE governance as general-purpose middleware for LLM-ABMs in water resources
- 3-level C&V protocol as a template for future LLM-ABM studies
- Memory-mediated cognition as alternative to parametric behavioral equations
- Model choice justification: why local small models with governance

**5.5 Limitations and Future Work** (~250 words)
- LLM stochasticity and model sensitivity (addressed by ICC and multi-seed)
- Computational cost: 100 agents × 13 years × 10 seeds ≈ 13,000 LLM calls
- Survey-based initialization: limited to NJ flood preparedness context
- Spatial simplification: point-based agents vs. parcel-level resolution
- Future: scaling to 1000+ agents, transfer to other basins, coupling with hydrodynamic models

---

#### 6. Conclusions (~400 words, 0.8 PU)
- Restate three findings (one per RQ)
- Broader implication: LLM-governed ABMs offer a new paradigm for coupled human-water modeling that captures cognitive realism
- Call to action: the water resources community should develop shared validation standards for LLM-ABMs

---

### Back Matter

#### Acknowledgments
- Funding source (NSF grant if applicable)
- AI tools disclosure: "This study used locally deployed open-source language models (Gemma 3 4B) for agent cognition within the SAGE framework. All LLM outputs were governed by domain validation rules. The authors take full responsibility for all content."

#### Conflict of Interest
"The authors declare there are no conflicts of interest for this manuscript."

#### Open Research
- **Data Availability**: NJ flood preparedness survey data deposited in [repository]; PRB flood hazard rasters from [source]; agent simulation outputs deposited in Zenodo with DOI.
- **Software Availability**: SAGE framework code available at [GitHub URL] under MIT license; analysis scripts at [GitHub URL]; Zenodo DOI for archived version.

#### References (~40-50 references in AGU author-date style)

---

## 2. Figure Specifications

### Figure 1: Study Area and Agent Distribution
- **Type**: Map (geographic)
- **Panels**: Single panel with inset
- **Content**: PRB boundary showing 27 census tracts; FEMA flood zones (100-yr, 500-yr) as shaded polygons; agent locations as colored dots (4 colors: MG-Owner=red, MG-Renter=orange, NMG-Owner=blue, NMG-Renter=cyan); inset showing PRB location within NJ
- **Data source**: Census tract shapefiles + FEMA NFHL + agent positions from DepthSampler
- **Tool**: Python matplotlib + geopandas
- **Script**: `paper3/analysis/fig1_study_area.py`
- **Size**: Full width (190mm)

### Figure 2: SAGE Framework Architecture
- **Type**: Schematic diagram
- **Panels**: 2 panels (a, b)
  - (a) Overall architecture: LLM core → Governance layer (profile, rules) → Memory engine → Social network → Environment — showing data flows
  - (b) Annual decision cycle: 3-tier phase ordering (Government → Insurance → Households) with memory retrieval → LLM reasoning → governance validation → action execution loop
- **Tool**: Draw.io or TikZ → exported as high-res PNG/PDF
- **Script**: Manual design with `paper3/analysis/fig2_architecture.drawio` (export to PDF)
- **Size**: Full width (190mm)

### Figure 3: Adaptation Trajectory Divergence (RQ1)
- **Type**: Time series (spaghetti plot)
- **Panels**: 3 panels (a, b, c)
  - (a) Traditional ABM: MG group trajectory (single line with CI band) vs NMG group trajectory — showing zero within-group variance
  - (b) LLM-ABM MG agents: 25 individual adaptation state trajectories (thin colored lines) + group mean (thick line) — showing emergent within-group variance
  - (c) LLM-ABM NMG agents: same as (b) for NMG
  - Y-axis: cumulative adaptation score (0-1 scale: 0=no action, 0.3=insurance only, 0.6=elevation, 1.0=buyout/relocated)
  - X-axis: simulation year (1-13)
  - Color: intensity by personal flood damage experienced (light=none, dark=severe)
- **Data source**: Per-agent adaptation state time series from primary experiment (10 seeds → select representative seed, or overlay all with transparency)
- **Tool**: Python matplotlib/seaborn
- **Script**: `paper3/analysis/fig3_trajectory_spaghetti.py`
- **Key message**: Traditional ABM produces identical within-group trajectories; LLM-ABM reveals meaningful individual divergence
- **Size**: Full width (190mm), tall (~150mm)

### Figure 4: Experience-Adaptation Survival Curves (RQ1)
- **Type**: Kaplan-Meier survival curves
- **Panels**: 2 panels (a, b)
  - (a) Time-to-first-adaptation by personal flood damage quartile (4 curves: Q1-Q4, pooled across all agents)
  - (b) Same stratified by MG × flood experience (4 curves: MG-flooded, MG-not-flooded, NMG-flooded, NMG-not-flooded)
  - X-axis: simulation year
  - Y-axis: fraction of agents who have NOT yet adopted any adaptation (survival probability)
  - Include: 95% CI bands from 10-seed bootstrap, log-rank test p-values, Cox PH hazard ratio annotations
- **Data source**: Per-agent time-to-first-adaptation events
- **Tool**: Python lifelines library
- **Script**: `paper3/analysis/fig4_survival_curves.py`
- **Key message**: Personal flood experience is a stronger predictor of adaptation timing than demographic group; the experience-adaptation gap is wider for MG agents
- **Size**: Full width (190mm)

### Figure 5: Institutional Feedback and Protection Inequality (RQ2)
- **Type**: Dual-axis time series
- **Panels**: 2 panels stacked vertically (a, b), shared x-axis
  - (a) Top panel — Institutional policy rates:
    - Left y-axis: Government subsidy rate (%, blue line)
    - Right y-axis: Insurance premium rate (%, red line)
    - Vertical dashed lines at flood event years (annotated with depth)
    - Shaded regions: subsidy increase periods (light blue) and premium increase periods (light red)
  - (b) Bottom panel — Household adaptation & inequality:
    - Left y-axis: Adaptation rate by group (MG solid, NMG dashed) — fraction with any protection
    - Right y-axis: Protection gap (MG fraction unprotected − NMG fraction unprotected) as bar chart
    - Annotated: cumulative damage Gini coefficient at years 5, 9, 13
- **Data source**: Per-year institutional decisions + per-agent adaptation states + cumulative OOP damages
- **Tool**: Python matplotlib with twin axes
- **Script**: `paper3/analysis/fig5_institutional_feedback.py`
- **Key message**: Government responds to floods with subsidy increases, but with temporal lag; insurance premium increases push marginal households out; protection gap widens despite targeted policy
- **Size**: Full width (190mm), tall (~140mm)

### Figure 6: Social Information and Adaptation Diffusion (RQ3)
- **Type**: Composite (network + line + bar)
- **Panels**: 3 rows
  - Row 1 (a-d): Network snapshots at years 1, 5, 9, 13
    - Nodes: colored by adaptation state (gray=none, yellow=insured, green=elevated, blue=buyout)
    - Node size: by personal flood experience intensity
    - Edges: thin gray for social links; thick colored for active gossip flows
    - Layout: spring layout preserving spatial relationships
  - Row 2 (e): Moran's I spatial autocorrelation coefficient over time
    - Expected random baseline (dashed), observed (solid with CI from 10 seeds)
    - Annotated with significance stars
  - Row 3 (f): Stacked bar chart of information channel citation rates
    - Bars for each year, stacked by channel: observation, gossip, news media, social media
    - Only for agents who made an adaptation decision that year
- **Data source**: Social network graph + per-agent adaptation states + reasoning text analysis (regex for channel keywords) + Moran's I computation
- **Tool**: Python networkx + matplotlib
- **Script**: `paper3/analysis/fig6_network_diffusion.py`
- **Key message**: Adaptation clusters on the network over time; gossip with reasoning propagation is the dominant information channel for adaptation decisions
- **Size**: Full width (190mm), tall (~180mm)

---

## 3. Table Specifications

### Table 1: Agent Configuration and Experiment Design
| Column | Content |
|--------|---------|
| Agent type | household_owner, household_renter, nj_government, fema_nfip |
| N | 25, 25, 1, 1 (by cell: 25 MG-Own, 25 MG-Rent, 25 NMG-Own, 25 NMG-Rent) |
| MG status | MG / NMG |
| Tenure | Owner / Renter |
| Flood-prone % | 70% (MG), 50% (NMG) |
| RCV range | Homeowner: $230K-$430K; Renter: contents $15K-$80K |
| Memory engine | HumanCentric (households), Window (institutions) |
| Skills | buy_insurance, elevate, buyout, relocate, do_nothing (varies by type) |
| Social network | 5 neighbors, 70% same-region |

### Table 2: Calibration and Validation Results
| Metric | Level | Threshold | Primary Result | SI-1 (Window Memory) | SI-2 (Fixed Institutions) | SI-3 (No Gossip) |
|--------|-------|-----------|----------------|----------------------|---------------------------|-------------------|
| CACR | L1 | ≥ 0.80 | [result] | [result] | [result] | [result] |
| R_H | L1 | ≤ 0.10 | [result] | [result] | [result] | [result] |
| BRC | L2 | ≥ 0.60 | [result] | [result] | [result] | [result] |
| ICC(2,1) | L3 | ≥ 0.60 | [result] | [result] | [result] | [result] |
| EBE | L3 | descriptive | [result] | [result] | [result] | [result] |

### Table 3: Summary of Key Findings by Research Question
| RQ | Primary Metric | Value | Interpretation |
|----|---------------|-------|----------------|
| RQ1 | Within-group TP variance (MG) | [σ²] | [x]-fold greater than traditional ABM |
| RQ1 | Cox PH hazard ratio (flood exp.) | [HR] | Flooded agents adapt [x]× faster |
| RQ2 | Subsidy-adaptation lag | [years] | Policy response trails damage by [n] years |
| RQ2 | Cumulative damage Gini (year 13) | [G] | Inequality [increased/decreased] over time |
| RQ3 | Gossip citation rate | [%] | Dominant channel for adaptation decisions |
| RQ3 | Moran's I (year 13) | [I] | Significant clustering (p < 0.01) |

---

## 4. Supplementary Materials Plan

All SM combined into **one PDF file** (AGU requirement). No data/software in SM (those go to Zenodo).

### SM-A: ODD+D Protocol (~15 pages)
Full ODD+D documentation following Müller et al. (2013):
- A1. Purpose and patterns
- A2. Entities, state variables, and scales
- A3. Process overview and scheduling
- A4. Design concepts (emergence, adaptation, objectives, learning, prediction, sensing, interaction, stochasticity, collectives, observation)
- A5. Initialization
- A6. Input data
- A7. Submodels
- **A7-D. Decision-making extension** (detailed PMT + LLM + governance description)

### SM-B: Prompt Templates (~5 pages)
- B1. Household owner prompt template (full text with {placeholders})
- B2. Household renter prompt template
- B3. Government agent prompt template
- B4. Insurance agent prompt template
- B5. Response format specification and governance rules

### SM-C: Agent Reasoning Trace Examples (~8 pages)
- C1. RQ1 examples: 3 agent reasoning traces showing memory-driven TP divergence
  - Agent with personal flood memory → high TP → elevate
  - Agent without flood memory → low TP → do nothing
  - Same demographics, different trajectories
- C2. RQ2 examples: 2 institutional reasoning traces
  - Government responding to high MG damage
  - Insurance raising premium after high loss ratio
- C3. RQ3 examples: 3 reasoning traces showing social information influence
  - Gossip-influenced decision (citing neighbor's reasoning)
  - News media-influenced decision
  - Social media-influenced decision (with noise)

### SM-D: Full C&V Results (~6 pages)
- D1. CACR detailed breakdown by construct pair (TP-action, CP-action, etc.)
- D2. R_H breakdown by hallucination type (re-elevation, post-relocation, thinking violation)
- D3. BRC comparison against each empirical benchmark
- D4. ICC per-archetype and per-vignette results (6 × 3 matrix)
- D5. EBE entropy decomposition
- D6. Per-seed C&V results (10 seeds)

### SM-E: Sensitivity and Ablation Analysis (~10 pages)
- E1. SI-1: Memory engine ablation (window vs. humancentric)
  - Figure S1: Within-group variance comparison
  - Table S1: C&V metrics comparison
- E2. SI-2: Fixed institutions (exogenous subsidy/premium)
  - Figure S2: Protection gap with vs. without institutional feedback
  - Table S2: Cumulative damage comparison
- E3. SI-3: Social channel ablation (toggle gossip/news/social media)
  - Figure S3: Adaptation clustering (Moran's I) by channel configuration
  - Table S3: Channel citation rates across ablations
- E4. SI-4: LLM model comparison (Gemma 3 4B vs. 12B vs. Mistral)
  - Figure S4: C&V metrics by model
  - Table S4: Decision distribution by model
- E5. SI-5: Seed robustness
  - Figure S5: Key metrics with 95% CI across 10 seeds
- E6. SI-6: Governance validation (what happens without governance)
  - Figure S6: CACR and R_H with vs. without governance

### SM-F: Memory Architecture Details (~4 pages)
- F1. Importance decay function (plot of importance vs. time for different emotional tags)
- F2. Emotional weighting scheme (fear, hope, anxiety, relief weights with rationale)
- F3. Source weighting scheme (personal, neighbor, media, social media weights)
- F4. Surprise-based encoding formula and examples
- F5. Memory retrieval algorithm (stratified retrieval with contextual boosters)

### SM-G: Social Network and Information Channels (~3 pages)
- G1. Network generation algorithm (preferential attachment with spatial weighting)
- G2. Degree distribution and clustering coefficient
- G3. Gossip propagation rules (importance threshold, max gossip per step, reasoning extraction)
- G4. News media generation rules (delay, reliability, aggregation method)
- G5. Social media generation rules (immediacy, reliability function, exaggeration model)

### SM-H: Financial Model Parameters (~3 pages)
- H1. Elevation cost model (per-foot estimates by foundation type)
- H2. Insurance premium calculation (RCV-based with CRS discount, flood zone adjustment)
- H3. Blue Acres buyout offer calculation (75% of pre-flood RCV)
- H4. Damage calculation (depth-damage functions for building and contents)
- H5. Coverage limits and deductible structure

### SM-I: Additional Figures (~5 pages)
- Figure S7: Per-agent construct trajectories (TP, CP, SP, SC, PA) for 6 representative agents
- Figure S8: Cumulative OOP damage distribution at year 13 (histogram, MG vs NMG)
- Figure S9: Pathway entropy time series (Shannon entropy of adaptation state sequences)
- Figure S10: Cross-correlation matrix (subsidy rate change × MG adaptation uptake lag)
- Figure S11: Premium-dropout scatter (P(insurance lapse) vs. premium change × income)
- Figure S12: Social contagion half-life by channel configuration

---

## 5. Analysis Scripts Required

| Script | Figure/Table | Dependencies | Priority |
|--------|-------------|-------------|----------|
| `fig1_study_area.py` | Figure 1 | geopandas, census shapefiles, FEMA NFHL | Medium |
| `fig2_architecture.drawio` | Figure 2 | Draw.io (manual) | Low |
| `fig3_trajectory_spaghetti.py` | Figure 3 | matplotlib, experiment results | High |
| `fig4_survival_curves.py` | Figure 4 | lifelines, experiment results | High |
| `fig5_institutional_feedback.py` | Figure 5 | matplotlib, experiment results | High |
| `fig6_network_diffusion.py` | Figure 6 | networkx, matplotlib, experiment results | High |
| `table1_agent_config.py` | Table 1 | config YAML | Low |
| `table2_cv_results.py` | Table 2 | C&V runner output | High |
| `table3_summary_findings.py` | Table 3 | all analysis results | High |
| `si_ablation_analysis.py` | SM-E all | experiment results | Medium |
| `si_memory_details.py` | SM-F figures | memory engine logs | Medium |
| `si_network_stats.py` | SM-G figures | social network data | Low |

---

## 6. Reference Strategy

### Core references (~40-50 total, AGU author-date style)

**PMT & Behavior** (~8):
- Rogers (1983) — PMT original theory
- Grothmann & Reusswig (2006) — PMT for natural hazards
- Bamberg et al. (2017) — meta-analysis of PMT in flood context
- Bubeck et al. (2012) — review of flood risk perceptions
- Siegrist & Gutscher (2008) — flood experience and risk perception

**Flood ABM** (~8):
- Haer et al. (2017) — PMT-based flood ABM
- de Ruig et al. (2022) — ABM for flood risk adaptation NYC
- Michaelis et al. (2020) — ABM flood insurance
- An (2012) — modeling human decisions in coupled systems
- Schlüter et al. (2017) — call for cognitive agents

**LLM Agents** (~6):
- Park et al. (2023) — Generative Agents (Stanford)
- Huang et al. (2025) — Nature Machine Intelligence LLM agents survey
- Chopra et al. (2024) — AgentTorch
- Gao et al. (2024) — LLM-based social simulation

**Memory & Cognition** (~4):
- Ebbinghaus (1885/1913) — forgetting curve
- Kahneman (2011) — dual-process / availability heuristic
- Di Baldassarre et al. (2015) — sociohydrology and memory of floods
- McEwen et al. (2017) — flood memory and community resilience

**NFIP & Policy** (~6):
- Kousky (2017) — NFIP economics review
- Gallagher (2014) — learning and insurance behavior
- Choi et al. (2024) — NJ flood survey (our data source)
- Atreya et al. (2013) — flood risk capitalization
- FEMA Risk Rating 2.0 documentation

**Social Influence** (~4):
- Bandura (1977) — social learning theory
- Centola & Macy (2007) — complex contagion
- Holley et al. (2022) — social networks in flood response
- Hudson et al. (2020) — social influence on flood preparedness

**Methods / Validation** (~6):
- Grimm et al. (2020) — ODD+D protocol
- Müller et al. (2013) — ODD+D decision extension
- Shrout & Fleiss (1979) — ICC
- Shannon (1948) — information entropy
- Moran (1950) — spatial autocorrelation

---

## 7. Writing Sequence

### Phase F-1: Draft skeleton (current)
Generate Word document with all section headings, Key Points, Abstract, and PLS drafted. Methods sections written in detail (these are stable — they describe what we built, not what we found).

### Phase F-2: Post-experiment writing
After Phase E experiments complete:
- Write Results section with actual numbers
- Generate all 6 main figures + 3 tables
- Write Discussion connecting findings to literature
- Write Conclusions

### Phase F-3: SM writing
- Generate ODD+D protocol
- Extract reasoning traces from experiment logs
- Generate SM figures and tables
- Compile into single PDF

### Phase F-4: Polish and review
- Internal coherence check
- Citation verification (all cited ↔ reference list)
- PU count verification (≤ 25)
- Key Points accuracy check
- AI tools disclosure
- Code-reviewer agent for analysis scripts
