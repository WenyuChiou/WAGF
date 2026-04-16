# 4-Cell Household Behavior Distribution Analysis

**Source**: `C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_42/gemma4_e4b_strict` | **Total records**: 5,200

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
| do_nothing | 917 | 70.5% |
| buy_insurance | 383 | 29.5% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 360 | 15 | 96.0% |
| do_nothing | 892 | 1 | 99.9% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 64 | 36 | 36.0% |
| 2 | 100 | 65 | 35 | 35.0% |
| 3 | 100 | 62 | 38 | 38.0% |
| 4 | 100 | 68 | 32 | 32.0% |
| 5 | 100 | 65 | 35 | 35.0% |
| 6 | 100 | 64 | 36 | 36.0% |
| 7 | 100 | 71 | 29 | 29.0% |
| 8 | 100 | 76 | 24 | 24.0% |
| 9 | 100 | 76 | 24 | 24.0% |
| 10 | 100 | 77 | 23 | 23.0% |
| 11 | 100 | 76 | 24 | 24.0% |
| 12 | 100 | 78 | 22 | 22.0% |
| 13 | 100 | 75 | 25 | 25.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| MG_INSURANCE_BARRIER: Marginalized household with no flood experience faces access barriers to NFIP enrollment. Consider | 7 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 3 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| ELEVATION_EXPERIENCE: elevate_house requires flood_count >= 2 (current: 1) | 2 |
| INCOME_GATE: elevate_house blocked for income $37,500 < $40K without near-full subsidy | 2 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 1 |
| Response missing required fields: stakeholder_perception, social_capital, place_attachment | 1 |

## NMG-Owner

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_insurance | 709 | 54.5% |
| do_nothing | 582 | 44.8% |
| elevate_house | 9 | 0.7% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 671 | 31 | 95.6% |
| do_nothing | 571 | 0 | 100.0% |
| elevate_house | 8 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 48 | 52 | 52.0% |
| 2 | 100 | 41 | 59 | 59.0% |
| 3 | 100 | 33 | 67 | 67.0% |
| 4 | 100 | 40 | 60 | 60.0% |
| 5 | 100 | 41 | 59 | 59.0% |
| 6 | 100 | 43 | 57 | 57.0% |
| 7 | 100 | 44 | 56 | 56.0% |
| 8 | 100 | 41 | 59 | 59.0% |
| 9 | 100 | 46 | 54 | 54.0% |
| 10 | 100 | 52 | 48 | 48.0% |
| 11 | 100 | 49 | 51 | 51.0% |
| 12 | 100 | 53 | 47 | 47.0% |
| 13 | 100 | 51 | 49 | 49.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 7 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 5 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 5 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 5 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 4 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 2 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| RENEWAL_FATIGUE: No flood in 11 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 1 |

## MG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 859 | 66.1% |
| do_nothing | 439 | 33.8% |
| relocate | 2 | 0.2% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 785 | 68 | 92.0% |
| do_nothing | 364 | 4 | 98.9% |
| relocate | 1 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 31 | 69 | 69.0% |
| 2 | 100 | 23 | 77 | 77.0% |
| 3 | 100 | 27 | 73 | 73.0% |
| 4 | 100 | 36 | 64 | 64.0% |
| 5 | 100 | 37 | 63 | 63.0% |
| 6 | 100 | 36 | 64 | 64.0% |
| 7 | 100 | 41 | 59 | 59.0% |
| 8 | 100 | 38 | 62 | 62.0% |
| 9 | 100 | 40 | 60 | 60.0% |
| 10 | 100 | 49 | 51 | 51.0% |
| 11 | 100 | 27 | 73 | 73.0% |
| 12 | 100 | 27 | 73 | 73.0% |
| 13 | 100 | 27 | 73 | 73.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 12 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 9 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 8 |
| RENEWAL_FATIGUE: No flood in 10 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 6 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 5 |
| RENEWAL_FATIGUE: No flood in 11 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 5 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 3 |

## NMG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 804 | 61.8% |
| do_nothing | 493 | 37.9% |
| relocate | 3 | 0.2% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 726 | 70 | 91.2% |
| do_nothing | 406 | 0 | 100.0% |
| relocate | 1 | 1 | 50.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 39 | 61 | 61.0% |
| 2 | 100 | 33 | 67 | 67.0% |
| 3 | 100 | 32 | 68 | 68.0% |
| 4 | 100 | 41 | 59 | 59.0% |
| 5 | 100 | 37 | 63 | 63.0% |
| 6 | 100 | 35 | 65 | 65.0% |
| 7 | 100 | 40 | 60 | 60.0% |
| 8 | 100 | 40 | 60 | 60.0% |
| 9 | 100 | 36 | 64 | 64.0% |
| 10 | 100 | 53 | 47 | 47.0% |
| 11 | 100 | 34 | 66 | 66.0% |
| 12 | 100 | 38 | 62 | 62.0% |
| 13 | 100 | 35 | 65 | 65.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 10 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 10 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 9 |
| ZONE_GUARD: buy_contents_insurance not cost-effective for LOW flood zone renter with no flood experience | 6 |
| RENEWAL_FATIGUE: No flood in 11 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 5 |
| RENEWAL_FATIGUE: No flood in 10 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 4 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 2 |

## MG vs NMG Adaptation Gap

### Owner Gap

| Metric | MG-Owner | NMG-Owner | Gap (MG - NMG) |
|--------|----------|-----------|----------------|
| Insurance Rate | 29.5% | 54.5% | -25.1pp |
| Elevation Rate | 0.0% | 0.7% | -0.7pp |
| Buyout Rate | 0.0% | 0.0% | +0.0pp |
| Adaptation Rate | 29.5% | 55.2% | -25.8pp |

### Renter Gap

| Metric | MG-Renter | NMG-Renter | Gap (MG - NMG) |
|--------|-----------|------------|----------------|
| Insurance Rate | 66.1% | 61.8% | +4.2pp |
| Relocation Rate | 0.2% | 0.2% | -0.1pp |
| Adaptation Rate | 66.2% | 62.1% | +4.2pp |

### Approval Rate Gap (All Skills)

| Cell | Total Approved | Total Rejected | Approval Rate |
|------|----------------|----------------|---------------|
| MG-Owner | 1,252 | 16 | 98.7% |
| NMG-Owner | 1,250 | 31 | 97.6% |
| MG-Renter | 1,150 | 72 | 94.1% |
| NMG-Renter | 1,133 | 71 | 94.1% |
