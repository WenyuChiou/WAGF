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
