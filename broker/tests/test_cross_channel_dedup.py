"""Phase 6T-G regression tests for cross-channel deduplication."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import pytest

from broker.components.social.dedup import (
    DEFAULT_CHANNEL_PRIORITY,
    CrossChannelDedupResult,
    dedup_by_canonical_event,
)


@dataclass
class _StubMessage:
    """Minimal stand-in for a Post-or-event-record consumed by dedup."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Priority resolution
# ---------------------------------------------------------------------------

class TestPriorityResolution:
    def test_official_beats_global_beats_peer_when_canonical_match(self):
        """Same canonical_event_id across 3 channels → OFFICIAL wins."""
        cev = "subsidy_change:2026:global"
        msgs = [
            _StubMessage("peer post", metadata={"canonical_event_id": cev}),
            _StubMessage("global news", metadata={"canonical_event_id": cev}),
            _StubMessage("official notice", metadata={"canonical_event_id": cev}),
        ]
        channels = ["PEER", "GLOBAL", "OFFICIAL"]

        results = dedup_by_canonical_event(msgs, channels)

        assert len(results) == 1
        assert results[0].chosen.text == "official notice"
        # All 3 channels recorded as sources
        assert set(results[0].sources) == {"OFFICIAL", "GLOBAL", "PEER"}
        assert results[0].canonical_event_id == cev
        assert "confirmed by 3 independent sources" in results[0].label

    def test_global_beats_peer_when_official_absent(self):
        cev = "flood:2026:tract_5"
        msgs = [
            _StubMessage("peer", metadata={"canonical_event_id": cev}),
            _StubMessage("global", metadata={"canonical_event_id": cev}),
        ]
        results = dedup_by_canonical_event(msgs, ["PEER", "GLOBAL"])
        assert len(results) == 1
        assert results[0].chosen.text == "global"
        assert "confirmed by 2 independent sources" in results[0].label

    def test_unknown_channel_label_gets_lowest_priority(self):
        """A channel label not in DEFAULT_CHANNEL_PRIORITY gets pri=0."""
        cev = "x:1:y"
        msgs = [
            _StubMessage("from PEER", metadata={"canonical_event_id": cev}),
            _StubMessage("from MYSTERY", metadata={"canonical_event_id": cev}),
        ]
        # MYSTERY isn't in the priority dict — should rank below PEER (pri=10)
        results = dedup_by_canonical_event(msgs, ["PEER", "MYSTERY"])
        assert results[0].chosen.text == "from PEER"


# ---------------------------------------------------------------------------
# Pass-through (no canonical_event_id)
# ---------------------------------------------------------------------------

