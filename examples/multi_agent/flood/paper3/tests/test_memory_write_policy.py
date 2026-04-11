"""Integration tests for the MA flood use of broker memory governance.

These tests verify that the MA flood category mapping together with the
broker-level PolicyFilteredMemoryEngine filters ratchet sources and
passes legitimate writes through.
"""

import inspect
from pathlib import Path

import pytest
import yaml

from broker.components.memory.content_types import MemoryContentType
from broker.components.memory.policy_filter import PolicyFilteredMemoryEngine
from broker.config.memory_policy import CLEAN_POLICY, LEGACY_POLICY, load_from_config
from examples.multi_agent.flood.memory.content_type_mapping import FLOOD_CATEGORY_TO_CONTENT_TYPE


class MockEngine:
    def __init__(self):
        self.add_calls = []

    def add_memory(self, agent_id, content, metadata=None):
        self.add_calls.append({"agent_id": agent_id, "content": content, "metadata": metadata})


class TestFloodCategoryMapping:
    def test_all_known_flood_categories_mapped(self):
        expected_keys = {
            "flood_experience",
            "flood_event",
            "insurance_history",
            "insurance_claim",
            "social_connections",
            "social_interaction",
            "flood_zone",
            "risk_awareness",
            "social_observation",
            "policy_decision",
            "place_attachment",
            "government_trust",
            "adaptation_action",
            "government_notice",
            "decision_reasoning",
            "reflection",
        }
        missing = expected_keys - set(FLOOD_CATEGORY_TO_CONTENT_TYPE)
        assert not missing, f"FLOOD_CATEGORY_TO_CONTENT_TYPE missing: {missing}"

    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("decision_reasoning", MemoryContentType.AGENT_SELF_REPORT),
            ("reflection", MemoryContentType.AGENT_REFLECTION_QUOTE),
            ("place_attachment", MemoryContentType.INITIAL_NARRATIVE),
            ("government_trust", MemoryContentType.INITIAL_NARRATIVE),
            ("adaptation_action", MemoryContentType.INITIAL_NARRATIVE),
            ("government_notice", MemoryContentType.INITIAL_NARRATIVE),
        ],
    )
    def test_ratchet_sources_classified_correctly(self, category, expected):
        assert FLOOD_CATEGORY_TO_CONTENT_TYPE[category] == expected

    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("flood_experience", MemoryContentType.EXTERNAL_EVENT),
            ("flood_event", MemoryContentType.EXTERNAL_EVENT),
            ("flood_zone", MemoryContentType.INITIAL_FACTUAL),
            ("insurance_history", MemoryContentType.INITIAL_FACTUAL),
            ("insurance_claim", MemoryContentType.INITIAL_FACTUAL),
            ("social_connections", MemoryContentType.INITIAL_FACTUAL),
            ("social_interaction", MemoryContentType.INITIAL_FACTUAL),
            ("risk_awareness", MemoryContentType.INITIAL_FACTUAL),
            ("social_observation", MemoryContentType.SOCIAL_OBSERVATION),
            ("policy_decision", MemoryContentType.INSTITUTIONAL_STATE),
        ],
    )
    def test_safe_sources_classified_correctly(self, category, expected):
        assert FLOOD_CATEGORY_TO_CONTENT_TYPE[category] == expected


