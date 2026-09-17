# r19 — Pre-launch settings audit, corpus regeneration 2026-09-15

**Scope.** Adversarial read-only review of every setting that will produce the
regenerated real-LLM corpus at commit `e75e390c`, before the queue is launched.
Target: the data behind Fig 2 (irrigation strict vs ungoverned + FQL) and Fig 3
(flood strict vs disabled + rule-based).

**Method.** Worktree `C:/Users/wenyu/Desktop/Lehigh/wagf-main-runs` (detached
`e75e390c`) read directly; git history and docs from the primary repo. No GPU
run, no `pytest`, no edits to any repo file. Four `--model mock` runs (irrigation
strict, irrigation ungoverned, flood strict, flood disabled) plus a rule-based
run were executed into the session scratch directory only.

**Launch state at the time of writing.** Nothing is running. The queue was
started once at 09:42 with `--workers 1`, stopped, and the partial seed-42 output
renamed to `strict_42yr_gemma3_4b_e75e390c_seed42_PARTIAL_workers1_stopped_2026-09-15`
(contains only `LAUNCH_COMMAND.txt`, an empty `reflection_log.jsonl` and `raw/`,
no `simulation_log.csv`, so the skip-check will not skip it). `regen_irrigation_fql.bat`
(09:48) and `regen_rulebased.bat` (09:49) already completed. The six GPU arms have
not run.

---

## 1. PASS / GAP table

| # | Check | Verdict | One-line reason |
|---|---|---|---|
| 1a | Flags in each bat vs surviving LAUNCH_COMMAND / manifests | **PASS** | model, `--real`, years, agents, memory-seed, num_ctx, num_predict, thinking-mode, governance-mode, config-dir all match the surviving records (§2.1) |
| 1b | `--workers 4` changes only scheduling — flood | **PASS** | every flood RNG draw is made on the main thread in `pre_year` / `advance_year`; worker count cannot reach them (§2.2) |
| 1c | `--workers 4` changes only scheduling — irrigation | **GAP (G1)** | `IrrigationEnvironment.execute_skill` draws from one shared `np.random.Generator` **inside the worker threads** (§2.2) |
| 1d | Shared mutable state in memory / audit writers | **PASS** | audit writer is `RLock`-guarded (F6); memory writes and per-agent env writes are main-thread or per-agent-key (§2.2) |
| 1e | Same exogenous stream for seed-42 governed vs seed-42 ungoverned | **PASS with caveat** | file-driven inputs are shared exactly; the *derived* stream diverges once decisions diverge — same at workers 1 and 4 (§2.3) |
| 2a | Irrigation control arm is the published one | **PASS** | bat uses `run_ungoverned_experiment.py`, which has no `--governance-mode` and attaches `with_custom_validators([])` (§3.1) |
| 2b | Governed vs ungoverned parity (prompt / menu / memory / reflection / parser / audit schema) | **PASS** | identical construction line-for-line; only `with_governance` + `with_custom_validators` + the consecutive-tracker no-op differ (§3.1) |
| 2c | `--rebalance-clusters` parity across the three Fig-2 arms | **GAP (G4)** | ON for FQL, unavailable in the ungoverned runner, not passed to strict — the FQL arm runs a different persona mix (§3.2) |
| 2d | Flood `--governance-mode disabled` — what is actually disabled | **PASS** | `thinking_rules: []` + `identity_rules: []`; validator pipeline still runs and emits the same columns (§3.3) |
| 3a | What is actually sent to Ollama per call | **PASS (documented)** | irrigation: `num_ctx`/`num_predict` only. flood: + `temperature 0.8 / top_p 0.9 / top_k 40` + `think:false` (§4.1) |
| 3b | An Ollama `seed` is sent | **GAP (document only, G8)** | the string `seed` does not occur in `broker/utils/llm_utils.py` — sampling is never seeded (§4.2) |
| 3c | Manifest records what was sent | **GAP (document only, G7)** | manifest reads global `LLM_CONFIG`, not the resolved per-type overrides → flood records `temperature: null` while 0.8 is sent (§4.3) |
| 3d | A recoverable record of the true sampling params exists | **PASS** | `config_snapshot.yaml` is written per run and carries the real values (§4.3) |
| 4 | Runtime environment that changes numerics is recorded | **GAP (G3)** | Ollama version, `OLLAMA_*`, GPU/driver, model digest reach no artifact; Ollama upgraded 0.33.3 → 0.34.0 between the September runs and now (§5) |
| 5a | Prompt / policy / skill-registry identity vs the old corpus | **PASS** | prompts byte-identical; both `agent_types.yaml` diffs are additive-only (0 deletions) (§6) |
| 5b | `config_hash` matches the old corpus | **GAP (document only, G9)** | irrigation `75ad0628600f → baa3e98b49d3`; flood `5b3959996135 → 3fd510c6ce62` — additive changes, but the hash no longer matches (§6) |
| 5c | Broker-core changes that alter the decision stream | **PASS with residual** | every behavioural change found is confined to audit/diagnostic columns; three files accepted on their commits' own audits (§6) |
| 5d | Irrigation input data provenance | **GAP (document only, G10)** | `ref/CRSS_DB/` is gitignored; byte-identity with the d8a5da41-era file cannot be proven (§6) |
| 6a | Columns the figure scripts need exist | **PASS for Fig 3, CONDITIONAL for Fig 2** | Fig 3 reads `simulation_log.csv` only, all present; Fig 2's pie matrix needs `construct_WSA_LABEL` from the audit CSV (§7) |
| 6b | Governed and ungoverned arms emit the same schema | **PASS** | byte-identical CSV headers and identical manifest key sets in both domains (§7) |
| 6c | Audit CSV column set is fixed | **GAP (document only, G11)** | fieldnames are the union of keys *observed in that run*, so the column set is run-dependent (§7) |
| 7a | GPU memory for 4 parallel 8192-token contexts | **PASS** | ≈ 6–7 GB estimated against 13.3 GB free; `OLLAMA_MAX_LOADED_MODELS=1` (§8.1) |
| 7b | Disk + nightly backup cover the new directories | **PASS with hazard** | junctions route worktree writes into the primary repo, which the 04:30 job copies; the junctions are also the 2026-09-15 failure mechanism (§8.2) |
| 7c | `num_predict 4096` truncation risk | **PASS** | p50 call is 1.5 s; truncation would surface as `empty_content_retries`, which the published corpus shows at ~0.6% (§8.3) |
| 7d | 120 s timeout is enough under 4-way parallel | **GAP (G2)** | 5 of 68,518 calls already exceeded 120 s at workers 1; a timeout becomes a `REJECTED_FALLBACK` row that `status` cannot distinguish from a governance block (§8.3) |
| 8 | FQL block rate 87–91 % vs the cited 71.1 ± 4.1 % | **RESOLVED — use 87–91 %** | 71.1 % has no recoverable provenance; 87–91 % triangulates with the paper's own original footnote and the April min-Mead number (§9) |
| 9a | FQL arm is in the master queue | **GAP (G5)** | `run_regen_queue_2026-09-15.bat` calls seven bats; `regen_irrigation_fql.bat` is not one of them (it ran separately at 09:48) (§10) |
| 9b | Python package versions pinned / recorded | **GAP (document only, G12)** | `requirements.txt` carries floors only; no `pip freeze` anywhere (§10) |
| 9c | Seed set 42–46 justification; flood hazard schedule varies with seed | **GAP (document only, G13)** | `flood_years.csv` is a fixed list (3, 4, 9) — seeds do not vary the hazard schedule (§10) |

