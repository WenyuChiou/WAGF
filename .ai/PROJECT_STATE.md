# WAGF Project State

## Active Experiments
- **Flood ABM 400x13yr**: seed42 complete (EPI=0.6703 PASS with updated benchmarks). Prompt fix for elevation_rate committed (7f92e7e). Needs re-run to verify elevation fix.
- **Irrigation ABM**: Pipeline running. seed42 complete, seed43 complete, seed44 in progress. 3 ungoverned remaining.
- **Gemma busy**: Someone using GPU, irrigation pipeline paused at seed44.

## C&V Module Status
- **P0 bugs FIXED** (uncommitted): EBE averaging, UNKNOWN sentinel, agent type inference
- **READMEs updated** (uncommitted): EN/ZH aligned, benchmark ranges current
- **Expert review complete**: 4 experts (LLM, social sci, water resources, CS prof). Word report at `paper3/analysis/CV_Module_Expert_Review_2026-02-14.docx`
- **Architecture plan**: 6-phase refactoring (Phase 0 done, Phases 1-5 planned)

## Key Metrics (400x13yr seed42, post-P0 fix)
- L1: CACR=0.8741, R_H=0.0002, EBE ratio=0.7398
- L2: EPI=0.6703, 6/8 benchmarks pass
- FAIL: elevation_rate=0.57 (max 0.35), mg_adaptation_gap=0.025 (min 0.05)
- 55 traces with UNKNOWN TP/CP excluded from CACR

## Paper Status
- Paper 1b (Nature Water): Drafts in paper/nature_water/drafts/
- Paper 3 (WRR): MA flood data complete, awaiting elevation fix verification
