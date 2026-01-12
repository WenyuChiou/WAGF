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
    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 3) -> List[str]:
        """
        Retrieve relevant memories for an agent.
        
        Args:
            agent: The agent instance (for accessing custom_attributes/demographics).
            query: Optional semantic query for retrieval.
            top_k: Number of items to retrieve.
        """
        pass

    @abstractmethod
    def clear(self, agent_id: str):
        """Reset memory for an agent."""
        pass


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

    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 3) -> List[str]:
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


class ImportanceMemoryEngine(MemoryEngine):
    """
    Active Retrieval Engine.
    Prioritizes significant events over routine ones.
    
    Weights and categories can be customized:
    - categories: {"flood": ["flood", "damage"], "social": ["friend"]}
    - weights: {"flood": 1.0, "social": 0.5, "routine": 0.1}
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

    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 5) -> List[str]:
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


class HumanCentricMemoryEngine(MemoryEngine):
    """
    Human-Centered Memory Engine with:
    1. Emotional encoding (fear, relief, regret, trust shifts)
    2. Source differentiation (personal > neighbor > community)
    3. Stochastic consolidation (probabilistic long-term storage)
    4. Time-weighted decay (exponential with emotion modifier)
    
    All parameters use 0-1 scale for consistency.
    
    References:
    - Park et al. (2023) Generative Agents: recency × importance × relevance
    - Chapter 8: Memory consolidation and forgetting strategies
    - Tulving (1972): Episodic vs Semantic memory distinction
    """
    
    def __init__(
        self,
        window_size: int = 3,
        top_k_significant: int = 2,
        consolidation_prob: float = 0.7,      # P(consolidate) for high-importance items
        decay_rate: float = 0.1,               # λ in e^(-λt) decay
        emotional_weights: Optional[Dict[str, float]] = None,
        source_weights: Optional[Dict[str, float]] = None,
        seed: Optional[int] = None
    ):
        """
        Args:
            window_size: Number of recent memories always included
            top_k_significant: Number of significant historical events to retrieve
            consolidation_prob: Base probability of consolidating high-importance memory [0-1]
            decay_rate: Exponential decay rate for time-based forgetting [0-1]
            emotional_weights: Override emotional category weights
            source_weights: Override source type weights
            seed: Random seed for stochastic consolidation
        """
        import random
        self.rng = random.Random(seed)
        
        self.window_size = window_size
        self.top_k_significant = top_k_significant
        self.consolidation_prob = consolidation_prob
        self.decay_rate = decay_rate
        
        # Working memory (short-term)
        self.working: Dict[str, List[Dict[str, Any]]] = {}
        # Long-term memory (consolidated)
        self.longterm: Dict[str, List[Dict[str, Any]]] = {}
        
        # Emotional encoding weights (PMT-aligned)
        self.emotional_weights = emotional_weights or {
            "fear": 1.0,         # Flood damage, high threat perception
            "regret": 0.9,       # "I should have elevated"
            "relief": 0.8,       # Insurance payout, successful claim
            "trust_shift": 0.7,  # Trust changes (increase/decrease)
            "observation": 0.4,  # Neutral social observation
            "routine": 0.1       # No notable event
        }
        
        # Source differentiation (personal experience weighted higher)
        self.source_weights = source_weights or {
            "personal": 1.0,     # MY house flooded
            "neighbor": 0.7,     # Neighbor's experience
            "community": 0.5,    # Community statistics
            "abstract": 0.3      # General information
        }
        
        # Emotion keywords for classification
        self.emotion_keywords = {
            "fear": ["flood", "damage", "destroyed", "loss", "$", "threat", "risk", "vulnerable"],
            "regret": ["should have", "could have", "wish", "if only", "mistake"],
            "relief": ["paid", "claim", "covered", "insurance worked", "grant", "approved"],
            "trust_shift": ["trust", "reliable", "doubt", "skeptic", "faith"]
        }
    
    def _classify_emotion(self, content: str, agent: Optional[BaseAgent] = None) -> str:
        """Classify content emotion using keyword matching."""
        content_lower = content.lower()
        
        emotion_keywords = self.emotion_keywords
        if agent and hasattr(agent, 'memory_config'):
            emotion_keywords = agent.memory_config.get("emotion_keywords", self.emotion_keywords)
            
        for emotion, keywords in emotion_keywords.items():
            for kw in keywords:
                if kw in content_lower:
                    return emotion
        return "routine"
    
    def _classify_source(self, content: str, agent: Optional[BaseAgent] = None) -> str:
        """Classify content source type."""
        content_lower = content.lower()
        
        # Default patterns
        personal_patterns = ["i ", "my ", "me ", "i've"]
        neighbor_patterns = ["neighbor", "friend"]
        community_patterns = ["%", "community", "region", "area"]
        
        if agent and hasattr(agent, 'memory_config'):
            source_cfg = agent.memory_config.get("source_patterns", {})
            personal_patterns = source_cfg.get("personal", personal_patterns)
            neighbor_patterns = source_cfg.get("neighbor", neighbor_patterns)
            community_patterns = source_cfg.get("community", community_patterns)

        if any(w in content_lower for w in personal_patterns):
            return "personal"
        elif any(w in content_lower for w in neighbor_patterns):
            return "neighbor"
        elif any(w in content_lower for w in community_patterns):
            return "community"
        return "abstract"
    
    def _compute_importance(self, content: str, metadata: Optional[Dict] = None, agent: Optional[BaseAgent] = None) -> float:
        """Compute memory importance score [0-1] based on emotion and source."""
        emotion = metadata.get("emotion") if metadata else None
        source = metadata.get("source") if metadata else None
        
        if emotion is None:
            emotion = self._classify_emotion(content, agent)
        if source is None:
            source = self._classify_source(content, agent)
        
        emotional_weights = self.emotional_weights
        source_weights = self.source_weights
        
        if agent and hasattr(agent, 'memory_config'):
            emotional_weights = agent.memory_config.get("emotional_weights", self.emotional_weights)
            source_weights = agent.memory_config.get("source_weights", self.source_weights)

        emotion_w = emotional_weights.get(emotion, 0.1)
        source_w = source_weights.get(source, 0.3)
        
        # Combined importance = emotion × source (both 0-1)
        return emotion_w * source_w
    
    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Standard add_memory (Compatibility)."""
        # We don't have agent object here, so we use default classification
        self._add_memory_internal(agent_id, content, metadata=metadata)

    def add_memory_for_agent(self, agent: BaseAgent, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Added for Phase 12: Context-aware memory scoring."""
        self._add_memory_internal(agent.id, content, metadata=metadata, agent=agent)

    def _add_memory_internal(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None, agent: Optional[BaseAgent] = None):
        """Internal worker for adding memory with scoring."""
        if agent_id not in self.working:
            self.working[agent_id] = []
        if agent_id not in self.longterm:
            self.longterm[agent_id] = []
        
        emotion = self._classify_emotion(content, agent)
        source = self._classify_source(content, agent)
        importance = self._compute_importance(content, metadata, agent)
        
        memory_item = {
            "content": content,
            "importance": importance,
            "emotion": emotion,
            "source": source,
            "timestamp": len(self.working[agent_id]) + len(self.longterm[agent_id]),
            "consolidated": False
        }
        
        self.working[agent_id].append(memory_item)
        
        # Stochastic consolidation: high importance items have chance to go to long-term
        if importance >= 0.6:  # Only consider consolidation for significant memories
            consolidate_p = self.consolidation_prob * importance
            if self.rng.random() < consolidate_p:
                memory_item["consolidated"] = True
                self.longterm[agent_id].append(memory_item)
    
    def _apply_decay(self, memories: List[Dict], current_time: int) -> List[Dict]:
        """Apply time-decay to memories, removing those below threshold."""
        import math
        decayed = []
        for m in memories:
            age = current_time - m["timestamp"]
            # Emotion-modified decay: high emotion memories decay slower
            emotion_modifier = 1.0 - (0.5 * self.emotional_weights.get(m["emotion"], 0.1))
            effective_decay = self.decay_rate * emotion_modifier
            decay_factor = math.exp(-effective_decay * age)
            m["decayed_importance"] = m["importance"] * decay_factor
            if m["decayed_importance"] > 0.05:  # Threshold for forgetting
                decayed.append(m)
        return decayed
    
    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 5) -> List[str]:
        """Retrieve memories: recent working + significant long-term."""
        if agent.id not in self.working:
            # Initialize from agent profile
            initial_mem = getattr(agent, 'memory', [])
            self.working[agent.id] = []
            self.longterm[agent.id] = []
            if isinstance(initial_mem, list):
                for m in initial_mem:
                    self.add_memory(agent.id, m)
        
        working = self.working.get(agent.id, [])
        longterm = self.longterm.get(agent.id, [])
        
        if not working and not longterm:
            return []
        
        current_time = len(working) + len(longterm)
        
        # 1. Get recent working memory
        recent = working[-self.window_size:]
        recent_texts = [m["content"] for m in recent]
        
        # 2. Get significant long-term memories (with decay)
        decayed_longterm = self._apply_decay(longterm, current_time)
        sorted_longterm = sorted(decayed_longterm, key=lambda x: x["decayed_importance"], reverse=True)
        
        significant = []
        for m in sorted_longterm:
            if m["content"] not in recent_texts and m["content"] not in significant:
                significant.append(m["content"])
            if len(significant) >= self.top_k_significant:
                break
        
        # Combine: significant (historical context) + recent (continuity)
        return significant + recent_texts
    
    def forget(self, agent_id: str, strategy: str = "importance", threshold: float = 0.2) -> int:
        """Forget memories using specified strategy.
        
        Strategies:
        - 'importance': Remove memories below threshold
        - 'time': Remove oldest memories beyond capacity
        - 'emotion': Remove low-emotion memories
        
        Returns: Number of memories forgotten
        """
        if agent_id not in self.working:
            return 0
        
        original_count = len(self.working[agent_id]) + len(self.longterm.get(agent_id, []))
        
        if strategy == "importance":
            self.working[agent_id] = [m for m in self.working[agent_id] if m["importance"] >= threshold]
            self.longterm[agent_id] = [m for m in self.longterm.get(agent_id, []) if m["importance"] >= threshold]
        elif strategy == "time":
            # Keep only recent 50 in working, recent 20 high-importance in longterm
            self.working[agent_id] = self.working[agent_id][-50:]
            self.longterm[agent_id] = sorted(self.longterm.get(agent_id, []), 
                                              key=lambda x: x["importance"], reverse=True)[:20]
        
        new_count = len(self.working[agent_id]) + len(self.longterm.get(agent_id, []))
        return original_count - new_count
    
    def clear(self, agent_id: str):
        """Clear all memories for agent."""
        self.working[agent_id] = []
        self.longterm[agent_id] = []
