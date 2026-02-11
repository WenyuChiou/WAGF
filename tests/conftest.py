"""
Shared pytest fixtures for the governed broker framework test suite.

Provides reusable mocks for LLM, agents, skill registry, simulation engine,
and broker components — enabling test isolation without Ollama dependency.
"""
import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from cognitive_governance.agents import BaseAgent, AgentConfig, StateParam
from broker.interfaces.skill_types import (
    SkillProposal, ApprovedSkill, SkillBrokerResult,
    SkillOutcome, ExecutionResult, ValidationResult,
)
from broker.components.skill_registry import SkillRegistry
from broker.components.memory_engine import WindowMemoryEngine


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------

class MockLLM:
    """Deterministic mock LLM that returns configurable responses."""

    def __init__(self, responses: Optional[Dict[str, str]] = None):
        self.responses = responses or {
            "default": json.dumps({"decision": "do_nothing"})
        }
        self.call_count = 0
        self.last_prompt = None

    def __call__(self, prompt: str, **kwargs) -> str:
        self.call_count += 1
        self.last_prompt = prompt
        year = kwargs.get("year", 1)
        key = f"year_{year}"
        return self.responses.get(key, self.responses.get("default", ""))


@pytest.fixture
def mock_llm():
    """Create a deterministic mock LLM."""
    return MockLLM()


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def _make_agent(agent_id: str, agent_type: str = "household",
                state: Optional[Dict[str, float]] = None) -> BaseAgent:
    """Helper to create a minimal BaseAgent for testing."""
    config = AgentConfig(
        name=agent_id,
        agent_type=agent_type,
        state_params=[
            StateParam(name="savings", raw_range=(0, 100000), initial_raw=50000),
        ],
        objectives=[],
        constraints=[],
        skills=[],
    )
    agent = BaseAgent(config)
    # Inject additional state if provided
    if state:
        for k, v in state.items():
            agent.dynamic_state[k] = v
    return agent


@pytest.fixture
def basic_agent():
    """Single basic household agent."""
    return _make_agent("agent_001", "household")


@pytest.fixture
def agent_pair():
    """Two agents of different types for phase-ordering tests."""
    return {
        "agent_A": _make_agent("agent_A", "type_alpha"),
        "agent_B": _make_agent("agent_B", "type_beta"),
    }


@pytest.fixture
def ten_agents():
    """Ten household agents for batch tests."""
    return {f"agent_{i:03d}": _make_agent(f"agent_{i:03d}") for i in range(10)}


# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_skill_registry():
    """Skill registry with 2 minimal skills (do_nothing + take_action)."""
    reg = SkillRegistry()
    reg.register("do_nothing", {
        "skill_id": "do_nothing",
        "description": "Take no action",
        "eligible_agent_types": ["*"],
        "preconditions": [],
        "institutional_constraints": {},
        "allowed_state_changes": [],
        "implementation_mapping": "sim.noop",
    })
    reg.register("take_action", {
        "skill_id": "take_action",
        "description": "Take an action",
        "eligible_agent_types": ["*"],
        "preconditions": [],
        "institutional_constraints": {},
        "allowed_state_changes": ["savings"],
        "implementation_mapping": "sim.act",
    })
    return reg


# ---------------------------------------------------------------------------
# Mock Simulation Engine
# ---------------------------------------------------------------------------

class MockSimulationEngine:
    """Minimal simulation engine for testing."""

    def __init__(self):
        self.year = 0
        self.executed_skills: List[Dict[str, Any]] = []

    def advance_year(self) -> Dict[str, Any]:
        self.year += 1
        return {"current_year": self.year}

    def execute_skill(self, approved_skill) -> ExecutionResult:
        self.executed_skills.append({
            "skill": approved_skill.skill_name,
            "agent": approved_skill.agent_id,
            "year": self.year,
        })
        return ExecutionResult(success=True, state_changes={})


@pytest.fixture
def mock_sim_engine():
    """Create a mock simulation engine."""
    return MockSimulationEngine()


# ---------------------------------------------------------------------------
# Memory Engine
# ---------------------------------------------------------------------------

@pytest.fixture
def window_memory():
    """Window memory engine with small window for testing."""
    return WindowMemoryEngine(window_size=3)


# ---------------------------------------------------------------------------
# Temporary Output
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory that auto-cleans."""
    out = tmp_path / "test_output"
    out.mkdir()
    return out
