# Task-031C: Explainable Memory Retrieval (XAI-ABM Integration)

**Status**: ✅ COMPLETE
**Assigned**: Claude Code
**Completed**: 2026-01-23

---

## Summary

Implemented **transparent, explainable cognitive processes** for the v4.0 Symbolic Context Engine, following traditional ABM framework patterns and XAI best practices.

---

## Design Principles

| Principle | Description |
|-----------|-------------|
| **Modularity** | Component-level inspection capability |
| **Audit Hooks** | Immutable state records for decision tracking |
| **Provenance Tracking** | Maintain representation lineage through reasoning |
| **Human-Readable Traces** | Surface agent's reasoning progress (MemR³ pattern) |

---

## Sprint Plan

### Sprint 1: CognitiveTrace Dataclass (HIGH)

**Create**: `broker/components/cognitive_trace.py`

```python
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
        if self.retrieved_memories is None:
            self.retrieved_memories = []
        if self.retrieval_reasoning is None:
            self.retrieval_reasoning = []

    def to_dict(self) -> Dict:
        """JSON-serializable representation."""
        return asdict(self)

    def explain(self) -> str:
        """Generate human-readable explanation (NetLogo-style)."""
        lines = [
            f"=== Cognitive Trace: Agent {self.agent_id} @ Tick {self.tick} ===",
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
                f"  Expectation (EMA): {self.expectation:.2f}" if self.expectation else "  Expectation: N/A",
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
```

---

### Sprint 2: Enhanced SymbolicContextMonitor (HIGH)

**Modify**: `broker/components/symbolic_context.py`

Add tracing capabilities:

```python
class SymbolicContextMonitor:
    """Frequency-based surprise detection with full tracing."""

    def __init__(self, sensors: List[Sensor], arousal_threshold: float = 0.5):
        self.signature_engine = SignatureEngine(sensors)
        self.frequency_map: Dict[str, int] = {}
        self.total_events: int = 0
        self.arousal_threshold = arousal_threshold

        # NEW: Trace history for explainability
        self._trace_history: List[Dict] = []
        self._last_trace: Optional[Dict] = None

    def observe(self, world_state: Dict) -> Tuple[str, float]:
        """Returns (signature, surprise) with full trace capture."""

        # Step 1: Quantize sensors
        quantized = {}
        for sensor in self.signature_engine.sensors:
            value = self.signature_engine._extract_value(world_state, sensor.path)
            quantized[sensor.name] = sensor.quantize(value)

        # Step 2: Compute signature
        sig = self.signature_engine.compute_signature(world_state)

        # Step 3: Novelty-First check
        is_novel = sig not in self.frequency_map
        prior_count = self.frequency_map.get(sig, 0)
        prior_frequency = prior_count / self.total_events if self.total_events > 0 else None

        if is_novel:
            surprise = 1.0
            self.frequency_map[sig] = 1
        else:
            surprise = 1.0 - (prior_count / self.total_events)
            self.frequency_map[sig] += 1

        self.total_events += 1

        # NEW: Capture trace
        self._last_trace = {
            "quantized_sensors": quantized,
            "signature": sig,
            "is_novel": is_novel,
            "prior_frequency": prior_frequency,
            "surprise": surprise,
            "frequency_map_size": len(self.frequency_map),
            "total_events": self.total_events
        }
        self._trace_history.append(self._last_trace.copy())

        return sig, surprise

    def get_last_trace(self) -> Optional[Dict]:
        """Return the last observation trace for logging."""
        return self._last_trace

    def get_trace_history(self) -> List[Dict]:
        """Return full trace history for analysis."""
        return self._trace_history.copy()

    def explain_last(self) -> str:
        """Human-readable explanation of last observation."""
        if not self._last_trace:
            return "No observations yet."

        t = self._last_trace
        lines = [
            f"Sensors: {t['quantized_sensors']}",
            f"Signature: {t['signature'][:8]}...",
        ]

        if t['is_novel']:
            lines.append("NOVEL STATE → Surprise = 100%")
        else:
            lines.append(f"Seen {t['prior_frequency']:.1%} of the time → Surprise = {t['surprise']:.1%}")

        return " | ".join(lines)
```

---

### Sprint 3: retrieve_with_trace Method (HIGH)

