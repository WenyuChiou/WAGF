# RUN_DECISION — what goes on the GPU, decided 2026-08-01

> **Entry point is [HANDOVER.md](HANDOVER.md).** This file is a working record and its status
> claims go stale. Anything about whether something passes, is complete or is ready is measured
> by `evidence/corpus_inventory.py`, `evidence/run_all.py` and `paper/submission_gate.py` --
> prefer those three to any sentence here.

**Supersedes the experiment section of `EXPERIMENT_OPTIONS.md`** (its §0 verdict table, §2 queue
design, §6 "candidates rejected without costing", and §7 queue spec). `EXPERIMENT_OPTIONS.md` remains
the record of *how the costs were derived*; this file is the decision of record for *what runs*.
`PLAN.md` §5's fences are unchanged and are restated here in §4 with one addition.

Written in response to a correct observation by the user: the corpus uses an ageing model set and
newer models are installed and unused. That observation is answered in §2 and §3 — it is a real gap,
it is smaller than it looks, and the version of it that would satisfy a reviewer does not fit before
the 14 Aug freeze.

---

## 1. The decision in three lines

1. **Run option 1 and nothing else.** First-attempt appraisal logging, **governed arm only**,
   **`gemma3:4b`** (the anchor cell), `--real` (78 agents), 42 years, `strict`, **seeds 42–46**.
   **52 GPU-h, ~2.5 days wall-clock, zero code changes.** Commands: `runs/launch_firstattempt.md`
   §2, with the two amendments in §1.1 below. Must be **started by end of 6 Aug** or abandoned.
2. **Run no new model.** Not `gemma4:12b`, not `qwen3`, not `llama3.1`, not `glm-4.7-flash`, not the
   cloud endpoints. The cheapest shape that would actually answer *"does this hold on current
   models?"* — a new model, **both arms**, ≥3 seeds — costs **247–348 GPU-h (10.3–14.5 days,
   extrapolated; basis in §3)** against an 8-day window that option 1 already needs 52 h of. The
   vintage objection is answered in §8 of the manuscript by the paragraph in §7 of this file, at zero
   GPU-h.
3. **If option 1 does not start by 6 Aug, the GPU stays idle.** The fence is on the queue, not on
   option 1 specifically. Freed capacity is not re-spendable on a substitute run. See §4.

### 1.1 Two amendments to `launch_firstattempt.md`, both settled here

| # | amendment | verified today |
|---|---|---|
| **A1** | **Keep `--num-ctx 8192 --num-predict 4096`.** `launch_firstattempt.md` §2 flagged this as an open disagreement with `EXPERIMENT_OPTIONS.md` §7's literal command. It is now settled in favour of the flags. | `production_v21_42yr_seed42/reproducibility_manifest.json` records **`num_ctx 8192, num_predict 4096`**. A run launched at HEAD **without** the flags records **`num_ctx 4096, num_predict 2048`** — measured, in `runs/smoke_gemma3_4b_a2y1/reproducibility_manifest.json`. `--config-dir` does **not** carry these; `broker/utils/performance_tuner.py` auto-tunes them from the model's parameter count. Both flags exist and override (`run_experiment.py:758-759`, applied at `:671`). Without them the replication silently diverges from the cell it replicates on the LLM-parameter axis. |
| **A2** | **Drop `--memory-seed <S>`. Leave it at the CLI default (42) for all five seeds.** | `EXPERIMENT_OPTIONS.md` §7 specifies `--memory-seed <S>`; the archival convention does not. Verified: `--memory-seed` default is `42` (`run_experiment.py:755`); **no** `examples/irrigation_abm/*.bat` batch script passes it; `memory_seed` appears in no archival `reproducibility_manifest.json`. So all five published anchor seeds shared one seed-memory draw. This run is an *instrumented replication of the anchor configuration* — every axis that can match should match. The statistic is within-run and within-decision, so it is invariant to this either way; matching costs nothing and removes a provenance question. |

