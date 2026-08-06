# SUPERSEDED — do not launch against this tree

**Written 2026-08-05.** This config tree is kept as the record of the smoke test that used it. It is
**not** the tree any production run should read.

## Use this instead

```
SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt/
```

That is the tree `SUBMISSION_2026/TAE/runs/launch_firstattempt.md` §2 specifies, and the one the
integrity gate is written against.

## Three reasons, each verified rather than assumed

**1. It is missing `executed_skill_columns`, and the column cannot be added retroactively.**

| tree | `initial_proposal_columns` | `executed_skill_columns` |
|---|---|---|
| this one | ✅ | ❌ **absent** |
| `SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt/` | ✅ | ✅ |

The consequence is visible in this tree's own smoke output: `executed_skill` is absent from
`ICLR2027/experiments/_smoke_firstattempt/irrigation_farmer_governance_audit.csv`.

This project's headline numbers follow an EXECUTED-ONLY rule — the executed action, never the
proposed one. `SUBMISSION_2026/TAE/ops/_lane_prereg_v1_superseded.md:98` prices the
proposed-versus-executed discrepancy this column closes at **up to 35 pp of level**. A run produced
without it cannot answer the executed-stage question at all, and no amount of later analysis
recovers the column.

**2. A run launched against it fails the integrity gate on every seed — after the GPU time is spent.**

`SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:85`

```python
ISOLATED_CONFIG_MARKER = "config_irrigation_firstattempt"  # dirname of the isolated config tree
```

`:391` raises `IntegrityError` when the manifest's recorded config path does not contain that
substring, and the module's no-warnings rule means it fails loudly rather than degrading. This
directory is named `config_firstattempt`, so the substring does not match. Ten and a half GPU-hours
per seed would be spent before the failure surfaces.

**3. Its line endings are LF where the frozen config and its four sibling files are CRLF.**

`config_hash` is a raw-bytes sha256 (`broker/core/experiment_runner.py:542`). With the line endings
differing as well as the flag, the hash moves for two reasons at once and cannot attribute the
change to either. The `SUBMISSION_2026` tree is CRLF and matches the frozen file, so its hash
difference is attributable to the flag alone.

## Why this is kept rather than deleted

It is the input half of a real smoke test whose output is on disk at
`ICLR2027/experiments/_smoke_firstattempt/`. That smoke test is the only end-to-end evidence that
the first-attempt columns are produced at all, and it is also the source of the only fill-rate
measurement available before seed 42 runs (93.33% of all rows, 80.00% of retried rows — both under
the gate's 95% bar; see `SUBMISSION_2026/TAE/analysis/preflight_2026-08-05.md` §7). Deleting the
config would leave that output unexplainable.

Keeping a superseded input next to its output is the record. Launching against it is the error this
file exists to prevent.
