# WAGF Repo Map

One page answering "where does X live" and "which doc do I read first."
Verified against `origin/main` at commit `e0eee08c` (2026-09). This file
describes structure; it does not change any Python/YAML behaviour.

---

## 1. Top-level directories

| Dir | What lives there | Entry points | Who edits it |
|---|---|---|---|
| `broker/` | Framework core: governance pipeline, memory engines, validators, audit writer, lifecycle hooks. Domain-agnostic. | `broker/core/experiment.py` (shim), `broker/core/skill_broker_engine.py::SkillBrokerEngine` | Framework maintainers only; see `broker/INVARIANTS.md` before touching. |
| `broker/tools/` | 10 operator CLIs (scaffold, validate, calibrate, audit-compare, recovery). | `python -m broker.tools.<name> --help` | Framework maintainers. |
| `broker/tests/` | Tests for `broker/` internals (105 `test_*.py` files). | `pytest broker/` | Whoever changes `broker/`. |
| `examples/` | Domain packs and runnable experiments (11 example dirs). | `examples/README.md` | Domain researchers; each dir usually has one owner-experiment. |
| `tests/` | Repo-root test suite — integration, core, sdk, flood, manual, fixtures (131 `test_*.py` files). | `pytest tests/` | Whoever changes cross-cutting behaviour. |
| `docs/` | Reference documentation: architecture, guides, module docs, references, multi-agent specs, skill chooser (74 files total, including this map). | `docs/architecture/architecture.md`, `docs/guides/` | Whoever changes the thing a doc describes. |
| `providers/` | LLM adapter layer (9 files: `__init__.py`, `anthropic.py`, `factory.py`, `gemini.py`, `llm_provider.py`, `ollama.py`, `openai_provider.py`, `rate_limiter.py`, `smoke.py`). | `providers/factory.py` | Framework maintainers when adding a new model backend. |
| `ref/` | Reference/comparison material — `RL-ABM-CRSS` (external RL-ABM baseline for the irrigation case). | `ref/README.md` | Read-only reference; rarely edited. |
| `reproduction/` | Analysis code that turns audit traces into the numbers a paper reports (does NOT include run outputs — those are gitignored `examples/*/results/`). Mirrors the `decomposition/` analysis that also exists under `SUBMISSION_2026/` on a separate, unmerged submission branch (not present in this tree — verified absent from `origin/main`). | `reproduction/README.md`, `reproduction/decomposition/run_all.py` | Paper authors doing figure/number regeneration. |
| `.claude/skills/` | 8 WAGF-specific Claude Code skills (domain builder, coupling designer, quickstart, experiment designer, audit-trace analyzer, coupling checker, verification ladder, reproducibility checker). | `docs/skills/wagf-skills.md` (chooser table) | Whoever maintains the AI-agent workflow. |
| `.github/workflows/` | CI: one `test.yml` with two jobs (`test`, `scaffold-smoke`). | `.github/workflows/test.yml` | Whoever changes what CI verifies. |

Note: this table omits `.git`, `.githooks`, `.research` (session-local
AI workspace, not framework structure).

---

## 2. Which architecture document to read

Read in this order, top to bottom — each answers a different question:

| Order | Document | Answers | Level |
|---|---|---|---|
| 1 | `README.md` | Why does this framework exist, what does it do | Project pitch |
| 2 | `ARCHITECTURE.md` | What is the framework's strategic shape (layers, extensibility story) | Strategic overview |
| 3 | `docs/architecture/architecture.md` | How the three layers actually pass data at runtime | Operational detail |
| 4 | `broker/INVARIANTS.md` | What contracts must never break, and which test enforces each one | Contracts |
| 5 | `docs/guides/` (start with `quickstart_guide.md` or `domain_pack_guide.md`) | How do I do a specific task (add a domain, run an ablation, calibrate) | How-to |

