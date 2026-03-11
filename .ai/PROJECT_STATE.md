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

### Flood Cross-Model (Group_C, 3–5 seeds, updated 2026-03-09)
| Model | Seeds (gov/dis) | No-val IBR | Gov IBR | No-val EHE | Gov EHE |
|-------|----------------|-----------|---------|-----------|---------|
| Ministral 3B | 5/5 | 7.7±1.2 | 0.1±0.1 | 0.829±0.016 | 0.806±0.019 |
| Gemma-3 4B | 5/5 | 8.5±1.1 | 0.9±0.9 | 0.815±0.053 | 0.861±0.045 |
| Ministral 8B | 5/5 | 2.9±0.6 | 0.0±0.1 | 0.797±0.024 | 0.769±0.019 |
| Gemma-3 12B | 5/4 | 0.3±0.2 | 0.0±0.0 | 0.585±0.077 | 0.495±0.056 |
| Ministral 14B | 5/3 | 3.6±0.3 | 0.0±0.0 | 0.876±0.026 | 0.795±0.019 |
| Gemma-3 27B | 5/3 | 0.4±0.3 | 0.0±0.0 | 0.662±0.019 | 0.681±0.020 |

- 4/6 IBR reductions significant (p<0.05)
- **3/6 ΔEHE significant** (Ministral 3B p=0.020, 8B p=0.037, 14B p=0.035)
- 3/6 ΔEHE non-significant (all Gemma-3 models)

### Data Completeness
| Dataset | Path | Status |
|---------|------|--------|
| Flood governed Group_C (6×3) | `JOH_FINAL/{model}/Group_C/Run_{1-3}` | ✅ 18/18 |
| Flood no-validator (6×3) | `JOH_ABLATION_DISABLED/{model}/Group_C_disabled/Run_{1-3}` | ✅ 18/18 |
| Flood extra seeds (governed) | `Group_C/Run_{4,5}` | ✅ COMPLETE |
| Flood rule-based | `rulebased/Run_{1-3}` | ✅ 3/3 |
| Irrigation governed v21 | `production_v21_42yr_seed{42-46}` | ✅ 5/5 |
| Irrigation no-validator v21 | `ungoverned_v21_42yr_seed{42-46}` | ✅ 5/5 |
| FQL baseline | `fql_raw/seed{42-51}` | ✅ 10/10 |
| **ARCHIVED: Group_B** | `JOH_FINAL/_archive_Group_B/` | 🗄️ DO NOT USE |

### Paper Files Status
| Section | File | Status |
|---------|------|--------|
| Abstract | `abstract_v10.md` | ✅ 150 words, v21 |
| Introduction | `introduction_v10.md` | ✅ v20 revision, 3-round review PASS |
| Results R1-R3 | `section2_v11_results.md` | ✅ v21, Group_C, 5-action scheme |
| Discussion | `section3_v11_discussion.md` | ✅ terminology fixed |
| Methods | `methods_v3.md` | ✅ Group_C only, EHE=proposed |
| SI | `supplementary_information.md` | ✅ Group_C tables, v21 |
| SI traces | `SI_reasoning_traces.md` | ✅ v21 paths |
| SI Table S5 | `supplementary_table_s1.md` | ✅ terminology |
| Cover letter | `cover_letter_v14.md` | ❌ OUTDATED (v20 numbers) |
| Word doc | `NatureWater_{MainText,SI}_v20.docx` | ✅ |

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

## EHE Calculation — DEFINITIVE (2026-03-09)
- Method: **Aggregate** EHE = H/log₂(k), all decisions pooled across years (NOT yearly-averaged)
- k = action space size (k=4 flood, k=5 irrigation)
- EHE = proposed actions (cognitive diversity), not executed
- **Flood**: Map `relocated` → `relocate` (include ALL rows in entropy)
- FQL: EHE not applicable (binary action space)
- **DO NOT** use yearly-averaged EHE — that gives ~0.63 instead of correct ~0.86

