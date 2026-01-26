# Task-032 Phase 4B: Entropy Calibrator (Gemini CLI)

**Status**: 🔲 Blocked on Phase 2
**Assignee**: Gemini CLI
**Effort**: 3-4 hours
**Priority**: LOW
**Prerequisite**: Phase 2 (PolicyEngine) complete

---

## Git Branch

```bash
# After Phase 2 completes:
git checkout task-032-phase2
git checkout -b task-032-phase4b

# Can run in parallel with Phase 4A
```

**Stacked PR Structure**:
```
main
 └── task-032-sdk-base (Phase 0)
      └── task-032-phase1 (Codex)
           └── task-032-phase2 (Gemini)
                ├── task-032-phase4a (Claude - XAI)
                └── task-032-phase4b (this branch) ← YOUR WORK HERE
```

---

## Objective

Implement the EntropyCalibrator that measures governance impact on action diversity using Shannon entropy and KL-divergence.

**Purpose**: Detect if governance rules are **over-restricting** or **under-restricting** agent behavior.

---

## Gap Analysis (Why This Is Needed)

Original plan was vague on:
- How to compute Shannon entropy from action distributions
- What divergence metric to use (KL vs JS vs Hellinger)
- Interpretation thresholds

---

## Formulas

### Shannon Entropy
```
H = -Σ p(x) * log₂(p(x))
```

### KL-Divergence
```
KL(P || Q) = Σ p(x) * log(p(x) / q(x))
```

### Friction Ratio Interpretation
| Ratio | Interpretation |
|:------|:---------------|
| ≈ 1.0 | Balanced (minimal governance impact) |
| > 2.0 | **Over-Governed** (excessive restriction) |
| < 0.8 | Under-Governed (rules too permissive) |

---

## Deliverables

### 1. `core/calibrator.py`

