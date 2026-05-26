"""Phase 6Q-C (2026-05-26) — memory-strategy stimulus-key genericity.

Pre-6Q-C the three surprise-strategy classes silently defaulted their
stimulus key to ``"flood_depth"`` — a Phase 6P follow-up audit flagged
this as a BLOCKER-class silent failure for any non-flood domain
(``world_state.get("flood_depth", 0.0)`` → always 0 → zero surprise
signal forever, no error, no warning).

This test file pins the new contract:
  - ``EMASurpriseStrategy`` requires explicit ``stimulus_key=``
  - ``SymbolicSurpriseStrategy`` requires explicit ``sensors=`` OR
    ``default_sensor_key=``
  - ``HybridSurpriseStrategy`` requires explicit ``ema_stimulus_key=``
    AND/OR ``sensors=``

The error message names Phase 6Q-C so a future reader sees the rationale.
"""
import pytest

from broker.memory.strategies.ema import EMASurpriseStrategy
from broker.memory.strategies.symbolic import SymbolicSurpriseStrategy
from broker.memory.strategies.hybrid import HybridSurpriseStrategy


class TestEMARequiresStimulusKey:
    def test_no_kwargs_raises(self):
        with pytest.raises(ValueError, match="stimulus_key"):
            EMASurpriseStrategy()

    def test_explicit_none_raises(self):
        with pytest.raises(ValueError, match="stimulus_key"):
            EMASurpriseStrategy(stimulus_key=None)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="stimulus_key"):
            EMASurpriseStrategy(stimulus_key="")

    def test_explicit_key_succeeds(self):
        strategy = EMASurpriseStrategy(stimulus_key="generic_signal")
        assert strategy.stimulus_key == "generic_signal"

    def test_phase_6q_c_in_error_message(self):
        with pytest.raises(ValueError) as excinfo:
            EMASurpriseStrategy()
        assert "6Q-C" in str(excinfo.value)


class TestSymbolicRequiresSensorsOrDefaultKey:
    def test_no_kwargs_raises(self):
        with pytest.raises(ValueError, match="sensors|default_sensor_key"):
            SymbolicSurpriseStrategy()

    def test_explicit_sensors_succeeds(self):
        from broker.memory.strategies.symbolic import Sensor
        sensors = [Sensor(path="x", name="X", bins=[
            {"label": "LOW", "max": 1.0},
            {"label": "HIGH", "max": 2.0},
        ])]
        strategy = SymbolicSurpriseStrategy(sensors=sensors)
        assert len(strategy._sensors) == 1

    def test_flood_depth_default_sensor_key_still_works(self):
        # Backward-compat path: passing the exact legacy key
        # "flood_depth" still constructs via DEFAULT_BINS preset.
        strategy = SymbolicSurpriseStrategy(default_sensor_key="flood_depth")
        assert len(strategy._sensors) == 1

    def test_unknown_default_sensor_key_raises_for_missing_bins(self):
        with pytest.raises(ValueError, match="DEFAULT_BINS|bins"):
            SymbolicSurpriseStrategy(default_sensor_key="nonexistent_key")


class TestHybridRequiresEMAStimulusKey:
    """Pre-6Q-C `ema_stimulus_key` defaulted to "flood_depth"; now
    required explicitly. A "sensors-only" convenience that borrowed
    the EMA key from `sensors[0].path` was considered + rejected
    (round-1 reviewer WARN: multi-sensor inputs of different physical
    quantities would silently track only the first via EMA)."""

    def test_no_kwargs_raises(self):
        with pytest.raises(ValueError, match="ema_stimulus_key"):
            HybridSurpriseStrategy()

    def test_sensors_only_still_raises(self):
        """Confirms the rejected convenience: sensors alone is not
        enough — the EMA half needs an explicit key."""
        from broker.memory.strategies.symbolic import Sensor
        sensors = [Sensor(path="generic", name="G", bins=[
            {"label": "LOW", "max": 1.0},
            {"label": "HIGH", "max": 2.0},
        ])]
        with pytest.raises(ValueError, match="ema_stimulus_key"):
            HybridSurpriseStrategy(sensors=sensors)

    def test_explicit_key_succeeds(self):
        strategy = HybridSurpriseStrategy(ema_stimulus_key="flood_depth")
        assert strategy._ema.stimulus_key == "flood_depth"
