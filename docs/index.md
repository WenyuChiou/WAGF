# WAGF User Manual

**Language: English | [繁體中文](index_zh.md)**

The **Water Agent Governance Framework (WAGF)** connects LLM-based decision agents, explicit physical/cognitive/social governance rules, and water-system models so invalid proposals are blocked, explained, retried, and recorded before any simulation state mutates.

---

## How WAGF Works

Every decision cycle executes a governed broker loop:

1. **Observe & Build Prompt**: The world advances (`advance_step()` or a coupled BMI/subprocess model), syncs variables onto each agent, and renders the prompt template (`prompt_template_file`).
2. **Propose**: The LLM (or built-in `--model mock`) returns a structured block (`<<<DECISION_START>>>...<<<DECISION_END>>>`) parsed into `SkillProposal` (action + appraisals/magnitude).
3. **Validate**: Registered validators check output schema, preconditions, physical/coupling bounds (`FeasibilityBound` / expression rules), institutional rules, and thinking rules.
4. **Block & Retry or Execute**: Failed `ERROR` rules append rule explanations to the retry prompt up to `max_retries`. Valid proposals execute against the world; exhausted retries fall back to `default_skill`.
5. **Audit**: Every attempt, retry reason, label drift, and executed state change is written to `*_governance_audit.csv`, `raw/*.jsonl`, `governance_summary.json`, and `reproducibility_manifest.json`.

---

## Choose Your Starting Path

| Your goal | Where to start | Time |
|---|---|---|
| **Build a new governed water simulation** | Copy `templates/water_starter/` or run `python -m broker.tools.scaffold_domain` | ~5 min |
| **Learn WAGF primitives step by step** | Read [Tutorial Overview](tutorial/README.md) (`01-first-run.md` to `06-measures.md`) | ~15 min |
| **Run standalone code snippets** | Run scripts in `examples/quickstart/` (`01_barebone.py`, `02_governance.py`) | ~2 min |
| **Reproduce Flood / Irrigation papers** | Inspect `examples/single_agent/`, `examples/irrigation_abm/`, and `DATA.md` | Varies |

---

## Path 1: Build Your Own Case (`python -m broker.run`)

Recommended reading order for domain authors building a clean case without legacy paper flags:

1. **Start from a clean starter**: Read [Quickstart Guide](guides/quickstart_guide.md) and inspect `templates/water_starter/` (documented in `templates/README.md`) to run a 2-year smoke case with a live `dead_pool_guard` block -> retry -> repair.
2. **Add your domain structure**: Follow [How to Add a New Domain](guides/HOW_TO_ADD_A_NEW_DOMAIN.md) or generate a skeleton via `python -m broker.tools.scaffold_domain`.
3. **Define configs & prompts**: See [Agent Type Specification Guide](guides/agent_type_specification_guide.md) and [YAML Configuration Reference](references/yaml_configuration_reference.md).
4. **Wire state & physical rules**: Read [Model State in Prompts and Checks](guides/model_state_in_prompt_and_checks.md) and [Coupling Connectors](COUPLING_CONNECTORS.md).
5. **Configure governance & retries**: Review [Governance Layers](guides/governance_layers.md) and [Retry Feedback Guide](guides/retry_feedback_guide.md).
6. **Verify audits & schemas**: Check [Audit Schema](AUDIT_SCHEMA.md) and [CLI Reference & Paper Comparison](guides/readme_reference.md).

---

## Path 2: Learn Core Primitives (`docs/tutorial/` & `examples/quickstart/`)

- **Python SDK & bare-minimum broker**: See [Quickstart Guide](guides/quickstart_guide.md) and run `examples/quickstart/01_barebone.py` / `examples/quickstart/02_governance.py` with `--output .tmp/qs`.
- **Six-chapter mock tutorial**: Follow [Tutorial Overview](tutorial/README.md):
  - [Chapter 1 — First Run](tutorial/01-first-run.md)
  - [Chapter 2 — Rules & Retries](tutorial/02-rules-and-retries.md)
  - [Chapter 3 — Audit Record](tutorial/03-audit.md)
  - [Chapter 4 — Two-Way Water Model](tutorial/04-water-model.md)
  - [Chapter 5 — Resume from Journal](tutorial/05-resume.md)
  - [Chapter 6 — IBR & EHE Measures](tutorial/06-measures.md)

---

## Path 3: Paper Benchmarks & Reproduction (Separate from Starter Learning)

Existing paper benchmarks under `examples/` carry domain-specific calibration tables and historical CLI flags. Keep them separate when learning the core API:

| Domain | Path | What It Contains |
|---|---|---|
| Single-agent Flood (PMT) | `examples/single_agent/` | Legacy 100-household flood adaptation runner (`run_flood.py`), PMT YAML rules, and `agent_initial_profiles.csv` schema |
| Colorado River Irrigation ABM | `examples/irrigation_abm/` | 78-farmer Upper/Lower Basin simulation (`run_experiment.py`), USBR CSV tables (`examples/irrigation_abm/data/README.md`), and optional external CRSS data (`DATA.md`) |
| Multi-agent Flood (PRB) | `examples/multi_agent/flood/` | Spatial Passaic River Basin study (`DATA.md`) |
| Reservoir Control (Coupled) | `examples/reservoir_control/` & `examples/reservoir_control_multidim/` | Single-magnitude and multi-setpoint coupled demos via `python -m broker.run` |
| Reproduction Scripts | `reproduction/README.md` | Post-run metric extraction and frozen-case guard fixtures |

For full repository orientation, see [Repository Map](REPO_MAP.md). For installation issues, model flags, and Windows/Python environment tips, see [Troubleshooting Guide](guides/troubleshooting_guide.md) and [CLI Reference](guides/readme_reference.md).

---

## Viewing This Manual Locally (Offline MkDocs Build)

Install optional documentation dependencies and serve or build static HTML locally from the repository root:

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

Or build standalone offline HTML into `site/` and view in any browser:

```bash
mkdocs build
python -m http.server --directory site 8000
```
