# Task-055C: Add Governance Guard to CognitiveCache Hit Path (Codex Assignment)

**Assigned To**: Codex
**Status**: COMPLETED (commit `80b8c55`, verified by Claude Code)
**Priority**: Low
**Estimated Scope**: ~20 lines changed, 1 file + 1 test file

---

## Objective

When `CognitiveCache` returns a cache hit in `ExperimentRunner._run_agents_sequential()` (line 262-294) and `_run_agents_parallel()` (line 324-352), the cached result bypasses the governance pipeline entirely. If agent state has changed between the original decision and the cache hit (e.g., agent was elevated since last time), the cached action might violate governance rules.

**Current mitigation**: The cache hash includes the full context, so state changes should produce a different hash. But hash collisions or incomplete context could lead to stale governance.

**Fix**: Add a lightweight governance check on cache hits, or invalidate cache entries when agent state changes.

---

## Context

### Current Code (`broker/core/experiment.py`, line 262-294)

```python
cached_data = self.efficiency.get(context_hash)
if cached_data:
    logger.info(f"[Efficiency] Cache HIT for {agent.id}")
    # Directly reconstruct result -- NO governance validation
    proposal = SkillProposal(
        skill_name=cached_proposal.get("skill_name", "do_nothing"),
        ...
    )
    result = SkillBrokerResult(
        outcome=SkillOutcome(cached_data.get("outcome", "APPROVED")),
        approved_skill=ApprovedSkill(
            skill_name=cached_data.get("approved_skill", {}).get("skill_name", "do_nothing"),
            ...
        ),
        ...
    )
    results.append((agent, result))
    continue  # Skips broker.process_step() entirely
```

### Risk Scenario

1. Year 3: Agent_5 (not elevated) → context_hash=ABC → decides `elevate_house` → cached
2. Year 4: Agent_5 is now elevated (state changed) → context_hash should be different (DEF)
3. BUT if `elevated` status is not in the context hash input, hash=ABC → cache HIT → returns `elevate_house` again → violates `elevation_block` rule

### Actual Risk Level

LOW -- because `context_builder.build()` includes agent attributes (including `elevated`), and the hash is computed from the full context dict. So step 3 above would produce a different hash. The risk is only from:
- Hash collisions (MD5 truncated to 16 chars)
- Context builder bugs that omit state fields

---

## Recommended Approach: Option A (Lightweight Validation)

Add a quick governance check on cache hits. If validation fails, invalidate the cache entry and fall through to the full broker pipeline.

### File: `broker/core/experiment.py`

**Change**: In `_run_agents_sequential()`, after cache hit reconstruction (around line 293), add validation:

```python
# After reconstructing result from cache (line 293):
# Quick governance check on cached result
if hasattr(self.broker, '_run_validators'):
    validation_context = {
        "agent_state": context,
        "agent_type": getattr(agent, 'agent_type', 'default')
    }
    # Reconstruct minimal proposal for validation
    cached_proposal_obj = SkillProposal(
        skill_name=cached_data.get("approved_skill", {}).get("skill_name", "do_nothing"),
        agent_id=agent.id,
        reasoning=cached_data.get("skill_proposal", {}).get("reasoning", {}),
        agent_type=getattr(agent, 'agent_type', 'default')
    )
    val_results = self.broker._run_validators(cached_proposal_obj, validation_context)
    if not all(v.valid for v in val_results):
        logger.warning(f"[Efficiency] Cache HIT for {agent.id} INVALIDATED by governance. Re-running.")
        self.efficiency.invalidate(context_hash)
        # Fall through to normal broker processing below
    else:
        results.append((agent, result))
        continue
else:
    results.append((agent, result))
    continue
```

**Also apply the same pattern** in `_run_agents_parallel()` (line 324-352).

### File: `broker/core/efficiency.py`

**Change**: Add `invalidate()` method to `CognitiveCache`:

```python
def invalidate(self, context_hash: str) -> bool:
    """Remove a cached entry. Returns True if entry existed."""
    if context_hash in self._cache:
        del self._cache[context_hash]
        return True
    return False
```

---

## Verification

### 1. Add test

**File**: `tests/test_cognitive_cache_governance.py`

```python
"""Test that CognitiveCache respects governance on cache hits."""
import pytest
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
```

### 2. Run tests

```bash
pytest tests/test_cognitive_cache_governance.py -v
pytest tests/ --ignore=tests/integration --ignore=tests/manual --ignore=tests/test_vector_db.py -v
```

---

## DO NOT

- Do NOT remove the CognitiveCache feature entirely
- Do NOT change the cache hash computation logic
- Do NOT modify `SkillBrokerEngine.process_step()`
- Do NOT add expensive operations (full LLM call) to the cache hit path -- only lightweight validation
