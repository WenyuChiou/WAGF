# RQ3 Five-Step Chain

## Step 1 Construct Validity

| arm          | agent_type   |   n_decisions | reason_source    |   TP_flood_risk_pct |   SP_government_trust_pct |   PA_home_attachment_pct |
|:-------------|:-------------|--------------:|:-----------------|--------------------:|--------------------------:|-------------------------:|
| CLN_Flat_123 | owner        |          2599 | per_construct    |            0.888419 |               0.433244    |                 0.896114 |
| CLN_Flat_123 | renter       |          2600 | integrated_prose |            0.943077 |               0.000384615 |                 0.468462 |
| CLN_Flat_42  | owner        |          2600 | per_construct    |            0.871154 |               0.398077    |                 0.901154 |
| CLN_Flat_42  | renter       |          2600 | integrated_prose |            0.936538 |               0.00153846  |                 0.464615 |
| CLN_Flat_456 | owner        |          2600 | per_construct    |            0.906538 |               0.45        |                 0.880769 |
| CLN_Flat_456 | renter       |          2600 | integrated_prose |            0.958077 |               0           |                 0.478462 |
| CLN_Full_123 | owner        |          2600 | per_construct    |            0.901923 |               0.234615    |                 0.895    |
| CLN_Full_123 | renter       |          2600 | integrated_prose |            0.941154 |               0.00192308  |                 0.444615 |
| CLN_Full_42  | owner        |          2600 | per_construct    |            0.881538 |               0.267308    |                 0.891154 |
| CLN_Full_42  | renter       |          2600 | integrated_prose |            0.938846 |               0.00884615  |                 0.447308 |
| LEG_Full_42  | owner        |          2600 | per_construct    |            0.798846 |               0.204231    |                 0.872692 |
| LEG_Full_42  | renter       |          2600 | integrated_prose |            0.898846 |               0.0215385   |                 0.714615 |

## Step 2 Cross-Sectional Tables

| arm          | level   |      rate |    n | analysis           |
|:-------------|:--------|----------:|-----:|:-------------------|
| CLN_Flat_123 | H       | 0.875097  | 1289 | sp_protection_rate |
| CLN_Flat_123 | L       | 0.035533  |  788 | sp_protection_rate |
| CLN_Flat_123 | M       | 0.489403  | 3114 | sp_protection_rate |
| CLN_Flat_123 | l       | 1         |    1 | sp_protection_rate |
| CLN_Flat_123 | nan     | 0.571429  |    7 | sp_protection_rate |
| CLN_Flat_42  | H       | 0.862361  | 1533 | sp_protection_rate |
| CLN_Flat_42  | L       | 0.0359043 |  752 | sp_protection_rate |
| CLN_Flat_42  | M       | 0.487788  | 2907 | sp_protection_rate |
| CLN_Flat_42  | VH      | 0         |    1 | sp_protection_rate |
| CLN_Flat_42  | nan     | 0.285714  |    7 | sp_protection_rate |
| CLN_Flat_456 | H       | 0.879672  | 1097 | sp_protection_rate |
| CLN_Flat_456 | L       | 0.0284414 |  879 | sp_protection_rate |
| CLN_Flat_456 | M       | 0.502018  | 3221 | sp_protection_rate |
| CLN_Flat_456 | nan     | 0.333333  |    3 | sp_protection_rate |
| CLN_Full_123 | H       | 0.886364  | 1320 | sp_protection_rate |
| CLN_Full_123 | L       | 0.0407609 |  736 | sp_protection_rate |
| CLN_Full_123 | M       | 0.495857  | 3138 | sp_protection_rate |
| CLN_Full_123 | VH      | 0         |    1 | sp_protection_rate |
| CLN_Full_123 | nan     | 0.6       |    5 | sp_protection_rate |
| CLN_Full_42  | H       | 0.892286  | 1439 | sp_protection_rate |
| CLN_Full_42  | L       | 0.0421607 |  759 | sp_protection_rate |
| CLN_Full_42  | M       | 0.501501  | 2999 | sp_protection_rate |
| CLN_Full_42  | nan     | 0         |    3 | sp_protection_rate |
| LEG_Full_42  | H       | 0.879195  | 1788 | sp_protection_rate |

