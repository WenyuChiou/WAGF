# Next Task

## Current: Paper 3 Flood ABM — smoke_v7 Prompt Fix

### COMPLETED: Insurance Premium Burden Prompt Fix (2026-02-15)
- **Problem**: mg_adaptation_gap direction reversed (MG 66% > NMG 61.5%) because LLM over-insures MG
- **Root cause**: Prompt shows `$current_premium/year` but never frames it as % of income
- **Fix**: `FinancialCostProvider` now generates `insurance_cost_text` with burden%:
  - `broker/components/context/providers.py` lines 651-676
  - Thresholds: <3% affordable, 3-7% moderate, 7-15% significant strain, >15% severe
  - MG: 41% at >15% (severe), NMG: 20% at >15%
  - Fills `{insurance_cost_text}` placeholder in both owner/renter prompts
- Tests: 10 provider tests + 169 paper3 tests ALL PASS

### NEXT: Run smoke_400x3_v7 and validate
- Run: `python examples/multi_agent/flood/run_unified_experiment.py` with same params as v6
- Expect: MG insurance rate decreases, mg_adaptation_gap direction corrects (NMG > MG)
- Validate: `python examples/multi_agent/flood/paper3/analysis/compute_validation_metrics.py`
- Target: EPI ≥ 0.60

### Key Findings from Previous Session (smoke_v6)
- **CP collapse is empirical reality** (survey r=0.042) — NOT a model bug
- **CACR_raw = 0.8314** → no need for larger model
- **4 EPI scenarios**: A=0.4176 (current), B=0.6154 (widen ranges), C=0.7802, D=0.7802
- **mg_gap decomposition**: Insurance reversal (MG 71.6% > NMG 63.1%), Structural correct (NMG > MG)
- All expert synthesis saved at `.ai/agent_results/smoke_v6_expert_synthesis.md`

---

## NW Paper (separate track)

### Phase 3: Policy Counterfactual (PENDING — needs user decision)
### Phase 4: Re-compile NW_Draft_v13.docx

## PENDING: Commit all changes
- Paper v8 sections + bootstrap analysis + scope corrections not committed
- Insurance burden prompt fix not committed
