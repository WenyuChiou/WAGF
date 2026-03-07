# Important Figure Inventory

Date: 2026-03-07

## Purpose

This inventory records the important figure assets currently used across the active manuscript lines:

- WRR water-sector framework paper workspace
- Nature Water manuscript workspace
- Paper 3 MA flood workspace

It is intended to prevent figure drift, duplicate exports, and accidental cross-paper mixing.

## 1. WRR Main Paper Figures

Source of truth:

- `paper/figures/fig1_architecture.png`
- `paper/figures/fig2_flood_combined.png`
- `paper/figures/fig3_irrigation.png`

Supporting scripts:

- `paper/shared/scripts/fig1_architecture.py`
- `paper/flood/scripts/fig2_flood_combined.py`
- `paper/irrigation/scripts/fig_wrr_irrigation.py`

Reference:

- `paper/PAPER_README.md`

Notes:

- These belong to the WRR paper line, not the Nature Water workspace.
- Keep them distinct from `paper/nature_water/figures/`.

## 2. WRR Supplementary Flood Figures

Source of truth:

- `paper/flood/figures/SI_Figure_Adaptation_Matrix_6x3.png`
- `paper/flood/figures/fig_s2_relocation.png`
- `paper/flood/figures/fig_s3_econ_hallucination.png`
- `paper/flood/figures/SI_Figure_Adaptation_Gemma3_3x3.png`
- `paper/flood/figures/SI_Figure_Adaptation_Ministral3_3x3.png`

Supporting scripts:

- `paper/flood/scripts/fig_s2_relocation.py`
- `paper/flood/scripts/fig_s3_econ_hallucination.py`
- `paper/flood/scripts/fig3_ebe_scaling.py`

Reference:

- `paper/PAPER_README.md`

## 3. Nature Water Canonical Figures

Current figure files present under `paper/nature_water/figures/`:

- `Fig1_framework.{png,pdf}`
- `Fig3_flood_case.{png,pdf}`
- `Fig3_pie_v3.{png,pdf}`
- `SFig_crossmodel_ehe_ibr.{png,pdf}`

Supporting scripts:

- `paper/nature_water/scripts/gen_framework_fig.py`
- `paper/nature_water/scripts/gen_fig2_case1_irrigation.py`
- `paper/nature_water/scripts/gen_fig3_case2_flood.py`
- `paper/nature_water/scripts/gen_fig3_crossmodel.py`

Compile target references:

- `paper/nature_water/scripts/compile_paper.py`

Important gap:

- `compile_paper.py` expects `paper/nature_water/figures/Fig2_irrigation_case.png`
- `gen_fig2_case1_irrigation.py` writes `Fig2_irrigation_case.{png,pdf}`
- As of 2026-03-07, `Fig2_irrigation_case.{png,pdf}` is not present in `paper/nature_water/figures/`

Operational rule:

- Treat the expected Nature Water main figure set as:
  - Fig 1: `Fig1_framework`
  - Fig 2: `Fig2_irrigation_case`
  - Fig 3: `Fig3_flood_case` and/or `Fig3_pie_v3` depending on current manuscript assembly
- Before final manuscript assembly, verify which of the Fig 3 assets is the canonical submission figure.

## 4. Nature Water Figure Candidates and Support Outputs

Secondary outputs currently produced or referenced by scripts:

- `Fig2c_prepost.{png,pdf}`
- `Fig_action_timeseries.{png,pdf}`
- `Fig3_cumulative_adaptation.{png,pdf}`

Rule:

- These should not be treated as canonical main-text figures unless explicitly promoted in the manuscript workspace.

## 5. Paper 3 MA Flood Canonical Figures

Source of truth:

- `examples/multi_agent/flood/paper3/analysis/figures/fig1_system_architecture.{png,pdf}`
- `examples/multi_agent/flood/paper3/analysis/figures/agent_spatial_distribution.{png,pdf}`

Supporting scripts:

- `examples/multi_agent/flood/paper3/analysis/fig_system_architecture.py`
- `examples/multi_agent/flood/paper3/analysis/fig_agent_spatial_distribution.py`

Reference:

- `examples/multi_agent/flood/paper3/analysis/figures/README.md`

Boundary:

- Paper 3 figures remain under the Paper 3 workspace.
- Nature Water may import final rendered exports if needed, but Paper 3 figure generation should not move into `paper/nature_water/`.

## 6. Immediate Follow-Up Checks

1. Regenerate or recover `paper/nature_water/figures/Fig2_irrigation_case.{png,pdf}` if Nature Water assembly still depends on it.
2. Confirm whether the current Nature Water main-text Fig 3 is:
   - `Fig3_flood_case`
   - `Fig3_pie_v3`
   - or a composed figure pipeline not yet exported
3. Keep WRR figures, Nature Water figures, and Paper 3 figures in separate directories and do not overwrite across paper lines.
