# Gemma 4 Nature Water Cross-Model Analysis

Generated from `household_governance_audit.csv` pooled across `Run_1` to `Run_5` for the eight-model flood comparison.

## Summary Table: All 8 Models

| Model | Condition | N | IBR | EHE | buy_insurance | elevate_house | relocate | do_nothing | TP VL | TP L | TP M | TP H | TP VH | Rejection | Retry |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Gemma 3 12B | disabled | 4661 | 0.0% | 0.472 | 81.5% | 10.3% | 2.4% | 5.7% | 0.0% | 28.4% | 69.6% | 2.0% | 0.0% | 0.0% | 0.0% |
| Gemma 3 12B | governed | 4840 | 0.0% | 0.430 | 83.1% | 9.9% | 1.0% | 5.9% | 0.0% | 25.8% | 71.6% | 2.6% | 0.0% | 0.0% | 0.1% |
| Gemma 3 27B | disabled | 4949 | 0.4% | 0.652 | 61.2% | 9.6% | 0.3% | 28.9% | 0.0% | 28.5% | 52.8% | 16.2% | 2.5% | 0.0% | 0.0% |
| Gemma 3 27B | governed | 4989 | 0.0% | 0.675 | 53.2% | 9.3% | 0.2% | 37.3% | 0.0% | 34.7% | 46.1% | 14.4% | 4.8% | 0.0% | 0.5% |
| Gemma 3 4B | disabled | 4662 | 8.2% | 0.736 | 47.4% | 10.2% | 1.6% | 40.8% | 4.6% | 12.7% | 47.1% | 30.9% | 4.7% | 0.0% | 0.0% |
| Gemma 3 4B | governed | 4468 | 0.9% | 0.756 | 52.2% | 10.6% | 2.9% | 34.2% | 4.7% | 13.9% | 48.9% | 28.2% | 4.2% | 1.1% | 8.3% |
| Gemma 4 e2b | disabled | 4646 | 0.1% | 0.601 | 72.4% | 10.4% | 2.0% | 15.2% | 0.0% | 17.3% | 66.3% | 16.4% | 0.0% | 0.0% | 0.0% |
| Gemma 4 e2b | governed | 4629 | 0.0% | 0.613 | 71.7% | 10.4% | 2.3% | 15.7% | 0.1% | 17.1% | 66.2% | 16.5% | 0.0% | 0.0% | 0.1% |
| Gemma 4 e4b | disabled | 3943 | 5.2% | 0.479 | 79.7% | 9.7% | 0.5% | 10.1% | 0.0% | 1.5% | 14.6% | 72.6% | 11.4% | 0.0% | 0.0% |
| Gemma 4 e4b | governed | 4924 | 0.0% | 0.356 | 86.3% | 9.7% | 0.4% | 3.6% | 0.0% | 1.4% | 14.8% | 73.1% | 10.8% | 0.0% | 4.7% |
| Ministral 3 14B | disabled | 4345 | 1.1% | 0.748 | 60.4% | 13.5% | 4.0% | 22.1% | 7.8% | 24.8% | 44.3% | 21.5% | 1.7% | 0.0% | 0.0% |
| Ministral 3 14B | governed | 4634 | 0.0% | 0.695 | 62.1% | 10.2% | 2.3% | 25.4% | 11.2% | 28.0% | 41.3% | 18.0% | 1.5% | 0.0% | 5.3% |
| Ministral 3 3B | disabled | 3410 | 2.4% | 0.763 | 62.8% | 16.5% | 11.1% | 9.5% | 1.2% | 20.5% | 43.5% | 32.4% | 2.4% | 0.0% | 0.0% |
| Ministral 3 3B | governed | 3674 | 0.1% | 0.699 | 68.3% | 12.9% | 9.4% | 9.4% | 1.3% | 19.7% | 47.9% | 28.7% | 2.4% | 0.1% | 9.3% |
| Ministral 3 8B | disabled | 4482 | 1.6% | 0.683 | 66.4% | 13.1% | 2.9% | 17.7% | 5.3% | 17.0% | 55.6% | 19.9% | 2.2% | 0.0% | 0.0% |
| Ministral 3 8B | governed | 4195 | 0.0% | 0.632 | 72.6% | 11.2% | 5.4% | 10.8% | 1.9% | 10.1% | 57.5% | 28.0% | 2.6% | 0.0% | 5.2% |

