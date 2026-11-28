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
from dataclasses import dataclass
import inspect
import logging
from typing import Any, Dict, Optional, Set, Tuple

from broker.components.coordination.coordinator import GameMaster
from broker.components.coordination.messages import (
    DEFAULT_LOCATION_ATTRS,
    MessagePool,
    coerce_location_value,
    normalize_location_attrs,
    resolve_agent_location,
)
from broker.components.orchestration.institutional_lifecycle import (
    InstitutionalLifecycleHandler,
)
from broker.components.orchestration.sagas import SagaCoordinator
from broker.components.social.knowledge_graph import VALID_VISIBILITIES
from broker.interfaces.coordination import (
    ActionProposal,
    AgentMessage,
    MessageType,
)
from broker.interfaces.event_generator import EventScope
from broker.interfaces.skill_types import SkillOutcome

logger = logging.getLogger(__name__)

_VALID_SCOPES = frozenset({"global", "regional", "local", "neighbors", "direct", "agent"})
_ALLOWED_POLICY_KEYS = frozenset({
    "scope",
    "visibility",
    "message_type",
    "priority",
    "ttl",
    "delivery_delay",
    "recipients",
    "target_ids",
    "recipient_types",
    "location",
})


@dataclass(frozen=True)
class _ResolvedAudience:
    """Single-pass audience resolution shared by MessagePool and SocialKG sinks."""

    mode: str
    event_scope: EventScope
    recipient_ids: Tuple[str, ...]
    recipient_types: Tuple[str, ...]
    location: Optional[str]
    restricted: bool
    kg_default_visibility: str
    explicit_targets: Tuple[str, ...] = ()


def _coerce_int(value: Any, name: str, *, minimum: Optional[int] = None) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer, got bool ({value!r})")
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"{name} must be an integer, got {type(value).__name__}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc
    if isinstance(value, float) and float(parsed) != value:
        raise ValueError(f"{name} must be an integer, got float {value!r}")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {parsed}")
    return parsed


def _normalize_string_sequence(value: Any, field_name: str, role: str) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(
            f"role_message_policy[{role!r}][{field_name!r}] must be a sequence of strings"
        )
    cleaned: list[str] = []
    for item in value:
        if type(item) is not str or not item.strip():
            raise ValueError(
                f"role_message_policy[{role!r}][{field_name!r}] entries must be non-empty strings, got {item!r}"
            )
        cleaned.append(item.strip())
    return tuple(dict.fromkeys(cleaned))


def _normalize_scope(raw_scope: Any, role: str) -> Optional[str]:
    if raw_scope is None:
        return None
    if isinstance(raw_scope, EventScope):
        norm = raw_scope.value
    elif isinstance(raw_scope, str):
        norm = raw_scope.strip().lower()
    else:
        raise ValueError(
            f"role_message_policy[{role!r}]['scope'] must be EventScope or string, got {raw_scope!r}"
        )
    if norm not in _VALID_SCOPES:
        raise ValueError(
            f"role_message_policy[{role!r}]['scope'] has unknown value {raw_scope!r}; "
            f"expected one of {sorted(_VALID_SCOPES)}"
        )
    return "direct" if norm == "agent" else norm


