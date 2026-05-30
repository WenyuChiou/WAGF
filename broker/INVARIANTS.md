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

**Closed by Phase 6K** (2026-05-22) — the inner-layer domain coupling that Phase 6J's outer-boundary cleanup explicitly deferred:
- **6K-A** — memory subsystem → single new `DomainPack.memory_policy()` hook returning a `MemoryPolicyBundle` (category_rules + external_event_whitelist + stimulus_key + default_content_type). `policy_classifier._DEFAULT_RULES` no longer carries the 5 flood/insurance category keys; `initial_loader.py` no longer hardcodes the `("flood_experience", "flood_event", "damage")` whitelist; `universal.py` no longer falls back to `stimulus_key="flood_depth_m"` (fail-loud `ValueError` instead, plus a per-domain bundle lookup). `PolicyFilteredMemoryEngine` gains a `domain=` kwarg so runtime writes see the same bundle the seed-time loader does. Three `TECH-DEBT(6K)` allowlist entries closed.
- **6K-B** — `broker/components/events/generators/flood.py` whole-file relocated to `broker/domains/water/event_generators/flood.py` (`R100` rename — verbatim). Two docstring examples in generic broker that referenced `FloodEventGenerator` genericized to "MyHazardEventGenerator" placeholders. Fourth and final `TECH-DEBT(6K)` allowlist entry closed.
- **6K-C** — `ThinkingValidator` 7 hardcoded PMT / Utility / Financial rules relocated to `broker/domains/water/thinking_checks.py` as free functions, registered via a new per-framework `_THINKING_CHECKS_BY_FRAMEWORK` registry (populated by `register_thinking_checks(framework, checks)` at domain-import time). Module-level `normalize_label` + `has_rule_for` helpers extracted from instance methods. `ThinkingValidator.validate()` injects `framework` + `_extreme_actions` into context before dispatching so the relocated free functions read them without holding a validator reference. Naturally addresses audit-B P1 items 1-3 (hardcoded PMT label triples + `do_nothing` / `maintain_policy` / `expand_coverage` skill literals + utility label thresholds — all migrated with the rules).
- **6K-D** — audit-B P1 item 11's substantive work (`BUYOUT_OFFER_FRACTION = 0.75` + `premium_escalation_pct > 30` migration) was already done by Phase 6H Item 7 when it relocated `FinancialCostProvider`. Pivoted to a smaller cleanup: tightened the residual NFIP / FEMA `Literature:` docstring references in `agents/base.py` (`Constraint` dataclass) and `components/context/providers.py` (`InsurancePremiumProvider` class) so the 6J-E FP allowlist entries for both files can drop. After 6K-D, `\bNFIP\b` and `\bFEMA\b` appear in generic `broker/` only in the permanently-allowlisted `simulation/environment.py` docstring.

