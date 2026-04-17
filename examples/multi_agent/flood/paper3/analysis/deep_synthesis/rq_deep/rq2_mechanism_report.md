# RQ2 Mechanism Decomposition

Effective premium burden is computed as:

`premium_rate * (1 - crs_discount) * (1 - subsidy_rate) * property_value / income * 100`

## Lowest-Burden Owner Protection

| arm         |   protection_rate |   dn_rate |   premium_burden_mean |   n_decisions |
|:------------|------------------:|----------:|----------------------:|--------------:|
| LEG_Full_42 |          0.741538 |  0.258462 |               1.64762 |           650 |
| CLN_Flat_42 |          0.696923 |  0.303077 |               2.19442 |           650 |
| CLN_Full_42 |          0.696923 |  0.303077 |               1.70198 |           650 |

## Lowest-Burden Renter Protection

| arm         |   protection_rate |   dn_rate |   premium_burden_mean |   n_decisions |
|:------------|------------------:|----------:|----------------------:|--------------:|
| LEG_Full_42 |          0.621538 |  0.378462 |              0.208326 |           650 |
| CLN_Flat_42 |          0.601538 |  0.398462 |              0.274008 |           650 |
| CLN_Full_42 |          0.595385 |  0.404615 |              0.213264 |           650 |

## Yearly Premium Burden Summary

| arm          | agent_type   |   premium_burden_mean |
|:-------------|:-------------|----------------------:|
| CLN_Flat_123 | owner        |              5.63002  |
| CLN_Flat_123 | renter       |              0.466177 |
| CLN_Flat_42  | owner        |              5.62968  |
| CLN_Flat_42  | renter       |              0.466177 |
| CLN_Flat_456 | owner        |              5.62968  |
| CLN_Flat_456 | renter       |              0.466177 |
| CLN_Full_123 | owner        |              4.6961   |
| CLN_Full_123 | renter       |              0.388871 |
| CLN_Full_42  | owner        |              4.34234  |
| CLN_Full_42  | renter       |              0.359576 |
| LEG_Full_42  | owner        |              4.14413  |
| LEG_Full_42  | renter       |              0.343164 |
