# Traditional Bayesian ABM vs LLM-ABM Comparison

Generated: 2026-03-15
Data sources:
- Traditional: `FLOODABM/outputs/baseline/baseline/decisions/action_share_owner_renter_tract_all_years.csv` (single run, ~52K HH, 27 tracts)
- LLM-ABM: `paper3/results/paper3_hybrid_v2/seed_42/gemma3_4b_strict/` (seed_42, 400 HH, hybrid institutional)

---

## Key Convergence and Divergence (13-Year Average)

### Owners

| Action | Traditional | LLM-ABM | Diff | Assessment |
|--------|------------|---------|------|------------|
| Insurance (FI) | 20.9% | 35.1% | +14.2% | **LLM HIGHER** |
| Elevation (EH) | 0.9% | 13.5% | +12.6% | **LLM HIGHER** |
| Buyout (BP) | 0.8% | 3.9% | +3.2% | CONVERGE |
| Do Nothing (DN) | 77.4% | 47.5% | -29.9% | **LLM LOWER** |

### Renters

| Action | Traditional | LLM-ABM | Diff | Assessment |
|--------|------------|---------|------|------------|
| Insurance (FI) | 32.1% | 30.6% | -1.5% | **CONVERGE** |
| Relocate (RL) | 24.2% | 2.4% | -21.8% | **LLM LOWER** |
| Do Nothing (DN) | 43.7% | 67.0% | +23.3% | **LLM HIGHER** |

---

## Interpretation

### Where They Converge
1. **Owner Buyout (~4% vs ~1%)** — both models produce low buyout rates, consistent with empirical data (2-15% cumulative)
2. **Renter Insurance (~30% vs ~32%)** — remarkably close despite fundamentally different mechanisms

### Where They Diverge — and Why

**1. Owner Do Nothing: Trad=77% vs LLM=48% (Δ=-30%)**
- Traditional ABM: TP decays exponentially without floods → high inaction
- LLM-ABM: agents receive yearly flood, institutional prompts, gossip → more active
- **Likely cause**: Traditional ABM has TP decay making agents progressively passive; LLM agents re-evaluate each year with fresh context

**2. Owner Elevation: Trad=0.9% vs LLM=13.5% (Δ=+12.6%)**
- Traditional ABM: EH is ONE-TIME with low Bayesian probability → rapid decline to ~0.1%
- LLM-ABM: agents can propose elevation each year (validators check affordability)
- **Likely cause**: Different action model — Traditional treats EH as irreversible with diminishing probability; LLM treats it as yearly decision with governance constraints

**3. Renter Relocation: Trad=24% vs LLM=2.4% (Δ=-22%)**
- Traditional ABM: RL has ~25% steady-state Bayesian probability
- LLM-ABM: relocation requires overcoming prompt barriers (3+ floods, cost-benefit)
- **Likely cause**: Traditional ABM calibrated RL probability from survey intention data; LLM-ABM models the actual decision friction (moving costs, disruption, lease-breaking)
- **Critical question**: Which is more realistic? Survey intention ≠ actual relocation. LLM-ABM may be closer to observed behavior.

**4. Owner Insurance: Trad=21% vs LLM=35% (Δ=+14%)**
- Traditional ABM: FI probability decays with TP
- LLM-ABM: institutional feedback (CRS discounts, subsidy) promotes insurance uptake
- **Likely cause**: 3-tier institutional agents actively encourage insurance; Traditional ABM has no institutional feedback

---

## Notes for Paper
- Traditional ABM uses ~52K agents vs LLM-ABM 400 → compare RATES not counts
- Traditional ABM has NO institutional agents, NO social network
- Traditional ABM MG = tract-level tenure mix; LLM-ABM MG = individual socioeconomic
- Monte Carlo results not yet available (outputs/montecarlo_v2 empty) — need to run Traditional ABM MC for confidence bands
- LLM-ABM currently single seed — need 3-5 seeds for fair comparison

---

## Yearly Data Tables

### Owners

| Year | T_FI | L_FI | T_EH | L_EH | T_BP | L_BP | T_DN | L_DN |
|------|------|------|------|------|------|------|------|------|
| 2011 | 29.6 | 27.5 | 4.0 | 31.0 | 1.4 | 0.0 | 65.0 | 41.5 |
| 2012 | 23.3 | 32.5 | 2.6 | 16.5 | 1.6 | 3.0 | 72.4 | 48.0 |
| 2013 | 21.4 | 32.5 | 1.7 | 17.0 | 1.4 | 5.5 | 75.5 | 45.0 |
| 2014 | 21.5 | 42.5 | 1.2 | 12.5 | 1.1 | 4.0 | 76.2 | 41.0 |
| 2015 | 19.9 | 41.0 | 0.8 | 14.0 | 0.9 | 5.5 | 78.4 | 39.5 |
| 2016 | 19.0 | 36.0 | 0.5 | 13.5 | 0.8 | 5.0 | 79.6 | 45.5 |
| 2017 | 19.2 | 36.5 | 0.4 | 12.5 | 0.6 | 3.5 | 79.8 | 47.5 |
| 2018 | 19.2 | 32.5 | 0.3 | 8.5 | 0.5 | 7.0 | 80.1 | 52.0 |
| 2019 | 18.5 | 33.5 | 0.2 | 8.5 | 0.4 | 3.5 | 80.8 | 54.5 |
| 2020 | 18.6 | 35.5 | 0.2 | 8.5 | 0.3 | 1.5 | 80.9 | 54.5 |
| 2021 | 20.4 | 37.0 | 0.2 | 8.0 | 0.3 | 3.0 | 79.2 | 52.0 |
| 2022 | 20.2 | 32.5 | 0.1 | 15.0 | 0.2 | 4.5 | 79.4 | 48.0 |
| 2023 | 21.2 | 37.0 | 0.1 | 10.0 | 0.3 | 5.0 | 78.5 | 48.0 |

### Renters

| Year | T_FI | L_FI | T_RL | L_RL | T_DN | L_DN |
|------|------|------|------|------|------|------|
| 2011 | 54.7 | 51.5 | 22.0 | 0.0 | 23.3 | 48.5 |
| 2012 | 46.5 | 34.0 | 24.2 | 2.5 | 29.3 | 63.5 |
| 2013 | 40.4 | 37.5 | 26.0 | 3.5 | 33.6 | 59.0 |
| 2014 | 37.1 | 38.5 | 25.2 | 6.5 | 37.7 | 55.0 |
| 2015 | 32.7 | 33.0 | 26.0 | 3.0 | 41.3 | 64.0 |
| 2016 | 29.7 | 36.0 | 26.5 | 0.5 | 43.8 | 63.5 |
| 2017 | 28.0 | 23.0 | 25.8 | 1.5 | 46.1 | 75.5 |
| 2018 | 26.5 | 19.0 | 25.1 | 3.5 | 48.4 | 77.5 |
| 2019 | 25.4 | 18.0 | 23.6 | 2.0 | 51.0 | 80.0 |
| 2020 | 24.4 | 15.5 | 23.3 | 0.5 | 52.3 | 84.0 |
| 2021 | 24.9 | 32.0 | 23.0 | 3.5 | 52.1 | 64.5 |
| 2022 | 23.7 | 31.0 | 22.2 | 3.0 | 54.1 | 66.0 |
| 2023 | 23.2 | 28.5 | 21.3 | 1.0 | 55.5 | 70.5 |
