"""Phase 6T-F.3 (2026-05-29): narrative-diffusion ERROR action-coherence tests.

Pins the influencer's ERROR-level governance contract:

1. ``NarrativeDiffusionFramework.get_blocked_skills`` /
   ``validate_action_coherence`` — the programmatic coherence spec (generic
   verbs), strictly disjoint from ``get_expected_behavior``.
2. The runtime ThinkingValidator (framework="narrative_diffusion") blocks an
   incoherent post-action at ERROR level and leaves coherent ones / silence
   untouched.
3. The flood influencer's declarative YAML ``thinking_rules`` stay in sync
   with the framework's ``get_blocked_skills`` (mapped through the pack's
   verb->skill table) — the guard against the divergence the validation docs
   warned about for PMT's twin CACR implementations.
4. The influencer config flips ``strict_mode`` on and leaves maintain_silence
   the documented-unconstrained fallback.
"""
from __future__ import annotations

from pathlib import Path

import yaml

# Importing the frameworks package registers narrative_diffusion metadata
# (FRAMEWORK_LABEL_ORDERS / FRAMEWORK_CONSTRUCTS) so ThinkingValidator accepts
# framework="narrative_diffusion".
import broker.validators.governance.frameworks  # noqa: F401
# Importing the example registers the flood pack (for narrative_diffusion_skill_map).
import examples.governed_flood  # noqa: F401

from broker.domains.registry import DomainPackRegistry
from broker.governance.rule_types import GovernanceRule, RuleCondition
from broker.validators.governance.frameworks.narrative_diffusion import (
    NarrativeDiffusionFramework,
)
from broker.validators.governance.thinking_validator import ThinkingValidator


REPO_ROOT = Path(__file__).resolve().parents[2]
INFLUENCER_CONFIG = (
    REPO_ROOT
    / "examples"
    / "multi_agent"
    / "flood"
    / "config"
    / "ma_agent_types_influencer.yaml"
)

DEAD_MOMENT = {"SALIENCE": "VL", "VIRALITY": "VL", "NARRATIVE_CONSISTENCY": "M"}
OFF_BRAND = {"SALIENCE": "H", "VIRALITY": "L", "NARRATIVE_CONSISTENCY": "L"}
HOT_MOMENT = {"SALIENCE": "VH", "VIRALITY": "VH", "NARRATIVE_CONSISTENCY": "M"}
HOT_OFF_BRAND = {"SALIENCE": "VH", "VIRALITY": "VH", "NARRATIVE_CONSISTENCY": "VL"}
NEUTRAL = {"SALIENCE": "M", "VIRALITY": "M", "NARRATIVE_CONSISTENCY": "M"}


# ─────────────────────────────────────────────────────────────────────
# 1 — framework coherence spec (generic verbs)
# ─────────────────────────────────────────────────────────────────────


