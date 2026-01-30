# Task-056: Communication Layer ↔ Memory Integration (Gemini Assignment)

> **Assigned To:** Gemini
> **Status:** COMPLETED
> **Priority:** Medium
> **Scope:** ~150 lines new code + ~30 lines edits, 2 new files + 1 edit

---

## Objective

The Communication Layer (Task-054) built 6 modules: `coordinator.py`, `conflict_resolver.py`, `phase_orchestrator.py`, `message_pool.py`, `message_provider.py`, `coordination.py`. **None of them integrate with `MemoryEngine`.**

This means:
- GameMaster resolves actions and generates Event Statements → **not stored in agent memory**
- MessagePool delivers messages between agents → **not stored in agent memory**
- Agents cannot reflect on past interactions, policies, or conflict outcomes

**Fix:** Create a `MemoryBridge` that wires Communication Layer outputs into the existing `MemoryEngine.add_memory()` API, and integrate it into the lifecycle hooks.

---

## Architecture Context

### Memory Engine API (existing, DO NOT modify)

```python
# broker/components/memory_engine.py
class MemoryEngine(ABC):
    def add_memory(self, agent_id: str, content: str,
                   metadata: Optional[Dict[str, Any]] = None): ...
```

**Metadata convention** (used throughout codebase):
```python
metadata = {
    "source": "personal" | "neighbor" | "community" | "abstract" | "social",
    "emotion": "critical" | "major" | "positive" | "shift" | "observation" | "routine",
    "importance": float,  # 0.0 - 1.0
    "type": str,          # "reasoning" | "event" | "reflection" | custom
}
```

### Communication Layer API (existing, DO NOT modify)

```python
# GameMaster.resolve_phase() returns:
List[ActionResolution]
  - .agent_id: str
  - .approved: bool
  - .event_statement: str    # ← THIS goes into memory
  - .denial_reason: str      # ← THIS goes into memory (if denied)
  - .original_proposal.skill_name: str

# MessagePool.get_unread() returns:
List[AgentMessage]
  - .sender_type: str
  - .message_type: str       # "policy_announcement" | "neighbor_warning" | etc.
  - .content: str            # ← THIS goes into memory
  - .priority: int
  - .data: Dict[str, Any]
```

### Lifecycle Hooks (existing)

```python
# examples/multi_agent/orchestration/lifecycle_hooks.py
class MultiAgentHooks:
    def pre_year(self, year, env, agents): ...
    def post_step(self, agent, result): ...
    def post_year(self, year, agents, memory_engine): ...
```

Current `post_step()` already stores decision memories:
```python
memory_engine.add_memory(agent_id, f"I decided to {decision} because {reason}",
                         metadata={"source": "social", "type": "reasoning"})
```

Current `post_year()` already stores event memories:
```python
memory_engine.add_memory(agent.id, f"Year {year}: We experienced {description}...",
                         metadata={"emotion": "fear", "source": "personal", "importance": 0.8})
```

---

## Changes Required

### File 1 (NEW): `broker/components/memory_bridge.py` (~100 lines)

Bridge between Communication Layer outputs and MemoryEngine.

