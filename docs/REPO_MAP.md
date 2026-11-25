# WAGF Repo Map

One page answering "where does X live" and "which doc do I read first."
Verified against `origin/main` at commit `1a5f7b47` (2026-11-24). This file
describes structure; it does not change any Python/YAML behaviour.

---

## 1. Top-level directories

| Dir | What lives there | Entry points | Who edits it |
|---|---|---|---|
| `broker/` | Framework core: governance pipeline, memory engines, validators, audit writer, lifecycle hooks. Domain-agnostic. | `broker/core/experiment.py` (shim), `broker/core/skill_broker_engine.py::SkillBrokerEngine` | Framework maintainers only; see `broker/INVARIANTS.md` before touching. |
| `broker/run/` | The single entry for every new case: `python -m broker.run CONFIG` reads `global_config.run` from the agent-types YAML, loads the `world`, `agents`, `hooks`, `validators` and `mock` slots, and writes the run manifest and `broker_run.json`. | `python -m broker.run <config>.yaml --model mock` (`broker/run/_entry.py`; import rule in `broker/run/_imports.py`) | Framework maintainers; case authors use the guide `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`. |
| `broker/tools/` | 11 operator CLIs (scaffold, validate, calibrate, audit-compare, recovery). | `python -m broker.tools.<name> --help` | Framework maintainers. |
| `broker/tests/` | Tests for `broker/` internals (135 `test_*.py` files). | `pytest broker/` | Whoever changes `broker/`. |
| `examples/` | Domain packs and runnable experiments (9 example dirs). | `examples/README.md` | Domain researchers; each dir usually has one owner-experiment. |
| `templates/` | Clean copy-and-adapt starter templates for new governed cases (`templates/water_starter/`). | `templates/README.md` | Framework maintainers & domain authors starting new cases. |
| `tests/` | Repo-root test suite — integration, core, sdk, flood, manual, fixtures (`test_*.py` files). | `pytest tests/` | Whoever changes cross-cutting behaviour. |
| `docs/` | Structured User Manual (`docs/index.md`, `mkdocs.yml`) and reference documentation: architecture, guides, module docs, references, skill chooser. | `docs/index.md`, `docs/guides/` | Whoever changes the thing a doc describes. |
| `providers/` | LLM adapter layer (9 files: `providers/__init__.py`, `providers/anthropic.py`, `providers/factory.py`, `providers/gemini.py`, `providers/llm_provider.py`, `providers/ollama.py`, `providers/openai_provider.py`, `providers/rate_limiter.py`, `providers/smoke.py`). Packaged together with `broker/` and imported by `broker/utils/llm_utils.py (create_provider_invoke)`. | `providers/factory.py` | Framework maintainers when adding a new model backend. |
| `ref/` | Reference/comparison material — `RL-ABM-CRSS` (external RL-ABM baseline for the irrigation case). | `ref/README.md` | Read-only reference; rarely edited. |
| `reproduction/` | Analysis code that turns audit traces into the numbers a paper reports (does NOT include run outputs — those are gitignored under each example's results directory). Mirrors the `reproduction/decomposition/` structure also kept on a separate, unmerged submission branch (not present in this tree). | `reproduction/README.md`, `reproduction/decomposition/run_all.py` | Paper authors doing figure/number regeneration. |
| `.claude/skills/` | 8 WAGF-specific Claude Code skills (domain builder, coupling designer, quickstart, experiment designer, audit-trace analyzer, coupling checker, verification ladder, reproducibility checker). | `docs/skills/wagf-skills.md` (chooser table) | Whoever maintains the AI-agent workflow. |
| `.github/workflows/` | CI: one `test.yml` with two jobs (`test`, `scaffold-smoke`). | `.github/workflows/test.yml` | Whoever changes what CI verifies. |

Note: this table omits `.git`, `.githooks`, and the gitignored local
`.research` workspace. The DomainPack protocol reference lives at
`docs/references/domain_pack_protocol_reference.md`.

---

## 1a. Generic modules and examples: where the line is

**Generic** means `broker/` (except `broker/domains/water/` and
`broker/tests/`) plus `providers/`. These two packages are what
`pyproject.toml` ships (`[tool.setuptools.packages.find]` includes
`broker*` and `providers*`; it excludes `examples*`, `tests*`, `docs*`).
**Examples** means `examples/`; see §4 for what each folder is.

**Import direction.** Generic code has no import statement for
`examples`: a syntax-tree scan of every non-test `.py` under `broker/`
found none (the `from examples...` strings that grep finds in a few
files are inside docstrings). The one import by name at run time is the
third row of the table below. Examples import `broker`. The rule is written in
`broker/INVARIANTS.md`, Invariant 5 (Domain-genericity contract), under
"Contract": every generic `broker/` subtree must be domain-agnostic; the
only non-generic trees are domain packages under `broker/domains/` and `broker/tests/`.

**Four places where the split is not clean:**

| Exception | What it means if you add a domain |
|---|---|
| `broker/domains/water/` holds 38 tracked files of flood and irrigation content inside the package. | Put your domain under `examples/` (or a domain subpackage under `broker/domains/`), not in the generic subtrees. |
| `broker/tests/` imports examples as fixtures (`examples/governed_flood/`, `examples/cat_model/`, `examples/single_agent/`, `examples/irrigation_abm/`, `examples/reservoir_control/`, `examples/reservoir_control_multidim/`, `examples/multi_agent/`). | The core tests need `examples/` present; deleting those folders breaks them. |
| `broker/config/schema.py (_import_domain_for_config_path)` picks what to auto-import from the config path: `examples/irrigation_abm/`, `examples/single_agent/`, `examples/multi_agent/flood/` and `examples/governed_flood/` import `broker.domains.water`; any other path imports nothing. | A new domain must import its own pack before loading its config. |
| Generic `broker/` code still contains legacy flood/irrigation names and defaults (for example `HouseholdPerceptionFilter`, `InsuranceInfoProvider`, `FloodDomainConfig`, and the default institutional agent types in `broker/components/cognitive/reflection.py`). | Check the defaults your domain relies on. |

Between examples: `examples/single_agent/` imports `examples/governed_flood/`
(it supplies the flood domain pack); `examples/multi_agent/` and
`examples/governed_flood/` import each other.

These counts were verified at `1a5f7b47`.

---

## 2. Which architecture document to read

Read in this order, top to bottom — each answers a different question:

| Order | Document | Answers | Level |
|---|---|---|---|
| 1 | `README.md` | Why does this framework exist, what does it do | Project pitch |
| 2 | `ARCHITECTURE.md` | What is the framework's strategic shape (layers, extensibility story) | Strategic overview |
| 3 | `docs/architecture/architecture.md` | How the three layers actually pass data at runtime | Operational detail |
| 4 | `broker/INVARIANTS.md` | What contracts must never break, and which test enforces each one | Contracts |
| 5 | `docs/guides/` (start with `docs/guides/quickstart_guide.md` or `docs/guides/domain_pack_guide.md`) | How do I do a specific task (add a domain, run an ablation, calibrate) | How-to |

**Known gap**: this repo previously had a generated `openwiki` prose
layer that is now a local, gitignored artefact and does not exist on a
fresh checkout of `origin/main`. Treat it as a local-only artefact, not
as a normative source for this map.

---

## 3. `broker/` subpackage map

One line per subpackage, main class or CLI read directly from the code:

| Subpackage | Main class / CLI |
|---|---|
| `broker/core/` | `ExperimentBuilder` (`broker/core/experiment_builder.py`), `ExperimentRunner` + `ExperimentConfig` (`broker/core/experiment_runner.py`), `SkillBrokerEngine` (`broker/core/skill_broker_engine.py`) — the governance loop itself |
| `broker/components/analytics/` | `GenericAuditWriter` + `AuditConfig` (`broker/components/analytics/audit.py`) |
| `broker/components/cognitive/` | `AgentReflectionContext`, `ReflectionInsight`, `ReflectionTrigger` (`broker/components/cognitive/reflection.py`) |
| `broker/components/context/` | `ContextBuilder` (ABC, `broker/components/context/builder.py`), `TieredContextBuilder` (`broker/components/context/tiered.py`) |
| `broker/components/coordination/` | `CoordinatorStrategy` (ABC) with `PassthroughStrategy` / `ConflictAwareStrategy` (`broker/components/coordination/coordinator.py`) |
| `broker/components/events/` | `EnvironmentEventManager` (`broker/components/events/manager.py`) |
| `broker/components/governance/` | `SkillRegistry` (`broker/components/governance/registry.py`) |
| `broker/components/memory/` | `MemoryEngine` (ABC, `broker/components/memory/engine.py`) |
| `broker/components/orchestration/` | `InstitutionalLifecycleHandler` (ABC, `broker/components/orchestration/institutional_lifecycle.py`) |
| `broker/components/social/` | `SocialGraph` (ABC) with `GlobalGraph` / `RandomGraph` (`broker/components/social/graph.py`) |
| `broker/validators/agent/` | `AgentValidator` (`broker/validators/agent/agent_validator.py`) |
| `broker/validators/governance/` | `BaseValidator` (ABC, `broker/validators/governance/base_validator.py`); domain frameworks under `broker/validators/governance/frameworks/` |
| `broker/validators/posthoc/` | keyword/thinking-rule post-hoc classifiers |
| `broker/memory/` | Surprise strategies (`broker/memory/strategies/`) and cognitive constraints (`broker/memory/config/`) |
| `broker/coupling/` | `EnvironmentCouplingAdapter` (`broker/coupling/adapter.py`); connector types in `broker/coupling/bmi_source.py` / `broker/coupling/grid_source.py` / `broker/coupling/subprocess_source.py` |
| `broker/calibration/` | `optimize.py` (`broker/calibration/optimize.py`: `OptimizeResult`, `TargetSplit`) + CLI `broker/tools/calibrate.py` |
| `broker/experiments/` | `broker/experiments/replay.py` (`MaskSpec`, `FactorMap`), `broker/experiments/ablation.py`, `broker/experiments/metrics.py` |
| `broker/domains/` | `DomainPackRegistry` (`broker/domains/registry.py`); `broker/domains/default.py` (`DefaultDomainPack`); water reference packs under `broker/domains/water/` |
| `broker/run/` | `main` and `RunContext` (`broker/run/_entry.py`), `Coupled` (a coupled world), slot import rule (`broker/run/_imports.py`); run with `python -m broker.run` |
| `broker/tools/` | 11 CLIs, each `if __name__ == "__main__"` runnable: `scaffold_domain` (`broker/tools/scaffold_domain.py`; writes `world.py` and a `global_config.run` block, no runner; `--physical-only` for decisions with no appraisal), `validate_prompt`, `gen_test_fixture`, `calibrate`, `ablate_factor`, `check_run_integrity`, `check_llm_transport` (read-only journal/log failure counts; `--all-steps` shows every step), `compare_audit_csv`, `readiness_report`, `recover_csv_from_jsonl`, `replay_shadow` |
| `broker/config/` | `GlobalConfig` (Pydantic, `broker/config/schema.py`); `broker/config/agent_types/registry.py` |
| `broker/utils/` | `broker/utils/model_adapter.py` re-exports `ModelAdapter` (defined in `broker/utils/parsing/base.py`) and `UnifiedAdapter` (defined in `broker/utils/parsing/unified_adapter.py`); also `broker/utils/data_loader.py`, `broker/utils/governance_auditor.py` |
| `broker/interfaces/` | `broker/interfaces/skill_types.py` (`SkillProposal`, `ApprovedSkill`, `ExecutionResult`, ...) — the framework's core Protocols and dataclasses |
| `broker/agents/` | `BaseAgent` + `AgentConfig` (`broker/agents/base.py`); `broker/agents/deciders.py` |
| `broker/governance/` | `broker/governance/rule_types.py` (`RuleCategory`, `RuleLevel`, `ConditionType`) |
| `broker/simulation/` | `BaseSimulationEngine` (`broker/simulation/base_simulation_engine.py`) |
| `broker/modules/survey/` | `AgentInitializer` + `AgentProfile` (`broker/modules/survey/agent_initializer.py`) |

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
`examples/single_agent/run_flood.py`), which is unaffected by this.