---

## 2. Item 1 — command lines and the `--workers 4` change

### 2.1 Flag-by-flag comparison

Surviving primary records, `SUBMISSION_2026/reviewer_prep_2026-09-05/out/original_corpus_records_2026-09-15/results/`:

| Arm | Old record | Regen bat | Match |
|---|---|---|---|
| irrigation strict | `strict_replication_.../LAUNCH_COMMAND.txt`: `--model gemma3:4b --real --years 42 --seed S --memory-seed 42 --workers 1 --governance-mode strict --num-ctx 8192 --num-predict 4096` | identical except `--workers 4` | ✓ (except workers) |
| irrigation strict | `production_v21_42yr_seed43/reproducibility_manifest.json`: `num_years 42`, `governance_profile strict`, `thinking_mode "auto"`, `num_ctx 8192`, `num_predict 4096` | `run_experiment.py` has no `--thinking-mode`; `LLM_CONFIG.thinking_mode` default is `"auto"` (`broker/utils/llm_utils.py:70`) | ✓ |
| irrigation ungoverned | `ungoverned_v21_42yr_seed42/reproducibility_manifest.json`: `governance_profile disabled`, `thinking_mode "auto"`, `num_ctx 8192`, `num_predict 4096`, `git_commit d8a5da41…` | same runner, same flags, `--workers 4` | ✓ (except workers) |
| flood strict | `JOH_FINAL/gemma3_4b/Group_C/Run_1` manifest is the 5-key minimal schema — no `thinking_mode`. Sibling `JOH_ABLATION_DISABLED/gemma3_4b/.../Run_2`: `thinking_mode "disabled"`, `num_ctx 8192`, `num_predict 4096`, `git_commit 5a1d467f…` | `--thinking-mode disabled --num-ctx 8192 --num-predict 4096`; agents/years left at argparse defaults 100/10 (`run_flood.py:1208–1209`) | ✓ (borrowed `thinking_mode` as the bat header documents) |
| flood disabled | same manifest as above, `governance_profile disabled` | `--governance-mode disabled` + same flags | ✓ |

Two facts worth recording because a reviewer will find them:

* The published irrigation pair was produced at **two different commits** —
  `production_v21_42yr_seed43` records `db05d3a2`, `ungoverned_v21_42yr_seed42`
  records `d8a5da41`; seeds 45/46 of both arms record no commit at all (5-key
  manifest). The regeneration fixes this: all ten runs at one commit.
* Both published manifests carry `"git_dirty": true`. The regeneration will
  record `git_dirty` honestly at launch (`experiment_runner.py:145–155` samples
  it in `__init__`, not at finalize).

### 2.2 What `--workers 4` actually changes

Update semantics are **identical** between the two paths, which is the important
part. `_run_agents_parallel` (`broker/core/experiment_runner.py:1443`) returns
only after its `ThreadPoolExecutor` block exits, and the caller applies state
changes afterwards (`:591–600`); `_run_agents_sequential` (`:1180`) builds the
same list and the same caller applies it. So under both settings every agent in a
phase decides against the same pre-year state — the synchronous update the design
depends on.

Per-agent seeding is also worker-independent: `self.step_counter += 1` happens on
the submitting thread in agent order, and `seed=self.config.seed + step_id` is
bound there (`:1550–1558`). A parallel run gives agent *i* the same
`step_id`/`seed` a sequential run would.

**What does change:**

1. **`results` is appended in `as_completed` order**, so `_apply_state_changes`
   and `post_step` fire in completion order, and audit-CSV rows land in
   completion order. Byte-identity against a workers-1 run is impossible; row
   *content* is unaffected.

2. **GAP G1 — irrigation only.** `IrrigationEnvironment.execute_skill`
   (`examples/irrigation_abm/irrigation_env.py:665`) draws from `self.rng`, one
   `np.random.default_rng(seed)` created at `:134` and shared by all 78 agents:

   ```
   726:  if exploration_rate > 0 and self.rng.random() < exploration_rate:
   727:      noise = self.rng.normal(0, sigma * 2.0)
   732:      noise = self.rng.normal(0, sigma)
   ```

   `execute_skill` runs inside `process_step`, i.e. **inside the worker thread**.
   Two consequences: (a) which agent-year receives which magnitude draw becomes
   thread-scheduling dependent, so `magnitude_pct` / `is_exploration` are not
   reproducible and differ from a workers-1 run; (b) `numpy.random.Generator` is
   documented as not thread-safe. In CPython a scalar `.normal()` holds the GIL,
   so torn state is unlikely in practice, but numpy makes no such guarantee and
   there is no lock in the code (`grep -rn "Lock" examples/` returns nothing).

   Magnitude feeds `request` → Lake Mead → `drought_index` → later prompts, so it
   is not cosmetic. It does not change *which skill* is proposed or blocked, so
   IBR and EHE are not directly computed from it.

3. Not a problem, checked and cleared:
   * the audit writer is `RLock`-guarded (`broker/components/analytics/audit.py:919–924`, the F6 fix);
   * `update_agent_request` (`irrigation_env.py:639`) writes only the calling agent's own dict entry — no cross-agent aggregate;
   * per-agent prompt and validator fields are snapshotted onto the agent objects on the main thread in `pre_year` (`run_experiment.py`, `IrrigationLifecycleHooks.pre_year`), so an intra-year env mutation by agent A cannot reach agent B's prompt in the same year;
   * the memory engine's own RNG (`broker/components/memory/engines/humancentric.py:263`, `self.rng.random() < consolidate_p`) is only reached from `add_memory`, which for both domains is called from main-thread hooks and `_apply_state_changes`; `retrieve()` draws nothing;
   * the option-order shuffles are either disabled (`shuffle_options` appears in no irrigation or single-agent config; `--shuffle-skills` is not passed) or deterministically seeded per call (`broker/core/_skill_filtering.py:558–566`);
   * the retry-backoff jitter at `providers/llm_provider.py:178,191` (`random.uniform`) is on the cloud-provider path only — `gemma3:4b` routes to `_invoke_ollama_direct`, which has no jitter.

### 2.3 Exogenous stream, stated plainly

**Irrigation.** With `--real`, precipitation comes from
`ref/CRSS_DB/CRSS_DB/HistoricalData/PrismWinterPrecip_ST_NOAA_Future.csv` and
agent parameters from `ref/RL-ABM-CRSS/ALL_colorado_ABM_params_cal_1108.csv`.
The synthetic precipitation fallback is the only RNG path
(`irrigation_env.py:837`, `self.rng.normal(0, 12)`) and it does not execute
because the CSV covers 2017–2060 and the run is 2019–2060. So **a seed-42
governed run and a seed-42 ungoverned run read exactly the same precipitation
series, the same water rights and the same agent parameters, at workers 1 and at
workers 4.** What they do *not* share is the derived state — Lake Mead level,
curtailment ratio, drought index — because those are computed from the previous
year's diversions, which differ by construction as soon as the two arms choose
differently. That is endogenous divergence, not a settings defect, and it is
identical at workers 1 and workers 4.

