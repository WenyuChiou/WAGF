---
name: wagf-verification-ladder
description: Use when a WAGF user asks to test a new domain end to end, run the smoke pipeline, decide whether a domain is done, continue after a domain runs, or verify a WAGF setup before experiment design or reproducibility audit.
---

# WAGF: Verification Ladder

This skill is the post-domain-builder gate stack. Use it after
`wagf-domain-builder` S7 says the domain runs, and before treating the
domain as experiment-ready or paper-ready.

The ladder has six gates. Run them in order. A later gate never repairs
an earlier one; it only adds new evidence.

## Gate 0 - Environment

Reuse `wagf-quickstart` Phase 1 rather than duplicating the full
environment rubric. The minimum local checks are:

```bash
python -c "import broker; print(broker.__version__)"
python -m pytest --collect-only broker/tests/test_ma_cat_settlement.py broker/tests/test_reservoir_ops_example.py
ollama ps
```

Run `ollama ps` only if Gate 4 real-LLM smoke is planned.

**PASS criteria**

- `broker` imports and prints a version.
- Pytest can collect the two shipped v0.6 template tests.
- For real-LLM work, Ollama is up and the intended model is loaded on
  GPU. If `ollama ps` shows CPU fallback for the active model, stop and
  fix the local Ollama/GPU setup before Gate 4.

**Failure triage**

| Symptom | Likely cause | Action |
|---|---|---|
| `ModuleNotFoundError: broker` | Running outside repo root or env not installed | Move to repo root; install requirements; rerun import check |
| Pytest collection fails | Broken local install or stale dependencies | Read the first import/collection error; fix before domain debugging |
| `ollama ps` empty | Daemon/model not running | Start Ollama, pull/run the model, then rerun `ollama ps` |
| Model shown but not GPU-backed | CPU fallback incident class | Reduce model size or fix GPU runtime; do not time a Gate 4 smoke on CPU fallback |

## Gate 1 - Config-Time Validation

Run the static prompt/YAML validator on the domain's actual agent config.
The shipped v0.6 examples are:

```bash
python -m broker.tools.validate_prompt examples/cat_model/config/ma_cat_agent_types.yaml
python -m broker.tools.validate_prompt examples/reservoir_control/config/reservoir_agent_types.yaml
```

For a new domain, replace the path with its existing
`agent_types.yaml` file:

```bash
python -m broker.tools.validate_prompt <path-to-agent_types.yaml>
```

Do not invent flags. `--agent-type` and `--strict` are the supported
optional flags.

**PASS criteria**

- Command exits 0.
- No BLOCKER placeholders remain.
- No dead rule keys, no unknown `global_config` keys, and no prompt
  placeholders that the broker or DomainPack cannot fill.

**Failure triage**

| Lint message | What it usually means | Edit target |
|---|---|---|
| BLOCKER / placeholder text | Scaffold text survived into production config | Prompt template or YAML field named in the diagnostic |
| Unknown placeholder | Prompt expects a field not produced by broker/DomainPack/dynamic_state | Add the producer or remove the placeholder |
| Dead rule key | G4 / 6N-E class: rule block is under a key the loader ignores | Move to `thinking_rules` or the loader-supported key named by the diagnostic |
| Unknown `global_config` key | Config drift or typo | Use the schema-supported spelling; do not assume unknown keys are harmless |

## Gate 2 - Mock Smoke, the Determinism Gate

Run the domain through its runner with `--model mock`. The shipped v0.6
mock smokes are:

```bash
python examples/cat_model/run_cat_ma.py --model mock --years 2 --output examples/cat_model/results_ma
python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4 --output examples/reservoir_control/results_ops
# --strict belongs on YOUR domain's run dir; the shipped example dirs may
# predate run_integrity.json and would fail spuriously under --strict.
python -m broker.tools.check_run_integrity <your_run_dir> --strict
```

For a new domain, use its actual runner and only the flags shown by that
runner's `--help`.

**PASS criteria**

- Runner exits 0.
- Audit rows equal `agents * periods` for every agent type expected to
  decide. This is the conservation check.
- `<run_dir>/reproducibility_manifest.json` exists.
- `<run_dir>/run_integrity.json` exists and has `integrity_ok: true`.
- No unexpected `failed_rules`. The documented `Unknown` failed_rules
  label from PMT-style format mocks is expected only when the error
  message is the missing-required-fields format check described in
  `docs/AUDIT_SCHEMA.md`.

**Failure triage**

| Symptom | Likely cause | Action |
|---|---|---|
| Rows shorter than `agents * periods` | F1-class abort, uncaught runner exception, or mock cache not installed | Check stdout and raw JSONL; confirm scripted mocks are installed before `runner.run()` |
| Missing manifest or run integrity | Runner bypassed the production output path | Use the production ExperimentBuilder runner path, not an ad hoc loop |
| `integrity_ok: false` | Runtime did not instantiate what config promised | Run `python -m broker.tools.check_run_integrity <run_dir> --strict` and fix the reported contract |
| `[Governance:Diagnostic] Key collision` with identical values | Benign key-collision diagnostic | Document it; do not treat as a failed gate by itself |
| `failed_rules=Unknown` everywhere | Usually the documented PMT-style format mock path | Verify error text; expected only for the frozen format-check producer |

## Gate 3 - Domain Tests

Write the domain test file before calling the domain done. Copy the
closest shipped template:

- `broker/tests/test_ma_cat_settlement.py` for period-end multi-agent
  domains.
- `broker/tests/test_reservoir_ops_example.py` for continuous-control
  domains.

Run the template tests and the new domain test:

```bash
python -m pytest broker/tests/test_ma_cat_settlement.py
python -m pytest broker/tests/test_reservoir_ops_example.py
python -m pytest <path-to-your-domain-test.py>
```

