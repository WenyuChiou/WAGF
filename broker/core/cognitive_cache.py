"""Cognitive Cache: Hash-based decision reuse for LLM efficiency.

This module provides a mechanism to skip redundant LLM calls by caching
decisions based on the hash of the input context. If the same context
(agent state + environment + social signals) is encountered again,
the previously validated decision is returned without invoking the LLM.

Usage:
    cache = CognitiveCache()
    
    # Before LLM call
    cached = cache.get(context_hash)
    if cached:
        return cached  # Skip LLM
    
    # After LLM call
    cache.put(context_hash, decision_json)
"""
import hashlib
import json
from typing import Dict, Any, Optional
from pathlib import Path

from broker.utils.logging import setup_logger

logger = setup_logger(__name__)


class CognitiveCache:
    """In-memory cache for skipping redundant LLM decisions."""
    
    def __init__(self, persistence_path: Optional[Path] = None, max_size: int = 10000):
        """Initialize the cognitive cache.
        
        Args:
            persistence_path: Optional path to persist cache to disk.
            max_size: Maximum number of entries to cache.
        """
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._persistence_path = persistence_path
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
        
        if persistence_path and persistence_path.exists():
            self._load()
    
    def compute_hash(self, context: Dict[str, Any]) -> str:
        """Compute a stable hash for a given context.
        
        Args:
            context: The decision context including agent state, environment, etc.
            
        Returns:
            A hex string representing the context hash.
        """
        # Extract key components for hashing
        hash_components = {
            "agent_id": context.get("agent_id"),
            "elevated": context.get("personal", {}).get("elevated"),
            "has_insurance": context.get("personal", {}).get("has_insurance"),
            "flood_event": context.get("environment_context", {}).get("flood_event"),
            "grant_available": context.get("environment_context", {}).get("grant_available"),
            "memory_hash": hashlib.md5(
                json.dumps(context.get("memory", []), sort_keys=True).encode()
            ).hexdigest()[:8],
        }
        
        serialized = json.dumps(hash_components, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
    
    def get(self, context_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached decision if available.
        
        Args:
            context_hash: The hash of the context.
            
        Returns:
            The cached decision dictionary, or None if not found.
        """
        cached = self._cache.get(context_hash)
        if cached:
            self._hits += 1
            logger.debug(f"[CognitiveCache:Hit] Hash={context_hash[:8]}...")
            return cached
        self._misses += 1
        return None
    
    def put(self, context_hash: str, decision: Dict[str, Any]) -> None:
        """Store a decision in the cache.
        
        Args:
            context_hash: The hash of the context.
            decision: The decision dictionary to cache.
        """
        if len(self._cache) >= self._max_size:
            # Simple FIFO eviction
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.debug(f"[CognitiveCache:Evict] Removed {oldest_key[:8]}...")
        
        self._cache[context_hash] = decision
        logger.debug(f"[CognitiveCache:Store] Hash={context_hash[:8]}...")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with hits, misses, size, and hit rate.
        """
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }
    
    def save(self, path: Optional[Path] = None) -> None:
        """Persist the cache to disk."""
        save_path = path or self._persistence_path
        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump({
                    "cache": self._cache,
                    "stats": self.get_stats(),
                }, f, indent=2)
            logger.info(f"[CognitiveCache:Save] Persisted to {save_path}")
    
    def _load(self) -> None:
        """Load the cache from disk."""
        try:
            with open(self._persistence_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cache = data.get("cache", {})
            logger.info(f"[CognitiveCache:Load] Loaded {len(self._cache)} entries")
        except Exception as e:
            logger.warning(f"[CognitiveCache:Load] Failed to load: {e}")
