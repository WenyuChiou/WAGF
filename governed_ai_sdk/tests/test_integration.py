"""
Integration tests for complete SDK.

Run: pytest governed_ai_sdk/tests/test_integration.py -v
"""

import subprocess
import sys

import pytest


class TestEndToEndFlow:
    """End-to-end integration tests."""

    def test_full_governance_flow(self):
        """Test complete governance flow from agent to trace."""
        from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
        from governed_ai_sdk.v1_prototype.core.policy_loader import PolicyLoader
        from governed_ai_sdk.v1_prototype.xai.counterfactual import CounterfactualEngine
        from governed_ai_sdk.v1_prototype.types import PolicyRule

        engine = PolicyEngine()
        xai = CounterfactualEngine()
        policy = PolicyLoader.from_dict(
            {
                "rules": [
                    {
                        "id": "r1",
                        "param": "x",
                        "operator": ">=",
                        "value": 100,
                        "message": "x too low",
                        "level": "ERROR",
                    }
                ]
            }
        )

        trace = engine.verify({}, {"x": 50}, policy)
        assert trace.valid is False

        rule = PolicyRule(**policy["rules"][0])
        cf = xai.explain(rule, {"x": 50})
        assert cf.delta_state["x"] == 50

    def test_symbolic_memory_with_engine(self):
        """Test symbolic memory triggers System 2 on novel states."""
        from governed_ai_sdk.v1_prototype.memory.symbolic import SymbolicMemory

        sensors = [
            {
                "path": "risk",
                "name": "RISK",
                "bins": [
                    {"label": "LO", "max": 0.5},
                    {"label": "HI", "max": 1.0},
                ],
            }
        ]

        memory = SymbolicMemory(sensors, arousal_threshold=0.5)
        _, surprise = memory.observe({"risk": 0.8})
        assert surprise == 1.0
        assert memory.determine_system(surprise) == "SYSTEM_2"

    def test_calibrator_with_real_actions(self):
        """Test calibrator with realistic action sequences."""
        from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator

        calibrator = EntropyCalibrator()
        raw = ["buy", "hold", "sell", "buy", "speculate", "hold", "hedge", "buy", "sell", "wait"]
        governed = ["buy", "hold", "sell", "buy", "hold", "buy", "sell", "wait"]

        result = calibrator.calculate_friction(raw, governed)
        assert result.friction_ratio > 0.5

    def test_all_imports_work(self):
        """Verify all SDK imports work."""
        from governed_ai_sdk.v1_prototype import (
            PolicyRule,
            GovernanceTrace,
            CounterFactualResult,
            EntropyFriction,
            SymbolicMemory,
            CounterfactualEngine,
            EntropyCalibrator,
        )
        from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine
        from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator as CoreCalibrator
        from governed_ai_sdk.v1_prototype.core.wrapper import GovernedAgent

        assert PolicyRule is not None
        assert PolicyEngine is not None
        assert EntropyCalibrator is not None
        assert CoreCalibrator is not None
        assert GovernedAgent is not None

    def test_demo_script_runs(self):
        result = subprocess.run(
            [sys.executable, "governed_ai_sdk/demo_sdk_usage.py"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "ALL PHASES PASSED" in result.stdout


class TestErrorHandling:
    """Test error handling across components."""

    def test_invalid_rule_raises(self):
        """Invalid PolicyRule raises ValueError."""
        from governed_ai_sdk.v1_prototype.types import PolicyRule

        with pytest.raises(ValueError):
            PolicyRule(
                id="bad",
                param="x",
                operator="INVALID",
                value=1,
                message="",
                level="ERROR",
            )

    def test_empty_policy_passes(self):
        """Empty policy means all actions pass."""
        from governed_ai_sdk.v1_prototype.core.engine import PolicyEngine

        engine = PolicyEngine()
        trace = engine.verify({}, {"x": 1}, {"rules": []})
        assert trace.valid is True