**Known gap**: this repo previously had a generated `openwiki/` prose
layer (added `3cb67302`, 2026-07-21) that would have sat between steps
3 and 5. openwiki/ was removed from the repo on 2026-08-07 (8709dbc8)
and is now a local, gitignored artefact; the project-local CLAUDE.md
(also gitignored, and itself not part of this repository's tracked
tree — see `.gitignore:274`) still points at it. Neither file exists
on a fresh checkout of `origin/main`, so treat both as local-only
artefacts, not as normative sources for this map. This map does not
fix either file (out of scope for a docs-structure PR); flagging it
here so the next person doesn't go looking for a file that a fresh
clone will not have.

---

## 3. `broker/` subpackage map

One line per subpackage, main class or CLI read directly from the code:

| Subpackage | Main class / CLI |
|---|---|
| `core/` | `ExperimentBuilder` (`experiment_builder.py`), `ExperimentRunner` + `ExperimentConfig` (`experiment_runner.py`), `SkillBrokerEngine` (`skill_broker_engine.py`) — the governance loop itself |
| `components/analytics/` | `GenericAuditWriter` + `AuditConfig` (`audit.py`) |
| `components/cognitive/` | `AgentReflectionContext`, `ReflectionInsight`, `ReflectionTrigger` (`reflection.py`) |
| `components/context/` | `ContextBuilder` (ABC, `builder.py`), `TieredContextBuilder` |
| `components/coordination/` | `CoordinatorStrategy` (ABC) with `PassthroughStrategy` / `ConflictAwareStrategy` (`coordinator.py`) |
| `components/events/` | `EnvironmentEventManager` (`manager.py`) |
| `components/governance/` | `SkillRegistry` (`registry.py`) |
| `components/memory/` | `MemoryEngine` (ABC, `engine.py`) |
| `components/orchestration/` | `InstitutionalLifecycleHandler` (ABC, `institutional_lifecycle.py`) |
| `components/social/` | `SocialGraph` (ABC) with `GlobalGraph` / `RandomGraph` (`graph.py`) |
| `validators/agent/` | `AgentValidator` (`agent_validator.py`) |
| `validators/governance/` | `BaseValidator` (ABC, `base_validator.py`); domain frameworks under `frameworks/` |
| `validators/posthoc` | keyword/thinking-rule post-hoc classifiers |
| `memory/` | `UnifiedCognitiveEngine` + `UnifiedMemoryItem` (`unified_engine.py`); strategies under `strategies/` |
| `coupling/` | `EnvironmentCouplingAdapter` (`adapter.py`); connector types in `bmi_source.py` / `grid_source.py` / `subprocess_source.py` |
| `calibration/` | `optimize.py` (`OptimizeResult`, `TargetSplit`) + CLI `broker/tools/calibrate.py` |
| `experiments/` | `replay.py` (`MaskSpec`, `FactorMap`), `ablation.py`, `metrics.py` |
| `domains/` | `DomainPackRegistry` (`registry.py`); `default.py` (`DefaultDomainPack`); water reference packs under `domains/water/` |
| `tools/` | 10 CLIs, each `if __name__ == "__main__"` runnable: `scaffold_domain`, `validate_prompt`, `gen_test_fixture`, `calibrate`, `ablate_factor`, `check_run_integrity`, `compare_audit_csv`, `readiness_report`, `recover_csv_from_jsonl`, `replay_shadow` |
| `config/` | `GlobalConfig` (Pydantic, `schema.py`); `agent_types/registry.py` |
| `utils/` | `model_adapter.py` re-exports `ModelAdapter` (defined in `parsing/base.py`) and `UnifiedAdapter` (defined in `parsing/unified_adapter.py`); also `data_loader.py`, `governance_auditor.py` |
| `interfaces/` | `skill_types.py` (`SkillProposal`, `ApprovedSkill`, `ExecutionResult`, ...) — the framework's core Protocols and dataclasses |
| `agents/` | `BaseAgent` + `AgentConfig` (`base.py`); `deciders.py` |
| `governance/` | `rule_types.py` (`RuleCategory`, `RuleLevel`, `ConditionType`) |
| `simulation/` | `BaseSimulationEngine` (`base_simulation_engine.py`) |
| `modules/survey/` | `AgentInitializer` + `AgentProfile` (`agent_initializer.py`) |

