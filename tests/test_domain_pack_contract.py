"""
Phase 6C-v2 (2026-05-10) — DomainPack facade contract tests.

Locks down the cross-cutting invariants that make DomainPack useful:

1. **Default no-op pack** — every method has a documented benign return
   so broker code can call into it unconditionally. Required so a new
   domain that hasn't filled in every method doesn't crash.

2. **Registry semantics** — register / get / get_or_default / has /
   clear / domains. ``get_or_default`` returns the no-op pack when the
   requested name is absent or None, and emits a one-time warning per
   missing name. Registry round-trip preserves identity.

3. **Water packs (irrigation + flood) preserve byte-identical
   behaviour** for all delegated methods. This is the regression net
   for Paper 1b headline data: if a refactor accidentally diverges
   FloodDomainPack.skill_emotion_metadata from the pre-refactor
   experiment_runner.py:383-388 literals, IBR/EHE numbers shift.

4. **Hot-path lookups** — reflection.py / experiment_runner.py /
   ma_manager.py / providers.py / validator_bundles.py all consult the
   registry at runtime; this test confirms each reads the pack via
   ``DomainPackRegistry.get_or_default(...)`` (or scans
   ``DomainPackRegistry.domains()``). Tested by inspecting source.
"""
from __future__ import annotations

import inspect

import pytest

from broker.domains.protocol import DomainPack
from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry


# ─────────────────────────────────────────────────────────────────────
# 1. Default no-op pack
# ─────────────────────────────────────────────────────────────────────

class TestDefaultDomainPack:
    """Default pack is the safety net — every method must return a
    benign default so broker code can call into it unconditionally."""

    def setup_method(self):
        self.pack = DefaultDomainPack()

    def test_implements_protocol(self):
        assert isinstance(self.pack, DomainPack)

    def test_name_is_default(self):
        assert self.pack.name == "default"

    def test_reflection_status_text_is_none(self):
        assert self.pack.reflection_status_text(None) is None
        assert self.pack.reflection_status_text(object()) is None

    def test_reflection_questions_is_empty(self):
        assert self.pack.reflection_questions() == []

    def test_reflection_persona_is_none(self):
        assert self.pack.reflection_persona() is None

    def test_reflection_trait_labels_is_empty(self):
        assert self.pack.reflection_trait_labels(None) == []
        assert self.pack.reflection_trait_labels(object()) == []

    def test_importance_profiles_is_empty(self):
        assert self.pack.importance_profiles() == {}

    def test_compute_importance_returns_base(self):
        assert self.pack.compute_importance(None) == 0.5
        assert self.pack.compute_importance({}, base=0.7) == 0.7

    def test_classify_emotion_is_neutral(self):
        assert self.pack.classify_emotion("any_decision", None) == "neutral"

    def test_emotional_keywords_is_empty(self):
        assert self.pack.emotional_keywords() == {}

    def test_retrieval_weights_sum_to_one(self):
        weights = self.pack.retrieval_weights()
        assert set(weights.keys()) == {"W_recency", "W_importance", "W_context"}
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_skill_emotion_metadata_is_empty(self):
        assert self.pack.skill_emotion_metadata("anything") == {}

    def test_extreme_actions_is_empty(self):
        assert self.pack.extreme_actions() == set()

    def test_event_handlers_is_empty(self):
        assert self.pack.event_handlers() == {}

    def test_agent_impact_handlers_is_empty(self):
        assert self.pack.agent_impact_handlers() == {}

    def test_memory_policy_is_none(self):
        # Phase 6K-A: DefaultDomainPack returns None — generic memory
        # subsystem falls back to its safe domain-agnostic behaviour
        # (empty whitelist, no stimulus-key default, no category rules
        # beyond the truly-generic _DEFAULT_RULES).
        assert self.pack.memory_policy() is None

    def test_drift_policy_is_empty(self):
        # Phase 6L-A: DefaultDomainPack returns {} — DriftDetector
        # constructor defaults (entropy 0.5, stagnation 0.6, etc.) apply.
        assert self.pack.drift_policy() == {}

    def test_population_governance_policy_is_empty(self):
        # Phase 6L-B: DefaultDomainPack returns {} — CrossAgentValidator
        # / CouncilValidator constructor defaults (0.8 / 0.5 / 0.5 / 0.5)
        # apply.
        assert self.pack.population_governance_policy() == {}

    def test_policy_event_tiers_is_empty(self):
        # Phase 6L-C: DefaultDomainPack returns {} — PolicyEventConfig
        # default severity_tiers (0.20 / 0.10 / 0.05) apply.
        assert self.pack.policy_event_tiers() == {}

    def test_bridge_importance_policy_is_empty(self):
        # Phase 6L-D: DefaultDomainPack returns {} — MemoryBridge
        # constructor defaults (approved=0.6, denied=0.75) apply.
        assert self.pack.bridge_importance_policy() == {}

    def test_mg_barrier_text_is_empty(self):
        assert self.pack.mg_barrier_text({}) == ""

    def test_builtin_checks_is_empty(self):
        assert self.pack.builtin_checks() == {}

    def test_initial_memory_templates_is_empty(self):
        assert self.pack.initial_memory_templates({}) == []

    # ─── Phase 6H DomainPack v2 additions ─────────────────────────

    def test_perception_descriptors_is_empty(self):
        assert self.pack.perception_descriptors() == {}

    def test_perception_field_policy_is_empty(self):
        assert self.pack.perception_field_policy() == {}

    def test_passthrough_agent_types_is_empty(self):
        assert self.pack.passthrough_agent_types() == set()

    def test_affordability_constraints_is_empty(self):
        assert self.pack.affordability_constraints() == {}

    def test_retrieval_policy_is_empty(self):
        assert self.pack.retrieval_policy() == {}


