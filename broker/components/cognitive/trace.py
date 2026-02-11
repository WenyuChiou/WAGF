"""
Dataclass definition for CognitiveTrace.

This dataclass represents an immutable audit record of a single cognitive observation
or step within an agent's decision-making process. It captures details from
surprise calculation, system determination, mode selection, and memory retrieval.
"""
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime

@dataclass
class CognitiveTrace:
    """Immutable audit record of a single cognitive observation."""

    # Identification
    agent_id: str
    tick: int
    timestamp: datetime

    # Stage 1: Surprise Calculation
    mode: str  # "symbolic" | "scalar"
    world_state: Dict[str, Any]

    # Symbolic Mode Details
    quantized_sensors: Optional[Dict[str, str]] = None
    signature: Optional[str] = None
    is_novel: Optional[bool] = None
    prior_frequency: Optional[float] = None

    # Scalar Mode Details (legacy)
    stimulus_key: Optional[str] = None
    reality: Optional[float] = None
    expectation: Optional[float] = None

    # Common Output
    surprise: float = 0.0
    arousal_threshold: float = 0.5

    # Stage 2: System Determination
    system: str = "SYSTEM_1"
    margin_to_switch: float = 0.0

    # Stage 3: Mode Selection
    ranking_mode: str = "legacy"

    # Stage 4: Memory Retrieval
    retrieved_memories: List[Dict] = None
    retrieval_reasoning: List[str] = None

    def __post_init__(self):
        # Ensure lists are initialized if None is passed during construction
        if self.retrieved_memories is None:
            self.retrieved_memories = []
        if self.retrieval_reasoning is None:
            self.retrieval_reasoning = []

    def to_dict(self) -> Dict:
        """JSON-serializable representation."""
        # Convert datetime to string for JSON serialization
        trace_dict = asdict(self)
        trace_dict['timestamp'] = self.timestamp.isoformat()
        return trace_dict

    def explain(self) -> str:
        """Generate human-readable explanation (NetLogo-style)."""
        lines = [
            f"=== Cognitive Trace: Agent {self.agent_id} @ Tick {self.tick} ====",
            "",
            "[PERCEPTION]",
        ]

        if self.mode == "symbolic":
            lines.extend([
                f"  Sensors: {self.quantized_sensors}",
                f"  Signature: {self.signature[:8]}..." if self.signature else "  Signature: N/A",
                f"  Novel?: {self.is_novel}",
            ])
            if self.prior_frequency is not None:
                lines.append(f"  Prior Frequency: {self.prior_frequency:.1%}")
            else:
                lines.append("  Prior Frequency: N/A (first time)")
        else:
            lines.extend([
                f"  Stimulus: {self.stimulus_key} = {self.reality}",
                f"  Expectation (EMA): {self.expectation:.2f}" if self.expectation is not None else "  Expectation: N/A",
            ])

        edge_warning = " (close to edge!)" if self.margin_to_switch < 0.5 else ""
        lines.extend([
            "",
            "[AROUSAL]",
            f"  Surprise: {self.surprise:.2f}",
            f"  Threshold: {self.arousal_threshold}",
            f"  System: {self.system}",
            f"  Margin: {self.margin_to_switch:.2f}{edge_warning}",
            "",
            "[RETRIEVAL]",
            f"  Mode: {self.ranking_mode}",
            f"  Memories Retrieved: {len(self.retrieved_memories)}",
        ])

        for i, reason in enumerate(self.retrieval_reasoning, 1):
            lines.append(f"    {i}. {reason}")

        return "\n".join(lines)

    def summary(self) -> str:
        """One-line summary for compact logging."""
        system_icon = "S2" if self.system == "SYSTEM_2" else "S1"
        novel_icon = "NEW" if self.is_novel else "---"
        return (
            f"[{self.agent_id}@{self.tick}] {system_icon} | "
            f"Surprise={self.surprise:.0%} | {novel_icon} | "
            f"Memories={len(self.retrieved_memories)}"
        )