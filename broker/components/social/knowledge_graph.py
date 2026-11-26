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
    ) -> None:
        if half_life_periods <= 0:
            raise ValueError(
                f"AsyncKnowledgeGraph.half_life_periods must be > 0; "
                f"got {half_life_periods!r}."
            )
        self.social_graph = social_graph
        self.follower_network = follower_network
        self.half_life_periods = float(half_life_periods)
        self.strict_no_governance_trace = bool(strict_no_governance_trace)

        self._triples: List[KnowledgeTriple] = []
        self._seq: int = 0
        self._delivered_by_observer: Dict[str, Set[str]] = {}
        self._delivery_cursor_period: Dict[str, int] = {}

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

    def _get_followed_ids(self, observer_id: str) -> Set[str]:
        if self.follower_network is None:
            return set()
        return set(self.follower_network.get_followed(observer_id))

    def _is_visible_to(
        self,
        triple: KnowledgeTriple,
        observer_id: str,
        current_period: int,
        *,
        include_self: bool,
        neighbor_ids: Optional[Set[str]],
        followed_ids: Optional[Set[str]],
    ) -> bool:
        if triple.available_period > current_period:
            return False
        if (
            triple.ttl_periods is not None
            and current_period >= triple.available_period + triple.ttl_periods
        ):
            return False

        source_id = triple.author_id or triple.subject
        is_self = source_id == observer_id
        if is_self and not include_self:
            return False

        vis = triple.visibility
        if vis == "global":
            return True
        if vis == "direct":
            return observer_id in triple.target_ids or (include_self and is_self)
        if vis == "neighbors":
            if include_self and is_self:
                return True
            return neighbor_ids is not None and source_id in neighbor_ids
        if vis == "followers":
            if include_self and is_self:
                return True
            return followed_ids is not None and source_id in followed_ids
        return False

    def _score_triple(self, triple: KnowledgeTriple, current_period: int) -> float:
        decay = age_weight(
            triple.available_period,
            current_period,
            self.half_life_periods,
        )
        return triple.confidence * decay

    def query_visible(
        self,
        observer_id: str,
        current_period: int,
        *,
        predicates: Optional[Union[str, Iterable[str]]] = None,
        subjects: Optional[Union[str, Iterable[str]]] = None,
        top_k: int = 10,
        include_self: bool = False,
    ) -> List[KnowledgeTriple]:
        """Query triples visible to ``observer_id`` at ``current_period``."""
        if top_k <= 0 or not self._triples:
            return []

        predicate_set = _normalize_filter_set(predicates)
        subject_set = _normalize_filter_set(subjects)

        neighbor_ids = self._get_neighbor_ids(observer_id) if self.social_graph is not None else None
        followed_ids = self._get_followed_ids(observer_id) if self.follower_network is not None else None

        scored: List[Tuple[float, int, int, int, str, KnowledgeTriple]] = []
        for idx, triple in enumerate(self._triples):
            if predicate_set is not None and triple.predicate not in predicate_set:
                continue
            if subject_set is not None and triple.subject not in subject_set:
                continue
            if not self._is_visible_to(
                triple,
                observer_id,
                current_period,
                include_self=include_self,
                neighbor_ids=neighbor_ids,
                followed_ids=followed_ids,
            ):
                continue

            score = self._score_triple(triple, current_period)
            scored.append((
                -score,
                -triple.available_period,
                -triple.published_period,
                -idx,
                triple.triple_id,
                triple,
            ))

        scored.sort(key=lambda item: item[:5])
        return [item[5] for item in scored[:top_k]]

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
    ) -> int:
        """Idempotently deliver unseen visible triples into ``memory_engine``."""
        if memory_engine is None or max_items <= 0 or not self._triples:
            return 0

        delivered_ids = self._delivered_by_observer.setdefault(observer_id, set())
        visible = self.query_visible(
            observer_id,
            current_period,
            predicates=predicates,
            subjects=subjects,
            top_k=len(self._triples),
            include_self=include_self,
        )

        unseen = [t for t in visible if t.triple_id not in delivered_ids][:max_items]
        count = 0
        for triple in unseen:
            score = self._score_triple(triple, current_period)
            importance = round(max(0.0, min(1.0, score)), 4)
            metadata: Dict[str, Any] = {
                "origin": "social",
                "period": current_period,
                "importance": importance,
                "emotion": "neutral",
                "source": "social",
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

        self._delivery_cursor_period[observer_id] = current_period
        return count

    def as_context_provider(
        self,
        period_getter: Callable[[], int],
        *,
        memory_engine: Optional[Any] = None,
        top_k: int = 5,
        context_key: str = "social_gossip",
    ) -> "KnowledgeGraphSocialProvider":
        """Build a :class:`KnowledgeGraphSocialProvider` bound to this graph."""
        from broker.components.social.kg_provider import KnowledgeGraphSocialProvider

        return KnowledgeGraphSocialProvider(
            kg=self,
            period_getter=period_getter,
            memory_engine=memory_engine,
            top_k=top_k,
            context_key=context_key,
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
