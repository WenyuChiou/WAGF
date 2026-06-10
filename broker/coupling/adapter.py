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
        # inc 3: a continuous-state coupling has no event source — zero events.
        events = (
            self.sources.event_src.draw_events(self._period)
            if self.sources.event_src is not None else []
        )
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
        """Commit the already-governed action, bracketed by the contract's
        runtime input checks (inc 3 — checks #1/#3 on the agent->world side
        plus the execution-sampling guard). These are CONTRACT checks, not
        governance: governance (domain rules, solvency, feasibility) ran in
        the retry loop; here we only enforce that what crosses the boundary
        matches the declared interface. They live HERE — not in
        skill_broker_engine (preserves the zero-core-edit property) and not
        in commit_world_delta (domain code cannot be its own guard)."""
        params = getattr(approved_skill, "parameters", None) or {}
        specs = self.contract.input_specs()
        problems: List[str] = []
        # PRE — agent-side writes: declared inputs are range-checked (#1);
        # writing a world_to_agent observation key is a direction breach (#3).
        for name, value in params.items():
            vs = specs.get(name)
            if vs is not None:
                rv = vs.range_violation(value)
                if rv:
                    problems.append(f"input {rv}")
            elif self.contract.check_direction(name) == "world":
                problems.append(
                    f"{name}: agent-side write to a world_to_agent observation "
                    "(direction check #3 — observations are world-owned)"
                )
        if problems:
            raise CouplingViolation(f"input contract violations (pre-commit): {problems}")

        delta = self.sources.commit_world_delta(approved_skill)

        # POST — committed values of declared inputs must satisfy their range,
        # and a value_source="proposal" input must equal the agent-authored
        # parameter (execution-sampling guard: a world-side re-sample of an
        # agent-owned setpoint is the divergence bug class).
        for key, val in (delta.world_changes or {}).items():
            vs = specs.get(key)
            if vs is None:
                continue  # world-side bookkeeping (audit payload), not a declared input
            rv = vs.range_violation(val)
            if rv:
                problems.append(f"committed {rv}")
                continue  # non-numeric val makes float() below unsafe; rv captured it (review W2)
            if vs.value_source == "proposal":
                if key not in params:
                    problems.append(
                        f"{key}: committed a proposal-sourced input absent from the "
                        "approved skill's parameters (execution-sampling guard)"
                    )
                elif abs(float(val) - float(params[key])) > 1e-9:
                    problems.append(
                        f"{key}: committed value {val} diverges from the approved "
                        f"proposal's {params[key]} (execution-sampling guard)"
                    )
        if problems:
            raise CouplingViolation(f"input contract violations (post-commit): {problems}")

        return ExecutionResult(
            success=True,
            state_changes=dict(delta.agent_state_changes),
            action_context={
                "world_delta": delta.audited_summary(),
                "contention_rule": delta.contention_rule,
            },
        )

    # ------------------------------------------------------------------
    # Reproducibility provenance (inc 3 — review P0-3). Duck-typed read by
    # ExperimentRunner._collect_reproducibility_metadata: a coupled run's
    # manifest must pin the WORLD side (hosted-model identity, contract
    # identity), not just the LLM side.
    # ------------------------------------------------------------------
    def get_provenance(self) -> Dict[str, Any]:
        import hashlib

        # CouplingContract is a frozen dataclass of frozen VarSpecs — its repr
        # is deterministic, so the sha256 is a stable contract identity.
        contract_sha = hashlib.sha256(repr(self.contract).encode("utf-8")).hexdigest()[:16]
        prov: Dict[str, Any] = {
            "adapter_class": type(self).__name__,
            "contract_sha256": contract_sha,
            "bundle_class": type(self.sources).__name__,
            "wrapped_engine_class": type(self.real_engine).__name__ if self.real_engine is not None else None,
        }
        fn = getattr(self.sources, "get_provenance", None)
        if callable(fn):
            try:
                prov["bundle_provenance"] = fn()
            except Exception as exc:  # provenance must never fail a run
                prov["bundle_provenance"] = {"error": repr(exc)}
        src = self.sources.event_src
        if src is not None:
            fn = getattr(src, "get_provenance", None)
            if callable(fn):
                try:
                    prov["event_source_provenance"] = fn()
                except Exception as exc:
                    prov["event_source_provenance"] = {"error": repr(exc)}
        return prov


__all__ = ["EnvironmentCouplingAdapter", "CouplingViolation"]
