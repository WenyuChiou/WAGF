"""
Universal Cognitive Engine (v3) - EMA-based System 1/2 Memory Architecture

This module implements the "Surprise Engine" pattern for human-like memory retrieval:
- System 1 (Routine): Low cognitive load, fast heuristic decisions
- System 2 (Crisis): High cognitive load, deliberate analytical thinking

The switching is governed by Prediction Error (Surprise) calculated via
Exponential Moving Average (EMA) of environmental stimuli.

Task-034: Added optional MemoryPersistence support for save/load across sessions.

References:
- Kahneman (2011): Thinking, Fast and Slow
- Friston (2010): Free Energy Principle / Predictive Processing
- Park et al. (2023): Generative Agents memory architecture
"""

from typing import Dict, Any, Optional, List, Tuple, TYPE_CHECKING
from datetime import datetime
import logging

if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.memory import MemoryPersistence

logger = logging.getLogger(__name__)

# Canonical EMAPredictor — single source of truth in strategies/ema.py
from cognitive_governance.memory.strategies.ema import EMAPredictor


class UniversalCognitiveEngine:
    """
    Universal Cognitive Engine (v3) - System 1/2 switching based on Surprise.

    This engine extends the HumanCentricMemoryEngine pattern with:
    1. EMA-based expectation tracking for environmental stimuli
    2. Dynamic System 1/2 mode switching based on prediction error
    3. "Boiling Frog" normalization - repeated exposure reduces surprise

    System 1 (Routine):
        - Low cognitive load
        - Uses recency-biased retrieval
        - Suitable for familiar, expected situations

    System 2 (Crisis):
        - High cognitive load
        - Uses importance-weighted retrieval
        - Activated when reality deviates significantly from expectations

    Args:
        stimulus_key: Environment key to track for surprise calculation (REQUIRED).
                      Examples: "environmental_indicator" (agent_type1), "economic_metric" (agent_type2),
                      "capability_gap" (agent_type3)
        arousal_threshold: Surprise level that triggers System 2.
                          Set to 99.0 to emulate v1 (always System 1)
                          Set to 0.0 to emulate v2 (always System 2)
        ema_alpha: EMA smoothing factor for expectation tracking
        **kwargs: Additional arguments passed to HumanCentricMemoryEngine
    """

    def __init__(
        self,
        stimulus_key: Optional[str] = None,
        sensory_cortex: Optional[List[Dict]] = None,
        arousal_threshold: float = 2.0,
        ema_alpha: float = 0.3,
        # HumanCentricMemoryEngine params
        window_size: int = 3,
        top_k_significant: int = 2,
        consolidation_prob: float = 0.7,
        consolidation_threshold: float = 0.6,
        decay_rate: float = 0.1,
        emotional_weights: Optional[Dict[str, float]] = None,
        source_weights: Optional[Dict[str, float]] = None,
        W_recency: float = 0.3,
        W_importance: float = 0.5,
        W_context: float = 0.2,
        ranking_mode: str = "weighted",
        seed: Optional[int] = None,
        # Task-034: Persistence support
        persistence: Optional["MemoryPersistence"] = None,
        auto_persist: bool = True,
    ):
        # Import here to avoid circular dependency
        from broker.components.memory_engine import HumanCentricMemoryEngine
        import warnings

        # Suppress the deprecation warning when we use it internally
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            self._base_engine = HumanCentricMemoryEngine(
                window_size=window_size,
                top_k_significant=top_k_significant,
                consolidation_prob=consolidation_prob,
                consolidation_threshold=consolidation_threshold,
                decay_rate=decay_rate,
                emotional_weights=emotional_weights,
                source_weights=source_weights,
                W_recency=W_recency,
                W_importance=W_importance,
                W_context=W_context,
                ranking_mode=ranking_mode,
                seed=seed
            )

        # Surprise engine params
        self.arousal_threshold = arousal_threshold
        self.mode = "scalar"
        self.context_monitor = None

        if sensory_cortex:
            try:
                from cognitive_governance.v1_prototype.memory.symbolic_core import (
                    Sensor, SymbolicContextMonitor,
                )
            except ImportError:
                raise ImportError(
                    "Symbolic sensory_cortex requires cognitive_governance.v1_prototype "
                    "(removed in v0.2). Use scalar mode (stimulus_key) instead."
                )
            sensors = [Sensor(**sensor_cfg) for sensor_cfg in sensory_cortex]
            self.context_monitor = SymbolicContextMonitor(sensors, arousal_threshold)
            self.mode = "symbolic"
            self.stimulus_key = None
            self.ema_predictor = None
        else:
            if not stimulus_key:
                stimulus_key = "flood_depth_m"
            self.stimulus_key = stimulus_key
            self.ema_predictor = EMAPredictor(alpha=ema_alpha, initial_value=0.0)

        # Current cognitive state
        self.current_system = "SYSTEM_1"
        self.last_surprise = 0.0

        # Store ranking mode for access
        self.ranking_mode = ranking_mode

        # Task-034: Persistence support
        self._persistence = persistence
        self._auto_persist = auto_persist

    @property
    def working(self) -> Dict[str, List[Dict[str, Any]]]:
        """Access base engine's working memory."""
        return self._base_engine.working

    @property
    def longterm(self) -> Dict[str, List[Dict[str, Any]]]:
        """Access base engine's long-term memory."""
        return self._base_engine.longterm

    def add_memory(self, agent_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add memory via base engine."""
        self._base_engine.add_memory(agent_id, content, metadata)

    def add_memory_for_agent(self, agent, content: str, metadata: Optional[Dict[str, Any]] = None):
        """Add memory with agent context via base engine."""
        self._base_engine.add_memory_for_agent(agent, content, metadata)

    def clear(self, agent_id: str):
        """Clear memory via base engine."""
        self._base_engine.clear(agent_id)

    def forget(self, agent_id: str, strategy: str = "importance", threshold: float = 0.2) -> int:
        """Forget memories via base engine."""
        return self._base_engine.forget(agent_id, strategy, threshold)

    def _compute_surprise(self, world_state: Optional[Dict[str, Any]] = None) -> float:
        """
        Compute surprise based on environmental stimulus.

        Args:
            world_state: Current environment state dict

        Returns:
            Surprise value (prediction error)
        """
        if world_state is None:
            return 0.0

        # Extract the stimulus value
        reality = float(world_state.get(self.stimulus_key, 0.0))

        if self.mode == "symbolic" and self.context_monitor:
            _, surprise = self.context_monitor.observe(world_state)
            return surprise

        # Calculate surprise before updating expectation
        surprise = self.ema_predictor.surprise(reality)

        # Update expectation for next time
        self.ema_predictor.update(reality)

        return surprise

    def _determine_system(self, surprise: float) -> str:
        """
        Determine which cognitive system to activate.

        Args:
            surprise: Computed prediction error

        Returns:
            "SYSTEM_1" or "SYSTEM_2"
        """
        if surprise > self.arousal_threshold:
            return "SYSTEM_2"
        return "SYSTEM_1"

    def retrieve(
        self,
        agent,
        query: Optional[str] = None,
        top_k: int = 5,
        contextual_boosters: Optional[Dict[str, float]] = None,
        world_state: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[str]:
        """
        Retrieve memories with System 1/2 mode switching.

        The cognitive system is determined by surprise level:
        - Low surprise → System 1 (recency-focused, fast retrieval)
        - High surprise → System 2 (importance-weighted, deliberate retrieval)

        Args:
            agent: The agent requesting memories
            query: Optional semantic query
            top_k: Number of memories to retrieve
            contextual_boosters: Context-aware tag boosters
            world_state: Current environment state for surprise calculation
            **kwargs: Additional arguments

        Returns:
            List of memory content strings
        """
        # Step 1: Compute surprise from environment
        self.last_surprise = self._compute_surprise(world_state)

        # Step 2: Determine cognitive system
        self.current_system = self._determine_system(self.last_surprise)

        # Step 3: Adjust retrieval strategy based on system
        original_mode = self._base_engine.ranking_mode

        if self.current_system == "SYSTEM_1":
            # System 1: Use legacy mode (recency-biased, faster)
            self._base_engine.ranking_mode = "legacy"
            logger.debug(f"[Cognitive] System 1 activated (surprise={self.last_surprise:.2f})")
        else:
            # System 2: Use weighted mode (importance-based, deliberate)
            self._base_engine.ranking_mode = "weighted"
            logger.debug(f"[Cognitive] System 2 activated (surprise={self.last_surprise:.2f})")

        # Step 4: Delegate to base engine
        result = self._base_engine.retrieve(
            agent=agent,
            query=query,
            top_k=top_k,
            contextual_boosters=contextual_boosters,
            **kwargs
        )

        # Step 5: Restore original mode
        self._base_engine.ranking_mode = original_mode
        self.ranking_mode = original_mode

        return result

    def retrieve_stratified(
        self,
        agent_id: str,
        allocation: Optional[Dict[str, int]] = None,
        total_k: int = 10,
        contextual_boosters: Optional[Dict[str, float]] = None,
        world_state: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Retrieve memories with source-stratified diversity and System 1/2 switching.

        Delegates to HumanCentricMemoryEngine.retrieve_stratified() with
        System 1/2 allocation adjustment.
        """
        # Step 1: Compute surprise from environment
        self.last_surprise = self._compute_surprise(world_state)

        # Step 2: Determine cognitive system
        self.current_system = self._determine_system(self.last_surprise)

        # Step 3: Adjust allocation based on cognitive system
        if allocation is None:
            if self.current_system == "SYSTEM_1":
                allocation = {
                    "personal": 5,
                    "neighbor": 2,
                    "community": 1,
                    "reflection": 1,
                    "abstract": 1,
                }
            else:
                allocation = {
                    "personal": 3,
                    "neighbor": 2,
                    "community": 2,
                    "reflection": 2,
                    "abstract": 1,
                }

        logger.debug(
            "[Cognitive] retrieve_stratified: %s (surprise=%.2f), allocation=%s",
            self.current_system,
            self.last_surprise,
            allocation,
        )

        # Step 4: Delegate to base engine
        return self._base_engine.retrieve_stratified(
            agent_id=agent_id,
            allocation=allocation,
            total_k=total_k,
            contextual_boosters=contextual_boosters,
        )

    def get_cognitive_state(self) -> Dict[str, Any]:
        """
        Get current cognitive state for debugging/logging.

        Returns:
            Dict with system state, surprise level, and expectation
        """
        expectation = None
        if self.ema_predictor:
            expectation = self.ema_predictor.predict()
        return {
            "system": self.current_system,
            "surprise": self.last_surprise,
            "expectation": expectation,
            "arousal_threshold": self.arousal_threshold
        }

    def retrieve_with_trace(
        self,
        agent,
        query: Optional[str] = None,
        top_k: int = 5,
        contextual_boosters: Optional[Dict[str, float]] = None,
        world_state: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Tuple[List[str], "CognitiveTrace"]:
        """
        Retrieve memories with full cognitive trace for XAI-ABM integration.

        This is the explainable version of retrieve() that returns both
        memories and a CognitiveTrace explaining the decision process.

        Args:
            agent: The agent requesting memories
            query: Optional semantic query
            top_k: Number of memories to retrieve
            contextual_boosters: Context-aware tag boosters
            world_state: Current environment state for surprise calculation
            **kwargs: Additional arguments

        Returns:
            Tuple of (memory_contents, CognitiveTrace)
        """
        from broker.components.cognitive_trace import CognitiveTrace

        # Stage 1: Compute surprise and capture trace data
        trace_kwargs = {}
        if self.mode == "symbolic" and self.context_monitor:
            sig, surprise = self.context_monitor.observe(world_state or {})
            sensor_trace = self.context_monitor.get_last_trace()
            trace_kwargs = {
                "quantized_sensors": sensor_trace.get("quantized_sensors"),
                "signature": sensor_trace.get("signature"),
                "is_novel": sensor_trace.get("is_novel"),
                "prior_frequency": sensor_trace.get("prior_frequency"),
            }
        else:
            reality = float((world_state or {}).get(self.stimulus_key, 0.0))
            surprise = self.ema_predictor.surprise(reality) if self.ema_predictor else 0.0
            trace_kwargs = {
                "stimulus_key": self.stimulus_key,
                "reality": reality,
                "expectation": self.ema_predictor.predict() if self.ema_predictor else None,
            }
            # Update EMA after capturing trace
            if self.ema_predictor:
                self.ema_predictor.update(reality)

        self.last_surprise = surprise

        # Stage 2: Determine system
        system = "SYSTEM_2" if surprise > self.arousal_threshold else "SYSTEM_1"
        margin = abs(surprise - self.arousal_threshold)
        self.current_system = system

        # Stage 3: Select ranking mode
        original_mode = self._base_engine.ranking_mode
        ranking_mode = "weighted" if system == "SYSTEM_2" else "legacy"
        self._base_engine.ranking_mode = ranking_mode

        # Stage 4: Retrieve memories with reasoning trail
        memories, reasoning = self._retrieve_with_reasoning(
            agent, top_k, contextual_boosters, ranking_mode
        )

        # Restore original mode
        self._base_engine.ranking_mode = original_mode

        # Stage 5: Build trace
        trace = CognitiveTrace(
            agent_id=str(getattr(agent, 'unique_id', 'unknown')),
            tick=getattr(agent, 'current_tick', 0),
            timestamp=datetime.now(),
            mode=self.mode,
            world_state=world_state or {},
            surprise=surprise,
            arousal_threshold=self.arousal_threshold,
            system=system,
            margin_to_switch=margin,
            ranking_mode=ranking_mode,
            retrieved_memories=[{"content": m} for m in memories],
            retrieval_reasoning=reasoning,
            **trace_kwargs
        )

        return memories, trace

    def _retrieve_with_reasoning(
        self,
        agent,
        top_k: int,
        contextual_boosters: Optional[Dict[str, float]],
        ranking_mode: str
    ) -> Tuple[List[str], List[str]]:
        """
        Internal: retrieve memories and generate human-readable reasoning.

        Args:
            agent: The agent requesting memories
            top_k: Number of memories to retrieve
            contextual_boosters: Context-aware tag boosters
            ranking_mode: "legacy" or "weighted"

        Returns:
            Tuple of (memory_contents, reasoning_trail)
        """
        import time
        reasoning = []
        agent_id = str(getattr(agent, 'unique_id', 'unknown'))

        # Get memory stores
        working = self._base_engine.working.get(agent_id, [])
        longterm = self._base_engine.longterm.get(agent_id, [])

        if ranking_mode == "legacy":
            # System 1: Recency-based (fast, automatic)
            reasoning.append("System 1 (Routine): Using recency-based retrieval")

            window_size = self._base_engine.window_size
            top_k_significant = self._base_engine.top_k_significant

            recent = working[-window_size:]
            reasoning.append(f"  -> Selected {len(recent)} most recent working memories")

            # Top-k significant from long-term
            sorted_lt = sorted(longterm, key=lambda m: m.get('importance', 0), reverse=True)
            significant = sorted_lt[:top_k_significant]
            reasoning.append(f"  -> Selected top {len(significant)} significant long-term memories")

            all_memories = significant + recent
            memories = [m.get('content', '') for m in all_memories[:top_k]]

        else:
            # System 2: Weighted (deliberate, importance-focused)
            reasoning.append("System 2 (Crisis): Using importance-weighted retrieval")

            all_memories = working + longterm
            current_time = time.time()

            scored = []
            for m in all_memories:
                # Calculate recency score (same as HumanCentricMemoryEngine)
                created_at = m.get('created_at', current_time)
                age = current_time - created_at
                recency_score = 1.0 - (age / max(current_time, 1))
                recency_score = max(0.0, min(1.0, recency_score))  # Clamp to [0, 1]

                importance_score = m.get('importance', 0.5)
                boost = self._compute_contextual_boost(m, contextual_boosters)

                W_r = self._base_engine.W_recency
                W_i = self._base_engine.W_importance
                W_c = self._base_engine.W_context

                final = (recency_score * W_r) + (importance_score * W_i) + (boost * W_c)
                scored.append((m, final, {
                    'recency': recency_score,
                    'importance': importance_score,
                    'boost': boost
                }))

            scored.sort(key=lambda x: x[1], reverse=True)

            for i, (m, score, breakdown) in enumerate(scored[:top_k]):
                content = m.get('content', '')
                content_preview = content[:50] + "..." if len(content) > 50 else content
                reasoning.append(
                    f"  #{i+1} [{score:.2f}] \"{content_preview}\" "
                    f"(R={breakdown['recency']:.2f}, I={breakdown['importance']:.2f}, B={breakdown['boost']:.2f})"
                )

            memories = [m.get('content', '') for m, _, _ in scored[:top_k]]

        return memories, reasoning

    def _compute_contextual_boost(
        self,
        memory: Dict[str, Any],
        contextual_boosters: Optional[Dict[str, float]]
    ) -> float:
        """Compute contextual boost for a memory based on tag matching."""
        if not contextual_boosters:
            return 0.0

        tags = memory.get('tags', [])
        boost = 0.0
        for tag in tags:
            if tag in contextual_boosters:
                boost += contextual_boosters[tag]
        return min(boost, 1.0)  # Cap at 1.0

    # =========================================================================
    # Task-034: Persistence Support
    # =========================================================================

    @property
    def persistence(self) -> Optional["MemoryPersistence"]:
        """Get the configured persistence backend."""
        return self._persistence

    @persistence.setter
    def persistence(self, value: Optional["MemoryPersistence"]):
        """Set a persistence backend for save/load."""
        self._persistence = value

    def save_agent_memories(self, agent_id: str) -> bool:
        """
        Save all memories for an agent to the persistence backend.

        Args:
            agent_id: The agent's unique identifier

        Returns:
            True if saved successfully, False if no persistence configured
        """
        if not self._persistence:
            logger.debug(f"No persistence configured, skipping save for {agent_id}")
            return False

        # Collect all memories for this agent
        working = self._base_engine.working.get(agent_id, [])
        longterm = self._base_engine.longterm.get(agent_id, [])

        all_memories = [
            {**m, "store": "working"} for m in working
        ] + [
            {**m, "store": "longterm"} for m in longterm
        ]

        self._persistence.save(agent_id, all_memories)
        logger.info(f"Saved {len(all_memories)} memories for agent {agent_id}")
        return True

    def load_agent_memories(self, agent_id: str) -> int:
        """
        Load memories for an agent from the persistence backend.

        Args:
            agent_id: The agent's unique identifier

        Returns:
            Number of memories loaded
        """
        if not self._persistence:
            logger.debug(f"No persistence configured, skipping load for {agent_id}")
            return 0

        memories = self._persistence.load(agent_id)
        if not memories:
            return 0

        # Clear existing memories
        self._base_engine.clear(agent_id)

        # Restore to appropriate stores
        for m in memories:
            store = m.pop("store", "working")
            if store == "longterm":
                if agent_id not in self._base_engine.longterm:
                    self._base_engine.longterm[agent_id] = []
                self._base_engine.longterm[agent_id].append(m)
            else:
                if agent_id not in self._base_engine.working:
                    self._base_engine.working[agent_id] = []
                self._base_engine.working[agent_id].append(m)

        logger.info(f"Loaded {len(memories)} memories for agent {agent_id}")
        return len(memories)

    def save_all_memories(self) -> Dict[str, int]:
        """
        Save all agent memories to the persistence backend.

        Returns:
            Dict mapping agent_id to number of memories saved
        """
        if not self._persistence:
            return {}

        result = {}
        all_agents = set(self._base_engine.working.keys()) | set(self._base_engine.longterm.keys())

        for agent_id in all_agents:
            working = self._base_engine.working.get(agent_id, [])
            longterm = self._base_engine.longterm.get(agent_id, [])
            count = len(working) + len(longterm)
            self.save_agent_memories(agent_id)
            result[agent_id] = count

        return result

    def load_all_memories(self) -> Dict[str, int]:
        """
        Load all agent memories from the persistence backend.

        Note: This requires the persistence backend to support list_agents().

        Returns:
            Dict mapping agent_id to number of memories loaded
        """
        if not self._persistence:
            return {}

        result = {}

        # Check if persistence has list_agents method
        if hasattr(self._persistence, "list_agents"):
            agents = self._persistence.list_agents()
            for agent_id in agents:
                count = self.load_agent_memories(agent_id)
                result[agent_id] = count

        return result

    def add_memory_with_persist(
        self,
        agent_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add memory and optionally persist immediately.

        This is an alternative to add_memory that respects auto_persist setting.

        Args:
            agent_id: The agent's unique identifier
            content: Memory content string
            metadata: Optional metadata dict
        """
        self._base_engine.add_memory(agent_id, content, metadata)

        if self._auto_persist and self._persistence:
            # Append just this memory to persistence
            memory_dict = {
                "content": content,
                "created_at": datetime.now().isoformat(),
                "store": "working",
                **(metadata or {})
            }
            self._persistence.append(agent_id, memory_dict)
