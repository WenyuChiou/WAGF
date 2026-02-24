# Expert Panel Review: Nature Water Analysis v14

## Full Pre-Submission Review

**Reviewers**: Expert panel (water resources, computational social science, ABM methodology, institutional theory)
**Date**: 2026-02-23
**Paper**: "Institutional Constraints Widen Adaptive Strategy Diversity in Language-Based Water Agents"
**Format**: Nature Water Analysis (~4,000 words main text + Methods + SI)

---

## 1. Abstract (~145 words)

### Strengths
- Leads with a concrete water finding (adaptive exploitation) rather than a method announcement — correct for NW audience.
- Efficiently conveys four distinct findings in a single paragraph: adaptive exploitation, rule decomposition (A1), cross-domain generalization, IBR reduction.

### Issues

1. **"We propose a governance architecture"** — The verb "propose" is method-forward. Nature Water Analysis format expects the water finding to lead. The architecture is the tool; the finding is the result.
   - *Suggested fix*: Replace opening sentence with something like: "Language-based agents governed by modular physical and institutional rules exploit water resources more aggressively during abundance while maintaining drought responsiveness."

2. **"compressed away by parameterized decision functions"** — Appears twice in the abstract+introduction. While intentional as a motif, in a 145-word abstract every word counts; this clause is 6 words of method-critique rather than water-science content.
   - *Suggested fix*: Trim to "...adaptive exploitation invisible to parameterized models" or cut entirely from the abstract (it appears in the intro).

3. **"was positive for five of six language models tested"** — Grammatically, the subject of "was positive" is "the effect" but the closest preceding noun is "acute flood hazard." Slight ambiguity.
   - *Suggested fix*: "the governance effect on strategy diversity was positive for five of six language models tested."

4. **No quantitative result in abstract** — The abstract mentions 0.8–11.6% and 1.7% for IBR but gives no numbers for the core irrigation finding (DR, r). Nature Water abstracts typically include 1–2 key numbers for the primary result.
   - *Suggested fix*: Consider adding "(demand ratio 0.394 vs 0.288; demand–drought coupling r = 0.547 vs 0.378)" after "adaptive exploitation."

---

## 2. Introduction (~830 words)

### Strengths
- The opening paragraph is excellent: "six decades, single paradigm" creates immediate tension and positions the paper historically.
- The progression Harvard Water Program → sociohydrology → ABM → LLM is logically tight and historically grounded. Blair & Buytaert (2016) is well-deployed as a pivot between aggregate and individual reasoning.

### Issues

5. **P3 is too long (~180 words)** — It packs ABM history, three limitations, and Schluter (2017) into one paragraph. The density risks losing the NW reader.
   - *Suggested fix*: Split after "...Hung and Yang (2021) encoded prior-appropriation operating rules for Colorado River demand management." Start a new paragraph with "More recent approaches have introduced adaptive mechanisms..."

6. **"over 40 distinct behavioural theories"** — This is a strong claim sourced to Schluter et al. (2017). Verify that Schluter's actual count supports "over 40" and not "dozens" or a different framing.
   - *Suggested fix*: If the exact count is uncertain, use "dozens of behavioural theories" or cite the specific figure from Schluter.

7. **P5 (risks paragraph) jumps from LLM promise to LLM danger without transition** — P4 ends on an optimistic note ("language may serve as a medium for representing..."), then P5 opens with "Yet language-based agents carry risks." The pivot is adequate but could be smoother.
   - *Suggested fix*: Minor — acceptable as-is, but adding "However, this representational power introduces..." would smooth the transition.

8. **"Answering this governance question connects computation to institutional theory"** — This sentence is the weakest transition in the paper. "Connects computation to institutional theory" is vague for a water journal.
   - *Suggested fix*: "Answering this governance question draws on institutional theory for common-pool resources."

9. **P7 results preview is very dense (~150 words)** — It front-loads nearly every result. NW Analysis intros typically give a 2–3 sentence preview, not a full paragraph of findings.
   - *Suggested fix*: Trim to: (a) adaptive exploitation finding, (b) A1 ablation finding, (c) cross-domain generalization. Move PMT comparison and "five of six" detail to Results.

