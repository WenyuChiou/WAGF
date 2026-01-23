"""
Tests for CognitiveTrace and XAI-ABM integration (Task-031C).
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from broker.components.cognitive_trace import CognitiveTrace
from broker.components.symbolic_context import Sensor, SymbolicContextMonitor
from broker.components.universal_memory import UniversalCognitiveEngine


class TestCognitiveTrace:

    def test_trace_creation_symbolic(self):
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
            ranking_mode="weighted"
        )
        assert trace.agent_id == "test_agent"
        assert trace.mode == "symbolic"
        assert trace.system == "SYSTEM_2"

    def test_trace_to_dict(self):
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
        d = trace.to_dict()
        assert isinstance(d, dict)
        assert d["agent_id"] == "test_agent"
        assert isinstance(d["timestamp"], str)

    def test_trace_explain(self):
        trace = CognitiveTrace(
            agent_id="test_agent",
            tick=1,
            timestamp=datetime.now(),
            mode="symbolic",
            world_state={"flood": 1.5},
            quantized_sensors={"FLOOD": "FLOOD:SEVERE"},
            signature="abc12345efgh",
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

    def test_trace_summary(self):
        trace = CognitiveTrace(
            agent_id="agent_001",
            tick=5,
            timestamp=datetime.now(),
            mode="symbolic",
            world_state={"flood": 1.5},
            is_novel=True,
            surprise=1.0,
            arousal_threshold=0.5,
            system="SYSTEM_2",
            margin_to_switch=0.5,
            ranking_mode="weighted",
            retrieved_memories=[{"content": "test"}]
        )
        summary = trace.summary()
        assert "agent_001@5" in summary
        assert "S2" in summary


class TestSymbolicContextMonitorTracing:

    def test_trace_history(self):
        sensors = [Sensor(path="flood", name="FLOOD", bins=[{"label":"LO","max":1},{"label":"HI","max":99}])]
        monitor = SymbolicContextMonitor(sensors)

        monitor.observe({"flood": 0.5})
        monitor.observe({"flood": 5.0})
        monitor.observe({"flood": 5.0})

        history = monitor.get_trace_history()
        assert len(history) == 3
        assert history[0]["is_novel"] == True
        assert history[1]["is_novel"] == True
        assert history[2]["is_novel"] == False

    def test_explain_last(self):
        sensors = [Sensor(path="flood", name="FLOOD", bins=[{"label":"LO","max":1},{"label":"HI","max":99}])]
        monitor = SymbolicContextMonitor(sensors)

        monitor.observe({"flood": 5.0})
        explanation = monitor.explain_last()

        assert "NOVEL STATE" in explanation
        assert "100%" in explanation


class TestRetrieveWithTrace:

    def test_retrieve_with_trace_symbolic(self):
        engine = UniversalCognitiveEngine(
            sensory_cortex=[
                {"path": "flood", "name": "FLOOD", "bins": [{"label": "NONE", "max": 0}, {"label": "SEVERE", "max": 99}]}
            ],
            arousal_threshold=0.5
        )

        class MockAgent:
            unique_id = "test_agent"
            current_tick = 1
            memory = {"working": [], "longterm": []}

        agent = MockAgent()
        engine.add_memory("test_agent", "Flood memory", {"importance": 0.8})

        memories, trace = engine.retrieve_with_trace(agent, world_state={"flood": 2.5})

        assert isinstance(trace, CognitiveTrace)
        assert trace.mode == "symbolic"
        assert trace.is_novel == True
        assert trace.system == "SYSTEM_2"

    def test_trace_contains_reasoning(self):
        engine = UniversalCognitiveEngine(
            sensory_cortex=[
                {"path": "flood", "name": "FLOOD", "bins": [{"label": "NONE", "max": 0}, {"label": "SEVERE", "max": 99}]}
            ],
            arousal_threshold=0.5
        )

        class MockAgent:
            unique_id = "test_agent"
            current_tick = 1
            memory = {"working": [], "longterm": []}

        agent = MockAgent()
        engine.add_memory("test_agent", "Important flood memory", {"importance": 0.9})

        memories, trace = engine.retrieve_with_trace(agent, world_state={"flood": 2.5})

        assert len(trace.retrieval_reasoning) > 0
        assert "System 2" in trace.retrieval_reasoning[0]
