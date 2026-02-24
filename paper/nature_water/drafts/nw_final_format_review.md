# Nature Water — Final Pre-Submission Format, Terminology & Definition Review

**Date**: 2026-02-23
**Reviewed files**: abstract_v10.md, introduction_v10.md, section2_v11_results.md, section3_v11_discussion.md, methods_v3.md
**Reviewer**: Claude (format/terminology audit)

---

## Check 1: Term Definitions — First-Use Audit

| Term | First defined? | Where? | Definition clear? | Action needed? |
|------|:-:|--------|:-:|--------|
| EHE (Effective Heterogeneity Entropy) | YES | Results Table 1 footnote: "normalized Shannon entropy over 5 action types; see Methods" | YES (formula in Methods) | PASS |
| IBR (Irrational Behaviour Rate) | YES | Results Table 2 footnote: "fraction of decisions classified as physically impossible or inconsistent..." | YES (detailed in Methods) | PASS |
| BRI (Behavioural Rationality Index) | YES | Results Table 1 footnote: "fraction of high-scarcity decisions where agents did not increase demand" | YES (relationship to IBR explained in Methods) | PASS |
| CACR (Construct-Action Coherence Rate) | NO in main text | Methods only: "CACR = 1 - IBR_coherence" | Partial — appears only in Methods, never used in Results or Discussion prose | **FLAG**: CACR is defined in Methods but never referenced in Results/Discussion. If it is not used in main text, consider removing from Methods or adding a brief mention. Currently fine as a Methods-only technical detail. |
| WSA (Water Shortage Appraisal) | YES | Methods, Irrigation Domain Setup | YES | PASS |
| ACA (Adaptive Capacity Appraisal) | YES | Methods, Irrigation Domain Setup | YES | PASS |
| TP (Threat Perception) / CP (Coping Perception) | NO | Never appear as "TP" or "CP" | N/A | **NOTE**: The paper uses "threat appraisal" and "coping appraisal" (PMT standard terms) throughout, not TP/CP. The abbreviations TP/CP from config files are NOT used in the paper. This is correct — the paper uses the full PMT terminology. PASS. |
| PMT (Protection Motivation Theory) | YES | Introduction P3: "Protection Motivation Theory" with Rogers 1983 citation | YES | PASS |
| Prior-appropriation | YES | Introduction P3: "prior-appropriation operating rules" (Hung and Yang, 2021) | Partial — used as if readers know it | **FLAG**: First used in Introduction P3 without definition. A NW audience likely knows this term, but consider a brief parenthetical gloss on first use, e.g., "prior-appropriation (the seniority-based water rights system governing western US rivers)". It IS defined implicitly in Discussion P1: "senior rights holders extract their full entitlement in normal years because shortage-sharing rules ensure proportionate curtailment during drought." |
| Demand ratio | YES | Results Table 1 footnote: "requested volume / historical baseline allocation" | YES | PASS |
| Demand-Mead coupling | YES | Results R1: "correlation between annual Lake Mead elevation and aggregate demand (r = 0.547...)" | YES — operationally defined on first use | PASS |
| Adaptive exploitation | YES | Abstract: "higher extraction during abundance, proportionate curtailment during drought" | YES — defined operationally | PASS |
| Adaptive diversity vs arbitrary diversity | YES | Results R2: "between diversity (a wider action distribution) and adaptive diversity (an action distribution coupled to environmental state)" | YES — explicit italicized distinction | PASS |
| MAF (million acre-feet) | YES | Results R2: "aggregate basin demand exceeds 6.0 million acre-feet (MAF)" | YES | PASS |
| CRSS (Colorado River Simulation System) | YES | Methods, Irrigation Domain Setup | YES | **FLAG**: First use in main text is Introduction P7 ("CRSS demand nodes") — but CRSS is not expanded there. It is expanded only in Methods. Add expansion on first main-text use. |
| Shortage tiers | YES | Methods, Reservoir Simulation: Tier 1/2/3 with thresholds | YES | PASS |
| FQL (Fuzzy Q-Learning) | YES | Results Table 1 caption: "FQL = fuzzy Q-learning baseline (Hung and Yang, 2021)" | YES | PASS |
| Agent-year / agent-timestep | NO | Used in Introduction P7 ("over 9,800 governed decisions") and throughout | Implicit — readers can infer | **MINOR**: The term "agent-year" appears in Table 2 footnote and Methods. Not formally defined but self-explanatory. PASS. |
| Feasibility boundaries | YES | Abstract and Introduction P6 | YES — Ostrom-derived concept, adequately glossed | PASS |
| Strategy diversity | YES | Abstract and Results R3 | YES — operationalized as EHE | PASS |
| JSON / JSONL | YES | Methods only | N/A — appropriate for Methods | PASS (see Check 3) |
| YAML | YES | Methods only | N/A — appropriate for Methods | PASS (see Check 3) |

