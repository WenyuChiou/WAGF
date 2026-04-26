# wagf_experiment_matrix.yml — annotated template

Copy this skeleton into `.research/wagf_experiment_matrix.yml` and fill
in. Comments mark the fields that are mandatory vs optional.

```yaml
# ───────────────────────────────────────────────────────────────────
# Metadata (mandatory)
# ───────────────────────────────────────────────────────────────────
research_question: |
  Does WAGF governance reduce LLM-driven irrational behaviour
  (high-threat inaction) under flood scenarios across multiple model
  families?

hypothesis: |
  Governance (strict mode) reduces IBR by ≥ 5 pp across all tested
  models, with effect size strongest in smaller-capacity models
  (≤ 8B parameters).

domain: flood              # flood | irrigation | multi_agent_flood
agent_count: 100           # flood=100, irrigation=78, MA flood=400
time_horizon_years: 10     # flood=10, irrigation=42

# ───────────────────────────────────────────────────────────────────
# Models (mandatory; at least 1)
# ───────────────────────────────────────────────────────────────────
# Use exact Ollama tag. Verify availability via `ollama list` before
# committing the matrix.
models:
  - tag: gemma3:4b
    governance: [strict, disabled]   # at least 2 conditions for paired-t
    seeds: [42, 43, 44, 45, 46]      # 5 seeds = paper convention

  - tag: gemma4:e4b
    governance: [strict, disabled]
    seeds: [42, 43, 44, 45, 46]

  - tag: ministral-3:8b
    governance: [strict, disabled]
    seeds: [42, 43, 44, 45, 46]

# ───────────────────────────────────────────────────────────────────
# Metrics (mandatory; pick from references/metrics_catalog.md)
# ───────────────────────────────────────────────────────────────────
metrics:
  - name: ibr
    canonical_script: examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py
    formula_ref: references/metrics_catalog.md#ibr
    output_artefact: analysis/governance_metrics.csv

  - name: ehe
    canonical_script: examples/irrigation_abm/analysis/nw_bootstrap_ci.py
    formula_ref: references/metrics_catalog.md#ehe
    output_artefact: analysis/governance_metrics.csv

  - name: retry_rate
    canonical_script: examples/single_agent/analysis/compute_retry_compliance.py
    formula_ref: references/metrics_catalog.md#retry_rate
    output_artefact: analysis/retry_outcomes.csv

  - name: temporal_diagnostic_M1_M2_M3
    canonical_script: examples/single_agent/analysis/compute_temporal_diagnostics.py
    formula_ref: references/metrics_catalog.md#temporal_diagnostics
    output_artefact: .ai/temporal_diagnostic.csv

# ───────────────────────────────────────────────────────────────────
# Statistical comparisons (mandatory)
# ───────────────────────────────────────────────────────────────────
statistical_comparisons:
  - name: governed_vs_disabled_per_model
    test: paired_t
    metric: ibr
    df_per_model: 4
    ci: 0.95
    expected_direction: positive   # ΔIBR = disabled - governed > 0

  - name: model_size_effect
    test: linear_regression
    predictor: log_param_count
    response: delta_ibr
    expected_direction: negative   # bigger model → smaller delta

# ───────────────────────────────────────────────────────────────────
# Output paths (mandatory)
# ───────────────────────────────────────────────────────────────────
output_root: examples/single_agent/results/JOH_FINAL_v2

run_dir_pattern: |
  {output_root}/{model_safe}/{condition_dir}/Run_{seed}
# Where:
#   model_safe   = tag with `:` → `_` (e.g. gemma4_e4b)
#   condition_dir = Group_C (governed) or Group_C_disabled (disabled)

# ───────────────────────────────────────────────────────────────────
# LLM hyperparameters (mandatory; capture in reproducibility manifest)
# ───────────────────────────────────────────────────────────────────
llm_params:
  num_ctx: 8192
  num_predict: 1536          # flood=1536; irrigation=4096
  temperature: null          # null = Ollama default; document choice
  top_p: null
  thinking_mode: disabled

# ───────────────────────────────────────────────────────────────────
# Optional: ablation variants
# ───────────────────────────────────────────────────────────────────
ablations: []
# Example:
# ablations:
#   - name: no_etb
#     governance_override: no_ETB
#     seeds: [42, 43, 44]

# ───────────────────────────────────────────────────────────────────
# Optional: reproducibility expectations (handed to abm-reproducibility-checker)
# ───────────────────────────────────────────────────────────────────
reproducibility:
  manifest_required: true
  git_commit_required: true
  model_digest_required: true
  expected_sentinel_columns:    # known reserved per INVARIANTS Inv 4
    - cog_is_novel_state
    - cog_surprise_value
    - cog_margin_to_switch
```

## Validation rules

1. `domain` must be one of {flood, irrigation, multi_agent_flood}.
2. `models[].tag` must validate against `ollama list` at run time.
3. `models[].governance` must be a non-empty subset of the modes
   declared in the domain's `agent_types.yaml`.
4. `models[].seeds` must have ≥ 3 entries for paired-t to be
   well-defined; warn if < 5.
5. `metrics[]` must have ≥ 1 entry; each entry must reference a
   canonical script that exists on disk.
6. `statistical_comparisons[]` must reference only metrics declared
   above.
7. `output_root` should not point at an existing populated directory
   without explicit user opt-in (avoid silent overwrite).
