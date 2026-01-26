# 🩺 Data Analysis Post-Mortem: Why the Figures Failed

**Date**: 2026-01-24
**Analyst**: Subagent (Data Forensics)
**Status**: Root Cause Identified

---

## 🚨 The Incident

The "First Edition" figures were rejected by the review panel for being "broken" or "flat".

- **Figure 2 (Panic Trajectory)**: Showed flat lines at 0.5.
- **Figure 3 (Governance Cost)**: Showed zero or incorrect intervention counts.

## 🔍 Root Cause Analysis

### 1. The "N/A" Contamination (Figure 2 Failure)

- **Observation**: Inspecting `simulation_log.csv` (1.5B Group B) revealed `threat_appraisal` values were `N/A`.
- **Cause**: The `simulation_log.csv` is populated using the _raw_ response context from the LLM _before_ the `ModelAdapter` injects the corrected/normalized values into the main state.
- **Impact**: The analysis script mapped `N/A` to `0.5`, resulting in a meaningless flat line.
- **Fix**: Do not use `simulation_log.csv`. Instead, parse **`household_traces.jsonl`**, which records the _final_ state after all governance and adapter layers have processed the step.

### 2. The "Encoding Hell" (Figure 3 Failure)

- **Observation**: The diagnostic script crashed with `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff`.
- **Cause**: The `execution.log` file was generated via PowerShell's `Tee-Object` or redirection, which on Windows defaults to **UTF-16 LE** (BOM). The Python script tried to read it as `utf-8`.
- **Impact**: The script crashed silently (swallowed by a `try...except` block), returning 0 interventions.
- **Fix**: Update the file reading logic to detect encoding (try `utf-16`, then `utf-8`) or use `errors='ignore'`.

---

## 🛠️ The "Fix-It" Logic Plan (for Next Script)

The new `analyze_abcmetrics_v2.py` must:

1.  **Robust Log Parsing**:

    ```python
    try:
        with open(log_path, encoding='utf-16') as f: ...
    except UnicodeError:
        with open(log_path, encoding='utf-8') as f: ...
    ```

2.  **Rich Trace Extraction**:
    - Read `household_traces.jsonl` line-by-line.
    - Extract `state['threat_appraisal_label']` (if available) or `decision` reasoning.

3.  **Wait for 8B**:
    - Do not plot Figure 1 until 8B Group C exists.

## ✅ Conclusion

The data is valid; the _reader_ (script) was flawed. We can regenerate perfect figures once these two technical debt items are paid.
