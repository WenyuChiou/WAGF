"""Memory write policy - broker-level content-type-aware governance.

Controls what content may enter agent memory. The policy is a set of
allow_* flags, one per canonical MemoryContentType, plus a loader that
reads the policy block from an experiment config yaml.

This module is DOMAIN-NEUTRAL. It does not encode any specific experiment's
category vocabulary. Domain-specific category mappings are passed to the
PolicyFilteredMemoryEngine and classify() function via a separate
``domain_mapping`` parameter.

See .ai/broker_memory_governance_architecture.md for the full architecture
and .ai/broker_memory_policy_design.md for the audit that drove the
original MA-scoped fix.
"""
from dataclasses import dataclass, fields
from typing import Any, Dict, Optional

from broker.components.memory.content_types import MemoryContentType


_DEPRECATED_FIELD_NAMES = {
    "decision_reasoning": "allow_agent_self_report",
    "reflection_quotes": "allow_agent_reflection_quote",
    "initial_pmt_narratives": "allow_initial_narrative",
    "initial_factual_seeds": "allow_initial_factual",
    "external_events": "allow_external_event",
    "institutional_events": "allow_institutional_state",
    "constructs": None,
}


@dataclass(frozen=True)
class MemoryWritePolicy:
    """Content-type-aware memory write policy.

    Each field corresponds one-to-one to a MemoryContentType value. Setting
    a field to False causes the PolicyFilteredMemoryEngine to silently drop
    writes classified as that content type; True allows them through.

    All fields default to the CLEAN_POLICY values (safe defaults that block
    the rationalization ratchet). Construct LEGACY_POLICY explicitly to
    reproduce pre-fix behavior in reproducibility-sensitive reruns.
    """

    allow_external_event: bool = True
    allow_agent_action: bool = True
    allow_social_observation: bool = True
    allow_institutional_state: bool = True
    allow_institutional_reflection: bool = True
    allow_initial_factual: bool = True

    allow_agent_self_report: bool = False
    allow_agent_reflection_quote: bool = False
    allow_initial_narrative: bool = False

    def allows(self, content_type: MemoryContentType) -> bool:
        """Return True if the given content type is allowed to enter memory."""
        field_name = f"allow_{content_type.value}"
        return bool(getattr(self, field_name, False))

    def to_dict(self) -> Dict[str, bool]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


LEGACY_POLICY = MemoryWritePolicy(
    allow_external_event=True,
    allow_agent_action=True,
    allow_social_observation=True,
    allow_institutional_state=True,
    allow_institutional_reflection=True,
    allow_initial_factual=True,
    allow_agent_self_report=True,
    allow_agent_reflection_quote=True,
    allow_initial_narrative=True,
)

CLEAN_POLICY = MemoryWritePolicy()


def load_from_config(cfg: Optional[Dict[str, Any]]) -> MemoryWritePolicy:
    """Construct a MemoryWritePolicy from a config dict.

    Rules:
      * None or empty config -> LEGACY_POLICY (reproducibility guarantee)
      * Missing memory_write_policy block -> LEGACY_POLICY
      * Present block -> CLEAN_POLICY defaults with the specified keys
        overriding defaults. Specifying the block signals opt-in to the
        new governance system.
      * Unknown (future) keys: silently ignored for forward compatibility
      * Deprecated (old MA-scoped) keys: raise ValueError with migration hint

    The rationale for inheriting CLEAN defaults instead of LEGACY: if you
    bothered to add the block at all, you're aware of the new system and
    probably want the safe defaults for anything you didn't explicitly
    set. Callers that want full legacy behavior must omit the block.
    """
    if not cfg:
        return LEGACY_POLICY
    block = cfg.get("memory_write_policy")
    if block is None:
        return LEGACY_POLICY
    if not isinstance(block, dict):
        raise TypeError(
            f"memory_write_policy must be a dict, got {type(block).__name__}"
        )

    deprecated_found = []
    for old_name, new_name in _DEPRECATED_FIELD_NAMES.items():
        if old_name in block:
            hint = f"rename to `{new_name}`" if new_name else "remove it"
            deprecated_found.append(f"  - `{old_name}`: {hint}")
    if deprecated_found:
        raise ValueError(
            "memory_write_policy uses deprecated MA-scoped field names. "
            "The policy has been refactored to use content-type-aware names. "
            "Migration required:\n" + "\n".join(deprecated_found)
        )

    valid_keys = {f.name for f in fields(MemoryWritePolicy)}
    kwargs = {k: bool(v) for k, v in block.items() if k in valid_keys}
    return MemoryWritePolicy(**{**CLEAN_POLICY.to_dict(), **kwargs})


__all__ = [
    "MemoryWritePolicy",
    "LEGACY_POLICY",
    "CLEAN_POLICY",
    "load_from_config",
]
