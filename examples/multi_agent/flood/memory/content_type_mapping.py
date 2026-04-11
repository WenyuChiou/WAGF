"""Domain-specific category -> MemoryContentType mapping for MA flood.

Imported by run_unified_experiment.py when wiring the
PolicyFilteredMemoryEngine. The policy filter consults this dict when
classifying memory writes; categories listed here override the
broker-level default rules.

This is the ONLY file in the MA flood example that encodes domain
category vocabulary. Future MA experiments create their own equivalent
file (e.g. DROUGHT_CATEGORY_TO_CONTENT_TYPE) and pass it to
with_memory_write_policy().
"""
from typing import Dict

from broker.components.memory.content_types import MemoryContentType


FLOOD_CATEGORY_TO_CONTENT_TYPE: Dict[str, MemoryContentType] = {
    # --- Factual event seeds / runtime events ---
    "flood_experience": MemoryContentType.EXTERNAL_EVENT,
    "flood_event": MemoryContentType.EXTERNAL_EVENT,
    "insurance_history": MemoryContentType.INITIAL_FACTUAL,
    "insurance_claim": MemoryContentType.INITIAL_FACTUAL,
    "social_connections": MemoryContentType.INITIAL_FACTUAL,
    "social_interaction": MemoryContentType.INITIAL_FACTUAL,
    "flood_zone": MemoryContentType.INITIAL_FACTUAL,
    "risk_awareness": MemoryContentType.INITIAL_FACTUAL,
    "social_observation": MemoryContentType.SOCIAL_OBSERVATION,

    # --- Institutional state changes ---
    "policy_decision": MemoryContentType.INSTITUTIONAL_STATE,

    # --- RATCHET SOURCES (initial seeds with first-person PMT narrative) ---
    "place_attachment": MemoryContentType.INITIAL_NARRATIVE,
    "government_trust": MemoryContentType.INITIAL_NARRATIVE,
    "adaptation_action": MemoryContentType.INITIAL_NARRATIVE,
    "government_notice": MemoryContentType.INITIAL_NARRATIVE,

    # --- RATCHET SOURCES (runtime LLM self-report) ---
    "decision_reasoning": MemoryContentType.AGENT_SELF_REPORT,
    "reflection": MemoryContentType.AGENT_REFLECTION_QUOTE,
}


__all__ = ["FLOOD_CATEGORY_TO_CONTENT_TYPE"]
