# Nature Water — Methods (v4 — reservoir model, flood hazard, stochastic PMT caveat, CRSS simplification)
## Date: 2026-02-17 | Not counted in main text word limit

---

## Methods

### Broker Architecture and Governance Pipeline

The Water Agent Governance Framework implements a three-layer architecture: an LLM agent layer, a governance broker, and a simulation engine. At each decision step, the context builder assembles a tiered, read-only signal package for the agent — personal state variables, social observations from network neighbours, and system-level information (drought indices, flood forecasts, institutional announcements) — bounded to what the agent's role and location would permit access to. The agent produces a structured JSON output comprising a proposed skill (action), natural-language reasoning, and psychological construct labels where applicable. The governance broker then evaluates this proposal through a six-step validation pipeline:

1. **Schema validation**: Confirms the output conforms to the required JSON structure.
2. **Skill legality**: Verifies the proposed action belongs to the agent's type-specific skill registry.
3. **Physical feasibility**: Checks mass balance, capacity limits, and domain-specific physical constraints.
4. **Institutional compliance**: Validates against policy rules (prior-appropriation doctrine, programme eligibility).
5. **Magnitude plausibility**: Assesses whether proposed changes fall within empirically calibrated bounds (e.g., year-over-year demand shifts within +/-15%).
6. **Theory consistency**: For domains with explicit behavioural theory framing (e.g., Protection Motivation Theory), verifies alignment between stated reasoning constructs and the proposed action.

When a proposal fails validation, the broker returns a structured explanation identifying the violated rule. The agent receives this feedback and may revise its proposal. A retry manager governs this loop (max 3 retries): if the same rule blocks consecutive attempts, an early-exit mechanism terminates the cycle to prevent futile LLM calls. Upon early exit, a domain-appropriate default action (typically "do nothing") executes, ensuring simulation advancement. Failed proposals, revision attempts, and governance explanations are recorded in JSONL audit traces for post-hoc analysis.

The broker core is fixed code requiring no modification across domains. All domain-specific knowledge is expressed through declarative configuration files:
- **Skill registries** (YAML): Define the action vocabulary per agent type.
- **Agent-type specifications** (YAML): Map state variables, decision attributes, and governance rule bindings.
- **Persona prompts** (natural language): Establish cognitive framing, institutional context, and behavioural theory orientation per agent type.
- **Governance rules** (YAML): Specify validator stacks, thresholds, and severity levels (WARNING vs. ERROR).

### LLM Configuration and Inference

All experiments used locally hosted open-weight models via Ollama, a local inference platform for open-weight language models. The primary model was Gemma-3 4B (Google, 2025; Ollama tag gemma3:4b); cross-scale comparisons included Gemma-3 12B (gemma3:12b) and 27B (gemma3:27b), and Ministral 3B (ministral:3b), 8B (ministral:8b), and 14B (ministral:14b). Temperature was set to 0.8 with top_p = 0.9 (nucleus sampling threshold) and context window of 8,192 tokens. The temperature value follows common practice in generative agent studies (Park et al., 2023); no temperature sensitivity analysis was conducted, and we note that a nominal temperature of 0.8 may produce different entropy characteristics across architectures. Structured output was enforced through delimiter-bounded JSON response formats with smart repair preprocessing — a rule-based procedure that fixes common JSON formatting errors (missing closing braces, unescaped characters, truncated fields) before parsing. Fixed random seeds (reported per domain below) ensured reproducibility across runs. No fine-tuning or reinforcement learning from human feedback was applied; all behavioural shaping occurred through prompt design and governance constraints. Full persona prompt templates and governance rule specifications (YAML) are provided in the Supplementary Information.

### Irrigation Domain Setup

