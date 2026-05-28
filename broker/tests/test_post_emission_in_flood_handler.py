"""Phase 6T-E.B regression: FloodEventMixin Post auto-emission via
MAEventManager._sync_event_to_env hook.

Verifies:
- With the social_feeds flag OFF (default), zero Posts emitted. The
  byte-identity guard for paper-3 v21.
- With the flag ON, each global flood event_type emits 1-2 Posts
  with canonical_event_id metadata, correct tier_id, and the
  intended author_id / author_role.
- Posts are appended to TieredEnvironment.social_feeds via env.add_post.
- Original handler still mutates env.global_state correctly under
  both flag states (emission is additive, never replaces).
- Exception in emit_posts_for_event does NOT break dispatch.
"""
from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from broker.components.events.ma_manager import MAEventManager
from broker.domains.registry import DomainPackRegistry
from broker.interfaces.event_generator import (
    EnvironmentEvent,
    EventScope,
    EventSeverity,
)
from broker.simulation.environment import TieredEnvironment

# Importing examples/governed_flood registers the FloodDomainPack.
import examples.governed_flood  # noqa: F401


def _make_event(event_type: str, year: int = 1, **data: Any) -> EnvironmentEvent:
    return EnvironmentEvent(
        event_type=event_type,
        severity=EventSeverity.SEVERE,
        scope=EventScope.GLOBAL,
        description=f"{event_type} test event year {year}",
        data=data,
        affected_agents=[],
        domain="flood",
    )


@pytest.fixture
def env_with_domain():
    """A TieredEnvironment with the flood domain registered for
    dispatcher resolution."""
    env = TieredEnvironment(global_state={"year": 1})
    env.domain = "flood"  # type: ignore[attr-defined]
    return env


@pytest.fixture
def manager_with_flood():
    """An MAEventManager where _resolve_handler will route flood
    events through FloodDomainPack. We don't need to register any
    generators — we directly call _sync_event_to_env."""
    return MAEventManager()


# ---------------------------------------------------------------------------
# Flag OFF — paper-3 byte-identity guard
# ---------------------------------------------------------------------------


class TestFlagOff:
    def test_flag_off_emits_zero_posts(self, env_with_domain, manager_with_flood):
        """No social-feeds-enabled flag in env.global_state → zero
        emission. The hook STILL runs but the pack short-circuits."""
        evt = _make_event("subsidy_change", new_value=0.7)

        manager_with_flood._sync_event_to_env(env_with_domain, evt)

        assert env_with_domain.social_feeds == {}, (
            f"flag OFF should not emit posts; got {env_with_domain.social_feeds}"
        )
        # Original handler still ran — subsidy_rate updated
        assert env_with_domain.global_state["subsidy_rate"] == 0.7

    def test_flag_off_explicit_false(self, env_with_domain, manager_with_flood):
        """Explicit ``_social_feeds_enabled: False`` matches absent."""
        env_with_domain.global_state["_social_feeds_enabled"] = False
        evt = _make_event("flood", year=2, depth_ft=5)
        manager_with_flood._sync_event_to_env(env_with_domain, evt)
        assert env_with_domain.social_feeds == {}


# ---------------------------------------------------------------------------
# Flag ON — emission behavior
# ---------------------------------------------------------------------------