**Closed by Phase 6L** (2026-05-23) — the "knobs" effort the Phase 6K plan deferred. Every audit-B P1 magic-constant tuning surface now has a YAML override path + a `DomainPack` hook, all wired via the canonical 4-tier precedence stack established by Phase 6H Item 3 (defaults → `DomainPack` → shared YAML → global YAML). Defaults are byte-identical to the pre-6L hardcoded literals — no behavioural change unless a caller explicitly overrides.
- **6L-A** — `DriftDetector` thresholds (`entropy_threshold` / `stagnation_threshold` / `collapse_threshold` / `jaccard_stagnation_threshold` / `history_window`) → new `DomainPack.drift_policy()` hook + `AgentTypeConfig.get_drift_config()` accessor. Lowest-risk sub-phase by design: no production caller, validates the template extends cleanly. Audit-B P1 item 5.
- **6L-B** — population-governance thresholds (`CrossAgentValidator` `echo_threshold` / `entropy_threshold` / `deadlock_threshold` + `MajorityCouncilValidator` quorum) → single `DomainPack.population_governance_policy()` hook bundling all four keys + `get_population_governance_config()` accessor. `MajorityCouncilValidator`'s hardcoded `>= 0.5` quorum literal extracted to a `quorum_threshold: float = 0.5` constructor kwarg; comparison reads `self.quorum_threshold`. `run_unified_experiment.py` wired at the `CrossAgentValidator` construction site. Audit-B P1 items 9 + 10.
- **6L-C** — `PolicyEventGenerator` severity-tier cutoffs (`severe` / `moderate` / `minor`, formerly hardcoded `0.20` / `0.10` / `0.05` literals inside `_determine_severity`) → extracted to `PolicyEventConfig.severity_tiers` dict via `field(default_factory=_default_severity_tiers)` + new `DomainPack.policy_event_tiers()` hook + `get_policy_event_tiers_config()` accessor. Accessor enforces non-negative + monotonic (`severe >= moderate >= minor`) at config-load time so a malformed override fails loud. Audit-B P1 item 12.
- **6L-D** — cognitive hot-path knobs. `MemoryBridge` resolution importance (`approved=0.6` / `denied=0.75`) → relocated to module-level `_DEFAULT_RESOLUTION_IMPORTANCE` dict + `MemoryBridge.__init__(importance_policy=...)` kwarg + `DomainPack.bridge_importance_policy()` hook + `get_bridge_importance_config()` accessor; the "denials more memorable" asymmetry is preserved with an inline doc + an accessor guard that rejects `denied < approved` at config-load time. `MultiAgentHooks` + `run_unified_experiment.py` threaded so YAML overrides reach the live MA-flood MemoryBridge. Reflection knobs (`base_importance`, `triggers.institutional_threshold` / `triggers.importance_boost`) ride the existing `get_reflection_config()` YAML pass-through — cognitive knobs stay YAML-only per Phase 6L plan (no DomainPack hook for reflection); `base_importance` is declare-only with a docstring deferral note (end-to-end wiring lands when a non-default value is genuinely needed). Audit-B P1 items 6 + 7 + 8.
- All four sub-phases verified by `pytest broker/ tests/` net-zero regression (5 pre-existing failures unchanged across the chain). Real-model `governed_flood` smoke run for 6L-D (cognitive hot path): 46 governance rule violations, within the natural variance band (46-55) seen across 6K-A / 6K-B / 6K-C smokes.

**Closed by Phase 6N-E** (2026-05-24) — the real production bug behind L3-1C's vaccination_demo thinking rules never firing: a YAML condition-dict shape mismatch.
- **Root cause**: vaccination_demo's 5 thinking_rules used the verbose `RuleCondition`-flavoured shape `{ type: construct, field: X, operator: "in", values: [...] }` (copy-pasted from `broker/governance/rule_types.py::RuleCondition` dataclass slots). But the production evaluator `AgentValidator._run_rule_set` at `broker/validators/agent/agent_validator.py:418` reads `cond.get("construct")` only — for verbose-shape conditions, `construct_name = None`, `get_label(None) = ""`, `label_matches("", ["H","VH"]) = False`, rule never fires. The bug was isolated to vaccination_demo — irrigation, governed_flood, single_agent flood, and multi_agent flood all use the canonical short shape `{ construct: X, values: [...] }`.
- **Origin**: L3-1C (commit `64899b8`) copied the dict shape from the `RuleCondition` dataclass instead of from the working irrigation YAML. Phase 6N-C fixed the top-level `rules:` → `thinking_rules:` key but did not audit the nested condition dict structure.
- **Phase 6N-E-1 fixes**:
  - Defensive evaluator at `broker/validators/agent/agent_validator.py:~418`: `construct_name = cond.get("construct") or cond.get("field")`. Backward-compatible — both shapes now work.
  - vaccination_demo `agent_types.yaml`: 5 thinking_rules rewritten to canonical short shape `{ construct: X, values: [...] }`. Same behaviour, cleaner authoring.
  - `wagf-domain-builder/references/edit_pass_checklist.md` + `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`: condition examples updated to canonical shape with explanatory comment about why.
  - 3 regression tests at `broker/tests/test_agent_validator_thinking.py`: pin the production `AgentValidator.validate_thinking()` end-to-end fire path with both canonical and legacy shapes.
- **Misleading Phase 6N-D-1 framing corrected**: that phase claimed "9 WARNING+blocked_skills rules silently block in irrigation/flood" based on the supposed `ThinkingValidator._validate_yaml_rules` ignoring `level`. But ThinkingValidator was always the dead-code path (production uses AgentValidator); AgentValidator's `_run_rule_set` already handled `level` correctly at line 459. The 0 fires across 39,943 paper-1b audit rows was real but its cause was the model never emitting matching construct combinations, NOT silent blocking.
- Smoke #9 verification (gemma4:e4b, 15 agents × 3 yr, seed=42, post-6N-E-1): 18/18 APPROVED, 0 lowercase leaks, 0 rule fires — correct behaviour: each row's HBM constructs were spot-checked and no row's conditions matched any rule. The regression test `test_canonical_construct_key_fires` proves the wiring works on the row-2 case (BARRIERS=H + EFFICACY=H + delay) that DID match.

