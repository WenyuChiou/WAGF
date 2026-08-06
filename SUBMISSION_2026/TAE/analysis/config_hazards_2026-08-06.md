# Config and parameter hazards for the TAE first-attempt seed queue

**Written 2026-08-06 ~08:45, read-only sweep, nothing edited and no job launched.**
Ranking criterion, applied to every item: *could this silently ruin one of seeds 43–46, or make a
finished run look valid when it is not?* Silent failures rank above loud ones. Everything is quoted
with `path:line`.

---

## The answer, in three sentences

**One thing must be decided before seed 43 launches: `git_dirty`.** The manifest samples
`git status --porcelain` at *finalize*, not at launch (`broker/core/experiment_runner.py:509-521`,
reached only from `_finalize_experiment` at `:402`), the tree has **23 dirty entries right now**, and
`SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:404-408` raises `IntegrityError` on
`git_dirty=true` — so on current state **all five runs fail the gate**, `n_pass = 0 < 3` fires the
"DELETE the appendix section entirely" abort rule at `e3_run_integrity.py:529-535`, and 52 GPU-hours
buy nothing. That is a *loud* failure, but it is discovered 10.4 hours late per seed, and it says
nothing about whether the science is sound.

Everything else is either a copy-paste discipline problem on the five hand-typed commands (items 1–3
below, all genuinely silent, all closed by *pasting* rather than retyping) or is already covered.
**No defect was found in the code path seeds 43–46 will take that silently corrupts a run under
correct operator input.** The runner, the audit writer and the gate are in good shape; the exposure
is the operator interface, not the framework.

---

## Live ground truth (measured, not assumed)

Three prior lanes reported the live run at year 27, 39 and 40. Measured directly at 08:41:

| fact | value | how |
|---|---|---|
| traces written | **3082 of 3276** (94%) | line count of `raw/irrigation_farmer_traces.jsonl` |
| elapsed | 9.35 h (first ts 2026-08-05 23:20:19 → last 08:41:02) | timestamps in the JSONL |
| rate | 329.8 traces/h | derived |
| **ETA** | **~0.6 h → finishes ≈ 09:16** | derived |
| projected total | **9.93 h** — under the 20.8 h ceiling, so `check_wallclock` will pass | derived |
| on-disk state | **only** `raw/irrigation_farmer_traces.jsonl` (48.3 MB) + `reflection_log.jsonl` (1.0 MB) | `ls` |
| git | HEAD `c2e5205f`, **23 dirty entries** | `git status --porcelain \| wc -l` |
| disk | 2.4 TB free of 3.7 TB; ~51 MB per run, ~206 MB for four more | `df -h` |

Two consequences worth stating up front:

- **Nothing but the JSONL exists until finalize.** No CSV, no manifest, no `config_snapshot.yaml`,
  no `run_integrity.json`. A `taskkill` / power loss / Windows-Update reboot at hour 9 leaves the
  scientific data recoverable (`broker.tools.recover_csv_from_jsonl`) but the run
  **uncertifiable** — `e3_run_integrity.py:155-163` needs `simulation_log.csv` and `:383-385` needs
  `reproducibility_manifest.json`. Neither can be rebuilt.
- **Disk is not a hazard.** 206 MB against 2.4 TB. Do not spend attention on it.

---

# (a) Act before seed 43 launches

## A1 — `git_dirty` is sampled at finalize, and the tree is dirty. LOUD, but it will fail every seed.

- `broker/core/experiment_runner.py:509-521` — `git status --porcelain` inside
  `_collect_reproducibility_metadata`, called from `_finalize_experiment` at `:402`, i.e. **~10 hours
  after launch**.
- `SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:404-408` reads that value as a statement about
  *launch* time: `"the pre-flight 'clean tagged tree' fence (launch_firstattempt.md section 1a) was
  not actually satisfied at run time"`.

The 23 entries are all outside the code the runner imports — 12 modified tracked files
(`ICLR2027/submission/paper/manuscript.tex`, four `SUBMISSION_2026/TAE/figures/*.pdf`,
`SUBMISSION_2026/TAE/paper/manuscript.docx`, five `examples/multi_agent/flood/*`) plus 11 untracked.
**None under `broker/` or `examples/irrigation_abm/`.** So the science is unaffected and the gate
verdict would be a false statement — but it is still a `FAIL`, and it repeats identically for 43–46.