### Summary: 2 action items, 1 minor flag
1. **CRSS**: Expand on first main-text use (Introduction P7)
2. **Prior-appropriation**: Consider brief gloss on first use (Introduction P3)
3. Minor: CACR defined only in Methods — fine if intentional

---

## Check 2: Terminology Consistency

| Concept | Terms used | Consistent? | Action needed? |
|---------|-----------|:-:|--------|
| Strategy diversity vs behavioural diversity | "strategy diversity" used throughout Results and Discussion. "behavioural diversity" does NOT appear in any section. | YES | PASS |
| Governed vs governance | "governed" (adjective for agents/condition), "governance" (noun for the system/mechanism), "institutional governance" (once in Discussion) | YES — natural usage | PASS |
| Ungoverned vs ungovern | "ungoverned" used consistently. No "ungovern" or "no governance" found. | YES | PASS |
| Demand ratio | Defined once, used consistently as "demand ratio" throughout | YES | PASS |
| Skill names — Irrigation | Paper uses: "increase demand (large or small), decrease demand (large or small), and maintain demand" (Methods). Results/Discussion use "demand increases" / "demand decrease" generically. | YES — prose versions are appropriate | PASS |
| Skill names — Flood | Paper uses: "insurance, elevation, relocation, or inaction" (Results R4) and "purchase flood insurance, elevate home, relocate, or do nothing" (Methods). Table 2 headers: "do_nothing", "insurance", "elevation", "relocation" | YES — consistent between prose and table | PASS |
| Adaptive exploitation | Used consistently in Abstract, Results R1, Discussion P1. Never shortened or varied. | YES | PASS |
| Action diversity | NOT used — only "strategy diversity" | YES — no conflicting term | PASS |
| EHE notation | "EHE" used consistently. Never "H_eff" or other variants. | YES | PASS |
| Behavioural theory names | "Protection Motivation Theory" (full) used on first mention; "PMT" thereafter. Consistent. | YES | PASS |
| Agent descriptors | "language-based agents" in Abstract/Introduction; "language agents" as shorter form in Results/Discussion. "LLM agents" NOT used in main text. | YES | PASS |
| Broker/framework | "governance broker" and "broker" used in Methods. "Water Agent Governance Framework" NOT used in main text (appropriate — avoid branding). | YES | PASS |

### Summary: No inconsistencies found. All terminology is uniform.

---

## Check 3: NW Audience Terminology — CS/ML Jargon Audit