**Closed by Phase 6N-D** (2026-05-24) — four broker-side bugs surfaced by the L3-1C code-reviewer and paper-data audit. All four were in the "deferred to Phase 6N-D candidate" bucket of the L3-1C commit (`64899b8`); fixed in this phase with regression-test coverage.
- **6N-D-1** — `ThinkingValidator._validate_yaml_rules` hardcoded `valid=False` regardless of `rule.level`. Multi-condition WARNING rules with `blocked_skills` therefore silently block-and-retried like ERROR rules. Fixed at `broker/validators/governance/thinking_validator.py:329-355`: reads `rule.level`, sets `valid=not is_error`, routes `rule_message` to `errors[]`/`warnings[]` per level, records level in metadata. Static paper-data audit across 39,943 audit rows (irrigation v21 5-seed gov + 5-seed no-val; single-agent flood Group_C 5-run gov + 3-run ablation) found **0 fires** of any WARNING+blocked_skills rule in any paper-1b reference data — so the fix has zero impact on paper IBR/EHE; the 9 WARNING+blocked_skills rules across 4 domains were never triggering their conditions. Three regression tests at `broker/tests/test_thinking_validator_level.py` pin the level-respecting contract.
- **6N-D-2** — `RuleCondition._get_value_from_context` returned raw `reasoning[field]` without case normalisation for `construct`-type conditions. Practically OK today because Phase 6N-B's upstream `unified_adapter.py:474` `.upper()` already canonicalises captures, but fragile to any caller bypassing the unified adapter (test fixtures, direct LLM injection, third-party tooling). Fixed at `broker/governance/rule_types.py:90-105` by adding defensive `.upper().strip()` for string values; numeric and `None` values pass through unchanged (preserves `>` / `<` operator semantics). Eight parametrised tests at `broker/tests/test_rule_condition_normalization.py`.
- **6N-D-3** — `rules_<category>_hit` count columns showed 0/3276 in irrigation v21 paper-1b audit CSVs even though `failed_rules` had real rule fires. Root cause: that audit data was generated April 25, but the fix that wires `rule_breakdown` into the audit trace (`_safe_rule_breakdown` at `broker/core/_audit_helpers.py:32-52`) shipped May 10 in commit `4b20320`. Production code is correct; this sub-phase adds 6 regression tests at `broker/tests/test_rule_breakdown_audit.py` so the fix can't be silently undone. Paper IBR/EHE pipelines read `proposed_skill` / `final_skill` / `status` / `wsa_label` (NOT these aggregate count columns), so the pre-May-10 all-zero artefact has zero paper impact.
- **6N-D-4** — `unified_adapter.py` free-text fallback CONSTRUCT EXTRACTION at ~line 585 over-matched the regex `\b(VL|L|M|H|VH)\b` against contraction letters: `\b` matches between an apostrophe and `m` inside `I-apostrophe-m`, so the bare `m` got captured as a LABEL. L3-1C smoke #6 caught a 1/45 leak; flood Group_C v21 paper data has 2/8918 (recorded in the cross-version comparability log entry "Pre-Phase-6N-B LABEL-case data hygiene audit"). Fixed by adding a whitelist filter immediately after the regex capture: reject any `temp_val` whose upper-cased form is not in `{VL, L, M, H, VH}`. 20 regression tests at `broker/tests/test_unified_adapter_label_overmatch.py` (grep-contract per Phase 6N-B precedent + parametrised admission logic + regex-still-overmatches root-cause documentation).
- **6N-D-5** — `examples/vaccination_demo/config/agent_types.yaml` restored `blocked_skills` to the 3 WARNING rules that L3-1C stripped as a Bug #5 workaround (commit `64899b8`). Post-6N-D-1 the workaround is no longer needed — WARNING+blocked_skills now correctly produces log-only behaviour (valid=True + rule fire in warnings column). Inline comments document the post-6N-D-1 semantics so a future L3 author doesn't strip them again.