```python
"""
Memory Bridge — Wires Communication Layer outputs into MemoryEngine.

Converts ActionResolution event statements and AgentMessage content
into properly tagged memories for agent retrieval and reflection.
"""
from typing import List, Dict, Any, Optional
from broker.components.memory_engine import MemoryEngine
from broker.interfaces.coordination import ActionResolution, AgentMessage
from broker.utils.logging import logger


# Source mapping: message_type → memory source tag
MESSAGE_SOURCE_MAP = {
    "policy_announcement": "community",
    "market_update": "community",
    "neighbor_warning": "neighbor",
    "neighbor_info": "neighbor",
    "media_broadcast": "community",
    "resolution": "abstract",       # GM resolution
    "direct": "neighbor",
}

# Emotion mapping: message_type → memory emotion tag
MESSAGE_EMOTION_MAP = {
    "policy_announcement": "major",
    "market_update": "observation",
    "neighbor_warning": "critical",
    "neighbor_info": "observation",
    "media_broadcast": "major",
    "resolution": "major",
    "direct": "observation",
}

# Importance mapping: message_type → base importance
MESSAGE_IMPORTANCE_MAP = {
    "policy_announcement": 0.7,
    "market_update": 0.5,
    "neighbor_warning": 0.8,
    "neighbor_info": 0.4,
    "media_broadcast": 0.6,
    "resolution": 0.75,
    "direct": 0.5,
}


class MemoryBridge:
    """Converts Communication Layer outputs into agent memories."""

    def __init__(self, memory_engine: MemoryEngine):
        self.memory_engine = memory_engine

    def store_resolution(self, resolution: ActionResolution, year: int = 0) -> None:
        """Store a GameMaster resolution as agent memory.

        Args:
            resolution: The ActionResolution from GameMaster.resolve_phase()
            year: Current simulation year (for memory prefix)
        """
        if not resolution.event_statement:
            return

        prefix = f"Year {year}: " if year > 0 else ""

        if resolution.approved:
            content = f"{prefix}{resolution.event_statement}"
            emotion = "positive"
            importance = 0.6
        else:
            content = f"{prefix}My request to {resolution.original_proposal.skill_name} was denied. {resolution.denial_reason}"
            emotion = "shift"
            importance = 0.75  # Denials are more memorable

        self.memory_engine.add_memory(
            resolution.agent_id,
            content,
            metadata={
                "source": "abstract",        # Institutional decision
                "emotion": emotion,
                "importance": importance,
                "type": "resolution",
                "skill_name": resolution.original_proposal.skill_name,
                "approved": resolution.approved,
            }
        )
        logger.debug(f" [MemoryBridge] Stored resolution for {resolution.agent_id}: approved={resolution.approved}")

    def store_resolutions(self, resolutions: List[ActionResolution], year: int = 0) -> int:
        """Store multiple resolutions. Returns count stored."""
        count = 0
        for r in resolutions:
            if r.event_statement or not r.approved:
                self.store_resolution(r, year)
                count += 1
        return count

    def store_message(self, agent_id: str, message: AgentMessage, year: int = 0) -> None:
        """Store a received message as agent memory.

        Args:
            agent_id: The receiving agent
            message: The AgentMessage received
            year: Current simulation year
        """
        prefix = f"Year {year}: " if year > 0 else ""
        source = MESSAGE_SOURCE_MAP.get(message.message_type, "abstract")
        emotion = MESSAGE_EMOTION_MAP.get(message.message_type, "observation")
        importance = MESSAGE_IMPORTANCE_MAP.get(message.message_type, 0.5)

        # Scale importance by message priority (0-10 range → 0.0-0.2 boost)
        importance = min(1.0, importance + message.priority * 0.02)

        sender_label = message.sender_type or message.sender_id
        content = f"{prefix}Received from {sender_label}: {message.content}"

        self.memory_engine.add_memory(
            agent_id,
            content,
            metadata={
                "source": source,
                "emotion": emotion,
                "importance": importance,
                "type": f"message_{message.message_type}",
                "sender_type": message.sender_type,
            }
        )

    def store_unread_messages(self, agent_id: str, messages: List[AgentMessage],
                              year: int = 0, max_store: int = 3) -> int:
        """Store top-priority unread messages as memories.

        Only stores top max_store messages to avoid memory flooding.
        Returns count stored.
        """
        sorted_msgs = sorted(messages, key=lambda m: -m.priority)[:max_store]
        for msg in sorted_msgs:
            self.store_message(agent_id, msg, year)
        return len(sorted_msgs)
```

### File 2 (NEW): `tests/test_memory_bridge.py` (~80 lines)

