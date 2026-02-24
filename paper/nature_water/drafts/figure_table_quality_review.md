# Figure and Table Quality Review — Nature Water v14

**Reviewer**: Data visualization expert (Claude Opus 4.6)
**Date**: 2026-02-24
**Scope**: 2 main-text figures, 3 main-text tables
**Standard**: Nature Water Analysis format

---

## Figure 1 (Fig2_irrigation.png): 4-Panel Irrigation Domain

### 1. Information Density

| Panel | Verdict | Notes |
|-------|---------|-------|
| **a** Lake Mead elevation | EARNS ITS SPACE | Shows reservoir trajectory divergence with shortage tiers; provides physical context for panels b-d. However, it only shows 3 of 4 conditions (FQL missing). |
| **b** Basin demand ratio | EARNS ITS SPACE | Core evidence for adaptive exploitation finding. All 4 conditions shown, clear temporal separation. |
| **c** Action distribution | EARNS ITS SPACE | Directly supports the "behavioural monoculture" vs diversity narrative. FQL's 84% validator-blocked maintain is visually striking. |
| **d** Diversity vs coupling scatter | EARNS ITS SPACE | Novel visualization synthesizing two metrics into a single space; the "adaptive vs arbitrary diversity" quadrant framing is the paper's key conceptual contribution. |

**Assessment**: All four panels are well-justified. No redundancy. The 2x2 layout tells a coherent story: physical system (a) -> agent demand (b) -> action distribution (c) -> synthesis (d).

### 2. Readability at Print Size

