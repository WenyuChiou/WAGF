# Irrigation v3 corpus runbook (spec WP7 Launch)

Code: `examples/irrigation_abm/tools/v3_corpus_launcher.py`. Tests:
`examples/irrigation_abm/tests/test_v3_corpus_launcher.py`.
Sources: `.research/design_specs/irrigation_v3_spec_2026-09-28.md` (WP7
7.1-7.6, section 4 pilot protocol) and
`examples/irrigation_abm/docs/v3_metrics.md` (the gate, P5(c), the
provenance guard). Where this page and either of those disagree, the
spec and `v3_metrics.md` win.

This page is the human-run sequence end to end. The launcher does the
preflight checks, the chaining and the state bookkeeping; every step
below that touches the GPU or edits a Windows scheduled task is still a
step a person runs and confirms, never something this page or the
launcher automates on its own.

## 0. Before you start

- `python examples/irrigation_abm/tools/v3_corpus_launcher.py plan --tag <tag>`
  works on an ordinary development tree (it does not require a clean
  tree or a matching HEAD) and is the fastest way to see the full 32-run
  list, exact command lines and output directories before anything is
  tagged.
- Nobody else is using the GPU for the pilot and corpus phases. Ask
  first; this machine's Ollama instance is shared.
- `examples/irrigation_abm/README.md`'s "Resuming a crashed run" section
  documents `run_experiment.py`'s own `--llm-journal` / `--resume-from`
  contract; this runbook only adds the orchestration on top of it.

## 1. Merge, tag, push, and a fresh run worktree (spec 7.1)

Spec 7.1 exactly: merge WP1, WP1b, WP2 to WP6, **and WP7 itself** (this
launcher and its runbook) into `main`, through a reviewed PR, not a local
`git merge`; tag THAT merge commit; full foreground `pytest tests/
broker/ examples/irrigation_abm/tests` green AT THE TAG (not before it,
and not on a different commit that merely claims to be the same code)
before anything else in this runbook starts. WP7 must be IN the tag: the
commands below are `python examples/irrigation_abm/tools/
v3_corpus_launcher.py ...` from the tagged worktree, which do not exist
in that tree at all if only WP1-WP6 were merged.

```
bash ~/.claude/scripts/pr-merge-safe.sh <pr-number> [-R owner/repo]
git checkout main
git pull
git tag irrigation-v3-YYYY-MM-DD
git push origin irrigation-v3-YYYY-MM-DD
git worktree add C:/Users/wenyu/Desktop/Lehigh/wagf-irrigation-v3-run irrigation-v3-YYYY-MM-DD
```

Use today's date for the tag. Do not reuse an old tag name. Pushing the
tag (not just creating it locally) is part of spec 7.1: a tag that only
exists on this machine is not yet the shared record of what the corpus
ran against. `pr-merge-safe.sh` is the standing merge gate for every PR
in this repo (refuses unless every check is SUCCESS/NEUTRAL/SKIPPED, and
refuses on zero reported checks) -- `git merge --ff-only` skips that gate
entirely and must not be used for the merge that becomes the corpus's own
commit.

Copy `ref/CRSS_DB` into the new worktree BEFORE running `pytest` below
(it is gitignored, about 60 MB, and a fresh worktree never has it; some
tests read real CRSS data):

```powershell
robocopy "C:/Users/wenyu/Desktop/Lehigh/wagf-persona/ref/CRSS_DB" "C:/Users/wenyu/Desktop/Lehigh/wagf-irrigation-v3-run/ref/CRSS_DB" /E
```

