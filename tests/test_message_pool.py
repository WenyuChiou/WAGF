"""Tests for broker.components.message_pool — Shared Message Pool.

Reference: Task-054 Communication Layer
"""
import pytest
from unittest.mock import MagicMock

from broker.interfaces.coordination import AgentMessage, Subscription
from broker.interfaces.event_generator import EventScope
from broker.components.message_pool import MessagePool


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pool():
    """Fresh MessagePool with no social graph."""
    return MessagePool()


@pytest.fixture
def pool_with_agents(pool):
    """Pool with 4 registered agents."""
    pool.register_agent("gov_1", location="region_A")
    pool.register_agent("ins_1", location="region_A")
    pool.register_agent("hh_1", location="region_A")
    pool.register_agent("hh_2", location="region_B")
    return pool


@pytest.fixture
def mock_social_graph():
    """Mock SocialGraph that returns fixed neighbors."""
    graph = MagicMock()
    graph.get_neighbors.return_value = ["hh_1", "hh_2"]
    return graph


# ---------------------------------------------------------------------------
# Agent Registration
# ---------------------------------------------------------------------------

class TestAgentRegistration:
    def test_register_single_agent(self, pool):
        pool.register_agent("agent_1")
        assert "agent_1" in pool._registered_agents

    def test_register_with_location(self, pool):
        pool.register_agent("agent_1", location="region_X")
        assert pool._agent_locations["agent_1"] == "region_X"

    def test_bulk_register(self, pool):
        agents = {
            "a1": MagicMock(region_id="R1", tract_id=None),
            "a2": MagicMock(region_id=None, tract_id="T5"),
            "a3": MagicMock(spec=[]),  # no region_id or tract_id
        }
        pool.register_agents(agents)
        assert len(pool._registered_agents) == 3


# ---------------------------------------------------------------------------
# Broadcast Delivery
# ---------------------------------------------------------------------------

class TestBroadcast:
    def test_broadcast_delivers_to_all(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "New policy announced!")
        # Should reach ins_1, hh_1, hh_2 (not gov_1 itself)
        assert pool.peek_count("ins_1") == 1
        assert pool.peek_count("hh_1") == 1
        assert pool.peek_count("hh_2") == 1
        assert pool.peek_count("gov_1") == 0  # Sender excluded

    def test_broadcast_returns_message(self, pool_with_agents):
        msg = pool_with_agents.broadcast(
            "gov_1", "government", "Test", message_type="policy",
            data={"rate": 0.05}, timestamp=3, priority=5,
        )
        assert isinstance(msg, AgentMessage)
        assert msg.message_type == "policy"
        assert msg.data == {"rate": 0.05}
        assert msg.timestamp == 3
        assert msg.priority == 5

    def test_broadcast_publish_returns_count(self, pool_with_agents):
        pool = pool_with_agents
        msg = AgentMessage(
            sender_id="gov_1", sender_type="government",
            message_type="announcement", content="Hello all",
            scope=EventScope.GLOBAL,
        )
        delivered = pool.publish(msg)
        assert delivered == 3  # 4 agents minus sender


# ---------------------------------------------------------------------------
# Direct Messaging
# ---------------------------------------------------------------------------

class TestDirectMessaging:
    def test_send_direct(self, pool_with_agents):
        pool = pool_with_agents
        pool.send_direct("gov_1", "government", "hh_1", "Your subsidy is approved")
        assert pool.peek_count("hh_1") == 1
        assert pool.peek_count("hh_2") == 0
        assert pool.peek_count("ins_1") == 0

    def test_send_direct_unregistered_recipient(self, pool_with_agents):
        pool = pool_with_agents
        msg = AgentMessage(
            sender_id="gov_1", sender_type="government",
            message_type="direct", content="Hello",
            recipients=["unknown_agent"],
            scope=EventScope.AGENT,
        )
        delivered = pool.publish(msg)
        assert delivered == 0  # Unregistered agent filtered out


# ---------------------------------------------------------------------------
# Neighbor-Scoped Delivery
# ---------------------------------------------------------------------------

class TestNeighborScoped:
    def test_send_to_neighbors_with_graph(self, mock_social_graph):
        pool = MessagePool(social_graph=mock_social_graph)
        pool.register_agent("hh_0")
        pool.register_agent("hh_1")
        pool.register_agent("hh_2")
        pool.register_agent("hh_3")
        pool.send_to_neighbors("hh_0", "Flood warning!")
        # graph returns ["hh_1", "hh_2"], so only those get it
        assert pool.peek_count("hh_1") == 1
        assert pool.peek_count("hh_2") == 1
        assert pool.peek_count("hh_3") == 0

    def test_send_to_neighbors_no_graph(self, pool_with_agents):
        pool = pool_with_agents
        msg = pool.send_to_neighbors("hh_1", "Neighbors beware!")
        # No graph: recipients list is empty, scope=AGENT → no delivery
        assert pool.peek_count("hh_2") == 0


# ---------------------------------------------------------------------------
# Regional Scoping
# ---------------------------------------------------------------------------

