from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

from cognitive_governance.agents import BaseAgent

if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.memory import MemoryScorer, MemoryScore

class MemoryEngine(ABC):
    """
    Abstract Base Class for managing agent memory and retrieval.
    Decouples 'Thinking' (LLM) from 'Retention' (Storage).

    Task-034: Added optional SDK MemoryScorer integration for domain-aware scoring.
    """
    def __init__(self, scorer: Optional["MemoryScorer"] = None):
        """
        Initialize memory engine with optional domain scorer.

        Args:
            scorer: Optional SDK MemoryScorer for domain-aware relevance scoring
        """
        self._scorer = scorer

    @property
    def scorer(self) -> Optional["MemoryScorer"]:
        """Get the configured memory scorer."""
        return self._scorer

    @scorer.setter
    def scorer(self, value: Optional["MemoryScorer"]):
        """Set a memory scorer for domain-aware retrieval."""
        self._scorer = value

    @abstractmethod
    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a new memory item for an agent."""
        pass

    @abstractmethod
    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 3, **kwargs) -> List[str]:
        """
        Retrieve relevant memories for an agent.

        Args:
            agent: The agent instance (for accessing custom_attributes/demographics).
            query: Optional semantic query for retrieval.
            top_k: Number of items to retrieve.
            **kwargs: Additional context (e.g., world_state).
        """
        pass

    @abstractmethod
    def clear(self, agent_id: str):
        """Reset memory for an agent."""
        pass

    def retrieve_stratified(
        self,
        agent_id: str,
        allocation: Optional[Dict[str, int]] = None,
        total_k: int = 10,
        contextual_boosters: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """Retrieve memories with source-stratified diversity guarantee.

        Subclasses that support stratified retrieval should override this.
        Default raises NotImplementedError.

        Args:
            agent_id: Agent to retrieve for
            allocation: Dict mapping source -> max slots
            total_k: Total memories to return
            contextual_boosters: Optional score boosters

        Returns:
            List of memory content strings, stratified by source
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support retrieve_stratified(). "
            "Use HumanCentricMemoryEngine or UniversalCognitiveEngine."
        )

    def retrieve_with_scoring(
        self,
        agent: BaseAgent,
        context: Dict[str, Any],
        query: Optional[str] = None,
        top_k: int = 3,
        **kwargs
    ) -> List[Tuple[str, Optional["MemoryScore"]]]:
        """
        v2 retrieval with domain-aware scoring (Task-034).

        Uses SDK MemoryScorer to rank memories by domain-specific relevance.
        Falls back to standard retrieve if no scorer is configured.

        Args:
            agent: The agent instance
            context: Current decision context (environment state, etc.)
            query: Optional semantic query
            top_k: Number of items to retrieve

        Returns:
            List of (memory_content, MemoryScore) tuples, sorted by score descending.
            MemoryScore is None if no scorer is configured.
        """
        memories = self.retrieve(agent, query=query, top_k=top_k * 2, **kwargs)

        if not self._scorer:
            return [(m, None) for m in memories[:top_k]]

        # Get agent state for scoring
        agent_state = {}
        if hasattr(agent, "custom_attributes"):
            agent_state = agent.custom_attributes.copy()
        if hasattr(agent, "__dict__"):
            agent_state.update({
                k: v for k, v in agent.__dict__.items()
                if not k.startswith("_") and not callable(v)
            })

        # Score each memory
        scored = []
        for memory_content in memories:
            memory_dict = {"content": memory_content}
            score = self._scorer.score(memory_dict, context, agent_state)
            scored.append((memory_content, score))

        # Sort by score descending and take top_k
        scored.sort(key=lambda x: x[1].total if x[1] else 0, reverse=True)
        return scored[:top_k]

    def get_scored_memories(
        self,
        agent: BaseAgent,
        context: Dict[str, Any],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get memories with full scoring breakdown for explainability.

        Args:
            agent: The agent instance
            context: Current decision context
            top_k: Number of memories to return

        Returns:
            List of dicts with 'content', 'score', 'components', 'explanation'
        """
        results = self.retrieve_with_scoring(agent, context, top_k=top_k)

        return [
            {
                "content": content,
                "score": score.total if score else 0.5,
                "components": score.components if score else {},
                "explanation": score.explanation if score else "No scorer configured",
                "rank": i + 1,
            }
            for i, (content, score) in enumerate(results)
        ]

from broker.components.engines.window_engine import WindowMemoryEngine
from broker.components.engines.importance_engine import ImportanceMemoryEngine
from broker.components.engines.humancentric_engine import HumanCentricMemoryEngine
from broker.components.engines.hierarchical_engine import HierarchicalMemoryEngine
from broker.components.memory_seeding import seed_memory_from_agents


def create_memory_engine(
    engine_type: str = "universal",
    scorer: Optional["MemoryScorer"] = None,
    persistence: Optional[Any] = None,
    **kwargs
) -> MemoryEngine:
    """
    Factory function for creating memory engines.

    Args:
        engine_type (str): "window" | "importance" | "humancentric" | "universal"
        scorer: Optional SDK MemoryScorer for domain-aware retrieval (Task-034)
        persistence: Optional SDK MemoryPersistence for save/load (Task-034)
        **kwargs: Arguments passed to the engine constructor.

    Returns:
        MemoryEngine: The instantiated engine.

    Example:
        >>> from cognitive_governance.v1_prototype.memory import get_memory_scorer, create_persistence
        >>> scorer = get_memory_scorer("flood")
        >>> persistence = create_persistence("json", "./memory_store")
        >>> engine = create_memory_engine("universal", scorer=scorer, persistence=persistence)
    """
    engine_type = engine_type.lower()

    if engine_type == "window":
        engine = WindowMemoryEngine(**kwargs)
    elif engine_type == "importance":
        engine = ImportanceMemoryEngine(**kwargs)
    elif engine_type == "humancentric":
        engine = HumanCentricMemoryEngine(**kwargs)
    elif engine_type == "universal":
        from broker.components.universal_memory import UniversalCognitiveEngine
        engine = UniversalCognitiveEngine(persistence=persistence, **kwargs)
    else:
        raise ValueError(f"Unknown memory engine type: {engine_type}")

    # Attach scorer if provided (Task-034)
    if scorer is not None:
        engine.scorer = scorer

    return engine