**Closed by Phase 6N-C** (2026-05-24) — a documentation-rot finding surfaced during L3-1C validator expansion. The vaccination_demo's `agent_types.yaml` had a `rules:` block (NOT the canonical `thinking_rules:` / `coherence_rules:` keys that `broker/utils/agent_config.py::get_thinking_rules()` recognises). The `rules:` block was silently dead config — `yaml.safe_load` parsed it, the audit pipeline never saw it, and `0/45` thinking-rules fired in the L3-1C smoke #6 with gemma3:1b for the simple reason that no rules were ever loaded. Pre-existing condition since the vaccination_demo PoC was first written (Phase 6C-v3 era).
- **6N-C-1** — `examples/vaccination_demo/config/agent_types.yaml` `rules:` key renamed to `thinking_rules:`. Runtime verified: `get_thinking_rules('individual')` now loads 5 rules (was 0).
- **6N-C-2** — root cause propagation audit + fix. The `wagf-domain-builder` skill (`SKILL.md` + 2 reference docs) and the `HOW_TO_ADD_A_NEW_DOMAIN.md` guide had all been teaching the wrong `rules:` key, so any domain built by following them inherited the dead-config trap. Five doc-files corrected in this commit: `.claude/skills/wagf-domain-builder/SKILL.md`, `.../references/cognitive_framework_chooser.md`, `.../references/edit_pass_checklist.md` (2 spots), `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` (2 spots).
- **6N-C-3** — empty-block prophylactic. `examples/gossip_demo/config/agent_types.yaml` and `examples/vaccination_ma_demo/config/agent_types.yaml` each had 3 `rules: []` (empty list) blocks. Currently harmless (nothing to be dead) but a future rule-adder would silently re-introduce dead config. Renamed all 6 to `thinking_rules: []`.

Audit verdict — repo-wide grep for bare `rules:` returns zero matches outside legitimate `*_rules:` keys (`thinking_rules`, `coherence_rules`, `business_rules`, `temporal_rules`, `identity_rules` in archive). Water-domain YAMLs (irrigation, single-agent flood, governed_flood, MA flood Paper 3) were ALL using `thinking_rules:` correctly already — bug isolated to the non-water demos whose authors followed the mis-teaching skill.

**Closed by Phase 6N-B** (2026-05-23) — two broker-side bugs surfaced during the L3-1B vaccination_demo Tier-2 upgrade smoke iterations:
- **6N-B-1** — `BaseAgentContextBuilder.format_prompt` did not inject the YAML-defined `{response_format}` JSON schema into prompts. Only `TieredContextBuilder` (used when an `InteractionHub` is wired) did. So any single-agent / no-Hub domain whose prompt template carried `{response_format}` fell through to `SafeFormatter`'s `[N/A]` default, leaving the LLM with no schema example. Caught when the vaccination_demo L3-1B smoke #1 hit 9/10 fallback under a 6-construct prompt (irrigation never hit this because its `run_experiment.py` pins `TieredContextBuilder(hub=None)` explicitly). Fixed by lifting the same try/except injection block from `TieredContextBuilder.format_prompt` (around line 543-562) into `BaseAgentContextBuilder.format_prompt` (line ~195), so the inheritance hierarchy now handles both paths. Smoke #3 + #5 verified the fix: 10/10 APPROVED with `<<<DECISION_START>>>` schema correctly injected.
- **6N-B-2** — the construct-LABEL regex extractor at `broker/utils/parsing/unified_adapter.py:~463` matched case-insensitively via `re.IGNORECASE` but `match.group(1)` preserved whatever case the LLM emitted. A chatty `gemma3:1b` writing `"m"` instead of `"M"` produced mixed-case labels in the audit CSV like `['M', 'm']`, breaking downstream governance rule conditions like `in ['H', 'VH']` that miss the lowercase variants. Fixed by calling `.upper()` on the captured group for LABEL constructs — the ordinal alphabet (VL/L/M/H/VH) is canonical uppercase by contract. Smoke #5 confirmed zero lowercase leaks across all 6 HBM construct columns.

Test coverage: `broker/tests/test_context_builder_response_format.py` carries three regression tests — `test_base_context_builder_injects_response_format` (Bug 1), `test_label_capture_normalized_to_uppercase` (Bug 2 inline regex), and `test_label_capture_no_lowercase_leak_documented` (Bug 2 grep-based contract).