**Scenario:** all five seeds run clean, all five record `git_dirty: true`, e3 certifies zero, the
abort rule says delete the appendix.

**Cheapest guard — pick one, before seed 43:**
1. Commit or stash the 12 modified tracked files and land the untracked ones, so the tree is clean
   at each finalize. Cleanest, and it makes the recorded value mean what the gate reads it as.
2. Or accept it and narrow the check — in `e3_run_integrity.py:404-408`, fail only when the dirty
   set intersects `broker/` or `examples/irrigation_abm/`. This edits the gate mid-campaign, so it
   needs recording in the evidence log.

Do **not** run any repo-wide `git` write while a seed is in flight (see B1).

*Seed 42 note:* it finalizes ≈ 09:16. Unless the tree is clean in the next ~30 minutes, seed 42
records `git_dirty: true`. Its data is fine; only the certification is at stake, and the decision
above applies retroactively to it. For context, the frozen archival corpus has the same property —
`examples/irrigation_abm/results/production_v21_42yr_seed42/reproducibility_manifest.json` reads
`git_dirty: True`. The gate is stricter than the project's own history.

## A2 — A mistaken `--output` destroys the previous seed's only durable artifact in the first seconds, and the resulting directory still certifies. **SILENT — the worst item here.**

Two independent facts compose:

- `broker/components/analytics/audit.py:166` — `clear_existing_traces: bool = True`, and
  `experiment_builder.py:481-483` constructs `AuditConfig` **without overriding it**. So
  `GenericAuditWriter.__init__` at `audit.py:492-499` **unlinks `raw/*_traces.jsonl`** at
  construction, seconds into the process, before the first LLM call.
- `examples/irrigation_abm/run_experiment.py:665-666` — `mkdir(parents=True, exist_ok=True)`; the
  runner does not refuse an existing `--output`.

And the gate does not catch the aftermath: `e3_run_integrity.py:389-416` `check_provenance` asserts
`agent_types_config`, `model`, `governance_profile` and `git_dirty` — **`seed` appears only in the
cosmetic `extra` string at `:413-416`**. It is never compared to the directory name, and `_main`
(`:474-540`) does no cross-run uniqueness check.

**Scenario.** The five commands in `runs/launch_firstattempt.md:137-180` differ in exactly **three**
places: `--seed`, `--memory-seed`, `--output`. Retyping the seed-43 line and editing two of the three
(say `--seed 43 --memory-seed 43` but leaving `--output …seed42`) does two things at once: it deletes
seed 42's JSONL — the *only* artifact that survives a crash — and then, if it completes, produces a
directory named `seed42` holding seed-43 data with a manifest saying `seed: 43`. All nine e3 checks
pass. Two of five "independent" seeds become one seed; between-seed variance is understated and the
CIs come out too tight. This is exactly the ministral-seed-44 class: correct-looking corpus, wrong
provenance, no error anywhere.

**Cheapest guard:** paste the commands from `launch_firstattempt.md` §2, never retype them, and run
§1f's `ls` first (it is the only existing defence and it is manual). A 4-line addition to
`check_provenance` closes the labelling half permanently — assert `manifest["seed"]` matches the
trailing digits of the run directory name. That file is outside `broker/` and safe to edit now.

## A3 — `--memory-seed` is a live behavioural RNG recorded in no artifact. **SILENT and unrecoverable.**

Reachability proven end to end:

- `run_experiment.py:755` — `p.add_argument("--memory-seed", type=int, default=42)`. Omitting it
  does not fail; it silently yields **42**.
- `run_experiment.py:629` — `seed=args.memory_seed` into `HumanCentricMemoryEngine`.
- `broker/components/memory/engines/humancentric.py:86` — `self.rng = random.Random(seed)`.
- `humancentric.py:253-258` — `if importance >= self.consolidation_threshold:` then
  `if self.rng.random() < consolidate_p:` decides which memories are promoted to long-term store.

That changes what `retrieve()` returns → what the prompt contains → what the model decides. With
`consolidation_probability: 0.7` and `consolidation_threshold: 0.6`
(`config_irrigation_firstattempt/agent_types.yaml:31-35`) and reflection insights stored at
importance 0.90, this RNG fires on essentially every reflection write across 42 years × 78 agents.