10. **"generating over 9,800 governed decisions across three seeds"** — But Methods says 78 agents × 42 years × 3 seeds = 9,828. The abstract rounds to "9,800" which is fine, but the intro says "9,800 governed decisions" while the actual governed count may differ (some decisions are ungoverned runs). Verify this refers to governed-condition decisions only.
    - *Suggested fix*: Clarify: "generating 9,828 agent-year decisions per condition across three seeds."

---

## 3. Results (~2,100 words)

### Strengths
- The four-subsection structure (R1–R4) tells a clean story: what → why → how much → how broadly.
- Table 1 is well-designed: the three-column (Governed/Ungoverned/A1) layout makes comparisons immediate. The A1 column is a powerful addition.

### Issues

11. **R1, paragraph 2: "In prior-appropriation systems, this parallels how senior rights holders extract their full entitlement..."** — This analogy is strong but asserted without citation. A reference to actual prior-appropriation behaviour (e.g., USBR reports, Getches 2009, or similar) would strengthen it.
    - *Suggested fix*: Add a citation for the empirical observation that senior rights holders extract aggressively in normal years.

12. **R1, paragraph 3: "concentrating 77–82% of decisions on demand increases across all seeds"** — Table S6 says "Percentage of agents increasing demand: ~53% (governed), 77–82% (ungoverned)." But the text says "77–82% of *decisions*" while the table says "of *agents*." These are different metrics.
    - *Suggested fix*: Harmonize — either change text to "of agents" or change table to "of decisions." Then verify which is correct in the data.

13. **Table 1 footnote: "BRI = fraction of high-scarcity decisions where agents did not increase demand"** — But the BRI column shows 58.0% for governed and 9.4% for ungoverned. If BRI is "fraction who did NOT increase," then governed = 58% is lower than null (60%), which the text interprets as "governance removes increase-bias." This is fine, but the A1 column shows "—" for BRI. Why is BRI not computed for A1?
    - *Suggested fix*: Add a brief note: "A1 BRI not computed because the demand ceiling is the primary mechanism linking scarcity signals to blocking; its removal invalidates the BRI denominator definition."

14. **R2: "nearly doubled shortage years from 13.3 to 25.3"** — 25.3/13.3 = 1.90×. "Nearly doubled" is accurate. Good.

15. **R3: "first-attempt EHE 0.761 governed versus 0.640 ungoverned"** — These numbers are in SI S3 but not in any main-text table. A key claim about mechanism (governance shapes reasoning, not just filters output) relies on numbers the reader must hunt for in the SI.
    - *Suggested fix*: Consider adding first-attempt EHE as a row in Table 1, or at minimum add "(Supplementary Section S3)" explicitly after the numbers.

16. **R3: "four governed agents selected four different skills through distinct cognitive frames: opportunity-seeking under self-assessed confidence, reflective learning..."** — This is compelling qualitative evidence, but the sentence runs to ~50 words listing four frames. For NW readers, this may be too much detail for the main text.
    - *Suggested fix*: Trim to: "four governed agents selected four different skills through distinct cognitive frames (Supplementary Tables S2–S4)."

17. **Table 2: Flood domain IBR** — Governed IBR = 0.9%, Ungoverned IBR = 1.1%. But Table S1 shows Gemma-3 4B ungoverned R_H = 1.15% and governed R_H = 0.86%. Table 2 rounds these to 0.9% and 1.1%. The rounding direction for ungoverned (1.15% → 1.1%) is fine but for governed (0.86% → 0.9%) rounds UP. This is technically correct but atypical.
    - *Suggested fix*: Use one decimal place consistently: 0.9% and 1.2%, or report to two decimals (0.86% and 1.15%) to match Table S1.

18. **R4: "IBR = 0.1–1.7% governed versus 0.8–11.6% ungoverned"** — The abstract says "0.8–11.6% to below 1.7%." Checking Table S1: governed minimum is Ministral 8B at 0.13%, governed maximum is Ministral 3B at 1.70%. Ungoverned minimum is Gemma-3 27B at 0.78%, ungoverned maximum is Ministral 14B at 11.61%. The range "0.1–1.7%" rounds 0.13 down to 0.1. The abstract says "below 1.7%" which is technically wrong since Ministral 3B = 1.70% exactly.
    - *Suggested fix*: Use "0.1–1.7%" in both places (consistent), or change abstract to "at or below 1.7%."

