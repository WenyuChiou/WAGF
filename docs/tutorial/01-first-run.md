# 1. Run the two quickstarts

From the repository root, install WAGF as described in the
[quickstart](../../README.md#quickstart), then run the built-in mock with a fresh
output directory:

```bash
python examples/single_agent/run_flood.py --model mock --years 1 --agents 2 --workers 1 --seed 42 --governance-mode strict --output .tmp/readme-flood
```

Run the paired irrigation wiring check with a different fresh output directory:

```bash
python examples/irrigation_abm/run_experiment.py --model mock --years 2 --agents 2 --workers 1 --seed 42 --governance-mode strict --coupling --output .tmp/readme-irrigation
```

That run writes four decisions to `irrigation_farmer_governance_audit.csv` and
the coupled water state to `simulation_log.csv`. [Chapter 4](04-water-model.md)
uses the 78 bundled profiles to make the feedback path and tier transition
visible.

This is **one-way coupling**: the supplied flood schedule drives household
decisions, while their actions do not change the hazard. The fixed schedule has
floods in years 3, 4 and 9; this shortest run covers a year without a flood.

The run completes and writes `household_governance_audit.csv` (two rows),
`simulation_log.csv`, `audit_summary.json` and `run_integrity.json` in the output
directory. The mock returns a decision without the required appraisals; retries
exhaust and the executed action is `do_nothing`. It also provides no readable
reflections: `run_integrity.json` records zero stored reflections and
`integrity_ok=false`. The runner prints that warning; completing this wiring
check does not make it a valid reflection-on experiment.

The runner refuses to reuse a populated output directory. When repeating this
chapter, change the output path in the run and in subsequent inspection commands.

Next: [see the rule block and retry](02-rules-and-retries.md).