class TestPassThrough:
    def test_no_canonical_id_pass_through(self):
        """Messages without canonical_event_id are emitted as
        single-source pass-through results — NEVER deduped. This is
        the regression gate against over-aggressive collapsing of
        legitimately divergent signal."""
        msgs = [
            _StubMessage("subsidy via official", metadata={}),  # no canonical_event_id
            _StubMessage("subsidy via global", metadata={}),
            _StubMessage("subsidy via peer", metadata={}),
        ]
        channels = ["OFFICIAL", "GLOBAL", "PEER"]

        results = dedup_by_canonical_event(msgs, channels)

        # All 3 should pass through as single-source results — NOT
        # collapsed even though they're "about" the same subsidy event.
        assert len(results) == 3
        for r in results:
            assert r.canonical_event_id is None
            assert len(r.sources) == 1
            assert r.label == ""

    def test_message_without_metadata_attr_passes_through(self):
        """Plain dicts without a ``metadata`` key are pass-through."""
        msgs = [{"text": "raw event dict"}]
        results = dedup_by_canonical_event(msgs, ["OFFICIAL"])
        assert len(results) == 1
        assert results[0].canonical_event_id is None
        assert results[0].chosen == {"text": "raw event dict"}

    def test_dict_with_metadata_subkey_works(self):
        """Plain dict shape: ``msg['metadata']['canonical_event_id']``."""
        msgs = [
            {"text": "official", "metadata": {"canonical_event_id": "e1"}},
            {"text": "peer", "metadata": {"canonical_event_id": "e1"}},
        ]
        results = dedup_by_canonical_event(msgs, ["OFFICIAL", "PEER"])
        assert len(results) == 1
        assert results[0].chosen["text"] == "official"

    def test_mixed_canonical_and_passthrough(self):
        """Some messages have canonical_event_id, others don't.
        Each group is independently processed."""
        msgs = [
            _StubMessage("flood official", metadata={"canonical_event_id": "f1"}),
            _StubMessage("flood peer", metadata={"canonical_event_id": "f1"}),
            _StubMessage("untagged", metadata={}),
            _StubMessage("flood global", metadata={"canonical_event_id": "f1"}),
        ]
        channels = ["OFFICIAL", "PEER", "GLOBAL", "GLOBAL"]
        results = dedup_by_canonical_event(msgs, channels)
        # 1 deduped result + 1 pass-through
        assert len(results) == 2
        # The deduped one comes first (first-seen order)
        deduped = [r for r in results if r.canonical_event_id == "f1"]
        passthrough = [r for r in results if r.canonical_event_id is None]
        assert len(deduped) == 1
        assert len(passthrough) == 1
        assert deduped[0].chosen.text == "flood official"
        assert deduped[0].label == "confirmed by 3 independent sources"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_single_channel_single_source_no_confirm_label(self):
        msgs = [_StubMessage("solo", metadata={"canonical_event_id": "e1"})]
        results = dedup_by_canonical_event(msgs, ["OFFICIAL"])
        assert len(results) == 1
        assert results[0].label == ""  # no "confirmed by N" suffix when N=1
        assert results[0].sources == ["OFFICIAL"]

    def test_empty_input_returns_empty_list(self):
        assert dedup_by_canonical_event([], []) == []

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match=r"messages and channels"):
            dedup_by_canonical_event(
                [_StubMessage("a", metadata={"canonical_event_id": "e1"})],
                ["OFFICIAL", "PEER"],  # one extra
            )

    def test_custom_priority_override(self):
        """Caller can override DEFAULT_CHANNEL_PRIORITY to flip ranking."""
        msgs = [
            _StubMessage("a", metadata={"canonical_event_id": "e1"}),
            _StubMessage("b", metadata={"canonical_event_id": "e1"}),
        ]
        # Flip ranking: PEER > OFFICIAL via custom priority
        custom_pri = {"OFFICIAL": 1, "PEER": 100}
        results = dedup_by_canonical_event(
            msgs, ["OFFICIAL", "PEER"], priority=custom_pri,
        )
        assert results[0].chosen.text == "b"  # PEER won

    def test_default_priority_constants_match_documented_values(self):
        """Lock the documented priority ordering — paper-3 dedup
        semantics depend on these exact values per
        .research/social_tier_injection_reference.md §10."""
        assert DEFAULT_CHANNEL_PRIORITY == {
            "OFFICIAL": 100, "GLOBAL": 50, "PEER": 10,
        }

    def test_first_seen_order_preserved_for_multiple_canonical_events(self):
        """When 2 distinct canonical events appear, results come out
        in first-seen order regardless of priority."""
        msgs = [
            _StubMessage("e2-peer", metadata={"canonical_event_id": "e2"}),
            _StubMessage("e1-official", metadata={"canonical_event_id": "e1"}),
        ]
        results = dedup_by_canonical_event(msgs, ["PEER", "OFFICIAL"])
        assert [r.canonical_event_id for r in results] == ["e2", "e1"]


# ---------------------------------------------------------------------------
# Result type contract
# ---------------------------------------------------------------------------

class TestResultContract:
    def test_result_is_frozen_dataclass(self):
        """CrossChannelDedupResult is frozen → callers can't mutate
        the returned objects, ensuring downstream rendering can't
        accidentally edit the audit trail."""
        result = CrossChannelDedupResult(
            chosen="x", sources=["OFFICIAL"], canonical_event_id="e1", label="",
        )
        with pytest.raises((AttributeError, Exception)):
            result.chosen = "tampered"  # type: ignore[misc]
