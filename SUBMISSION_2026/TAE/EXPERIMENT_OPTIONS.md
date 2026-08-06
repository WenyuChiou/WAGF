# EXPERIMENT OPTIONS — TAE submission, costed 2026-07-31

> **Entry point is [HANDOVER.md](HANDOVER.md).** This file is a working record and its status
> claims go stale. Anything about whether something passes, is complete or is ready is measured
> by `evidence/corpus_inventory.py`, `evidence/run_all.py` and `paper/submission_gate.py` --
> prefer those three to any sentence here.

> **Mostly superseded. `RUN_DECISION.md` is the decision of record for what runs.** That file
> explicitly supersedes this one's §0 verdict table, §2 queue design, §6 rejected-candidates list
> and §7 queue spec. **Two things here are still live and are in no other file:** §1a (the code at
> HEAD *does* persist attempt-0 labels) and §1e (measured wall-clocks — 10.4 h governed, 8.2 h
> no-validator, read off trace timestamps — the only measured GPU cost basis in the project).
> The day counts below are counted from 31 July and no longer hold.

29 days to the 29 Aug AoE deadline. `DECISION.md` §11 budgets ~9.5 writing days, so **slack ≈ 19.5
days**. GPU is free. Backend is non-deterministic at fixed seed, so every option below is priced in
N-seed aggregates, never single runs.

The materials audit was right that **no re-run is NEEDED**. This memo asks the different question:
would a run materially strengthen the paper inside 19.5 days. For one option the answer is yes.

---

## 0. Verdict first

| rank | option | run it? | GPU-h | wall-clock | code changes |
|---|---|---|---:|---|---|
| **1** | **First-attempt appraisal logging, governed anchor cell, 5 seeds** | **YES** | **52** | **2.2 d** | **none — one YAML key** |
| 2 | Same, both arms (adds the no-validator comparison) | optional add-on | +41 | +1.7 d | none |
| 3 | World-conditioned vs appraisal-conditioned rule ablation | NO — it cannot isolate what it appears to | 104 | 4.3 d | none (YAML profile, verified) |
| 4 | Feedback-off / reservoir-pinned arm | NO | 52 | 2.2 d + 1.5–3 d coding | edits frozen `examples/` — boundary violation |
| 5 | More seeds on unbalanced cells | NO — actively harmful | 14–78 | 0.6–3.3 d | none |

**Single recommendation: run option 1 and nothing else.** It is the only candidate that attacks the
paper's self-declared weakest point (`DECISION.md` §5, §8, §12), it needs zero code changes, it costs
9% of the remaining slack, and its statistic is **within-run** so it never has to reproduce a
published number to be valid. Everything else either duplicates evidence the paper already has, buys
statistical power the paper does not need, or introduces the exact defect class the audit registered.

**The zero-GPU design stays intact either way.** Option 1 is an *appendix* result on a separately
named, provenance-clean corpus. Sections 3–6 remain derived entirely from the shipped corpus. If the
queue dies, the paper is unchanged. That property is a hard requirement below, not a hope.

---

## 1. What I verified before costing anything

Everything in this section was executed, not read off a document.

### 1a. The code DOES persist the first-attempt appraisal labels — not just the skill

`DECISION.md` §5 says the unselected first-attempt appraisal is unrecoverable. That is **correct about
the shipped corpus and wrong about the current code.** The instrumentation added in commit `0c6aa60e`
captures labels, not only skills:

- `broker/core/skill_broker_engine.py:364-366` snapshots, before the advisory pass and before the
  retry loop reassigns `skill_proposal`:
  ```python
  initial_skill  = skill_proposal.skill_name if skill_proposal else None
  initial_labels = _extract_construct_labels(skill_proposal)
  attempt_skills = [initial_skill]
  ```
- `broker/core/_audit_helpers.py:109-131` — `_extract_construct_labels` pipe-joins **every
  `*_LABEL` key** of the attempt-0 reasoning dict. Verified directly:
  `_extract_construct_labels({'WSA_LABEL':'VH','WSA_REASON':...,'ACA_LABEL':'H',...})`
  → `'WSA_LABEL=VH|ACA_LABEL=H'`.
- `broker/core/_audit_helpers.py:272-287` emits `initial_skill` / `initial_labels` / `attempt_skills`
  only when `global_config.audit.initial_proposal_columns` is true;
  `broker/components/analytics/audit.py:253-256` surfaces them into the CSV.