class TestFrameworkCoherence:
    def setup_method(self):
        self.fw = NarrativeDiffusionFramework()

    def test_dead_moment_blocks_all_promotion_verbs(self):
        blocked = set(self.fw.get_blocked_skills(DEAD_MOMENT))
        assert blocked == {"amplify", "share", "counter_narrative"}
        # silence is never blocked
        assert "stay_silent" not in blocked

    def test_off_brand_blocks_amplify_and_share_only(self):
        blocked = set(self.fw.get_blocked_skills(OFF_BRAND))
        assert blocked == {"amplify", "share"}
        # counter_narrative is the EXPECTED response off-brand — not blocked
        assert "counter_narrative" not in blocked

    def test_hot_moment_blocks_nothing(self):
        assert self.fw.get_blocked_skills(HOT_MOMENT) == []

    def test_hot_off_brand_still_blocks_nothing(self):
        # High salience + high virality makes amplify/share EXPECTED even
        # off-brand (band-1 of get_expected_behavior wins), so band-2 is gated
        # out by the "virality NOT high" guard.
        assert self.fw.get_blocked_skills(HOT_OFF_BRAND) == []

    def test_neutral_blocks_nothing(self):
        assert self.fw.get_blocked_skills(NEUTRAL) == []

    def test_blocked_never_overlaps_expected(self):
        # The core invariant: a verb is never simultaneously expected and
        # blocked for the same appraisals.
        for appr in (DEAD_MOMENT, OFF_BRAND, HOT_MOMENT, HOT_OFF_BRAND, NEUTRAL):
            expected = set(self.fw.get_expected_behavior(appr))
            blocked = set(self.fw.get_blocked_skills(appr))
            assert expected.isdisjoint(blocked), (
                f"overlap for {appr}: expected={expected} blocked={blocked}"
            )

    def test_blocked_disjoint_from_expected_over_all_125_combinations(self):
        # Machine-verify the disjointness invariant exhaustively rather than
        # trusting the 5 sample points above — the band-2 "virality NOT high"
        # guard is the subtle case and this is cheap (125 combos).
        labels = ("VL", "L", "M", "H", "VH")
        for s in labels:
            for v in labels:
                for c in labels:
                    appr = {
                        "SALIENCE": s,
                        "VIRALITY": v,
                        "NARRATIVE_CONSISTENCY": c,
                    }
                    expected = set(self.fw.get_expected_behavior(appr))
                    blocked = set(self.fw.get_blocked_skills(appr))
                    assert expected.isdisjoint(blocked), (
                        f"overlap at S={s} V={v} C={c}: "
                        f"expected={expected} blocked={blocked}"
                    )

    def test_validate_action_coherence_rejects_blocked_verb(self):
        res = self.fw.validate_action_coherence(DEAD_MOMENT, "amplify")
        assert res.valid is False
        assert res.errors

    def test_validate_action_coherence_allows_silence_in_dead_moment(self):
        res = self.fw.validate_action_coherence(DEAD_MOMENT, "stay_silent")
        assert res.valid is True
        assert res.errors == []

    def test_validate_action_coherence_allows_coherent_verb(self):
        res = self.fw.validate_action_coherence(HOT_MOMENT, "amplify")
        assert res.valid is True


# ─────────────────────────────────────────────────────────────────────
# 2 — runtime ThinkingValidator blocks at ERROR
# ─────────────────────────────────────────────────────────────────────


def _yaml_rules_as_governance_rules():
    """Build GovernanceRule objects equivalent to the influencer config's
    two declarative thinking_rules (so the runtime block can be exercised
    without standing up the full governance loader)."""
    band1 = GovernanceRule(
        id="influencer_dead_moment_blocks_posting",
        category="thinking",
        conditions=[
            RuleCondition(type="construct", field="SALIENCE", operator="in", values=["VL", "L"]),
            RuleCondition(type="construct", field="VIRALITY", operator="in", values=["VL", "L"]),
        ],
        blocked_skills=["amplify_event", "post_counter_narrative", "share_success_story"],
        level="ERROR",
        message="dead moment",
    )
    band2 = GovernanceRule(
        id="influencer_off_brand_blocks_promotion",
        category="thinking",
        conditions=[
            RuleCondition(type="construct", field="NARRATIVE_CONSISTENCY", operator="in", values=["VL", "L"]),
            RuleCondition(type="construct", field="SALIENCE", operator="in", values=["H", "VH"]),
            RuleCondition(type="construct", field="VIRALITY", operator="in", values=["VL", "L", "M"]),
        ],
        blocked_skills=["amplify_event", "share_success_story"],
        level="ERROR",
        message="off brand",
    )
    return [band1, band2]


