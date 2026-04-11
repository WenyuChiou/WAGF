"""Canonical memory content type taxonomy.

Every add_memory call across the broker should tag its metadata with a
``content_type`` key whose value is one of the MemoryContentType enum values
(or the enum member itself). The policy filter consults this tag to decide
whether the write is allowed under the current MemoryWritePolicy.

Callers that don't tag content_type will be classified by heuristic rules
defined in policy_classifier.py, which falls back to EXTERNAL_EVENT (safe)
if nothing matches.
"""
from enum import Enum


class MemoryContentType(str, Enum):
    """Semantic classification of memory content, independent of domain.

    The enum values are short snake_case strings so they can be stored in
    config yaml, JSON, and metadata dicts without conversion.
    """

    # -- Safe content (default allowed in CLEAN_POLICY) --
    EXTERNAL_EVENT = "external_event"
    """External physical or institutional event observed by the agent.
    Examples: flood hit, structural damage, no-flood year, change in
    published subsidy rate the agent reads from a gazette."""

    AGENT_ACTION = "agent_action"
    """Record of an action the agent took in a prior year, factual.
    Example: "Year 5: I chose buy_insurance." """

    SOCIAL_OBSERVATION = "social_observation"
    """Aggregated observation of neighbors or peer group behavior.
    Example: "3 of my 4 neighbors elevated their homes this year." """

    INSTITUTIONAL_STATE = "institutional_state"
    """Institutional agent recording a state change it made.
    Example: "Set subsidy rate to 50%; budget remaining 80%." """

    INSTITUTIONAL_REFLECTION = "institutional_reflection"
    """Government or insurance agent reflection summary. These agents are
    not subject to the rationalization ratchet because their constructs
    are not part of the PMT analysis for households."""

    INITIAL_FACTUAL = "initial_factual"
    """Pre-simulation seed memory containing verifiable profile facts.
    Examples: flood zone, insurance status, number of generations in area.
    Does not embed first-person psychological narrative."""

    # -- Risky content (default DENIED in CLEAN_POLICY) --
    AGENT_SELF_REPORT = "agent_self_report"
    """LLM-generated first-person narrative of the agent's own
    psychological state or decision rationale. Writing this back to memory
    causes the rationalization ratchet - the LLM reads its own prior
    confabulations as evidence in subsequent decisions and self-reinforces.
    Example: "I decided to do_nothing because I have high place attachment." """

    AGENT_REFLECTION_QUOTE = "agent_reflection_quote"
    """Agent year-end reflection entry that embeds a verbatim quote of a
    previously retrieved memory. Creates a memory-of-memory duplication
    that compounds the ratchet when the quoted snippet is itself a prior
    self-report."""

    INITIAL_NARRATIVE = "initial_narrative"
    """Pre-simulation seed memory containing first-person psychological
    narrative derived from survey construct scores. Priming effect: the
    LLM reads these Y1 seeds as if they were its own thoughts and anchors
    on them from the very first decision."""


__all__ = ["MemoryContentType"]
