"""
Tests for broker.core.efficiency.CognitiveCache.

Covers: hash stability, cache hit/miss, eviction, invalidation,
persistence round-trip, and stats tracking.
"""
import json
import pytest
from pathlib import Path

from broker.core.efficiency import CognitiveCache


# ---------------------------------------------------------------------------
# Hash stability & sensitivity
# ---------------------------------------------------------------------------

class TestComputeHash:
    """Tests for CognitiveCache.compute_hash()."""

    def test_same_context_produces_same_hash(self):
        cache = CognitiveCache()
        ctx = {
            "agent_id": "a1",
            "state": {"flooded": False, "savings": 50000},
            "environment_context": {"current_year": 1},
        }
        h1 = cache.compute_hash(ctx)
        h2 = cache.compute_hash(ctx)
        assert h1 == h2, "Identical contexts must produce identical hashes"

    def test_different_state_produces_different_hash(self):
        cache = CognitiveCache()
        ctx1 = {"agent_id": "a1", "state": {"flooded": False}}
        ctx2 = {"agent_id": "a1", "state": {"flooded": True}}
        assert cache.compute_hash(ctx1) != cache.compute_hash(ctx2)

    def test_different_env_produces_different_hash(self):
        cache = CognitiveCache()
        ctx1 = {"agent_id": "a1", "state": {}, "environment_context": {"current_year": 1}}
        ctx2 = {"agent_id": "a1", "state": {}, "environment_context": {"current_year": 2}}
        assert cache.compute_hash(ctx1) != cache.compute_hash(ctx2)

    def test_different_agent_produces_different_hash(self):
        cache = CognitiveCache()
        ctx1 = {"agent_id": "a1", "state": {}}
        ctx2 = {"agent_id": "a2", "state": {}}
        assert cache.compute_hash(ctx1) != cache.compute_hash(ctx2)

    def test_hash_is_hex_string(self):
        cache = CognitiveCache()
        h = cache.compute_hash({"agent_id": "a1", "state": {}})
        assert isinstance(h, str)
        assert len(h) == 16  # sha256[:16]
        int(h, 16)  # Must be valid hex


# ---------------------------------------------------------------------------
# Get / Put / Invalidate
# ---------------------------------------------------------------------------

class TestCacheOperations:
    """Tests for get/put/invalidate."""

    def test_miss_returns_none(self):
        cache = CognitiveCache()
        assert cache.get("nonexistent_hash") is None

    def test_put_then_get(self):
        cache = CognitiveCache()
        cache.put("hash_a", {"skill": "do_nothing"})
        result = cache.get("hash_a")
        assert result == {"skill": "do_nothing"}

    def test_invalidate_removes_entry(self):
        cache = CognitiveCache()
        cache.put("hash_b", {"skill": "elevate"})
        assert cache.invalidate("hash_b") is True
        assert cache.get("hash_b") is None

    def test_invalidate_nonexistent_returns_false(self):
        cache = CognitiveCache()
        assert cache.invalidate("nonexistent") is False

    def test_eviction_at_max_size(self):
        cache = CognitiveCache(max_size=3)
        cache.put("h1", {"v": 1})
        cache.put("h2", {"v": 2})
        cache.put("h3", {"v": 3})
        # This should evict h1 (oldest)
        cache.put("h4", {"v": 4})
        assert cache.get("h1") is None, "Oldest entry should be evicted"
        assert cache.get("h4") == {"v": 4}


# ---------------------------------------------------------------------------
# Stats tracking
# ---------------------------------------------------------------------------

class TestCacheStats:
    """Tests for hit/miss stat tracking."""

    def test_stats_initial(self):
        cache = CognitiveCache()
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0
        assert stats["hit_rate"] == 0.0

    def test_stats_after_operations(self):
        cache = CognitiveCache()
        cache.put("h1", {"v": 1})
        cache.get("h1")  # hit
        cache.get("h2")  # miss
        cache.get("h1")  # hit
        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate"] == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestCachePersistence:
    """Tests for save/load round-trip."""

    def test_save_and_load(self, tmp_path):
        path = tmp_path / "cache.json"
        # Save
        cache1 = CognitiveCache(persistence_path=path)
        cache1.put("h1", {"skill": "buy_insurance"})
        cache1.put("h2", {"skill": "elevate"})
        cache1.save()
        assert path.exists()

        # Load into new instance
        cache2 = CognitiveCache(persistence_path=path)
        assert cache2.get("h1") == {"skill": "buy_insurance"}
        assert cache2.get("h2") == {"skill": "elevate"}

    def test_load_missing_file_no_crash(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        cache = CognitiveCache(persistence_path=path)
        assert cache.get_stats()["size"] == 0

    def test_save_to_explicit_path(self, tmp_path):
        cache = CognitiveCache()
        cache.put("h1", {"v": 1})
        save_path = tmp_path / "explicit.json"
        cache.save(path=save_path)
        assert save_path.exists()
        data = json.loads(save_path.read_text(encoding="utf-8"))
        assert "h1" in data["cache"]
