# Flood WRR26-rerun GPU runbook

Branch `prep/flood-wrr-rerun`, based on `origin/main` 13b13b20. This file is
the exact command set for the GPU rerun once the branch is reviewed, merged
and tagged; no real LLM has been run from this branch (mock and scripted-mock
only -- see section 7).

## 1. What changed and why

See the flood design record (`.research/design_specs/
flood_design_record_2026-09-29.md`, PI decisions 2026-10-06 and 2026-10-07)
for the full provenance table. In one line each, every change this branch
makes relative to the `83fa97e1` corpus:

1. Insurance renewal (design record row C2): `has_insurance` lapses ONLY on
   `do_nothing` (unless bought again that year); elevating or relocating
   leaves it UNTOUCHED, matching WRR26's own code -- the previous WAGF code
   cancelled an elevated household's existing policy the moment it elevated.
2. Neighbour-observation memory (row F1) is WRR26's own TWO separate lines
   per year ("I observe {e}% of my neighbors have elevated homes." then
   "...have relocated.") instead of one combined sentence.
3. Neighbour-trust update (row E3) now uses the community action rate from
   BEFORE the year's decisions (`FinalParityHook.pre_year` captures it;
   `post_year` reads it back), as WRR26's code does.
4. Memory is five most recent EVENT LINES, one `add_memory` call per line
   (row F2; `FinalParityHook.pre_year`), not one `" | "`-joined line per
   year.
5. The "Year t: You chose to X." own-action memory line (row F3, not in
   WRR26) is removed.
6. `### MULTI-ACTION OPTION` and the `magnitude_pct` / `secondary_decision`
   / `secondary_magnitude_pct` response fields (row C5, unused by the flood
   model) are gone from `config/prompts/household.txt` and
   `shared.response_format.fields`.
7. The 4 leading blank lines are gone (`{system_prompt}{priority_section}`
   added to the top of `household.txt`, matching
   `broker/components/context/tiered.py`'s own fallback and irrigation's
   template).
8. An elevated household's prompt now says "1, 2, or 3" everywhere,
   including the JSON placeholder (`{valid_choices_text}`, dynamic).
9. The `elevation_threat_low` (R4) retry message no longer contains the
   unfilled `{context.TP_LABEL}` placeholder (removed, not wired through a
   formatter -- `AgentValidator._run_rule_set` never ran YAML rule messages
   through one).
10. `global_config.governance.appraisal_freeze: true` -- every thinking rule
    reads each construct label as first stated in the decision (irrigation's
    WP3.8 option, generic, default off elsewhere).
