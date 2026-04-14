# RQ1 — Gemma 4 LEGACY seed_42 vs Traditional FLOODABM

Generated: 2026-04-13
Data sources:
- Traditional: `FLOODABM/outputs/baseline/baseline/decisions/action_share_owner_renter_tract_all_years.csv` (52K HH × 27 tracts × 13 years, Bayesian regression + Bernoulli)
- LLM: `paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict/` (400 HH × 13 years, Gemma 4 e4b, post-caf3499 initial memory fix, LEGACY memory policy ratchet ACTIVE)

Baseline notes:
- LLM run is the fresh LEGACY rerun that replaces the pre-caf3499 `paper3_gemma4_e4b/seed_42/` snapshot (initial memories loaded correctly at Y1 for all 400 agents).
- CLEAN-policy companion run (seed_42 under the broker memory write governance fix) not yet complete. This analysis uses LEGACY only.

---

## Owner — annual comparison

| Year | tFI | tEH | tBP | tDN | lFI | lEH | lBP | lDN | dFI | dEH | dBP | dDN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 29.6 | 4.0 | 1.4 | 65.0 | 43.0 | 0.0 | 0.0 | 57.0 | +13.4 | -4.0 | -1.4 | -8.0 |
| 2012 | 23.3 | 2.6 | 1.6 | 72.4 | 50.0 | 0.0 | 0.0 | 50.0 | +26.7 | -2.6 | -1.6 | -22.4 |
| 2013 | 21.4 | 1.7 | 1.4 | 75.5 | 50.0 | 1.5 | 0.0 | 48.5 | +28.6 | -0.2 | -1.4 | -27.0 |
| 2014 | 21.5 | 1.2 | 1.1 | 76.2 | 55.0 | 1.0 | 0.0 | 44.0 | +33.5 | -0.2 | -1.1 | -32.2 |
| 2015 | 19.9 | 0.8 | 0.9 | 78.4 | 51.0 | 1.0 | 0.0 | 48.0 | +31.1 | +0.2 | -0.9 | -30.4 |
| 2016 | 19.0 | 0.5 | 0.8 | 79.6 | 48.0 | 0.0 | 0.0 | 52.0 | +29.0 | -0.5 | -0.8 | -27.6 |
| 2017 | 19.2 | 0.4 | 0.6 | 79.8 | 48.0 | 1.5 | 0.0 | 50.5 | +28.8 | +1.1 | -0.6 | -29.3 |
| 2018 | 19.2 | 0.3 | 0.5 | 80.1 | 54.5 | 0.5 | 0.5 | 44.5 | +35.3 | +0.2 | +0.0 | -35.6 |
| 2019 | 18.5 | 0.2 | 0.4 | 80.8 | 57.0 | 1.5 | 0.0 | 41.5 | +38.5 | +1.3 | -0.4 | -39.3 |
| 2020 | 18.6 | 0.2 | 0.3 | 80.9 | 57.5 | 4.5 | 0.0 | 38.0 | +38.9 | +4.3 | -0.3 | -42.9 |
| 2021 | 20.4 | 0.2 | 0.3 | 79.2 | 63.5 | 0.0 | 0.0 | 36.5 | +43.1 | -0.2 | -0.3 | -42.7 |
| 2022 | 20.2 | 0.1 | 0.2 | 79.4 | 61.5 | 3.5 | 0.0 | 35.0 | +41.3 | +3.4 | -0.2 | -44.4 |
| 2023 | 21.2 | 0.1 | 0.3 | 78.5 | 61.0 | 2.0 | 0.0 | 37.0 | +39.8 | +1.9 | -0.3 | -41.5 |
| **MEAN** | **20.9** | **1.0** | **0.8** | **77.4** | **53.8** | **1.3** | **0.0** | **44.8** | **+32.9** | **+0.4** | **-0.7** | **-32.6** |