# ─────────────────────────────────────────────────────────────────────
# 2. Registry semantics
# ─────────────────────────────────────────────────────────────────────

class TestDomainPackRegistry:
    def setup_method(self):
        # Snapshot existing registrations so we don't disturb other tests.
        self._snapshot = dict(DomainPackRegistry._packs)

    def teardown_method(self):
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(self._snapshot)
        DomainPackRegistry._missing_warned.clear()

    def test_register_and_get(self):
        pack = DefaultDomainPack()
        DomainPackRegistry.register("synthetic_xyz", pack)
        assert DomainPackRegistry.get("synthetic_xyz") is pack
        assert DomainPackRegistry.has("synthetic_xyz")

    def test_get_returns_none_when_absent(self):
        assert DomainPackRegistry.get("never_registered") is None

    def test_get_or_default_returns_pack_when_present(self):
        pack = DefaultDomainPack()
        DomainPackRegistry.register("synthetic_xyz", pack)
        assert DomainPackRegistry.get_or_default("synthetic_xyz") is pack

    def test_get_or_default_returns_default_when_absent(self):
        result = DomainPackRegistry.get_or_default("never_registered_999")
        assert isinstance(result, DefaultDomainPack)

    def test_get_or_default_returns_default_for_none(self):
        assert isinstance(DomainPackRegistry.get_or_default(None), DefaultDomainPack)
        assert isinstance(DomainPackRegistry.get_or_default(""), DefaultDomainPack)

    def test_register_rejects_empty_name(self):
        with pytest.raises(ValueError):
            DomainPackRegistry.register("", DefaultDomainPack())

    def test_re_register_replaces(self):
        pack_a = DefaultDomainPack()
        pack_b = DefaultDomainPack()
        DomainPackRegistry.register("synthetic_xyz", pack_a)
        DomainPackRegistry.register("synthetic_xyz", pack_b)
        assert DomainPackRegistry.get("synthetic_xyz") is pack_b


# ─────────────────────────────────────────────────────────────────────
# 3. Water pack regression — BYTE-IDENTICAL pre/post refactor
# ─────────────────────────────────────────────────────────────────────

