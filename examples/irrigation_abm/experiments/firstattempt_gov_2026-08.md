# Arm: `firstattempt_gov` — logging the appraisal the agent wrote first

**Written 2026-08-05, before the run.** Everything below the "Results" heading is empty until seed 42
finishes. That ordering is deliberate: a design record written afterwards records what was found, not
what was asked.

| | |
|---|---|
| **run directories** | `examples/irrigation_abm/results/firstattempt_gov_gemma3_4b_seed42` … `seed46` |
| **model** | `gemma3:4b` (the anchor cell — matches both papers' headline model) |
| **arm** | governed / `--governance-mode strict` only |
| **seeds** | `--seed` 42, 43, 44, 45, 46 — run sequentially, never in parallel |
| **memory seed** | `--memory-seed 42` for **all five**, i.e. the default. See §2a. |
| **isolated config** | `SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt/` |
| **cost** | ~10.4 h per run, ~52 GPU-h total |
| **decision of record** | `SUBMISSION_2026/TAE/PLAN.md` §5 — "RUN OPTION 1, AND NOTHING ELSE" |
| **design record status** | written before launch · results section pending |

---

## 1. The question

When an agent's proposed action is blocked, it is asked to choose again. It re-answers the whole
prompt — including the part where it reports **how bad it thinks the situation is**.

The shipped corpus records only the appraisal that survived. So a conformance rate computed as
*"among decisions where the agent said conditions were severe, how many still asked for more water"*
is conditioned on a variable that the enforcement being measured may itself have rewritten.

**This arm records the appraisal at the first attempt as well as the last, so the question becomes
observable instead of inferred.**

The paper currently answers it by stratification — hold the simulator-recorded world state fixed and
the apparent effect collapses. That argument is sound but indirect. This arm tests the same claim by
a different route, which is worth more than another seed of the same measurement: it can disagree.

## 2. What changes, exactly

One YAML block, in an isolated copy of the config tree. Nothing in `broker/` changes.

```yaml
global_config:
  audit:
    initial_proposal_columns: true    # initial_skill, initial_labels, attempt_skills
    executed_skill_columns: true      # executed_skill, executed_via_fallback
```

Both keys default **off**, so every frozen run stays byte-identical. The isolated tree differs from
`examples/irrigation_abm/config/` in exactly two files — `agent_types.yaml` (this block) and
`DIFF_AGAINST_FROZEN.md` (documentation). Verified by `diff -rq` on 2026-08-05, and its line endings
are CRLF like the frozen tree, so `config_hash` moves for one reason only.

`executed_skill_columns` is on because this project's headline numbers follow an **executed-only**
rule, the pairing is called for at `broker/core/_audit_helpers.py:271`, and the column **cannot be
added retroactively**. A superseded config copy at `ICLR2027/experiments/config_firstattempt/` omits
it; see the `SUPERSEDED.md` beside it for why not to launch against that one.

## 2a. `--memory-seed` stays at the default 42 — a deliberate deviation from the decision text

**There are two seeds and they do different things.** Confusing them would make this arm a different
experiment from the corpus it is meant to sit beside.

| flag | what it controls | archival practice | here |
|---|---|---|---|
| `--seed` | the experiment's randomness | **varied**: 42, 43, 44, 45, 46 | **same — varied 42–46** |
| `--memory-seed` | passed as `seed=` to `HumanCentricMemoryEngine` (`run_experiment.py:629`); the memory engine's internal ranking randomness only | **never passed** → default **42** on all five runs | **42 on all five** |

`EXPERIMENT_OPTIONS.md:403` writes `--memory-seed <S>`, i.e. per-seed. **This arm does not follow
that, on the author's decision of 2026-08-06**, and the reason is reuse.

The archival v21 batch scripts — the ones that produced the corpus this arm sits beside, and that
Nature Water's headline irrigation numbers come from — never pass `--memory-seed` at all
(`grep -rn "memory-seed" examples/irrigation_abm/*.bat` returns nothing), so all five archival runs
share memory seed 42 and vary only the sampling seed.

Matching that leaves the new arm differing from the frozen corpus in **exactly two ways: the audit
flag, and the code state.** Varying the memory seed as well would add a third axis — different
initial memories — which buys nothing for a within-decision measurement and costs a paragraph of
explanation in any paper that compares the two.

**Seed 42 is unaffected either way**: `--memory-seed 42` and the per-seed convention coincide there.
The deviation only applies to seeds 43–46, which had not been launched when the decision was taken.

### The three new columns

| column | what it holds |
|---|---|
| `initial_skill` | the action proposed at attempt 0, before any rule spoke |
| `initial_labels` | the appraisal at attempt 0, pipe-delimited: `WSA_LABEL=M\|ACA_LABEL=M` |
| `attempt_skills` | the action at every attempt, pipe-delimited |

Snapshotted at `broker/core/skill_broker_engine.py:365`, before the retry loop can reassign the
proposal.

## 3. The gap in this instrument — state it in Methods, do not discover it in review

**The appraisal is captured at the first attempt and the final one. Not in between.**
`attempt_skills` tracks the *action* at every attempt; there is no equivalent for the *labels*.

Two consequences, both of which constrain what may be claimed:

1. Whether the appraisal moves on the first push-back or only under repeated pressure is **not
   answerable from this data**. No "more enforcement produced more revision" claim is available.
2. A label that moves away and returns — medium, high, medium — records as **unchanged**. So the
   measured drift is a **floor, not a point estimate**. Report it as a floor.

One further precision for Methods: "first attempt" means the first attempt the system could *parse*.
If the model emitted unparseable output and was asked to reformat, only the last of those is captured
(`broker/core/_retry_loop.py:144`). That is arguably the right boundary for this question — the
appraisal has to be readable to be conditioned on — but it is not literally the first thing the agent
wrote, and the distinction belongs in the text.

## 4. What would falsify the paper's current account

Three outcomes, all reportable. This is the part that makes it an experiment.

| finding | consequence |
|---|---|
| appraisal rarely moves between attempts | the stratification argument is confirmed by an independent route; the world-composition account carries the whole effect; §8's admission narrows |
| appraisal moves substantially | there is a within-decision revision channel alongside the cross-arm compositional one. **Two different quantities, not a falsification** — but §5, §8 and the abstract each need a paragraph distinguishing them, and Figure 1's feedback edge becomes load-bearing rather than illustrative |
| the columns come back mostly empty | the instrument failed, not the theory. See §5 |

`PLAN.md` §5 pre-authorises one extra writing day for the middle case.

## 5. The stop condition — check this before spending the remaining 41 GPU-hours

**Integrity gate: `initial_labels` must be non-empty on >95% of all rows AND >95% of retried rows**
(`SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:91-92`).

The only measurement that exists before this run comes in **under both bars**:

| stratum | smoke (`gemma3:1b`, 15 rows) | gate |
|---|---|---|
| all rows | 93.33% | >95% ❌ |
| retried rows | 80.00% | >95% ❌ |

The empty row is not a parse failure: `status=APPROVED`, `retry_count=3`, `attempt_skills` fully
populated. The model produced an action and no appraisal labels.

n=15 is far too small to predict, and `gemma3:1b` is much weaker than `gemma3:4b`. The 4b rate will
very likely be higher. But it is the only evidence, it points the wrong way, and it lands hardest on
the retried stratum — which is the entire point of the arm.

**The failure is not random, and its direction is knowable in advance.** A construct-less attempt-0
is exactly the low-quality generation most likely to be rewritten. Dropping those rows biases
measured drift **downward**. So a low fill rate does not merely add noise; it makes the arm
systematically understate its own effect.

**Run seed 42 alone. Measure the fill rate. If retried rows come in under 95%, stop.**

## 6. Reuse — this arm is not only for the conference paper

Nature Water Paper 1b has the same gap. `examples/single_agent/analysis/compute_retry_compliance.py`
reads `final_act`, `final_skill`, `final_tp`, `n_retries` — it can count retries but **cannot see
what the first attempt said**. `final_tp` is the flood domain's self-reported appraisal, so the
missing quantity is exactly what these columns capture.

Four conditions were imposed on this arm so that a journal, not just a workshop, can use it:

1. **Isolated config root** — the frozen v21 corpus is Nature Water's current headline data and is
   not touched.
2. **`gemma3:4b`** — Paper 1b's headline model. An arm on a different model would tell Nature Water
   nothing about its own numbers.
3. **Clean manifests from the first run.** The reproducibility audit is RED for historic runs and was
   waived only for a non-archival workshop PDF. A journal will not accept that waiver; these runs are
   produced so that at minimum the new arms are reproducible.
4. **Arm identity pinned in the manifest** (`5dc063c5`) — `governance_profile_resolved`,
   `advise_spec_resolved`, `max_retries_resolved`. An undeclared profile fails loudly.

**What this arm does NOT license.** It is a within-run, within-decision measurement. Comparing its
rejection rates or `failed_rules` taxonomy against the frozen corpus is **not** valid, for two
independent reasons that stack:

- `failed_rules` now writes `precondition_violation` where the frozen corpus wrote `Unknown`
  (broker `0b17c367`, 2026-06-10, on `origin/main`);
- new runs carry a `shadow_blocked` column the ten anchor runs lack (`audit.py:322`).

The within-run comparison is unaffected by both, which is what makes this arm safe to run at a
different code state than the corpus it sits beside.

## 7. What reads this arm

| consumer | what it does |
|---|---|
| `SUBMISSION_2026/TAE/evidence/e3_run_integrity.py` | the gate — row counts, join gaps, fill rate, config-isolation marker. Exit 0 is necessary, not sufficient |
| `SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py` | the analysis. **Raises rather than reporting 0% drift if the columns are absent** — a flag-OFF run cannot answer this question and must not be scored as zero |
| Nature Water | not yet wired. See §6 for the conditions that make it usable |

`e7`'s refusal behaviour is the point of that file. A run without the columns is not evidence of no
drift; it is evidence of nothing.

## 8. Launch

Pre-launch checks and the exact command: `SUBMISSION_2026/TAE/analysis/preflight_2026-08-05.md` §6.
Two that have cost real time before:

- `ollama ps` must read **100% GPU**. On 2026-05-13 a driver update silently moved inference to CPU
  and ran 12× slower for four hours before anyone noticed.
- Windows Update paused ≥ 4 days. An auto-reboot killed a run at year 10.

---

## Results

*Empty until seed 42 completes. Record here: fill rate by stratum, drift rate with its denominator,
the `failed_rules` literal census, wall-clock per run, and any run excluded by the gate and why.*