**Where it is recorded: nowhere.** Verified against a real artifact — the archival seed-42 manifest
has exactly **19 keys** (`model, seed, num_years, governance_profile, agent_types_config,
model_digest, model_family, model_parameter_size, model_quantization, git_commit, git_dirty,
thinking_mode, temperature, top_p, num_ctx, num_predict, config_hash, timestamp, python_version`).
No `memory_seed`. `broker/core/run_integrity.py:101-112` records `seed` but not `memory_seed`.
`config_snapshot.yaml` is a re-read of the YAML file (`experiment_runner.py:415-421`) and cannot see
a CLI value.

**Scenario.** Seed 45's line is edited for `--seed` and `--output` but `--memory-seed 42` is left
behind. The run completes, writes 3,276 rows, a manifest saying `seed: 45`, and a `run_integrity.json`
saying `seed: 45`. **Nothing on disk distinguishes it from a correct seed-45 run**, and no post-hoc
analysis can recover the fact. Note the launch doc itself flags (§2 "Flagged, not resolved") that
`--memory-seed <S>` diverges from every archival batch script — none of which pass it — so the
convention in force here is the *unusual* one, which raises the chance of reverting to habit.

**Cheapest guard:** paste, don't retype (same guard as A2); and after each seed exits, append the
launch command verbatim to a file beside the run directory. There is no artifact-side recovery.

## A4 — Capture stdout as well as stderr. **SILENT — it is the multiplier on A3 and B2.**

`SUBMISSION_2026/TAE/runs/_logs/seed42.log` is 5.5 MB and contains 762 `[Governance:Success]` lines
(`logger.warning` → stderr) and 40 `--- Year N ---` banners (`experiment_runner.py:306`,
`logger.info`). It contains **zero** `print()` output. Verified by direct count, all four are `0`:

| string | source | count |
|---|---|---|
| `ISOLATED` | `run_experiment.py:471` `print(f"[Config] ISOLATED config dir: {config_dir}")` | **0** |
| `Loaded 78` | `run_experiment.py:548` | **0** |
| `seed=42` | `run_experiment.py:719-722` run banner | **0** |
| `Reflection] Year` | `run_experiment.py:445` | **0** |

So the **only** runtime confirmation that `--config-dir` took effect, and the **only** confirmation of
`--real` / agent count / `--years` / `--seed` / `window=`, is not in the captured log — and on an
abnormal exit the block buffer is lost outright. The `[Ablation] … DISABLED` line
(`run_experiment.py:497`) is a `print()` too, which is what makes B2 dangerous rather than merely
unrecorded.

**Cheapest guard**, for seeds 43–46, no code change:

```
python -u examples/irrigation_abm/run_experiment.py ... > SUBMISSION_2026/TAE/runs/_logs/seed<S>.log 2>&1
```

(the archival `.bat` files already redirect both streams). Then the first 20 lines of the log are a
30-second launch verification for A3's sibling `--seed`, for `--config-dir`, and for `--real`.

---

# (b) Act after all five seeds finish

## B1 — No repo-wide `git` operation while a seed is in flight. SILENT.

Because capture is at finalize (A1), a `git commit` or `checkout` during the 10.4 h window makes the
manifest record a commit that is **not** the code the already-imported process is running. The JSONL
header stamps its own commit at `AuditWriter` construction (`audit.py:503` → `:35`); the live header
reads `50247de3f1ba` while HEAD is now `c2e5205f` — **20 commits later, all made during this run**.
I checked `git diff --stat 50247de3f1ba..HEAD -- broker/` and it is **empty**, so no behavioural drift
occurred this time. The point is that the mechanism which would surface drift is unreliable in both
directions, and this is precisely the ministral-seed-44 detector.

Corollary silent case: a tree dirty *at launch* and cleaned before finalize records
`git_dirty: false`, and e3 then certifies "clean tagged tree at run time" on evidence that cannot
establish it. Whatever is decided in A1, the recorded field does not measure the quantity the gate
reads it as. Worth fixing in `experiment_runner.py` after the campaign — sample git state at
`__init__`, not at finalize.

## B2 — Validator on/off flags change which rules fire and appear in no artifact. SILENT.

`run_experiment.py:495-497` sets `irr_validators.ENABLE_DEMAND_CEILING = False` under
`--ablation-mode`; `:509` and `:512` set `ENABLE_CONSECUTIVE_CAP` / `ENABLE_ZERO_ESCAPE` under
`--pilot-phase`. These are Python module globals, not YAML, so `config_snapshot.yaml` cannot see
them, the manifest does not carry them, and `thinking_rules_resolved_counts`
(`experiment_runner.py:571-575`) counts YAML rules only — it stays at 3. A seed launched with
`--ablation-mode no_demand_ceiling` yields a corpus whose provenance is byte-for-byte
indistinguishable from the governed arm; the only trace is one rule string never appearing in
`triggered_rules`.

