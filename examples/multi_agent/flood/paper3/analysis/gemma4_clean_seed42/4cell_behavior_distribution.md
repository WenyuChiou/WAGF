# 4-Cell Household Behavior Distribution Analysis

**Source**: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_42/gemma4_e4b_strict` | **Total records**: 5,200

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
| do_nothing | 861 | 66.2% |
| buy_insurance | 437 | 33.6% |
| elevate_house | 2 | 0.2% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 410 | 12 | 97.2% |
| do_nothing | 832 | 0 | 100.0% |
| elevate_house | 2 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 61 | 39 | 39.0% |
| 2 | 100 | 59 | 41 | 41.0% |
| 3 | 100 | 62 | 38 | 38.0% |
| 4 | 100 | 65 | 35 | 35.0% |
| 5 | 100 | 66 | 34 | 34.0% |
| 6 | 100 | 65 | 35 | 35.0% |
| 7 | 100 | 63 | 37 | 37.0% |
| 8 | 100 | 63 | 37 | 37.0% |
| 9 | 100 | 72 | 28 | 28.0% |
| 10 | 100 | 77 | 23 | 23.0% |
| 11 | 100 | 68 | 32 | 32.0% |
| 12 | 100 | 74 | 26 | 26.0% |
| 13 | 100 | 66 | 34 | 34.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| MG_INSURANCE_BARRIER: Marginalized household with no flood experience faces access barriers to NFIP enrollment. Consider | 3 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 3 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 1 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 1 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 1 |
| ELEVATION_EXPERIENCE: elevate_house requires flood_count >= 2 (current: 1) | 1 |
| INCOME_GATE: elevate_house blocked for income $37,500 < $40K without near-full subsidy | 1 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 1 |
| RENEWAL_FATIGUE: No flood in 10 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 1 |

## NMG-Owner

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_insurance | 724 | 55.7% |
| do_nothing | 566 | 43.5% |
| elevate_house | 10 | 0.8% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 684 | 31 | 95.7% |
| do_nothing | 557 | 2 | 99.6% |
| elevate_house | 10 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 41 | 59 | 59.0% |
| 2 | 100 | 36 | 64 | 64.0% |
| 3 | 100 | 31 | 69 | 69.0% |
| 4 | 100 | 39 | 61 | 61.0% |
| 5 | 100 | 42 | 58 | 58.0% |
| 6 | 100 | 43 | 57 | 57.0% |
| 7 | 100 | 40 | 60 | 60.0% |
| 8 | 100 | 44 | 56 | 56.0% |
| 9 | 100 | 49 | 51 | 51.0% |
| 10 | 100 | 58 | 42 | 42.0% |
| 11 | 100 | 46 | 54 | 54.0% |
| 12 | 100 | 54 | 46 | 46.0% |
| 13 | 100 | 43 | 57 | 57.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 7 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 7 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 5 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 5 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 5 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 1 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital | 1 |
| Response missing required fields: coping_perception, stakeholder_perception, place_attachment | 1 |

## MG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 844 | 64.9% |
| do_nothing | 456 | 35.1% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 784 | 51 | 93.9% |
| do_nothing | 391 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 28 | 72 | 72.0% |
| 2 | 100 | 25 | 75 | 75.0% |
| 3 | 100 | 25 | 75 | 75.0% |
| 4 | 100 | 35 | 65 | 65.0% |
| 5 | 100 | 45 | 55 | 55.0% |
| 6 | 100 | 41 | 59 | 59.0% |
| 7 | 100 | 43 | 57 | 57.0% |
| 8 | 100 | 38 | 62 | 62.0% |
| 9 | 100 | 40 | 60 | 60.0% |
| 10 | 100 | 56 | 44 | 44.0% |
| 11 | 100 | 26 | 74 | 74.0% |
| 12 | 100 | 27 | 73 | 73.0% |
| 13 | 100 | 27 | 73 | 73.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 10 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 7 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 6 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| RENEWAL_FATIGUE: No flood in 10 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 5 |
| RENEWAL_FATIGUE: No flood in 11 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 4 |
| Response missing required fields: coping_perception, stakeholder_perception, place_attachment | 1 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for LOW zone agent. Median NFIP tenure is 2-4 years  | 1 |

## NMG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 802 | 61.7% |
| do_nothing | 497 | 38.2% |
| relocate | 1 | 0.1% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 730 | 68 | 91.5% |
| do_nothing | 432 | 1 | 99.8% |
| relocate | 0 | 0 | N/A |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 36 | 64 | 64.0% |
| 2 | 100 | 33 | 67 | 67.0% |
| 3 | 100 | 32 | 68 | 68.0% |
| 4 | 100 | 41 | 59 | 59.0% |
| 5 | 100 | 48 | 52 | 52.0% |
| 6 | 100 | 35 | 65 | 65.0% |
| 7 | 100 | 40 | 60 | 60.0% |
| 8 | 100 | 37 | 63 | 63.0% |
| 9 | 100 | 37 | 63 | 63.0% |
| 10 | 100 | 55 | 45 | 45.0% |
| 11 | 100 | 34 | 66 | 66.0% |
| 12 | 100 | 35 | 65 | 65.0% |
| 13 | 100 | 34 | 66 | 66.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 13 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 10 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 10 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 7 |
| ZONE_GUARD: buy_contents_insurance not cost-effective for LOW flood zone renter with no flood experience | 5 |
| RENEWAL_FATIGUE: No flood in 11 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 5 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 3 |

## MG vs NMG Adaptation Gap

### Owner Gap

| Metric | MG-Owner | NMG-Owner | Gap (MG - NMG) |
|--------|----------|-----------|----------------|
| Insurance Rate | 33.6% | 55.7% | -22.1pp |
| Elevation Rate | 0.2% | 0.8% | -0.6pp |
| Buyout Rate | 0.0% | 0.0% | +0.0pp |
| Adaptation Rate | 33.8% | 56.5% | -22.7pp |

### Renter Gap

| Metric | MG-Renter | NMG-Renter | Gap (MG - NMG) |
|--------|-----------|------------|----------------|
| Insurance Rate | 64.9% | 61.7% | +3.2pp |
| Relocation Rate | 0.0% | 0.1% | -0.1pp |
| Adaptation Rate | 64.9% | 61.8% | +3.2pp |

### Approval Rate Gap (All Skills)

| Cell | Total Approved | Total Rejected | Approval Rate |
|------|----------------|----------------|---------------|
| MG-Owner | 1,244 | 12 | 99.0% |
| NMG-Owner | 1,251 | 33 | 97.4% |
| MG-Renter | 1,175 | 51 | 95.8% |
| NMG-Renter | 1,162 | 69 | 94.4% |
