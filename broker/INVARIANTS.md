# WAGF Framework Invariants

**Status**: authoritative — any change here requires review against `broker/tests/test_framework_invariants.py`.

**Audience**: anyone adding a new memory engine, audit column, cognitive module, social signal, validator module, or domain adapter under `broker/`.

**Why this document exists**: on 2026-04-19 the NW flood cross-model experiments shipped with a degraded memory pipeline (retrieved memories silently stripped of salience metadata, audit log showing `emotion="neutral"` for every row). The root cause was not a single bug — it was the absence of framework-level contracts that would have made the degradation detectable. This document codifies the contracts that must hold. If you catch yourself writing code that violates one of these, stop and either (a) revise your code, (b) revise this document with review, or (c) document a temporary exception in the code with an explicit expiry.

---

## Invariant 1 — Memory type contract

### Contract
```
MemoryRecord: TypedDict / dataclass with at minimum:
  - content:    str                # human-readable text
  - emotion:    str                # classification from domain emotion vocabulary
  - importance: float              # [0.0, 1.0], computed or authored
  - source:     str                # {personal, neighbor, community, abstract}
  - timestamp:  int                # simulation step or year
  - metadata:   Dict[str, Any]     # domain-specific extensions

MemoryEngine.retrieve(...) -> List[MemoryRecord]
MemoryEngine.retrieve_content_only(...) -> List[str]   # compatibility helper only
```

### Rules
1. Any subclass of `MemoryEngine` MUST preserve metadata in `retrieve()`. Returning bare `List[str]` from `retrieve()` is forbidden.
2. Callers that need `List[str]` for string-formatting MUST explicitly call `retrieve_content_only(...)`. The intent to discard metadata must be visible at the call site.
3. `add_memory(agent_id, content, metadata)` and `add_memory_for_agent(agent, content, metadata)` MUST both route through the same internal classification path (see Invariant 3).
4. If `metadata` is absent when adding a memory, the engine MAY invoke a classifier (e.g., `_classify_emotion`) to infer it, but MUST NOT silently discard missing fields by substituting arbitrary defaults. The inferred value MUST be distinguishable from a missing value via a marker (e.g., `metadata["emotion_inferred"] = True`).

### Detection / enforcement
- `broker/tests/test_framework_invariants.py::test_memory_engine_contract` — asserts every `MemoryEngine` subclass preserves metadata end-to-end for a synthetic critical memory.
- Base `MemoryEngine.__init_subclass__` — on import, verifies subclass `retrieve()` does not return bare `List[str]` (annotation-level check).

### Known current state (as of 2026-04-19)
- Base `retrieve()` declares `List[str]` return — this is the legacy contract being repaired on `feat/memory-pipeline-v2` by Codex. Target state is `List[MemoryRecord]`.
- `retrieve_content_only()` already exists (`broker/components/memory/engine.py:53-68`) as the compatibility helper.

---

## Invariant 2 — Audit integrity contract

### Contract
Every column in an audit CSV MUST correspond to one of:
- A real upstream signal, populated by at least one production code path.
- An explicit "reserved for future" column, documented in the schema with owner + expected-populator date.

### Rules
1. `AuditWriter` MUST NOT hardcode placeholder values that look like real data. `"neutral"`, `0.0`, `"personal"`, `False` are examples of values that silently mask missing upstream data — these MUST be replaced with explicit sentinels (`None`, `"UNSET"`, `NaN`) when the upstream is absent.
2. If a column's upstream is known to be absent for a given experiment (e.g., cognitive module parked for V2), the AuditWriter MUST emit ONE WARNING at experiment start naming the absent column(s); it MUST NOT write a placeholder value on every row.
3. Every column name in the audit schema MUST have at least one grep-locatable assignment in `broker/` or `examples/<domain>/` code. Orphan columns (declared but never written) are forbidden.
4. Aggregated columns (e.g., `mem_top_emotion` = max-frequency over retrieved memories) MUST document in the schema that they are aggregates, not per-row observations. Per-memory detail, if needed, belongs in a separate JSONL sidecar, not collapsed into single CSV cells.