Additionally, add to the pre-flight (**A3**): **assert the model tag resolves before launching.**
There is no model-existence preflight anywhere in the runner or in `broker/utils/llm_utils.py`; a
typo'd tag returns HTTP 404, which `_invoke_ollama_direct` converts to empty content, and the run
completes as 3,276 fallback rows with **exit code 0**. One line — `ollama show gemma3:4b` must
succeed — before each command in `launch_firstattempt.md` §2.

---

## 2. Why the anchor first-attempt run cannot be moved to a newer model

The hole this run closes is a hole in **the published numbers**, and the published numbers are
`gemma3:4b`. `DECISION.md` §5 states the defect precisely: for a governed decision that was retried
and then approved, the appraisal on record is the **accepted** generation's, i.e. selected on the
rule — 763 of 3,276 decisions on anchor seed 42 (23.3%), and 22.7–26.2% across all five anchor seeds
against 5.3–7.4% in the comparison arm (`EXPERIMENT_OPTIONS.md` §1c). The quantity the run produces is
a **paired, within-decision contrast on that stratum**: attempt-0 HIGH-share minus accepted HIGH-share
on the same rows, in the same run, then `paired_t` over the per-seed deltas. Its whole validity comes
from never leaving the run — which is also why it is safe to run at a code state different from the
one that produced the corpus. Move it to `gemma4:12b` and the statistic is still internally valid, but
it now bounds acceptance-selection **in a cell that appears nowhere in the paper**, while §4, §5, §6
and the abstract continue to report `gemma3:4b` numbers whose selection bias remains unmeasured. The
reviewer's sentence — *"your conditioning variable is measured after the rule selected for it"* — is
written against the anchor cell and is answered only by a measurement on the anchor cell. A newer
model answers a different question (§3), and answering a different question louder does not close
this one.

---

## 3. The model matrix

**Cost bases, named.** *Measured:* anchor irrigation cost, from first/last `timestamp` in each
archival run's `raw/*_traces.jsonl` (`EXPERIMENT_OPTIONS.md` §1e) — **governed 10.4 h/run,
no-validator 8.2 h/run** (midpoints of 9.10–11.61 and 6.86–9.56). `ops/environment.md`'s table
(`gemma3:4b` 1.1 h/1,000) reproduces on flood and understates irrigation by 2.1–3.2×; it is not used
for irrigation anywhere below. *Extrapolated:* everything for a model that has never run irrigation.
Two independent extrapolation bases for `gemma4:12b`, both stated:

- **Ratio basis** — 16.4 s vs 3.7 s per generation on one real rendered anchor prompt, n=30 each,
  same parse path (`runs/probe_parse_reliability.py`) → **4.43×**. Governed 46 h/run.
- **Smoke basis** — `runs/smoke_gemma4_12b_a4y2`, 8 decisions. I re-derived this independently from
  the trace timestamps today: first `2026-08-01T05:16:17`, last `05:25:15` = **538 s / 8 decisions =
  67.3 s per decision**, against the archival anchor's 11.4 s/decision (10.4 h ÷ 3,276). → governed
  **61–65 h/run** after correcting for the smoke method's ~1.2× over-estimate of the anchor.

Neither basis captures `gemma4:12b`'s retry rate on the real 78-agent CRSS population, which
multiplies cost directly and is **unmeasured**. Treat 46–65 h/governed-run as a range with an open
upper tail, not a point.

