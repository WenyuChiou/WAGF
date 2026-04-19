---
phase: 4
date: 2026-04-18
scope: synthesis of Phase 1 (inventory) + Phase 2 (correctness) + Phase 3 (interface)
author: Claude
depends_on:
  - broker/_AUDIT_INVENTORY_2026-04-18.md
  - broker/_AUDIT_CORRECTNESS_2026-04-18.md
  - broker/_AUDIT_INTERFACE_2026-04-18.md
---

# Broker Framework Gap Analysis

Synthesis of three audit phases. Each gap is tagged S0/S1/S2 severity, S/M/L effort, H/M/L impact, with an explicit dependency where one exists.

Severity scale
- **S0** — blocks publication or next-domain reuse; must fix before NW submission or before extending the framework.
- **S1** — limits the framework's credibility or reusability; should fix before external review.
- **S2** — hygiene; fix opportunistically.

## A. Architecture gaps

| # | Gap | Severity | Effort | Impact | Depends on |
|---|---|---|---|---|---|
| A1 | Most `broker/components/*` have empty `__init__.py`. Examples bypass facades with 99 deep imports. `broker/components/memory` is the only real facade, yet 16/18 of its consumer imports are still deep. | **S1** | M | H | — |
| A2 | `broker/utils/`, `broker/core/`, `broker/modules/` have NO `__init__.py` exports. These are heavily consumed (`broker.utils` 21 deep imports from examples) but expose no advertised API at all. | **S1** | M | H | — |
| A3 | Root `broker` over-exports: 42 public symbols, only 8 consumed by examples. 34 zero-consumer symbols bloat the public surface. | S2 | M | M | A1+A2 preferred first |
| A4 | `broker.governance` exposes `BaseValidator`/`PersonalValidator`/etc. through lazy `__getattr__`. Facade is opaque; underlying classes ARE documented but the package `__init__.py` hides them. | S2 | S | M | — |
| A5 | Duplicate namespace risk: `broker/memory/` (top-level research toolkit, 19 files) vs `broker/components/memory/` (production integration, 17 files). Two separate codepaths with overlapping concerns. Currently OK because consumers differ, but rename or merge pending. | S2 | L | M | — |
| A6 | Two `governance` namespaces: top-level `broker/governance/` (3 files) vs `broker/components/governance/` (4 files). Similar duplication to A5 but smaller scale. | S2 | S | M | — |

## B. Testing gaps

| # | Gap | Severity | Effort | Impact | Depends on |
|---|---|---|---|---|---|
| B1 | `broker/components/prompt_templates` has ZERO tests. This is the package that provides the memory-template vocabulary consumed by Paper 3 dual-role finding. Untested. | **S1** | S | H | — |
| B2 | Four zero-coverage modules flagged as dead-code candidates: `broker/components/cognitive/trace.py`, `broker/components/governance/permissions.py`, `broker/interfaces/schemas.py`, `broker/memory/embeddings.py`, `broker/simulation/base_simulation_engine.py`, `broker/validators/agent/base.py`, `broker/validators/calibration/conservatism_diagnostic.py`. Decide: delete, deprecate, or test. | S2 | M | M | — |
| B3 | `broker.simulation` overall coverage 42%, `broker.modules` 37%. Lowest-coverage sub-packages in the framework. | S2 | L | M | — |
| B4 | 9 skipped tests in the scoped run. Not audited — unclear if they are skip-due-to-platform, skip-due-to-env, or skip-due-to-incomplete. | S2 | S | L | — |

## C. Documentation gaps

| # | Gap | Severity | Effort | Impact | Depends on |
|---|---|---|---|---|---|
| C1 | Methods v4 describes a 6-step validator pipeline (schema → action legality → physical → institutional → magnitude → theory). Code has 4 FLAGs where structure diverges: (a) institutional is actually 3 labels (institutional/social/economic), (b) magnitude is warning-only not a rejection gate, (c) retry-loop requires DETERMINISTIC repetition, not any repetition, (d) fallback executes registry-default skill, not "do nothing". | **S0** | S-M | H | — |
| C2 | 12 undocumented public symbols surfaced by Phase 3 type-hint/docstring scan. Worst offender: `broker.memory` (10 N-type-hints + 3 N-docstrings out of 28 exports). | S1 | M | M | A2/A3 partly |
| C3 | Validator pipeline has no single authoritative docstring in `broker/core/skill_broker_engine.py` that matches the Methods 6-step description. A reader following the Methods paper cannot trace to code. | **S1** | S | H | C1 preferred first |
| C4 | `broker.governance`'s lazy `__getattr__` returns validator classes without docstrings at the package level. Consumer introspection reveals nothing. | S2 | S | M | A4 fix |

## D. Scope violations (contamination from Paper 3)

| # | Gap | Severity | Effort | Impact | Depends on |
|---|---|---|---|---|---|
| D1 | `broker/` has no "renter" or "EPI" residue per Phase 2 scan (all zero hits), but `examples/multi_agent/flood/` still has the full Paper 3 multi-agent scope. That is correct — scope isolation works. Mark as **compliant**, not a gap. | — | — | — | — |
| D2 | `broker/components/memory/engines/humancentric.py` contains a broker-memory-governance commit (9057097, 2026-04-11) that was added specifically for Paper 3's CLEAN policy. Is the generalized `memory_write_policy` still required for NW single-agent runs? If it is framework-level, it stays; if it is Paper-3-only, move to examples. | S1 | S | M | — |

