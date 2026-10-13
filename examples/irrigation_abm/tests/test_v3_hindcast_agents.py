"""Agent hindcast acceptance checks, with projection regressions kept separate."""
import hashlib
import csv
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from examples.irrigation_abm.analysis import hindcast_v3 as hv
from examples.irrigation_abm.hindcast_env import (
    HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR, HINDCAST_PRECIP_CSV,
    HINDCAST_PRECIP_SHA256, HindcastAgentEnvironment, hindcast_config_kwargs,
    hindcast_provenance, initial_pf_prev, reanchor_profiles,
)
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment, WaterSystemConfig, _load_ub_subbasin_variant_means,
)
from examples.irrigation_abm.irrigation_personas import build_water_situation_text

ROOT = Path(__file__).resolve().parents[3]
YEARS = range(HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR + 1)


@pytest.fixture(scope="module")
def inputs():
    profiles = hv.load_profiles(seed=42)
    return profiles, hv.load_observed(), hv.observed_requests(
        profiles, range(HINDCAST_FIRST_YEAR - 2, HINDCAST_LAST_YEAR + 1))


def make_env(profiles, cls=HindcastAgentEnvironment):
    env = cls(WaterSystemConfig(**hindcast_config_kwargs()))
    env.initialize_from_profiles(reanchor_profiles(profiles))
    env.load_crss_precipitation(str(HINDCAST_PRECIP_CSV))
    return env


def test_t1_replay_equals_recorded_hindcast_bitwise(inputs):
    profiles, observed, requests = inputs

    class ReplayEnv(HindcastAgentEnvironment):
        def _reset_requests_to_base(self):
            super()._reset_requests_to_base()
            for aid, af in requests[self.current_year].items():
                self._agents[aid]["request"] = af

    env = make_env(profiles, ReplayEnv)
    actual = []
    for _ in YEARS:
        env.advance_year()
        st = env.settle_year()
        actual.append([st["mead_storage_end_maf"], st["powell_storage_end_maf"],
                       st["powell_release_maf"]])
    reference = hv.run_hindcast(HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR,
                               profiles=profiles, observed=observed, requests=requests)
    expected = [[row["mead_total_sim"], row["powell_total_sim"], row["release_sim"]]
                for row in reference.series]
    assert np.asarray(actual, dtype=np.float64).tobytes() == np.asarray(expected, dtype=np.float64).tobytes()


def test_t2_plan_at_keep_mead_gate(inputs, record_property):
    profiles, observed, requests = inputs
    env = make_env(profiles)
    settlements = []
    for year in YEARS:
        env.advance_year()
        for aid, af in requests[year].items():
            env.update_agent_request(aid, af)
        settlements.append(env.settle_year())
    errors = [hv.mead_elevation_ft(st["mead_storage_end_maf"]) - observed[y]["mead_elev_ft_eoy"]
              for y, st in zip(YEARS, settlements)]
    replay = hv.run_hindcast(HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR,
                            profiles=profiles, observed=observed, requests=requests)
    release_delta = [abs(st["powell_release_maf"] - row["release_sim"])
                     for st, row in zip(settlements, replay.series)]
    storage_delta = [abs(st["mead_storage_end_maf"] - row["mead_total_sim"])
                     for st, row in zip(settlements, replay.series)]
    values = {"mead_mae_ft": float(np.mean(np.abs(errors))),
              "mead_bias_ft": float(np.mean(errors)), "max_abs_ft": max(map(abs, errors)),
              "max_release_difference_maf": max(release_delta),
              "max_mead_storage_difference_maf": max(storage_delta)}
    for key, value in values.items():
        record_property(key, value)
    print("plan-at-keep", json.dumps(values))
    assert values["mead_mae_ft"] <= 25.0
    assert release_delta[:8] == [0.0] * 8
    assert max(release_delta[8:]) > 0.0


def test_t3_reanchor_only_use_fields(inputs):
    profiles, _, requests = inputs
    anchored = reanchor_profiles(profiles)
    assert len(anchored) == 78
    for old, new in zip(profiles, anchored):
        assert old.actual_2018_diversion == pytest.approx(requests[2018][old.agent_id], rel=1e-15)
        assert new.actual_2018_diversion == requests[HINDCAST_FIRST_YEAR - 1][old.agent_id]
        assert new.actual_2017_diversion == requests[HINDCAST_FIRST_YEAR - 2][old.agent_id]
        for name in old.__dataclass_fields__:
            if name not in ("actual_2017_diversion", "actual_2018_diversion"):
                assert np.array_equal(getattr(old, name), getattr(new, name))


