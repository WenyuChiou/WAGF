# Session Log

## Session AV (2026-03-03) — Fig 3 Panel (b) Redesign + Experiment Management

### Fig 3b Design (v13→v22, 9+ iterations)
- v13: Cumulative insurance-years → GOV/DIS overlap (4.54 vs 4.62), rejected
- v14: First-difference delta line → "太單調了" (too monotonous)
- v15: Stacked area 3 rows → redundant with panel (a)
- v16: Diverging bars → professor vetoed pre/post flood comparison
- v17: Heatmap 3×10 → only 1 dimension
- v18: Ternary trajectory → "太擠" (bottom-edge crowding)
- v19/v19b: Phase space → wrong axis choice / bottom-heavy
- v20: Sparkline matrix 3×3 → user: "能變成一張圖嗎"
- v21: Compact 3×1 → user approved, flood years corrected to {3,4,9}
- **v22 (FINAL)**: Clean 3×1 with data-driven y-limits, subtle flood shading, gridlines

### Panel (b) Final Design
- 3 stacked sub-panels: Insurance / Elevation / Relocation rates (%)
- Each overlays 3 conditions: Governed LLM (blue), LLM no validator (orange), Traditional ABM (grey dashed)
- ±1 SE bands from 3 seeds, flood periods Y3-4 and Y9 shaded in light blue-grey
- Integrated into `gen_fig3_case2_flood.py` (replaces old EHE line chart)
- Layout fix: panel (c) shifted right (wspace 0.15→0.28) to prevent ylabel overlap

### Prototype Cleanup
- Removed 9 files: Fig3b_v20/v21/v22 .png/.pdf + gen_fig3b_v20/v21/v22 .py

### Flood Disabled Batch ✅ COMPLETE (18/18)
- All 6 models × 3 seeds finished (including gemma3:27b Run_2/3 which were pending)

### Irrigation v21 Pipeline 🔄 RUNNING
- User started: `run_nw_pipeline.py --skip-wait --start-from 2 --stop-at 10`
- seed42 already complete, seeds 43-46 governed + seeds 42-46 ungoverned queued
- No-ceiling ablation deferred (SI only)
- v20 outdated data archived to `_archive_outdated/`

### Resource Management
- Killed stale processes (PID 144320, 205292)
- Unloaded gemma3:27b from Ollama VRAM (14GB freed)

### Files Modified
- `paper/nature_water/scripts/gen_fig3_case2_flood.py`: panel (b) rewritten, layout adjusted
- `paper/nature_water/figures/Fig3_flood_case.{png,pdf}`: regenerated
- 9 prototype files deleted from `paper/nature_water/figures/`
- `.ai/NEXT_TASK.md`: updated experiment inventory + fig 3 status
- `.ai/SESSION_LOG.md`: this entry

---

## Session AT (2026-02-26) — Results/Discussion v17 + Experiment Inventory

### NW Analysis Format Confirmed
- Main text ≤ 4,000w (excl. Abstract, Methods, refs, legends)
- Abstract ≤ 150w, Display items ≤ 7, References ~50
- Subheadings in Results/Methods only; Discussion has NO subheadings

### Results v17 Written (`section2_v17_results.md`)
- R1: Validators enable scarcity-responsive behavior (~650w) — both domains
- R2: Non-compliance at scarcity × capacity boundary (~350w) — anticipatory extraction + CA null
- R3: Cross-model generalization (~250w) — 6 models, rule design > scale
- Table 1 (irrigation) + Table 2 (flood) — PMT IBR = "—" (not applicable)
- Demand-ceiling ablation, FQL, first-attempt diversity → all moved to SI
- Total Results: ~1,350w

### Discussion v17 Written (`section3_v17_discussion.md`)
- P1: Central finding + Ostrom parallel
- P2: Diagnostic capacity (anticipatory extraction audit trail)
- P3: NEW — CA null cross-domain insight (PMT theory test)
- P4: Scope conditions + limitations
- P5: Consistency + domain-transferability + outlook
- Total Discussion: ~790w

### Introduction P6 Corrected
- "twelvefold" → "sixteenfold" (actual: 0.6% → 9.7% ≈ 16×)
- "relocation nearly vanishes" → REMOVED (28% vs 22%, not dramatic)
- Added specific irrigation numbers: "IBR from 91% to 42%"