**Not a live hazard** — none of the four flags appears in any of the five commands, so the risk is a
*wrongly added* flag, not a dropped one. Fix by adding them to the manifest after the campaign.

## B3 — Nothing reconciles JSONL against CSV, and the counters built to detect loss have zero consumers. SILENT.

`audit.py:794-796` appends to `_trace_buffer` **unconditionally**, after the JSONL flush is attempted
at `:790-791`. On terminal flush failure `audit.py:939-946` discards the JSONL buffer (correct — the
F2 fix chose detectable loss over undetectable duplication) and increments
`summary["jsonl_events_lost"]`. But the CSV is built at finalize from `_trace_buffer`
(`audit.py:872-873, :976`), which still holds those traces. Result: **CSV row count > JSONL line
count**, and both gates pass — `e3_run_integrity.py:155-163` compares the CSV against the constant
3276, and `check_wallclock` (`:334-372`) reads the JSONL but bounds only its *time span*.

Verified by grep across the repo (tests excluded): `jsonl_events_lost` appears only at
`audit.py:525, 939, 944-945`; `csv_export_failures` only at `audit.py:1024`. **No consumer anywhere.**
They are written into `audit_summary.json` and read by nothing;
`broker/tools/readiness_report.py:163-183` reads `total_traces` and never cross-checks.

**Cheapest guard, and it is nearly free:** after each seed, compare the JSONL line count to 3277
(3,276 traces + 1 metadata header). See the checklist below.

## B4 — Directory reuse plus a kill-without-finalize produces a fully certified merge of two runs. SILENT, compound.

Write modes differ per file, so reuse is a *merge*, not a clobber:

| file | mode | line |
|---|---|---|
| `raw/*_traces.jsonl` | **deleted at startup** | `audit.py:492-499` |
| `reflection_log.jsonl` | **appends** if present | `broker/components/cognitive/reflection.py:169-171, :554` |
| `*_governance_audit.csv` | `'w'`, at finalize only | `audit.py:991` |
| `simulation_log.csv` | truncate, **after** `runner.run()` returns | `run_experiment.py:723, :739` |
| `reproducibility_manifest.json` etc. | `'w'`, at finalize | `experiment_runner.py:438, 459, 476` |

Relaunch onto a *completed* directory, then die without Python-level finalize (Windows Update reboot,
`taskkill`, power — the documented 2026-05-13 incident). The directory then holds the OLD complete
`simulation_log.csv`, the OLD audit CSV, the OLD manifest, plus a NEW **partial** JSONL and a
concatenated reflection log. e3 certifies it: row counts 3276/3276 (old), join exact (old), columns
present (old), reflection non-empty (merged), provenance consistent (old manifest), and
`check_wallclock` reads only the *partial* JSONL's span — ~7 h for 27 years, comfortably under the
20.8 h ceiling.

The near-miss is precise: `check_wallclock` **counts records into `n` at `e3_run_integrity.py:345`
and then uses `n` only inside an error string at `:360`** — it never asserts `n == EXPECTED_ROWS`.
One line closes it.

Related, same family: `experiment_runner.py:288` fixes `iterations = 42` before the loop, `:356-357`
calls `_finalize_experiment(iterations)` from a `finally`, and `:398` writes `"num_years": iterations`
— so **a crash at year 27 writes a manifest saying `num_years: 42`**. `audit_summary.json`'s
`finalized_at` is stamped unconditionally (`audit.py:804`), and `run_integrity.json`'s `integrity_ok`
only asserts reflection entries > 0 (`run_integrity.py:119-120`), so a partial run reads
`integrity_ok: true`. **No field records completion.** In a *fresh* directory the discriminators are
the absence of `simulation_log.csv` (`main()` has no try/except at `run_experiment.py:785-786`) and a
short audit CSV; in a *reused* directory both are defeated.

Ranked in group (b) rather than (a) because it needs two things to go wrong at once, and §1f's manual
`ls` blocks the first. Code-proven, not observed: all 41 archival dirs are `num_years=42` with 3,276
rows.

