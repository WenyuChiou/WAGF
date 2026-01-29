"""Test that CognitiveCache respects governance on cache hits."""
from broker.core.efficiency import CognitiveCache


def test_cache_invalidate():
    cache = CognitiveCache()
    cache.put("hash123", {"skill": "elevate_house"})
    assert cache.get("hash123") is not None

    result = cache.invalidate("hash123")
    assert result is True
    assert cache.get("hash123") is None


def test_cache_invalidate_nonexistent():
    cache = CognitiveCache()
    result = cache.invalidate("nonexistent")
    assert result is False
