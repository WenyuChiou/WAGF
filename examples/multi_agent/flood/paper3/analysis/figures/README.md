# Paper3 Figure Workspace

This directory contains the MA flood figure workspace for Paper 3.

## Canonical Tracked Figures

These are the currently tracked figure assets used as stable references inside the repository:

- `fig1_system_architecture.{png,pdf}`
- `agent_spatial_distribution.{png,pdf}`

They should remain at this top level unless all downstream references are updated together.

## Working Figure Material

Untracked or in-progress figure candidates, exports, and helper scripts belong under:

- `figures/working/candidates/`
- `figures/working/scripts/`
- `figures/working/archive/`

These working areas are ignored in git so they do not pollute the main Paper 3 runtime tree.

## Boundary Rule

- Paper 3 figures belong here, not under `paper/nature_water/`.
- Nature Water may import selected final figure exports, but its manuscript figures remain under `paper/nature_water/figures/`.
