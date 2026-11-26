from typing import List, Dict, Any, Optional

from broker.agents import BaseAgent
from ..engine import MemoryEngine

class WindowMemoryEngine(MemoryEngine):
    """
    Standard sliding window memory. Returns the last N items.

    CONTENT-ONLY engine: ``retrieve()`` returns ``List[str]`` under a
    documented Invariant-1 exemption (broker/INVARIANTS.md, 2026-06-10) —
    window stores no metadata to preserve, and its production consumers eat
    plain strings. Select ``humancentric`` for any path that depends on
    emotion / importance / source metadata. The exemption is closed to new
    engines: anything new must return ``List[MemoryRecord]``.
    """
    def __init__(self, window_size: int = 3, enforce_window: bool = False):
        # enforce_window (opt-in, default off): keep only the last
        # ``window_size`` items, so a prompt holds at most
        # min(window_size, top_k) of them. Off, the engine keeps the last 100
        # and ``window_size`` changes nothing, as before
        # (python -m broker.run turns it on when the YAML sets window_size).
        if enforce_window and (isinstance(window_size, bool) or not isinstance(window_size, int)
                               or window_size < 1):
            raise ValueError(f"window_size must be an integer >= 1, got {window_size!r}")
        self.window_size = window_size
        self.enforce_window = enforce_window
        self.storage: Dict[str, List[str]] = {}

    def _keep(self) -> int:
        return self.window_size if self.enforce_window else 100

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        if agent_id not in self.storage:
            self.storage[agent_id] = []
        self.storage[agent_id].append(content)
        self.storage[agent_id] = self.storage[agent_id][-self._keep():]

    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 3, **kwargs) -> List[str]:
        if agent.id not in self.storage:
            # First time access: check if agent has initial memory from profile
            initial_mem = getattr(agent, 'memory', [])
            if isinstance(initial_mem, list):
                self.storage[agent.id] = list(initial_mem)
            else:
                self.storage[agent.id] = []
                
        mems = self.storage.get(agent.id, [])
        if self.enforce_window:
            mems = mems[-self.window_size:]  # an initial profile memory may be longer
        return mems[-top_k:]

    def clear(self, agent_id: str):
        if agent_id in self.storage:
            self.storage[agent_id] = []
