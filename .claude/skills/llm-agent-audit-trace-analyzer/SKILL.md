---
name: llm-agent-audit-trace-analyzer
description: Turn raw WAGF audit traces (household_governance_audit.csv + raw/*.jsonl) into paper-ready governance metrics — IBR, EHE, rejection taxonomy, retry outcomes, model-condition comparisons. Use when the user says "analyze these traces", "compute governance metrics", "summarize rejection and retry outcomes", or hands over a results directory and asks "what does this say".
---

# WAGF: LLM Agent Audit Trace Analyzer

Convert raw WAGF audit artefacts into paper-ready governance metrics
and diagnostic tables. The skill is a thin orchestration layer over
existing, validated production scripts. It never reimplements the
formulas.

## When to Use

Load this skill when the user says any of:

- "Analyze these WAGF audit traces."
- "Compute governance metrics from JSONL logs."
- "Summarize rejection and retry outcomes by model and condition."
- "Give me an IBR / EHE table for these runs."
- "What does this audit log say about validator coverage?"

Do NOT use this skill for:

- Reproducibility verification → `abm-reproducibility-checker`.
- Designing a NEW experiment → `wagf-experiment-designer`.
- Generic CSV summarization → `data-analyst`.

## Inputs

The user must supply ONE of:

- A path to a single run directory (contains
  `household_governance_audit.csv` + `raw/*.jsonl`).
- A path to a results-tree root (e.g.
  `examples/single_agent/results/JOH_FINAL_v2/`) that the skill
  recurses to find runs.
- An explicit list of (model, condition, seed) triples.

If nothing supplied, ask. Do not invent a path.

## Workflow

1. **Discover runs**: walk the input path; for each run dir, record
   path, model, seed, condition (governed / disabled), and confirm
   the audit CSV is non-empty.
2. **Per-run metrics** (delegate to existing scripts; do NOT
   reimplement):
   - IBR = R1+R3+R4 fraction → use
     `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py:compute_ibr_components`
     (canonical formula, post-test-fix d8a5da4).
   - EHE = normalized Shannon entropy → use
     `examples/irrigation_abm/analysis/nw_bootstrap_ci.py:shannon_entropy`
     (or for irrigation, `examples/irrigation_abm/analysis/compute_ibr.py`).
   - Sentinel sweep → use
     `broker/components/analytics/audit.py:detect_audit_sentinels_in_csv`.
   - Temporal diagnostics M1/M2/M3 → call
     `examples/single_agent/analysis/compute_temporal_diagnostics.py`
     with `--gemma4-pipeline {v1,v2}` flag matched to the dataset.
   - Retry compliance Pattern A/B/C → call
     `examples/single_agent/analysis/compute_retry_compliance.py`.
3. **Aggregate**: group by (model, condition); compute mean ± s.d.
   across seeds; paired t-test for governed-vs-disabled; 95% CI.
4. **Detect anomalies**: any sentinel-flagged column not on the
   `broker/INVARIANTS.md` Invariant 4 reserved list → flag in caveats.
5. **Write artefacts** (see Outputs).

## Outputs

Write all under `analysis/` (create if missing):

- `governance_metrics.csv` — long-format table with rows = (model,
  condition, seed) and columns = (n_decisions, ibr, r1, r3, r4, ehe,
  rejection_rate, retry_rate, m1_rate, m2_rate, m3_rate).
- `governance_summary.md` — structured paper-ready report (see
  contract below).
- `rejection_taxonomy.csv` — per (model, condition, validator_rule)
  rejection counts and percentages.
- `retry_outcomes.csv` — Pattern A/B/C distribution per (model,
  condition).
- `model_condition_comparison.md` — pairwise governed-vs-disabled
  paired t-tests with ΔIBR, ΔEHE, 95% CI, p-value per model.

## Output structure contract

`governance_summary.md` MUST contain these four sections in order with
these exact headings:

1. `## Scope` — paths analysed, run counts per (model, condition)
2. `## Headline metrics` — one short narrative paragraph (≤120 words)
   stating the headline finding (e.g., "Validators reduced IBR from
   X% to Y% across N models; the reduction was significant (p<…) in
   K of N").
3. `## Metrics table` — the model × condition × metric matrix in
   markdown table form.
4. `## Caveats` — explicit list of: missing seeds, sentinel-flagged
   columns, partial runs, datasets that mix code versions (cross-link
   to `abm-reproducibility-checker` if any).

Plus `## Reproducible command list` at the end so the next reader can
re-run the analysis.

Never collapse these into prose. Never bury caveats inside the
narrative.

## Refusal Protocol

The skill MUST refuse to:

1. Invent a metric formula. If a metric the user asks for is not
   covered by the existing `compute_*.py` scripts, say so explicitly
   and ask whether to add a new script (out-of-scope for this skill).
2. Pool seeds across model versions or code versions without flagging.
   When pooling, the caveats section must list every distinct git
   commit observed across the pooled manifests.
3. Report a paired t-test p-value when n < 3 paired observations
   without an explicit warning.
4. Drop sentinel-flagged columns silently. Always list them in caveats.
5. Compare runs whose `agent_types_config` paths differ without a
   warning.

## Bundled resources

- `references/trace_schema.md` — the full
  `household_governance_audit.csv` column dictionary plus the raw
  `*.jsonl` record shape.
- `references/metrics_definitions.md` — exact formulas with file:line
  refs to the canonical implementations.
- `references/script_index.md` — which existing script computes which
  metric, with usage examples.
- `scripts/run_analyzer.py` — runnable wrapper that orchestrates the
  per-run metric computation and emits the five output artefacts.

## Acceptance criteria

The skill is ready when:

- It produces all five artefacts for any non-empty results dir.
- For
  `examples/single_agent/results/JOH_FINAL_v2/gemma4_e4b/Group_C/`,
  the recomputed Table 5 row matches paper SI to ±0.001 on IBR mean.
- For a tree containing both governed and disabled subtrees, the
  paired t-test reproduces SFig 1 numbers within ±0.01 on every ΔIBR.
- Caveats section is non-empty for any input that has missing seeds or
  flagged sentinel columns.
- Refusal protocol triggers when fed an unknown metric name (e.g.,
  "compute the WAGF coherence index").
