# Expert Terminology Review — Nature Water Paper v14

**Panel**: 3 water resource domain experts (hydrology, flood management, institutional water governance)
**Date**: 2026-02-24
**Scope**: All main text drafts, SI, figure scripts, and compile script

---

## 1. ERRORS — Wrong or Misleading Terminology (Must Fix)

### E1. "Lake Mead elevation" used where "Lake Mead water surface elevation" or simply "Lake Mead level" would be standard
- **Files**: `section2_v11_results.md` (lines 12, 26), `methods_v3.md` (line 50), `gen_fig2_irrigation.py` (line 284), `compile_paper.py` (line 406)
- **Issue**: In Bureau of Reclamation and Colorado River operations literature, "elevation" alone is ambiguous — it could refer to dam crest, spillway, or surface level. The standard USBR term is "water surface elevation" or simply "pool elevation." However, Nature Water reviewers would likely understand "Lake Mead elevation" from context, and the 2007 Interim Guidelines themselves use "elevation" shorthand. **Low severity** — acceptable in this context but adding "pool" or "water surface" on first use would improve precision.
- **Recommendation**: On first mention (abstract or R1 opening), write "Lake Mead pool elevation" or "Lake Mead water-surface elevation"; thereafter "Mead elevation" is fine.

### E2. "Shortage years" vs. "shortage-threshold crossings" inconsistency in Table 1 vs. SI
- **Files**: `section2_v11_results.md` Table 1 header says "Shortage years (/42)"; `supplementary_information.md` Table 6 says "Shortage-threshold crossings (of 42 yr)"
- **Issue**: These refer to the same metric. "Shortage years" is the colloquial Colorado River term; "shortage-threshold crossings" sounds like it counts individual crossing events (each time the level dips below a threshold), not the number of years in shortage. In USBR parlance, a "shortage declaration" or "shortage condition" applies for a full operating year.
- **Fix**: Use "Shortage years (/42)" consistently in both locations. If counting threshold crossings (entering and exiting), that is a different metric entirely and should be clarified.

### E3. "Curtailment spread" is not a standard water resources term
- **Files**: `supplementary_information.md` Table 6 and note
- **Issue**: "Curtailment spread" (defined as plentiful-year DR minus shortage-year DR) is a custom metric. A Nature Water reviewer would not recognize it. The concept is closer to "demand elasticity with respect to shortage" or "demand responsiveness."
- **Recommendation**: Replace with "demand responsiveness (plentiful-year demand ratio minus shortage-year demand ratio)" or define explicitly on first use. Currently it is defined in the table note, which is adequate for SI, but the name itself is misleading — "curtailment" implies mandatory supply reduction, whereas this metric captures voluntary demand adjustment.

### E4. "Demand ratio" definition needs careful framing
- **Files**: abstract, results, methods, figure scripts
- **Issue**: "Demand ratio = requested volume / historical baseline allocation" (Table 1 note). In Colorado River operations, "demand" typically refers to consumptive use or diversion request. Dividing by "historical baseline allocation" creates a normalized index, but this is not a standard USBR metric. The paper should clarify that this is a simulation-specific metric, not a USBR operational term.
- **Current state**: The Table 1 note does define it. The abstract uses "demand ratio 0.394 versus 0.288" without definition. A Nature Water reviewer reading only the abstract might assume this is a standard ratio.
- **Recommendation**: In the abstract, consider "normalized demand ratio" or "(demand ratio, the fraction of baseline water entitlements requested)" on first use.

### E5. "Pro rata" curtailment described but not consistent with prior appropriation
- **Files**: `methods_v3.md` line 52 — "Curtailment reduces all agents' fulfilled diversions pro rata."
- **Issue**: Under prior appropriation doctrine, curtailment is NOT pro rata — it follows seniority (junior rights curtailed first). Pro-rata sharing is characteristic of riparian doctrine or some interstate compact provisions. The 2007 Interim Guidelines do impose volumetric reductions by tier (5%, 10%, 20%), which apply to Lower Basin states but are NOT strictly pro rata across all users.
- **Severity**: HIGH. A water law reviewer would flag this immediately.
- **Fix**: Clarify that the simulation uses simplified tier-based percentage reductions applied uniformly (which is acknowledged as a simplification), not true prior-appropriation priority-based curtailment. The sentence should read something like: "Shortage tiers reduce all agents' fulfilled diversions by the tier percentage, a simplification of the seniority-based curtailment sequence used in actual Colorado River operations."