## Step 3 Within-Agent SP Transition Summary

| arm          |     chi2 |     p_value |   cramers_v |   n_pairs |
|:-------------|---------:|------------:|------------:|----------:|
| CLN_Flat_123 |  57.4869 | 9.77849e-12 |   0.0775129 |      4784 |
| CLN_Flat_42  |  64.6375 | 3.06784e-13 |   0.0821667 |      4787 |
| CLN_Flat_456 |  69.3555 | 3.10491e-14 |   0.0850415 |      4795 |
| CLN_Full_123 |  67.6081 | 7.25621e-14 |   0.0839985 |      4791 |
| CLN_Full_42  | 115.843  | 4.12384e-24 |   0.109918  |      4794 |
| LEG_Full_42  |  70.6482 | 1.65631e-14 |   0.0864273 |      4729 |

## Step 4 Deliberative Override

| arm          | metric                |      rate |    n |
|:-------------|:----------------------|----------:|-----:|
| CLN_Flat_123 | A_tp_hvh_sp_hvh_to_dn | 0.119438  | 1281 |
| CLN_Flat_123 | B_sp_l_to_insurance   | 0.035533  |  788 |
| CLN_Flat_42  | A_tp_hvh_sp_hvh_to_dn | 0.131579  | 1520 |
| CLN_Flat_42  | B_sp_l_to_insurance   | 0.0359043 |  752 |
| CLN_Flat_456 | A_tp_hvh_sp_hvh_to_dn | 0.117324  | 1091 |
| CLN_Flat_456 | B_sp_l_to_insurance   | 0.0284414 |  879 |
| CLN_Full_123 | A_tp_hvh_sp_hvh_to_dn | 0.107798  | 1308 |
| CLN_Full_123 | B_sp_l_to_insurance   | 0.0407609 |  736 |
| CLN_Full_42  | A_tp_hvh_sp_hvh_to_dn | 0.101612  | 1427 |
| CLN_Full_42  | B_sp_l_to_insurance   | 0.0421607 |  759 |
| LEG_Full_42  | A_tp_hvh_sp_hvh_to_dn | 0.115885  | 1769 |
| LEG_Full_42  | B_sp_l_to_insurance   | 0.0733333 |  750 |

## Step 5 MG-Owner vs NMG-Owner

| arm          | profile   |   sp_l_pct |   survey_pa_score_mean |   pooled_dn_pct |   y13_ins_pct |   y13_cum_oop |
|:-------------|:----------|-----------:|-----------------------:|----------------:|--------------:|--------------:|
| CLN_Flat_123 | MG-Owner  |   0.156923 |                 3.0146 |        0.682308 |          0.27 |        324525 |
| CLN_Flat_123 | NMG-Owner |   0.223249 |                 3.2261 |        0.468822 |          0.53 |        187082 |
| CLN_Flat_42  | MG-Owner  |   0.156154 |                 3.0146 |        0.705385 |          0.22 |        330159 |
| CLN_Flat_42  | NMG-Owner |   0.199231 |                 3.2255 |        0.447692 |          0.46 |        208011 |
| CLN_Flat_456 | MG-Owner  |   0.170769 |                 3.0146 |        0.697692 |          0.28 |        335127 |
| CLN_Flat_456 | NMG-Owner |   0.237692 |                 3.2255 |        0.493846 |          0.44 |        221306 |
| CLN_Full_123 | MG-Owner  |   0.143846 |                 3.0146 |        0.67     |          0.32 |        334910 |
| CLN_Full_123 | NMG-Owner |   0.198462 |                 3.2255 |        0.438462 |          0.51 |        213723 |
| CLN_Full_42  | MG-Owner  |   0.153846 |                 3.0146 |        0.662308 |          0.26 |        273868 |
| CLN_Full_42  | NMG-Owner |   0.198462 |                 3.2255 |        0.435385 |          0.44 |        191314 |
| LEG_Full_42  | MG-Owner  |   0.178462 |                 3.0146 |        0.561538 |          0.39 |        312176 |
| LEG_Full_42  | NMG-Owner |   0.206154 |                 3.2255 |        0.334615 |          0.83 |        210387 |
