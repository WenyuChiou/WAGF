# Diff: this config tree vs. the frozen paper config

Verified 2026-08-01. Command run from the repo root:

```
diff -rq examples/irrigation_abm/config SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt
diff -u  examples/irrigation_abm/config/agent_types.yaml \
         SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt/agent_types.yaml
```

`diff -rq` (recursive, report-only) output: **one line**, naming `agent_types.yaml` as the only
file that differs. `policies/financial_prudence.yaml`, `prompts/irrigation_farmer.txt`,
`README.md`, and `skill_registry.yaml` are byte-identical to the frozen tree.

`diff -u` on `agent_types.yaml` — the full and only delta:

```diff
--- examples/irrigation_abm/config/agent_types.yaml
+++ SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt/agent_types.yaml
@@ -15,6 +15,18 @@
 # GLOBAL CONFIGURATION
 # =============================================================================
 global_config:
+  # TAE first-attempt appraisal logging (SUBMISSION_2026/TAE/EXPERIMENT_OPTIONS.md option 1;
+  # PLAN.md section 5). The ONLY delta versus examples/irrigation_abm/config/agent_types.yaml.
+  # initial_proposal_columns persists the attempt-0 skill + construct labels
+  # (broker/core/skill_broker_engine.py:364-366 -> broker/core/_audit_helpers.py:109-131 ->
+  # broker/components/analytics/audit.py:253-256), key-gated and default-OFF, so this flag is
+  # the whole instrumentation. executed_skill_columns is the free companion flag (F3) that
+  # closes the proposed-vs-executed reading; it does not touch the frozen v21 corpus, which
+  # was produced with this block absent.
+  audit:
+    initial_proposal_columns: true
+    executed_skill_columns: true
+
   memory:
     window_size: 5
     consolidation_threshold: 0.6
```

That is the entire diff: one new `global_config.audit` block, two keys, both `true`, both
key-gated and default-OFF elsewhere in the codebase (`broker/utils/agent_config.py`
`get_audit_initial_proposal_columns` / `get_audit_executed_skill_columns`). Nothing else in
this tree — not the skill registry, not the validators policy, not the prompt template — was
touched. This is what makes the resulting corpus a within-run instrument rather than a new
experimental arm: every rule, every prompt token, every skill definition is identical to the
one that produced the frozen `production_v21_42yr_seed{42..46}` corpus; only two additional
CSV columns get written.

Re-run the two `diff` commands above before the queue starts, to catch any drift introduced
between this file being written and the run actually launching.