19. **R4: "six models spanning two families and three parameter scales"** — Two families (Gemma-3, Ministral) × three sizes (small, medium, large) = six models. But the sizes are 3B/4B, 8B/12B, 14B/27B — not perfectly matched scales. This is acknowledged implicitly but a water reader may wonder why the scales don't match.
    - *Suggested fix*: Add parenthetical: "(3B–27B parameters; see Methods for model details)."

---

## 4. Discussion (~950 words)

### Strengths
- P1 opens with the central water finding, not a literature review — correct for NW.
- P3 (computational laboratory) is the strongest paragraph in the paper. The four specific policy experiments (shortage thresholds, allocation regimes, premium structures, DCP triggers) make the method contribution concrete and actionable for water researchers.

### Issues

20. **P1: "r = 0.547 substantially more than ungoverned agents (r = 0.378)"** — Repeating these numbers from Results is acceptable in the Discussion, but "substantially" is a qualitative judgment. The difference is 0.169 in Pearson r. Consider whether this merits "substantially" or just "more."
    - *Suggested fix*: Either add a statistical test result (e.g., "significantly higher, p = X") or soften to "meaningfully higher."

21. **P2: "Ostrom (1990) observed that well-designed institutions... create structured arenas within which diverse adaptive strategies become viable."** — This is a close paraphrase of the Introduction's P6. The repetition is intentional but feels heavy for a 950-word Discussion.
    - *Suggested fix*: Shorten to: "This aligns with Ostrom's (1990) observation that institutional design creates arenas for diverse adaptive strategies."

22. **P3: "A fuzzy Q-learning baseline (Hung & Yang, 2021) achieved comparable demand ratios but near-zero demand–Mead coupling (r = 0.057 versus 0.547 governed)"** — This is a strong result but it appears ONLY in the Discussion, not in Results. The FQL comparison is in SI S11 only. For a result this important (it isolates the representational contribution of language), it deserves at least a mention in R1 or R4.
    - *Suggested fix*: Add one sentence in R1 or R4 referencing the FQL result, pointing to SI S11, so the Discussion can build on it rather than introducing it.

23. **P4: "42% of high-scarcity decisions still attempted demand increases despite drought signals (Table 1, BRI)"** — BRI = 58.0% means 58% did NOT increase. So 42% DID increase. The math checks out, but the text says "Table 1, BRI" — yet BRI in Table 1 is defined as "fraction of high-scarcity decisions where agents did not increase demand." The 42% is (1 - BRI), which the reader must compute.
    - *Suggested fix*: Add: "...42% of high-scarcity decisions still attempted demand increases (i.e., 1 − BRI = 1 − 0.58; Table 1)."

24. **P5 (scope conditions): "Only one model (Gemma-3 4B) was tested in the irrigation domain"** — This is the paper's most significant limitation and it appears in the final paragraph. For NW reviewers, this will be a major concern. The flood domain has 6 models but irrigation — the primary domain — has only one.
    - *Suggested fix*: No text change needed, but be prepared for reviewer pushback. Consider whether a brief sentence in P5 explains why (e.g., computational cost of 78×42×3 runs per model).

25. **P5: "Each domain required substantial configuration (personas, validators, skill registries); transferability refers to the governance architecture, not the configuration effort."** — This is an important and honest caveat. It could be expanded slightly to quantify the configuration effort (e.g., "approximately X person-weeks per domain").
    - *Suggested fix*: Minor — acceptable as-is, but quantification would strengthen honesty.

---

## 5. Methods

### Strengths
- The six-step validation pipeline is clearly presented and easy to follow.
- The reservoir simulation is well-documented with explicit equations and parameter values.

### Issues

26. **"Temperature was set to 0.8... no temperature sensitivity analysis was conducted"** — This is an important caveat. However, temperature is a major control on LLM output diversity. A reviewer may ask why temperature sensitivity was not tested, given that the paper's central claim is about diversity.
    - *Suggested fix*: Add one sentence: "Temperature sensitivity is a direction for future work; the fixed value was chosen following Park et al. (2023) and held constant across all conditions, ensuring that diversity differences reflect governance effects rather than sampling variation."

27. **Flood domain setup: "Group C (Governed + HumanCentric Memory)... Group C is not analysed in this paper"** — Then why describe it? This is confusing for the reader and wastes ~40 words.
    - *Suggested fix*: Remove Group C description entirely, or reduce to a single parenthetical: "(a third memory condition was tested but is not analysed here)."

