# Simple information variant without the beneficial-use limit, executed memory lines

A copy of `config_variants/simple_nolimit` (the without-rules arm; added 2026-11-26) with this change:
`irrigation_farmer.memory.rejection_line_style: executed` (Invariant 7 in
`broker/INVARIANTS.md`: rules correct the current decision and leave no trace).

Also (2026-11-26, the retry labels are for the logs only):
`global_config.governance.intervention_framing: plain`, so the retry text the
agent sees carries no log label, and the two thinking-rule messages open with
"Under the rule on ..., ... is not available in this decision" instead of
"... blocked under the rule on ...". The reason after the colon is unchanged.

- Every year with a decision gets the same memory line form, whether a rule
  stepped in or not: `Year Y: Action carried out: <action>{ (by N%)}.` followed
  by the year's outcome. The line names no rule and no blocked proposal.
- Importance, emotion and routine of that line, and the reflection's salience
  inputs, follow the action that ran only (`_proposed_and_fallback` in
  `run_experiment.py`).
- An unreadable answer that ran the default reads "Action carried out" like any
  other year. Only an aborted year, where nothing ran, still reads "no valid
  decision was read" (unchanged from `simple_nolimit`).

`config_variants/simple`, `simple_nolimit` and `config/agent_types.yaml` are
unchanged; their paper runs stay as they are. Re-running both arms on these
variants waits on the owner's OK.

Run it with `--config-dir examples/irrigation_abm/config_variants/simple_nolimit_executed`.
Registry, policies, prompts and README are copied unchanged from `simple_nolimit`.
