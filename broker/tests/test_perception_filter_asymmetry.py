"""Phase 6S-D regression — perception-filter behavior pinning.

This module pins the CURRENT behavior of WAGF's perception filter
chain, including two known gaps documented in
``.research/social_tier_injection_reference.md`` §7:

  Gap #1 — Observable injection asymmetry
  Gap #4 — MG observable threshold too aggressive

The actual runtime fix is **deliberately deferred** because:

1. Paper-1b uses a 5-seed v21 Gemma-3 4B dataset (per MEMORY.md
   "B1 RERUN COMPLETE 2026-04-28") whose mock-byte-identity baseline
   would shift if perception filter behavior changes for the ~16%
   MG cohort. Without a budgeted paper-1b multi-seed rerun, fixing
   these gaps risks invalidating the canonical dataset.

2. The current behavior is documented in
   ``.research/social_tier_injection_reference.md`` §7 as known
   future debt; this test file is the regression gate that prevents
   silent drift before a deliberate v2 perception-filter migration.

Test strategy:
- Tests of CORRECT current behavior run normally (pass at HEAD).
- Tests asserting the desired POST-FIX behavior are marked
  ``@pytest.mark.xfail(strict=True, reason="Phase 6S-D documented gap, deferred fix")``.
  A future paper-1b multi-seed rerun that ships the v2 filter will
  remove the xfail markers, flipping them to genuine PASS — at which
  point the perception filter is on the v2 baseline.

By using ``strict=True`` xfail, an accidental "fix" that flips the
expected-failure to pass without removing the marker will FAIL the
suite — forcing the contributor to explicitly mark the v2 migration.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers — construct a minimal HouseholdPerceptionFilter that exercises
# the documented behavior without a full flood-domain fixture.
# ---------------------------------------------------------------------------

def _make_filter_with_community_fields():
    """Return a HouseholdPerceptionFilter with a minimal community-
    observable-fields list (covers both COMMUNITY-scope and SPATIAL-
    scope sentinels so the MG-threshold tests can distinguish)."""
    from broker.components.social.perception import HouseholdPerceptionFilter
    return HouseholdPerceptionFilter(
        descriptor_mappings={},
        community_observable_fields=[
            # COMMUNITY-scoped (society-wide; MG strip is CORRECT here)
            "insurance_penetration_rate",
            "elevation_penetration_rate",
            # SPATIAL-scoped (per-agent neighborhood; MG strip is the
            # over-aggressive behavior documented in §7 Gap #4)
            "neighbor_insurance_rate",
            "neighbor_elevation_rate",
        ],
        neighbor_action_fields=[],
    )


def _mg_agent():
    """Minimal dict agent with is_mg=True and required agent_type."""
    return {"agent_type": "household", "is_mg": True}


def _non_mg_agent():
    return {"agent_type": "household", "is_mg": False}


# ---------------------------------------------------------------------------
# CURRENT behavior — passes at HEAD (Phase 6S-D-pinned)
# ---------------------------------------------------------------------------

class TestCurrentBehavior:
    """Pin the behavior that exists TODAY. Any code change that breaks
    these tests is a silent regression — should be evaluated against
    paper-1b reproducibility before landing."""

    def test_mg_agent_loses_community_scope_observable(self):
        """COMMUNITY-scoped observables are correctly stripped for
        MG agents. This part of the MG filter is CORRECT — no gap."""
        f = _make_filter_with_community_fields()
        context = {
            "observables": {
                "insurance_penetration_rate": 0.45,  # community scope
                "my_neighbor_count": 5,
            },
        }
        result = f.filter(context, _mg_agent())
        assert "insurance_penetration_rate" not in result.get("observables", {})
        # Personal observable (my_* prefix) is retained.
        assert result["observables"].get("my_neighbor_count") == 5

    def test_non_mg_agent_retains_community_scope_observable(self):
        """Non-MG households see community observables (current
        behavior, expected to remain after any v2 migration)."""
        f = _make_filter_with_community_fields()
        context = {
            "observables": {
                "insurance_penetration_rate": 0.45,
            },
        }
        result = f.filter(context, _non_mg_agent())
        # Raw value reaches output because no DescriptorMapping was
        # supplied (descriptors={} in helper) — this is the
        # documented Gap #1 (observable injection asymmetry).
        assert "insurance_penetration_rate" in result.get("observables", {})


# ---------------------------------------------------------------------------
# Gap #4 — MG threshold over-aggressive (xfail until v2 migration)
# ---------------------------------------------------------------------------

class TestKnownGapMGOverAggressive:
    """Pin Gap #4 from ``.research/social_tier_injection_reference.md`` §7.

    Desired post-fix behavior: MG agents should retain SPATIAL-scope
    observables (per-agent neighborhood data) and lose only
    COMMUNITY-scope. Current behavior strips both indiscriminately.

    A future paper-1b multi-seed rerun that ships the v2 perception
    filter would remove the ``@xfail`` marker — at which point the
    test flips to PASS as the new normal.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Phase 6S-D Gap #4: MG agents currently lose ALL "
            "community_observable_fields including SPATIAL-scope. "
            "Documented in .research/social_tier_injection_reference.md "
            "§7. Fix deferred until paper-1b multi-seed rerun budget "
            "available — reruns would invalidate v21 dataset."
        ),
    )
    def test_mg_agent_retains_spatial_scope_observable_post_v2_fix(self):
        """DESIRED post-fix behavior — MG agents see their own
        neighborhood spatial data. NOT current behavior."""
        f = _make_filter_with_community_fields()
        context = {
            "observables": {
                "neighbor_insurance_rate": 0.30,  # SPATIAL scope
            },
        }
        result = f.filter(context, _mg_agent())
        # Desired: SPATIAL-scope observable retained for MG agent.
        # Current (xfailing): stripped.
        assert "neighbor_insurance_rate" in result.get("observables", {})

    def test_mg_agent_loses_spatial_scope_observable_today(self):
        """CURRENT behavior — MG agent loses SPATIAL-scope along with
        COMMUNITY-scope. This is the gap we'll fix later."""
        f = _make_filter_with_community_fields()
        context = {
            "observables": {
                "neighbor_insurance_rate": 0.30,
            },
        }
        result = f.filter(context, _mg_agent())
        # Current behavior — strip succeeds.
        assert "neighbor_insurance_rate" not in result.get("observables", {})