The irrigation application represents 78 agents corresponding to Colorado River Simulation System (CRSS) demand nodes across the Upper and Lower Colorado River Basin. Each agent manages a continuous water-allocation decision over a 42-year horizon (simulating conditions from 1981 to 2022). Agent reasoning follows a dual-appraisal framework — Water Shortage Appraisal (WSA) and Adaptive Capacity Appraisal (ACA) — derived from fuzzy-quantitative-linguistic persona heuristics that extend the institutional decision logic of Hung and Yang (2021). Agents are characterized by seniority (priority date), storage access, historical demand flexibility, and basin membership (Upper vs. Lower). Five skills define the action vocabulary: increase demand (large or small), decrease demand (large or small), and maintain demand. Each skill triggers bounded Gaussian magnitude sampling (mean from persona heuristics, sigma from cluster parameters) clamped to [0, water_right], ensuring physical feasibility independent of governance. Twelve validators enforce constraints: 7 physical (mass balance, capacity limits, rate-of-change bounds), 1 institutional (demand ceiling stabilizer, linking individual proposals to aggregate basin state — the rule tested in the A1 ablation), 2 social (seniority compliance, basin-level coordination), 1 temporal (seasonal plausibility), and 1 behavioural (WSA-ACA construct-action alignment).

To isolate the governance contribution, we conducted a two-condition ablation:
- **Governed**: Full governance pipeline (12 validators, WARNING and ERROR severity levels, retry loop with early exit). WARNING-level violations issue feedback but allow execution; ERROR-level violations block the proposal and trigger retries (max 3).
- **Ungoverned**: Identical agent personas, environment, and magnitude sampling, but with governance disabled (no validators, no retry loop). The LLM freely selects any skill; physical bounds are maintained solely through the code-level clamp in the simulation engine.

A third condition tested targeted ablation:
- **A1 (No demand ceiling)**: Full governance pipeline minus the `demand_ceiling_stabilizer`, which blocks demand-increase proposals when aggregate basin demand exceeds 6.0 MAF. Removing this single rule isolates whether the diversity effect requires the specific constraint that links individual decisions to aggregate basin state, while retaining all 11 other validators.

Each condition was run with 3 replicate seeds (42, 43, 44) for a total of 9 irrigation runs. Because magnitude is code-generated in all conditions, the ablation cleanly isolates the governance effect on skill selection quality.

### Reservoir Simulation

Agent decisions drive Lake Mead through an endogenous mass-balance model. At each annual timestep, the simulation computes:

Storage(t+1) = Storage(t) + Inflows(t) − ΣWithdrawals(t) − Evaporation(t) − Downstream(t)

where Inflows comprise natural flow at Lee Ferry (base 12.0 MAF/yr, scaled by Upper Basin precipitation from historical CRSS traces for 1981–2022, clamped to [6, 17] MAF) plus Lower Basin tributaries (1.0 MAF/yr fixed); Withdrawals are the sum of all 78 agents' fulfilled diversions from the previous year (simultaneous update: all agents observe the same Mead state at the start of each year, make decisions, and withdrawals affect Mead at the start of the following year); Evaporation is elevation-dependent (0.6–0.8 MAF/yr); and Downstream includes Mexico Treaty deliveries (1.5 MAF/yr) and non-agricultural municipal demand (1.2 MAF/yr). Storage-to-elevation conversion uses a USBR-derived lookup table interpolated across 10 control points (895–1,220 ft). Storage changes are clamped to ±3.5 MAF/yr to prevent numerical instabilities.

Shortage tiers activate at elevation thresholds following the 2007 Interim Guidelines: Tier 1 at 1,075 ft (5% curtailment), Tier 2 at 1,050 ft (10%), Tier 3 at 1,025 ft (20%). Curtailment reduces all agents' fulfilled diversions pro rata. Upper Basin diversions are additionally constrained by a minimum Powell release of 7.0 MAF/yr and infrastructure capacity of 5.0 MAF/yr, with pro-rata reduction when aggregate Upper Basin demand exceeds the effective cap.