def _validate_role_policy(
    role: str,
    raw_policy: Mapping[str, Any],
    default_ttl: int,
    default_delivery_delay: int,
    institutional: bool,
) -> Dict[str, Any]:
    if not isinstance(raw_policy, Mapping):
        raise ValueError(f"role_message_policy[{role!r}] must be a mapping")
    unknown = sorted(k for k in raw_policy if k not in _ALLOWED_POLICY_KEYS)
    if unknown:
        raise ValueError(
            f"role_message_policy[{role!r}] has unknown key(s) {unknown}; "
            f"allowed: {sorted(_ALLOWED_POLICY_KEYS)}"
        )

    scope_mode = _normalize_scope(raw_policy.get("scope"), role)
    visibility = raw_policy.get("visibility")
    if visibility is not None:
        if not isinstance(visibility, str) or visibility.strip().lower() not in VALID_VISIBILITIES:
            raise ValueError(
                f"role_message_policy[{role!r}]['visibility'] must be one of "
                f"{VALID_VISIBILITIES}, got {visibility!r}"
            )
        visibility = visibility.strip().lower()

    recipients = _normalize_string_sequence(raw_policy.get("recipients"), "recipients", role)
    target_ids = _normalize_string_sequence(raw_policy.get("target_ids"), "target_ids", role)
    recipient_types = _normalize_string_sequence(
        raw_policy.get("recipient_types"), "recipient_types", role
    )

    if scope_mode == "direct" and not (recipients or target_ids):
        raise ValueError(
            f"role_message_policy[{role!r}] with direct/agent scope requires recipients or target_ids"
        )

    location = None
    if raw_policy.get("location") is not None:
        location = coerce_location_value(raw_policy.get("location"))
        if location is None:
            raise ValueError(
                f"role_message_policy[{role!r}]['location'] must be a non-empty scalar string"
            )

    raw_msg_type = raw_policy.get("message_type")
    if raw_msg_type is not None and (not isinstance(raw_msg_type, str) or not raw_msg_type.strip()):
        raise ValueError(
            f"role_message_policy[{role!r}]['message_type'] must be a non-empty string"
        )

    priority = _coerce_int(
        raw_policy.get("priority", 5 if institutional else 0),
        f"role_message_policy[{role!r}]['priority']",
    )
    ttl = _coerce_int(
        raw_policy.get("ttl", default_ttl),
        f"role_message_policy[{role!r}]['ttl']",
        minimum=0,
    )
    delivery_delay = _coerce_int(
        raw_policy.get("delivery_delay", default_delivery_delay),
        f"role_message_policy[{role!r}]['delivery_delay']",
        minimum=0,
    )

    return {
        "scope": scope_mode,
        "visibility": visibility,
        "message_type": raw_msg_type.strip() if isinstance(raw_msg_type, str) else None,
        "priority": priority,
        "ttl": ttl,
        "delivery_delay": delivery_delay,
        "recipients": recipients,
        "target_ids": target_ids,
        "recipient_types": recipient_types,
        "has_explicit_recipients": "recipients" in raw_policy and raw_policy["recipients"] is not None,
        "has_explicit_target_ids": "target_ids" in raw_policy and raw_policy["target_ids"] is not None,
        "has_explicit_recipient_types": (
            "recipient_types" in raw_policy and raw_policy["recipient_types"] is not None
        ),
        "location": location,
    }


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
        default_ttl: int = 2,
        default_delivery_delay: int = 1,
        location_attrs: Optional[Sequence[str]] = None,
    ):
        self.handlers: Dict[str, InstitutionalLifecycleHandler] = dict(handlers or {})
        self.message_pool = message_pool
        self.game_master = game_master
        self.saga_coordinator = saga_coordinator
        self.social_kg = social_kg
        self._env_ref: Dict[str, Any] = env_ref if env_ref is not None else {}
        self.institutional_roles: Set[str] = set(institutional_roles or ())
        self.default_ttl = _coerce_int(default_ttl, "default_ttl", minimum=0)
        self.default_delivery_delay = _coerce_int(
            default_delivery_delay, "default_delivery_delay", minimum=0
        )
        self.location_attrs: Tuple[str, ...] = normalize_location_attrs(location_attrs)

        self.role_message_policy: Dict[str, Dict[str, Any]] = {
            str(role): _validate_role_policy(
                str(role),
                policy,
                self.default_ttl,
                self.default_delivery_delay,
                self._is_institutional(str(role)),
            )
            for role, policy in (role_message_policy or {}).items()
        }

        self._current_year: int = 0
        self._current_env: Dict[str, Any] = self._env_ref
        self._registered_agent_ids: Set[str] = set()
        self._agents_by_id: Dict[str, Any] = {}
        self._warned_events: Set[Tuple[str, ...]] = set()
        self.skipped_audience_counts: Dict[str, int] = {}

    def _warn_once(self, key: Tuple[str, ...], message: str, *args: Any) -> None:
        if key not in self._warned_events:
            self._warned_events.add(key)
            logger.warning(message, *args)

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
        refresh_fn = getattr(self.message_pool, "refresh_agent_locations", None)
        if callable(refresh_fn):
            refresh_fn(agents)

    def _sync_agent_state(self, agent_id: str, agent: Any) -> None:
        if not agent_id:
            return
        self._agents_by_id[agent_id] = agent
        is_active = getattr(agent, "is_active", True) is not False
        if self.message_pool is not None:
            set_active_fn = getattr(self.message_pool, "set_agent_active", None)
            if callable(set_active_fn):
                set_active_fn(agent_id, is_active)
            refresh_fn = getattr(self.message_pool, "refresh_agent_locations", None)
            if callable(refresh_fn):
                refresh_fn({agent_id: agent})
        kg_set_active = getattr(self.social_kg, "set_agent_active", None)
        if callable(kg_set_active):
            kg_set_active(agent_id, is_active)

    def _is_institutional(self, agent_type: str) -> bool:
        return agent_type in self.handlers or agent_type in self.institutional_roles

    def _resolve_graph(self) -> Optional[Any]:
        return (
            getattr(self.message_pool, "_graph", None)
            or getattr(self.social_kg, "social_graph", None)
            or getattr(self.social_kg, "graph", None)
        )

    def _agent_location(self, aid: str, ag: Any) -> Optional[str]:
        live = resolve_agent_location(ag, self.location_attrs)
        if live is not None:
            return live
        pool_locations = getattr(self.message_pool, "_agent_locations", None) or {}
        return coerce_location_value(pool_locations.get(aid))

    def _active_candidate_items(self, sender_id: str) -> list[Tuple[str, Any]]:
        return [
            (aid, ag) for aid, ag in self._agents_by_id.items()
            if aid != sender_id and getattr(ag, "is_active", True)
        ]

    def _filter_active_ids(
        self,
        candidate_ids: Sequence[str],
        sender_id: str,
        recipient_types: Tuple[str, ...],
        *,
        require_known: bool = False,
    ) -> Tuple[str, ...]:
        type_set = set(recipient_types)
        filtered: list[str] = []
        for aid in dict.fromkeys(candidate_ids):
            if aid == sender_id:
                continue
            ag = self._agents_by_id.get(aid)
            if ag is None and require_known:
                continue
            if ag is not None and not getattr(ag, "is_active", True):
                continue
            if type_set and getattr(ag, "agent_type", None) not in type_set:
                continue
            filtered.append(aid)
        return tuple(filtered)

    def _resolve_audience(
        self,
        agent: Any,
        agent_id: str,
        agent_type: str,
    ) -> _ResolvedAudience:
        policy = self.role_message_policy.get(agent_type, {})
        institutional = self._is_institutional(agent_type)
        raw_scope = policy.get("scope")
        recipient_types: Tuple[str, ...] = tuple(policy.get("recipient_types") or ())
        has_types = bool(policy.get("has_explicit_recipient_types")) or bool(recipient_types)
        explicit_recipients: Tuple[str, ...] = tuple(policy.get("recipients") or ())
        explicit_targets: Tuple[str, ...] = tuple(policy.get("target_ids") or ())
        has_explicit_recipients = bool(policy.get("has_explicit_recipients")) or bool(explicit_recipients)

        graph = self._resolve_graph()
        location = policy.get("location") or self._agent_location(agent_id, agent)
        default_kg_vis = "global" if institutional else "neighbors"

        if has_explicit_recipients:
            resolved_ids = self._filter_active_ids(
                explicit_recipients, agent_id, recipient_types, require_known=False
            )
            return _ResolvedAudience(
                mode="direct",
                event_scope=EventScope.AGENT,
                recipient_ids=resolved_ids,
                recipient_types=recipient_types,
                location=location,
                restricted=True,
                kg_default_visibility=default_kg_vis,
                explicit_targets=explicit_targets,
            )

        if raw_scope is None:
            mode = "global" if institutional else ("neighbors" if graph is not None else "global")
        else:
            mode = raw_scope

        if mode == "direct":
            resolved_ids = self._filter_active_ids(
                explicit_targets, agent_id, recipient_types, require_known=False
            )
            return _ResolvedAudience(
                mode="direct",
                event_scope=EventScope.AGENT,
                recipient_ids=resolved_ids,
                recipient_types=recipient_types,
                location=location,
                restricted=True,
                kg_default_visibility=default_kg_vis,
                explicit_targets=resolved_ids,
            )

        if mode in ("regional", "local"):
            if not location:
                resolved_ids: Tuple[str, ...] = ()
            else:
                type_set = set(recipient_types)
                resolved_ids = tuple(
                    aid for aid, ag in self._active_candidate_items(agent_id)
                    if self._agent_location(aid, ag) == location
                    and (not has_types or getattr(ag, "agent_type", None) in type_set)
                )
            return _ResolvedAudience(
                mode=mode,
                event_scope=EventScope.AGENT,
                recipient_ids=resolved_ids,
                recipient_types=recipient_types,
                location=location,
                restricted=True,
                kg_default_visibility=default_kg_vis,
                explicit_targets=explicit_targets,
            )

        if mode == "neighbors":
            neighbors = list(graph.get_neighbors(agent_id)) if graph is not None else []
            resolved_ids = self._filter_active_ids(
                neighbors, agent_id, recipient_types if has_types else (), require_known=False
            )
            if has_types:
                type_set = set(recipient_types)
                resolved_ids = tuple(
                    nid for nid in resolved_ids
                    if getattr(self._agents_by_id.get(nid), "agent_type", None) in type_set
                )
            return _ResolvedAudience(
                mode="neighbors",
                event_scope=EventScope.AGENT,
                recipient_ids=resolved_ids,
                recipient_types=recipient_types,
                location=location,
                restricted=has_types,
                kg_default_visibility="neighbors",
                explicit_targets=explicit_targets,
            )

        # mode == "global"
        if has_types:
            type_set = set(recipient_types)
            resolved_ids = tuple(
                aid for aid, ag in self._active_candidate_items(agent_id)
                if getattr(ag, "agent_type", None) in type_set
            )
            return _ResolvedAudience(
                mode="global",
                event_scope=EventScope.AGENT,
                recipient_ids=resolved_ids,
                recipient_types=recipient_types,
                location=location,
                restricted=True,
                kg_default_visibility=default_kg_vis,
                explicit_targets=explicit_targets,
            )

        return _ResolvedAudience(
            mode="global",
            event_scope=EventScope.GLOBAL,
            recipient_ids=(),
            recipient_types=(),
            location=location,
            restricted=False,
            kg_default_visibility="global",
            explicit_targets=explicit_targets,
        )

    def _record_skip(self, agent_type: str, channel: str, reason: str) -> None:
        self.skipped_audience_counts[agent_type] = self.skipped_audience_counts.get(agent_type, 0) + 1
        self._warn_once(
            ("skip", agent_type, channel, reason),
            "MultiActorLifecycleBridge: skipping %s delivery for role %r (%s)",
            channel,
            agent_type,
            reason,
        )

    def _publish_executed_action(
        self,
        agent: Any,
        agent_id: str,
        agent_type: str,
        skill_name: str,
        number_text: str,
        outcome_text: str,
        year: int,
        audience: _ResolvedAudience,
        source_step_id: Optional[Any] = None,
    ) -> None:
        if self.message_pool is None:
            return
        if agent_id not in self._registered_agent_ids:
            self._ensure_registered({agent_id: agent})

        if audience.event_scope == EventScope.AGENT and not audience.recipient_ids:
            self._record_skip(agent_type, "message_pool", f"no matching recipients for mode={audience.mode}")
            return

        policy = self.role_message_policy.get(agent_type, {})
        institutional = self._is_institutional(agent_type)
        default_msg_type = (
            MessageType.POLICY_ANNOUNCEMENT.value
            if institutional
            else MessageType.NEIGHBOR_INFO.value
        )
        message_type = policy.get("message_type") or default_msg_type
        priority = policy.get("priority", 5 if institutional else 0)
        ttl = policy.get("ttl", self.default_ttl)

        action_label = skill_name.replace("_", " ")
        num_suffix = f" (number {number_text})" if number_text else ""
        content = f"Period {year}: {agent_id} ({agent_type}) executed {action_label}{num_suffix}."

        payload: Dict[str, Any] = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            "executed_skill": skill_name,
            "period": year,
        }
        if source_step_id is not None:
            payload["source_step_id"] = source_step_id
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
            recipients=list(audience.recipient_ids),
            recipient_types=list(audience.recipient_types),
            scope=audience.event_scope,
            location=audience.location,
            timestamp=year,
            priority=priority,
            ttl=ttl,
        )
        self.message_pool.publish(msg)

    @staticmethod
    def _accepts_kwarg(fn: Callable[..., Any], name: str) -> bool:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return False
        return name in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )

    @staticmethod
    def _accepts_target_ids(record_fn: Callable[..., Any]) -> bool:
        return MultiActorLifecycleBridge._accepts_kwarg(record_fn, "target_ids")

    def _record_social_kg(
        self,
        agent_id: str,
        agent_type: str,
        skill_name: str,
        year: int,
        number_text: str,
        outcome_text: str,
        audience: _ResolvedAudience,
        source_step_id: Optional[Any] = None,
    ) -> None:
        if self.social_kg is None:
            return
        record_fn = getattr(self.social_kg, "record_executed_action", None)
        if not callable(record_fn):
            return

        policy = self.role_message_policy.get(agent_type, {})
        delivery_delay = policy.get("delivery_delay", self.default_delivery_delay)
        explicit_visibility = policy.get("visibility")
        has_explicit_target_ids = bool(policy.get("has_explicit_target_ids"))
        accepts_targets = self._accepts_kwarg(record_fn, "target_ids")

        target_ids: Tuple[str, ...] = ()
        if explicit_visibility is not None:
            visibility = explicit_visibility
            if visibility == "direct":
                if has_explicit_target_ids:
                    target_ids = self._filter_active_ids(
                        audience.explicit_targets, agent_id, (), require_known=False
                    )
                else:
                    target_ids = audience.recipient_ids or self._filter_active_ids(
                        audience.explicit_targets, agent_id, (), require_known=False
                    )
                if not target_ids:
                    self._record_skip(agent_type, "social_kg", "direct visibility with 0 targets")
                    return
        elif has_explicit_target_ids:
            visibility = "direct"
            target_ids = self._filter_active_ids(
                audience.explicit_targets, agent_id, (), require_known=False
            )
            if not target_ids:
                self._record_skip(agent_type, "social_kg", "explicit target_ids resolved to 0 targets")
                return
        elif audience.restricted:
            if not accepts_targets:
                self._warn_once(
                    ("kg_no_targets", agent_type),
                    "MultiActorLifecycleBridge: social_kg for role %r does not accept target_ids; "
                    "falling back to role default visibility %r without direct targeting.",
                    agent_type,
                    audience.kg_default_visibility,
                )
                visibility = audience.kg_default_visibility
            elif not audience.recipient_ids:
                self._record_skip(agent_type, "social_kg", f"empty audience for mode={audience.mode}")
                return
            else:
                visibility = "direct"
                target_ids = audience.recipient_ids
        else:
            visibility = audience.kg_default_visibility

        kwargs: Dict[str, Any] = {
            "number_text": number_text,
            "delivery_delay": delivery_delay,
            "visibility": visibility,
            "outcome_text": outcome_text,
        }
        if target_ids and (accepts_targets or visibility == "direct"):
            kwargs["target_ids"] = target_ids
        if source_step_id is not None and self._accepts_kwarg(record_fn, "metadata"):
            kwargs["metadata"] = {"source_step_id": source_step_id}

        record_fn(
            agent_id,
            agent_type,
            skill_name,
            year,
            **kwargs,
        )

    def pre_year(self, year: int, env: Dict[str, Any], agents: Dict[str, Any]) -> None:
        """Advance pool/GM step state, refresh locations, and dispatch ``pre_year``."""
        self._current_year = year
        self._current_env = env if env is not None else self._env_ref
        self._ensure_registered(agents)

        present_types = {getattr(ag, "agent_type", "default") for ag in agents.values()}
        for configured_role in sorted(set(self.role_message_policy) - present_types):
            self._warn_once(
                ("unused_policy_role", configured_role),
                "MultiActorLifecycleBridge: role_message_policy configures role %r, which matches no registered agent.",
                configured_role,
            )

        if self.message_pool is not None:
            self.message_pool.advance_step(year)

        if self.game_master is not None and hasattr(self.game_master, "reset_phase"):
            self.game_master.reset_phase()

        if self.social_kg is not None:
            sync_kg_fn = getattr(self.social_kg, "sync_active_agents", None)
            if callable(sync_kg_fn):
                sync_kg_fn(agents)

        for aid, agent in agents.items():
            self._sync_agent_state(str(aid), agent)
            if getattr(agent, "is_active", True) is False:
                continue
            agent_type = getattr(agent, "agent_type", "default")
            handler = self.handlers.get(agent_type)
            if handler is not None:
                handler.pre_year(agent, year, self._current_env)
                self._sync_agent_state(str(aid), agent)

    def post_step(self, agent: Any, result: Any) -> None:
        """Dispatch ``post_decision``, sync live state, and emit executed-action facts."""
        agent_id = str(getattr(agent, "id", None) or getattr(agent, "name", ""))
        self._sync_agent_state(agent_id, agent)

        extracted = _extract_executed_action(result)
        if extracted is None:
            return

        skill_name, number_text, outcome_text = extracted
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
        self._sync_agent_state(agent_id, agent)

        if self.game_master is not None and hasattr(self.game_master, "submit_proposal"):
            self.game_master.submit_proposal(
                ActionProposal(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    skill_name=skill_name,
                    metadata={"period": year},
                )
            )

        source_step_id = getattr(result, "_step_id", None)
        if source_step_id is None:
            source_step_id = getattr(agent, "_last_step_id", None)

        audience = self._resolve_audience(agent, agent_id, agent_type)
        self._publish_executed_action(
            agent, agent_id, agent_type, skill_name, number_text, outcome_text, year, audience,
            source_step_id=source_step_id,
        )
        self._record_social_kg(
            agent_id, agent_type, skill_name, year, number_text, outcome_text, audience,
            source_step_id=source_step_id,
        )

    def post_year(self, year: int, agents: Dict[str, Any]) -> None:
        """Resolve GM phase, dispatch ``post_year`` handlers, and step sagas."""
        self._current_year = year
        env = self._current_env if self._current_env is not None else self._env_ref

        if self.game_master is not None and hasattr(self.game_master, "resolve_phase"):
            self.game_master.resolve_phase(shared_state=env)

        for aid, agent in agents.items():
            if getattr(agent, "is_active", True) is False:
                self._sync_agent_state(str(aid), agent)
                continue
            agent_type = getattr(agent, "agent_type", "default")
            handler = self.handlers.get(agent_type)
            if handler is not None:
                handler.post_year(agent, year, env)
            self._sync_agent_state(str(aid), agent)

        if self.social_kg is not None:
            sync_kg_fn = getattr(self.social_kg, "sync_active_agents", None)
            if callable(sync_kg_fn):
                sync_kg_fn(agents)

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

    def snapshot(self) -> Dict[str, Any]:
        """Return a serializable coordination state snapshot for end-of-run audit."""
        policy_out: Dict[str, Any] = {}
        for role, cfg in sorted(self.role_message_policy.items()):
            entry = dict(cfg)
            for seq_key in ("recipients", "target_ids", "recipient_types"):
                if isinstance(entry.get(seq_key), tuple):
                    entry[seq_key] = list(entry[seq_key])
            policy_out[role] = entry

        out: Dict[str, Any] = {
            "last_year": self._current_year,
            "institutional_roles": sorted(self.institutional_roles),
            "handler_roles": sorted(self.handlers.keys()),
            "registered_agent_count": len(self._registered_agent_ids),
            "default_ttl": self.default_ttl,
            "default_delivery_delay": self.default_delivery_delay,
            "role_message_policy": policy_out,
            "skipped_audience_counts": dict(sorted(self.skipped_audience_counts.items())),
        }
        graph = self._resolve_graph()
        if graph is not None and callable(getattr(graph, "summary", None)):
            out["social_graph"] = graph.summary()
        if self.message_pool is not None and callable(getattr(self.message_pool, "summary", None)):
            out["message_pool"] = self.message_pool.summary()
        if self.game_master is not None and callable(getattr(self.game_master, "summary", None)):
            out["game_master"] = self.game_master.summary()
        if self.saga_coordinator is not None:
            saga_snap = getattr(self.saga_coordinator, "snapshot", None) or getattr(
                self.saga_coordinator, "summary", None
            )
            if callable(saga_snap):
                out["saga_coordinator"] = saga_snap()
        if self.social_kg is not None and callable(getattr(self.social_kg, "snapshot", None)):
            out["social_kg"] = self.social_kg.snapshot()
        return out


__all__ = ["MultiActorLifecycleBridge"]