# ---------------------------------------------------------------------------
# Gap #1 — Observable injection asymmetry (xfail until v2 migration)
# ---------------------------------------------------------------------------

class TestKnownGapObservableAsymmetry:
    """Pin Gap #1 from ``.research/social_tier_injection_reference.md`` §7.

    Desired post-fix behavior: any raw numeric observable injected by
    ``ObservableStateProvider`` MUST be either verbalised by a
    ``DescriptorMapping`` (lay agent) or visible only to passthrough
    agent types — never reach a non-passthrough agent's prompt as a
    raw float. Current behavior leaks raw floats for fields a domain
    forgot to whitelist in ``percentage_fields`` /
    ``community_observable_fields``.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "Phase 6S-D Gap #1: ObservableStateProvider writes raw "
            "numeric fields BEFORE PerceptionAwareProvider runs; "
            "fields not in percentage_fields whitelist leak as raw "
            "floats. Documented in "
            ".research/social_tier_injection_reference.md §7. "
            "Fix deferred — paper-1b byte-identity sensitive."
        ),
    )
    def test_unwhitelisted_raw_observable_stripped_for_non_mg_household_post_v2_fix(self):
        """DESIRED post-fix: even an un-whitelisted raw observable is
        stripped for lay agents (no domain-author footgun). NOT
        current behavior."""
        f = _make_filter_with_community_fields()
        context = {
            "observables": {
                # A domain author forgot to declare this field in
                # percentage_fields. Currently the raw float reaches
                # the lay agent's prompt.
                "some_unwhitelisted_metric": 0.73,
            },
        }
        result = f.filter(context, _non_mg_agent())
        # Desired: raw float stripped (no descriptor → no exposure).
        assert "some_unwhitelisted_metric" not in result.get("observables", {})

    def test_unwhitelisted_raw_observable_leaks_today(self):
        """CURRENT behavior — un-whitelisted observable leaks as raw
        float to lay agent. This is the gap we'll fix later."""
        f = _make_filter_with_community_fields()
        context = {
            "observables": {
                "some_unwhitelisted_metric": 0.73,
            },
        }
        result = f.filter(context, _non_mg_agent())
        # Current: raw float remains in output.
        assert result.get("observables", {}).get("some_unwhitelisted_metric") == 0.73


# ---------------------------------------------------------------------------
# Migration path documentation
# ---------------------------------------------------------------------------

def test_migration_path_documented():
    """Sanity test asserting the social-tier reference doc exists.
    If a future contributor removes the doc without addressing the
    gaps, this test surfaces the regression."""
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    doc = repo_root / ".research" / "social_tier_injection_reference.md"
    assert doc.exists(), (
        f"social-tier injection reference doc missing: {doc}. "
        f"Phase 6S-C shipped this doc as the canonical gap inventory; "
        f"removing it strands the xfail markers in this file."
    )
    text = doc.read_text(encoding="utf-8")
    # Doc must contain §7 Known gaps section (anchor for xfail
    # markers — if removed, future contributors might re-fix the
    # gaps without coordinating with the rest of the design).
    assert "Known gaps" in text
