# Smoke Test v6 Expert Panel Synthesis (2026-02-15)

## Panel
- Dr. Kevin Liu — LLM behavior specialist
- Dr. Sarah Chen — Social scientist / PMT expert
- Dr. Maria Gonzalez — Water resources engineer (PRB)
- Dr. James Park — ABM calibration / metrics specialist

## Consensus: 3 P0 Blockers Before Production

### P0.1: CP Collapse (κ=-0.013, 89.8% CP=M)
- **All 4 experts** flag as critical
- LLM cannot differentiate coping perception across income levels
- Root cause: abstract qualitative labels + RLHF central-tendency bias
- Fix: quantitative cost-burden anchors in prompt + consider CP_objective/CP_subjective split
- Success criteria: CP distribution ≥20% in L/VL, κ_CP ≥0.30

### P0.2: mg_adaptation_gap Direction Reversal (MG 66% > NMG 61.5%)
- MG adapts MORE than NMG — opposite of empirical reality
- Root cause: LLM "sympathy bias" + insurance dominance in composite metric
- Fix: MG insurance affordability gate (premium/income >4%) + barrier enumeration in prompt
- Dr. Park: "Cannot proceed to production without resolving"

### P0.3: REJECTED→do_nothing Conflation (280/1200 = 23.3%)
- Current: governance-blocked proposals mapped to "do_nothing" in benchmarks
- This conflates agent preference with system constraint
- Fix: separate behavioral metrics (exclude REJECTED) from governance metrics

## P1 Recommendations

### P1.1: Distance-Based EPI (Dr. Park)
- Binary in/out-of-range creates cliff effects for near-boundary results
- All 4 failures within 0.005-0.016 → continuous scoring would reward proximity
- Implementation: trapezoidal penalty function

### P1.2: Status Quo Bias (All experts)
- 7.7% genuine do_nothing vs 35-65% empirical
- Add normalized inaction framing in prompt: "40-60% of flooded HH choose do_nothing"
- Add cognitive cost descriptions (paperwork, displacement, uncertainty)

### P1.3: Benchmark Range Adjustments (Dr. Gonzalez)
- insurance_rate_all: widen to [0.15, 0.60] — post-Sandy NJ data supports
- do_nothing_postflood: widen to [0.30, 0.70] — cross-context uncertainty
- insurance_lapse: 3yr simulation mechanically insufficient for 5-9yr decay

### P1.4: Null Model Baseline (Dr. Park)
- Random agents expected EPI ~0.20
- Current 0.42 = 2× better than chance — meaningful even if below 0.60
- Essential for defending threshold choice

## Expected Impact
- Dr. Liu estimates P1 prompt batch (30-45 min) → EPI 0.42 → 0.64-0.68
- Dr. Chen: if κ_CP < 0.30 after fixes → drop PMT framing, pivot to satisficing heuristics
- Dr. Park: implement continuous EPI + fix mg_gap + exclude REJECTED → likely PASS

## Implementation Priority
1. Prompt fixes (CP anchors, status quo normalization, MG barriers) — 1hr
2. Metric fixes (continuous EPI, exclude REJECTED, null model) — 2hr
3. Governance fixes (MG insurance gate, INCOME_GATE threshold review) — 1hr
4. Re-run smoke test — 30min
5. If PASS → production 400×13yr
