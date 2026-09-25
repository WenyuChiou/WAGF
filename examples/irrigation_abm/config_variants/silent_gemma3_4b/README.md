# Irrigation config variant: silent_gemma3_4b

This is an **experiment-arm config variant**, not the primary irrigation
config surface (that lives at
[`../../config/`](../../config/), read its own README first).

## What this is

A full copy of `examples/irrigation_abm/config/` as it stood at commit
`fcd74a5f` on `main`, with exactly one governance line changed in
`agent_types.yaml` (line 53): `retry_feedback_mode: silent` added under
`global_config.governance:`. `skill_registry.yaml`,
`prompts/irrigation_farmer.txt`, and `policies/financial_prudence.yaml` are
byte-identical to their sources. This `README.md` is the one other
intentional difference, rewritten to describe the variant instead of the
source directory (a plain copy of the source README would have pointed
`../run_experiment.py` and `../validators/` at paths that do not resolve
from inside `config_variants/`).

Confirm `agent_types.yaml` is still the only *behavioural* diff before using
this variant for a real run:

```
diff -r examples/irrigation_abm/config examples/irrigation_abm/config_variants/silent_gemma3_4b
```

(expect exactly two hunks: the `retry_feedback_mode` line above, and this
README).

## Why it exists

Irrigation has no `--retry-feedback-mode` CLI flag (unlike flood's
`examples/single_agent/run_flood.py`); the knob is set via the YAML config
only. `run_experiment.py` needs a *complete* config tree when pointed at an
isolated `--config-dir`, so this is a full copy rather than a single
overlaid file.

## How to run it

```
--config-dir examples/irrigation_abm/config_variants/silent_gemma3_4b
```

(plus the usual `--model` / `--years` / `--agents` / `--governance-mode`
flags; see `examples/irrigation_abm/run_experiment.py`'s own `--help`.)

## Naming note

`silent_gemma3_4b` names the intended experiment arm (mirroring the sibling
`placebo_gemma3_4b` naming convention this branch was asked to follow), not
a config-level model pin: `agent_types.yaml`'s `llm.model` is
`"command-line-override"`, same as the source, and the actual model comes
from `run_experiment.py --model` at invocation time.

## Re-sync note

This is a plain file copy, not a generated overlay: if
`examples/irrigation_abm/config/` changes, this variant will silently drift
out of parity unless it is re-copied (keeping the one `retry_feedback_mode`
line) and re-diffed with the command above. There is no automation that
keeps the two in sync.
