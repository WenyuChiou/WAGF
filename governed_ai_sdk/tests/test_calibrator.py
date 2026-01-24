"""Tests for EntropyCalibrator."""

import math

import pytest


def test_entropy_calibrator_balanced_ratio():
    from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator

    calibrator = EntropyCalibrator()
    raw = ["buy", "sell", "hold", "speculate"]
    governed = ["buy", "hold"]

    result = calibrator.calculate_friction(raw, governed)

    assert math.isclose(result.S_raw, 2.0, rel_tol=1e-6)
    assert math.isclose(result.S_governed, 1.0, rel_tol=1e-6)
    assert math.isclose(result.friction_ratio, 2.0, rel_tol=1e-6)
    assert result.interpretation == "Balanced"


def test_entropy_calibrator_over_governed():
    from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator

    calibrator = EntropyCalibrator()
    raw = ["buy", "sell", "hold", "speculate"]
    governed = ["buy", "buy", "buy", "buy"]

    result = calibrator.calculate_friction(raw, governed)

    assert result.is_over_governed is True
    assert result.interpretation == "Over-Governed"
    assert result.friction_ratio > 2.0


def test_entropy_calibrator_under_governed():
    from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator

    calibrator = EntropyCalibrator()
    raw = ["buy", "buy", "buy"]
    governed = ["buy", "sell", "hold"]

    result = calibrator.calculate_friction(raw, governed)

    assert result.interpretation == "Under-Governed"
    assert result.friction_ratio < 0.8


def test_entropy_calibrator_kl_divergence_non_negative():
    from governed_ai_sdk.v1_prototype.core.calibrator import EntropyCalibrator

    calibrator = EntropyCalibrator()
    raw = ["buy", "sell", "buy", "hold"]
    governed = ["buy", "hold", "hold"]

    result = calibrator.calculate_friction(raw, governed)

    assert result.kl_divergence >= 0.0