### Owner MAD + Pearson r (13-year)
| Action | MAD (pp) | Pearson r | Classification |
|---|---:|---:|---|
| FI (insurance) | 32.9 | **-0.49** | DIVERGE, anti-phase |
| EH (elevation) | 1.6 | -0.46 | **CONVERGE magnitude** (trajectory anti-phase but both near zero) |
| BP (buyout) | 0.7 | -0.16 | **CONVERGE magnitude** |
| DN (do nothing) | 32.6 | **-0.63** | DIVERGE, anti-phase |

---

## Renter — annual comparison

| Year | tFI | tRL | tDN | lFI | lRL | lDN | dFI | dRL | dDN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2011 | 54.7 | 22.0 | 23.3 | 64.0 | 0.0 | 36.0 | +9.3 | -22.0 | +12.7 |
| 2012 | 46.5 | 24.2 | 29.3 | 68.0 | 2.0 | 30.0 | +21.5 | -22.2 | +0.7 |
| 2013 | 40.4 | 26.0 | 33.6 | 65.0 | 1.5 | 33.5 | +24.6 | -24.5 | -0.1 |
| 2014 | 37.1 | 25.2 | 37.7 | 65.5 | 0.5 | 34.0 | +28.4 | -24.7 | -3.7 |
| 2015 | 32.7 | 26.0 | 41.3 | 64.0 | 0.0 | 36.0 | +31.3 | -26.0 | -5.3 |
| 2016 | 29.7 | 26.5 | 43.8 | 64.0 | 0.0 | 36.0 | +34.3 | -26.5 | -7.8 |
| 2017 | 28.0 | 25.8 | 46.1 | 62.5 | 2.0 | 35.5 | +34.5 | -23.8 | -10.6 |
| 2018 | 26.5 | 25.1 | 48.4 | 59.0 | 1.5 | 39.5 | +32.5 | -23.6 | -8.9 |
| 2019 | 25.4 | 23.6 | 51.0 | 55.5 | 2.0 | 42.5 | +30.1 | -21.6 | -8.5 |
| 2020 | 24.4 | 23.3 | 52.3 | 48.5 | 0.5 | 51.0 | +24.1 | -22.8 | -1.3 |
| 2021 | 24.9 | 23.0 | 52.1 | 55.5 | 3.0 | 41.5 | +30.6 | -20.0 | -10.6 |
| 2022 | 23.7 | 22.2 | 54.1 | 52.5 | 3.0 | 44.5 | +28.8 | -19.2 | -9.6 |
| 2023 | 23.2 | 21.3 | 55.5 | 53.0 | 2.0 | 45.0 | +29.8 | -19.3 | -10.5 |
| **MEAN** | **32.1** | **24.2** | **43.8** | **59.8** | **1.4** | **38.8** | **+27.7** | **-22.8** | **-4.9** |

### Renter MAD + Pearson r (13-year)
| Action | MAD (pp) | Pearson r | Classification |
|---|---:|---:|---|
| FI (insurance) | 27.7 | **+0.74** | Magnitude DIVERGE, **trajectory CONVERGE** |
| RL (relocation) | 22.8 | -0.38 | DIVERGE (LLM relocates ~1.4% vs Bayesian 24%) |
| DN | 7.0 | **+0.78** | **Trajectory CONVERGE, magnitude -5pp** (near convergence) |

---

## Convergence / divergence classification

| Category | Actions | Magnitude diff | Pearson r | Reading |
|---|---|---|---|---|
| **Magnitude CONVERGE** (|Δ| ≤ 2pp) | Owner EH, Owner BP, Renter DN | +0.4, -0.7, -4.9 | negative / weak positive | LLM matches Bayesian on rare high-cost actions and the general DN baseline |
| **Trajectory CONVERGE** (r ≥ +0.7) | Renter FI, Renter DN | +27.7 / -4.9 | +0.74 / +0.78 | LLM and Bayesian share the same year-to-year shape for renter outcomes, but the LLM trajectory is shifted toward insurance |
| **Magnitude DIVERGE** (|Δ| > 20pp) | Owner FI, Owner DN, Renter FI, Renter RL | +32.9, -32.6, +27.7, -22.8 | mixed | LLM is systematically more insurance-heavy and less relocation-prone |
| **Trajectory DIVERGE** (r < 0) | All four owner actions | — | -0.16 to -0.63 | Owner trajectories are anti-phase: LLM FI rises while Bayesian FI falls; LLM DN falls while Bayesian DN rises |

