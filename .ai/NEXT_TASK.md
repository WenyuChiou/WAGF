# Next Task: Re-run Disabled + Narrative Update (2026-02-26)

## CRITICAL BUG FIX: R5 Re-Elevation (Session AO)

### Bug Summary
`_inject_filtered_skills()` in `broker/core/_skill_filtering.py` overwrote context builder's
pre-filtered `available_skills`, re-injecting `elevate_house` for already-elevated agents.

### Fix Applied
`_skill_filtering.py:36-50` — now checks `context["available_skills"]` before overwriting;
only keeps action_ids that the context builder left in place.

### Impact on Data
- **ALL disabled Run_1 R5 violations (378 cases, 28.1%) are INVALID** — LLM was offered elevate_house as a valid option
- **Real ungoverned violation rate: ~6%** (R1=2.6%, R3≈0.5%, R4≈2.8%)
- Governed data UNAFFECTED (identity rules catch R5 at validator stage)
- no_etb data UNAFFECTED (has elevation_block identity rule)

### Narrative Adjustment Required
- **Old**: "34% of ungoverned decisions are wasted — R5 re-elevation dominates"
- **New**: "~6% of ungoverned decisions are irrational — inaction under high threat (R1) and overinvestment at low threat (R3/R4). Governance reduces this to <1%."
- R5 removed from violation analysis entirely
- "Behavioral bifurcation" framing drops R5 perseveration leg → simplify to R1 inaction focus
- Pie chart violation heatmap: recalculate WITHOUT R5 → much lower violation rates

## Fig 3 — 2×3 Layout UPDATED (Session AO)

### Naming Convention (教授修正)
- ~~Ungoverned~~ → **LLM (no validation)** — 有治理 prompt 但不驗證/執行
- 三條件：Rule-based | LLM (no validation) | Governed LLM

### Current Layout (7.09 × 7.0 in)
```
Row 1:  a1 (Rule-based)         a2 (LLM no val)      a3 (Governed LLM)   ← equal width
Row 2:  b (initial vs final)    c1 (no-val pie)       c2 (Gov pie)        ← b narrow, c1/c2 wide
```

### Panel Details
- **(a)**: Stacked bars, cumulative protection state, 3 conditions equal-width
- **(b)**: Multi-layer flood protection trajectory (line chart)
  - Y = % agents with (insurance+elevation) OR relocated
  - 3 lines: Rule-based (grey dashed), LLM no-val (orange), Governed (blue)
  - Flood markers (F) at Y3, Y4, Y9; individual runs as thin transparent lines
  - Water insight: governance builds resilience through layered protection; no-val plateaus at ~30-40%
- **(c)**: TA×CA pie matrix — violation heatmap needs recalc (exclude R5)
  - Run_1 only for both conditions (n=1000 each)

### Script: `paper/nature_water/scripts/gen_fig3_case2_flood.py`

## Water Insights (Updated after R5 bug fix)

### Insight 1 (panel b): Adaptation after flood events
> "Governance rules not only block irrational decisions, but also enable agents to adapt to changing water conditions."

### Insight 2 (panel c + cross-domain, LEAD INSIGHT): Acute vs chronic water stress cognition
> "Under chronic water stress (irrigation), agents calibrate to both threat AND coping capacity. Under acute flood hazard, threat overwhelms coping assessment entirely — governance rules substitute for the suppressed capacity judgment."
- Cross-domain ACA evidence confirmed (v20 data)
- CA-null = NW contribution

### Insight 3 (REVISED): Irrational decisions under no governance
> "~6% of ungoverned decisions are irrational: high-threat inaction and low-threat overinvestment. Governance rules reduce this to <1%."
- R5 REMOVED (was code bug, not LLM behavior)
- Smaller but cleaner number, more defensible

## Pipeline Status
```
Irrigation v21:
  Governed seed=42     ✅ COMPLETE (verified clean, IBR=37.8%, Mead 994-1160ft)
  Ungoverned seed=42   📋 Queued
  No-ceiling seed=42   📋 SI only

Flood disabled (R5 bug fix applied, data cleaned):
  Run_1 (seed=42)      📋 READY — old data archived to _archive_pre_r5fix/
  Run_2 (seed=4202)    📋 READY
  Run_3 (seed=4203)    📋 READY
  → User runs: python run_after_irrigation.py --skip-wait --force

Flood governed:
  Run_1/2/3            ✅ COMPLETE (unaffected by bug)

Flood no_etb:
  Run_1/2/3            ✅ COMPLETE (unaffected by bug)
```

## Immediate TODO
1. ✅ R5 bug fixed (`_skill_filtering.py`)
2. ✅ Panel (b) redesigned: multi-layer protection trajectory (water insight)
3. ✅ Naming: "Ungoverned" → "LLM (no validation)" throughout
4. 🔄 Flood disabled Run_1/2/3 re-running (pipeline started, irrigation complete)
5. 🔲 Update pie chart violation calc: exclude R5 from `compute_violations()`
6. 🔲 Update paper narrative (Insight 3 revised, violation % corrected)
7. 🔲 Wait for irrigation v21 ungoverned → update Fig 2
8. 🔲 NW expert re-review with corrected data
9. 🔲 Update results section draft
10. 🔲 Apply NW formatting fixes (hatching, font audit)