**Flood.** `flood_years.csv` contains `3, 4, 9` and is read with
`--flood-mode fixed` (the default), so the hazard schedule is fixed, seed-
independent, and shared across every arm and every seed. Two per-year stochastic
elements use the global `random` module — `grant_available`
(`run_flood.py:291`) and per-agent flood damage (`:375, :381`) plus stochastic
recall (`:404–405`) — but all of them execute in `advance_year` and `pre_year` on
the **main thread**, in agent-dict order. `--workers 4` therefore cannot perturb
them. They *do* diverge between the governed and ungoverned arms even at workers
1, because relocated agents are skipped before the damage draw
(`run_flood.py:369–371`) so the number of draws per year depends on the
trajectory. Honest statement for the paper: the flood hazard schedule is shared
across arms; the grant and damage realisations are not, from the first year the
arms' relocation counts differ.

---

## 3. Item 2 — control-arm parity

### 3.1 Irrigation: `run_ungoverned_experiment.py` vs `run_experiment.py --governance-mode strict`

The bat uses `run_ungoverned_experiment.py`, which is the published control. It
has no `--governance-mode` argument at all (`parse_args`, `:328–341`), so it
cannot be confused with `run_experiment.py --governance-mode disabled` — the
runner §4a warns about, which still attaches
`with_custom_validators([irrigation_governance_validator])` unconditionally
(`run_experiment.py:735`). **PASS.**

Parity was checked construction-line by construction-line
(`run_experiment.py:620–760` vs `run_ungoverned_experiment.py:125–300`). Identical:
prompt template (`config/prompts/irrigation_farmer.txt`, byte-identical to
d8a5da41), skill registry, `create_profiles_from_data` with the same two CSVs and
`np.random.default_rng(seed)`, persona magnitude assignment, `WaterSystemConfig(seed=seed)`,
`coupling_contract_active` read through the same getter, `HumanCentricMemoryEngine`
with the same eleven arguments including `seed=args.memory_seed`,
`TieredContextBuilder` with the same arguments, the feedback dashboard, the
performance tuner call, `ReflectionEngine` with the same four arguments, and the
same `create_legacy_invoke` LLM entry point (`:65` and `:57` respectively).

Differences, exhaustively:

| Difference | Effect |
|---|---|
| `.with_governance(args.governance_mode, …)` vs `.with_governance("disabled", …)` | the experimental variable |
| `.with_custom_validators([irrigation_governance_validator])` vs `([])` | the experimental variable |
| `UngovernedLifecycleHooks.post_step` omits `update_consecutive_tracker()` | inert — the consecutive-cap validator is only enabled under `--pilot-phase C/D` (`run_experiment.py:530–536`), which neither bat passes |
| governed calls `reset_consecutive_tracker()` | inert, same reason |

Mock runs confirm the two arms write byte-identical `simulation_log.csv` and
`irrigation_farmer_governance_audit.csv` headers and identical
`reproducibility_manifest.json` key sets (122 keys each). The "ungoverned runner
has a thinner manifest" suspicion is **refuted at this commit**.

### 3.2 GAP G4 — `--rebalance-clusters` asymmetry across the Fig-2 arms

* `regen_irrigation_strict.bat` — flag not passed → real CRSS cluster labels.
* `regen_irrigation_ungoverned.bat` — the runner has no such flag → real CRSS labels.
* `regen_irrigation_fql.bat` — **passes `--rebalance-clusters`** → clusters forced
  to 50 % aggressive / 30 % forward-looking / 20 % myopic
  (`run_fql_baseline.py:473–482`), which also changes `persona_scale`,
  `magnitude_*` and `exploration_rate` per agent.

So the LLM arms and the FQL baseline in Fig 2 run on **different persona mixes**.
This matches the published arms (the FQL runner's own docstring gives
`--rebalance-clusters` as the canonical invocation, and `fql_nogov_2026-08.md`
confirms the shipped `fql_raw` used it), so it is not a regression — but it is
an unmatched condition sitting inside one figure, and a hostile reviewer will
ask. Decide before launch whether to (a) keep it and state it in the caption/SI,
or (b) add a matched no-rebalance FQL run (CPU, minutes) as a robustness check.

### 3.3 Flood: what `--governance-mode disabled` disables

From `examples/single_agent/agent_types.yaml` (`household.governance.disabled`):

```yaml
disabled:
  thinking_rules: []
  identity_rules: []
```

`strict` carries four `thinking_rules` (`extreme_threat_block` ERROR,
`low_coping_block` WARNING, `relocation_threat_low` ERROR,
`elevation_threat_low` ERROR) and one `identity_rule` (`elevation_block` ERROR)
— verified byte-identical between the surviving
`JOH_FINAL/gemma3_4b/Group_C/Run_2/config_snapshot.yaml` and e75e390c's in-tree
config.

What `disabled` does **not** turn off, and this is the honest framing: the
validator pipeline still runs, the skill-registry preconditions still apply, the
parser and the format-retry loop are unchanged, and the audit CSV is written with
the same columns. It is a *rule-set* ablation, not a pipeline ablation. The
surviving `JOH_ABLATION_DISABLED/.../Run_1/audit_summary.json` shows
`validation_errors: 0` with `structural_faults_fixed: 5` — i.e. zero rule firings
but the format-repair layer still active, exactly as expected.

`advise`/soft-rule feedback is not in play: `governance.advise_mode` appears in
neither production config, so the advise channel is off in both flood arms.
Fallback is active in both arms (see §8.3).

---

## 4. Item 3 — what is actually sent to Ollama, and what is recorded

### 4.1 The resolved call

At import, `_load_global_config()` (`broker/utils/llm_utils.py:143–189`) looks for
`Path.cwd()/agent_types.yaml` and then `broker/utils/agent_types.yaml`. Neither
exists (verified). So the global `LLM_CONFIG` starts at the dataclass defaults:
`temperature=None, top_p=None, top_k=None, num_predict=-1, num_ctx=16384,
max_retries=2, timeout=120, thinking_mode="auto"`.

The runners then mutate it from the CLI: `num_ctx`/`num_predict` in all three
runners; flood additionally sets `thinking_mode` (`run_flood.py:1451`) and would
set temperature/top-p/top-k if the flags were passed — the bats do not pass them.

The per-agent-type call does **not** use the `llm_invoke` handed to
`runner.run(...)`. `_run_agents_parallel`/`_sequential` call
`self.get_llm_invoke(agent_type)` (`experiment_runner.py:216–238`), which merges
`shared.llm` + `global_config.llm` + `<type>.llm_params` from the domain YAML via
`AgentTypeConfig.get_llm_params` (`broker/utils/agent_config.py:1964–1975`) and
passes the result as `overrides`, which then `update()`s the params dict
(`llm_utils.py:405`).

