# WAGF Project State

## ⚠️ PAPER SCOPE — READ FIRST
- **Paper 1b (Nature Water)**: SINGLE-AGENT experiments only (flood + irrigation) + FQL baseline
- **Paper 3 (flood ABM)**: MULTI-AGENT experiments (400 agents, 12 skills, EPI benchmarks)
- **NEVER mix data between papers** — no buyout, no EPI, no MA flood data in NW paper

## Nature Water Paper (Paper 1b) — ACTIVE

### Narrative Direction (CONFIRMED 2026-02-21)
- **Core insight**: Governed LLM agents produce interpretable adaptive behavior that rule-based ABMs cannot
- **Narrative arc**: Harvard Water Program → ABM pain points → LLM solution → governance scaffolding
- **Three conditions**: LLM Governed vs LLM Ungoverned vs FQL Baseline (Hung & Yang 2021)
- **Results order**: Irrigation (lead) → Water outcomes → FQL comparison → Flood (secondary)
- **Key quote**: "Institutional boundary enforcement does not suppress reasoning — it scaffolds the adaptive capacity that numerical decision rules cannot represent."

### Experiments Used
| Domain | Architecture | Agents | Duration | Skills | Seeds/Runs | Model |
|--------|-------------|--------|----------|--------|------------|-------|
| **Flood** | Single-agent | 100 | 10yr | 4 (insurance, elevation, relocation, do_nothing) | 3 runs × 6 models × 3 groups | Gemma-3 4B/12B/27B, Ministral 3B/8B/14B |
| **Irrigation** | Single-agent | 78 CRSS | 42yr | 5 (increase_large/small, maintain, decrease_small/large) | 3 seeds × 2 conditions | Gemma-3 4B |
| **FQL Baseline** | Single-agent | 78 CRSS | 42yr | 2 actions (increase/decrease) | 3 seeds | Hung & Yang 2021 Q-learning |
| **Rule-based** | Deterministic PMT | 100 | 10yr | 4 (same as flood) | 3 runs | N/A (threshold logic) |

### FQL Baseline (COMPLETE — 2026-02-21)
- **Worktree**: `../wagf-fql-baseline` on branch `feature/fql-baseline`
- **Commits**: `5a88d4a` (initial), `bc492f4` (remove EHE from FQL)
- **Design**: FQL core algorithm 100% faithful to Hung & Yang 2021 (Q-table, Bayesian posterior, asymmetric reward, ε-greedy, 3 calibrated clusters)
- **Key decisions**:
  - 2-action model only (increase/decrease) — NO maintain, NO large/small
  - Magnitude resampling via execute_skill() — trade-off for fair comparison, does NOT affect FQL learning (FQL learns from actual Div_y)
  - Preceding factor persistence (f_next = f_t) — consistent with LLM
  - EHE NOT computed for FQL (binary action space, maintain=100% validator blocking artifact)
- **Expert review**: 2 of 3 experts initially critical, both reversed after code review. Consensus: ACCEPT WITH MINOR REVISIONS. Methods must clarify "FQL decision kernel + WAGF execution".
- **Files** (in wagf-fql-baseline worktree):
  - `learning/fql_skill_mapper.py` — sign-only mapping
  - `run_fql_baseline.py` — full runner with --no-governance flag
  - `tests/test_fql_baseline.py` — 11 tests ALL PASS
  - `analysis/fql_comparison_metrics.py` — EHE LLM only, water metrics all 3
  - `analysis/fql_comparison_figure.py` — 6-panel comparison figure

### FQL Results (78 agents × 42yr × 3 seeds)
| Metric | LLM Governed | LLM Ungoverned | FQL Baseline |
|--------|:---:|:---:|:---:|
| EHE (3-dir) | 0.737 ± 0.009 | 0.503 ± 0.024 | N/A |
| Demand ratio | 0.394 ± 0.004 | 0.288 ± 0.020 | 0.237 ± 0.012 |
| Demand-Mead r | 0.547 ± 0.083 | 0.378 ± 0.081 | 0.407 ± 0.160 |
| Shortage years | 13.3 ± 1.5 | 5.0 ± 1.7 | 4.0 ± 0.0 |
| WSA coherence | 0.580 ± 0.051 | 0.094 ± 0.016 | 0.124 ± 0.032 |