**Known wart** (do not fix in this PR): `broker/__init__.py`'s `__all__`
lists 8 names (`ExperimentBuilder`, `HumanCentricMemoryEngine`,
`InteractionHub`, `MemoryEngine`, `TieredContextBuilder`,
`WindowMemoryEngine`, `create_social_graph`, `load_agents_from_csv`).
`ExperimentBuilder` IS in that list — but `ExperimentRunner` is
imported into the `broker` namespace one line above (`from
.core.experiment import ExperimentBuilder, ExperimentRunner`) and is
NOT in `__all__`, and `ExperimentConfig` is never imported into the
`broker` namespace at all (only reachable via `broker.core.experiment`
or `broker.core.experiment_runner`). Direct imports
(`from broker import ExperimentRunner`) still work regardless of
`__all__`; only `from broker import *` would miss it. Examples import
`ExperimentBuilder` from `broker` directly (e.g.
`examples/single_agent/run_flood.py:1233`), which is unaffected by
this.

---

## 4. `examples/` — what's there, what state it's in

| Dir | README | Tests | Run script | Registers DomainPack | Start here |
|---|---|---|---|---|---|
| `quickstart/` | yes | no | `01_barebone.py`, `02_governance.py` (numbered tutorial) | no | `python examples/quickstart/02_governance.py` |
| `single_agent/` | yes | no | `run_flood.py` + 11 `.bat` launchers | yes | `python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100` |
| `irrigation_abm/` | yes | yes | 3 run scripts + 5 `.bat` launchers | yes | see `examples/irrigation_abm/README.md` |
| `multi_agent/flood/` | yes (`README.md`, `README_research.md`, `README_zh.md`) | yes | `run_unified_experiment.py`; `paper3/` has its own 6 `.bat` launchers | yes | `python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b` |
| `governed_flood/` | yes | no | `run_experiment.py` | yes | `python examples/governed_flood/run_experiment.py --model gemma3:4b --years 3 --agents 10` — also the fixture source imported by 17 `broker/tests/` files (`grep -rl "import examples.governed_flood\|from examples.governed_flood" broker/tests/`), do not delete |
| `vaccination_demo/` | yes | yes | run scripts + `run_vaccination_batch.bat` | yes | see `examples/vaccination_demo/README.md` |
| `cat_model/` | **added this PR** | no | `run_cat.py` (single-agent insurer), `run_cat_ma.py` (multi-agent pool) | yes | `python examples/cat_model/run_cat.py --model mock --years 3` |
| `reservoir_control/` | **added this PR** | no | `run_reservoir_ops.py` | yes | `python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4` |
| `reservoir_control_multidim/` | **added this PR** | no | `run_reservoir_multidim.py` | yes | `python examples/reservoir_control_multidim/run_reservoir_multidim.py --model mock --years 4` |
| `coupling_examples/` | **added this PR** | no | `archetype_c_subprocess/run_archetype_c.py` | no (worked example, not a paper domain) | `python examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py --model mock --years 4` |
| `_test_fixtures/` | **added this PR** | no (consumed by `tests/integration/test_e2e_genericity.py`) | none (fixture, not runnable standalone) | yes — registered under key `"traffic"` (directory is `fake_traffic/`) | not runnable directly — read `tests/integration/test_e2e_genericity.py` |

---

## 5. Tests — three locations, one CI command

| Location | File count | What it covers | Run with |
|---|---|---|---|
| `tests/` | 131 `test_*.py` | Repo-root integration/core/sdk/flood/manual suites | `pytest tests/` |
| `broker/tests/` | 105 `test_*.py` | Framework-internal unit + invariant tests | `pytest broker/` |
| `examples/**/test_*.py` | 28 `test_*.py` total (`find examples -name "test_*.py"`\|`wc -l`): 27 inside `tests/` dirs under `irrigation_abm/`, `multi_agent/flood/paper3/`, `vaccination_demo/`, plus 1 outside any `tests/` dir at `multi_agent/flood/parametric/test_household_decider.py` | Per-experiment analysis/pipeline checks | run individually per dir; **not** part of the CI command below |