Net effect per call (`_invoke_ollama_direct`, `llm_utils.py:255–300`):

| | irrigation | flood |
|---|---|---|
| YAML `global_config.llm` | `num_ctx 8192`, `num_predict 4096`, `max_retries 2` — **no sampling params** | `temperature 0.8`, `top_p 0.9`, `top_k 40`, `num_ctx 8192`, `num_predict 4096`, `max_retries 2` |
| Options actually POSTed | `{num_predict: 4096, num_ctx: 8192}` | `{num_predict: 4096, num_ctx: 8192, temperature: 0.8, top_p: 0.9, top_k: 40}` |
| Top-level `think` | not set (`thinking_mode="auto"` → `get_think_flag()` returns `None`) | `false` (`--thinking-mode disabled`) |
| `format` | `None` — JSON mode is globally disabled | same |

So the two domains run at different sampling settings. That is inherited from the
published corpus, not introduced here, but it should be stated once in the
methods rather than left for a reviewer to discover: irrigation uses the model's
own defaults, flood pins 0.8 / 0.9 / 40.

### 4.2 GAP G8 — no Ollama seed is ever sent

`grep -n "seed" broker/utils/llm_utils.py` returns **nothing**. There is no
`seed` key in `LLMConfig`, in `to_ollama_params()`, or in the options dict built
by `_invoke_ollama_direct`. The run `--seed` drives: the global `random`/`numpy`
seeding at runner start, `create_profiles_from_data`'s generator,
`WaterSystemConfig(seed=…)` → `IrrigationEnvironment.rng`, the per-step
`seed=config.seed + step_id` recorded in the audit trace, and (via
`--memory-seed`, separately) the memory engine's consolidation RNG. **It does not
seed token sampling.** Two runs at the same `--seed` are therefore not expected to
be byte-identical even before the workers question — which is consistent with the
project's existing position (`.baselines/BASELINE_HASHES.md`; real-LLM
verification uses N-seed aggregate statistics, not byte-identity).

### 4.3 GAP G7 — the manifest records the wrong sampling params

`_collect_reproducibility_metadata` (`broker/core/experiment_runner.py:792`,
section "3. LLM config snapshot") reads the **global** `LLM_CONFIG`:

```python
metadata["thinking_mode"] = LLM_CONFIG.thinking_mode
metadata["temperature"]   = LLM_CONFIG.temperature
metadata["top_p"]         = LLM_CONFIG.top_p
metadata["num_ctx"]       = LLM_CONFIG.num_ctx
metadata["num_predict"]   = LLM_CONFIG.num_predict
```

For flood, `LLM_CONFIG.temperature` is still `None` (the 0.8 lives only in the
per-type overrides), so the manifest records `null`. `top_k`, `timeout` and
`max_retries` are not recorded at all. This is confirmed against the published
corpus, where the same directory contains both halves of the contradiction:

* `JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_2/reproducibility_manifest.json` → `"temperature": null, "top_p": null`
* `JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_2/config_snapshot.yaml:26-28` → `temperature: 0.8 / top_p: 0.9 / top_k: 40`

**Decision: do not fix the code before launch.** The fix is small (five lines in
one function), but it is inside `broker/`, it is governance-adjacent under the
review gate, and it would move HEAD off `e75e390c`, invalidating every directory
name in the queue and every "regenerated at e75e390c" statement already written
into the bats and the plan. The truth is already recoverable from
`config_snapshot.yaml`, which every run writes
(`experiment_runner.py:698–727`) and which the published corpus also carries. The
reviewer-proofing action is therefore documentation plus the external record in
G3, and the code fix goes on a branch after the corpus lands.

One related item worth knowing: `config_snapshot.yaml` injects only the resolved
**model** from the CLI (`:714`). If a CLI `--num-ctx` ever differed from the
YAML's, the snapshot would record the YAML value. In this queue they are both
8192/4096, so the snapshot is accurate.

---

## 5. Item 4 — GAP G3, the unrecorded runtime environment

Read from the live system and from `C:/Users/wenyu/AppData/Local/Ollama/server*.log`:

| Fact | Value | Recorded in any run artifact? |
|---|---|---|
| Ollama version | **0.34.0** (running server started 2026-09-15 09:53:32) | no |
| previous version | **0.33.3** on 2026-09-10 (`server-4.log`) — upgraded ~2026-09-13 (`upgrade.log`) | no |
| `OLLAMA_NUM_PARALLEL` | **4** in the running server; **1** in every rotated log back to 2026-09-10 | no |
| `OLLAMA_KV_CACHE_TYPE` | **q8_0** — in effect in *every* server session back to 2026-09-10 | no |
| `OLLAMA_FLASH_ATTENTION` | **true**, same span | no |
| `OLLAMA_CONTEXT_LENGTH` | 64000 (server default; per-request `num_ctx: 8192` overrides) | no |
| `OLLAMA_MAX_LOADED_MODELS` / `OLLAMA_KEEP_ALIVE` / `OLLAMA_MAX_QUEUE` | 1 / effectively infinite / 512 | no |
| GPU / driver | NVIDIA GeForce RTX 4080 SUPER, driver 591.86, 16376 MiB, 13273 MiB free | no |
| model | `gemma3:4b`, id `a2af6cc3eb7f`, 3.3 GB | partially — `model_digest` falls back to `modified_at` (the published manifests all record `"2026-01-29T12:50:07.405621-05:00"`, a timestamp, not a digest) |
| Python / packages | 3.14.0; numpy 2.4.2, pandas 2.3.3, requests 2.32.5 | python only |

**Why this matters.** `OLLAMA_KV_CACHE_TYPE=q8_0` quantises the KV cache and
`OLLAMA_FLASH_ATTENTION=1` changes the attention kernel; both change generation
numerics. The logs prove they have been on since at least 2026-09-10, which
covers the September replication runs — but the published April/May 2026 corpus
predates every surviving log, so **whether the published corpus ran with
quantised KV cache is unknowable**. Say that in the SI rather than let a
reviewer ask. The same applies to the 0.33.3 → 0.34.0 upgrade sitting between the
September replications and this regeneration.

**Minimal fix, no code change.** Each bat already writes `LAUNCH_COMMAND.txt`
before the run. Add three lines in the same block, per seed:

```bat
ollama --version                                             >> "!OUT!\LAUNCH_COMMAND.txt"
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader >> "!OUT!\LAUNCH_COMMAND.txt"
set OLLAMA_                                                  >> "!OUT!\LAUNCH_COMMAND.txt"
ollama list ^| findstr gemma3:4b                             >> "!OUT!\LAUNCH_COMMAND.txt"
```

(`set OLLAMA_` prints every `OLLAMA_*` variable visible to the batch process.
Note the caveat below.) A one-off `environment.json` written next to the queue at
launch would also do, but per-run is better: it survives directory moves and sits
beside the manifest the reviewer will read.

