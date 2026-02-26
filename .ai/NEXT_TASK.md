# Next Task: Run 3 Flood Disabled Seeds (2026-02-26)

## R5 Bug Fix — VERIFIED (Session AQ)
- **Root cause**: `TieredContextBuilder.build()` initializes `available_skills = []` (empty). `_inject_filtered_skills` sees falsy `pre_filtered` → skips intersection → overwrites with ALL 4 skills including `elevate_house`.
- **Fix**: `FinalContextBuilder.build()` now reads skills from `agent.config.skills` (non-empty), filters `elevate_house` for elevated agents, then sets `context['available_skills']`. The intersection in `_inject_filtered_skills` then correctly preserves the filtered list.
- **Pipeline test**: PASS — prompt shows only 3 options, `dynamic_skill_map` maps "2"→"relocate", `skill_map` resolves correctly.
- **Gov impact**: NONE — gov has identity_rules as second defense; FinalContextBuilder fix only affects the first defense layer.
- **Lesson**: On Windows, `__pycache__` cleanup with `find -exec rm` can silently fail. Always verify `.pyc` files are actually deleted before re-testing.

## Files Modified (Session AQ)
- `broker/core/_skill_filtering.py` — removed R5 debug traces (logic unchanged)
- `examples/single_agent/run_flood.py` — FinalContextBuilder.build() R5 fix (lines 130-138)
  - FROM: filter `context.get('available_skills', [])` (always empty)
  - TO: read `agent.config.skills` → filter → set `context['available_skills']`

## Cleaned Up
- Deleted invalid Run_1/Run_2 data (had R5 violations)
- Cleaned all `__pycache__` directories
- Cleaned temp test artifacts

## Immediate Next Steps
1. 🔲 **Git commit** the R5 fix + cleanup
2. 🔲 **Run 3 flood disabled seeds** (seeds 42, 43, 44)
   - `python run_flood.py --model gemma3:4b --years 13 --governance-mode disabled --seed 42 --output results/JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_1`
   - Same for seed 43 (Run_2), seed 44 (Run_3)
3. 🔲 **Verify figure data** is correct after runs complete
4. 🔲 Update Fig 2 with 3-condition data (FQL | disabled | governed)

## Fig 2 Current State (gen_fig2_case1_irrigation.py)
- 3 conditions: **Governed LLM** | **LLM (no validation)** | **Baseline (FQL)**
- Panel (a): stacked area + Mead + FQL
- Panel (b): Water demand vs Shortage years scatter
- Panel (c): WSA×ACA pie matrix
- Output: `Fig2_irrigation_case.{png,pdf}`