- Gate: `broker/utils/agent_config.py:307-341`, default OFF, key-gated so flag-OFF runs stay
  byte-identical.

Note the asymmetry that matters: `attempt_skills` records **skills for every attempt** but
`initial_labels` records **labels for attempt 0 only**. Intermediate retry attempts' labels are still
not persisted. Attempt-0 labels versus the accepted labels is exactly the contrast §5 needs, so this
is sufficient — but do not promise a per-attempt appraisal trajectory.

### 1b. End-to-end proof on a real LLM, not a mock

Mock runs are useless here: the mock adapter emits no constructs, so `initial_labels` comes out empty
and `construct_WSA_LABEL` is not even a column. I ran the real model.

Isolated config copy under the scratchpad + `global_config.audit.initial_proposal_columns: true`, then

```
python examples/irrigation_abm/run_experiment.py --model gemma3:4b --years 2 --agents 4 \
  --seed 42 --workers 1 --config-dir <ISO> --output <SCRATCH> --governance-mode strict
```

Result (8 decisions, columns as written to `irrigation_farmer_governance_audit.csv`):

| agent | yr | retry_count | status | initial_labels | construct_WSA_LABEL | final_skill |
|---|---:|---:|---|---|---|---|
| Agent_000 | 1 | **2** | APPROVED | **WSA_LABEL=VH\|ACA_LABEL=H** | **M** | increase_large |
| Agent_001 | 1 | 0 | APPROVED | WSA_LABEL=M\|ACA_LABEL=M | M | increase_small |
| Agent_002 | 1 | 0 | APPROVED | WSA_LABEL=L\|ACA_LABEL=L | L | maintain_demand |
| Agent_003 | 1 | 0 | APPROVED | WSA_LABEL=M\|ACA_LABEL=H | M | increase_large |
| … (4 more, all retry_count = 0, initial == accepted) | | | | | | |

Two things are established. On `retry_count == 0` rows the attempt-0 labels equal the accepted
labels, which is the correctness check the column has to pass. And on the one retried-and-approved
row, the agent reported **VH** on attempt 0, was blocked by `high_threat_high_cope_no_increase`
(WSA ∈ {H,VH} **AND** ACA ∈ {H,VH} → block increase), and the accepted generation reported **M**
while keeping `increase_large`. **The unselected appraisal and the accepted appraisal differ, and the
column records both.**

A second, larger pilot (12 agents × 6 years, 72 decisions) produced only 2 retried rows — synthetic
agents under a mild drought draw rarely trigger the rules — but **2 of 2 flipped from HIGH to
non-HIGH** across retries.

**Read these as instrument validation, not as effect size.** n = 1 and n = 2 on short synthetic runs.
They prove the quantity is recorded and is not identically zero. They prove nothing about magnitude.

### 1c. The selection stratum, measured on all 5 anchor seeds

From `examples/irrigation_abm/results/{production,ungoverned}_v21_42yr_seed4{2..6}`
(`irrigation_farmer_governance_audit.csv`, n = 3,276 each):

| arm | retried | budget-exhausted | rejected | **retried AND approved** |
|---|---|---|---|---|
| with-validators | 60.8–70.3 % | 40.9–52.7 % | 36.4–47.6 % | **22.7–26.2 % (mean 24.3 %)** |
| no-validator | 31.1–39.1 % | 27.5–34.5 % | 25.8–32.7 % | **5.3–7.4 % (mean 6.3 %)** |

This confirms `DECISION.md` §5's "roughly 23%" (seed 42 gives 763/3,276 = 23.3%) and adds a fact the
brief does not have: **the acceptance-selected stratum is about four times larger in the governed arm
than in the comparison arm.** The selection is not merely present, it is asymmetric across the two
things being differenced. That makes the hole worth closing rather than merely disclosing.

### 1d. A `world_only` governance profile is pure YAML — no code changes

Verified by running it. `--governance-mode <name>` resolves any profile in the config's `governance`
block (`run_experiment.py:779`, P0-1d), and `--config-dir` isolates the tree. I added

```yaml
world_only:
  thinking_rules: []            # drops low_threat_no_increase + high_threat_high_cope_no_increase
  identity_rules: [ water_right_cap, minimum_utilisation_floor ]   # world preconditions kept
```

to an isolated copy, ran it, and the run completed with
`config_snapshot.yaml: governance_profile: world_only`.