**Caveat on `set OLLAMA_`:** it prints the *batch process's* environment, which is
not necessarily the *server's*. The server's true configuration is the "server
config" line in `C:/Users/wenyu/AppData/Local/Ollama/server.log`. The most honest
record is to copy that one line into the run directory at launch:

```bat
findstr /C:"server config" "%LOCALAPPDATA%\Ollama\server.log" >> "!OUT!\LAUNCH_COMMAND.txt"
```

---

## 6. Item 5 — config identity vs the old-corpus commits

Fingerprint method: the published manifests record
`config_hash = sha256(agent_types.yaml)[:12]`. Verified the method reproduces:
`git show d8a5da41:examples/irrigation_abm/config/agent_types.yaml` hashes to
`75ad0628600f`, exactly the value in `ungoverned_v21_42yr_seed42` and
`production_v21_42yr_seed43`.

| File | old | e75e390c | diff |
|---|---|---|---|
| `examples/irrigation_abm/config/agent_types.yaml` | `75ad0628600f` | `baa3e98b49d3` | +108 / **−0** |
| `examples/single_agent/agent_types.yaml` | `5b3959996135` | `3fd510c6ce62` | +65 / **−0** |
| `examples/irrigation_abm/config/prompts/irrigation_farmer.txt` | — | — | **zero diff** |
| `examples/single_agent/config/prompts/household.txt` | — | — | **zero diff** |
| `examples/single_agent/skill_registry.yaml` | — | — | **zero diff** |
| `examples/irrigation_abm/config/skill_registry.yaml` | — | — | +20 / −0 |
| `examples/irrigation_abm/config/policies/financial_prudence.yaml` | — | — | **zero diff** |

Classification:

* **Inert.** `shared.template_vars` (irrigation) is read only by
  `broker/tools/validate_prompt.py:798–799`, a lint tool. The skill-registry
  additions (`category` / `intensity` / `reversibility`, "Phase 6O-B action
  taxonomy") are consumed only by `DomainPack.action_taxonomy()` →
  `broker/tools/readiness_report.py`; no validator, skill-filter or eligibility
  path reads them, and every `description` — the only field that reaches the
  prompt menu — is unchanged.
* **Affects only new arms.** Both `grounded_v1` blocks. They are additive; the
  `strict` and `disabled` blocks are byte-unchanged in both domains.
* **Affects behaviour, confined to audit/diagnostic columns.** Audit schema
  version 1 → 2 plus a `*.schema.json` sidecar; `rules_*_hit` / `social_*` /
  `cog_*` columns changing from placeholder zeros to real values (Phase 6C W7/W8,
  already logged as "paper impact: zero" in `broker/INVARIANTS.md`);
  `failed_rules` strings `"Unknown"` → `"output_schema_violation"` /
  `"precondition_violation"`; the F5 retry-magnitude WARNING flag; the F1/F4
  ABORTED sentinel rows (an exception-killed agent-step used to vanish silently
  and now emits a row). None of these is read by IBR or EHE, which use
  `proposed_skill`, `final_skill`, `status`, `wsa_label`/`aca_label`.

Instance-level cross-check against the surviving `config_snapshot.yaml` files —
**33 of them, all flood, zero irrigation.** Flood strict
(`JOH_FINAL/gemma3_4b/Group_C/Run_2`) differs from e75e390c's in-tree strict
config in exactly two cosmetic places: the snapshot carries the resolved
`gemma3:4b` where the in-tree YAML carries the `"command-line-override"`
placeholder, and `household.psychological_framework: pmt` is explicit in-tree
(made so by Phase 6J-A) where the older snapshot inferred it. Thinking rules and
identity rules are byte-identical. Flood disabled differs only in the model
placeholder.

**GAP G10 — irrigation input provenance.** `ref/CRSS_DB/` is gitignored
(`.gitignore:131`), so byte-identity with the file that produced the
d8a5da41-era corpus cannot be proven from git. The file on disk today
(`PrismWinterPrecip_ST_NOAA_Future.csv`, 44 × 9, 2017–2060) has zero blank cells,
and every file under `ref/CRSS_DB/` carries a 2026-02-24 mtime from a single copy
event — so it has not moved between the September runs and today. That bounds the
risk but does not close it. Record the SHA-256 of both input CSVs in the
per-run environment record from §5; that costs nothing and closes the question
for every future run.

**Residual, disclose rather than claim verified:** three areas were accepted on
their own commits' audit trails rather than re-derived —
`broker/core/agent_initializer.py` (spot-checked by commit stat), the decider
registry byte-identity claim in `a0851c58`, and `f0159053`'s framework-parameter
routing fix (whose own audit argues the three cognitive frameworks share one
VL–VH ordinal scale so label comparison is numerically identical). Also:
`broker/INVARIANTS.md`'s own cross-version comparability log stops at 2026-05-10,
so everything after that date — including the whole flood range, since
`5a1d467f` is dated 2026-05-30 — is outside the repo's own ledger.

---

## 7. Item 6 — output schema, verified by mock run

Five runs at e75e390c into the scratch directory, all exit 0.

**Artifacts written.** Both irrigation runners and both flood runners write the
same twelve-file set: `simulation_log.csv`, `<type>_governance_audit.csv` +
`.schema.json`, `reproducibility_manifest.json`, `run_integrity.json`,
`audit_summary.json`, `governance_summary.json`, `config_snapshot.yaml`,
`validator_health.csv` + `_by_agent_type.csv`, `raw/*_traces.jsonl`, and (irrigation
only) `reflection_log.jsonl`. `run_flood_rulebased.py` writes only
`simulation_log.csv` and a plot — it has no governance pipeline, which is
expected, but it means the rule-based arm carries **no manifest**; T0-7's own note
already flagged that the three previously-published rule-based runs had none
either. If Fig 3 cites the rule-based column, write a one-paragraph provenance
note beside it by hand.

Audit filenames match the canonical loaders exactly:
`irrigation_farmer_governance_audit.csv` (= `SUBMISSION_2026/decomposition/_loader.py`)
and `household_governance_audit.csv` (= `reviewer_prep_2026-09-05/scripts/_common.py`).

**Arm parity — PASS.** Governed and ungoverned irrigation emit byte-identical
`simulation_log.csv` and audit headers and identical 122-key manifests. Flood
strict and disabled likewise (83-key manifests). Fig 2's paired comparison and
Fig 3's contrast are not at risk of a schema mismatch between arms.

**Columns present.** `simulation_log.csv` (irrigation, both arms):
`agent_id, year, cluster, basin, yearly_decision, wsa_label, aca_label, request,
diversion, water_right, curtailment_ratio, drought_index, shortage_tier,
lake_mead_level, mead_storage_maf, has_efficient_system,
below_minimum_utilisation, utilisation_pct, magnitude_pct, magnitude_fallback,
is_exploration, memory` — every column `_loader.py` and
`fql_comparison_metrics.py` read.

`simulation_log.csv` (flood, both arms): `agent_id, year, cumulative_state,
yearly_decision, proposed_skill, governance_intervention, failed_rules,
hallucination_types, retry_count, threat_appraisal, coping_appraisal, elevated,
has_insurance, relocated, trust_insurance, trust_neighbors, memory` — every
column `gen_fig3_case2_flood.py` reads on its live path.

Audit CSVs carry `proposed_skill, final_skill, status, fallback_activated,
retry_count, format_retries, validated, failed_rules, …, llm_retries, llm_success`
in both domains and both arms.

**Names that do not exist as columns anywhere in the repo:** `fql_raw_skill`,
`fql_action`, `fql_blocked` are not emitted by any runner. The FQL baseline
reuses the standard `yearly_decision` column and `gen_fig2` remaps values through
a local Python dict. (`fql_blocked` *does* exist in the FQL runner's own
`simulation_log.csv` — see §9 — but not in the governed/ungoverned schema.) Treat
the three as non-existent for the LLM arms rather than missing.

**Open item, and the one thing mock cannot settle.** `construct_WSA_LABEL`,
`construct_ACA_LABEL` and `construct_TP_LABEL` are **absent from every mock-mode
audit CSV**. Root cause found: the audit fieldnames are the **union of keys
actually observed across the run's rows** (`broker/components/analytics/audit.py`,
`compute_csv_fieldnames`; `construct_<KEY>` columns are built from reasoning keys
matching `_CONSTRUCT_SUFFIXES` at `:481`). The mock model never emits
`WSA_LABEL`/`TP_LABEL`, so all sixteen mock agent-years are `status=REJECTED`
("Missing constructs …") and the columns are never created. This is a mock
artifact, not a schema regression — the whole governance layer is built around
those keys and the published corpus's reviewer-prep scripts read them
successfully. But it was not empirically confirmed at this commit.

