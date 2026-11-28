# Irrigation arm without the validator

Use `--governance-mode disabled` with this arm. Its beneficial-use limit is off. From the repository root, pass both flags to the irrigation runner.

```text
--governance-mode disabled --config-dir examples/irrigation_abm/config_variants/without_validator
```

[Agent settings](agent_types.yaml) select the [simple decision template](prompts/irrigation_farmer.txt).
See [configuration overrides](NOTES.md) for the differences from the base irrigation config.