## B5 — FQL baseline: both arms share one default path, and FQL dirs carry no provenance. SILENT, and reachable *now*.

`examples/irrigation_abm/run_fql_baseline.py:522-525` defaults to `results/fql_raw/seed{S}` for **both**
arms; `--no-governance` (`:589-590`) reaches `run_simulation(no_governance=...)` at `:546` without
touching the path, and `:552-553` truncates. FQL run directories contain **only**
`simulation_log.csv` — no manifest, no seed record, no arm record. So
`run_fql_baseline.py --real --seed 42 --no-governance` with `--output` omitted silently replaces the
governed FQL baseline with no-governance data.

This is live: `results/fql_nogov/` was written **2026-08-06 01:50** (10 seed dirs), inside this
campaign window, and FQL is CPU-only — precisely the runner that is safe to launch while the LLM holds
the GPU. It was done correctly (explicit `--output`), but the default remains a trap. Not one of the
four seeds, hence group (b).

## B6 — `create_llm_invoke` silently downgrades a real run to a constant mock. SILENT, low probability, catastrophic.

`broker/utils/llm_utils.py:493-499`:

```python
except ImportError:
    _LOGGER.warning("langchain-ollama not found. Falling back to mock LLM.")
    return lambda p: ('{"decision": 1}', LLMStats())
except Exception as e:
    _LOGGER.warning(f"Falling back to mock LLM due to: {e}")
    return lambda p: ('{"decision": 1}', LLMStats())
```

The constructed `OllamaLLM` object is never used — the returned closure calls
`_invoke_ollama_direct` directly ("Phase 46F: UNIVERSAL DIRECT API … bypasses LangChain entirely") —
so the import is a vestigial gate whose failure handler returns a constant. The resulting run exits 0,
writes a manifest saying `"model": "gemma3:4b"` with a live `model_digest` (the `/api/show` probe at
`experiment_runner.py:491-504` is independent of the invoke path), and produces 3,276 identical
decisions.

Reachability is real but unproven: this environment already runs LangChain on unsupported Python
3.14 (`seed42.log` line 5: `UserWarning: Core Pydantic V1 functionality isn't compatible with Python
3.14 or greater`), so any dependency change during the 2.5-day queue could turn the warning into an
ImportError. I could not make it fire.

**Detection is one grep**, in the checklist below: a healthy run logs `[LLM:Init]` (present **3×** in
seed42.log); a mocked run logs `Falling back to mock LLM` (**0×** in seed42.log).

---

# (c) Recorded, not worth acting on — so nobody re-finds them

