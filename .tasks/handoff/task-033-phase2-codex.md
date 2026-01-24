# Task-033 Phase 2: Scalability Enhancement

**Assignee**: Codex
**Branch**: `task-033-phase2-scalability` (create from `task-033-phase1-types` after Phase 1 merges)
**Dependencies**: Phase 1 must be complete first

---

## Objective

Add scalability features to PolicyEngine for large-scale simulations (10K+ agents).

---

## Deliverables

### 2.1 Policy Cache with LRU

**File**: `governed_ai_sdk/v1_prototype/core/policy_cache.py`

```python
"""LRU cache for compiled policy rules."""
from collections import OrderedDict
from typing import Dict, List, Any
from ..types import PolicyRule


class PolicyCache:
    """LRU cache for compiled policy rules."""

    def __init__(self, max_size: int = 100):
        self._cache: OrderedDict[str, List[PolicyRule]] = OrderedDict()
        self._max_size = max_size

    def get_or_compile(self, policy: Dict[str, Any]) -> List[PolicyRule]:
        """Return cached rules or compile and cache."""
        policy_id = self._compute_hash(policy)
        if policy_id in self._cache:
            self._cache.move_to_end(policy_id)
            return self._cache[policy_id]

        rules = self._compile_rules(policy)
        self._cache[policy_id] = rules
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)
        return rules

    def _compute_hash(self, policy: Dict[str, Any]) -> str:
        """Compute deterministic hash for policy dict."""
        import hashlib
        import json
        policy_str = json.dumps(policy, sort_keys=True)
        return hashlib.md5(policy_str.encode()).hexdigest()

    def _compile_rules(self, policy: Dict[str, Any]) -> List[PolicyRule]:
        """Compile and sort rules by severity (high-severity first)."""
        rules = []
        for r in policy.get("rules", []):
            rule = PolicyRule(
                id=r["id"],
                param=r["param"],
                operator=r["operator"],
                value=r["value"],
                message=r["message"],
                level=r.get("level", "ERROR"),
                xai_hint=r.get("xai_hint"),
                domain=r.get("domain", "generic"),
                param_type=r.get("param_type", "numeric"),
                param_unit=r.get("param_unit"),
                severity_score=r.get("severity_score", 1.0),
                literature_ref=r.get("literature_ref"),
                rationale=r.get("rationale"),
            )
            rules.append(rule)
        # Sort by severity (high-severity rules first for early exit)
        return sorted(rules, key=lambda r: r.severity_score, reverse=True)

    def clear(self):
        """Clear the cache."""
        self._cache.clear()

    def stats(self) -> Dict[str, int]:
        """Return cache statistics."""
        return {"size": len(self._cache), "max_size": self._max_size}
```

### 2.2 Batch Verify Method

**File**: `governed_ai_sdk/v1_prototype/core/engine.py` (modify existing)

Add this method to `PolicyEngine` class:

```python
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

def batch_verify(
    self,
    requests: List[Tuple[Dict[str, Any], Dict[str, Any]]],  # [(action, state), ...]
    policy: Dict[str, Any],
    parallel: bool = True,
    max_workers: int = 4
) -> List[GovernanceTrace]:
    """
    Verify multiple action-state pairs efficiently.

    Args:
        requests: List of (action, state) tuples
        policy: Policy configuration
        parallel: Whether to use parallel processing
        max_workers: Number of parallel workers

    Returns:
        List of GovernanceTrace results
    """
    if parallel and len(requests) > 10:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(
                lambda req: self.verify(req[0], req[1], policy),
                requests
            ))
    return [self.verify(action, state, policy) for action, state in requests]
```

### 2.3 Integrate Cache into Engine

Modify `PolicyEngine.__init__` to use cache:

```python
from .policy_cache import PolicyCache

class PolicyEngine:
    def __init__(self, cache_size: int = 100):
        self._cache = PolicyCache(max_size=cache_size)
```

---

## Tests

**File**: `governed_ai_sdk/tests/test_scalability.py`

```python
"""Tests for scalability features."""
import pytest
import time
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
from governed_ai_sdk.v1_prototype.core.policy_cache import PolicyCache


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

        # Just verify it completes in reasonable time
        assert parallel_time < 5.0  # Should complete in under 5 seconds
```

---

## Verification

```bash
# Create branch
git checkout task-033-phase1-types
git pull
git checkout -b task-033-phase2-scalability

# Run tests
python -m pytest governed_ai_sdk/tests/test_scalability.py -v

# Verify batch processing
python -c "
from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
engine = PolicyEngine()
policy = {'rules': [{'id': 'r1', 'param': 'x', 'operator': '>=', 'value': 10, 'message': 'test', 'level': 'ERROR'}]}
requests = [({}, {'x': i}) for i in range(10000)]
results = engine.batch_verify(requests, policy)
print(f'Batch verify 10K: {sum(r.valid for r in results)} passed')
"
```

---

## Report Format

After completion, add to `.tasks/handoff/current-session.md`:

```
---
REPORT
agent: Codex
task_id: task-033-phase2
scope: governed_ai_sdk/v1_prototype/core
status: done
changes:
- governed_ai_sdk/v1_prototype/core/policy_cache.py (created)
- governed_ai_sdk/v1_prototype/core/engine.py (updated with batch_verify)
tests: pytest governed_ai_sdk/tests/test_scalability.py -v (X passed)
artifacts: none
issues: <any issues encountered>
next: merge into task-033-phase1-types
---
```