class TestIrrigationDomainPackByteIdentical:
    """IrrigationDomainPack must produce byte-identical output to the
    pre-refactor IrrigationAdapter for every delegated method.

    Importance changes here would cascade to memory ranking and shift
    paper IBR/EHE numbers. This is the canary."""

    def setup_method(self):
        import examples.irrigation_abm  # noqa: F401 — registration side-effect
        from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
        self.pack = DomainPackRegistry.get_or_default("irrigation")
        self.inner = IrrigationAdapter()

    def test_pack_is_registered(self):
        assert self.pack.name == "irrigation"
        assert isinstance(self.pack, DomainPack)

    def test_importance_profiles_identical(self):
        assert self.pack.importance_profiles() == self.inner.importance_profiles

    def test_emotional_keywords_identical(self):
        assert self.pack.emotional_keywords() == self.inner.emotional_keywords

    def test_retrieval_weights_identical(self):
        assert self.pack.retrieval_weights() == self.inner.retrieval_weights

    @pytest.mark.parametrize("ctx", [
        {"supply_ratio": 0.5, "drought_count": 1, "recent_decision": "decrease_small", "water_right_pct": 0.6},
        {"supply_ratio": 0.95, "drought_count": 3, "recent_decision": "maintain_demand", "water_right_pct": 0.95},
        {"supply_ratio": 1.0, "drought_count": 0, "recent_decision": "maintain_demand", "water_right_pct": 0.5},
    ])
    def test_compute_importance_identical(self, ctx):
        assert self.pack.compute_importance(ctx) == self.inner.compute_importance(ctx)

    def test_classify_emotion_identical(self):
        for decision in ("increase_demand", "decrease_demand", "maintain_demand"):
            for supply in (0.4, 0.7, 1.0):
                ctx = {"supply_ratio": supply, "water_right_pct": 0.95}
                assert self.pack.classify_emotion(decision, ctx) == self.inner.classify_emotion(decision, ctx)

    def test_irrigation_skill_emotion_metadata_falls_through(self):
        """All irrigation skills get {} → broker uses routine 0.1
        default, matching pre-refactor experiment_runner.py:387 fall-
        through branch."""
        for skill in ("increase_small", "increase_large", "decrease_small",
                      "decrease_large", "maintain_demand"):
            assert self.pack.skill_emotion_metadata(skill) == {}, (
                f"Irrigation skill '{skill}' must not override default — would "
                f"shift memory tagging vs v21 baseline."
            )

    def test_irrigation_extreme_actions_empty(self):
        assert self.pack.extreme_actions() == set()

    def test_irrigation_event_handlers_empty(self):
        assert self.pack.event_handlers() == {}

    def test_irrigation_agent_impact_handlers_empty(self):
        assert self.pack.agent_impact_handlers() == {}

    def test_irrigation_memory_policy_is_none(self):
        # Phase 6K-A: irrigation domain has no memory-subsystem
        # overrides today; the inherited default of None keeps generic
        # behaviour.
        assert self.pack.memory_policy() is None

    def test_irrigation_drift_policy_empty(self):
        # Phase 6L-A: irrigation does not yet override DriftDetector
        # defaults; inherits the {} default.
        assert self.pack.drift_policy() == {}

    def test_irrigation_population_governance_policy_empty(self):
        # Phase 6L-B: irrigation does not yet override population-
        # governance defaults; inherits the {} default.
        assert self.pack.population_governance_policy() == {}

    def test_irrigation_policy_event_tiers_empty(self):
        # Phase 6L-C: irrigation does not yet override PolicyEvent
        # severity tiers; inherits the {} default.
        assert self.pack.policy_event_tiers() == {}

    def test_irrigation_bridge_importance_policy_empty(self):
        # Phase 6L-D: irrigation does not yet override MemoryBridge
        # resolution importance values; inherits the {} default.
        assert self.pack.bridge_importance_policy() == {}

    def test_irrigation_mg_barrier_text_empty(self):
        assert self.pack.mg_barrier_text({}) == ""


