"""Phase 6T-F.2 (2026-05-29): social_media_influencer lifecycle handler tests.

Pins the contract for the SECOND concrete consumer of the Phase 6T-C
``InstitutionalLifecycleHandler`` extension point:

1. ``post_decision`` turns each post-action skill into a Post appended to
   the environment's ``social_feeds`` via ``env.add_post``.
2. ``maintain_silence`` (and any unmapped skill) emits NO post.
3. The handler is no-crash when ``env`` lacks a callable ``add_post``
   (the 6T-F.4 runner wiring is not in scope here).
4. The influencer is registered on the flood pack via
   ``FloodSetupMixin.institutional_lifecycle_handlers`` (government /
   insurance are NOT — they stay in MultiAgentHooks).
5. The execution-phase contract places the influencer after the
   institutional phases and before the household phase.
"""
from __future__ import annotations

from types import SimpleNamespace

# Importing the example package registers FloodDomainPack at import time.
import examples.governed_flood  # noqa: F401

from broker.components.orchestration.institutional_lifecycle import (
    InstitutionalLifecycleHandler,
)
from broker.components.social.post import Post
from broker.domains.registry import DomainPackRegistry
from broker.simulation.environment import TieredEnvironment

from examples.governed_flood.adapters.influencer_lifecycle import (
    INFLUENCER_AUTHOR_ROLE,
    INFLUENCER_PHASE_ORDER,
    INFLUENCER_TIER_ID,
    InfluencerLifecycleHandler,
    insert_influencer_phase,
)


POST_ACTIONS = ["amplify_event", "post_counter_narrative", "share_success_story"]


def _agent(agent_id="inf_1", **dynamic_state):
    return SimpleNamespace(
        agent_id=agent_id,
        agent_type="social_media_influencer",
        dynamic_state=dict(dynamic_state),
    )


# ─────────────────────────────────────────────────────────────────────
# post_decision -> env.add_post
# ─────────────────────────────────────────────────────────────────────


class TestPostDecisionEmitsPost:
    def test_is_institutional_lifecycle_handler(self):
        assert isinstance(
            InfluencerLifecycleHandler(), InstitutionalLifecycleHandler
        )

    def test_each_post_action_appends_one_post(self):
        for skill in POST_ACTIONS:
            env = TieredEnvironment()
            handler = InfluencerLifecycleHandler()
            handler.post_decision(_agent(), skill, year=3, env=env)

            posts = env.social_feeds.get("inf_1", [])
            assert len(posts) == 1, f"{skill} should emit exactly one post"
            post = posts[0]
            assert isinstance(post, Post)
            assert post.author_id == "inf_1"
            assert post.author_role == INFLUENCER_AUTHOR_ROLE
            assert post.tier_id == INFLUENCER_TIER_ID
            assert post.event_year == 3
            assert post.event_type == skill
            assert post.metadata["narrative_action"] == skill
            assert post.text  # non-empty

    def test_post_text_differs_per_action(self):
        texts = set()
        for skill in POST_ACTIONS:
            env = TieredEnvironment()
            InfluencerLifecycleHandler().post_decision(
                _agent(), skill, year=1, env=env
            )
            texts.add(env.social_feeds["inf_1"][0].text)
        assert len(texts) == len(POST_ACTIONS)

    def test_reasoning_enriches_post_text_when_present(self):
        env = TieredEnvironment()
        agent = _agent(reasoning="Severe flooding hit the east tracts.")
        InfluencerLifecycleHandler().post_decision(
            agent, "amplify_event", year=2, env=env
        )
        text = env.social_feeds["inf_1"][0].text
        assert "Severe flooding hit the east tracts." in text

    def test_post_text_falls_back_to_template_without_reasoning(self):
        env = TieredEnvironment()
        InfluencerLifecycleHandler().post_decision(
            _agent(), "amplify_event", year=2, env=env
        )
        # No reasoning slot -> text is exactly the template (no dangling space).
        text = env.social_feeds["inf_1"][0].text
        assert text == text.strip()
        assert text


# ─────────────────────────────────────────────────────────────────────
# silence / unmapped / missing add_post
# ─────────────────────────────────────────────────────────────────────