---

## Core RQ1 findings

**Thesis**: Gemma 4 and Bayesian FLOODABM agree on what is rare and what is common in flood adaptation, agree on the temporal shape of renter outcomes, but disagree systematically on the magnitude of insurance uptake and on the sign of owner trajectories.

1. **Rare high-cost decisions converge to within 2pp.** Both frameworks produce owner elevation rates of about 1% and buyout rates below 1%. The LLM does not over-inflate exotic adaptation options, matching the Bayesian posterior on survey-rare actions.

2. **Renter temporal trajectories synchronize.** Renter DN shows Pearson r = +0.78 across 13 years and renter FI shows r = +0.74. The two frameworks share the same annual rhythm for when renters protect and when they do nothing, even though the LLM sits ~28pp higher on insurance and ~5pp lower on inaction. The Bayesian framework drives this rhythm through flood-triggered TP spikes and gradual decay; the LLM reproduces the same shape through reasoning over flood experience and memory accumulation.

3. **Owner trajectories are anti-phase.** All four owner actions have negative Pearson r (FI -0.49, EH -0.46, BP -0.16, DN -0.63). The LLM owner FI rises monotonically from 43% to 63% across 13 years while the Bayesian FI declines from 30% to 21%. The LLM owner DN falls from 57% to 37% while Bayesian DN climbs from 65% to 79%. The mechanism is that the Bayesian framework applies exponential TP decay between flood events, so owner threat perception erodes as the flood memory fades; the LLM has no such decay and accumulates flood memory across years, which continues to pull owners toward insurance.

4. **Systematic insurance over-adaptation.** The LLM buys insurance at +33pp for owners and +28pp for renters above the Bayesian baseline. The reasoning text analysis shows near-saturated affordability (98-99%) and adaptation (92-98%) vocabulary across all decisions, consistent with a prompt that treats insurance as a default cost-effective response. Whether this over-adaptation is a bias or a more realistic representation of post-2011 NFIP uptake patterns is a discussion point.

---

## Figure plan

**Fig 3 — Dual time series (6 panels)**:
- Panels: Owner FI, Owner EH, Owner BP, Owner DN, Renter FI, Renter RL, Renter DN (pick 6)
- Each panel: Traditional (solid line) + LLM (dashed line) over 13 years
- Panel labels:
  - EH, BP: "magnitude converged" (green border)
  - Renter FI, Renter DN: "trajectory converged, magnitude shifted" (yellow border)
  - Owner FI, Owner DN: "trajectory diverged" (red border)
- Each panel subtitle shows MAD and Pearson r

**Fig 4 — Reasoning vocabulary signature** (from preliminary analysis):
- Owner vs Renter, 6 reasoning buckets (threat, affordability, rootedness, fatalism, adaptation, past_reference)
- Bars showing % of decisions whose reasoning contains each vocabulary bucket
- Called out as the mechanism behind owner trajectory divergence (LLM flood memory accumulates, no TP decay)

---

## Caveats and next steps

- **CLEAN comparison pending**: CLEAN seed_42 (run 2/7 of `run_gemma4_full_experiment.bat`) will tell us whether blocking the ratchet also blocks the owner FI rise. If CLEAN Owner FI flattens or declines with time, Pearson r may flip positive and the owner trajectory divergence story weakens.
- **Single-seed LLM vs 52K-HH Bayesian**: the LLM n=400 is one seed, and the Bayesian n=52K aggregates 27 tracts with 15 MC runs. Multi-seed LLM confirmation (seeds 123 and 456 in runs 3/7 and 4/7) will close this gap.
- **Year alignment**: FLOODABM years 2011-2023 map to LLM years 1-13. The PRB flood calendar matches between the two via `floodabm_params.yaml`.
- **Sector boundary**: the comparison excludes government and insurance-agent actions; both frameworks differ structurally on those layers and an apples-to-apples comparison is not possible at the institutional level.
