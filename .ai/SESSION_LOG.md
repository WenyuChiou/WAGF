# Session Log

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
