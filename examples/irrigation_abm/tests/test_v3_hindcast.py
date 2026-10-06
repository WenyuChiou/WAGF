"""Acceptance test for the Lower Basin non-farm constant (WaterSystemConfig.lb_non_ag_total_maf).

The 2000-2018 hindcast (examples/irrigation_abm/analysis/hindcast_v3.py) is scored with the rule
pre-registered on 2026-09-29 (.research/design_specs/irrigation_v3_hindcast_2026-09-29.md, section 1).
With the default constant at 5.2 MAF all four tests pass; at the former 5.0 MAF only the combined-storage
bias bound fails. Runs in a few seconds; skipped when the H&Y reference data (ref/CRSS_DB) is absent.
"""
from pathlib import Path

import pytest

from examples.irrigation_abm.analysis import hindcast_v3 as hv
from examples.irrigation_abm.irrigation_env import WaterSystemConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_REF_AVAILABLE = (REPO_ROOT / "ref" / "CRSS_DB" / "CRSS_DB" / "HistoricalData"
                       / "LB_historical_annual_diversion.csv").is_file()
needs_ref = pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")


@pytest.fixture(scope="module")
def inputs():
    profiles = hv.load_profiles()
    return {"profiles": profiles, "observed": hv.load_observed(),
            "requests": hv.observed_requests(profiles, range(2000, 2019))}


def test_observed_csv_is_pinned():
    """hindcast_observed_v3.csv loads only at its pinned sha256 and covers 1999-2018."""
    obs = hv.load_observed()
    assert sorted(obs) == list(range(1999, 2019))
    assert obs[2018]["mead_elev_ft_eoy"] == pytest.approx(1081.46)          # USBR, end of Dec 2018
    assert obs[2018]["powell_live_af_eoy"] == pytest.approx(10_098_900)     # USBR RISE 509, 31 Dec 2018


@needs_ref
def test_hindcast_passes_m1_to_m3_at_default_constant(inputs):
    """Default WaterSystemConfig (5.2 MAF, spec item 25, AND
    powell_release_mode="ig2007_tiers", spec items 26/27): the pins moved
    from the storage_balancing prototype's 13.0 ft / +1.09 MAF / KGE 0.74
    (still exactly reproduced under WaterSystemConfig(powell_release_mode=
    "storage_balancing"): examples/irrigation_abm/tests/test_v3_powell_tiers.py
    (TestStorageBalancingHindcast.test_storage_balancing_at_5p2_hindcast))
    to the 2007 Interim Guidelines tiers' own, better-fitting numbers
    (design memo .research/design_specs/irrigation_v3_powell_tiers_2026-09-29.md
    section 4: Mead MAE 10.3 ft, KGE 0.92, combined bias +1.04 MAF)."""
    assert WaterSystemConfig().lb_non_ag_total_maf == pytest.approx(5.2)
    assert WaterSystemConfig().powell_release_mode == "ig2007_tiers"
    r = hv.run_hindcast(2000, 2018, **inputs)
    assert r.gate == {"M1": True, "M2": True, "M3_bias": True, "M3_change": True}
    assert r.metrics["M1_mead_mae_ft"] == pytest.approx(10.3, abs=0.1)
    assert r.metrics["M3_combined_bias_maf"] == pytest.approx(1.04, abs=0.01)
    assert r.metrics["mead_kge"] == pytest.approx(0.92, abs=0.01)


@needs_ref
def test_hindcast_fails_only_m3_bias_at_5p0(inputs):
    """Same ig2007_tiers move as the test above: MAE 18.6 -> 21.2 ft,
    combined bias +2.79 -> +2.71 MAF; the gate pattern itself (only the
    combined-storage bias bound fails at the old 5.0 MAF constant) is
    unchanged."""
    r = hv.run_hindcast(2000, 2018, lb_non_ag_total_maf=5.0, **inputs)
    assert r.gate == {"M1": True, "M2": True, "M3_bias": False, "M3_change": True}
    assert r.metrics["M1_mead_mae_ft"] == pytest.approx(21.2, abs=0.1)
    assert r.metrics["M3_combined_bias_maf"] == pytest.approx(2.71, abs=0.01)


