# WAGF Project State

## ⚠️ PAPER SCOPE — READ FIRST
- **Paper 1b (Nature Water)**: SINGLE-AGENT experiments only (flood + irrigation) + FQL baseline
- **Paper 3 (flood ABM)**: MULTI-AGENT experiments (400 agents, 12 skills, EPI benchmarks)
- **NEVER mix data between papers** — no buyout, no EPI, no MA flood data in NW paper

## Nature Water Paper (Paper 1b) — ACTIVE

### Narrative Direction (UPDATED Session AI, 2026-02-25)
- **Core insight**: Governed LLM agents produce interpretable adaptive behavior that rule-based ABMs cannot
- **Narrative arc**: Harvard Water Program → ABM pain points → LLM solution → governance scaffolding
- **Three conditions**: LLM Governed vs LLM Ungoverned vs FQL Baseline (Hung & Yang 2021)
- **Three Water Insights (Session AJ — updated 2026-02-26)**:
  - Insight 1: "Governance rules not only block irrational decisions, but also enable agents to adapt to changing water conditions" → **Fig 2(a,b)** + **Fig 3(a,b)**
  - Insight 2: "LLM agents evaluate their environment but fail to act on that evaluation without governance — the appraisal-action link emerges only under [TBD wording, not 'institutional structure']" → **Fig 2(c)** + **Fig 3(c)** pie matrix + ρ + protective action %
  - Insight 3: "A single rule separates adaptive diversity from arbitrary diversity" → **Fig 4** + ablation experiments
  - Cross-model replication → Extended Data (forest plot)
  - **TODO**: Flood ablation running (extreme_threat_block removal) for Insight 3
  - **TODO**: Pie matrix needs quantitative support: per-cell protective action %, marginal Spearman ρ
- **Key framing**: Insights are water-science findings; WAGF is the tool (like a microscope). Results ≠ framework validation.
- **Key quote**: "Institutional boundary enforcement does not suppress reasoning — it scaffolds the adaptive capacity that numerical decision rules cannot represent."

### Experiments Used
| Domain | Architecture | Agents | Duration | Skills | Seeds/Runs | Model |
|--------|-------------|--------|----------|--------|------------|-------|
| **Flood** | Single-agent | 100 | 10yr | 4 (insurance, elevation, relocation, do_nothing) | 3 runs × 6 models × 3 groups | Gemma-3 4B/12B/27B, Ministral 3B/8B/14B |
| **Irrigation** | Single-agent | 78 CRSS | 42yr | 5 (increase_large/small, maintain, decrease_small/large) | 3 seeds × 2 conditions | Gemma-3 4B |
| **FQL Baseline** | Single-agent | 78 CRSS | 42yr | 2 actions (increase/decrease) | 10 seeds (42-51) | Hung & Yang 2021 Q-learning |
| **Rule-based** | Deterministic PMT | 100 | 10yr | 4 (same as flood) | 3 runs | N/A (threshold logic) |

### FQL Baseline (10 seeds COMPLETE — 2026-02-25)
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

### FQL Results (78 agents × 42yr × 10 seeds) — UPDATED 2026-02-25
| Metric | LLM Governed | LLM Ungoverned | FQL Baseline (10 seeds) |
|--------|:---:|:---:|:---:|
| Behavioural diversity | 0.738 ± 0.017 | 0.637 ± 0.017 | — |
| Demand ratio | 0.394 ± 0.004 | 0.288 ± 0.020 | 0.344 ± 0.039 |
| Shortage years | 13.3 ± 1.5 | 5.0 ± 1.7 | 13.6 ± 8.8 |
| Min Mead (ft) | 1,002 ± 1 | 1,001 ± 0.4 | 1,005 ± 11 |
- **NOTE**: FQL 10-seed values differ significantly from original 3-seed (DR was 0.395, now 0.344; Shortage was 24.7, now 13.6)
- **Finding**: FQL high variability (σ >> LLM) = Q-learning sensitive to initial conditions; governance provides stability