```python
"""Tests for MemoryBridge: Communication Layer → Memory integration."""
import pytest
from unittest.mock import MagicMock, call
from broker.components.memory_bridge import MemoryBridge, MESSAGE_SOURCE_MAP
from broker.interfaces.coordination import ActionProposal, ActionResolution, AgentMessage


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.add_memory = MagicMock()
    return engine


@pytest.fixture
def bridge(mock_engine):
    return MemoryBridge(mock_engine)


class TestResolutionStorage:
    """Test GameMaster resolution → memory."""

    def test_approved_resolution_stored(self, bridge, mock_engine):
        proposal = ActionProposal(agent_id="H1", agent_type="household", skill_name="buy_insurance")
        resolution = ActionResolution(
            agent_id="H1", original_proposal=proposal,
            approved=True, event_statement="H1 was approved for buy_insurance."
        )
        bridge.store_resolution(resolution, year=3)

        mock_engine.add_memory.assert_called_once()
        args = mock_engine.add_memory.call_args
        assert args[0][0] == "H1"
        assert "Year 3:" in args[0][1]
        assert args[1]["metadata"]["type"] == "resolution"
        assert args[1]["metadata"]["approved"] is True

    def test_denied_resolution_stored(self, bridge, mock_engine):
        proposal = ActionProposal(agent_id="H2", agent_type="household", skill_name="elevate_house")
        resolution = ActionResolution(
            agent_id="H2", original_proposal=proposal,
            approved=False, denial_reason="Insufficient budget",
            event_statement=""
        )
        bridge.store_resolution(resolution, year=5)

        mock_engine.add_memory.assert_called_once()
        content = mock_engine.add_memory.call_args[0][1]
        assert "denied" in content
        assert "elevate_house" in content

    def test_empty_event_statement_skipped(self, bridge, mock_engine):
        proposal = ActionProposal(agent_id="H3", agent_type="household", skill_name="do_nothing")
        resolution = ActionResolution(
            agent_id="H3", original_proposal=proposal,
            approved=True, event_statement=""
        )
        bridge.store_resolution(resolution, year=1)
        mock_engine.add_memory.assert_not_called()

    def test_batch_resolutions(self, bridge, mock_engine):
        p1 = ActionProposal(agent_id="H1", agent_type="household", skill_name="buy_insurance")
        p2 = ActionProposal(agent_id="H2", agent_type="household", skill_name="elevate_house")
        resolutions = [
            ActionResolution(agent_id="H1", original_proposal=p1, approved=True, event_statement="Approved."),
            ActionResolution(agent_id="H2", original_proposal=p2, approved=False, denial_reason="No budget"),
        ]
        count = bridge.store_resolutions(resolutions, year=4)
        assert count == 2
        assert mock_engine.add_memory.call_count == 2


class TestMessageStorage:
    """Test MessagePool message → memory."""

    def test_policy_announcement_stored(self, bridge, mock_engine):
        msg = AgentMessage(
            sender_id="GOV", sender_type="government",
            message_type="policy_announcement",
            content="Subsidy rate increased to 60%",
            priority=5, timestamp=3
        )
        bridge.store_message("H1", msg, year=3)

        mock_engine.add_memory.assert_called_once()
        meta = mock_engine.add_memory.call_args[1]["metadata"]
        assert meta["source"] == "community"
        assert meta["emotion"] == "major"
        assert meta["type"] == "message_policy_announcement"

    def test_neighbor_warning_high_importance(self, bridge, mock_engine):
        msg = AgentMessage(
            sender_id="H5", sender_type="household",
            message_type="neighbor_warning",
            content="Flood damage was severe in my area",
            priority=8, timestamp=2
        )
        bridge.store_message("H1", msg, year=2)

        meta = mock_engine.add_memory.call_args[1]["metadata"]
        assert meta["source"] == "neighbor"
        assert meta["importance"] >= 0.8  # base 0.8 + priority boost

    def test_max_store_limits(self, bridge, mock_engine):
        messages = [
            AgentMessage(sender_id="G", sender_type="gov", message_type="policy_announcement",
                        content=f"Msg {i}", priority=i, timestamp=1)
            for i in range(10)
        ]
        count = bridge.store_unread_messages("H1", messages, year=1, max_store=3)
        assert count == 3
        assert mock_engine.add_memory.call_count == 3


class TestSourceMapping:
    """Test message_type → source/emotion mapping."""

    def test_all_types_mapped(self):
        expected_types = ["policy_announcement", "market_update", "neighbor_warning",
                          "neighbor_info", "media_broadcast", "resolution", "direct"]
        for t in expected_types:
            assert t in MESSAGE_SOURCE_MAP, f"Missing mapping for {t}"
```

### File 3 (EDIT): `examples/multi_agent/orchestration/lifecycle_hooks.py`

Add MemoryBridge integration into the existing hook flow. The edit adds **~30 lines** to the existing `MultiAgentHooks` class.