CI (`.github/workflows/test.yml:63-65`) runs, verbatim (reflowed from
the workflow's line continuation):

```
python -m pytest tests/ broker/ -ra --tb=short --continue-on-collection-errors -k "not real_llm"
```

plus a separate `scaffold-smoke` job that runs
`scaffold_domain` → `validate_prompt` → the generated
`run_experiment.py --model mock --years 1 --agents 1` end to end, to
catch a class of bug no unit test can (a broken generated-runner
import). None of the 28 `examples/**/test_*.py` files are invoked by
either CI job — they are for whoever is actively working in that
example directory.

---

## 6. `.bat` launcher index

23 launchers exist today (the pre-audit estimate for this PR was 18;
verified count is higher because `single_agent/` has 11, not 6, and
`vaccination_demo/` has one that wasn't in the original count). Not
moved in this PR — indexed only.

### `examples/irrigation_abm/` (5)

| File | Purpose (from its own header) |
|---|---|
| `check_e4b_status.bat` | One-shot status check of the e4b seed46 recovery run. |
| `run_gemma12b_batch.bat` | Gemma-3 12B cross-model batch: 6 runs (3 seeds × governed/ungoverned). |
| `run_gemma4_e2b_batch.bat` | Gemma-4 e2b cross-model batch: 10 runs (5 seeds × governed/ungoverned). |
| `run_gemma4_e4b_batch.bat` | Gemma-4 e4b cross-model batch: 10 runs (5 seeds × governed/ungoverned). |
| `run_gemma4_irrigation_all.bat` | Master launcher chaining e2b → e4b (20 runs total). |

### `examples/multi_agent/flood/paper3/` (6)

| File | Purpose |
|---|---|
| `rerun_weighted_memory.bat` | Paper-3 rerun applying memory + social + reflection fixes. |
| `run_gemma4_ablation_b_only.bat` | Gemma-4 e4b, Ablation B only (flat institutional policy, clean memory). |
| `run_gemma4_full_experiment.bat` | Gemma-4 e4b, full experiment (legacy baseline + clean pivot). |
| `run_gemma4_ma.bat` | Multi-agent Gemma-4 launcher (resolves repo root, `cd`s into `examples/multi_agent/flood`). |
| `run_gemma4_ma_pivot_clean.bat` | Clean-policy pivot batch. |
| `run_gemma4_ma_pivot_full.bat` | Full pivot: 3-seed pooled Full + 3-seed Ablation B. |

### `examples/single_agent/` (11)

| File | Purpose |
|---|---|
| `run_gemma4_26b_disabled.bat` | Fill gemma4:26b Group_C_disabled gap, 5 seeds, no-validator. |
| `run_gemma4_26b_governed.bat` | Mirror of the above with `--governance-mode strict`. |
| `run_gemma4_crossmodel.bat` | Cross-model batch launcher (resolves repo root + profiles CSV). |
| `run_gemma4_remaining_seeds.bat` | Fills in remaining incomplete seeds. |
| `run_gemma4_rerun_incomplete.bat` | Reruns runs that ended incomplete. |
| `run_pilot_gemma3_4b_v2.bat` | V2 memory-pipeline pilot, Gemma-3 4B × 2 conditions × 2 seeds. |
| `run_pilot_gemma4_26b_v2.bat` | V2 memory-pipeline pilot, Gemma-4 26B × 2 conditions × 2 seeds. |
| `run_rerun_gemma4_26b_v2.bat` | Gemma-4 26B V2 rerun, fixing the 2026-04-19 priority-schema confound (2 conditions × 5 seeds). |
| `run_rerun_gemma4_all_v2.bat` | Master launcher chaining e2b → e4b → 26b V2 reruns. |
| `run_rerun_gemma4_e2b_v2.bat` | Gemma-4 e2b V2 rerun (2 conditions × 5 seeds). |
| `run_rerun_gemma4_e4b_v2.bat` | Gemma-4 e4b V2 rerun (2 conditions × 5 seeds). |

### `examples/vaccination_demo/` (1)

| File | Purpose |
|---|---|
| `run_vaccination_batch.bat` | Tier-2 showcase batch: 3 seeds × 2 models = 6 runs; Windows companion to `run_vaccination_batch.sh`. |

### Removed launchers

The following obsolete, unreferenced one-off schedulers were removed on
2026-10-12. They were last present at commit `252b3f60`; recover any with
`git show 252b3f60:<path>`.

- Ensemble: `examples/irrigation_abm/run_ensemble.bat`.
- Missing-only: `examples/single_agent/run_wrr_missing_only.ps1`.
- Repair: `examples/single_agent/run_wrr_repair_run3_and_run45.ps1`.
- Run-3 queue: `examples/single_agent/run_wrr_run3_full_queue.ps1`.

The three flood scripts write under `examples/single_agent/results/JOH_FINAL`
and pass these seeds: `Run_1 = 42`, `Run_2 = 4202`, `Run_3 = 4203`,
`Run_4 = 4204`, and `Run_5 = 4205`. Missing-only states Runs 1-3; Repair
states Runs 3-5; Run-3 queue uses 4203. This is what the scripts pass, not a
record of which seeds the stored runs hold; for those see
`.claude/skills/llm-agent-audit-trace-analyzer/references/metrics_definitions.md`.

The scripts pass these explicit model options. The flood entries apply to
Group_B/Group_C; their Group_A baseline commands do not pass these options.

| Model | `num-ctx` | `num-predict` | Launcher(s) |
|---|---|---|---|
| `ministral-3:3b` | 8192 | 1536 | Missing-only |
| `ministral-3:3b` | 4096 | 1024 | Repair |
| `ministral-3:8b` | 8192 | 1536 | Missing-only |
| `ministral-3:8b` | 4096 | 1024 | Repair, Run-3 queue |
| `ministral-3:14b` | 8192 | 1536 | Missing-only, Repair, Run-3 queue |
| `gemma3:4b` | 8192 | 1536 | Missing-only |
| `gemma3:4b` | 4096 | 1024 | Repair |
| `gemma3:4b` | 8192 | 4096 | Ensemble |
| `gemma3:12b` | 8192 | 1536 | Missing-only, Repair |
| `gemma3:27b` | 8192 | 1536 | Missing-only, Repair, Run-3 queue |

---

## 7. Results and data conventions

- **`results/` directories are gitignored**, not committed. `.gitignore`
  covers `results/`, `results_humancentric/`,
  `examples/single_agent/results_*/`, `examples/multi_agent/results_unified/`,
  `examples/cat_model/results_ma/`, `examples/cat_model/results_ma_e4b/`,
  `examples/reservoir_control/results_ops/`,
  `examples/reservoir_control_multidim/results_*/`, and
  `tests/smoke_results/`.
- **Directory naming embeds the code commit hash**, not just a version
  tag, per the 2026-04-25 "P2: Directory name suggests one code state,
  data was generated by another" incident (see
  `.claude/skills/abm-reproducibility-checker/references/known_failure_patterns.md`)
  — a results dir name alone should let you find the code that produced it.
- **`reproduction/`** is the paper-facing analysis layer: it reads
  `examples/*/results/` (absent from a fresh clone) and turns audit
  traces into the numbers a paper cites. It mirrors the same
  `decomposition/` analysis structure that lives under
  `SUBMISSION_2026/` on a separate submission branch not present in
  this tree — `reproduction/` is the version that ships with the code
  repository; `SUBMISSION_2026/` is the version that ships with a
  specific paper submission.

---

## Related

- `examples/README.md` — example-directory index with start-here commands.
- `docs/skills/wagf-skills.md` — full WAGF Claude-skill chooser table.
- `broker/INVARIANTS.md` — the six framework contracts and their test guards.
