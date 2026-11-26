"""ContextProvider backed by AsyncKnowledgeGraph.

STATUS: EXPERIMENTAL (Multi-Actor / Social Extension — Pre-1.0 API).
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

from broker.components.context.providers import ContextProvider
from broker.components.social.knowledge_graph import AsyncKnowledgeGraph


class KnowledgeGraphSocialProvider(ContextProvider):
    """Injects visible social knowledge-graph facts into agent context.

    Queries :meth:`AsyncKnowledgeGraph.query_visible`, optionally delivers
    unseen facts into ``memory_engine`` via
    :meth:`AsyncKnowledgeGraph.sync_to_memory`, and writes formatted bullet lines
    into ``context[context_key]`` (default ``"social_gossip"``).
    """

    def __init__(
        self,
        kg: AsyncKnowledgeGraph,
        period_getter: Optional[Callable[[], int]] = None,
        *,
        memory_engine: Optional[Any] = None,
        top_k: int = 5,
        context_key: str = "social_gossip",
        sync_max_items: Optional[int] = None,
        predicates: Optional[Iterable[str]] = None,
        subjects: Optional[Iterable[str]] = None,
        include_self: bool = False,
    ) -> None:
        self.kg = kg
        self.period_getter = period_getter
        self.memory_engine = memory_engine
        self.top_k = top_k
        self.context_key = context_key
        self.sync_max_items = sync_max_items
        self.predicates = predicates
        self.subjects = subjects
        self.include_self = include_self

    def _resolve_period(self, context: Dict[str, Any], kwargs: Dict[str, Any]) -> int:
        if self.period_getter is not None:
            return int(self.period_getter())
        if "period" in kwargs and kwargs["period"] is not None:
            return int(kwargs["period"])
        if "year" in kwargs and kwargs["year"] is not None:
            return int(kwargs["year"])
        env_ctx = kwargs.get("env_context") or context.get("environment_context") or {}
        if isinstance(env_ctx, dict):
            for key in ("period", "current_year", "year"):
                if key in env_ctx and env_ctx[key] is not None:
                    return int(env_ctx[key])
        return 0

    def provide(
        self,
        agent_id: str,
        agents: Dict[str, Any],
        context: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Query visible KG triples for ``agent_id`` and populate context."""
        current_period = self._resolve_period(context, kwargs)

        if self.memory_engine is not None:
            max_sync = self.sync_max_items if self.sync_max_items is not None else self.top_k
            self.kg.sync_to_memory(
                agent_id,
                current_period,
                self.memory_engine,
                max_items=max_sync,
            )

        triples = self.kg.query_visible(
            agent_id,
            current_period,
            predicates=self.predicates,
            subjects=self.subjects,
            top_k=self.top_k,
            include_self=self.include_self,
        )
        lines = [self.kg.format_triple(t) for t in triples]

        if lines:
            context[self.context_key] = "\n".join(f"- {line}" for line in lines)
            if self.context_key == "social_gossip":
                local = context.setdefault("local", {})
                social = local.setdefault("social", [])
                if not isinstance(social, list):
                    social = [str(social)] if social else []
                    local["social"] = social
                social.extend(lines)
        else:
            context[self.context_key] = ""


__all__ = ["KnowledgeGraphSocialProvider"]