---

## 4. `examples/` — what's there, what state it's in

| Dir | Role | README | Tests | Run script | Registers DomainPack | Start here |
|---|---|---|---|---|---|---|
| `examples/quickstart/` | Numbered tutorial scripts | yes | no | `examples/quickstart/01_barebone.py`, `examples/quickstart/02_governance.py` (numbered tutorial) | no | `python examples/quickstart/02_governance.py` |
| `examples/single_agent/` | Main case: flood adaptation (hazard affects households, not the reverse); uses the pack in `examples/governed_flood/` | yes | yes (12) | `examples/single_agent/run_flood.py` + 11 `.bat` launchers; paper measures: `python -m examples.single_agent.analysis.paper_measures projection --runs DIR... --out CSV` | yes | `python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100` |
| `examples/irrigation_abm/` | Main case: Colorado River irrigation (two-way: requests change Lake Mead, its level and shortage tier come back) | yes | yes (44) | 3 run scripts (`examples/irrigation_abm/run_experiment.py` is the entry) + 5 `.bat` launchers; read-back: `python examples/irrigation_abm/analysis/simple_prompt_check.py RUN_DIR`; paper measures: `python -m examples.irrigation_abm.analysis.paper_measures {projection,hindcast} --runs DIR... --out CSV` | yes | see `examples/irrigation_abm/README.md` |
| `examples/multi_agent/flood/` | Separate multi-agent flood study; not a main case | yes (`examples/multi_agent/flood/README.md`, `examples/multi_agent/flood/README_research.md`, `examples/multi_agent/flood/README_zh.md`) | yes (24) | `examples/multi_agent/flood/run_unified_experiment.py`; `examples/multi_agent/flood/paper3/` has its own 6 `.bat` launchers | yes | `python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b` |
| `examples/governed_flood/` | Shared flood domain pack + small runner; imported by `examples/single_agent/`, `examples/multi_agent/`, core tests | yes | no | `examples/governed_flood/run_experiment.py` | yes | `python examples/governed_flood/run_experiment.py --model gemma3:4b --years 2 --agents 10` — also the fixture source imported by 15 `broker/tests/` files (`grep -rl "examples\.governed_flood" broker/tests/`), do not delete |
| `examples/cat_model/` | Coupling-layer demo (catastrophe insurance); used by core tests | yes | no | `examples/cat_model/run_cat.py` (single-agent insurer), `examples/cat_model/run_cat_ma.py` (multi-agent pool) | yes | `python examples/cat_model/run_cat.py --model mock --years 3` |
| `examples/reservoir_control/` | Worked example: connecting a new water model through `broker/coupling/` | yes | no | `python -m broker.run` (no separate runner script) | yes | `python -m broker.run examples/reservoir_control/config/reservoir_agent_types.yaml --model mock --years 4 --seed 42 --output examples/reservoir_control/results_ops` |
| `examples/reservoir_control_multidim/` | Same, with three setpoints in one decision | yes | no | `examples/reservoir_control_multidim/run_reservoir_multidim.py` | yes | `python examples/reservoir_control_multidim/run_reservoir_multidim.py --model mock --years 4` |
| `examples/coupling_examples/` | Worked example of a coupling archetype | yes | no | `examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py` | no (worked example, not a paper domain) | `python examples/coupling_examples/archetype_c_subprocess/run_archetype_c.py --model mock --years 4` |

