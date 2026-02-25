# WRR RR Anomaly Expert Audit (Gemma3-4B, Run_1+Run_2)

## Question

Why does `gemma3_4b` show:
- `Group_A RR ~= 1%`
- `Group_C RR > Group_A` in the current table?

## Data and Method

- Logs checked:
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_*/Run_*/simulation_log.csv`
  - `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_*/Run_*/raw/household_traces.jsonl`
- Event-level RR extraction (three-rule definition) exported to:
  - `docs/wrr_gemma3_4b_rr_event_audit_v2.csv`
- Proposal-vs-executed RR comparison exported to:
  - `docs/wrr_rr_proposal_vs_executed_run12.csv`

## Findings (Reviewer-style)

1. `Group_C` RR events are all retry-exhausted rejects.
- `Group_C`: 22 RR events
- All 22 are `trace_outcome=REJECTED`, `trace_retry=3`, `rule=extreme_threat_block`
- Therefore these are not successful governed executions; they are unresolved proposals after retry ceiling.

2. `Group_B` has the same pattern.
- `Group_B`: 7 RR events
- All are also `REJECTED + retry=3`.

3. Current RR table mixes proposal-level quality with execution-level interpretation.
- Current metric pipeline uses `simulation_log` action fields for RR.
- In governed groups, rejected proposals can still appear as `yearly_decision=do_nothing`, so they are counted in proposal-level RR.
- This is valid for proposal-quality diagnostics, but can be misread as final executed behavior.

4. Why `Group_A` is around 1%.
- `Group_A` has no governance retry path; proposal and execution are effectively the same.
- Under the current strict 3-rule RR definition, `gemma3_4b Group_A` has 21/1998 violations (`1.051%`).
- Distribution:
  - high-threat inaction: 16
  - low-threat structural: 5
  - low-threat relocation: 0

## Quantitative Contrast (Gemma3-4B)

From `docs/wrr_rr_proposal_vs_executed_run12.csv`:

- `Group_A`: proposal RR `1.051%`, executed RR `1.051%`
- `Group_B`: proposal RR `0.412%`, executed RR `0.000%`
- `Group_C`: proposal RR `1.267%`, executed RR `0.000%`

Interpretation:
- The apparent `Group_C > Group_A` inversion is proposal-level residuals.
- At executed-action level, governed groups are `0%` for this RR definition in current runs.

## Logging/Schema Issue Found

In `examples/single_agent/run_flood.py`, `governance_intervention` is computed as:

- `proposed_skill != skill_name` when both exist, else `False`.

For rejected cases where proposed and approved skill names are equal (status rejected), this can log `False` even with `retry_count=3` and failed rules.

This underreports intervention in `simulation_log` and can mislead downstream analysis.

## Recommended Manuscript Handling

1. Keep current RR in main table only if clearly labeled as proposal-level RR.
2. Add executed-only RR (or at least a sensitivity note) in SI.
3. Add one sentence explaining retry-ceiling residuals:
- governed RR residuals are dominated by `REJECTED + retry=3` proposal rows.
4. Fix logging semantics in code before final camera-ready reruns.