### Flood Data Verified (3-seed gemma3:4b)
| Condition | IBR | EHE | Relocation (cum) |
|-----------|-----|-----|-----------------|
| With validators | 0.6% ± 0.4% | 0.738 ± 0.038 | 28.0% ± 4.3% |
| Without validators | 9.7% ± 0.7% | 0.737 ± 0.003 | 22.3% ± 2.6% |
| Rule-based PMT | — | 0.752 ± 0.043 | 27.0% ± 12.0% |

### gemma3:12b No-validator Run_1 Analysis
- IBR ≈ 0.1% (very few H/VH threat appraisals, only 13/940)
- Insurance monoculture: 83% insurance, EHE=0.447
- Nearly identical to governed 12b — validators have minimal effect on this model
- 12b problem is behavioral monoculture, not inconsistency

### Experiment Inventory (see NEXT_TASK.md for full table)
- Flood governed: 18/18 ✅
- Flood no-validator: 3/18 complete, 1 running, 14 remaining
- Irrigation governed v21: 1/5 seeds ✅
- Irrigation no-validator v21: 0/5 seeds ❌
- FQL: 10/10 ✅

### Main Text Word Count
| Section | Words |
|---------|-------|
| Introduction | ~890 |
| Results | ~1,350 |
| Discussion | ~790 |
| **Total** | **~3,030 / 4,000** |

### Files Created/Modified
- `paper/nature_water/drafts/section2_v17_results.md`: NEW
- `paper/nature_water/drafts/section3_v17_discussion.md`: NEW
- `paper/nature_water/drafts/introduction_v10.md`: P6 corrections
- `paper/nature_water/scripts/gen_fig2_case1_irrigation.py`: ungov_dir_fn v21 fallback
- `.ai/NEXT_TASK.md`: full experiment inventory + priority list
- MEMORY.md: Prof. Yang review reminder + v17 status

---

## Session AS (2026-02-26) — Fig 2/3 Redesign + v20 Archive + 6-Model Batch

### Fig 3 Redesign
- **Panel (b)**: Multi-layer protection trajectory → **Per-year EHE (behavioural entropy)**
  - Shows LLM agents produce richer diversity than rule-based ABMs (the LLM unique value)
  - Rule-based: low flat EHE (~0.6), LLM: higher EHE (~0.7+), responsive to flood events
  - Function: `_compute_yearly_ehe()` replaces `_compute_multilayer_trajectory()`
- **Panel (c) violation colors**: Fixed — stronger colormap (white→orange→deep red), shared `vmax=100`
  - Both panels on same scale for direct comparison (disabled dark vs governed light)
- **Naming**: "LLM (no validation)" → **"LLM (no validator)"** across both Fig 2 and Fig 3 scripts

### Fig 2 Redesign
- **Panel (a)**: 3 sub-panels → **2 sub-panels** (FQL overlaid as dashed line in both)
  - Sub-panel 1: **Governed LLM** (stacked area + Mead + FQL dashed)
  - Sub-panel 2: **Governed LLM (no validator)** (stacked area + Mead + FQL dashed)
  - FQL no longer has its own dedicated sub-panel
- **Naming**: "LLM (no validator)" → **"Governed LLM (no validator)"** throughout
- Legend moved to no-validator panel, right y-axis (Mead) on rightmost panel

### v20 Data Archived
- Moved all v20 irrigation results to `examples/irrigation_abm/results/_archive_v20/`
  - 5× production_v20 (governed) + 5× ungoverned_v20 = 10 directories
- Remaining: `production_v21_42yr_seed42` (correct) + `ungoverned_v21_42yr_seed42` (incomplete, 173 traces)
- Prevents Fig 2 script from accidentally using broken v20 data

### Disabled Run_2 Analysis
- Run_2 complete: 923 traces (Year 1-10), 100 agents, R5=0, IBR=10.2%, EHE=0.739
- Consistent with Run_1 (IBR=8.9%, EHE=0.737) — stable across seeds

### 6-Model Disabled Batch Created
- Script: `examples/single_agent/run_flood_disabled_batch.py`
- Models (order): gemma3:12b → 27b → ministral3:3b → 8b → 14b → gemma3:4b
- 3 seeds each (42, 43, 44), --years 10, --governance-mode disabled
- 16 jobs total (gemma3_4b Run_1/2 skipped = already done)
- `--skip-existing` flag auto-skips completed runs
- User executing: `python run_flood_disabled_batch.py --skip-existing`

### Introduction P6 Rewritten
- "cognitive infrastructure" → "validation rules do not suppress behavioral diversity but redirect it"
- "governed vs ungoverned" → **"with validators vs without validators"** (CRITICAL naming fix)
- British "behaviour" → American "behavior" throughout P6
- Added: "irrational behavior increases twelvefold", "voluntary relocation nearly vanishes"
- Added: "threat-dominated reasoning in which coping appraisal plays no measurable role"