def test_t4_precip_pin_mapping_and_projection_overlap():
    assert hashlib.sha256(HINDCAST_PRECIP_CSV.read_bytes()).hexdigest() == HINDCAST_PRECIP_SHA256
    historical = hv.CRSS_DB_DIR / "HistoricalData"
    winter = pd.read_csv(historical / "PrismWinterPrecip_NOAA_Winter_1905-2018.csv", index_col=0)
    precip = pd.read_csv(HINDCAST_PRECIP_CSV, index_col=0)
    future = pd.read_csv(historical / "PrismWinterPrecip_ST_NOAA_Future.csv", index_col=0)
    stations = {"WY": "WY_JACKSON", "NM": "NM_DURANGO", "AZ": "NM_DURANGO",
                **dict.fromkeys(("UT1", "UT2", "UT3"), "UT_FLAMINGGORGE"),
                **dict.fromkeys(("CO1", "CO2", "CO3"), "CO_ASPEN")}
    assert list(precip.index) == list(range(HINDCAST_FIRST_YEAR - 2, HINDCAST_LAST_YEAR + 1))
    assert set(precip.columns) == set(stations)
    for column, station in stations.items():
        np.testing.assert_array_equal(precip[column], winter.loc[precip.index, station])
    np.testing.assert_array_equal(precip.loc[[2017, 2018]], future.loc[[2017, 2018], precip.columns])


def test_t5_observed_flow_share_and_default_error(inputs):
    profiles, observed, _ = inputs
    env = make_env(profiles)
    env.advance_year()
    p = next(p for p in profiles if p.basin == "upper_basin")
    ctx = env.get_agent_context(p.agent_id)
    mean = _load_ub_subbasin_variant_means()[env.config.ub_subbasin_supply_variant][p.precip_group]
    assert ctx["ub_subbasin_flow_share"] == observed[HINDCAST_FIRST_YEAR][f"q_{p.precip_group}_af"] / mean
    projection = IrrigationEnvironment()
    projection.initialize_from_profiles(profiles)
    projection._precip_history = env._precip_history.copy()
    projection._current_year = HINDCAST_FIRST_YEAR
    with pytest.raises(ValueError, match="no ub_subbasin_supply_v3.csv row"):
        projection.get_agent_context(p.agent_id)


def test_t6_first_prompt_uses_1999_state(inputs):
    profiles, _, requests = inputs
    env = make_env(profiles)
    env.advance_year()
    for basin, verb in (("upper_basin", "used"), ("lower_basin", "diverted")):
        p = next(p for p in profiles if p.basin == basin)
        text = build_water_situation_text(env.get_agent_context(p.agent_id))
        assert f"It is now the year {HINDCAST_FIRST_YEAR}" in text
        assert f"In {HINDCAST_FIRST_YEAR - 1} you {verb} {requests[1999][p.agent_id]:,.0f}" in text


def test_t7_trend_and_fql_initial_flags(inputs):
    profiles, _, _ = inputs
    env = make_env(profiles)
    env.advance_year()
    precip = pd.read_csv(HINDCAST_PRECIP_CSV, index_col=0)
    flags = initial_pf_prev(profiles)
    assert len(flags) == 78
    for p in profiles:
        expected = int(precip.loc[1999, p.precip_group] > precip.loc[1998, p.precip_group]) if p.basin == "upper_basin" else 0
        assert flags[p.agent_id] == expected
        if p.basin == "lower_basin":
            assert "rising from last year" in build_water_situation_text(env.get_agent_context(p.agent_id))


def test_t8_pre2008_tier_zero(inputs):
    env = make_env(inputs[0])
    for year in range(HINDCAST_FIRST_YEAR, 2008):
        env.advance_year()
        assert env.current_year == year
        assert all(env.get_agent_context(aid)["shortage_tier"] == 0 for aid in env.agent_ids)
        env.settle_year()


@pytest.mark.parametrize("runner,extra", [("run_experiment", ["--model", "mock"]),
                                         ("run_fql_baseline", ["--fql-init", "zero"])])