@needs_ref
def test_split_sample_record_implied_values_bracket_5p2(inputs):
    """The record-implied constant is 5.17 MAF on 2003-2010 and 5.21 MAF on 2011-2018."""
    kw = {"profiles": inputs["profiles"], "observed": inputs["observed"]}
    a = hv.record_implied_non_ag(range(2003, 2011), **kw)
    b = hv.record_implied_non_ag(range(2011, 2019), **kw)
    assert a == pytest.approx(5.167, abs=0.005)
    assert b == pytest.approx(5.214, abs=0.005)
    assert abs(a - 5.2) < 0.05 and abs(b - 5.2) < 0.05


@needs_ref
def test_record_implied_non_ag_lb_return_flow_fraction_default_is_unset(inputs):
    """Item 36e (P3-d, Opus review 2026-10-06): leaving lb_return_flow_fraction unset (None) reads
    WaterSystemConfig's own default, 0.0, so it is byte-identical to passing 0.0 explicitly, and
    both are byte-identical to the pre-item-36e behaviour (no fraction parameter at all)."""
    kw = {"profiles": inputs["profiles"], "observed": inputs["observed"]}
    unset = hv.record_implied_non_ag(range(2003, 2011), **kw)
    explicit_zero = hv.record_implied_non_ag(range(2003, 2011), lb_return_flow_fraction=0.0, **kw)
    assert explicit_zero == unset
    assert unset == pytest.approx(5.167, abs=0.005)       # same pin as the test above


@needs_ref
def test_record_implied_non_ag_lb_return_flow_fraction_raises_the_implied_value(inputs):
    """A positive f (item 36e) subtracts (1 - f) x the LB draw instead of the full draw, so the
    record-implied non-farm constant that still closes Mead's balance is larger by
    f x (mean LB draw over the window) -- P3-d, Opus review 2026-10-06."""
    years = range(2003, 2011)
    kw = {"profiles": inputs["profiles"], "observed": inputs["observed"], "requests": inputs["requests"]}
    baseline = hv.record_implied_non_ag(years, **kw)
    f = 0.2
    with_return_flow = hv.record_implied_non_ag(years, lb_return_flow_fraction=f, **kw)

    wr = {p.agent_id: p.water_right for p in inputs["profiles"]}
    lb_ids = [p.agent_id for p in inputs["profiles"] if p.basin != "upper_basin"]
    lb_draws_maf = [sum(min(inputs["requests"][t][a], wr[a]) for a in lb_ids) / 1e6 for t in years]
    expected_increase = f * (sum(lb_draws_maf) / len(lb_draws_maf))

    assert with_return_flow - baseline == pytest.approx(expected_increase, abs=1e-9)
    assert with_return_flow > baseline


@needs_ref
def test_hindcast_result_reports_lb_return_flow_fraction_column(inputs):
    """Opus review P3-d (2026-10-06): HindcastResult carries the RESOLVED lb_return_flow_fraction
    (env.config's own value, mirroring powell_release_mode), and _row() surfaces it as a CSV
    column -- visible even for a row built from split_sample(), which has no other way to receive
    it. A short 2-year window is enough; this test is about the plumbing, not the fit metrics."""
    kw = {"profiles": inputs["profiles"], "observed": inputs["observed"], "requests": inputs["requests"]}

    r_default = hv.run_hindcast(2000, 2001, **kw)
    assert r_default.lb_return_flow_fraction == 0.0
    assert hv._row("case", "window", r_default)["lb_return_flow_fraction"] == 0.0

    r_set = hv.run_hindcast(2000, 2001, lb_return_flow_fraction=0.2, **kw)
    assert r_set.lb_return_flow_fraction == pytest.approx(0.2)
    assert hv._row("case", "window", r_set)["lb_return_flow_fraction"] == pytest.approx(0.2)
