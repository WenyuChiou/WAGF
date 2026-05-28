"""Phase 6R-D-1 regression — DomainPack sub-protocol structure.

Pins the 7-sub-protocol split of ``broker.domains.protocol.DomainPack``.
Each sub-protocol owns a cohesive method group; the composite
``DomainPack`` inherits from all 7.

Test goals:
1. All 7 sub-protocol names export from ``broker.domains.protocol``.
2. Each sub-protocol declares exactly the methods it owns (per the
   ``.research/domain_pack_protocol_reference.md`` audit).
3. ``DomainPack`` inherits from all 7 in MRO.
4. A concrete pack (FloodDomainPack via the registered example) satisfies
   each sub-protocol's ``isinstance`` check (runtime_checkable Protocol).
5. The composite preserves the 32-method surface — no method was
   accidentally dropped during the split.
"""
from __future__ import annotations

from typing import get_type_hints

import pytest

from broker.domains.protocol import (
    DomainPack,
    EventPack,
    GovernancePack,
    MemoryPack,
    PerceptionPack,
    ReflectionPack,
    SetupPack,
    SkillPack,
)


# ---------------------------------------------------------------------------
# Per-sub-protocol method-ownership pinning
# ---------------------------------------------------------------------------

class TestSubProtocolMethodOwnership:
    """Each sub-protocol declares exactly the methods listed in its
    docstring. The ownership map is the load-bearing contract for the
    split — Phase 6R-D-4 (consumer migration) types its kwargs against
    these sub-protocols, so the method-set MUST be stable.
    """

    EXPECTED_METHODS = {
        ReflectionPack: {
            "reflection_status_text",
            "reflection_questions",
            "reflection_persona",
            "reflection_trait_labels",
        },
        MemoryPack: {
            "importance_profiles",
            "compute_importance",
            "classify_emotion",
            "emotional_keywords",
            "retrieval_weights",
            "memory_policy",
        },
        SkillPack: {
            "skill_emotion_metadata",
            "extreme_actions",
            "action_taxonomy",
            "affordability_constraints",
        },
        EventPack: {
            "event_handlers",
            "agent_impact_handlers",
            # Phase 6T-A (2026-05-27) additions — dispatch safety +
            # event lifecycle policy hooks. See
            # broker/components/events/exceptions.py for rationale.
            "event_type_to_domain",
            "event_persistence_policy",
            "silent_skip_event_types",
        },
        PerceptionPack: {
            "perception_descriptors",
            "perception_field_policy",
            "passthrough_agent_types",
            # Phase 6T-E (2026-05-27) additions — social-media tier
            # vocabulary + verbalisation + per-agent filter. Per the
            # audit at .research/social_media_genericity_audit.md the
            # tier vocabulary lives in the DomainPack (not in broker/).
            "credibility_tiers",
            "credibility_weight",
            "verbalise_post",
            "suppressed_tiers",
            "social_media_post_filter",
            # Phase 6T-E.B (2026-05-28) addition — pack-level default
            # for the SocialMediaProvider feature flag. The flag
            # resolver in broker/components/social/feed_flag.py
            # consults YAML first; if absent, falls back to this.
            "social_feeds_default_enabled",
        },
        GovernancePack: {
            "psychological_framework",
            # Phase 6T-B (2026-05-27) addition — per-agent-type
            # framework selector. Closes engineering-audit Y6 by
            # routing household / government / insurance decisions
            # to PMT / utility / financial respectively.
            "framework_for_agent_type",
            "builtin_checks",
            "retrieval_policy",
            "drift_policy",
            "population_governance_policy",
            "policy_event_tiers",
            "bridge_importance_policy",
            "prompt_placeholder_extensions",
        },
        SetupPack: {
            "csv_loader_class",
            "synthetic_loader_class",
            "phase_layout",
            "initial_memory_templates",
            "mg_barrier_text",
            # Phase 6T-C (2026-05-27) additions — institutional
            # lifecycle dispatch extension point + env-key whitelist.
            # Closes R5+R6 as an extension point; actual extraction
            # of bespoke flood code deferred to Phase 6T-F.
            "institutional_lifecycle_handlers",
            "multi_agent_env_keys",
        },
    }

    def _declared_methods(self, protocol_cls):
        """Methods declared directly on the class (not inherited)."""
        return {
            name for name, value in vars(protocol_cls).items()
            if callable(value) and not name.startswith("_")
        }

    @pytest.mark.parametrize(
        "sub_protocol, expected",
        list(EXPECTED_METHODS.items()),
        ids=lambda v: v.__name__ if hasattr(v, "__name__") else str(v),
    )
    def test_sub_protocol_declares_expected_methods(self, sub_protocol, expected):
        declared = self._declared_methods(sub_protocol)
        assert declared == expected, (
            f"{sub_protocol.__name__} method-set drift: "
            f"declared={sorted(declared)} expected={sorted(expected)}"
        )

    def test_total_method_count_is_44(self):
        """Sanity check: union of all 7 sub-protocol method-sets is 44 —
        the original 32 (per ``.research/domain_pack_protocol_reference.md``)
        plus 3 Phase 6T-A EventPack additions
        (``event_type_to_domain``, ``event_persistence_policy``,
        ``silent_skip_event_types``) plus 1 Phase 6T-B GovernancePack
        addition (``framework_for_agent_type``) plus 2 Phase 6T-C
        SetupPack additions (``institutional_lifecycle_handlers``,
        ``multi_agent_env_keys``) plus 5 Phase 6T-E PerceptionPack
        additions (``credibility_tiers``, ``credibility_weight``,
        ``verbalise_post``, ``suppressed_tiers``,
        ``social_media_post_filter``) plus 1 Phase 6T-E.B PerceptionPack
        addition (``social_feeds_default_enabled``)."""
        total = sum(len(s) for s in self.EXPECTED_METHODS.values())
        assert total == 44

    def test_no_method_belongs_to_two_sub_protocols(self):
        """Critical invariant — each method has exactly ONE sub-protocol
        home. The consumer-disjointness audit (Agent 1's Phase 6R
        Section 2) confirmed this; a method appearing in two would
        cause type-narrowing ambiguity post-6R-D-4."""
        seen = {}
        for sub_proto, methods in self.EXPECTED_METHODS.items():
            for m in methods:
                assert m not in seen, (
                    f"method {m!r} declared in both "
                    f"{seen[m].__name__} and {sub_proto.__name__}"
                )
                seen[m] = sub_proto


