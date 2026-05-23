# Changelog

All notable changes to the Water Agent Governance Framework (WAGF) will be
documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Phase 6H (DomainPack v2 + genericity hardening) — **Items 1–5 of 8**.
Net-zero test regression vs v0.3.0 (full `broker/ tests/`: 11 failures,
all pre-existing and identical before/after); real-model `gemma4:e4b`
smoke green. Items 6–8 (affordability validator, FinancialCostProvider
dedup, thinking-validator rules) and the reflection status-text /
importance fallbacks remain on the I5 `TestDomainGenericity` KNOWN-DEBT
allowlist — the framework is more generic but not yet
flood-coupling-free.

### Added

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
    6L (knobs)" bullet from the 6K block is removed; the deferral
    list now reads Phase 6M (PMT schema extraction) + skill-name
    docstring (intentionally not pursued) only.
  - Verification across all five sub-phases: `pytest broker/ tests/`
    net-zero regression (5 pre-existing failures unchanged across
    the chain); `TestDomainGenericity` 21/21 green; real-model
    `governed_flood` smoke (gemma3:1b, 2 yr, 6 agents) ran end-to-end
    clean for 6L-D (the cognitive hot-path sub-phase) with 46
    governance rule violations — within the natural variance band
    46-55 seen across 6K-A (48) / 6K-B (55) / 6K-C (48) smokes.
    6L-A / 6L-B / 6L-C / 6L-E are plumbing / docs and did not
    require smoke per the Phase 6L plan.

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
