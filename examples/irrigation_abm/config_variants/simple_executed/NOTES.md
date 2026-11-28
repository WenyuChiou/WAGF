# Simple information variant, executed memory lines

All runners use executed memory lines and plain retry wording. This variant sets
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
  decision was read" (unchanged from `simple`).

Reproduce the earlier memory and retry wording from tag v0.7.0.

The without-rules arm's copy is `config_variants/simple_nolimit_executed`.

Run it with `--config-dir examples/irrigation_abm/config_variants/simple_executed`.
Registry, policies, prompts and README are copied unchanged from `simple`.
