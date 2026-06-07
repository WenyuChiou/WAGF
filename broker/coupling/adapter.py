"""``EnvironmentCouplingAdapter`` — wraps the object the runner already steps
(``sim_engine``) so a domain can host diverse external simulators behind the
single coupling contract, with NO edit to broker/ core.

The adapter satisfies the duck-typed ``SimulationEngineProtocol`` (advance_*)
and ``SkillExecutorProtocol`` (execute_skill), so the domain runner injects it
in place of the raw engine: ``ExperimentRunner(sim_engine=adapter)``.

Critical division of labour (the design's load-bearing correction):
  * ``advance_step`` does world->agent: pump the interface bundle in the
    contract's pinned order, run the unit / cadence / missing-value checks,
    and project the contracted observations into the flat env dict.
  * ``execute_skill`` is a PURE COMMITTER. Governance on a world-mutating
    action does NOT happen here — it happens earlier, as a ``builtin_checks``
    ERROR validator on the SkillProposal inside the existing governance retry
    loop (so a rejection genuinely re-prompts; a veto here would silently drop
    the delta after the loop already closed APPROVED). Here we only apply the
    already-approved delta once (E2) and record the contention resolution (E4).
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from ..interfaces.skill_types import ApprovedSkill, ExecutionResult
from .contract import CouplingContract
from .interfaces import InterfaceBundle

logger = logging.getLogger(__name__)


class CouplingViolation(RuntimeError):
    """Raised when a contract check fails at runtime under ``fail_loud``."""


class EnvironmentCouplingAdapter:
    """Generic adapter; domain-vocab-free."""

    def __init__(
        self,
        real_engine: Any,
        contract: CouplingContract,
        sources: InterfaceBundle,
        agent_lookup: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.real_engine = real_engine
        self.contract = contract
        self.sources = sources
        self.agent_lookup = agent_lookup
        self._period = 0
        # Validate the contract's static checks once, up front (fail-fast).
        static = contract.check_units() + contract.check_cadence()
        if static:
            raise CouplingViolation(f"CouplingContract static checks failed: {static}")

    # ------------------------------------------------------------------
    # SimulationEngineProtocol — world -> agent
    # ------------------------------------------------------------------
    def advance_step(self) -> Dict[str, Any]:
        self._period += 1
        base = self._advance_real()
        events = self.sources.event_src.draw_events(self._period)
        env = self.sources.run_pipeline(
            base, events, self.contract.operation_order, self.contract.control_hold_policy
        )
        self._validate_observations(env)  # numerical-correctness #1 at runtime
        env["current_year"] = base.get("current_year", self._period)
        return env

    # The protocol declares advance_year; alias it so isinstance() + the
    # runner's advance_year fallback both see the adapter as conformant.
    def advance_year(self) -> Dict[str, Any]:
        return self.advance_step()

    def _advance_real(self) -> Dict[str, Any]:
        """Pull the base per-tick dict from the wrapped engine (advance_step
        preferred, then advance_year), tolerating a None/absent engine."""
        if self.real_engine is None:
            return {"current_year": self._period}
        for meth in ("advance_step", "advance_year"):
            fn = getattr(self.real_engine, meth, None)
            if callable(fn):
                out = fn()
                if isinstance(out, dict):
                    return dict(out)
                logger.warning(
                    "[coupling] wrapped engine %s() returned non-dict %s; falling "
                    "back to {current_year} (observations will be supplied by the "
                    "bundle pipeline)", meth, type(out).__name__,
                )
                return {"current_year": self._period}
        return {"current_year": self._period}

    def _validate_observations(self, env: Dict[str, Any]) -> None:
        """Apply ``on_missing`` policy + range checks to each contracted
        observation. Never silent-zero: a missing ``fail_loud`` variable
        raises; ``last_good`` / ``quarantine`` are handled by the domain
        pipeline (the adapter only enforces the declared policy boundary)."""
        problems: List[str] = []
        for vs in self.contract.observations:
            if vs.name not in env or env[vs.name] is None:
                if vs.on_missing == "fail_loud":
                    problems.append(f"{vs.name}: missing (on_missing=fail_loud)")
                continue
            rv = vs.range_violation(env[vs.name])
            if rv:
                problems.append(rv)
        if problems:
            raise CouplingViolation(f"observation contract violations: {problems}")

    # ------------------------------------------------------------------
    # SkillExecutorProtocol — agent -> world (PURE COMMITTER; no re-gate)
    # ------------------------------------------------------------------
    def execute_skill(self, approved_skill: ApprovedSkill) -> ExecutionResult:
        delta = self.sources.commit_world_delta(approved_skill)
        return ExecutionResult(
            success=True,
            state_changes=dict(delta.agent_state_changes),
            action_context={
                "world_delta": delta.audited_summary(),
                "contention_rule": delta.contention_rule,
            },
        )


__all__ = ["EnvironmentCouplingAdapter", "CouplingViolation"]
