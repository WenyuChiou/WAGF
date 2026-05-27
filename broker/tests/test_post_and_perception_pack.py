"""
Phase 6T-E tests for the generic ``Post`` dataclass + the five
audit-mandated additions to :class:`PerceptionPack`.

Verifies:

- :class:`Post` field shape + bounded-numeric validation
- :func:`age_weight` decay arithmetic + future-year guard
- ``DefaultDomainPack`` defaults for the 5 new methods:
  ``credibility_tiers`` (empty), ``credibility_weight``
  (1.0 known / 0.0 unknown), ``verbalise_post`` (debug format),
  ``suppressed_tiers`` (empty), ``social_media_post_filter``
  (passthrough)
- A custom pack overriding all five methods to demonstrate the
  audit-locked design (tier vocabulary is pack-provided, NOT
  broker-hardcoded)
- Post module's genericity: AST-scan + the new
  ``TestNoUSMediaTierLiteralsInBrokerSocial`` gate covers this
  centrally; this file adds a focused module-level check

Per the audit at ``.research/social_media_genericity_audit.md``,
the Post dataclass uses ``tier_id: str`` (NOT an enum). The tier
vocabulary lives in the DomainPack's ``credibility_tiers``.

Inline-mock-pack budget: stays under the ≤3 invariant by using a
single multi-purpose ``_DemoPack``.

Plan: ``~/.claude/plans/swirling-knitting-lighthouse.md`` 6T-E
interface-opening commit.
"""
from __future__ import annotations

from typing import Any, List, Optional, Set

import pytest

from broker.components.social.post import Post, age_weight
from broker.domains.default import DefaultDomainPack
from broker.domains.protocol import PerceptionPack


# ─────────────────────────────────────────────────────────────────────
# Fixture pack (under ≤3 inline-mock-pack invariant)
# ─────────────────────────────────────────────────────────────────────


class _DemoPack(DefaultDomainPack):
    """Multi-purpose demo pack covering every test concern: tier
    vocabulary, credibility weight mapping, verbalisation, tier
    suppression, per-agent filter."""

    name = "demopack"

    def credibility_tiers(self) -> List[str]:
        # Deliberately non-flood vocabulary to prove the pack-side
        # ownership: a future vaccination_ma can declare its own.
        return ["medical_authority", "clinician", "community", "rumor"]

    def credibility_weight(self, tier_id: str) -> float:
        return {
            "medical_authority": 1.0,
            "clinician": 0.85,
            "community": 0.5,
            "rumor": 0.2,
        }.get(tier_id, 0.0)

    def verbalise_post(self, post: Any) -> str:
        templates = {
            "medical_authority": "Health authority reports: {text}",
            "clinician": "A clinician posted: {text}",
            "community": "A community member shared: {text}",
            "rumor": "Unverified rumor: {text}",
        }
        template = templates.get(post.tier_id, "{text}")
        return template.format(text=post.text)

    def suppressed_tiers(self) -> Set[str]:
        return {"rumor"}

    def social_media_post_filter(self, agent: Any, post: Any) -> Optional[Any]:
        # Demo: an "anti-rumor" agent (with attribute `distrusts_rumor`)
        # drops rumor-tier posts entirely.
        if (getattr(agent, "distrusts_rumor", False)
                and post.tier_id == "rumor"):
            return None
        return post


# ─────────────────────────────────────────────────────────────────────
# Class 1 — Post dataclass shape + validation
# ─────────────────────────────────────────────────────────────────────


class TestPostDataclass:
    """Post is a generic envelope — bounded-numeric validation
    rejects pathological inputs, other fields are free-form."""

    def test_construct_with_minimal_args(self):
        post = Post(
            text="hello",
            author_id="AUTH_X",
            author_role="influencer",
            event_year=3,
            event_type="general",
        )
        assert post.text == "hello"
        assert post.engagement_score == 0.0
        assert post.tier_id == ""
        assert post.metadata == {}

    def test_construct_with_all_fields(self):
        post = Post(
            text="A flood is coming",
            author_id="GOV_1",
            author_role="government",
            event_year=5,
            event_type="flood",
            engagement_score=120.0,
            tier_id="official_authority",
            metadata={"hashtags": ["#flood"], "related_event_id": "evt_42"},
        )
        assert post.engagement_score == 120.0
        assert post.tier_id == "official_authority"
        assert post.metadata["hashtags"] == ["#flood"]

    def test_negative_engagement_score_rejected(self):
        with pytest.raises(ValueError, match="engagement_score"):
            Post(
                text="x",
                author_id="A",
                author_role="role",
                event_year=1,
                event_type="t",
                engagement_score=-1.0,
            )

    def test_negative_event_year_rejected(self):
        with pytest.raises(ValueError, match="event_year"):
            Post(
                text="x",
                author_id="A",
                author_role="role",
                event_year=-1,
                event_type="t",
            )

    def test_empty_tier_id_allowed(self):
        """tier_id default is empty string — a Post can exist
        without a credibility tier (e.g. a draft post, or a domain
        that doesn't use the credibility model)."""
        post = Post(
            text="x",
            author_id="A",
            author_role="role",
            event_year=1,
            event_type="t",
        )
        assert post.tier_id == ""


# ─────────────────────────────────────────────────────────────────────
# Class 2 — age_weight decay arithmetic
# ─────────────────────────────────────────────────────────────────────