### Run_1 Data Cleanup
- Removed 302 traces (Year 11-13) from Run_1 JSONL
- Deduplicated 842 retry traces (format parsing retries) → 986 final traces
- Run_1 IBR corrected: 8.9% → 8.7% after dedup

### CRITICAL NAMING CONVENTION (updated in MEMORY.md)
- Both conditions use WAGF framework
- Comparison: **"with validators" vs "without validators"**, NOT "governed vs ungoverned"
- Figure labels: "Governed LLM" vs "Governed LLM (no validator)"
- Paper text: "With validators..." / "Without validators..."

### Files Modified
- `paper/nature_water/scripts/gen_fig3_case2_flood.py`: panel (b) EHE, violation colors, naming
- `paper/nature_water/scripts/gen_fig2_case1_irrigation.py`: 2-panel layout, naming
- `paper/nature_water/drafts/introduction_v10.md`: P6 rewritten (validator framing)
- `examples/single_agent/run_flood_disabled_batch.py`: NEW — 6-model batch runner
- `examples/irrigation_abm/results/_archive_v20/`: v20 data archived

---

## Session AR (2026-02-26) — Disabled Run_1 Analysis + Fig 3 JSONL Loader + IBR Comparison

### Year Count Mismatch Found
- Disabled Run_1 was started with `--years 13` (MA flood convention), but SA flood = **10 years**
- Governed runs (JOH_FINAL) confirmed: all Year 10 max
- **Resolution**: Run_1 data valid — filter `year <= 10`, discard Year 11-13
- Run_2/Run_3 should use default `--years 10` (no `--years` flag needed)

### gen_fig3_case2_flood.py — JSONL Fallback Loader
- Disabled runs produce `household_traces.jsonl` (not `simulation_log.csv` until complete)
- Added `_load_llm_run_from_traces()`: reads JSONL, flattens nested fields, filters `year <= max_year`
  - `approved_skill.skill_name` → `yearly_decision`
  - `skill_proposal.reasoning.TP_LABEL` → `threat_appraisal` (uppercased)
  - `skill_proposal.reasoning.CP_LABEL` → `coping_appraisal` (uppercased)
  - `state_after.{elevated, has_insurance, relocated}` → boolean columns
- `_load_llm_run_grouped()` now: prefer CSV → fallback JSONL
- CSV loader also adds `year <= 10` filter for consistency
- Fig 3 generated successfully: 2 disabled runs loaded (Run_1: 1828, Run_2: 56 in progress)

### Disabled Run_1 Analysis (Year 1-10, n=1828)
- **R5 violations: 0** ✅ (fix confirmed)
- Actions: buy_insurance 50.9%, do_nothing 36.9%, elevate_house 10.3%, relocate 1.9%
- Year 1-3: heavy elevation (25-35%), Year 4+: elevation stops (all upgraded)
- TP: M=49.4%, H=33.0%, L=9.6%, VH=5.1%, VL=2.9%
- CP: M=93.9% (near-uniform — no governance → no coping differentiation)
- Year 10 final state: 45.5% elevation-only, 53.3% ins+elev, 1.2% relocated
- EHE = 0.737

### Post-hoc IBR Comparison (Key Finding)
| Condition | IBR | R1 | R5 | EHE |
|-----------|-----|----|----|-----|
| Governed LLM (n=3) | **0.8%** ± 0.9% | 0.8% | 0 | 0.743 |
| Disabled LLM (n=1) | **8.9%** | 8.8% | 0 | 0.737 |
| Rule-based PMT (n=3) | N/A | N/A | N/A | 0.598 |

- Governance reduces IBR by **11×** (0.8% vs 8.9%)
- Nearly all violations = R1 (high threat + do_nothing)
- EHE nearly identical (0.743 vs 0.737) → governance ≠ less diversity, = smarter diversity
- Rule-based lowest EHE (0.598) → LLM agents inherently more diverse

### Files Modified
- `paper/nature_water/scripts/gen_fig3_case2_flood.py`: added JSONL loader + year<=10 filter
- `.ai/SESSION_LOG.md`, `.ai/NEXT_TASK.md`: updated

---

## Session AQ (2026-02-26) — R5 Root Cause Fix + Fig 2 Regeneration

