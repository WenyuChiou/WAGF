# Coupling pattern chooser

Use this page during C0 pattern recognition. Pick the simplest pattern
that can answer the research question without hiding feedback-loop
assumptions.

| Pattern | Name | When to use | Adapter template |
|---|---|---|---|
| A | File replay | You have CSV, NetCDF, or gridded outputs already produced by a model run, and WAGF only needs to replay them by year, scenario, or agent. | `.claude/skills/wagf-coupling-designer/templates/adapter_A_file_replay.py.tmpl` |
| B | Python library | The external model is importable in the same Python process and can expose `step()`, `predict()`, or a similar call. | `.claude/skills/wagf-coupling-designer/templates/adapter_B_python_library.py.tmpl` |
| C | Subprocess CLI | The model runs from a command line tool and reads/writes files per step; deferred to v2 because error handling and temp directories need a stricter scaffold. | deferred to v2 |
| D | Long-running service | The model stays alive behind HTTP, gRPC, or a socket; deferred to v2 because retries, timeouts, and idempotency must be designed first. | deferred to v2 |
| E | Co-simulation engine | WAGF and a simulator advance together through a broker such as FMI, mosaik, or custom event scheduling; deferred to v2 because clock ownership is the hard part. | deferred to v2 |

## Quick choice rule

Start with Pattern A when the external model is expensive, opaque, or
already has scenario outputs. It gives deterministic smoke tests and
lets the PhD build the WAGF side before gaining model runtime access.

Use Pattern B when the model author can provide a Python object with a
stable API. It is the fastest integration loop, but it also shares
memory, random state, and crash fate with the WAGF process.

Do not choose Pattern C/D/E just because the real model eventually
needs them. Build the contract and mock first, then upgrade the adapter
only when the real boundary is documented.

## Required next file

After choosing A or B, open the matching pattern reference:

- Pattern A: `.claude/skills/wagf-coupling-designer/references/coupling_patterns/A_file_replay.md`
- Pattern B: `.claude/skills/wagf-coupling-designer/references/coupling_patterns/B_python_library.md`

Then draft the contract from:

- `.claude/skills/wagf-coupling-designer/templates/coupling_contract.md.tmpl`

## Classification prompts

Ask these before choosing:

- Do you need the agent action to change the external model state during
  the same run?
- Can you run the external model locally from Python today?
- Are the available files outputs, inputs, or calibration data?
- Does the PhD need a smoke test before the real model is accessible?

Answers usually sort cleanly:

- Existing outputs only: Pattern A.
- Importable Python model: Pattern B.
- Executable binary with files: Pattern C later.
- Network or queue boundary: Pattern D later.
- Shared clock negotiation: Pattern E later.

## Common misclassification

Do not call a static scenario CSV "Python library coupling" because
pandas reads it. The boundary is still file replay.

Do not call an importable surrogate "file replay" because it was trained
from CSV. The boundary is the Python API.