### Key Results (Single-Agent, LLM only)
- **Irrigation EHE**: Governed 0.737 vs ungoverned 0.503 (constraint paradox holds)
- **First-attempt EHE**: Governed 0.761 vs ungoverned 0.640 (not retry artifact)
- **Water outcomes**: Governed demand ratio 0.394 vs ungoverned 0.288; Mead LOWER under governance
- **Flood scaffolding**: 2/6 Yes, 1/6 Marginal, 3/6 Reversed — MODEL-DEPENDENT
- **Null-model CACR**: random=60%, governed=58%, ungoverned=9.4%

### Policy Counterfactual
- **No-ceiling ablation** (irrigation) — 4 seeds complete (42-44, 46). Mean EHE=0.798, DR=0.431, Shortage=23.8
- **B1: Insurance premium doubling** (flood) — COMPLETE (9 runs), SI ONLY

### Paper Sections (v14 — 2026-02-24)
- **NatureWater_MainText_v14.docx**: COMPILED — Analysis format
- **NatureWater_SI_v14.docx**: Supplementary Information
- **Display items**: 2 tables + 4 figures

### Professor Briefing Materials (2026-02-24)
- **professor_summary_IBR_EHE.docx**: Flood table — 6 models, no CI, no seed count
- **professor_summary_irrigation.docx**: Irrigation table — 6 cols, no CI, no seed count
- **10min_talking_points.docx**: Presentation script (5 slides + Q&A)
- Tables use "Ungoverned"/"Governed" (not Ungov.), "No Ceiling" (not A1), "Δ (G−U)"
- Seed counts omitted — user will supplement runs before submission
  - Fig. 1: Framework architecture (simulation loop)
  - Fig. 2: Irrigation 4-panel (Mead, demand ratio, action dist, diversity-coupling scatter)
  - Fig. 3: Flood cumulative adaptation (3 panels: PMT / Ungoverned / Governed)
  - Fig. 4: Cross-model forest plot (6 models, paired dot + delta with 95% CI)
  - Table 1: Irrigation 4-condition (Governed / Ungoverned / No Ceiling / FQL)
  - Table 2: Flood 3-condition (Governed / Rule-based PMT / Ungoverned)
- **Figures redesigned** (2026-02-24): Okabe-Ito colorblind-safe palette, hatching for grayscale, NW-compliant panel labels
- **Fig. 2 Panel (a) updated**: Now shows all 4 conditions (added FQL grey dotted line), expert-reviewed PASS
- **R1 rewritten**: Three-way comparison (Governed/Ungov/FQL) leads, coupling (r) defined with motivation
- **Terminology cleaned** (Session V): A1→"No ceiling", Group A/B/C→descriptive, changelogs stripped, 10 professor review fixes

### Data Completeness
- JOH_FINAL: 54/54 COMPLETE
- B1: 9/9 complete
- Rule-based: 3/3 complete
- Irrigation: 6/6 complete
- FQL Baseline: 3/3 complete

---

## Paper 3 (Multi-Agent Flood ABM) — Draft v1 COMPLETE

### Production (3 seeds)
- seed_42: EPI=0.890 (7/8 PASS) — pre-bugfix
- seed_43: EPI=0.560 (5/8 PASS) — post-bugfix
- seed_44: EPI=0.615 (5/8 PASS) — post-bugfix
- Mean EPI = 0.689 ± 0.144, L1 ALL PASS all seeds

### Draft v1: `paper3/drafts/paper3_draft_v1.md` — ~7,121 words
- All sections full prose (Yang writing style)
- Expert panel: 3.6/5, Major Revision
- Must-fix: CACR_raw DONE, reframe DONE, memory bug disclosed, seeds running

### Round 2 Seeds
- seed_42_v2, 45, 46, 47 launched via nohup (PID 14496)
- After completion: cross-seed robustness → counterfactual → trim → refs/figures/SI

---

## EHE Calculation — UNIFIED
- Method: Aggregate EHE, fixed k = action space size
- FQL: EHE not applicable (binary action space)

## C&V Module
- Expert panel review complete (10 experts, mean 3.29/5.0)
