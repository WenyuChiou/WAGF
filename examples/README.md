# Two water cases, two coupling directions

**Language: [English](README.md) | [中文](README_zh.md)**

Run these built-in mock cases from the repository root with Python 3.10 or later,
after the [installation step](../README.md#quickstart). They require no model
service. Use fresh output directories. Times below include startup and imports
on one Windows/Python 3.14 machine; they describe only these small checks.

## Flood adaptation: one-way coupling

The flood hazard drives households' adaptation decisions; their decisions do not
change the hazard. This case shows proposal checking, retry feedback, a configured
default after exhausted retries, and a household audit.

```bash
python examples/single_agent/run_flood.py --model mock --years 1 --agents 2 --workers 1 --seed 42 --governance-mode strict --output .tmp/readme-flood
```

Measured runtime: **about 5 seconds on one Windows machine**. Outputs in `.tmp/readme-flood/` include
`household_governance_audit.csv` (two decisions), `simulation_log.csv`,
`audit_summary.json`, `governance_summary.json` and `run_integrity.json`.
The mock proposes `buy_insurance` without required appraisals, exhausts retries,
and executes `do_nothing`. It stores no reflections: the integrity warning is
expected for this mock and the run is not comparable to reflection-on studies.

For configuration and real local-model runs, read the
[flood README](single_agent/README.md).

## Colorado River irrigation: two-way coupling

Users' requests affect deliveries and Lake Mead storage. The resulting level
and shortage tier affect allocations and enter the following year's prompt.
This case shows the coupling adapter, annual water state and per-user audits.

```bash
python examples/irrigation_abm/run_experiment.py --model mock --years 2 --agents 2 --workers 1 --seed 42 --governance-mode strict --coupling --output .tmp/readme-irrigation
```

Measured runtime: **about 5 seconds on one Windows machine**. Outputs in `.tmp/readme-irrigation/` include
`irrigation_farmer_governance_audit.csv` (four decisions), `simulation_log.csv`,
`audit_summary.json`, `run_integrity.json` and a persistent
`agent_types.coupling.yaml` derived configuration. End-of-year Lake Mead storage
changes from 14.349 to 15.776 million acre-feet; the year-2 starting level is
1100.739 ft, up from 1081.460 ft in year 1. The shortage tier stays at 0.

The mock omits appraisals, exhausts retries and executes the configured
`maintain_demand` default. It also stores no reflections, and the integrity
record flags that limitation. [Tutorial chapter 4](../docs/tutorial/04-water-model.md)
uses the existing 78-user profiles to show a tier transition and the tier cut it causes,
still using the mock model.

For water-system assumptions, configuration and real local-model runs, read the
[irrigation README](irrigation_abm/README.md).

## Other folders in `examples/`

The two cases above are the main ones. `governed_flood/` supplies the flood
domain pack that `single_agent/` uses; the other folders are demos, worked
examples or test fixtures.

| Folder | What it is |
|---|---|
| `governed_flood/` | Shared flood domain pack plus a small runner. Imported by `single_agent/`, `multi_agent/` and core tests; do not delete. |
| `multi_agent/flood/` | Separate multi-agent flood study; not one of the two main cases. |
| `reservoir_control/` | Worked example of connecting a new water model through `broker/coupling/`; run with the mock model. |
| `reservoir_control_multidim/` | Same, with three setpoints in one decision; run with the mock model. |
| `coupling_examples/` | Worked example of a coupling archetype. |
| `cat_model/` | Coupling-layer demo (catastrophe insurance); used by core tests. |
| `vaccination_demo/` | Non-water demo domain. |
| `quickstart/` | Numbered tutorial scripts. |
| `_test_fixtures/` | Fixture domain for tests; not runnable on its own. |

Which parts of the repo are generic and which are examples:
[`docs/REPO_MAP.md`](../docs/REPO_MAP.md).

Continue with the [six-part tutorial](../docs/tutorial/README.md).