class TestFloodDomainPackByteIdentical:
    """FloodDomainPack must reproduce pre-refactor flood behaviour
    byte-for-byte. Verified against the literal values that lived at
    reflection.py:301-313, experiment_runner.py:383-388,
    ma_manager.py:275-289, providers.py:706-712, validator_bundles.py:87."""

    def setup_method(self):
        import examples.governed_flood  # noqa: F401 — registration side-effect
        from examples.governed_flood.adapters.flood_adapter import FloodAdapter
        self.pack = DomainPackRegistry.get_or_default("flood")
        self.inner = FloodAdapter()

    def test_pack_is_registered(self):
        assert self.pack.name == "flood"
        assert isinstance(self.pack, DomainPack)

    # Reflection status text — preserves reflection.py:301-313 exactly
    def test_reflection_status_text_household_only(self):
        class Ctx:
            agent_type = "irrigation_farmer"
            mg_status = False
            custom_traits = {"elevated": True, "insured": True, "flood_count": 3}
        assert self.pack.reflection_status_text(Ctx()) is None

    def test_reflection_status_text_household_with_no_flags(self):
        class Ctx:
            agent_type = "household"
            mg_status = False
            custom_traits = {}
        assert self.pack.reflection_status_text(Ctx()) is None

    def test_reflection_status_text_household_full(self):
        class Ctx:
            agent_type = "household"
            mg_status = True
            custom_traits = {"elevated": True, "insured": True, "flood_count": 2}
        out = self.pack.reflection_status_text(Ctx())
        # Same field ordering as pre-refactor (lines 303-310)
        assert out == (
            "Current status: your house is elevated, "
            "you have flood insurance, "
            "you've been flooded 2 time(s), "
            "you have limited resources."
        )

    def test_reflection_trait_labels(self):
        """Byte-identical to the pre-refactor batch traits block —
        short labels, `{n}x` form, append-if-truthy order."""
        class Full:
            agent_type = "household"
            mg_status = True
            custom_traits = {"elevated": True, "insured": True, "flood_count": 3}
        assert self.pack.reflection_trait_labels(Full()) == [
            "elevated", "insured", "flooded 3x", "MG",
        ]

        class Empty:
            agent_type = "household"
            mg_status = False
            custom_traits = {}
        assert self.pack.reflection_trait_labels(Empty()) == []

    # Skill emotion — reproduces experiment_runner.py:383-388 literals
    def test_elevate_house_emotion(self):
        assert self.pack.skill_emotion_metadata("elevate_house") == {
            "emotion": "major", "importance": 0.7, "source": "personal"
        }

    def test_relocate_emotion(self):
        assert self.pack.skill_emotion_metadata("relocate") == {
            "emotion": "major", "importance": 0.7, "source": "personal"
        }

    def test_buy_insurance_emotion(self):
        assert self.pack.skill_emotion_metadata("buy_insurance") == {
            "emotion": "positive", "importance": 0.6, "source": "personal"
        }

    def test_other_skills_fall_through(self):
        for skill in ("do_nothing", "buyout_program", "unknown_skill"):
            assert self.pack.skill_emotion_metadata(skill) == {}

    # Extreme actions — preserves validator_bundles.py:87 kwarg
    def test_extreme_actions(self):
        assert self.pack.extreme_actions() == {"relocate", "elevate_house"}

    def test_passthrough_agent_types(self):
        assert self.pack.passthrough_agent_types() == {"government", "insurance"}

    def test_affordability_constraints(self):
        spec = self.pack.affordability_constraints()
        assert set(spec) == {"elevate_house"}
        assert spec["elevate_house"]["base_cost"] == 150_000.0
        assert spec["elevate_house"]["income_multiplier"] == 3.0
        assert spec["elevate_house"]["default_subsidy_rate"] == 0.5

    # Phase 6P-B (2026-05-25) — phase_layout dispatch
    def test_phase_layout_returns_water_four_phase_order(self):
        from broker.interfaces.coordination import ExecutionPhase
        layout = self.pack.phase_layout()
        assert layout is not None
        assert len(layout) == 4
        phases = [pc.phase for pc in layout]
        assert phases == [
            ExecutionPhase.INSTITUTIONAL,
            ExecutionPhase.INDIVIDUAL,
            ExecutionPhase.RESOLUTION,
            ExecutionPhase.OBSERVATION,
        ]

    # Phase 6P-C (2026-05-25) — loader dispatch via DomainPack
    def test_csv_loader_class_returns_flood_csv_loader(self):
        from broker.domains.water.loaders import FloodCSVLoader
        assert self.pack.csv_loader_class() is FloodCSVLoader

    def test_synthetic_loader_class_returns_flood_synthetic_loader(self):
        from broker.domains.water.loaders import FloodSyntheticLoader
        assert self.pack.synthetic_loader_class() is FloodSyntheticLoader

    # Phase 6P-E (2026-05-25) added a
    # ``test_hazard_severity_thresholds_returns_flood_meter_values``
    # contract test here. Phase 6Q-B (2026-05-26) removed it when the
    # underlying ``DomainPack.hazard_severity_thresholds`` hook was
    # deleted (HazardEventGenerator relocated to the water namespace —
    # the thresholds now live alongside their consumer in
    # ``HazardEventConfig.severity_thresholds``).

    def test_flood_loaders_accept_canonical_constructor_kwargs(self):
        """Phase 6P-C code-reviewer #3 — the loader-dispatch contract
        promises the returned classes accept ``column_mappings=`` and
        ``seed=`` respectively. Pin that constructor signature so a
        future override does not silently break the dispatch."""
        import inspect
        csv_cls = self.pack.csv_loader_class()
        syn_cls = self.pack.synthetic_loader_class()
        csv_params = inspect.signature(csv_cls.__init__).parameters
        syn_params = inspect.signature(syn_cls.__init__).parameters
        assert "column_mappings" in csv_params, (
            f"{csv_cls.__name__}.__init__ must accept column_mappings="
        )
        assert "seed" in syn_params, (
            f"{syn_cls.__name__}.__init__ must accept seed="
        )

    # Event handlers — preserves ma_manager.py:275-289 chain
    def test_event_handlers_keys(self):
        assert set(self.pack.event_handlers().keys()) == {
            "flood", "no_flood", "subsidy_change", "premium_change"
        }

    def test_flood_handler_mutates_gs(self):
        class Event:
            data = {"occurred": True, "depth_m": 1.5, "depth_ft": 5.0}
        gs = {}
        self.pack.event_handlers()["flood"](Event(), gs)
        assert gs == {
            "flood_occurred": True,
            "flood_depth_m": 1.5,
            "flood_depth_ft": 5.0,
        }

    def test_no_flood_handler_resets_gs(self):
        class Event:
            data = {}
        gs = {"flood_occurred": True, "flood_depth_m": 2.0, "flood_depth_ft": 6.5}
        self.pack.event_handlers()["no_flood"](Event(), gs)
        assert gs == {
            "flood_occurred": False,
            "flood_depth_m": 0,
            "flood_depth_ft": 0,
        }

    def test_subsidy_change_handler_uses_default(self):
        class Event:
            data = {"new_value": 0.8}
            description = "Subsidy increased"
        gs = {}
        self.pack.event_handlers()["subsidy_change"](Event(), gs)
        assert gs["subsidy_rate"] == 0.8
        assert gs["govt_message"] == "Subsidy increased"

    # Agent-impact handlers — preserves the ma_manager.py get_agent_impact
    # flood event-type chain (Phase 6J-B)
    def test_agent_impact_handlers_keys(self):
        assert set(self.pack.agent_impact_handlers().keys()) == {
            "flood", "flood_damage", "insurance_payout"
        }

    def test_impact_flood_handler_aggregates_depth(self):
        class Event:
            data = {"depth_m": 0.4}
        handlers = self.pack.agent_impact_handlers()
        impact = {}
        handlers["flood"](Event(), impact)
        assert impact["flooded"] is True
        assert impact["depth_m"] == 0.4
        # A second, deeper event takes the max.
        class Deeper:
            data = {"depth_m": 0.9}
        handlers["flood"](Deeper(), impact)
        assert impact["depth_m"] == 0.9

    def test_impact_flood_damage_handler_sums(self):
        class Event:
            data = {"damage_amount": 25000, "oop_cost": 10000}
        handlers = self.pack.agent_impact_handlers()
        impact = {}
        handlers["flood_damage"](Event(), impact)
        handlers["flood_damage"](Event(), impact)
        assert impact["damage_amount"] == 50000
        assert impact["oop_cost"] == 20000

    def test_impact_insurance_payout_handler_sums(self):
        class Event:
            data = {"payout_amount": 15000}
        handlers = self.pack.agent_impact_handlers()
        impact = {}
        handlers["insurance_payout"](Event(), impact)
        assert impact["payout_amount"] == 15000

    # Memory policy — preserves the three flood literals previously
    # hardcoded in generic broker/components/memory/ (Phase 6K-A).
    def test_memory_policy_returns_bundle(self):
        bundle = self.pack.memory_policy()
        assert bundle is not None

    def test_memory_policy_category_rules_have_flood_keys(self):
        from broker.components.memory.content_types import MemoryContentType
        bundle = self.pack.memory_policy()
        assert bundle.category_rules["flood_experience"] is MemoryContentType.EXTERNAL_EVENT
        assert bundle.category_rules["flood_event"] is MemoryContentType.EXTERNAL_EVENT
        assert bundle.category_rules["damage"] is MemoryContentType.EXTERNAL_EVENT
        assert bundle.category_rules["insurance_claim"] is MemoryContentType.INITIAL_FACTUAL
        assert bundle.category_rules["insurance_history"] is MemoryContentType.INITIAL_FACTUAL

    def test_memory_policy_external_event_whitelist(self):
        bundle = self.pack.memory_policy()
        assert set(bundle.external_event_whitelist) == {
            "flood_experience", "flood_event", "damage",
        }

    def test_memory_policy_stimulus_key_is_flood_depth_m(self):
        bundle = self.pack.memory_policy()
        assert bundle.stimulus_key == "flood_depth_m"

    def test_drift_policy_inherits_default(self):
        # Phase 6L-A: flood domain does not yet override drift defaults;
        # inherits the {} default from DefaultDomainPack so DriftDetector
        # constructor defaults apply.
        assert self.pack.drift_policy() == {}

    def test_population_governance_policy_inherits_default(self):
        # Phase 6L-B: flood domain does not yet override population-
        # governance defaults; inherits the {} default so
        # CrossAgentValidator / CouncilValidator constructor defaults
        # apply.
        assert self.pack.population_governance_policy() == {}

    def test_policy_event_tiers_inherits_default(self):
        # Phase 6L-C: flood domain does not yet override PolicyEvent
        # severity-tier cutoffs; inherits the {} default so
        # PolicyEventConfig defaults (0.20 / 0.10 / 0.05) apply.
        assert self.pack.policy_event_tiers() == {}

    def test_bridge_importance_policy_inherits_default(self):
        # Phase 6L-D: flood domain does not yet override the MemoryBridge
        # asymmetric 0.6/0.75 default; the inline 'Denials are more
        # memorable' design rationale stays the documented choice.
        assert self.pack.bridge_importance_policy() == {}

    # MG barrier text — preserves providers.py:706-712 string
    def test_mg_barrier_text_contains_passaic(self):
        text = self.pack.mg_barrier_text({})
        assert "Passaic River Basin" in text
        assert "Insurance Enrollment Context" in text
        assert "NFIP" in text

    # Importance / emotion / retrieval — delegated to inner adapter
    def test_importance_profiles_delegated(self):
        assert self.pack.importance_profiles() == self.inner.importance_profiles

    def test_compute_importance_delegated(self):
        for ctx in (
            {"flood_count": 1},
            {"flood_count": 3, "mg_status": True},
            {"flood_count": 0, "mg_status": False, "recent_decision": "do_nothing"},
        ):
            assert self.pack.compute_importance(ctx) == self.inner.compute_importance(ctx)