class TestProxyAgainstFloodMapping:
    @pytest.mark.parametrize(
        "category",
        [
            "decision_reasoning",
            "reflection",
            "place_attachment",
            "government_trust",
            "adaptation_action",
            "government_notice",
        ],
    )
    def test_clean_policy_drops_ratchet_sources(self, category):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=FLOOD_CATEGORY_TO_CONTENT_TYPE)
        proxy.add_memory("H0001", f"test {category}", {"category": category})
        assert len(inner.add_calls) == 0

    @pytest.mark.parametrize(
        "category",
        [
            "flood_experience",
            "flood_event",
            "flood_zone",
            "insurance_history",
            "insurance_claim",
            "social_connections",
            "social_interaction",
            "risk_awareness",
            "social_observation",
            "policy_decision",
        ],
    )
    def test_clean_policy_allows_factual_writes(self, category):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=FLOOD_CATEGORY_TO_CONTENT_TYPE)
        proxy.add_memory("H0001", f"test {category}", {"category": category})
        assert len(inner.add_calls) == 1
        assert inner.add_calls[0]["metadata"]["category"] == category

    def test_legacy_policy_passes_everything(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, LEGACY_POLICY, domain_mapping=FLOOD_CATEGORY_TO_CONTENT_TYPE)
        for category in FLOOD_CATEGORY_TO_CONTENT_TYPE:
            proxy.add_memory("H0001", f"test {category}", {"category": category})
        assert len(inner.add_calls) == len(FLOOD_CATEGORY_TO_CONTENT_TYPE)

    def test_clean_policy_records_drop_counts(self):
        inner = MockEngine()
        proxy = PolicyFilteredMemoryEngine(inner, CLEAN_POLICY, domain_mapping=FLOOD_CATEGORY_TO_CONTENT_TYPE)
        proxy.add_memory("H0001", "x", {"category": "decision_reasoning"})
        proxy.add_memory("H0001", "y", {"category": "place_attachment"})
        assert proxy.dropped_counts["agent_self_report"] == 1
        assert proxy.dropped_counts["initial_narrative"] == 1


class TestConfigIntegration:
    def test_ma_agent_types_yaml_ships_clean_policy(self):
        yaml_path = Path(__file__).resolve().parents[2] / "config" / "ma_agent_types.yaml"
        with yaml_path.open("r", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle)

        global_cfg = cfg.get("global_config", {})
        assert "memory_write_policy" in global_cfg
        policy = load_from_config(global_cfg)
        assert policy == CLEAN_POLICY

    @pytest.mark.parametrize(
        "old_field",
        [
            "decision_reasoning",
            "reflection_quotes",
            "initial_pmt_narratives",
            "initial_factual_seeds",
            "external_events",
            "institutional_events",
        ],
    )
    def test_deprecated_field_names_rejected(self, old_field):
        with pytest.raises(ValueError, match="allow_"):
            load_from_config({"memory_write_policy": {old_field: False}})


class TestLifecycleNoPolicyAttribute:
    def test_hooks_class_has_no_mem_policy_attribute(self):
        from examples.multi_agent.flood.orchestration.lifecycle_hooks import MultiAgentHooks

        hooks = MultiAgentHooks(environment={})
        assert not hasattr(hooks, "_mem_policy")

    def test_hooks_constructor_has_no_memory_write_policy_param(self):
        from examples.multi_agent.flood.orchestration.lifecycle_hooks import MultiAgentHooks

        sig = inspect.signature(MultiAgentHooks.__init__)
        assert "memory_write_policy" not in sig.parameters

    def test_reflection_writes_agent_action_content_type(self):
        from examples.multi_agent.flood.orchestration.lifecycle_hooks import MultiAgentHooks

        class ReflectionEngine:
            def __init__(self):
                self.add_calls = []

            def retrieve_stratified(self, *args, **kwargs):
                return ["memory"]

            def add_memory(self, agent_id, content, metadata=None):
                self.add_calls.append({"agent_id": agent_id, "content": content, "metadata": metadata})

        hooks = MultiAgentHooks(environment={})
        hooks.agent_flood_depths = {}
        agent = type("Agent", (), {"dynamic_state": {"flooded_this_year": False}, "agent_type": "household_owner"})()
        engine = ReflectionEngine()

        hooks._run_ma_reflection("H0001", 1, {"H0001": agent}, engine, False)

        assert len(engine.add_calls) == 1
        assert engine.add_calls[0]["metadata"]["content_type"] == MemoryContentType.AGENT_ACTION.value