28. **"Twelve validators enforce constraints: 7 physical... 1 institutional... 2 social... 1 temporal... and 1 behavioural"** — 7+1+2+1+1 = 12. Correct. But the SI S7 lists the 7 physical validators and one of them is "Upstream flow variability constraints" which is not obviously a physical constraint (it could be hydrological or institutional).
    - *Suggested fix*: Minor — rename to "Hydrological flow variability" or accept the categorization.

29. **Statistical Analysis: "Each experimental condition was replicated with three independent random seeds"** — The justification ("consistent with standard practice") is adequate but n=3 is a known weakness. The paper handles this well by reporting all six models showing directional consistency, which is compelling despite small n.
    - *Suggested fix*: No change needed; the existing justification is appropriate.

30. **Rule-Based PMT Agent section: "42.8% of raw decisions" were composite** — This is a high rate. The handling (splitting into constituents) is clearly described, but a reviewer may question whether this conflates the PMT agent's action space with the LLM's.
    - *Suggested fix*: Add: "This composite rate reflects the deterministic threshold logic, which can simultaneously exceed both action thresholds; LLM agents select a single action per year by design."

---

## 6. Supplementary Information

### Strengths
- S2 (reasoning traces) is excellent. The paired governed/ungoverned traces in Table S2 are the paper's most compelling qualitative evidence.
- S11 (FQL baseline) is well-designed and the 84–89% blocking rate is an important finding that honestly reports a methodological mismatch.

### Issues

31. **Table S1: Group labels** — Table S1 uses "A (ungoverned)" and "C (governed)" but the main text uses "governed" and "ungoverned" without group letters. The Methods define Group A = ungoverned, Group B = governed, Group C = governed + memory. But S1 compares A vs C, not A vs B. This is a significant inconsistency.
    - *Suggested fix*: **CRITICAL** — If the main text reports governed results from Group B, but SI Table S1 reports Group C as "governed," these may be different experimental conditions. Verify that the EHE values in Table S1 (e.g., Gemma-3 4B governed = 0.636) match the Group B values, not Group C. If S1 actually reports Group C data, this is a data-claim mismatch throughout the paper.

32. **S3: "Governed first-attempt EHE: 0.761 ± 0.020"** — Main text R3 cites 0.761. Consistent.

33. **S5: Premium doubling sensitivity** — The reversal (ungoverned > governed under premium doubling) is an important finding that could undermine the main claim if a reviewer interprets it as showing the governance effect is fragile. The current framing ("external cost pressure can substitute for governance") is honest but may invite criticism.
    - *Suggested fix*: Add: "This reversal occurs under a single model (Gemma-3 4B) with a single economic parameter; whether it generalizes across models is untested."

34. **S9: "Δ EHE from +0.012 to +0.415"** — But Table 3 shows delta range from −0.024 to +0.329. The S9 range (+0.012 to +0.415) does not match Table 3. This is a clear number mismatch.
    - *Suggested fix*: **CRITICAL** — Update S9 to match Table 3 values: "Δ EHE from −0.024 to +0.329."

35. **S9: "All six models showed positive governance effects under the primary normalization (Table 3)"** — But Table 3 shows Ministral 8B at −0.024. This is NOT positive. Direct contradiction.
    - *Suggested fix*: **CRITICAL** — Change to "Five of six models showed positive governance effects under the primary normalization (Table 3), with one (Ministral 8B) showing a small negative effect."

36. **S11: FQL demand ratio 0.395 ± 0.008 vs LLM 0.394 ± 0.004** — These are remarkably close, which strengthens the isolation argument. Good.

---

## 7. Cross-Section Consistency Check

### Numbers verified against user-provided key data:

