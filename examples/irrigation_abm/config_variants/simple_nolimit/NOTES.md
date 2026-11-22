# Simple information variant without the beneficial-use limit

Source commit: `7591e80f`. Implements addendum 13 of
`.research/design_specs/irrigation_v3_fix_preregistration_2026-10-09.md`
(gitignored internal design record; referenced here without copying it). The
file name says "preregistration", but nothing was registered with an outside
registry; it is a dated internal design record.

Overrides relative to `config/`:

- `irrigation_farmer.prompt_information: simple`.
- `irrigation_farmer.keepfix_package.S1`, `L`, `K6`, and `table`: `false`.
- `irrigation_farmer.feedback.tracked_metrics: []` and `dashboard_format: none`.
- `irrigation_farmer.prompt_template_file: prompts/irrigation_farmer.txt`,
  pointing to this variant's simple decision template.
- The contents of `prompts/irrigation_farmer.txt` are the simple template.
- Limit switch: `irrigation_farmer.beneficial_use_limit.enabled: false`.

Registry, policies, README and all other settings are copied unchanged.
This `NOTES.md` is additional documentation, excluded from the identical file-set check.
