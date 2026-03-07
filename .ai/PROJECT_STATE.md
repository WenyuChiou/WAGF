# WAGF Project State (Updated 2026-03-07)

## Repo Boundary Status (2026-03-07)
- `paper/nature_water/` is the manuscript workspace for the Nature Water paper
- `examples/multi_agent/flood/paper3/` is the dedicated MA flood Paper 3 workspace
- NW should continue to use only single-agent flood + irrigation + FQL baseline inputs
- `ref/RL-ABM-CRSS/` has been restored from the official paper GitHub and is required for FQL baseline reproducibility
- Paper 3 review notes and figure candidates have been isolated into ignored working folders so they do not pollute the main runtime tree
- Safe local artifacts removed from the repo root: prompt dump, seed logs, `verification_test/`, `node_modules/`, and `.egg-info/`

## PAPER SCOPE — READ FIRST
- **Paper 1b (Nature Water)**: SINGLE-AGENT experiments only (flood + irrigation) + FQL baseline
- **Paper 3 (flood ABM)**: MULTI-AGENT experiments (400 agents, 12 skills, EPI benchmarks)
- **NEVER mix data between papers** — no buyout, no EPI, no MA flood data in NW paper

## Nature Water Paper (Paper 1b) — ACTIVE

### Paper Title
**"Institutional Constraints Shape Adaptive Strategy Diversity in Language-Based Water Agents"**

### CRITICAL: Group_C ONLY (2026-03-07)
- **ALL flood governed experiments use Group_C** (HumanCentric memory)
- **Group_B (Window memory) is ARCHIVED** → `JOH_FINAL/_archive_Group_B/`
- **NEVER use Group_B data** in any figure, table, or text

### Three Conditions (naming)
| Condition | Data Path | Memory |
|-----------|-----------|--------|
| **Rule-based PMT** | `rulebased/Run_{1-3}` | N/A |
| **LLM (no validator)** | `JOH_ABLATION_DISABLED/{model}/Group_C_disabled/Run_{1-3}` | HumanCentric |
| **Governed LLM** | `JOH_FINAL/{model}/Group_C/Run_{1-3}` | HumanCentric |

- **NEVER use "ungoverned"** — both conditions use WAGF, only validators toggled
- **NEVER use "buyout"** — single-agent flood has 4 skills: insurance, elevation, relocation, do_nothing

### V21 Irrigation Metrics (verified, 5 seeds each)

**Governed (seeds 42-46)**
| Metric | Mean ± std |
|--------|-----------|
| IBR (%) | 38.2 ± 4.2 |
| EHE | 0.687 ± 0.046 |
| DR | 0.411 ± 0.004 |
| Mead (ft) | 1,087 ± 2 |
| Min Mead (ft) | 988 ± 12 |
| Shortage (/42) | 14.2 ± 1.3 |

**No-validator (seeds 42-46)**
| Metric | Mean ± std |
|--------|-----------|
| IBR (%) | 61.1 ± 3.0 |
| EHE | 0.848 ± 0.011 |
| DR | 0.770 ± 0.011 |
| Mead (ft) | 975 ± 9 |
| Min Mead (ft) | 895 ± 0 (dead pool) |
| Shortage (/42) | 39.2 ± 1.0 |

### Flood Cross-Model (Group_C, 3 seeds each)
| Model | No-val IBR | Gov IBR | No-val EHE | Gov EHE |
|-------|-----------|---------|-----------|---------|
| Ministral 3B | 5.0±0.5 | 0.1±0.0 | 0.825±0.014 | 0.798±0.018 |
| Gemma-3 4B | 8.1±1.4 | 0.8±0.9 | 0.846±0.034 | 0.860±0.051 |
| Ministral 8B | 2.3±0.2 | 0.0±0.0 | 0.791±0.025 | 0.766±0.018 |
| Gemma-3 12B | 0.2±0.2 | 0.0±0.0 | 0.603±0.068 | 0.475±0.056 |
| Ministral 14B | 3.1±0.2 | 0.0±0.0 | 0.876±0.021 | 0.803±0.006 |
| Gemma-3 27B | 0.4±0.2 | 0.0±0.0 | 0.662±0.016 | 0.686±0.022 |

- 4/6 IBR reductions significant (p<0.05)
- 1/6 ΔEHE significant (Ministral 14B, p=0.035)
- 5/6 ΔEHE non-significant

### Data Completeness
| Dataset | Path | Status |
|---------|------|--------|
| Flood governed Group_C (6×3) | `JOH_FINAL/{model}/Group_C/Run_{1-3}` | ✅ 18/18 |
| Flood no-validator (6×3) | `JOH_ABLATION_DISABLED/{model}/Group_C_disabled/Run_{1-3}` | ✅ 18/18 |
| Flood extra seeds (6×2×2) | `Group_C/Run_{4,5}` + `Group_C_disabled/Run_{4,5}` | ⏳ PENDING |
| Flood rule-based | `rulebased/Run_{1-3}` | ✅ 3/3 |
| Irrigation governed v21 | `production_v21_42yr_seed{42-46}` | ✅ 5/5 |
| Irrigation no-validator v21 | `ungoverned_v21_42yr_seed{42-46}` | ✅ 5/5 |
| FQL baseline | `fql_raw/seed{42-51}` | ✅ 10/10 |
| **ARCHIVED: Group_B** | `JOH_FINAL/_archive_Group_B/` | 🗄️ DO NOT USE |

### Paper Files Status
| Section | File | Status |
|---------|------|--------|
| Abstract | `abstract_v10.md` | ✅ 150 words, v21 |
| Introduction | `introduction_v10.md` | ✅ v21, sentence splits done |
| Results R1-R3 | `section2_v11_results.md` | ✅ v21, Group_C, 5-action scheme |
| Discussion | `section3_v11_discussion.md` | ✅ terminology fixed |
| Methods | `methods_v3.md` | ✅ Group_C only, EHE=proposed |
| SI | `supplementary_information.md` | ✅ Group_C tables, v21 |
| SI traces | `SI_reasoning_traces.md` | ✅ v21 paths |
| SI Table S5 | `supplementary_table_s1.md` | ✅ terminology |
| Cover letter | `cover_letter_v14.md` | ❌ OUTDATED (v20 numbers) |
| Word doc | `NatureWater_{MainText,SI}_v19.docx` | ✅ |

### Figures Status
| Figure | Script | Status |
|--------|--------|--------|
| Fig 1 (architecture) | user-created | ❌ user will create |
| Fig 2 (irrigation) | `gen_fig2_case1_irrigation.py` | ✅ 5-action, single seed pie |
| Fig 3 (flood) | `gen_fig3_case2_flood.py` | ✅ Group_C |
| Fig 4 (cross-model) | `gen_fig3_crossmodel.py` | ✅ Group_C |

---

## CRITICAL: v20→v21 Irrigation Data Break (2026-02-26)
- **ALL v20 irrigation results INVALID** — execute_skill base asymmetry bug
- v21 fix: ALL skills use `agent["request"]` as base
- v20 data paths: `production_v20_*`, `ungoverned_v20_*` — IGNORE

## EHE Calculation
- Method: Aggregate EHE, fixed k = action space size (k=4 flood, k=5 irrigation)
- EHE = proposed actions (cognitive diversity), not executed
- FQL: EHE not applicable (binary action space)
- **IMPORTANT**: Map `relocated` → `relocate` when computing flood EHE (include all rows)

---

## Paper 3 (Multi-Agent Flood ABM) — RECALIBRATION NEEDED
- 400 agents × 13yr, 12 skills, per-agent-depth PRB floods
- NFIP trajectory recalibration pending
