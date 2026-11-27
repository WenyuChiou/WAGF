"""Domain-generic asynchronous knowledge-graph social engine.

STATUS: EXPERIMENTAL (Multi-Actor / Social Extension — Pre-1.0 API).

Provides :class:`KnowledgeTriple` and :class:`AsyncKnowledgeGraph`, a lightweight,
in-memory, domain-agnostic social fact store supporting:

- Asynchronous propagation via ``published_period + delivery_delay``
  (``available_period``) and optional ``ttl_periods`` expiration.
- Topology-aware visibility scopes: ``"global"``, ``"neighbors"`` (backed by
  :class:`~broker.components.social.graph.SocialGraph`), ``"followers"``
  (backed by :class:`~broker.components.social.follower_network.FollowerNetwork`),
  and ``"direct"`` (explicit ``target_ids``).
- Deterministic age-decayed confidence ranking using
  :func:`~broker.components.social.post.age_weight`.
- Idempotent per-observer memory synchronization via :meth:`sync_to_memory`
  with ``origin="social"`` metadata compatible with
  :class:`~broker.components.memory.origin_gate.OriginGate`.
- Invariant 7 enforcement (``broker/INVARIANTS.md``): refuses governance-trace
  wording (``GOVERNANCE_PHRASES``) when ``strict_no_governance_trace=True``.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

from broker.components.social.post import age_weight

if TYPE_CHECKING:
    from broker.components.social.kg_provider import KnowledgeGraphSocialProvider


VALID_VISIBILITIES: Tuple[str, ...] = ("global", "neighbors", "followers", "direct")
_VALID_VISIBILITY_SET = frozenset(VALID_VISIBILITIES)


def _iter_nested_strings(value: Any) -> Iterable[str]:
    """Yield all string values contained in a nested structure."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            if isinstance(k, str):
                yield k
            yield from _iter_nested_strings(v)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _iter_nested_strings(item)


def _get_governance_phrases() -> Tuple[str, ...]:
    """Lazily read GOVERNANCE_PHRASES to avoid top-level broker.core cycles."""
    from broker.core.run_integrity import GOVERNANCE_PHRASES

    return GOVERNANCE_PHRASES


def _find_governance_phrase(text: str) -> Optional[str]:
    """Return the first matching governance phrase (case-insensitive), or None."""
    if not text:
        return None
    lowered = text.lower()
    for phrase in _get_governance_phrases():
        if phrase in lowered:
            return phrase
    return None


def _normalize_filter_set(values: Optional[Union[str, Iterable[str]]]) -> Optional[Set[str]]:
    """Normalize an optional string or iterable of strings into a set."""
    if values is None:
        return None
    if isinstance(values, str):
        return {values}
    return {str(v) for v in values}


@dataclass
class KnowledgeTriple:
    """Domain-generic knowledge-graph fact with delayed delivery and scoping."""

    triple_id: str
    subject: str
    predicate: str
    obj: str
    value: Optional[float] = None
    text: str = ""
    author_id: str = ""
    author_role: str = ""
    published_period: int = 0
    delivery_delay: int = 0
    ttl_periods: Optional[int] = None
    visibility: str = "neighbors"
    target_ids: Tuple[str, ...] = ()
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.visibility not in _VALID_VISIBILITY_SET:
            raise ValueError(
                f"KnowledgeTriple.visibility must be one of {VALID_VISIBILITIES}; "
                f"got {self.visibility!r}."
            )
        if self.published_period < 0:
            raise ValueError(
                f"KnowledgeTriple.published_period must be >= 0; "
                f"got {self.published_period!r}."
            )
        if self.delivery_delay < 0:
            raise ValueError(
                f"KnowledgeTriple.delivery_delay must be >= 0; "
                f"got {self.delivery_delay!r}."
            )
        if self.ttl_periods is not None and self.ttl_periods < 0:
            raise ValueError(
                f"KnowledgeTriple.ttl_periods must be >= 0 or None; "
                f"got {self.ttl_periods!r}."
            )
        conf = float(self.confidence)
        if not (0.0 <= conf <= 1.0):
            raise ValueError(
                f"KnowledgeTriple.confidence must be in [0.0, 1.0]; "
                f"got {self.confidence!r}."
            )
        self.confidence = conf
        if not isinstance(self.target_ids, tuple):
            self.target_ids = tuple(str(t) for t in self.target_ids)
        if self.metadata is None:
            self.metadata = {}

    @property
    def available_period(self) -> int:
        """Earliest period at which this fact becomes visible to observers."""
        return self.published_period + self.delivery_delay


