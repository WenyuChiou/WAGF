"""P1 (silent-failure hunter): a present-but-unusable appraisal or zone
must RAISE, not silently resolve to a plausible value.

Before this fix:

* a blank survey cell (``NaN``), ``None``, ``""``, ``"N/A"`` or ``"abc"``
  for ``tp_score`` / ``cp_score`` silently became ``TP_LABEL`` /
  ``CP_LABEL`` = ``"VL"`` — the SAME plausible label for every one of
  those five distinct "I could not read this" inputs, indistinguishable
  from an agent who genuinely reported no threat at all;
* an out-of-range Likert value (``0``, ``6``, ``-2``) was silently
  clamped into ``[1, 5]`` before being read, turning a data-entry error
  into a real-looking ``VL`` / ``VH``;
* a ``flood_zone`` that stringified to ``"NAN"`` / ``"NONE"`` / ``""``
  read as an ordinary (if unusual) zone code, not as "this cell was
  blank" — a blank cell silently became a flood-prone zone.

Every falsification below recreates the OLD formula inline (the actual
old code no longer exists in ``household_decider.py``) and shows it
lands on the plausible-but-wrong answer the review flagged, immediately
before asserting the NEW code raises instead.
"""
from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import pytest

from examples.multi_agent.flood.parametric.household_decider import (
    APPRAISAL_SCALE,
    AnchoredLogisticHouseholdDecider,
    _LABEL_SCALE,
    _appraisal_to_unit,
    _band,
    _require,
)


def _agent(**fixed: Any) -> SimpleNamespace:
    base = {
        "tenure": "Owner",
        "flood_zone": "HIGH",
        "tp_score": 3.0,
        "cp_score": 3.0,
        "property_value": 350_000.0,
    }
    base.update(fixed)
    return SimpleNamespace(id="H0001", fixed_attributes=base)


def _decider() -> AnchoredLogisticHouseholdDecider:
    return AnchoredLogisticHouseholdDecider(seed=7)


# ---------------------------------------------------------------------------
# The pre-fix formula, recreated for falsification only — NOT imported from
# production code, which no longer contains it.
# ---------------------------------------------------------------------------

def _as_float_pre_fix(value: Any, default: float) -> float:
    if isinstance(value, str):
        scaled = _LABEL_SCALE.get(value.strip().upper())
        if scaled is not None:
            return scaled
        try:
            return float(value)
        except ValueError:
            return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _appraisal_to_unit_pre_fix(value: Any, scale, default: float) -> float:
    """The exact body ``_appraisal_to_unit`` had before review P1."""
    if isinstance(value, str) and value.strip().upper() in _LABEL_SCALE:
        return _LABEL_SCALE[value.strip().upper()]
    raw = _as_float_pre_fix(value, default)
    low, high = float(scale[0]), float(scale[1])
    return min(1.0, max(0.0, (raw - low) / (high - low)))


UNIT_ANCHOR = 0.5  # what the pre-fix call sites passed as `default`


class TestPreFixFalsification:
    """Prove the bug existed before asserting the fix. Each case reproduces
    the historical ``TP_LABEL = "VL"`` (or clamped ``"VH"``) the review
    finding describes."""

    @pytest.mark.parametrize("value", [
        float("nan"), None, "", "N/A", "abc",
    ], ids=["nan", "none", "empty", "n_a", "abc"])
    def test_every_unusable_input_pre_fix_bands_to_the_same_vl(self, value):
        unit = _appraisal_to_unit_pre_fix(value, APPRAISAL_SCALE, UNIT_ANCHOR)
        assert _band(unit) == "VL", (
            f"pre-fix formula must band {value!r} to VL for this test to be "
            f"exercising the bug the review found"
        )

    def test_out_of_range_likert_pre_fix_clamps_to_vh(self):
        unit = _appraisal_to_unit_pre_fix(6, APPRAISAL_SCALE, UNIT_ANCHOR)
        assert _band(unit) == "VH"

    def test_out_of_range_likert_pre_fix_clamps_low_to_vl(self):
        for value in (0, -2):
            unit = _appraisal_to_unit_pre_fix(value, APPRAISAL_SCALE, UNIT_ANCHOR)
            assert _band(unit) == "VL"

    def test_a_blank_zone_pre_fix_stringifies_to_nan_and_would_match_not_in_low(self):
        """The rule-engine half of the same bug (review P1, `_require`):
        a blank `flood_zone` used to reach the caller as the STRING
        ``"NAN"`` — not a real zone code, but not caught either, and a
        household_renter `flood_zone: {not_in: [LOW]}` condition (see
        `ma_agent_types_mixed_population.yaml`) is trivially SATISFIED by
        it: `"NAN" not in ["LOW"]` is True. `matches=True` on a rule that
        should never have fired for a blank cell."""
        pre_fix_zone = str(float("nan")).upper()
        assert pre_fix_zone == "NAN"
        matches = pre_fix_zone not in ["LOW"]
        assert matches is True, (
            "the pre-fix stringify-and-compare path DOES satisfy a "
            "not_in: [LOW] condition for a blank cell — that is the bug"
        )