### E6. "Prior-appropriation operating rules" conflated with shortage-sharing rules
- **Files**: `introduction_v10.md` line 14 — "Hung and Yang (2021) encoded prior-appropriation operating rules (the seniority-based water rights system governing western US rivers)"
- **Issue**: The parenthetical is correct, but calling them "operating rules" is slightly imprecise. Prior appropriation is a legal doctrine; what Hung & Yang encoded were operational rules derived from that doctrine (e.g., curtailment order). "Prior-appropriation allocation rules" or "prior-appropriation-based operating rules" would be more precise.
- **Severity**: Minor. The parenthetical clarification saves it.

---

## 2. INCONSISTENCIES — Same Concept, Different Terms

### I1. "Strategy diversity" vs. "EHE" vs. "behavioural diversity" vs. "normalized Shannon entropy"
- **Files**: Main text consistently uses "strategy diversity" (good). But `gen_fig2_irrigation.py` uses variable name `ehe` and function `compute_ehe_per_seed()` (lines 170-206). The y-axis label says "Strategy diversity" (line 389), which is correct for the figure output.
- **Impact**: Code-internal variable names do not affect the paper, but if anyone inspects the code (reproducibility), "EHE" is unexplained. The SI defines the metric well.
- **Recommendation**: No change needed in paper text. Consider renaming `ehe` to `sd` or `strategy_diversity` in the code for consistency with the paper's terminology.

### I2. "IBR" vs. "BRI" vs. "Irrational Behaviour Rate" vs. "Behavioural Rationality Index"
- **Files**: Methods defines both; Results uses BRI for irrigation and IBR for flood. Abstract mentions neither by name. SI uses R_H.
- **Issue**: Three names for closely related metrics is confusing. The Methods paragraph (line 79) explains the relationship: "BRI approximates 1 - IBR but uses a domain-specific definition." This is adequate but the reader must track IBR, BRI, R_H, and CACR across the paper.
- **Recommendation**: Consider a consolidated table in the Methods or SI listing all acronyms with their domain, definition, and relationship. Nature Water readers expect clarity; four related acronyms for behavioral rationality measures is a lot.

### I3. "Demand ceiling stabilizer" vs. "demand ceiling" vs. "demand-ceiling stabilizer"
- **Files**: Results uses "demand ceiling stabilizer" (line 34), "demand ceiling" (line 36), and "demand-ceiling stabilizer" in discussion. Methods uses "demand_ceiling_stabilizer" (code name) and "demand ceiling stabilizer" (prose).
- **Recommendation**: Pick one: "demand ceiling" for the rule concept in prose, "demand-ceiling stabilizer" (hyphenated) for the specific validator. Currently acceptable but minor inconsistency.

### I4. "Feasibility boundaries" vs. "institutional boundaries" vs. "governance boundaries"
- **Files**: Abstract uses "feasibility boundaries"; Introduction uses "institutional boundaries"; Discussion uses both.
- **Issue**: These may be intentionally distinct (feasibility = physical constraints; institutional = social/legal rules), but the paper uses them somewhat interchangeably. A water governance reviewer would read "institutional boundaries" as Ostrom-derived and "feasibility boundaries" as engineering-derived.
- **Recommendation**: Define on first use and use consistently, or acknowledge that feasibility boundaries encompass both physical and institutional constraints.

### I5. "Flood zone" classification inconsistency
- **Files**: Methods says "flood zone (HIGH, MODERATE, LOW)" — all caps. SI Note 7 mentions "zone-specific log-normal distributions." Table 2 note does not specify zones.
- **Issue**: FEMA uses specific flood zone designations (A, AE, V, X, etc.). The paper's HIGH/MODERATE/LOW is a simulation simplification, which is fine but should be explicitly noted as such. If a reviewer asks "which FEMA zones?", the paper should be prepared.
- **Recommendation**: Add a parenthetical: "flood zone (HIGH, MODERATE, LOW — a simplified representation of FEMA Special Flood Hazard Areas)."

