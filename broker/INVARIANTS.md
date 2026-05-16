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
- `broker/components/cognitive/adapters.py::DomainReflectionAdapter` — protocol defined, zero implementations. Reflection.py hardcodes flood logic instead of using the adapter.
- `broker/components/orchestration/phases.py:48` — `saga_coordinator` parameter unused. Must be removed or activated.
- `broker/components/memory/engines/hierarchical.py::_consolidate` — no-op stub. Module already `@deprecated`; cleanup deferred to a separate hygiene pass.

---

## Invariant 5 — Domain-genericity contract

### Contract
Modules under `broker/components/` and `broker/core/` MUST be domain-agnostic. Domain-specific logic belongs in `examples/<domain>/` or behind `Adapter` protocol implementations.

### Rules
1. No field names like `elevated`, `flood_count`, `WSA`, `insurance`, `drought_tier` may appear in `broker/components/` or `broker/core/` Python code unless:
   - Inside a `domain_adapters/` sub-directory, OR
   - Inside a generic `custom_attributes: Dict[str, Any]` pass-through field, OR
   - On an explicit allow-list in `broker/tests/domain_tokens_allowlist.txt`.
2. Emotion keyword maps, importance heuristics, and validator rule sets MUST be injectable via domain adapter protocols — never hardcoded with one domain's vocabulary in generic code.
3. If a generic module has "default behavior for one particular domain" baked in, that behavior MUST be moved to an explicit default adapter that can be swapped.
4. Default skill names (e.g., `do_nothing`, `maintain`) MUST come from configuration, not from `broker/components/governance/registry.py` constants.

### Detection / enforcement
- `tests/test_domain_genericity.py` — Phase 6A landing tests covering registry default + retriever fallback. Future iterations should expand the grep-style sweep to `broker/components/` and `broker/core/` against an allow-list.
- Code review: any new feature in `broker/` must pass the domain-token check.

### Known current state (updated 2026-04-26 by Phase 6A landing)

**Phase 6A landed (deprecation-warn or fixed)**:
- `broker/components/governance/registry.py` — `_default_skill` now tracks `_default_skill_explicit`; `get_default_skill()` emits one-time warning when YAML did not declare `default_skill:`. All 9 existing example domains already declare it (verified). Behavior preserved.
- `broker/components/governance/retriever.py:23` — was `["do_nothing"]`; now empty list with one-time warning if instantiated without `global_skills`. Production path unaffected (broker engine wires `global_skills` from `agent_types_config.get_global_skills`).
- `broker/core/experiment_runner.py` (6 cache-fallback sites) — was hardcoded `"do_nothing"`; now reads `self.broker.skill_registry.get_default_skill()`. Irrigation cache misses now fall back to `maintain_demand` instead of `do_nothing`.
- `broker/components/cognitive/reflection.py:403` — legacy flood-specific importance fallback now emits one-time deprecation warning naming the offending keywords (`flood_count`, `elevate_house`, `relocate`, `buy_insurance`, `do_nothing`) and pointing callers at `DomainReflectionAdapter`. **TODO(v22)**: extract into `FloodReflectionAdapter` under `broker/domains/water/`.

**Deferred to v22 (still real leaks; see Phase 6 sweep findings 2026-04-26)**:
- `broker/components/social/perception.py:41-67` — `PERCENTAGE_FIELDS` and `COMMUNITY_OBSERVABLE_FIELDS` hardcode flood metrics (`insurance_penetration_rate`, `elevation_penetration_rate`, `relocation_rate`, `neighbors_elevated`, `neighbors_relocated`). Needs adapter pattern; non-trivial refactor (~150 lines).
- `broker/components/cognitive/reflection.py:302-309` — agent-status text generator hardcodes `elevated`, `insured`, `flood_count` literals. Needs `AgentContext` protocol redesign.
- `broker/components/prompt_templates/memory_templates.py` — entire class is flood-specific (flood_zone, flood_experience, FEMA). Move to `broker/domains/water/` plus introduce a domain-pluggable template registry.
- `broker/domains/water/validator_bundles.py:35-61` — broker code imports from `examples/irrigation_abm/` and `examples/governed_flood/`, violating "examples plug into broker, not the reverse". Architectural fix.
- `broker/core/agent_initializer.py:52-56, 515` — `AgentProfile` dataclass + unified-context-builder field extraction hardcode `["elevated", "insured", "relocated", "savings", "income"]`. Needs config-driven extraction list.

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