| # | Item | Why it is parked |
|---|---|---|
| C1 | **`--governance-mode` typo runs 0 rules.** `broker/utils/agent_config.py:1241` falls back to `gov.get("default", {})`; the isolated config declares only `strict:` and `disabled:` and **no `default:`**, and `require_profile` is **absent** from it (verified — `global_config.governance` at `agent_types.yaml:63-66` has only `max_retries`, `max_reports_per_retry`, `domain`), so `_resolve_governance_profile` (`:1189-1225`) is inert. **But it is caught post-hoc:** the manifest records the typo'd string and `e3_run_integrity.py:399` asserts `governance_profile == "strict"`; `experiment_runner.py:568-575` also records `governance_profile_resolved` and `thinking_rules_resolved_counts` (would read 0). Loud at the gate, costs 10.4 h. Adding `require_profile: true` to the isolated config would make it fail at load — but that edits the config mid-campaign, so it belongs after the freeze. |
| C2 | **Default `--output` pollutes `results/` but does not touch the corpus.** `run_experiment.py:665` → `examples/irrigation_abm/results`, and `:685` passes it through `with_exact_output`, which bypasses the model/profile subfolder (`experiment_builder.py:473-474`) — so files land in the **root** of `results/`, as siblings of the 41 frozen dirs, never inside `production_v21_42yr_seed<S>/`. TAE analysis cannot ingest it (`SUBMISSION_2026/TAE/evidence/_data.py:14` exports no globs; `_reject_contaminated` at `:270-287` refuses anything outside the two results roots). `--output` is explicit in all five commands. |
| C3 | **`run_ungoverned_experiment.py` hardcodes `config_dir = base / "config"` (`:110`) with no `--config-dir`**, and defaults to a `ungoverned_v20_*` name (`:239`). A no-validator arm physically could not read the isolated config, and would fail loudly at `e3_run_integrity.py:215-226`. **No ungoverned arm is authorised** (`launch_firstattempt.md:239-242`) — conditional on a scope change. |
| C4 | **`global_config.llm` in the domain YAML (`agent_types.yaml:57-61`) is dead text.** `broker/utils/llm_utils.py:142-146` resolves only `Path.cwd()/"agent_types.yaml"` or `Path(__file__).parent/"agent_types.yaml"` — neither exists, so `LLM_CONFIG` is pure dataclass defaults. The `num_ctx: 8192 / num_predict: 4096` written there make the CLI overrides *look* redundant when they are not (the tuner would halve them to 4096/2048 — `performance_tuner.py:29-30`). Loud if it happened: `num_ctx`/`num_predict` are in the manifest (`experiment_runner.py:529-530`), the log line confirms them (`seed42.log` line 4 reads `num_ctx=8192, num_predict=4096`), and `audit.py:612-638` warns when `prompt_tokens/num_ctx > 0.9`. Delete the dead YAML block after the campaign. |
| C5 | **Ollama sampling is unseeded, and the audit carries a `seed` column that never touched the sampler.** `llm_utils.py:264-276` never places `seed` in `options` (grep for `options['seed']` across `broker/` returns nothing), while `experiment_runner.py:882` and `:1068` pass `seed=self.config.seed + step_id` into `broker.process_step` → `skill_broker_engine.py:542` → audit only. Known (Phase 6R-D-4); the trap is that a future analyst will read the column as evidence of reproducible generation. Document it, do not "fix" it — changing it would break byte-identity with the archival corpus. |
| C6 | **`temperature: null` / `top_p: null` in the manifest mean "key omitted from the request", not "temperature 0"** (`llm_utils.py:271-276` adds them only when non-`None`). The effective value is `gemma3:4b`'s Modelfile default. And `model_digest` is not a content hash — the archival manifests hold `"2026-01-29T12:50:07.405621-05:00"`, i.e. `/api/show` returned no `digest` and the code fell through to `modified_at` (`experiment_runner.py:500`). So an `ollama pull gemma3:4b` between seeds would change sampling with only an mtime string as evidence. Guard: do not pull, and compare that string across the five manifests at the freeze. |
| C7 | **`global_config.memory.window_size: 5` (`agent_types.yaml:31`) is shadowed** — `window_size` comes from `--window-size` (`run_experiment.py:756, :618`) while its four YAML siblings *are* read. They agree at 5 today, so nothing is wrong; a maintainer editing that block would find four of five keys take effect. |
| C8 | **`--workers` is unrecorded and the tuner's log line invites raising it.** `seed42.log` line 3 reads `Workers: 2 (adjusted from 2)`, but `run_experiment.py:686` uses `args.workers` and discards `perf.workers` — the run is at `--workers 1`. The module-level `_consecutive_increase_tracker` race (`examples/irrigation_abm/validators/irrigation_validators.py:601, :619-621`) is inert because `ENABLE_CONSECUTIVE_CAP = False` (`:490`), and `--workers 1` is in all five commands. |
| C9 | **`trace_to_csv_row` runs outside the `try` in `_export_csv` (`audit.py:976` vs `:990`) and the handler catches only `OSError` (`:1007`).** A non-OSError during row building would escape into `run()`'s `finally` and kill every remaining artifact. **Reachability not established** — the irrigation run has one agent type, `skill_proposal` is a dataclass or `None`, and the `or {}` guards at `audit.py:213-214` handle `None`. Structural weakness, not a live hazard. |
| C10 | **Both flood domains write `household_governance_audit.csv` (`audit.py:972`) and both defaults omit the seed** (`run_flood.py:1207-1209`, `run_unified_experiment.py:218`); single-agent `--seed` defaults to `None` → system time (`run_flood.py:1367`). Not on this path; listed so it is not re-found. |
| C11 | **Config validation is absent in general** — no schema on this path (`broker/config/schema.py` has no production importer), unknown keys ignored, a duplicated `global_config:` key silently keeps the last mapping, and a string `"false"` reads as `True` through `bool(block.get(...))` at `agent_config.py:338-341`. The isolated config is already written and diffed, so this is an authoring hazard for *future* configs, not for seeds 43–46. Note the one real protection: `run_experiment.py:515-516` does its own unguarded `yaml.safe_load` before `AgentTypeConfig`, so malformed YAML fails loudly here even though `_load_yaml` (`:117-146`) would swallow it. |
| C12 | **Disk and log rotation.** 2.4 TB free; ~51.5 MB per run, ~206 MB for four; `hooks/hook_debug.log` at 6.6 MB. Dismissed with numbers. |
| C13 | **`--config-dir` missing files fails loudly.** `run_experiment.py:462-470` checks `agent_types.yaml`, `skill_registry.yaml` and `prompts/irrigation_farmer.txt` and raises `SystemExit` naming them. There is **no** silent fallback to the frozen config. Not a hazard. |
| C14 | **Only `agent_types.yaml` is hashed.** `config_hash` (`experiment_runner.py:534-544`) and `config_snapshot.yaml` cover it alone; `skill_registry.yaml` and `prompts/irrigation_farmer.txt` — the prompt being the largest single determinant of behaviour — are read from `--config-dir` and hashed nowhere. Provenance gap, no live exposure (the tree is frozen and diffed). |

