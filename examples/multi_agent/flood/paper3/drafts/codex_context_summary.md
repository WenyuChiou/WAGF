# Paper 3 Context Summary for WRR Drafting

## Scope of this memo

This file is a drafting aid only. It summarizes the current interpretation from:

- `examples/multi_agent/flood/paper3/CLAUDE.local.md`
- `.ai/NEXT_TASK.md`
- `examples/multi_agent/flood/paper3/drafts/paper3_draft_v2.md` (especially Section 4.2 style)
- the requested RQ2 and RQ3 analysis tables

It does not draft the paper text itself.

## 1. Current understanding of the three RQs and their key findings

### RQ1

**Question:** Where do LLM household agents converge with and diverge from the traditional survey-calibrated Bayesian ABM, and what do the reasoning traces add?

**Current finding:** The two paradigms converge on rare or strongly constrained actions, but diverge on high-frequency behaviors where memory, barriers, and deliberation matter more.

- Convergence claims to carry into the RQ1 section:
  - Owner elevation: `1.3 pp` difference
  - Owner buyout participation: `0.5 pp` difference
  - Renter flood insurance / contents insurance: `3.6 pp` difference
- Divergence claims to carry into the RQ1 section:
  - Owner flood insurance: `15.6 pp` difference
  - Renter relocation: `20.8 pp` difference
  - Renter do-nothing: `20.2 pp` difference
- Mechanistic interpretation to preserve:
  - LLM reasoning traces expose an **adaptation deficit**: households often recognize risk but still do not act because of affordability, feasibility, and disruption barriers.
  - LLM traces also support an **intention-action gap** interpretation for relocation: protective intent in survey-style logic does not translate into executed relocation once practical barriers are considered.

### RQ2

**Question:** How do endogenous government subsidy and insurance pricing decisions alter adaptation outcomes, especially across marginalized and non-marginalized households, relative to fixed institutional assumptions?

**Current finding:** Institutional endogenization has little aggregate effect, but it materially changes the **equity channel** by reducing affordability blocking for marginalized owners. The strongest RQ2 result is not aggregate adoption; it is the widening gap between proposed and executed behavior after validators enforce affordability.

- Aggregate finding to preserve:
  - Owners: no significant Full vs Flat difference
  - Renters: statistically significant but substantively tiny Full vs Flat difference
- Equity finding to preserve:
  - Affordability blocking is heavily concentrated among marginalized households, and is much worse under fixed policies.
- Main interpretation to preserve:
  - The LLM does **not** meaningfully self-differentiate by income in proposed behavior.
  - The real MG/NMG gap emerges at execution, because validators impose binding affordability and feasibility constraints.

### RQ3

**Question:** Among psychological constructs that are not directly enforced by governance rules, do LLM agents exhibit theory-consistent construct-behavior relationships?

**Current finding:** RQ3 should be framed around **unconstrained or minimally constrained constructs**, especially stakeholder perception (SP) and place attachment (PA), not around TP-CP dynamics. Cross-sectional construct-action coherence is strong enough to support a standalone section, but the temporal dynamics are weak and should not be over-claimed.

- Safe positive findings:
  - Higher SP is associated with protective action, especially insurance.
  - Lower PA is associated with renter relocation.
  - MG owners show the most trapped profile: highest PA with lowest SP.
- Main interpretation to preserve:
  - SP and PA are the cleanest constructs for interpretation.
  - CP is contaminated by validator logic and should not anchor the theory claim.
  - Time trends are statistically significant mainly because `N` is large; effect sizes are weak.

## 2. Exact numbers to use for each RQ section

### RQ1 numbers to use

These come from the latest project context files provided for this task, not from older rerun notes.

- Convergence:
  - Owner elevation difference: `1.3 pp`
  - Owner buyout difference: `0.5 pp`
  - Renter contents insurance difference: `3.6 pp`
- Divergence:
  - Owner insurance difference: `15.6 pp`
  - Renter relocation difference: `20.8 pp`
  - Renter do-nothing difference: `20.2 pp`
- Reasoning trace support:
  - `67%` fatalism in do-nothing reasoning
  - `100%` of relocation decisions cite relocation barriers
  - `86%` cite memory-unique information
  - Gossip citation relative risk: `0.75` for protection, so gossip is negatively associated with protection

### RQ2 numbers to use

#### Aggregate Full vs Flat comparison

From `rq2_ablation_b_aggregate.csv`:

- Owners:
  - `chi2 = 2.549`
  - `p = 0.466492`
  - `dof = 3`
  - `Cramer's V = 0.0128`
  - Interpretation: not significant
- Renters:
  - `chi2 = 6.8528`
  - `p = 0.032505`
  - `dof = 2`
  - `Cramer's V = 0.021`
  - Interpretation: significant, but negligible effect size

#### Equity / affordability summary

From `rq2_equity_summary.csv`:

- Full condition, MG:
  - total rejections `886`
  - affordability rejections `100`
  - affordability rejection rate `2.56%`
  - executed owner insurance `31.69%`
  - executed elevation `0.92%`
  - executed buyout `0.23%`
  - executed do-nothing `67.15%`
- Full condition, NMG:
  - total rejections `734`
  - affordability rejections `0`
  - affordability rejection rate `0.00%`
  - executed owner insurance `40.74%`
  - executed elevation `2.69%`
  - executed buyout `1.56%`
  - executed do-nothing `55.00%`
- Flat condition, MG:
  - total rejections `820`
  - affordability rejections `247`
  - affordability rejection rate `6.33%`
  - executed owner insurance `32.23%`
  - executed elevation `0.85%`
  - executed buyout `0.26%`
  - executed do-nothing `66.67%`
- Flat condition, NMG:
  - total rejections `691`
  - affordability rejections `19`
  - affordability rejection rate `0.49%`
  - executed owner insurance `42.56%`
  - executed elevation `2.85%`
  - executed buyout `1.41%`
  - executed do-nothing `53.18%`

#### Proposed vs executed behavior

From `rq2_4cell_proposed_vs_executed.csv`:

- MG-Owner:
  - proposed do-nothing `44.51%` (`1736/3900`)
  - executed do-nothing `67.15%` (`2619/3900`)
  - do-nothing gap `22.64 pp`
  - proposed insurance `36.08%`
  - executed insurance `31.69%`
  - proposed elevation `17.13%`
  - executed elevation `0.92%`
  - proposed buyout `2.28%`
  - executed buyout `0.23%`
- NMG-Owner:
  - proposed do-nothing `36.18%` (`1411/3900`)
  - executed do-nothing `55.00%` (`2145/3900`)
  - do-nothing gap `18.82 pp`
  - proposed insurance `42.15%`
  - executed insurance `40.74%`
  - proposed elevation `17.77%`
  - executed elevation `2.69%`
  - proposed buyout `3.90%`
  - executed buyout `1.56%`
- MG vs NMG owner do-nothing gap:
  - proposed gap: `8.33 pp` (`44.51 - 36.18`)
  - executed gap: `12.15 pp` (`67.15 - 55.00`)
  - interpretation: validators widen the inequality gap by about `3.82 pp`
- Renters:
  - MG-Renter contents insurance: proposed `37.51%`, executed `34.23%`
  - NMG-Renter contents insurance: proposed `35.26%`, executed `31.10%`
  - MG-Renter relocation: proposed `3.64%`, executed `3.44%`
  - NMG-Renter relocation: proposed `3.82%`, executed `3.36%`
  - renter proposed-executed gaps are modest compared with owners

#### Policy trajectory

From `rq2_policy_trajectory.csv`:

- Subsidy trajectory, Full: `0.52, 0.58, 0.58, 0.63, 0.68, 0.68, 0.68, 0.68, 0.68, 0.65, 0.65, 0.65, 0.65`
- Subsidy trajectory, Fixed comparison series: `0.525, 0.55, 0.55, 0.6, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65, 0.65`
- CRS trajectory, Full: `0.15, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.18, 0.20, 0.20, 0.18, 0.18, 0.00`
- CRS trajectory, Fixed comparison series: `0.15, 0.175, 0.175, 0.175, 0.20, 0.20, 0.20, 0.20, 0.175, 0.175, 0.175, 0.175, 0.20`
- Interpretation to keep:
  - subsidy rises into a mid-period plateau, then slightly retracts
  - CRS discount increases late, then collapses to `0.00` in Year 13

### RQ3 numbers to use

#### Unconstrained / minimally constrained construct logic

From context files:

- SP has `0` blocking rules
- SC has `0` blocking rules
- PA has only `1` rule, and it blocks owner buyout at high PA; it does **not** govern renter relocation
- TP and CP should not be treated as emergent because validator rules explicitly use them

#### Main inferential statistics

From `rq3_construct_stats.csv`:

- Temporal trends:
  - Spearman `SP vs year = 0.0969`, `p = 8.433066253946232e-34`, `n = 15584`
  - Spearman `PA vs year = -0.0728`, `p = 8.970544597452136e-20`, `n = 15584`
- Cross-sectional construct-behavior findings:
  - MWU `SP insurance vs do-nothing`: statistic `30135406.0`, `p = 2.7530159586737e-279`, `n = 13700`
  - means reported in table interpretation: insurance `2.78`, do-nothing `2.45`
  - MWU `PA relocate vs do-nothing (renters)`: statistic `587342.5`, `p = 1.749679071119506e-05`, `n = 4959`
  - means reported in table interpretation: relocate `2.61`, do-nothing `2.76`
- Group contrasts:
  - MWU `SP MG vs NMG`: `p = 5.16678664010586e-17`, MG mean `2.57`, NMG mean `2.65`
  - MWU `PA MG vs NMG`: `p = 1.2392319886344944e-30`, MG mean `2.88`, NMG mean `2.76`
- Flood-dose response:
  - Spearman `SP vs flood_count = 0.4576`, `p = 0.0`, `n = 15584`
  - Spearman `PA vs flood_count = 0.0609`, `p = 2.8662333418966195e-14`, `n = 15584`

#### Action-level construct means

From `rq3_construct_action_profiles.csv`:

- `buy_contents_insurance`: TP `3.5786`, CP `2.6832`, SP `2.8044`, SC `2.3245`, PA `2.6156`
- `buy_insurance`: TP `3.5944`, CP `2.7679`, SP `2.7505`, SC `2.2134`, PA `2.9423`
- `buyout_program`: TP `3.8571`, CP `2.8487`, SP `2.7479`, SC `2.6261`, PA `3.0546`
- `do_nothing`: TP `2.9400`, CP `2.7574`, SP `2.4501`, SC `2.2098`, PA `2.8451`
- `elevate_house`: TP `3.8717`, CP `2.8465`, SP `2.7166`, SC `2.2125`, PA `2.8185`
- `relocate`: TP `3.7526`, CP `2.7904`, SP `2.8969`, SC `2.2921`, PA `2.6117`

#### CP reversal numbers

From `rq3_unconstrained_constructs.csv`:

- Owners, CP=H:
  - do-nothing `97.31%` (`217/223`)
  - insurance `2.69%` (`6/223`)
  - elevation `0.00%`
- Owners, CP=M:
  - do-nothing `59.54%` (`3487/5857`)
  - insurance `36.86%` (`2159/5857`)
  - elevation `2.41%` (`141/5857`)
- Renters, CP=H:
  - do-nothing `100.00%` (`43/43`)
  - contents insurance `0.00%`
  - relocate `0.00%`
- Renters, CP=M:
  - do-nothing `63.45%` (`3408/5371`)
  - contents insurance `32.53%` (`1747/5371`)
  - relocate `4.02%` (`216/5371`)
- Distribution note from context:
  - only `3.6%` of decisions report CP=H, versus roughly `72%` reporting CP=M

#### Trapped MG-owner profile

From the current project context:

- MG-Owner has highest PA: `3.01`
- MG-Owner has lowest SP: `2.55`
- This is the clearest 4-cell interpretation for "trapped adaptation."

#### Time-series values worth citing only if needed

From `rq3_sp_pa_yearly.csv`:

- Overall SP rises from `2.3568` in 2011 to `2.6981` in 2023
- Overall PA declines from `2.8883` in 2011 to `2.6931` in 2023
- MG SP rises from `2.3238` to `2.6483`
- NMG SP rises from `2.3896` to `2.7479`
- MG-Owner PA declines from `3.1570` to `2.9233`
- NMG-Owner PA declines from `3.0906` to `2.7367`
- These are descriptive support only; the paper should emphasize weak temporal effect sizes, not dramatic trajectories

## 3. Counterintuitive findings that must be addressed

### CP reversal

This is the most important counterintuitive result.

- Higher reported coping perception does **not** map to more protection.
- Instead, CP=H agents are more passive than CP=M agents.
- Interpretation to keep: Gemma 3 4B likely reads "high coping" as "I can manage the current situation" rather than "I am capable of undertaking costly protective action."
- This belongs in limitations / interpretation, not as evidence that PMT is wrong.

### Gossip as an inaction signal