# ---------------------------------------------------------------------------
# Composite — DomainPack inheritance
# ---------------------------------------------------------------------------

class TestCompositeInheritance:
    def test_DomainPack_inherits_from_all_7_sub_protocols(self):
        mro_names = [c.__name__ for c in DomainPack.__mro__]
        for sub_name in (
            "ReflectionPack",
            "MemoryPack",
            "SkillPack",
            "EventPack",
            "PerceptionPack",
            "GovernancePack",
            "SetupPack",
        ):
            assert sub_name in mro_names, (
                f"{sub_name} missing from DomainPack MRO: {mro_names}"
            )

    def test_DomainPack_preserves_all_32_methods(self):
        """The composite must expose every method from every
        sub-protocol — confirms no method was accidentally orphaned
        during the split."""
        expected_methods = set()
        for methods in TestSubProtocolMethodOwnership.EXPECTED_METHODS.values():
            expected_methods.update(methods)
        actual = {
            name for name in dir(DomainPack)
            if not name.startswith("_") and callable(getattr(DomainPack, name))
        }
        missing = expected_methods - actual
        assert not missing, f"DomainPack missing methods after split: {missing}"


# ---------------------------------------------------------------------------
# runtime_checkable — registered packs satisfy each sub-protocol
# ---------------------------------------------------------------------------

class TestRegisteredPacksSatisfySubProtocols:
    """The concrete example packs must satisfy each sub-protocol via
    Python's ``isinstance`` (runtime_checkable Protocol). This is the
    structural guarantee that consumers using narrowed types
    (``ReflectionPack`` instead of ``DomainPack``) will accept the
    same concrete packs."""

    @pytest.fixture(autouse=True)
    def _register_flood(self):
        import examples.governed_flood  # noqa: F401

    @pytest.mark.parametrize(
        "sub_protocol",
        [
            ReflectionPack, MemoryPack, SkillPack, EventPack,
            PerceptionPack, GovernancePack, SetupPack,
        ],
        ids=lambda c: c.__name__,
    )
    def test_flood_pack_satisfies(self, sub_protocol):
        from broker.domains.registry import DomainPackRegistry
        pack = DomainPackRegistry.get("flood")
        assert pack is not None, "FloodDomainPack not registered"
        assert isinstance(pack, sub_protocol), (
            f"FloodDomainPack does not satisfy {sub_protocol.__name__}"
        )

    def test_flood_pack_satisfies_composite(self):
        from broker.domains.registry import DomainPackRegistry
        pack = DomainPackRegistry.get("flood")
        assert isinstance(pack, DomainPack)
