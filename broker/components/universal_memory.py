"""
Universal Cognitive Engine (v3) - EMA-based System 1/2 Memory Architecture

This module implements the "Surprise Engine" pattern for human-like memory retrieval:
- System 1 (Routine): Low cognitive load, fast heuristic decisions
- System 2 (Crisis): High cognitive load, deliberate analytical thinking

The switching is governed by Prediction Error (Surprise) calculated via
Exponential Moving Average (EMA) of environmental stimuli.

References:
- Kahneman (2011): Thinking, Fast and Slow
- Friston (2010): Free Energy Principle / Predictive Processing
- Park et al. (2023): Generative Agents memory architecture
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


class EMAPredictor:
    """
    Exponential Moving Average predictor for environmental state tracking.

    Formula: E_t = (alpha * R_t) + ((1 - alpha) * E_{t-1})

    Where:
    - E_t = Current expectation
    - R_t = Current reality (observed value)
    - alpha = Smoothing factor (higher = faster adaptation)

    Args:
        alpha: Smoothing factor [0-1]. Higher values = faster adaptation to new data.
               0.1 = High inertia (slow adaptation)
               0.5 = Balanced
               0.9 = Fast adaptation (almost immediate)
        initial_value: Starting expectation value
    """

    def __init__(self, alpha: float = 0.3, initial_value: float = 0.0):
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self.alpha = alpha
        self.expectation = initial_value
        self._initialized = False

    def update(self, reality: float) -> float:
        """
        Update expectation based on observed reality.

        Args:
            reality: The observed value from the environment

        Returns:
            The updated expectation value
        """
        if not self._initialized:
            # First observation: set expectation directly
            self.expectation = reality * self.alpha
            self._initialized = True
        else:
            # Standard EMA update
            self.expectation = (self.alpha * reality) + ((1 - self.alpha) * self.expectation)
        return self.expectation

    def predict(self) -> float:
        """Return current expectation (prediction for next observation)."""
        return self.expectation

    def surprise(self, reality: float) -> float:
        """
        Calculate surprise (prediction error) given an observation.

        Surprise = |Reality - Expectation|

        Args:
            reality: The observed value

        Returns:
            Absolute prediction error (non-negative)
        """
        return abs(reality - self.expectation)


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
        stimulus_key: str,  # REQUIRED - no default value to ensure explicit configuration
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
        seed: Optional[int] = None
    ):
        # Validate required parameters
        if not stimulus_key:
            raise ValueError(
                "stimulus_key is required for UniversalCognitiveEngine. "
                "Examples: 'environmental_indicator' (agent_type1), 'economic_metric' (agent_type2), "
                "'capability_gap' (agent_type3)"
            )

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
        self.stimulus_key = stimulus_key
        self.ema_predictor = EMAPredictor(alpha=ema_alpha, initial_value=0.0)

        # Current cognitive state
        self.current_system = "SYSTEM_1"
        self.last_surprise = 0.0

        # Store ranking mode for access
        self.ranking_mode = ranking_mode

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

    def get_cognitive_state(self) -> Dict[str, Any]:
        """
        Get current cognitive state for debugging/logging.

        Returns:
            Dict with system state, surprise level, and expectation
        """
        return {
            "system": self.current_system,
            "surprise": self.last_surprise,
            "expectation": self.ema_predictor.predict(),
            "arousal_threshold": self.arousal_threshold
        }
