# launch_firstattempt.md — exact commands, first-attempt appraisal logging

Prepared 2026-08-01. This is the ONLY run `PLAN.md` §5 and `EXPERIMENT_OPTIONS.md` §2/§7
authorise: first-attempt appraisal logging, **governed arm only**, `gemma3:4b` anchor cell,
`--real` (78 agents), 42 years, `strict`, seeds 42–46. Zero code changes — one YAML key, already
turned on in `runs/config_irrigation_firstattempt/` (see `DIFF_AGAINST_FROZEN.md` in that
directory for the verified single-line diff against the frozen paper config).

**This document does not launch anything.** It is what a human runs by hand, one line at a time,
after every box in §1 is checked.

---

## 0. What this buys, in one sentence

`DECISION.md` §5/§8/§12 says the corpus "cannot separate honest re-reporting from a residual
gaming component, only bound it." This run measures the bound directly: it records the agent's
attempt-0 appraisal label next to the accepted-generation label on every governed decision, so the
retried-and-approved stratum (≈24.3% of governed decisions) can be checked for within-decision
appraisal revision instead of merely disclaimed.

---

## 1. Pre-flight checklist — every box must be checked before §2 runs

### 1a. Clean tagged tree (`PLAN.md` "Fri 1 Aug" row; `EXPERIMENT_OPTIONS.md` §7 step 0)

```
git status --porcelain
```

**MUST be empty.** It is **not** empty as of 2026-08-01 — verified today:

```
 M .gitignore
 M examples/multi_agent/flood/orchestration/lifecycle_hooks.py
 M examples/multi_agent/flood/paper3/analysis/empirical_benchmarks.py
 M examples/multi_agent/flood/paper3/analysis/validation/metrics/l1_micro.py
 M examples/multi_agent/flood/paper3/configs/calibration.yaml
 M examples/multi_agent/flood/run_unified_experiment.py
?? examples/multi_agent/flood/config/prompts_institutional_v2/
?? examples/multi_agent/flood/config/prompts_institutional_v3/
?? examples/multi_agent/flood/config/prompts_v2/
?? examples/multi_agent/flood/config/prompts_v3/
?? examples/multi_agent/flood/data/POPULATION_v2_GENERATOR.md
?? examples/multi_agent/flood/data/initial_memories_v2.json
?? examples/multi_agent/flood/paper3/prepare_agents_v2.py
?? examples/multi_agent/flood/paper3/tests/test_parametric_decider.py
?? examples/multi_agent/flood/parametric/
?? examples/reservoir_control/results_ops_e4b/
```