The demand ceiling stabilizer — a governance rule tested in the ablation analysis — blocks demand-increase proposals when total basin demand exceeds 6.0 MAF. This operates at the governance layer (pre-execution), distinct from the code-level clamp that bounds fulfilled diversions post-execution.

Our simulation uses a simplified single-reservoir representation of the CRSS system; the full Bureau of Reclamation CRSS includes 12 reservoirs, hydropower constraints, and operational rules not represented here. Results should be interpreted as stylized institutional dynamics, not predictive water-supply forecasts.

### Flood Domain Setup

The flood-adaptation application models 100 household agents making protective decisions over 10 simulated years. Agents are initialized from census-tract demographic profiles with heterogeneous attributes: flood zone (HIGH, MODERATE, LOW), income level, tenure type (owner vs renter), and prior adaptation state (none, insured, elevated). Flood events occur stochastically with annual probability 0.2; when a flood occurs, agents experience inundation depths drawn from zone-specific log-normal distributions (HIGH zone: μ=1.2 ft, σ=0.8; MODERATE: μ=0.4, σ=0.5; LOW: μ=0.1, σ=0.3), with spatial correlation within zones but independence across zones. Agent reasoning follows Protection Motivation Theory (Rogers, 1983): threat appraisal (perceived probability x severity) combines with coping appraisal (response efficacy x self-efficacy - response cost) to motivate action selection. Four skills are available: purchase flood insurance, elevate home, relocate, or do nothing. The elevation skill is permanently blocked once completed.

The experiment uses a three-group factorial design:
- **Group A (Ungoverned)**: LLM with window memory and governance validation disabled — establishes the baseline behavioural quality. Critically, Group A agents receive identical prompt templates, PMT-based response format requirements, and environmental context signals as Groups B and C; the only difference is that proposed decisions bypass governance validation and execute directly.
- **Group B (Governed)**: LLM with window memory (5-year window) and full governance validation — isolates the governance effect.
- **Group C (Governed + HumanCentric Memory)**: LLM with surprise-weighted, arousal-gated memory featuring stochastic consolidation and exponential decay, plus full governance validation — tests whether cognitively inspired memory improves native alignment. Group C results did not substantively differ from Group B and are omitted; main-text comparisons use Groups A and B only.

Governance rules include: blocking relocation when threat appraisal is low (ERROR level), blocking do-nothing when threat is high (ERROR level), and preventing re-elevation of already-elevated homes. Each group was run with 3 replicate seeds (43, 44, 45) for a total of 9 runs per model scale.

**Strategy diversity metric.** For both domains, strategy diversity is measured from each agent's annual action selection — the decision variable submitted in each yearly round — rather than from cumulative protection states. This ensures methodological consistency: irrigation diversity reflects yearly allocation choices among five actions; flood diversity reflects yearly protective-action choices among four actions (purchase insurance, elevate home, relocate, or do nothing). Elevation is a permanent one-time action; insurance must be actively renewed each year, creating a tradeoff in which choosing elevation implicitly forgoes insurance renewal. The annual-decision metric captures these tradeoffs, whereas cumulative protection states (e.g., an agent who has both insurance and elevation) conflate current-year choices with historical decisions.

### Rule-Based PMT Agent

To benchmark language-based agents against the traditional ABM approach, we implemented a deterministic rule-based agent using Protection Motivation Theory. This agent computes threat appraisal (TA) from flood zone and prior flood experience and coping appraisal (CA) from income, insurance status, and adaptation state. Action selection follows threshold logic: if CA > tau_CA and TA > tau_TA, the agent selects elevation; if CA > tau_CA, insurance; if TA > tau_TA and CA <= tau_CA, do nothing (insufficient coping); otherwise do nothing. Thresholds tau_CA and tau_TA are calibrated to empirical PMT survey data (Bubeck et al., 2012). The rule-based agent uses the same 100 agent profiles, 10-year horizon, stochastic flood events, and evaluation protocol as the LLM-based experiments. Three independent runs with different random seeds were conducted. Unlike language agents (which select one action per year), the rule-based agent can simultaneously recommend insurance and elevation when both TA and CA exceed thresholds (42.8% of raw decisions). These composite recommendations are split into constituent single-action decisions for EHE computation. The rule-based agent is deterministic; a stochastic variant (adding noise to threshold comparisons or probabilistic action selection) would yield higher baseline diversity, making this comparison conservative. This comparison isolates the representational contribution of language-based reasoning: both approaches use PMT as the behavioural theory, but the rule-based agent maps numerical scores to actions through fixed thresholds, while the language agent reasons through natural language within governance boundaries.