### I6. "Protection Motivation Theory" capitalization and abbreviation
- **Files**: Consistently capitalized and abbreviated as "PMT" — good. But Introduction (line 14) says "Protection Motivation Theory" with capitals, while Methods (line 60) says it again. The abbreviation is never formally introduced with "(PMT)" in the main text body.
- **Recommendation**: Introduce as "Protection Motivation Theory (PMT; Rogers, 1983)" on first use in the Introduction, then use "PMT" thereafter.

---

## 3. CS JARGON LEAKS — Terms a Water Reviewer Would Not Recognize

### J1. "Skill" / "skill registry" / "skill selection"
- **Files**: Throughout — results, methods, tables, figure scripts
- **Issue**: "Skill" is software engineering / agent-framework jargon. Water resource modellers use "action," "strategy," "decision option," or "management alternative." The paper does use "action" in places (Table 2 note: "action share"), creating a dual vocabulary.
- **Severity**: MEDIUM. Appears 30+ times. A Nature Water reviewer would find "skill" jarring. The term appears in Table 1 labels, figure axes, and running text.
- **Recommendation**: In the main text and figure labels, use "action" or "decision option" throughout. Reserve "skill" for the Methods section where the software architecture is described, with a clear note that "skills" are the framework's implementation of domain actions. The Table 1 column currently says "Skill distribution" — change to "Action distribution."

### J2. "Broker" / "governance broker" / "broker core"
- **Files**: Methods (line 10, 19), Discussion (line 14)
- **Issue**: "Broker" is a software middleware pattern (message broker, service broker). The water community would use "governance layer," "validation framework," or "institutional filter." The paper mostly uses "governance" language in the main text (good), but "broker" appears in Methods.
- **Severity**: Low in main text (mostly Methods), but Methods is read by reviewers. Introduction line 22 mentions "the same broker with domain-specific rule configurations" — this should say "the same governance architecture."
- **Recommendation**: Use "governance architecture" or "governance pipeline" in all main-text prose. "Broker" can appear in Methods as a technical implementation detail.

### J3. "Retry manager" / "retry loop" / "early-exit mechanism"
- **Files**: `methods_v3.md` lines 19-20
- **Issue**: Pure software engineering language. A water reviewer would understand "iterative revision process" or "proposal-revision cycle."
- **Recommendation**: Frame as: "When a proposal fails validation, the agent receives structured feedback and may revise its proposal (up to three attempts). If the same rule blocks consecutive attempts, the cycle terminates with a domain-appropriate default action." Remove "retry manager," "early-exit mechanism," and "futile LLM calls."

### J4. "JSONL audit traces" / "structured JSON output" / "JSON formatting errors"
- **Files**: `methods_v3.md` lines 19, 29
- **Issue**: Implementation details that a water reviewer does not need. "Structured audit logs" or "machine-readable decision records" would convey the same information.
- **Recommendation**: Keep "structured JSON output" in the LLM Configuration subsection (reviewers expect this for reproducibility) but change "JSONL audit traces" to "structured decision logs."

### J5. "Context builder" / "signal package"
- **Files**: `methods_v3.md` line 10
- **Issue**: "Context builder" is a software pattern. "Signal package" is non-standard in both CS and water. A water reviewer would understand "information bundle" or "decision context."
- **Recommendation**: Rephrase as: "At each decision step, the framework assembles the information available to the agent — personal state variables, social observations from network neighbours, and system-level indicators (drought indices, flood forecasts, institutional announcements) — bounded to what the agent's role and location would permit."

### J6. "Governance value-add metric" / "pre-governance" / "post-governance"
- **Files**: `methods_v3.md` line 87
- **Issue**: "Value-add" is business/consulting jargon. "Pre-governance" and "post-governance" are clear in context but non-standard.
- **Recommendation**: "Governance contribution metric" or "governance improvement." "Pre-validation" and "post-validation" would be clearer.

### J7. "Behavioural monoculture"
- **Files**: Results lines 44, 64; Discussion
- **Issue**: This is a useful metaphor but borrowed from ecology/agriculture (genetic monoculture) and might confuse rather than clarify. A water reviewer might wonder about the ecological connotation.
- **Severity**: Low. The metaphor is vivid and the meaning is clear from context (all agents choose the same action).
- **Recommendation**: Keep — it works — but define on first use: "behavioural monoculture (near-uniform action selection across the population)."

