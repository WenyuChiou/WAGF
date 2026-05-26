# Changelog

All notable changes to the Water Agent Governance Framework (WAGF) will be
documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Phase 6H (DomainPack v2 + genericity hardening) — **Items 1–9 of 9
complete** (closed 2026-05-21 / 2026-05-22; original 8-item scope
extended to 9 when reflection.py status-text was split out from
Item 5/perception into its own Item 9). The `I5 TestDomainGenericity`
KNOWN-DEBT allowlist is now empty (all entries downgraded to docstring-only false-positives;
no generic `broker/` file carries a live domain-token leak — see
`broker/INVARIANTS.md:140` and the closure-comments in
`broker/tests/test_framework_invariants.py:452-471`).

Phase 6P (post-6H genericity polish) — **Sub-phases 6P-A → 6P-E
shipped 2026-05-25**. Closes the runtime cross-namespace coupling
(6P-A `validate_all` dispatcher · 6P-B `phases.py::from_domain` ·
6P-C `agent_initializer` loader dispatch · 6P-D event-generator
vocabulary · 6P-E hazard severity hook + source-level vocab guard).
Net-zero paper-1b reproducibility regression; 2388/0-failed full
pytest baseline.

Phase 6Q (genuine genericity debt close-out) — **in flight**.
After Phase 6P, a 5-parallel-subagent audit surfaced 3 BLOCKERs
the original Phase-6P audit missed (memory-strategy
`stimulus_key="flood_depth"` default · `ThinkingValidator
(framework="pmt")` default · hazard event payload schema
hardcoding `depth_m`/`depth_ft`) plus a Phase-6P-B follow-on
(`_default_phases()` static method still water-importing). Phase
6Q-A closes the doc-rot + the missed `_default_phases` coupling;
6Q-B through 6Q-F land BLOCKER fixes + a fake-traffic E2E
genericity gate. See `~/.claude/plans/breezy-dazzling-knuth.md`.

### Changed

- **Phase 6Q-F-2-a — Foundation for full E2E genericity gate (fake-traffic fixture package)** (2026-05-26). First half of the Phase 6Q-F-2 plan documented in `~/.claude/plans/breezy-dazzling-knuth.md`. Phase 6Q-F-1 (commit `fdd0dcf`) landed the structural + sys-modules gates using an inline `FakeTrafficDomainPack` defined in the test file itself; this sub-phase **promotes the fixture to a proper package** at `examples/_test_fixtures/fake_traffic/` with full YAML configs + MockTrafficLLM responses, so deeper layers of the broker pipeline can be exercised end-to-end in Phase 6Q-F-2-b (the actual 1-year `ExperimentRunner.run`, deferred).
  - **NEW `examples/_test_fixtures/__init__.py`** + **`examples/_test_fixtures/fake_traffic/__init__.py`** — the fixture package + registration. Mirrors the `examples.governed_flood` / `examples.vaccination_demo` pattern: explicit `DomainPackRegistry.register("traffic", FakeTrafficDomainPack())` at module import time (Phase 6Q-G contract). Underscore prefix in the directory name (`_test_fixtures`) signals "internal — NOT a paper-shipping example".
  - **NEW `examples/_test_fixtures/fake_traffic/pack.py`** — `FakeTrafficDomainPack` subclasses `DefaultDomainPack`. Overrides only what's needed to exercise reflection + memory + skill registry paths: `name`, `reflection_status_text`, `reflection_questions`, `reflection_persona`, `importance_profiles`, `emotional_keywords`, `extreme_actions`, `action_taxonomy`, and crucially `psychological_framework() → FRAMEWORK_ESCAPE_HATCH`. This is the central genericity claim: a domain with NO registered psychometric framework can still drive the broker end-to-end.
  - **NEW `traffic_skill_registry.yaml`** — 6 skills (`take_alternate_route` / `delay_departure` / `switch_to_transit` / `carpool` / `do_nothing` for commuters; `announce_advisory` for dispatchers). Vocabulary is congestion-response themed; zero flood vocabulary (regression-tested below).
  - **NEW `traffic_agent_types.yaml`** — 2 agent types (`commuter` + `dispatcher`). Both declare `psychological_framework: ""` (the FRAMEWORK_ESCAPE_HATCH sentinel). `global_config.memory.stimulus_key: "congestion_level"` satisfies the Phase 6Q-C required-key contract.
  - **NEW `mock_responses.py`** — `MOCK_TRAFFIC_RESPONSES` dict (year-keyed deterministic LLM responses) + `MockTrafficLLM` class. Mirrors the `tests/fixtures/mock_llm.py::MockLLM` pattern but lives inside the fake_traffic package for cohesion (also avoids the `tests/` not-being-a-package import issue).
  - **NEW `tests/integration/test_e2e_genericity.py`** — 9 construct-time assertions across 4 classes:
    - `TestFakeTrafficPackageImport` (3 tests) — package imports cleanly; FakeTrafficDomainPack registers; `psychological_framework()` returns the escape hatch sentinel.
    - `TestTrafficYAMLConfigs` (2 tests) — skill_registry + agent_types YAML parse, contain expected non-water structure, contain zero flood-domain skill names (regression guard).
    - `TestMockTrafficLLM` (3 tests) — mock responses parse as valid broker JSON payloads; year + agent_type dispatch works; responses contain zero flood vocabulary.
    - `TestFakeTrafficSysModulesCleanliness` (1 test) — subprocess-isolated assertion that importing the fake_traffic package + calling `DomainPackRegistry.get("traffic")` triggers ZERO water-module loads. Complements the structural gate from Phase 6Q-F-1 (which exercises `build_domain_validators("traffic")` cleanliness instead).
  - **Scope split rationale**: 6Q-F-2-a (this commit) = fixture package + read-only construct-time assertions, ~9 tests + ~250 LOC fixtures + ~150 LOC test = digestible commit. 6Q-F-2-b (next session) = 1-year synthetic `ExperimentRunner.run` + audit-CSV assertions + retry-loop exercise, ~400 LOC + ~2-3 hr work that benefits from fresh attention.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2439 passed / 10 skipped / 0 failed** (+9 vs post-Phase-6Q-K-1 2430 baseline).
  - **Layer 5 audit status**: structural gate (6Q-F-1) ✓ + sys-modules gate (6Q-G) ✓ + **fixture-package gate (6Q-F-2-a, this commit) ✓**. Remaining: actual ExperimentRunner.run trace exercise (6Q-F-2-b).

- **Phase 6Q-K-1 — Remove last 2 PMT-bias fallbacks in `unified_context_builder`** (2026-05-26). First half of Layer 3 audit cluster A (4 PMT-bias paths from the Phase 6P-E follow-up). Two changes, both in `broker/core/unified_context_builder.py`:
  - **`_get_framework_for_type` line 495**: changed catch-all default from `PsychologicalFrameworkType.PMT` → `PsychologicalFrameworkType.GENERIC`. Pre-6Q-K-1 any agent_type that didn't match the household/government/insurance substring branches silently inherited PMT framework labels — a flood-bias for unrecognised agent types. The 3 explicit branches still resolve correctly for water-MAS agent types (`household_*` / `nj_government` / `insurance` keep matching). Downstream consumers passing `"generic"` to `ThinkingValidator` get the Phase 6Q-D-4 graceful FRAMEWORK_ESCAPE_HATCH downgrade (since `"generic"` is in `FrameworkType` enum but not in `FRAMEWORK_LABEL_ORDERS` registry — fail-soft via the cascade defense).
  - **`_get_constructs_for_type` lines 520-523**: replaced PMT-flavoured `TP_LABEL`/`CP_LABEL` fallback dict with `{}` + warn-once-per-agent_type. Pre-6Q-K-1 (Phase 6M-A documented but preserved the bias) any agent_type without an explicit `constructs:` YAML block AND no `type_def` in `agent_type_registry` silently received PMT framework constructs — leaking flood-framework vocabulary into every domain that forgot to declare its own. Now: empty dict + a one-time warning naming the agent_type and pointing readers at the YAML fix. New `_WARNED_UNDECLARED_CONSTRUCTS` set parallels the existing `_WARNED_UNDECLARED_FRAMEWORK` dedup pattern.
  - **Backward-compat**: Flood/Irrigation/Vaccination YAML all declare `constructs:` per Phase 6P-E (verified by grep) — they hit the early-return at the `type_def.constructs` line and never reach the fallback. Paper-1b byte-identical preserved.
  - **Round-1 issue + fix**: my first version of the warning text included literal water-domain construct names (`WSA_LABEL+ACA_LABEL`) as illustrative examples — this tripped `TestDomainGenericity::test_no_unmarked_domain_token_in_generic_code` (2 failures: WSA_LABEL + ACA_LABEL detected as water tokens in generic broker source). Rewrote the warning text without specific labels.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2430 passed / 10 skipped / 0 failed** (same as post-Phase-6Q-J baseline; the test renames within `_WARNED_UNDECLARED_CONSTRUCTS` are new but don't add visible regression tests yet — `_get_constructs_for_type` empty fallback is exercised only when no domain declares constructs, which doesn't happen for the 3 example domains).
  - **Audit cluster A status**: items #1 + #2 CLOSED. Items #3 (`AgentProfile` typed PMT fields) + #4 (`SyntheticLoader.PMT_PARAMS`) deferred to Phase 6Q-K-2 — they form a tightly-coupled pair (PMT_PARAMS → AgentProfile.tp_score etc.) and the audit's "M effort" estimate underweighted the consumer-graph blast radius. Cleaner to handle alongside Phase 6R sub-protocol split.

- **Phase 6Q-J — Remove `from_domain(None) → "flood"` legacy default** (2026-05-26). Closes Layer 3 audit finding #10 from the Phase 6P-E follow-up. Pre-fix `broker/components/orchestration/phases.py:137` had `resolved = (domain or "").strip().lower() or "flood"` — `None` and empty-string both fell through to the flood domain layout. This was a Phase 6P-B (2026-05-25) backward-compat carryover; every other dispatch path in the broker treats `None`-domain as "use the generic fallback", but `from_domain` alone kept silently defaulting to flood.
  - **`broker/components/orchestration/phases.py:137`** — `or "flood"` removed; the `resolved is not None` branch is now an explicit guard, and the generic 3-phase layout is returned for any `None`/empty input. Docstring updated to reflect the new contract (`Phase 6Q-J: None now resolves to generic, not flood`).
  - **`tests/test_phase_orchestrator.py`** — `test_from_domain_none_uses_default_phases` renamed to `test_from_domain_none_uses_generic_phases` and assertion flipped: `assert len(orch.phases) == 3` (was `== 4`). The explicit `from_domain("flood")` test was untouched and continues to assert 4-phase flood layout.
  - **Backward-compat scope check**: `grep PhaseOrchestrator.from_domain` repo-wide before the change — only `tests/test_phase_orchestrator.py` and `tests/integration/test_communication_layer.py` call it, and only the former passes `None`. No production callers affected (paper-1b runners construct `PhaseOrchestrator` directly with explicit `phases=`).
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2430 passed / 10 skipped / 0 failed** (same as post-Phase-6Q-E; test renamed + assertion flipped, net-zero count change).

- **Phase 6Q-E — De-flood the scaffold-domain default-skill placeholder** (2026-05-26). Closes Layer 3 audit finding #18 from the Phase 6P-E follow-up. Pre-fix `broker/tools/scaffold_domain.py:130, 239` had `default = skills[0] if skills else "do_nothing"` — a new-domain author scaffolding without `--skills` inherited the flood-domain skill name `"do_nothing"` (registered in `examples/governed_flood/config/skill_registry.yaml:43`) in their generated `skill_registry.yaml` + `agent_types.yaml`. Functionally dead (the placeholder only fires when `skills` is empty; experiment_builder catches the invalid reference at run time) but cosmetically wrong — a vaccination researcher reading their fresh scaffold output sees a flood-specific name.
  - Renamed both fallbacks to `"TODO_default_skill"`. The TODO-marker is visibly a placeholder that won't pass an editorial pass, signaling clearly "you must supply real skills". Generic naming avoids the cross-domain leak.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2430 passed / 10 skipped / 0 failed** (same as post-Phase-6Q-D-5; scaffold output is checked by manual invocation of `python -m broker.tools.scaffold_domain`, not by existing tests).

- **Phase 6Q-D-5 — Cascade defense for `UnifiedCognitiveEngine` strategy ctor + `DomainPackRegistry.register` smoke-test** (2026-05-26). Closes the two remaining MED-class boundary-audit pairs surfaced by the Phase 6Q-D-3 follow-up audit. Both fixes are defense-in-depth: existing guards already cover the common cases, but edge cases (whitespace-only stimulus_keys, partially-imported custom packs) could still crash the broker before today.
  - **Pair #4b CLOSED — `broker/memory/unified_engine.py`**: surprise-strategy construction at lines 263-296 now wrapped in `try/except ValueError`. Pre-fix the falsy-guards (`if self.domain_config.sensory_cortex` / `elif self.domain_config.stimulus_key`) already filtered out None/empty cases, so Phase 6Q-C's strict-required-kwarg ValueError was unlikely to fire here — but edge cases (whitespace-only strings, sensors=[] with default_sensor_key=None, custom `DomainConfig` subclass with unexpected falsy behaviour) could still slip through. On raise, the engine logs the offending config + falls back to `self._strategy = None`. Downstream `get_surprise` callers already handle the null-strategy case (returns 0.0 surprise + SYSTEM_1).
  - **Pair #5 CLOSED — `broker/domains/registry.py`**: new `DomainPackRegistry._smoke_test_pack(name, pack)` helper called at registration time. Iterates a representative subset of DomainPack methods (`psychological_framework`, `extreme_actions`, `memory_policy` — 3 chosen because they sit on hot consumer paths: validator dispatch + reflection + memory engine). For each: if missing → log "missing method" warning; if call raises → log warning naming the method + exception type. Pack is STILL registered (Phase 6Q-D-4 already wraps the downstream consumers with graceful-fallback guards, so a broken pack in the registry doesn't crash the dispatch path). The smoke's value is **EARLIER detection**: a broken method surfaces at module-import time (where the trace points at the registration call site) instead of mysteriously during a multi-hour experiment run. Pure log-and-continue contract.
  - **NEW `broker/tests/test_cascade_defense_engine_registry.py`** — 5 regression tests:
    - `test_invalid_stimulus_key_falls_back_to_null_strategy` — engine null-fallback via monkey-patched raising EMA strategy.
    - `test_explicit_strategy_bypass_guard` — explicit `surprise_strategy=` skips construction entirely; guard never fires.
    - `test_broken_method_logs_warning_but_still_registers` — DomainPack with raising `psychological_framework()` registers with warning.
    - `test_missing_method_logs_warning` — DomainPack lacking `psychological_framework()` registers with "missing method" warning.
    - `test_happy_path_pack_registers_silently` — FloodDomainPack registers with zero smoke warnings.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2430 passed / 10 skipped / 0 failed** (+5 cascade-defense tests vs post-Phase-6Q-D-4 2425 baseline).
  - **All 4 boundary-audit pairs now CLOSED**: Pair #2 (6Q-D-4) + Pair #3 (6Q-D-4) + Pair #4b (6Q-D-5) + Pair #5 (6Q-D-5). The governance / validator / memory / DomainPack subsystem now has end-to-end graceful-degradation: broken packs and broken configs log warnings + keep the broker running with reduced fidelity instead of crashing.
  - **Performance note**: the registry smoke-test adds 3 method calls at each `DomainPackRegistry.register(...)` call. Called once per domain at module import — typical broker startup registers 1-3 packs total, so the added cost is sub-millisecond and only at import time, not hot-path.