But note **which rules that profile can and cannot touch.** The two appraisal-conditioned rules live
in `agent_types.yaml` and are removable by profile. The four world-conditioned ones —
`demand_ceiling_stabilizer`, `curtailment_awareness`, `supply_gap_block_increase`,
`demand_floor_stabilizer` — live in `examples/irrigation_abm/validators/irrigation_validators.py` and
are wired unconditionally at `run_experiment.py:684`
(`.with_custom_validators([irrigation_governance_validator])`). Only `demand_ceiling_stabilizer` has
an ablation switch (`--ablation-mode no_demand_ceiling`). So the *world-only* arm is free; the
*appraisal-only* arm would need code. I also confirmed those four Python validators contain no
reference to `WSA_LABEL` / `ACA_LABEL` / the reasoning dict, which independently supports
`DECISION.md` §7's classification of them as world-conditioned.

### 1e. The cost model in `ops/environment.md` understates irrigation by ~2.5×

`environment.md` quotes `gemma3:4b` at **1.1 h per 1,000 decisions**. Measured from the first and last
`timestamp` in each run's `raw/*_traces.jsonl`:

| run | decisions | wall-clock | h per 1,000 |
|---|---:|---:|---:|
| flood `JOH_FINAL/gemma3_4b/Group_C/Run_2` | 879 | 1.08 h | 1.23 |
| flood `JOH_ABLATION_DISABLED/gemma3_4b/.../Run_2` | 909 | 1.06 h | 1.17 |
| flood `JOH_FINAL_v2/gemma4_e4b/Group_C/Run_1` | 988 | 1.80 h | 1.82 |
| **irrigation `production_v21_42yr_seed42` (gov)** | 3,276 | **11.61 h** | **3.54** |
| **irrigation `production_v21_42yr_seed45` (gov)** | 3,276 | **9.10 h** | **2.78** |
| **irrigation `ungoverned_v21_42yr_seed42`** | 3,276 | **9.56 h** | **2.92** |
| **irrigation `ungoverned_v21_42yr_seed45`** | 3,276 | **6.86 h** | **2.09** |

`environment.md`'s table reproduces on **flood** and is wrong for **irrigation** by 2.1–3.2×. A live
pilot today independently measured 10.2 s/decision = 2.84 h/1,000 for a governed irrigation run,
inside the archival governed range. Irrigation costs more per decision because of the growing memory
window, the per-year reflection pass, and the retry loop.