def test_t9_default_runner_never_imports_hindcast(runner, extra, tmp_path):
    script = (
        "import runpy,sys; sys.argv=" + repr([runner, "--years", "1", "--agents", "2", "--output", str(tmp_path), *extra]) + "; "
        "runpy.run_module('examples.irrigation_abm." + runner + "',run_name='__main__'); "
        "assert not any(n.endswith(('hindcast_env','hindcast_v3')) for n in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr


@pytest.mark.parametrize("runner,flags", [
    ("run_experiment", ["--years", "19"]),
    ("run_experiment", ["--real", "--years", "3"]),
    ("run_experiment", ["--real", "--years", "19", "--coupling"]),
    ("run_experiment", ["--real", "--years", "19", "--rebalance-clusters"]),
    ("run_fql_baseline", ["--years", "19"]),
    ("run_fql_baseline", ["--real", "--years", "3"]),
    ("run_fql_baseline", ["--real", "--years", "19", "--from-logs", "missing.csv"]),
    ("run_fql_baseline", ["--real", "--years", "19", "--fql-init", "zero"]),
])
def test_t10_runner_refusals(runner, flags, monkeypatch):
    from importlib import import_module
    module = import_module("examples.irrigation_abm." + runner)
    monkeypatch.setattr(sys, "argv", [runner, "--hindcast", "--model", "mock", *flags] if runner == "run_experiment" else [runner, "--hindcast", *flags])
    with pytest.raises(SystemExit, match="--hindcast requires"):
        module.main()


def test_t11_provenance_and_identifying_config(monkeypatch, tmp_path):
    from examples.irrigation_abm import run_experiment as runner
    monkeypatch.setattr(sys, "argv", ["runner", "--model", "mock"])
    args = runner.parse_args()
    assert "hindcast" not in runner._irrigation_identifying_config(args)
    args.hindcast = True
    assert runner._irrigation_identifying_config(args)["hindcast"] is True
    config = WaterSystemConfig(**hindcast_config_kwargs())
    block = hindcast_provenance(config, fql_init="calibrated", fql_init_dir="All-1109")
    assert block["window"] == [HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR]
    assert block["anchor_year"] == HINDCAST_FIRST_YEAR - 1
    assert block["agent_text_handling"] == "unchanged: all projection text kept; spec section 6 items F1 to F6 await the PI"
    required = {"mode", "observed_csv_sha256", "precip_csv_sha256", "precip_source_sha256",
                "ub_depletion_sha256", "lb_diversion_sha256", "mead_levels_sha256",
                "tier_start_year", "pre2008_release_rule", "powell_release_mode",
                "lb_non_ag_total_maf", "lb_return_flow_fraction", "fql_init",
                "fql_init_dir", "fql_trained_through", "limits", "code_commit", "git_dirty"}
    assert required <= block.keys()
    (tmp_path / "reproducibility_manifest.json").write_text('{}', encoding="utf-8")
    (tmp_path / "config_snapshot.yaml").write_text('metadata: {}\n', encoding="utf-8")
    runner._record_hindcast_provenance(tmp_path, config)
    assert json.loads((tmp_path / "reproducibility_manifest.json").read_text())["hindcast"]["mode"] == "hindcast"


def test_t12_scoring_parts_units_and_benchmarks():
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score
    from examples.irrigation_abm.analysis.v3_metrics import kge
    metric = kge([1, 2, 4], [1, 2, 4])
    assert (metric.kge, metric.r, metric.alpha, metric.beta) == (1, 1, 1, 1)
    recorded = score.recorded_series()
    ub = pd.read_csv(hv.UB_DEPLETION_CSV, index_col=0)
    assert recorded["ub:WY"][2000] == float(ub.loc[2000, "WY"]) / 1000
    benchmarks = score.benchmark_series(recorded)
    for name, series in recorded.items():
        assert benchmarks["persistence_recorded_prior_year"][name][2000] == series[1999]
        assert all(benchmarks["constant_recorded_1999"][name][y] == series[1999] for y in YEARS)
    constant = kge([recorded["ub:WY"][1999]] * len(YEARS), [recorded["ub:WY"][y] for y in YEARS])
    assert constant.r == constant.alpha == 0
    assert "convention" in constant.note


def test_window_change_uses_matching_mead_history(inputs):
    import examples.irrigation_abm.hindcast_env as original
    source = Path(original.__file__).read_text(encoding="utf-8")
    source = source.replace("HINDCAST_FIRST_YEAR = 2000", "HINDCAST_FIRST_YEAR = 2001")
    namespace = {"__file__": original.__file__, "__name__": "shifted_hindcast"}
    exec(compile(source, original.__file__, "exec"), namespace)
    env = namespace["HindcastAgentEnvironment"](WaterSystemConfig(**namespace["hindcast_config_kwargs"]()))
    env.initialize_from_profiles(namespace["reanchor_profiles"](inputs[0]))
    env.load_crss_precipitation(str(HINDCAST_PRECIP_CSV))
    assert env._mead_history == [namespace["_mead_dec_levels"]()[1999]]
    env.advance_year()
    assert env.current_year == 2001


def test_window_change_checks_only_matching_mead_seed(inputs):
    import examples.irrigation_abm.hindcast_env as original

    source = Path(original.__file__).read_text(encoding="utf-8")
    source = source.replace("HINDCAST_FIRST_YEAR = 2000", "HINDCAST_FIRST_YEAR = 2001")
    namespace = {"__file__": original.__file__, "__name__": "shifted_hindcast"}
    exec(compile(source, original.__file__, "exec"), namespace)
    levels = namespace["_mead_dec_levels"]()
    levels[1998] = -1.0
    namespace["_mead_dec_levels"] = lambda: levels
    env = namespace["HindcastAgentEnvironment"](
        WaterSystemConfig(**namespace["hindcast_config_kwargs"]()))
    assert env._mead_history == [levels[1999]]


def test_fql_hindcast_rejects_coupling_previous_action(inputs, tmp_path, monkeypatch):
    from examples.irrigation_abm import run_fql_baseline as runner

    selected = inputs[0][0].agent_id
    original = runner._load_ql_div_2017_2018
    monkeypatch.setattr(runner, "_load_ql_div_2017_2018",
                        lambda aid, basin, directory: (1.0, 2.0) if aid == selected
                        else original(aid, basin, directory))
    monkeypatch.setattr(sys, "argv", ["runner", "--hindcast", "--real",
                        "--no-governance", "--fql-init", "calibrated", "--years", "19",
                        "--seed", "42", "--paper-water-margin", "0.4",
                        "--cluster-method", "hy2021", "--output", str(tmp_path / "run")])
    with pytest.raises(SystemExit, match="historical_annual_series"):
        runner.main()
    assert not (tmp_path / "run" / "simulation_log.csv").exists()


def test_fql_empty_initial_flags_are_used(inputs, tmp_path):
    from examples.irrigation_abm import run_fql_baseline as runner

    profiles = inputs[0]
    env = make_env(profiles)
    agents = runner.create_fql_agents(profiles, seed=42, fql_init="calibrated",
                                     fql_init_dir=hv.CRSS_DB_DIR / "Initial_Files" / "All-1109",
                                     crss_db_dir=hv.CRSS_DB_DIR)
    flags = {}
    runner.run_simulation(env, agents, {p.agent_id: p for p in profiles}, 1,
                          tmp_path, no_governance=True, pf_prev_init=flags)
    assert set(flags) == set(env.agent_ids)


def write_scoring_run(folder, inputs, seed, *, kind="llm", arm="strict", lag=0):
    from examples.irrigation_abm import run_fql_baseline as fql

    profiles, _, requests = inputs
    folder.mkdir()
    config = WaterSystemConfig(seed=seed, **hindcast_config_kwargs())
    pins = fql._pinned_v3_data_checksums(config.ub_subbasin_supply_variant)
    manifest = {
        "model": "replay-fixture", "model_digest": None, "seed": seed,
        "governance_profile_resolved": arm, "config_hash": "fixture-config",
        "derived_from_config_sha256": None, "cluster_method": "hy2021",
        "paper_water_margin": 0.4, "beneficial_use_limit": {"enabled": True},
        "keepfix_package": {"S1": True}, "memory_engine_class": "fixture-memory",
        "retry_feedback_mode": "full", "llm_params_resolved": {"model": "replay-fixture"},
        "thinking_mode": "disabled", "llm_thinking": {}, "llm_safeguard": {},
        "workers": 1, "water_system_config": asdict(config),
        "hindcast": hindcast_provenance(config), "pinned_v3_data_checksums": pins,
        "coupling_retrofit_metadata": {
            "water_system_lb_priority_mode": config.lb_priority_mode,
            "water_system_lb_tributary_source": config.lb_tributary_source,
            "water_system_hydrology_v3_sha256": pins["hydrology_v3_csv"],
            "water_system_mead_capacity_sha256": pins["mead_capacity_usbr2009_1ft_csv"],
            "water_system_lb_priority_split_sha256": pins["lb_priority_split_v3_csv"],
        },
    }
    for key in ("hold_requests_fixed", "powell_release_mode", "powell_post2026_equalization",
                "lb_non_ag_total_maf", "lb_return_flow_fraction", "min_utilisation_fraction",
                "ub_supply_mode", "ub_subbasin_supply_variant", "lb_priority_mode", "lb_p56_in_tier"):
        manifest[key] = getattr(config, key)
    for key in ("ub_subbasin_supply_v3", "ub_subbasin_envelope_v3", "ub_subbasin_variant_means_v3"):
        manifest[key + "_sha256"] = pins[key + "_csv"]
    if kind == "fql":
        manifest.update(runner="run_fql_baseline", fql_init="calibrated",
                        fql_init_dir_name="All-1109", no_governance=True,
                        fql_init_per_agent={}, crss_db_input_checksums={})
        manifest["hindcast"] = hindcast_provenance(config, fql_init="calibrated",
                                                   fql_init_dir="All-1109")
    manifest["hindcast"]["code_commit"] = "a" * 40
    manifest["git_head" if kind == "fql" else "git_commit"] = manifest["hindcast"]["code_commit"]
    manifest["git_dirty"] = manifest["hindcast"]["git_dirty"] = False
    path = folder / "reproducibility_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with (folder / "simulation_log.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["agent_id", "year", "calendar_year", "basin", "ub_subbasin", "request", "diversion"])
        writer.writeheader()
        for year in YEARS:
            for p in profiles:
                writer.writerow(dict(agent_id=p.agent_id, year=year-HINDCAST_FIRST_YEAR+1,
                                     calendar_year=year, basin=p.basin, ub_subbasin=p.precip_group or "",
                                     request=requests[year-lag][p.agent_id], diversion=requests[year-lag][p.agent_id]))
    return manifest


