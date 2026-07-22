# WAGF quickstart

WAGF (Water Agent Governance Framework, Python >= 3.10, MIT) is a governed LLM-driven agent framework for coupled human-nature systems: human decision-makers (households, farmers, operators) are modelled as LLM agents, and every decision passes through a Governance Broker — hard feasibility rules plus behavioral-theory "thinking" checks, with retry-and-targeted-feedback on rejection — before it can mutate simulation state. The broker core (`broker/`) is domain-agnostic; domains plug in via YAML (`skill_registry.yaml`, `agent_types.yaml`) plus an optional `DomainPack` subclass, without modifying framework code. Validated reference domains are flood adaptation (Protection Motivation Theory) and irrigation (dual-appraisal), with vaccination (Health Belief Model) as the non-water showcase. The central entry points are `broker/core/skill_broker_engine.py` (the six-step governance pipeline) and `broker/core/experiment.py` (`ExperimentBuilder` / `ExperimentRunner`); a mock-mode demo runs with no LLM at all: `python examples/quickstart/01_barebone.py`.

## Start here

- [Broker package map](./architecture/broker-map.md) — what each `broker/` sub-package owns, and where to add a new domain, governance rule, validator, memory engine, or coupling.
- [Governance pipeline flow](./architecture/governance-pipeline.md) — how a decision travels: LLM proposal → parsing → feasibility screening → behavioral-theory checks → retry with feedback → state mutation → audit trace.
- [Running experiments](./operations/running-experiments.md) — the `examples/` map (quickstart, single_agent, multi_agent, irrigation_abm, vaccination_demo, cat_model, reservoir_control...), invocation forms, config locations, and which operations overwrite results.
- [Testing and paper tooling](./operations/testing-and-papers.md) — running the suite, test layout (`tests/core/`, `tests/sdk/`, `tests/integration/`...), what CI runs, and pointers to audit/analysis tools.

## Repository layout

- `broker/` — the framework package. [`broker/INVARIANTS.md`](../broker/INVARIANTS.md) states the contracts every change must preserve. Sub-packages:
  - `core/` — orchestration: `skill_broker_engine.py` (governance pipeline), `experiment.py` / `experiment_builder.py` / `experiment_runner.py` (run API), `_retry_loop.py`, `agent_initializer.py`, `run_integrity.py`.
  - `agents/` — agent base class, loader, and protocols (`base.py`, `loader.py`, `protocols.py`).
  - `components/` — pluggable building blocks: `memory/` (production memory-engine ABC + implementations), `context/` (context assembly chain), `cognitive/` (reflection engine), `governance/` (skill registry + `temporal_rules/`), plus events, coordination, orchestration, social, analytics, prompt_templates.
  - `validators/` — the validator implementations, split `governance/` (pre-execution rule checks), `agent/`, and `posthoc/`.
  - `governance/` — rule type definitions (`rule_types.py`, `type_validator.py`).
  - `config/` — config schema and agent-type/memory-policy loading (`schema.py`, `agent_types/`, `memory_policy.py`).
  - `coupling/` — external-model coupling layer: BMI hosting (`bmi_source.py`), continuous control (`continuous.py`), grid→agent projection (`projection.py`), contracts and flags. See [docs/COUPLING_CONNECTORS.md](../docs/COUPLING_CONNECTORS.md).
  - `domains/` — domain plug-in seam: `protocol.py` (DomainPack protocol), `registry.py` (DomainPackRegistry), `default.py` (no-op default pack), `water/`.
  - `interfaces/` — typed protocols shared across layers (action taxonomy, observable state, environment/lifecycle protocols, artifacts).
  - `memory/` — research toolkit (persistence, checkpoint/replay, vector DB, graph); distinct from `components/memory/`, which is the governance hot path — see [ARCHITECTURE.md](../ARCHITECTURE.md) "Two memory trees".
  - `simulation/` — base simulation engine, environment, and state manager.
  - `tools/` — operator CLIs: `readiness_report.py` (post-run audit, three profiles), `check_run_integrity.py`, `compare_audit_csv.py`, `replay_shadow.py`, `scaffold_domain.py`, `recover_csv_from_jsonl.py`.
  - `utils/`, `modules/`, `tests/` — parsing/adapters/logging helpers, survey module, and broker-local tests.
- `examples/` — one directory per reference implementation (quickstart tutorial, single_agent + multi_agent flood, governed_flood, irrigation_abm, vaccination_demo, cat_model, reservoir_control, reservoir_control_multidim) with their YAML configs; see [examples/README.md](../examples/README.md).
- `providers/` — LLM provider adapters (`anthropic.py`, `openai_provider.py`, `gemini.py`, `ollama.py`, `factory.py`, `rate_limiter.py`, `smoke.py`); selected via `--model` strings like `anthropic:...` / `openai:...` / `gemini:...` or a bare Ollama tag.
- `tests/` — pytest suite at repo root (~110 top-level files plus `core/`, `sdk/`, `integration/`, `flood/`, `manual/`, `fixtures/`, `toy_domain/`); run with `python -m pytest tests/ -v`. See [tests/README.md](../tests/README.md).
- `docs/` — deep documentation: guides (`docs/guides/`), architecture (`docs/architecture/`), module references (`docs/modules/`), `AUDIT_SCHEMA.md`, `COUPLING_CONNECTORS.md`, and the skills chooser (`docs/skills/wagf-skills.md`).
- `.claude/skills/` — the 8 bundled Claude Code skills, auto-loaded when the repo is opened in Claude Code: `wagf-quickstart`, `wagf-experiment-designer`, `wagf-domain-builder`, `wagf-verification-ladder`, `wagf-coupling-designer`, `llm-agent-audit-trace-analyzer`, `model-coupling-contract-checker`, `abm-reproducibility-checker`.
- `.githooks/` — repo pre-commit hook (see its README); `.github/workflows/test.yml` is CI: `tests/core/` then `tests/sdk/` and `tests/integration/` with `-k "not real_llm"`, on Python 3.10-3.12.
- Paper/analysis tooling: no `paper/` or `analysis/` directory ships in this public tree; post-run analysis lives in `broker/tools/` (readiness reports, audit-CSV comparison, shadow replay). Manuscript content is out of wiki scope.

## Deep docs

- [ARCHITECTURE.md](../ARCHITECTURE.md) — system layers, entry points, the two memory trees, coupling layer.
- [broker/INVARIANTS.md](../broker/INVARIANTS.md) — the contracts (byte-identity, default-OFF features, audit schema) that framework changes must not break.
- [DATA.md](../DATA.md) — what data ships with the repo and provenance/usage constraints.
- [CONTRIBUTING.md](../CONTRIBUTING.md) — dev workflow, test expectations, and post-experiment readiness reports.
- [README.md](../README.md) — install, quick start, example table, YAML-vs-Python extension matrix, documentation index.

## Backlog

Not yet covered by this wiki (read source or `docs/` directly for now):

- The four Start-here pages listed above are the planned page set; any not yet present in `openwiki/` are pending.
- `providers/` internals (factory resolution order, rate limiting, smoke checks).
- The memory research toolkit (`broker/memory/`: persistence, checkpoint/replay, vector DB) beyond the two-trees distinction.
- `broker/components/` breadth — events, coordination, orchestration, social, analytics are unmapped beyond one-liners.
- The survey module (`broker/modules/survey/`) and psychometric/calibration tooling (`broker/core/psychometric.py`, related tests).
- Multi-dimensional setpoint actions and `GridProjector` in `broker/coupling/` (post-v0.6.0, default-OFF).