**Modify**: `broker/components/universal_memory.py`

Add new method to UniversalCognitiveEngine:

```python
def retrieve_with_trace(
    self,
    agent: "Agent",
    top_k: int = 5,
    contextual_boosters: Optional[Dict[str, float]] = None,
    world_state: Optional[Dict] = None
) -> Tuple[List[Dict], "CognitiveTrace"]:
    """
    Retrieve memories with full cognitive trace.

    Returns:
        (memories, trace): Retrieved memories and the cognitive trace explaining WHY
    """
    from broker.components.cognitive_trace import CognitiveTrace
    from datetime import datetime

    # Stage 1: Compute surprise
    if self.mode == "symbolic":
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
        surprise = self.ema_predictor.surprise(reality)
        self.ema_predictor.update(reality)
        trace_kwargs = {
            "stimulus_key": self.stimulus_key,
            "reality": reality,
            "expectation": self.ema_predictor.predict(),
        }

    # Stage 2: Determine system
    system = "SYSTEM_2" if surprise > self.arousal_threshold else "SYSTEM_1"
    margin = abs(surprise - self.arousal_threshold)

    # Stage 3: Select ranking mode
    ranking_mode = "weighted" if system == "SYSTEM_2" else "legacy"
    self._base_engine.ranking_mode = ranking_mode

    # Stage 4: Retrieve with reasoning
    memories, reasoning = self._retrieve_with_reasoning(
        agent, top_k, contextual_boosters, ranking_mode
    )

    # Build trace
    trace = CognitiveTrace(
        agent_id=str(agent.unique_id),
        tick=getattr(agent, 'current_tick', 0),
        timestamp=datetime.now(),
        mode=self.mode,
        world_state=world_state or {},
        surprise=surprise,
        arousal_threshold=self.arousal_threshold,
        system=system,
        margin_to_switch=margin,
        ranking_mode=ranking_mode,
        retrieved_memories=memories,
        retrieval_reasoning=reasoning,
        **trace_kwargs
    )

    return memories, trace
```

---

### Sprint 4: Visualization Tools (MEDIUM)

**Create**: `broker/visualization/cognitive_plots.py`

```python
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Optional, List

def plot_cognitive_timeline(traces: List["CognitiveTrace"], save_path: Optional[str] = None):
    """Plot cognitive state over time."""

    df = pd.DataFrame([t.to_dict() for t in traces])

    fig, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)

    # Surprise over time
    ax1 = axes[0]
    ax1.plot(df['tick'], df['surprise'], 'b-', label='Surprise')
    ax1.axhline(y=df['arousal_threshold'].iloc[0], color='r', linestyle='--', label='Threshold')
    ax1.fill_between(df['tick'], df['surprise'], df['arousal_threshold'],
                     where=df['surprise'] > df['arousal_threshold'], alpha=0.3, color='red')
    ax1.set_ylabel('Surprise')
    ax1.legend()
    ax1.set_title(f'Cognitive Timeline: Agent {traces[0].agent_id}')

    # System state
    ax2 = axes[1]
    system_numeric = [1 if s == "SYSTEM_2" else 0 for s in df['system']]
    ax2.fill_between(df['tick'], system_numeric, step='post', alpha=0.5)
    ax2.set_ylabel('System')
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(['System 1\n(Routine)', 'System 2\n(Crisis)'])

    # Novelty markers
    ax3 = axes[2]
    novel_ticks = df[df['is_novel'] == True]['tick']
    ax3.scatter(novel_ticks, [1]*len(novel_ticks), marker='*', s=100, c='gold', label='Novel State')
    ax3.set_ylabel('Novel Events')
    ax3.set_xlabel('Tick')

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)

    return fig

def plot_signature_frequency(frequency_map: Dict[str, int], top_n: int = 10):
    """Visualize most common state signatures."""

    sorted_sigs = sorted(frequency_map.items(), key=lambda x: x[1], reverse=True)[:top_n]

    labels = [sig[:8] + "..." for sig, _ in sorted_sigs]
    counts = [count for _, count in sorted_sigs]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(labels, counts, color='steelblue')
    ax.set_xlabel('Frequency')
    ax.set_title('Most Common State Signatures')
    ax.invert_yaxis()

    return fig
```

---

### Sprint 5: Tests (MEDIUM)

