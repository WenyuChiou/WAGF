"""Legacy metadata classifier: map unlabeled metadata dicts to canonical
MemoryContentType values.

Priority of classification rules (first match wins):
  1. metadata["content_type"] set explicitly (string or enum)
  2. metadata["category"] present in domain_mapping or default_rules
  3. metadata["type"] heuristic (reasoning -> AGENT_SELF_REPORT, etc.)
  4. Safe fallback: EXTERNAL_EVENT

The fallback is EXTERNAL_EVENT rather than AGENT_SELF_REPORT on purpose:
we fail OPEN, not closed. A domain author who forgets to tag their writes
should still get their legitimate event/action memories through - the
worst case is that some risky writes slip through uncategorized, which
is recoverable via audit. The opposite would silently destroy legitimate
flood/damage memories and break the experiment invisibly.
"""
from typing import Any, Dict, Optional

from .content_types import MemoryContentType


# Phase 6K-A (2026-05-22): water-domain category keys (flood + damage +
# insurance-experience labels) relocated to
# FloodDomainPack.memory_policy().category_rules. The keys retained here
# are framework-agnostic — any agent-society domain may use them.
_DEFAULT_RULES: Dict[str, MemoryContentType] = {
    "social_observation": MemoryContentType.SOCIAL_OBSERVATION,
    "neighbor_observation": MemoryContentType.SOCIAL_OBSERVATION,
    "policy_decision": MemoryContentType.INSTITUTIONAL_STATE,
    "institutional_event": MemoryContentType.INSTITUTIONAL_STATE,
}

_TYPE_HEURISTICS: Dict[str, MemoryContentType] = {
    "reasoning": MemoryContentType.AGENT_SELF_REPORT,
    "self_report": MemoryContentType.AGENT_SELF_REPORT,
    "reflection": MemoryContentType.AGENT_REFLECTION_QUOTE,
    "event": MemoryContentType.EXTERNAL_EVENT,
    "action": MemoryContentType.AGENT_ACTION,
}


def classify(
    metadata: Optional[Dict[str, Any]],
    domain_mapping: Optional[Dict[str, MemoryContentType]] = None,
    domain: Optional[str] = None,
) -> MemoryContentType:
    """Return the canonical content type for a memory write.

    Args:
        metadata: The metadata dict passed to ``add_memory``. May be None
            or empty.
        domain_mapping: Optional per-call category → content-type override.
            Looked up before any DomainPack bundle or the generic default
            rules; an explicit caller mapping always wins.
        domain: Optional domain name. When supplied (and ``domain_mapping``
            is omitted), Phase 6K-A pulls the bundle from
            ``DomainPackRegistry.get_or_default(domain).memory_policy()``
            and uses its ``category_rules`` as the mapping. This is how
            water-domain category keys reach the classifier without
            living in generic broker code.

    Returns:
        A MemoryContentType. Never raises — unclassifiable inputs return
        ``MemoryContentType.EXTERNAL_EVENT`` (safe fallback).
    """
    if not metadata:
        return MemoryContentType.EXTERNAL_EVENT

    ct = metadata.get("content_type")
    if ct is not None:
        if isinstance(ct, MemoryContentType):
            return ct
        try:
            return MemoryContentType(ct)
        except ValueError:
            pass

    # Phase 6K-A (2026-05-22): a domain pack may supply category rules
    # via memory_policy().category_rules. Explicit caller-supplied
    # domain_mapping still wins to keep test-side overrides honoured.
    if domain_mapping is None and domain:
        try:
            from broker.domains.registry import DomainPackRegistry
            bundle = DomainPackRegistry.get_or_default(domain).memory_policy()
            if bundle is not None and bundle.category_rules:
                domain_mapping = bundle.category_rules
        except ImportError:
            pass

    category = metadata.get("category")
    if category:
        if domain_mapping and category in domain_mapping:
            return domain_mapping[category]
        if category in _DEFAULT_RULES:
            return _DEFAULT_RULES[category]

    type_hint = metadata.get("type")
    if type_hint and type_hint in _TYPE_HEURISTICS:
        return _TYPE_HEURISTICS[type_hint]

    return MemoryContentType.EXTERNAL_EVENT


__all__ = ["classify"]