- **Phase 6Q-D-4 — Cascade-failure defense for `build_domain_validators`** (2026-05-26). Closes the HIGHEST-leverage failure point identified by the Phase 6Q-D-3 follow-up boundary-audit. Pre-6Q-D-4 a custom DomainPack returning a typo'd / unregistered `psychological_framework()` string caused `ThinkingValidator.__init__` to raise `ValueError` (per the Phase 6C-v3 strict-registration guard), which propagated through `validate_all` → `SkillBrokerEngine` retry loop → killed the entire agent's year-N decision. No graceful fallback existed — a single typo in a custom pack took down the broker.
  - **Two defenses added to `broker/components/governance/domain_validator_dispatch.py::build_domain_validators`**:
    1. Each DomainPack accessor (`pack.extreme_actions()`, `pack.psychological_framework()`) wrapped in its own `try/except Exception` — broken pack methods now log a warning + fall back to a benign default (empty set / `FRAMEWORK_ESCAPE_HATCH`) instead of crashing.
    2. Pre-construction registry check: if `framework` is non-empty AND not in `FRAMEWORK_LABEL_ORDERS`, downgrade to `FRAMEWORK_ESCAPE_HATCH` with a warn-once-per-`(domain, framework)` dedup. Catches the typo case before `ThinkingValidator` can raise.
  - **Warn-once dedup pattern**: new module-level `_WARNED_UNREGISTERED_FRAMEWORK` set, same shape as `unified_context_builder._WARNED_UNDECLARED_FRAMEWORK` (Phase 6J-A precedent). 3 calls with the same `(domain, framework)` typo produce 1 warning, not 3.
  - **All warnings name the fix**: messages tell the operator what to do (call `register_framework_metadata(...)` at import time OR change the pack to return a registered name OR fix the pack's broken method).
  - **NEW `broker/tests/test_dispatcher_cascade_defense.py`** — 5 regression tests pinning the 3 cascade paths:
    - `test_typo_framework_downgrades_to_escape_hatch` — typo case → escape hatch + warning.
    - `test_downgrade_warn_dedup_per_domain_framework` — 3 dispatch calls produce 1 warning (dedup).
    - `test_psychological_framework_raise_falls_back_to_escape_hatch` — pack method raises → escape hatch + warning.
    - `test_extreme_actions_raise_falls_back_to_empty_set` — same for extreme_actions.
    - `test_registered_pmt_framework_passes_through` — happy path (FloodDomainPack → "pmt") unaffected.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2425 passed / 10 skipped / 0 failed** (+5 cascade-defense tests vs post-Phase-6Q-D-3 2420 baseline).
  - **Boundary audit pair status post-6Q-D-4**: Pair #3 (HIGH cascade — typo framework crashes pipeline) → **CLOSED**. Pair #2 (MED — pack method raise crashes dispatcher) → **CLOSED**. Pair #4b (MED — `UnifiedCognitiveEngine` doesn't guard EMA/Symbolic raises) → still open (Phase 6Q-D-5 candidate). Pair #5 (MED-HIGH — partial domain-pack registration) → still open (Phase 6Q-D-5 candidate).
  - **Happy path preserved**: registered frameworks (PMT/Utility/Financial/cognitive_appraisal/HBM) still pass through untouched. FloodDomainPack/IrrigationDomainPack/VaccinationDomainPack/all paper-1b runners unaffected.

- **Phase 6Q-D-3 — Wire `triggered_rules` audit producer + document `rules_evaluated_count` as KNOWN-DEBT** (2026-05-26). Closes a metric finding surfaced by the Phase 6Q-D-2 follow-up smoke (1-yr 3-agent flood + gemma4:e4b end-to-end). The smoke output showed `validated=True` but `rules_evaluated_count=0` for every audit row. Investigation: `broker/components/analytics/audit.py:352-354` reads `t.get("rules_evaluated", [])` and `t.get("triggered_rules", [])` from the trace dict — but **no producer anywhere in the codebase wrote either trace key**. Task-041 Phase 3 added the schema + reader without wiring the producer side. The columns were silent placeholders since they landed.
  - **`broker/core/_audit_helpers.py`** — added `_safe_triggered_rules(all_validation_history)` helper. Collects rule IDs from each `ValidationResult.metadata.rule_id` (single) + `metadata.rules_hit` (list, used by validator bundles), deduplicates + sorts. Returns `[]` on any error (audit write path must never crash — same defense-in-depth pattern as `_safe_rule_breakdown`). Trace dict at line 188 now sets `"triggered_rules": _safe_triggered_rules(all_validation_history)`. Distinct from the existing `failed_rules` column which is BLOCK-only via `validation_issues`; the new `rules_triggered` is BLOCK + WARN combined for a unified fire view.
  - **`.claude/skills/llm-agent-audit-trace-analyzer/references/trace_schema.md`** — updated the rule-audit table: `rules_triggered` annotated as wired-in-6Q-D-3 (was always-empty pre-fix); `rules_evaluated_count` annotated as **aspirational, currently always 0** (KNOWN-DEBT — closing this requires instrumenting the validator engine to emit a `rules_evaluated` list per decision regardless of fire status, deferred to a future 6Q-D-4 / 6R follow-up).
  - **NEW `broker/tests/test_triggered_rules_audit.py`** — 9 unit tests pinning the new helper: empty / single-rule_id / rules_hit list / BLOCK+WARN combined / dedup / sort / combined rule_id+rules_hit / malformed-history graceful fallback / no-rule_id-no-hits empty.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2420 passed / 10 skipped / 0 failed** (+9 triggered_rules tests vs post-Phase-6Q-D-2 2411 baseline).
  - **Live LLM gate**: Phase 6Q-D-2 smoke output already exercised the new producer path (humancentric memory + flood paper-1b proxy run); `rules_triggered` populates correctly when ValidationResults carry rule IDs. For the clean-approval row in that smoke `rules_triggered=""` (no rules fired — Year 1, agent made compliant choice), identical to `failed_rules=""` for the same row — the wiring is live but the data is empty *for that scenario*, which is the correct behavior.
  - **No new DomainPack hook needed** — the helper sources rule IDs from existing `ValidationResult` metadata; this is pure trace-side instrumentation.

- **Phase 6Q-D-2 — Relocate `create_flood_surprise_strategy` factory to water namespace** (2026-05-26). Closes Layer 3 audit finding #20 from the Phase 6P-E follow-up. Pre-6Q-D-2 the factory lived at `broker/memory/strategies/multidimensional.py:280` in generic broker namespace despite hardcoding flood-domain variable names (`flood_depth` / `neighbor_panic` / `elevated_pct` / `subsidy_rate`) — a domain-specific factory wearing generic clothes. Re-exported through `broker/memory/strategies/__init__.py` and `broker/memory/__init__.py` it presented itself as part of the broker's domain-neutral memory API.
  - **NEW `broker/domains/water/memory_strategies.py`** — verbatim relocation of the factory. The underlying `MultiDimensionalSurpriseStrategy` class stays in generic broker (it takes an arbitrary `variables: Dict[str, float]` and IS domain-neutral) — only the flood-flavoured factory shorthand moved.
  - **`broker/memory/strategies/multidimensional.py:280`** — factory body deleted; replaced with an inline tombstone comment recording the move + the Layer 3 audit finding.
  - **`broker/memory/strategies/__init__.py`** + **`broker/memory/__init__.py`** — `create_flood_surprise_strategy` removed from both the `from .multidimensional import (...)` block and the `__all__` list. Replaced with a tombstone comment pointing at the canonical water-namespace home.
  - **`tests/test_multidim_surprise.py:8-10`** — import path updated to `from broker.domains.water.memory_strategies import create_flood_surprise_strategy`. All 4 test instantiation sites unchanged (only the import line moves). The test still passes via the new path.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2411 passed / 10 skipped / 0 failed** (same baseline as post-Phase-6Q-H; no behavioral change). Sample smoke on `test_genericity_runtime_gate.py` + `test_broker_core_lazy_imports.py` + `test_multidim_surprise.py` → 32/32 green (new convention: sample 2-3 representative test files instead of running the full smoke battery for low-risk relocate-only commits).
  - **Paper-1b byte-identity**: `create_flood_surprise_strategy` has zero production callers in `examples/` — only `tests/test_multidim_surprise.py` uses it. Paper-1b runners use the directly-constructed `MultiDimensionalSurpriseStrategy(variables=...)` path (or the `EMASurpriseStrategy` / `HybridSurpriseStrategy` via Phase 6K-A `UniversalCognitiveEngine`). Move is test-only blast radius.

- **Phase 6Q-H — Retrospective-reviewer follow-up: direct lazy-import test + new-domain registration docs** (2026-05-26). Backfills the code-reviewer pass that was skipped on commits `fdd0dcf` (Phase 6Q-F-1) and `4bc5165` (Phase 6Q-G). Both retrospective reviewers returned APPROVE; this commit lands the 2 actionable items they flagged.
  - **NEW `broker/tests/test_broker_core_lazy_imports.py`** (~85 LOC, 6 tests) — direct coverage of the `broker/core/__init__.py` PEP 562 `__getattr__` lazy dispatch added in Phase 6Q-F-1. Pre-6Q-H the subprocess genericity gate exercised this path indirectly (asserting `import broker.core` doesn't pull water modules), but no test directly verified that `from broker.core import PMTFramework` returns the correct class. Tests cover: the lazy-map dict literal is canonical, names are absent from `broker.core.__dict__` until accessed (with `importlib.reload` baseline reset), each lazy attribute resolves to the same class object as the canonical `broker.domains.water.*` import, and unknown attribute access raises `AttributeError` per Python's standard contract.
  - **`.claude/skills/wagf-domain-builder/SKILL.md`** + **`.claude/skills/wagf-domain-builder/references/edit_pass_checklist.md`** + **`docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`** — added the Phase 6Q-G registration contract: any new domain using a water-registered psychometric framework (PMT / Utility / Financial / cognitive_appraisal) must add `import broker.domains.water` to its `__init__.py` before `DomainPackRegistry.register(...)`. Custom-framework domains (HBM-style) don't need it. Reference path: `examples/governed_flood/__init__.py`.
  - **YAGNI decision recorded**: the retrospective 6Q-G reviewer also flagged `broker/tools/{validate_prompt,readiness_report}.py` as future traps if they ever instantiate `ThinkingValidator` without an explicit `import broker.domains.water`. **Defensive guards NOT added** in 6Q-H: `readiness_report.py` explicitly disclaims validator loads in its module docstring ("never instantiates validators, never loads broker runtime"); `validate_prompt.py` is a static YAML/prompt validator that does not currently construct ThinkingValidator. If either tool grows that capability in Phase 6Q-F-2 (the deferred full-E2E gate), the maintainer adds the import then. Trade-off: clarity (no preemptive defensive code) over forward-defense (one-liner per tool).
  - **Round-1 code-reviewer feedback applied**: NIT 1 — comment in `test_broker_core_lazy_imports.py:test_lazy_names_are_NOT_in_module_dict_before_access` reworded for accuracy (the reload mechanic vs PEP 562 caching semantics were conflated in the original). NIT 2 — reviewer flagged `examples/governed_flood/__init__.py` as "unverified path" because they reviewed in isolation; confirmed live (the file was edited in commit `4bc5165` to add the explicit water import).
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2411 passed / 10 skipped / 0 failed** (+6 lazy-import tests vs post-6Q-G 2405 baseline).

- **Phase 6Q-G — Remove `broker/domains/__init__.py` auto-discovery; runtime gate now green** (2026-05-26). Closes the architectural genericity violation surfaced by the Phase 6Q-F-1 runtime gate. Pre-6Q-G this package ran `_discover_domain_packs()` at module-load time — `pkgutil.iter_modules(__path__)` scanned every sub-package under `broker/domains/` and called its `register()` function. Even a bare `from broker.domains.protocol import DomainPack` triggered the package `__init__`, which unconditionally loaded 7 water-namespace modules (`pmt` / `utility` / `financial` / `cognitive_appraisal` / `thinking_checks` / `social_specs` + the package itself).
  - **`broker/domains/__init__.py`** — `_discover_domain_packs()` function + its module-level call deleted. Module is now a pure docstring describing the new registration contract: each domain still self-registers at its `__init__.py` module-load time, but the trigger is an **explicit import** of that sub-package, not auto-discovery.
  - **Explicit water trigger added to dependent examples**:
    - `examples/governed_flood/__init__.py` — added `import broker.domains.water` (inside the existing `try:` block, before `DomainPackRegistry.register`). The dependency was always real (flood uses the PMT framework + thinking-validator metadata that water registers); 6Q-G makes it visible.
    - `examples/irrigation_abm/__init__.py` — same pattern; irrigation uses `cognitive_appraisal` framework, registered by `broker.domains.water`.
    - `examples/vaccination_demo/__init__.py` — unchanged (vaccination uses HBM which registers via `examples.vaccination_demo.cognition`; no water dependency).
  - **Explicit water trigger added to standalone tests**:
    - `tests/test_thinking_validator.py` — added `import broker.domains.water` (uses framework="pmt"/"utility"/"financial").
    - `broker/tests/test_thinking_validator_level.py` — same pattern.
  - **Runtime gate xfail removed**: `broker/tests/test_genericity_runtime_gate.py::TestTrafficDomainSysModulesGate::test_traffic_dispatch_does_not_load_water_modules` was xfailed in 6Q-F-1 as a documentation marker for this violation. With 6Q-G shipped, the gate now PASSES and serves as the regression guard. If a future change re-introduces a path where importing a non-water broker module transitively loads water, this assertion fires with the leaked module list.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2405 passed / 10 skipped / 0 failed** (net +1 vs post-Phase-6Q-F-1: the xfailed test converted to xpassed → now pure pass; one prior xfail counter retired).
  - **Live LLM gate**: Phase 6Q-D smoke re-run end-to-end — all 5 checks green (FloodDomainPack → "pmt" dispatch, IrrigationDomainPack → "cognitive_appraisal", VaccinationDomainPack → "hbm", FRAMEWORK_ESCAPE_HATCH path, gemma4:e4b reachable in 6.53 s). Initially failed in the first round of 6Q-G with `"framework 'pmt' is not registered"` — surfaced the missing-explicit-import in `examples/governed_flood/__init__.py` + `examples/irrigation_abm/__init__.py` immediately. Fix landed in the same commit (the gate worked exactly as intended — it caught a real regression that pre-6Q-G auto-discovery had masked).
  - **Paper-1b byte-identity preserved**: paper-1b flood + irrigation runners both go through `examples.governed_flood` / `examples.irrigation_abm` package import paths, which now explicitly trigger `broker.domains.water` registration. Framework registry state at the time `ThinkingValidator(framework=...)` constructs is identical pre/post-6Q-G — only the *trigger* changed (auto-discovery → explicit example import).
  - **Phase 6P-E 5-layer audit final state**: Layer 5 structural + sys-modules runtime gates BOTH GREEN. Outstanding from the audit: Layer 3 LOW/WARN tail (PMT-bias paths in `unified_context_builder.py` + `agent_initializer.py`), Layer 4 sub-protocol split (Phase 6R), Layer 5 full E2E pipeline with synthetic agent run + mock LLM (Phase 6Q-F-2). The framework is now demonstrably-generic at the import + dispatch layer; the deeper E2E remains as a follow-on validation.

- **Phase 6Q-F-1 — Minimal runtime genericity gate** (2026-05-26). Implements the structural half of the Layer 5 "fake-traffic E2E gate" from the post-Phase-6P-E plan. The full E2E with synthetic 1-year agent run + mock LLM (Phase 6Q-F-2) is deferred; this sub-phase lands the cheaper structural + sys-modules gate first because it surfaces ROOT causes the AST guard alone can't catch.
  - **NEW `broker/tests/test_genericity_runtime_gate.py`** — `FakeTrafficDomainPack` (a deliberately minimum-surface non-water DomainPack inheriting only `name="traffic"` from `DefaultDomainPack`) drives 5 structural assertions + 1 subprocess sys.modules assertion. The structural tests (in-process) confirm: `psychological_framework()` returns the `FRAMEWORK_ESCAPE_HATCH` sentinel (not silent "pmt"), `extreme_actions()` is empty (no flood inheritance), `csv_loader_class()` / `synthetic_loader_class()` / `phase_layout()` return None (generic fallbacks fire), and `build_domain_validators("traffic")` returns 5 validators with `framework=""` ThinkingValidator.
  - **`broker/core/__init__.py`** — fixed an eager-import that defeated the existing PEP 562 lazy `__getattr__` in `broker/core/psychometric.py`. Pre-6Q-F-1 the package `__init__` did `from .psychometric import (PMTFramework, UtilityFramework, FinancialFramework, ...)` which eagerly accessed those names, triggering 3 water-module imports + their 3 deprecation warnings on EVERY `import broker.core`. Replaced with eager-safe re-exports (`ConstructDef` / `PsychologicalFramework` / `ValidationResult` / registry helpers) plus a new package-level `__getattr__` that lazily resolves the moved water classes. Backward-compat preserved: `from broker.core import PMTFramework` still works for legacy callers; plain `import broker.core` no longer pre-loads water. (Side-effect: pytest warning count dropped 235 → 232 across the full suite.)
  - **Runtime gate **xfails** by design** — the subprocess sys.modules check at `TestTrafficDomainSysModulesGate::test_traffic_dispatch_does_not_load_water_modules` is currently expected to fail because **`broker/domains/__init__.py` runs `_discover_domain_packs()` at module-load time**. Even a bare `from broker.domains.protocol import DomainPack` triggers the package `__init__`, which scans every sub-package under `broker/domains/` (currently only `water`) and calls its `register()` function. This is a real architectural genericity violation deserving its own commit (Phase 6Q-G). The gate's `xfail` status documents the violation and converts to a regression guard the moment 6Q-G ships.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2404 passed / 10 skipped / 1 xfailed / 0 failed** (+5 structural tests + 1 xfailed subprocess gate vs post-Phase-6Q-D 2399 baseline).
  - **Phase 6Q-F-2 deferred scope** (next session or post-6Q-G): the full E2E gate with synthetic 1-year run + mock LLM + complete YAML configs lands the runtime trace-level genericity proof. The minimal 6Q-F-1 structural gate is the foundation; 6Q-F-2 adds the agent pipeline coverage.
  - **Layer 5 audit milestone**: with 6Q-F-1 landed, the Phase 6P-E 5-subagent audit's 5-layer model is now mostly closed — Layer 1 (6Q-B), Layer 2 (6Q-A), Layer 3 BLOCKERs (6Q-C + 6Q-D), Layer 4 doc gap (6Q-A), Layer 5 structural gate (6Q-F-1). Outstanding: Layer 3 LOW/WARN tail (PMT-bias paths in `unified_context_builder.py` / `agent_initializer.py`), Layer 4 sub-protocol split (Phase 6R), Layer 5 E2E pipeline (Phase 6Q-F-2), and the newly-surfaced Phase 6Q-G (`broker/domains/__init__.py` auto-discovery removal).

- **Phase 6Q-D — `ThinkingValidator` framework BLOCKER + YAML wiring restored** (2026-05-26). Closes Layer 3 finding #5 from the Phase 6P-E follow-up audit. Pre-6Q-D `ThinkingValidator.__init__(framework: str = "pmt")` silently defaulted to PMT for any caller that didn't pass `framework=` explicitly — and crucially, **the only two production callers** in `broker/components/governance/domain_validator_dispatch.py` (lines 41 + 95) **did not pass it**. Result: every domain's governance dispatch silently inherited PMT label ordering + PMT construct metadata regardless of YAML declaration. Vaccination_demo declared `psychological_framework: hbm` and irrigation_abm declared `psychological_framework: cognitive_appraisal` — both YAML fields were dead config.
  - **Wiring restored via DomainPack hook**:
    - **`broker/domains/protocol.py`** — added `DomainPack.psychological_framework() -> str` Protocol method. Documents the recognised values (`"pmt"` / `"cognitive_appraisal"` / `"hbm"` / `"utility"` / `"financial"`) + the `""` empty-string escape hatch for domains without registered framework metadata.
    - **`broker/domains/default.py`** — `DefaultDomainPack.psychological_framework()` returns `""` (escape hatch).
    - **`examples/governed_flood/adapters/flood_pack.py`** — `FloodDomainPack.psychological_framework()` returns `"pmt"` (matches its YAML).
    - **`examples/irrigation_abm/adapters/irrigation_pack.py`** — `IrrigationDomainPack.psychological_framework()` returns `"cognitive_appraisal"` (matches YAML; previously dead config).
    - **`examples/vaccination_demo/adapters/vaccination_pack.py`** — `VaccinationDomainPack.psychological_framework()` returns `"hbm"` (matches YAML; previously dead config).
    - **`broker/components/governance/domain_validator_dispatch.py`** — `build_domain_validators(domain)` now reads `pack.psychological_framework()` and passes it as `ThinkingValidator(framework=...)`. `_empty_validators()` (the unknown-domain fallback) explicitly passes `framework=""` instead of relying on the constructor default.
  - **Constructor signature changed**:
    - **`broker/validators/governance/thinking_validator.py:171`** — `framework: str = "pmt"` → `framework: Optional[str] = None`. Raises `ValueError` if `None` with a message naming Phase 6Q-D + listing the recognised framework values + the escape hatch. Pre-6Q-D's Phase 6C-v3 strict-registration check for non-empty unknown frameworks remains intact.
  - **Test sites updated** (5 implicit `ThinkingValidator()` calls relied on the silent PMT default):
    - `tests/test_governance_rules.py` — 3 sites updated to `ThinkingValidator(framework="pmt", ...)` (tests exercised PMT-specific rules).
    - `tests/test_thinking_validator.py:208, :350` — 2 sites updated to `ThinkingValidator(framework="pmt")`.
    - `tests/test_thinking_validator.py:340` — `test_default_framework_is_pmt` renamed to `test_framework_now_required` and rewritten to assert `ValueError` rather than the deprecated default.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2399 passed / 10 skipped / 0 failed** (net-zero vs post-Phase-6Q-C baseline — one test renamed, several updated, none removed).
  - **Live LLM gate**: 5-check smoke (`scratchpad/phase_6q_d_smoke.py`) — `ThinkingValidator()` raises with 6Q-D-namespaced error; all 3 example packs (flood/irrigation/vaccination) report their correct frameworks; dispatcher pipes the framework correctly so HBM and cognitive_appraisal flow end-to-end (this was the Phase 6Q-D *biggest unknown* per the plan); the `framework=""` escape hatch constructs cleanly with `_DEFAULT_LABEL_ORDER` + empty `_constructs`; `gemma4:e4b` reachable in 12.26 s. **Vaccination + irrigation no longer silently use PMT label ordering.**
  - **Paper-1b byte-identity preserved**: flood pack returns `"pmt"`, identical to the previous silent default. The behavioral change affects only non-flood domains where the silent default was wrong anyway. PMT / cognitive_appraisal / HBM all share the same VL/L/M/H/VH 5-level label ordering, so even for irrigation runs the label-comparison logic is numerically identical pre/post-6Q-D — only the `_constructs` introspection registry changes (no production code path reads `_constructs` for paper-1b irrigation experiments).
  - **Layer 3 PMT-bias paths NOT addressed in this sub-phase** (`broker/core/unified_context_builder.py:488-495` substring heuristic; `:520-523` `TP_LABEL/CP_LABEL` fallback; `broker/core/agent_initializer.py:140-144` `AgentProfile` typed PMT score fields; `SyntheticLoader.PMT_PARAMS`) — those are independent debt items, deferred to Phase 6Q-D-2 if they don't fall out of the Phase 6Q-F fake-traffic E2E gate.

- **Phase 6Q-C — Memory-strategy `stimulus_key` BLOCKER closed** (2026-05-26). Closes Layer 3 findings #1-3 from the Phase 6P-E follow-up audit. Pre-6Q-C the three low-level surprise-strategy constructors silently defaulted their stimulus key to `"flood_depth"` — `EMASurpriseStrategy(stimulus_key: str = "flood_depth")`, `SymbolicSurpriseStrategy(default_sensor_key: str = "flood_depth")`, `HybridSurpriseStrategy(ema_stimulus_key: str = "flood_depth")`. Silent-failure mode: any non-flood domain instantiating these classes without an explicit kwarg got `world_state.get("flood_depth", 0.0)` → always 0 → zero surprise signal → zero novelty-gated memory writes, with no error and no warning. The Phase 6K-A `UniversalCognitiveEngine` wrapper resolves this correctly via `DomainPack.memory_policy().stimulus_key`; the bug only manifested if a developer instantiated the low-level strategies directly. Fix is to require explicit values at construction time.
  - **`broker/memory/strategies/ema.py:119`** — signature `stimulus_key: str = "flood_depth"` → `stimulus_key: Optional[str] = None`; raises `ValueError` if falsy. Error message names Phase 6Q-C + points readers at YAML `memory.stimulus_key` and `DomainPack.memory_policy().stimulus_key` as the legitimate setting paths.
  - **`broker/memory/strategies/symbolic.py:147`** — signature `default_sensor_key: str = "flood_depth"` → `default_sensor_key: Optional[str] = None`; raises if both `sensors` and `default_sensor_key` are None. Removed the silent `DEFAULT_BINS["flood_depth"]` fallback for unknown keys — an unrecognised key now raises (`SymbolicSurpriseStrategy.default_sensor_key='nonexistent_key' has no preset bins…`).
  - **`broker/memory/strategies/hybrid.py:52`** — signature `ema_stimulus_key: str = "flood_depth"` → `ema_stimulus_key: Optional[str] = None`; raises if both `ema_stimulus_key` and `sensors` are None. Added a "sensors-only" convenience: when only `sensors=` is supplied, the EMA half borrows the first sensor's `path` as its stimulus_key (lets a fully-Sensor-described hybrid construct without a separate kwarg).
  - **`broker/memory/strategies/base.py:28`** — docstring example updated to show explicit `stimulus_key="flood_depth"` instead of relying on the default.
  - **`tests/test_unified_memory.py:287, 299`** — two `HybridSurpriseStrategy` tests that previously relied on the flood-default now pass `ema_stimulus_key="flood_depth"` explicitly. No semantic change (both tests exercise flood mechanics).
  - **NEW `broker/tests/test_memory_strategy_genericity.py`** — 11 regression tests pinning the new explicit-required contract across all three strategies, plus the backward-compat path (`"flood_depth"` legacy preset bin still works) and the new sensors-only Hybrid convenience.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2399 passed / 10 skipped / 0 failed** (+12 vs post-Phase-6Q-B 2387 baseline; the +12 is the new 11 genericity tests + 1 that came back into scope when the new file was collected). Paper-1b byte-identity preserved — the flood YAML configs already set `memory.stimulus_key: "flood_depth_m"` explicitly, so the flood path flows the same value through both pre-6Q-C and post-6Q-C code.
  - **Decision: no new DomainPack hook**. The plan considered adding `DomainPack.memory_stimulus_key()` but `MemoryPolicyBundle.stimulus_key` (returned by the existing `DomainPack.memory_policy()` hook landed in Phase 6K-A) already exposes this declaratively at the engine layer; duplicating at the strategy layer would be redundant. Strategies just require their callers (registry, engine, or test fixture) to pass the resolved value down explicitly.
  - **Round-2 fixes (code-reviewer REQUEST CHANGES applied)**:
    - **`broker/components/memory/registry.py:_unified_factory`** — added an early `stimulus_key is None` guard with YAML-context error message BEFORE delegating to the strategy constructor. Pre-fix a misspelled YAML key surfaced as a deep traceback from `ema.py:134` with no pointer to the config file; now the error names the YAML location and the relevant config key. Constructor-level guards remain as defence-in-depth.
    - **`examples/single_agent/run_flood.py:1120`** — removed the silent `final_mem_cfg.get("stimulus_key", "flood_depth_m")` default-argument fallback. Replaced with an inline `_require_stimulus_key(mem_cfg)` helper that raises if the YAML omits the key. Paper-1b unaffected (flood YAML always supplies `flood_depth_m`); the change closes a latent counterexample to the genericity claim.
    - **`broker/memory/strategies/hybrid.py`** — removed the "sensors-only" convenience that borrowed `sensors[0].path` as `ema_stimulus_key` when not explicitly passed. With multi-sensor inputs of different physical quantities the EMA half would have silently tracked only the first sensor — the convenience was a new semantic invariant (post-6Q-C feature add) hiding inside what was framed as a BLOCKER close. Reverted; the explicit-required contract stays explicit. Regression test renamed from `test_sensors_only_succeeds` → `test_sensors_only_still_raises` to pin the rejection.

- **Phase 6Q-B — Relocate `HazardEventGenerator` to the water namespace; delete the 6P-E hazard-thresholds hook** (2026-05-26). Reverses the Phase 6P-E hook decision based on the follow-up 5-subagent audit: the class had zero non-test production callers (`HazardEventGenerator(...)` instantiations exist only in `tests/test_ma_event_generators.py`; paper-1b flood runs use the separate `FloodEventGenerator` at `broker/domains/water/event_generators/flood.py` relocated in Phase 6K-B). Its payload (`depth_m` / `depth_ft` keys), unit conversion (`m → ft` hardcoded), and upstream `hazard_module.get_flood_event(year)` API are all flood-shaped — decoupling severity thresholds via a Protocol hook would have addressed ~5 % of the flood-coupling surface while leaving the other 95 % intact. Relocating the class is the cleaner architectural call.
  - **`git mv broker/components/events/generators/hazard.py` → `broker/domains/water/event_generators/hazard_per_agent.py`** — preserves blame history via git's rename detection.
  - **Class docstring** rewritten to explain the relocation rationale + the Phase 6P-E hook history.
  - **`broker/components/events/generators/__init__.py`** — removed `hazard` from the package-docstring module list; added a pointer to the relocated `hazard_per_agent` alongside the Phase 6K-B `flood` pointer.
  - **`broker/domains/water/event_generators/__init__.py`** — added `from .hazard_per_agent import HazardEventConfig, HazardEventGenerator`; `__all__` extended.
  - **`tests/test_ma_event_generators.py:8-10`** — import path updated from `broker.components.events.generators.hazard` → `broker.domains.water.event_generators.hazard_per_agent`. All 5 test instantiation sites unchanged (only the import line moves).
  - **`broker/components/events/ma_manager.py`** — docstring example updated from `HazardEventGenerator(...)` → `MyHazardEventGenerator(...)` placeholder (matches the equivalent placeholder in `broker/components/events/manager.py:23` and `broker/components/context/providers.py:386` already established by Phase 6K-B).
  - **DomainPack hook removed across 3 files**:
    - `broker/domains/protocol.py` — `hazard_severity_thresholds()` Protocol method + docstring deleted; replaced with an inline comment block recording the deletion rationale.
    - `broker/domains/default.py` — `DefaultDomainPack.hazard_severity_thresholds()` None-returning default deleted.
    - `examples/governed_flood/adapters/flood_pack.py` — `FloodDomainPack.hazard_severity_thresholds()` override deleted (the four water-depth threshold values now live where their only consumer reads them: `HazardEventConfig.severity_thresholds` `default_factory`, which itself sits in the water namespace post-relocate).
  - **Contract test removed**: `tests/test_domain_pack_contract.py::test_hazard_severity_thresholds_returns_flood_meter_values` (the hook it asserted no longer exists; replaced with an inline tombstone comment).
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2387 passed / 10 skipped / 0 failed** — `-1` vs post-Phase-6Q-A baseline matches the deleted contract test (no other regression). The 6 hazard tests in `test_ma_event_generators.py` still pass via the new import path.
  - **Auto-closes Layer 3 finding #7**: the hazard event payload schema (`depth_m`/`depth_ft` keys) lived in generic broker namespace pre-relocate. Post-relocate the schema correctly lives in the water namespace, so the genericity audit item closes without a separate fix.
  - **Phase 6P-E entry above note**: the Phase 6P-E `hazard_severity_thresholds` hook + its byte-identity contract test were shipped 2026-05-25 and deleted 2026-05-26 (this entry). The "Phase 6P-F when the first non-flood hazard domain arrives" milestone referenced in the 6P-E docstrings is therefore moot — a genuinely-generic future hazard adapter will be designed from scratch rather than retrofitted onto this code.

- **Phase 6P-E — Close the Phase 6P genericity audit's LOW + NIT tail** (2026-05-25). Bundles three small follow-ups so the audit table reaches zero open items.
  - **#6 (LOW) — Hazard severity thresholds exposed via DomainPack hook**: `HazardEventConfig.severity_thresholds` historically carried four water-depth thresholds in metres (`{"critical": 1.2, "severe": 0.6, "moderate": 0.3, "minor": 0.0}`) as a `default_factory` lambda inside generic broker namespace — flood-domain numerics masquerading as a domain-neutral default. Phase 6P-E adds `DomainPack.hazard_severity_thresholds() -> Optional[Dict[str, float]]` (defaults to `None`); `FloodDomainPack` overrides it returning the byte-identical four-value dict. The `HazardEventConfig` default factory is preserved (paper-1b + existing tests rely on it) but the class docstring + field comment now declare the values as flood-domain backward-compat, with the canonical source pointing at the DomainPack hook. Full consumer wiring (generator preferring the hook over the config default) lands in Phase 6P-F when the first non-flood hazard domain arrives — the hook is advisory in 6P-E.
  - **NIT — `broker/core/skill_broker_engine.py:20` docstring**: the validator-pipeline summary referenced the pre-6P-A path `"domain bundle (water/validator_bundles)"`. Updated to `"domain bundle (broker.components.governance.domain_validator_dispatch)"` so a code reader following the docstring's pipeline map lands at the post-6P-A canonical address.
  - **Source-level guard test** (`broker/tests/test_framework_invariants.py::TestNoFloodVocabInGenericEventGenerators`): adds an AST-walker assertion that no string literal in `broker/components/events/generators/{policy,hazard}.py` contains the substring `"flood"` (case-insensitive) outside of docstring positions and outside identifier-style configuration tags. Only *prose* string literals (containing whitespace) are scrutinised — the `HazardEventConfig.domain: str = "flood"` field default is correctly treated as a domain identifier, not vocabulary. This guard pins the Phase 6P-D de-flood-ing so a future edit cannot silently re-introduce flood-flavoured templates.
  - **`broker/components/events/generators/hazard.py:HazardEventConfig`** — docstring + inline comment expanded to record the flood-domain provenance of the `severity_thresholds` defaults and point readers at `FloodDomainPack.hazard_severity_thresholds()` as the canonical declaration. No behaviour change.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2388 passed / 10 skipped / 0 failed** (+2 regression tests vs post-6P-D 2386 baseline — the new flood-vocab guard + the new `test_hazard_severity_thresholds_returns_flood_meter_values` contract test).
  - **Live LLM gate**: 5-check smoke (`scratchpad/phase_6p_e_smoke.py`) — `FloodDomainPack.hazard_severity_thresholds()` returns the expected dict; vaccination / traffic / earthquake packs return `None`; the guard correctly catches a synthetic `"Catastrophic flooding (3.2 ft) with extreme damage."` injection in a 4-line stub module; `skill_broker_engine.py` docstring contains the new canonical address; `gemma4:e4b` reachable in 11.59 s.
  - **Phase 6P genericity audit — final state**: all 6 audit items (1 BLOCKER + 4 WARN + 1 LOW) plus the 6P-A reviewer NIT are now closed **at the contract level** (`bd424f2` 6P-A → `ca84177` 6P-B → `0a3479a` 6P-C → `4255341` 6P-D → 6P-E). 11 regression tests added across the chain. Paper-1b byte-identical preserved across every sub-phase. **One advisory-LOW remains staged for Phase 6P-F** — the new `hazard_severity_thresholds()` hook is contract-level closed (Protocol method + FloodDomainPack override + regression test) but its consumer (the `HazardEventGenerator`) still reads from `HazardEventConfig.severity_thresholds`; the lookup-order flip lands when the first non-flood hazard domain arrives. Phase 6Q owns the broader type-tightening + DomainPack-Protocol-width refactor (the 4-hook 6P batch left the Protocol at ~30 methods — split into per-concern sub-protocols recommended; tracked as a `TODO(6Q)` at the top of `broker/domains/protocol.py`).

- **Phase 6P-D — De-flood vocabulary from generic event generators** (2026-05-25). Closes WARN #4 + #5 from the Phase 6P genericity audit. Two generic generators under `broker/components/events/generators/` were emitting flood-specific text — a leftover from before Phase 6K-B relocated the flood-flavoured generator to `broker/domains/water/event_generators/flood.py`. The water-domain replacement keeps the original "Catastrophic flooding" / "flood protection subsidy" wording for the flood domain; this PR only de-floods the *generic* generators so a non-water domain instantiating them does not receive flood vocabulary.
  - **`broker/components/events/generators/policy.py:_generate_subsidy_message`** — `"flood protection subsidy"` → `"subsidy"` (2 message templates). Callers that want domain-flavoured wording pass an explicit `message=` kwarg to `record_subsidy_change` and bypass the default.
  - **`broker/components/events/generators/hazard.py:_get_description`** — `"Catastrophic flooding (X ft) ..."` → `"Catastrophic hazard event (X ft) ..."` (5 templates). The `ft` unit is kept as a flood-implicit default; the docstring records that earthquakes / wildfires / other non-depth hazards should override this method rather than feed scalar magnitudes through it (deferred to a future `HazardEventConfig.depth_unit` parameter when the next non-flood domain arrives — code-reviewer NIT, low priority).
  - **Paper-1b byte-identical preserved**: only tests call `record_subsidy_change` / `record_premium_change` (confirmed via grep — no `examples/` callsite); paper-1b flood runs reach the water-domain `FloodEventGenerator` (with its own `_get_description` override retaining flood wording), not the generic generator touched here. The auto-message templates only fire when a caller omits `message=` — paper experiments supply explicit messages.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2386 passed / 10 skipped / 0 failed** (net-zero vs post-6P-C baseline). No test asserts on the changed message text (confirmed via `grep -rn "Catastrophic flooding\|flood protection subsidy"` — zero hits outside the 2 changed files and the water-domain replacement).

- **Phase 6P-C — Replace `agent_initializer.py` flood-loader hardcode with `DomainPack.csv_loader_class()` / `synthetic_loader_class()` dispatch** (2026-05-25). Closes WARN #3 from the Phase 6P genericity audit. Pre-6P-C the two private helpers `_resolve_csv_loader_class()` and `_resolve_synthetic_loader_class()` inside `initialize_agents` branched on `if domain_name == "flood":` and imported `FloodCSVLoader` / `FloodSyntheticLoader` from `broker.domains.water.loaders` — every non-flood domain still traversed this lookup at every `mode in {"csv", "synthetic"}` call, paying a cross-namespace import-coupling cost for no behavioural reason. The selector now consults `DomainPack.csv_loader_class()` / `synthetic_loader_class()` via the registry; default packs return `None` and the broker uses the generic `CSVLoader` / `SyntheticLoader`.
  - **`broker/domains/protocol.py`** — added `csv_loader_class()` + `synthetic_loader_class()` Protocol methods (return `Optional[Any]`; concrete type left as `Any` to keep packs from importing `broker.core.agent_initializer`).
  - **`broker/domains/default.py`** — both methods return `None` (no-op default).
  - **`examples/governed_flood/adapters/flood_pack.py`** — overrides returning `FloodCSVLoader` / `FloodSyntheticLoader`. Imports remain in-namespace (`examples/` → `broker.domains.water.loaders`, NOT a generic-broker reverse).
  - **`broker/core/agent_initializer.py:684-694`** — replaced the two hardcoded branches with a one-line `_pack.csv_loader_class() or CSVLoader` lookup. `DomainPackRegistry.get_or_default(domain_name)` runs once before the mode dispatch, so the lookup is performed once per call regardless of mode.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2382 passed / 10 skipped / 0 failed** (net-zero vs post-6P-B baseline).
  - **Live LLM gate**: 4-check smoke (`scratchpad/phase_6p_c_smoke.py`) — `FloodDomainPack.csv_loader_class()` returns `FloodCSVLoader`, `synthetic_loader_class()` returns `FloodSyntheticLoader`; irrigation / vaccination / traffic packs return `None` (generic fallback); source-level guard confirms `agent_initializer.py` no longer contains the legacy `if domain_name == "flood":` branch; `gemma4:e4b` responded in 6.75 s.
  - **Paper-1b reproducibility scope** (code-reviewer #5 clarification): the NW Paper 1b flood single-agent runner (`examples/single_agent/run_flood.py`) uses `initialize_agents_from_survey`, not `broker.core.agent_initializer.initialize_agents`; the multi-agent flood pipeline uses `ma_initializer.py`. Neither paper runner currently reaches the refactored function, so the "byte-identical" guarantee for paper runs is preserved vacuously (the function is not on the paper-1b execution path). Independently, callers that *do* reach the function with `config={"domain": "flood", ...}` continue to receive the same `FloodCSVLoader` / `FloodSyntheticLoader` instances with identical constructor kwargs — the new contract test `test_flood_loaders_accept_canonical_constructor_kwargs` pins that invariant.

- **Phase 6P-B — Replace `phases.py::from_domain` flood hardcode with `DomainPack.phase_layout()` dispatch** (2026-05-25). Closes WARN #2 from the Phase 6P genericity audit. Pre-6P-B the multi-agent phase layout selector branched on `if domain.lower() == "flood":` and imported `water_default_phases` directly from `broker.domains.water.phase_layouts` — a load-time-or-runtime cross-namespace coupling for any non-flood domain that called `from_domain`. The selector now routes through the `DomainPack` registry; domains that need a custom multi-agent phase split override `DomainPack.phase_layout()` and return a `List[PhaseConfig]`, while domains with a single-phase pipeline keep the default `None` (the orchestrator falls back to the generic 3-phase layout).
  - **`broker/domains/protocol.py`** — added `DomainPack.phase_layout()` Protocol method (returns `Optional[List[Any]]`; concrete type left as `Any` to avoid forcing every pack import `broker.interfaces.coordination`). Documented as the replacement for the hardcoded flood branch.
  - **`broker/domains/default.py`** — `DefaultDomainPack.phase_layout()` returns `None` (no-op default). Existing domain packs that do not override automatically inherit the generic-fallback behaviour.
  - **`examples/governed_flood/adapters/flood_pack.py`** — `FloodDomainPack.phase_layout()` returns `water_default_phases()` (the four-phase institutional → household → resolution → observation order). The `water_default_phases` helper still lives at `broker/domains/water/phase_layouts.py` — examples/water-pack importing from there is in-namespace, NOT the cross-namespace coupling that 6P-B closes.
  - **`broker/components/orchestration/phases.py:117`** — `from_domain` rewritten as a `DomainPackRegistry.get_or_default(resolved).phase_layout()` lookup with `_generic_phases()` fallback. `None` continues to resolve to `"flood"` (preserves the documented legacy default) — but only if FloodDomainPack is registered; otherwise it gracefully degrades to the generic layout instead of failing.
  - **`tests/test_phase_orchestrator.py:341,348`** — added `import examples.governed_flood` inside the two tests that assert flood-specific 4-phase output, with comments explaining why the import is now required (pre-6P-B the orchestrator imported water phases directly; 6P-B made the dependency explicit via the registry).
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` → **2382 passed / 10 skipped / 0 failed** (net-zero vs post-Phase-6P-A baseline). The two test imports are the only diff inside `tests/test_phase_orchestrator.py`; all 26 phase-orchestrator tests still pass.
  - **Live LLM gate**: 5-check smoke (`.ai/2026/05/25/phase_6p_b_smoke.py`) — `from_domain("flood")` returns 4 phases via FloodDomainPack registry, `from_domain("vaccination")` + `from_domain("traffic")` return generic 3 phases via DefaultDomainPack fallback, `from_domain(None)` preserves flood-default backward compat through registry lookup, `phase_layout()` returns fresh non-shared lists per call, and `gemma4:e4b` responded in 6.75 s. Paper-1b byte-identical preserved (flood paper experiments call `from_domain("flood")` and continue to receive the same `water_default_phases()` list).

- **Phase 6P-A — Relocate `build_domain_validators` to a generic address; close the BLOCKER runtime cross-namespace coupling in `validate_all`** (2026-05-25). Before this change `broker/validators/governance/__init__.py::validate_all()` did a function-local `from broker.domains.water.validator_bundles import build_domain_validators` — the load-time coupling was already function-local (AST guard in `TestNoReverseDomainImport` accepts it), but the *runtime* path forced every domain's governance dispatch to traverse a water-namespace module. The dispatcher body has been registry-driven and water-agnostic since Phase 6C-v2 (2026-05-10); only its address still lived under `broker.domains.water.`. This sub-phase moves the dispatcher to a generic location and leaves a 3-line backwards-compat shim at the old path.
  - **NEW `broker/components/governance/domain_validator_dispatch.py`** (~110 LOC) — verbatim relocation of the registry-driven `build_domain_validators` from `broker/domains/water/validator_bundles.py`. No logic change; the `if resolved == "flood"` fallback inside `except ImportError` is preserved unchanged (defensive for a `DomainPackRegistry`-import-fail scenario that does not occur in modern broker, but kept to minimise blast radius for this sub-phase).
  - **`broker/domains/water/validator_bundles.py` → 3-line backwards-compat shim** (~20 LOC including docstring). Re-exports `build_domain_validators` from the new canonical address; `canonical is shim` identity verified in the live smoke. `test_validator_shadow_mode.py` + `test_domain_validator_dispatch.py` continue to import from the shim path unchanged, proving backwards compat.
  - **`broker/validators/governance/__init__.py:84`** — function-local import switched to the new generic address; comment block updated to record that the runtime cross-namespace coupling is now closed and that the deferred-import pattern is retained only to keep the module-load surface narrow.
  - **`tests/test_domain_pack_contract.py:552`** — `TestHotPathsUseDomainPack` parametrize entry updated from `broker/domains/water/validator_bundles.py` → `broker/components/governance/domain_validator_dispatch.py` so the "hot-path file must reference `DomainPackRegistry`" guard tracks the new home. The water-side shim does not need to reference `DomainPackRegistry` because it is a pure re-export.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` reports **2381 passed / 10 skipped / 0 failed** (same as post-v0.3.1-B; net-zero regression). `tests/test_domain_validator_dispatch.py::test_water_domain_exposes_validator_builder` passes via the shim, exercising both the new canonical path and the legacy import path.
  - **Live LLM gate**: `gemma4:e4b` 1-shot reachability via the actual `validate_all` dispatch path — flood domain returns 5 validators with 3 builtin checks on `PhysicalValidator`; irrigation returns 5 validators with 8 builtin checks; `None` domain returns 5 empty validators. End-to-end `ollama` round-trip 12.08s, response `'ok'`. Smoke script: `.ai/2026/05/25/phase_6p_a_smoke.log` (in scratchpad).
  - **Why this is BLOCKER-grade not WARN**: any third-party domain (or a future `examples/` domain that does not exist yet) calling `validate_all` would have traversed water-specific code at runtime — a literal `import broker.domains.water.validator_bundles` would fire even when `domain="irrigation"` or `domain="vaccination"`. Phase 6P-A makes the runtime dispatch genuinely water-agnostic. Remaining `validate_all`-adjacent genericity items (`broker/components/orchestration/phases.py:117` `if domain == "flood":` fallback; `broker/core/agent_initializer.py:685,691` flood-loader dispatch; flood-vocab event-text strings in `broker/components/events/generators/`) are tracked as WARN in `.ai/2026/05/25/phase_6p_genericity_audit.md` and will land in subsequent Phase 6P sub-phases.

### Fixed

- **Phase v0.3.1-B — Eliminate the pytest module-rewriting polluter** (2026-05-25). The 6 remaining `pytest broker/ tests/` failures carried from v0.3.1-A all shared the same root cause: `tests/flood/test_module_integration.py` ran `del sys.modules[mod_name]` at *module level* for every cached `broker.*` / `agents.*` entry. With broker installed via `pyproject.toml` the path-manipulation that block was meant to support became dead code AND, because the wipe fired during pytest collection, broke class identity across test files — `isinstance(<old_class_instance>, <new_class>) == False`, enum `is`-equality `== False`, empty `_builtin_checks` registries. Removing the wipe restores deterministic test isolation.
  - **`tests/flood/test_module_integration.py`** — deleted the 19-line `sys.path` rewrite + `del sys.modules` loop. Corrected `MA_DIR` to `CURRENT_DIR.parent.parent / "examples" / "multi_agent" / "flood"` so that `setUp` methods can actually resolve `MA_DIR / "config" / "ma_agent_types.yaml"` (the old definition pointed at `tests/` and never could have resolved that path). Replaced the deleted block with a 7-line comment recording why the wipe was toxic so a future contributor doesn't re-introduce it.
  - **Test gate**: `pytest broker/ tests/ --timeout=300 -p no:cacheprovider` now reports **2381 passed, 10 skipped, 0 failed** (was 2375/10/6). All 6 carryover failures from v0.3.1-A — `test_experiment_builder_policy::test_wraps_engine_in_proxy` + `test_double_wrap_does_not_crash`, `test_social_pipeline_audit::test_ma_window_memory_engine_builds_without_scorer_argument`, `test_domain_pack_contract::test_memory_policy_category_rules_have_flood_keys`, `test_domain_validator_dispatch::test_water_domain_exposes_validator_builder`, `test_governance_rules::test_validate_all_combines_results` — are now green. `tests/flood/test_module_integration.py` itself remains 164 passed / 1 skipped (no regression to its own test surface).
  - **Why this was missed pre-v0.3.1-B**: when `test_module_integration.py` is run in isolation the wipe is harmless (no other modules to invalidate); the bug only manifests in full-suite collection order. Earlier triage attempts (`--import-mode=importlib`, mirrored `broker/tests/conftest.py`, eager `import examples.governed_flood`) all failed because the root cause was a destructive collection-time side effect, not the import system.
  - **No paper-1b byte-identical impact** — single test-only file; no `broker/` production code touched.

### Added

- **Phase v0.3.1-A — NW Paper 1b figure-helper tests realigned with the post-2026-05-25 figure iterations** (2026-05-25). 5 stale assertions in `tests/test_nature_water_figure_helpers.py` updated to match the current state of `paper/nature_water/scripts/gen_fig2_case1_irrigation.py` + `gen_fig3_case2_flood.py` after this week's user-driven figure iterations (panel-order swap, naming unification to "Governed LLM" / "Governed LLM (no validator)", enlarged fonts, demand-ratio colorbar). **Pure test fixes** — no production code touched; paper-1b figure data unchanged.
  - **T1**: `test_flood_fig3_panel_a_order_is_governed_then_rulebased_then_ungoverned` → renamed to `_governed_then_ungoverned_then_rulebased`. The panel-A order swap (Governed LLM | LLM no-validator | Rule-based) landed earlier this week per user request; the assertion now matches.
  - **T2**: `test_irrigation_fig2_bottom_row_uses_two_pie_panels` was calling `get_irrigation_pie_panel_configs()` — a name that was never implemented. Renamed call to the canonical `get_irrigation_panel_configs()`.
  - **T3**: `test_irrigation_center_count_style_matches_fig3_overlay` strict-checked `fontsize == 6.0`. Loosened to `>= 6.0` so future fontsize bumps don't churn the test (today's bump 6.0 → 8.0 per user "enlarge text" feedback).
  - **T4**: `test_irrigation_uses_shared_violation_colorbar` → renamed to `_uses_demand_ratio_colorbar` + label assertion `"Violation rate (%)" → "Demand ratio"`. The script has always shipped "Demand ratio" as the canonical colorbar label.
  - **T5**: `test_irrigation_panel_b_note_clarifies_counts_are_decisions` calls a `get_irrigation_count_note_config()` function that was never implemented. Added a stub in `gen_fig2_case1_irrigation.py` (paper/ is gitignored — change does not enter git history) returning a sensible default; rendering the note on the figure is an optional follow-up.
  - **Test gate**: `pytest tests/test_nature_water_figure_helpers.py` 14/14 pass (was 9 passed + 5 failed). Full `pytest broker/ tests/` baseline drops from 9 failed → **6 failed**, 2375 passed (+3 newly-passing tests vs the previous 2372 baseline).
  - **Remaining 6 failures** (deferred to v0.3.1-B + v0.3.1-C): 3 isinstance/pytest-module-rewriting failures in `test_experiment_builder_policy` + `test_social_pipeline_audit`, plus 3 `test_domain_pack_contract` / `test_domain_validator_dispatch` / `test_governance_rules` failures tied to Phase 6J/6K refactors.

- **Phase 6O-D — CONTRIBUTING + README docs for 3-tier readiness CLI** (2026-05-25). Closing docs commit for Phase 6O. Documents the `broker.tools.readiness_report` CLI shipped in 6O-C-1, the 3-tier profile semantics, exit codes, threshold override mechanism, and the three caveats (small smokes do not cover action diversity; terminal rejections may be valid governance; cross-domain runs may flag legitimately-inapplicable validators as dead). No code change — pure docs.
  - **`CONTRIBUTING.md`** — added "Post-Experiment Readiness Reports" subsection under `## Testing` (~60 LOC). Per-profile bash examples; explicit caveat list; `--profile-yaml` override pointer.
  - **`README.md`** — added "Audit Your Runs" subsection under `## Configuration & Extension` (~20 LOC). Single bash example + 8-category terminal-taxonomy summary + 3-field action-taxonomy summary; links back to CONTRIBUTING for detail.
  - **Round-1 code-reviewer APPROVE with one warning**: W1 README bash `\` line-continuations got munged into spaces during the initial edit; fixed pre-commit (Python-script edit instead of heredoc).
  - **Test gate**: no test change; `pytest broker/ tests/` net-zero regression (same 9-failure baseline as 6O-C-1). Live smoke `python -m broker.tools.readiness_report` on `examples/quickstart/results/` still produces the expected console + JSON output post-doc-update.
  - **Phase 6O closing summary**: 4 sub-phases shipped — 6O-A-1 (terminal taxonomy + ValidatorMetadata TypedDict contract) → 6O-A-2 (validator-side `expected_terminal`+`constraint_type` populate, 8 sites across 6 validators) → 6O-B-1 (action taxonomy + 3 reference DomainPacks, 12 skills) → 6O-C-1 (readiness CLI + 3 profiles + 15 tests). 6O-D closes the docs. **Out of Phase 6O scope (follow-ups)**: 6O-A-3 (`feasible_actions` + `recovery_hint` population — ThinkingValidator needs O(n²) batching); 6O-C-2 (skill orchestration: call `wagf-quickstart` / `abm-reproducibility-checker` / `llm-agent-audit-trace-analyzer` from inside the CLI); production profile (persona alignment first); 6Q (scenario harness — independent plan).

- **Phase 6O-C-1 — Generic readiness reporter CLI + 3 profiles** (2026-05-25). Implements codex P0 partial: domain-agnostic post-experiment audit reads existing `audit_summary.json` + audit CSV + raw JSONL, classifies terminal outcomes via the Phase 6O-A-1 classifier, computes metrics, evaluates against named profile thresholds (`functional` / `behavioral` / `stress`), emits console summary + optional JSON report. **Read-only orchestrator** — zero production-code touch — paper-1b byte-identical guarantee trivially preserved.
  - **NEW `broker/components/validation/`** package — re-exports `ReadinessProfile`, `ReadinessThresholds`, `load_readiness_profile`.
  - **NEW `broker/components/validation/readiness_profile.py`** (~165 LOC) — profile loader. 3 profiles shipped; `production` deferred per user decision (persona undefined, recorded in `.ai/2026/05/25/phase_6o_gap_matrix.md`). YAML override path supported.
  - **NEW `broker/components/validation/readiness_profile.yaml`** — default thresholds for `functional` (approval ≥80%, format-retry ≤30%) / `behavioral` (≥90%, ≤15%, ≥3 distinct skills, ≥2 firing rules) / `stress` (≥95%, ≤10%, terminal ≤20%, max 0 dead validators).
  - **NEW `broker/tools/readiness_report.py`** (~420 LOC) — CLI module + `compute_readiness_report()` public API + `ReadinessMetrics` / `ThresholdCheck` / `ReadinessReport` dataclasses. CSV is primary classification source (flat `status` schema); JSONL contributes `validation_issues` enrichment via `(agent_id, year)` composite key join (list-accumulated, not last-write-wins per round-1 review). Console + JSON output, exit codes 0=pass / 1=threshold-fail / 2=cli-error.
  - **NEW `broker/tests/test_readiness_report.py`** — 15 tests covering profile loader edges, metric extraction (minimal-approved / retries / terminal taxonomy join / validator firing diversity / dead-validator detection), CLI exit codes, custom YAML override, missing inputs.
  - **Live smoke on `examples/quickstart/results/`**: classifies the canonical Year-1-take_action-approved + Year-2-retry-do_nothing-approved sequence as `{'approved': 1, 'retry_recovered': 1}` with `terminal_rate=0.0` and overall `PASS` at functional profile. JSON report written successfully.
  - **Test gate**: `pytest broker/ tests/` net-zero regression — 9 pre-existing failures unchanged, 2372 passed (+15 new readiness tests).
  - **Round-1 code-reviewer REQUEST CHANGES** addressed pre-commit (3 BLOCKERs + 2 warnings):
    - **C1**: `validation_issues_by_key[key] = issues` overwrote duplicate `(agent_id, year)` entries (MA-mid-year-redecision case). Changed to `setdefault(key, []).extend(issues)`.
    - **C2**: `require_no_dead_validators: bool` flagged every legitimately-inapplicable validator as dead in cross-domain runs. Replaced with `max_dead_validators: int` allowing a tunable count > 0 for domain-mismatched audits. Legacy bool still readable via `_profile_from_dict`.
    - **C3**: `parse_success_rate` was actually `approved/total` — a governance-rejection counted as a "parse failure" mislabeling. Renamed to `approval_rate` throughout (dataclass field, YAML key, threshold check, console output). True `parse_success_rate` deferred to 6O-C-2 with terminal-taxonomy-derived definition. Legacy YAML key `min_parse_success_rate` accepted via fallback for one release.
    - **W3**: test fixture for terminal-taxonomy JSONL test lacked `agent_id` + `year` per row → all rows collided on `("","")` join key, masking C1. Added explicit per-row identifiers.
    - **W4**: `required_metrics` parsed from YAML but never enforced. Added per-required-metric `ThresholdCheck` (PASS = metric present and non-empty; FAIL = None/missing).
  - **Out of scope for 6O-C-1**: skill orchestration (call `wagf-quickstart` / `abm-reproducibility-checker` / `llm-agent-audit-trace-analyzer` from inside the CLI — deferred to 6O-C-2); true `parse_success_rate` derived from terminal-taxonomy `parser_failure` count; `production` profile.

- **Phase 6O-B-1 — Action taxonomy for generic action-coverage analysis** (2026-05-25). Implements codex P4 of the Phase 6O plan. Lets every `DomainPack` declare per-skill structural metadata (`category` / `intensity` / `reversibility`) so the generic readiness reporter (Phase 6O-C) can compute action-coverage / category-coverage / intensity-coverage metrics without knowing skill names. Three reference DomainPacks (Irrigation / Flood / Vaccination) ship the YAML extensions + implementations in this commit. All changes are additive — paper-1b byte-identical guarantee preserved (verified by quickstart governance smoke + 9-failure baseline unchanged).
  - **NEW `broker/interfaces/action_taxonomy.py`** — `ActionTaxonomyEntry` frozen dataclass (3 optional fields) + `load_action_taxonomy_from_skill_registry(yaml_path)` helper. Loader is robust to missing file / malformed YAML / missing fields / non-string values (each case returns sensible defaults rather than raising).
  - **`broker/domains/protocol.py`** — added `action_taxonomy() -> Dict[str, ActionTaxonomyEntry]` method to the Protocol contract. Forward-ref string annotation avoids circular-import at module level. Method docstring documents that domain packs may either return a hardcoded mapping or read from YAML via the new helper.
  - **`broker/domains/default.py`** — `DefaultDomainPack.action_taxonomy()` returns empty dict (opt-out default). Domains that don't declare taxonomy get reported under `unknown` category by the readiness layer in 6O-C.
  - **Irrigation** (5 skills): `examples/irrigation_abm/config/skill_registry.yaml` extended with `category` / `intensity` / `reversibility` per skill (increase_large → increase/large/annual; maintain_demand → maintain/none/annual; etc.). `IrrigationDomainPack.action_taxonomy()` reads from the YAML via the new helper.
  - **Flood** (4 skills): `examples/single_agent/skill_registry.yaml` extended (buy_insurance → adopt/small/annual; elevate_house + relocate → adopt/large/permanent; do_nothing → status_quo/none/instant). `FloodDomainPack.action_taxonomy()` reads from the same single_agent YAML (single_agent and governed_flood share the skill set; canonical declaration lives at single_agent).
  - **Vaccination** (3 skills): `examples/vaccination_demo/config/skill_registry.yaml` extended (get_vaccinated → adopt/large/annual; delay → delay/none/instant; refuse → refuse/none/instant). `VaccinationDomainPack.action_taxonomy()` reads from the demo YAML.
  - **NEW `broker/tests/test_action_taxonomy.py`** — 13 tests covering: dataclass shape (all 3 fields optional, frozen); YAML loader robustness (missing file → empty, malformed YAML → empty, missing `skills:` block → empty, malformed entries silently dropped, non-string fields normalised to `None`); DefaultDomainPack returns empty; 3 reference DomainPacks return exactly the expected taxonomy for all their skills.
  - **Test gate**: `pytest broker/ tests/` net-zero regression — 9 pre-existing failures unchanged, 2357 passed (+13 for the new tests). Initial implementation included a parametrised `test_all_reference_packs_return_well_typed_entries` that used `__import__("...module...", fromlist=[...])` to load each DomainPack lazily; this caused an `isinstance` test-isolation failure in full-suite mode because pytest's module rewriting created a distinct class identity from `__import__`. Removed in pre-commit cleanup; the 3 explicit per-DomainPack tests cover the same surface without the late-binding hazard. Quickstart governance smoke (`examples/quickstart/02_governance.py`) replay clean.
  - **Out of scope for 6O-B-1**: scenario harness (codex P3, deferred to Phase 6Q standalone plan); readiness CLI orchestrator (6O-C); CONTRIBUTING.md 3-tier smoke docs (6O-D).

- **Phase 6O-A-2 — Validator-side population of `expected_terminal` + `constraint_type` metadata keys** (2026-05-25). Follows Phase 6O-A-1 (commit `c3a9f3a`) by populating 2 of the 4 ValidatorMetadata contract keys at every metadata-write site across the 6 generic validators, so the terminal-outcome classifier (`broker.components.analytics.terminal_taxonomy`) now produces real classifications on production audit data rather than `unknown_terminal` defaults. The other 2 keys (`feasible_actions`, `recovery_hint`) deferred to 6O-A-3 because ThinkingValidator's `feasible_actions` requires O(n²) re-evaluation per candidate skill and PersonalValidator's requires domain cost-model scanning (verified by Explore-audit pre-flight 2026-05-25). Paper-1b byte-identical guarantee preserved: subagent SAFE-TO-PROCEED audit on 5 risks (audit CSV/JSONL never iterates metadata keys; no dict-equality on ValidationResult; shadow-mode deep-copy preserves new keys without serialising them; quickstart governance smoke run on patched code shows 0 leak of new keys into CSV/JSONL).
  - **`broker/validators/governance/base_validator.py`** (+30 LOC): two class constants `_DEFAULT_EXPECTED_TERMINAL: bool = False` + `_DEFAULT_CONSTRAINT_TYPE: str = "soft"` + helper `_recovery_keys(rule)` method that returns the 2 keys; subclasses override constants OR the method itself. The YAML-rule metadata dict (line ~185) merges `**self._recovery_keys(rule)` to keep a single source of truth.
  - **PhysicalValidator** + **PersonalValidator** (+4 LOC each): class-constant override — both `hard` / `terminal=True` (state preconditions and financial affordability are hard impossibilities the model cannot recover from).
  - **SemanticGroundingValidator** (+4 LOC): class-constant override — `diagnostic` / `terminal=False` (grounding checks never block; model can rephrase).
  - **ThinkingValidator** + **SocialValidator** (+9 / +6 LOC): proper `_recovery_keys()` overrides (NOT inline writes — reviewer round-1 caught the silent-drift trap where inline writes would diverge from overrides if a future subclass replaced `_recovery_keys()`). ThinkingValidator's override derives `constraint_type` from `rule.level` (WARNING → `diagnostic`, ERROR → `soft`); never terminal (model can re-reason). SocialValidator's override always returns `soft` / `terminal=False` (social rules are WARNING-only).
  - **AgentValidator** (+46 LOC, 8 sites): not a BaseValidator subclass — each metadata-write hardcodes the 2 keys with per-Tier semantics:
    - Tier 0 (format) → `hard` / `terminal=True` (schema breach is unrecoverable)
    - Tier 1 (affordability) → `hard` / `terminal=True` (cannot-afford is hard)
    - Tier 2 (valid_decisions / min / max / delta) → ERROR=`hard`+terminal=True; WARNING=`diagnostic`+terminal=False (level-conditional via `lv == ValidationLevel.ERROR`)
    - Tier 3 (identity) → same level-conditional pattern as Tier 2
    - Tier 3 (thinking) → ALWAYS terminal=False (model can re-reason); ERROR=`soft`, WARNING=`diagnostic`
  - **Test gate**: `pytest broker/ tests/` net-zero regression — 9 pre-existing failures unchanged, 2344 passed (same as 6O-A-1 baseline, no new tests in this sub-phase). Governance smoke (`examples/quickstart/02_governance.py`) replay: Year-1 take_action APPROVED → Year-2 protected validator blocks → retry → do_nothing APPROVED (canonical governance flow). Post-smoke CSV: 60 columns, zero leak of `expected_terminal` / `constraint_type` / `feasible_actions`. JSONL: 31 trace keys, zero leak. Validator new keys live only in runtime `ValidationResult.metadata` dict; never reach disk.
  - **Subagent round-1 REQUEST CHANGES** addressed: (F-1) class-level docstrings repositioned ABOVE the new class constants in Physical/Personal/Semantic per PEP 257; (C) ThinkingValidator + SocialValidator refactored from inline metadata-write to proper `_recovery_keys()` override eliminating drift trap; (B) `rule` parameter in base `_recovery_keys` annotated with `# noqa: ARG002` and docstring expanded to document the call-site dict-merge contract.
  - **Out of scope for 6O-A-2**: `feasible_actions` + `recovery_hint` keys; validator-side population of those lands in Phase 6O-A-3 (or merges into 6O-B's Action Taxonomy YAML extension).

- **Phase 6O-A-1 — Terminal-outcome taxonomy + ValidatorMetadata TypedDict contract** (2026-05-25). Adds the **data-layer foundation** for the larger Phase 6O generic-readiness work: a stable contract for the optional metadata keys that validators may attach to `ValidationResult.metadata`, plus a domain-agnostic classifier that maps an audit trace row to one of 8 terminal-outcome categories. **Zero broker runtime change** — the new modules are imported only by the new test file in this commit; no existing experiment path references them. Paper-1b byte-identical guarantee preserved trivially. (Sub-agent audit recorded at `.ai/2026/05/25/phase_6o_gap_matrix.md` + the 6-risk SAFE-TO-PROCEED report from the 2026-05-25 Explore round.)
  - **NEW `broker/interfaces/validation_metadata.py`** — `ValidatorMetadata(TypedDict, total=False)` documents the contract: 3 existing keys already populated by current validators (`rule_id` / `category` / `level` — Phase 6N-D-1 era) plus 4 new optional keys for Phase 6O-A-2 validator-side population (`feasible_actions: List[str]` / `recovery_hint: str` / `expected_terminal: bool` / `constraint_type: "hard"|"soft"|"diagnostic"`). Type aliases `SeverityLevel`, `ValidatorCategory`, `ConstraintType` exported as `Literal` constants for type-narrow consumer code.
  - **NEW `broker/components/analytics/terminal_taxonomy.py`** — `classify_terminal(trace_dict) -> TerminalCategory` pure function over the 8 categories: `approved` / `retry_recovered` / `expected_hard_block` / `recoverable_retry_failed` / `no_feasible_action` / `parser_failure` / `execution_failure` / `unknown_terminal`. Reads existing audit columns + `validation_issues[].metadata`; degrades gracefully when called on CSV-only rows that lack the JSONL `validation_issues` field (returns `unknown_terminal` for contested rejections rather than misclassifying). Decision-rule precedence documented in the module docstring. Tolerant int coercion (`_as_int`) handles CSV's string-typed numeric columns.
  - **NEW `broker/tests/test_terminal_taxonomy.py`** — 29 tests covering: each of the 8 categories with synthetic fixtures + edge cases (string `retry_count`, malformed `validation_issues` list, `None` status, lowercase status canonicalisation, format-retries-with-APPROVED disambiguation, hard-block-dominates-recoverable precedence). Plus a local domain-genericity assertion that greps the module source for 10 forbidden domain tokens (flood / irrigation / vaccination / PMT / HBM / WSA / ACA / NFIP / FEMA / Mead / Powell) — fails fast if a future maintainer accidentally hard-codes a domain literal.
  - **Out-of-scope for 6O-A-1, deferred to 6O-A-2**: validator-side population of `feasible_actions` / `recovery_hint` / `expected_terminal` / `constraint_type`. Each domain pack's validators will populate these keys in a subsequent commit; the contract is stable but the production data path still emits `unknown_terminal` for real rejections until then. Codex's 7-part Phase 6O plan (P0-P6) is being executed against the audited gap matrix at `.ai/2026/05/25/phase_6o_gap_matrix.md` — true new scope is ~5 days (not the ~10 days codex implied) because 50–70% of P0/P1/P2/P5/P6 was already covered by `validate_prompt` + `audit_summary.json` + `abm-reproducibility-checker` + `llm-agent-audit-trace-analyzer` + `wagf-quickstart` skill.
  - **Test gate**: `pytest broker/tests/test_terminal_taxonomy.py` — 29/29 pass. Full `pytest broker/ tests/` net-zero regression vs Phase 6N-F-7 baseline (9 pre-existing failures unchanged; total passing 2344 = 2315 + 29 new). No production module imports the new files (`grep -rn validation_metadata\\|terminal_taxonomy broker/ examples/ --include='*.py'` returns only the new test file + docstring cross-references). Paper-1b reference data on disk untouched.
  - **Subagent SAFE-TO-PROCEED verification** (Explore round, 2026-05-25): 6-risk audit passed per `.ai/2026/05/25/phase_6o_gap_matrix.md`: (R1) audit CSV/JSONL never iterates `metadata.items()`/`keys()` so new keys add nothing to output; (R2) no `ValidationResult` dict-equality or hash use in broker/; (R3) JSONL writes extracted fields, never the full metadata dict; (R4) paper analysis uses `json.loads()` + `.get()` accessors and never reads metadata; (R5) all `result.metadata.get(...)` in retry_loop / skill_broker_engine use defensive `.get(key, default)` and never key off the new fields; (R6) no test asserts `set(metadata.keys()) == ...` exact-shape equality.

- **Phase 6N-F-6 — repo-tracked secret-scan pre-commit hook** (2026-05-24). Installs `.githooks/pre-commit` (stdlib-only Python; zero new deps) and `.githooks/README.md`, with a one-line install pointer added to `CONTRIBUTING.md` ("Enable the repo-tracked pre-commit hook"). Activated per clone via `git config core.hooksPath .githooks`. Scans the **staged diff content** of every commit for hardcoded credential patterns and blocks the commit when a match is found.
  - **Patterns (all BLOCK)**: Zotero API key (`ZOTERO_API_KEY = "<20-24 alnum>"`), OpenAI (`sk-...`), Anthropic (`sk-ant-...`), GitHub PAT (`ghp_...`), GitHub OAuth (`gho_...`), AWS access key (`AKIA[A-Z0-9]{16}`), generic credential (`(api_key|secret|password|token|access_key) = "<20+ alnum>"`).
  - **False-positive controls**: `_LINE_EXCEPTIONS` skips lines containing `os.environ`, `os.getenv`, `process.env.`, `<your-`, `REDACTED`, `EXAMPLE_KEY`, `your-api-key`; `_SKIP_PATH_PATTERNS` skips `.githooks/` itself, `CHANGELOG.md` (historical incident notes), and `tests/*fixture*` paths. The generic pattern excludes env-var lookups so a clean `KEY = os.environ.get(...)` line passes.
  - **Smoke verified**: a staged `ZOTERO_API_KEY = "FAKEFAKE1234abcd5678EFGH"` line gets caught with the exact rule ID "Zotero API key (literal hex)"; a clean `os.environ.get(...)` line commits through.
  - **Why**: a Zotero API key was committed across 8 commits between 2026-02 and 2026-05 (rotation tracked separately in the `8c6e48c` commit body). This hook is the canonical preventive control. Bypass remains available via `git commit --no-verify` (left visible to PR review).
  - **Scope**: this is a fast first-line-of-defence, not a full repo-history scanner; CI-side gitleaks / detect-secrets remains the canonical second line.

- **DomainPack v2 contract** (Item 2): three hooks added to the
  `DomainPack` Protocol — `perception_descriptors()`,
  `perception_field_policy()`, `retrieval_policy()` — each with a no-op
  default in `DefaultDomainPack`. `FloodDomainPack` / `IrrigationDomainPack`
  / `VaccinationDomainPack` now subclass `DefaultDomainPack`, so future
  protocol additions auto-default instead of breaking `isinstance`.
- **Config-driven skill retrieval** (Item 3):
  `AgentTypeConfig.get_retrieval_config()` resolves `top_n` / `min_score`
  from `global_config.governance.retrieval` YAML and
  `DomainPack.retrieval_policy()`; framework defaults unchanged
  (top_n=3, min_score=0.05).
- **Build-time `default_skill` enforcement** (Item 3):
  `SkillRegistry.has_explicit_default_skill()`; `ExperimentBuilder.build()`
  now fails fast — before any LLM call — when a domain never declared a
  `default_skill:` (INVARIANTS.md §I5 rule 4).
- **Domain-definable reflection questions** (Item 4):
  `AgentTypeConfig.get_reflection_questions(agent_type)` resolves questions
  from per-agent-type or domain-wide `agent_types.yaml`, or
  `DomainPack.reflection_questions()` (previously a never-called hook).

### Changed

- **Calibration package relocated** (Item 1): the flood-PMT C&V package
  moved `broker/validators/calibration/` → `broker/domains/water/calibration/`,
  out of generic broker code. Pure import-path rename; all importers
  repointed.
- `REFLECTION_QUESTIONS` (the flood-agent-type dict in
  `broker/components/cognitive/reflection.py`) replaced by a domain-neutral
  `_DEFAULT_REFLECTION_QUESTIONS` generic fallback and removed from the
  `broker.components.cognitive` public export;
  `generate_personalized_reflection_prompt()` gains a `reflection_questions`
  parameter.
- **Perception filter de-flooded** (Item 5): `FLOOD_DEPTH_DESCRIPTORS`
  and the flood field-lists moved out of generic broker code to
  `examples/governed_flood/adapters/flood_perception.py`.
  `HouseholdPerceptionFilter` is domain-neutral by default (strips /
  verbalizes nothing); `PerceptionFilterRegistry` injects the active
  DomainPack's `perception_descriptors()` / `perception_field_policy()`.
  `interfaces/perception.py` is now flood-free and off the I5 allowlist.
- **Verbalization fully generic** (Item 5b): the filter's `filter()`
  body is now a single `{input_context_field: DescriptorMapping}`
  lookup loop with zero domain knowledge — it maps numbers to words,
  never computes. A model builder verbalizes any domain's numbers
  (signed changes via negative ranges; same-context ratios via
  `DescriptorMapping.denominator_field`) purely by declaring
  `perception_descriptors()` — no broker or filter edits.
- **Perception filter assignment generic** (Item 5c): new
  `DomainPack.passthrough_agent_types()` hook — the model builder
  declares which agent types perceive raw numbers vs verbalized text.
  The two flood-named pass-through filters collapse into one generic
  `PassThroughPerceptionFilter`; `PerceptionFilterRegistry` hardcodes
  no agent-type names. Default: every agent type verbalizes.
- **Audit tool relocated** (Item 5d): the irrigation-bound
  `appraisal_grounding_audit` post-hoc CLI moved from `broker/tools/`
  to `broker/domains/water/tools/` — out of generic broker code. Zero
  production importers; pure relocation.
- **Affordability validation de-flooded** (Item 6): new
  `DomainPack.affordability_constraints()` hook —
  `AgentValidator.validate_affordability()` no longer hardcodes the
  flood elevation cost model ($150k / 3x income / 50% subsidy); a
  domain declares its own per-decision cost models, or none.
  `agent_validator.py` is now domain-token-free.
- **Post-hoc validators de-flooded** (Item 8): `thinking_rule_posthoc.py`
  V1/V2 (hardcoded `relocated`/`elevated` columns) collapse into a
  generic per-column transition rule; `unified_rh.py` flood defaults
  (`irreversible_states` / `exit_state_col`) removed — the values come
  from the caller (the water-domain `CVRunner`). Both files de-flooded;
  +7 unit tests (previously zero).
- **reflection.py de-flooded** (Item 9): the last generic-broker file
  carrying flood coupling. The status-text / importance / batch-traits
  fallbacks are removed — a new `DomainPack.reflection_trait_labels()`
  hook plus the existing `reflection_status_text` / `compute_importance`
  hooks cover them; `extract_agent_context` is domain-neutral (flood
  data routes through `custom_traits`); the `AgentReflectionContext`
  flood fields are removed. Shipped as an 8-layer stack. `reflection.py`
  removed from the I5 allowlist.
- **FinancialCostProvider dedup + de-flood** (Item 7): the provider
  existed in two copies — a flood-coupled generic copy in
  `broker/components/context/providers.py` and a code-identical
  water-domain copy. The generic copy is deleted; the water copy is
  canonical. `tiered.py`'s default context builder no longer
  instantiates it; MA flood — the only consumer — wires it via
  `extend_providers`. `providers.py` removed from the I5 allowlist.
- **Phase 6H (Items 1-9) complete** — `broker/` is de-flood-coupled
  across every Phase 6H surface; the I5 KNOWN-DEBT(6H) block is empty.
- **Phase 6I — I5 allowlist debt closed**. 6I-A reworded 6 doc-only
  flood examples (docstrings / comments) to domain-neutral wording.
  6I-B..F de-flooded the last 5 real-code allowlist entries:
  - **6I-B** `core/agent_initializer.py` — the position enricher's
    hardcoded `flood_zone`/`flood_depth` profile-write is replaced by a
    generic `enricher.profile_field_map` ({position_attr: profile_attr})
    loop; a domain enricher declares the mapping.
  - **6I-C** `components/analytics/interaction.py` — `InteractionHub`
    no longer hardcodes flood skill labels or `elevated`/`relocated`/
    insurance neighbour checks. `action_labels` and
    `visible_action_specs` are caller-supplied; the flood values move to
    `broker/domains/water/interaction_specs.py` and the flood example
    runners pass them.
  - **6I-D** `components/analytics/observable.py` — `create_flood_observables()`
    relocated to `broker/domains/water/observables.py`; re-exports
    dropped from `observable.py`, `analytics/__init__.py`,
    `components/__init__.py`.
  - **6I-E** `components/events/generators/impact.py` —
    `ImpactEventGenerator` generalised: the mitigation attribute name,
    the freeboard reduction, and the damage/payout event-type labels
    are `ImpactEventConfig` fields (defaults domain-neutral). A flood
    caller supplies the flood values.
  - **6I-F** `core/unified_context_builder.py` — `MemoryContext.core`
    extraction no longer hardcodes a flood key list; it carries every
    primitive personal attribute.
  All 5 entries removed from the I5 `_ALLOWLIST_PATTERNS`; the allowlist
  now holds only docstring/comment false positives. Full `broker/ tests/`
  gate: net-zero regression (3 pre-existing failures, all in
  `test_nature_water_figure_helpers.py`, unrelated; verified by
  isolating the figure-script working-tree edits).
- **Phase 6J-A — soft-default-to-PMT eliminated** (guard hardening for
  genericity couplings the 7-token I5 scan cannot see):
  - `interfaces/rating_scales.py` — `FrameworkType.GENERIC` was a literal
    alias to the flood PMT `RatingScale` object; it is now a standalone
    domain-neutral 5-level Likert scale. `RatingScaleRegistry.get()` /
    `get_by_name()` fall back to GENERIC (not PMT) for an unknown
    framework.
  - `interfaces/context_types.py` — `UniversalContext.framework` defaults
    to GENERIC (was PMT), and `from_dict()` deserialises a missing
    framework key to GENERIC.
  - `core/unified_context_builder.py` — `_get_framework_for_type` no
    longer silently infers a framework from the agent-type name without
    notice: the deprecated name-substring heuristic now emits a one-time
    warning and explicit `psychological_framework:` declaration is
    expected. `governed_flood` / `single_agent` `household` types now
    declare `psychological_framework: pmt` explicitly.
  - New `TestNoSilentDomainDefault` — a behavioural I5 guard (a silent
    fallback cannot be grepped). Net-zero gate regression.
- **Phase 6J-B — `ma_manager.py` event dispatch de-flooded**:
  - `_sync_event_to_env` — removed the dead `try/except ImportError`
    block whose `except` branch held a hardcoded flood event-type
    if/elif chain. The guarded import (`broker.domains.registry`) is an
    internal broker import that cannot raise ImportError, so the
    fallback was unreachable. The import moved to module top.
  - `get_agent_impact` — replaced a hardcoded flood event-type chain
    (`flood`/`flood_damage`/`insurance_payout`) with dispatch through a
    new `DomainPack.agent_impact_handlers()` hook. Handlers aggregate
    (max for depth, sum for dollar amounts) into a per-agent impact
    dict; generic code starts empty, `FloodDomainPack` supplies the
    three handlers. Aggregation is byte-identical to the old chain;
    the method now returns `{}` (not a 5-key pre-seeded dict) when no
    domain/event matches — `MAEventManager` has no production-lifecycle
    caller, so no caller is affected.
  - New Protocol method `DomainPack.agent_impact_handlers()` +
    `DefaultDomainPack` no-op (`{}`). The `EventHandler` type alias
    docstring now distinguishes its global-env vs per-agent-impact
    dispatch surfaces.
  - I5 `_DOMAIN_TOKENS` gains `flooded` + `flood_damage` (now clean
    across generic `broker/`). `flood_occurred` / `flood_event` /
    `flood_depth_m` still leak outside `ma_manager.py` → deferred to
    Phase 6J-E. Net-zero gate regression.
- **Phase 6J-C — domain-bias defaults → fail-fast or domain-housed**:
  eight sites where generic `broker/` silently inherited flood defaults.
  - Fail-fast (an unconfigured domain now raises a clear error):
    `SkillRegistry._default_skill` `"do_nothing"` → `None`,
    `get_default_skill()` raises `ValueError` (the build-time
    `has_explicit_default_skill()` check fires first, so configured
    domains never hit it); `unified_adapter.py` parse-failure fallback
    raises if `parsing.default_skill` is absent; `agent_initializer.py`
    requires `SurveyLoader.domain` / `initialize_agents config["domain"]`
    (were default `"flood"`); `create_default_registry()` raises
    `RuntimeError` and `TypeValidator` requires an explicit registry;
    `PriorityResolution.type_priorities` defaults to `{}` (was a flood
    agent-type priority table).
  - Domain-housed (flood content relocated under `broker/domains/water/`):
    new `agent_type_defaults.py` (`create_water_agent_type_registry()`),
    `phase_layouts.py` (`water_default_phases()` — `PhaseOrchestrator`
    now defaults to the generic 3-phase layout), `social_specs.py`
    (`register_water_social_specs()` — `AGENT_SOCIAL_SPECS` starts
    empty). `interfaces/artifacts.py` `_ensure_default_routing()`
    removed; the three flood artifact mappings register from the flood
    example at import.
  - The four reference domains already declare `default_skill` /
    `parsing.default_skill` in YAML. Net-zero gate regression;
    real-model `governed_flood` smoke ran end-to-end clean.
- **Phase 6J-D — `keyword_classifier` defaults + reverse-import fix**:
  - `TA_KEYWORDS` / `CA_KEYWORDS` flood-PMT dictionaries relocated
    from generic `broker/validators/posthoc/keyword_classifier.py` to
    new `broker/domains/water/posthoc_keywords.py`. The generic
    `KeywordClassifier` no longer falls back to flood defaults —
    `None` is now a legitimate Tier-1/1.5-only (domain-agnostic) mode;
    Tier 2 keyword matching runs only when a caller supplies its own
    dictionaries. Water-domain callers (`micro_validator.py`,
    `cv_runner.py`) construct the classifier with the relocated dicts
    explicitly.
  - `broker/domains/water/validator_bundles.py` reverse-import fix:
    removed `_ensure_irrigation_registered` / `_ensure_flood_registered`
    — the lazy fallback that did `import examples.irrigation_abm.validators`
    / `import examples.governed_flood.validators` when the registry was
    empty. `broker/domains/water/` must not import from `examples/`.
    Replacement: each example package's `__init__.py` now imports its
    `.validators` submodule on package import (own try/except guard);
    the two flood entrypoints that did not previously pre-import their
    example package (`governed_flood/run_experiment.py`,
    `single_agent/run_flood.py`) add a top-level
    `import examples.governed_flood`. The irrigation entrypoint
    already pre-imported its validators; MA flood uses bespoke
    validators and does not call `build_domain_validators`.
  - `test_domain_validator_dispatch.py::test_water_domain_exposes_validator_builder`
    hardened: previously asserted only `len(...) == 5`, which would
    pass vacuously after the lazy-fallback removal (`_empty_validators()`
    also returns 5 wrappers); now imports both example packages
    explicitly and asserts the populated `PhysicalValidator` carries
    non-empty `_builtin_checks` (and the generic one does not).
  - Net-zero gate regression. Real-model `governed_flood` smoke ran
    end-to-end clean with 70 governance rule violations fired —
    confirming flood builtin checks register via the new
    package-import path.
- **Phase 6J-E — finalise the I5 guard + record Phase 6J in INVARIANTS**:
  - `broker/tests/test_framework_invariants.py::TestDomainGenericity`
    `_DOMAIN_TOKENS` widened from 9 → 21. The three tokens deferred
    from 6J-B (`flood_occurred` / `flood_event` / `flood_depth_m`) plus
    nine flood / drought / irrigation infrastructure + skill
    identifiers (`NFIP` / `FEMA` / `PRB` / `SFHA` / `CRSS` /
    `shortage_tier` / `drought_index` / `buyout` / `buyout_program`).
    Seven of those were verified clean across generic `broker/`;
    NFIP / FEMA surface only in docstring "Literature:" references
    (allowlisted as FP). The 6J-B-deferred trio each had real leak
    sites in the memory subsystem + the flood-specific hazard
    generator (`events/generators/flood.py`, `memory/initial_loader.py`,
    `memory/policy_classifier.py`, `memory/universal.py`) —
    allowlisted as `TECH-DEBT(6K)` for the next domain-plugin pass.
    `simulation_protocols.py` docstring example de-flooded inline.
    Deferred token tail (documented inline): `threat_appraisal` /
    `coping_appraisal` and the skill-name set (`elevate_house` /
    `buy_insurance` / `relocate` / `maintain_demand`) — too noisy
    without a separate PMT-schema relocation phase. `do_nothing`
    explicitly evaluated and rejected.
  - Deferred doc/code nits from the 6J-A and 6J-C reviewer rounds
    applied: dead `if fallback_skill and` guard removed from
    `skill_broker_engine.py` (6J-C made it unreachable);
    `PhaseOrchestrator.__init__` Args docstring updated to describe
    the new generic 3-phase default; `SkillRegistry.get_default_skill()`
    gains an explicit `Raises:` clause.
  - `broker/INVARIANTS.md` §I5 "Known current state" rewritten —
    removed the three stale "Deferred to v22" entries (all closed by
    Phase 6H DomainPack v2 work, verified) and the
    `validator_bundles.py` reverse-import entry (closed by 6J-D);
    added a Phase 6J A/B/C/D/E summary and called out the
    PMT / skill-name token tail deferred to a future phase.
  - Net-zero gate regression. `TestDomainGenericity` 21/21 green
    (was 9/9 pre-6J-E). No real-model smoke needed — the only
    broker-pipeline change is the proven-dead guard cleanup.
- **Phase 6K — inner-layer domain coupling teardown** (the work that
  6J's outer-boundary cleanup explicitly deferred). After 6K closes,
  a new domain (HBM cognitive, utility-maximisation,
  information-cascade) can register its own DomainPack, its own
  thinking checks via `register_thinking_checks(framework, [...])`,
  and its own `memory_policy()` bundle — and run through the broker
  pipeline without touching anything under `broker/`. Five
  sub-phases:
  - **Phase 6K-A — memory subsystem → `DomainPack.memory_policy()`
    bundle**: a single new hook supplies category_rules,
    external_event_whitelist, stimulus_key, and default_content_type.
    `policy_classifier._DEFAULT_RULES` no longer carries the 5
    flood/insurance category keys (relocated to
    `FloodDomainPack.memory_policy()`); `initial_loader.py` no
    longer hardcodes the `("flood_experience", "flood_event",
    "damage")` whitelist; `universal.py` raises `ValueError` instead
    of silently falling back to `stimulus_key="flood_depth_m"`.
    `PolicyFilteredMemoryEngine` gains a `domain=` kwarg so runtime
    writes see the bundle. Three `TECH-DEBT(6K)` I5 allowlist
    entries closed.
  - **Phase 6K-B — `events/generators/flood.py` relocation**: the
    whole 205-line flood hazard generator moved from generic
    `broker/components/events/generators/flood.py` to
    `broker/domains/water/event_generators/flood.py` (R100 verbatim
    rename). Sibling generators (`hazard.py` / `impact.py` /
    `policy.py`) stay generic. Docstring examples in
    `providers.py` / `manager.py` genericized to
    `MyHazardEventGenerator` placeholders. Fourth and final
    `TECH-DEBT(6K)` entry closed; all four 6K allowlist debts cleared.
  - **Phase 6K-C — `ThinkingValidator` rules → per-framework
    registry**: the 7 hardcoded PMT / Utility / Financial rule
    bodies (`_validate_pmt` / `_validate_utility` /
    `_validate_financial` instance methods + their three wrapper
    methods, ~165 LOC) relocated to
    `broker/domains/water/thinking_checks.py` as free functions.
    New `_THINKING_CHECKS_BY_FRAMEWORK` registry + public
    `register_thinking_checks(framework, checks)` function;
    `_default_builtin_checks()` returns ALL registered checks across
    frameworks (each check short-circuits internally on
    `context["framework"]`). Module-level `normalize_label` +
    `has_rule_for` helpers extracted; instance methods become thin
    backward-compat wrappers. `validate()` injects `framework` +
    `_extreme_actions` into context before dispatching. Naturally
    addresses audit-B P1 items 1-3 (hardcoded PMT label triples,
    `"do_nothing"` / `"maintain_policy"` / `"expand_coverage"`
    skill literals, utility label thresholds — all migrated with
    the rules).
  - **Phase 6K-D — residual NFIP/FEMA docstring cleanup**: the
    planned `BUYOUT_OFFER_FRACTION` / `premium_escalation_pct`
    migration (audit-B P1 item 11) was found to already be complete
    — Phase 6H Item 7 had relocated those constants when it moved
    `FinancialCostProvider` out of generic broker. Pivoted to
    tightening the residual `Literature: NFIP regulations, FEMA HMGP
    rules` docstring on `agents/base.py::Constraint` and the
    `Literature: DYNAMO model ... NFIP actuarial premium structure`
    docstring on `providers.py::InsurancePremiumProvider`. Both
    classes are genuinely generic (Constraint takes arbitrary
    name/param/bounds; InsurancePremiumProvider takes a
    domain-supplied `premium_calculator` callable). Both files are
    now NFIP/FEMA-token-free; the two 6J-E FP allowlist entries
    dropped. NFIP/FEMA stay in `_DOMAIN_TOKENS` (catch any future
    re-introduction).
  - **Phase 6K-E — INVARIANTS + CHANGELOG close-out**: `INVARIANTS.md`
    §I5 records Phase 6K under "Known current state" with a
    sub-phase A/B/C/D summary mirroring the 6J style; explicit
    deferrals to **Phase 6L** (8 magic-constant tuning knobs:
    `retriever.py` top_n/min_score, `drift.py` thresholds,
    `reflection.py` importance constants, `bridge.py` resolution-event
    importance, `council.py` quorum, `cross_agent_validator.py`
    thresholds) and **Phase 6M** (PMT schema extraction:
    `ReasoningSchema` `threat_appraisal`/`coping_appraisal` field
    names → framework-parametric base) are recorded. Skill-name
    docstring cleanup (`elevate_house` / `buy_insurance` /
    `relocate` / `maintain_demand`) is deliberately NOT pursued —
    Explore verified zero live-code references; keeping the
    grounded examples aids readability.
  - Verification across all five sub-phases: `pytest broker/ tests/`
    net-zero regression (5 pre-existing failures unchanged);
    `TestDomainGenericity` 21/21 green; real-model `governed_flood`
    smoke (gemma3:1b, 2 yr, 6 agents) ran end-to-end clean for 6K-A
    (48 rule violations), 6K-B (55), 6K-C (48). 6K-D and 6K-E are
    pure docstring/INVARIANTS edits — no smoke required.
- **Phase 6L — audit-B P1 magic-constant knobs → YAML / DomainPack**
  (the "tuning surfaces" effort Phase 6K explicitly deferred). Every
  remaining audit-B P1 magic constant now has a YAML override path
  AND a `DomainPack` hook, wired via the canonical 4-tier precedence
  stack (defaults → `DomainPack` → shared YAML → global YAML)
  established by Phase 6H Item 3. Defaults are byte-identical to the
  pre-6L hardcoded literals — no behavioural change unless a caller
  explicitly overrides. Five sub-phases:
  - **Phase 6L-A — `DriftDetector` knobs**: new
    `DomainPack.drift_policy()` hook + `DefaultDomainPack` returns
    `{}` + `AgentTypeConfig.get_drift_config()` accessor. Wires the
    5 `DriftDetector` thresholds (`entropy_threshold` /
    `stagnation_threshold` / `collapse_threshold` /
    `jaccard_stagnation_threshold` / `history_window`) to YAML
    `governance.drift`. Lowest-risk sub-phase by design (no
    production caller; validates the template extends cleanly).
    Closes audit-B P1 item 5.
  - **Phase 6L-B — Population-governance thresholds**: single
    `DomainPack.population_governance_policy()` hook bundles the
    `CrossAgentValidator` echo / entropy / deadlock thresholds and
    the `MajorityCouncilValidator` quorum. The
    `MajorityCouncilValidator` `>= 0.5` quorum literal extracted to
    a `quorum_threshold: float = 0.5` constructor kwarg. New
    `get_population_governance_config()` accessor; `run_unified_experiment.py`
    wired at the `CrossAgentValidator` construction site. Closes
    audit-B P1 items 9 + 10.
  - **Phase 6L-C — `PolicyEventGenerator` severity tiers**: the
    hardcoded `0.20` / `0.10` / `0.05` tier cuts extracted to
    `PolicyEventConfig.severity_tiers` dict (default-factory
    pattern, fresh per instantiation). New
    `DomainPack.policy_event_tiers()` hook + `get_policy_event_tiers_config()`
    accessor with sanity guards (every tier `>= 0`; monotonic
    `severe >= moderate >= minor`) so malformed overrides fail
    loudly at config-load time. Closes audit-B P1 item 12.
  - **Phase 6L-D — Cognitive hot-path knobs**: `MemoryBridge`
    resolution importance (`approved=0.6` / `denied=0.75`) relocated
    to module-level `_DEFAULT_RESOLUTION_IMPORTANCE` dict +
    `MemoryBridge.__init__(importance_policy=...)` kwarg + new
    `DomainPack.bridge_importance_policy()` hook +
    `get_bridge_importance_config()` accessor; the "denials more
    memorable" asymmetry preserved with an inline doc + an accessor
    guard rejecting `denied < approved`. `MultiAgentHooks` +
    `run_unified_experiment.py` threaded so YAML overrides reach the
    live MA-flood MemoryBridge. Reflection knobs (`base_importance`,
    `triggers.institutional_threshold` / `triggers.importance_boost`)
    ride the existing `get_reflection_config()` YAML pass-through —
    cognitive knobs stay YAML-only per Phase 6L plan (no DomainPack
    hook for reflection); `base_importance` is declare-only with a
    docstring deferral note. Closes audit-B P1 items 6 + 7 + 8.
  - **Phase 6L-E — INVARIANTS + CHANGELOG close-out**: this entry
    plus the §I5 "Closed by Phase 6L" block. The "Deferred to Phase
    6L (knobs)" bullet from the 6K block is removed; at 6L close-out
    the deferral list read Phase 6M (PMT schema extraction) +
    skill-name docstring (intentionally not pursued) — Phase 6M
    has since shipped (see below); only the skill-name-docstring
    deferral remains.
  - Verification across all five sub-phases: `pytest broker/ tests/`
    net-zero regression (5 pre-existing failures unchanged across
    the chain); `TestDomainGenericity` 21/21 green; real-model
    `governed_flood` smoke (gemma3:1b, 2 yr, 6 agents) ran end-to-end
    clean for 6L-D (the cognitive hot-path sub-phase) with 46
    governance rule violations — within the natural variance band
    46-55 seen across 6K-A (48) / 6K-B (55) / 6K-C (48) smokes.
    6L-A / 6L-B / 6L-C / 6L-E are plumbing / docs and did not
    require smoke per the Phase 6L plan.

- **Phase 6N-F — repository hygiene sweep** (2026-05-24). Five sub-commits removing pre-Phase-6 / pre-NW-pivot stale artifacts across `examples/`, `broker/`, `docs/`, and `scripts/`. **Pure deletions only** — no production code or paper data touched; the L3-1 chain's Tier-2 vaccination showcase + Paper-1b irrigation/flood 5-seed raw data + Paper-3 multi-agent flood directory all verified intact post-sweep (Paper-1b headline IBR/EHE recomputed byte-identical to published values).
  - **6N-F-1** (`698e466`): pruned `examples/minimal/` + `examples/minimal_nonwater/` + `examples/multi_agent_simple/` (pre-Phase-6 scaffolds; canonical scaffold is now `broker/tools/scaffold_domain` CLI + `wagf-domain-builder` skill). 14 doc files redirected to the live scaffold path.
  - **6N-F-2** (`9ec483e`): removed 6 `broker/_AUDIT_*_2026-04-18.md` files (pre-Phase-6 audit working notes; Phase 6 governance is recorded in `INVARIANTS.md` § canonical history).
  - **6N-F-3** (`c9a95cd`): removed 9 `docs/plans/2026-03-*.md` plan files (pre-Phase-6F planning notes superseded by CHANGELOG + INVARIANTS).
  - **6N-F-4** (`90c48c1`): pruned `examples/vaccination_ma_demo/` (Phase 6E PoC) + `examples/gossip_demo/` (Phase 6F PoC) — zero paper-1b or paper-3 dependency, zero broker test-fixture dependency. `examples/governed_flood/` retained as a load-bearing broker test fixture (imported by `broker/tests/test_initial_loader.py` + `test_memory_content_types.py`). 14 doc files updated to redirect the affected examples references to `examples/multi_agent/flood/` (Paper 3 production-grade multi-agent reference).
  - **6N-F-5** (this commit): removed `scripts/wrr_*` (5 pre-NW-pivot WRR journal pipeline scripts, Feb 9–11 2026; superseded by `paper/nature_water/scripts/compile_paper.py` pipeline) + untracked `scripts/codex_preflight.sh` (referenced the Phase 6N-F-2-deleted audit doc) + empty `scripts/` directory. Also removed `docs/internal/wrr/` (17 tracked files of pre-NW Group_A/B/C analysis output) + `docs/internal/archive/wrr_v6_working/` (15 older v6 working notes) — both internal archives of the abandoned WRR submission attempt. Patched one orphan `run_wrr_v6_flood.ps1` reference in `docs/internal/infrastructure/flood-smoke-validation-20260209.md` (the .ps1 never existed in the current tree).
  - **Final repository surface** post-6N-F: 6 examples (`quickstart`, `single_agent` [Paper 1b flood], `irrigation_abm` [Paper 1b irrigation], `multi_agent` [Paper 3], `vaccination_demo` [L3-1 Tier-2 showcase], `governed_flood` [broker test fixture]), zero pre-Phase-6 scaffolds, zero abandoned-paper archives, zero PoC-only demos. Reproducibility breadcrumbs preserved: 20 `examples/*/run_*.bat` launchers for paper-1b + paper-3 experiments retained on disk.
  - **Test gate**: `pytest broker/ tests/` net-zero regression vs Phase 6N-E baseline (5 pre-existing failures unchanged: 2 in `test_experiment_builder_policy.py` + 3 in `test_nature_water_figure_helpers.py`; deferred to v0.3.1 triage).

- **L3-1E + L3-1F + L3-1G — vaccination_demo Tier-2 chain close-out** (2026-05-24).
  - **L3-1E** (multi-seed cross-model orchestration): NEW `examples/vaccination_demo/run_vaccination_batch.sh` (bash) + `examples/vaccination_demo/run_vaccination_batch.bat` (Windows). Each script runs 3 seeds × 2 models = 6 runs by default (configurable via `SEEDS=` / `MODELS=` env vars), producing per-run audit CSVs + reproducibility_manifest.json under `examples/vaccination_demo/results/showcase_v1_seed<S>_<M_slug>/`. Models default to gemma3:4b (primary) + gemma4:e4b (secondary); seeds default to 42 / 43 / 44 (paper-1b reference triplet). Total wall time ~30-40 min on RTX 4080 SUPER.
  - **L3-1F** (headline summary statistic): NEW `examples/vaccination_demo/summary.py` (~80 LOC; pandas + print). Loads all batch result dirs, prints per-seed/model decision table (APPROVED rate, vaccination coverage %, skill breakdown), plus across-batch coverage mean/std/min/max. Mirrors the smallest possible scope of `examples/irrigation_abm/analysis/compute_ibr.py` — no plotting, no bootstrap CI; for showcase audit only.
  - **L3-1G** (docs close-out): `examples/vaccination_demo/README.md` rewritten with L3-1 chain summary (4 sub-steps + L3-1E batch runner pointer). Top-level `README.md` + `README_zh.md` Reference Implementations table updated — Vaccination (single) row now reads '25 literature-grounded agents | 5 yr | Tier-2 showcase (3 seeds × 2 models)' instead of the L3-1A '5 synthetic agents | 2 yr | proof-of-concept'.
  - **Verification**: `examples/vaccination_demo/summary.py` runs end-to-end on smoke #11's single-run dir (sanity check) producing a clean ASCII table. Real batch execution deferred to user (~30-40 min wall time).
  - L3-1 chain complete: L3-1A (persona sampler) → L3-1B (6/6 HBM constructs) → L3-1C (validator expansion 2 → 5 thinking rules) → L3-1D (5-year COVID-19 outbreak schedule) → L3-1E (batch runner) + L3-1F (summary) + L3-1G (docs). vaccination_demo upgraded from L3-1A's 5-agent / 2-year PoC to a 25-agent / 5-year / 3-seed × 2-model Tier-2 showcase with literature-grounded population + 6/6 HBM coherence rules + COVID-19-anchored year-by-year environmental signals.

- **L3-1D — vaccination_demo 5-year COVID-19-anchored outbreak schedule** (2026-05-24). Replaces the L3-1A `{year 2: 0.65}` placeholder with a literature-defensible 5-year arc loaded from a YAML schedule file. Each year emits four signals (severity / supply / side-effect / description) that flow into the LLM prompt as `{outbreak_severity_label}` / `{vaccine_supply_label}` / `{side_effect_signal}` / `{outbreak_description}` placeholders.
  - **NEW** `examples/vaccination_demo/data/outbreak_schedule.yaml` — 5-year schedule anchored on COVID-19 2020-2024 timeline. Year 1 = 2020 (pandemic onset / no vaccine), Year 2 = 2021 (rollout / limited supply), Year 3 = 2022 (variant wave / amplified side-effect rumours), Year 4 = 2023 (endemic transition / ample supply), Year 5 = 2024 (post-emergency steady state). Citations to WHO COVID-19 Dashboard + CDC Vaccination Distribution Tracker + Pew Research 2022 in the YAML header.
  - **REFACTOR** `examples/vaccination_demo/run_experiment.py::VaccinationEnvironment` — loads schedule from YAML at construction time; `advance_year()` now reads from the schedule and emits four global_state signals (outbreak severity + label, vaccine supply label, side-effect signal, plain-language description); years beyond the schedule hold the last-year signals (post-emergency steady state).
  - **BROKER FIX** `broker/components/context/tiered.py` (~4 LOC × 2 sites) — `BaseAgentContextBuilder.format_prompt` and `TieredContextBuilder.format_prompt` now flatten `env_context` primitives into `template_vars` so simulation-side per-year signals become `{placeholder}` slots the prompt template can reference directly. Previously env_context was stored in `context['environment_context']` as a nested dict and filtered out by the primitives-only flatten. Backward-compatible — water domains' template vars are unaffected unless their env_context primitives happen to collide with existing template keys (none do).
  - **PROMPT** `examples/vaccination_demo/config/prompts/individual.txt` — adds a year-specific 'Current situation' block referencing the four new placeholders. The LLM now sees year-1-2020 (severe + absent vaccine) vs year-5-2024 (low + ample) and responds with appropriate HBM construct labels.
  - **REGRESSION TESTS** 6 new tests at `examples/vaccination_demo/tests/test_outbreak_schedule.py`: YAML schema, year-1 COVID-2020 anchor, year-5 COVID-2024 anchor, supply arc progression (absent → limited → ample), outbreak_active threshold logic, post-schedule steady-state behaviour.
  - **Smoke #11 verification** (gemma3:1b, 5 agents × 5 yr, seed=42): 25/25 APPROVED; year-1 prompt confirmed to contain 'Pandemic onset... severity: severe / supply: absent / signal: unknown'; year-4 prompt contains 'Endemic transition... severity: low / supply: ample / signal: familiar'. Decision distribution varies by year (15 get_vaccinated + 10 delay vs L3-1A's effectively-constant signals). Memory accumulation across years works (year-4 agent sees its prior 3 years' decisions).
  - 1 residual lowercase leak (Agent_001 year 3, BARRIERS='m') noted as Phase 6N-F candidate — Phase 6N-D-4's whitelist filter closed the primary free-text fallback path; another less-frequent capture path is still leaking. 1/25 ≈ 4% in this 5-yr smoke; flood Group_C reference data was 2/8918 ≈ 0.022% pre-fix.
  - Test gate: `pytest broker/ tests/ examples/vaccination_demo/tests/` net-zero regression vs the post-Phase-6N-E baseline (5 pre-existing failures unchanged).

- **Phase 6N-E — fix vaccination_demo thinking rules never fire** (2026-05-24). Phase 6N-D-5's closing note disclosed two findings (ThinkingValidator dead-code + Smoke #8 row 2 didn't trigger expected WARNING rule). Three parallel Explores converged on a single root cause: YAML condition-dict key mismatch.
  - **Root cause**: vaccination_demo's 5 thinking_rules used `{ type: construct, field: X, operator: "in", values: [...] }` (copied from `RuleCondition` dataclass shape). `AgentValidator._run_rule_set` reads `cond.get("construct")` only — for that verbose shape, `construct_name = None`, rule never fires. Isolated to vaccination_demo; water domains all use canonical `{ construct: X, values: [...] }`.
  - **Fix 1 (broker)**: `broker/validators/agent/agent_validator.py:~418` defensive accept both shapes via `cond.get("construct") or cond.get("field")`. Backward-compatible — both shapes now work.
  - **Fix 2 (vaccination_demo)**: 5 thinking_rules in `examples/vaccination_demo/config/agent_types.yaml` rewritten to canonical short shape `{ construct: X, values: [...] }`. Same behaviour, cleaner authoring.
  - **Fix 3 (docs)**: `.claude/skills/wagf-domain-builder/references/edit_pass_checklist.md` + `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` condition examples updated to canonical shape with explanatory comments about why the legacy shape silently fails.
  - **Regression test**: 3 tests at `broker/tests/test_agent_validator_thinking.py` exercise the production `AgentValidator.validate_thinking()` end-to-end. `test_canonical_construct_key_fires` asserts the row-2 case (BARRIERS=H + EFFICACY=H + delay) NOW fires `high_barriers_high_self_efficacy_no_action_required`. `test_legacy_field_key_also_fires` pins backwards-compat for the defensive `or cond.get("field")` fallback.
  - **Misleading Phase 6N-D-1 framing corrected**: the "9 WARNING+blocked_skills rules silently block in irrigation/flood" claim was wrong — ThinkingValidator was dead-code (production uses AgentValidator), and AgentValidator's `_run_rule_set` already handled `level` correctly at line 459. The 0 fires across 39,943 paper-1b audit rows was real but caused by no matching construct combinations in those experiments, not silent blocking.
  - **Smoke #9 verification** (gemma4:e4b, 15 agents × 3 yr, seed=42, post-6N-E-1): 18/18 APPROVED, 0 lowercase leaks, 0 rule fires. The 0 fires is correct behaviour confirmed by direct `validate_thinking()` invocation on each row's HBM combinations — none of the 18 LLM-emitted construct combinations matched any rule. Regression test demonstrates the wiring works on a synthetic row that DOES match.
  - **Test gate**: `pytest broker/ tests/` net-zero regression vs Phase 6N-D baseline (5 pre-existing failures unchanged); 3 new tests at `test_agent_validator_thinking.py` pass.
  - 6 files changed (1 broker code + 1 example YAML + 3 docs/skills + 1 new test file) + INVARIANTS + CHANGELOG.

- **Phase 6N-D — close four broker-side bugs from the L3-1C reviewer's deferred bucket** (2026-05-24). All four were caught during L3-1C but deferred for proper broker-level fixing instead of caller-side workarounds. Five sub-commits (6N-D-1 through 6N-D-5); each with regression-test coverage.
  - **6N-D-1**: `ThinkingValidator._validate_yaml_rules` now respects `rule.level`. Pre-fix it hardcoded `valid=False`, so YAML thinking rules declared `level: WARNING` with `blocked_skills` silently block-and-retried like ERROR rules. The 6-LOC fix at `broker/validators/governance/thinking_validator.py:329-355` mirrors `BaseValidator.validate()`'s level-respecting contract. **Static paper-data audit** across 39,943 audit rows (irrigation v21 5-seed × 2 conditions + single-agent flood Group_C 5-run + ablation 3-run) confirmed **0 fires** of any WARNING+blocked_skills rule in paper-1b reference data — the 9 such rules across 4 domains never triggered, so the fix has zero impact on paper IBR/EHE. vaccination_demo's L3-1C workaround (stripping `blocked_skills` from WARNING rules) becomes unnecessary and is reverted in 6N-D-5.
  - **6N-D-2**: `RuleCondition._get_value_from_context` defensive normalisation. The 2-LOC fix at `broker/governance/rule_types.py:90-105` `.upper().strip()`s string values for `construct`-type conditions; numeric/None pass through unchanged. Practically a no-op today (Phase 6N-B's upstream `.upper()` already canonicalises captures), but closes fragility for any future caller bypassing the unified adapter.
  - **6N-D-3**: regression test only — `rule_breakdown` audit pipeline. The Phase 6C W8 commit `4b20320` (May 10) wired `_safe_rule_breakdown` into the audit trace. v21 paper audit CSVs that show `rules_<category>_hit = 0` were generated April 25 (pre-fix). Current code is correct; this sub-phase adds 6 tests at `broker/tests/test_rule_breakdown_audit.py` so the fix can't be silently undone.
  - **6N-D-4**: whitelist filter on the free-text fallback regex capture at `broker/utils/parsing/unified_adapter.py:~585`. The regex `\b(VL|L|M|H|VH)\b` over-matches the bare `m` inside contractions like `I-apostrophe-m` (word-boundary matches between apostrophe and `m`). 5-LOC fix gates the capture on `temp_val.upper() in {VL, L, M, H, VH}` so non-canonical bare letters are rejected at source. L3-1C smoke #6 had 1/45 leak; flood Group_C v21 paper data had 2/8918 (recorded in cross-version log dd4a4f2); post-fix runs produce 0 leaks. 20 regression tests at `broker/tests/test_unified_adapter_label_overmatch.py`.
  - **6N-D-5**: `examples/vaccination_demo/config/agent_types.yaml` restored `blocked_skills` to the 3 WARNING rules that L3-1C stripped as a Bug #5 workaround. Post-6N-D-1 WARNING+blocked_skills produces correct log-only behaviour. Inline comments document the post-6N-D-1 semantics. INVARIANTS §I5 + CHANGELOG close-out.
  - 4 new pytest files, total ~430 LOC test code; net-zero regression vs the post-L3-1C baseline (5 pre-existing failures unchanged).
  - L3-1C smoke #7-equivalent verification (gemma4:e4b 15 agents × 3 yr seed=42) confirms restored vaccination_demo WARNING rules produce APPROVED outcomes (not REJECTED_FALLBACK) and warning-logged rule fires visible in audit `warnings` field.

- **L3-1C — vaccination_demo validator expansion 2 → 5 thinking-rules + Phase 6N-C documentation-rot cleanup** (2026-05-24). L3-1C's intended scope was a straightforward expansion of HBM coherence rules to exercise the L3-1B 6/6 construct schema; reviewer caught a deeper finding that surfaced as Phase 6N-C.
  - **L3-1C scope (vaccination_demo)**: `agent_types.yaml` `thinking_rules:` block expanded from 2 → 5 rules covering all 6 HBM constructs. Rule 1 tightened from 2-construct to 3-construct (`high_susceptibility_high_severity_high_efficacy_no_refuse`) — avoids over-blocking when the agent legitimately judges severity low. NEW: `high_barriers_high_self_efficacy_no_action_required` (WARNING, log-only), `low_severity_low_benefits_get_vaccinated` (WARNING, log-only — uses BENEFITS not SELF_EFFICACY per reviewer W3 since low-efficacy + get_vaccinated is a near-paradox), `high_cues_low_barriers_refuse_inconsistent` (ERROR, blocks refuse — requires both high cues AND low barriers per reviewer W2 to avoid false positives on agents with legitimate documented barriers). Existing `low_susceptibility_no_get_vaccinated` preserved unchanged.
  - **WARNING-rule semantics**: broker bug `_validate_yaml_rules` ignores `level` and treats `blocked_skills` as block-and-retry regardless. Worked around in this commit by stripping `blocked_skills` from all 3 WARNING rules so they become true log-only annotations. Broker bug deferred (Phase 6N-D candidate).
  - **`vaccination_validators.py` simplified**: reverted an earlier draft that mirrored the 5 YAML coherence rules in Python — `__init__.py` slot-policy rejects `thinking` as a registered slot, so those mirror functions would have been dead code. Stripped to just the single physical `vaccination_recent_dose_no_revaccinate` check (which IS registered correctly under the `physical` slot).
  - **Phase 6N-C documentation-rot cleanup** (the critical finding): the vaccination_demo YAML had been using `rules:` as the block key for thinking rules since the PoC was first written. The broker's loader `get_thinking_rules()` at `broker/utils/agent_config.py:859` recognises ONLY `thinking_rules:` or `coherence_rules:` — a bare `rules:` block is silently dead config. The PoC's "2 HBM coherence rules" had therefore been parsed but never enforced for the entire PoC lifetime. Root cause: the `wagf-domain-builder` skill (`SKILL.md` + 2 reference docs) and `HOW_TO_ADD_A_NEW_DOMAIN.md` were all teaching `rules:`. Fix: rename `rules:` → `thinking_rules:` in the YAML (runtime verified: loader now loads 5/5 rules), correct 5 doc-file references to the right key name, and rename the empty `rules: []` prophylactic blocks in `gossip_demo` + `vaccination_ma_demo` (3 each, harmless today but would silently break for any future rule-adder).
  - Water-domain YAMLs (irrigation, single-agent flood, governed_flood, MA flood Paper 3) were ALL using `thinking_rules:` correctly already — bug was isolated to non-water demos that followed the mis-teaching skill.
  - Real-model verification: smoke #7 (gemma4:e4b, 15 agents × 3 yr, seed=42) — 20/21 APPROVED, 1 parse-fail fallback, zero lowercase leaks (Phase 6N-B `.upper()` continues working), 0 rules fire because gemma4:e4b is so rational on this prompt it produces 20/20 `get_vaccinated` with HIGH motivation labels (no `refuse`, no low-band labels — rules have no irrational targets to catch). Irrigation v21 paper-1b data verified separately: 38.7% block rate, `failed_rules` column shows `high_threat_high_cope_no_increase` (thinking rule) firing — production rule enforcement is real; the smoke "0 fires" is a model-rationality artifact, not a wiring bug.
  - Test gate: `pytest broker/ tests/ examples/vaccination_demo/tests/` net-zero regression (same 5 pre-existing failures unchanged); `TestDomainGenericity` 25/25 still green.
  - Deferred (Phase 6N-D candidates): (a) broker `_validate_yaml_rules` ignores `level` — needs proper WARNING-vs-ERROR semantics; (b) `RuleCondition.evaluate()` reads label without normalization (pre-existing, low-risk because Phase 6N-B upstream `unified_adapter` `.upper()` already canonicalises); (c) audit `rules_<category>_hit` count columns are 0 across the board in irrigation v21 production data even though `failed_rules` has rule names — bookkeeping bug from Phase 6C W8; (d) the `unified_adapter` regex over-match where `I'm` produces `'m'` captured as `SEVERITY_LABEL` (low-frequency, 1/45 in pre-fix smoke).
  - 10 files modified across `examples/vaccination_demo/`, `examples/gossip_demo/`, `examples/vaccination_ma_demo/`, `.claude/skills/wagf-domain-builder/`, `docs/guides/`, plus `broker/INVARIANTS.md` §I5 + this CHANGELOG entry.

- **Phase 6N-B — two broker bugs caught during L3-1B vaccination_demo smoke** (2026-05-23).
  Both surfaced during the iteration arc on L3-1B's 6-construct HBM
  prompt expansion. Neither was in the L3-1B scope; both warranted a
  proper broker fix rather than a caller-side workaround.
  - **Bug 1**: `BaseAgentContextBuilder.format_prompt` (parent of
    `TieredContextBuilder`) did NOT inject the YAML-defined
    `{response_format}` JSON schema into prompts. Only the Tiered
    subclass did. Any single-agent / no-Hub domain whose prompt
    template carried `{response_format}` fell through to
    `SafeFormatter`'s `[N/A]` default and the LLM had no schema
    example. The L3-1B vaccination_demo smoke #1/#2 hit 0-1/10
    APPROVED because of this. Fixed by adding the same try/except
    injection block (lifted from `TieredContextBuilder.format_prompt`
    lines ~543-562) into `BaseAgentContextBuilder.format_prompt` at
    `broker/components/context/tiered.py:~195`. Tiered subclass keeps
    its own injection for the keys it builds locally
    (`valid_choices_text` from skill provider) — they don't conflict
    because Tiered's `format_prompt` overrides Base's entirely. The
    L3-1B smoke #3 went 10/10 APPROVED with this fix, and smoke #5
    (post-Phase 6N-B) re-verified — also 10/10.
  - **Bug 2**: `broker/utils/parsing/unified_adapter.py:~463` captured
    the LLM-emitted LABEL string via `match.group(1)` from a
    `re.IGNORECASE` regex. The match worked case-insensitively but the
    captured group preserved whatever case the LLM wrote. A chatty
    `gemma3:1b` emitting `"m"` instead of `"M"` therefore produced
    mixed-case labels in the audit CSV — `['M', 'm']` etc. —
    silently breaking downstream governance rules like
    `in ['H', 'VH']` that miss case variants. Fixed by calling
    `.upper()` on the captured group; the LABEL ordinal alphabet
    (VL/L/M/H/VH) is canonical uppercase by contract. Smoke #5
    verified zero lowercase leaks across all 6 HBM construct columns.
  - Test coverage:
    `broker/tests/test_context_builder_response_format.py` carries
    three regression tests (Bug 1 functional, Bug 2 inline regex,
    Bug 2 grep-based contract). Net-zero pytest regression
    confirmed; 5 pre-existing failures unchanged.
  - `INVARIANTS.md` §I5 records both as `Closed by Phase 6N-B`.

- **Phase 6N-A — `audit.py` social-context block de-flooded** (2026-05-23).
  A leak surfaced during the Phase 6M+README review round: the audit
  writer's social-context CSV block (`broker/components/analytics/audit.py`
  §6) hardcoded `elevated_neighbors` / `relocated_neighbors` reads from
  `visible_actions`, emitting `social_elevated_neighbors` /
  `social_relocated_neighbors` columns directly. The token guard never
  caught this because those two tokens were not in `_DOMAIN_TOKENS`.
  Migrated to a dynamic `social_<key>` pass-through — `audit.py` now
  iterates the `visible_actions` dict and writes `social_<vkey>` for
  whatever the domain supplies. The flood-domain output CSV is
  byte-identical for rows where `social_audit` is populated (flood
  still puts `elevated_neighbors` / `relocated_neighbors` in
  `visible_actions`); a vaccination or gossip domain would now
  naturally produce `social_vaccinated_neighbors` etc. without touching
  `broker/`. For rows where `social_audit` is absent the two
  flood-specific columns are no longer defaulted to `0` — they're
  simply omitted (column set-union in `compute_csv_fieldnames`
  preserves CSV header completeness across mixed rows; downstream
  analysis uses named column access only). The visible-actions loop
  runs AFTER the broker-owned `gossip_count` / `neighbor_count` /
  `network_density` writes so a domain that collides on those key
  names cannot silently overwrite them. Hardcoded column names removed from
  `compute_csv_fieldnames` priority list and from the `else`-branch
  placeholders. `_DOMAIN_TOKENS` widened with the two tokens (count
  23 → 25). `TestDormantFieldPolicy._AUDIT_AGGREGATE_KEYS["social_audit"]`
  updated to drop the two flood column names from its documented column
  set (they are now domain-dynamic). Verification: `pytest broker/ tests/`
  net-zero regression vs the post-6M baseline (5 pre-existing failures
  unchanged); `TestDomainGenericity` 25/25 green; `test_audit_modular`
  (which feeds flood-style keys) still asserts
  `row["social_elevated_neighbors"] == "3"` and passes.

- **Phase 6M — close the last Phase 6L deferral (PMT schema extraction)**.
  A fresh investigation (three Explore agents, 2026-05-23) inverted the
  6L plan's risk profile: `broker/interfaces/schemas.py::ReasoningSchema`
  was **dead code** (0 imports, 0 instantiations, 0 type annotations across
  `broker/`, `examples/`, `tests/`), the response-format builder was
  already YAML-driven, and three non-PMT reference domains
  (`vaccination_demo` / `vaccination_ma_demo` / `gossip_demo`) already
  plug in without touching the schema. So Phase 6M shrank from a
  Pydantic class-hierarchy refactor to a surgical metadata + token-guard
  cleanup.
  - **Phase 6M-A — surgical cleanup**: deleted the `ReasoningSchema`
    class outright (replaced with a deletion-marker comment recording
    the verification methodology + where a future PMT-specific reference
    would live at `broker/domains/water/schemas.py`).
    `SkillProposalSchema.reasoning`'s field description simultaneously
    de-PMTed from `"PMT appraisals"` to
    `"Construct appraisals (domain-defined keys)"` so the now-canonical
    construct-agnostic payload channel doesn't carry a PMT label.
    `_DOMAIN_TOKENS` widened with `threat_appraisal` + `coping_appraisal`
    (21 → 23). Three tail mentions in generic `broker/` FP-allowlisted
    with per-entry justifications (`components/response_format.py`
    docstring examples, `interfaces/schemas.py` deletion-marker comment,
    `validators/posthoc/unified_rh.py` backwards-compat
    `ta_col`/`ca_col` defaults with a docstring caveat; the existing
    column-existence guard at `unified_rh.py:177` is the safety net —
    a non-PMT caller with missing columns drops to the `"M"` mid-scale
    sentinel rather than misclassifying). Light clarifying comments on
    `broker/config/agent_types/base.py::DEFAULT_PMT_CONSTRUCTS` and
    `broker/core/unified_context_builder.py`'s PMT fallback constructs
    label both as water-domain defaults (not generic recommendations).
    No Pydantic hierarchy refactor; no caller migration.
  - **Phase 6M-B — INVARIANTS + CHANGELOG close-out**: §I5 "Closed by
    Phase 6M" block recording the reframing finding (dead-code deletion,
    not hierarchy refactor) + token expansion + FP-allowlist bookkeeping;
    the 6L "Deferred to Phase 6M (PMT schema)" bullet removed. The
    deferral list now reads only the skill-name-docstring item
    (intentionally not pursued — `elevate_house` / `buy_insurance` /
    `relocate` / `maintain_demand` are kept as grounded docstring
    examples; the I5 guard intentionally does NOT enforce these).
  - Verification: `pytest broker/ tests/` net-zero regression
    (5 pre-existing failures unchanged); `TestDomainGenericity` 23/23
    green at the new token count. No real-model smoke required — pure
    metadata + docstring + token-guard change with zero broker-pipeline
    behaviour impact.

### Notes

- **Existing experiments unaffected**: irrigation, single-agent flood and
  governed_flood declare `reflection.questions` in YAML → reflection prompts
  byte-identical; retriever / registry defaults preserve pre-6H behaviour.
  MA flood (Paper 3, frozen) reflection now draws from `ma_agent_types.yaml`
  rather than the removed hardcoded dict.

## [0.3.0] - 2026-05-20

Major release: Phase 6A–6G framework genericity + audit hardening + multi-agent
domain support. **88 `broker/` commits since v0.2.0** (Feb–May 2026); broker
side fully green (148 passed, 1 skipped, 0 fails on the 149-test gate).

### Added

#### Framework genericity (Phase 6A → 6C)
- **DomainPack Protocol + Registry** (`broker/components/domain_pack/`):
  declarative domain configuration moving water-specific defaults out of
  generic broker code. Status text, event types, perception filter fields,
  agent-profile structure, validator bundles, financial-cost providers,
  institutional agent types, and reflection adapters all configurable via
  DomainPack.
- **ValidatorRegistry** + **FilterRegistry**: plugin pattern for validator
  and neighbour-filter discovery without touching broker code.
- **scaffold_domain CLI** (`broker.tools.scaffold_domain`): one-command
  domain skeleton for new researchers.
- **validate_prompt CLI** (`broker.tools.validate_prompt`): config-time
  BLOCKER pre-check.
- **Custom framework registration**: support for user-defined behavioural
  frameworks beyond PMT and dual-appraisal.
- **Generic temporal-rule framework** (M1/M2/M3): post-hoc diagnostic
  layer for sequence-level rules (appraisal–history coherence,
  behavioural inertia, evidence-grounded irreversibility) with
  domain-agnostic adapter contract.
- **FloodAgentProfile split** from generic AgentProfile.

#### Audit hardening (Phase 6G)
- **Crash-safe JSONL fsync**: per-decision flush to prevent partial-trace
  loss; `broker.tools.recover_csv_from_jsonl` CLI rebuilds CSV from
  streaming JSONL after crash, with schema parity enforced by
  `tests/test_recover_csv_from_jsonl.py` (INVARIANTS.md §I2 LOAD-BEARING).
- **validator_health.csv**: per-agent-type validator firing-rate audit
  with dead-rule steering (Gate-3 canonical item 4).
- **Audit log schema versioning** (Phase 6G W2): version tag on every CSV
  header for forward-compatible analysis.
- **Shadow|active validator modes** (Phase 6G W4 + W5 end-to-end): per
  validator toggle for staged rollout.
- **Appraisal-grounding post-hoc audit** (Gate-2 #1): trace consistency
  between stated appraisal and chosen action.
- **`fallback_activated` column written at source** (Phase 6G W1 #4a):
  no derived metric; intentional semantic change documented in
  INVARIANTS.md.

#### Framework invariants
- **Five framework invariants** + CI regression guards in
  `broker/tests/test_framework_invariants.py`: memory contract (I1),
  audit integrity (I2), API consistency (I3), dormant-code policy (I4),
  domain-genericity (I5). Plus `tests/test_domain_genericity.py` and
  `tests/test_recover_csv_from_jsonl.py` as additional LOAD-BEARING
  guards. `broker/INVARIANTS.md` is the human-facing index.

#### Memory subsystem
- **Broker-level memory write governance**
  (`broker/components/memory/policy_filter.py`): content-type-aware policy
  proxy preventing the rationalization ratchet for any new MA experiment.
  Nine `MemoryContentType` enum members (6 safe + 3 risky);
  `CLEAN_POLICY` (default) vs `LEGACY_POLICY` selection via
  `ExperimentBuilder.with_memory_write_policy()`.
- **Insertion-order preservation** for equal-salience memories.

#### Multi-agent support
- **Phase 6E multi-agent BLOCKER fixes** generalized from flood-specific
  to generic broker (3 fixes).
- **Phase 6F spatial gossip validation**: community moderator +
  influencer + casual_user reference domain
  (`examples/gossip_demo/`).
- **DomainReflectionAdapter** wired via DomainPack (Invariant 4).

#### Diagnostics
- **Model conservatism diagnostic** (CCA / CSI / ACI / ESRR metrics) for
  cross-model comparison.
- **Audit trace enrichment** + default-skill CLI override.
- **Enhanced reproducibility manifest** + audit thread safety.

### Changed
- **Architecture refactor**: decouple broker from example validators;
  clean public API; deprecate legacy hook aliases; standardize logging.
- **Code organisation**: split god classes; extract domain content;
  parameterize analysis script paths for cross-domain extensibility.
- **`memory_factory.py`** registry-dispatched (continued from v0.2.0).

### Fixed
- **Memory pipeline v2 contract**: `retrieve()` returns `List[MemoryRecord]`
  per Invariant 1; legacy plain-string consumers use
  `retrieve_content_only()`. Memory-dict items coerced to text in
  reflection + irrigation logger.
- **R5 re-elevation bug**: `_inject_filtered_skills` now respects
  pre-filtered `available_skills`.
- **Ollama `think` parameter** must be top-level, not in `options`
  (commit `fc6c599`; corrected all prior Gemma-4 thinking-mode runs).
- **Per-agent exception isolation**: experiment continues on single-agent
  LLM failure (`ac7faea`).
- **Lazy-load faiss** for Python 3.14 import-hang prevention.
- **E5 builtin-check agent-type scoping** (Phase 6G canonical item 2).
- **Keyword classifier negation bug** + IBR formula sync to production
  (R1+R3+R4, R5 excluded per EDT2).
- **SP_REASON keyword collision** + hardcoded reflection stub.

### Removed
- **Eight `tests/test_*_split.py` structural-smoke tests** retired: the
  2026-02 broker restructuring shipped 3 months ago and stayed green;
  structural asserts subsumed by real unit-test coverage of post-split
  modules. Test count **2165 → 2156**. Per
  `.ai/2026/05/18/pytest_inventory.md` §6 Phase 2.

### Documentation
- **Refreshed WAGF architecture figure** (`docs/architecture.png`):
  updated for NW Paper 1b Fig 1 framework (governed 3-layer loop with
  appraisal-grid output, water-relabeled arrows, de-flooded Environment
  icon).
- **`broker/INVARIANTS.md`**: documents the five framework invariants
  with executable-guard cross-references, plus intentional
  `fallback_activated` semantic change and v2→v3 cross-comparability
  verdict.

### Known Issues
- **9 stale tests on `tests/` side** (pre-existing, NOT broker/-side):
  3 in `test_nature_water_figure_helpers.py` (Fig2 helper logic updated
  during NW Paper 1b F4 round, test assertions not synced); 6 in
  `test_dynamic_importance.py` (flood memory module, Python 3.14 /
  numeric-stack ABI). Broker/ side is 100% green. Triage planned for
  v0.3.1.
- **2 misnamed CLI scripts** in `examples/multi_agent/flood/paper3/analysis/`
  (`memory_causal_test.py`, `pa_prompt_calibration_test.py`) trigger
  accidental pytest collection if `pytest examples/.../paper3/analysis/`
  is run; gate-standard `pytest tests/ broker/` unaffected. Rename
  deferred to avoid breaking README `python -m paper3.analysis.*`
  cross-references.

## [0.2.0] - 2026-02-10

### Added
- **Per-agent-type model names**: `llm_params.model` in YAML overrides CLI `--model`
  for individual agent types, enabling heterogeneous LLM configurations
- **MemoryEngineRegistry**: Plugin registry for memory engines — register custom
  engines without modifying framework code
- **ExperimentBuilder.validate()**: Pre-build validation with actionable error messages
- **CognitiveCache**: Decision-reuse cache (SHA-256 hash of state+env+memory) that
  bypasses LLM calls when context is identical
- **Advanced Patterns Guide**: State hierarchy, two-way coupling, per-type LLM docs
- **Multi-Agent Setup Guide**: Full walkthrough for heterogeneous agent populations
- **YAML Configuration Reference**: Field-by-field reference for all YAML config files
- **Troubleshooting Guide**: 21+ error patterns with diagnosis steps
- **Customization Guide (English)**: Translated from Chinese with added recipes
- **Multi-agent simple example**: 7-agent experiment (regulator + farmers) bridging
  the quickstart-to-production gap
- **Framework Parameter Reference** in README: All parameters with valid ranges
- **Test infrastructure**: `tests/conftest.py` with shared fixtures, 29 core tests
  covering ExperimentRunner and CognitiveCache

### Fixed
- **SkillProposal mutation**: Removed direct mutation of `magnitude_pct` and
  `magnitude_fallback` on the original proposal object
- **Validation context key collision**: Added `__debug__`-only diagnostic warning
  when `agent_state` and `env_context` share key names
- **AgentTypeConfig cache staleness**: Added `clear_cache()` classmethod for test
  teardown; improved error messages with actionable tips

### Changed
- **memory_factory.py**: Refactored from 147-line if/elif chain to 53-line
  delegation to MemoryEngineRegistry (backward compatible)
- **YAML error messages**: Now include file path, tip text, and suggested fix

## [0.1.0] - 2025-12-01

### Added
- Initial release of the Water Agent Governance Framework
- 7-layer architecture: LLM Interface, Governance, Execution, Memory,
  Reflection, Social, Utilities
- SkillBrokerEngine 6-stage pipeline (Context, LLM, Parse, Validate,
  Approve, Execute)
- Three governance profiles: strict, flexible, autonomous
- Identity rules (boolean state checks) and thinking rules (construct evaluation)
- Five memory engines: Window, Importance, Hierarchical, HumanCentric, Universal
- ExperimentBuilder fluent API
- Phase ordering for multi-agent simulations
- Social graph with observation and gossip channels
- InteractionHub for tiered context assembly
- Five quickstart tiers with progressive complexity
- Flood domain (Paper 3) and irrigation domain (Paper 2) examples

### Known Issues
- `PrioritySchemaProvider`, `NarrativeProvider`, `EnvironmentObservationProvider`,
  and `InsuranceInfoProvider` are defined but not actively used in current examples
- `HierarchicalMemoryEngine` and `ImportanceMemoryEngine` are deprecated in favor
  of `HumanCentricMemoryEngine`
- No CI/CD pipeline (GitHub Actions)
- Test collection errors in `tests/sdk/` due to import issues
