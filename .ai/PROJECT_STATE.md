# WAGF Project State

## ⚠️ PAPER SCOPE — READ FIRST
- **Paper 1b (Nature Water)**: SINGLE-AGENT experiments only (flood + irrigation)
- **Paper 3 (flood ABM)**: MULTI-AGENT experiments (400 agents, 12 skills, EPI benchmarks)
- **NEVER mix data between papers** — no buyout, no EPI, no MA flood data in NW paper

## Nature Water Paper (Paper 1b) — ACTIVE

### Experiments Used
| Domain | Architecture | Agents | Duration | Skills | Seeds/Runs | Model |
|--------|-------------|--------|----------|--------|------------|-------|
| **Flood** | Single-agent | 100 | 10yr | 4 (insurance, elevation, relocation, do_nothing) | 3 runs × 6 models × 3 groups | Gemma-3 4B/12B/27B, Ministral 3B/8B/14B |
| **Irrigation** | Single-agent | 78 CRSS | 42yr | 5 (increase_large/small, maintain, decrease_small/large) | 3 seeds × 2 conditions | Gemma-3 4B |

### What NW Paper Does NOT Have
- NO buyout skill (that's multi-agent flood only)
- NO EPI/L2 empirical benchmarks (EPI=0.78 belongs to Paper 3)
- NO multi-agent coordination or social dynamics
- NO 400-agent runs

### Key Results (Single-Agent)
- **Irrigation EHE (primary)**: Governed 0.738 ± 0.017 vs ungoverned 0.637 ± 0.017 (3 seeds, ROBUST)
- **Bootstrap 95% CI**: EHE difference [0.078, 0.122], zero overlap, d=6.0
- **Flood scaffolding (S4, k=4)**: 2/6 Yes, 2/6 Marginal, 2/6 Reversed — MODEL-DEPENDENT
- **Flood pooled CI**: +0.047 [−0.064, 0.172] — DOES NOT exclude zero
- **Composite action ("both")**: 2.6%–79.0% across models — LLM artifact, not diversity
- **First-attempt EHE**: Governed 0.761 vs ungoverned 0.640 (irrigation, not retry artefact)
- **Null-model CACR**: random=60%, governed=58%, ungoverned=9.4%
- **Cross-domain**: Irrigation 0.738 vs flood 0.754 (similar but flood CI wider)

### Water-System Outcomes (Irrigation)
- Governed agents use MORE water (demand ratio 0.394 vs 0.288)
- Governed Mead is LOWER (mean ~1094 ft vs ~1173 ft) — NOT commons collapse
- Governed agents are drought-responsive (r=0.547 vs r=0.378)
- Story: "adaptive demand management" — governance enables responsive extraction, not conservation

### Paper Sections
- **abstract_v6.md** (contains v9): Model-dependent flood framing, irrigation-first structure
- **introduction_v10.md**: FINAL
- **section2_v5_results.md** (contains v9): S4 Table 1 (3-run, k=4), honest flood framing
- **section3_v7_discussion.md** (contains v10): Model-dependent discussion, composite-action analysis
- **methods_v1.md** (v2): Added composite-action handling paragraph + k specification
- **supplementary_table_s1.md**: 4-scenario k sensitivity analysis (NEW)
- **supplementary_table_s1.md**: 4-scenario k sensitivity (NEW)
- **NW_Draft_v13.docx**: COMPILED (28.5 KB) — includes water-system outcomes + S4 Table 1

### Expert Panel Reviews
- **R1**: 5 reviewers, mean 3.1/5 → `expert_reviews/NW_Expert_Panel_Review.md`
- **R2**: ABM-limitation discussion, mean 3.5/5 → `expert_reviews/NW_Expert_Discussion_R2.md`
- **NOTE**: R2 agents were given incorrect info about EPI/buyout — recommendations about EPI tables and buyout scenarios are invalid

---

## Irrigation Pipeline — COMPLETE (2026-02-14, 37.3h total)

### All 6 Experiments (3 governed + 3 ungoverned)

| Seed | Governed EHE | Ungoverned EHE | Gov increase% | Ungov increase% |
|------|-------------|----------------|---------------|-----------------|
| 42 | 0.739 | 0.655 | 52.1% | 81.5% |
| 43 | 0.754 | 0.634 | 56.8% | 77.4% |
| 44 | 0.720 | 0.622 | 49.1% | 80.5% |

### IBR Decomposition
- Governed: 39.5% rejection, 61.9% retry rate, 0.7% fallback
- Ungoverned: 7.4% rejection, 9.1% retry rate, 0.1% fallback
- WSA coherence: governed 58.0% vs ungoverned 9.4%

---

## Paper 3 (Multi-Agent Flood ABM) — SEPARATE PAPER

### What Paper 3 Has (NOT in NW paper)
- 400 agents × 13yr, 12 skills (including buyout), per-agent-depth
- L2 empirical benchmarks (insurance_sfha, renter_uninsured, buyout, etc.)
- Multi-agent social dynamics, coordination

### Status: smoke_v6 DONE, prompt fix applied, v7 pending

#### smoke_v6 Results (400×3yr)
- EPI = 0.4176 (FAIL), 4/8 pass, 4 fail within 0.02 of boundary
- L1: CACR=0.9591, CACR_raw=0.8314, R_H=0.0
- CGR: kappa_tp=0.42, kappa_cp=-0.013 (CP collapse = empirical reality)
- mg_adaptation_gap REVERSED: MG 66% > NMG 61.5% (insurance dominates)

#### Key Findings
- **CP collapse is empirical** (survey r=0.042) — NOT a model bug
- **Only SC/PA correlate with income** (r=0.12, 0.15); TP/CP/SP income-independent
- **mg_gap decomposition**: Insurance reversal (MG>NMG), structural correct (NMG>MG)
- **REJECTED→do_nothing**: 280/1200 (23.3%), 95.4% of MG elevations blocked

#### Applied Fix: Insurance Premium Burden Prompt
- `FinancialCostProvider` generates `insurance_cost_text` with burden%
- MG: 41% at >15% ("severe"), NMG: 20% → expected to correct gap
- File: `broker/components/context/providers.py` lines 651-676
- Tests: all pass

#### Next: smoke_v7 (waiting for user command)

---

## EHE Calculation — UNIFIED
- Method: Aggregate EHE, fixed k = action space size
- Files: l1_micro.py, engine.py, compute_ibr.py, ensemble_analysis.py
- Tests: 169 passed

## C&V Module
- Expert panel review complete (10 experts, mean 3.29/5.0)
- P0 quick wins identified, pending user approval