```python
"""
Entropy Calibrator for Governance Impact Measurement.

Measures whether governance is over-restricting or under-restricting
agent action diversity using Shannon entropy and KL-divergence.
"""

import math
from collections import Counter
from typing import List, Dict, Optional
from governed_ai_sdk.v1_prototype.types import EntropyFriction


class EntropyCalibrator:
    """
    Measure governance impact on action diversity.

    Example:
        >>> calibrator = EntropyCalibrator()
        >>> raw = ["buy", "sell", "hold", "buy", "sell", "speculate"]
        >>> governed = ["buy", "buy", "hold"]  # speculate blocked
        >>> result = calibrator.calculate_friction(raw, governed)
        >>> print(result.interpretation)
        "Over-Governed"
    """

    def __init__(
        self,
        over_governed_threshold: float = 2.0,
        under_governed_threshold: float = 0.8
    ):
        """
        Initialize calibrator.

        Args:
            over_governed_threshold: Friction ratio above this = over-governed
            under_governed_threshold: Friction ratio below this = under-governed
        """
        self.over_threshold = over_governed_threshold
        self.under_threshold = under_governed_threshold

    def calculate_friction(
        self,
        raw_actions: List[str],
        governed_actions: List[str]
    ) -> EntropyFriction:
        """
        Calculate entropy friction between raw and governed action distributions.

        Args:
            raw_actions: List of intended actions (before governance)
            governed_actions: List of allowed actions (after governance)

        Returns:
            EntropyFriction with entropy values and interpretation
        """
        # Handle empty inputs
        if not raw_actions:
            return EntropyFriction(
                S_raw=0.0,
                S_governed=0.0,
                friction_ratio=1.0,
                kl_divergence=0.0,
                is_over_governed=False,
                interpretation="No Data",
                raw_action_count=0,
                governed_action_count=0,
                blocked_action_count=0,
            )

        # Calculate entropies
        s_raw = self._shannon_entropy(raw_actions)
        s_gov = self._shannon_entropy(governed_actions) if governed_actions else 0.0

        # Calculate KL divergence
        kl_div = self._kl_divergence(raw_actions, governed_actions)

        # Calculate friction ratio
        friction_ratio = s_raw / max(s_gov, 1e-6)

        # Determine interpretation
        if friction_ratio > self.over_threshold:
            interpretation = "Over-Governed"
            is_over_governed = True
        elif friction_ratio < self.under_threshold:
            interpretation = "Under-Governed"
            is_over_governed = False
        else:
            interpretation = "Balanced"
            is_over_governed = False

        # Count blocked actions
        blocked_count = len(raw_actions) - len(governed_actions)

        return EntropyFriction(
            S_raw=s_raw,
            S_governed=s_gov,
            friction_ratio=friction_ratio,
            kl_divergence=kl_div,
            is_over_governed=is_over_governed,
            interpretation=interpretation,
            raw_action_count=len(raw_actions),
            governed_action_count=len(governed_actions),
            blocked_action_count=max(0, blocked_count),
        )

    def _shannon_entropy(self, actions: List[str]) -> float:
        """
        Calculate Shannon entropy: H = -Σ p(x) * log₂(p(x))

        Higher entropy = more diverse actions
        Lower entropy = more concentrated on few actions
        """
        if not actions:
            return 0.0

        counts = Counter(actions)
        total = len(actions)

        entropy = 0.0
        for count in counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)

        return entropy

    def _kl_divergence(
        self,
        p_actions: List[str],
        q_actions: List[str]
    ) -> float:
        """
        Calculate KL divergence: KL(P || Q) = Σ p(x) * log(p(x) / q(x))

        Measures how different the governed distribution is from raw.
        Higher = more impact from governance.
        """
        if not p_actions or not q_actions:
            return float('inf')

        p_counts = Counter(p_actions)
        q_counts = Counter(q_actions)
        p_total = len(p_actions)
        q_total = len(q_actions)

        kl = 0.0
        for action, p_count in p_counts.items():
            p_prob = p_count / p_total
            q_count = q_counts.get(action, 0)

            if q_count > 0:
                q_prob = q_count / q_total
                kl += p_prob * math.log2(p_prob / q_prob)
            else:
                # Action completely blocked - add penalty
                kl += p_prob * 10  # Large penalty for blocked actions

        return kl

    def batch_analyze(
        self,
        sessions: List[Dict]
    ) -> Dict:
        """
        Analyze multiple sessions for aggregate statistics.

        Args:
            sessions: List of {"raw": [...], "governed": [...]} dicts

        Returns:
            Aggregate statistics across all sessions
        """
        results = []
        for session in sessions:
            result = self.calculate_friction(
                session.get("raw", []),
                session.get("governed", [])
            )
            results.append(result)

        if not results:
            return {"error": "No sessions to analyze"}

        avg_friction = sum(r.friction_ratio for r in results) / len(results)
        over_governed_count = sum(1 for r in results if r.is_over_governed)

        return {
            "total_sessions": len(results),
            "avg_friction_ratio": avg_friction,
            "over_governed_sessions": over_governed_count,
            "over_governed_rate": over_governed_count / len(results),
            "avg_s_raw": sum(r.S_raw for r in results) / len(results),
            "avg_s_governed": sum(r.S_governed for r in results) / len(results),
        }


def create_calibrator(
    over_threshold: float = 2.0,
    under_threshold: float = 0.8
) -> EntropyCalibrator:
    """Factory function."""
    return EntropyCalibrator(over_threshold, under_threshold)
```

### 2. Update `core/__init__.py`

Add to existing exports:

```python
from .calibrator import EntropyCalibrator, create_calibrator
```

---

## Test Cases (Create `tests/test_calibrator.py`)

