# IBR Analysis — CS-Friendly Tables

## Context

**IBR (Irrational Behaviour Rate)** measures the percentage of LLM agent decisions that violate Protection Motivation Theory (PMT) predictions in a flood adaptation simulation. Three verification rules:

- **V1**: Agent relocated despite self-appraising flood threat as low
- **V2**: Agent elevated house despite self-appraising flood threat as low
- **V3**: Agent chose inaction despite self-appraising flood threat as very high (with adequate coping)

**Groups**:
- **A (ungoverned)**: Free-form LLM output, no governance layer. Threat appraisals inferred post-hoc via keyword classifier.
- **C (governed)**: LLM output validated by PMT-based governance rules before execution. Structured threat labels emitted directly.

**Experiment**: 6 LLMs (Gemma-3 4B/12B/27B, Ministral 3B/8B/14B) × 100 agents × 10 years × 3 random seeds.

---

## Files

### `table1_per_run_raw.csv` (36 rows)
Every individual run for Groups A and C. Columns:
- `model`, `group` (A/C), `run` (Run_1/2/3)
- `N_active`: agent-year observations (post-relocation excluded)
- `R_H_%`: hallucination rate = (V1+V2+V3)/N_active × 100
- `V1`, `V2`, `V3`: violation counts per rule
- `EHE`: normalized Shannon entropy (strategy diversity)

### `table2_summary_effect_sizes.csv` (6 rows)
Per-model summary with full statistical detail. Key columns:
- `A_R_H_r1/r2/r3`: per-seed ungoverned R_H% (all 3 data points visible)
- `C_R_H_r1/r2/r3`: per-seed governed R_H%
- `Delta_R_H`: paired mean difference (A − C)
- `Cohen_d`: effect size (paired, d = mean_diff / sd_diff)
- `CI_95_lo/hi`: 95% CI from paired t-distribution (df=2, t_crit=4.303)
- `p_paired_t`: two-tailed paired t-test
- `sig`: significance level (*/**/***/ ns)
- `A_V1/V2/V3_mean`, `C_V1/V2/V3_mean`: per-run mean violation counts

**Result**: 4/6 significant (p < 0.01), 2/6 non-significant but directionally consistent (A > C).

### `table3_classifier_methodology.csv` (12 rows)
Documents the classification approach per group:
- Group A: Three-tier keyword classifier (explicit labels → qualifier precedence → keyword matching), low-threat threshold = {L, VL, M}
- Group C: Structured labels from governance pipeline, low-threat threshold = {L, VL}

---

## Key Findings

| Model | A R_H% | C R_H% | Delta | Cohen's d | p |
|---|---|---|---|---|---|
| Ministral-14B | 11.61 | 0.40 | +11.21 | 19.0 | <0.001 *** |
| Ministral-3B | 8.89 | 1.70 | +7.19 | 5.8 | 0.010 ** |
| Gemma3-12B | 3.35 | 0.15 | +3.20 | 16.9 | 0.001 ** |
| Ministral-8B | 1.56 | 0.13 | +1.43 | 11.2 | 0.003 ** |
| Gemma3-27B | 0.78 | 0.33 | +0.44 | 1.2 | 0.183 ns |
| Gemma3-4B | 1.15 | 0.86 | +0.29 | 1.0 | 0.242 ns |

## V3 = 0 Note

V3 (inaction under VH threat) is zero across all models because:
1. **Group A**: Keyword classifier rarely assigns VH — LLMs use hedged language ("significant risk") not extreme labels
2. **Group C**: VH labels are rare (1-2% of agent-years), and agents consistently acted under VH

This is a method limitation, not an agent behaviour finding.

## Classifier Fix (2026-02-23)

The keyword classifier had a negation/qualification bug: "low risk of flooding" matched H keyword "risk of flood". Fixed by adding Tier 1.5 (qualifier precedence) that detects "low risk", "moderate concern" before keyword matching. Before fix: Ministral-14B A = 1.6%; after fix: 11.6%.

---

*Generated from `examples/single_agent/results/JOH_FINAL/compute_flood_ibr.py`*
*Source data: `paper/tables/IBR_detail.csv`*
