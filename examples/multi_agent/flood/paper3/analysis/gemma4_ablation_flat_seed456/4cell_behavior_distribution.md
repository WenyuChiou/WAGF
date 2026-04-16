# 4-Cell Household Behavior Distribution Analysis

**Source**: `examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_456/gemma4_e4b_strict` | **Total records**: 5,200

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
| do_nothing | 907 | 69.8% |
| buy_insurance | 392 | 30.2% |
| elevate_house | 1 | 0.1% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 372 | 8 | 97.9% |
| do_nothing | 881 | 1 | 99.9% |
| elevate_house | 1 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 72 | 28 | 28.0% |
| 2 | 100 | 65 | 35 | 35.0% |
| 3 | 100 | 61 | 39 | 39.0% |
| 4 | 100 | 67 | 33 | 33.0% |
| 5 | 100 | 68 | 32 | 32.0% |
| 6 | 100 | 65 | 35 | 35.0% |
| 7 | 100 | 69 | 31 | 31.0% |
| 8 | 100 | 75 | 25 | 25.0% |
| 9 | 100 | 79 | 21 | 21.0% |
| 10 | 100 | 73 | 27 | 27.0% |
| 11 | 100 | 68 | 32 | 32.0% |
| 12 | 100 | 72 | 28 | 28.0% |
| 13 | 100 | 73 | 27 | 27.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| MG_INSURANCE_BARRIER: Marginalized household with no flood experience faces access barriers to NFIP enrollment. Consider | 3 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 2 |
| ELEVATION_EXPERIENCE: elevate_house requires flood_count >= 2 (current: 1) | 2 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital | 1 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 1 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 1 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 1 |

## NMG-Owner

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_insurance | 653 | 50.2% |
| do_nothing | 642 | 49.4% |
| elevate_house | 5 | 0.4% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_insurance | 623 | 18 | 97.2% |
| do_nothing | 623 | 1 | 99.8% |
| elevate_house | 4 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 50 | 50 | 50.0% |
| 2 | 100 | 49 | 51 | 51.0% |
| 3 | 100 | 47 | 53 | 53.0% |
| 4 | 100 | 49 | 51 | 51.0% |
| 5 | 100 | 51 | 49 | 49.0% |
| 6 | 100 | 43 | 57 | 57.0% |
| 7 | 100 | 43 | 57 | 57.0% |
| 8 | 100 | 50 | 50 | 50.0% |
| 9 | 100 | 53 | 47 | 47.0% |
| 10 | 100 | 51 | 49 | 49.0% |
| 11 | 100 | 48 | 52 | 52.0% |
| 12 | 100 | 54 | 46 | 46.0% |
| 13 | 100 | 54 | 46 | 46.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 6 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 3 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 3 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 2 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 1 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 1 |
| [Rule: owner_complex_action_low_coping] Complex actions are blocked due to your low confidence in your ability to cope. | 1 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 1 |

## MG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 794 | 61.1% |
| do_nothing | 506 | 38.9% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 755 | 33 | 95.8% |
| do_nothing | 455 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 28 | 72 | 72.0% |
| 2 | 100 | 28 | 72 | 72.0% |
| 3 | 100 | 39 | 61 | 61.0% |
| 4 | 100 | 41 | 59 | 59.0% |
| 5 | 100 | 54 | 46 | 46.0% |
| 6 | 100 | 40 | 60 | 60.0% |
| 7 | 100 | 38 | 62 | 62.0% |
| 8 | 100 | 52 | 48 | 48.0% |
| 9 | 100 | 56 | 44 | 44.0% |
| 10 | 100 | 45 | 55 | 55.0% |
| 11 | 100 | 27 | 73 | 73.0% |
| 12 | 100 | 29 | 71 | 71.0% |
| 13 | 100 | 29 | 71 | 71.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 10 |
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 9 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 8 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 8 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 3 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| RENEWAL_FATIGUE: No flood in 10 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 2 |
| RENEWAL_FATIGUE: No flood in 11 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 2 |
| Response missing required fields: coping_perception, stakeholder_perception, place_attachment | 1 |

