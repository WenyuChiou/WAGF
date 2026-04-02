# Paper 3 Publication Figures

All main-text and supplementary figures for WRR submission.

## Directory Structure
```
figures/
├── main/           # Main text figures (Fig 1-8), WRR double-column 6.85in
├── supplementary/  # SM figures
├── scripts/        # Figure generation scripts (one per figure)
└── README.md
```

## Figure Inventory

### Main Text Figures

| Fig | Content | RQ | Status | Source Script | Notes |
|-----|---------|-----|--------|--------------|-------|
| 1 | Study area + agent spatial distribution | — | Exists (old) | `fig_agent_spatial_distribution.py` | Needs resize to 6.85in, Okabe-Ito palette |
| 2 | System architecture (3-tier WAGF) | — | **Use `docs/architecture.png`** | — | Resize to 6.85in, already good quality |
| 3 | RQ1: 6-panel Trad vs LLM trajectories | RQ1 | Exists | `rq1_publication_figure.py` | Needs: unify x-axis 2011-2023, Okabe-Ito, 6.85in, remove annotation boxes |
| 4 | RQ1: Reasoning trace keyword taxonomy | RQ1 | Exists | `rq1_reasoning_keywords.py` | Needs: Okabe-Ito, 6.85in |
| 5 | RQ2: Policy trajectory + equity (2x2) | RQ2 | Needs revision | `rq2_equity_figure.py` | Fix panels c/d: replace with proposed vs executed gap + affordability blocking |
| 6 | RQ3: SP/PA construct-action profiles | RQ3 | **NEW** | TBD | SP→behavior bars + PA→RL + 4-cell trapped profile |
| 7 | RQ3: PMT dynamics 4-panel | RQ3 | Exists | `rq3_pmt_dynamics.py` | Replace seed lines with mean+SD band, drop TP×CP heatmap (circular) |
| 8 | Validation benchmark summary | — | **NEW** | TBD | EPI + 4 benchmarks + ICC, compact table-figure |

### Supplementary Figures

| Fig | Content | Status | Source |
|-----|---------|--------|--------|
| S1 | Cross-seed robustness multipanel | Exists | `cross_seed_robustness.py` |
| S2 | Cross-seed action distribution | Exists | `cross_seed_robustness.py` |
| S3 | Cross-seed RQ2 Full vs Ablation | Exists | `cross_seed_robustness.py` |
| S4 | Cross-seed RQ3 PMT dynamics | Exists | `cross_seed_robustness.py` |
| S5 | TP decay curve | Exists | `rq3_pmt_dynamics.py` |
| S6 | Per-seed benchmark heatmap | Exists | `cross_seed_robustness.py` |

## Style Requirements (WRR)
- **Width**: 6.85 inches (double-column)
- **Font**: 8-10pt, sans-serif preferred
- **Color palette**: Okabe-Ito (colorblind-safe)
  - `#E69F00` (orange), `#56B4E9` (sky blue), `#009E73` (green), `#F0E442` (yellow)
  - `#0072B2` (blue), `#D55E00` (vermillion), `#CC79A7` (pink), `#000000` (black)
- **X-axis**: Calendar years 2011-2023 (not simulation years 1-13)
- **Format**: PNG (300 dpi) + PDF
- **Labels**: Panel labels (a), (b), (c), (d) in top-left corner

## Generation
```bash
cd examples/multi_agent/flood
python paper3/figures/scripts/fig3_rq1_trajectories.py   # → figures/main/fig3_rq1_trajectories.{png,pdf}
python paper3/figures/scripts/fig5_rq2_equity.py          # → figures/main/fig5_rq2_equity.{png,pdf}
```
