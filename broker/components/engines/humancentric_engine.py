from typing import List, Dict, Any, Optional, Tuple
import heapq
import logging

from cognitive_governance.agents import BaseAgent
from broker.components.memory_engine import MemoryEngine

logger = logging.getLogger(__name__)

class HumanCentricMemoryEngine(MemoryEngine):
    """
    Human-Centered Memory Engine with:
    1. Emotional encoding (fear, relief, regret, trust shifts)
    2. Source differentiation (personal > neighbor > community)
    3. Stochastic consolidation (probabilistic long-term storage)
    4. Time-weighted decay (exponential with emotion modifier)
    
    All parameters use 0-1 scale for consistency.
    
    References:
    - Park et al. (2023) Generative Agents: recency x importance x relevance
    - Chapter 8: Memory consolidation and forgetting strategies
    - Tulving (1972): Episodic vs Semantic memory distinction
    """
    
    def __init__(
        self,
        window_size: int = 3,
        top_k_significant: int = 2,
        consolidation_prob: float = 0.7,      # P(consolidate) for high-importance items
        consolidation_threshold: float = 0.6, # Min importance to consider consolidation
        decay_rate: float = 0.1,               # λ in e^(-λt) decay
        emotional_weights: Optional[Dict[str, float]] = None,
        source_weights: Optional[Dict[str, float]] = None,
        # v2 Weighted Scoring Params
        W_recency: float = 0.3,
        W_importance: float = 0.5,
        W_context: float = 0.2,
        # Mode switch: "legacy" (v1 compatible) or "weighted" (v2)
        ranking_mode: str = "legacy",
        seed: Optional[int] = None,
        forgetting_threshold: float = 0.2,    # Default threshold for forgetting
    ):
        """
        Args:
            window_size: Number of recent memories always included
            top_k_significant: Number of historical events
            ranking_mode: "legacy" (v1) or "weighted" (v2)
        """
        # Note: HumanCentricMemoryEngine is superseded by UniversalCognitiveEngine (v3)
        # but remains the production engine for the irrigation ABM case study.
        # v1 behavior: arousal_threshold=99.0; v2 behavior: arousal_threshold=0.0
        import random
        self.rng = random.Random(seed)
        
        self.window_size = window_size
        self.top_k_significant = top_k_significant
        self.consolidation_prob = consolidation_prob
        self.consolidation_threshold = consolidation_threshold
        self.decay_rate = decay_rate
        self.ranking_mode = ranking_mode
        self.forgetting_threshold = forgetting_threshold
        
        # Retrieval weights
        self.W_recency = W_recency
        self.W_importance = W_importance
        self.W_context = W_context
        
        # Working memory (short-term)
        self.working: Dict[str, List[Dict[str, Any]]] = {}
        # Long-term memory (consolidated)
        self.longterm: Dict[str, List[Dict[str, Any]]] = {}
        
        # Emotional encoding weights (Generic)
        self.emotional_weights = emotional_weights or {
            "critical": 1.0,     # Negative impact, failure, damage
            "major": 0.9,        # Significant event or choice
            "positive": 0.8,     # Success, reward, protection
            "shift": 0.7,        # Trust or behavioral changes
            "observation": 0.4,  # Neutral social observation
            "routine": 0.1       # No notable event
        }
        
        # Source differentiation (personal experience weighted higher)
        self.source_weights = source_weights or {
            "personal": 1.0,     # Direct experience
            "neighbor": 0.7,     # Proximate observation
            "community": 0.5,    # Group statistics
            "abstract": 0.3      # General information
        }
        
        # Emotion keywords for classification (Generic)
        self.emotion_keywords = {
            "critical": ["failure", "damage", "destroyed", "loss", "error", "emergency"],
            "major": ["should have", "could have", "important", "decision"],
            "positive": ["success", "improved", "protected", "approved", "gain"],
            "shift": ["trust", "reliable", "doubt", "skeptic", "change"]
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
        
        # Default patterns logic (Fixing the logic error)
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
        # Allow direct override via metadata
        if metadata and "importance" in metadata:
            return float(metadata["importance"])
            
        emotion = metadata.get("emotion") if metadata else None
        source = metadata.get("source") if metadata else None
        
        if emotion is None: emotion = self._classify_emotion(content, agent)
        if source is None: source = self._classify_source(content, agent)
        
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

        # Revised logic for importance, emotion, source.
        # Initialize importance, emotion, and source. Prioritize metadata if available.
        importance = 0.5
        emotion = "routine"
        source = "abstract"

        if metadata:
            importance = float(metadata.get("importance", importance))
            emotion = metadata.get("emotion", self._classify_emotion(content, agent))
            source = metadata.get("source", self._classify_source(content, agent))
        else:
            emotion = self._classify_emotion(content, agent)
            source = self._classify_source(content, agent)
            importance = self._compute_importance(content, {"emotion": emotion, "source": source}, agent)

        final_metadata = metadata.copy() if metadata else {}
        final_metadata["importance"] = importance
        final_metadata["emotion"] = emotion
        final_metadata["source"] = source

        memory_item = {
            "content": content,
            "importance": importance,
            "emotion": emotion,
            "source": source,
            "timestamp": len(self.working[agent_id]) + len(self.longterm[agent_id]),
            "consolidated": False,
            **final_metadata
        }

        self.working[agent_id].append(memory_item)
        
        # Stochastic consolidation: high importance items have chance to go to long-term
        if importance >= self.consolidation_threshold:  # Configurable threshold
            consolidate_p = self.consolidation_prob * importance
            if self.rng.random() < consolidate_p:
                memory_item["consolidated"] = True
                self.longterm[agent_id].append(memory_item)
    
    def _apply_decay(self, memories: List[Dict], current_time: int) -> List[Dict]:
        """Apply emotional time decay (Legacy Logic)."""
        import math
        decayed = []
        for m in memories:
            age = current_time - m["timestamp"]
            # Emotion-modified decay: high emotion memories decay slower
            emotion_modifier = 1.0 - (0.5 * self.emotional_weights.get(m.get("emotion"), 0.1))
            effective_decay = self.decay_rate * emotion_modifier
            decay_factor = math.exp(-effective_decay * age)
            m["decayed_importance"] = m["importance"] * decay_factor
            if m["decayed_importance"] > 0.05:  # Threshold for forgetting
                decayed.append(m)
        return decayed
    
    def retrieve(self, agent: BaseAgent, query: Optional[str] = None, top_k: int = 5, contextual_boosters: Optional[Dict[str, float]] = None, **kwargs) -> List[str]:
        """Retrieve memories using dual mode: Legacy (v1) or Weighted (v2)."""
        
        if agent.id not in self.working:
            initial_mem = getattr(agent, 'memory', [])
            self.working[agent.id] = []
            self.longterm[agent.id] = []
            if isinstance(initial_mem, list):
                for m in initial_mem:
                    # Ensure metadata is correctly extracted and passed.
                    if isinstance(m, dict) and "content" in m:
                        content_to_add = m["content"]
                        metadata_to_add = m.get("metadata", {})
                        self.add_memory_for_agent(agent, content_to_add, metadata_to_add)
                    else:
                        # Handle cases where 'm' is just a string (no metadata).
                        self.add_memory_for_agent(agent, m)
        
        working = self.working.get(agent.id, [])
        longterm = self.longterm.get(agent.id, [])
        
        if not working and not longterm:
            return []
        
        max_timestamp = -1
        if working:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in working))
        if longterm:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in longterm))
        current_time = max_timestamp + 1

        # --- MODE 1: LEGACY (v1 Parity for Groups A/B) ---
        if self.ranking_mode == "legacy":
             recent = working[-self.window_size:]
             recent_texts = [m["content"] for m in recent]
             
             decayed_longterm = self._apply_decay(longterm, current_time)
             
             # Contextual Boosters are IGNORED in legacy mode
             # Use generic significance key
             top_significant = heapq.nlargest(
                 self.top_k_significant + len(recent_texts) + 2,
                 decayed_longterm,
                 key=lambda x: x.get("decayed_importance", 0)
             )
             
             significant = []
             for m in top_significant:
                 if m["content"] not in recent_texts and m["content"] not in significant:
                     significant.append(m["content"])
                 if len(significant) >= self.top_k_significant:
                     break
            
             return significant + recent_texts

        # --- MODE 2: WEIGHTED (v2 Model for Stress Test) ---
        else:
            # Correctly combine and deduplicate memories while preserving metadata.
            all_memories_map = {}
            for mem in self._apply_decay(longterm, current_time):
                all_memories_map[mem["content"]] = mem
            for mem in working:
                all_memories_map[mem["content"]] = mem
            all_memories = list(all_memories_map.values())

            scored_memories = []
            for mem in all_memories:
                age = current_time - mem["timestamp"]
                recency_score = 1.0 - (age / max(current_time, 1))
                importance_score = mem.get("importance", mem.get("decayed_importance", 0.1))
                
                contextual_boost = 0.0
                if contextual_boosters:
                    for tag_key_val, boost_val in contextual_boosters.items():
                        if ":" in tag_key_val:
                            tag_cat, tag_val = tag_key_val.split(":", 1)
                            if mem.get(tag_cat) == tag_val:
                                contextual_boost = boost_val
                                break
                
                final_score = (recency_score * self.W_recency) + \
                              (importance_score * self.W_importance) + \
                              (contextual_boost * self.W_context)

                logger.debug(f"Memory: '{mem['content']}'")
                logger.debug(f"  Timestamp: {mem['timestamp']}, Current Time: {current_time}")
                logger.debug(f"  Emotion: {mem.get('emotion')}, Source: {mem.get('source')}")
                logger.debug(
                    f"  Scores - Recency: {recency_score:.2f}, Importance: {importance_score:.2f}, "
                    f"Contextual Boost: {contextual_boost:.2f}"
                )
                logger.debug(f"  Final Score: {final_score:.2f}")

                scored_memories.append((mem["content"], final_score))
            
            top_k_memories = heapq.nlargest(top_k, scored_memories, key=lambda x: x[1])
            return [content for content, score in top_k_memories]

    def retrieve_stratified(
        self,
        agent_id: str,
        allocation: Optional[Dict[str, int]] = None,
        total_k: int = 10,
        contextual_boosters: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """Retrieve memories with source-stratified diversity guarantee.

        Instead of pure top-k by score, allocates retrieval slots by source category.
        This ensures reflection prompts see a mix of personal experiences,
        neighbor observations, community events, and past reflections.

        Args:
            agent_id: Agent to retrieve for
            allocation: Dict mapping source -> max slots.
                        Default: {"personal": 4, "neighbor": 2, "community": 2, "reflection": 1, "abstract": 1}
            total_k: Total memories to return (cap)
            contextual_boosters: Same as retrieve() -- optional score boosters

        Returns:
            List of memory content strings, stratified by source
        """
        if allocation is None:
            allocation = {
                "personal": 4,
                "neighbor": 2,
                "community": 2,
                "reflection": 1,
                "abstract": 1,
            }

        working = self.working.get(agent_id, [])
        longterm = self.longterm.get(agent_id, [])

        if not working and not longterm:
            return []

        # Combine all memories (same dedup logic as retrieve weighted mode)
        max_timestamp = -1
        if working:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in working))
        if longterm:
            max_timestamp = max(max_timestamp, max(m["timestamp"] for m in longterm))
        current_time = max_timestamp + 1

        all_memories_map = {}
        for mem in self._apply_decay(longterm, current_time):
            all_memories_map[mem["content"]] = mem
        for mem in working:
            all_memories_map[mem["content"]] = mem
        all_memories = list(all_memories_map.values())

        # Score all memories (same scoring as weighted mode)
        scored = []
        for mem in all_memories:
            age = current_time - mem["timestamp"]
            recency_score = 1.0 - (age / max(current_time, 1))
            importance_score = mem.get("importance", mem.get("decayed_importance", 0.1))

            contextual_boost = 0.0
            if contextual_boosters:
                for tag_key_val, boost_val in contextual_boosters.items():
                    if ":" in tag_key_val:
                        tag_cat, tag_val = tag_key_val.split(":", 1)
                        if mem.get(tag_cat) == tag_val:
                            contextual_boost = boost_val
                            break

            final_score = (recency_score * self.W_recency) + \
                          (importance_score * self.W_importance) + \
                          (contextual_boost * self.W_context)

            scored.append((mem, final_score))

        # Group by source
        import heapq
        source_groups: Dict[str, List] = {}
        for mem, score in scored:
            src = mem.get("source", "abstract")
            # Map reflection-sourced memories
            if mem.get("type") == "reflection" or "Consolidated Reflection" in mem.get("content", ""):
                src = "reflection"
            if src not in source_groups:
                source_groups[src] = []
            source_groups[src].append((mem["content"], score))

        # Sort each group by score descending
        for src in source_groups:
            source_groups[src].sort(key=lambda x: -x[1])

        # Allocate slots per source
        result = []
        remaining_slots = total_k

        for src, max_slots in allocation.items():
            available = source_groups.get(src, [])
            take = min(max_slots, len(available), remaining_slots)
            for content, score in available[:take]:
                result.append(content)
                remaining_slots -= 1
            if remaining_slots <= 0:
                break

        # Fill remaining slots with highest-scoring memories from any source
        if remaining_slots > 0:
            all_sorted = sorted(scored, key=lambda x: -x[1])
            for mem, score in all_sorted:
                if mem["content"] not in result and remaining_slots > 0:
                    result.append(mem["content"])
                    remaining_slots -= 1

        return result

    def forget(self, agent_id: str, strategy: str = "importance", threshold: Optional[float] = None) -> int:
        """Forget memories using specified strategy.

        Strategies:
        - 'importance': Remove memories below threshold
        - 'time': Remove oldest memories beyond capacity
        - 'emotion': Remove low-emotion memories

        Returns: Number of memories forgotten
        """
        # Use instance default if threshold not provided
        if threshold is None:
            threshold = self.forgetting_threshold

        if agent_id not in self.working:
            return 0

        original_count = len(self.working[agent_id]) + len(self.longterm.get(agent_id, []))
        
        if strategy == "importance":
            self.working[agent_id] = [m for m in self.working[agent_id] if m.get("importance", 0) >= threshold]
            self.longterm[agent_id] = [m for m in self.longterm.get(agent_id, []) if m.get("importance", 0) >= threshold]
        elif strategy == "time":
            # Keep only recent 50 in working, recent 20 high-importance in longterm
            self.working[agent_id] = self.working[agent_id][-50:]
            self.longterm[agent_id] = sorted(self.longterm.get(agent_id, []), 
                                              key=lambda x: x.get("importance", 0), reverse=True)[:20]
        
        new_count = len(self.working[agent_id]) + len(self.longterm.get(agent_id, []))
        return original_count - new_count
    
    def clear(self, agent_id: str):
        """Clear all memories for agent."""
        self.working[agent_id] = []
        self.longterm[agent_id] = []
