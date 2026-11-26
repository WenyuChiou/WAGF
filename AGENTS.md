# AGENTS.md — Water Agent Governance Framework (WAGF)

WAGF is a cognitive governance middleware for LLM-driven human-water agent-based models. It connects LLM agents, YAML/Python governance rules, memory/reflection modules, and external water simulators so invalid proposals are blocked, explained, retried, and recorded before any simulation state mutates.

## Current Release Scope (v0.6 / Framework Paper)

- **In scope (production & framework paper)**: generic `broker/`, `providers/`, `templates/water_starter/`, and **single-agent-type** cases (`examples/single_agent/`, `examples/irrigation_abm/`, `examples/reservoir_control/`, `examples/reservoir_control_multidim/`) run via `python -m broker.run CONFIG` or frozen paper runners. Note: single-agent-type covers both single-operator (`N=1`) and homogeneous populations (`N=78`, `N=100`).
- **Experimental / deferred (next study)**: `broker/components/coordination/`, `broker/components/social/`, `broker/components/orchestration/`, and `examples/multi_agent/`. Treat these as **Pre-1.0 Experimental** hooks for follow-up heterogeneous multi-actor (household + insurer + government) and asynchronous knowledge-graph social studies. Do not wire them into default single-agent-type `broker.run` paths or refactor them unless explicitly tasked.

## Repository Rules

1. **Follow `broker/INVARIANTS.md`**:
   - Never import `examples/*` inside non-test `broker/` code.
   - Never hardcode domain-specific tokens (flood/irrigation construct names, domain skill names) inside generic `broker/` subtrees; put domain packs under `broker/domains/<domain>/` or `examples/<domain>/`.
   - Preserve audit schema contracts (`raw/*.jsonl` traces are source of truth; CSV projections live in `broker/components/analytics/audit.py`).
2. **Never break frozen paper cases**: `examples/single_agent/` and `examples/irrigation_abm/` configs and mock-baseline outputs are guarded by frozen-guard tests; never alter them casually.
3. **Citations and docs**: cite code as `path/to/file.py (SymbolName)`, never volatile line numbers. Run doc path and manual checks after changing any markdown or YAML reference.

## Verification Commands

- **Core + integration tests (no live LLM)**:
  `python -m pytest tests/ broker/ examples/single_agent/tests -ra --tb=short --continue-on-collection-errors -k "not real_llm"`
- **Scaffold smoke check**:
  `python -m broker.tools.scaffold_domain` + `python -m broker.tools.validate_prompt` + `python -m broker.run <config> --model mock --years 1 --agents 1`
- **Docs & manual check**:
  `python -m pytest tests/test_docs_paths_exist.py tests/test_skill_paths_exist.py tests/test_user_manual.py --timeout=600 -q`
  `python -m mkdocs build --strict`

## Protected Files (Require Explicit Owner Approval)

- `CLAUDE.md`, `AGENTS.md`, `*/AGENTS.md`, `.github/workflows/`, `.githooks/`
- API keys / env files (`~/.claude/.env`, `.wagf/api_keys.env`) — never read or print.
