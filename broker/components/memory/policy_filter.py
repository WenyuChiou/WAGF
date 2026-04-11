"""PolicyFilteredMemoryEngine: proxy that enforces a MemoryWritePolicy.

Wraps any MemoryEngine implementation and intercepts add_memory calls.
Each write is classified via policy_classifier.classify() using an
optional domain_mapping. If the policy forbids the classified content
type, the write is silently dropped and a counter is incremented.
All non-write methods (retrieve, clear, etc.) are forwarded to the
inner engine via explicit methods and __getattr__ fallback.

Mirror the structural pattern of the single-agent DecisionFilteredMemoryEngine
(see examples/single_agent/run_flood.py:211-226) - same proxy shape, same
__getattr__ fallback convention.
"""
from collections import defaultdict
from typing import Any, Dict, Optional

from broker.config.memory_policy import MemoryWritePolicy

from .content_types import MemoryContentType
from .policy_classifier import classify


class PolicyFilteredMemoryEngine:
    """Memory engine proxy that enforces a MemoryWritePolicy.

    Args:
        inner: The real memory engine instance to wrap.
        policy: The MemoryWritePolicy to enforce.
        domain_mapping: Optional per-domain category -> content type dict.
            Passed to the classifier on every add_memory call.
    """

    def __init__(
        self,
        inner: Any,
        policy: MemoryWritePolicy,
        domain_mapping: Optional[Dict[str, MemoryContentType]] = None,
    ):
        self._inner = inner
        self._policy = policy
        self._domain_mapping = domain_mapping
        self._dropped_counts: Dict[str, int] = defaultdict(int)
        self._allowed_counts: Dict[str, int] = defaultdict(int)

    @property
    def policy(self) -> MemoryWritePolicy:
        return self._policy

    @property
    def domain_mapping(self) -> Optional[Dict[str, MemoryContentType]]:
        return self._domain_mapping

    @property
    def dropped_counts(self) -> Dict[str, int]:
        """Per-content-type count of writes that were dropped.

        Keys are MemoryContentType string values; values are ints.
        Returned as a plain dict so callers can json.dumps() it safely.
        """
        return dict(self._dropped_counts)

    @property
    def allowed_counts(self) -> Dict[str, int]:
        """Per-content-type count of writes that were allowed through."""
        return dict(self._allowed_counts)

    def stats(self) -> Dict[str, Any]:
        """Return a serializable summary for the reproducibility manifest."""
        return {
            "policy": self._policy.to_dict(),
            "dropped_counts": self.dropped_counts,
            "allowed_counts": self.allowed_counts,
            "domain_mapping_size": (
                len(self._domain_mapping) if self._domain_mapping else 0
            ),
        }

    def _should_allow(self, metadata: Optional[Dict[str, Any]]) -> bool:
        content_type = classify(metadata, domain_mapping=self._domain_mapping)
        if self._policy.allows(content_type):
            self._allowed_counts[content_type.value] += 1
            return True
        self._dropped_counts[content_type.value] += 1
        return False

    def add_memory(
        self,
        agent_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self._should_allow(metadata):
            return None
        return self._inner.add_memory(agent_id, content, metadata)

    def add_memory_for_agent(
        self,
        agent: Any,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        if not self._should_allow(metadata):
            return None
        if hasattr(self._inner, "add_memory_for_agent"):
            return self._inner.add_memory_for_agent(agent, content, metadata)
        return self._inner.add_memory(agent.id, content, metadata)

    def retrieve(self, agent, query=None, top_k: int = 3, **kwargs):
        return self._inner.retrieve(agent, query=query, top_k=top_k, **kwargs)

    def clear(self, agent_id: str):
        return self._inner.clear(agent_id)

    def __getattr__(self, name: str):
        return getattr(self._inner, name)


__all__ = ["PolicyFilteredMemoryEngine"]