| model | corpus status | arms | seeds | GPU-h | basis | what it buys |
|---|---|---|---:|---:|---|---|
| **`gemma3:4b`** — **THE RUN** | anchor, 5+5 runs | governed only | **42–46** | **52** | measured | The bound on acceptance-selection, **as a measurement**, on the cell every headline number comes from. Closes `DECISION.md` §12's named residual. |
| `gemma3:4b` both-arms add-on | anchor | + no-validator | 42–46 | +41 | measured | Converts a structural argument into a measured null. **Conditional only** — see §4. |
| `gemma4:12b` | **installed, in no cell** | both (a one-arm cell computes no shift) | 3 | **247** | extrapolated, ratio | One row in `table1_cells.csv`. **Does not change `DECISION.md` §8's "two open-weight families ≤27B" by one word** — it is the same family as `gemma4:{e2b,e4b,26b}`, at a size point inside the 4B–27B range the corpus already spans. |
| `gemma4:12b` | as above | both | 3 | **348** | extrapolated, smoke | as above |
| `gemma4:12b` | as above | both | 5 | 412 | extrapolated, ratio | as above |
| `gemma4:latest` | **already in the corpus under another tag** | — | — | — | — | **Nothing, and it would be an error.** `ollama list` today: `gemma4:latest` and `gemma4:e4b` are both ID `c6eb396dbd59`, 9.6 GB. Same weights. `gemma4:e4b` has 20 runs in the corpus. |
| `llama3.1:8b` | installed, in no cell | both | 3 | ~96 (+15% margin → 111) | extrapolated, `ops/environment.md` 1.9÷1.1 = 1.73× ratio applied to measured irrigation midpoints | The only genuinely useful thing on this list: a **third family**, which turns "two open-weight families" into "three" in §8. That is the entire manuscript delta — one row, one word. §§3–6 unchanged. And it is a 2024 model, so it does **not** answer "current models". |
| `qwen3:8b` / `qwen3.5:4b` | installed, in no cell | — | — | — | — | **Disqualified from any same-prompt cell.** `broker/utils/llm_utils.py:61-64,95-105` appends `"\n/no_think"` to **every prompt** for `qwen3`. Verified by execution. The prompt is no longer the frozen prompt, and `--config-dir` cannot reach `model_quirks` to stop it. |
| `glm-4.7-flash:q4_K_M` / `-hermes` | installed, in no cell | — | — | ~520 | extrapolated ×10 from `gemma3:27b`'s VRAM-overflow signature | **Infeasible.** 19 GB each against 16,376 MiB total VRAM (`nvidia-smi` today: 16,376 total, 7,766 used at idle). Guaranteed CPU offload. `ops/environment.md` already prices that regime: `gemma3:27b` at 17 GB costs ~10× the small models. Also `parse_model_size` cannot read the tag and silently assumes 7B. |
| `kimi-k2.5:cloud` / `k2.6:cloud` | not local weights | — | — | n/a | probed today | **Negative value.** `kimi-k2.5` → HTTP 410 *"retired at 2026-07-31"*; `kimi-k2.6` → HTTP 403 *"requires a subscription"*. Both unusable. A non-200 becomes empty content, so either would produce a silent full-run fallback corpus rather than an error. A model retired **yesterday, mid-campaign** is the argument against cloud endpoints, not for them. |
| new family on **flood** | — | both | 3 runs | ~14 | `ops/environment.md` flood table, which reproduces | The one affordable new-model shape. Rejected anyway — see §7. |

**The window arithmetic, which is the decision.** 6 Aug go/no-go → 14 Aug freeze is **8 days = 192 h**
of perfect, uninterrupted, serial GPU. Option 1 needs 52 h of it. The cheapest defensible new-model
cell is 247 h on its own. It does not fit, and it does not fit by a margin no amount of scheduling
recovers.

---

## 4. Schedule with hard fences