### Key Results (Single-Agent, LLM only)
- **Irrigation diversity**: Governed 0.738 vs ungoverned 0.637 (adaptive exploitation)
- **First-attempt diversity**: Governed 0.761 vs ungoverned 0.640 (not retry artifact)
- **Water outcomes**: Governed demand ratio 0.394 vs ungoverned 0.288; Mead LOWER under governance
- **Flood scaffolding**: 2/6 Yes, 1/6 Marginal, 3/6 Reversed — MODEL-DEPENDENT
- **Null-model CACR**: random=60%, governed=58%, ungoverned=9.4%

### CRITICAL: v20→v21 Irrigation Data Break (2026-02-26)
- **ALL v20 irrigation results INVALID** — execute_skill base asymmetry bug
- v20 dirs (`production_v20_*`, `ungoverned_v20_*`, `ablation_no_ceiling_seed*`): DO NOT cite
- v21 dirs (`*_v21_*`): pending rerun via `run_nw_pipeline.py`
- v20 IBR/EHE numbers (gov 42%, ungov 91%, noceil 49%) are WRONG
- FQL baseline unaffected (uses own Q-learning, not execute_skill)

### Flood Ablation Experiments (2026-02-26)
- **Ablation 1 (Run_1 COMPLETE, Run_2/3 PAUSED)**: `strict_no_etb` = strict minus extreme_threat_block → Insight 3
  - Script: `run_ablation_no_etb.py`, 3 seeds (42, 4202, 4203)
  - Output: `results/JOH_ABLATION_NO_ETB/gemma3_4b/Group_C_no_ETB/Run_{1,2,3}/`
  - **Run_1 Results** (vs Governed mean):
    | Metric | Governed (3 seeds) | Ablation no_etb (Run_1) | Change |
    |--------|:---:|:---:|:---:|
    | EHE | 0.860 ± 0.051 | 0.796 | ↓7.4% |
    | IBR | 0.8% | 6.4% | ↑8× |
    | No protection | 4.9% | 3.5% | similar |
    | Relocated | 13.3% | 5.2% | ↓2.5× |
    | Elevation only | 36.4% | 48.1% | ↑32% |
    | Ins + Elev | 38.2% | 35.5% | similar |
  - **Interpretation**: Removing one rule → relocation ↓2.5×, IBR ↑8×, diversity ↓ — supports Insight 3
  - **Insight linkage**: Core evidence for Insight 3; supplements Insight 1 (adaptation capacity) and Insight 2 (appraisal-action gap)
- **Ablation 2 (IN PROGRESS — Run_1)**: `disabled` = no governance rules → verify no_etb ≈ disabled
  - Script: `run_ablation_disabled.py`, running in background
  - Output: `results/JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_{1,2,3}/`
  - Same system as Group_C: humancentric memory + priority schema, ONLY rules disabled
  - Design: cascading effects = governance effect, not confound
  - **Purpose**: If disabled ≈ no_etb → confirms entire governance effect hinges on one rule (ETB)
- **LLMABMPMT-Final (Group_A)**: demoted to SI — different system entirely, not clean ablation
  - Label as "Baseline LLM" not "Ungoverned" in paper and figures

### Policy Counterfactual
- **No-ceiling ablation** (irrigation) — v20 data INVALID, v21 rerun queued
- **B1: Insurance premium doubling** (flood) — COMPLETE (9 runs), SI ONLY

### Paper Sections (v14 — 2026-02-24)
- **NatureWater_MainText_v14.docx**: COMPILED — Analysis format
- **NatureWater_SI_v14.docx**: Supplementary Information
- **Display items**: 2 tables + 4 figures

### Figures (Session AI — 2026-02-25 — Final Redesign)
- **Fig. 1**: Framework architecture (simulation loop)
- **Fig. 2**: Irrigation 3-panel — Insight 1 + Insight 2
  - (a) Mead stacked area × 3 conditions, ±1σ confidence bands (LLM=black, FQL=grey, 10 seeds)
  - (b) Basin demand rate vs shortage scatter, 10 FQL triangles
  - (c) WSA×ACA pie matrix — Insight 2 evidence (appraisal-conditional behavior)
