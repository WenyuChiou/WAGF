# Gemma 4 e4b vs Gemma 3 4B Cross-Model Analysis

Comparison scope:
- `examples/multi_agent/flood/paper3/results/paper3_hybrid_v2/seed_42/gemma3_4b_strict/`
- `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b/seed_42/gemma4_e4b_strict/`

Method notes:
- Basic action distributions use `final_skill` exactly as requested.
- MG-owner executed distributions map `status != APPROVED` to executed `do_nothing`.
- Construct percentages are computed over valid non-missing labels only; malformed labels are reported separately.

## Cross-Model Summary Table

| Model | Metric | Value |
| --- | --- | --- |
| Gemma 3 4B | Owner rejection rate | 21.1% |
| Gemma 3 4B | Owner retry rate | 30.7% |
| Gemma 3 4B | Owner do_nothing | 40.6% |
| Gemma 3 4B | Owner buy_insurance | 38.2% |
| Gemma 3 4B | Owner elevate_house | 17.9% |
| Gemma 3 4B | Renter rejection rate | 4.2% |
| Gemma 3 4B | Renter retry rate | 14.1% |
| Gemma 3 4B | Renter do_nothing | 58.8% |
| Gemma 3 4B | Renter buy_contents_insurance | 37.5% |
| Gemma 3 4B | Owner CP=H share | 3.6% |
| Gemma 3 4B | Owner CP=H do_nothing | 83.9% |
| Gemma 3 4B | Case A high TP+SP do_nothing | 30.1% |
| Gemma 3 4B | Case B low SP insurance | 22.4% |
| Gemma 3 4B | MG-Owner executed do_nothing | 67.0% |
| Gemma 3 4B | NMG-Owner executed do_nothing | 56.4% |
| Gemma 4 e4b | Owner rejection rate | 2.3% |
| Gemma 4 e4b | Owner retry rate | 7.0% |
| Gemma 4 e4b | Owner do_nothing | 48.4% |
| Gemma 4 e4b | Owner buy_insurance | 49.8% |
| Gemma 4 e4b | Owner elevate_house | 1.7% |
| Gemma 4 e4b | Renter rejection rate | 17.9% |
| Gemma 4 e4b | Renter retry rate | 29.4% |
| Gemma 4 e4b | Renter do_nothing | 40.6% |
| Gemma 4 e4b | Renter buy_contents_insurance | 54.7% |
| Gemma 4 e4b | Owner CP=H share | 23.6% |
| Gemma 4 e4b | Owner CP=H do_nothing | 21.0% |
| Gemma 4 e4b | Case A high TP+SP do_nothing | 20.7% |
| Gemma 4 e4b | Case B low SP insurance | 5.6% |
| Gemma 4 e4b | MG-Owner executed do_nothing | 67.7% |
| Gemma 4 e4b | NMG-Owner executed do_nothing | 33.6% |

## 1. Basic Metrics Comparison

## Gemma 3 4B

### Owners

| Metric | Value |
| --- | --- |
| N decisions | 2600 |
| Rejection rate | 21.1% |
| Retry rate | 30.7% |

Action distribution (`final_skill`):
| Action | Share |
| --- | --- |
| buy_insurance | 38.2% |
| elevate_house | 17.9% |
| buyout_program | 3.3% |
| do_nothing | 40.6% |

Construct distribution (TP; valid labels n=2595 of non-missing n=2595):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 17.2% |
| M | 25.8% |
| H | 57.0% |
| VH | 0.0% |

Construct distribution (CP; valid labels n=2594 of non-missing n=2594):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 22.2% |
| M | 74.2% |
| H | 3.6% |
| VH | 0.0% |

Construct distribution (SP; valid labels n=2594 of non-missing n=2594):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 41.2% |
| M | 54.5% |
| H | 4.2% |
| VH | 0.0% |

Construct distribution (SC; valid labels n=2594 of non-missing n=2594):
| Label | Share |
| --- | --- |
| VL | 0.7% |
| L | 83.5% |
| M | 12.5% |
| H | 3.4% |
| VH | 0.0% |

Construct distribution (PA; valid labels n=2594 of non-missing n=2594):
| Label | Share |
| --- | --- |
| VL | 0.7% |
| L | 22.3% |
| M | 60.1% |
| H | 16.5% |
| VH | 0.4% |

### Renters

| Metric | Value |
| --- | --- |
| N decisions | 2600 |
| Rejection rate | 4.2% |
| Retry rate | 14.1% |

Action distribution (`final_skill`):
| Action | Share |
| --- | --- |
| buy_contents_insurance | 37.5% |
| relocate | 3.6% |
| do_nothing | 58.8% |

Construct distribution (TP; valid labels n=2600 of non-missing n=2600):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 22.7% |
| M | 33.9% |
| H | 43.0% |
| VH | 0.4% |

Construct distribution (CP; valid labels n=2600 of non-missing n=2600):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 31.0% |
| M | 68.3% |
| H | 0.7% |
| VH | 0.0% |

Construct distribution (SP; valid labels n=2600 of non-missing n=2600):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 39.1% |
| M | 59.5% |
| H | 1.4% |
| VH | 0.0% |

Construct distribution (SC; valid labels n=2600 of non-missing n=2600):
| Label | Share |
| --- | --- |
| VL | 0.1% |
| L | 71.7% |
| M | 27.6% |
| H | 0.6% |
| VH | 0.0% |

Construct distribution (PA; valid labels n=2600 of non-missing n=2600):
| Label | Share |
| --- | --- |
| VL | 0.1% |
| L | 40.6% |
| M | 48.2% |
| H | 11.1% |
| VH | 0.0% |

## Gemma 4 e4b

### Owners

