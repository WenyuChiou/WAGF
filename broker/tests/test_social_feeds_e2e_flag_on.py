"""Phase 6T-E.B v0.5.1 end-to-end behavioral test (flag ON).

Verifies the v0.5.1 wire goes through cleanly:

* TieredEnvironment.social_feeds populates via FloodEventMixin.emit_posts_for_event
  when the env-state flag is True.
* SocialMediaProvider reads env.social_feeds + uses FollowerNetwork to
  filter authors + renders the section block into the context dict.
* The rendered ``context["social_media_feed"]`` non-empty when the
  flag is ON and at least one followed author has posted.

This is a unit-style integration test (no LLM, no full experiment
loop) — it exercises the data path from event dispatch through
provider rendering to confirm the v0.5.1 wiring is sound.
"""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from broker.components.context.providers import SocialMediaProvider
from broker.components.events.ma_manager import MAEventManager
from broker.components.social.follower_network import FollowerNetwork
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventScope,
    EventSeverity,
)
from broker.simulation.environment import TieredEnvironment
from broker.domains.registry import DomainPackRegistry

# Importing examples/governed_flood registers FloodDomainPack.
import examples.governed_flood  # noqa: F401


def _make_subsidy_event(year: int, new_value: float) -> EnvironmentEvent:
    return EnvironmentEvent(
        event_type="subsidy_change",
        severity=EventSeverity.MODERATE,
        scope=EventScope.GLOBAL,
        description=f"Subsidy rate update for year {year}: now {new_value:.0%}",
        data={"new_value": new_value},
        affected_agents=[],
        domain="flood",
    )


def _make_household_agent(agent_id: str, agent_type: str = "household_owner") -> Any:
    class _Agent:
        id = agent_id
    agent = _Agent()
    agent.agent_type = agent_type  # type: ignore[attr-defined]
    return agent


@pytest.fixture
def wired_env_flag_on():
    """A TieredEnvironment + FollowerNetwork wired exactly like
    run_unified_experiment.py does it when the flag is ON."""
    env = TieredEnvironment(global_state={"year": 1, "_social_feeds_enabled": True})
    env.domain = "flood"  # type: ignore[attr-defined]

    network = FollowerNetwork()
    for hh_id in ("hh_001", "hh_002"):
        for author in ("nj_government", "fema_nfip", "peer_residents"):
            network.add_edge(author_id=author, follower_id=hh_id)
    return env, network


def test_event_dispatch_populates_env_social_feeds(wired_env_flag_on):
    """End-to-end: a subsidy_change event flows through the
    dispatcher and lands as a Post in env.social_feeds."""
    env, _network = wired_env_flag_on
    manager = MAEventManager()
    evt = _make_subsidy_event(year=1, new_value=0.7)

    manager._sync_event_to_env(env, evt)

    # FloodEventMixin emits one Post for subsidy_change (nj_government author)
    assert "nj_government" in env.social_feeds
    post = env.social_feeds["nj_government"][0]
    assert post.tier_id == "official_authority"
    assert post.event_type == "subsidy_change"
    assert post.event_year == 1
    # Canonical event id present + well-formed
    assert post.metadata["canonical_event_id"].startswith("subsidy_change:1:")


def test_provider_renders_populated_feed_for_household(wired_env_flag_on):
    """End-to-end: with social_feeds populated + follower network
    wired, SocialMediaProvider produces the section block in the
    rendered context."""
    env, network = wired_env_flag_on
    manager = MAEventManager()

    # Emit events to populate social_feeds
    manager._sync_event_to_env(env, _make_subsidy_event(year=1, new_value=0.7))
    env.global_state["year"] = 2
    manager._sync_event_to_env(env, _make_subsidy_event(year=2, new_value=0.5))

    # Render context for a household
    pack = DomainPackRegistry.get("flood")
    provider = SocialMediaProvider(env, network, pack, top_k=5)
    agent = _make_household_agent("hh_001")
    ctx: Dict[str, Any] = {}
    provider.provide("hh_001", {"hh_001": agent}, ctx, year=2)

    feed = ctx.get("social_media_feed", "")
    # Section block format: \n\n## Social media (recent posts):\n- ...
    assert feed.startswith("\n\n## Social media (recent posts):\n"), (
        f"feed missing section header; got: {feed!r}"
    )
    # Both subsidy events surface as posts
    assert "subsidy" in feed.lower(), f"subsidy text missing in feed: {feed!r}"
    # Audit trail populated
    audit: List[Any] = ctx["_social_media_audit"]
    assert len(audit) >= 1


def test_non_follower_sees_empty_feed(wired_env_flag_on):
    """Agents NOT in the follower network see no posts even when
    env.social_feeds is populated. Critical isolation property."""
    env, network = wired_env_flag_on
    manager = MAEventManager()
    manager._sync_event_to_env(env, _make_subsidy_event(year=1, new_value=0.7))

    pack = DomainPackRegistry.get("flood")
    provider = SocialMediaProvider(env, network, pack, top_k=5)

    # A new household NOT registered in the follower network
    agent = _make_household_agent("hh_orphan")
    ctx: Dict[str, Any] = {}
    provider.provide("hh_orphan", {"hh_orphan": agent}, ctx, year=1)

    assert ctx["social_media_feed"] == ""
    assert ctx["_social_media_audit"] == []


def test_flag_off_path_empty_feed(wired_env_flag_on):
    """With _social_feeds_enabled=False, FloodEventMixin emits zero
    posts → env.social_feeds stays empty → provider writes ""."""
    env, network = wired_env_flag_on
    env.global_state["_social_feeds_enabled"] = False

    manager = MAEventManager()
    manager._sync_event_to_env(env, _make_subsidy_event(year=1, new_value=0.7))

    # Critical: env.social_feeds must stay empty (FloodEventMixin
    # short-circuited; the dispatcher's post-emission hook fed
    # nothing to env.add_post).
    assert env.social_feeds == {}

    pack = DomainPackRegistry.get("flood")
    provider = SocialMediaProvider(env, network, pack, top_k=5)
    agent = _make_household_agent("hh_001")
    ctx: Dict[str, Any] = {}
    provider.provide("hh_001", {"hh_001": agent}, ctx, year=1)

    assert ctx["social_media_feed"] == ""