| Metric | Expected | Abstract | Results | Discussion | Methods | SI | Status |
|--------|----------|----------|---------|------------|---------|-----|--------|
| Irrigation DR gov | 0.394 | not stated | 0.394 ± 0.004 (T1) | — | — | — | OK |
| Irrigation DR ungov | 0.288 | not stated | 0.288 ± 0.020 (T1) | — | — | — | OK |
| Irrigation DR A1 | 0.440 | not stated | 0.440 ± 0.012 (T1) | — | — | — | OK |
| Irrigation r gov | 0.547 | not stated | 0.547 ± 0.083 (T1) | 0.547 (P1) | — | S11: 0.547 | OK |
| Irrigation r ungov | 0.378 | not stated | 0.378 ± 0.081 (T1) | 0.378 (P1) | — | — | OK |
| Irrigation r A1 | 0.234 | not stated | 0.234 ± 0.127 (T1) | — | — | — | OK |
| Irrigation EHE gov | 0.738 | not stated | 0.738 ± 0.017 (T1, R3) | — | — | — | OK |
| Irrigation EHE ungov | 0.637 | not stated | 0.637 ± 0.017 (T1, R3) | — | — | — | OK |
| Irrigation EHE A1 | 0.793 | not stated | 0.793 ± 0.002 (T1) | — | — | — | OK |
| Flood EHE gov (4B) | 0.636 | not stated | 0.636 ± 0.044 (T2, T3) | — | — | S1: 0.636 | OK |
| Flood EHE PMT | 0.486 | not stated | 0.486 ± 0.011 (T2) | — | — | — | OK |
| Flood EHE ungov (4B) | 0.307 | not stated | 0.307 ± 0.059 (T2, T3) | — | — | S1: 0.307 | OK |
| IBR range ungov | 0.8–11.6% | 0.8–11.6% | 0.8–11.6% (R4) | — | — | S1: 0.78–11.61% | **MINOR**: 0.78 rounds to 0.8 |
| IBR range gov | below 1.7% | below 1.7% | 0.1–1.7% (R4) | — | — | S1: 0.13–1.70% | **MINOR**: "below 1.7%" vs exactly 1.70% |
| 4/6 sig IBR | 4/6 | 4 of 6 (abstract) | 4 of 6 (R4) | 4 of 6 (P5) | — | S1b: p<0.01 for 4 | OK |
| 5/6 pos EHE | 5/6 | 5 of 6 (abstract) | 5 of 6 (R4) | 5 of 6 (P5) | — | — | OK |

### Terminology consistency:

| Term | Abstract | Intro | Results | Discussion | Methods | SI |
|------|----------|-------|---------|------------|---------|-----|
| "strategy diversity" | yes | yes | yes | yes | yes | yes | OK — consistent throughout |
| "adaptive exploitation" | yes | yes | yes | yes | — | — | OK |
| "feasibility boundaries" | yes | — | — | yes | — | — | OK |
| EHE definition | — | — | T1 note | — | Methods | S9 | **ISSUE**: T1 says "H/log₂(k)" but S9 uses "H/log(k)" without base specification |
| BRI vs IBR | — | — | T1=BRI, R4=IBR | — | IBR (L1) | IBR (S1) | **ISSUE**: Two names for related but distinct metrics — see Issue 37 below |

### Critical inconsistencies found:

37. **BRI vs IBR naming** — Table 1 calls the rationality metric "BRI" (Behavioural Rationality Index). R4 and the abstract use "IBR" (Irrational Behaviour Rate) for the flood domain. Methods defines both. The relationship is: BRI = 1 − IBR (approximately, since they measure different things per domain). But the casual reader will be confused by two acronyms for related concepts.
    - *Suggested fix*: In the main text, use one metric name consistently. Since the flood domain uses IBR and the irrigation domain uses BRI, and they measure complementary quantities, consider: (a) defining both once in Methods, (b) using "irrational behaviour rate" descriptively in the abstract/results without the acronym, and (c) keeping BRI for irrigation and IBR for flood only in tables.

38. **S1 Group labels (A vs C)** — As noted in Issue 31, Table S1 compares Group A (ungoverned) with Group C (governed + memory), not Group B (governed, standard memory). If main-text Tables 2–3 report Group B data, the SI is reporting a different experimental condition. This must be verified.

39. **S9 number mismatch** — As noted in Issues 34–35, S9 claims all six models positive and cites a delta range that does not match Table 3.

---

## 8. Overall Assessment

### Word count estimate:
- Abstract: ~145 words — OK (limit 150)
- Introduction: ~830 words — OK
- Results: ~2,100 words — OK
- Discussion: ~950 words — OK
- **Main text total: ~3,930 words** — within the ~4,000 target
- Methods: uncounted (separate) — OK
- SI: ~3,500 words + tables — reasonable