| Metric | Value |
| --- | --- |
| N decisions | 2599 |
| Rejection rate | 2.3% |
| Retry rate | 7.0% |

Action distribution (`final_skill`):
| Action | Share |
| --- | --- |
| buy_insurance | 49.8% |
| elevate_house | 1.7% |
| buyout_program | 0.1% |
| do_nothing | 48.4% |

Construct distribution (TP; valid labels n=2595 of non-missing n=2595):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 5.9% |
| M | 11.5% |
| H | 26.5% |
| VH | 56.0% |

Construct distribution (CP; valid labels n=2594 of non-missing n=2595):
| Label | Share |
| --- | --- |
| VL | 2.8% |
| L | 29.8% |
| M | 43.4% |
| H | 23.7% |
| VH | 0.3% |
Malformed labels excluded from percentages: M-H=1.

Construct distribution (SP; valid labels n=2595 of non-missing n=2595):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 7.5% |
| M | 42.5% |
| H | 47.3% |
| VH | 2.7% |

Construct distribution (SC; valid labels n=2595 of non-missing n=2595):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 5.7% |
| M | 77.8% |
| H | 15.3% |
| VH | 1.1% |

Construct distribution (PA; valid labels n=2595 of non-missing n=2595):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 0.1% |
| M | 1.8% |
| H | 72.8% |
| VH | 25.2% |

### Renters

| Metric | Value |
| --- | --- |
| N decisions | 2600 |
| Rejection rate | 17.9% |
| Retry rate | 29.4% |

Action distribution (`final_skill`):
| Action | Share |
| --- | --- |
| buy_contents_insurance | 54.7% |
| relocate | 4.7% |
| do_nothing | 40.6% |

Construct distribution (TP; valid labels n=2526 of non-missing n=2530):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 9.4% |
| M | 14.1% |
| H | 15.4% |
| VH | 61.1% |
Malformed labels excluded from percentages: m=2, h=2.

Construct distribution (CP; valid labels n=2521 of non-missing n=2521):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 9.3% |
| M | 35.8% |
| H | 54.5% |
| VH | 0.4% |

Construct distribution (SP; valid labels n=2519 of non-missing n=2519):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 5.0% |
| M | 39.9% |
| H | 52.4% |
| VH | 2.7% |

Construct distribution (SC; valid labels n=2520 of non-missing n=2530):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 4.6% |
| M | 63.3% |
| H | 28.5% |
| VH | 3.6% |
Malformed labels excluded from percentages: l=9, m=1.

Construct distribution (PA; valid labels n=2519 of non-missing n=2521):
| Label | Share |
| --- | --- |
| VL | 0.0% |
| L | 2.4% |
| M | 27.8% |
| H | 53.7% |
| VH | 16.1% |
Malformed labels excluded from percentages: M-H=1, m=1.

## 2. CP Reversal Check

| Model | Owner CP=H share | CP=H N | CP=H do_nothing | CP=H active |
| --- | --- | --- | --- | --- |
| Gemma 3 4B | 3.6% | 93 | 78/93 (83.9%) | 15/93 (16.1%) |
| Gemma 4 e4b | 23.6% | 614 | 129/614 (21.0%) | 485/614 (79.0%) |

Verdict: Gemma 4 does not reproduce the Gemma 3 CP reversal artifact.

## 3. Deliberative Override Check

Case definitions:
- Case A: `TP in {H, VH}` and `SP in {H, VH}`; report fraction still choosing `do_nothing`.
- Case B: `SP in {L, VL}`; report fraction choosing insurance (`buy_insurance` or `buy_contents_insurance`).

| Model | Case A do_nothing | Case B insurance |
| --- | --- | --- |
| Gemma 3 4B | 44/146 (30.1%) | 468/2086 (22.4%) |
| Gemma 4 e4b | 536/2591 (20.7%) | 18/322 (5.6%) |

Reference values supplied in the task for prior Gemma 3 analysis:
- Case A: 122/396 (31.0%) high-motivation inaction.
- Case B: 1525/6492 (23.5%) low-trust insurance.
- The seed_42 values above are directionally comparable but not numerically identical to those prior pooled counts.

## 4. MG-Owner Trapped Profile

| Model | Group | N | buy_insurance | elevate_house | buyout_program | do_nothing |
| --- | --- | --- | --- | --- | --- | --- |
| Gemma 3 4B | MG-Owner | 1300 | 31.8% | 1.2% | 0.1% | 67.0% |
| Gemma 3 4B | NMG-Owner | 1300 | 38.8% | 2.8% | 2.0% | 56.4% |
| Gemma 4 e4b | MG-Owner | 1300 | 31.5% | 0.8% | 0.0% | 67.7% |
| Gemma 4 e4b | NMG-Owner | 1299 | 64.0% | 2.4% | 0.0% | 33.6% |

Reference values supplied in the task for Gemma 3: MG-Owner executed `do_nothing` = 67.2%, NMG-Owner = 55.0%.

## 5. Implications for Paper 3 Discussion / Limitations

- Gemma 4 substantially reduces owner-side governance failure: owner rejection drops from 21.1% to 2.3%, so cross-model differences are less confounded by blocked actions.
- The strongest Gemma 3 artifact in this comparison is not present in Gemma 4: owner CP=H rises from 3.6% to 23.6%, and CP=H owners are much less passive.
- Gemma 4 shows lower low-SP insurance override than Gemma 3 in this seed_42 comparison (5.6% vs 22.4%), which weakens the case for a generic low-trust insurance bias.
- MG-owner trapping persists in Gemma 4, but it is concentrated in MG owners rather than both owner groups: MG-owner executed do_nothing is 67.7% vs 33.6% for NMG owners.