class TestAgeWeight:
    """Exponential half-life decay: weight = 0.5 ** (elapsed / hl)."""

    def test_same_year_weight_is_one(self):
        assert age_weight(post_year=5, current_year=5) == 1.0

    def test_half_life_year_returns_half(self):
        # half_life_years=2.0, elapsed=2 → weight=0.5
        assert age_weight(post_year=3, current_year=5) == pytest.approx(0.5)

    def test_double_half_life_returns_quarter(self):
        # half_life_years=2.0, elapsed=4 → weight=0.25
        assert age_weight(post_year=1, current_year=5) == pytest.approx(0.25)

    def test_custom_half_life(self):
        # half_life_years=1.0, elapsed=3 → weight=0.125
        assert age_weight(
            post_year=2, current_year=5, half_life_years=1.0
        ) == pytest.approx(0.125)

    def test_future_post_returns_one(self):
        """A post from the future (current_year < post_year) is
        defensive — early-return 1.0 instead of returning weight >1
        (which would over-weight the post). Realistically this
        branch only fires on argument-order mistakes."""
        assert age_weight(post_year=10, current_year=5) == 1.0

    def test_negative_half_life_rejected(self):
        with pytest.raises(ValueError, match="half_life_years"):
            age_weight(post_year=1, current_year=5, half_life_years=-1.0)

    def test_zero_half_life_rejected(self):
        with pytest.raises(ValueError, match="half_life_years"):
            age_weight(post_year=1, current_year=5, half_life_years=0.0)


# ─────────────────────────────────────────────────────────────────────
# Class 3 — DefaultDomainPack defaults
# ─────────────────────────────────────────────────────────────────────


class TestDefaultDomainPackPerceptionDefaults:
    """A pack without social-media customisation gets safe defaults
    — empty tier list, fail-closed credibility weights, debug-grade
    verbalisation, no suppression, passthrough filter."""

    @pytest.fixture
    def pack(self):
        return DefaultDomainPack()

    def test_credibility_tiers_default_empty(self, pack):
        assert pack.credibility_tiers() == []

    def test_credibility_weight_unknown_returns_zero(self, pack):
        """Fail-closed: unknown tier_id → weight 0.0, so a spoofed
        or typo'd tier doesn't accidentally propagate full
        credibility."""
        assert pack.credibility_weight("any_string") == 0.0
        assert pack.credibility_weight("") == 0.0

    def test_verbalise_post_default_debug_format(self, pack):
        post = Post(
            text="hello",
            author_id="A",
            author_role="role",
            event_year=1,
            event_type="t",
            tier_id="official_authority",
        )
        assert pack.verbalise_post(post) == "[official_authority] hello"

    def test_suppressed_tiers_default_empty(self, pack):
        assert pack.suppressed_tiers() == set()

    def test_social_media_post_filter_default_passthrough(self, pack):
        post = Post(
            text="x", author_id="A", author_role="r",
            event_year=1, event_type="t",
        )
        assert pack.social_media_post_filter(object(), post) is post


# ─────────────────────────────────────────────────────────────────────
# Class 4 — Pack override demonstrates audit-locked design
# ─────────────────────────────────────────────────────────────────────


class TestPackOverrideRoundTrip:
    """Demonstrate that a pack overriding all five methods composes
    correctly. Uses non-flood vocabulary (medical_authority /
    clinician / community / rumor) to prove the pack-side
    ownership: any domain can ship its own tier vocabulary without
    bending it into US-media-shaped categories."""

    @pytest.fixture
    def pack(self):
        return _DemoPack()

    def test_pack_implements_perception_pack_protocol(self, pack):
        assert isinstance(pack, PerceptionPack)

    def test_credibility_tiers_returns_pack_vocabulary(self, pack):
        assert pack.credibility_tiers() == [
            "medical_authority", "clinician", "community", "rumor",
        ]

    def test_credibility_weight_maps_per_tier(self, pack):
        assert pack.credibility_weight("medical_authority") == 1.0
        assert pack.credibility_weight("clinician") == 0.85
        assert pack.credibility_weight("rumor") == 0.2
        # Unknown tier → 0.0 (pack chose to inherit fail-closed):
        assert pack.credibility_weight("typo_tier") == 0.0

    def test_verbalise_post_uses_pack_templates(self, pack):
        post = Post(
            text="vaccine safe",
            author_id="CDC", author_role="agency",
            event_year=2, event_type="advisory",
            tier_id="medical_authority",
        )
        assert pack.verbalise_post(post) == (
            "Health authority reports: vaccine safe"
        )

    def test_suppressed_tiers_filter(self, pack):
        assert pack.suppressed_tiers() == {"rumor"}

    def test_social_media_post_filter_drops_for_distrusting_agent(self, pack):
        rumor = Post(
            text="x", author_id="A", author_role="r",
            event_year=1, event_type="t", tier_id="rumor",
        )
        # Default agent (no distrusts_rumor) → passthrough
        assert pack.social_media_post_filter(object(), rumor) is rumor

        # Anti-rumor agent → drops to None
        class _AntiRumor:
            distrusts_rumor = True

        assert pack.social_media_post_filter(_AntiRumor(), rumor) is None


# ─────────────────────────────────────────────────────────────────────
# Class 5 — Post module genericity (focused module-level check)
# ─────────────────────────────────────────────────────────────────────


class TestPostModuleGenericity:
    """Centralised AST gate lives in
    ``test_framework_invariants.py::TestNoUSMediaTierLiteralsInBrokerSocial``.
    This is a focused module-level check that fails fast if Post
    accidentally gains forbidden imports."""

    def test_post_module_imports_no_domain_code(self):
        import ast
        from pathlib import Path

        import broker.components.social.post as module
        source_path = Path(module.__file__)
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        forbidden_prefixes = (
            "broker.domains.water",
            "examples.",
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden_prefixes), (
                        f"post imports forbidden module {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith(forbidden_prefixes), (
                    f"post imports from forbidden module {mod!r}"
                )
