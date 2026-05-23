"""Broker-level initial memory loader.

Reads per-agent initial memories from a JSON file and writes them to a
memory engine. If the engine is wrapped by PolicyFilteredMemoryEngine,
the policy is automatically enforced; this helper does not duplicate the
filter logic - it just tags each write with the appropriate content type
so the proxy can classify it correctly.

Expected JSON shape:
    {
        "agent_id_1": [
            {"content": "...", "category": "...", "importance": 0.5, "source": "survey"},
            ...
        ],
        ...
    }
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set

from .content_types import MemoryContentType
from .policy_classifier import classify


@dataclass
class InitialLoadReport:
    """Summary returned by load_initial_memories_from_json."""

    loaded_count: int = 0
    skipped_missing_agent: int = 0
    classified_by_type: Dict[str, int] = field(default_factory=dict)
    dropped_counts: Dict[str, int] = field(default_factory=dict)
    source_path: str = ""
    total_agents_in_file: int = 0
    total_agents_loaded: int = 0

    def summary(self) -> str:
        """Human-readable one-liner for logging."""
        parts = [
            f"Loaded {self.loaded_count} initial memories "
            f"across {self.total_agents_loaded} agents",
        ]
        if self.dropped_counts:
            dropped_total = sum(self.dropped_counts.values())
            details = ", ".join(
                f"{k}={v}" for k, v in sorted(self.dropped_counts.items())
            )
            parts.append(f"(dropped {dropped_total} by policy: {details})")
        if self.skipped_missing_agent:
            parts.append(
                f"[{self.skipped_missing_agent} memories for agents "
                f"not in filter]"
            )
        return " ".join(parts)


# Sentinel for distinguishing "caller did not pass default_content_type"
# from "caller passed INITIAL_FACTUAL explicitly", so a domain pack's
# bundle.default_content_type can override the function default but not
# silently override an explicit caller choice.
_DEFAULT_CT_UNSET = object()


def load_initial_memories_from_json(
    memory_engine: Any,
    json_path: Path,
    agent_id_filter: Optional[Set[str]] = None,
    domain: Optional[str] = None,
    domain_mapping: Optional[Dict[str, MemoryContentType]] = None,
    external_event_whitelist: Optional[tuple] = None,
    default_content_type: Any = _DEFAULT_CT_UNSET,
) -> InitialLoadReport:
    """Load per-agent initial memories from a JSON file and inject them
    into the given memory engine.

    Args:
        memory_engine: Target engine. If it is a PolicyFilteredMemoryEngine,
            the wrapper will enforce the policy automatically; the caller
            does not need to pre-filter. This helper just tags each write
            with the right content_type so classification is unambiguous.
        json_path: Path to the initial memories JSON file.
        agent_id_filter: If provided, only load memories for agents whose
            id is in this set. Memories for other agents are skipped
            (counted in the report).
        domain: Optional domain name. When supplied, the loader queries
            ``DomainPackRegistry.get_or_default(domain).memory_policy()``
            and uses its ``category_rules`` (as a fallback for
            ``domain_mapping``) and its ``external_event_whitelist``
            (as a fallback for the kwarg of the same name). Phase 6K-A
            (2026-05-22).
        domain_mapping: Optional per-call category → content-type
            override. When supplied, overrides any bundle mapping.
        external_event_whitelist: Tuple of category names allowed to
            keep ``MemoryContentType.EXTERNAL_EVENT`` at seed time;
            categories outside this set whose classification resolves
            to EXTERNAL_EVENT get downgraded to ``default_content_type``
            (the "fail open, not closed" guard from the module
            docstring). Phase 6K-A (2026-05-22) — previously a
            hardcoded water-domain tuple; the values now come from the
            bundle (see FloodDomainPack.memory_policy()). None →
            bundle lookup; if still None → empty tuple (every
            EXTERNAL_EVENT downgrades).
        default_content_type: Fallback content type used to tag any
            memory whose category has no classification hit. Defaults
            to INITIAL_FACTUAL which is allowed under both CLEAN and
            LEGACY policy — safe.

    Returns:
        InitialLoadReport with loaded/dropped counts per content type.
        The dropped_counts field is populated by reading the proxy's
        stats() if available; otherwise it remains empty.
    """
    # Phase 6K-A (2026-05-22): resolve whitelist + default_content_type
    # from the DomainPack bundle when the caller did not pass them
    # explicitly. An explicit caller-supplied value always wins; passing
    # the empty tuple explicitly disables the whitelist (every
    # EXTERNAL_EVENT downgrades).
    bundle = None
    if domain:
        try:
            from broker.domains.registry import DomainPackRegistry
            bundle = DomainPackRegistry.get_or_default(domain).memory_policy()
        except ImportError:
            pass  # guard against circular import during early load
    if external_event_whitelist is None:
        external_event_whitelist = (
            bundle.external_event_whitelist if bundle is not None else ()
        )
    if default_content_type is _DEFAULT_CT_UNSET:
        if bundle is not None and bundle.default_content_type is not None:
            default_content_type = bundle.default_content_type
        else:
            default_content_type = MemoryContentType.INITIAL_FACTUAL

    json_path = Path(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        initial_memories = json.load(f)

    report = InitialLoadReport(
        source_path=str(json_path),
        total_agents_in_file=len(initial_memories),
    )

    pre_dropped = {}
    if hasattr(memory_engine, "dropped_counts"):
        pre_dropped = dict(memory_engine.dropped_counts)

    loaded_agent_count = 0
    for agent_id, memories in initial_memories.items():
        if agent_id_filter is not None and agent_id not in agent_id_filter:
            report.skipped_missing_agent += len(memories)
            continue
        any_loaded = False
        for mem in memories:
            category = mem.get("category", "general")
            content_type = classify(
                {"category": category},
                domain_mapping=domain_mapping,
                domain=domain,
            )
            if (
                content_type is MemoryContentType.EXTERNAL_EVENT
                and category not in external_event_whitelist
            ):
                content_type = default_content_type

            metadata = {
                "category": category,
                "importance": mem.get("importance", 0.5),
                "source": mem.get("source", "survey"),
                "year": 0,
                "content_type": content_type.value,
            }
            memory_engine.add_memory(agent_id, mem["content"], metadata)
            key = content_type.value
            report.classified_by_type[key] = (
                report.classified_by_type.get(key, 0) + 1
            )
            any_loaded = True
        if any_loaded:
            loaded_agent_count += 1

    if hasattr(memory_engine, "dropped_counts"):
        post_dropped = dict(memory_engine.dropped_counts)
        for ct, count in post_dropped.items():
            delta = count - pre_dropped.get(ct, 0)
            if delta > 0:
                report.dropped_counts[ct] = delta

    total_submitted = sum(report.classified_by_type.values())
    total_dropped = sum(report.dropped_counts.values())
    report.loaded_count = total_submitted - total_dropped
    report.total_agents_loaded = loaded_agent_count
    return report


__all__ = ["InitialLoadReport", "load_initial_memories_from_json"]
