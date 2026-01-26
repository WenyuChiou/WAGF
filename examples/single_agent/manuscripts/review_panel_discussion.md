# 🎓 Virtual Review Panel: Critiquing the First Edition Figures

**Date**: 2026-01-24
**Topic**: Data Visualization Audit (The "Broken" Figures)
**Status**: CRITICAL REVIEW - REJECTION LIKELY

---

## 👥 The Panel

1.  **Strict Methodologist (PI Persona)**: Obsessed with data completeness and comparability.
2.  **Visual Analytic Expert (Reviewer 3)**: Focuses on what the chart _actually_ says vs what we _want_ it to say.

---

## 🛑 Critique Session 1: The "Missing Data" Scandal (Figure 1)

**User (Self-Correction)**: "Figure 1 is useless because 8B Group C is missing. We can't compare stability if one bar is empty."

**Strict Methodologist**: "Agreed. This is a fatal flaw. You cannot claim 'Scalability' if you only show partial data.

- **The Problem**: The script plotted what was available, but 8B Group C is still _running_.
- **The Verdict**: DO NOT generate this plot until the experiment finishes. A placeholder plot with missing bars is worse than no plot—it implies zero data."

---

## 🛑 Critique Session 2: The "Broken" Trajectories (Figure 2 & 3)

**User**: "Figure 2 and 3 are completely broken."

**Visual Analytic Expert**: "Let's dissect _why_."

### Figure 2: The Logic Gap in TP Scores

- **Observation**: The lines might be flat or non-existent?
- **Root Cause**: The `TP_Score` mapping in `analyze_abc_metrics.py` is too simple. The models (especially 1.5B) might be outputting complex reasoning that the simple `safe_map` function is mapping to default `0.5`, leading to a flat line.
- **Fix Required**: We need to use the `ModelAdapter`'s robust parsing logic (or the `audit_errors.py` logic) to extract the _real_ TP, not just grep for 'High'/'Low'."

### Figure 3: The "Zero Cost" Fallacy

- **Observation**: The Governance Cost curve might be showing zeros or nonsensical spikes.
- **Root Cause**: The script counts `Validation FAILED` from `execution.log`.
  - _Issue_: If the log format changed (e.g., `[Governance:Retry]` vs `Validation FAILED`), the regex misses it.
  - _Issue_: 1.5B had "0 Parse Errors" but 25 Interventions. Did the script find those 25 lines?
- **Verdict**: The regex in `parse_execution_log_for_interventions` is too brittle. It failed to catch the actual intervention events we _saw_ in the terminal earlier.

---

## 🛠️ Remediation Plan (The "Fix It" Ticket)

1.  **Wait**: Stop analyzing incomplete runs (8B Group C).
2.  **Refine Parser**: Rewrite `analyze_abc_metrics.py` to use a robust regex for Audit Logs (`[Governance:Initial] ... Validation FAILED`) instead of simple string matching.
3.  **Trace Extraction**: For Figure 2, parse the JSONL traces directly for `threat_appraisal`, don't rely on the flattened CSV if the CSV normalizing logic is suspect.

**Action**: We pause visualization until 8B Group C completes (~2 hours). In the meantime, we fix the parsing script.
