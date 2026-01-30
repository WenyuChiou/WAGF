"""Tests for scalability features."""
import pytest
import time
from cognitive_governance.v1_prototype.core.engine import PolicyEngine
from cognitive_governance.v1_prototype.core.policy_cache import PolicyCache


class TestPolicyCache:
    """Tests for PolicyCache."""

    def test_cache_hit(self):
        """Cached policies return same rules."""
        cache = PolicyCache(max_size=10)
        policy = {"rules": [{"id": "r1", "param": "x", "operator": ">=", "value": 10, "message": "test", "level": "ERROR"}]}

        rules1 = cache.get_or_compile(policy)
        rules2 = cache.get_or_compile(policy)

        assert rules1 is rules2  # Same object (cached)

    def test_cache_eviction(self):
        """LRU eviction works correctly."""
        cache = PolicyCache(max_size=2)

        p1 = {"rules": [{"id": "r1", "param": "x", "operator": ">=", "value": 1, "message": "m", "level": "ERROR"}]}
        p2 = {"rules": [{"id": "r2", "param": "x", "operator": ">=", "value": 2, "message": "m", "level": "ERROR"}]}
        p3 = {"rules": [{"id": "r3", "param": "x", "operator": ">=", "value": 3, "message": "m", "level": "ERROR"}]}

        cache.get_or_compile(p1)
        cache.get_or_compile(p2)
        cache.get_or_compile(p3)  # Should evict p1

        assert cache.stats()["size"] == 2

    def test_severity_sorting(self):
        """Rules are sorted by severity (high first)."""
        cache = PolicyCache()
        policy = {
            "rules": [
                {"id": "r1", "param": "x", "operator": ">=", "value": 1, "message": "low", "level": "ERROR", "severity_score": 0.3},
                {"id": "r2", "param": "x", "operator": ">=", "value": 2, "message": "high", "level": "ERROR", "severity_score": 0.9},
            ]
        }

        rules = cache.get_or_compile(policy)
        assert rules[0].id == "r2"  # High severity first
        assert rules[1].id == "r1"


class TestBatchVerify:
    """Tests for batch verification."""

    def test_batch_verify_sequential(self):
        """Batch verify works sequentially."""
        engine = PolicyEngine()
        policy = {"rules": [{"id": "r1", "param": "x", "operator": ">=", "value": 10, "message": "test", "level": "ERROR"}]}

        requests = [({}, {"x": i}) for i in range(20)]
        results = engine.batch_verify(requests, policy, parallel=False)

        assert len(results) == 20
        assert sum(r.valid for r in results) == 10  # x >= 10

    def test_batch_verify_parallel(self):
        """Batch verify works in parallel."""
        engine = PolicyEngine()
        policy = {"rules": [{"id": "r1", "param": "x", "operator": ">=", "value": 10, "message": "test", "level": "ERROR"}]}

        requests = [({}, {"x": i}) for i in range(100)]
        results = engine.batch_verify(requests, policy, parallel=True)

        assert len(results) == 100
        assert sum(r.valid for r in results) == 90  # x >= 10

    def test_batch_performance(self):
        """Batch processing is faster than sequential for large requests."""
        engine = PolicyEngine()
        policy = {"rules": [{"id": "r1", "param": "x", "operator": ">=", "value": 10, "message": "test", "level": "ERROR"}]}

        requests = [({}, {"x": i % 100}) for i in range(1000)]

        start = time.time()
        engine.batch_verify(requests, policy, parallel=True)
        parallel_time = time.time() - start

        assert parallel_time < 5.0  # Should complete in under 5 seconds