### R5 Bug — TRUE Root Cause Found & Fixed
- Session AO fix was INCOMPLETE: added pre-filter intersection in `_skill_filtering.py`, but `FinalContextBuilder.build()` was filtering an EMPTY list (`available_skills=[]` from TieredContextBuilder default)
- **Root cause chain**:
  1. `TieredContextBuilder.build()` initializes `available_skills = []` (empty list)
  2. `FinalContextBuilder.build()` old code: filters `[]` → still `[]`
  3. `_inject_filtered_skills()`: `if pre_filtered:` → `[]` is falsy → SKIPS intersection
  4. Overwrites with all 4 skills including `elevate_house` for elevated agents
- **Fix** (run_flood.py lines 130-138): Read skills from `agent.config.skills` (non-empty), filter `elevate_house` if elevated, then set `context['available_skills']`
- **Pipeline test PASS**: prompt shows 3 options, dynamic_skill_map "2"→"relocate", skill_map resolves correctly
- **Gov impact**: NONE — gov has `identity_rules` as second defense layer
- **Lesson**: `__pycache__` on Windows can survive `find -exec rm -rf` — always verify deletion
- Commit: `c26c403`

### Cleanup
- Deleted invalid Run_1/Run_2 data (had R5 violations from buggy code)
- Removed debug traces from `_skill_filtering.py` (net zero change)
- Cleaned all `__pycache__`, test artifacts, temp files

### Fig 2 Regenerated (gen_fig2_case1_irrigation.py)
- 3 conditions: Governed LLM | LLM (no validation) | Baseline (FQL)
- Data: gov seed42=v21, seeds 43-46=v20 fallback; ungov=v20; FQL=seeds 42-51
- Action split: Gov 38.7% rejected, 48.6% chosen maintain | Ungov 8.7% rejected
- Output: `Fig2_irrigation_case.{png,pdf}`

### Flood Disabled Seeds — Running
- User manually running 3 seeds (42, 43, 44) with fixed code
- Results → `results/JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_{1,2,3}`

### Files Modified
- `examples/single_agent/run_flood.py`: FinalContextBuilder R5 fix + strict_no_etb CLI choice
- `broker/core/_skill_filtering.py`: debug traces removed (logic unchanged from Session AO)
- `.ai/NEXT_TASK.md`, `.ai/SESSION_LOG.md`: updated

## Session AP (2026-02-26) — Irrigation v21 Analysis + Fig 2 Consolidation

### Fig 2 Regenerated
- Updated `gen_fig2_irrigation.py` to prefer v21 data (governed seed42 from v21, seed43/44 fallback to v20)
- Also updated `compute_first_attempt_ehe()` for v21 audit
- v21 governed: EHE=0.710, IBR=0.410, DR=0.389, SY=14.3

### Maintain Behavior Analysis
- 58.7% of all decisions = maintain_demand
- **98.6% voluntary** (LLM chose maintain), only 1.4% governance-forced fallback
- WSA×ACA dual-appraisal confirmed: VL→100% maintain, H×H→39% maintain (61% increase)
- Governance REJECTED 1,194 decisions (36%) but ALL retried successfully — LLM self-corrected

### Request vs Diversion Mechanism
- `diversion = request × (1 - curtailment_ratio)` — mathematically exact
- 64.3% of agent-years: curtailment=0, request=diversion
- Shortage tiers: Tier1=5%, Tier2=10%, Tier3=20% curtailment
- Request is path-dependent: each year adjusts from previous year's request (not independent)

### Methods v3 Updated
- Added proxy framing: discrete actions = planting/operational decisions
- Added request→diversion explanation with feedback loop
- Decided NOT to add detailed curtailment/path-dependency (NW word limit)

### Key Insight: v21 More Conservative Than v20
- v21 fixed asymmetric base bug in execute_skill() → more maintain, less increase
- v20 maintain=1,448 vs v21 maintain=1,923 (seed42)
- Behavior more realistic: farmers are conservative, change slowly

### Fig 2 Consolidation
- Deleted old `gen_fig2_irrigation.py` (3-panel: stacked area + DR scatter + EHE bars)
- Kept `gen_fig2_case1_irrigation.py` as sole Fig 2 script (3-panel: stacked area + MAF scatter + pie matrix)
- Updated governed path: v21 preferred, v20 fallback
- Old `Fig2_irrigation.{png,pdf}` deleted

### Expert Panel Review
- 4 specialists: Water Resources Engineer, Agricultural Economist, ABM Scientist, Behavioral Psychologist
- Verdict: ACCEPT WITH MINOR REVISIONS (7.75/10)
- Key strength: WSA×ACA gradient is strongest validation artifact
- Key concern: DR=0.389 below real-world (but lower basin weighted DR=0.665 is realistic)
- Action items: n≥3 seeds for v21, justify 6.0 MAF ceiling, lead with relative comparison
- Saved: `examples/irrigation_abm/analysis/v21_expert_plausibility_review.md`

