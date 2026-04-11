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


_DEFAULT_RULES: Dict[str, MemoryContentType] = {
    "flood_experience": MemoryContentType.EXTERNAL_EVENT,
    "flood_event": MemoryContentType.EXTERNAL_EVENT,
    "damage": MemoryContentType.EXTERNAL_EVENT,
    "insurance_claim": MemoryContentType.INITIAL_FACTUAL,
    "insurance_history": MemoryContentType.INITIAL_FACTUAL,
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
) -> MemoryContentType:
    """Return the canonical content type for a memory write.

    Args:
        metadata: The metadata dict passed to ``add_memory``. May be None
            or empty.
        domain_mapping: Optional per-domain override. Keys are category
            name strings, values are MemoryContentType members. Looked up
            before the default rules; overrides any default.

    Returns:
        A MemoryContentType. Never raises - unclassifiable inputs return
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