### Validation Protocol

We adopted a multi-level validation protocol informed by pattern-oriented modelling principles (Grimm et al., 2005).

**Level 1 — Micro-behavioural coherence.** The Irrational Behavioural Ratio (IBR) quantifies the percentage of agent decisions that violate the predictions of the domain's behavioural theory. For the flood domain, IBR captures PMT violations (e.g., relocating under low-threat conditions). For the irrigation domain, IBR decomposes into three rule sets: (A) physical impossibilities — proposing demand increases at the water-right cap, below minimum utilisation, during supply gaps (fulfilment < 70%), or during Tier 2+ mandatory curtailment; (B) dual-appraisal incoherence — mismatches between the agent's self-assessed WSA/ACA labels and its proposed action, evaluated against a 25-cell coherence matrix mapping each (WSA, ACA) combination to its theoretically rational skill set; and (C) temporal violations — four or more consecutive demand increases during drought (drought index >= 0.7). The Construct-Action Coherence Rate (CACR = 1 - IBR_coherence) provides a direct analog to the flood domain's PMT coherence metric. Both metrics are computed per agent per decision step and aggregated across the simulation.

**Level 2 — Population-level patterns.** Effective Heterogeneity Entropy (EHE) measures strategy diversity as normalized Shannon entropy: EHE = H / log_2(k), where k is the number of actions in the agent's designed decision interface (k = 4 for flood, k = 5 for irrigation). Cognitive lifespan T_life is defined as the number of simulated years during which EHE > 0.4, capturing when a population collapses into repetitive behaviour. For irrigation, aggregate demand ratio against CRSS baseline serves as the primary population-level calibration target.

**Level 3 — Cross-scale comparison.** To assess whether governance compensates for model scale, we compare governed 4B agents against ungoverned agents at 12B and 27B scales using Mann-Whitney U tests, Cohen's d effect sizes, and bootstrap confidence intervals on EHE differences.

### Statistical Analysis

Ensemble analyses used 3 replicate runs per configuration with fixed random seeds. We acknowledge that n = 3 per condition limits formal inferential power: Mann-Whitney U tests with n_1 = n_2 = 3 have a minimum achievable two-tailed p-value of 0.05, and bootstrap confidence intervals from 3 observations yield limited resolution. We therefore report primarily descriptive statistics (means, ranges, and EHE values per seed) and treat ensemble runs as providing robustness checks rather than formal hypothesis tests. Where reported, effect sizes use Cohen's d with the caveat that confidence intervals are wide at this sample size. For agent-level analyses, we computed chi-squared tests on aggregate skill distributions pooled across seeds, which provide adequate power given the large number of agent-decisions per condition (e.g., 100 agents x 10 years x 3 seeds = 3,000 agent-decisions for flood). To decompose the governance contribution, we computed CACR on proposed skills (pre-governance) and final skills (post-governance), yielding a governance value-add metric. All analyses were conducted in Python 3.11 using NumPy, SciPy, and pandas.

---

## Changes from v2
- **NEW section**: "Rule-Based PMT Agent" — describes hand-coded baseline, threshold logic, composite handling, and comparison rationale
- **Clarification**: S4 normalization now cross-referenced from rule-based section
- Minor formatting consistency (Unicode symbols replaced for docx compatibility)
