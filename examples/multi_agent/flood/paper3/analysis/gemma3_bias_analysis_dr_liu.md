# Gemma 3 4B Behavioral Bias Analysis: 400-Agent Flood ABM Pilot

**Author**: Dr. Kevin Liu (LLM Behavior Specialist)
**Date**: 2026-02-15
**Scope**: Diagnosis of two failing L2 benchmarks — `do_nothing_postflood` (0.334 vs 0.35) and `mg_adaptation_gap` (0.045 vs 0.05) — with actionable prompt, governance, and architecture recommendations.

---

## 1. CP Collapse to Medium: Central-Tendency Bias in Ordinal Rating

**Diagnosis.** The 89.8% CP=M finding is a textbook manifestation of **central-tendency bias** in small language models. Gemma 3 4B, like most sub-7B parameter models, has a well-documented tendency to default to the middle option on ordinal scales when the discriminating signal is ambiguous. The PMT construct definition in the prompt reads:

> *"CP (Coping Perception): How confident are you that mitigation options (insurance, elevation, buyout) are effective and affordable?"*

This conflates two orthogonal dimensions — **efficacy** (does the option work?) and **affordability** (can I pay for it?). A low-income agent may believe insurance is highly effective but completely unaffordable, producing a cognitively incoherent rating. Faced with this tension, Gemma defaults to M as a "safe" middle-ground response. The model is not reasoning through the construct — it is resolving ambiguity with the least committal token.

Additionally, the rating scale (VL/L/M/H/VH) is presented as a flat enumeration without anchoring examples. Small LLMs are highly sensitive to the token distribution of their training data, where "Medium" is the most frequent descriptor in review/rating contexts.

**Recommendations:**

- **[PROMPT] Split CP into two sub-constructs**: Replace the single CP field with `cp_efficacy` ("How effective would the best available option be at reducing your flood risk?") and `cp_affordability` ("Can you realistically afford the best available option this year given your income?"). Force the model to commit on each dimension separately. The governance layer can then combine them: true high coping requires BOTH high efficacy AND high affordability. *Expected impact*: CP=H should increase for NMG agents (high efficacy + affordable) while CP=L increases for MG agents (high efficacy + unaffordable), restoring the adaptation gap.

- **[PROMPT] Add anchored examples to the rating scale**: Replace the bare `VL=Very Low, L=Low, M=Medium, H=High, VH=Very High` with context-specific anchors. For CP: "VL = I cannot afford any option and doubt they would help; L = Options exist but are out of reach financially; M = I could afford basic insurance but not structural changes; H = I can afford insurance and possibly elevation with subsidies; VH = I can comfortably afford any option including elevation." Anchoring forces the model to pattern-match against concrete situations rather than defaulting to the center.

---

## 2. Action Bias: Insurance Anchoring and Sycophantic Option Selection

**Diagnosis.** The H_M quadrant (TP=High, CP=Medium) producing 328 insurance / 280 elevate / 38 do_nothing reveals two distinct mechanisms:

(a) **Positional and informational anchoring.** The prompt provides extensive financial detail for insurance (premium, deductible, coverage limits) and elevation (three cost tiers, subsidy math, burden percentage). The do_nothing option receives zero concrete detail — it is defined only by absence. Gemma, which learns to weight tokens proportional to their informational density in context, naturally gravitates toward the options with the richest description. The skill registry description for do_nothing ("Take no protective action this year. This includes waiting for more information...") is framed as a list of rationalizations, not as a positive choice.

(b) **RLHF-inherited helpfulness bias.** Gemma 3 was fine-tuned with RLHF that rewards "helpful" completions. When role-playing a flood-vulnerable agent, "taking action" is parsed as the "helpful" response. Do_nothing reads as refusal-to-engage, which RLHF penalizes. This is not classical sycophancy (agreeing with the user) but rather **proactive helpfulness bias** — the model conflates "being a good agent" with "taking protective action."

**Recommendations:**

- **[PROMPT] Elevate do_nothing to a first-class rational choice**: Add a dedicated subsection: `### WHY DO_NOTHING CAN BE THE BEST CHOICE\n- You have competing financial priorities (rent, food, medical bills)\n- Your flood zone is LOW or MODERATE and insurance premiums exceed expected losses\n- You were not personally flooded and have no direct damage experience\n- Your income makes even basic insurance a financial strain (>5% of income)\n- Behavioral research shows 60-70% of households take no action in any given year — this is the empirical norm, not a failure.` This gives do_nothing equivalent informational weight to the action options.

- **[PROMPT] Add post-flood do_nothing normalization**: In the DECISION CALIBRATION CONTEXT section, add: "After a flood, 35-65% of households STILL choose do_nothing. This is especially common when: the flood caused minor damage (<$5K), the household has limited savings, or the household believes this was a rare event. Do not assume that experiencing a flood automatically requires taking action." This directly targets the `do_nothing_postflood` benchmark.