# ─────────────────────────────────────────────────────────────────────
# 4. Hot-path callers consult the registry
# ─────────────────────────────────────────────────────────────────────

class TestHotPathsUseDomainPack:
    """Source-level check: the 5 broker hot-spot files refactored in
    Phase 6C-v2 import / call DomainPackRegistry. Guards against future
    edits silently re-introducing hardcoded if-domain branches.
    """

    @pytest.mark.parametrize("module_path", [
        "broker/components/cognitive/reflection.py",        # C3
        "broker/core/experiment_runner.py",                 # W2
        "broker/components/events/ma_manager.py",           # W5
        # Phase 6P-A (2026-05-25): the dispatcher relocated from
        # `broker/domains/water/validator_bundles.py` to a generic
        # address. The water-side file is now a 3-line backwards-compat
        # shim; the DomainPackRegistry hot-path lives in the new file.
        "broker/components/governance/domain_validator_dispatch.py",  # C5 (relocated)
        "broker/domains/water/providers.py",                # C2 (6H Item 7: FinancialCostProvider relocated to water)
    ])
    def test_module_imports_domain_pack_registry(self, module_path):
        with open(module_path, "r", encoding="utf-8") as f:
            source = f.read()
        assert "DomainPackRegistry" in source, (
            f"{module_path} no longer references DomainPackRegistry — "
            f"refactor may have regressed (Phase 6C-v2 hot-spot)."
        )


