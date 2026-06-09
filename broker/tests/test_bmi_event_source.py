"""Tests for BmiEventSource — hosting a CSDMS-BMI-conformant model as a WAGF
EventSource (Phase 6V increment 2).

Locks: (1) the toy solver conforms to the BMI verb-set Protocol; (2) the wrapper
conforms to the EventSource Protocol; (3) update->get_value->Event semantics +
thresholding; (4) it is a DROP-IN for the hand-written FloodFootprintSource in
the cat-model chain — the financial chain + the world-mutation governance check
are untouched (the BMI host changes only WHERE the hazard intensity comes from).
No LLM/GPU: deterministic.
"""
from __future__ import annotations

import pytest

from broker.coupling import (
    BmiComponent,
    BmiEventSource,
    CouplingContract,
    EnvironmentCouplingAdapter,
    EventSource,
    VarSpec,
)
from examples.cat_model.bmi_flood_model import ToyBmiFloodModel
from examples.cat_model.cat_validators import insurer_payout_solvency_check
from examples.cat_model.coupling_modules import CatBundle, PortfolioLedger


# --------------------------------------------------------------------------
# Protocol conformance
# --------------------------------------------------------------------------
def test_toy_model_is_bmi_conformant():
    model = ToyBmiFloodModel(rainfall=[1.0])
    assert isinstance(model, BmiComponent)


def test_bmi_source_is_event_source():
    src = BmiEventSource(ToyBmiFloodModel(rainfall=[1.0]), value_var="depth")
    assert isinstance(src, EventSource)


def test_wrapping_non_bmi_object_raises_typeerror():
    class NotABmi:  # missing update/get_value/get_var_units/get_current_time
        pass

    with pytest.raises(TypeError):
        BmiEventSource(NotABmi(), value_var="depth")


# --------------------------------------------------------------------------
# Wrapper semantics
# --------------------------------------------------------------------------
def test_units_delegates_to_bmi_when_unset():
    src = BmiEventSource(ToyBmiFloodModel(rainfall=[1.0]), value_var="depth")
    assert src.units() == "ft"  # ToyBmiFloodModel.get_var_units("depth")


def test_explicit_unit_overrides_bmi():
    src = BmiEventSource(ToyBmiFloodModel(rainfall=[1.0]), value_var="depth", unit="m")
    assert src.units() == "m"


def test_draw_events_advances_model_and_thresholds():
    # linear reservoir: S=max(0, S + R - 0.4 S). rain[0]=0 -> depth 0 (no event);
    # rain[1]=6 -> depth 6 (event); recession keeps depth>0 next step (event).
    model = ToyBmiFloodModel(rainfall=[0.0, 6.0, 0.0], drainage_k=0.4)
    model.initialize()
    src = BmiEventSource(model, value_var="depth")

    assert src.draw_events(0) == []  # depth 0 -> below threshold
    ev = src.draw_events(1)
    assert len(ev) == 1 and ev[0].payload["depth"] == pytest.approx(6.0)
    assert ev[0].period == 1
    ev2 = src.draw_events(2)
    assert len(ev2) == 1 and ev2[0].payload["depth"] == pytest.approx(3.6)  # recession


def test_event_threshold_suppresses_small_depths():
    model = ToyBmiFloodModel(rainfall=[6.0, 0.0], drainage_k=0.4)
    model.initialize()
    src = BmiEventSource(model, value_var="depth", event_threshold=4.0)
    assert len(src.draw_events(0)) == 1  # depth 6 > 4
    assert src.draw_events(1) == []  # depth 3.6 <= 4 -> suppressed


def test_event_at_exact_threshold_is_suppressed():
    """Boundary: depth == threshold suppresses (the operator is `<=`), matching
    FloodFootprintSource's `depth <= 0.0` semantics."""
    model = ToyBmiFloodModel(rainfall=[6.0], drainage_k=0.4)
    model.initialize()
    src = BmiEventSource(model, value_var="depth", event_threshold=6.0)
    assert src.draw_events(0) == []  # depth exactly 6.0, threshold 6.0 -> suppressed


def test_intensity_at_returns_event_value():
    model = ToyBmiFloodModel(rainfall=[5.0])
    model.initialize()
    src = BmiEventSource(model, value_var="depth")
    ev = src.draw_events(0)[0]
    assert src.intensity_at("any_agent", ev) == pytest.approx(5.0)


def test_scalar_reducer_rejects_nonscalar_get_value():
    """A multi-cell get_value (no per-agent reducer) must FAIL, not silently take
    element 0 — that would mis-bill every agent the first cell's intensity."""
    class MultiCellBmi:
        def update(self): pass
        def get_value(self, name): return [1.0, 2.0, 3.0]
        def get_var_units(self, name): return "ft"
        def get_current_time(self): return 0.0

    src = BmiEventSource(MultiCellBmi(), value_var="depth", unit="ft")
    with pytest.raises(ValueError):
        src.draw_events(0)