11. Retry text for R1/R3/R4 is neutral: states the judgment made "at the
    start of this decision" in plain words, names no label code, carries no
    "lower/raise your threat" instruction. `global_config.governance.
    rule_id_prefix: false` (following irrigation's own WP3.5) additionally
    drops the "[Rule: <id>] " prefix, so the retry text names no internal
    rule id either. `global_config.governance.plain_action_names: true`
    (following irrigation's own WP4) names the blocked skill in plain words
    ("elevate house"), never its internal skill id ("elevate_house").
12. R1 (`extreme_threat_block`) redefined: threat H or VH AND coping NOT VL
    or L (PMT's non-protective response, Grothmann and Reusswig 2006
    p.106), not threat alone.
13. `global_config.llm` now sends gemma3:4b's own Modelfile defaults
    explicitly (`temperature: 1.0`, `top_p: 0.95`, `top_k: 64`), matching
    irrigation's own `agent_types.yaml` (spec 7.3) -- the same effective
    sampling as WRR26 sending none, now recorded in every manifest instead
    of left implicit. `num_ctx`/`num_predict` unchanged (8192/4096);
    `--thinking-mode disabled` stays a CLI flag (see commands below).
14. Four arms, each with a documented command: `strict`, `disabled`
    (`--governance-mode`), `silent` (`--retry-feedback-mode silent`),
    `no-nudge` (`--config-root examples/single_agent/config_variants/nonudge`).
15. `global_config.audit.initial_proposal_columns`, `attempt_columns` and
    `corrected_status_columns` are all `true` (needed by the post-run IBR,
    section 5): `initial_skill`/`initial_labels`/`attempt_skills` (the first
    parsed attempt and the full attempt history), `attempt_labels` /
    `appraisal_relabeled` (per-attempt labels and whether a construct was
    relabelled on retry), and `execution_path`/`executed_skill` plus an
    audit row for a fully-unparsed (ABORTED) decision, which would otherwise
    not exist in the CSV at all. `global_config.audit.retry_prompt_columns:
    true` additionally saves the exact retry-prompt text into
    `raw/household_traces.jsonl` (`retry_prompts`, JSONL-only, never a CSV
    column).
16. `run_flood.py`'s `--use-priority-schema` now refuses to run (a clear
    `ValueError`) instead of silently rendering a glued-together prompt: the
    WRR26-rerun `household.txt` template's first line
    (`{system_prompt}{priority_section}{narrative_persona}`) has no
    separator between `{priority_section}` and `{narrative_persona}`, so an
    old Group-C launcher that passes this flag would otherwise produce a
    malformed prompt silently. `--use-priority-schema` was never part of
    the WRR26-fidelity rerun; a priority-schema experiment needs a separate
    template/arm.

Everything else (WRR26 parameters, trust-wording cutoffs, flood years
3/4/9, damage draw, elevation effect, grants, initial profiles CSV, the
labelled-appraisal JSON response, retry with reasons, the "Do Nothing" note)
is unchanged. Verified with a scripted-mock smoke (section 7) and
`pytest examples/single_agent broker tests` (section 8).

## 2. Model, sampling and governance flags

- Model: `gemma3:4b` (WRR26 Sec. 3.1.1; design record row G1).
- Sampling: `temperature 1.0`, `top_p 0.95`, `top_k 64` sent explicitly
  (item 13 above) -- gemma3:4b's own Ollama Modelfile defaults, so the
  effective sampling matches WRR26 (which sends none) while the per-agent-type
  resolved params now record the values actually in effect. The manifest's
  own TOP-LEVEL `temperature`/`top_p` fields stay `null`: those two keys
  mirror a separate, run-wide `LLM_CONFIG` singleton that `run_flood.py`
  never populates from flood's own `agent_types.yaml` (no `--temperature`/
  `--top-p` CLI flags exist for it to read, and no `agent_types.yaml` sits
  at the process's cwd or next to `broker/utils/llm_utils.py` for it to
  load from); the real, per-agent-type values actually sent to Ollama are
  under `llm_params_resolved["household"]` instead
  (`broker/core/experiment_runner.py`'s reproducibility-metadata block 3c).
- `--num-ctx 8192 --num-predict 4096 --thinking-mode disabled` on every
  launch (design record row G4).
- `--memory-engine window --window-size 5` (default; design record row F4
  -- this is the engine every frozen launch command actually uses, despite
  `agent_types.yaml`'s `household.memory.engine_type: human_centric`,
  which only takes effect under `--memory-engine humancentric`).
- `--flood-mode fixed` (years 3/4/9 from `flood_years.csv`; default).
- `--memory-seed 42` (memory engine consolidation seed; default; distinct
  from `--seed`, which seeds Python's `random` for damage draws, grants
  and stochastic recall).

## 3. Commands

Run from the repo root. `<sha>` = the short commit sha this branch lands at
once merged (`git rev-parse --short HEAD`); embed it in every output
directory name, as the existing corpus does
(`JOH_strict_defaults_gemma3_4b_83fa97e1`). Do not start the real run from an
uncommitted tree -- commit first so the sha in the directory name is
meaningful.

### strict and disabled, seeds 42-51 (10 seeds each, the primary arms)

```bash
for seed in 42 43 44 45 46 47 48 49 50 51; do
  for mode in strict disabled; do
    python examples/single_agent/run_flood.py \
      --model gemma3:4b --years 10 --agents 100 \
      --governance-mode "$mode" \
      --seed "$seed" --memory-seed 42 --workers 1 \
      --num-ctx 8192 --num-predict 4096 --thinking-mode disabled \
      --output "examples/single_agent/results/JOH_${mode}_defaults_gemma3_4b_<sha>/Run_${seed}"
  done
done
```

### silent, seeds 42-46 (5 seeds; strict rules, content-free retry text)

```bash
for seed in 42 43 44 45 46; do
  python examples/single_agent/run_flood.py \
    --model gemma3:4b --years 10 --agents 100 \
    --governance-mode strict --retry-feedback-mode silent \
    --seed "$seed" --memory-seed 42 --workers 1 \
    --num-ctx 8192 --num-predict 4096 --thinking-mode disabled \
    --output "examples/single_agent/results/JOH_silent_defaults_gemma3_4b_<sha>/Run_${seed}"
done
```

### no-nudge, strict and disabled, seeds 42-43 (2 seeds each)

```bash
for seed in 42 43; do
  for mode in strict disabled; do
    python examples/single_agent/run_flood.py \
      --model gemma3:4b --years 10 --agents 100 \
      --governance-mode "$mode" \
      --config-root examples/single_agent/config_variants/nonudge \
      --seed "$seed" --memory-seed 42 --workers 1 \
      --num-ctx 8192 --num-predict 4096 --thinking-mode disabled \
      --output "examples/single_agent/results/JOH_${mode}_nonudge_gemma3_4b_<sha>/Run_${seed}"
  done
done
```

Total: 20 (strict/disabled) + 5 (silent) + 4 (no-nudge) = 29 real-LLM runs,
100 agents x 10 years each. At the defaults corpus's own per-run wall time
(design record: about 20 GPU h for the 20 strict/disabled seeds alone),
budget roughly 30 GPU h total for all 29 runs; confirm against the actual
per-decision latency on the first completed run before queuing the rest.

Each command is independent and safe to run in any order or in parallel
across machines/GPUs; nothing here shares state across runs except the
read-only config files.

## 4. LLM journal / resume

The framework has a crash-resume journal (`broker/utils/llm_journal.py`,
`ExperimentConfig.llm_journal_path` / `resume_journal_path`, wired through
`ExperimentRunner._build_llm_journal_manager`), but
`examples/single_agent/run_flood.py`'s CLI does **not** expose it -- there is
no `--llm-journal` / `--resume` flag, and `run_parity_benchmark` never sets
those two `ExperimentConfig` fields. So a crashed 100x10 run cannot be
resumed from where it left off through this script today; it would need to
be restarted from year 1 (or recovered from `raw/household_traces.jsonl`
with `broker.tools.recover_csv_from_jsonl` for the CSV/log side, which is
NOT the same as resuming the LLM calls themselves). Adding
`--llm-journal`/`--resume` to `run_flood.py` would be a small, generic,
in-scope follow-up (mirror how irrigation or another example wires it, if
any does) but is out of scope for this rerun. For now: run each seed as one
foreground job, and if a batch of 29 runs is queued unattended, detach each
one as its own subprocess with its own log file, one directory per run
(section 3), so a crash loses at most one run's progress, not the whole
batch.

## 5. Post-run IBR (irrigation v3 spec item 37e, the shared IBR family)

Canonical function: `examples/single_agent/analysis/flood_ibr_v2.py
(compute_flood_ibr_v2)`, unit-tested on a synthetic trace in
`examples/single_agent/tests/test_flood_ibr_v2.py` (44 tests, no real run
needed). This is a NEW module for the rerun corpus; it does not replace
`gemma4_nw_crossmodel_analysis.py (compute_ibr_components)`, the canonical
function for the PRE-rerun 83fa97e1 corpus's own (final-label) IBR
definition -- that function and its downstream reports are untouched.

Definition (spec item 37e, the SHARED family irrigation's own
`examples/irrigation_abm/analysis/v3_metrics.py (ibr_metrics)` computes for
TR1/TR3; this module computes the same family for flood's R1/R3/R4): for
each run's `household_governance_audit.csv`,

- **denominator (n)**: every row (every agent-year decision, ABORTED
  included; a relocated agent's later years carry no row, as before).
- **first-stated labels**: `initial_labels` (attempt 0) when a construct is
  stated there, else the first later attempt that states it
  (`first_stated_labels`; irrigation's own `_first_stated`).
- **PRIMARY (`ibr_pct`)**: the agent's LAST PARSED attempt's action
  (`Decision.last_parsed_proposal`; steps back past a literal last attempt
  that did not parse) judged against the first-stated labels, against the
  redefined rules -- R1 (threat H/VH AND coping not VL/L), R3 (threat
  VL/L AND relocate), R4 (threat VL/L AND elevate_house); R5 excluded, as
  before. Each agent-year counts once (the CSV already has exactly one row
  per agent-year). **Not simply `final_skill`**: on a `REJECTED_FALLBACK`
  row `final_skill` IS the registry default itself
  (`broker/core/skill_broker_engine.py _build_approved_skill`'s
  `is_generic_fallback` branch), not the agent's real last proposal (and
  `proposed_skill` there is blank, not the default, since it is read from
  the post-retry-loop `skill_proposal` local, which is `None` on exactly
  this branch); the real last PARSED proposal is read from `attempt_skills`
  instead (see the module docstring for the exact mechanics).
- **first-proposal share (`ibr_first_proposal_pct`)**: attempt 0's OWN
  action judged against the FIRST-STATED labels (not attempt 0's own
  literal label -- matching irrigation's own `ibr_first_proposal_*`, judged
  against `first_wsa`, which is itself first-stated, not literally attempt
  0's).
- **executed share (`ibr_executed_pct`)**: the `executed_skill` COLUMN, read directly (not
  re-derived from `status` plus a default-skill assumption), judged against
  the first-stated labels. Shows whether a violation actually reached the
  simulated world, not just the model's own paper trail. Note: the executed
  share is NOT bounded above or below by the primary in either direction --
  the registry default (do_nothing) can execute for a reason unrelated to
  R1 (the last PARSED proposal was not R1-shaped at all) while the
  first-stated labels still satisfy R1's condition, so the default itself
  can form a fresh R1 violation the primary never had.
- **final-label share (`ibr_final_label_pct`)**: the LITERAL last attempt's
  action (`None` when it did not parse) judged against that SAME attempt's
  own `final_labels`. An unparsed last attempt contributes no violation
  automatically (no action to match), so this share divides by n like every
  other one -- no special denominator exclusion is needed.
- **relabel rate (`relabel_rate_pct`)**: retried decisions (`retry_count >
  0`) whose `appraisal_relabeled` FRAMEWORK COLUMN is true, over retried
  decisions (not n -- irrigation's own `Decision.retried` /
  `relabel_rate_pct` convention; the column itself is written by
  `broker/core/_appraisal_freeze.py (relabeled_after_first_statement)`).
  Read directly from the column the generic engine already writes; flood
  counts TP and CP together (irrigation counts WSA only, its one governed
  construct). `None` (not `0.0`) when `retried_decisions == 0`;
  `aggregate_over_seeds` skips a `None` run rather than averaging it in as
  zero.
- **ABORTED rows** (`status` is `ABORTED` or `ABORTED_EXCEPTION`, mirroring
  irrigation's own `v3_metrics.py (ibr_metrics)` convention): no decision to
  judge (the sentinel trace writer never records `initial_skill`/
  `initial_labels`). Counted in the denominator, never a violation on any
  share, tallied separately as `aborted_count`.
- **last_attempt_unparsed_n** / **ibr_stepback_violations_n**: the count of
  decisions whose literal last attempt had no skill, and, of those, the
  ones counted as a PRIMARY violation (every one of them was found ONLY by
  stepping back, since the literal last attempt's own action is `None`
  there).
- **first_tp_missing** / **first_cp_missing**: decisions (ABORTED included,
  like irrigation's own `first_wsa_missing`) whose first-stated TP_LABEL /
  CP_LABEL is blank -- a diagnostic on how much of the corpus had nothing to
  judge, not itself a share.
- Every percent field above is 0-100 (`_pct`, copied verbatim from
  irrigation: `None if denominator == 0 else 100.0 * numerator /
  denominator`), never a bare 0-1 fraction; `ibr_metrics` (and so
  `compute_flood_ibr_v2`) RAISES when there are zero decisions (a
  header-only CSV included) rather than returning an all-zero result.
- A non-ABORTED row with no parsed attempt at all RAISES (mirrors
  irrigation's own `parse_decision`, "first attempt did not parse on a
  non-ABORTED row") instead of degrading silently.
- Mean and range over seeds (`aggregate_over_seeds`).

CLI:

```bash
python examples/single_agent/analysis/flood_ibr_v2.py \
  --csv examples/single_agent/results/JOH_strict_defaults_gemma3_4b_<sha>/Run_42/household_governance_audit.csv \
        examples/single_agent/results/JOH_strict_defaults_gemma3_4b_<sha>/Run_43/household_governance_audit.csv \
        ...
```

`disabled` rows carry no retries, so `initial_skill` == the last attempt's
own skill and `initial_labels` == `final_labels` on every disabled row, and
every share collapses to the same single number for that arm -- the correct
degenerate case, not a bug (see the module docstring).

## 6. Analysis caveats

Two WRR26-fidelity consequences of this rerun that any post-run analysis
(IBR or otherwise) must account for, plus one explicit non-change:

- **Relocated rows keep `has_insurance` as it was at relocation** (item 1
  of section 1): WRR26's own code never touches `has_insurance` on relocate
  (only "buy insurance" and "do nothing" assign it), so a relocated
  household's insurance flag is frozen at whatever it was the year it
  relocated, not meaningfully "current" for any later year (relocated
  households have no further decisions or audit rows anyway, per the
  existing convention, but `simulation_log.csv`'s per-year snapshot still
  carries the agent forward with that frozen flag). **Any analysis of
  insurance-holding rates must exclude relocated agent-years**, exactly as
  IBR already excludes them from the decision denominator (design record
  section 3.1: "every decision by a household that has not relocated").
- **An ABORTED decision executes nothing; WRR26 treats the analogous LLM
  failure as "do nothing"**: `SkillBrokerEngine._write_aborted_sentinel_trace`
  records `executed_skill=""` and `execution_path="aborted"` for a
  fully-unparsed decision -- the household does not act that year at all.
  WRR26's own code has no equivalent concept: `parse_response`'s `decision`
  variable defaults to `"4"` (do nothing) and is simply never reassigned if
  none of the expected digits appear in the response, so an unparsable
  WRR26 response silently becomes a "do nothing" decision, indistinguishable
  in its own log from a household that genuinely chose to do nothing. This
  is a disclosed divergence, not a bug to fix: WAGF's ABORTED sentinel
  exists so a fully-unparsed decision is VISIBLE in the audit trail (not
  silently folded into "do nothing"), which is exactly what lets
  `flood_ibr_v2.py` count and report `aborted_count` separately instead of
  inflating the do_nothing tally the way WRR26's own code would.
- **`examples/governed_flood` (the multi-agent flood domain pack) is NOT
  touched by any of this rerun.** `examples/single_agent/run_flood.py`
  imports it only to register `FloodDomainPack` + validators
  (`import examples.governed_flood  # noqa: F401`); nothing under
  `examples/governed_flood/` itself was read or edited in preparing this
  branch.

## 7. Verification run before the real GPU batch

Before spending GPU hours, re-run the mock smoke (no Ollama) that this
branch was verified with, to confirm the environment and config still
produce 4 complete arms:

```bash
python examples/single_agent/tests/scripted_mock_driver.py \
  --governance-mode strict --agents 100 --years 10 --seed 42 \
  --output examples/single_agent/results/_smoke_strict
# repeat for --governance-mode disabled, --retry-feedback-mode silent,
# and --config-root examples/single_agent/config_variants/nonudge
```

`scripted_mock_driver.py` is tracked in the repo (not a scratch file); its
docstring explains exactly why a plain `--model mock` run does not exercise
governance at all (the generic mock returns bare `{"decision": N}` with no
appraisal labels, so no thinking rule ever fires), and how to patch
`broker.utils.llm_utils.create_llm_invoke` correctly. The same module backs
the automated regression guard
`examples/single_agent/tests/test_prompt_rendering.py` (no prompt, first
attempt or retry, may start with a blank line).

## 8. Full test suite before the batch starts

Run each root separately, foreground, with a timeout:

```bash
python -m pytest examples/single_agent/tests --timeout=300 -q
python -m pytest broker/ --timeout=600 -q
python -m pytest tests/ --timeout=600 -q
python -m pytest examples/irrigation_abm/tests --timeout=600 -q
```

All four must be green before the batch starts (irrigation is unaffected by
this branch; run it anyway to confirm the shared `broker/` surface this
branch touches has not regressed anything it depends on).