Every GPU-hour below uses the **measured** irrigation numbers, not `environment.md`:
**governed 10.4 h/run, no-validator 8.2 h/run** (midpoints), ×1.73 for `gemma3:12b` /
`ministral-3:8b` (`environment.md`'s own 1.9 ÷ 1.1 model ratio; not independently measured here).
`environment.md` is outside this folder's write boundary, so this correction is recorded here rather
than applied there.

---

## 2. Option 1 — first-attempt appraisal logging

### What it buys

`DECISION.md` names this the paper's weakest point in two places (§5, §8) and the residual it cannot
close in §12: "the corpus cannot separate honest re-reporting from a residual gaming component, only
bound it." This run **produces the bound as a measurement instead of an argument.**

Concretely, the paper gains, on a provenance-clean corpus:

1. **The unselected reference distribution.** Attempt-0 HIGH-appraisal prevalence for every governed
   decision, next to the accepted-generation prevalence on the same rows. §5 currently has to say the
   number does not exist.
2. **A direct measurement of within-decision appraisal revision** on the retried-and-approved
   stratum (24.3% of governed decisions). If it is near zero, §5's honest-re-reporting mechanism gets
   its strongest single piece of evidence and §12's residual is closed, not bounded. If it is large,
   the paper reports a second, smaller channel operating on a quarter of decisions, which §5 currently
   has no way to see at all.
3. **A pre-empted reviewer objection.** "Your conditioning variable is measured after the rule
   selected for it" is the first thing a measurement-validity reviewer at a venue called *Can We Trust
   AI Evaluation?* will write. Answering with a number is worth more than answering with a paragraph.

It does **not** buy: a per-attempt appraisal trajectory (only attempt 0 is stored), or anything about
the shipped corpus, which remains unaffected.

### Does the paper NEED it?

No. §5's argument already survives without it, because the never-retried stratum shows a *larger*
shift and the year-1 null holds under maximum retry pressure. The paper can ship as a zero-GPU result
and be honest. This is a **benefit**, and a large one, on the specific point the paper is most
exposed on.

### Design — the minimum that supports the claim

The statistic must be **within-run and within-decision** so the new corpus never has to reproduce a
published number. That is the design's whole point: a new run is at HEAD, and every published run is
at one of 18 unknown, dirty code states, so any cross-corpus comparison inherits defect #9 and is
unarguable. A within-run paired contrast inherits nothing.

- **Arm:** governed only. `--real` (78 agents), 42 years, `gemma3:4b` (the anchor cell), `strict`.
- **Config:** an isolated complete copy of `examples/irrigation_abm/config/` with one added key:
  ```yaml
  global_config:
    audit:
      initial_proposal_columns: true
      executed_skill_columns: true    # free, and closes the proposed-vs-executed reading
  ```
- **Seeds:** 42, 43, 44, 45, 46. **Minimum defensible = 3** (df = 2, matching the paper's own
  `paired_t` on the 3-seed cells); **recommended = 5** (df = 4, the published convention).
- **Statistic:** per seed, on ~800 retried-and-approved rows, HIGH-share under attempt-0 labels minus
  HIGH-share under accepted labels; then `paired_t` over the 5 per-seed deltas, using the existing
  `TAE/evidence/_data.py` machinery. Also report the whole-run counterfactual: the governed cell's
  HIGH prevalence and conditional rate recomputed with attempt-0 labels for all 3,276 rows, against
  the same run's accepted-label version.
- Do **not** truncate the horizon. Slack is ample and a shorter run describes a different world
  trajectory.

### Cost

| variant | runs | GPU-h (measured basis) | wall-clock, +15% for incidents |
|---|---:|---:|---|
| governed, 3 seeds (**minimum**) | 3 | 31 | **1.5 d** |
| **governed, 5 seeds (recommended)** | 5 | **52** | **2.5 d** |
| both arms, 5 seeds (option 2 add-on) | 10 | 93 | 4.5 d |
| optional: governed flood, 5 runs, same flag | 5 | 6 | 0.3 d |

Code changes: **none.** One YAML key in an isolated config, plus `--output` to a new directory.

The both-arms variant is worth naming separately because the no-validator arm has its own selection
stratum (5.3–7.4%), and reporting the bound for only one arm invites "you measured selection where it
was largest." It costs +1.7 days and I would take it if the first five seeds land clean by 12 Aug.

The flood add-on is nearly free and demonstrates the instrument is not irrigation-specific. Flood's
governed retry rate is 4.5–5.8%, so expect a near-null; that is a fine thing to report.

### Risks

1. **The result may complicate §5, and this is the real risk.** Both pilots hinted at HIGH → non-HIGH
   drift across retries on exactly the rule that reads the appraisal. If that generalises at scale,
   the paper must write: the cross-arm shift is world-driven (year-1 null, never-retried larger,
   reservoir tracking — none of which this run touches), *and* there is a separate within-decision
   revision channel on the retried quarter. Those are different quantities and the second does not
   falsify the first. But §5, §8 and probably the abstract need a careful paragraph. **Budget one
   extra writing day.** Do not start this run unless that day is affordable — it is, at 19.5 days of
   slack, but it must be a decision rather than a surprise.
2. **Provenance.** `environment.md` requires a clean tagged tree. HEAD is `10e190cf` with **no tag**,
   and the tree is dirty in 6 files — all under `examples/multi_agent/flood/` plus `.gitignore`, none
   in `broker/` or `examples/irrigation_abm/`. Commit or stash that unrelated work and tag before the
   queue starts, or the new corpus inherits the one defect the campaign was meant to remove.
3. **Output collision.** `environment.md` hazard 4: `--output` must be passed explicitly and the
   queue must refuse if the target exists. A governed `gemma3:4b` run without `--output` writes into
   `results/` next to the frozen corpus.
4. **Documented operational failures.** Windows Update auto-reboot (one incident, 6h47m lost), silent
   100% CPU fallback (one incident, 4 h at ~12× slower, no exception raised), silent-death runs
   exiting 0. Pause updates for the window; assert throughput per run, not just exit code; assert
   3,276 rows and zero `(agent, year)` gaps before a run enters the analysis.
5. **Schedule.** 2.5 days against 19.5 days of slack. Even three consecutive incidents fit.

### Abort rule

Freeze the analysis on whatever seeds have passed the integrity assertion by **14 Aug**. Report n = 3
if that is what completed. If fewer than 3 complete, **drop the section entirely** — the paper is
whole without it. Nothing in §§3–6 may depend on this run.

---

## 3. Option 3 — world-conditioned vs appraisal-conditioned rule ablation

**Configurable today with zero code changes for the direction that matters** (verified, §1d): a
`world_only` YAML profile drops the two appraisal-conditioned rules and keeps the world-conditioned
stack, which is enforced from Python regardless of profile. The reverse arm (appraisal-only) would
need code.

**Cost:** both arms must be re-run at the same code state — comparing a new `world_only` arm against
the shipped `strict` corpus is defect #9 by construction. 2 arms × 5 seeds × 10.4 h = **104 GPU-h,
4.3 d** (3 seeds: 62 h, 2.6 d).

**Do not run it, and the reason is the paper's own argument.** Removing the two appraisal-conditioned
rules removes 3,882 of the 10,507 recorded rule fires. Retry pressure collapses, actions change, agent
demands change, and therefore **the reservoir trajectory diverges between the `strict` and
`world_only` arms.** By the paper's established mechanism — the appraisal moves because the world
moved — any appraisal difference between those two arms is then confounded by exactly the channel §5
identifies. The ablation looks like it isolates the appraisal-conditioned layer and does not. It would
buy a number the paper would have to spend half a page disclaiming, for 4.3 days.

The within-system contrast `DECISION.md` §7 wants for Figure 1 is already available **inside the
existing corpus**, at zero GPU: the same arm, the same runs, rejections partitioned by which rule
fired (3,840 appraisal-conditioned vs 2,629 world-conditioned). That is the tighter comparison, and it
is already built.

---

## 4. Option 4 — feedback-off / reservoir-pinned arm

**Not feasible inside this folder's boundary, and not worth an exception.**

Mechanically: `irrigation_env.advance_year()` (line 462) calls `_generate_lake_mead_level()` (line
732), which computes storage from **agent diversions** via the mass balance. Pinning the trajectory
means injecting a recorded elevation series there. That is a new code path in
`examples/irrigation_abm/irrigation_env.py` — a frozen paper file this task is explicitly barred from
modifying — plus config plumbing, plus tests, plus a review round. Realistically **1.5–3 days of code
before any GPU**, then 5 × 10.4 h = 52 GPU-h.

Scientifically it is also weaker than it sounds. Mead drives `_update_preceding_factors`,
`_compute_drought_index`, `total_available_water`, `_apply_curtailment` and the shortage tier, which
in turn feed `curtailment_awareness` and `supply_gap_block_increase`. Pinning the reservoir while
leaving demands live breaks mass balance: the arm stops being a coupled simulation and becomes a
fixed-exogenous-forcing simulation whose internal consistency a reviewer can attack.

And the paper already owns that control three times over: the **year-1 stratum** (worlds provably
identical, `year1_exact_equal_rate = 1.0`), the **never-retried stratum**, and **flood**, which
`MATERIALS_VERDICT` defect #2 establishes has *no* action→environment feedback at all
(`run_flood.py:285-291`). A pinned irrigation arm is a within-testbed restatement of evidence that
already exists in three forms, at the cost of 3–5 days and a boundary exception.

---

## 5. Option 5 — more seeds on the unbalanced cells

> **CLOSED 2026-08-03 — executed for ministral3:8b, and this option’s central prediction came
> true.** The `ungoverned_v21_42yr_ministral3_8b_seed44` run described below was produced, so the
> cell is now balanced at 3 against 3 and the exclusion has been removed. The mixed-vintage risk
> argued here was real and did materialise: the new run is on a later broker commit, and that
> commit writes `failed_rules = "precondition_violation"` where the other 20 irrigation runs write
> `Unknown` for the identical allocation-cap rejection. It was caught by `fig1_rule_layers.py`’s
> own falsification gate rather than passing silently, and handled by mapping both literals to the
> precondition layer in `_data._NO_RULE_TOKENS`; the two are the same event, carrying identical
> `error_messages` and hitting only the two increase skills. The confound is therefore disclosed
> in §8 of the paper rather than invisible — which is the outcome the reasoning below said to
> protect. **The reasoning is kept, not deleted: it is why the vintage difference was looked for
> at all.** The gemma3:12b half of this option was NOT run and the argument against it stands.

**Original assessment, superseded for ministral3:8b only:**

**Do not run. This one is actively harmful, which is the opposite of how it looks.**

- `ministral3:8b` irrigation is 3 governed vs 2 no-validator; the missing run is
  `ungoverned_v21_42yr_ministral3_8b_seed44`. One run ≈ 14 GPU-h.
- `gemma3:12b` is 3+3; two more seed pairs ≈ 64 GPU-h, 2.7 d.

Every new seed runs at HEAD. Every existing seed in those cells runs at an older, dirty, in one case
unrecorded code state. Adding one is **defect #9 (mixed-vintage arms) deliberately introduced into
cells that are currently clean on that axis.** Right now `ministral3:8b` is a *disclosed* exclusion —
`_data.py:195` names it in `IRRIGATION_UNBALANCED_PREFIXES` and bars it from every paired contrast,
and the paper says so. Balancing it with a differently-vintaged run converts an honest, visible
exclusion into an invisible confound. *(2026-08-03: this happened. The confound was made visible
instead of invisible — see the banner at the top of this option.)*

The power it would buy is not needed. Per `MATERIALS_VERDICT` §2 the regime separation is **COMPLETE**
under six independent stratifications, including balanced-cells-only (7 cells) where the margin is
unchanged at +15.01 pp. Nothing in the paper turns on `ministral3:8b` going from 3+2 to 3+3.

---

## 6. Candidates considered and rejected without costing

- **A third model family (Qwen / Llama, both installed).** `environment.md` correctly notes it would
  weaken the "two open-weight families ≤27B" objection. But that objection lives in §8 Limitations, is
  cheap to concede, and a new family run at HEAD is a fresh mixed-vintage cell that cannot be pooled
  with the 14-cell table. It buys generality the claim does not rest on. Rejected on the same grounds
  as option 5.
- **Re-running any published cell for clean provenance.** 131 runs have zero clean manifests. Fixing
  that means re-running the corpus, which is weeks. §8 states it as a limitation instead. Correct call.
- **A mock-LLM byte-identity re-run.** Proves the code path, proves nothing about the claim. The
  existing pytest suite (3,293 passed) plus the flag's byte-identity gates already cover it.

---

## 7. If option 1 is approved — queue spec

```
# 0. clean tree + tag (unrelated multi_agent/flood work must be committed or stashed first)
git status --porcelain      # must be empty
git tag tae-firstattempt-2026-08-XX

# 1. isolated config: COMPLETE copy, not an overlay (runner pre-flights this)
cp -r examples/irrigation_abm/config  SUBMISSION_2026/TAE/runs/config_irrigation_instrumented
#    add to global_config:  audit: { initial_proposal_columns: true, executed_skill_columns: true }

# 2. per seed in 42 43 44 45 46 — sequential, --output ALWAYS explicit, refuse if it exists
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed <S> --memory-seed <S> --workers 1 \
  --governance-mode strict \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_instrumented \
  --output      SUBMISSION_2026/TAE/runs/instrumented_gov_seed<S>

# 3. per-run integrity assertion BEFORE the run counts (exit 0 is not evidence)
#    - 3,276 audit rows, 3,276 sim rows, zero (agent_id, year) gaps or duplicates
#    - non-empty reflection_log.jsonl
#    - initial_labels non-empty on >95% of rows   <-- the flag actually took
#    - wall-clock within 2x of 10.4 h              <-- catches the silent CPU fallback
```

Analysis goes in a new `TAE/evidence/` script importing `_data.py`, keeping the one-source-of-truth
rule. `_data.py` itself needs a small addition — its discovery functions are hard-anchored to
`examples/*/results` and will refuse a path under `SUBMISSION_2026/` (`_reject_contaminated` raises on
any path escaping both results roots). Add a separate, equally strict discovery function for the
instrumented corpus rather than loosening the guard.

Pause Windows Update for the window before starting.

---

## 8. What I could not determine

- **Effect size.** The two pilots (n = 1 and n = 2 retried rows, short synthetic runs) show the
  attempt-0 and accepted appraisals differ and differ in the direction the rule would produce. They
  are instrument validation. Anyone quoting them as a magnitude is misreading this document.
- **Whether the re-run reproduces the published anchor cell.** It runs at a different code state and
  the backend is non-deterministic at fixed seed. This is why the recommended statistic is designed to
  be within-run: the question is deliberately not asked. If the run happens to reproduce the published
  shift, say so as a bonus; do not build on it.
- **`gemma3:12b` / `ministral-3:8b` irrigation run times.** Scaled by `environment.md`'s 1.9 ÷ 1.1
  model ratio, not measured. Only affects options 3 and 5, both rejected.
- **Whether the archival wall-clocks (9.10–11.61 h) had a dedicated GPU.** They are upper bounds if
  anything else was running. The live pilot today measured 2.84 h/1,000 inside that range, so the
  costing is not obviously inflated.
