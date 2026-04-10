# Gemma 4 Rerun vs Gemma 3 Seed_42 Analysis

Rerun context:
- Broker thinking bug fix (`fc6c599`): `--thinking-mode disabled` now maps to Ollama top-level `think=false`.
- PA prompt criteria fix (`145198c`): explicit generational PA anchors plus removal of buyout emotional priming from the owner prompt.

Scope:
- Gemma 3 baseline: `examples/multi_agent/flood/paper3/results/paper3_hybrid_v2/seed_42/gemma3_4b_strict/`
- Gemma 4 rerun: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b/seed_42/gemma4_e4b_strict/`
- Gemma 4 manifest confirms `thinking_mode=disabled` at commit `145198c6d077179b8038a66b77a81507a656c4c7`.
- MG and generations are joined from `examples/multi_agent/flood/data/agent_profiles_balanced.csv` by `agent_id`.

Method notes:
- CSVs loaded with pandas using `encoding='utf-8-sig'`.
- Rejection rate is `status != APPROVED`.
- Retry rate is `retry_count > 0` with missing treated as 0.
- Construct distributions are normalized over valid non-missing labels `{VL,L,M,H,VH}`; malformed labels are excluded and noted.
- MG-owner executed `do_nothing` maps non-approved owner decisions to executed `do_nothing`.

## 1. Basic Metrics

| Model | Agent | N | Reject | Retry | Action distribution | TP (VL/L/M/H/VH) | CP (VL/L/M/H/VH) | SP (VL/L/M/H/VH) | SC (VL/L/M/H/VH) | PA (VL/L/M/H/VH) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 3 4B | Owner | 2600 | 21.1% | 30.7% | buy_insurance 38.2%<br>elevate_house 17.9%<br>buyout_program 3.3%<br>do_nothing 40.6% | VL 0.0%/L 17.2%/M 25.8%/H 57.0%/VH 0.0% | VL 0.0%/L 22.2%/M 74.2%/H 3.6%/VH 0.0% | VL 0.0%/L 41.2%/M 54.5%/H 4.2%/VH 0.0% | VL 0.7%/L 83.5%/M 12.5%/H 3.4%/VH 0.0% | VL 0.7%/L 22.3%/M 60.1%/H 16.5%/VH 0.4% |
| Gemma 3 4B | Renter | 2600 | 4.2% | 14.1% | buy_contents_insurance 37.5%<br>relocate 3.6%<br>do_nothing 58.8% | VL 0.0%/L 22.7%/M 33.9%/H 43.0%/VH 0.4% | VL 0.0%/L 31.0%/M 68.3%/H 0.7%/VH 0.0% | VL 0.0%/L 39.1%/M 59.5%/H 1.4%/VH 0.0% | VL 0.1%/L 71.7%/M 27.6%/H 0.6%/VH 0.0% | VL 0.1%/L 40.6%/M 48.2%/H 11.1%/VH 0.0% |
| Gemma 4 e4b (NEW) | Owner | 2600 | 4.4% | 9.2% | buy_insurance 52.8%<br>elevate_house 1.3%<br>buyout_program 0.1%<br>do_nothing 45.7% | VL 0.0%/L 12.9%/M 22.5%/H 31.7%/VH 32.9% | VL 2.1%/L 24.6%/M 65.2%/H 8.0%/VH 0.0% | VL 0.0%/L 18.2%/M 49.7%/H 32.1%/VH 0.0% | VL 0.0%/L 8.6%/M 88.0%/H 3.4%/VH 0.0% | VL 0.0%/L 0.0%/M 5.4%/H 88.2%/VH 6.4% |
| Gemma 4 e4b (NEW) | Renter | 2600 | 6.2% | 10.6% | buy_contents_insurance 59.4%<br>relocate 1.3%<br>do_nothing 39.3% | VL 0.0%/L 11.8%/M 18.7%/H 33.3%/VH 36.2% | VL 0.0%/L 4.2%/M 87.0%/H 8.8%/VH 0.0% | VL 0.0%/L 11.0%/M 58.6%/H 30.3%/VH 0.1% | VL 0.0%/L 5.0%/M 69.7%/H 24.7%/VH 0.7% | VL 0.0%/L 0.7%/M 25.2%/H 63.0%/VH 11.1% |

Construct data quality notes:
- Gemma 3 4B Owner TP: valid n=2595 of N=2600.
- Gemma 3 4B Owner CP: valid n=2594 of N=2600.
- Gemma 3 4B Owner SP: valid n=2594 of N=2600.
- Gemma 3 4B Owner SC: valid n=2594 of N=2600.
- Gemma 3 4B Owner PA: valid n=2594 of N=2600.
- Gemma 4 e4b (NEW) Owner TP: valid n=2587 of N=2600.
- Gemma 4 e4b (NEW) Owner CP: valid n=2584 of N=2600.
- Gemma 4 e4b (NEW) Owner SP: valid n=2584 of N=2600.
- Gemma 4 e4b (NEW) Owner SC: valid n=2584 of N=2600.
- Gemma 4 e4b (NEW) Owner PA: valid n=2584 of N=2600.
- Gemma 4 e4b (NEW) Renter TP: valid n=2586 of N=2600.
- Gemma 4 e4b (NEW) Renter CP: valid n=2577, non-missing n=2578, invalid labels excluded: m=1.
- Gemma 4 e4b (NEW) Renter SP: valid n=2577 of N=2600.
- Gemma 4 e4b (NEW) Renter SC: valid n=2579, non-missing n=2581, invalid labels excluded: m=2.
- Gemma 4 e4b (NEW) Renter PA: valid n=2583 of N=2600.

## 2. PA Calibration Check

| Model | Owner PA distribution | 1-gen H+VH | 1-2 gen H+VH | 3+ gen H+VH | Verdict |
| --- | --- | --- | --- | --- | --- |
| Gemma 3 4B | VL 0.7%/L 22.3%/M 60.1%/H 16.5%/VH 0.4% | 11.2% | 12.1% | 53.8% | acceptable |
| Gemma 4 e4b (NEW) | VL 0.0%/L 0.0%/M 5.4%/H 88.2%/VH 6.4% | 93.1% | 93.6% | 97.3% | biased |

PA by owner generations:

| Model | Generations | N | VL | L | M | H | VH | H+VH |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 3 4B | 1 | 2106 | 0.8% | 24.9% | 62.9% | 11.1% | 0.1% | 11.2% |
| Gemma 3 4B | 2 | 195 | 0.0% | 17.9% | 60.0% | 21.0% | 0.5% | 21.5% |
| Gemma 3 4B | 3 | 182 | 0.0% | 8.2% | 43.4% | 47.3% | 1.1% | 48.4% |
| Gemma 3 4B | 4 | 39 | 0.0% | 7.7% | 53.8% | 38.5% | 0.0% | 38.5% |
| Gemma 3 4B | 5 | 78 | 0.0% | 1.3% | 24.4% | 67.9% | 6.4% | 74.4% |
| Gemma 4 e4b (NEW) | 1 | 2106 | 0.0% | 0.0% | 6.2% | 88.9% | 4.2% | 93.1% |
| Gemma 4 e4b (NEW) | 2 | 195 | 0.0% | 0.0% | 1.0% | 86.7% | 11.8% | 98.5% |
| Gemma 4 e4b (NEW) | 3 | 182 | 0.0% | 0.0% | 3.3% | 89.0% | 7.7% | 96.7% |
| Gemma 4 e4b (NEW) | 4 | 39 | 0.0% | 0.0% | 2.6% | 84.6% | 10.3% | 94.9% |
| Gemma 4 e4b (NEW) | 5 | 78 | 0.0% | 0.0% | 0.0% | 53.8% | 46.2% | 100.0% |

Verdict:
- Gemma 3 broadly follows the intended gradient: 1-generation owners are mostly M, while H/VH rises for 3+ generations (53.8%).
- Gemma 4 still saturates PA. H/VH covers 94.6% of owner decisions overall and 93.1% of 1-generation owners.

## 3. CP Reversal Check

| Model | CP=H share | CP=H N | CP=H do_nothing | CP=H do_nothing rate |
| --- | --- | --- | --- | --- |
| Gemma 3 4B | 3.6% | 93 | 78/93 | 83.9% |
| Gemma 4 e4b (NEW) | 8.0% | 208 | 166/208 | 79.8% |

Verdict: Gemma 4 still shows the CP reversal artifact. The CP=H share rises from 3.6% to 8.0%, and CP=H owners still choose `do_nothing` in 79.8% of cases.

## 4. Deliberative Override Check

- Case A: `TP in {H,VH}` and `SP in {H,VH}`; fraction still choosing `do_nothing`.
- Case B: `SP in {L,VL}`; fraction choosing insurance (`buy_insurance` or `buy_contents_insurance`).

| Model | Case A count | Case A do_nothing | Case B count | Case B insurance |
| --- | --- | --- | --- | --- |
| Gemma 3 4B | 44/146 | 30.1% | 468/2086 | 22.4% |
| Gemma 4 e4b (NEW) | 177/1592 | 11.1% | 89/752 | 11.8% |

Verdict: deliberative override weakens in Gemma 4. Case A high-motivation inaction falls from 30.1% to 11.1%, and Case B low-SP insurance falls from 22.4% to 11.8%.

## 5. MG-Owner Trapped Profile

| Model | MG owners N | MG do_nothing | NMG owners N | NMG do_nothing | Gap (MG-NMG) |
| --- | --- | --- | --- | --- | --- |
| Gemma 3 4B | 1300 | 67.0% | 1300 | 56.4% | +10.6 pp |
| Gemma 4 e4b (NEW) | 1300 | 64.2% | 1300 | 35.8% | +28.4 pp |

Verdict: MG-owner trapping is amplified in Gemma 4. The executed `do_nothing` gap widens from +10.6 pp in Gemma 3 to +28.4 pp in Gemma 4.

## 6. Verdict Table

| Finding | Gemma 3 4B | Gemma 4 e4b (NEW) | Verdict |
| --- | --- | --- | --- |
| CP reversal | 3.6%; do_nothing 83.9% | 8.0%; do_nothing 79.8% | persists |
| PA saturation | H+VH 16.9% | H+VH 94.6% | biased |
| Deliberative override | Case A 30.1%; Case B 22.4% | Case A 11.1%; Case B 11.8% | weakened |
| MG-Owner trapping | 67.0% vs 56.4% | 64.2% vs 35.8% | amplified |

## 7. Implications for Paper 3 Dual-Model Strategy

- Gemma 4 is not a clean cross-model robustness check for the PA channel: owner PA remains heavily saturated at H/VH even after disabling thinking and adding level anchors.
- The PA saturation problem is strongest exactly where the new prompt was supposed to help. Among 1-generation owners, Gemma 4 still assigns H/VH PA in 93.1% of decisions, versus an intended M baseline for 1-2 generations.
- The CP reversal artifact also persists post-fix. Gemma 4 owners labeled CP=H still choose `do_nothing` 79.8% of the time, only modestly below Gemma 3's 83.9%.
- Some RQ3 patterns do look robust across models: MG-owner trapping survives in both, and the MG/NMG gap is larger in Gemma 4 (+28.4 pp vs +10.6 pp).
- Some RQ3 patterns are model-sensitive rather than robust. Deliberative override weakens sharply in Gemma 4, with high TP+SP inaction dropping to 11.1% and low-SP insurance dropping to 11.8%.
- For the Discussion paragraph, frame Gemma 4 as a useful stress test rather than a confirmatory replicate: it preserves some structural asymmetries but introduces strong PA bias and still retains the CP reversal failure mode.
- A defensible dual-model strategy is to treat convergent findings such as MG-owner trapping as more credible, while labeling PA-heavy and CP-heavy construct interpretations as model-contingent.
