# Two water cases, six short chapters

Run commands from the repository root after the
[installation step](../../README.md#quickstart). All executable examples use the
repository's built-in mock, need no model service, and write under `.tmp/`.
Use fresh output directories. Run chapters in order: later commands inspect the
earlier runs. Repeated run commands in the front page, gallery and chapter 1
describe the same run; do not rerun them into a populated directory.

1. [Run the two quickstarts](01-first-run.md) — one-way flood coupling and the
   paired irrigation wiring check.
2. [See a rule block and retry](02-rules-and-retries.md) — incomplete mock appraisals,
   retries and the executed default.
3. [Read the audit record](03-audit.md) — proposals, attempts, execution and
   integrity limitations.
4. [Run irrigation with Lake Mead](04-water-model.md) — two-way requests,
   deliveries, storage and next-year prompts.
5. [Resume irrigation from its journal](05-resume.md) — replay recorded calls
   into a new directory.
6. [Compute IBR and EHE](06-measures.md) — the share of decisions that break
   the counted rules (IBR) and how evenly decisions spread across actions (EHE),
   with existing analysis modules and what these mock outputs can establish.

The mock returns incomplete appraisals and no usable flood reflections. These
chapters demonstrate framework wiring; they do not supply behavioural or paper
results. Configuration and real-model instructions are in the
[flood](../../examples/single_agent/README.md) and
[irrigation](../../examples/irrigation_abm/README.md) case guides.
