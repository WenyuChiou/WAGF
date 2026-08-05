# World-state reweighting diagnostics

The manuscript reports two selected rungs of the frozen anchor-cell
stratification ladder. The published pooled residual is a direct-standardized
point estimate using the pooled distribution of comparable recorded-world
strata. The per-seed diagnostic is a separate estimate: each seed is
standardized on its own pooled stratum distribution and the paired interval is
computed across five seeds.

| World state used | Pooled coverage (governed / no-validator) | Pooled residual (pp) | Per-seed mean (95% CI) |
| --- | ---: | ---: | ---: |
| Shortage tier | 100.0% / 100.0% | -2.53 | -3.12 (-5.56, -0.68) |
| Tier + Mead elevation (25 ft) | 81.9% / 70.5% | -4.47 | -4.95 (-8.29, -1.62) |
| Tier + Mead (10 ft) + drought decile | 50.5% / 42.4% | +0.57 | -0.53 (-4.32, +3.25) |
| Tier + Mead + drought + agent cluster | 43.4% / 36.4% | +0.21 | -0.87 (-4.94, +3.19) |

The pooled and per-seed columns are not interchangeable estimators. The paper
therefore describes the pooled residual as descriptive and does not center a
per-seed interval on the pooled point estimate.