| Term | Where used | Appropriate for NW? | Recommendation |
|------|-----------|:-:|--------|
| "language-based agents" | Throughout | YES | Correct framing — avoids "LLM" in main text |
| "LLM" | Methods ("LLM agent layer", "LLM calls"), Table 2 column headers ("Governed LLM", "Ungoverned LLM") | **BORDERLINE** | **FLAG**: "LLM" appears in Table 2 and Table 3 headers. Consider replacing with "language agent" or "language-based" in table headers. Methods usage is acceptable. |
| "language model" / "language models" | Results R4: "six language models tested" | YES | Appropriate for NW |
| "parameter count" | NOT used | N/A | PASS — paper uses "model scale" or "parameter scales" |
| "JSON" | Methods only: "structured JSON output" | YES for Methods | PASS — technical detail appropriate in Methods |
| "YAML" | Methods only: "Skill registries (YAML)" | YES for Methods | PASS |
| "JSONL" | Methods only: "JSONL audit traces" | YES for Methods | PASS |
| "retry" / "early-exit" | Methods only: "retry manager", "early-exit mechanism" | YES for Methods | PASS — governance terminology used in main text ("blocked", "prevented") |
| "fallback" | NOT in main text | N/A | PASS |
| "inference" | Methods: "local inference platform" | YES for Methods | PASS |
| "token" / "context window" | Methods: "context window of 8,192 tokens" | YES for Methods | PASS |
| "decoder-only transformers" | Discussion P5 (scope conditions) | **BORDERLINE** | **FLAG**: "instruction-tuned decoder-only transformers" is ML jargon. Consider simplifying to "instruction-tuned language models" — the architecture detail adds nothing for NW readers. |
| "temperature" / "top_p" / "nucleus sampling" | Methods only | YES for Methods | PASS — standard ML methods reporting |
| "open-weight models" | Methods | YES | More precise than "open-source" |
| "Ollama" | Methods | YES for Methods | Reproducibility detail |
| "smart repair preprocessing" | Methods | **BORDERLINE** | **MINOR FLAG**: Could simplify to "rule-based preprocessing that corrects common formatting errors before parsing" — the term "smart repair" is internal jargon. |

### Summary: 3 flags
1. **"LLM"** in Table 2/3 headers — consider "Language agent" instead
2. **"decoder-only transformers"** in Discussion — simplify to "instruction-tuned language models"
3. **"smart repair"** in Methods — minor, rephrase as generic description

---

## Check 4: Nature Water Format Compliance

### Abstract
| Criterion | Status | Notes |
|-----------|:-:|-------|
| Unreferenced | **PASS** | No citations in abstract |
| <=150 words | **PASS** | ~145 words per header |
| Single paragraph | **PASS** | One continuous paragraph |
| Results-first structure | **PASS** | Opens with finding, not method |

### Main Text Word Count
| Section | Approx. words | Notes |
|---------|:---:|-------|
| Introduction | ~830 | Within NW Analysis limit |
| Results | ~2,100 | Per header |
| Discussion | ~950 | Per header |
| **Total (excl. Methods)** | **~3,880** | **NW Analysis limit = 4,000. PASS.** |
| Methods | ~2,200 | Not counted in main limit |

### Figure/Table Numbering
| Item | Status | Notes |
|------|:-:|-------|
| Table 1 | **PASS** | Results R1 — irrigation outcomes |
| Table 2 | **PASS** | Results R3 — flood domain comparison |
| Table 3 | **PASS** | Results R4 — cross-model comparison |
| Sequential | **PASS** | Tables 1, 2, 3 in order |
| Figures | **N/A** | No figures referenced in text body (presumably in SI or as separate files) |

### References Format
| Criterion | Status | Notes |
|-----------|:-:|-------|
| In-text citations | **PASS** | Author (Year) or Author et al. (Year) format throughout |
| Nature format (Author. Title. *Journal* **vol**, pages (year).) | **CANNOT VERIFY** | Reference list not included in reviewed files. Needs separate check of bibliography file. |

### SI Cross-References
| Reference in main text | Status |
|----------------------|:-:|
| "Supplementary Section S11" (FQL) | **PASS** — referenced in Results R1 and Discussion P3 |
| "Supplementary Tables S2-S4" (reasoning traces) | **PASS** — referenced in Results R3 |
| "Supplementary Table S6" (additional metrics) | **PASS** — referenced in Table 1 footnote |
| "Table S1" (IBR decomposition) | **PASS** — referenced in Results R4, Table 3 footnote |
| "Supplementary Information" (retry statistics) | **PASS** — referenced in Results R3 |
| "SI Table S1 note" (Groups B vs C) | **PASS** — referenced in Methods |
| SI for model-specific discussion (12B) | **PASS** — referenced in Results R4 |