### J8. "Hallucination" used in Introduction
- **Files**: `introduction_v10.md` line 18 — "constraint violations — distinct from the factual hallucinations studied in natural language processing"
- **Issue**: The paper correctly distinguishes its constraint violations from NLP hallucinations. But the term "hallucination" itself may confuse water reviewers. The paper handles this well by immediately clarifying.
- **Severity**: Negligible. The framing is correct.

---

## 4. RECOMMENDATIONS — Better Phrasing for Nature Water Audience

### R1. Mead elevation units
- Throughout the paper, elevation is reported in feet (ft). This is correct for Colorado River operations (USBR uses feet and acre-feet). Nature Water is an international journal and might prefer metric units. However, Colorado River literature universally uses feet and acre-feet, and converting would lose domain authenticity.
- **Recommendation**: Keep feet and MAF. Add a one-time parenthetical for international readers: "Lake Mead pool elevation (in feet above sea level, following USBR convention)" on first use.

### R2. "Prior appropriation" needs more context for international readers
- Nature Water's audience includes researchers from countries with riparian, communal, or hybrid water rights systems. "Prior appropriation" is western US-specific.
- **Current state**: The Introduction provides a parenthetical "(the seniority-based water rights system governing western US rivers)" — this is good.
- **Recommendation**: In Methods, add one sentence: "Under prior appropriation, water rights are allocated on a 'first in time, first in right' basis, with senior rights holders entitled to their full allocation before junior holders receive any water."

### R3. "Demand-Mead coupling" axis label
- **File**: `gen_fig2_irrigation.py` line 388 — axis label is "Demand-Mead correlation (Pearson r)"
- **Issue**: This is clear and appropriate. "Coupling" in the running text is consistent with sociohydrology terminology (human-water coupling).
- **Recommendation**: No change. The axis label correctly specifies the statistical measure.

### R4. Figure 1 caption "shortage-tier thresholds"
- **File**: `compile_paper.py` line 406 — "(a) Lake Mead elevation time series with shortage-tier thresholds"
- **Issue**: "Shortage-tier thresholds" is correct USBR terminology (Tier 1, 2, 3 from the 2007 Interim Guidelines). Good.
- **Recommendation**: No change needed.

### R5. "Stochastic flood events" in Results
- **File**: `section2_v11_results.md` line 62 — "stochastic flood events"
- **Issue**: Clear and appropriate for an international audience. The Methods adds specifics (annual probability 0.2, zone-specific distributions).
- **Recommendation**: No change needed.

### R6. "Coping appraisal" and "threat appraisal" — PMT terminology
- Used correctly throughout. These are standard PMT terms (Rogers, 1983). Bubeck et al. (2012) is appropriately cited for calibration.
- **Recommendation**: No change needed.

### R7. "Inundation depths" in Methods
- **File**: `methods_v3.md` line 60 — "inundation depths drawn from zone-specific log-normal distributions"
- **Issue**: "Inundation depth" is standard flood engineering terminology. Good.
- **Recommendation**: No change needed.

### R8. "Dual-appraisal framework — Water Shortage Appraisal (WSA) and Adaptive Capacity Appraisal (ACA)"
- **File**: `methods_v3.md` line 33
- **Issue**: WSA and ACA are custom constructs (not from PMT literature). They parallel PMT's threat/coping appraisal but are irrigation-specific. This is fine if introduced as simulation-specific constructs.
- **Recommendation**: Add "adapted from PMT's threat–coping framework for irrigation contexts" after introducing WSA/ACA.

### R9. "Operating point" language in Discussion
- **File**: `section3_v11_discussion.md` — "governance shifts the operating point upward" (Results, line 15)
- **Issue**: "Operating point" is control engineering jargon. Water resource managers would say "steady-state demand level" or "equilibrium extraction level."
- **Recommendation**: Replace with "governance shifts the equilibrium demand level upward" or "governance enables higher sustained extraction."

