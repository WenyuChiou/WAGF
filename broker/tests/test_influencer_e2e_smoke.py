"""Phase 6T-F.4 (2026-05-29): influencer end-to-end mock smoke.

Proves the full social-channel chain for the social_media_influencer:

  seed FollowerNetwork (households follow the influencer)
    -> the influencer's accepted post-action becomes a Post in
       env.social_feeds via InfluencerLifecycleHandler.post_decision
    -> SocialMediaProvider renders that post into a FOLLOWING household's
       prompt context + audit trail
    -> a NON-follower household sees nothing (isolation)
    -> maintain_silence emits nothing.

No LLM (the decision is supplied directly) and NO paper-3 runner is touched
— this composes the broker pieces exactly as a 6T-F influencer-experiment
runner would, with mock data. Mirrors broker/tests/test_social_feeds_e2e_flag_on.py.
"""
from __future__ import annotations

from typing import Any, Dict

# Importing the example registers FloodDomainPack at import time.
import examples.governed_flood  # noqa: F401

from broker.components.context.providers import SocialMediaProvider
from broker.components.social.follower_network import FollowerNetwork
from broker.domains.registry import DomainPackRegistry
from broker.simulation.environment import TieredEnvironment

from examples.governed_flood.adapters.influencer_lifecycle import (
    InfluencerLifecycleHandler,
    seed_influencer_followers,
)


INFLUENCER_ID = "social_media_influencer_1"
FOLLOWERS = ["hh_001", "hh_002"]


def _influencer_agent():
    class _A:
        agent_id = INFLUENCER_ID
        agent_type = "social_media_influencer"
        dynamic_state = {
            "reasoning": "Severe flooding is spreading fast across the basin."
        }

    return _A()


def _household_agent(agent_id: str):
    class _A:
        pass

    a = _A()
    a.agent_id = agent_id
    a.agent_type = "household_owner"
    return a


def _wire(flag: bool = True):
    env = TieredEnvironment(
        global_state={"year": 2, "_social_feeds_enabled": flag}
    )
    env.domain = "flood"  # type: ignore[attr-defined]
    network = FollowerNetwork()
    seed_influencer_followers(network, INFLUENCER_ID, FOLLOWERS)
    return env, network


# ─────────────────────────────────────────────────────────────────────
# seeding helper
# ─────────────────────────────────────────────────────────────────────


class TestSeedInfluencerFollowers:
    def test_edges_added_both_directions(self):
        network = FollowerNetwork()
        n = seed_influencer_followers(network, INFLUENCER_ID, FOLLOWERS)
        assert n == 2
        assert set(network.get_followers(INFLUENCER_ID)) == set(FOLLOWERS)
        for hh in FOLLOWERS:
            assert INFLUENCER_ID in network.get_followed(hh)

    def test_self_follow_and_empty_skipped(self):
        network = FollowerNetwork()
        n = seed_influencer_followers(
            network, INFLUENCER_ID, [INFLUENCER_ID, "", "hh_001"]
        )
        assert n == 1
        assert set(network.get_followers(INFLUENCER_ID)) == {"hh_001"}


# ─────────────────────────────────────────────────────────────────────
# full chain: influencer post -> following household feed
# ─────────────────────────────────────────────────────────────────────


class TestInfluencerToHouseholdChain:
    def _provide(self, env, network, agent_id):
        pack = DomainPackRegistry.get("flood")
        provider = SocialMediaProvider(env, network, pack, top_k=5)
        ctx: Dict[str, Any] = {}
        provider.provide(agent_id, {agent_id: _household_agent(agent_id)}, ctx, year=2)
        return ctx

    def test_amplify_post_lands_in_env_feed(self):
        env, _ = _wire()
        InfluencerLifecycleHandler().post_decision(
            _influencer_agent(), "amplify_event", year=2, env=env
        )
        assert INFLUENCER_ID in env.social_feeds
        post = env.social_feeds[INFLUENCER_ID][0]
        assert post.event_type == "amplify_event"
        assert post.author_role == "influencer"

    def test_following_household_sees_influencer_post(self):
        env, network = _wire()
        InfluencerLifecycleHandler().post_decision(
            _influencer_agent(), "amplify_event", year=2, env=env
        )
        ctx = self._provide(env, network, "hh_001")

        feed = ctx.get("social_media_feed", "")
        assert feed, "following household must see a non-empty feed"
        lower = feed.lower()
        # the amplify template body surfaces ...
        assert "protecting your home" in lower
        # ... and the model's reasoning was woven into the post text
        assert "spreading fast" in lower
        assert ctx["_social_media_audit"], "audit trail must be populated"

    def test_non_follower_household_sees_nothing(self):
        env, network = _wire()
        InfluencerLifecycleHandler().post_decision(
            _influencer_agent(), "amplify_event", year=2, env=env
        )
        ctx = self._provide(env, network, "hh_orphan")
        assert ctx["social_media_feed"] == ""
        assert ctx["_social_media_audit"] == []

    def test_maintain_silence_emits_no_post(self):
        env, network = _wire()
        InfluencerLifecycleHandler().post_decision(
            _influencer_agent(), "maintain_silence", year=2, env=env
        )
        assert env.social_feeds == {}
        ctx = self._provide(env, network, "hh_001")
        assert ctx["social_media_feed"] == ""

    def test_handler_is_flag_agnostic(self):
        # The handler itself does NOT read ``_social_feeds_enabled`` — that
        # flag gates the EVENT-emission path (FloodEventMixin.emit_posts_for_event),
        # not the active influencer decision. So an amplify decision appends a
        # post even when the flag is off; turning the social channel on/off
        # for the influencer experiment is the runner's job (provider gating),
        # not this handler's. Asserting the post is appended documents that
        # separation.
        env, _ = _wire(flag=False)
        InfluencerLifecycleHandler().post_decision(
            _influencer_agent(), "amplify_event", year=2, env=env
        )
        assert INFLUENCER_ID in env.social_feeds