**FLAG**: Verify that the actual SI document contains all referenced sections (S2-S4, S6, S11, Table S1). Cross-reference numbering must be confirmed against the SI file.

---

## Check 5: Domain Terminology — Config File Alignment

### Irrigation Skills
| Config term | Paper term | Match? |
|------------|-----------|:-:|
| increase_large | "increase demand (large)" | YES |
| increase_small | "increase demand (small)" | YES |
| maintain_demand | "maintain demand" | YES |
| decrease_small | "decrease demand (small)" | YES |
| decrease_large | "decrease demand (large)" | YES |
| 5 skills total | "Five skills define the action vocabulary" | YES |

### Flood Skills
| Config term | Paper term | Match? |
|------------|-----------|:-:|
| do_nothing | "do nothing" / "inaction" | YES |
| buy_insurance | "purchase flood insurance" / "insurance" | YES |
| elevate_house | "elevate home" / "elevation" | YES |
| relocate | "relocate" / "relocation" | YES |
| 4 skills total | "Four skills are available" | YES |

### Appraisal Frameworks
| Config term | Paper term | Match? |
|------------|-----------|:-:|
| WSA (irrigation) | "Water Shortage Appraisal (WSA)" | YES |
| ACA (irrigation) | "Adaptive Capacity Appraisal (ACA)" | YES |
| TP (flood) | "threat appraisal" (PMT standard) | YES — TP abbreviation not used, full term used instead |
| CP (flood) | "coping appraisal" (PMT standard) | YES — CP abbreviation not used, full term used instead |

### Behavioral Clusters
| Config term | Paper prose | Match? |
|------------|-----------|:-:|
| aggressive | Not explicitly named in paper | **NOTE**: Behavioral cluster names do not appear in main text. They are implementation details. Acceptable. |
| forward_looking_conservative | Not in paper | Acceptable — implementation detail |
| myopic_conservative | Not in paper | Acceptable — implementation detail |

### Summary: All domain terms match. Cluster names appropriately omitted from paper.

---

## Consolidated Action Items

### Must Fix (before submission)

| # | Issue | Section | Fix |
|---|-------|---------|-----|
| 1 | **CRSS not expanded on first main-text use** | Introduction P7 | Change "CRSS demand nodes" to "Colorado River Simulation System (CRSS) demand nodes" |
| 2 | **"decoder-only transformers"** — ML jargon unnecessary for NW | Discussion P5 | Change to "instruction-tuned language models" |

### Should Fix (recommended)

| # | Issue | Section | Fix |
|---|-------|---------|-----|
| 3 | **"LLM" in table headers** | Tables 2, 3 | Replace "Governed LLM" / "Ungoverned LLM" with "Governed language agent" / "Ungoverned language agent" |
| 4 | **Prior-appropriation undefined** on first use | Introduction P3 | Add brief parenthetical: "(the seniority-based water-rights doctrine governing western US rivers)" |
| 5 | **"smart repair preprocessing"** — internal jargon | Methods | Rephrase: "a rule-based procedure that corrects common JSON formatting errors (missing braces, unescaped characters) before parsing" |

### Optional (minor polish)

| # | Issue | Section | Fix |
|---|-------|---------|-----|
| 6 | CACR defined in Methods but never used in main text | Methods | Intentional? If not needed outside Methods, fine as-is. If referenced in SI, ensure consistency. |
| 7 | SI cross-reference numbering | All | Verify against actual SI file that S2-S4, S6, S11, Table S1 all exist with matching content |
| 8 | Reference list format | Bibliography | Verify Nature format: Author. Title. *Journal* **vol**, pages (year). — requires checking the .bib or reference file separately |

---

## Overall Assessment

The paper is in strong shape for submission. Terminology is internally consistent throughout all five sections. The water-first framing is maintained — CS/ML jargon is appropriately confined to Methods. The two must-fix items (CRSS expansion, decoder-only transformers) are single-line edits. The should-fix items improve accessibility for the NW audience but are not blockers.

Word count (~3,880) is within the 4,000-word Analysis format limit with ~120 words of margin.