Copy, never junction. A junction into the worktree has cost a full
results tree before when the worktree was later removed with
`git worktree remove --force` (the removal followed the junction and
deleted the target's contents); a plain copy cannot do that. If
`ref/CRSS_DB` changes later, rerun the `robocopy` rather than trying to
keep a live link.

Now run the full suite, in the new worktree, with `ref/CRSS_DB` already
in place:

```
cd C:/Users/wenyu/Desktop/Lehigh/wagf-irrigation-v3-run
pytest tests/ broker/ examples/irrigation_abm/tests
```

This must be green before continuing to section 2; if it is not, the
merge is not actually ready and nothing below this point should run. The
launcher's own test suite (`examples/irrigation_abm/tests/
test_v3_corpus_launcher.py`) is included here deliberately, beyond spec
7.1's literal `tests/ broker/`: it is the thing this whole runbook trusts
to launch the corpus correctly, and it belongs in the SAME green-at-the-
tag guarantee as everything else.

From here on, run every launcher command with this new worktree as the
working directory, and pass `--tag irrigation-v3-YYYY-MM-DD` on every
`run` / `resume` / `gate` call. The launcher refuses (`git status
--porcelain` not empty, or HEAD not at the tag) if either is wrong, so a
mistake here is caught immediately rather than discovered mid-run.

Not scripted anywhere in this launcher (deliberately out of scope for
WP7): spec 7.4's section-5 CPU sensitivities (minimum-use floor and
water-right-margin variants, the alternate UB supply envelopes, the
other calibrated warm-start snapshot). Those are SI-only, reported after
the corpus, and have no place in the 32-run plan this launcher builds.

### CPU sensitivities (SI only, outside the 32-run plan)

Each is 10 seeds (42-51), launched directly via `run_fql_baseline.py`
(the launcher's `build_plan` does not expose these flags), same
`--years 42 --paper-water-margin 0.4 --cluster-method hy2021` as every
other v3 FQL run, into its own clearly-named output directory (never
reusing an existing one). Substitute `<sha8>` for the tag's own sha8 and
`<N>` for each seed 42-51.

**(i) FQL warm-start snapshot `All` instead of `All-1109`:**

```
python examples/irrigation_abm/run_fql_baseline.py --real --no-governance --fql-init calibrated \
  --years 42 --seed <N> --paper-water-margin 0.4 --cluster-method hy2021 \
  --fql-init-dir ref/CRSS_DB/CRSS_DB/Initial_Files/All \
  --output examples/irrigation_abm/results/v3_corpus/v3_fql_sensitivity_<sha8>_fqlinitAll_seed<N>
```

**(ii) Minimum-use floor 0 and 0.05 x W** (2026-10-06: `--min-utilisation-fraction`,
`WaterSystemConfig.min_utilisation_fraction`, default 0.10). **FQL-only**:
`run_experiment.py` REFUSES any `--min-utilisation-fraction` other than the
0.10 default (Opus review P2-1, 2026-10-06) -- `config/agent_types.yaml`'s
`minimum_utilisation_floor` rule message hard-codes "10% of your water
right" and is deliberately not templated, so an LLM agent blocked under a
different floor would be told the wrong number. Only `run_fql_baseline.py`
(no LLM, no retry message) can run this sensitivity until that message is
templated:

```
python examples/irrigation_abm/run_fql_baseline.py --real --no-governance --fql-init calibrated \
  --years 42 --seed <N> --paper-water-margin 0.4 --cluster-method hy2021 \
  --min-utilisation-fraction 0.0 \
  --output examples/irrigation_abm/results/v3_corpus/v3_fql_sensitivity_<sha8>_floor000_seed<N>

python examples/irrigation_abm/run_fql_baseline.py --real --no-governance --fql-init calibrated \
  --years 42 --seed <N> --paper-water-margin 0.4 --cluster-method hy2021 \
  --min-utilisation-fraction 0.05 \
  --output examples/irrigation_abm/results/v3_corpus/v3_fql_sensitivity_<sha8>_floor005_seed<N>
```

**(iii) `--lb-return-flow-fraction 0.2`** (2026-10-06: run as a PAIR, never
alone -- the default `lb_non_ag_total_maf` (5.2) was itself the
record-implied value at `lb_return_flow_fraction = 0.0`
(`analysis/hindcast_v3.py (record_implied_non_ag)`); pairing a non-zero
fraction with the `f = 0.0` constant double-counts water the fraction
already credits back to Mead. First re-derive the record-implied
non-farm constant for `f = 0.2` from the hindcast, then pass BOTH flags
to the FQL run:

```
python examples/irrigation_abm/analysis/hindcast_v3.py --lb-return-flow-fraction 0.2 \
  --out examples/irrigation_abm/results/v3_corpus/hindcast_lbflow020

# Read the "derived on 2003-2010" / "derived on 2011-2018" rows'
# lb_non_ag_total_maf from hindcast_lbflow020/hindcast_v3_summary.csv and
# average them (the same procedure that derived the f=0.0 default, 5.2
# MAF, from 5.167/5.214 -- see WaterSystemConfig.lb_non_ag_total_maf's
# own comment), e.g. <derived_5p2_equivalent>.

python examples/irrigation_abm/run_fql_baseline.py --real --no-governance --fql-init calibrated \
  --years 42 --seed <N> --paper-water-margin 0.4 --cluster-method hy2021 \
  --lb-return-flow-fraction 0.2 --lb-non-ag-total-maf <derived_5p2_equivalent> \
  --output examples/irrigation_abm/results/v3_corpus/v3_fql_sensitivity_<sha8>_lbflow020_seed<N>
```

Also note (2026-10-06 CPU rerun): `v3_metrics.py gate_p1`'s mass-balance
check now adds back `lb_phys_ratio * lb_return_flow_maf` (the amount this
fraction actually credits against Mead's outflow this year, logged
unscaled by phi) when scoring a non-default `lb_return_flow_fraction`
run -- without that correction P1 fails at face value (residual up to
0.77 MAF/yr) even though mass balance holds.

**(iv) `--powell-post2026-equalization hold_2026`** (2026-10-06:
`--powell-post2026-equalization {extend_slope,hold_2026}` on
`run_fql_baseline.py`; default `extend_slope`):

```
python examples/irrigation_abm/run_fql_baseline.py --real --no-governance --fql-init calibrated \
  --years 42 --seed <N> --paper-water-margin 0.4 --cluster-method hy2021 \
  --powell-post2026-equalization hold_2026 \
  --output examples/irrigation_abm/results/v3_corpus/v3_fql_sensitivity_<sha8>_hold2026_seed<N>
```

Every sensitivity's acceptance check is the same `v3_metrics.load_run` +
`gate_p1` / `gate_p2` / `gate_p4` WP5 check section 2 below describes,
run directly against the sensitivity's own 10 output directories (never
reusing the reference's).

## 2. FQL reference and the WP1b replays (CPU, no GPU, no Ollama)

```
python examples/irrigation_abm/tools/v3_corpus_launcher.py run fql --tag irrigation-v3-YYYY-MM-DD
python examples/irrigation_abm/tools/v3_corpus_launcher.py run replays --tag irrigation-v3-YYYY-MM-DD
```

Each launches its own chain of CPU-only commands (10 FQL seeds; one
`v3_metrics.py replay` call that writes both replay A and replay B)
inside one detached process, and returns immediately with a PID and a
log path. Poll with:

```
python examples/irrigation_abm/tools/v3_corpus_launcher.py plan --tag irrigation-v3-YYYY-MM-DD
```

and watch the `[fql]` / `[replays]` rows move from `pending` through
`running` (a live process still holds that run's PID) to `done` (or
`crashed`, if it died without a clean manifest), or read the log file
the `run` command printed. Neither phase needs `--confirm-gpu` or
`--workers`; neither touches Ollama.

Before moving on, confirm the FQL reference passes its own WP5
acceptance (spec section 5 / WP5): 10 seeds (42-51), 32,760 agent-years
total, zero requests above the water right, mass balance closed every
year, natural flow equal to the hydrology table, and the 2019 UB request
total within [2.6, 3.6] MAF. The pilot protocol (spec section 4) starts
"after the FQL reference passes the WP5 acceptance" -- this is a manual
check against the 10 FQL output directories' own `simulation_log.csv` and
manifests. `v3_metrics.py metrics` is not a substitute: it requires
`--runs` (LLM run directories) and refuses a call with only FQL seeds and
no LLM run, so it cannot run at all at this point in the sequence
(the pilot pair, its only possible `--runs` input, has not been launched
yet). Nothing here is something `gate` checks for you before the pilot.

## 3. Throughput check before the pilot (workers 1 vs 4)

Before picking a `--workers` value for the pilot and corpus phases, run
a short, cheap check of your own (the launcher does not script this one,
since it is a one-off calibration, not part of the corpus):

```
python examples/irrigation_abm/run_experiment.py --real --model gemma3:4b --years 2 --governance-mode strict --workers 1 --output <scratch>/throughput_w1
python examples/irrigation_abm/run_experiment.py --real --model gemma3:4b --years 2 --governance-mode strict --workers 4 --output <scratch>/throughput_w4
```

Compare wall-clock time. Before the `--workers 4` run, raise the Ollama
server's own concurrency limit to at least the worker count:

```
setx OLLAMA_NUM_PARALLEL 4
```

(then restart the Ollama server for it to take effect). **Ask the other
person using this machine's Ollama instance before changing
`OLLAMA_NUM_PARALLEL`**: it is a server-wide setting, not scoped to this
run, and raising it changes how their own requests get served too.
Without it, concurrent requests queue server-side and `--workers 4`
buys nothing (`examples/irrigation_abm/README.md`, "Not guaranteed").
Delete the two throughput-check output directories afterward; they are
not part of the corpus.

Whatever `--workers N` you settle on here is the value every later
`run pilot` / `run resume` / `run corpus` call must use: the launcher's
state file records the first one and refuses a different value after
that (see section 5).

## 4. Pilot (GPU, 2 runs)

```
python examples/irrigation_abm/tools/v3_corpus_launcher.py run pilot --tag irrigation-v3-YYYY-MM-DD --workers <N> --confirm-gpu
```

This is the first GPU launch in the campaign: it records `<N>` in the
launcher's state file (default `C:/Users/wenyu/.wagf_launcher/state.json`,
override with `--state-dir`). It launches strict-seed-42 and
disabled-seed-42, in that order, inside one detached process, each with
`--llm-journal --workers <N>`. Check progress the same way as section 2
(`plan`, or the log file).

If a pilot run crashes partway (Ollama restart, a transient Windows
task, anything in the memory notes on long-running batches), see
section 8 before touching anything.

## 5. P5(c) human review

Once both pilot runs show `done`:

```
python examples/irrigation_abm/tools/v3_corpus_launcher.py gate --tag irrigation-v3-YYYY-MM-DD
```

`gate` always runs `p5c-sample` first, which writes
`v3_pilot_p5c_<sha8>/p5c_review_template.json` and the sampled prompt
texts under `v3_pilot_p5c_<sha8>/p5c_prompts/` inside the results root.
The first time you run `gate`, the review file does not exist yet, so
the launcher prints where the template is and what to do, then still
runs `pilot-gate` (which will not pass P5(c) without it).

A reviewer who did not write this code reads the sampled prompts, fills
in `reviewer`, `reviewer_wrote_code` (must be `false`) and, per sampled
prompt, `sentences_without_source`, and saves the filled copy as
`v3_pilot_p5c_<sha8>/p5c_review.json` (or anywhere else, passed via
`--p5c-review <path>`). Rerun `gate` once that file exists.

## 6. The gate

Rerun `gate` (same command as section 5) after the P5(c) review file
exists. It requires the FQL and replay phases to already show `done`
(spec 7.4 orders them before the pilot, so by this point they should
be) and refuses with a clear message naming whichever is not. It writes
`v3_pilot_gate_<sha8>/v3_pilot_gate_report.json` and
`v3_pilot_gate_report.md`, prints PASS or FAIL with the per-check
detail `pilot-gate` itself prints, and records the pass/fail and the
exit code in the launcher's state file, keyed to this commit's sha8.

If it fails: per spec section 4, there is no automatic retry, and a
failed gate restarts from **section 1**, not section 4. Fix the problem
in the code, merge the fix, tag a NEW `irrigation-v3-YYYY-MM-DD` (append
a suffix if you tag twice in one day), create a NEW fresh worktree at
that tag, and redo the FQL reference and replays (section 2) before the
pilot pair runs again -- the old FQL/replay outputs were produced
against the OLD commit and are not valid provenance for the new one
(`v3_metrics.py`'s provenance guard checks `git_commit` / `git_head`
across every run it pools). `run corpus` refuses unless a PASSED result
is on record for the exact commit it resolves, so skipping straight to a
new pilot pair without redoing section 2 would simply fail later, at
`gate` or `run corpus`, instead of being caught here.

## 7. The 19 post-gate runs (GPU)

Only after a PASSED gate:

```
python examples/irrigation_abm/tools/v3_corpus_launcher.py run corpus --tag irrigation-v3-YYYY-MM-DD --workers <N> --confirm-gpu
```

`<N>` must be the same value used for the pilot; the launcher refuses a
different one. This launches, in order, strict and disabled seeds
43-46, placebo and silent seeds 42-46, and the feasibility-only seed-42
run (spec item 16), 19 runs chained in one detached process. Spec 7.6's
budget estimate (about 63 plus-or-minus 16 GPU hours for the 21 LLM
runs, pilot included) is re-estimated from the pilot pair's own measured
time before this phase starts; if the pilot took much longer or shorter
than expected, revisit the estimate before leaving this phase running
unattended overnight.

## 8. Resuming a crashed run

Find the crashed label from `plan` (status `crashed`: a journal or
partial output exists but there is no clean, non-aborted manifest).
Then:

```
python examples/irrigation_abm/tools/v3_corpus_launcher.py resume <label> --tag irrigation-v3-YYYY-MM-DD --workers <N> --confirm-gpu
```

This relaunches from the crashed run's own `llm_journal.jsonl` via
`--resume-from`, into a NEW directory (`<original>_resume1`, or the next
free suffix in its resume chain if it has already been resumed once
before); the crashed directory itself is never written to or deleted.
`--workers` here may be a different number from the original crash
(`run_experiment.py` allows that for a single resume), but it still must
match whatever the launcher's state file AND the pilot pair's own
recorded manifests already show for this campaign, same as any other GPU
launch (section 4): the corpus is pooled for analysis as one `--workers`
value, and `v3_metrics.py`'s own provenance guard would otherwise refuse
the pool later, at analysis time instead of now.

`resume` refuses a run whose status is `running`, not `crashed` -- the
launcher's own record of that run's PID shows a process still alive, and
resuming it would start a SECOND process against the same output
directory. If `plan` shows a run stuck at `running` long after you
expect it to have finished, check the log file first; only kill it if you
are sure it is actually stuck:

```
taskkill /F /PID <pid>
```

Always `/F` (force), never `/T` (which would also signal the console
this process shares -- it has none, being launched detached, but `/T`
additionally tries to terminate a tree of child processes, which is
broader than intended here). Use the PID `plan` prints next to a
`running` or `crashed` entry, the log file, or the launcher's state file
(`state.json`'s own `launches` list, or `.wagf_launcher/runs/<label>.json`
for the per-run record) -- never guess a PID from `tasklist` output by
process name alone, since a shared machine may have more than one
`python.exe`.

A crashed FQL or replay entry (CPU phases) is NOT resumed: `resume` is
LLM-only (`run_experiment.py`'s `--resume-from` / `llm_journal.jsonl`
contract does not exist for `run_fql_baseline.py` or `v3_metrics.py
replay`). Move the crashed directory aside (do not delete it, in case it
is useful for diagnosis) and run the phase again:

```
move "<results-root>\v3_fql_reference_<sha8>_seed45" "<results-root>\v3_fql_reference_<sha8>_seed45_FAILED_<date>"
python examples/irrigation_abm/tools/v3_corpus_launcher.py run fql --tag irrigation-v3-YYYY-MM-DD
```

With the crashed directory moved out of the way, that seed's own output
directory no longer exists, so `run fql` sees it as `pending` again (item
2: an attempt directory is never silently reused) and relaunches exactly
that one seed, alongside any other still-pending seeds.

**Finishing a phase after one run in it crashed.** `run corpus` launches
ONE chain covering every still-pending corpus run; if entry 7 of 19
crashes, the chain stops there (no automatic retry) and entries 8-19
never start. `resume <label>` relaunches only the ONE crashed entry, in
its OWN separate chain -- it does not also pick up the rest of the
original queue. The sequence to actually finish the phase is:

1. `resume <label>` for the crashed entry; wait for it to finish (`plan`
   shows it `done`, or `crashed` again if it fails a second time).
2. `run corpus` (the SAME phase) again. The launcher refuses this while
   EITHER chain (the original or the resume) is still alive (item 1), so
   step 2 cannot be run concurrently with step 1 by mistake; once both
   have exited, `run corpus` launches a NEW chain covering whatever is
   still `pending` (entries 8-19, skipping the now-`done` resumed entry
   and the crashed original, which `resume` already handled).

## 9. Backup

After each phase finishes (fql, replays, pilot, corpus, and especially
right after the gate passes), run the existing nightly backup script by
hand rather than waiting for its 04:30 schedule:

```
powershell -NoProfile -ExecutionPolicy Bypass -File "C:/Users/wenyu/Desktop/Lehigh/backup_wagf_to_gdrive.ps1"
```

It is a copy-only `robocopy /E` into `G:\我的雲端硬碟\WAGF_backup`
(never deletes), already paired to
`governed_broker_framework/examples/irrigation_abm/results`, which is
exactly the default results root this launcher writes into (see the
launcher's module docstring for why that default was chosen). Safe to
run at any time, takes seconds for an incremental copy.

## 10. Protecting an overnight GPU run (user steps, not automated)

Before leaving the pilot or corpus phase running unattended overnight,
the operator (not the launcher) should, in an elevated PowerShell:

1. List scheduled tasks due in the next 48 hours and disable the
   disk/update ones that have previously interrupted long LLM runs
   (Data Integrity Scan, OneDrive per-machine update task, Windows
   Update install-service scans):

   ```powershell
   Get-ScheduledTask | Get-ScheduledTaskInfo |
       Where-Object { $_.NextRunTime -and $_.NextRunTime -lt (Get-Date).AddHours(48) } |
       Sort-Object NextRunTime
   ```

   then `Disable-ScheduledTask` the disk/update ones due in that window;
   see the memory note on system-task protection for the exact task
   names this has bitten before and the elevated-PowerShell pattern
   (`audit_settings.py` is a DIFFERENT tool, for `.claude/settings.local.json`
   hygiene, not for listing Windows scheduled tasks).
2. Pause Windows Update for the expected duration of the run (a registry
   write under `HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings`,
   also in that memory note).
3. Save the pre-change task states and a restore script before disabling
   anything, so the tasks can be put back afterward.
4. Do not run a CPU-heavy verification (e.g. a full `pytest` pass) at
   the same time as a GPU phase; sequence them.

This is an operator checklist, not a launcher subcommand: it changes
Windows-level, machine-wide state (scheduled tasks, Windows Update) that
should never be flipped by an unattended script without the operator
reading what it is about to disable.

## 11. When the corpus is done

- Confirm every row in `plan` shows `done`.
- Run the backup (section 9) one more time.
- Remove the run worktree (`git worktree remove`) once its results are
  backed up; since `ref/CRSS_DB` was copied, not junctioned, into it,
  there is nothing to unlink first.
- `git worktree prune` from the main clone.
