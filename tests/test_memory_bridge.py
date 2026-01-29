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
