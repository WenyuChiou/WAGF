# Nature Water Workspace

This directory is the manuscript workspace for the Nature Water submission. It is intentionally separate from the multi-agent flood `paper3` runtime package.

## Source Of Truth

- Manuscript drafts: `paper/nature_water/drafts/`
- Final manuscript artifacts: `paper/nature_water/*.docx`
- Nature Water figures: `paper/nature_water/figures/`
- Nature Water tables: `paper/nature_water/tables/`
- Nature Water build scripts: `paper/nature_water/scripts/`

## Boundary Rules

- Do not write simulation outputs into this directory.
- Do not store MA flood runtime traces here.
- Scripts in this directory may read validated upstream results, but all Nature Water outputs must stay under `paper/nature_water/`.
- `examples/multi_agent/flood/paper3/results/` remains the MA flood result source of truth.

## Working Material

- `expert_reviews/`, `reviews/`, and `professor_briefing/` are manuscript-support folders.
- Historical or superseded figure candidates should stay in `figures/archive/`.

## Figure Inventory

- Important cross-paper figure inventory: `docs/plans/2026-03-07-important-figure-inventory.md`
- Before rebuilding the manuscript, verify that all canonical Nature Water figure exports referenced by `scripts/compile_paper.py` exist in `paper/nature_water/figures/`.