None of these paths are under `examples/irrigation_abm/` or `broker/`, so they cannot affect the
irrigation runner. They must still be committed or stashed before tagging — an untracked/dirty
tree at tag time is exactly the "0 of 131 runs have clean provenance" defect (`MATERIALS_VERDICT`
#9/#14, `BACKLOG.md` W8) this run exists partly to avoid repeating. **This is a P0.2 / examples/
edit and is out of this folder's write scope (`BOUNDARY.md` §1) — Wenyu resolves it, not a TAE
session.** Do not run `git add` / `git stash` / `git commit` from this folder to force the box
checked.

Once `git status --porcelain` is empty:

```
git tag tae-firstattempt-2026-08-01
```

(If the go/no-go slips past 1 Aug, use the actual launch date in the tag name, not this one —
the tag records when the tree was frozen, not when this document was written.)

### 1b. Windows Update paused for the run window

2.5 days wall-clock (5 seeds × 10.4 h) plus buffer for the "+15% for incidents" margin
`EXPERIMENT_OPTIONS.md` §2 costs in — pause for **4 days** to be safe.
Settings → Windows Update → Pause updates → pick a date ≥4 days out. (One incident already cost
this project 6h47m on this exact hazard — `EXPERIMENT_OPTIONS.md` §2 risk 4, `ops/environment.md`
hazard 1 — do not skip this because it "probably won't happen again.")

### 1c. GPU confirmed not on CPU fallback

Before starting the queue, and spot-checked once during it:

```
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv
ollama ps
```

Confirmed today (repo-idle baseline): `NVIDIA GeForce RTX 4080 SUPER, 6308 MiB / 16376 MiB, 0%`
— GPU present, not currently pinned. Once a run is underway, `ollama ps` must show the model
loaded with a GPU percentage near 100%; a run showing sustained 100% CPU utilisation and near-zero
GPU utilisation is the documented silent-fallback failure mode
(`EXPERIMENT_OPTIONS.md` §2 risk 4) — kill it and restart rather than letting it finish 12× slow.

### 1d. Disk free

```
df -h
```

Confirmed today: **2.4 TB free of 3.7 TB (34% used)**. Five irrigation runs at the measured
governed cost (~11.6 h / 3,276 decisions, `EXPERIMENT_OPTIONS.md` §1e) are negligible against
that; not a gating concern, checked here only because the pre-flight checklist names it.

### 1e. Config completeness and isolation, already verified

```
diff -rq examples/irrigation_abm/config SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt
```

Must print exactly one line naming `agent_types.yaml`. See
`runs/config_irrigation_firstattempt/DIFF_AGAINST_FROZEN.md` for the full diff and why it is the
only delta. Re-run this diff immediately before the queue starts — if anyone has edited either
tree since this was written, the isolation guarantee needs re-verifying, not assuming.

### 1f. Output-collision guard — MANUAL, because the runner does not refuse

`run_experiment.py:665-666` is `output_dir.mkdir(parents=True, exist_ok=True)` — it does **not**
refuse to write into an existing directory (`ops/environment.md` hazard 4,
`EXPERIMENT_OPTIONS.md` §2 risk 3). Before every command in §2, confirm the target does not exist:

```
ls SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>   # must fail: "No such file or directory"
```

If it exists (a partial/aborted prior attempt), move or delete it first — never let a re-launch
silently interleave with a partial run's files.

---

## 2. The five commands — sequential, one seed at a time

`--workers 1` (sequential; the run is governed-arm-only so there is no separate no-validator
queue to interleave). Run seed 42 to completion, confirm it with
`evidence/e3_run_integrity.py` (§3 below), **then** start seed 43, and so on — do not launch all
five in parallel. `EXPERIMENT_OPTIONS.md` §2 prices this as 5 × 10.4 h = 52 GPU-h / 2.5 d
wall-clock on that basis.

```bash
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed 42 --memory-seed 42 --workers 1 \
  --governance-mode strict \
  --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42
```

```bash
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed 43 --memory-seed 43 --workers 1 \
  --governance-mode strict \
  --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed43
```

```bash
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed 44 --memory-seed 44 --workers 1 \
  --governance-mode strict \
  --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed44
```

```bash
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed 45 --memory-seed 45 --workers 1 \
  --governance-mode strict \
  --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed45
```

```bash
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed 46 --memory-seed 46 --workers 1 \
  --governance-mode strict \
  --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed46
```

Every `--output` is explicit and lives under `SUBMISSION_2026/TAE/runs/`, never the runner's
default `results/` — a governed `gemma3:4b` run without an explicit `--output` writes next to the
frozen `production_v21_42yr_seed<S>` corpus (`ops/environment.md` hazard 4; `BOUNDARY.md` forbids
writing into `examples/` from this folder in any case).

**Flagged, not resolved — read before the 6 Aug go/no-go:**

- **`--num-ctx 8192 --num-predict 4096` is added here and is NOT in the literal command in
  `EXPERIMENT_OPTIONS.md` §7 or the §1b pilot command.** Verified today:
  `broker/utils/performance_tuner.py`'s `MODEL_TIER_PRESETS` auto-tunes a 4B model (gemma3:4b
  falls in the `(5.0, 4096, 2048, 2)` tier) to `num_ctx=4096, num_predict=2048` — **half** of what
  every archival production batch script for this exact cell passes explicitly
  (`examples/irrigation_abm/run_gemma12b_batch.bat`, `run_gemma4_e2b_batch.bat`,
  `run_gemma4_e4b_batch.bat`, `run_ensemble.bat`, `README.md` all use
  `--num-ctx 8192 --num-predict 4096`). Without the override, this run would use a
  different generation budget than the anchor cell it is meant to validate the mechanism for,
  which risks a different retry/parse-failure profile and invalidates the 10.4 h/run costing
  basis (measured ON runs that carried this override). I added the flags to match the archival
  convention rather than silently pick either way — **this is a disagreement with the decision
  document's literal text, not an interpretation of it, and should be confirmed at the go/no-go**
  rather than discovered mid-run.
