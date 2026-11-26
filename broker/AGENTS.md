# AGENTS.md — `broker/` Core Package Rules

This directory contains the generic WAGF governance middleware (plus `broker/domains/` and `broker/tests/`).

## Hard Invariants (see `broker/INVARIANTS.md`)

1. **No reverse imports**: non-test code under `broker/` MUST NEVER import from `examples/`.
2. **Domain genericity (`TestDomainGenericity`)**: generic `broker/` modules (`core/`, `run/`, `coupling/`, `components/`, `validators/`, `utils/`, `interfaces/`, `memory/`, `agents/`, `config/`) MUST NOT hardcode flood, drought, or irrigation vocabulary outside documented allowlist entries. Domain logic belongs behind `DomainPack` (`broker/domains/protocol.py`) or `CouplingContract` (`broker/coupling/contract.py`).
3. **Audit single source of truth**: `trace_to_csv_row` and `compute_csv_fieldnames` in `broker/components/analytics/audit.py` govern both live export and `broker/tools/recover_csv_from_jsonl.py`. Keep new columns additive and key-gated unless an invariant says otherwise.
4. **Memory contract**: `MemoryEngine.retrieve()` implementations (`broker/components/memory/`) MUST preserve metadata (`MemoryRecord` dicts), except the documented `WindowMemoryEngine` exemption.
5. **Experimental fence**: `broker/components/coordination/`, `broker/components/social/`, and `broker/components/orchestration/` are parked for follow-up multi-actor / social studies. Do not add new coupling from `broker/run/` or `broker/core/` into these subpackages during single-agent-type releases.
6. **No governance trace in memory (Invariant 7)**: under `rejection_line_style: executed` (default on `broker.run`), memory writes, reflection inputs, and stored lessons must not carry rule ids, rule messages, or rejection phrasing; verify with `python -m broker.tools.check_governance_carryover` when modifying memory, reflection, or retry paths.

## Required Checks Before Committing `broker/` Edits

- `python -m pytest broker/tests/ --timeout=600 -q -k "not real_llm"`
- Verify `broker/tests/test_framework_invariants.py` passes with zero new allowlist shortcuts.
