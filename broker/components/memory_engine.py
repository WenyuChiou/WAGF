from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from agents.base_agent import BaseAgent

class MemoryEngine(ABC):
    """
    Abstract Base Class for managing agent memory and retrieval.
    Decouples 'Thinking' (LLM) from 'Retention' (Storage).
    """
    
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

from broker.components.engines.window_engine import WindowMemoryEngine
from broker.components.engines.importance_engine import ImportanceMemoryEngine
from broker.components.engines.humancentric_engine import HumanCentricMemoryEngine
from broker.components.engines.hierarchical_engine import HierarchicalMemoryEngine
from broker.components.memory_seeding import seed_memory_from_agents

def create_memory_engine(engine_type: str = "universal", **kwargs) -> MemoryEngine:
    """
    Factory function for creating memory engines.
    
    Args:
        engine_type (str): "window" | "importance" | "humancentric" | "universal"
        **kwargs: Arguments passed to the engine constructor.
    
    Returns:
        MemoryEngine: The instantiated engine.
    """
    engine_type = engine_type.lower()
    
    if engine_type == "window":
        return WindowMemoryEngine(**kwargs)
    elif engine_type == "importance":
        return ImportanceMemoryEngine(**kwargs)
    elif engine_type == "humancentric":
        return HumanCentricMemoryEngine(**kwargs)
    elif engine_type == "universal":
        from broker.components.universal_memory import UniversalCognitiveEngine
        return UniversalCognitiveEngine(**kwargs)
    else:
        raise ValueError(f"Unknown memory engine type: {engine_type}")