class TestRegionalScope:
    def test_regional_scope_filters_by_location(self, pool_with_agents):
        pool = pool_with_agents
        msg = AgentMessage(
            sender_id="gov_1", sender_type="government",
            message_type="announcement", content="Region A alert",
            scope=EventScope.REGIONAL, location="region_A",
        )
        delivered = pool.publish(msg)
        # region_A agents: ins_1, hh_1 (gov_1 is sender, excluded)
        assert delivered == 2
        assert pool.peek_count("ins_1") == 1
        assert pool.peek_count("hh_1") == 1
        assert pool.peek_count("hh_2") == 0  # region_B


# ---------------------------------------------------------------------------
# Subscription Filtering
# ---------------------------------------------------------------------------

class TestSubscriptions:
    def test_subscription_filters_message_type(self, pool_with_agents):
        pool = pool_with_agents
        pool.subscribe("hh_1", message_types=["policy_announcement"])
        pool.broadcast("gov_1", "government", "Policy update",
                       message_type="policy_announcement")
        pool.broadcast("gov_1", "government", "Market info",
                       message_type="market_update")
        assert pool.peek_count("hh_1") == 1  # Only policy, not market
        assert pool.peek_count("hh_2") == 2  # No subscription, gets all

    def test_subscription_filters_source_type(self, pool_with_agents):
        pool = pool_with_agents
        pool.subscribe("hh_1", source_types=["government"])
        pool.broadcast("gov_1", "government", "Gov message")
        pool.broadcast("ins_1", "insurance", "Ins message")
        assert pool.peek_count("hh_1") == 1  # Only from government
        assert pool.peek_count("hh_2") == 2  # Gets both

    def test_no_subscription_receives_all(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "Msg 1")
        pool.broadcast("ins_1", "insurance", "Msg 2")
        assert pool.peek_count("hh_1") == 2


# ---------------------------------------------------------------------------
# Message Retrieval
# ---------------------------------------------------------------------------

class TestRetrieval:
    def test_get_messages_sorted_by_priority(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "Low priority",
                       priority=1, timestamp=1)
        pool.broadcast("ins_1", "insurance", "High priority",
                       priority=10, timestamp=2)
        msgs = pool.get_messages("hh_1")
        assert len(msgs) == 2
        assert msgs[0].priority == 10  # Highest priority first
        assert msgs[1].priority == 1

    def test_get_messages_since_step(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "Old", timestamp=1)
        pool.broadcast("gov_1", "government", "New", timestamp=5)
        msgs = pool.get_messages("hh_1", since_step=3)
        assert len(msgs) == 1
        assert msgs[0].content == "New"

    def test_get_messages_by_type(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "Policy",
                       message_type="policy")
        pool.broadcast("ins_1", "insurance", "Market",
                       message_type="market")
        msgs = pool.get_messages("hh_1", message_types=["policy"])
        assert len(msgs) == 1
        assert msgs[0].message_type == "policy"


# ---------------------------------------------------------------------------
# Unread Tracking
# ---------------------------------------------------------------------------

class TestUnread:
    def test_get_unread_advances_cursor(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "Msg 1")
        pool.broadcast("ins_1", "insurance", "Msg 2")

        unread = pool.get_unread("hh_1")
        assert len(unread) == 2

        # Second call: no new messages
        unread2 = pool.get_unread("hh_1")
        assert len(unread2) == 0

        # Third message arrives
        pool.broadcast("gov_1", "government", "Msg 3")
        unread3 = pool.get_unread("hh_1")
        assert len(unread3) == 1
        assert unread3[0].content == "Msg 3"


# ---------------------------------------------------------------------------
# TTL Expiration
# ---------------------------------------------------------------------------

class TestTTL:
    def test_advance_step_expires_messages(self, pool_with_agents):
        pool = pool_with_agents
        # TTL=1 message at step 0
        pool.broadcast("gov_1", "government", "Ephemeral", timestamp=0)
        assert pool.peek_count("hh_1") == 1

        # Advance to step 1 → message expires (current_step - timestamp >= ttl)
        expired = pool.advance_step(1)
        assert expired > 0
        assert pool.peek_count("hh_1") == 0

    def test_ttl_zero_never_expires(self, pool_with_agents):
        pool = pool_with_agents
        msg = AgentMessage(
            sender_id="gov_1", sender_type="government",
            message_type="persistent", content="Forever",
            scope=EventScope.GLOBAL, timestamp=0, ttl=0,
        )
        pool.publish(msg)
        pool.advance_step(100)
        assert pool.peek_count("hh_1") == 1  # Still there

    def test_longer_ttl_survives(self, pool_with_agents):
        pool = pool_with_agents
        msg = AgentMessage(
            sender_id="gov_1", sender_type="government",
            message_type="announcement", content="Lasts 3 steps",
            scope=EventScope.GLOBAL, timestamp=5, ttl=3,
        )
        pool.publish(msg)
        pool.advance_step(6)  # 6-5=1 < 3 → survives
        assert pool.peek_count("hh_1") == 1
        pool.advance_step(8)  # 8-5=3 >= 3 → expires
        assert pool.peek_count("hh_1") == 0


# ---------------------------------------------------------------------------
# Clear / Summary
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_clear_resets_everything(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "Msg")
        pool.clear()
        assert pool.peek_count("hh_1") == 0
        assert len(pool._messages) == 0

    def test_summary(self, pool_with_agents):
        pool = pool_with_agents
        pool.broadcast("gov_1", "government", "Msg")
        s = pool.summary()
        assert s["total_messages"] == 1
        assert s["registered_agents"] == 4