## Session AO (2026-02-26) — R5 Bug Fix + Narrative Correction

### CRITICAL BUG: R5 Re-Elevation Was Code Bug, Not LLM Hallucination
- **Root cause**: `_inject_filtered_skills()` in `broker/core/_skill_filtering.py` overwrote
  context builder's pre-filtered `available_skills` list with ALL action_ids from agent_types.yaml
- **Flow**: `run_flood.py` FinalContextBuilder correctly removes `elevate_house` when `elevated=True`
  → broker's `_inject_filtered_skills` overwrites with all 4 skills → LLM sees elevate_house as valid option
- **Secondary bug**: Skill registry precondition `"not elevated"` reads from empty `state` dict → always passes
- **378 R5 "violations"** in disabled Run_1 were LLM choosing a legitimately offered option

### Fix Applied
- `_skill_filtering.py:36-50`: Added pre-filter check — if `context["available_skills"]` already set,
  intersect with it rather than overwriting
- Verified: mock test confirms `elevate_house` excluded when context builder filters it
- Existing tests unaffected (pre-existing failures only: irrigation_integration, ma_reflection, tiered_builder)

### Narrative Impact
- **Old violation rate**: 34% (R5=28.1% + R1=2.6% + R3≈0.5% + R4≈2.8%)
- **Real violation rate**: ~6% (R1 + R3 + R4 only)
- Insight 3 revised: "~6% irrational" replaces "34% wasted"
- "Behavioral bifurcation" framing simplified: R5 perseveration leg removed
- Pie chart violation heatmap will be much lighter after recalculation

### Data Status
- Disabled Run_1/2/3: ALL need re-run with fixed code (R5 decisions will change)
- Governed data: unaffected (identity rules catch R5 at validator)
- no_etb data: unaffected (has elevation_block rule)

### Naming Correction (教授 feedback)
- ~~Ungoverned~~ → **LLM (no validation)** — disabled mode still has governance prompts, just no validation/enforcement
- Updated throughout: panel (a) titles, panel (b) legend, panel (c) titles, summary stats

### Panel (b) Redesign: 3 iterations
1. **Before/after flood** → 教授: 看不出差異
2. **Initial vs final state** → 與 panel (a) 重複（Y1 vs Y10 同資訊）
3. **Multi-layer protection trajectory** (FINAL) → NW expert panel 4-0 consensus
   - Line chart: % agents with (ins+elev) OR relocated, per year
   - 3 lines + flood markers (F at Y3/Y4/Y9) + individual run traces
   - **Water insight**: governance builds flood resilience through layered protection
     - Governed/Rule-based: 2% → 72-77% (flood-triggered jumps)
     - LLM no-val: 1% → 39% (plateaus, elevation monoculture)
   - EHE was rejected: no differentiation (all ~0.7-0.8)
- Functions: `_compute_multilayer_trajectory()`, `draw_panel_b()`

### Irrigation v21 seed42 Verified Clean
- 3276 rows (78×42), 0 NaN, 0 mismatches
- IBR=37.8% (v20 was 42%), Mead 994-1160ft, DR=0.401 stable
- ACA effect present but weaker than v20 (VL=0%→H=52%, v20 was 66-97%)
- Rejection rate 36.4%, all rejected → maintain (request unchanged: 100%)
- No governance_audit.csv in simulation_log (yearly_decision = PROPOSED, known logging bug)

### Data Cleanup
- Flood disabled Run_1: old buggy data moved to `_archive_pre_r5fix/` subfolder
  - Contains: simulation_log_pre_r5fix.csv + all old outputs (audit, config, etc.)
- Aborted pipeline remnants cleaned (empty reflection_log, partial household_traces)
- Run_1/2/3 directories ready for clean re-run
- User to run: `python run_after_irrigation.py --skip-wait --force`

### Files Modified
- `broker/core/_skill_filtering.py`: bug fix (pre-filter intersection)
- `paper/nature_water/scripts/gen_fig3_case2_flood.py`: panel (b) redesign + naming correction
- `.ai/NEXT_TASK.md`: updated with bug fix status + revised narrative + new panel (b)
- `.ai/SESSION_LOG.md`: this entry

---

## Session AN (2026-02-26) — Fig 3 Layout Overhaul + Water Insights + Pipeline