### R10. Figure legend: "A1 (no ceiling)" too cryptic
- **File**: `gen_fig2_irrigation.py` line 259
- **Issue**: "A1" is an internal experiment code. In the figure, a water reviewer needs to immediately understand what this condition means.
- **Recommendation**: Change legend to "No demand ceiling" or "Ceiling removed" — drop the "A1" prefix from figure legends while keeping it in running text for cross-reference.

### R11. "Construct-action alignment" in Methods pipeline step 6
- **File**: `methods_v3.md` line 17
- **Issue**: "Theory consistency" and "construct-action alignment" are social science terminology, appropriate for a paper bridging computation and behavioural theory. Clear.
- **Recommendation**: No change needed.

### R12. "Agent-year observations" / "agent-timestep" counting
- **Files**: Multiple — SI, Methods, Results
- **Issue**: "Agent-year" is clear (one agent's decision in one year). "Agent-timestep" appears in SI statistical methods. Both are acceptable.
- **Recommendation**: Standardize on "agent-year" in main text and SI since the timestep is annual in both domains.

---

## 5. CROSS-FILE CONSISTENCY SUMMARY

| Concept | Abstract | Introduction | Results | Discussion | Methods | SI | Figures |
|---------|----------|-------------|---------|------------|---------|----|---------|
| Metric name for action diversity | strategy diversity | strategy diversity | strategy diversity | strategy diversity | strategy diversity | strategy diversity | Strategy diversity (axis) |
| Main model | (implicit) | (implicit) | Gemma-3 4B | (implicit) | Gemma-3 4B | Gemma-3 4B | (implicit) |
| Flood actions | (not listed) | flood insurance...elevation | insurance, elevation, relocation, inaction | (not re-listed) | insurance, elevate, relocate, do nothing | same | No protection, Insurance, Elevation, Relocated |
| Irrigation actions | (not listed) | (not listed) | increase large/small, maintain, decrease small/large | (not listed) | increase (large/small), decrease (large/small), maintain | same | Increase large/small, Maintain, Decrease small/large |
| Mead threshold unit | (none) | (none) | ft | ft | ft | ft | ft (axis) |
| Shortage tiers | (none) | (none) | Tier 1/2/3 | Tier 3 | Tier 1 (1,075), Tier 2 (1,050), Tier 3 (1,025) | same | Tier 1/2/3 (figure lines) |
| Demand ratio definition | (none) | (none) | Table note | (none) | (none — should add) | Table 6 note | (none on axis) |

**Notable gaps**:
- Demand ratio is never defined in the Methods section, only in a Table 1 note. Should appear in Methods.
- The figure axis (panel b) says "Basin demand ratio" without a definition. Consider adding units or a subtitle.

---

## 6. PRIORITY ACTIONS

| Priority | ID | Action |
|----------|-----|--------|
| **HIGH** | E5 | Fix "pro rata" curtailment description — contradicts prior appropriation doctrine |
| **HIGH** | J1 | Replace "skill" with "action" in main text prose, tables, and figure labels |
| **MEDIUM** | E2 | Standardize "shortage years" across main text and SI |
| **MEDIUM** | I2 | Add acronym consolidation table (IBR/BRI/CACR/R_H) to Methods or SI |
| **MEDIUM** | J2 | Replace "broker" with "governance architecture" in results/discussion |
| **MEDIUM** | J3 | Reframe "retry manager" / "early-exit" in water-accessible language |
| **MEDIUM** | R9 | Replace "operating point" with water-standard terminology |
| **LOW** | E1 | Add "pool" or "water surface" to first Mead elevation mention |
| **LOW** | E3 | Define "curtailment spread" more clearly or rename |
| **LOW** | I3 | Standardize "demand ceiling" hyphenation |
| **LOW** | I4 | Clarify "feasibility boundaries" vs "institutional boundaries" |
| **LOW** | I5 | Note FEMA zone simplification |
| **LOW** | R1 | Add metric context for international readers |
| **LOW** | R2 | Expand prior appropriation explanation in Methods |
| **LOW** | R10 | Simplify "A1" legend in figures |

---

*Report prepared by three-expert panel review. Consensus: the paper demonstrates strong command of water resource terminology overall. The HIGH-priority items (E5 and J1) should be addressed before submission; MEDIUM items would strengthen reviewer reception; LOW items are polish.*
