from typing import List, Dict, Any, Optional

from cognitive_governance.agents import BaseAgent
from broker.components.memory_engine import MemoryEngine

class WindowMemoryEngine(MemoryEngine):
    """
    Standard sliding window memory. Returns the last N items.
    """
    def __init__(self, window_size: int = 3):
        self.window_size = window_size
        self.storage: Dict[str, List[str]] = {}

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        if agent_id not in self.storage:
            self.storage[agent_id] = []
        self.storage[agent_id].append(content)
        # We don't truncate here to allow retrieve() to handle different window sizes if needed,
        # but for simplicity we can truncate to a maximum reasonable buffer.
        self.storage[agent_id] = self.storage[agent_id][-100:] 

    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 3, **kwargs) -> List[str]:
        if agent.id not in self.storage:
            # First time access: check if agent has initial memory from profile
            initial_mem = getattr(agent, 'memory', [])
            if isinstance(initial_mem, list):
                self.storage[agent.id] = list(initial_mem)
            else:
                self.storage[agent.id] = []
                
        mems = self.storage.get(agent.id, [])
        return mems[-top_k:]

    def clear(self, agent_id: str):
        if agent_id in self.storage:
            self.storage[agent_id] = []