---

## 5. Tests — three locations, one CI command

| Location | File count | What it covers | Run with |
|---|---|---|---|
| `tests/` | 150 `test_*.py` | Repo-root integration/core/sdk/flood/manual suites | `pytest tests/` |
| `broker/tests/` | 135 `test_*.py` | Framework-internal unit + invariant tests | `pytest broker/` |
| `examples/` test suites | 80 `test_*.py`: `examples/irrigation_abm/tests/` 44, `examples/multi_agent/flood/` 24, `examples/single_agent/tests/` 12, other folders 0 | Per-experiment analysis/pipeline checks | run individually per dir; only `examples/single_agent/tests/` is part of the CI command below |

Frozen-case guard tests live at `tests/test_frozen_guard_flood.py` and
`tests/test_frozen_guard_multi_agent.py`.

CI (`.github/workflows/test.yml`, step "Tests (no LLM)") runs, verbatim
(reflowed from the workflow's line continuation):

```
python -m pytest tests/ broker/ examples/single_agent/tests -ra --tb=short --continue-on-collection-errors -k "not real_llm"
```

plus a separate `scaffold-smoke` job that runs
`broker/tools/scaffold_domain.py` → `broker/tools/validate_prompt.py` → the
generated case run through `python -m broker.run <config> --model mock --years 1 --agents 1`
end to end, to catch a class of bug no unit test can (a broken generated
`world.py` or adapter import). The tests under `examples/irrigation_abm/` and
`examples/multi_agent/` (68 files) are not invoked by either CI job; they
are for whoever is actively working in that example directory.

---

## 6. `.bat` launcher index

22 launchers are indexed below.

### `examples/irrigation_abm/` (5)

| File | Purpose (from its own header) |
|---|---|
| `examples/irrigation_abm/check_e4b_status.bat` | One-shot status check of the e4b seed46 recovery run. |
| `examples/irrigation_abm/run_gemma12b_batch.bat` | Gemma-3 12B cross-model batch: 6 runs (3 seeds × governed/ungoverned). |
| `examples/irrigation_abm/run_gemma4_e2b_batch.bat` | Gemma-4 e2b cross-model batch: 10 runs (5 seeds × governed/ungoverned). |
| `examples/irrigation_abm/run_gemma4_e4b_batch.bat` | Gemma-4 e4b cross-model batch: 10 runs (5 seeds × governed/ungoverned). |
| `examples/irrigation_abm/run_gemma4_irrigation_all.bat` | Master launcher chaining e2b → e4b (20 runs total). |

### `examples/multi_agent/flood/paper3/` (6)

| File | Purpose |
|---|---|
| `examples/multi_agent/flood/paper3/rerun_weighted_memory.bat` | Paper-3 rerun applying memory + social + reflection fixes. |
| `examples/multi_agent/flood/paper3/run_gemma4_ablation_b_only.bat` | Gemma-4 e4b, Ablation B only (flat institutional policy, clean memory). |
| `examples/multi_agent/flood/paper3/run_gemma4_full_experiment.bat` | Gemma-4 e4b, full experiment (legacy baseline + clean pivot). |
| `examples/multi_agent/flood/paper3/run_gemma4_ma.bat` | Multi-agent Gemma-4 launcher (resolves repo root, `cd`s into `examples/multi_agent/flood/`). |
| `examples/multi_agent/flood/paper3/run_gemma4_ma_pivot_clean.bat` | Clean-policy pivot batch. |
| `examples/multi_agent/flood/paper3/run_gemma4_ma_pivot_full.bat` | Full pivot: 3-seed pooled Full + 3-seed Ablation B. |

### `examples/single_agent/` (11)

| File | Purpose |
|---|---|
| `examples/single_agent/run_gemma4_26b_disabled.bat` | Fill gemma4:26b Group_C_disabled gap, 5 seeds, no-validator. |
| `examples/single_agent/run_gemma4_26b_governed.bat` | Mirror of the above with `--governance-mode strict`. |
| `examples/single_agent/run_gemma4_crossmodel.bat` | Cross-model batch launcher (resolves repo root + profiles CSV). |
| `examples/single_agent/run_gemma4_remaining_seeds.bat` | Fills in remaining incomplete seeds. |
| `examples/single_agent/run_gemma4_rerun_incomplete.bat` | Reruns runs that ended incomplete. |
| `examples/single_agent/run_pilot_gemma3_4b_v2.bat` | V2 memory-pipeline pilot, Gemma-3 4B × 2 conditions × 2 seeds. |
| `examples/single_agent/run_pilot_gemma4_26b_v2.bat` | V2 memory-pipeline pilot, Gemma-4 26B × 2 conditions × 2 seeds. |
| `examples/single_agent/run_rerun_gemma4_26b_v2.bat` | Gemma-4 26B V2 rerun, fixing the 2026-04-19 priority-schema confound (2 conditions × 5 seeds). |
| `examples/single_agent/run_rerun_gemma4_all_v2.bat` | Master launcher chaining e2b → e4b → 26b V2 reruns. |
| `examples/single_agent/run_rerun_gemma4_e2b_v2.bat` | Gemma-4 e2b V2 rerun (2 conditions × 5 seeds). |
| `examples/single_agent/run_rerun_gemma4_e4b_v2.bat` | Gemma-4 e4b V2 rerun (2 conditions × 5 seeds). |

### Removed launchers

The following obsolete, unreferenced one-off schedulers were removed on
2026-10-12:

- Ensemble: `run_ensemble.bat` (formerly under `examples/irrigation_abm/`).
- Missing-only: `run_wrr_missing_only.ps1` (formerly under `examples/single_agent/`).
- Repair: `run_wrr_repair_run3_and_run45.ps1` (formerly under `examples/single_agent/`).
- Run-3 queue: `run_wrr_run3_full_queue.ps1` (formerly under `examples/single_agent/`).

The three flood scripts wrote under `JOH_FINAL` in `examples/single_agent/`
and passed these seeds: `Run_1 = 42`, `Run_2 = 4202`, `Run_3 = 4203`,
`Run_4 = 4204`, and `Run_5 = 4205`. Missing-only states Runs 1-3; Repair
states Runs 3-5; Run-3 queue uses 4203. This is what the scripts pass, not a
record of which seeds the stored runs hold; for those see
`.claude/skills/llm-agent-audit-trace-analyzer/references/metrics_definitions.md`.

The scripts passed these explicit model options. The flood entries apply to
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

- **Results directories are gitignored**, not committed. `.gitignore`
  excludes output folders such as `results`, `results_humancentric`,
  `results_*`, `results_unified`, `results_ma`, `results_ma_e4b`,
  `results_ops`, and `smoke_results` under the repository and `examples/`.
- **Directory naming embeds the code commit hash**, not just a version
  tag, per the 2026-04-25 "P2: Directory name suggests one code state,
  data was generated by another" incident (see
  `.claude/skills/abm-reproducibility-checker/references/known_failure_patterns.md`)
  — a results dir name alone should let you find the code that produced it.
- **`reproduction/`** is the paper-facing analysis layer: it reads
  gitignored results directories (absent from a fresh clone) and turns audit
  traces into the numbers a paper cites. It mirrors the
  `reproduction/decomposition/` analysis structure kept for a specific paper
  submission (`reproduction/` is the version that ships with the code
  repository).

---

## Related

- `examples/README.md` — example-directory index with start-here commands.
- `docs/skills/wagf-skills.md` — full WAGF Claude-skill chooser table.
- `broker/INVARIANTS.md` — the six framework contracts and their test guards.