class TestAffordabilityValidation:
    """Phase 6H Item 6: AgentValidator.validate_affordability() reads the
    active DomainPack's affordability_constraints() — no hardcoded flood
    cost model. Flood byte-identical: $150k base, 50% subsidy default,
    affordable iff post-subsidy cost <= 3x income."""

    def setup_method(self):
        from broker.domains.registry import DomainPackRegistry
        self._saved_packs = dict(DomainPackRegistry._packs)
        import examples.governed_flood  # noqa: F401 — registers FloodDomainPack

    def teardown_method(self):
        from broker.domains.registry import DomainPackRegistry
        DomainPackRegistry.clear()
        for _name, _pack in self._saved_packs.items():
            DomainPackRegistry.register(_name, _pack)

    @staticmethod
    def _context(income):
        return {
            "agent_state": {"state": {"income": income, "subsidy_rate": 0.5}},
            "env_state": {},
        }

    def test_elevation_unaffordable_for_low_income(self):
        from broker.validators.agent.agent_validator import AgentValidator
        v = AgentValidator(enable_financial_constraints=True)
        # cost = 150000 * (1 - 0.5) = 75000; threshold = 10000 * 3 = 30000
        ok, reason = v.validate_affordability("a", "elevate_house", self._context(10_000))
        assert ok is False
        assert reason and "elevate_house" in reason

    def test_elevation_affordable_for_high_income(self):
        from broker.validators.agent.agent_validator import AgentValidator
        v = AgentValidator(enable_financial_constraints=True)
        ok, _ = v.validate_affordability("a", "elevate_house", self._context(100_000))
        assert ok is True

    def test_unconstrained_decision_passes(self):
        from broker.validators.agent.agent_validator import AgentValidator
        v = AgentValidator(enable_financial_constraints=True)
        # do_nothing is not in flood affordability_constraints -> no check
        ok, reason = v.validate_affordability("a", "do_nothing", self._context(1))
        assert ok is True and reason is None
