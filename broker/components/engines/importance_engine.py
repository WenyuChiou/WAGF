from typing import List, Dict, Any, Optional
import logging

from cognitive_governance.agents import BaseAgent
from broker.components.memory_engine import MemoryEngine

logger = logging.getLogger(__name__)

class ImportanceMemoryEngine(MemoryEngine):
    """
    Active Retrieval Engine.
    Prioritizes significant events over routine ones.

    Weights and categories can be customized per domain:
    - categories: {"crisis": ["damage", "loss"], "social": ["neighbor", "friend"]}
    - weights: {"crisis": 1.0, "social": 0.5, "routine": 0.1}
    """
    def __init__(
        self, 
        window_size: int = 3, 
        top_k_significant: int = 2,
        weights: Optional[Dict[str, float]] = None,
        categories: Optional[Dict[str, List[str]]] = None
    ):
        self.window_size = window_size
        self.top_k_significant = top_k_significant
        self.storage: Dict[str, List[Dict[str, Any]]] = {}
        
        # Merge weights and categories (Generic defaults)
        self.weights = weights or {
            "critical": 1.0, "high": 0.8, "medium": 0.5, "routine": 0.1
        }
        self.categories = categories or {
            "critical": ["alert", "danger", "failure", "emergency"],
            "high": ["change", "success", "important", "new"],
            "medium": ["observed", "heard", "social", "network"]
        }
        
        # Standard: Enforce 0-1 normalization for scoring weights
        if any(w < 0.0 or w > 1.0 for w in self.weights.values()):
            logger.warning(f"[Universality:Warning] Memory weights {self.weights.values()} are outside 0-1 range. Standardizing to [0,1] is recommended.")

    def _score_content(self, content: str, agent: Optional[BaseAgent] = None) -> float:
        """Heuristic scoring based on keyword importance."""
        content_lower = content.lower()
        
        # Determine weights and categories (Support per-agent override)
        weights = self.weights
        categories = self.categories
        
        if agent and hasattr(agent, 'memory_config'):
            cfg = agent.memory_config
            weights = cfg.get("weights", self.weights)
            categories = cfg.get("categories", self.categories)

        # Use simple max-score strategy (highest category weight found)
        highest_weight = weights.get("routine", 0.1)
        
        for category, keywords in categories.items():
            for kw in keywords:
                if kw in content_lower:
                    weight = weights.get(category, 0.1)
                    if weight > highest_weight:
                        highest_weight = weight
                    break # Found a match for this category
                    
        return highest_weight

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Standard add_memory (Compatibility)"""
        if agent_id not in self.storage:
            self.storage[agent_id] = []
        
        score = metadata.get("significance") if metadata else None
        if score is None:
            score = self._score_content(content)
            
        self._add_memory_internal(agent_id, content, score)

    def _add_memory_internal(self, agent_id: str, content: str, score: float):
        self.storage[agent_id].append({
            "content": content,
            "score": score,
            "timestamp": len(self.storage[agent_id])
        })

    def add_memory_for_agent(self, agent: BaseAgent, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Added for Phase 12: Context-aware memory scoring."""
        if agent.id not in self.storage:
            self.storage[agent.id] = []
        
        score = metadata.get("significance") if metadata else None
        if score is None:
            score = self._score_content(content, agent)
            
        self._add_memory_internal(agent.id, content, score)

    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 5, **kwargs) -> List[str]:
        if agent.id not in self.storage:
            # First time access: check if agent has initial memory from profile
            initial_mem = getattr(agent, 'memory', [])
            if isinstance(initial_mem, list):
                self.storage[agent.id] = []
                for m in initial_mem:
                    self.add_memory(agent.id, m)
            else:
                self.storage[agent.id] = []

        mems = self.storage.get(agent.id, [])
        if not mems:
            return []
            
        # 1. Get most recent (Recency)
        recent = mems[-self.window_size:]
        recent_texts = [m["content"] for m in recent]
        
        # 2. Get most significant (Significance) - excluding those already in recent
        others = mems[:-self.window_size]
        significant = sorted(others, key=lambda x: x["score"], reverse=True)
        
        top_sig = []
        for s in significant:
            if s["content"] not in recent_texts:
                top_sig.append(s["content"])
            if len(top_sig) >= self.top_k_significant:
                break
                
        # Combine: Significant events first (for context) then Recent (for continuity)
        # or vice versa? Usually Significant provides the 'Trauma/History' context.
        return top_sig + recent_texts

    def clear(self, agent_id: str):
        self.storage[agent_id] = []



import heapq
