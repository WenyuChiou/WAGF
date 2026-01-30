from typing import List, Dict, Any, Optional

from cognitive_governance.agents import BaseAgent
from broker.components.memory_engine import MemoryEngine

class HierarchicalMemoryEngine(MemoryEngine):
    """
    Tiered memory system inspired by MemGPT.
    
    1. Core Memory: Permanent identity/demographics (from fixed_attributes)
    2. Episodic Memory: Recent events (Sliding window)
    3. Semantic Memory: Consolidated patterns/summaries of history
    """
    def __init__(self, window_size: int = 5, semantic_top_k: int = 3):
        self.window_size = window_size
        self.semantic_top_k = semantic_top_k
        self.episodic: Dict[str, List[Dict[str, Any]]] = {}
        self.semantic: Dict[str, List[Dict[str, Any]]] = {}

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        if agent_id not in self.episodic:
            self.episodic[agent_id] = []
        
        entry = {
            "content": content,
            "timestamp": len(self.episodic[agent_id]),
            "importance": metadata.get("importance", 0.5) if metadata else 0.5
        }
        self.episodic[agent_id].append(entry)
        
        # Consolidation check: if episodic grows too large, move important items to semantic
        if len(self.episodic[agent_id]) > self.window_size * 4:
            self._consolidate(agent_id)

    def _consolidate(self, agent_id: str):
        """Move high-importance episodic memories to semantic memory."""
        memories = self.episodic[agent_id]
        if not memories: return
        
        # Keep everything in episodic for now, but tag some for semantic retrieval
        # In a real system, episodic would be pruned and semantic would be summarized or indexed.
        pass

    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 5, **kwargs) -> Dict[str, Any]:
        """
        Returns a structured dictionary of memories across all tiers.
        """
        agent_id = agent.id
        
        # Phase 0: Initialize from profile if empty
        if agent_id not in self.episodic:
            initial_mem = getattr(agent, 'memory', [])
            self.episodic[agent_id] = []
            if isinstance(initial_mem, list):
                for m in initial_mem:
                    self.add_memory(agent_id, m)
        
        # 1. CORE MEMORY (Fixed Attributes)

        core = {}
        if hasattr(agent, 'fixed_attributes'):
            core = {k: v for k, v in agent.fixed_attributes.items() if isinstance(v, (str, int, float, bool))}
            
        # 2. EPISODIC MEMORY (Recent)
        episodic_entries = self.episodic.get(agent_id, [])
        recent = [m["content"] for m in episodic_entries[-self.window_size:]]
        
        # 3. SEMANTIC MEMORY (Important Historical)
        # For now, use importance-based selection from older entries
        historical = episodic_entries[:-self.window_size]
        important = sorted(historical, key=lambda x: x["importance"], reverse=True)
        semantic = [m["content"] for m in important[:self.semantic_top_k]]
        
        # Return a structure that ContextBuilder can interpret
        return {
            "core": core,
            "episodic": recent,
            "semantic": semantic
        }

    def clear(self, agent_id: str):
        self.episodic[agent_id] = []
        self.semantic[agent_id] = []
