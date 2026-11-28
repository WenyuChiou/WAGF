# Configuration overrides for with_validator

Use `--governance-mode strict` with this arm. Its beneficial-use limit is on. The two arms use the same simple-information prompt.

Relative to `config/`, this arm sets the following options.

- `irrigation_farmer.prompt_information: simple` and `prompt_template_file: prompts/irrigation_farmer.txt` select this folder's simple decision template. The two appraisal fields have shorter reason hints.
- `shared.rating_scale` is removed and the template has no `{rating_scale}` line. The prompt explains each five-level rating in plain words, so the generic "VL = Very Low ... VH = Very High" block is not shown.
- The keepfix options `S1`, `L`, `K6` and `table` are false. Feedback uses `tracked_metrics: []` and `dashboard_format: none`.
- `global_config.llm.sampling_seed: per_call` sets a reproducible seed for each call. `global_config.audit.retry_prompt_columns: true` records the retry text in the raw trace.
- `global_config.governance.intervention_framing: plain` selects plain retry wording. The two strict thinking-rule messages name the unavailable action and give the reason. Memory lines record the executed action.
- `irrigation_farmer.beneficial_use_limit.enabled` is `true` (the base setting). Both arms use the base skill registry and policies.

Before 2026-11-27 these folders were named `simple_executed` and `simple_nolimit_executed`, and earlier `simple` and `simple_nolimit` runs can be reproduced from tag v0.7.0.