class AsyncKnowledgeGraph:
    """Asynchronous, topology-scoped social knowledge graph for multi-actor runs."""

    def __init__(
        self,
        social_graph: Optional[Any] = None,
        follower_network: Optional[Any] = None,
        half_life_periods: float = 2.0,
        strict_no_governance_trace: bool = True,
        neighbor_hops: int = 1,
    ) -> None:
        if half_life_periods <= 0:
            raise ValueError(
                f"AsyncKnowledgeGraph.half_life_periods must be > 0; "
                f"got {half_life_periods!r}."
            )
        if int(neighbor_hops) < 1:
            raise ValueError(
                f"AsyncKnowledgeGraph.neighbor_hops must be >= 1; got {neighbor_hops!r}."
            )
        self.social_graph = social_graph
        self.follower_network = follower_network
        self.half_life_periods = float(half_life_periods)
        self.strict_no_governance_trace = bool(strict_no_governance_trace)
        self.neighbor_hops = int(neighbor_hops)

        self._triples: List[KnowledgeTriple] = []
        self._seq: int = 0
        self._delivered_by_observer: Dict[str, Set[str]] = {}
        self._delivery_cursor_period: Dict[str, int] = {}
        self._channel_cursor_period: Dict[Tuple[Any, ...], int] = {}
        self._inactive_agents: Set[str] = set()
        self._observed_inactive_agents: Set[str] = set()

    def set_agent_active(self, agent_id: str, active: bool = True) -> None:
        """Mark whether ``agent_id`` can observe or relay social KG triples."""
        aid = str(agent_id)
        if active:
            self._inactive_agents.discard(aid)
        else:
            self._inactive_agents.add(aid)

    def sync_active_agents(self, agents: Mapping[str, Any]) -> None:
        """Refresh the observed set of deactivated agents from live agent objects."""
        self._observed_inactive_agents = {
            str(aid)
            for aid, ag in agents.items()
            if getattr(ag, "is_active", True) is False
        }

    def _is_active_node(self, agent_id: str) -> bool:
        if agent_id in self._inactive_agents or agent_id in self._observed_inactive_agents:
            return False
        graph_inactive = getattr(self.social_graph, "inactive_agents", ())
        return agent_id not in graph_inactive

    def _validate_no_governance_trace(self, triple: KnowledgeTriple) -> None:
        """Enforce Invariant 7: refuse governance phrases in social KG triples."""
        if not self.strict_no_governance_trace:
            return
        fields_to_check = (
            ("subject", triple.subject),
            ("predicate", triple.predicate),
            ("obj", triple.obj),
            ("text", triple.text),
        )
        for field_name, val in fields_to_check:
            hit = _find_governance_phrase(str(val))
            if hit is not None:
                raise ValueError(
                    f"Invariant 7 violation: social knowledge triple {field_name} "
                    f"contains governance phrase {hit!r}. Social KG facts may "
                    f"carry only executed actions and world outcomes."
                )
        for meta_str in _iter_nested_strings(triple.metadata):
            hit = _find_governance_phrase(meta_str)
            if hit is not None:
                raise ValueError(
                    f"Invariant 7 violation: social knowledge triple metadata "
                    f"contains governance phrase {hit!r}. Social KG facts may "
                    f"carry only executed actions and world outcomes."
                )

    @staticmethod
    def format_triple(triple: KnowledgeTriple) -> str:
        """Render a triple to a concise human-readable line."""
        if triple.text:
            return triple.text
        base = f"{triple.subject} {triple.predicate} {triple.obj}".strip()
        if triple.value is not None:
            return f"{base} ({triple.value})"
        return base

    def assert_fact(
        self,
        subject_or_triple: Optional[Union[str, KnowledgeTriple]] = None,
        predicate: str = "",
        obj: str = "",
        *,
        subject: Optional[str] = None,
        value: Optional[float] = None,
        text: str = "",
        author_id: str = "",
        author_role: str = "",
        published_period: int = 0,
        delivery_delay: int = 0,
        ttl_periods: Optional[int] = None,
        visibility: str = "neighbors",
        target_ids: Iterable[str] = (),
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        triple_id: Optional[str] = None,
    ) -> KnowledgeTriple:
        """Assert a new fact into the social knowledge graph."""
        self._seq += 1
        if isinstance(subject_or_triple, KnowledgeTriple):
            triple = subject_or_triple
        else:
            resolved_subject = subject if subject is not None else subject_or_triple
            if resolved_subject is None:
                raise TypeError("assert_fact() requires a KnowledgeTriple or subject")
            assigned_id = triple_id or f"kg-{self._seq}"
            triple = KnowledgeTriple(
                triple_id=assigned_id,
                subject=str(resolved_subject),
                predicate=str(predicate),
                obj=str(obj),
                value=value,
                text=text,
                author_id=author_id,
                author_role=author_role,
                published_period=published_period,
                delivery_delay=delivery_delay,
                ttl_periods=ttl_periods,
                visibility=visibility,
                target_ids=tuple(str(t) for t in target_ids),
                confidence=confidence,
                metadata=dict(metadata) if metadata is not None else {},
            )

        self._validate_no_governance_trace(triple)
        self._triples.append(triple)
        return triple

    def record_executed_action(
        self,
        agent_id: str,
        agent_role: str,
        action_name: str,
        period: int,
        *,
        number_text: str = "",
        delivery_delay: int = 1,
        visibility: str = "neighbors",
        outcome_text: str = "",
        target_ids: Tuple[str, ...] = (),
        confidence: float = 1.0,
        ttl_periods: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeTriple:
        """Record an executed agent action (Invariant 7 compliant)."""
        parsed_value: Optional[float] = None
        if number_text:
            try:
                parsed_value = float(str(number_text).strip())
            except ValueError:
                parsed_value = None

        actor_label = f"{agent_id} ({agent_role})" if agent_role else str(agent_id)
        summary = f"{actor_label} executed {action_name}"
        if number_text:
            summary = f"{summary} ({number_text})"
        if outcome_text:
            summary = f"{summary}: {outcome_text}"

        merged_meta = dict(metadata) if metadata is not None else {}
        if number_text:
            merged_meta.setdefault("number_text", str(number_text))
        if outcome_text:
            merged_meta.setdefault("outcome_text", str(outcome_text))

        return self.assert_fact(
            subject=agent_id,
            predicate="executed_action",
            obj=action_name,
            value=parsed_value,
            text=summary,
            author_id=agent_id,
            author_role=agent_role,
            published_period=period,
            delivery_delay=delivery_delay,
            ttl_periods=ttl_periods,
            visibility=visibility,
            target_ids=target_ids,
            confidence=confidence,
            metadata=merged_meta,
        )

    def _get_neighbor_ids(self, observer_id: str) -> Set[str]:
        if self.social_graph is None:
            return set()
        return set(self.social_graph.get_neighbors(observer_id))

    def _get_neighbor_hop_map(
        self,
        observer_id: str,
        max_hops: int,
        published_period: int,
    ) -> Dict[str, int]:
        """BFS shortest hop distances on ``social_graph`` up to ``max_hops``.

        An edge ``(u, v)`` is traversable for a triple published at
        ``published_period`` only if the edge's start period is ``<= published_period``,
        preventing newly connected agents from retroactively reading pre-link facts.
        """
        if self.social_graph is None or max_hops < 1 or not self._is_active_node(observer_id):
            return {}
        get_edge_start = getattr(self.social_graph, "get_edge_start_period", None)
        hops: Dict[str, int] = {}
        visited: Set[str] = {observer_id}
        queue: deque[Tuple[str, int]] = deque([(observer_id, 0)])
        while queue:
            cur, dist = queue.popleft()
            if dist >= max_hops:
                continue
            for nxt in self.social_graph.get_neighbors(cur):
                if nxt in visited or not self._is_active_node(nxt):
                    continue
                if callable(get_edge_start):
                    edge_start = get_edge_start(cur, nxt)
                    if edge_start is not None and edge_start > published_period:
                        continue
                visited.add(nxt)
                hops[nxt] = dist + 1
                queue.append((nxt, dist + 1))
        return hops

    @staticmethod
    def _effective_available_period(triple: KnowledgeTriple, hop: int) -> int:
        if hop <= 1:
            return triple.available_period
        hop_delay = max(1, int(triple.delivery_delay))
        return triple.available_period + (hop - 1) * hop_delay

    def _get_followed_ids(self, observer_id: str) -> Set[str]:
        if self.follower_network is None:
            return set()
        return set(self.follower_network.get_followed(observer_id))

    def _resolve_triple_availability(
        self,
        triple: KnowledgeTriple,
        observer_id: str,
        current_period: int,
        *,
        include_self: bool,
        followed_ids: Optional[Set[str]],
        effective_hops: int,
        hop_cache: Dict[int, Dict[str, int]],
    ) -> Optional[int]:
        source_id = triple.author_id or triple.subject
        is_self = source_id == observer_id
        if is_self and not include_self:
            return None

        vis = triple.visibility
        effective_avail = triple.available_period
        if vis == "global":
            pass
        elif vis == "direct":
            if not (observer_id in triple.target_ids or (include_self and is_self)):
                return None
        elif vis == "neighbors":
            if include_self and is_self:
                pass
            else:
                if self.social_graph is None:
                    return None
                hop_map = hop_cache.get(triple.published_period)
                if hop_map is None:
                    hop_map = self._get_neighbor_hop_map(
                        observer_id, effective_hops, triple.published_period,
                    )
                    hop_cache[triple.published_period] = hop_map
                hop = hop_map.get(source_id)
                if hop is None:
                    return None
                effective_avail = self._effective_available_period(triple, hop)
        elif vis == "followers":
            if include_self and is_self:
                pass
            elif followed_ids is None or source_id not in followed_ids:
                return None
        else:
            return None

        if effective_avail > current_period:
            return None
        if (
            triple.ttl_periods is not None
            and current_period >= effective_avail + triple.ttl_periods
        ):
            return None
        return effective_avail

    def _score_triple(
        self,
        triple: KnowledgeTriple,
        current_period: int,
        *,
        available_period: Optional[int] = None,
    ) -> float:
        avail = triple.available_period if available_period is None else available_period
        decay = age_weight(
            avail,
            current_period,
            self.half_life_periods,
        )
        return triple.confidence * decay

    def _query_visible_with_availability(
        self,
        observer_id: str,
        current_period: int,
        *,
        predicates: Optional[Union[str, Iterable[str]]] = None,
        subjects: Optional[Union[str, Iterable[str]]] = None,
        top_k: int = 10,
        include_self: bool = False,
        hops: Optional[int] = None,
    ) -> List[Tuple[KnowledgeTriple, int]]:
        """Query visible ``(triple, effective_available_period)`` pairs ranked for ``observer_id``."""
        if top_k <= 0 or not self._triples:
            return []

        effective_hops = self.neighbor_hops if hops is None else int(hops)
        if effective_hops < 1:
            raise ValueError(f"hops must be >= 1; got {effective_hops!r}.")

        predicate_set = _normalize_filter_set(predicates)
        subject_set = _normalize_filter_set(subjects)

        followed_ids = self._get_followed_ids(observer_id) if self.follower_network is not None else None
        hop_cache: Dict[int, Dict[str, int]] = {}

        scored: List[Tuple[float, int, int, int, str, KnowledgeTriple]] = []
        for idx, triple in enumerate(self._triples):
            if predicate_set is not None and triple.predicate not in predicate_set:
                continue
            if subject_set is not None and triple.subject not in subject_set:
                continue
            effective_avail = self._resolve_triple_availability(
                triple,
                observer_id,
                current_period,
                include_self=include_self,
                followed_ids=followed_ids,
                effective_hops=effective_hops,
                hop_cache=hop_cache,
            )
            if effective_avail is None:
                continue

            score = self._score_triple(triple, current_period, available_period=effective_avail)
            scored.append((
                -score,
                -effective_avail,
                -triple.published_period,
                -idx,
                triple.triple_id,
                triple,
            ))

        scored.sort(key=lambda item: item[:5])
        return [(item[5], -item[1]) for item in scored[:top_k]]

    def query_visible(
        self,
        observer_id: str,
        current_period: int,
        *,
        predicates: Optional[Union[str, Iterable[str]]] = None,
        subjects: Optional[Union[str, Iterable[str]]] = None,
        top_k: int = 10,
        include_self: bool = False,
        hops: Optional[int] = None,
    ) -> List[KnowledgeTriple]:
        """Query triples visible to ``observer_id`` at ``current_period``."""
        pairs = self._query_visible_with_availability(
            observer_id,
            current_period,
            predicates=predicates,
            subjects=subjects,
            top_k=top_k,
            include_self=include_self,
            hops=hops,
        )
        return [triple for triple, _ in pairs]

    def sync_to_memory(
        self,
        observer_id: str,
        current_period: int,
        memory_engine: Any,
        *,
        max_items: int = 5,
        predicates: Optional[Union[str, Iterable[str]]] = None,
        subjects: Optional[Union[str, Iterable[str]]] = None,
        include_self: bool = False,
        hops: Optional[int] = None,
    ) -> int:
        """Idempotently deliver unseen visible triples into ``memory_engine``."""
        if memory_engine is None or max_items <= 0 or not self._triples:
            return 0
        effective_hops = self.neighbor_hops if hops is None else int(hops)
        predicate_set = _normalize_filter_set(predicates)
        subject_set = _normalize_filter_set(subjects)
        channel_key = (
            observer_id,
            frozenset(predicate_set) if predicate_set is not None else None,
            frozenset(subject_set) if subject_set is not None else None,
            bool(include_self),
            effective_hops,
        )
        if self._channel_cursor_period.get(channel_key) == current_period:
            return 0

        delivered_ids = self._delivered_by_observer.setdefault(observer_id, set())
        visible_pairs = self._query_visible_with_availability(
            observer_id,
            current_period,
            predicates=predicate_set,
            subjects=subject_set,
            top_k=len(self._triples),
            include_self=include_self,
            hops=effective_hops,
        )

        unseen = [(t, avail) for t, avail in visible_pairs if t.triple_id not in delivered_ids][:max_items]
        count = 0
        for triple, effective_avail in unseen:
            score = self._score_triple(triple, current_period, available_period=effective_avail)
            importance = round(max(0.0, min(1.0, score)), 4)
            source = "neighbor" if triple.visibility == "neighbors" else "community"
            metadata: Dict[str, Any] = {
                "origin": "social",
                "period": current_period,
                "importance": importance,
                "source": source,
                "triple_id": triple.triple_id,
            }
            if triple.author_id:
                metadata["author_id"] = triple.author_id
            memory_engine.add_memory(
                observer_id,
                self.format_triple(triple),
                metadata=metadata,
            )
            delivered_ids.add(triple.triple_id)
            count += 1

        self._channel_cursor_period[channel_key] = current_period
        self._delivery_cursor_period[observer_id] = current_period
        return count

    def as_context_provider(
        self,
        period_getter: Callable[[], int],
        *,
        memory_engine: Optional[Any] = None,
        top_k: int = 5,
        context_key: str = "social_gossip",
        hops: Optional[int] = None,
    ) -> "KnowledgeGraphSocialProvider":
        """Build a :class:`KnowledgeGraphSocialProvider` bound to this graph."""
        from broker.components.social.kg_provider import KnowledgeGraphSocialProvider

        return KnowledgeGraphSocialProvider(
            kg=self,
            period_getter=period_getter,
            memory_engine=memory_engine,
            top_k=top_k,
            context_key=context_key,
            hops=hops,
        )

    def snapshot(self) -> Dict[str, Any]:
        """Return a serializable snapshot of the graph and delivery cursors."""
        triples_out = []
        for triple in self._triples:
            entry = asdict(triple)
            entry["available_period"] = triple.available_period
            triples_out.append(entry)

        return {
            "triple_count": len(self._triples),
            "half_life_periods": self.half_life_periods,
            "strict_no_governance_trace": self.strict_no_governance_trace,
            "triples": triples_out,
            "delivered_by_observer": {
                obs: sorted(ids)
                for obs, ids in sorted(self._delivered_by_observer.items())
            },
            "delivery_cursor_period": dict(sorted(self._delivery_cursor_period.items())),
        }


__all__ = [
    "AsyncKnowledgeGraph",
    "KnowledgeTriple",
    "VALID_VISIBILITIES",
]