**Closed by Phase 6N** (2026-05-23) — the audit-writer leak surfaced during the Phase 6M+README review round. `broker/components/analytics/audit.py` §6 (social-context CSV block) used to hardcode `elevated_neighbors` / `relocated_neighbors` as dict-key reads when emitting `social_elevated_neighbors` / `social_relocated_neighbors` columns — flood-domain skill names baked into a generic audit writer. Two tokens (`elevated_neighbors` + `relocated_neighbors`) were missing from `_DOMAIN_TOKENS`, so the I5 guard never caught the leak; the existing `social_elevated_neighbors` / `social_relocated_neighbors` column names were even priority-listed in `audit.py`'s `compute_csv_fieldnames`. The README review was about to claim "enforced by `TestDomainGenericity`" without disclosing this gap.
- **6N-A** — `audit.py` §6 migrated to a dynamic `social_<key>` pass-through (`for vkey, vval in visible.items(): row[f"social_{vkey}"] = vval`); the hardcoded column names removed from `priority_keys`. The visible-actions loop runs AFTER the broker-owned writes for `social_gossip_count` / `social_neighbor_count` / `social_network_density` so a domain that collides on those key names cannot silently overwrite them. The `else`-branch placeholders that wrote `0` for the two specific flood columns also dropped (now only `social_gossip_count` + `social_neighbor_count` + `social_network_density` get unconditional defaults, since those are the three columns the writer truly owns domain-independently; flood-style columns now simply don't appear in rows where `social_audit` is absent). The `_DOMAIN_TOKENS` guard widened with `elevated_neighbors` + `relocated_neighbors` (count 23 → 25). `TestDormantFieldPolicy._AUDIT_AGGREGATE_KEYS["social_audit"]` updated to drop the two flood column names from the documented column list (they're domain-dynamic now). Downstream CSV schema is byte-identical for any domain whose social context provider still supplies the same dict keys on populated rows — flood reproduces flood columns, vaccination would reproduce `social_vaccinated_neighbors` etc.

**Closed by Phase 6M** (2026-05-23) — the "PMT schema extraction" item the Phase 6L plan deferred. A fresh Phase 6M investigation (three Explore agents) inverted the original risk profile: the Pydantic class targeted for hierarchy refactor was dead code, the response-format builder was already YAML-driven, and three non-PMT reference domains (`vaccination_demo` / `vaccination_ma_demo` / `gossip_demo`) already plug in without touching the schema. So the actual change shrank to a surgical cleanup, not a hierarchy refactor.
- **6M-A** — `broker/interfaces/schemas.py` `ReasoningSchema` (PMT `threat_appraisal` / `coping_appraisal` Pydantic fields) deleted as dead code (Phase 6M Explore: 0 imports, 0 instantiations, 0 type annotations across `broker/`, `examples/`, `tests/`). Reasoning payloads flow through the construct-agnostic `SkillProposalSchema.reasoning: Dict[str, Any]` field (its `description` simultaneously de-PMTed to `"Construct appraisals (domain-defined keys)"`); response-format builder reads construct names from YAML. `threat_appraisal` + `coping_appraisal` added to the I5 `_DOMAIN_TOKENS` guard (count 21 → 23). Three tail mentions in generic `broker/` FP-allowlisted with per-entry justifications: `components/response_format.py` (docstring `Usage:` + construct-mapping examples), `interfaces/schemas.py` (deletion-marker comment), `validators/posthoc/unified_rh.py` (backwards-compat `ta_col`/`ca_col` defaults retained with a docstring caveat; the existing column-existence guard at line 177 is the safety net — a non-PMT caller with no matching columns drops cleanly to the `"M"` mid-scale sentinel rather than misclassifying).

**Deferred** (deliberate scoping decisions carried over from Phase 6K):
- **Skill-name docstring cleanup** — `elevate_house` / `buy_insurance` / `relocate` / `maintain_demand` appear in many generic broker docstrings and protocol examples as grounded examples. Phase 6J-E Explore verified ZERO live code references for these four tokens. Keeping the examples aids readability; the I5 guard intentionally does NOT enforce these tokens.

---

## Invariant 6 — Run-integrity provenance contract

### Contract

A run's `config_snapshot.yaml` records the CONFIG that was *requested*; it does
not record what the framework actually *instantiated* at runtime. Those can
diverge silently. Every run therefore MUST also emit a `run_integrity.json` side
artifact that records the runtime instantiation truth — which memory engine class
was actually wired, whether the reflection engine exists, and how many reflection
entries were produced — and MUST flag (never abort) when the runtime contradicts
the config.