**Change 1:** Import and accept MemoryBridge in constructor

```python
# ADD to imports at top of file:
from broker.components.memory_bridge import MemoryBridge

# ADD to __init__ parameters:
def __init__(
    self,
    environment: Dict,
    memory_engine: Optional[MemoryEngine] = None,
    hazard_module: Optional[HazardModule] = None,
    media_hub: Optional[MediaHub] = None,
    per_agent_depth: bool = False,
    year_mapping: Optional[YearMapping] = None,
    # NEW parameters:
    game_master: Optional[Any] = None,       # GameMaster instance
    message_pool: Optional[Any] = None,      # MessagePool instance
):
    # ... existing init code ...
    # NEW:
    self.game_master = game_master
    self.message_pool = message_pool
    self._memory_bridge = MemoryBridge(memory_engine) if memory_engine else None
```

**Change 2:** In `post_step()`, after institutional agent decisions, store resolution memories

```python
# ADD at end of post_step(), after existing institutional logic:

# Store GameMaster resolution as memory (if available)
if self._memory_bridge and self.game_master:
    resolution = self.game_master.get_resolution(agent.id)
    if resolution:
        self._memory_bridge.store_resolution(resolution, year=self.env.get("year", 0))
```

**Change 3:** In `post_year()`, store unread messages as memories

```python
# ADD at end of post_year(), after damage memory storage:

# Store important messages as memories
if self._memory_bridge and self.message_pool:
    for agent_id in agents:
        unread = self.message_pool.get_unread(agent_id)
        if unread:
            self._memory_bridge.store_unread_messages(
                agent_id, unread, year=year, max_store=3
            )
```

---

## Data Flow Summary

```
BEFORE (no integration):
  GameMaster.resolve_phase() → List[ActionResolution] → (discarded)
  MessagePool.publish()      → mailboxes             → context only (ephemeral)

AFTER (with MemoryBridge):
  GameMaster.resolve_phase() → List[ActionResolution] → MemoryBridge.store_resolutions()
                                                       → memory_engine.add_memory()
                                                       → agent can reflect on past resolutions

  MessagePool.publish()      → mailboxes → MemoryBridge.store_unread_messages()
                                          → memory_engine.add_memory()
                                          → agent remembers policy announcements
```

## Memory Tag Semantics

| Communication Event | source | emotion | importance | type |
|-------------------|--------|---------|------------|------|
| Approved resolution | abstract | positive | 0.6 | resolution |
| Denied resolution | abstract | shift | 0.75 | resolution |
| Policy announcement | community | major | 0.7 | message_policy_announcement |
| Market update | community | observation | 0.5 | message_market_update |
| Neighbor warning | neighbor | critical | 0.8 | message_neighbor_warning |
| Neighbor info | neighbor | observation | 0.4 | message_neighbor_info |
| Media broadcast | community | major | 0.6 | message_media_broadcast |

These tags align with `HumanCentricMemoryEngine`'s `emotional_weights` and `source_weights` scoring:
- `neighbor` × `critical` = 0.7 × 1.0 = **0.70** (high retention)
- `community` × `observation` = 0.5 × 0.4 = **0.20** (low retention, decays fast)
- `abstract` × `shift` = 0.3 × 0.7 = **0.21** (moderate, but importance override keeps it)

---

## Verification

### 1. Unit tests
```bash
pytest tests/test_memory_bridge.py -v
```
All tests must pass.

### 2. Existing tests (no regression)
```bash
pytest tests/ --ignore=tests/integration --ignore=tests/manual --ignore=tests/test_vector_db.py -v
```
No new failures.

### 3. Import check
```bash
python -c "from broker.components.memory_bridge import MemoryBridge; print('OK')"
```

---

## DO NOT

- Do NOT modify `broker/components/memory_engine.py` or any MemoryEngine implementation
- Do NOT modify `broker/components/coordinator.py`, `message_pool.py`, or any Communication Layer module
- Do NOT modify `broker/interfaces/coordination.py`
- Do NOT add new dependencies (all imports are from existing broker modules)
- Do NOT change the `add_memory()` API signature
- Keep `lifecycle_hooks.py` changes backward-compatible (all new params are Optional with default None)