def test_none_get_value_raises_clear_error():
    """A model returning None for its value var must FAIL with a diagnostic
    message, not crash float(None) with an opaque TypeError or silent-default."""
    class NoneBmi:
        def update(self): pass
        def get_value(self, name): return None
        def get_var_units(self, name): return "ft"
        def get_current_time(self): return 0.0

    src = BmiEventSource(NoneBmi(), value_var="depth", unit="ft")
    with pytest.raises(ValueError, match="None"):
        src.draw_events(0)


# --------------------------------------------------------------------------
# BMI model lifecycle (the standard verb set)
# --------------------------------------------------------------------------
def test_model_determinism_same_rainfall_same_series():
    rain = [0.0, 7.0, 2.0, 0.0]
    a = ToyBmiFloodModel(rainfall=list(rain)); a.initialize()
    b = ToyBmiFloodModel(rainfall=list(rain)); b.initialize()
    sa = [(a.update(), a.get_value("depth")[0])[1] for _ in rain]
    sb = [(b.update(), b.get_value("depth")[0])[1] for _ in rain]
    assert sa == sb


def test_initialize_resets_state():
    m = ToyBmiFloodModel(rainfall=[5.0, 5.0])
    m.initialize(); m.update()
    assert m.get_current_time() == 1.0 and m.get_value("depth")[0] > 0.0
    m.initialize()  # reset
    assert m.get_current_time() == 0.0 and m.get_value("depth")[0] == 0.0


def test_update_until_and_time_metadata():
    m = ToyBmiFloodModel(rainfall=[1.0, 1.0, 1.0], dt=1.0)
    m.initialize()
    m.update_until(2.0)
    assert m.get_current_time() == 2.0
    assert m.get_time_step() == 1.0
    assert m.get_var_units("depth") == "ft"
    assert m.get_output_var_names() == ["depth"]


def test_set_value_overrides_forcing():
    m = ToyBmiFloodModel(rainfall=[0.0, 0.0, 0.0])
    m.initialize()
    m.update()  # consume rain[0]=0 -> depth 0
    m.set_value("rainfall", [10.0])  # override remaining forcing
    m.update()
    assert m.get_value("depth")[0] == pytest.approx(10.0)


def test_set_value_rejects_output_var():
    m = ToyBmiFloodModel(rainfall=[1.0]); m.initialize()
    with pytest.raises(KeyError):
        m.set_value("depth", 5.0)  # depth is an output, not settable


# --------------------------------------------------------------------------
# Drop-in: BmiEventSource replaces FloodFootprintSource, chain unchanged
# --------------------------------------------------------------------------
def test_bmi_source_is_dropin_for_footprint_in_cat_chain():
    """Swap the hazard source for a BMI-hosted model; the rest of the cat chain
    (depth->damage->financial) + the solvency governance check are unchanged."""
    model = ToyBmiFloodModel(rainfall=[8.0])  # period-1 flood, depth 8 ft
    model.initialize()
    led = PortfolioLedger(pool_budget=10_000.0)  # tiny pool -> insolvent
    bundle = CatBundle(BmiEventSource(model, value_var="depth"), led,
                       exposure_value=250_000.0, deductible=5_000.0, limit=200_000.0)
    # draw_events(1) ADVANCES the BMI model one step (not a period selector) and
    # returns the event list run_pipeline consumes.
    env = bundle.run_pipeline({"current_year": 1}, bundle.event_src.draw_events(1), ())
    assert env["flood_depth_ft"] == pytest.approx(8.0)
    assert env["agent_ground_up_loss"] > 0.0
    # the world-mutation governance check fires on this BMI-sourced observation
    out = insurer_payout_solvency_check(
        "approve_payout", [], {"env_state": env, "agent_type": "insurer"})
    assert len(out) == 1 and out[0].valid is False
    assert out[0].metadata["rule_id"] == "pool_insolvent"


def test_adapter_drives_bmi_source_end_to_end():
    model = ToyBmiFloodModel(rainfall=[4.0])
    model.initialize()
    led = PortfolioLedger(pool_budget=100_000.0)
    bundle = CatBundle(BmiEventSource(model, value_var="depth"), led)
    contract = CouplingContract(
        observations=(
            VarSpec("flood_depth_ft", float, "ft", lo=0.0, hi=100.0),
            VarSpec("agent_ground_up_loss", float, "USD_2020", lo=0.0),
            VarSpec("pool_budget_remaining", float, "USD_2020", lo=0.0),
        ),
        inputs=(VarSpec("owed_payout", float, "USD_2020",
                        direction="agent_to_world", consumer_of_record=False),),
    )
    adapter = EnvironmentCouplingAdapter(real_engine=None, contract=contract, sources=bundle)
    env = adapter.advance_step()  # period 1 -> bmi.update() -> depth 4
    assert env["current_year"] == 1
    assert env["flood_depth_ft"] == pytest.approx(4.0)
    # exact: depth_damage_ratio(4.0) * 250_000 = (0.05 + 0.08*4) * 250_000
    #      = 0.37 * 250_000 = 92_500 (ground-up loss, pre-deductible)
    assert env["agent_ground_up_loss"] == pytest.approx(92_500.0)