- **Fig. 3**: Flood 3-panel (4-column, b/c swapped) — Insight 1 + Insight 2
  - (a) Rule-based | Ungoverned | Ablation TBD | Governed — absolute agent counts
  - (b) Before/after flood bars — simplified 2-part legend (color=condition, hatch=phase)
  - (c) TA×CA pie matrix — Insight 2 evidence (acute hazard binary pattern)
  - Legend inside Ungoverned panel (lower-right)
- **Fig. 4**: IBR×EHE scatter — Insight 3 evidence
  - (a) Irrigation: governed/no-ceiling/ungoverned clearly separated
  - (b) Flood: 6 models × governed/ungoverned + ablation TBD
- **Extended Data**: Cross-model forest plot (EHE)
- All figures: Okabe-Ito palette, ±1σ bands, NW-compliant, legends enlarged
- Old figures archived to `figures/archive/`

### Tables
- Table 1: Irrigation 4-condition (Governed / Ungoverned / No Ceiling / FQL)
- Table 2: Flood 3-condition (Governed / Rule-based PMT / Ungoverned)

### Text Edits (Session X)
- Abstract: sentences split, em dashes → commas
- Intro: Ostrom bridging clause, P7 shortened, dangling clause fixed
- Results: R1 shortage claim softened, R2/R3 "confirming"→"indicating"/"suggesting"
- Discussion: D1 comparison fixed, D2 overclaim softened, SI reference added
- **R1 rewritten** (Session W): Three-way comparison leads, coupling (r) defined with motivation

### Professor Briefing Materials (2026-02-24)
- Tables + talking points in `professor_briefing/`

### Data Completeness
- JOH_FINAL: 54/54 COMPLETE
- B1: 9/9 complete
- Rule-based: 3/3 complete
- Irrigation: 6/6 complete
- FQL Baseline: 10/10 COMPLETE (seeds 42-51, 42-44 re-run for consistency)

---

## Paper 3 (Multi-Agent Flood ABM) — NFIP RECALIBRATION IN PROGRESS

### Production (3 seeds) — PRE-RECALIBRATION
- seed_42: EPI=0.890 (7/8 PASS) — pre-bugfix
- seed_43: EPI=0.560 (5/8 PASS) — post-bugfix
- seed_44: EPI=0.615 (5/8 PASS) — post-bugfix
- Mean EPI = 0.689 ± 0.144, L1 ALL PASS all seeds

### NFIP Trajectory Recalibration (2026-02-25)
- **Problem**: Simulated insurance 23%→31% (ratchet up) vs observed 17%→12.5% (decline)
- **Expert panel**: 6 fixes (P1-P6), 70% structural + 30% prompt
- **P1-P5 code IMPLEMENTED**: Premium escalation, cost pressure, renewal fatigue, trajectory metric
- **P6 pending**: Paper discussion paragraph (after validation)
- **Phase A-D calibration**: Waiting for GPU availability
  - Phase A: 28 agents × 5yr (smoke test)
  - Phase B: 28 agents × 13yr (trajectory check)
  - Phase C: 400 agents × 13yr × 1 seed (full EPI)
  - Phase D: 400 agents × 13yr × 3 seeds (production)

### Flood Ablation Design Notes
- **extreme_threat_block**: 95.3% of all triggers in Group_C gemma3:4b (122/128)
- **Symmetric with irrigation**: ceiling=demand cap, extreme_threat_block=inaction cap
- **Small model effect**: 4B/3B trigger rules 10-20× more than 12B/27B
- **Group_C governed trigger rate**: 14.9% of decisions had failed_rules, but only 2.8% hard REJECTED
- **Governance = mostly nudge**: 97.2% APPROVED (many after retry), cascade matters more than blocking

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
