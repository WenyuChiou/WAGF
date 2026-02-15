# Session Log

## 2026-02-15 Session (current)

### Completed
1. **C&V Module P0 Fixes** (commit 38b718e): CGR, null-model, bootstrap CIs, BehavioralTheory protocol
2. **Smoke test v6** (400×3yr): EPI=0.4176 (FAIL), 4/8 benchmarks fail but all within 0.02 of boundary
3. **Expert panel analysis** (4 agents): Consensus on 3 P0 blockers:
   - CP collapse (κ=-0.013) — CONFIRMED as empirical reality from survey data (r=0.042)
   - mg_adaptation_gap reversal (MG 66% > NMG 61.5%) — insurance dominance
   - REJECTED→do_nothing conflation (280/1200 = 23.3%)
4. **Full PMT construct analysis** vs income (673 NJ survey respondents):
   - Only SC (r=0.123) and PA (r=0.147) correlate with income
   - TP, CP, SP all income-independent
   - TP is strongest behavior predictor (+0.61 for acted vs not)
5. **CACR_raw = 0.8314** → no need for Gemma 12B model size test
6. **Affordability ablation**: 4 EPI scenarios (A=0.4176, B=0.6154, C=0.7802, D=0.7802)
7. **mg_gap decomposition**:
   - Insurance: MG 71.6% > NMG 63.1% (REVERSED, gap=0.085)
   - Structural: MG 14.8% < NMG 19.1% (CORRECT, gap=0.042)
   - Insurance dominates composite → reversal
8. **Insurance burden prompt fix** (option 2, user-selected):
   - `FinancialCostProvider` now computes `insurance_burden_pct` and generates `insurance_cost_text`
   - Thresholds: <3% affordable, 3-7% moderate, 7-15% strain, >15% severe
   - MG: 41% at >15% (severe) vs NMG: 20% → expected to correct gap direction
   - Tests: 10 provider + 169 paper3 ALL PASS
9. Updated `.ai/NEXT_TASK.md` with fix details

### Pending (waiting for user command)
- Run smoke_400x3_v7 with insurance burden prompt fix
- Validate EPI ≥ 0.60

---

## 2026-02-14 Session

### Completed
1. Checked pipeline: gov_seed44 COMPLETE, ungov_seed42 COMPLETE, ungov_seed43 COMPLETE
2. EHE for seed44: 0.720 (more conservative, maintain 48%)
3. Ungoverned seed42: EHE=0.655, 81.5% increase, behavioral collapse
4. Ungoverned seed43: EHE=0.634, 77.4% increase, decrease_large=1
5. **Unified EHE calculation across both domains**:
   - Diagnosed discrepancy: per-year mean (0.638) vs aggregate (0.739)
   - Root cause: ensemble_analysis.py used per-year mean, flood used k_observed
   - Fix: all code now uses aggregate EHE with fixed k
   - Changed 4 files + 1 test, 169 tests pass
6. Updated .ai/ session persistence files
7. Generated NW_Draft_v10.docx

### Results
- Governed EHE: 0.738 ± 0.017 (3 seeds)
- Ungoverned EHE: 0.637 ± 0.017 (3 seeds)
- Scaffolding Delta: +0.101

---

## 2026-02-14 Earlier Session
- C&V expert review (10 experts, mean 3.29/5.0), P0 bug fixes, worktree refactoring

## 2026-02-13 Session
- Introduction v10 written (2 rounds dual-expert review)
- 6 Zotero refs added, 7 tagged
- Old drafts deleted, NW_Draft_v10.docx compiled
