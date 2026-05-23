"""
DefaultDomainPack — no-op implementation of :class:`DomainPack`.

Returned by :func:`DomainPackRegistry.get_or_default` when no pack is
registered for the requested domain. Every method returns a benign
default so broker code can call into the pack unconditionally without
guarding for ``None``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from broker.domains.protocol import BuiltinCheck, EventHandler


class DefaultDomainPack:
    """Sentinel pack — every method is a safe no-op.

    Used when:
      - The experiment hasn't declared a ``domain`` (early bring-up of
        a new application).
      - The declared domain is unknown to the registry (typo or pack
        not yet imported).
      - A test exercises the pipeline with no domain wiring.

    Behavioural contract: calling any method MUST NOT mutate state.
    """

    name: str = "default"

    # ─── Reflection ───────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        return None

    def reflection_questions(self) -> List[str]:
        return []

    def reflection_persona(self) -> Optional[str]:
        return None

    def reflection_trait_labels(self, context: Any) -> List[str]:
        return []

    # ─── Memory / importance / emotion ────────────────────────────

    def importance_profiles(self) -> Dict[str, float]:
        return {}

    def compute_importance(self, context: Any, base: float = 0.5) -> float:
        return base

    def classify_emotion(self, decision: str, context: Any) -> str:
        return "neutral"

    def emotional_keywords(self) -> Dict[str, str]:
        return {}

    def retrieval_weights(self) -> Dict[str, float]:
        # Equal weights — no domain-informed bias.
        return {"W_recency": 1.0 / 3, "W_importance": 1.0 / 3, "W_context": 1.0 / 3}

    # ─── Skills ────────────────────────────────────────────────────

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        return {}

    def extreme_actions(self) -> Set[str]:
        return set()

    # ─── Events ────────────────────────────────────────────────────

    def event_handlers(self) -> Dict[str, EventHandler]:
        return {}

    def agent_impact_handlers(self) -> Dict[str, EventHandler]:
        return {}

    # ─── Memory policy (Phase 6K-A) ───────────────────────────────

    def memory_policy(self):  # -> Optional[MemoryPolicyBundle]
        return None

    # ─── Context provider hooks ────────────────────────────────────

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        return ""

    # ─── Validators ────────────────────────────────────────────────

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        return {}

    # ─── Memory templates ─────────────────────────────────────────

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        return []

    # ─── Perception (Phase 6H DomainPack v2) ──────────────────────

    def perception_descriptors(self) -> Dict[str, Any]:
        return {}

    def perception_field_policy(self) -> Dict[str, List[str]]:
        return {}

    def passthrough_agent_types(self) -> Set[str]:
        return set()

    def affordability_constraints(self) -> Dict[str, Any]:
        return {}

    # ─── Retrieval tuning (Phase 6H DomainPack v2) ────────────────

    def retrieval_policy(self) -> Dict[str, Any]:
        return {}

    # ─── Population drift monitoring (Phase 6L-A) ─────────────────

    def drift_policy(self) -> Dict[str, Any]:
        return {}

    # ─── Population-governance thresholds (Phase 6L-B) ────────────

    def population_governance_policy(self) -> Dict[str, Any]:
        return {}