class TestFlagOn:
    @pytest.fixture(autouse=True)
    def _enable_feeds(self, env_with_domain):
        env_with_domain.global_state["_social_feeds_enabled"] = True

    def test_subsidy_change_emits_official_post(self, env_with_domain, manager_with_flood):
        evt = _make_event("subsidy_change", year=1, new_value=0.8)
        manager_with_flood._sync_event_to_env(env_with_domain, evt)

        assert "nj_government" in env_with_domain.social_feeds
        posts = env_with_domain.social_feeds["nj_government"]
        assert len(posts) == 1
        p = posts[0]
        assert p.tier_id == "official_authority"
        assert p.author_role == "government"
        assert p.event_type == "subsidy_change"
        assert "canonical_event_id" in p.metadata
        assert p.metadata["canonical_event_id"].startswith("subsidy_change:")

    def test_premium_change_emits_verified_post(self, env_with_domain, manager_with_flood):
        # Pack reads simulation year from env.global_state["year"] —
        # mimic the MA runner setting it at the start of year 2.
        env_with_domain.global_state["year"] = 2
        evt = _make_event("premium_change", new_value=0.04)
        manager_with_flood._sync_event_to_env(env_with_domain, evt)

        assert "fema_nfip" in env_with_domain.social_feeds
        post = env_with_domain.social_feeds["fema_nfip"][0]
        assert post.tier_id == "verified_account"
        assert post.author_role == "insurance"
        assert post.event_year == 2

    def test_flood_emits_two_posts_official_and_peer(self, env_with_domain, manager_with_flood):
        evt = _make_event("flood", year=3, depth_ft=6, depth_m=1.8)
        manager_with_flood._sync_event_to_env(env_with_domain, evt)

        # Government official + peer residents
        assert "nj_government" in env_with_domain.social_feeds
        assert "peer_residents" in env_with_domain.social_feeds

        gov_post = env_with_domain.social_feeds["nj_government"][0]
        peer_post = env_with_domain.social_feeds["peer_residents"][0]

        assert gov_post.tier_id == "official_authority"
        assert peer_post.tier_id == "peer_post"
        # Both reference the same canonical_event_id so 6T-G dedup
        # can join them across channels.
        assert gov_post.metadata["canonical_event_id"] == peer_post.metadata["canonical_event_id"]

    def test_no_flood_emits_official_only(self, env_with_domain, manager_with_flood):
        evt = _make_event("no_flood", year=4)
        manager_with_flood._sync_event_to_env(env_with_domain, evt)

        # Only government — no peer post for "no_flood"
        assert "nj_government" in env_with_domain.social_feeds
        assert "peer_residents" not in env_with_domain.social_feeds


# ---------------------------------------------------------------------------
# Dispatch-safety: emit failure doesn't break the event pipeline
# ---------------------------------------------------------------------------


class TestDispatchSafety:
    def test_emit_exception_does_not_propagate(self, env_with_domain, manager_with_flood):
        """If the pack's emit_posts_for_event raises, the dispatcher
        catches and continues. Same safety pattern as the handler
        try/except."""
        env_with_domain.global_state["_social_feeds_enabled"] = True
        evt = _make_event("subsidy_change", year=1, new_value=0.7)

        # Patch emit on the registered FloodDomainPack
        pack = DomainPackRegistry.get("flood")
        with patch.object(type(pack), "emit_posts_for_event",
                          side_effect=RuntimeError("simulated emit failure")):
            # Should NOT raise — dispatcher catches the exception
            manager_with_flood._sync_event_to_env(env_with_domain, evt)

        # Original handler still mutated env.global_state
        assert env_with_domain.global_state["subsidy_rate"] == 0.7
        # No posts because the emission failed (silently logged)
        assert env_with_domain.social_feeds == {}

    def test_pack_without_emit_method_works(self, env_with_domain, manager_with_flood):
        """A pack that hasn't implemented emit_posts_for_event is
        gracefully skipped (no AttributeError)."""
        # Even with flag ON, if hook is missing the dispatcher just
        # doesn't emit. We simulate by temporarily deleting the method
        # via a patch.
        env_with_domain.global_state["_social_feeds_enabled"] = True
        pack = DomainPackRegistry.get("flood")

        with patch.object(type(pack), "emit_posts_for_event", create=False, new=None):
            # patch.object with new=None deletes the attribute lookup
            evt = _make_event("subsidy_change", year=1, new_value=0.7)
            manager_with_flood._sync_event_to_env(env_with_domain, evt)

        # No crash; handler still ran
        assert env_with_domain.global_state["subsidy_rate"] == 0.7
