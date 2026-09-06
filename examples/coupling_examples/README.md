# coupling_examples

Worked examples of `broker.coupling` connector patterns — teaching
material for `docs/COUPLING_CONNECTORS.md`, not paper-shipping domains.

## `archetype_c_subprocess/`

Archetype C — service model via subprocess. A governed LLM agent reads
a sensor reading from `external_model.py` (a real subprocess, called
once per period over JSON stdin/stdout) and decides normal-vs-anomaly.
Proves `SubprocessModelConnector` end to end without a GPU.

- `run_archetype_c.py` — runnable script; `external_model.py` — toy sensor.
- `contract.md` — filled coupling-contract narrative (docs only; the
  executable contract is `_build_contract()` in `run_archetype_c.py` —
  no YAML contract loader exists in this repo, by design).
- `config/` — agent-type + skill-registry YAML.

REST (the other "service model" half) stays documented-but-deferred.

## Run it

```bash
python examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py --model mock --years 4
```
