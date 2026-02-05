# Paper 3: LLM-Governed Multi-Agent Flood Adaptation

## Quick Reference for AI Agents

This document enables AI agents to quickly understand the Paper 3 design and framework.

### What This Paper Does

- Uses LLM (Gemma 3 4B) to simulate 400 households' flood adaptation decisions
- 13-year simulation in Passaic River Basin, NJ
- 3-tier governance: Government → Insurance → Households
- Claims **structural plausibility** not prediction accuracy

### Target Journal

**Water Resources Research (WRR)**

---

## Key Concepts

| Term | Meaning |
|------|---------|
| MG | Marginalized Group (income<$50K OR housing_burden>30% OR no_vehicle) |
| NMG | Non-Marginalized Group |
| TP | Threat Perception (VL/L/M/H/VH) - perceived flood risk |
| CP | Coping Perception (VL/L/M/H/VH) - perceived ability to respond |
| PMT | Protection Motivation Theory - TP×CP → Action |
| SAGA | Semantic Agent Governance Architecture |
| ICC | Intraclass Correlation Coefficient (reliability measure) |
| EPI | Empirical Plausibility Index (aggregate validation) |
| CACR | Construct-Action Coherence Rate (per-decision validation) |
| R_H | Hallucination Rate (impossible action rate) |
| PRB | Passaic River Basin (study area) |
| SFHA | Special Flood Hazard Area (FEMA designation) |
| RCV | Replacement Cost Value (building + contents) |

---

## Data Sources (CRITICAL - DO NOT CONFUSE)

| Source | N | Used For | Type |
|--------|---|----------|------|
| Survey (NJ households) | 755 → 400 | Agent initialization | Empirical |
| Archetypes | 15 | L3 validation (ICC probing) | Manually designed |
| LLM Probing | 2,700 | ICC/eta² computation | LLM-generated |

**IMPORTANT**:
- Archetypes are **NOT** sampled from survey data
- Archetypes are manually designed to span demographic-situational extremes
- L3 validation is **independent** of the primary experiment
- L1/L2 validation uses experiment traces (52,000 decisions)

---

## Three Research Questions

| RQ | Question | Key Hypothesis | Key Figure |
|----|----------|----------------|------------|
| RQ1 | How does flood memory affect within-group adaptation divergence? | Flooded households adapt faster; MG gap is larger | Spaghetti plot |
| RQ2 | How does institutional feedback affect protection inequality? | Subsidy lag + premium spiral widens MG-NMG gap | Dual-axis time series |
| RQ3 | Which social information channel accelerates adaptation diffusion? | Gossip with reasoning > observation | Network visualization |

---

## Validation Metrics (Pass/Fail)

| Level | Metric | Threshold | Current Status |
|-------|--------|-----------|----------------|
| L1 Micro | CACR | ≥0.80 | ⏳ Pending |
| L1 Micro | R_H | ≤0.10 | ⏳ Pending |
| L1 Micro | EBE | >0 | ⏳ Pending |
| L2 Macro | EPI | ≥0.60 | ⏳ Pending |
| L3 Cognitive | ICC(2,1) | ≥0.60 | ✓ 0.964 |
| L3 Cognitive | eta² | ≥0.25 | ✓ 0.33 |
| L3 Sensitivity | Directional | ≥75% | ✓ 75% |

---

## 8 Empirical Benchmarks

| # | Metric | Range | Weight | Category |
|---|--------|-------|--------|----------|
| B1 | insurance_rate_sfha | 0.30-0.50 | 1.0 | AGGREGATE |
| B2 | insurance_rate_all | 0.15-0.40 | 0.8 | AGGREGATE |
| B3 | elevation_rate | 0.03-0.12 | 1.0 | AGGREGATE |
| B4 | buyout_rate | 0.02-0.15 | 0.8 | AGGREGATE |
| B5 | do_nothing_rate_postflood | 0.35-0.65 | 1.5 | CONDITIONAL |
| B6 | mg_adaptation_gap | 0.10-0.30 | **2.0** | DEMOGRAPHIC |
| B7 | rl_uninsured_rate | 0.15-0.40 | 1.0 | CONDITIONAL |
| B8 | insurance_lapse_rate | 0.05-0.15 | 1.0 | TEMPORAL |

---

## Directory Structure