class TestRuntimeThinkingValidatorBlock:
    """Exercises ThinkingValidator._validate_yaml_rules — a faithful proxy
    for the rule-evaluation logic. NOTE (6T-F.4 follow-up): the LIVE pipeline
    runs AgentValidator._run_rule_set, a separate but behaviourally-equivalent
    implementation of the same {construct, values} condition format. A direct
    AgentValidator.validate_thinking("social_media_influencer", ...) test
    against the YAML-loaded rules belongs in the 6T-F.4 e2e smoke (which
    stands up the full governance loader). Tracked as a known gap."""

    def _blocked(self, skill, appraisals):
        validator = ThinkingValidator(framework="narrative_diffusion")
        context = {"reasoning": dict(appraisals), "framework": "narrative_diffusion"}
        results = validator._validate_yaml_rules(
            skill_name=skill,
            rules=_yaml_rules_as_governance_rules(),
            context=context,
            framework="narrative_diffusion",
        )
        # A skill is blocked iff any fired rule is an ERROR (valid=False).
        return any(not r.valid for r in results)

    def test_amplify_blocked_in_dead_moment(self):
        assert self._blocked("amplify_event", DEAD_MOMENT) is True

    def test_counter_narrative_blocked_in_dead_moment(self):
        assert self._blocked("post_counter_narrative", DEAD_MOMENT) is True

    def test_silence_never_blocked_in_dead_moment(self):
        assert self._blocked("maintain_silence", DEAD_MOMENT) is False

    def test_amplify_blocked_off_brand(self):
        assert self._blocked("amplify_event", OFF_BRAND) is True

    def test_counter_narrative_allowed_off_brand(self):
        # off-brand -> counter is the expected response, must NOT be blocked
        assert self._blocked("post_counter_narrative", OFF_BRAND) is False

    def test_amplify_allowed_in_hot_moment(self):
        assert self._blocked("amplify_event", HOT_MOMENT) is False

    def test_error_result_carries_message(self):
        validator = ThinkingValidator(framework="narrative_diffusion")
        context = {"reasoning": dict(DEAD_MOMENT), "framework": "narrative_diffusion"}
        results = validator._validate_yaml_rules(
            skill_name="amplify_event",
            rules=_yaml_rules_as_governance_rules(),
            context=context,
            framework="narrative_diffusion",
        )
        fired = [r for r in results if not r.valid]
        assert fired
        assert fired[0].errors  # ERROR rule pushes its message to errors[]


# ─────────────────────────────────────────────────────────────────────
# 3 — YAML config stays in sync with the framework
# ─────────────────────────────────────────────────────────────────────


class TestConfigFrameworkSync:
    def setup_method(self):
        with open(INFLUENCER_CONFIG, encoding="utf-8") as fh:
            self.cfg = yaml.safe_load(fh)
        self.rules = (
            self.cfg["governance"]["strict"]["social_media_influencer"]["thinking_rules"]
        )
        self.skill_map = DomainPackRegistry.get_governance_pack(
            "flood"
        ).narrative_diffusion_skill_map()
        self.fw = NarrativeDiffusionFramework()

    def _rule(self, rule_id):
        for r in self.rules:
            if r["id"] == rule_id:
                return r
        raise AssertionError(f"rule {rule_id} not found")

    def _mapped(self, appraisals):
        return {self.skill_map[v] for v in self.fw.get_blocked_skills(appraisals)}

    def test_strict_mode_is_on(self):
        assert self.cfg["social_media_influencer"]["parsing"]["strict_mode"] is True

    def test_silence_is_documented_unconstrained(self):
        block = self.cfg["governance"]["strict"]["social_media_influencer"]
        assert "maintain_silence" in block["documented_unconstrained_skills"]

    def test_all_rules_are_error_level(self):
        assert all(r["level"] == "ERROR" for r in self.rules)

    def test_dead_moment_rule_matches_framework(self):
        rule = self._rule("influencer_dead_moment_blocks_posting")
        assert set(rule["blocked_skills"]) == self._mapped(DEAD_MOMENT)

    def test_off_brand_rule_matches_framework(self):
        rule = self._rule("influencer_off_brand_blocks_promotion")
        assert set(rule["blocked_skills"]) == self._mapped(OFF_BRAND)

    def test_rules_cover_all_active_post_skills(self):
        constrained = set()
        for r in self.rules:
            constrained.update(r["blocked_skills"])
        active = {"amplify_event", "post_counter_narrative", "share_success_story"}
        assert active <= constrained