### Fig 3: 3-row → 2×3 Layout Redesign
- Started from 3-row layout (12in tall): a | b | c (two pie grids side-by-side)
- Multiple iterations: ylabel overlap, pie oval→circle, b-c spacing, cell size
- **NW expert panel** (4 specialists): score 3.1/5, P0=fonts below 5pt at 12in height
- **Solution**: 2×3 grid layout (7.09×7.0in)
  - Row 1: a1, a2, a3 (equal-width stacked bars) via nested GridSpec
  - Row 2: b (narrow, before/after), c1 (ungov pie), c2 (gov pie)
- Nested GridSpec: gs_row1 (equal 3-col) + gs_row2 (0.75:1.1:1.1)
- `draw_single_pie_grid()` replaces old `draw_panel_b()` (manual fig.add_axes)
- All legends/ticks → abbreviations: DN/FI/HE/RL, condition names full in panel (b)
- Pie chart: `aspect='equal', adjustable='box'` for circular pies
- Run_1 only for both conditions (n=1000 comparable, was 3000 vs 1000 bug)

### Water Insights Finalized (3 insights)
1. **Adaptation after flood** (panel b): "Governance rules not only block irrational decisions, but also enable agents to adapt to changing water conditions"
2. **Perception→action translation** (panel c, MAIN): "Same perception, different action — ungoverned agents respond with elevation monoculture regardless of threat; governed agents diversify proportional to risk. CA null-effect = governance as external coping scaffold"
3. **Wasted resources** (panel c violations, discussion): "34% ungoverned decisions wasted — R5 re-elevation dominates"
- User confirmed #1 and #2 as main text insights
- CA null-effect is a PMT theoretical contribution

### Pipeline Created
- `run_after_irrigation.py`: waits for irrigation v21 seed42 → runs flood disabled Run_2/3
- Polls every 2min for simulation_log.csv ≥3000 lines
- Flood disabled: seed=4202 (Run_2), seed=4203 (Run_3)

### CRITICAL DISCOVERY: ACA Effect Cross-Domain Comparison
- **Irrigation ACA = MASSIVE effect** (v20 data, 5 seeds):
  - ACA=VL/L: 0-1% increase, ~99% maintain
  - ACA=H/VH: 66-97% increase
  - Effect present in BOTH governed and ungoverned
- **Flood CA = NULL effect** (pie chart, all CA levels same within TA row)
- **Implication**: Acute (flood) vs chronic (irrigation) water stress → categorically different cognitive structures
- NW expert panel: CA-null is the real water insight, not polarization
- Reframe: "threat-dominated cognition" under acute hazard, governance = external coping scaffold
- **This is the Nature Water contribution** — only visible via cross-domain comparison

### NW Expert Panel Review (Session AN)
- 3 reviewers: Water Policy (3/5), NW Editor (2/5 current → 4+ with reframe), Behavioral Sci (3.5/5)
- Consensus: lead with CA-null, use "behavioral bifurcation" not "polarization"
- R5 = maladaptive coping (PMT term), connect to NFIP moral hazard literature
- Upgrade path clear: reframe around CA-null × governance interaction

### Files Modified
- `gen_fig3_case2_flood.py`: complete rewrite of layout + draw functions
- `run_after_irrigation.py`: NEW — post-irrigation pipeline
- `.ai/NEXT_TASK.md`: updated with current state + cross-domain discovery
- `.ai/SESSION_LOG.md`: this entry

---

## Session AL (2026-02-26) — Pipeline + Fig 3 Redesign + Disabled Analysis

### Fig 3 Panel (c) — Pie Matrix → Dose-Response Line Chart
- Iterated pie matrix backgrounds (5 approaches), none satisfying
- NW expert panel (4 specialists) consensus: pie matrix → SI, dose-response → main text
- **CA null-effect is a finding**: governance as external coping scaffold (PMT theoretical contribution)
- Replaced `draw_panel_b` (pie matrix) with dose-response line chart:
  - X: TA level (VL→VH), Y: protective action %
  - Two lines: Governed (ρ=1.000) vs Ablation no_etb (ρ=0.900)
  - Gap shading at H/VH, Δ=19-27pp annotation
  - Marker size ∝ sqrt(n), n= labels as "gov/abl" format