@pytest.mark.parametrize("key", ["observed_csv_sha256", "precip_csv_sha256", "precip_source_sha256", "mead_levels_sha256"])
def test_scoring_rejects_wrong_hydrology_pin(inputs, tmp_path, key):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score
    folder = tmp_path / "run"
    manifest = write_scoring_run(folder, inputs, 42)
    manifest["hindcast"][key] = "0" * 64
    (folder / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match=key):
        score.score_runs([folder], [], tmp_path / "out")


@pytest.mark.parametrize("key,value", [("model", "other_mock"), ("lb_non_ag_total_maf", 5.0)])
def test_scoring_rejects_mixed_seed_ensemble(inputs, tmp_path, key, value):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score
    first, second = tmp_path / "first", tmp_path / "second"
    write_scoring_run(first, inputs, 42)
    manifest = write_scoring_run(second, inputs, 43)
    manifest[key] = value
    (second / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="mixed"):
        score.score_runs([first, second], [], tmp_path / "out")


def test_score_runs_perfect_recorded_replay_all_agents(inputs, tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / "replay"
    write_scoring_run(folder, inputs, 42)
    rows = score.score_runs([folder], [], tmp_path / "scores")
    actual = [row for row in rows if row["kind"] == "llm" and row["series"].startswith(("ub:", "lb:"))]
    expected = {"ub:" + s for s in hv.UB_SUBBASINS}
    expected.update("lb:" + p.agent_id for p in inputs[0] if p.basin == "lower_basin")
    expected.update(("ub:total", "lb:total"))
    assert len(actual) == len(expected) * 2 == 66
    assert {(row["series"], row["quantity"]) for row in actual} == {
        (series, quantity) for series in expected for quantity in ("request", "diversion")}
    for row in actual:
        assert row["n"] == 19
        for part in ("kge", "r", "alpha", "beta"):
            assert row[part] == pytest.approx(1.0, abs=1e-12), (row["series"], row["quantity"], part)


def test_score_runs_one_year_shift_is_not_perfect(inputs, tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / "lagged"
    write_scoring_run(folder, inputs, 42, lag=1)
    rows = score.score_runs([folder], [], tmp_path / "scores")
    for quantity in ("request", "diversion"):
        assert any(row["kge"] < 1.0 - 1e-6 for row in rows
                   if row["kind"] == "llm" and row["quantity"] == quantity
                   and row["series"].startswith(("ub:", "lb:")) and row["kge"] is not None)


def test_score_runs_swapped_upper_basin_labels(inputs, tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / "swapped"
    write_scoring_run(folder, inputs, 42)
    upper = [p for p in inputs[0] if p.basin == "upper_basin"]
    first = upper[0]
    second = next(p for p in upper if p.precip_group != first.precip_group)
    swaps = {first.agent_id: second.precip_group, second.agent_id: first.precip_group}
    path = folder / "simulation_log.csv"
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["agent_id"] in swaps:
            row["ub_subbasin"] = swaps[row["agent_id"]]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    try:
        scores = score.score_runs([folder], [], tmp_path / "scores")
    except score.ScoreError as exc:
        assert "identit" in str(exc)
    else:
        for subbasin in (first.precip_group, second.precip_group):
            assert all(row["kge"] < 1.0 - 1e-6 for row in scores
                       if row["kind"] == "llm" and row["series"] == "ub:" + subbasin)


def test_score_runs_units_recorded_kaf_lb_af_and_simulated_af(inputs, tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / "units"
    write_scoring_run(folder, inputs, 42)
    recorded = score.recorded_series()
    simulated = score._load_run_series(folder, "llm")[0]
    ub = pd.read_csv(hv.UB_DEPLETION_CSV, index_col=0)
    lb = pd.read_csv(hv.LB_DIVERSION_CSV, index_col=0)
    for year in YEARS:
        for basin, frame, divisor in (("ub:", ub, 1000.0), ("lb:", lb, 1_000_000.0)):
            for name in frame.columns:
                expected = float(frame.loc[year, name]) / divisor
                assert recorded[basin + name][year] == pytest.approx(expected, rel=1e-12)
                for quantity in ("request", "diversion"):
                    assert simulated[quantity][basin + name][year] == pytest.approx(expected, rel=1e-12)
    rows = score.score_runs([folder], [], tmp_path / "scores")
    assert all(row["beta"] == pytest.approx(1.0, abs=1e-12) for row in rows
               if row["kind"] == "llm" and row["series"].startswith(("ub:", "lb:")))


@pytest.mark.parametrize("key,value", [("model", "different-fixture"), ("lb_non_ag_total_maf", 5.0),
                                       ("memory_engine_class", "other-memory")])
def test_scoring_rejects_mixed_configuration_across_arms(inputs, tmp_path, key, value):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    first, second = tmp_path / "strict", tmp_path / "disabled"
    write_scoring_run(first, inputs, 42)
    manifest = write_scoring_run(second, inputs, 42, arm="disabled")
    manifest[key] = value
    (second / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="mixed"):
        score.score_runs([first, second], [], tmp_path / "scores")


@pytest.mark.parametrize("key", ["model_digest", "cluster_method", "lb_non_ag_total_maf"])
def test_scoring_rejects_configuration_key_missing_in_both_runs(inputs, tmp_path, key):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folders = [tmp_path / "strict", tmp_path / "disabled"]
    for folder, arm in zip(folders, ("strict", "disabled")):
        manifest = write_scoring_run(folder, inputs, 42, arm=arm)
        del manifest[key]
        (folder / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="missing.*" + key):
        score.score_runs(folders, [], tmp_path / "scores")


def test_scoring_rejects_llm_fql_physical_mismatch(inputs, tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    llm, fql = tmp_path / "llm", tmp_path / "fql"
    write_scoring_run(llm, inputs, 42)
    manifest = write_scoring_run(fql, inputs, 42, kind="fql")
    manifest["lb_return_flow_fraction"] = 0.1
    (fql / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="mixed"):
        score.score_runs([llm], [fql], tmp_path / "scores")


@pytest.mark.parametrize("key", ["mead_initial_elevation", "lb_tributary_source"])
def test_scoring_rejects_fql_water_key_missing_in_both_runs(inputs, tmp_path, key):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folders = [tmp_path / "fql42", tmp_path / "fql43"]
    for folder, seed in zip(folders, (42, 43)):
        manifest = write_scoring_run(folder, inputs, seed, kind="fql")
        del manifest["water_system_config"][key]
        (folder / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="missing.*" + key):
        score.score_runs([], folders, tmp_path / "scores")


def test_scoring_rejects_llm_fql_tributary_source_mismatch(inputs, tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    llm, fql = tmp_path / "llm", tmp_path / "fql"
    write_scoring_run(llm, inputs, 42)
    manifest = write_scoring_run(fql, inputs, 42, kind="fql")
    manifest["water_system_config"]["lb_tributary_source"] = "different-source"
    (fql / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="mixed physical"):
        score.score_runs([llm], [fql], tmp_path / "scores")


def test_scoring_mock_refusal_and_every_output_label(inputs, tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / "mock"
    manifest = write_scoring_run(folder, inputs, 42)
    manifest["model"] = "mock"
    (folder / "reproducibility_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="--allow-mock"):
        score.score_runs([folder], [], tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
    rows = score.score_runs([folder], [], tmp_path / "allowed", allow_mock=True)
    warning = "mock run: scores have no meaning"
    assert all(row["warning"] == warning for row in rows)
    assert all(row["model"] == "mock" for row in rows if row["kind"] == "llm")
    with (tmp_path / "allowed" / score.SCORES_CSV).open(newline="", encoding="utf-8") as stream:
        assert all(row["warning"] == warning for row in csv.DictReader(stream))
    markdown = (tmp_path / "allowed" / score.REPORT_MD).read_text(encoding="utf-8")
    assert "mock" in markdown
    assert markdown.count(warning) >= 3


def test_scoring_lower_basin_summary_reports_convention_and_undefined_counts(tmp_path):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score
    from examples.irrigation_abm.analysis.v3_metrics import Kge

    varying = {year: float(year - 1990) for year in YEARS}
    constant = {year: 10.0 for year in YEARS}
    conventional = score._score(constant, varying)
    undefined = score._score(varying, constant)
    assert conventional.r == conventional.alpha == 0
    assert undefined.kge is None
    metrics = [conventional] * 2 + [undefined] * 3 + [Kge(1, 1, 1, 1, 19)] * 17
    rows = [score._row("fixture", "llm", "strict", "replay-fixture", 42,
                       f"lb:agent{index}", "request", metric)
            for index, metric in enumerate(metrics)]
    summary = score._lb_summary(rows, run="fixture", kind="llm", arm="strict",
                                model="replay-fixture", seed=42, quantity="request")
    assert summary["kge"] == 1.0
    assert summary["n"] == 19
    assert summary["convention_scored"] == 2
    assert summary["undefined"] == 3
    assert "2 of 22 agents convention-scored, 3 undefined" in summary["note"]
    sanity = score._row("recorded_replay", "sanity", "sanity", "not applicable", "",
                        "recorded_replay", "sanity", Kge(1, 1, 1, 1, 19))
    path = tmp_path / "counts.md"
    score._write_report([summary, sanity], path)
    markdown = path.read_text(encoding="utf-8")
    assert "2 convention, 3 undefined" in markdown
    assert markdown.count("Counts") == 3


@pytest.mark.parametrize("case", ["llm_arms", "fql_seeds", "llm_fql"])
def test_scoring_rejects_different_code_commits(inputs, tmp_path, case):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    first, second = tmp_path / "first", tmp_path / "second"
    first_kind = "fql" if case == "fql_seeds" else "llm"
    second_kind = "llm" if case == "llm_arms" else "fql"
    original = write_scoring_run(first, inputs, 42, kind=first_kind)
    changed = write_scoring_run(second, inputs, 43 if case == "fql_seeds" else 42,
                                kind=second_kind, arm="disabled")
    changed["git_head" if second_kind == "fql" else "git_commit"] = changed["hindcast"]["code_commit"] = "deadbeef"
    (second / score.MANIFEST).write_text(json.dumps(changed), encoding="utf-8")
    llm = [folder for folder, kind in ((first, first_kind), (second, second_kind)) if kind == "llm"]
    fql = [folder for folder, kind in ((first, first_kind), (second, second_kind)) if kind == "fql"]
    with pytest.raises(score.ScoreError) as caught:
        score.score_runs(llm, fql, tmp_path / "refused")
    message = str(caught.value)
    assert "commit" in message
    assert all(text in message for text in (str(first), str(second), original["hindcast"]["code_commit"], "deadbeef"))
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("kind", ["llm", "fql"])
@pytest.mark.parametrize("field", ["git_commit", "git_head", "git_commit_at_finalize"])
def test_scoring_rejects_conflicting_commit_fields(inputs, tmp_path, kind, field):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / kind
    manifest = write_scoring_run(folder, inputs, 42, kind=kind)
    manifest[field] = "deadbeef"
    (folder / score.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="commit") as caught:
        score.score_runs([folder] if kind == "llm" else [], [folder] if kind == "fql" else [],
                         tmp_path / "refused")
    assert all(text in str(caught.value) for text in
               (str(folder), "deadbeef", manifest["hindcast"]["code_commit"]))


@pytest.mark.parametrize("kind", ["llm", "fql"])
def test_scoring_rejects_missing_commit_fields(inputs, tmp_path, kind):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / kind
    manifest = write_scoring_run(folder, inputs, 42, kind=kind)
    commit = manifest.pop("git_head" if kind == "fql" else "git_commit")
    del manifest["hindcast"]["code_commit"]
    path = folder / score.MANIFEST
    path.write_text(json.dumps(manifest), encoding="utf-8")
    llm, fql = ([folder], []) if kind == "llm" else ([], [folder])
    with pytest.raises(score.ScoreError, match="missing.*commit"):
        score.score_runs(llm, fql, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
    for location, key in ((manifest, "git_commit"), (manifest, "git_head"),
                          (manifest["hindcast"], "code_commit")):
        location[key] = commit
        path.write_text(json.dumps(manifest), encoding="utf-8")
        assert score.score_runs(llm, fql, tmp_path / key)
        del location[key]


@pytest.mark.parametrize("kind", ["llm", "fql"])
@pytest.mark.parametrize("field", ["git_dirty", "hindcast.git_dirty", "git_dirty_at_finalize"])
def test_scoring_dirty_run_refused_and_labelled(inputs, tmp_path, kind, field):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / kind
    manifest = write_scoring_run(folder, inputs, 42, kind=kind)
    location = manifest["hindcast"] if field.startswith("hindcast.") else manifest
    location[field.split(".")[-1]] = True
    (folder / score.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    llm, fql = ([folder], []) if kind == "llm" else ([], [folder])
    with pytest.raises(score.ScoreError, match="--allow-dirty"):
        score.score_runs(llm, fql, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()
    assert score.main(["--" + kind, str(folder), "--out", str(tmp_path / "cli-refused")]) == 2
    out = tmp_path / "allowed"
    assert score.main(["--" + kind, str(folder), "--out", str(out), "--allow-dirty"]) == 0
    warning = "run from a modified tree"
    with (out / score.SCORES_CSV).open(newline="", encoding="utf-8") as stream:
        run_rows = [row for row in csv.DictReader(stream) if row["kind"] == kind]
    assert len(run_rows) == 68
    assert all(warning in row["warning"] for row in run_rows)
    tables = (out / score.REPORT_MD).read_text(encoding="utf-8").split("\n## ")[1:4]
    assert len(tables) == 3
    assert all(warning in table and str(folder.resolve()) in table for table in tables)


@pytest.mark.parametrize("kind", ["llm", "fql"])
def test_scoring_rejects_missing_dirty_fields(inputs, tmp_path, kind):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / kind
    manifest = write_scoring_run(folder, inputs, 42, kind=kind)
    del manifest["git_dirty"]
    del manifest["hindcast"]["git_dirty"]
    path = folder / score.MANIFEST
    path.write_text(json.dumps(manifest), encoding="utf-8")
    llm, fql = ([folder], []) if kind == "llm" else ([], [folder])
    with pytest.raises(score.ScoreError, match="missing.*dirty"):
        score.score_runs(llm, fql, tmp_path / "refused")
    for index, (location, key) in enumerate(((manifest, "git_dirty"),
                                           (manifest["hindcast"], "git_dirty"),
                                           (manifest, "git_dirty_at_finalize"))):
        location[key] = False
        path.write_text(json.dumps(manifest), encoding="utf-8")
        rows = score.score_runs(llm, fql, tmp_path / str(index))
        assert all(row["warning"] == "" for row in rows)
        del location[key]


@pytest.mark.parametrize("kind", ["llm", "fql"])
def test_scoring_mixed_dirty_seed_warning_survives_summary(inputs, tmp_path, kind):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    dirty, clean = tmp_path / "dirty", tmp_path / "clean"
    manifest = write_scoring_run(dirty, inputs, 42, kind=kind)
    write_scoring_run(clean, inputs, 43, kind=kind)
    manifest["git_dirty"] = True
    (dirty / score.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    llm, fql = ([dirty, clean], []) if kind == "llm" else ([], [dirty, clean])
    with pytest.raises(score.ScoreError, match="--allow-dirty"):
        score.score_runs(llm, fql, tmp_path / "refused")
    out = tmp_path / "allowed"
    warning = "run from a modified tree"
    for folders in ([dirty, clean], [clean, dirty]):
        rows = score.score_runs(folders if kind == "llm" else [], folders if kind == "fql" else [],
                                out, allow_dirty=True)
        assert all(warning in row["warning"] for row in rows if row["run"] == str(dirty.resolve()))
        assert all(warning not in row["warning"] for row in rows if row["run"] == str(clean.resolve()))
        tables = (out / score.REPORT_MD).read_text(encoding="utf-8").split("\n## ")[1:4]
        assert all(warning in table and str(dirty.resolve()) in table for table in tables)
        assert all(str(clean.resolve()) not in table for table in tables)
    if kind == "llm":
        for folder in (dirty, clean):
            path = folder / score.MANIFEST
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["model"] = "mock"
            path.write_text(json.dumps(manifest), encoding="utf-8")
        rows = score.score_runs(llm, [], out, allow_dirty=True, allow_mock=True)
        assert all(score.MOCK_WARNING in row["warning"] for row in rows)
        assert all(warning in row["warning"] for row in rows if row["run"] == str(dirty.resolve()))
        tables = (out / score.REPORT_MD).read_text(encoding="utf-8").split("\n## ")[1:4]
        assert all(warning in table and score.MOCK_WARNING in table for table in tables)


@pytest.mark.parametrize("kind", ["llm", "fql"])
@pytest.mark.parametrize("value", [None, "", 42])
def test_scoring_rejects_invalid_commit_values(inputs, tmp_path, kind, value):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / kind
    manifest = write_scoring_run(folder, inputs, 42, kind=kind)
    manifest["hindcast"]["code_commit"] = value
    (folder / score.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="commit"):
        score.score_runs([folder] if kind == "llm" else [], [folder] if kind == "fql" else [],
                         tmp_path / "refused")


@pytest.mark.parametrize("kind", ["llm", "fql"])
@pytest.mark.parametrize("value", [None, "false"])
def test_scoring_rejects_invalid_dirty_values(inputs, tmp_path, kind, value):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    folder = tmp_path / kind
    manifest = write_scoring_run(folder, inputs, 42, kind=kind)
    manifest["git_dirty"] = value
    (folder / score.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(score.ScoreError, match="dirty"):
        score.score_runs([folder] if kind == "llm" else [], [folder] if kind == "fql" else [],
                         tmp_path / "refused")


@pytest.mark.parametrize("dirty_kind,clean_kind", [("llm", "llm"), ("llm", "fql"), ("fql", "llm")])
def test_scoring_dirty_warning_does_not_label_clean_groups(inputs, tmp_path, dirty_kind, clean_kind):
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as score

    dirty, clean = tmp_path / "dirty", tmp_path / "clean"
    manifest = write_scoring_run(dirty, inputs, 42, kind=dirty_kind)
    write_scoring_run(clean, inputs, 43, kind=clean_kind, arm="disabled")
    manifest["git_dirty"] = True
    (dirty / score.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    llm = [folder for folder, kind in ((dirty, dirty_kind), (clean, clean_kind)) if kind == "llm"]
    fql = [folder for folder, kind in ((dirty, dirty_kind), (clean, clean_kind)) if kind == "fql"]
    with pytest.raises(score.ScoreError, match="--allow-dirty"):
        score.score_runs(llm, fql, tmp_path / "refused")
    out = tmp_path / "allowed"
    rows = score.score_runs(llm, fql, out, allow_dirty=True)
    assert all(row["warning"] == "" for row in rows if row["run"] == str(clean.resolve()))
    markdown = (out / score.REPORT_MD).read_text(encoding="utf-8")
    clean_prefix = "| disabled |" if clean_kind == "llm" else "| fql:calibrated |"
    clean_lines = [line for line in markdown.splitlines() if line.startswith(clean_prefix)]
    assert clean_lines and all("run from a modified tree" not in line for line in clean_lines)
    assert all(str(dirty.resolve()) in table and "run from a modified tree" in table
               for table in markdown.split("\n## ")[1:4])