- **Figure size**: 7.09 x 5.8 inches (full-width). Adequate for 2-column layout.
- **Font sizes**: Base 7.5 pt, axis labels 8 pt, tick labels 7 pt, legend 6.5-7 pt. These are at the lower bound of legibility; Nature Water typically requires minimum 5 pt after reduction, so these should survive.
- **ISSUE**: Panel (d) annotation labels ("FQL (2-action)", "A1 (no ceiling)", etc.) at 6 pt with thin 0.5 pt arrows. At 50% reduction for single-column reproduction, these would be 3 pt -- below legibility threshold. **Recommend**: Increase annotation font to 7 pt minimum or use a legend instead of per-point labels.
- **ISSUE**: Panel (a) shortage tier labels ("Tier 1", "Tier 2", "Tier 3") at 6 pt in gray. At print size these may be nearly invisible. **Recommend**: Increase to 7 pt or darken the gray.
- **ISSUE**: Panel (c) percentage labels inside bars (e.g., "23%", "30%") at 6.5 pt are acceptable but tight. The narrower bars (e.g., FQL's 11% segment) may be hard to read.

### 3. Self-Containment (Caption Analysis)

The caption (from `compile_paper.py` lines 402-414) reads:

> "Figure 1. Adaptive exploitation under institutional governance (irrigation domain, 78 agents x 42 years, 3 seeds). (a) Lake Mead elevation... (b) Basin demand ratio... (c) Action distribution... (d) Strategy diversity versus demand-Mead coupling..."

**ISSUES**:
- Caption does NOT define "demand ratio" (total request / total water right). The table note does, but a reader examining the figure alone would not know. **Recommend**: Add "(request / baseline allocation)" after "Basin demand ratio" in the panel (b) description.
- Caption says "shaded bands show +/- 1 s.d. across 3 seeds" -- good.
- Caption does NOT explain what "A1 (no ceiling)" means. It says "A1 (green)" but a reader unfamiliar with the ablation nomenclature would be lost. **Recommend**: Add "A1 removes the demand-ceiling validator" parenthetically.
- Caption does NOT define "strategy diversity" (normalized Shannon entropy). It is defined in the Table 1 note but not in the figure caption. **Recommend**: Add "(normalized Shannon entropy, H/log2(k))" to panel (d) description.
- The quadrant labels "Arbitrary diversity" and "Adaptive diversity" in panel (d) are NOT explained in the caption. **Recommend**: Add a sentence: "Left quadrant = high diversity without drought coupling; right quadrant = diversity coupled to reservoir state."
- Panel (a) omits FQL but panel (b) includes it. The caption does not explain this asymmetry. **Recommend**: Add "FQL not shown in (a) as its reservoir trajectory overlaps A1."
- **Missing from caption**: What the individual points in panel (d) represent (each point = one seed). The caption says "Pearson r" but not "each point represents one of 3 seeds."

### 4. Color + Symbol Redundancy

- **Panels (a-b)**: Line style distinguishes FQL (dashed) from LLM conditions (solid), but the three LLM conditions are distinguished by color ONLY. All use solid lines with identical line width (1.0 pt). **FAIL**: A reader printing in grayscale cannot distinguish governed (blue) from ungoverned (vermillion) from A1 (green).
- **Panel (c)**: The 5 skill colors use Okabe-Ito palette (good for colorblindness) but NO pattern/hatch fill. However, percentage labels partially compensate.
- **Panel (d)**: Uses different markers per condition (circle, square, diamond, triangle). **PASS**: Shape alone distinguishes conditions, even in grayscale.
- **Recommendation for panels (a-b)**: Add distinct line styles (solid, dotted, dash-dot) or markers at intervals (every 5th year) to enable grayscale discrimination. This is a CRITICAL fix for Nature Water, which requires figures to be interpretable without color.

### 5. Statistical Clarity

- **Uncertainty shown**: Shaded +/- 1 s.d. bands in panels (a) and (b). Good.
- **Sample size**: Caption states "3 seeds" and "78 agents x 42 years." Adequate.
- **Panel (c)**: Shows pooled action shares across all seeds. No uncertainty bars. With n=3 seeds, per-seed bars with error bars would be impractical. Acceptable as-is, but could note "pooled across 3 seeds" more explicitly.
- **Panel (d)**: Individual seed points shown (3 per condition = 12 total points). No summary statistics overlaid (no mean marker or ellipse). Acceptable -- the spread IS the uncertainty.
- **ISSUE**: Panel (d) y-axis "Strategy diversity" is computed differently for FQL (H/log2(2)) versus LLM conditions (H/log2(5)). The normalization makes them comparable (both 0-1 scale), but this is a methodological subtlety that the caption does not mention. **Recommend**: Add a note that FQL uses 2-action normalization while LLM conditions use 5-action normalization, or flag this in the table note.

### 6. Panel Label Format

- Labels are lowercase bold "a", "b", "c", "d" without parentheses. Positioned at (-0.12, 1.05) in axes coordinates.
- **PASS**: Matches Nature Water requirements (lowercase bold, no parentheses).

### 7. Missing Information

1. **No formal statistical test for between-condition differences.** The scatter plot visually separates conditions but no p-values or confidence intervals are shown for between-group comparisons. Reviewers may ask for Welch t-tests or bootstrap CIs on the governed-vs-ungoverned differences in panels (b) and (d).
2. **Panel (a) omits FQL**: The FQL reservoir trajectory is not shown. If it differs from A1, this omission could mask relevant information.
3. **No time-varying uncertainty in panel (c)**: Skill distributions are aggregated over all 42 years. A reviewer might ask whether the distribution shifts over time (e.g., do governed agents shift from increase-heavy early to decrease-heavy late?).
4. **Panel (d) lacks axis limits consistency**: The x-axis range appears to be approximately -0.3 to 0.8, auto-scaled. This means the quadrant boundary at x=0 is not centered. This is fine for data display but could mislead a casual reader about the "quadrant" framing.

---

## Figure 2 (Fig3_cumulative_adaptation.png): 3-Panel Flood Adaptation

### 1. Information Density

| Panel | Verdict | Notes |
|-------|---------|-------|
| **a** Rule-based PMT | EARNS ITS SPACE | Baseline comparison. Shows rapid convergence to elevation-dominated protection. |
| **b** Ungoverned LLM | EARNS ITS SPACE | Shows stagnation in "No protection." Clear contrast with (a) and (c). |
| **c** Governed LLM | EARNS ITS SPACE | Shows diverse protection mix including relocation (pink). Key finding. |

**Assessment**: Three-panel comparison is well-justified and compact. The visual contrast between panels is immediately striking: (a) is mostly green, (b) is mostly gray, (c) is a diverse mix. This figure communicates the main finding effectively at a glance.

### 2. Readability at Print Size

- **Figure size**: 7.09 x 3.0 inches (full-width, short). Good proportions for a 3-panel horizontal layout.
- **Font sizes**: Consistent with Figure 1 (7-8 pt range). Acceptable.
- **ISSUE**: The panel descriptors ("Rule-based PMT", "Ungoverned language agent", "Governed language agent") are at 7.5 pt as `set_title`. They are placed above the panel with `pad=12`. This should be legible.
- **ISSUE**: The shared legend at the bottom uses 7 pt font with 5 items in one row (`ncol=5`). With hatching patterns, this may be cramped at print size. **Recommend**: Verify the legend does not clip or overlap. Consider reducing to `ncol=3` with two rows if needed.
- **ISSUE**: X-axis labels (years 1-10) appear directly on bars. At this figure width (~2.3 inches per panel), 10 labels in 7 pt should be legible.

### 3. Self-Containment (Caption Analysis)

The caption (from `compile_paper.py` lines 418-424) reads:

> "Figure 2. Flood-adaptation trajectories across agent types (100 agents x 10 years). Bars show 3-seed means. (a) Rule-based PMT agents converge rapidly... (b) Ungoverned language agents stagnate... (c) Governed language agents develop diverse mix... Insurance requires annual renewal; elevation is permanent."

**ISSUES**:
- Caption does NOT define what the y-axis represents beyond "Share of agents (%)." It should clarify this is the cumulative protection STATE (not the action taken that year). An agent counted as "Insurance + Elevation" is one who currently holds both, not one who bought both this year. **Recommend**: Add "Each bar shows the distribution of cumulative protection states at year-end."
- Caption does NOT define PMT (Protection Motivation Theory). A reader encountering this figure first would not know what "Rule-based PMT" means. **Recommend**: Add "(Protection Motivation Theory)" on first use.
- Caption does NOT mention the LLM model used. It says "100 agents x 10 years" but not "Gemma-3 4B." **Recommend**: Add model name for reproducibility.
- "Insurance requires annual renewal; elevation is permanent" is a good clarification. But "Relocated" is not explained. **Recommend**: Add "Relocated agents exit the decision pool."
- **Missing from caption**: Flood hazard characterization. How often do floods occur? What severity? Without this, the reader cannot assess whether 35.6% inaction (panel c) is reasonable.

### 4. Color + Symbol Redundancy

- **PASS**: The script applies BOTH color AND hatch patterns to all five categories:
  - No protection: gray, no hatch
  - Insurance only: blue, `///` hatch
  - Elevation only: vermillion, `...` hatch
  - Insurance + Elevation: green, `xxx` hatch
  - Relocated: reddish purple, `\\\` hatch
- This is a model implementation. All categories are distinguishable in grayscale via hatch pattern alone. **Excellent**.

### 5. Statistical Clarity

- **Uncertainty shown**: Caption says "3-seed means." However, the bars themselves show only the mean, with NO error bars or indication of seed-to-seed variability. **ISSUE**: With only n=3 seeds, reviewers may want to see error bars or at minimum individual seed lines overlaid. **Recommend**: Add thin error whiskers on each stacked segment, or overlay individual seed markers.
- **Sample size**: 100 agents x 10 years x 3 seeds = 3,000 agent-year observations per condition. Stated in caption.

### 6. Panel Label Format

- Labels are lowercase bold "a", "b", "c" without parentheses. Positioned at (-0.05, 1.08) in axes coordinates.
- **PASS**: Matches Nature Water requirements.

### 7. Missing Information

1. **No error bars on stacked bars.** This is the most likely reviewer criticism. The 3-seed means are shown but variability is invisible.
2. **No flood event indicators.** The figure shows protection states but not WHEN floods occurred. Adding tick marks or indicators along the x-axis for flood years would help readers understand the causal link (e.g., "agents adopted insurance AFTER Year 3 flood").
3. **The "Relocated" category appears only in panel (c).** This is a feature, not a bug (it supports the paper's finding), but a reviewer might question whether relocation was available to all agent types. The caption should clarify that all three conditions had access to the same action set.
4. **No indication of the direction of transitions.** Are agents moving from "No protection" to "Insurance" over time, or cycling? The stacked bar format does not reveal individual trajectories. Consider noting this limitation or pointing to SI for transition matrices.

---

## Table 1: Water-System Outcomes (Irrigation)

### 1. Completeness

- Contains 7 metrics across 4 conditions. All metrics referenced in the R1 and R2 result paragraphs are present.
- **ISSUE**: The text references "mean demand ratio of 0.394 compared with 0.288" -- present in table. Good.
- **ISSUE**: The text references "r = 0.547 governed versus 0.378 ungoverned" -- present in table. Good.
- **ISSUE**: BRI is listed for Governed (58.0%) and Ungoverned (9.4%) but NOT for A1 or FQL. The dashes are explained in the table note. Acceptable, but a reviewer may ask why A1's BRI is not computed (it uses the same 5-action LLM).
- **MISSING**: The text mentions "first-attempt strategy diversity 0.761 governed versus 0.640 ungoverned" (R3 paragraph) but this metric is NOT in Table 1. It is apparently in SI. Consider adding a row or footnote reference.

### 2. Clarity

- Column headers are clear: Governed, Ungoverned, A1 (No Ceiling), FQL Baseline.
- Row labels are descriptive. Units specified for Mead elevation (ft) and shortage years (/42).
- **ISSUE**: "Mean demand ratio" does not specify units or definition in the table itself. Defined in the note below. Acceptable.
- **ISSUE**: "Demand-Mead coupling (r)" -- the parenthetical "(r)" is helpful but might be confused with a reference. Consider "Demand-Mead coupling (Pearson r)".
- **ISSUE**: "42-yr mean Mead elevation (ft)" and "Min Mead elevation (ft)" lack +/- s.d. unlike other rows. If these are per-condition single values (not averaged across seeds), explain. Actually, the 42-yr mean Mead shows single values (1,094, 1,173, etc.) while Min Mead shows "1,002 +/- 1". This inconsistency suggests the 42-yr mean is rounded or pooled. **Recommend**: Add +/- s.d. to the 42-yr mean row for consistency, or add a note explaining the reporting convention.

### 3. Statistical Reporting

- Most values reported as mean +/- s.d. (3 seeds). Good.
- **ISSUE**: BRI is reported as a single percentage (58.0%, 9.4%) without +/- s.d. or CI. With n=3 seeds, variability should be reported. **Recommend**: Add +/- s.d.
- **ISSUE**: No p-values for between-condition comparisons. The text makes implicit comparisons (governed > ungoverned) but no formal tests are reported in the table. This may be acceptable for an Analysis-format piece, but reviewers accustomed to hypothesis testing may request them.
- The table note explains the null expectation for BRI (60% under uniform random). Good context.

### 4. Redundancy

- No obvious overlap with Tables 2 or 3 (which cover the flood domain).
- Strategy diversity appears in Table 1 (irrigation) and Table 2 (flood, Gemma-3 4B only) -- different domains, so not redundant.

### 5. Table Notes

- Comprehensive. Defines: demand ratio, demand-Mead coupling, strategy diversity, BRI, A1, FQL.
- **ISSUE**: Note says "See Supplementary Table 6 for additional water-system metrics." This is helpful cross-referencing.
- **ISSUE**: The note says "BRI = Behavioural Rationality Index" but the table header says "Behavioural Rationality (BRI, %)". The term "index" vs "percentage" is slightly inconsistent. Ensure the Methods section uses consistent terminology.
- **ISSUE**: The note mentions "relationship to IBR used in the flood domain" but does not explain the relationship directly. A reader comparing Tables 1 and 2 might be confused that one uses BRI and the other IBR. **Recommend**: Add a brief clarification: "BRI measures rational behaviour (higher = better); IBR measures irrational behaviour (lower = better). They are conceptual complements, not arithmetic inverses."

---

## Table 2: Strategy Diversity (Flood Domain, Gemma-3 4B Only)

### 1. Completeness

- Three conditions, each with: strategy diversity, IBR, and per-action breakdowns. All referenced in R3 text.
- **ISSUE**: The text says "governed language agents (0.636 +/- 0.044) exceeded rule-based PMT agents (0.486 +/- 0.011), which exceeded ungoverned language agents (0.307 +/- 0.059)" -- all present. Good.
- **ISSUE**: The text says "85.9% inaction in flood" for ungoverned -- present in the do_nothing column (85.9%). Good.

### 2. Clarity

- Headers are clear. Action percentages shown as individual columns.
- **ISSUE**: "IBR (%)" is defined in the note but the values (0.86, 0.0, 1.15) are given as raw numbers, not with "%" in the cells. The "0.0" for rule-based PMT is deterministic (no irrationality by design), which is fine but might benefit from a note.
- **ISSUE**: The action percentages do not have +/- s.d. They appear to be pooled across 3 seeds. This is inconsistent with strategy diversity, which shows per-seed s.d. **Recommend**: Either add +/- s.d. to action percentages or note explicitly "pooled across 3 seeds."

### 3. Statistical Reporting

- Strategy diversity: mean +/- s.d. (3 runs). Good.
- IBR: Single values without s.d. Same concern as BRI in Table 1.
- No formal statistical comparisons between conditions. Given n=3, consider Welch t-test or permutation test, or at minimum confidence intervals.

### 4. Redundancy

- Strategy diversity for Gemma-3 4B also appears in Table 3 (first row). The values should match: Table 2 shows 0.307/0.636; Table 3 shows 0.307/0.636. **CONSISTENT**. Slight redundancy, but Table 2 adds action breakdowns not in Table 3, while Table 3 adds multi-model comparison. Acceptable.

### 5. Table Notes

- Comprehensive. Defines strategy diversity, IBR, action counting conventions.
- "Combined insurance-and-elevation events (<1%) are counted as elevation" -- good methodological detail.
- "Post-relocation agent-years excluded" -- important for interpreting the denominators.
- **ISSUE**: The note says "IBR = Irrational Behavior Rate" but Table 1 uses "BRI = Behavioural Rationality Index." The note explains the IBR definition but does not clarify the BRI/IBR relationship. **Recommend**: Cross-reference Table 1 note.

---

## Table 3: Governance Effect Across Six Models (Flood Domain)

### 1. Completeness

- Six models, each with: ungoverned strategy diversity, governed strategy diversity, delta, 95% CI. All referenced in R4 text.
- **ISSUE**: Text says "positive governance effects on strategy diversity for five of six models, with three statistically significant." The CIs let readers determine significance (CI excludes 0), but the text does not directly flag which three are significant. **Recommend**: Bold the significant deltas or add an asterisk column.

### 2. Clarity

- Headers are clear and unambiguous.
- **ISSUE**: Column alignment is specified as center (`:--:`) in markdown. In Word output, verify this renders correctly.
- Model names (Gemma-3 4B, 12B, 27B; Ministral 3B, 8B, 14B) are clear and ordered within families.

### 3. Statistical Reporting

- Mean +/- s.d. per condition: Good.
- 95% CIs from Welch t-distribution: Appropriate for n=3 with unequal variances. Good.
- **ISSUE**: CIs are reported but p-values are not. Adding p-values would strengthen the table (or at least significance indicators like * for p < 0.05, ** for p < 0.01).
- **ISSUE**: With n=3 per condition, the Welch t-distribution has very few degrees of freedom (df approximately 2-4). CIs will be wide. This is transparent (the CIs are shown), but a reviewer might question the statistical power. **Recommend**: Note the degrees of freedom or acknowledge low power in the table note.

### 4. Redundancy

- Gemma-3 4B row overlaps with Table 2 (strategy diversity values match). Minor redundancy, acceptable for readability.

### 5. Table Notes

- Defines strategy diversity, delta, CI method.
- "Post-relocation agent-years excluded" -- consistent with Table 2. Good.
- "Full IBR decomposition in Supplementary Table 1" -- good cross-reference.
- **MISSING**: No note about multiple comparisons. Six models are tested; if claiming "three of six significant," a reviewer may ask about family-wise error correction (e.g., Bonferroni, Holm). **Recommend**: Address this in the note or Methods section.

---

## Summary of Critical Issues (Prioritized)

### Must-Fix Before Submission

| # | Item | Figure/Table | Issue |
|---|------|-------------|-------|
| 1 | **Grayscale discrimination in Fig 1 panels a-b** | Fig 1 | Three solid lines distinguished by color ONLY. Add line styles or markers for grayscale. NW requires figures interpretable without color. |
| 2 | **No error bars in Fig 2** | Fig 2 | Stacked bars show 3-seed means with no variability indication. Add whiskers or overlay seed data. |
| 3 | **Fig 1 caption incomplete** | Fig 1 | Missing definitions: demand ratio, A1 ablation, strategy diversity formula, quadrant meaning, per-point seed explanation. |
| 4 | **BRI/IBR without s.d.** | Tables 1-2 | Reported as single values; should include +/- s.d. across 3 seeds. |

### Strongly Recommended

| # | Item | Figure/Table | Issue |
|---|------|-------------|-------|
| 5 | Fig 1d annotations too small (6 pt) | Fig 1 | Risk of illegibility at single-column size. Increase to 7+ pt. |
| 6 | BRI/IBR terminology inconsistency | Tables 1-2 | BRI (Table 1, higher=better) vs IBR (Table 2, lower=better). Clarify relationship explicitly. |
| 7 | Fig 2 caption: define PMT, model name, flood frequency | Fig 2 | Caption should be self-contained for readers who start at the figure. |
| 8 | 42-yr mean Mead without s.d. | Table 1 | Inconsistent reporting: some rows have s.d., this row does not. |
| 9 | Significance indicators in Table 3 | Table 3 | Bold or asterisk the three significant deltas; readers should not have to mentally check CI bounds. |
| 10 | Multiple comparisons not addressed | Table 3 | Six models tested; family-wise error rate uncontrolled. Note or adjust. |

### Minor / Nice-to-Have

| # | Item | Figure/Table | Issue |
|---|------|-------------|-------|
| 11 | Fig 1a tier labels in light gray 6pt | Fig 1 | May be invisible at print. Darken or enlarge. |
| 12 | Fig 2: no flood event indicators | Fig 2 | Adding flood-year markers on x-axis would aid interpretation. |
| 13 | Fig 2 caption: explain relocation exit | Fig 2 | "Relocated agents exit the decision pool" is important context. |
| 14 | Action percentages in Table 2 lack s.d. | Table 2 | Pooled across seeds without noting this. |
| 15 | Table 3 note: mention df or statistical power | Table 3 | n=3 gives df approx 2-4; CIs are necessarily wide. Acknowledge. |
| 16 | FQL normalization differs (H/log2(2) vs H/log2(5)) | Fig 1d / Table 1 | Caption/note should clarify different action-space normalization. |
| 17 | Explain why FQL omitted from Fig 1 panel a | Fig 1 | Caption should note this explicitly. |

---

## Overall Assessment

**Figure 1** is a strong, information-dense figure with a clear narrative arc. The main vulnerability is grayscale discrimination in line plots (panels a-b), which is a submission requirement for Nature Water. The caption needs expansion to be self-contained.

**Figure 2** is visually effective and immediately communicates the key finding. The use of color + hatch is exemplary. The main gap is the absence of any uncertainty indication on the stacked bars. Adding error bars to stacked bar charts is technically challenging; an alternative would be to show individual seed panels as small multiples in SI and note "see Supplementary Figure X for per-seed variation."

**Tables 1-3** are generally well-structured and contain the key metrics. The main issues are: (a) inconsistent reporting of s.d. across metrics (some rows have it, some do not), (b) the BRI/IBR naming split between domains creates unnecessary confusion, and (c) Table 3 would benefit from explicit significance markers.

The figures and tables together tell a coherent story. No major restructuring is needed -- the issues above are refinements that would strengthen the submission against likely reviewer critiques.