```python
"""
Test suite for EntropyCalibrator.

Run: pytest governed_ai_sdk/tests/test_calibrator.py -v
"""

import pytest
import math
from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator


class TestShannonEntropy:
    """Tests for Shannon entropy calculation."""

    def test_uniform_distribution(self):
        """Uniform distribution has maximum entropy."""
        calibrator = EntropyCalibrator()

        # 4 unique actions, each appears once
        actions = ["a", "b", "c", "d"]
        entropy = calibrator._shannon_entropy(actions)

        # log2(4) = 2.0 for uniform distribution
        assert abs(entropy - 2.0) < 0.01

    def test_single_action_zero_entropy(self):
        """Single repeated action has zero entropy."""
        calibrator = EntropyCalibrator()

        actions = ["buy", "buy", "buy", "buy"]
        entropy = calibrator._shannon_entropy(actions)

        assert entropy == 0.0

    def test_empty_actions(self):
        """Empty list returns zero entropy."""
        calibrator = EntropyCalibrator()

        assert calibrator._shannon_entropy([]) == 0.0


class TestFrictionRatio:
    """Tests for friction ratio and interpretation."""

    def test_over_governed(self):
        """Many actions blocked = over-governed."""
        calibrator = EntropyCalibrator()

        raw = ["buy", "sell", "hold", "speculate", "hedge", "short", "long", "wait"]
        governed = ["buy", "buy", "buy"]  # Only buy allowed

        result = calibrator.calculate_friction(raw, governed)

        assert result.is_over_governed is True
        assert result.interpretation == "Over-Governed"
        assert result.friction_ratio > 2.0

    def test_balanced(self):
        """Similar distributions = balanced."""
        calibrator = EntropyCalibrator()

        raw = ["buy", "sell", "hold"]
        governed = ["buy", "sell"]  # One action blocked

        result = calibrator.calculate_friction(raw, governed)

        assert result.interpretation == "Balanced"
        assert 0.8 <= result.friction_ratio <= 2.0

    def test_under_governed(self):
        """Governed more diverse than raw = under-governed."""
        calibrator = EntropyCalibrator()

        raw = ["buy", "buy", "buy"]  # Low diversity
        governed = ["buy", "sell", "hold", "wait"]  # High diversity (edge case)

        result = calibrator.calculate_friction(raw, governed)

        # S_raw = 0, S_governed > 0, ratio < 0.8
        assert result.friction_ratio < 0.8 or result.interpretation == "Under-Governed"


class TestKLDivergence:
    """Tests for KL divergence calculation."""

    def test_identical_distributions(self):
        """Identical distributions have zero KL divergence."""
        calibrator = EntropyCalibrator()

        actions = ["a", "b", "c"]
        kl = calibrator._kl_divergence(actions, actions)

        assert abs(kl) < 0.01

    def test_blocked_action_penalty(self):
        """Blocked actions increase KL divergence."""
        calibrator = EntropyCalibrator()

        raw = ["a", "b", "c"]
        governed = ["a", "b"]  # "c" blocked

        kl = calibrator._kl_divergence(raw, governed)

        assert kl > 0  # Should have penalty


class TestEntropyFrictionOutput:
    """Tests for EntropyFriction dataclass output."""

    def test_blocked_count(self):
        """Blocked count is calculated correctly."""
        calibrator = EntropyCalibrator()

        raw = ["a", "b", "c", "d", "e"]
        governed = ["a", "b"]

        result = calibrator.calculate_friction(raw, governed)

        assert result.raw_action_count == 5
        assert result.governed_action_count == 2
        assert result.blocked_action_count == 3

    def test_explain_method(self):
        """EntropyFriction.explain() returns string."""
        calibrator = EntropyCalibrator()

        result = calibrator.calculate_friction(
            ["buy", "sell", "hold"],
            ["buy"]
        )

        explanation = result.explain()
        assert isinstance(explanation, str)
        assert "Entropy" in explanation


class TestBatchAnalysis:
    """Tests for batch analysis."""

    def test_batch_multiple_sessions(self):
        """Batch analysis works on multiple sessions."""
        calibrator = EntropyCalibrator()

        sessions = [
            {"raw": ["a", "b", "c"], "governed": ["a"]},
            {"raw": ["x", "y"], "governed": ["x", "y"]},
            {"raw": ["p", "q", "r", "s"], "governed": ["p"]},
        ]

        stats = calibrator.batch_analyze(sessions)

        assert stats["total_sessions"] == 3
        assert "avg_friction_ratio" in stats
        assert "over_governed_sessions" in stats
```

---

## Verification Commands

```bash
# 1. Verify imports
python -c "from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator; print('OK')"

# 2. Run calibrator tests
pytest governed_ai_sdk/tests/test_calibrator.py -v

# 3. Integration test
python -c "
from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator

calibrator = EntropyCalibrator()

# Over-governed scenario
raw = ['buy', 'sell', 'hold', 'speculate', 'hedge']
governed = ['buy', 'buy']

result = calibrator.calculate_friction(raw, governed)
print(f'S_raw: {result.S_raw:.3f}')
print(f'S_governed: {result.S_governed:.3f}')
print(f'Friction Ratio: {result.friction_ratio:.2f}')
print(f'Interpretation: {result.interpretation}')
print(f'Is Over-Governed: {result.is_over_governed}')
"
```

---

## Success Criteria

1. Shannon entropy calculation is mathematically correct
2. KL-divergence handles blocked actions properly
3. Friction ratio interpretation thresholds work
4. Batch analysis provides useful aggregate stats
5. At least 10 tests pass

---

## Handoff Checklist

- [ ] `core/calibrator.py` created with EntropyCalibrator
- [ ] `core/__init__.py` updated
- [ ] `tests/test_calibrator.py` created
- [ ] Shannon entropy verified mathematically
- [ ] All verification commands pass