class TestAppraisalToUnitRaisesOnUnusableInput:
    """Post-fix: `_appraisal_to_unit` raises, naming the agent, instead of
    reproducing the plausible-VL answer demonstrated above."""

    @pytest.mark.parametrize("value", [
        float("nan"), None, "", "N/A", "abc",
    ], ids=["nan", "none", "empty", "n_a", "abc"])
    def test_unusable_value_raises_naming_the_agent(self, value):
        with pytest.raises(ValueError, match="H0001"):
            _appraisal_to_unit(value, APPRAISAL_SCALE, field="tp_score",
                               agent_id="H0001")

    @pytest.mark.parametrize("value", [0, 6, -2])
    def test_out_of_declared_scale_raises_naming_the_agent(self, value):
        with pytest.raises(ValueError, match="H0001"):
            _appraisal_to_unit(value, APPRAISAL_SCALE, field="tp_score",
                               agent_id="H0001")

    def test_a_label_already_in_label_scale_is_accepted_not_rejected(self):
        """DECISION: 'accept a label string already in _LABEL_SCALE' — a
        positive control proving the fix did not also break the
        legitimate label path."""
        unit = _appraisal_to_unit("H", APPRAISAL_SCALE, field="tp_score",
                                  agent_id="H0001")
        assert unit == _LABEL_SCALE["H"]
        assert _band(unit) == "H"

    def test_a_numeric_value_inside_the_scale_still_works(self):
        unit = _appraisal_to_unit(3.0, APPRAISAL_SCALE, field="tp_score",
                                  agent_id="H0001")
        assert unit == pytest.approx(0.5)

    def test_the_default_parameter_is_gone(self):
        """DECISION: 'delete the dead default parameter' — the old
        positional third argument is no longer accepted."""
        import inspect
        params = list(inspect.signature(_appraisal_to_unit).parameters)
        assert "default" not in params


class TestRequireRejectsABlankZone:
    def test_nan_zone_raises_naming_the_agent(self):
        agent = _agent(flood_zone=float("nan"))
        with pytest.raises(ValueError, match="H0001"):
            _require(agent, {}, "flood_zone", field="flood_zone",
                     agent_id="H0001", reject_blank=True)

    @pytest.mark.parametrize("blank", ["", "NaN", "None", "nan", "NONE"])
    def test_string_blank_variants_raise(self, blank):
        agent = _agent(flood_zone=blank)
        with pytest.raises(ValueError, match="H0001"):
            _require(agent, {}, "flood_zone", field="flood_zone",
                     agent_id="H0001", reject_blank=True)

    def test_a_real_zone_is_unaffected(self):
        agent = _agent(flood_zone="HIGH")
        assert _require(agent, {}, "flood_zone", field="flood_zone",
                        agent_id="H0001", reject_blank=True) == "HIGH"

    def test_reject_blank_is_opt_in(self):
        """A caller that does not pass `reject_blank=True` keeps the old
        (pass-through) behaviour — only `flood_zone`'s call site opts in,
        per the DECISION scoping this to fields with no legitimate
        'blank' code."""
        agent = _agent(flood_zone=float("nan"))
        value = _require(agent, {}, "flood_zone", field="flood_zone",
                         agent_id="H0001")
        assert isinstance(value, float) and math.isnan(value)


class TestDecideRaisesEndToEnd:
    """The same falsifications, exercised through the public `decide()`
    entrypoint an experiment actually calls."""

    def test_blank_tp_score_raises(self):
        agent = _agent(tp_score=float("nan"))
        with pytest.raises(ValueError, match="H0001"):
            _decider().decide(agent=agent, env={}, agent_id="H0001",
                              agent_type="household_owner")

    def test_abc_cp_score_raises(self):
        agent = _agent(cp_score="abc")
        with pytest.raises(ValueError, match="H0001"):
            _decider().decide(agent=agent, env={}, agent_id="H0001",
                              agent_type="household_owner")

    def test_out_of_range_tp_score_raises(self):
        agent = _agent(tp_score=6)
        with pytest.raises(ValueError, match="H0001"):
            _decider().decide(agent=agent, env={}, agent_id="H0001",
                              agent_type="household_owner")

    def test_h_label_tp_score_does_not_raise(self):
        agent = _agent(tp_score="H")
        skill, reasoning = _decider().decide(
            agent=agent, env={}, agent_id="H0001", agent_type="household_owner")
        assert reasoning["TP_LABEL"] == "H"

    def test_nan_flood_zone_raises(self):
        agent = _agent(flood_zone=float("nan"))
        with pytest.raises(ValueError, match="H0001"):
            _decider().decide(agent=agent, env={}, agent_id="H0001",
                              agent_type="household_owner")