- **[GOVERNANCE] Add a WARNING-level rule for post-flood action without damage justification**: If `flood_count > 0` AND `cumulative_damage < 5000` AND the agent selects an action other than do_nothing, issue a WARNING: "You experienced flooding but sustained minimal damage. Many households in your situation choose to wait. Are you sure this action is warranted?" WARNINGs do not block (per the project's lesson that WARNING=0% behavior change for small LLMs), but they add friction tokens that may shift the probability distribution. If this proves insufficient, escalate to ERROR-level gating.

---

## 3. MG Sympathy Bias: Prosocial Overcompensation

**Diagnosis.** The inverted adaptation gap (MG=66% vs NMG=61.5%) is driven almost entirely by MG agents buying insurance at 58% vs NMG at 53%. This is **prosocial compensation bias**: Gemma's RLHF training includes alignment toward protecting vulnerable populations. When the prompt states a low income and marginalized status, the model generates reasoning like "purchasing insurance is the most sensible immediate action" — interpreting its role as advocating for the agent's welfare rather than simulating realistic constrained behavior.

The sample trace is diagnostic: an MG renter with $27.5K income, zero prior floods, immediately buys insurance after a single flood event. Real-world data shows low-income renters are the LEAST likely to purchase flood insurance, not the most. The model is playing "helpful financial advisor" instead of "resource-constrained human."

**Recommendations:**

- **[PROMPT] Add income-burden framing for insurance decisions**: After the premium line in the renter prompt, add: `- Insurance as % of income: {premium_pct_income:.1f}%\n- Context: Households spending >3% of income on insurance premiums often lapse within 2 years. At your income level, ${current_premium:,.0f}/year represents a significant tradeoff against other necessities.` Making the tradeoff concrete counteracts the abstract "insurance is good" heuristic.

- **[ARCHITECTURE] Implement an insurance affordability gate for MG agents**: Add a soft governance rule: if `is_mg=True` AND `premium / income > 0.04` (4%), issue an ERROR blocking insurance purchase with message: "At your income level, this premium represents a severe financial burden. Most households in your situation cannot sustain this expense." This is the insurance-side equivalent of the existing INCOME_GATE for elevation. Without this, the governance layer asymmetrically constrains MG elevation (via INCOME_GATE) while leaving MG insurance unconstrained — creating the exact inversion observed.

- **[PROMPT] Remove implicit vulnerability-as-motivation framing from MG memory tags**: The config shows MG agents retrieve memories tagged with `vulnerability`, `financial_hardship`, `financial_barrier`, `cost_concern`. These tags, when surfaced as memory text, prime the model to generate compensatory reasoning ("despite my hardship, I must protect myself"). Consider replacing `vulnerability` with `resource_limit` and `financial_hardship` with `budget_constraint` — framing that emphasizes constraint rather than evoking sympathy.

---

## 4. Do-Nothing Avoidance: The Structural Deficit

**Diagnosis.** Only 5% do_nothing in the dominant H_M quadrant. Beyond the RLHF helpfulness bias discussed above, there is a structural issue: the governance rules actively push agents AWAY from do_nothing. The `renter_inaction_moderate_threat` rule issues a WARNING when TP=H/VH and CP=M — which is exactly the H_M quadrant. While WARNINGs theoretically have 0% effect on small LLMs, they still appear in the prompt context on retries, adding "consider taking protective action" language that further suppresses do_nothing.

Additionally, the `owner_inaction_high_threat` rule blocks do_nothing at TP=VH+CP=VH, and `owner_complex_action_low_coping` blocks elevation/buyout at CP=VL/L. But there is NO rule that blocks or discourages action at LOW threat. An agent with TP=L can still freely choose elevation or insurance without governance friction.

**Recommendations:**

- **[GOVERNANCE] Convert `renter_inaction_moderate_threat` from WARNING to INFO**: Since the project has established that WARNINGs have 0% behavior change on Gemma 3, this rule serves no calibration purpose. Downgrading to INFO removes the "consider taking protective action" language from retry prompts without losing the audit trail.

- **[GOVERNANCE] Add low-threat action skepticism rule**: For TP=VL/L, add a WARNING (or ERROR if needed) that blocks elevate_house and buyout_program: "With low perceived threat, major structural actions are not justified. If you genuinely perceive low flood risk, do_nothing or basic insurance are the appropriate responses." This creates symmetric governance pressure — currently the rules only push agents toward action, never toward inaction.

---

## 5. Summary of Prioritized Recommendations

| # | Type | Fix | Target Benchmark | Effort |
|---|------|-----|-------------------|--------|
| 1 | **[ARCHITECTURE]** | Insurance affordability gate for MG (premium/income > 4%) | mg_adaptation_gap | Low |
| 2 | **[PROMPT]** | Elevate do_nothing with dedicated rationale subsection | do_nothing_postflood | Low |
| 3 | **[PROMPT]** | Add post-flood do_nothing normalization language | do_nothing_postflood | Low |
| 4 | **[PROMPT]** | Split CP into cp_efficacy + cp_affordability | Both (indirect) | Medium |
| 5 | **[PROMPT]** | Add anchored examples to PMT rating scale | CP collapse | Medium |
| 6 | **[PROMPT]** | Add income-burden framing for insurance | mg_adaptation_gap | Low |
| 7 | **[GOVERNANCE]** | Downgrade renter_inaction_moderate_threat to INFO | do_nothing_postflood | Trivial |
| 8 | **[GOVERNANCE]** | Add low-threat action skepticism rule | do_nothing_postflood | Low |
| 9 | **[PROMPT]** | Reframe MG memory tags (vulnerability -> resource_limit) | mg_adaptation_gap | Low |

**Implementation order**: Items 1, 2, 3, and 7 should be applied first as a batch — they are low-effort, independent, and directly target the two failing benchmarks. Run a 28-agent, 3-year smoke test after this batch. If benchmarks pass, defer items 4-5 (CP split) to avoid introducing new failure modes before the 400x13yr production run.

**Risk note**: Item 1 (insurance affordability gate) creates a new deterministic constraint. Verify that it does not push overall insurance rates below the `insurance_sfha` benchmark (currently at 0.6027, already slightly over threshold). The gate should apply ONLY to MG agents, not globally.