| fence | date | rule |
|---|---|---|
| **Prerequisite** | **before launch** | `git status --porcelain` **empty**, tree tagged `tae-firstattempt-2026-08-<DD>`, Windows Update paused ≥4 days, target `--output` directories confirmed non-existent, `diff -rq` against the frozen config prints exactly one line, `ollama show gemma3:4b` succeeds (A3). Verified today: the tree is **not** clean — 6 modified + 10 untracked paths, all under `examples/multi_agent/flood/` and `examples/reservoir_control/`, plus `.gitignore`. **None is under `examples/irrigation_abm/` or `broker/`, so none can affect this run** — but an untracked tree at tag time reproduces the exact provenance defect (`MATERIALS_VERDICT` #9/#14) this run exists to avoid. Clearing it is a P0.2 / `examples/` edit and is **outside this folder's write scope — Wenyu does it, not an agent.** This is the critical path. |
| **HARD GO/NO-GO** | **6 Aug** | If the queue has not started by end of 6 Aug, **abandon permanently.** Not rescheduled, not shortened, not moved into the buffer. |
| **NO SUBSTITUTION** *(new — added by this decision)* | **6 Aug onward** | The fence is on **the GPU queue**, not on option 1. If option 1 is abandoned, the freed 52 GPU-h is **not** reallocated to a new-model cell, a flood add-on, or extra seeds. Capacity released by a fence is released to the writing window. This rule exists so the 7 Aug conversation "well, the GPU is free now" cannot happen. |
| **Per-run integrity** | after each seed | §5 below. Run it the moment a seed's process exits, **before** launching the next. Exit 0 is not evidence. |
| **Both-arms add-on** | **12 Aug** | Take the +41 GPU-h no-validator arm **only if all five governed seeds have passed integrity by end of 12 Aug.** Otherwise skip it and say in §8 that the bound was measured on the arm where the selection stratum is ~4× larger (24.3% vs 6.3%). |
| **FREEZE** | **14 Aug** | Analysis freezes on whatever seeds passed. **n ≥ 3** → report with df = 2. **n < 3** → delete the appendix section entirely; §8 keeps only the limitation sentence. Never partially present. |
| **Downside budget** | — | If attempt-0 → accepted drift generalises, §5/§8/abstract need one paragraph separating the cross-arm world-driven shift from a within-decision revision channel on the retried quarter. **One extra writing day is pre-authorised** (`PLAN.md` §5). Two pilots (n=1 and n=2 retried rows) both showed HIGH → non-HIGH flips, so this branch is not remote. |

**Unbudgeted work to schedule now, not discover at the freeze:** the analysis script does not exist.
`launch_firstattempt.md` §5 is explicit that it can only be written once real column names and row
counts are on disk, and it needs a **new** strict discovery function for
`SUBMISSION_2026/TAE/runs/firstattempt_gov_seed*` — `_data.py`'s `_reject_contaminated()` will
correctly refuse those paths and must **not** be loosened. **Budget ~2 h, on 12 or 13 Aug**, in the
same days as §8 drafting.

**Sequential, one seed at a time, with a human gate between each.** Five seeds is five interruptions
across 2.5 days. The GPU cost is not the real cost.

---

## 5. The integrity gate — exit 0 is not evidence

`SUBMISSION_2026/TAE/evidence/e3_run_integrity.py` exists and is the gate. Run it per seed
directory; a run that fails any assertion is **not in the analysis**:

```
python SUBMISSION_2026/TAE/evidence/e3_run_integrity.py SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>
```

It asserts, per run: **3,276 audit rows and 3,276 simulation rows** (= 78 agents × 42 years,
asserted in the script itself); **zero `(agent_id, year)` gaps or duplicates** in both files; the
`initial_labels` / `initial_skill` / `attempt_skills` columns **present**; `initial_labels`
**non-empty on >95% of rows** (i.e. the flag actually took); attempt-0 and accepted appraisals
**actually differ somewhere** (a column of identical values would mean the snapshot is being taken
after the retry loop, not before); **non-empty `reflection_log.jsonl`**; **wall-clock within 2× of
10.4 h** — the throughput check that catches the documented silent 100% CPU fallback, which raises no
exception and exits 0; and **provenance** (tag/commit/dirty).

Three failure modes it exists for, each with a recorded incident: Windows Update auto-reboot (one
incident, 6h47m lost), silent CPU fallback (one incident, 4 h at ~12× slower, no error), silent-death
runs exiting 0 with truncated output.

**One addition, mandatory if any new-model cell is ever run under a future decision:**
`REJECTED_FALLBACK` rate must be a **per-run assertion with a stated ceiling**, not a post-hoc
observation. Anchor base rates, measured on the shipped corpus (governed, seed 42, n=3,276 each):
`gemma3:4b` **0.70%**, `gemma4:e2b` 0.03%, `gemma4:e4b` / `gemma3:12b` / `ministral-3:8b` **0.00%**.
A model at, say, 3% would still "work" mechanically while dropping 3% of decisions out of the
appraisal statistic **non-randomly** — fallback rows concentrate on the retry-heavy stratum the paper
is about. That is a bias in the conditioning variable, not a crash, and nothing else in the queue
would catch it.

**Timeout ceiling, recorded because it has no escape hatch.** `LLM_CONFIG.timeout` is 120 s and is
settable only from an `agent_types.yaml` in the process CWD — not via `--config-dir`, not via a CLI
flag. `large_model_patterns` raises it to 600 s only for `26b/27b/30b/32b/70b`. This does not bind
`gemma3:4b`. It **would** bind any 8–14B model whose generation runs long, and the framework records
a timeout as empty content → retry → fallback, which reads as model misbehaviour rather than a
configuration ceiling. Another reason a new-model cell is not the low-risk option it appears to be.

---

## 6. The invariant, and what each run would ADD section by section

**§§3–6 derive entirely from the shipped corpus.** If the queue dies at any fence, the paper is
unchanged. Nothing below is load-bearing for any section. The downside branch is always a
**deletion**, never a rewrite.

| § | today, from the shipped corpus | what option 1 ADDS | if the run dies |
|---|---|---|---|
| §1 Introduction | The gap; systems-novelty concession. | **Nothing.** | unchanged |
| §2 Setup | Two testbeds, 9 LLM configs, validators-on/off. | **Nothing** — the instrumented replication is named only in the appendix and §8, as its own corpus. | unchanged |
| §3 Two rule layers separate | 59.4% / 40.6% layer split; within-stack contrast; Fig 1. | **Nothing.** | unchanged |
| §4 Conditioning variable moves | Per-cell table, both arms' prevalence, complete regime separation. | **Nothing.** | unchanged |
| §5 Mechanism (**the core**) | Year-1 null; never-retried shift *larger* (+48.21 vs +40.02, 5 of 5 cells; +49.1 vs +40.45 before 2026-08-03); shift tracks the reservoir. States that the first-attempt appraisal is unrecoverable from this corpus. | **One paragraph + one appendix pointer.** The bound on acceptance-selection becomes a measured δ on the retried-and-approved stratum instead of an argument. | The paragraph is not written. The three existing supports stand alone, exactly as `DECISION.md` §5 already has them. |
| §6 What it does to the statistic | Conditional vs unconditional, 5 irrigation cells, 12B +11.4 → +0.2. | **Nothing.** | unchanged |
| §7 What to do instead | Report prevalence in both arms; design-fixed denominators; world-state antecedents. | **Nothing.** | unchanged |
| §8 Limitations | Acceptance-selection stated as an unquantified limitation. | **One clause**: the limitation becomes quantified — max contribution of acceptance-selection bounded by 0.243 × δ. | The unquantified limitation sentence stays, as currently planned. |
| Appendix | — | **The whole appendix section**, on a separately named, provenance-clean corpus. | Deleted (the `n < 3` rule). |

**The wording constraint, non-negotiable.** The appendix must say *"measured on an instrumented
replication of the anchor configuration"*, **never** *"measured on the published corpus"*. The backend
is non-deterministic at fixed seed, so the new run's 3,276 decisions are not the published run's
3,276 decisions. What it estimates is a bias magnitude **in a configuration** — which is exactly the
unit the paper already trades in (seed is the inferential unit; every cell value is a mean of per-seed
rates over a non-deterministic backend). `NUMBERS.md` must carry the replication as its own corpus
with its own script and stdout line.

---

## 7. Rejected, with reasons, so none of this is re-litigated

**On the user's observation specifically.** The gap is real as an inventory fact and smaller than it
looks as a diagnosis. Four things, each verified today: (i) the corpus is **two families**
(Gemma + Ministral, gemma3/gemma4 as one lineage), which is exactly what `DECISION.md` §8 already
concedes — no gemma4 variant changes that sentence; (ii) `gemma4:latest` is **the same ollama digest**
as `gemma4:e4b`, already in the corpus 20 times; (iii) the genuinely newest installed model,
`glm-4.7-flash` at 5 weeks, is 19 GB against 16,376 MiB of VRAM and is the one that cannot run;
(iv) the vintage gap to the newest *feasible, unrepresented* candidate is **7 weeks, same family**.

| rejected | why |
|---|---|
| **`gemma4:12b` as a new cell** | 247–348 GPU-h for the minimum defensible shape (both arms × 3 seeds) against a 192 h window that option 1 needs 52 h of. And it buys **zero** manuscript delta — same family, size point inside an already-spanned range. Technically it is fine: no code change needed, 100% on GPU at 8.1 GB, and **30/30 clean parses with both construct labels** on a real anchor prompt (better than the anchor's own 29/30). It fails on cost and on value, not on feasibility. |
| **`gemma4:latest`** | Same digest as `gemma4:e4b` (`c6eb396dbd59`). A duplicate cell under a second tag. |
| **`qwen3:8b` / `qwen3.5:4b`** | The framework appends `"\n/no_think"` to every prompt for `qwen3`. Not a same-prompt cell, and `--config-dir` cannot reach the quirk table. |
| **`glm-4.7-flash` (either tag)** | 19 GB vs 16,376 MiB VRAM. Guaranteed CPU offload; ~520 GPU-h extrapolated from `gemma3:27b`'s overflow signature. Infeasible, not merely expensive. |
| **`kimi-k2.5` / `k2.6` cloud** | 410 (retired 2026-07-31) and 403 (subscription). Non-200 → silent fallback corpus, not an error. Breaks the open-weight, locally-hosted, tagged-provenance framing the paper rests on. |
| **`llama3.1:8b` as a third family, irrigation** | The only candidate with a real manuscript delta — "two families" → "three" in §8. Costs **96–111 GPU-h (extrapolated)**, i.e. *more than option 1*, for **one word**, and it is a 2024 model so it does not answer "current models" either. Running it alongside option 1 (134–163 GPU-h total, serial, with human gates) leaves option 1 with **no room to relaunch a failed seed** — which is precisely how option 1 ends up below n = 3 and gets deleted. |
| **New family on flood (~14 GPU-h)** | Genuinely cheap and still rejected: flood has **no action→environment feedback** (`run_flood.py:285-291`) and carries none of the identified claim, which is within-irrigation; **B5 is now RESOLVED (2026-08-01, ahead of its 3 Aug slot) and the answer removes this particular worry** — `evidence/e2_flood_instrument.py` traced `construct_TP_LABEL` across all 90 flood runs and 81,704 decisions and returned **IDENTICAL INSTRUMENT** (`evidence/B5_flood_instrument.md`), so flood is *not* forced to descriptive-only and a new cell would have numbers to print. **The rejection stands on the other two grounds**, which B5 never depended on; and a 10th flood cell lands in a low-regime bundle (\|shift\| ≤ 6.3 pp) that a skimming reviewer reads as *"the effect does not appear in the new model."* |
| **Any new cell pooled with the existing 14** | Impossible. Every existing cell runs at one of **18 unknown, dirty code states**; a new one runs at a clean tagged HEAD. Model versus code state would be perfectly confounded, n = 1 on the confound — `MATERIALS_VERDICT` defect #9 deliberately introduced. |
| **Rule ablation (`world_only`)** | 104 GPU-h. Removing the two appraisal-conditioned rules removes 3,882 of 10,507 rule fires, so demands and therefore the reservoir diverge between arms — the appraisal difference is confounded by exactly the channel §5 identifies. Unchanged from `EXPERIMENT_OPTIONS.md` §3. |
| **Reservoir-pinned arm** | 1.5–3 d of coding in frozen `examples/` before any GPU, breaks mass balance, and the paper already owns the control three ways. Unchanged from `EXPERIMENT_OPTIONS.md` §4. |
| **More seeds on unbalanced cells** | Manufactures the mixed-vintage defect in cells currently clean on that axis, converting a disclosed exclusion into an invisible confound. Separation is already complete under six stratifications. Unchanged from `EXPERIMENT_OPTIONS.md` §5. |

### The 20-minute substitute for a new-model cell

Write this into §8. It answers the vintage objection on the ground the paper actually stands on, and
it costs zero GPU-hours:

> The claim is a property of the measurement design, not of model capability: a norm whose antecedent
> is model-authored has no observation channel independent of the generation it governs, and no
> increase in scale or recency creates one. The corpus spans 4B–27B across two open-weight families
> and two testbeds; the composition effect is present at both ends of that range, and on one
> configuration (Gemma-3 12B, +11.4 conditional → +0.2 unconditional) it accounts for the entire
> reported gain. Whether the magnitude changes on frontier models is open; whether the statistic can
> separate behaviour from composition does not depend on it.

---

## 8. What this decision rests on, and what it does not

**Verified by execution today** (this session): `git status --porcelain` (16 dirty paths, HEAD
`10e190cf`, no `tae-*` tag); `nvidia-smi` (RTX 4080 SUPER, 16,376 MiB total, 7,766 MiB used, 0%
util); `ollama list` (`gemma4:latest` ID `c6eb396dbd59` = `gemma4:e4b`); the `num_ctx`/`num_predict`
divergence across three manifests (§1.1 A1); `--memory-seed` default 42 and its absence from every
archival batch script (§1.1 A2); `--num-ctx`/`--num-predict` flags exist and override; the
`gemma4:12b` smoke trace span (538 s / 8 decisions = 67.3 s/decision), which independently
corroborates the slower of the two cost bases in §3; `e3_run_integrity.py` exists with the eight
checks listed in §5.

**Taken from a sibling lane's measurement, not re-run here:** the n=30 parse-reliability probe
(`runs/probe_parse_reliability.py`) giving 16.4 s vs 3.7 s per generation, the 30/30 vs 29/30 parse
counts, the cloud HTTP 410/403 probes, and the `qwen3` prompt-mutation check. Re-running the probe
would cost ~12 min of GPU; the smoke-trace corroboration above points the same way and is enough to
carry a NO-GO.

**Labelled estimates, not measurements:** every GPU-h figure for a model that has never run
irrigation — `gemma4:12b` (247/348/412), `llama3.1:8b` (~96), `glm-4.7-flash` (~520). Each names its
multiplier basis inline in §3. The 46–65 h/run range for `gemma4:12b` has an **open upper tail**
because its retry rate on the real 78-agent population is unmeasured, and retry rate multiplies cost
directly. A NO-GO does not become a GO if that tail is generous.

**Not verifiable from here:** whether the archival 9.10–11.61 h wall-clocks had a dedicated GPU (if
not, they are upper bounds and the ratio-based projections are optimistic).

**Note on inputs.** One of the three costing lanes feeding this decision returned a null result (its
recommendation, risks and detail were all the literal string `test`). Its contribution is therefore
zero; the cost model here rests on `EXPERIMENT_OPTIONS.md` §1e's measured archival wall-clocks, the
feasibility lane's probe, and my own independent re-derivation from the smoke traces. Recorded so the
gap is visible rather than assumed covered.

---

## 9. Nature Water

Paused. Nothing here touches it. Recorded only, unchanged and unacted-on per `PLAN.md` §6: six NW
drafts were edited 2026-07-30 with no recoverable diff, and
`figures/Fig3_cumulative_adaptation.{png,pdf}` were overwritten by a script that drops one of three
series. Both need the user's eyes when NW is unpaused.