class TestNoPostCases:
    def test_maintain_silence_emits_no_post(self):
        env = TieredEnvironment()
        InfluencerLifecycleHandler().post_decision(
            _agent(), "maintain_silence", year=1, env=env
        )
        assert env.social_feeds == {}

    def test_unmapped_skill_emits_no_post(self):
        env = TieredEnvironment()
        InfluencerLifecycleHandler().post_decision(
            _agent(), "buy_insurance", year=1, env=env
        )
        assert env.social_feeds == {}

    def test_env_without_add_post_is_noop_not_crash(self):
        # A bare dict (the ABC's nominal env type) has no add_post — the
        # handler must not raise (6T-F.4 wires the real TieredEnvironment).
        handler = InfluencerLifecycleHandler()
        handler.post_decision(_agent(), "amplify_event", year=1, env={})
        # Reaching here without an exception is the assertion.


# ─────────────────────────────────────────────────────────────────────
# registration on the flood pack
# ─────────────────────────────────────────────────────────────────────


class TestFloodPackRegistration:
    def test_flood_pack_registers_influencer_handler(self):
        pack = DomainPackRegistry.get_setup_pack("flood")
        handlers = pack.institutional_lifecycle_handlers()
        assert "social_media_influencer" in handlers
        assert isinstance(
            handlers["social_media_influencer"], InfluencerLifecycleHandler
        )

    def test_flood_pack_does_not_register_gov_or_insurance(self):
        # Government / insurance lifecycle stays in MultiAgentHooks — the
        # extension point intentionally carries only the influencer until
        # the deferred extraction.
        handlers = DomainPackRegistry.get_setup_pack(
            "flood"
        ).institutional_lifecycle_handlers()
        assert "government" not in handlers
        assert "insurance" not in handlers


# ─────────────────────────────────────────────────────────────────────
# execution-phase ordering contract
# ─────────────────────────────────────────────────────────────────────


def _flat_index(order, agent_type):
    for i, phase in enumerate(order):
        if agent_type in phase:
            return i
    raise AssertionError(f"{agent_type} not in phase order {order}")


class TestPhaseOrdering:
    def test_constant_places_influencer_after_institutions_before_households(self):
        inf = _flat_index(INFLUENCER_PHASE_ORDER, "social_media_influencer")
        assert inf > _flat_index(INFLUENCER_PHASE_ORDER, "government")
        assert inf > _flat_index(INFLUENCER_PHASE_ORDER, "insurance")
        assert inf < _flat_index(INFLUENCER_PHASE_ORDER, "household_owner")
        assert inf < _flat_index(INFLUENCER_PHASE_ORDER, "household_renter")

    def test_insert_helper_slots_influencer_before_first_household_phase(self):
        base = [["government"], ["insurance"], ["household_owner", "household_renter"]]
        out = insert_influencer_phase(base)
        assert out == [
            ["government"],
            ["insurance"],
            ["social_media_influencer"],
            ["household_owner", "household_renter"],
        ]

    def test_insert_helper_preserves_other_phases_and_inserts_once(self):
        base = [["government"], ["household_owner"], ["insurance"]]
        out = insert_influencer_phase(base)
        # Influencer inserted before the first household phase, exactly once;
        # the trailing institutional phase is preserved as-is.
        assert out == [
            ["government"],
            ["social_media_influencer"],
            ["household_owner"],
            ["insurance"],
        ]
        flat = [a for phase in out for a in phase]
        assert flat.count("social_media_influencer") == 1

    def test_insert_helper_appends_when_no_household_phase(self):
        base = [["government"], ["insurance"]]
        out = insert_influencer_phase(base)
        assert out[-1] == ["social_media_influencer"]
        flat = [a for phase in out for a in phase]
        assert flat.count("social_media_influencer") == 1

    def test_insert_helper_is_idempotent(self):
        # Re-entrant call must not insert a second influencer phase (which
        # would fire the agent twice per year).
        base = [["government"], ["insurance"], ["household_owner", "household_renter"]]
        once = insert_influencer_phase(base)
        twice = insert_influencer_phase(once)
        assert once == twice
        flat = [a for phase in twice for a in phase]
        assert flat.count("social_media_influencer") == 1
