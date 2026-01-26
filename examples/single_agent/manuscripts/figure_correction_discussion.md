# 📉 Figure Correction Session: Why are we still failing?

**Date**: 2026-01-24
**Topic**: Fixing Figure 2 (Empty) and Metric Selection for Figure 3
**Status**: Debugging & Refinement

---

## 🛑 Issue 1: Figure 2 is STILL Empty

**User**: "Figure 2 is empty. Nothing plotted."

**Data Analyst (Subagent)**: "I see my mistake.

1.  **Code Check**: My filter `subset = df[df['Group'].isin(['Group_B', 'Group_C'])]` might be too aggressive if the dataframe `df` itself is empty or if the `Group` column didn't match perfectly.
2.  **Trace Logic**: I parsed `household_traces.jsonl`. However, the file structure might have `step` instead of the expected `year` key, or `agent_id` is missing.
3.  **Diagnosis**: I need to print the `head()` of the dataframe to see if I actually loaded any data. If `df` is empty, of course the plot is blank."

**PI (Strict Methodologist)**: "Also, verify the JSON keys. Are you sure `threat_appraisal` is in `state`? Or is it in `agent_state`? Don't guess. Check a file."

---

## 🛑 Issue 2: Intervention Rate vs Count (Figure 3)

**User**: "Why use Intervention **Rate**?"

**Data Analyst**: "I divided by `Total Decisions` because 8B ran longer (10 years) than 1.5B (which I thought might have crashed). I wanted to normalize."

**PI (Strict Methodologist)**: "That's misleading if the denominator is shaky.

1.  **Simplicity First**: Just show access **Total Interventions Count**.
    - _Why_: Both are running 100 agents for 10 years (target). We care about the _absolute burden_ on the governance system.
    - _Correction_: If 1.5B triggered 138 interventions and 8B triggered 23, showing '138 vs 23' is powerful enough. Don't hide it behind a 0.001 rate."

---

## ⚠️ Issue 3: Survivorship Bias (Figure 2)

**User Check**: "Does the log only contain people who haven't elevated?"
**Methodologist Audit**:

- **Elevated**: Still present in logs (e.g., Agent 1 in Year 2). They continue to provide `threat_appraisal` and make decisions (Buy Insurance vs Do Nothing).
- **Relocated**: **ABSENT** from logs. Agent 6 relocated in Year 1 and disappears from Year 2 traces.
- **Implication**: Figure 2 (Panic Score) represents the **Average Panic of the RESIDENT Population**. It naturally excludes those who panicked enough to leave. This biases the score "downwards" (making the population look calmer than it technically was at the start). We must state this limitation clearly in the Figure Caption.

---

## 🛠️ The V3 Correction Plan

1.  **Fix Figure 2 Data Loading**:
    - Add print statements to debug _why_ the DataFrame is empty.
    - Verify the JSON path for `threat_appraisal`.
2.  **Fix Figure 3 Metric**:
    - Switch Y-Axis to **Total Intervention Count**.
    - Keep it simple.

**Action**: Rewrite script to V3.
