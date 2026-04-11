"""Unit tests for ExperimentBuilder.with_memory_write_policy wiring."""

import pytest

from broker.components.memory.content_types import MemoryContentType
from broker.components.memory.policy_filter import PolicyFilteredMemoryEngine
from broker.config.memory_policy import CLEAN_POLICY, LEGACY_POLICY
from broker.core.experiment_builder import ExperimentBuilder


class MockEngine:
    def add_memory(self, agent_id, content, metadata=None):
        return None

    def retrieve(self, agent, query=None, top_k=3, **kwargs):
        return []

    def clear(self, agent_id):
        return None


class TestBuilderPolicyMethod:
    def test_requires_engine_first(self):
        builder = ExperimentBuilder()
        with pytest.raises(RuntimeError, match="with_memory_engine"):
            builder.with_memory_write_policy(CLEAN_POLICY)

    def test_wraps_engine_in_proxy(self):
        builder = ExperimentBuilder().with_memory_engine(MockEngine())
        builder.with_memory_write_policy(CLEAN_POLICY)
        assert isinstance(builder.memory_engine, PolicyFilteredMemoryEngine)

    def test_preserves_inner_engine_identity(self):
        inner = MockEngine()
        builder = ExperimentBuilder().with_memory_engine(inner).with_memory_write_policy(CLEAN_POLICY)
        assert builder.memory_engine._inner is inner

    def test_stores_policy_for_later_retrieval(self):
        builder = ExperimentBuilder().with_memory_engine(MockEngine()).with_memory_write_policy(LEGACY_POLICY)
        assert builder._memory_write_policy == LEGACY_POLICY

    def test_domain_mapping_passed_through(self):
        mapping = {"x": MemoryContentType.EXTERNAL_EVENT}
        builder = ExperimentBuilder().with_memory_engine(MockEngine())
        builder.with_memory_write_policy(CLEAN_POLICY, domain_mapping=mapping)
        assert builder.memory_engine.domain_mapping == mapping

    def test_fluent_chain_returns_self(self):
        builder = ExperimentBuilder()
        result = builder.with_memory_engine(MockEngine()).with_memory_write_policy(CLEAN_POLICY)
        assert result is builder

    def test_double_wrap_does_not_crash(self):
        builder = ExperimentBuilder().with_memory_engine(MockEngine())
        builder.with_memory_write_policy(CLEAN_POLICY)
        builder.with_memory_write_policy(LEGACY_POLICY)
        assert isinstance(builder.memory_engine, PolicyFilteredMemoryEngine)

    def test_second_wrap_updates_stored_policy(self):
        builder = ExperimentBuilder().with_memory_engine(MockEngine())
        builder.with_memory_write_policy(CLEAN_POLICY)
        builder.with_memory_write_policy(LEGACY_POLICY)
        assert builder._memory_write_policy is LEGACY_POLICY

    def test_second_wrap_uses_previous_proxy_as_inner(self):
        builder = ExperimentBuilder().with_memory_engine(MockEngine())
        builder.with_memory_write_policy(CLEAN_POLICY)
        first_proxy = builder.memory_engine
        builder.with_memory_write_policy(LEGACY_POLICY)
        assert builder.memory_engine._inner is first_proxy
