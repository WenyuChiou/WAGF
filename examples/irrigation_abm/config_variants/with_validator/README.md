# Irrigation arm with the validator

Use `--governance-mode strict` with this arm. Its beneficial-use limit is on. From the repository root, pass both flags to the irrigation runner.

```text
--governance-mode strict --config-dir examples/irrigation_abm/config_variants/with_validator
```

[Agent settings](agent_types.yaml) select the [simple decision template](prompts/irrigation_farmer.txt).
See [configuration overrides](NOTES.md) for the differences from the base irrigation config.
