"""
Institutional-lifecycle extension point for heterogeneous multi-actor runs.

STATUS: EXPERIMENTAL (Multi-Actor Extension — Pre-1.0 API).
Inactive on default single-agent-type ``python -m broker.run`` runs; used by
multi-actor setups to dispatch year-boundary, per-decision, and year-end
lifecycle hooks per ``agent_type`` via ``SetupPack.institutional_lifecycle_handlers``
and :class:`~broker.components.coordination.bridge.MultiActorLifecycleBridge`.

- :class:`InstitutionalLifecycleHandler` — abstract base class with no-op
  lifecycle hooks (``pre_year``, ``post_decision``, ``post_year``).
- :meth:`SetupPack.institutional_lifecycle_handlers` — ``DomainPack`` hook
  returning ``Dict[str, InstitutionalLifecycleHandler]`` keyed by ``agent_type``.
- :meth:`SetupPack.multi_agent_env_keys` — ``DomainPack`` hook declaring
  allowed shared-environment keys for multi-agent runs.

Genericity invariant
====================
This module lives in ``broker/components/orchestration/`` so it MUST
contain no domain tokens. The ABC method signatures and supporting types
are domain-agnostic, verified by
``broker/tests/test_framework_invariants.py::TestDomainGenericity``.
"""
from __future__ import annotations

from abc import ABC
from typing import Any


class InstitutionalLifecycleHandler(ABC):
    """Generic per-agent-type lifecycle hooks for multi-agent runners.

    Subclasses implement zero or more of the three lifecycle phases to
    customise behaviour for a specific ``agent_type``. The base class
    provides no-op defaults so a subclass can override only the phases
    it needs — e.g. a budget-aware government handler might implement
    ``post_decision`` to mutate environment state, while an
    observational-only auditor handler might implement only
    ``post_year`` to emit metrics.

    Subclasses are registered via
    :meth:`broker.domains.protocol.SetupPack.institutional_lifecycle_handlers`
    on the relevant :class:`DomainPack`. The multi-agent runner looks
    up the handler for each agent's ``agent_type`` and dispatches the
    matching lifecycle phase.

    Lifecycle ordering (canonical, per phase):

    1. :meth:`pre_year` — called once for each agent at the start of
       each simulation year, BEFORE the agent's decision LLM call.
       Used for state initialisation, year-boundary cleanups, prompt
       context priming.
    2. :meth:`post_decision` — called once per agent per year AFTER
       the validator pipeline has accepted (or replaced) the agent's
       decision. Used for environment state mutation reflecting the
       decision (e.g. subsidy_rate updates, premium recalculation).
    3. :meth:`post_year` — called once per agent at the end of the
       year, AFTER ``post_decision`` for every agent in this phase.
       Used for cross-agent aggregation, memory-bridge writes,
       reflection triggers.

    The ``env`` parameter is the multi-agent runner's mutable
    environment dict. Handlers MAY mutate ``env``; the runner makes
    no thread-safety guarantee for parallel dispatch. The ``agent``
    parameter is whatever the runner stores in its agents dict — most
    commonly a :class:`broker.agents.BaseAgent` subclass instance,
    but handlers should rely only on the attributes they actually
    read (``agent_type``, ``dynamic_state``, ``fixed_attributes``).
    """

    def pre_year(self, agent: Any, year: int, env: dict) -> None:
        """No-op default. Override to run start-of-year logic for
        this agent_type. The runner calls this BEFORE the agent's
        decision LLM call.
        """
        return None

    def post_decision(
        self,
        agent: Any,
        decision: str,
        year: int,
        env: dict,
    ) -> None:
        """No-op default. Override to mutate environment state in
        response to the agent's accepted ``decision``. The runner
        calls this AFTER the validator pipeline has approved /
        replaced the proposed skill (``decision`` is the executed
        skill name, not the proposed one — per the EXECUTED-ONLY
        rule documented in MEMORY.md).
        """
        return None

    def post_year(self, agent: Any, year: int, env: dict) -> None:
        """No-op default. Override to run end-of-year logic for this
        agent_type. The runner calls this once per agent AFTER
        ``post_decision`` has fired for every agent in this phase.
        """
        return None


__all__ = ["InstitutionalLifecycleHandler"]
