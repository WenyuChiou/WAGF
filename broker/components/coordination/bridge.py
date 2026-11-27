"""Multi-Actor Lifecycle Bridge — coordinates institutional handlers, messaging, sagas, and social KG.

STATUS: EXPERIMENTAL (Multi-Actor / Coordination Extension — Pre-1.0 API).
Inactive on default single-agent-type ``python -m broker.run`` runs unless
explicitly configured via the ``run.coordinator`` slot or wired via hooks.

Design Principles:
1. Domain-agnostic: zero domain vocabulary; dispatches solely by ``agent_type``
   and configured policies.
2. Invariant 7 compliant: published ``AgentMessage`` notifications and
   ``social_kg.record_executed_action`` calls emit ONLY executed action facts
   (never rejected proposals, rule IDs, or governance messages).
3. Non-invasive: chains cleanly with any case-defined ``pre_year``,
   ``post_step``, and ``post_year`` hooks via :meth:`as_hooks`.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import inspect
import logging
from typing import Any, Dict, Optional, Set, Tuple

from broker.components.coordination.coordinator import GameMaster
from broker.components.coordination.messages import MessagePool
from broker.components.orchestration.institutional_lifecycle import (
    InstitutionalLifecycleHandler,
)
from broker.components.orchestration.sagas import SagaCoordinator
from broker.interfaces.coordination import (
    ActionProposal,
    AgentMessage,
    MessageType,
)
from broker.interfaces.event_generator import EventScope
from broker.interfaces.skill_types import SkillOutcome

logger = logging.getLogger(__name__)


def _extract_executed_action(result: Any) -> Optional[Tuple[str, str, str]]:
    """Return ``(skill_name, number_text, outcome_text)`` when a skill ran.

    Returns ``None`` if execution did not succeed or no skill executed.
    Invariant 7: never surfaces rejected proposals, rule IDs, or
    governance messages.
    """
    if result is None:
        return None
    exec_res = getattr(result, "execution_result", None)
    if exec_res is None or not getattr(exec_res, "success", False):
        return None

    outcome = getattr(result, "outcome", None)
    rejected_row = outcome in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN)
    executed_skill = getattr(result, "executed_skill", None)
    approved_skill = getattr(result, "approved_skill", None)

    if rejected_row:
        if not isinstance(executed_skill, str) or not executed_skill:
            return None
        skill_name = executed_skill
    else:
        skill_name = (
            executed_skill
            if isinstance(executed_skill, str) and executed_skill
            else getattr(approved_skill, "skill_name", None)
        )
    if not isinstance(skill_name, str) or not skill_name:
        return None

    was_fallback = bool(getattr(result, "executed_via_fallback", False))
    params = (
        {}
        if (was_fallback or approved_skill is None)
        else (getattr(approved_skill, "parameters", None) or {})
    )
    number_val = params.get("magnitude_pct")
    if isinstance(number_val, bool) or not isinstance(number_val, (int, float)):
        number_text = ""
    else:
        number_text = f"{float(number_val):g}"

    action_ctx = getattr(exec_res, "action_context", None) or {}
    raw_outcome = action_ctx.get("outcome_text", "") if isinstance(action_ctx, Mapping) else ""
    outcome_text = raw_outcome if isinstance(raw_outcome, str) else ""
    return skill_name, number_text, outcome_text


class MultiActorLifecycleBridge:
    """Bridge multi-actor coordination primitives into ``ExperimentRunner`` hooks.

    Connects:
    - ``handlers``: ``Mapping[agent_type, InstitutionalLifecycleHandler]``
    - ``message_pool``: ``MessagePool`` for step expiry, registration, and
      executed-action notifications
    - ``game_master``: ``GameMaster`` for phase reset, proposal tracking, and
      end-of-year resolution
    - ``saga_coordinator``: ``SagaCoordinator`` (or duck-typed ``step_sagas`` /
      ``advance_all``) advanced at ``post_year``
    - ``social_kg``: duck-typed knowledge graph exposing
      ``record_executed_action(agent_id, agent_role, action_name, period, ...)``
    """

    def __init__(
        self,
        handlers: Optional[Mapping[str, InstitutionalLifecycleHandler]] = None,
        *,
        message_pool: Optional[MessagePool] = None,
        game_master: Optional[GameMaster] = None,
        saga_coordinator: Optional[SagaCoordinator] = None,
        social_kg: Optional[Any] = None,
        env_ref: Optional[Dict[str, Any]] = None,
        role_message_policy: Optional[Mapping[str, Mapping[str, Any]]] = None,
        institutional_roles: Optional[Sequence[str]] = None,
        default_ttl: int = 1,
        default_delivery_delay: int = 1,
    ):
        self.handlers: Dict[str, InstitutionalLifecycleHandler] = dict(handlers or {})
        self.message_pool = message_pool
        self.game_master = game_master
        self.saga_coordinator = saga_coordinator
        self.social_kg = social_kg
        self._env_ref: Dict[str, Any] = env_ref if env_ref is not None else {}
        self.role_message_policy: Dict[str, Dict[str, Any]] = {
            str(role): dict(policy)
            for role, policy in (role_message_policy or {}).items()
        }
        self.institutional_roles: Set[str] = set(institutional_roles or ())
        self.default_ttl = default_ttl
        self.default_delivery_delay = default_delivery_delay

        self._current_year: int = 0
        self._current_env: Dict[str, Any] = self._env_ref
        self._registered_agent_ids: Set[str] = set()
        self._agents_by_id: Dict[str, Any] = {}

    def _ensure_registered(self, agents: Mapping[str, Any]) -> None:
        self._agents_by_id.update(agents)
        if self.message_pool is None:
            return
        unregistered = {
            aid: ag for aid, ag in agents.items()
            if aid not in self._registered_agent_ids
        }
        if unregistered:
            self.message_pool.register_agents(unregistered)
            self._registered_agent_ids.update(unregistered.keys())

    def _is_institutional(self, agent_type: str) -> bool:
        return agent_type in self.handlers or agent_type in self.institutional_roles

    def _publish_executed_action(
        self,
        agent: Any,
        agent_id: str,
        agent_type: str,
        skill_name: str,
        number_text: str,
        outcome_text: str,
        year: int,
    ) -> None:
        if self.message_pool is None:
            return
        if agent_id not in self._registered_agent_ids:
            self._ensure_registered({agent_id: agent})

        policy = self.role_message_policy.get(agent_type, {})
        institutional = self._is_institutional(agent_type)
        raw_scope = policy.get("scope")
        recipient_types = list(policy.get("recipient_types") or ())
        explicit_recipients = list(policy.get("recipients") or ())

        pool_locations = getattr(self.message_pool, "_agent_locations", {}) or {}

        def _agent_location(aid: str, ag: Any) -> Optional[str]:
            return (
                pool_locations.get(aid)
                or getattr(ag, "region_id", None)
                or getattr(ag, "tract_id", None)
            )

        location = policy.get("location") or _agent_location(agent_id, agent)

        def _spatial_recipients() -> Optional[list[str]]:
            if not location:
                return None
            matches = [
                aid for aid, ag in self._agents_by_id.items()
                if aid != agent_id
                and _agent_location(aid, ag) == location
                and (not recipient_types or getattr(ag, "agent_type", None) in recipient_types)
            ]
            return matches or None

        if explicit_recipients:
            recipients = explicit_recipients
            event_scope = EventScope.AGENT
        elif isinstance(raw_scope, EventScope):
            event_scope = raw_scope
            if raw_scope in (EventScope.REGIONAL, EventScope.LOCAL):
                resolved = _spatial_recipients()
                if not resolved:
                    return
                recipients = resolved
                event_scope = EventScope.AGENT
            elif recipient_types and raw_scope == EventScope.GLOBAL:
                recipients = [
                    aid for aid, ag in self._agents_by_id.items()
                    if aid != agent_id and getattr(ag, "agent_type", None) in recipient_types
                ]
                if not recipients:
                    return
                event_scope = EventScope.AGENT
            elif raw_scope == EventScope.AGENT:
                return
            else:
                recipients = []
        else:
            if raw_scope is None:
                pool_graph = getattr(self.message_pool, "_graph", None)
                scope_mode = "global" if institutional else (
                    "neighbors" if pool_graph is not None else "global"
                )
            else:
                scope_mode = str(raw_scope).strip().lower()

            if scope_mode == "neighbors":
                pool_graph = getattr(self.message_pool, "_graph", None)
                neighbors = list(pool_graph.get_neighbors(agent_id)) if pool_graph is not None else []
                if recipient_types:
                    neighbors = [
                        nid for nid in neighbors
                        if getattr(self._agents_by_id.get(nid), "agent_type", None) in recipient_types
                    ]
                recipients = neighbors
                event_scope = EventScope.AGENT
                if not recipients:
                    return
            elif scope_mode in ("direct", "agent"):
                return
            elif scope_mode in ("regional", "local"):
                resolved = _spatial_recipients()
                if not resolved:
                    return
                recipients = resolved
                event_scope = EventScope.AGENT
            elif recipient_types:
                recipients = [
                    aid for aid, ag in self._agents_by_id.items()
                    if aid != agent_id and getattr(ag, "agent_type", None) in recipient_types
                ]
                if not recipients:
                    return
                event_scope = EventScope.AGENT
            else:
                recipients = []
                event_scope = EventScope.GLOBAL

        default_msg_type = (
            MessageType.POLICY_ANNOUNCEMENT.value
            if institutional
            else MessageType.NEIGHBOR_INFO.value
        )
        message_type = str(policy.get("message_type") or default_msg_type)
        priority = int(policy.get("priority", 5 if institutional else 0))
        ttl = int(policy.get("ttl", self.default_ttl))

        action_label = skill_name.replace("_", " ")
        num_suffix = f" (number {number_text})" if number_text else ""
        content = f"Period {year}: {agent_id} ({agent_type}) executed {action_label}{num_suffix}."

        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "executed_skill": skill_name,
            "period": year,
        }
        if number_text:
            payload["number_text"] = f"number {number_text}"
        if outcome_text:
            payload["outcome_text"] = outcome_text

        msg = AgentMessage(
            sender_id=agent_id,
            sender_type=agent_type,
            message_type=message_type,
            content=content,
            data=payload,
            recipients=recipients,
            recipient_types=recipient_types,
            scope=event_scope,
            location=location,
            timestamp=year,
            priority=priority,
            ttl=ttl,
        )
        self.message_pool.publish(msg)

    def _record_social_kg(
        self,
        agent_id: str,
        agent_type: str,
        skill_name: str,
        year: int,
        number_text: str,
        outcome_text: str,
    ) -> None:
        if self.social_kg is None:
            return
        record_fn = getattr(self.social_kg, "record_executed_action", None)
        if not callable(record_fn):
            return
        policy = self.role_message_policy.get(agent_type, {})
        institutional = self._is_institutional(agent_type)
        visibility = policy.get("visibility") or ("global" if institutional else "neighbors")
        delivery_delay = int(policy.get("delivery_delay", self.default_delivery_delay))

        raw_targets = policy.get("target_ids") or policy.get("recipients")
        if raw_targets:
            target_ids = tuple(str(t) for t in raw_targets)
        elif policy.get("recipient_types"):
            target_types = set(policy["recipient_types"])
            target_ids = tuple(
                aid for aid, ag in self._agents_by_id.items()
                if aid != agent_id and getattr(ag, "agent_type", None) in target_types
            )
        else:
            target_ids = ()

        if visibility == "direct" and not target_ids:
            return

        kwargs: Dict[str, Any] = {
            "number_text": number_text,
            "delivery_delay": delivery_delay,
            "visibility": visibility,
            "outcome_text": outcome_text,
        }
        if target_ids:
            try:
                sig = inspect.signature(record_fn)
                accepts_targets = "target_ids" in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                )
            except (TypeError, ValueError):
                accepts_targets = visibility == "direct"
            if accepts_targets or visibility == "direct":
                kwargs["target_ids"] = target_ids

        record_fn(
            agent_id,
            agent_type,
            skill_name,
            year,
            **kwargs,
        )

    def pre_year(self, year: int, env: Dict[str, Any], agents: Dict[str, Any]) -> None:
        """Advance pool/GM step state and dispatch per-agent-type ``pre_year``."""
        self._current_year = year
        self._current_env = env if env is not None else self._env_ref
        self._ensure_registered(agents)

        if self.message_pool is not None:
            self.message_pool.advance_step(year)

        if self.game_master is not None and hasattr(self.game_master, "reset_phase"):
            self.game_master.reset_phase()

        for agent in agents.values():
            if not getattr(agent, "is_active", True):
                continue
            agent_type = getattr(agent, "agent_type", "default")
            handler = self.handlers.get(agent_type)
            if handler is not None:
                handler.pre_year(agent, year, self._current_env)

    def post_step(self, agent: Any, result: Any) -> None:
        """Dispatch ``post_decision`` and emit executed-action facts."""
        extracted = _extract_executed_action(result)
        if extracted is None:
            return

        skill_name, number_text, outcome_text = extracted
        agent_id = getattr(agent, "id", None) or getattr(agent, "name", "")
        agent_type = getattr(agent, "agent_type", "default")
        last_ctx = getattr(agent, "_last_action_context", None)
        year = (
            last_ctx.get("year", self._current_year)
            if isinstance(last_ctx, Mapping)
            else self._current_year
        )
        env = self._current_env if self._current_env is not None else self._env_ref

        handler = self.handlers.get(agent_type)
        if handler is not None:
            handler.post_decision(agent, skill_name, year, env)

        if self.game_master is not None and hasattr(self.game_master, "submit_proposal"):
            self.game_master.submit_proposal(
                ActionProposal(
                    agent_id=str(agent_id),
                    agent_type=agent_type,
                    skill_name=skill_name,
                    metadata={"period": year},
                )
            )

        self._publish_executed_action(
            agent, str(agent_id), agent_type, skill_name, number_text, outcome_text, year
        )
        self._record_social_kg(
            str(agent_id), agent_type, skill_name, year, number_text, outcome_text
        )

    def post_year(self, year: int, agents: Dict[str, Any]) -> None:
        """Resolve GM phase, dispatch ``post_year`` handlers, and step sagas."""
        self._current_year = year
        env = self._current_env if self._current_env is not None else self._env_ref

        if self.game_master is not None and hasattr(self.game_master, "resolve_phase"):
            self.game_master.resolve_phase(shared_state=env)

        for agent in agents.values():
            if not getattr(agent, "is_active", True):
                continue
            agent_type = getattr(agent, "agent_type", "default")
            handler = self.handlers.get(agent_type)
            if handler is not None:
                handler.post_year(agent, year, env)

        if self.saga_coordinator is not None:
            step_fn = getattr(self.saga_coordinator, "step_sagas", None)
            if callable(step_fn):
                step_fn(year)
            else:
                advance_fn = getattr(self.saga_coordinator, "advance_all", None)
                if callable(advance_fn):
                    advance_fn(current_step=year)

    def as_hooks(
        self,
        inner_hooks: Optional[Mapping[str, Callable]] = None,
    ) -> Dict[str, Callable]:
        """Return ``ExperimentRunner`` lifecycle hooks chained with ``inner_hooks``."""
        hooks: Dict[str, Callable] = dict(inner_hooks or {})
        inner_pre_year = hooks.get("pre_year")
        inner_post_step = hooks.get("post_step")
        inner_post_year = hooks.get("post_year")

        def pre_year(year: int, env: Dict[str, Any], agents: Dict[str, Any]) -> None:
            self.pre_year(year, env, agents)
            if inner_pre_year is not None:
                inner_pre_year(year, env, agents)

        def post_step(agent: Any, result: Any) -> None:
            self.post_step(agent, result)
            if inner_post_step is not None:
                inner_post_step(agent, result)

        def post_year(year: int, agents: Dict[str, Any]) -> None:
            self.post_year(year, agents)
            if inner_post_year is not None:
                inner_post_year(year, agents)

        hooks["pre_year"] = pre_year
        hooks["post_step"] = post_step
        hooks["post_year"] = post_year
        return hooks


__all__ = ["MultiActorLifecycleBridge"]
