# WRR Reasoning-Log Behavioral Audit (Governed Flood Traces)

- Trace scope: Group_B/Group_C only
- Candidate cases: 38
- Physical-tagged cases: 1
- Physical high-confidence cases: 1
- Irrational-tagged cases: 38
- CSV: `docs/wrr_reasoning_log_behavioral_cases_v6.csv`

## Physical/Identity Findings

- `re_elevation`: 1

Outcome split:
- `REJECTED`: 1

- Intent-mismatch flagged: 1

## Irrational (Thinking-Coherence) Findings

- `low_threat_costly_structural`: 8
- `high_threat_inaction`: 29
- `low_threat_relocation`: 1

Outcome split:
- `REJECTED`: 38

## Representative Physical Examples

| Type | Model/Group/Run | Agent-Year | Skill | Outcome | Retry | Intent Mismatch | Reasoning |
|---|---|---|---|---|---:|---|---|
| re_elevation | ministral3_3b/Group_B/Run_1 | Agent_73/Y5 | elevate_house | REJECTED | 3 | text_mentions_insurance_but_skill_is_elevation |  |

## Representative Irrational Examples

| Type | Model/Group/Run | Agent-Year | Skill | TP_LABEL | Outcome | Retry | Reasoning |
|---|---|---|---|---|---|---:|---|
| low_threat_costly_structural | gemma3_12b/Group_B/Run_2 | Agent_13/Y2 | elevate_house | L | REJECTED | 3 | While I have flood insurance, my doubts about the insurance company and skepticism towards my neighbors' actions make me uneasy. The flood 15 years ago, though not directly impacting my neighborhood, demonstrates the potential for significant damage. Given the available elevation |
| low_threat_costly_structural | gemma3_12b/Group_C/Run_2 | Agent_20/Y2 | elevate_house | L | REJECTED | 3 | While I've been fortunate to avoid flooding so far, the past flood event and the reported insurance claim delays, coupled with my slight doubts about my insurance company, suggest a need for proactive measures. My neighbors are increasingly elevating their homes, and I trust thei |

## Expert Interpretation

- Most physical inconsistencies in governed traces are intercepted (rejected or retried), indicating validator containment rather than execution leakage.
- The strongest physical case shows parser-intent mismatch: free-text rationale supports insurance-like behavior while parsed skill is elevation under already-elevated state.
- Remaining irrational cases are primarily coherence mismatches (e.g., high-threat inaction), consistent with bounded-rational behavior under finite retry budgets.
