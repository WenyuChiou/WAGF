# Paper 3 — C&V (Calibration & Validation) Module

## Overview

This module implements the 5-metric C&V pipeline for Paper 3 (WRR).
It connects the generic SAGE C&V validators (`broker/validators/calibration/`)
to the Paper 3 multi-agent flood experiment outputs.

## Architecture

```
broker/validators/calibration/    <-- Generic SAGE C&V engine
  cv_runner.py                    <-- CACR, BRC, R_H orchestration
  psychometric_battery.py         <-- ICC(2,1), Cronbach α, Fleiss κ
  micro_validator.py              <-- PMT construct-action coherence
  vignettes/                      <-- 3 severity-level vignettes (high/med/low)

paper3/analysis/                  <-- Paper 3 case-level wiring (this module)
  audit_to_cv.py                  <-- AuditWriter CSV → CVRunner DataFrame adapter
  empirical_benchmarks.py         <-- External benchmark comparison (NFIP, Blue Acres)

paper3/configs/
  icc_archetypes.yaml             <-- 6 archetypes for ICC psychometric probing

paper3/run_cv.py                  <-- Master C&V runner (3 modes)
```

## 5 Core Metrics

| Metric | Level | Threshold | Requires LLM? | Requires Experiment Data? |
|--------|-------|-----------|:-:|:-:|
| CACR   | L1 Micro | >= 0.80 | No | Yes |
| R_H + EBE | L1 Micro | <= 0.10 | No | Yes |
| BRC    | L2 Macro | >= 0.60 | No | Yes |
| ICC(2,1) | L3 Cognitive | >= 0.60 | Yes (540 calls) | No |
| Cronbach α / Fleiss κ | L3 Cognitive | Descriptive | Yes (same 540) | No |

## Usage

### Mode 1: Post-Hoc Validation (after experiment)

Reads experiment audit CSVs, computes CACR/R_H/BRC, compares with empirical benchmarks.

```bash
cd examples/multi_agent/flood/
python paper3/run_cv.py --mode posthoc --trace-dir paper3/results/seed_42/
```

**Input**: `{trace_dir}/household_owner_governance_audit.csv` and
`{trace_dir}/household_renter_governance_audit.csv`

**Output**: `{trace_dir}/cv/posthoc_report.json`, `benchmark_comparison.csv`

### Mode 2: ICC Probing (requires LLM, independent of experiment)

Probes 6 archetypes × 3 vignettes × 30 replicates = 540 LLM calls.

```bash
python paper3/run_cv.py --mode icc --model gemma3:4b --replicates 30
```

**Output**: `paper3/results/cv/icc_report.json`, `icc_responses.csv`

### Mode 3: Aggregate (cross-seed comparison)

Loads all per-seed post-hoc reports, builds comparison table with mean ± std.

```bash
python paper3/run_cv.py --mode aggregate --results-dir paper3/results/
```

**Output**: `paper3/results/cv/aggregate_cv_table.csv`, `aggregate_stats.json`

## Data Adapter: AuditWriter → CVRunner

The `audit_to_cv.py` module transforms GenericAuditWriter output format
into CVRunner-compatible DataFrames.

### Column Mapping

| AuditWriter CSV | CVRunner DataFrame |
|----------------|-------------------|
| `final_skill` | `yearly_decision` |
| `construct_TP_LABEL` | `threat_appraisal` + `ta_level` |
| `construct_CP_LABEL` | `coping_appraisal` + `ca_level` |
| `reason_text` / `raw_output` | `reasoning` |
| (derived cumulative) | `elevated`, `relocated`, `insured` |

### Cumulative State Derivation

- `elevated`: True once agent chooses `elevate_house` (irreversible)
- `relocated`: True once agent chooses `relocate` or `buyout_program` (irreversible)
- `insured`: True when agent has active insurance (renewable)

## Empirical Benchmarks

External plausibility checks (separate from BRC internal concordance):

| Benchmark | Expected Range | Source |
|-----------|---------------|--------|
| NFIP insurance uptake (SFHA) | 30-50% | Kousky (2017) |
| Elevation adoption (cumulative) | 3-12% | Haer et al. (2017) |
| Blue Acres buyout | 2-15% | NJ DEP |
| Inaction rate (post-flood) | 35-65% | Grothmann & Reusswig (2006) |
| MG-NMG adaptation gap | 10-30% | Choi et al. (2024) |

## ICC Archetypes

6 archetypes covering the 4-cell balanced design + 2 extremes:

1. `mg_owner_floodprone` — Marginalized homeowner, high-risk zone
2. `mg_renter_floodprone` — Marginalized renter, high-risk zone
3. `nmg_owner_floodprone` — Non-marginalized homeowner, high-risk zone
4. `nmg_renter_safe` — Non-marginalized renter, low-risk zone
5. `resilient_veteran` — Experienced NMG homeowner, already elevated
6. `vulnerable_newcomer` — New MG renter, no flood experience

## Testing

```bash
python scratchpad/test_cv_adapter.py
```

Tests: column renaming, cumulative state derivation, multi-type merge,
empirical benchmark comparison, LLM response parsing.

## Dependencies

- `broker/` (SAGE framework) — CVRunner, PsychometricBattery, PMTFramework
- `pandas`, `numpy`, `pyyaml` (standard)
- `requests` (for Ollama LLM calls in ICC mode only)
- `scipy` (optional, for ICC confidence intervals and p-values)
