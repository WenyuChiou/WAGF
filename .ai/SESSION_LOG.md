# Session Log

## Session BX (2026-03-09) — EHE/IBR Metric Fix + Analysis Cleanup

### Root Cause: EHE Discrepancy (0.631 vs 0.860)
- Paper EHE came from `gen_fig3_crossmodel.py` which uses **aggregate** entropy + `relocated` → `relocate`
- Previous fix wrongly used yearly-averaged EHE + excluded relocated rows
- Corrected to aggregate EHE: Gemma3-4B gov 3-seed = 0.8603 ≈ paper's 0.860 ✓

### Root Cause: IBR Discrepancy (11.46% vs 0.8%)
- Old script included R5 (re-elevation) in IBR
- Paper definition: IBR = R1+R3+R4 only, R5 excluded per EDT2
- Corrected: Gemma3-4B gov = 0.87% ≈ paper's 0.8% ✓

### Commit 993eff9
- Added corrected `compute_flood_metrics.py` (aggregate EHE, IBR without R5)
- Deleted 5 old scripts using Group_A as no-validator baseline:
  nw_b1_premium_analysis.py, nw_p0_flood_statistics.py, nw_p0_k_sensitivity.py,
  nw_p0_table1_s4_final.py, nw_rulebased_comparison.py

### PROJECT_STATE Updated
- Added definitive EHE/IBR calculation rules with "DO NOT" warnings
- Added comparison framework table clarifying Group_C vs Group_C_disabled
- Added canonical script references

---

## Session BW (2026-03-08) — Introduction Revision + Experiment Inventory

### Introduction Revision (v19 → v20)
- **Edit 1**: Merged P2+P3 into single paragraph (~175w, saved ~128w), all 20 citations retained
- **Edit 2**: Added bridge P3 paragraph emphasizing ABM structural limitations and why LLMs solve them
- **Edit 3**: Rewrote P6 as qualitative preview (no raw percentages)
- **3 rounds professor review**: 7.3 → 8.4 → 8.8 (PASS)
- **NW Reviewer assessment**: 7/10, flagged 8 concerns — all addressed
- **Prof Yang assessment**: flagged FQL ≠ "numerical optimisation", Hyun/Lin & Yang undersold — all fixed

### Key Fixes Applied
- FQL: "numerical optimisation" → "reinforcement learning", WAGF = complementary
- "order of magnitude" → "1.6-fold in irrigation to an order of magnitude in flood"
- "inherently linguistic" → observability argument with concrete examples
- Hyun & Yang (2019): independent sentence, Bayesian + watershed-scale
- Lin & Yang (2022): "advanced computational realism but, by design, do not expose..."
- Cross-model claim scoped to "in the flood domain"
- "ungoverned" → "agents operating without validators"
- Appraisal-action inconsistency: "failure of translation rather than of information access"

### Formatting Cleanup
- Removed 5 em dashes → commas/parentheses
- Removed 1 body semicolon → period
- Removed 1 informal colon → period
- GPT words cleaned: "tractability" → "computational realism", "active area of inquiry" → "is debated", "varies systematically" → "varies with model architecture and scale", "traceable justification alongside" → "explicit justification embedded in", double "deliberation" → single

### Experiment Inventory
- Irrigation v21: 5+5 seeds COMPLETE
- Flood governed (JOH_FINAL): 6 models × 5 seeds COMPLETE
- Flood no-validator (JOH_ABLATION_DISABLED): 6 models × 3 seeds (gemma3_4b/ministral3_3b have 5)
- User confirmed: DO NOT supplement ablation seeds, current data is final
- FQL baseline: 10 seeds COMPLETE

### Docx Compiled
- `NatureWater_MainText_v20.docx` + `NatureWater_SI_v20.docx`

---

## Session BV (2026-03-08) — Config Surface READMEs

Summary:
- Added short config-surface READMEs for the three primary reference implementations.

## Session BU (2026-03-08) — Single-Agent README Split

Summary:
- Split `examples/single_agent/README.md` into developer-facing and research-facing versions.

## Session BT-BQ (2026-03-08) — Design Audit + Decoupling

Summary:
- Systematic design audit completed
- Core-example decoupling Phase 1 (validator_bundles, artifacts)
- Example navigation simplified, config-surface READMEs added

## Sessions BF-BP (2026-03-07) — ABM Generalization + Release Readiness

Summary:
- 6-task ABM generalization plan executed (Tasks 1-6 all pass)
- Cognitive appraisal theory framework registered for irrigation
- Release readiness audit, repo boundary map, water-sector positioning
- Provider smoke utility added

## Sessions BA-BE (2026-03-07) — Group_B→C + SI Audit + Paper Polish

Summary:
- Group_B archived, SI reorganized (12→9 notes), Fig 4 demoted to SI
- v21 paper rewrite complete, professor review fixes applied
- EDT1/EDT2 formatting, overclaim fixes, file cleanup

## Earlier sessions: AV-AZ — see previous logs
---

## Session BX (2026-03-10) ??Paper3 MA Flood RQ Reframing

Summary:
- Reframed Paper 3 around intervention-based research questions
- Recommended main axis: institutional feedback and inequality formation
- Recommended secondary axis: social information contribution
- Explicitly excluded memory ablation as a primary RQ due to defense burden
- Added formal plan: `docs/plans/2026-03-10-paper3-ma-flood-rq-plan.md`