- Gossip exposure is negatively associated with protection (`RR = 0.75`).
- This should not be framed as successful social learning.
- Better framing: gossip is transmitting **descriptive norms of inaction** or serving as post-hoc justification.

### Proposed MG/NMG behavior is too similar

- The LLM's proposed owner choices are relatively close across MG and NMG.
- The large equity gap appears after approval and execution, not in proposal.
- This is counterintuitive because one might expect income differences to appear directly in reasoning.
- Interpretation to keep: the small model has an RLHF-style protective action bias, so textual context alone does not create strong socioeconomic differentiation.

### Memory matters, but not cleanly

- `86%` of reasoning cites memory-unique information.
- But key numeric state variables overlap with non-memory agent state.
- Therefore memory can be discussed as **consistent with** persistence in insurance and risk salience, but not as an isolated causal mechanism.

### SP temporal trend is weak despite strong flood-dose response

- `SP vs flood_count` is strong (`rho = 0.4576`), but `SP vs year` is weak (`rho = 0.0969`).
- This suggests event-linked accumulation or cold-start adjustment, not a smooth trust-building dynamic.

## 4. Circular reasoning risks to avoid

### Do not claim emergent TP/CP-to-action alignment

- Validator rules explicitly use TP and CP to constrain allowable actions.
- Therefore TP-CP-action consistency is partly designed into the system.
- CACR is a governance/coherence diagnostic, not independent evidence that the model discovered PMT.

### Do not treat CP as an independent theoretical construct in RQ3

- CP is contaminated by validator logic and by the CP reversal problem.
- If CP appears, it should be discussed as a problematic construct interpretation, not the centerpiece of theory-consistent emergence.

### Do not use proposed actions as behavioral outcomes

- Proposed actions reflect intention.
- Executed actions reflect actual model behavior after feasibility and affordability constraints.
- All behavioral claims about inequality and realized adaptation should use **executed** actions.

### Do not over-claim memory causality

- Memory-rich reasoning is not the same as a clean memory treatment effect.
- Without a dedicated memory ablation, causal language should be avoided.

### Do not over-claim social influence causality

- Gossip citations are descriptive and may be rationalization rather than mechanism.
- Use "descriptive norm exposure" or "consistent with inaction norms," not "social learning caused."

### Do not oversell statistically significant weak trends

- With `n = 15,584`, very small effects become significant.
- RQ3 should prioritize effect size and interpretability over p-values alone.

## 5. Style notes from the existing draft

### Sentence structure

- Start each paragraph with a clear result claim in bold or emphatic topic-sentence form.
- Follow with one or two sentences of quantitative support.
- End with an interpretive sentence that links the pattern back to flood adaptation theory or model structure.
- Preferred structure in Section 4.2:
  - claim
  - quantitative comparison
  - mechanism / interpretation

### Terminology

- Use `LLM-ABM` and `traditional ABM` consistently.
- Use `do-nothing` in prose, even if tables use `do_nothing`.
- Use `contents insurance` for renters when clarity matters.
- Use `marginalized (MG)` and `non-marginalized (NMG)` on first mention in a section.
- Use `reasoning traces`, `adaptation deficit`, `intention-action gap`, `institutional endogenization`, and `structural plausibility`.
- Prefer `model diagnostics` over `validation` when characterizing behavior.

### Citation style

- WRR style in the draft is author-date in parentheses, e.g., `(Grothmann & Reusswig, 2006; Bubeck et al., 2012)`.
- Use citations to support interpretive framing, not every sentence with a number.
- Empirical or theoretical framing is usually attached at the end of a claim sentence.

### Tone and diction

- Formal, compact, and interpretive.
- Avoid hype language such as "proves," "demonstrates conclusively," or "human-like."
- Prefer cautious phrasing:
  - `suggests`
  - `is consistent with`
  - `indicates`
  - `reflects a structural difference`
  - `should be interpreted as`

### Numerical reporting conventions

- Report percentages with one decimal place when comparing rates.
- Report test statistics exactly as available from the analysis tables.
- Pair significance with effect size when available.
- For cross-model comparison, emphasize difference in percentage points and temporal pattern rather than formal significance testing.

## Bottom-line drafting guidance

- RQ1 should emphasize convergence/divergence plus what reasoning traces reveal.
- RQ2 should emphasize the equity channel and the proposed-to-executed gap, not aggregate institutional effects.
- RQ3 should emphasize SP and PA cross-sectional coherence, while explicitly avoiding circular TP/CP claims.
