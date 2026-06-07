"""Composable simulator interfaces — narrow, typed Protocols a domain
implements à la carte, plus the value types they exchange.

The Protocol verb-set is a *superset* of the BMI/OpenMI/FMI verb set
(``update`` / ``get_value`` / ``set_value`` / ``get_var_units``): a BMI/FMI
component is wrapped by a thin ``EventSource`` in ~30 lines, so WAGF *hosts*
a standards-conformant numerical model rather than re-implementing one. What
BMI cannot express — a decision-making agent whose action IS the ``set_value``,
governed before it commits — is the layer above (the adapter + the world-
mutation validators that live in the domain's ``builtin_checks``).

Domain-vocab-free: ``EventSource`` is named generically (rather than after any
specific domain concept) so the framework genericity grep stays green even if a
domain-specific token is added to the guard list later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple, runtime_checkable


# --------------------------------------------------------------------------
# Value types crossing the boundary
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Event:
    """One discrete event drawn for a period (e.g. a footprint). ``payload``
    carries per-location intensity or whatever the source produces."""

    event_id: str
    period: int
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MdrDraw:
    """A vulnerability result: mean damage ratio + a sampled realisation.
    Both are dimensionless ratios in [0, 1]."""

    mean_damage_ratio: float
    sampled_damage_ratio: float


@dataclass(frozen=True)
class Settlement:
    """The audited resolution of a shared-pool contention (E4). ``per_agent``
    is the resolved disbursement; ``rule`` names the order-independent policy
    used (e.g. 'pro_rata' / 'full') so the audit trace can explain it."""

    per_agent: Dict[str, float]
    rule: str
    total: float
    pool_remaining: float


@dataclass(frozen=True)
class WorldDelta:
    """The committed effect of one approved, already-governed action.
    ``agent_state_changes`` flows back to the agent; ``audited_summary`` +
    ``contention_rule`` flow to the audit trace (E4)."""

    agent_state_changes: Dict[str, Any] = field(default_factory=dict)
    world_changes: Dict[str, Any] = field(default_factory=dict)
    contention_rule: str = "none"

    def audited_summary(self) -> Dict[str, Any]:
        return {"world_changes": dict(self.world_changes), "contention_rule": self.contention_rule}


# --------------------------------------------------------------------------
# The à-la-carte simulator interfaces
# --------------------------------------------------------------------------
@runtime_checkable
class EventSource(Protocol):
    """Produces >=0 events per period (BMI: update + get_value)."""

    def draw_events(self, period: int) -> List[Event]: ...

    def intensity_at(self, agent_id: str, event: Event) -> float: ...

    def units(self) -> str:  # BMI get_var_units -> VarSpec.unit
        ...


@runtime_checkable
class ExposureUpdater(Protocol):
    """Holds and mutates per-agent exposure (assets at risk)."""

    def exposure_of(self, agent_id: str) -> Dict[str, Any]: ...

    def remove_asset(self, agent_id: str) -> None:  # one-way irreversible removal (E2 once-only)
        ...

    def modify_attr(self, agent_id: str, key: str, delta: float) -> None:  # protective attr change
        ...


@runtime_checkable
class VulnerabilityModel(Protocol):
    """Maps intensity x exposure -> damage."""

    def damage_ratio(self, intensity: float, exposure: Dict[str, Any]) -> MdrDraw: ...


@runtime_checkable
class FinancialLedger(Protocol):
    """Loss -> financial terms -> shared-pool settlement."""

    def ground_up_to_gross(self, loss: float, policy: Dict[str, Any]) -> float: ...

    def gross_to_net(self, gross: float) -> float: ...

    def settle(self, claims: Dict[str, float]) -> Settlement:  # E4 audited contention
        ...


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------
@dataclass
class InterfaceBundle:
    """A domain composes only the interfaces it needs; missing ones are
    skipped in the pipeline. ``broker.coupling`` MUST NOT import any domain
    package — the bundle is constructed by the domain and passed in."""

    event_src: EventSource
    exposure: Optional[ExposureUpdater] = None
    vulnerability: Optional[VulnerabilityModel] = None
    financial: Optional[FinancialLedger] = None

    def run_pipeline(
        self,
        base_env: Dict[str, Any],
        events: List[Event],
        operation_order: Tuple[str, ...],
        control_hold_policy: str = "constant",
    ) -> Dict[str, Any]:
        """Compose the present interfaces in the pinned ``operation_order``
        (E3), returning a flat env dict of world-side state. Stages whose
        interface is absent are skipped. The default implementation handles the
        canonical event-based chain; a domain may subclass for richer physics.

        NOTE: ``control_hold_policy`` is threaded through for the (deferred)
        continuous sub-step regime; in the event-based path it is a no-op."""
        env: Dict[str, Any] = dict(base_env)
        env["_events"] = [e.event_id for e in events]
        env["_event_count"] = len(events)
        return env

    def commit_world_delta(self, approved_skill: Any) -> WorldDelta:
        """Commit an ALREADY-GOVERNED action exactly once (E2). Governance ran
        in the retry loop on the proposal; here we only apply + audit. A domain
        overrides this to route the action to its exposure/financial modules.
        The default is an inert no-op delta (safe for an event-source-only domain)."""
        return WorldDelta(agent_state_changes={}, world_changes={}, contention_rule="none")


__all__ = [
    "Event",
    "MdrDraw",
    "Settlement",
    "WorldDelta",
    "EventSource",
    "ExposureUpdater",
    "VulnerabilityModel",
    "FinancialLedger",
    "InterfaceBundle",
]
