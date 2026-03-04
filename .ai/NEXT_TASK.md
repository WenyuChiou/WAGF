# Next Task: Update Tables + Fig 4 + Paper (2026-03-03)

## Experiment Inventory

### FLOOD — Complete
| Dataset | Path Pattern | Status |
|---------|-------------|--------|
| **Governed LLM** (6 models × 3 seeds) | `JOH_FINAL/{model}/Group_B/Run_{1,2,3}` | ✅ 18/18 |
| **LLM (no validator)** (6 models × 3 seeds) | `JOH_ABLATION_DISABLED/{model}/Group_C_disabled/Run_{1,2,3}` | ✅ 18/18 |
| **Governed LLM** (gemma3_4b, humancentric) | `JOH_FINAL/gemma3_4b/Group_C/Run_{1,2,3}` | ✅ 3/3 |
| **Rule-based PMT** (gemma3_4b) | `rulebased/Run_{1,2,3}` | ✅ 3/3 |
| No ETB ablation (SI) | `JOH_ABLATION_NO_ETB/.../Run_1` | 1/3 (low priority) |

### IRRIGATION — Running
| Dataset | Status |
|---------|--------|
| Governed v21 seed42 | ✅ 3277 rows |
| Governed v21 seeds 43-46 | 🔄 Pipeline running |
| No-validator v21 seeds 42-46 | ⏳ Queued in pipeline |
| No-ceiling v21 (SI) | ⏳ Deferred |
| FQL baseline (10 seeds) | ✅ Complete |

Pipeline: `run_nw_pipeline.py --skip-wait --start-from 2 --stop-at 10`

## Three Conditions (CRITICAL naming)
| Condition | Main text (gemma3_4b) | Cross-model (Fig 4, SI) |
|-----------|----------------------|------------------------|
| **Rule-based PMT** | `rulebased/Run_{1,2,3}` | gemma3_4b only |
| **LLM (no validator)** | `Group_C_disabled/Run_{1,2,3}` | All 6 models |
| **Governed LLM** | `Group_C/Run_{1,2,3}` (humancentric) | `Group_B/Run_{1,2,3}` (window memory) |

- Group_B = cross-model governed (only available for all 6 models)
- Group_C = main text governed (humancentric, post-R5 fix)
- **NEVER label "Group_B" or "Group_C"** in paper — just "Governed LLM"

## Verified Metrics (2026-03-03)

### Table 2: Main text (gemma3_4b, Group_C vs Group_C_disabled vs rulebased)
| Metric | Rule-based PMT | LLM (no validator) | Governed LLM |
|--------|:-:|:-:|:-:|
| IBR (%) | — | 8.1 ± 1.7 | 0.8 ± 1.1 |
| EHE | 0.598 ± 0.017 | 0.846 ± 0.042 | 0.860 ± 0.063 |
| Relocation (%) | 0.3 ± 0.6 | 19.0 ± 10.0 | 27.0 ± 14.7 |

### SI Table: Cross-model (Group_B governed vs Group_C_disabled)
| Model | Gov IBR% | Dis IBR% | ΔIBR(pp) | Gov EHE | Dis EHE | ΔEHE |
|-------|----------|----------|----------|---------|---------|------|
| gemma3_4b | 0.6 | 8.1 | +7.5 | 0.866 | 0.846 | -0.02 |
| gemma3_12b | 0.1 | 0.2 | +0.2 | 0.612 | 0.603 | -0.01 |
| gemma3_27b | 0.0 | 0.4 | +0.4 | 0.638 | 0.662 | +0.02 |
| ministral3_3b | 0.3 | 5.0 | +4.8 | 0.810 | 0.825 | +0.01 |
| ministral3_8b | 0.0 | 2.3 | +2.3 | 0.728 | 0.791 | +0.06 |
| ministral3_14b | 0.0 | 3.1 | +3.1 | 0.833 | 0.876 | +0.04 |

Key: IBR excludes R5 (re-elevation = code bug in disabled runs). All 6 models show IBR reduction. EHE difference < 0.07 for all.

## Immediate TODO
1. ✅ Metrics computed and verified
2. ✅ SI tables updated (Supplementary Tables 1+2, condition naming fixed throughout)
3. ✅ Fig 4 regenerated (cross-model forest plot with Group_B vs Group_C_disabled)
4. ✅ Introduction P6 — "sixteenfold" → "tenfold", American→British spelling fixed
5. ✅ Extended Data Table 2 — updated to Group_C/C_disabled/rulebased verified data
6. ✅ Results R4 — rewritten with new narrative (IBR reduction + ΔEHE non-significant)
7. ✅ Discussion — updated effect sizes and interpretation
8. ✅ "Ungoverned" → "LLM (no validator)" in all 5 core files
9. ✅ Methods flood section — rewritten to 3-condition design (Rule-based/No validator/Governed)
10. **Abstract v10** — ⚠️ BLOCKED: contains v20 irrigation numbers (91%, 42%, 37%)
11. **Results R1-R3** — ⚠️ BLOCKED: v20 irrigation numbers throughout
12. **Extended Data Table 1** — ⚠️ BLOCKED: all irrigation metrics are v20
13. **SI Notes 3, 4, 6** — ⚠️ BLOCKED: v20 irrigation data
14. **SI Table 7** — needs recomputation with Group_B/C_disabled (low priority)

## Display Items (≤ 7)
| # | Content | Status |
|---|---------|--------|
| Fig. 1 | WAGF architecture | ❌ Needs creation |
| Fig. 2 | Irrigation 4-panel | ⏳ Blocked — needs v21 no-validator data |
| Fig. 3 | Flood 2-panel (a+b) | ✅ (a) stacked bars + (b) pie matrices |
| Fig. 4 | Cross-model forest plot | ✅ Regenerated with correct data |
| Table 1 | Irrigation metrics | ⏳ Blocked — needs v21 data |
| Table 2 | Flood metrics | ✅ Written into Extended Data Table 2 |

## Paper Sections
| Section | Version | Words | Status |
|---------|---------|-------|--------|
| Abstract | v10 | 148w | ⚠️ BLOCKED — v20 irrigation numbers |
| Introduction | v19 | ~890w | ✅ P6 flood numbers fixed; P6 irrigation numbers still v20 |
| Results | v18 | ~2,200w | ✅ R4 + EDT2 updated; R1-R3 still v20 |
| Discussion | v18 | ~950w | ✅ Updated cross-model interpretation |
| Methods | v5 | no limit | ✅ 3-condition design, naming fixed |
| SI | v2 | — | ✅ Tables 1+2 updated, naming fixed |
| **Total main** | | ~3,030/4,000w | |