**GAP G11.** Because the column set is run-dependent, a seed whose run produced
no parseable construct at all would silently drop the column and `KeyError` the
figure script. Pre-register a column-presence check as part of the post-run gate,
not just a row count.

**Fig 2 / Fig 3 readiness.** Fig 3 regenerates from `simulation_log.csv` alone —
only the directory re-pointing in `.research/experiment_plan_framework_paper_2026-09-06.md`
§0b is needed. Fig 2's stacked-area and demand-ratio panels likewise; its pie
matrix reads `audit_df['construct_WSA_LABEL']` and depends on the run producing
non-REJECTED rows.

---

## 8. Item 7 — capacity, truncation, timeout

### 8.1 GPU memory — PASS

`gemma3:4b` Q4_K_M is 3.3 GB of weights. With `OLLAMA_NUM_PARALLEL=4` Ollama
allocates four KV slots; at `num_ctx 8192` with `q8_0` quantised cache and
gemma3's interleaved sliding-window attention, the four slots come to roughly
1.5–2.5 GB, plus ~1 GB of compute buffers — call it 6–7 GB against 13.27 GB free.
`OLLAMA_MAX_LOADED_MODELS=1` prevents a second model being resident.
`OLLAMA_KEEP_ALIVE` is effectively infinite, so the model will not be evicted
mid-queue. **Verify empirically one minute after launch** with `ollama ps`: the
PROCESSOR column must read 100 % GPU and the CONTEXT column should reflect 4 ×
8192, not 64000 × 4. If `OLLAMA_CONTEXT_LENGTH=64000` ends up being applied per
slot, memory will be far higher than this estimate — that is the single check
worth watching.

### 8.2 Disk and backup — PASS, with a hazard to write down

C: 1885 GB free, G: 1791 GB free. The nightly `WAGF_Results_Backup_GDrive` task
(04:30 daily, last result 0) runs `backup_wagf_to_gdrive.ps1`, which robocopies
`governed_broker_framework\examples\irrigation_abm\results` and
`...\single_agent\results` — **and the worktree's results directories are
junctions pointing at exactly those paths**:

```
wagf-main-runs\examples\irrigation_abm\results  → ReparsePoint → governed_broker_framework\examples\irrigation_abm\results
wagf-main-runs\examples\single_agent\results    → ReparsePoint → governed_broker_framework\examples\single_agent\results
wagf-main-runs\ref\CRSS_DB                      → ReparsePoint → governed_broker_framework\ref\CRSS_DB
```

So the new corpus is covered by the nightly job, and the job is copy-only
(`robocopy /E`, no `/MIR`), so a source deletion cannot propagate.

**The hazard:** those junctions are the 2026-09-15 failure mechanism. Any
`git worktree remove`, `rm -rf`, or cleanup script pointed at
`wagf-main-runs` will follow them and delete the primary repo's results. Before
launch, write that warning into a `DO_NOT_DELETE.txt` at the worktree root and
into the queue bat's header, and make the post-run cleanup step
"remove the junctions first, then the worktree".

Note also that `$worktreePairs` in the backup script covers only
`reservoir_control` and `vaccination_demo` from the worktree — correct as written,
because everything else routes through the junctions, but it means the script
silently depends on the junctions existing. If the junctions are ever replaced by
real directories, the backup stops covering the corpus with no error.

### 8.3 GAP G2 — the 120 s timeout is the reviewer-facing integrity risk

**Where it is set.** `LLMConfig.timeout = 120` (`llm_utils.py:54`);
`get_timeout(model)` returns it because `gemma3:4b` matches none of
`large_model_patterns`; `_invoke_ollama_direct` reads
`LLM_CONFIG.get_timeout(model)` at `:296`. **It cannot be raised from the domain
YAML**: `_load_global_config()` never finds an `agent_types.yaml` (§4.1), and
`_invoke_ollama_direct` reads the global `LLM_CONFIG`, not the per-type `params`
dict that the YAML's `timeout` key would land in. So `timeout: 600` in
`agent_types.yaml` would be silently ignored.

**What happens on a timeout.** `requests.exceptions.Timeout` →
`return "", LLMStats(success=False)` (`llm_utils.py:331–333`) → the invoke loop
sees empty content, increments `empty_content_retries`, appends a space to the
prompt and retries once (`max_retries: 2` = two attempts total) → if the second
also fails, `return "", LLMStats(success=False, empty_content_failure=True)`
(`:475`). Downstream the parser produces no usable choice, so
`skill_broker_engine.py:948–960` takes the `is_generic_fallback` branch:
`approval_status = "REJECTED_FALLBACK"`, `outcome = UNCERTAIN`,
`fallback_activated = True`, and the registry default skill is executed —
`maintain_demand` for irrigation, `do_nothing` for flood.

**Why that is a science problem, not just an ops problem.** The reviewer-prep
scripts read `status` for `REJECTED` / `REJECTED_FALLBACK`. A timeout therefore
lands in the same bucket as a genuine governance block unless the analysis also
reads `fallback_activated` / `llm_success`. Under 4-way parallelism per-call
latency rises, so the timeout rate rises, so the governed arm accumulates
manufactured "rejections" — a directional bias in favour of the paper's own
claim. That is exactly the kind of thing a hostile reviewer is looking for.

**How big is the risk, empirically.** From
`C:/Users/wenyu/AppData/Local/Ollama/server-5.log`, 68,518 `/api/generate` calls
across the 2026-09-06→10 runs at `--workers 1`:

```
n=68518  min=0.01s  p50=1.5s  p90=2.4s  p95=2.6s  p99=3.7s  max=153.0s
  >30s:  29 (0.042%)
  >60s:  24 (0.035%)
  >110s: 16 (0.023%)
  >120s:  5 (0.007%)
```

The body of the distribution is far from the limit; the risk lives entirely in a
thin tail (0.04 % of calls take > 30 s, presumably long generations toward
`num_predict 4096` or a model load). Under 4-way sharing, per-call latency
roughly doubles, so that tail crosses 120 s much more often — a plausible range
is 0.05–0.3 %, i.e. tens of calls across the irrigation arms. For scale, the
published `production_v21_42yr_seed42` corpus had 20 format retries and 19
structural faults fixed over 3,276 traces (≈ 0.6 %), so a timeout rate in that
range would be comparable to the existing repair rate rather than swamping it.

**Recommendation (choose one before launch):**

* **Preferred, zero risk to the commit:** keep `--workers 4` and pre-register a
  post-run integrity gate — for each seed, compute
  `mean(fallback_activated)` and `mean(llm_success == False)` from the audit CSV
  and require both to sit at or below the published corpus's ≈ 0.6 % repair rate.
  Any seed over it is re-run, not analysed. The columns are already written
  (`fallback_activated`, `retry_count`, `llm_retries`, `llm_success` — confirmed
  present in the mock audit header), so this costs nothing but a short script.
* **Conservative:** run the irrigation arms at `--workers 2`. Halves the latency
  inflation, keeps most of the speed-up, and reduces G1's exposure too.
* **Not recommended without a review round:** raising `LLMConfig.timeout` in
  `broker/utils/llm_utils.py`. It is a one-line change but it moves HEAD off
  `e75e390c`.

**Truncation (`num_predict 4096`) — PASS.** A truncated response that still
contains parseable JSON parses normally; one that does not surfaces as
`empty_content_retries` and then the same `REJECTED_FALLBACK` path, so the gate
above covers it. The published corpus's low repair rate (≈ 0.6 %) indicates 4096
is not binding for `gemma3:4b` at these prompt lengths.

---

## 9. Item 8 — the FQL block-rate anomaly, resolved

**Use 87–91 %.** Per-seed block rate from the regenerated
`fql_raw_e75e390c/seed{42..51}` (`fql_blocked == True` over all 3,276 agent-year
rows, where `fql_blocked ≡ yearly_decision != fql_raw_skill`):

```
42: 89.96   43: 90.42   44: 90.87   45: 89.44   46: 87.24
47: 89.07   48: 90.20   49: 90.54   50: 90.48   51: 88.64
```

**The 71.1 ± 4.1 % figure has no recoverable provenance.** It comes from
`examples/irrigation_abm/experiments/fql_nogov_2026-08.md:43,98` and
`paper/nature_water/FQL_BASELINE_NOTE_2026-08-06.md:54–56`, computed on 2026-08-06
against whatever the gitignored `examples/irrigation_abm/results/fql_raw/`
contained that day. It is **not** a metric-definition mismatch — the same column
and the same denominator were used. The same note already flags the discrepancy
against the paper's own footnote and leaves it unresolved: "Extended Data Table 1's
footnote says 84–89 % of FQL actions were rejected. Pooled over ten seeds… 71.1 %…
the two figures should not both circulate."

**Everything that could have caused a real shift is ruled out.** `fql.py`: zero
commits since 2026-01-30. `run_fql_baseline.py`: one docstring-only commit
(`7c55b3b6`, 2026-08-06). `irrigation_validators.py`: last changed 2026-02-15.
`examples/irrigation_abm/config/`: no commits since before 2026-07-15.
`ref/CRSS_DB/`: filesystem-unchanged since 2026-02-24.
`--rebalance-clusters`: used in both the old and the new run. The FQL kernel is
fully seeded (`run_fql_baseline.py:446–447`, per-agent
`np.random.default_rng(seed+i)` at `:134`), so it is deterministic given fixed
code, data and flags — "noise" is not an available explanation.

**Two independent corroborations.** (i) The only recoverable historical copy,
`git show 4fbdbc33^:examples/irrigation_abm/results/fql_raw/seed{42,43,44}/simulation_log.csv`
(committed 2026-02-22), gives 89.38 / 83.52 / 79.70 % on the same metric — near the
new numbers, far from 71.1 %. The paper's own "84–89 %" footnote was traced by
`git log -S` to `b8208b4f` (2026-02-22 18:45), whose diff cites those exact files.
(ii) The regenerated 5-seed min Lake Mead is 998.1 ± 2.2 ft against the April
"B2 audit fix" canonical 999.3 ± 4.7 ft — a 1.2 ft agreement, well inside the SD.

**Open, secondary.** Demand ratio computed with the canonical formula
(`fql_comparison_metrics.py:304–306`) gives 0.413 ± 0.002 for e75e390c against
0.352 in the current draft. That does not reconcile as cleanly as min-Mead does
and should be re-checked before Fig 2 ships. The single decisive action: run
`examples/irrigation_abm/analysis/fql_comparison_metrics.py` against
`fql_raw_e75e390c/seed{42..51}` and diff its whole output table against the
current SI FQL row, cell by cell — that settles both the block-rate footnote and
the demand-ratio cell in one pass.

---

## 10. Item 9 — everything else a hostile reviewer would reach for

* **GAP G5 — the FQL arm is not in the master queue.**
  `run_regen_queue_2026-09-15.bat` calls seven bats; `regen_irrigation_fql.bat` is
  not among them. It ran separately at 09:48 and completed. Fig 2 needs it, so
  nothing is missing from the data — but the queue's own header says "seven arms"
  and the plan's §0b list omits FQL entirely. Add a line to both so the provenance
  chain does not have a hole where a reviewer expects the baseline.

* **GAP G13 — the flood hazard schedule does not vary with seed.**
  `examples/single_agent/flood_years.csv` is the literal list `3, 4, 9`, read with
  `--flood-mode fixed`. All five "seeds" therefore share one flood schedule; the
  seeds vary agent initialisation, the damage/grant draws, and LLM sampling only.
  That is defensible (it isolates behavioural variance from hazard variance) but
  it must be said, or a reviewer will read "5 seeds" as five hazard realisations.

* **GAP G12 — no package version record.** `requirements.txt` carries floors only
  (`numpy>=1.24`, `pandas>=2.0`, `requests>=2.28`). The manifest records
  `python_version` and nothing else. Add `pip freeze` output to the per-run
  environment record from §5 — one line in the bat.

* **Seed set 42–46.** Nothing in the plan or the bats states *why* five
  consecutive integers starting at 42. It is a convention, and that is a fine
  answer, but write it down once: seeds are replicates, chosen before any result
  was seen, and the set was fixed by the original v21 corpus. Say so in the SI
  rather than leaving it to look post-hoc.

