"""
VaccinationDomainPack — DomainPack implementation for the vaccination example.

Phase 6C-v3 reference: this class subclasses :class:`broker.domains.protocol.DomainPack`
(structurally, via Protocol) and overrides only the methods that vaccination
needs to customise.  Every other method falls through to the default no-op
in :class:`broker.domains.default.DefaultDomainPack`.

Phase 6R-D-6b (2026-05-26): the previously-monolithic
``VaccinationDomainPack`` class body splits into six sub-pack mixins
matching the Phase 6R-D-1 sub-protocols vaccination overrides
(Reflection, Memory, Skill, Event, Governance, Setup —
PerceptionPack is NOT overridden so no VaccinationPerceptionMixin
exists). Public surface unchanged:
``DomainPackRegistry.register("vaccination", VaccinationDomainPack())``.

This module is the **canonical example** of how a new application domain
plugs into WAGF.  ~190 LOC; no broker/ edits required.
"""
from __future__ import annotations
from pathlib import Path

from typing import Any, Callable, Dict, List, Optional, Set

from broker.interfaces.action_taxonomy import (
    ActionTaxonomyEntry,
    load_action_taxonomy_from_skill_registry,
)
from broker.domains.default import DefaultDomainPack


# ─────────────────────────────────────────────────────────────────────
# Event handlers — translate event_type → env_state mutation.
# These get registered with WAGF's EventManager via DomainPack.event_handlers().
# ─────────────────────────────────────────────────────────────────────


def _handle_outbreak(event: Any, env_state: Dict[str, Any]) -> None:
    env_state["outbreak_active"] = True
    env_state["outbreak_severity"] = event.data.get("severity", 0.5)
    env_state["outbreak_message"] = event.description


def _handle_vaccine_rollout(event: Any, env_state: Dict[str, Any]) -> None:
    env_state["vaccine_supply"] = event.data.get("doses", 0)
    env_state["rollout_message"] = event.description


# ─────────────────────────────────────────────────────────────────────
# Sub-pack mixins (Phase 6R-D-6b, 2026-05-26)
# ─────────────────────────────────────────────────────────────────────


class VaccinationReflectionMixin:
    """ReflectionPack methods — vaccination-specific status narrative."""

    def reflection_status_text(self, context: Any) -> Optional[str]:
        if getattr(context, "agent_type", None) != "individual":
            return None
        parts = []
        vaccinated = getattr(context, "vaccinated", None)
        if vaccinated is None:
            vaccinated = getattr(context, "custom_traits", {}).get("vaccinated", False)
        if vaccinated:
            weeks = getattr(context, "weeks_since_dose", None)
            if weeks is None:
                weeks = getattr(context, "custom_traits", {}).get("weeks_since_dose", 0)
            parts.append(f"you received a vaccine dose {int(weeks)} week(s) ago")
        else:
            parts.append("you are currently unvaccinated")
        recent_infection = (
            getattr(context, "had_infection", None)
            or getattr(context, "custom_traits", {}).get("had_infection", False)
        )
        if recent_infection:
            parts.append("you recovered from a prior infection")
        return f"Current status: {', '.join(parts)}."

    def reflection_questions(self) -> List[str]:
        return []  # delegated to agent_types.yaml reflection.questions

    def reflection_persona(self) -> Optional[str]:
        return None


