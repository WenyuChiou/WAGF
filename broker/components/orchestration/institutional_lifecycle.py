"""
Phase 6T-C (2026-05-27): institutional-lifecycle extension point.

Provides the generic :class:`InstitutionalLifecycleHandler` ABC plus
the supporting type aliases that multi-agent runners use to dispatch
year-boundary / per-decision / year-end lifecycle logic per
``agent_type``. Closes engineering-audit findings R5 (no per-
agent_type lifecycle extension point) and R6 (bespoke flood
``MultiAgentHooks`` class bloats with every new institutional type).

Design rationale
================
Pre-6T-C the only multi-agent lifecycle implementation lived in
``examples/multi_agent/flood/orchestration/lifecycle_hooks.py`` as a
single 1237-LOC :class:`MultiAgentHooks` class with ``agent_type ==
"government"`` / ``"insurance"`` branches inside ``post_step``,
``pre_year``, and ``post_year``. Adding a new institutional
agent_type (Phase 6T-F's planned ``social_media_influencer``) would
either bloat this class further or require yet another bespoke
branch in already-entangled code.

Phase 6T-C opens the extension point WITHOUT extracting existing
code:

- :class:`InstitutionalLifecycleHandler` — abstract base class with
  three no-op lifecycle hooks (``pre_year``, ``post_decision``,
  ``post_year``). New agent_types implement a subclass.
- :meth:`SetupPack.institutional_lifecycle_handlers` — DomainPack
  hook returning ``Dict[str, InstitutionalLifecycleHandler]`` keyed
  by ``agent_type``. The multi-agent runner dispatches via this map.
- :meth:`SetupPack.multi_agent_env_keys` — DomainPack hook codifying
  the env-dict-whitelist convention previously implemented as an
  emergent pattern in each multi-agent lifecycle file.

The existing flood ``MultiAgentHooks`` is **not** refactored this
sub-phase. The gov/insurance branches share ``self.env`` /
``self.memory_engine`` state with the household branch + with
``pre_year`` metric aggregation; clean extraction is HIGH
byte-identity risk for paper-3 (400 agents × 13 years production
runs). The plan defers actual code-movement to Phase 6T-F when the
``social_media_influencer`` agent_type becomes the second consumer
of this extension point — at that point the abstraction has TWO
concrete uses and the extraction can be validated against both.

For now, the value-add is the contract: a future
``social_media_influencer`` lifecycle handler implements this ABC
and registers via ``FloodSetupMixin.institutional_lifecycle_handlers``,
rather than landing as yet another ``elif agent.agent_type ==
"social_media_influencer":`` branch in the 1237-LOC bespoke file.

Genericity invariant
====================
This module lives in ``broker/components/orchestration/`` so it MUST
contain no domain tokens (water / flood / household / etc.). The
ABC's method signatures and the supporting types are domain-
agnostic. Verified by
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