### Rules

1. The single source of truth is `broker/core/run_integrity.py::record_run_integrity`.
   Every run entry point (single-agent `run_flood.py`, `ExperimentRunner.finalize`)
   calls it; new run paths MUST call it too.
2. It is **record-and-FLAG, never raise**. `run_integrity.json` is a side artifact
   and MUST NOT touch the byte-locked simulation outputs (`simulation_log.csv` /
   `*_audit.csv`). Aborting a long real-LLM run because a *log file* looked short
   would be worse than the defect. A `humancentric` memory engine with zero
   reflection entries sets `integrity_ok=false` and prints a loud warning; it does
   not stop the run.
3. The recorded contract MUST include at minimum: `memory_engine_type` and/or
   `memory_engine_class`, `reflection_log_entries`, `governance_mode`, `seed`, and
   `integrity_ok`. `ExperimentRunner` additionally embeds the same dict in
   `reproducibility_manifest.json` under `run_integrity`.
4. Reflection parity is asserted whenever the memory engine is humancentric — by the
   explicit `memory_engine_type` string (run_flood) or inferred from the instantiated
   engine class (ExperimentRunner). Non-humancentric engines record their class but
   never false-flag. The `reflection_engine` object, when passed, is recorded as
   `reflection_engine_wired` for transparency but does not gate the expectation.

### Detection / enforcement

- `broker/tests/test_framework_invariants.py::TestRunIntegrityContract` — asserts the
  key properties: `record_run_integrity` writes only `run_integrity.json` (no
  byte-locked output touched); flags the `humancentric`-but-no-reflection mismatch with
  `integrity_ok=false` on BOTH the explicit-type path (run_flood passes
  `memory_engine_type`) and the inferred-class path (ExperimentRunner passes the engine
  object, class name → type); never raises (including a non-serializable `extra` and an
  unwritable output dir); and does not false-flag a non-humancentric engine.
- `python -m broker.tools.check_run_integrity <run_dir> [...]` — generic CI / operator
  checker; exits 1 on any `integrity_ok=false`. The NW-paper gov-vs-noval *pairwise*
  checker is the domain-specific companion at
  `examples/single_agent/analysis/check_run_integrity.py`.

### Known current state (added 2026-05-30)

Motivated by the 2026-05-30 reflection-missing data-defect audit: a no-validator
flood batch ran with `memory_engine_type='humancentric'` in config but the reflection
engine stayed `None`, so reflection never ran. `config_snapshot.yaml` looked correct;
the runtime silently diverged; the gov-vs-noval comparison gained a reflection
confound that no artifact surfaced (18 runs quarantined, headline P0 re-run scheduled).
The single-agent `run_flood.py` stopgap guardrail (added the same day) is now absorbed
into `record_run_integrity`; `ExperimentRunner` was extended in the same change so the
irrigation / multi-agent path records its runtime memory engine class too (the silent
`WindowMemoryEngine` fallback in `ExperimentRunner.__init__` is the analogous trap).
Byte-identity verified: `run_integrity.json` is a pure side artifact; v21 / paper-3
mock-LLM CSV output is unchanged.

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

### vaccination_demo Tier-2 showcase complete — 2026-05-24

**Datasets**: vaccination_demo upgraded from L3-1A's 5-agent / 2-year PoC to L3-1 chain Tier-2 showcase across 4 sub-steps + close-out — 25 literature-grounded agents (US Census + Pew + CDC), 5-year COVID-19-anchored outbreak schedule, 5 YAML thinking_rules covering all 6 HBM constructs, 3-seed × 2-model batch runner.

**Broker changes in the L3-1 chain**: Phase 6N-A (audit.py social-context de-flood) + Phase 6N-B (BaseAgentContextBuilder response_format injection + unified_adapter `.upper()`) + Phase 6N-C (`rules:` → `thinking_rules:` docs/skill cleanup) + Phase 6N-D-1/2/4 (ThinkingValidator level / RuleCondition normalisation / unified_adapter regex whitelist) + Phase 6N-D-3 (rule_breakdown audit regression test) + Phase 6N-E (RuleCondition shape compat) + L3-1D env_context flattening in tiered.py. All broker changes are paper-1b-data-safe per the Pre-Phase-6N-B LABEL-case data hygiene audit (next entry) and the 6N-D-1 static paper-data audit (0 fires of WARNING+blocked_skills rules across 39,943 paper-1b reference rows).

