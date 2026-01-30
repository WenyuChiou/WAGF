# Task-058E: Observable State Drift Metrics

> **Assigned to:** ~~Codex~~ → COMPLETED by Claude
> **Priority:** P1
> **Status:** ✅ COMPLETE — `create_drift_observables()` added to `observable_state.py`. 3 metrics: entropy, dominant_pct, stagnation_rate.
> **Depends on:** 058-C (DriftDetector must exist)
> **Branch:** `feat/memory-embedding-retrieval`

---

## Objective

Add drift-related metrics to `ObservableStateManager` as a factory method, similar to the existing `create_flood_observables()`.

## File: `broker/components/observable_state.py` (MODIFY, ~20 lines added)

### Change: Add `register_drift_metrics()` factory method

After the existing `create_flood_observables()` method (around line 280), add:

```python
@staticmethod
def create_drift_observables(drift_detector=None):
    """Create drift-related observable metrics.

    Metrics:
    - decision_entropy: Shannon entropy of latest population decision distribution
    - dominant_action_pct: Percentage choosing the most common action
    - stagnation_rate: Fraction of agents flagged as stagnant
    """
    metrics = {}

    def entropy_metric(agents, env):
        if drift_detector and drift_detector.population_snapshots:
            latest = drift_detector.population_snapshots[-1]
            from broker.components.drift_detector import DriftDetector
            dist = latest.get("distribution", {})
            return DriftDetector.compute_shannon_entropy(dist)
        return 0.0

    def dominant_pct_metric(agents, env):
        if drift_detector and drift_detector.population_snapshots:
            latest = drift_detector.population_snapshots[-1]
            dist = latest.get("distribution", {})
            total = sum(dist.values())
            if total > 0:
                return max(dist.values()) / total
            return 0.0
        return 0.0

    def stagnation_rate_metric(agents, env):
        if drift_detector:
            total = len(drift_detector.decision_history)
            if total == 0:
                return 0.0
            stagnant = sum(
                1 for aid in drift_detector.decision_history
                if drift_detector.compute_jaccard_similarity(aid) > drift_detector.jaccard_threshold
            )
            return stagnant / total
        return 0.0

    metrics["decision_entropy"] = entropy_metric
    metrics["dominant_action_pct"] = dominant_pct_metric
    metrics["stagnation_rate"] = stagnation_rate_metric

    return metrics
```

### Integration Pattern

In `lifecycle_hooks.py` or `disaster_sim.py`, the caller would do:

```python
drift_metrics = ObservableStateManager.create_drift_observables(drift_detector)
for name, fn in drift_metrics.items():
    obs_manager.register(name, fn, scope="community")
```

## Test: Add to `tests/test_observable_state.py` (existing file, ~10 lines)

Add a test class:

```python
class TestDriftObservables:
    def test_create_drift_observables_returns_three_metrics(self):
        metrics = ObservableStateManager.create_drift_observables()
        assert "decision_entropy" in metrics
        assert "dominant_action_pct" in metrics
        assert "stagnation_rate" in metrics

    def test_entropy_metric_without_detector_returns_zero(self):
        metrics = ObservableStateManager.create_drift_observables(None)
        assert metrics["decision_entropy"]([], {}) == 0.0
```

## DO NOT

- Do NOT modify `create_flood_observables()` or any existing methods
- Do NOT change the `ObservableStateManager.__init__` signature
- Do NOT import DriftDetector at module level (lazy import only in metric functions)

## Verification

```bash
pytest tests/test_observable_state.py -v
```

---

## Completion (Codex)

- Status: ✅ Completed
- Commit: `d9c07b2`
- Tests: `pytest tests/test_observable_state.py -v`

### Files Updated
- `broker/components/observable_state.py`
- `tests/test_observable_state.py`
