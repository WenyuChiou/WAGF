"""Unit tests for PolicyFilteredMemoryEngine proxy."""

from unittest.mock import MagicMock

import pytest

from broker.components.memory.content_types import MemoryContentType
from broker.components.memory.policy_filter import PolicyFilteredMemoryEngine
from broker.config.memory_policy import CLEAN_POLICY, LEGACY_POLICY


class MockEngine:
    """Minimal mock memory engine that records every call."""

    def __init__(self):
        self.add_calls = []
        self.retrieve_calls = []
        self.clear_calls = []

    def add_memory(self, agent_id, content, metadata=None):
        self.add_calls.append({"agent_id": agent_id, "content": content, "metadata": metadata})
        return "added"

    def add_memory_for_agent(self, agent, content, metadata=None):
        self.add_calls.append(
            {"agent_id": agent.id, "content": content, "metadata": metadata, "via": "for_agent"}
        )
        return "added_for_agent"

    def retrieve(self, agent, query=None, top_k=3, **kwargs):
        self.retrieve_calls.append({"agent": agent, "query": query, "top_k": top_k, "kwargs": kwargs})
        return ["mock_memory"]

    def clear(self, agent_id):
        self.clear_calls.append(agent_id)
        return "cleared"

    def custom_method(self, x):
        return f"custom({x})"


class TestWriteFiltering:
    def test_clean_policy_allows_external_event(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        assert proxy.add_memory("a1", "flood hit", {"category": "flood_event"}) == "added"
        assert len(inner.add_calls) == 1

    def test_clean_policy_drops_agent_self_report(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        assert proxy.add_memory("a1", "I reasoned...", {"content_type": "agent_self_report"}) is None
        assert len(inner.add_calls) == 0

    def test_legacy_policy_allows_agent_self_report(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, LEGACY_POLICY)
        assert proxy.add_memory("a1", "I reasoned...", {"content_type": "agent_self_report"}) == "added"
        assert len(inner.add_calls) == 1

    def test_clean_drops_initial_narrative(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("a1", "I have deep ties", {"content_type": "initial_narrative"})
        assert len(inner.add_calls) == 0

    def test_clean_drops_reflection_quote(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("a1", "Reflection Year 5", {"content_type": "agent_reflection_quote"})
        assert len(inner.add_calls) == 0

    def test_clean_allows_institutional_reflection(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("gov", "We observed a trend", {"content_type": "institutional_reflection"})
        assert len(inner.add_calls) == 1

    def test_clean_allows_agent_action(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("a1", "I elevated the home", {"type": "action"})
        assert len(inner.add_calls) == 1


class TestAddMemoryForAgent:
    def test_for_agent_respects_policy(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        agent = MagicMock()
        agent.id = "a1"

        assert proxy.add_memory_for_agent(agent, "flood hit", {"category": "flood_event"}) == "added_for_agent"
        assert len(inner.add_calls) == 1
        assert proxy.add_memory_for_agent(agent, "I reasoned", {"content_type": "agent_self_report"}) is None
        assert len(inner.add_calls) == 1

    def test_for_agent_falls_back_to_add_memory_when_inner_lacks_variant(self):
        class NoVariantEngine:
            def __init__(self):
                self.add_calls = []

            def add_memory(self, agent_id, content, metadata=None):
                self.add_calls.append({"agent_id": agent_id, "content": content, "metadata": metadata})
                return "added"

        inner = NoVariantEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        agent = MagicMock()
        agent.id = "a2"

        proxy.add_memory_for_agent(agent, "event", {"category": "flood_event"})
        assert inner.add_calls == [{"agent_id": "a2", "content": "event", "metadata": {"category": "flood_event"}}]


class TestForwarding:
    def test_retrieve_forwarded_unchanged(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        result = proxy.retrieve("agent1", query="test", top_k=5, extra=True)
        assert result == ["mock_memory"]
        assert inner.retrieve_calls == [
            {"agent": "agent1", "query": "test", "top_k": 5, "kwargs": {"extra": True}}
        ]

    def test_clear_forwarded(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        assert proxy.clear("a1") == "cleared"
        assert inner.clear_calls == ["a1"]

    def test_getattr_fallback_to_inner(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        assert proxy.custom_method("x") == "custom(x)"

    def test_policy_property_exposes_configured_policy(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        assert proxy.policy is CLEAN_POLICY

    def test_domain_mapping_property_exposes_mapping(self):
        inner = MockEngine()
        mapping = {"weird": MemoryContentType.AGENT_SELF_REPORT}
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=mapping)
        assert proxy.domain_mapping == mapping


class TestCounters:
    def test_dropped_counts_populated(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        for _ in range(3):
            proxy.add_memory("a1", "reasoning", {"content_type": "agent_self_report"})
        for _ in range(2):
            proxy.add_memory("a1", "attachment", {"content_type": "initial_narrative"})
        assert proxy.dropped_counts["agent_self_report"] == 3
        assert proxy.dropped_counts["initial_narrative"] == 2
        assert "external_event" not in proxy.dropped_counts

    def test_allowed_counts_populated(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("a1", "flood", {"category": "flood_event"})
        proxy.add_memory("a1", "neighbor", {"category": "social_observation"})
        assert proxy.allowed_counts["external_event"] == 1
        assert proxy.allowed_counts["social_observation"] == 1

    def test_stats_shape(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("a1", "reasoning", {"content_type": "agent_self_report"})
        stats = proxy.stats()
        assert "policy" in stats
        assert "dropped_counts" in stats
        assert "allowed_counts" in stats
        assert "domain_mapping_size" in stats
        assert stats["dropped_counts"]["agent_self_report"] == 1

    def test_counts_are_returned_as_plain_dicts(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("a1", "flood", {"category": "flood_event"})
        assert isinstance(proxy.allowed_counts, dict)
        assert isinstance(proxy.dropped_counts, dict)

    def test_stats_domain_mapping_size_zero_without_mapping(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        assert proxy.stats()["domain_mapping_size"] == 0


class TestDomainMapping:
    def test_domain_mapping_passed_to_classifier(self):
        inner = MockEngine()
        domain = {"my_weird_category": MemoryContentType.AGENT_SELF_REPORT}
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=domain)
        proxy.add_memory("a1", "text", {"category": "my_weird_category"})
        assert len(inner.add_calls) == 0
        assert proxy.dropped_counts["agent_self_report"] == 1

    def test_no_domain_mapping_uses_default_rules(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY)
        proxy.add_memory("a1", "flood", {"category": "flood_event"})
        assert len(inner.add_calls) == 1

    def test_domain_mapping_allows_bespoke_safe_category(self):
        inner = MockEngine()
        domain = {"incident_log": MemoryContentType.INSTITUTIONAL_STATE}
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=domain)
        proxy.add_memory("gov", "text", {"category": "incident_log"})
        assert len(inner.add_calls) == 1
        assert proxy.allowed_counts["institutional_state"] == 1