**Implication**: WAGF non-water generalisation now has a Tier-2 reference domain. The original Phase 6C-v3 vaccination_demo PoC (5 agents, 2 years, 2/6 HBM constructs, dead `rules:` block) is superseded by the L3-1 chain. The vaccination_demo Tier-2 setup demonstrates the framework's plug-in path end-to-end: YAML thinking_rules fire under live LLM input (Phase 6N-E regression test), year-specific env signals flow into the LLM prompt (Phase L3-1D + tiered.py env_context flatten), 6/6 HBM constructs populate the audit CSV.

**Audit detail**: full sub-step inventory in `CHANGELOG.md` entries for L3-1A through L3-1G + Phase 6N-A through 6N-E.

### Pre-Phase-6N-B LABEL-case data hygiene audit — 2026-05-23

**Context**: Phase 6N-B fixed two latent broker bugs (Bug 1: `BaseAgentContextBuilder` did not inject `{response_format}`; Bug 2: `unified_adapter.py` captured LABEL strings in whatever case the LLM emitted instead of normalising to canonical uppercase). The L3-1B vaccination_demo smoke caught both; Bug 2 in particular raised a concern that pre-Phase-6N-B audit CSVs across the water-domain papers might also carry lowercase contamination.

**Audit run** (2026-05-23 against the on-disk audit CSVs that already underlie Paper 1b headline numbers):

| Dataset | Lowercase LABEL rows | Total rows | Contamination % |
|---|---|---|---|
| Irrigation v21 5-seed (Gemma-3 4B, `wsa_label` + `aca_label`) | **0** | 65,304 | 0.00% |
| Flood single-agent Group_C 5-run (Gemma-3 4B, `construct_TP_LABEL` + `construct_CP_LABEL`) | **2** | 8,918 | 0.022% |
| Vaccination smoke #4 (Gemma-3 1B, all 6 HBM `_LABEL` columns) — pre-Phase-6N-B baseline | 1 | 60 | 1.67% |

**Specific findings on Paper 1b flood data**: two `construct_CP_LABEL` rows carry `'m'` instead of `'M'` — one in `JOH_FINAL/gemma3_4b/Group_C/Run_2` and one in `Run_3`. Both are in the small-model 4B baseline; the 12B / 27B / Ministral cross-model runs were not exhaustively audited but the same root cause applies wherever a chatty LLM emits a lowercase label.

**Implication for Paper 1b headline numbers**: **NONE**. The IBR computation pipeline at `paper/nature_water/scripts/gen_fig2_case1_irrigation.py:694` (irrigation) and the analogous flood-side path filter on `tp.isin(['H','VH'])` after `.str.upper().str.strip()` — the existing analysis code already applies an explicit uppercase pass before the membership test. So the 2 `'m'` rows in the flood data:
1. Do not get counted into the "high TP" set (a sane behaviour — they read as missing rather than as `'M'`-medium).
2. Do not move the IBR formula `R1 + R3 + R4` denominator or numerator since the formula filters by tp/cp band, not by the raw label value.

**Confirmation**: re-ran the Paper 1b headline computations on 2026-05-23 against the same CSV files — irrigation `36.1 ± 3.6%` gov / `59.1 ± 1.7%` no-val (ΔIBR `+23.0 pp`, p=0.0001) and ΔEHE `+0.184` (p=0.0014) reproduce byte-identical to the published values. Flood gemma3:4b `0.87 ± 0.91%` gov / `8.53 ± 1.08%` no-val matches the memory-recorded corrected band (0.9% / 8.5%).

**No paper re-run required**. Post-Phase-6N-B audit CSVs (any new run from commit `4c112d0` onward) will be free of lowercase leaks because `unified_adapter.py` now applies `.upper()` at capture time. The 2 historical `'m'` rows in flood Paper 1b are recorded here as a documented pre-existing data-hygiene observation, not as a reproducibility flaw.

**Audit script**: in-line Python at the end of the post-Phase-6N-B conversation log (2026-05-23). Re-runnable via `pandas.read_csv` on the result dirs above; the check is `df[col].astype(str) != df[col].astype(str).str.upper()`.

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