class VaccinationMemoryMixin:
    """MemoryPack methods — HBM-flavoured importance + emotion mapping
    plus outbreak-aware dynamic salience."""

    def importance_profiles(self) -> Dict[str, float]:
        return {
            "first_outbreak": 0.95,
            "post_vaccination": 0.80,
            "side_effect_event": 0.88,
            "stable_year": 0.55,
        }

    def compute_importance(self, context: Any, base: float = 0.65) -> float:
        importance = base
        outbreak = float(context.get("outbreak_severity", 0)) if isinstance(context, dict) else 0
        if outbreak > 0.6:
            importance = self.importance_profiles()["first_outbreak"]
        recent_decision = context.get("recent_decision", "") if isinstance(context, dict) else ""
        if recent_decision == "get_vaccinated":
            importance = max(importance, self.importance_profiles()["post_vaccination"])
        return round(min(1.0, max(0.0, importance)), 2)

    def classify_emotion(self, decision: str, context: Any) -> str:
        outbreak = float(context.get("outbreak_severity", 0)) if isinstance(context, dict) else 0
        if decision == "get_vaccinated" and outbreak > 0.6:
            return "critical"
        if decision == "refuse" and outbreak > 0.6:
            return "major"
        if decision == "delay":
            return "minor"
        return "important"

    def emotional_keywords(self) -> Dict[str, str]:
        return {
            "outbreak": "critical",
            "side_effect": "major",
            "vaccinated": "important",
            "delay": "minor",
            "refused": "important",
        }

    def retrieval_weights(self) -> Dict[str, float]:
        return {"W_recency": 0.40, "W_importance": 0.40, "W_context": 0.20}


class VaccinationSkillMixin:
    """SkillPack methods — get_vaccinated / refuse / delay metadata +
    taxonomy from YAML."""

    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        if skill_name == "get_vaccinated":
            return {"emotion": "major", "importance": 0.80, "source": "personal"}
        if skill_name == "refuse":
            return {"emotion": "important", "importance": 0.65, "source": "personal"}
        if skill_name == "delay":
            return {"emotion": "minor", "importance": 0.35, "source": "personal"}
        return {}

    def action_taxonomy(self) -> Dict[str, ActionTaxonomyEntry]:
        """Phase 6O-B — read taxonomy from vaccination_demo skill_registry.yaml."""
        yaml_path = (
            Path(__file__).resolve().parent.parent
            / "config"
            / "skill_registry.yaml"
        )
        return load_action_taxonomy_from_skill_registry(yaml_path)

    def extreme_actions(self) -> Set[str]:
        # Vaccination has no one-way irreversible actions in this PoC.
        return set()


class VaccinationEventMixin:
    """EventPack methods — outbreak + vaccine-rollout env mutators."""

    def event_handlers(self) -> Dict[str, Callable[[Any, Dict[str, Any]], None]]:
        return {
            "outbreak": _handle_outbreak,
            "vaccine_rollout": _handle_vaccine_rollout,
        }


class VaccinationGovernanceMixin:
    """GovernancePack methods — HBM framework selector + empty validator
    bundle (validators self-register via ValidatorRegistry)."""

    def psychological_framework(self) -> str:
        """Phase 6Q-D (2026-05-26): HBM (Health Belief Model) — the
        framework registered by
        ``examples/vaccination_demo/cognition/hbm_framework.py``
        at package import time. Matches the
        ``psychological_framework: hbm`` declaration in
        ``examples/vaccination_demo/config/agent_types.yaml``."""
        return "hbm"

    def builtin_checks(self) -> Dict[str, List[Callable]]:
        # Already registered via ValidatorRegistry at
        # examples/vaccination_demo/validators/__init__.py import time.
        return {}


class VaccinationSetupMixin:
    """SetupPack methods — no geographic narrative, no template-driven
    initial-memory seeding (PoC seeds inline in run_experiment.py)."""

    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        # Vaccination PoC does not inject geographic / MG-specific narrative.
        return ""

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        # PoC seeds memories inline in run_experiment.py; no template
        # provider needed.
        return []


# ─────────────────────────────────────────────────────────────────────
# Composite — VaccinationDomainPack
# ─────────────────────────────────────────────────────────────────────


class VaccinationDomainPack(
    VaccinationReflectionMixin,
    VaccinationMemoryMixin,
    VaccinationSkillMixin,
    VaccinationEventMixin,
    VaccinationGovernanceMixin,
    VaccinationSetupMixin,
    DefaultDomainPack,
):
    """DomainPack for vaccination decision-making (HBM-based).

    Phase 6R-D-6b (2026-05-26): composite of 6 sub-pack mixins. Public
    surface unchanged from Phase 6C-v3:
    ``DomainPackRegistry.register("vaccination", VaccinationDomainPack())``.
    """

    name: str = "vaccination"