- **`--memory-seed <S>` (matching `--seed`) is per `EXPERIMENT_OPTIONS.md` §7's queue spec**, but
  it also diverges from the archival batch scripts above, none of which pass `--memory-seed`
  (leaving it at the CLI default of `42` for every seed). Both conventions exist in this repo;
  `EXPERIMENT_OPTIONS.md` §7 is the decision of record for this run and is followed here. Recorded
  so the divergence from the archival convention is a decision, not a surprise.
- `--rebalance-clusters`, `--no-magnitude`, `--pilot-phase`, `--ablation-mode` are all omitted
  (defaults) — none is named by `DECISION.md` §5, `EXPERIMENT_OPTIONS.md` §2/§7, or any archival
  production command for this cell.

---

## 3. Per-run integrity gate — run before a seed counts

```
python SUBMISSION_2026/TAE/evidence/e3_run_integrity.py SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42
```

See `evidence/e3_run_integrity.py` for what it checks and why exit 0 alone is not evidence. Run it
against each seed directory as soon as that seed's process exits, before starting the next one —
catching a silent-death or CPU-fallback run early is cheaper than discovering it on 14 Aug with no
time left to relaunch.

---

## 4. The fences — reproduced here so this document is self-contained

(Decision of record: `PLAN.md` §5, `EXPERIMENT_OPTIONS.md` §2 "Abort rule".)

| fence | date | rule |
|---|---|---|
| Prerequisite | before starting | §1 above, every box checked. Not met → the run does not start. |
| HARD GO/NO-GO | **6 Aug 2026** | If the queue has not started by end of 6 Aug, **abandon the run permanently.** Do not reschedule it into the writing window. |
| Per-run integrity | each run | §3 above; a run failing any assertion is not in the analysis. |
| FREEZE | **14 Aug 2026** | Analysis freezes on whatever seeds have passed integrity by then. n ≥ 3 → report with df = 2. **n < 3 → delete the section entirely.** |
| Invariant | always | `SUBMISSION_2026/TAE/` sections 3–6 derive entirely from the shipped (frozen) corpus. If this queue dies, the paper is unchanged — nothing here may become load-bearing for §§3–6. |

Do not truncate the horizon (`EXPERIMENT_OPTIONS.md` §2 design note) and do not launch more than
the five governed seeds named above without a fresh decision — the both-arms add-on and the
flood add-on are named in `EXPERIMENT_OPTIONS.md` §2 but are **not** authorised by `PLAN.md` §5
("RUN OPTION 1, AND NOTHING ELSE") without the stated 12 Aug conditional-approval trigger.

---

## 5. After all seeds finish (or after the 14 Aug freeze, whichever first)

Analysis goes in a **new** script under `SUBMISSION_2026/TAE/evidence/` that imports `_data.py`
and adds a separate, equally strict discovery function for
`SUBMISSION_2026/TAE/runs/firstattempt_gov_seed*` — `_data.py`'s existing discovery functions are
hard-anchored to `examples/*/results` and will (correctly) refuse a path under
`SUBMISSION_2026/` via `_reject_contaminated()`. Do **not** loosen that guard; add a sibling
function, per `BOUNDARY.md` §3's recommendation for exactly this situation. That script does not
exist yet — it is not part of this preparation pass, since it can only be written once real
column names and row counts are on disk.
