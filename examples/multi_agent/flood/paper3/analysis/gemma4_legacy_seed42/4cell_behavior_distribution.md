# 4-Cell Household Behavior Distribution Analysis

**Source**: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict` | **Total records**: 5,200

## Summary by Cell

| Cell | Agents | Records | Records/Agent |
|------|--------|---------|---------------|
| MG-Owner | 100 | 1,300 | 13.0 |
| NMG-Owner | 100 | 1,300 | 13.0 |
| MG-Renter | 100 | 1,300 | 13.0 |
| NMG-Renter | 100 | 1,300 | 13.0 |

## MG-Owner

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| do_nothing | 730 | 56.2% |
| buy_insurance | 550 | 42.3% |
| elevate_house | 19 | 1.5% |
| buyout_program | 1 | 0.1% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 497 | 36 | 93.2% |
| buyout_program | 0 | 1 | 0.0% |
| do_nothing | 690 | 1 | 99.9% |
| elevate_house | 3 | 16 | 15.8% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 61 | 39 | 39.0% |
| 2 | 100 | 55 | 45 | 45.0% |
| 3 | 100 | 58 | 42 | 42.0% |
| 4 | 100 | 54 | 46 | 46.0% |
| 5 | 100 | 59 | 41 | 41.0% |
| 6 | 100 | 57 | 43 | 43.0% |
| 7 | 100 | 61 | 39 | 39.0% |
| 8 | 100 | 54 | 46 | 46.0% |
| 9 | 100 | 52 | 48 | 48.0% |
| 10 | 100 | 50 | 50 | 50.0% |
| 11 | 100 | 53 | 47 | 47.0% |
| 12 | 100 | 56 | 44 | 44.0% |
| 13 | 100 | 60 | 40 | 40.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 14 |
| MG_INSURANCE_BARRIER: Marginalized household with no flood experience faces access barriers to NFIP enrollment. Consider | 8 |
| AFFORDABILITY: Cannot afford elevation ($67,500 > 3x income $60,000) | 7 |
| INCOME_GATE: elevate_house blocked for income $20,000 < $40K without near-full subsidy | 7 |
| [Rule: owner_complex_action_low_coping] Complex actions are blocked due to your low confidence in your ability to cope. | 7 |
| ELEVATION_EXPERIENCE: elevate_house requires flood_count >= 2 (current: 1) | 7 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 7 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 6 |
| ELEVATION_JUSTIFICATION: LOW flood zone agent needs 2+ flood events to justify elevation investment (current flood_count | 6 |
| ZONE_GUARD: elevate_house inappropriate for LOW flood zone agent with no flood experience | 5 |

## NMG-Owner

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_insurance | 850 | 65.4% |
| do_nothing | 435 | 33.5% |
| elevate_house | 15 | 1.2% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 783 | 34 | 95.8% |
| do_nothing | 424 | 0 | 100.0% |
| elevate_house | 8 | 7 | 53.3% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 53 | 47 | 47.0% |
| 2 | 100 | 45 | 55 | 55.0% |
| 3 | 100 | 39 | 61 | 61.0% |
| 4 | 100 | 34 | 66 | 66.0% |
| 5 | 100 | 37 | 63 | 63.0% |
| 6 | 100 | 47 | 53 | 53.0% |
| 7 | 100 | 40 | 60 | 60.0% |
| 8 | 100 | 35 | 65 | 65.0% |
| 9 | 100 | 31 | 69 | 69.0% |
| 10 | 100 | 26 | 74 | 74.0% |
| 11 | 100 | 20 | 80 | 80.0% |
| 12 | 100 | 14 | 86 | 86.0% |
| 13 | 100 | 14 | 86 | 86.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 9 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 7 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| ZONE_GUARD: elevate_house inappropriate for LOW flood zone agent with no flood experience | 5 |
| ELEVATION_EXPERIENCE: elevate_house requires flood_count >= 2 (current: 0) | 5 |
| ELEVATION_JUSTIFICATION: LOW flood zone agent needs 2+ flood events to justify elevation investment (current flood_count | 5 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 3 |

## MG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 812 | 62.5% |
| do_nothing | 472 | 36.3% |
| relocate | 16 | 1.2% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 723 | 76 | 90.5% |
| do_nothing | 422 | 7 | 98.4% |
| relocate | 10 | 3 | 76.9% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 33 | 67 | 67.0% |
| 2 | 100 | 30 | 70 | 70.0% |
| 3 | 100 | 33 | 67 | 67.0% |
| 4 | 100 | 34 | 66 | 66.0% |
| 5 | 100 | 34 | 66 | 66.0% |
| 6 | 100 | 36 | 64 | 64.0% |
| 7 | 100 | 34 | 66 | 66.0% |
| 8 | 100 | 36 | 64 | 64.0% |
| 9 | 100 | 38 | 62 | 62.0% |
| 10 | 100 | 47 | 53 | 53.0% |
| 11 | 100 | 35 | 65 | 65.0% |
| 12 | 100 | 42 | 58 | 58.0% |
| 13 | 100 | 40 | 60 | 60.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 29 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 9 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 8 |
| ZONE_GUARD: buy_contents_insurance not cost-effective for LOW flood zone renter with no flood experience | 7 |
| MG_INSURANCE_BARRIER: Marginalized household with no flood experience faces access barriers to NFIP enrollment. Consider | 7 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 5 |

## NMG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 742 | 57.1% |
| do_nothing | 538 | 41.4% |
| relocate | 20 | 1.5% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 642 | 82 | 88.7% |
| do_nothing | 488 | 0 | 100.0% |
| relocate | 13 | 6 | 68.4% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 39 | 61 | 61.0% |
| 2 | 100 | 30 | 70 | 70.0% |
| 3 | 100 | 34 | 66 | 66.0% |
| 4 | 100 | 34 | 66 | 66.0% |
| 5 | 100 | 38 | 62 | 62.0% |
| 6 | 100 | 36 | 64 | 64.0% |
| 7 | 100 | 37 | 63 | 63.0% |
| 8 | 100 | 43 | 57 | 57.0% |
| 9 | 100 | 47 | 53 | 53.0% |
| 10 | 100 | 55 | 45 | 45.0% |
| 11 | 100 | 48 | 52 | 52.0% |
| 12 | 100 | 47 | 53 | 53.0% |
| 13 | 100 | 50 | 50 | 50.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| ZONE_GUARD: buy_contents_insurance not cost-effective for LOW flood zone renter with no flood experience | 22 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 19 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 11 |
| [Rule: relocated_already] Identity Block: buy_contents_insurance restricted by relocated | 9 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 9 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| [Rule: relocated_already] Identity Block: relocate restricted by relocated | 6 |

## MG vs NMG Adaptation Gap

### Owner Gap

| Metric | MG-Owner | NMG-Owner | Gap (MG - NMG) |
|--------|----------|-----------|----------------|
| Insurance Rate | 42.3% | 65.4% | -23.1pp |
| Elevation Rate | 1.5% | 1.2% | +0.3pp |
| Buyout Rate | 0.1% | 0.0% | +0.1pp |
| Adaptation Rate | 43.8% | 66.5% | -22.7pp |

### Renter Gap

| Metric | MG-Renter | NMG-Renter | Gap (MG - NMG) |
|--------|-----------|------------|----------------|
| Insurance Rate | 62.5% | 57.1% | +5.4pp |
| Relocation Rate | 1.2% | 1.5% | -0.3pp |
| Adaptation Rate | 63.7% | 58.6% | +5.1pp |

### Approval Rate Gap (All Skills)

| Cell | Total Approved | Total Rejected | Approval Rate |
|------|----------------|----------------|---------------|
| MG-Owner | 1,190 | 54 | 95.7% |
| NMG-Owner | 1,215 | 41 | 96.7% |
| MG-Renter | 1,155 | 86 | 93.1% |
| NMG-Renter | 1,143 | 88 | 92.9% |