```text
paper3/
├── analysis/
│   ├── figures/              # All paper figures (PNG + PDF)
│   │   ├── fig1_system_architecture.png
│   │   ├── agent_spatial_distribution.png
│   │   └── agent_distribution_stats.csv
│   ├── tables/               # Paper tables (CSV)
│   ├── fig_agent_spatial_distribution.py
│   ├── fig_system_architecture.py
│   ├── compute_validation_metrics.py
│   └── export_agent_initialization.py
│
├── data/                     # Supplementary data CSVs
│   ├── agent_initialization_complete.csv
│   ├── empirical_benchmarks.csv
│   └── icc_archetypes_definition.csv
│
├── results/
│   ├── cv/                   # L3 validation (pre-experiment)
│   │   ├── icc_report.json
│   │   ├── icc_responses.csv
│   │   └── persona_sensitivity_report.json
│   │
│   ├── validation/           # L1/L2 validation (post-experiment)
│   │   ├── validation_report.json
│   │   ├── l1_micro_metrics.json
│   │   └── l2_macro_metrics.json
│   │
│   └── paper3_primary/       # Experiment traces
│       └── seed_42/
│           └── gemma3_4b_strict/
│               └── raw/*.jsonl
│
├── configs/                  # Experiment configurations
│   ├── icc_archetypes.yaml
│   └── vignettes/
│
└── CLAUDE.local.md           # This file
```

---

## Key Commands

```bash
# Change to flood directory
cd examples/multi_agent/flood

# Generate spatial distribution figures
python paper3/analysis/fig_agent_spatial_distribution.py

# Run L3 validation (ICC probing)
python paper3/run_cv.py --mode icc --model gemma3:4b

# Run persona sensitivity test
python paper3/run_cv.py --mode persona_sensitivity --model gemma3:4b

# Compute L1/L2 metrics (after experiment)
python paper3/analysis/compute_validation_metrics.py \
    --traces paper3/results/paper3_primary/seed_42

# Export agent initialization data
python paper3/analysis/export_agent_initialization.py
```

---

## Governance Rules (PMT-based)

### Household Owners

| TP | CP | Allowed Actions |
|----|----|-----------------|
| VH/H | VH/H | elevate, buy_insurance, buyout |
| VH/H | M | buy_insurance, retrofit |
| VH/H | VL/L | do_nothing (fatalism allowed) |
| M | * | any reasonable action |
| VL/L | * | do_nothing, buy_insurance (optional) |

### Household Renters

| TP | CP | Allowed Actions |
|----|----|-----------------|
| VH/H | VH/H | buy_contents_insurance, relocate |
| VH/H | M | buy_contents_insurance |
| VH/H | VL/L | do_nothing (fatalism allowed) |
| M | * | any reasonable action |
| VL/L | * | do_nothing |

---

## SAGA 3-Tier Architecture

```text
Phase 1: Government (NJDEP)
    │ → Sets subsidy_rate
    ▼
Phase 2: Insurance (FEMA/CRS)
    │ → Sets crs_discount, premium_rate
    ▼
Phase 3: Households (400 agents)
    │ → Make adaptation decisions based on:
    │   - Updated subsidy/premium rates
    │   - Individual TP/CP assessments
    │   - Memory of past floods
    ▼
Environment Update
    │ → Apply PRB flood depths (2011-2023)
    │ → Calculate damages
    │ → Update agent memories
```

---

## File Naming Convention

- **Figures**: `fig{N}_{short_name}.png/pdf` (e.g., `fig1_system_architecture.png`)
- **Tables**: `table{N}_{short_name}.csv`
- **Data**: `{descriptive_name}.csv`
- **Scripts**: `fig_{short_name}.py` or `{verb}_{noun}.py`

---

## Agent Initialization Summary

- **Total Agents**: 400 (100 per cell)
- **4-Cell Design**: MG-Owner, MG-Renter, NMG-Owner, NMG-Renter
- **MG Criteria**: income < $50K OR housing_burden > 30% OR no_vehicle
- **Flood Zone Assignment**:
  - MG: 70% flood-prone, 30% dry
  - NMG: 50% flood-prone, 50% dry
- **RCV Generation**:
  - Owners: lognormal($280K/$400K median), σ=0.3
  - Renters: contents only, income-based
- **Initial Memories**: 6 categories (flood_experience, insurance, social, gov_trust, place, zone)

---

## Common Issues

1. **Survey vs Archetypes confusion**: Remember they are separate data sources
2. **L3 validation timing**: Must run BEFORE primary experiment
3. **Census Tract data**: Auto-downloaded from TIGER/Line when generating figures
4. **PRB raster years**: 2011-2023 (13 years), cycles if simulation > 13 years

---

*Last updated: 2026-02-05*