Notes:
- `IBR` is the pooled share of decisions with `construct_TP_LABEL` in `{H, VH}` and `final_skill = do_nothing`.
- `EHE` is normalized Shannon entropy over `buy_insurance`, `elevate_house`, `relocate`, and `do_nothing`.
- Rejection rate counts `status != APPROVED`. Retry rate counts `retry_count > 0`.

## Governance Effect

| Model | Mean IBR governed | Mean IBR disabled | dIBR | Mean EHE governed | Mean EHE disabled | dEHE | p-value |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gemma 3 12B | 0.0% | 0.0% | 0.0% | 0.427 | 0.467 | 0.040 | 1.0000 |
| Gemma 3 27B | 0.0% | 0.4% | 0.4% | 0.674 | 0.644 | -0.030 | 0.0075 |
| Gemma 3 4B | 0.9% | 8.2% | 7.3% | 0.749 | 0.728 | -0.021 | 0.0079 |
| Gemma 4 e2b | 0.0% | 0.1% | 0.1% | 0.612 | 0.601 | -0.012 | 0.0720 |
| Gemma 4 e4b | 0.0% | 5.3% | 5.3% | 0.355 | 0.477 | 0.123 | 0.0108 |
| Ministral 3 14B | 0.0% | 1.1% | 1.1% | 0.694 | 0.747 | 0.053 | 0.0075 |
| Ministral 3 3B | 0.1% | 2.4% | 2.4% | 0.698 | 0.763 | 0.065 | 0.0097 |
| Ministral 3 8B | 0.0% | 1.6% | 1.6% | 0.632 | 0.679 | 0.047 | 0.0097 |

Interpretation: positive `dIBR` or `dEHE` means the disabled condition is higher than the governed condition.

## Cross-Generation Comparison: Gemma 3 4B vs Gemma 4 e4b

**Governed**

| Metric | Gemma 3 4B | Gemma 4 e4b | Difference (Gemma 4 - Gemma 3, pp) |
|---|---:|---:|---:|
| IBR | 0.9% | 0.0% | -0.9 |
| Action `buy_insurance` | 52.2% | 86.3% | 34.1 |
| Action `elevate_house` | 10.6% | 9.7% | -0.8 |
| Action `relocate` | 2.9% | 0.4% | -2.6 |
| Action `do_nothing` | 34.2% | 3.6% | -30.7 |
| TP `VL` | 4.7% | 0.0% | -4.7 |
| TP `L` | 13.9% | 1.4% | -12.5 |
| TP `M` | 48.9% | 14.8% | -34.1 |
| TP `H` | 28.2% | 73.1% | 44.9 |
| TP `VH` | 4.2% | 10.8% | 6.6 |

Interpretation: less high-threat inaction, more insurance uptake, a harsher TP profile, conservatism diagnostics show CCA=0.839, ACI=0.645, ESRR=0.004.

**Disabled**

| Metric | Gemma 3 4B | Gemma 4 e4b | Difference (Gemma 4 - Gemma 3, pp) |
|---|---:|---:|---:|
| IBR | 8.2% | 5.2% | -3.0 |
| Action `buy_insurance` | 47.4% | 79.7% | 32.3 |
| Action `elevate_house` | 10.2% | 9.7% | -0.5 |
| Action `relocate` | 1.6% | 0.5% | -1.2 |
| Action `do_nothing` | 40.8% | 10.1% | -30.7 |
| TP `VL` | 4.6% | 0.0% | -4.6 |
| TP `L` | 12.7% | 1.5% | -11.2 |
| TP `M` | 47.1% | 14.6% | -32.5 |
| TP `H` | 30.9% | 72.6% | 41.7 |
| TP `VH` | 4.7% | 11.4% | 6.6 |

Interpretation: less high-threat inaction, more insurance uptake, a harsher TP profile, conservatism diagnostics show CCA=0.840, ACI=0.523, ESRR=0.006.

## Conservatism Analysis

Command run:

```bash
python examples/single_agent/analysis/model_conservatism_report.py --results-dir examples/single_agent/results
```

Output:

```text
Found 79 experiment runs

====================================================================================================
Model                Cond            N     CCA     CSI     ACI    ESRR  TP H+VH% Top Action         Warnings
----------------------------------------------------------------------------------------------------
gemma3_12b           disabled     4661   0.020  -0.087   0.533   0.046      2.0% buy_insurance      ACI=0.52: action over-concentration; ACI=0.55: action over-concentration
gemma3_12b           governed     4840   0.026  -0.086   0.573   0.013      2.6% buy_insurance      ACI=0.53: action over-concentration; ACI=0.56: action over-concentration
gemma3_27b           disabled     4949   0.187   0.015   0.321   0.029     18.7% buy_insurance      CCA=0.17: model severely under-reports threat; CCA=0.18: model severely under-reports threat
gemma3_27b           governed     4989   0.192  -0.038   0.292   0.024     19.2% buy_insurance      CCA=0.17: model severely under-reports threat; CCA=0.18: model severely under-reports threat
gemma3_4b            disabled     4662   0.358  -0.130   0.272   0.014     35.6% buy_insurance      CCA=0.29: model severely under-reports threat; CCA=0.31: model under-reports threat
gemma3_4b            governed     4468   0.325  -0.107   0.251   0.032     32.4% buy_insurance      CCA=0.30: model under-reports threat; CCA=0.31: model under-reports threat
gemma4_e2b           disabled     4646   0.164  -0.332   0.399   0.028     16.4% buy_insurance      CCA=0.16: model severely under-reports threat; CCA=0.17: model severely under-reports threat
gemma4_e2b           governed     4629   0.166  -0.324   0.388   0.029     16.5% buy_insurance      CCA=0.15: model severely under-reports threat; CCA=0.16: model severely under-reports threat
gemma4_e4b           disabled     3943   0.840  -0.038   0.523   0.006     84.0% buy_insurance      ACI=0.50: action over-concentration; ACI=0.54: action over-concentration
gemma4_e4b           governed     4924   0.839  -0.048   0.645   0.004     83.9% buy_insurance      ACI=0.63: action over-concentration; ACI=0.65: action over-concentration
ministral3_14b       disabled     4345   0.232  -0.043   0.253   0.091     23.2% buy_insurance      CCA=0.19: model severely under-reports threat; CCA=0.20: model severely under-reports threat
ministral3_14b       governed     4634   0.195  -0.165   0.306   0.032     19.4% buy_insurance      CCA=0.19: model severely under-reports threat; CCA=0.20: model severely under-reports threat
ministral3_3b        disabled     3410   0.348   0.143   0.237   0.219     34.8% buy_insurance      CCA=0.33: model under-reports threat; CCA=0.34: model under-reports threat
ministral3_3b        governed     3674   0.312   0.070   0.302   0.158     31.1% buy_insurance      CCA=0.28: model severely under-reports threat; CCA=0.29: model severely under-reports threat
ministral3_8b        disabled     4482   0.222  -0.094   0.321   0.077     22.1% buy_insurance      CCA=0.18: model severely under-reports threat; CCA=0.19: model severely under-reports threat
ministral3_8b        governed     4195   0.305   0.093   0.368   0.086     30.5% buy_insurance      CCA=0.28: model severely under-reports threat; CCA=0.29: model severely under-reports threat
====================================================================================================

Metric Guide:
  CCA  = Construct-Context Alignment [0-1]: fraction of flood-year decisions with TP>=H
  CSI  = Construct Sensitivity Index [-1,1]: Spearman(year, TP) - responsiveness to exposure
  ACI  = Action Concentration Index [0-1]: 0=diverse, 1=all same action
  ESRR = Extreme Scenario Response Rate [0-1]: strong actions in severe scenarios

[stderr]
C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\config\schema.py:142: UserWarning: Field name "construct" in "RuleCondition" shadows an attribute in parent "BaseModel"
  class RuleCondition(BaseModel):
C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\broker\config\schema.py:172: UserWarning: Field name "construct" in "GovernanceRule" shadows an attribute in parent "BaseModel"
  class GovernanceRule(BaseModel):
```

## Key Findings for NW Discussion

- Gemma 4 e2b keeps a governance effect: pooled IBR falls from 0.1% to 0.0% (per-seed dIBR=0.1%, p=0.0720).
- Gemma 4 e4b keeps a governance effect: pooled IBR falls from 5.2% to 0.0% (per-seed dIBR=5.3%, p=0.0108).
- Behavioral diversity remains high for Gemma 4: governed/disabled EHE is 0.613/0.601 for Gemma 4 e2b and 0.356/0.479 for Gemma 4 e4b.
- Against Gemma 3 4B, governed Gemma 4 e4b reduces `do_nothing` by -30.7 pp and shifts behavior toward insurance/elevation, lowering pooled IBR by -0.9 pp.
- Conservatism diagnostics suggest Gemma 4 governed variants are not simply frozen into `do_nothing`: Gemma 4 e2b has ACI=0.388 and ESRR=0.029, while Gemma 4 e4b has ACI=0.645 and ESRR=0.004.