**Minimum test set**

- End-to-end row conservation: rows equal `agents * periods`.
- Wall fires, retry happens, and retry resolves. Assert
  `retry_count` AND `failed_rules` AND final `status`; never use `OR`
  between those conditions.
- Arithmetic pin against a hand calculation for at least one physical
  or financial transition.
- Registration isolation: importing this domain must not contaminate
  other DomainPack/framework registrations.
- Scripted mocks installed through `runner._llm_cache`, the production
  seam. Never frame-sniff rendered prompts as the governed-path test
  oracle.

**Failure triage**

| Test failure | Likely cause | Action |
|---|---|---|
| Retry assertion passes with `OR` | Test is not proving recovery | Rewrite to require retry AND failed_rules AND approved final status |
| Wall never fires | Scenario arithmetic does not cross the threshold | Recompute the fixture by hand and pin the threshold in the test |
| Mock needs rendered-prompt scraping | Mock is coupled to phrasing instead of broker behavior | Install scripted mocks via `runner._llm_cache` and assert audit/output state |
| Registration leak | Import side effect pollutes global registry | Move registration into the domain package's explicit import path |

## Gate 4 - Real-LLM Smoke, the Format-Compliance Gate

Run a small local-model smoke after Gate 2 and Gate 3 are green. The
reference model from the 2026-06-10 incidents is `gemma4:e4b`.

```bash
ollama ps
python examples/cat_model/run_cat_ma.py --model gemma4:e4b --years 1 --output examples/cat_model/results_ma_e4b
python examples/reservoir_control/run_reservoir_ops.py --model gemma4:e4b --years 4 --output examples/reservoir_control/results_ops_e4b
```

For a new domain, use 1-4 periods and the smallest agent count that
still exercises every agent type and every critical wall.

**PASS criteria**

- Runner exits cleanly.
- Every agent-period row is APPROVED or explicitly explained.
- Retry/fallback rates are reviewed, not ignored.
- `missing_world_state` is absent unless the test is intentionally
  exercising an honest missing-key path.
- Every `REJECTED_FALLBACK` row is investigated and classified as
  format, governance, or domain-data failure.

**The e4b trap checklist**

1. `### OPTIONS` renders a real menu, not `[N/A]`; hub-less path needs
   `dynamic_state["options_text"]` injection with numbering locked to
   `parsing.skill_map`.
2. `decision` field has an explicit `description`; the format
   builder's default claims "1, 2, or 3" regardless of menu size.
3. Numeric fields demand digits-only in their description.
4. `num_predict` is large enough; the influencer 1024->2048
   truncation case was real.
5. Audit check: retry/fallback rates, `missing_world_state` absent,
   `REJECTED_FALLBACK` rows investigated as format vs governance.

**Failure triage**

| Symptom | Likely cause | Action |
|---|---|---|
| Prompt shows `[N/A]` under options | Hub-less builder did not populate options | Inject `dynamic_state["options_text"]`; keep numbering in sync with `parsing.skill_map` |
| Model chooses non-existent option | Hardcoded/default decision description misleads it | Give the `decision` output field an explicit menu-aware description |
| Numeric parse failures | Description allows words, units, or prose | Require digits-only numeric fields |
| Truncated JSON / missing closing marker | `num_predict` too low | Increase `num_predict` and rerun the small smoke |
| High fallback rate | Could be schema, governance, or missing world state | Inspect raw trace and audit columns before changing validators |

## Gate 5 - Done Definition and Hand-Offs

A domain is "done" only after Gates 0-4 have evidence and Gate 5
routes the next workflow.

```bash
python -m broker.tools.check_run_integrity <run_dir> --strict
python -m broker.tools.compare_audit_csv <baseline-audit.csv> <candidate-audit.csv>
```

Use `compare_audit_csv` for baseline comparisons. Do not use raw
`sha256` as the only check; audit CSVs contain wall-clock and
set-order noise such as `mem_top_source`-adjacent drift. If freezing a
baseline, record it under `.baselines/BASELINE_HASHES.md`.

**PASS criteria**

- One row per gate in the final PASS/FAIL table.
- Every PASS row names the command that was run and the output path it
  checked.
- Every FAIL row has an owner and next action.
- The next skill is selected from the hand-off table below.

**Failure triage**

| Situation | Action |
|---|---|
| Coupled domain | Load `model-coupling-contract-checker` next |
| Experiment design | Load `wagf-experiment-designer` next |
| Paper-bound or submission-bound run | Load `abm-reproducibility-checker` next |
| Audit traces need metrics | Load `llm-agent-audit-trace-analyzer` after the experiment produces traces |
| Baseline diff fails | Use `compare_audit_csv` samples to classify structural vs timestamp/set-order drift |

## Refusal Protocol

The skill MUST refuse to:

1. Declare any gate passed without running that gate's command and
   reading the output.
2. Invent metrics, pass criteria, model tags, command flags, or file
   paths.
3. Run or bless Gate 4 before Gate 2 mock smoke is green. Real-LLM
   before mock is undebuggable.
4. Treat `failed_rules=Unknown` as benign without checking the paired
   error message against the documented PMT-style format producer.
5. Claim a coupled domain is done without `workers=1` and the
   `model-coupling-contract-checker` hand-off.

## Hand-Offs

| After the ladder finds... | Invoke next |
|---|---|
| Coupling contract, external simulator, or feedback loop risk | `model-coupling-contract-checker` |
| A green domain that needs a research matrix | `wagf-experiment-designer` |
| Completed traces that need governance metrics | `llm-agent-audit-trace-analyzer` |
| Submission or artifact-freeze preparation | `abm-reproducibility-checker` |
| Environment/setup failure | `wagf-quickstart` Phase 1 remediation only |