### Nature Water Analysis format compliance:
- Unreferenced abstract: YES
- ~4,000 word main text: YES (~3,930)
- Methods section: YES (separate, uncounted)
- SI: YES
- Tables in main text: 3 (T1, T2, T3) — appropriate
- Figures: NONE referenced — **ISSUE**: Nature Water Analysis papers typically include 2–4 figures. The paper has zero figures in the main text. This is a significant format concern.

### Narrative coherence:
The paper tells a unified story: governance enables adaptive water behaviour (R1), a single rule creates the coupling (R2), governance outperforms hand-coded baselines (R3), the effect generalizes (R4). The Discussion builds cleanly on these four results. The Introduction sets up the problem well. **Overall narrative: STRONG.**

### Audience fit:
The paper is written for water scientists, not CS researchers. Water is the subject of every finding sentence. LLM technical details are minimized in the main text. Institutional theory (Ostrom, prior-appropriation) frames the contribution. **Audience fit: GOOD.**

---

## 9. Verdict: MINOR REVISIONS

The paper is well-written, scientifically sound, and appropriately framed for Nature Water. The core findings are supported by data, the narrative is coherent, and the audience targeting is correct. However, several issues require attention before submission:

---

## 10. Top 5 Priority Fixes

### P1. [CRITICAL] S1 Group label mismatch (Issue 31/38)
Table S1 labels the governed condition as "C" but the main text defines Group B as the standard governed condition and Group C as governed + memory. Verify that all main-text governed data comes from the same experimental group reported in S1. If S1 reports Group C but main text reports Group B, either relabel S1 or ensure the numbers are identical (which they may be if Group C happens to match Group B for the metrics reported). **This is the single most important fix because it could indicate a data-source inconsistency.**

### P2. [CRITICAL] S9 contradicts Table 3 (Issues 34–35)
S9 states "all six models showed positive governance effects" and cites a delta range of "+0.012 to +0.415." Table 3 shows Ministral 8B at −0.024, and the actual range is −0.024 to +0.329. Fix both the count (five of six, not all six) and the range to match Table 3.

### P3. [IMPORTANT] No figures in main text (Overall Assessment)
Nature Water Analysis papers typically include figures. Consider adding: (a) a time-series figure showing governed vs ungoverned demand trajectories overlaid on Mead elevation (this would visually demonstrate adaptive exploitation — R1), and (b) a panel figure showing EHE across six models (Table 3 data as a forest plot or dot plot with CIs — R4). Figures make the paper more accessible to scanning readers and are expected by NW reviewers.

### P4. [IMPORTANT] FQL result introduced in Discussion without Results support (Issue 22)
The FQL comparison (r = 0.057 vs 0.547) is a key finding that isolates the representational contribution of natural-language reasoning. It currently appears only in the Discussion and SI S11. Add at least one sentence in Results (R1 or R4) referencing this finding with a pointer to SI S11.

### P5. [MODERATE] BRI/IBR dual naming confusion (Issue 37)
Two acronyms (BRI, IBR) for related-but-distinct metrics across domains will confuse readers and reviewers. Unify the terminology or add a clear cross-reference on first use of each. Consider a single sentence in Methods: "We use BRI (fraction of rational decisions) for irrigation and IBR (fraction of irrational decisions) for flood; BRI ≈ 1 − IBR, though the domain-specific definitions differ (see Validation Protocol)."

---

## Additional Recommended Fixes (Lower Priority)

| Priority | Issue # | Fix |
|----------|---------|-----|
| Moderate | 1 | Revise abstract opening to lead with finding, not method |
| Moderate | 9 | Trim P7 results preview in Introduction |
| Moderate | 12 | Harmonize "77–82% of decisions" vs "of agents" |
| Moderate | 17 | Align Table 2 IBR rounding with Table S1 |
| Moderate | 18 | Change abstract "below 1.7%" to "at or below 1.7%" |
| Low | 5 | Split long P3 in Introduction |
| Low | 15 | Add "(Supplementary Section S3)" after first-attempt EHE numbers |
| Low | 16 | Trim cognitive frames list in R3 |
| Low | 21 | Shorten Ostrom repetition in Discussion P2 |
| Low | 26 | Add temperature sensitivity caveat in Methods |
| Low | 27 | Remove Group C description from Methods |
| Low | 33 | Add model-specificity caveat to S5 premium doubling |

---

*Review prepared by expert panel. All page/line references are to the v14 drafts dated 2026-02-22.*