**Stale checklist item, worth one edit:** `launch_firstattempt.md` §1e says the `diff -rq` "must print
exactly one line". It now prints **two** — the second is
`Only in …config_irrigation_firstattempt: DIFF_AGAINST_FROZEN.md`, the doc-file the pre-flight itself
added. The delta is otherwise verified correct. A checklist that fails on a benign line trains the
operator to wave the whole check through.

---

# Pre-launch and post-run checklist for seeds 43–46

Literal commands, repo root, PowerShell or Git Bash. Under a minute total.

### Before launching seed `<S>`

```bash
# 1. Target must NOT exist (launch_firstattempt.md 1f -- the runner will not refuse)
ls SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>        # must say: No such file or directory

# 2. Previous seed's JSONL must still be there (proves no --output slip destroyed it)
ls -la SUBMISSION_2026/TAE/runs/firstattempt_gov_seed*/raw/irrigation_farmer_traces.jsonl

# 3. git_dirty decision from A1 -- this must be EMPTY at the moment the run FINALIZES
git status --porcelain | wc -l

# 4. Config tree unchanged (2 lines expected now, not 1 -- see the stale-checklist note)
diff -rq examples/irrigation_abm/config SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt

# 5. GPU is free -- one model resident, nothing else
ollama ps
```

**Then PASTE the seed-`<S>` block from `launch_firstattempt.md` §2. Do not retype it.**
Add `-u` and redirect both streams:

```bash
python -u examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed <S> --memory-seed <S> --workers 1 \
  --governance-mode strict --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S> \
  > SUBMISSION_2026/TAE/runs/_logs/seed<S>.log 2>&1
```

### Within 2 minutes of launch — catches A3, A4, B6, C1, C4 before 10 hours are spent

```bash
head -25 SUBMISSION_2026/TAE/runs/_logs/seed<S>.log
```

Confirm, in that head:

| expect to see | catches |
|---|---|
| `[Config] ISOLATED config dir: ...config_irrigation_firstattempt` | wrong / omitted `--config-dir` |
| `[Data] Loaded 78 real CRSS agents` | `--real` omitted |
| `[Pillar 2] HumanCentricMemoryEngine (window=5, ...)` | memory engine wired |
| `--- Irrigation ABM \| ... \| seed=<S> ---` | `--seed` typo |
| `[PerformanceTuner] Applied: num_ctx=8192, num_predict=4096` | tuner halving the budget (this one is a `_LOGGER.info` at `performance_tuner.py:225`, so it is already visible today — every other row in this table needs the stdout capture) |
| `[LLM:Init] Using OllamaLLM for model: gemma3:4b` | the mock-LLM downgrade (B6) |
| **no** `Falling back to mock LLM` | same |
| **no** `[Ablation]` / `[Pilot]` line | a stray validator flag (B2) |

Then, the one thing no log can show — **record the command you actually ran**, because
`--memory-seed` is in no artifact:

```bash
history 1 >> SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>/LAUNCH_COMMAND.txt
```

### Mid-run, any time — 5 seconds

```bash
wc -l SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>/raw/irrigation_farmer_traces.jsonl
```

Divide by 78 for the current year. Rate is ~330 traces/h; anything below ~150/h is the CPU-fallback
signature (`nvidia-smi`, `ollama ps`) long before `check_wallclock` would catch it at hour 21.

### After the run exits — before it counts