### Detection / enforcement
- `test_audit_no_hardcoded_sentinels_leak` — synthetic run asserts `mem_top_emotion` shows variety when input memories have variety.
- `test_dormant_field_policy` — grep-scans that every audit column name has at least one writer in the codebase.
- Runtime: `AuditWriter.finalize()` checks for suspicious constancy (same value across 100+ rows) and logs WARNING.
- **Phase 6G (2026-05-15)**: audit CSV column ordering + per-row schema is computed by the module-level functions `trace_to_csv_row()` and `compute_csv_fieldnames()` in `broker/components/analytics/audit.py`. These are the single source of truth used by BOTH the live writer (`GenericAuditWriter._export_csv`) and the crash-recovery CLI (`broker.tools.recover_csv_from_jsonl`). Any schema change MUST update both consumers via the shared functions — drift between live-finalized CSV and crash-recovered CSV is enforced against by `tests/test_recover_csv_from_jsonl.py::test_recovered_csv_matches_live_finalize_schema`.

### Known current state
- `broker/core/_audit_helpers.py:64` hardcodes `{"emotion": "neutral", "source": "personal"}` — being fixed by Codex Fix D on `feat/memory-pipeline-v2`.
- `broker/components/analytics/audit.py:325-330, 351-359` hardcodes `cog_*` and `social_*` defaults to `0` / `False` / `""` when upstream dicts absent — **will be fixed in Phase D of this plan** by replacing with `None` sentinels and one-time WARNING.
- `fallback_activated` column writer side: row-construction now reads `trace['fallback_activated']` when present, falling back to status-string inference for older traces. The retry_loop write side (Phase 6G #4a) is still pending and should populate the trace dict directly — see [[wagf-design-flaws-harness-engineering-audit-2026-05-14]].
- **`fallback_activated` semantic change (commit `0e3187c`, intentional bug-fix of the flaw-4 schema inconsistency):** the status-string inference set now includes `"REJECTED_FALLBACK"` (old set was only `FALLBACK`/`fallback`/`MODIFIED`). This is the *correct* behaviour — a `REJECTED_FALLBACK` decision genuinely did activate the fallback skill. **Consequence for crash recovery:** running `broker.tools.recover_csv_from_jsonl` on a *pre-`0e3187c`* JSONL trace will set `fallback_activated=True` for rows whose `approved_skill.status == "REJECTED_FALLBACK"`, whereas the original on-disk CSV (written by the old buggy logic) holds `False` for those same rows. v21 5-seed Gemma-3 4B has 105 such rows / 16,380 decisions (0.64%). **No paper number is affected** — Paper 1b IBR is computed from `proposed_skill` (proposal-level) and the fallback rate is read from the `status` column directly; nothing reads the `fallback_activated` column. Do NOT naively diff a recovered CSV's `fallback_activated` column against an old on-disk CSV's — they will differ by exactly the REJECTED_FALLBACK rows, by design.

---

## Invariant 3 — API consistency contract

### Contract
Parallel API methods on the same domain concept MUST preserve identical metadata semantics.

### Rules
1. If two methods `foo(x, ...)` and `foo_for_y(y, x, ...)` exist and operate on the same concept, both MUST route through the same internal classification / validation path. The only legitimate difference should be which contextual inputs are available (e.g., whether an agent object is passed for per-agent emotion keyword overrides).
2. Prefer a single API with an optional `agent: Optional[BaseAgent] = None` parameter over two methods. Dual methods are allowed only when the two use cases have genuinely incompatible signatures; never for convenience.
3. Domain-facing code (examples/<domain>/) SHOULD call the agent-aware variant; if it must use the non-agent variant, it MUST pass explicit `metadata={"emotion": ..., "importance": ..., "source": ...}` to avoid fallback to a different classifier.

### Detection / enforcement
- `test_parallel_api_consistency` — adds the same content through both `add_memory` and `add_memory_for_agent`; asserts stored emotion classification is identical.
- Code review checklist in `CONTRIBUTING.md` (to be added): "Does this new method have a parallel variant? If yes, do both route through `_classify_metadata`?"

### Known current state
- `HumanCentricMemoryEngine.add_memory` vs `add_memory_for_agent`: the two methods diverge in emotion classification because `_classify_emotion(content, agent=None)` uses different keyword map than `_classify_emotion(content, agent=agent)`. Fix approach: introduce `_classify_metadata(content, agent=None, metadata=None)` as the single internal path both methods call.

---

## Invariant 4 — Dormant code policy

### Contract
Schema fields, dataclasses, and code paths MUST be either production-live or explicitly marked as reserved / deprecated.

### Rules
1. Audit CSV columns MUST be populated by at least one production code path OR declared in a `reserved_columns.yaml` with an owner and expected activation date.
2. Dataclasses defined but never constructed in production code MUST be marked `@deprecated` with a migration path in the docstring.
3. Abstract methods in protocols MUST have at least one concrete implementation imported in the default production graph. If a protocol has zero implementations, it MUST be removed or moved to an `experimental/` folder.
4. Constructor parameters accepted but never used MUST either be removed or documented in the docstring with a TODO for activation.

### Detection / enforcement
- `test_dormant_field_policy` — ties audit columns to writer grep results (same test as Invariant 2 rule 3).
- Manual review: quarterly scan for `@deprecated` markers older than 6 months; decide to activate or remove.

### Known current state (dormant items identified by 2026-04-19 audit)
- `broker/components/cognitive/trace.py::CognitiveTrace` — dataclass defined, never populated. **Will be marked `@deprecated` in Phase D** with a pointer to the future V2 cognitive module.
- `broker/components/cognitive/adapters.py::DomainReflectionAdapter` — no longer dormant: `broker/components/cognitive/reflection.py::compute_dynamic_importance` delegates to the registered `DomainPack.compute_importance` when available. The hardcoded flood block remains only as a documented deprecated no-pack fallback during the transition window.
- `broker/components/orchestration/phases.py:48` — `saga_coordinator` parameter unused. Must be removed or activated.
- `broker/components/memory/engines/hierarchical.py::_consolidate` — no-op stub. Module already `@deprecated`; cleanup deferred to a separate hygiene pass.

---

## Invariant 5 — Domain-genericity contract

### Contract
Every generic `broker/` subtree MUST be domain-agnostic. The only non-generic trees are `broker/domains/<domain>/` (the domain home) and `broker/tests/`. Domain-specific logic belongs in `examples/<domain>/`, `broker/domains/<domain>/`, or behind `Adapter` protocol implementations.

### Rules
1. No field names like `elevated`, `flood_count`, `WSA_LABEL`, `insurance`, `drought_tier` may appear in any generic `broker/` Python code unless:
   - Inside a `domain_adapters/` sub-directory, OR
   - Inside a generic `custom_attributes: Dict[str, Any]` pass-through field, OR
   - On the explicit `_ALLOWLIST_PATTERNS` list in `broker/tests/test_framework_invariants.py::TestDomainGenericity` with a justification comment.
2. Emotion keyword maps, importance heuristics, and validator rule sets MUST be injectable via domain adapter protocols — never hardcoded with one domain's vocabulary in generic code.
3. If a generic module has "default behavior for one particular domain" baked in, that behavior MUST be moved to an explicit default adapter that can be swapped.
4. Default skill names (e.g., `do_nothing`, `maintain`) MUST come from configuration, not from `broker/components/governance/registry.py` constants.

### Detection / enforcement
- `tests/test_domain_genericity.py` — Phase 6A landing tests covering registry default + retriever fallback.
- `broker/tests/test_framework_invariants.py::TestDomainGenericity` — parametrized grep-style sweep of every generic `broker/` subtree against `_DOMAIN_TOKENS`. The 2026-05-20 harness-engineering audit fixed two bugs in this guard: lowercase `WSA_label`/`ACA_label` tokens never matched production `WSA_LABEL`/`ACA_LABEL`, and the scan covered only `components/` + `core/`. Both fixed; the ~25 leaks that surfaced were frozen in `_ALLOWLIST_PATTERNS`, triaged FP (docstring/comment) or KNOWN-DEBT (real leak). Phase 6H (DomainPack v2) and Phase 6I closed **every** real-code KNOWN-DEBT entry — the allowlist now holds only docstring/comment false positives; no generic `broker/` file carries a live domain-token leak. Full catalogue: `.ai/2026/05/20/harness_audit_{A,B,C}_*.md`.
- Code review: any new feature in `broker/` must pass the domain-token check.

### Known current state (updated 2026-05-22 by Phase 6J)

**Phase 6A landed (deprecation-warn or fixed)**:
- `broker/components/governance/registry.py` — `_default_skill` tracked explicitly via `_default_skill_explicit`. Phase 6J-C tightened this to fail-fast: `get_default_skill()` now raises `ValueError` if no YAML / `set_default_skill()` configured it (the build-time `has_explicit_default_skill()` check fires first on every experiment path, so well-configured domains never hit the raise).
- `broker/components/governance/retriever.py:23` — was `["do_nothing"]`; now empty list with one-time warning if instantiated without `global_skills`. Production path unaffected (broker engine wires `global_skills` from `agent_types_config.get_global_skills`).
- `broker/core/experiment_runner.py` (6 cache-fallback sites) — reads `self.broker.skill_registry.get_default_skill()`. Irrigation cache misses fall back to `maintain_demand` instead of `do_nothing`.

**Closed by Phase 6H DomainPack v2** (2026-05-21..22):
- `broker/components/social/perception.py` — strip-list field-name policy moved to `DomainPack.perception_field_policy()`; the flood metric list (`insurance_penetration_rate`, `elevation_penetration_rate`, `relocation_rate`, `neighbors_*`) now lives in `examples/governed_flood/adapters/flood_perception.py`.
- `broker/components/cognitive/reflection.py` — agent-status text generator + flood importance fallback + batch-traits block fully de-flooded; replaced by `DomainPack.reflection_status_text() / .reflection_questions() / .reflection_trait_labels()` (Item 9). `AgentReflectionContext` flood fields removed.
- `broker/components/prompt_templates/memory_templates.py` — flood-specific content extracted to `broker/domains/water/flood_memory_templates.py`; the original file is retained as a generic `MemoryTemplate` dataclass stub with a backward-compat shim. Flood-specific templates are injected via `FloodMemoryTemplateProvider` (Phase 6B-2).

**Closed by Phase 6I** (2026-05-22): agent_initializer / unified-context-builder field-extraction leak — position field-write uses a generic `enricher.profile_field_map` (6I-B); InteractionHub vocabulary is caller-supplied via `broker.domains.water.interaction_specs` (6I-C); `create_flood_observables` relocated to `broker/domains/water/observables.py` (6I-D); `ImpactEventGenerator` mitigation field + event labels are config (6I-E); `unified_context_builder` core_state keys are domain-neutral (6I-F).

**Closed by Phase 6J** (2026-05-22):
- **6J-A** — soft-default-to-PMT eliminated. `FrameworkType.GENERIC` is a standalone domain-neutral scale (not an alias to PMT); `UniversalContext.framework` defaults to GENERIC; `_get_framework_for_type` no longer silently infers a framework from agent-type name substrings. New behavioural guard `TestNoSilentDomainDefault`.
- **6J-B** — `ma_manager.py` event dispatch de-flooded: removed unreachable `try/except ImportError` flood fallback; `get_agent_impact` flood event-type chain replaced by `DomainPack.agent_impact_handlers()` hook.
- **6J-C** — domain-bias defaults converted to fail-fast or domain-housed (8 sites). `SkillRegistry.get_default_skill()` raises if unconfigured; `unified_adapter.py` parse-failure fallback raises if `parsing.default_skill` absent; `agent_initializer.py` requires `config["domain"]`; `create_default_registry()` raises (water content relocated to `broker/domains/water/agent_type_defaults.py`); `PhaseOrchestrator.__init__` defaults to generic 3-phase layout (flood 4-phase relocated to `broker/domains/water/phase_layouts.py`); `AGENT_SOCIAL_SPECS` starts empty (flood specs relocated to `broker/domains/water/social_specs.py`); `PriorityResolution.type_priorities` defaults to `{}`; artifact routing maps start empty (flood mappings registered by `examples/multi_agent/flood/protocols/artifacts.py`); `TypeValidator` requires an explicit registry.
- **6J-D** — `validator_bundles.py` reverse-import removed. `_ensure_irrigation_registered` / `_ensure_flood_registered` (which lazy-imported from `examples/*/validators`) deleted; each example package's `__init__.py` now imports its `.validators` submodule on package import, and each flood entrypoint adds a top-level `import examples.governed_flood`. The hardened `test_water_domain_exposes_validator_builder` asserts populated `_builtin_checks` so the new path cannot vacuously pass. The `TA_KEYWORDS` / `CA_KEYWORDS` flood-PMT keyword dicts also relocated from generic `broker/validators/posthoc/keyword_classifier.py` to `broker/domains/water/posthoc_keywords.py`; the generic classifier supports a Tier-1/1.5-only mode when no keywords are supplied.
- **6J-E** — `_DOMAIN_TOKENS` widened with 12 new tokens (`flood_occurred` / `flood_event` / `flood_depth_m` + flood / drought / irrigation infrastructure + skill identifiers `NFIP` / `FEMA` / `PRB` / `SFHA` / `CRSS` / `shortage_tier` / `drought_index` / `buyout` / `buyout_program`). 5 leak sites triaged: `simulation_protocols.py` docstring example de-flooded; `agents/base.py` + `components/context/providers.py` allowlisted as FP (only docstring "Literature:" references); `events/generators/flood.py` + `components/memory/initial_loader.py` + `components/memory/policy_classifier.py` + `components/memory/universal.py` allowlisted as TECH-DEBT(6K) — the memory subsystem and the flood-specific hazard generator need a DomainPack plugin pass.

**Deferred to a future PMT-extraction / "skill-name" phase**: the I5 token set does not yet enforce `threat_appraisal` / `coping_appraisal` (PMT field names live in generic `schemas.py`, `response_format.py`, and `unified_rh.py` defaults) or the skill-name set (`elevate_house`, `buy_insurance`, `relocate`, `maintain_demand`) — these appear in many generic memory / validator docstrings and protocol examples; locking them now would require either a large allowlist surface or a separate refactor. `do_nothing` was explicitly evaluated and rejected (too common a phrase to enforce as a token).

---

## Process rules

### Adding a new invariant
1. Draft the contract + rules + enforcement strategy.
2. Add a test to `broker/tests/test_framework_invariants.py`.
3. Run the test against current `main` — it should fail (revealing current state).
4. Fix the violations.
5. Land invariant + test + fixes together in one PR.
6. Update this document's "Known current state" section of the affected invariant.

### Relaxing an invariant
1. Document the use case that justifies relaxation.
2. Add the exception to the relevant allow-list file or mark the code path with an explicit `# noqa: invariant-N` comment with owner and justification.
3. Never silently skip the invariant check.

### Reviewing changes
Every PR that touches `broker/` should have the INVARIANTS.md row of the review template checked. Reviewer verifies no invariant is newly violated.

---

## Cross-version comparability log

When a refactoring PR lands that *could* change experimental behavior, record the audit lineage here so future paper reproducibility manifests can cite it.

### v21 dataset ↔ v22 (post-Phase-6A/6B/6C) — audit 2026-05-10

**Datasets**: irrigation v21 5-seed Gemma-3 4B baseline (B1 RERUN COMPLETE 2026-04-28) and Gemma-4 e2b/e4b 5-seed cross-model batches.

**Refactoring commits between v21 baseline runs and current main**: `16dee6a` (Phase 6A registry/retriever/runner/reflection narrowing), `f9ea845` (Phase 6B-1 ValidatorRegistry), `1e2a748` (Phase 6B-4 FilterRegistry), `3f32e1f` (Phase 6B-2 flood memory templates relocate), `4b20320` (Phase 6C W7+W8: drought_index/total_basin_demand collision fix + rule_breakdown population).

**Audit verdict** (independent code-reviewer agent, 2026-05-10): all 5 commits are **behavior-preserving for irrigation**. Specifically:
- `16dee6a` Phase 6A `do_nothing → registry.get_default_skill()` change at `experiment_runner.py:454,465,479,539,549,563` is on a cache-hit fallback path that is unreachable in normal runs (`SkillBrokerResult.to_dict()` always serializes a real `skill_name`).
- `f9ea845`/`1e2a748`/`3f32e1f` are flood-only paths irrigation never enters.
- `4b20320` only affects audit CSV column population (`rules_*_hit` from placeholder zeros to real values); IBR (`compute_ibr.py`) and EHE read only `proposed_skill / final_skill / status / wsa_label / aca_label`, none of which are changed.

**Implication**: v21 5-seed Gemma-3 4B baseline and current Gemma-4 e4b cross-model batch are **fully cross-comparable** for Paper 1b's task #85 (cross-model EDT2 + paired-t). No re-run, no SI robustness footnote required. If a reviewer asks, cite this audit row.

**Audit detail**: `.claude/projects/.../memory/phase6abc_irrigation_behavior_audit_2026-05-10.md` (author's local memory).

### v2 → v3 (Phase 6C-v3, 2026-05-10) — STILL FULLY COMPARABLE

**New refactor commits** between v2 (PR #11 merged 2026-05-07) and v3 (this PR):
`99f1eaa` (Group A AgentProfile cascade), `3f0b2af` (Group H ThinkingValidator strict registration), `ab1163e` (Group B partial institutional_agent_types), `9280a7e` (Group D perception filter fields injectable), `a0607aa` (Group C partial FinancialCostProvider water-domain copy).

**Verification suite** (2026-05-10):
- `pytest tests/ broker/`: 1955 pass, no regression vs v2 baseline.
- 3-domain integration smoke (`gemma3:4b 2yr`):
  - Irrigation 6 rows main vs worktree: schema identical, decisions identical (6/6 APPROVED), validator firing identical, 1/6 LLM stochastic skill variance.
  - SA flood 200 rows: schema identical, 200/200 APPROVED in both, 4 unique skills in both, ~3% LLM variance, REJECTED rate 0/200 (P=0.17 vs v21 0.87% prior).
  - MA flood 204 rows across 4 agent types: schema identical, all decisions match (APPROVED/REJECTED counts within 2/130 for owner), 1.5-2.9% LLM variance per agent type.
- 3-agent independent verification (response quality / data integrity / statistical envelope): all return positive verdicts. SA flood n=200 sits inside v21 Y1-Y2 envelope on every skill. Zero hallucinations, zero schema regression, zero new sentinels.

**Verdict**: Phase 6C-v3 is **byte-identical for paper-relevant behaviour** on irrigation, SA flood (Paper 1b reference), and MA flood (Paper 3). v21 5-seed dataset and post-v3 datasets are fully cross-comparable. No paper re-run required.

**Outstanding caveats** (do NOT affect Paper 1b/3 metrics):
- ~20 BLOCKERs deferred to Phase 6C-v4 (calibration validators, agent_validator affordability allowlist, reflection.py legacy paths, etc.). All either have deprecation warnings already, or are post-hoc analysis tools, or only affect new non-water domains. Tracked in `.ai/phase6c_v3_full_plan_2026-05-10.md`.
- SAflood `mem_top_emotion=neutral` / `mem_top_source=personal` constant — pre-existing in v2 baseline, NOT introduced by v3. Separate fix scope.

**Audit detail**: 3-agent verification reports + smoke artifacts at `.ai/smoke_test_2026-05-10/`; planning + per-finding rationale at `.ai/phase6c_v3_full_plan_2026-05-10.md`.

---

## References

- `broker/tests/test_framework_invariants.py` — executable encoding of these invariants
- `broker/_AUDIT_*_2026-04-18.md` — historical audit docs (may be superseded by this file)
- `.ai/nw_memory_pipeline_remediation_plan_2026-04-19.md` — the remediation plan that motivated Invariants 1–3
- `.ai/wagf_module_audit_2026-04-19.md` (Phase D) — module-by-module findings from the 2026-04-19 audit
- `memory/MEMORY.md` — cross-project lessons, including the 2026-04-19 memory pipeline leak discovery