## NMG-Renter

### Skill Distribution (All Years)

| Skill | Count | % |
|-------|-------|---|
| buy_contents_insurance | 763 | 58.7% |
| do_nothing | 537 | 41.3% |

### Approval vs Rejection by Skill

| Skill | Approved | Rejected | Approval Rate |
|-------|----------|----------|---------------|
| buy_contents_insurance | 700 | 49 | 93.5% |
| do_nothing | 479 | 0 | 100.0% |

### Year-by-Year Adaptation Rate (% non-do_nothing)

| Year | Total | do_nothing | Adaptive | Adaptation Rate |
|------|-------|------------|----------|-----------------|
| 1 | 100 | 45 | 55 | 55.0% |
| 2 | 100 | 35 | 65 | 65.0% |
| 3 | 100 | 42 | 58 | 58.0% |
| 4 | 100 | 39 | 61 | 61.0% |
| 5 | 100 | 51 | 49 | 49.0% |
| 6 | 100 | 37 | 63 | 63.0% |
| 7 | 100 | 40 | 60 | 60.0% |
| 8 | 100 | 54 | 46 | 46.0% |
| 9 | 100 | 48 | 52 | 52.0% |
| 10 | 100 | 35 | 65 | 65.0% |
| 11 | 100 | 33 | 67 | 67.0% |
| 12 | 100 | 38 | 62 | 62.0% |
| 13 | 100 | 40 | 60 | 60.0% |

### Top 10 Rejection Reasons

| Reason | Count |
|--------|-------|
| RENEWAL_FATIGUE: No flood in 4 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 13 |
| RENEWAL_FATIGUE: No flood in 8 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 12 |
| RENEWAL_FATIGUE: No flood in 5 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 11 |
| Response missing required fields: threat_perception, coping_perception, stakeholder_perception, social_capital, place_at | 7 |
| RENEWAL_FATIGUE: No flood in 3 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| RENEWAL_FATIGUE: No flood in 7 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 4 |
| Response missing required fields: coping_perception, stakeholder_perception, social_capital, place_attachment | 2 |
| RENEWAL_FATIGUE: No flood in 6 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 yea | 2 |
| RENEWAL_FATIGUE: No flood in 11 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 2 |
| RENEWAL_FATIGUE: No flood in 10 year(s) — insurance renewal unlikely for MEDIUM zone agent. Median NFIP tenure is 2-4 ye | 1 |

## MG vs NMG Adaptation Gap

### Owner Gap

| Metric | MG-Owner | NMG-Owner | Gap (MG - NMG) |
|--------|----------|-----------|----------------|
| Insurance Rate | 30.2% | 50.2% | -20.1pp |
| Elevation Rate | 0.1% | 0.4% | -0.3pp |
| Buyout Rate | 0.0% | 0.0% | +0.0pp |
| Adaptation Rate | 30.2% | 50.6% | -20.4pp |

### Renter Gap

| Metric | MG-Renter | NMG-Renter | Gap (MG - NMG) |
|--------|-----------|------------|----------------|
| Insurance Rate | 61.1% | 58.7% | +2.4pp |
| Relocation Rate | 0.0% | 0.0% | +0.0pp |
| Adaptation Rate | 61.1% | 58.7% | +2.4pp |

### Approval Rate Gap (All Skills)

| Cell | Total Approved | Total Rejected | Approval Rate |
|------|----------------|----------------|---------------|
| MG-Owner | 1,254 | 9 | 99.3% |
| NMG-Owner | 1,250 | 19 | 98.5% |
| MG-Renter | 1,210 | 33 | 97.3% |
| NMG-Renter | 1,179 | 49 | 96.0% |