```bash
# a. JSONL completeness -- must be 3277 (3276 traces + 1 metadata header). Closes B3/B4.
wc -l SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>/raw/irrigation_farmer_traces.jsonl

# b. Seed and memory-provenance in the manifest -- read seed with your own eyes, e3 does not check
#    it against the directory name (A2)
PYTHONIOENCODING=utf-8 python -c "import json,sys; d=json.load(open(sys.argv[1])); print({k:d[k] for k in ('seed','num_years','governance_profile','git_dirty','config_hash','num_ctx','num_predict','governance_profile_resolved','thinking_rules_resolved_counts') if k in d})" \
  SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>/reproducibility_manifest.json

# c. The three counters nothing reads (B3) -- all must be 0 / absent
PYTHONIOENCODING=utf-8 python -c "import json,sys; d=json.load(open(sys.argv[1])); print({k:d.get(k) for k in ('total_traces','jsonl_events_lost','csv_export_failures','audit_sentinel_warnings')})" \
  SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>/audit_summary.json

# d. No silent mock, no LLM failure storm
grep -c "Falling back to mock LLM" SUBMISSION_2026/TAE/runs/_logs/seed<S>.log     # must be 0
grep -cE "timed out|HTTP Error|empty_content" SUBMISSION_2026/TAE/runs/_logs/seed<S>.log

# e. The gate
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/e3_run_integrity.py \
  SUBMISSION_2026/TAE/runs/firstattempt_gov_seed<S>
```

### At the freeze, across all five

```bash
PYTHONIOENCODING=utf-8 python -c "
import json,glob
for p in sorted(glob.glob('SUBMISSION_2026/TAE/runs/firstattempt_gov_seed*/reproducibility_manifest.json')):
    d=json.load(open(p))
    print(p.split('/')[-2], '| seed', d.get('seed'), '| yrs', d.get('num_years'),
          '| cfg', d.get('config_hash'), '| digest', str(d.get('model_digest'))[:32],
          '| commit', str(d.get('git_commit'))[:12], '| dirty', d.get('git_dirty'))
"
```

Five distinct seeds matching their directory names, one `config_hash`, one `model_digest`
(C6 — a change here means the model was re-pulled mid-campaign), and `num_years: 42` everywhere.

---

# What I could not establish

1. **Whether the `create_llm_invoke` mock fallback (B6) can actually fire in this environment.** The
   Python 3.14 / Pydantic-V1 warning at `seed42.log` line 5 is real and the handler is real, but
   triggering the ImportError would mean touching the environment while the run holds the GPU. I did
   not. Ranked on its detection cost (one grep), not on a demonstrated probability.
2. **Whether `trace_to_csv_row` (C9) can raise a non-OSError on irrigation input.** I found no
   reachable malformed trace. Recorded as structural, ranked last.
3. **Anything requiring a run.** The brief forbids GPU work and I did not launch even a mock run, so
   B4's merge scenario, A2's `--output` collision and A3's memory-seed divergence are **code-proven,
   not observed**. I verified the passive half: all 41 archival irrigation directories carry
   `num_years=42` with 3,276 rows, so there is no counterexample on disk — which is consistent with
   both "it never happened" and "it happened and is invisible".
4. **Whether the frozen archival corpus is affected by A3.** The four archival batch scripts
   (`run_gemma4_e4b_batch.bat`, `run_gemma12b_batch.bat`, `run_gemma4_e2b_batch.bat`,
   `run_ensemble.bat`) pass **no** `--memory-seed`, so every `production_v21_42yr_seed{42..46}` ran
   with memory RNG = 42 — the archival five-seed replicates already share it. I did not assess what
   that does to the published variance estimates; it is out of scope for this sweep but should not
   stay unexamined.
5. **Type coercion on `global_config.memory.*`.** Those values flow raw into
   `HumanCentricMemoryEngine` (`run_experiment.py:617-630`) with no coercion, unlike
   retrieval/drift/population/tiers/bridge (`agent_config.py:633-642, 711-726, 796-805, 866-875,
   967-976`). I did not trace where a string `decay_rate` would surface. Low rank: the config is
   frozen and correct.
6. **Nothing was tested by mutation on the live config.** All config probes referenced in this
   document were reasoned from source; I did not write mutated copies during this sweep. The two
   empirical anchors I did establish — that the isolated config declares no `default:` profile and
   no `require_profile`, and that the live JSONL already carries `initial_skill` /
   `initial_labels` / `attempt_skills` — are direct reads.