### Disabled Run_1 COMPLETE — Key Finding: disabled ≠ no_etb
- Pipeline ran flood disabled automatically, completed in ~2.5h
- **Surprise**: disabled better at H (92.6% vs 77.9%) but same at VH (~73%)
- **Elevation monoculture**: disabled 67.4% elevation-only (vs 53.3% no_etb, 48.9% governed)
- **Portfolio collapse**: Ins+Elev 19.7% (vs 35.5% no_etb, 38.2% governed)
- **Relocation vanishes**: 2.6% (vs 5.2% no_etb, 13.3% governed)
- **Implication**: Rules have TWO functions — ETB handles intensity (act vs don't), other rules handle breadth (which action)

### Insight 2 REFRAMED
- Old: "A single rule separates adaptive from arbitrary diversity"
- New: "Governance rules orchestrate both intensity and breadth of adaptive response — one rule ensures agents act under extreme threat; the full rule system distributes them across complementary protective strategies"

### Pipeline Setup
- Created `run_nw_priority_pipeline.py` — priority-first design (1 run/condition, then fill)
- Phase 1: disabled(✅) → irr governed(🔄) → irr ungoverned → irr noceil
- Phase 2: remaining seeds (14 experiments)
- Seed verification: all experiments use 42, 4202, 4203 (consistent with Group_C)

### Files Modified
- `gen_fig3_case2_flood.py`: replaced pie matrix with dose-response line chart
- `run_nw_priority_pipeline.py`: NEW — priority pipeline
- `run_nw_full_pipeline.py`: NEW — full pipeline (superseded by priority)
- `.ai/NEXT_TASK.md`: disabled results, updated insights, pipeline status
- `.ai/SESSION_LOG.md`: this entry

---

## Session AK (2026-02-26) — Ablation Analysis + Trace + Insight Reframe

### Ablation no_etb Run_1 Results
- EHE 0.860→0.796, IBR 0.8%→6.4%, Relocated 13.3%→5.2%
- Spearman ρ: Governed=1.000 vs Ablation=0.900 (dose-response weakens at high TA)
- Dose-response table: governed TA=VH 100% protective vs ablation 72.9%

### Trace Analysis — Protection Substitution Discovery
- 64 high-threat+do_nothing violations, 43 unique agents
- Pattern: almost all already elevated → "my house is protected, I don't need more"
- ETB rule's real role: push already-protected agents to consider ADDITIONAL measures

### Three → Two Water Insights (MERGED)
- New: 2 insights
  1. "Governance creates the appraisal-action link" (What + Why) → Fig 2 + Fig 3
  2. "A single rule separates adaptive from arbitrary diversity" (How much) → Fig 4

### Fig 3 Updated
- 4 conditions: Rule-based | Baseline LLM | Ablation (no ETB) | Governed
- Panel (c) pie matrix: multiple background color iterations (see Session AL for final)

---

## Session AJ (2026-02-26) — v21 Bug Fix + Flood Ablation Setup

### CRITICAL: Irrigation v20 Data Invalidated
- **Root cause**: `irrigation_env.py:588` `execute_skill()` used different bases for different skills
  - `increase`: base = `diversion` (compressed by curtailment + Powell, e.g., 108K)
  - `decrease`: base = `water_right` (full allocation, e.g., 198K)
  - `maintain`: base = `request` (paper demand, e.g., 198K)
- **Effect**: Governed agents (more rejections → more maintain → high request preserved) always had higher demand than ungoverned (increases from compressed diversion → low demand). This was an ARTIFACT, not real behavior.
- **Evidence**: Powell compresses UB diversion from 198K→108K (45%). increase_small(4%) on 108K=+4.3K, but maintain preserves 198K.
- **v21 fix**: All skills now use `agent["request"]` as base. Symmetric and correct.
- **Consequence**: ALL v20 irrigation results (IBR, EHE, demand ratios) are INVALID. Must use v21 data.

### Logging Bug Discovered
- `simulation_log.csv` `yearly_decision` column = PROPOSED skill (LLM intent), NOT executed skill
- For REJECTED proposals, fallback `maintain_demand` executes but log shows original skill name
- Ground truth: `governance_audit.csv` has `proposed_skill`, `final_skill`, `status` columns
- Governed rejection rate: 39.5% of all decisions
- Fig 2 stacked area updated to use audit trace, split maintain into `maintain_chosen` / `maintain_rejected`

### Flood Ablation Created
- New governance profile `strict_no_etb` in `agent_types.yaml` (lines 397-428)
- = Group_C strict minus `extreme_threat_block` (the rule that blocks do_nothing when TP=H/VH)
- Keeps: low_coping_block, relocation_threat_low, elevation_threat_low, elevation_block
- Batch script: `run_ablation_no_etb.py` — 3 seeds (42, 4202, 4203)
- `run_flood.py` updated: `strict_no_etb` added to `--governance-mode` choices

### Pipeline Updated
- `run_nw_pipeline.py` rewritten for v21: 15 experiments (gov/ungov/noceil × 5 seeds)
- Waits for flood ablation process to finish, then auto-starts irrigation
- Output dirs: `production_v21_*`, `ungoverned_v21_*`, `ablation_no_ceiling_v21_*`

### maintain_demand Discussion — RESOLVED
- Using `request` (not `diversion`) is correct for maintain
- Rationale: request = demand intention, diversion = physical delivery after constraints
- Using diversion would cause double-curtailment (update_agent_request re-applies curtailment)
- Real water rights holders don't permanently lower applications after one curtailment year

### Files Modified
- `irrigation_env.py`: v21 fix (line 588, 673)
- `agent_types.yaml`: added `strict_no_etb` governance profile
- `run_flood.py`: added `strict_no_etb` to choices
- `run_ablation_no_etb.py`: NEW — flood ablation batch runner
- `run_nw_pipeline.py`: rewritten for v21 full rerun
- `gen_fig2_case1_irrigation.py`: audit-based action correction (from previous session)

### Three Water Insights Updated
- Insight 1: "Governance rules not only block irrational decisions, but also enable agents to adapt to changing water conditions"
- Insight 2 (NEW): "LLM agents evaluate their environment but fail to act on that evaluation without governance — the appraisal-action link emerges only under [TBD wording]"
  - Replaces old "chronic vs acute" framing (too thin, NW panel rated ADEQUATE)
  - Lead with ungoverned FAILURE (counterintuitive), not governed success
  - Evidence: pie matrix + per-cell protective action % + marginal Spearman ρ + IBR
- Insight 3: "A single rule separates adaptive diversity from arbitrary diversity"

### Flood Experimental Design Clarified
- Group_A (LLMABMPMT-Final) = different system from Paper 1a → demote to SI
- Need clean "true ungoverned": same WAGF system, governance-mode=disabled
- Only disable governance rules; keep humancentric memory + priority schema
- Cascading effect = governance treatment effect, not confound
- Run order: no_etb (running) → disabled (queued) → irrigation v21

### Pending
- Flood ablation no_etb running (user executing, 3 seeds)
- Flood ablation disabled queued (need to create script)
- Irrigation v21 pipeline queued (15 experiments, auto-starts after flood)
- Tomorrow report: flood results + Three Water Insights + explain irrigation bug fix

---

## Session AI (2026-02-25) — Water Insights + Figure Redesign + FQL 10 Seeds

### Three Water Insights Defined (replacing R1-R4 framework-centric framing)
- Insight 1: Institutional rules = cognitive infrastructure (Fig 2a,b + Fig 3a,b)
- Insight 2: Chronic vs acute hazard institutional dynamics (Fig 2c + Fig 3c pie matrices)
- Insight 3: Single rule separates adaptive vs arbitrary diversity (Fig 4 + ablation)
- Key reframe: Insights are WATER findings, not framework validation

### Figure Changes
- **Fig 2(a)**: Added ±1σ confidence bands for both LLM (black) and FQL (grey) Mead lines
- **Fig 2(b)**: Now 10 FQL triangles (was 5), FQL_SEEDS=[42-51] separate from SEEDS=[42-46]
- **Fig 3**: Swapped panels b/c — (b)=before/after bars, (c)=TA×CA pie matrix — aligns with Insight mapping
- **Fig 3(b)**: Simplified legend from 6 entries → 5 (color=condition + hatch=before/after)
- **Fig 2(c)**: n= labels at grid bottom, legend ncol=5

### FQL Baseline: 10 Seeds Complete
- Seeds 42-51 all done; 42-44 re-run for consistency
- 10-seed stats: DR=0.344±0.039 (was 0.395), Shortage=13.6±8.8 (was 24.7), MinMead=1005±11
- High variability vs LLM stability is itself a finding

### Pending
- Flood ablation experiment (extreme_threat_block removal) → STARTED in Session AJ
- Table 1 update with 10-seed FQL
- Results section rewrite (insight-based)

---

## Session AH (2026-02-25) — R1-R4 Redefinition + Fig 2 Polish

### R1-R4 Redefined (domain-general)
- R1: Governance closes the appraisal-action gap
- R2: Removing a single rule increases diversity but degrades outcomes
- R3: Rule violations concentrate where perceived stress is highest
- R4 → SI: Cross-model replication moved to Extended Data

### Results Section Structure
- Case-based: Case 1 (irrigation) + Case 2 (flood), each covers R1-R3

---

## Earlier sessions: AG, AF, AE, AD, AB, AA, Z, Y, X — see previous log
