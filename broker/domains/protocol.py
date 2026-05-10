"""
DomainPack Protocol — single facade for all domain-specific behavior.

Phase 6C-v2 (2026-05-10): a new application domain (vaccination, traffic,
finance, etc.) implements this Protocol once and registers it via
``DomainPackRegistry.register("<name>", pack)``. Broker code queries the
pack via ``DomainPackRegistry.get_or_default(domain)`` and delegates
domain-specific decisions to the pack's methods.

Design rationale
================
Before this layer, broker code had ``if agent_type == "household":``
gates and ``if event_type == "flood":`` chains hardcoded in 8+ hot-spot
sites. New domains either had to edit those branches (brittle) or
work around them with custom builders (incomplete). DomainPack
consolidates the dispatch surface so:

1. New domains implement only what they need (every method has a
   sensible default in :class:`DefaultDomainPack`).
2. Adding a domain is one class + one registration call. Zero edits
   under ``broker/``.
3. The five existing specific registries (Skill, Validator, Filter,
   MemoryEngine, Event) stay as concrete state stores; ``DomainPack``
   is the facade that wires them together.

Backward compatibility
======================
Water (irrigation + flood) is migrated to :class:`IrrigationDomainPack`
and :class:`FloodDomainPack` subclasses. Their behavior is byte-identical
to the pre-refactor hardcodes — verified by regression tests in
``tests/test_domain_pack_contract.py``.
"""
from __future__ import annotations

from typing import (
    Any, Callable, Dict, List, Optional, Protocol, Set,
    runtime_checkable,
)


# ─────────────────────────────────────────────────────────────────────
# Type aliases (kept loose — concrete shapes are owned by their modules)
# ─────────────────────────────────────────────────────────────────────

EventHandler = Callable[[Any, Dict[str, Any]], None]
"""(event, env_state) -> None. Mutates env_state in place."""

BuiltinCheck = Callable[..., List[Any]]
"""(skill_name, rules, context) -> List[ValidationResult]. Re-typed in
ValidatorRegistry; here we keep loose to avoid an import cycle."""


# ─────────────────────────────────────────────────────────────────────
# Protocol
# ─────────────────────────────────────────────────────────────────────

@runtime_checkable
class DomainPack(Protocol):
    """Bundle of domain-specific behaviors queried by the broker pipeline.

    Every method has a no-op default in :class:`DefaultDomainPack`.
    Implementers override only what's relevant for their domain.

    Attributes
    ----------
    name : str
        Domain identifier matching the value passed to validators
        (e.g., ``"irrigation"``, ``"flood"``, ``"vaccination"``).
    """

    name: str

    # ─── Reflection ───────────────────────────────────────────────

    def reflection_status_text(self, context: Any) -> Optional[str]:
        """Per-agent narrative status block injected into the individual
        reflection prompt. Return ``None`` to skip — the prompt then
        contains only the generic identity line.

        Replaces the hardcoded flood block in
        ``broker/components/cognitive/reflection.py:301-313``.
        """
        ...

    def reflection_questions(self) -> List[str]:
        """Prompt questions for the reflection LLM call. Empty list →
        broker falls back to ``agent_types.yaml`` ``reflection.questions``
        or the legacy ``REFLECTION_QUESTIONS`` dict."""
        ...

    def reflection_persona(self) -> Optional[str]:
        """Persona instruction prepended to reflection prompts (e.g.,
        "Speak in first person as a farmer..."). ``None`` → use YAML
        config or default."""
        ...

    # ─── Memory / importance / emotion ────────────────────────────

    def importance_profiles(self) -> Dict[str, float]:
        """Named importance baselines (e.g.,
        ``{"first_shortage": 0.92, "drought_year": 0.95}``).
        Replaces the hardcoded flood profiles in
        ``broker/components/cognitive/reflection.py:96-98``."""
        ...

    def compute_importance(self, context: Any, base: float = 0.5) -> float:
        """Dynamic importance score for a memory derived from context."""
        ...

    def classify_emotion(self, decision: str, context: Any) -> str:
        """Emotion label for a memory anchored on a decision +
        environmental context (e.g., ``"critical"``, ``"major"``,
        ``"minor"``, ``"neutral"``)."""
        ...

    def emotional_keywords(self) -> Dict[str, str]:
        """Map of domain-specific event keywords → emotion labels."""
        ...

    def retrieval_weights(self) -> Dict[str, float]:
        """Weights summing to 1.0 over (recency, importance, context)
        for the memory retrieval scoring."""
        ...

    # ─── Skills ────────────────────────────────────────────────────

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        """Per-skill emotion + importance metadata for memory tagging.

        Replaces the hardcoded
        ``if skill_name in {"elevate_house", "relocate"}: ... elif
        "buy_insurance": ...`` chain in
        ``broker/core/experiment_runner.py:383-388``.

        Returns ``{}`` for skills that should use the base/default
        importance and the adapter's classify_emotion output.
        """
        ...

    def extreme_actions(self) -> Set[str]:
        """Set of skill names treated as 'extreme' by the thinking
        validator (e.g., one-way irreversible actions). Replaces the
        ``ThinkingValidator(extreme_actions=...)`` constructor kwarg
        currently set per-domain in ``validator_bundles.py``."""
        ...

    # ─── Events ────────────────────────────────────────────────────

    def event_handlers(self) -> Dict[str, EventHandler]:
        """Mapping of ``event_type → handler(event, env_state)``.

        Replaces the hardcoded ``if event.event_type == "flood": ...
        elif "no_flood": ... elif "subsidy_change": ...`` chain in
        ``broker/components/events/ma_manager.py:275-330``.

        New domains register their own event types (e.g., for
        vaccination: ``{"outbreak": ..., "vaccine_rollout": ...}``).
        """
        ...

    # ─── Context provider hooks ────────────────────────────────────

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        """Domain-specific narrative text for marginalised-group agents
        injected by ``FinancialCostProvider``. Default empty string —
        no MG-specific content. Replaces the hardcoded
        ``"Passaic River Basin"`` in
        ``broker/components/context/providers.py:708``.
        """
        ...

    # ─── Validators (already partially handled by ValidatorRegistry) ─

    def builtin_checks(self) -> Dict[str, List[BuiltinCheck]]:
        """Mapping of validator slot → list of builtin check functions.

        Slots: ``"physical"``, ``"personal"``, ``"social"``,
        ``"semantic"`` (``"thinking"`` uses ``extreme_actions()``
        instead).

        Default empty → falls back to ``ValidatorRegistry.get_checks(...)``
        registrations made by example packages directly (Phase 6B-1
        path remains valid).
        """
        ...

    # ─── Memory templates (initial agent memories) ────────────────

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        """Domain-specific initial memories generated from an agent
        profile at experiment startup. Default empty list → no
        initial memories injected. Replaces flood-specific
        ``FloodMemoryTemplateProvider`` (Phase 6B-2)."""
        ...