## IBR Calculation — DEFINITIVE (2026-03-09)
- IBR = (R1 + R3 + R4) / N_active × 100%
- R1: high threat (H/VH) + do_nothing
- R3: low threat (VL/L) + relocate
- R4: low threat (VL/L) + elevate_house
- R5 (re-elevation): **tracked but EXCLUDED** from IBR per EDT2
- N_active = rows where yearly_decision ≠ "relocated" (exclude post-relocation rows)
- **DO NOT** include R5 in IBR — that inflates governed IBR from 0.8% to ~11%

## Metric Scripts — DEFINITIVE (2026-03-09)
- **Canonical analysis**: `examples/single_agent/analysis/compute_flood_metrics.py` (commit 993eff9)
- **Figure generation**: `paper/nature_water/scripts/gen_fig3_crossmodel.py`
- **DELETED** (wrong Group_A baseline): nw_p0_*.py, nw_b1_*.py, nw_rulebased_comparison.py
- **In results/ (gitignored, reference only)**: compute_flood_ibr.py (V1/V2/V3 posthoc pipeline)

## Comparison Framework — NEVER CONFUSE
| Condition | Data Path | Label in Paper |
|-----------|-----------|----------------|
| **Governed LLM** | `JOH_FINAL/{model}/Group_C/` | "Governed LLM" |
| **LLM (no validator)** | `JOH_ABLATION_DISABLED/{model}/Group_C_disabled/` | "LLM (no validator)" |
| **Rule-based PMT** | `rulebased/Run_{1-3}/` | "Rule-based PMT" |
| ~~Group_A~~ | ~~JOH_FINAL/{model}/Group_A/~~ | **NEVER USE as no-validator baseline** |
| ~~Group_B~~ | ~~archived~~ | **NEVER USE** |

- Both Governed and No-validator use WAGF framework + HumanCentric memory
- Only difference: validator enforcement toggled on/off
- NEVER say "ungoverned" — say "no validator" or "without validators"

---

## Paper 3 (Multi-Agent Flood ABM) — RECALIBRATION NEEDED
- 400 agents × 13yr, 12 skills, per-agent-depth PRB floods
- NFIP trajectory recalibration pending
## 2026-03-07 - ABM Generalization Direction

- Target audience expansion: external ABM developers, not only current water/flood experiments.
- Current assessment:
  - Theory-driven governance is real and implemented in core validators.
  - External framing is still PMT/flood-heavy even where code is generic.
  - Multi-skill is better described as bounded composite action, not a general planner.
- Active execution plan:
  - `docs/plans/2026-03-07-abm-generalization-plan.md`
- Required invariants during refactor:
  - Preserve single-agent flood behavior.
  - Preserve irrigation dual-appraisal behavior and FQL reference path.
  - Preserve paper3 multi-agent flood workflow isolation.
  - Keep `multi_skill` default off unless explicitly enabled.
## Paper3 MA Flood Research Direction (2026-03-10)
- Frame Paper 3 as an intervention-based mechanism study, not as three loose descriptive RQs
- Main research emphasis:
  - inequality across the balanced 4-cell population
  - endogenous institutional feedback
  - social information channels
- Memory remains part of the architecture but is **not** a primary ablation/RQ axis

### Balanced 4-Cell Population
- MG homeowner
- MG renter
- NMG homeowner
- NMG renter

### Recommended RQs
1. How do flood adaptation inequalities evolve across marginalized and non-marginalized homeowners and renters?
2. How does endogenous institutional feedback reshape those inequalities?
3. How do social information channels alter the timing and spread of protective action across homeowner and renter groups?

### Experimental Mapping
- RQ1 -> full model / `examples/multi_agent/flood/paper3/configs/primary_experiment.yaml`
- RQ2 -> institutional contrast / `si2_exogenous_institutions`
- RQ3 -> social contrasts / `si3a_no_gossip`, `si3b_no_social_media`, `si3c_isolated`
- `si7_no_governance` is a robustness check, not a main RQ