**Create**: `tests/test_cognitive_trace.py`

```python
import pytest
from broker.components.cognitive_trace import CognitiveTrace
from broker.components.symbolic_context import Sensor, SymbolicContextMonitor
from datetime import datetime

class TestCognitiveTrace:

    def test_trace_creation(self):
        trace = CognitiveTrace(
            agent_id="test_agent",
            tick=1,
            timestamp=datetime.now(),
            mode="symbolic",
            world_state={"flood": 1.5},
            surprise=0.8,
            arousal_threshold=0.5,
            system="SYSTEM_2",
            margin_to_switch=0.3,
            ranking_mode="weighted"
        )
        assert trace.agent_id == "test_agent"
        assert trace.system == "SYSTEM_2"

    def test_trace_explain(self):
        trace = CognitiveTrace(
            agent_id="test_agent",
            tick=1,
            timestamp=datetime.now(),
            mode="symbolic",
            world_state={"flood": 1.5},
            quantized_sensors={"FLOOD": "FLOOD:SEVERE"},
            signature="abc12345",
            is_novel=True,
            surprise=1.0,
            arousal_threshold=0.5,
            system="SYSTEM_2",
            margin_to_switch=0.5,
            ranking_mode="weighted",
            retrieval_reasoning=["System 2: importance-weighted"]
        )

        explanation = trace.explain()
        assert "Agent test_agent" in explanation
        assert "SYSTEM_2" in explanation
        assert "Novel?: True" in explanation


class TestSymbolicContextMonitorTracing:

    def test_trace_history(self):
        sensors = [Sensor(path="flood", name="FLOOD", bins=[{"label":"LO","max":1},{"label":"HI","max":99}])]
        monitor = SymbolicContextMonitor(sensors)

        # Make several observations
        monitor.observe({"flood": 0.5})
        monitor.observe({"flood": 5.0})
        monitor.observe({"flood": 5.0})

        history = monitor.get_trace_history()
        assert len(history) == 3

        # First observation is novel
        assert history[0]["is_novel"] == True

        # Second observation is also novel (different bin)
        assert history[1]["is_novel"] == True

        # Third observation is NOT novel (same as second)
        assert history[2]["is_novel"] == False

    def test_explain_last(self):
        sensors = [Sensor(path="flood", name="FLOOD", bins=[{"label":"LO","max":1},{"label":"HI","max":99}])]
        monitor = SymbolicContextMonitor(sensors)

        monitor.observe({"flood": 5.0})
        explanation = monitor.explain_last()

        assert "NOVEL STATE" in explanation
        assert "Surprise = 100%" in explanation
```

---

## Files Summary

| File | Action | Priority |
|------|--------|----------|
| `broker/components/cognitive_trace.py` | **CREATE** | HIGH |
| `broker/components/symbolic_context.py` | MODIFY | HIGH |
| `broker/components/universal_memory.py` | MODIFY | HIGH |
| `broker/visualization/cognitive_plots.py` | **CREATE** | MEDIUM |
| `tests/test_cognitive_trace.py` | **CREATE** | MEDIUM |

---

## Verification Commands

```bash
# 1. Test cognitive trace
pytest tests/test_cognitive_trace.py -v

# 2. Quick integration check
python -c "
from broker.components.symbolic_context import Sensor, SymbolicContextMonitor

sensors = [Sensor(path='flood', name='FLOOD', bins=[{'label':'LO','max':1},{'label':'HI','max':99}])]
mon = SymbolicContextMonitor(sensors)

mon.observe({'flood': 0.5})
mon.observe({'flood': 5.0})
mon.observe({'flood': 5.0})

print('Trace History:')
for trace in mon.get_trace_history():
    print(f'  Sig: {trace[\"signature\"][:8]}, Novel: {trace[\"is_novel\"]}, Surprise: {trace[\"surprise\"]:.0%}')

print()
print('Last explanation:', mon.explain_last())
"

# 3. Ensure backwards compatibility
pytest tests/test_symbolic_context.py tests/test_universal_memory.py -v
```

---

## Reference

- Plan: `C:\Users\wenyu\.claude\plans\cozy-roaming-perlis.md` (Task-031C section)
- Literature: MemR³ (2024), Mesa ABM, NetLogo Logging
