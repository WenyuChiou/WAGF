"""Phase 6T-G (2026-05-28): cross-channel deduplication.

The same real-world event can reach an agent through up to three
broker prompt channels:

* OFFICIAL — institutional declarations (``{inst_subsidy_rate}`` etc.)
* GLOBAL   — global news / policy announcements (``{global_news}``)
* PEER     — social-media posts (``{social_media_feed}``)

Pre-6T-G the prompt rendered all three independently, padding the
context window and biasing the household toward repeated mentions.
This module collapses identical events across channels by their
``canonical_event_id`` (an opt-in metadata key set by the emitting
domain pack), keeping only the highest-priority channel and annotating
multi-source confirmation when N>1 channels reported the same event.

Channel-class labels (``OFFICIAL`` / ``GLOBAL`` / ``PEER``) name the
**channel class**, NOT the credibility tier of any individual post.
Credibility tiers are domain-supplied (``DomainPack.credibility_tiers``).
The literals here are intentionally uppercase to make the namespace
distinction unambiguous in code review.

Messages WITHOUT ``canonical_event_id`` in their metadata pass through
unchanged — dedup is exact-match only. This is the regression gate
against over-aggressive collapsing of legitimately divergent signal
(e.g. ``subsidy_change`` events get a distinct canonical_event_id per
channel in the flood pack so they are NEVER deduped).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Channel-class priority. Domain packs MAY override via a hook in a
# future revision; for now these defaults match the audit-trail
# semantics documented in
# ``.research/social_tier_injection_reference.md`` §10.
DEFAULT_CHANNEL_PRIORITY: Dict[str, int] = {
    "OFFICIAL": 100,
    "GLOBAL": 50,
    "PEER": 10,
}


@dataclass(frozen=True)
class CrossChannelDedupResult:
    """One surviving message per unique canonical event.

    Attributes:
        chosen: The original message object from the highest-priority
            channel that reported this canonical event. Type is
            intentionally ``Any`` because messages can be raw Posts,
            event dicts, or rendered strings depending on caller.
        sources: Channel-class labels of every channel that reported
            this canonical event (e.g. ``["OFFICIAL", "PEER"]`` when
            an official subsidy change ALSO showed up on social
            feeds). Always at least one entry.
        canonical_event_id: The dedup key. ``None`` for pass-through
            (no canonical_event_id in source metadata).
        label: Operator-facing confirmation text. Empty when
            ``len(sources) == 1``; otherwise
            ``"confirmed by N independent sources"``.
    """
    chosen: Any
    sources: List[str] = field(default_factory=list)
    canonical_event_id: Optional[str] = None
    label: str = ""


def _extract_canonical_id(message: Any) -> Optional[str]:
    """Pull ``canonical_event_id`` from a message's metadata.

    Supports two shapes:
    * ``message.metadata`` dict (e.g. ``Post.metadata``)
    * ``message["metadata"]`` dict (plain-dict event records)

    Returns ``None`` if either the metadata or the key is absent;
    callers treat ``None`` as "pass through unchanged".
    """
    meta = getattr(message, "metadata", None)
    if meta is None and isinstance(message, dict):
        meta = message.get("metadata")
    if not isinstance(meta, dict):
        return None
    val = meta.get("canonical_event_id")
    if val is None:
        return None
    return str(val)


def dedup_by_canonical_event(
    messages: List[Any],
    channels: List[str],
    priority: Optional[Dict[str, int]] = None,
) -> List[CrossChannelDedupResult]:
    """Group ``messages`` by ``canonical_event_id`` and pick the
    highest-priority channel representative per group.

    Args:
        messages: Parallel list with ``channels`` — one entry per
            (channel, message) pair. Pre-6T-G callers built one big
            list across channels before calling here.
        channels: Channel-class labels matching ``messages`` index-by-
            index. Must be the same length as ``messages``. Unknown
            labels (not in ``priority``) get priority 0 (lowest).
        priority: Override of ``DEFAULT_CHANNEL_PRIORITY``. Pass to
            tune ranking without monkey-patching the module global.

    Returns:
        List of :class:`CrossChannelDedupResult`, preserving the
        first-seen order of canonical events. Messages without a
        canonical_event_id are emitted as their own single-source
        result (pass-through) — no exception, no warning.

    Raises:
        ValueError: ``len(messages) != len(channels)``.
    """
    if len(messages) != len(channels):
        raise ValueError(
            "dedup_by_canonical_event: messages and channels must be the "
            f"same length, got {len(messages)} vs {len(channels)}."
        )

    pri = priority if priority is not None else DEFAULT_CHANNEL_PRIORITY

    # Group preserving first-seen order. We avoid OrderedDict because
    # plain dict is insertion-ordered in Python 3.7+ — repo CI targets
    # 3.10+ per pyproject.toml.
    grouped: Dict[str, List[int]] = {}
    pass_through_indices: List[int] = []

    for idx, msg in enumerate(messages):
        canonical = _extract_canonical_id(msg)
        if canonical is None:
            pass_through_indices.append(idx)
            continue
        grouped.setdefault(canonical, []).append(idx)

    out: List[CrossChannelDedupResult] = []

    # Emit grouped results in first-seen order.
    for canonical, idxs in grouped.items():
        # Highest priority wins; ties broken by first-seen order
        # (stable sort preserves the original list order).
        best_idx = max(idxs, key=lambda i: pri.get(channels[i], 0))
        sources = [channels[i] for i in idxs]
        n = len(sources)
        label = f"confirmed by {n} independent sources" if n > 1 else ""
        out.append(CrossChannelDedupResult(
            chosen=messages[best_idx],
            sources=sources,
            canonical_event_id=canonical,
            label=label,
        ))

    # Append pass-through messages (no canonical_event_id) as
    # single-source results, preserving their original order.
    for idx in pass_through_indices:
        out.append(CrossChannelDedupResult(
            chosen=messages[idx],
            sources=[channels[idx]],
            canonical_event_id=None,
            label="",
        ))

    return out


__all__ = [
    "DEFAULT_CHANNEL_PRIORITY",
    "CrossChannelDedupResult",
    "dedup_by_canonical_event",
]