## E. Performance flags

| # | Gap | Severity | Effort | Impact | Depends on |
|---|---|---|---|---|---|
| E1 | Only one test >5 sec in Phase 2 (`test_single_year_completes` 7.24s). No broader profiling of validator retry loop, memory retrieval, or prompt-build hot paths. | S2 | M | L | — |
| E2 | Retry loop (`broker/core/_retry_loop.py`) terminates on DETERMINISTIC repeat. Non-deterministic blockers cause up to 3 LLM calls per rejection cycle. Worst case per agent per year could be 12 LLM calls. Not measured. | S2 | M | M | — |

## F. Security / supply-chain

| # | Gap | Severity | Effort | Impact | Depends on |
|---|---|---|---|---|---|
| F1 | **UTF-8 BOM** at start of 5+ broker files (Phase 1 flagged `context/builder.py`, `prompt_templates/__init__.py`, `memory_templates.py`, `config/__init__.py`, `config/schema.py`). Runtime imports work, but `ast.parse` with explicit `encoding='utf-8'` breaks. Code hygiene, not blocking. | S2 | S | L | — |
| F2 | **Pydantic warnings** (real, fires every test run): `broker/config/schema.py:142` `RuleCondition.construct` and `:172` `GovernanceRule.construct` both shadow a BaseModel attribute. Rename to e.g. `rule_construct` to silence. | S1 | S | M | — |
| F3 | **Python 3.14 + langsmith**: `Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater`. Emits warning every run. Pinning or removing langsmith is an option. | S2 | S | L | — |
| F4 | **requests dependency mismatch**: `urllib3 (2.6.3)` or `chardet (7.4.3)/charset_normalizer (3.4.4)` doesn't match a supported version. Warning only. | S2 | S | L | — |
| F5 | **datetime.utcnow() deprecation**: `broker/memory/persistence.py:185, 292`. Python 3.14 scheduled removal. | S2 | S | L | — |
| F6 | **Pandas FutureWarning**: silent downcasting after `fillna(...).infer_objects(...)` in `broker/validators/posthoc/unified_rh.py` and `thinking_rule_posthoc.py`. Will break in a future pandas. | S2 | S | L | — |
| F7 | Parser alias resolution bug (discovered while fixing regressions): bare `INCREASE`/`DECREASE` aliases in government yaml, `IMPROVE_CRS` and `SIGNIFICANTLY_REDUCE` in insurance yaml, resolve to the wrong skill or fall through to default. Yaml documents these aliases but parser doesn't honour them. | S1 | M | M | — |
| F8 | No input validation on `examples/single_agent/agent_initial_profiles.csv` or other CSV parsing boundaries. A malformed CSV could silently produce wrong agent population. | S2 | M | M | — |
| F9 | No rate-limit/timeout enforcement at the Ollama HTTP boundary beyond what Ollama itself provides. A stuck model could hang an experiment indefinitely (experienced once today with Gemma 4 26b Run_5). | S2 | M | L | — |

## G. Test drift and 2-04 broker-memory-governance impact

The 12 regressions fixed in this audit all stemmed from production code changing between 2026-02-11 and 2026-04-18 without updating tests. Specifically:

- 4 parser tests: yaml vocabulary expanded from 3-level to 5-level (2026-04-03)
- 1 irrigation math test: v21 demand-base change (2026-03-03)
- 3 MA reflection tests: broker memory governance generalization (2026-04-11, commit 9057097)
- 4 no-hub context tests: provider logic added `income > 0` comparison (2026-02-24)

**Gap G1** — No pre-merge check catches "tests that depend on a module you just changed". A lightweight `pytest --last-failed` or git-pre-commit running affected-tests would have surfaced these earlier. **S1 / M / M**.

## H. Surprise-event response

The broker/ working tree was transiently deleted (190 files) between Phase 1 end (~15:17) and Phase 2 start (~15:33), despite the Codex brief being READ-ONLY. Root cause remains UNKNOWN (not scheduled task, not git hook, not a Codex command — investigation inconclusive).

**Gap H1** — No pre-Codex integrity snapshot. A `git stash` + file-count check before every Codex launch would catch this class of event deterministically. **S2 / S / M**.

## Summary roll-up

| Severity | Count | Must-fix before |
|---|---:|---|
| S0 | 1 (C1 validator doc drift) | NW submission |
| S1 | 10 (A1, A2, B1, C2, C3, D2, F2, F7, G1) | External review |
| S2 | 15 | Opportunistic |

S0 blocker summary: **the Methods v4 description of the validator pipeline does not structurally match the code**. That must be fixed before the paper goes to reviewers, because the code is the ultimate arbiter and reviewers will look.

S1 urgent summary: facade gaps, prompt_templates has no tests, doc gaps around validator pipeline, one potential scope violation in broker memory governance, pydantic warnings, parser alias bug, pre-merge test-affected check.

Recommended action list: see `broker/_AUDIT_ACTION_LIST_2026-04-18.md`.