* **Run-naming.** Output directories embed `e75e390c` per the CLAUDE.md
  convention, which is right, but **both figure scripts read the old names**
  (`production_v21_42yr_seed{s}`, `ungoverned_v21_42yr_seed{s}`,
  `JOH_FINAL/<model>/Group_C`, `JOH_ABLATION_DISABLED/<model>/Group_C_disabled`,
  `rulebased`, `Run_1..Run_5`). The re-pointing constants are already enumerated
  in `.research/experiment_plan_framework_paper_2026-09-06.md` §0b. Note in
  particular that the flood bats write `Run_42..Run_46` while the scripts expect
  `Run_1..Run_5` — that is a mapping change, not just a directory change.

* **Row counts will not match the old corpus, for a good reason.** The published
  flood arms record 857 (`JOH_FINAL/gemma3_4b/Group_C/Run_1`) and 984
  (`JOH_ABLATION_DISABLED/.../Run_1`) traces against a 100 × 10 grid. That is
  relocation attrition — a relocated agent leaves `active_agents` and stops
  producing rows — not silent dropping. The integrity check must therefore be
  "rows = agents × years minus relocation attrition", not "rows = 1000". Separately,
  the F1/F4 fixes mean an exception-killed step now emits an ABORTED sentinel row
  where the old corpus dropped it silently, so a small row-count difference in the
  other direction is the new run being *more* complete, not less.

* **The acceptance bands were computed on the old, partly-different corpus.**
  `r7_seed_robustness.csv`'s means and SDs come from runs at `--workers 1`, at
  mixed commits, with partly different denominators, and (for flood Run_1..3) with
  the documented +20 % injected-memory backfill. If a regenerated arm lands
  outside its ±2 SD band, that is informative but not decisive, and the
  confounders should be named in the same sentence as the miss.

---

## 11. Ordered actions

### Must fix before launch

1. **G1 — decide the worker count for the irrigation arms, and record the
   decision.** Either (a) keep `--workers 4` and state in the methods that the
   per-agent magnitude draw order is scheduling-dependent, that the published
   corpus ran at `--workers 1`, and that the acceptance bands are therefore not
   worker-matched; or (b) run irrigation at `--workers 1` or `2`. Flood is
   unaffected either way and can stay at 4. Evidence: `irrigation_env.py:665,
   726–752`.
2. **G2 — pre-register the timeout/fallback integrity gate** (or drop to
   `--workers 2`). Concretely: for each finished seed, compute
   `mean(fallback_activated)` and `mean(llm_success == False)` from
   `<type>_governance_audit.csv`; require ≤ 0.6 %; re-run any seed that exceeds
   it. Write the threshold down *before* launch so it is not chosen after seeing
   the numbers.
3. **G3 — add the environment record to each bat** (four to five `>>` lines per
   seed, no code change): `ollama --version`, the server-config line from
   `%LOCALAPPDATA%\Ollama\server.log`, `nvidia-smi --query-gpu=name,driver_version`,
   `pip freeze`, and SHA-256 of the two CRSS input CSVs.
4. **G4 — resolve the `--rebalance-clusters` asymmetry** between the FQL baseline
   and the LLM arms in Fig 2: either state it in the caption/SI, or add a matched
   no-rebalance FQL run (CPU, minutes).
5. **G5 — put the FQL arm into the queue's documented arm list** (and into
   `.research/experiment_plan_framework_paper_2026-09-06.md` §0b), recording that
   it ran separately at 09:48 at `e75e390c`.
6. **Write the junction warning** into the worktree root and the queue bat header
   before anything is launched (`§8.2`).
7. **One pre-flight check, one minute after launch:** `ollama ps` must show 100 %
   GPU and a CONTEXT consistent with 4 × 8192. If it shows 64000-scaled contexts,
   stop and set `OLLAMA_CONTEXT_LENGTH=8192` before restarting.

### Fix during the run (no code change)

8. Watch `fallback_activated` / `llm_success` per completed seed against the gate
   from action 2; do not wait until all five seeds finish.
9. After the first irrigation seed completes, check that the audit CSV contains
   `construct_WSA_LABEL` and `construct_ACA_LABEL` (G11) — the column set is the
   union of observed keys, so its absence would break Fig 2's pie matrix and is
   cheaper to catch at seed 1 than at seed 5.
10. Run `examples/irrigation_abm/analysis/fql_comparison_metrics.py` against
    `fql_raw_e75e390c/seed{42..51}` and diff the full table against the current SI
    FQL row — settles both the 87–91 % footnote and the 0.413-vs-0.352 demand-ratio
    cell (§9).
11. Confirm the 04:30 backup picks up the new directories on the first night
    (`backup_wagf_last.log`, `rc` values).

### Document only (SI / methods / provenance appendix)

12. **G7** — `reproducibility_manifest.json` records `temperature`/`top_p` from the
    global config, so the flood arm's manifest says `null` while 0.8 / 0.9 / 40 are
    sent. The true values are in `config_snapshot.yaml` in the same directory; the
    published corpus has the identical defect. Point reviewers at the snapshot.
    Fix the code on a branch after the corpus lands
    (`broker/core/experiment_runner.py`, `_collect_reproducibility_metadata`,
    section "3. LLM config snapshot").
13. **G8** — no Ollama `seed` is sent; the run seed governs agent initialisation,
    personas, magnitude noise, memory consolidation and the flood draws, not token
    sampling. Repeat runs are compared by N-seed aggregate statistics, never by
    byte-identity.
14. **G9** — `config_hash` differs from the published corpus
    (`75ad0628600f → baa3e98b49d3`; `5b3959996135 → 3fd510c6ce62`); both diffs are
    additive (`+108/−0`, `+65/−0`) and the `strict` and `disabled` rule sets are
    byte-unchanged.
15. **G10** — `ref/CRSS_DB/` is not version-controlled; byte-identity with the
    d8a5da41-era input cannot be proven. State it, and close it going forward with
    the hashes from action 3.
16. **Audit schema 1 → 2** plus the changed diagnostic columns (`rules_*_hit`,
    `failed_rules` strings, the WARNING-level magnitude-cap flag, ABORTED sentinel
    rows), so a byte-diff against the old corpus is not misread as a governance
    difference.
17. **Runtime numerics disclosure** — `OLLAMA_KV_CACHE_TYPE=q8_0` and
    `OLLAMA_FLASH_ATTENTION=1` have been in effect at least since 2026-09-10;
    whether they were in effect for the April/May 2026 published corpus is
    unknowable. Ollama also moved 0.33.3 → 0.34.0 between the September
    replications and this regeneration.
18. **G13** — the flood hazard schedule (`flood_years.csv` = 3, 4, 9) is fixed and
    seed-independent.
19. **G12** — package versions are recorded only from this run forward.
20. **Seed set 42–46** — state that seeds are pre-chosen replicates inherited from
    the v21 corpus.
21. **Row-count expectations** — relocation attrition in flood, ABORTED sentinels in
    both domains; and the acceptance bands come from a workers-1, mixed-commit,
    partly-backfilled corpus.
22. **Two arms that ran at `--workers 1` semantics under the old corpus but will
    now differ** — the published irrigation pair was produced at two different
    commits (`db05d3a2` / `d8a5da41`), seeds 45/46 recorded none, and both
    manifests carry `git_dirty: true`. The regeneration fixes all three.
