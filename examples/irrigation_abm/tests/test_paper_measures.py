"""Pre-registered paper measures: hand-computed cases and recorded replay."""
from __future__ import annotations

import csv
import dataclasses
import json
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.irrigation_abm.analysis import v3_metrics as vm


def measures():
    from examples.irrigation_abm.analysis import paper_measures
    return paper_measures


def decision(action=vm.KEEP, wsa="M", *, first=None, physical_ratio=1.0, year=1):
    return vm.Decision(
        agent_id="A", year=year, status="APPROVED", execution_path="approved",
        executed_skill=action, proposed_skill=first or action,
        attempts=(vm.Attempt(first or action, {"WSA_LABEL": wsa}, ()),),
        retry_count=0, format_retries=0, llm_success=True,
        keep_request_af=50.0, expected_at_keep_af=50.0,
        supply_ratio=1.0, physical_ratio=physical_ratio,
        first_wsa=wsa, first_aca="M", final_wsa="M", wsa_relabeled=False,
        error_messages="", timestamp="",
    )


@pytest.mark.parametrize("action,wsa,ratio,request_af,peak,expected", [
    (vm.INCREASE, "H", 1, 50, 80, {"TR1"}),
    (vm.INCREASE, "VH", 1, 50, 80, {"TR1"}),
    (vm.DECREASE, "L", 1, 50, 80, {"TR3"}),
    (vm.DECREASE, "VL", 1, 50, 80, {"TR3"}),
    (vm.INCREASE, "M", 0.9, 50, 80, {"supply"}),
    (vm.INCREASE, "M", 1, 80.5001, 80, {"limit"}),
    (vm.INCREASE, "M", 1, 100.5001, 200, {"limit", "right"}),
    (vm.DECREASE, "M", 1, 9.4999, 80, {"floor"}),
    (vm.INCREASE, "M", 1, 80.5, 80, set()),
    (vm.INCREASE, "M", 1, 100.5, 200, set()),
    (vm.DECREASE, "M", 1, 9.5, 80, set()),
    (vm.INCREASE, "L", vm.FULL_SUPPLY_RATIO, 50, 80, set()),
    (vm.DECREASE, "H", 0.1, 50, 80, set()),
    (vm.KEEP, "VH", 0.1, 101, 80, set()),
])
def test_rule_predicates(action, wsa, ratio, request_af, peak, expected):
    flags = measures().rule_flags(decision(action, wsa, physical_ratio=ratio),
                                  request_af, 100.0, peak)
    assert {name for name, value in flags.items() if value} == expected


def test_first_scarcity_and_full_rules_ignore_retired_exception():
    d = dataclasses.replace(decision(vm.INCREASE, "H"),
                            final_wsa="L", tier_cut_restore_enabled=True,
                            previous_gap_reason="lb_junior_tier_cut",
                            previous_request_af=100)
    assert measures().rule_flags(d, 50, 100, 80)["TR1"] is True


def test_overlap_first_proposal_and_executed_denominator():
    ds = [decision(vm.INCREASE, "H", year=1),
          decision(vm.KEEP, "H", first=vm.INCREASE, year=2),
          dataclasses.replace(decision(year=3), executed_skill=None,
                              execution_path="aborted")]
    rows = {("A", y): {"request": 81, "water_right": 100} for y in (1, 2, 3)}
    result = measures().ibr_summary(ds, rows, {"A": 80})
    assert result["n"] == 2
    assert result["n_aborted"] == 1
    assert result["ibr_count"] == 1
    assert result["ibr_pct"] == 50
    assert result["TR1_count"] == result["limit_count"] == 1
    assert result["first_behavioural_count"] == 2
    assert result["first_behavioural_pct"] == 100
    assert result["physical_excluding_supply_pct"] == 50  # over executed decisions, not all three


def test_physical_overlap_counts_once_per_executed_decision():
    d = decision(vm.INCREASE, "M", physical_ratio=0.9)
    result = measures().ibr_summary([d], {("A", 1): {"request": 101, "water_right": 100}},
                                   {"A": 80})
    assert result["physical_count"] == result["ibr_count"] == 1
    assert result["physical_ibr_pct"] == result["ibr_pct"] == 100
    assert result["supply_count"] == result["limit_count"] == result["right_count"] == 1
    assert result["physical_excluding_supply_count"] == 1


def test_first_proposal_is_distinct_from_final_keep():
    d = dataclasses.replace(decision(vm.KEEP, "H", first=vm.INCREASE), attempts=(
        vm.Attempt(vm.INCREASE, {"WSA_LABEL": "H"}, ()),
        vm.Attempt(vm.KEEP, {"WSA_LABEL": "H"}, ())))
    assert d.first_proposal == vm.INCREASE and d.final_proposal == vm.KEEP
    result = measures().ibr_summary([d], {("A", 1): {"request": 50, "water_right": 100}},
                                   {"A": 80})
    assert result["first_behavioural_count"] == 1
    assert result["first_behavioural_pct"] == 100
    assert result["ibr_count"] == 0


def test_fql_behavioural_not_applicable_and_missing_supply_is_unknown():
    d = decision(vm.INCREASE, None, physical_ratio=None)
    result = measures().ibr_summary([d], {("A", 1): {"request": 81, "water_right": 100}},
                                   {"A": 80}, behavioural=False)
    assert result["behavioural_ibr_pct"] is None
    assert result["ibr_count"] is result["ibr_pct"] is None
    assert result["ibr_scope"] == "not applicable"
    assert result["behavioural_note"] == "not applicable"
    assert result["first_behavioural_count"] is None
    assert result["supply_count"] is None
    assert result["limit_count"] == 1
    assert result["physical_ibr_pct"] is None
    assert "supply" in result["physical_note"]
    assert result["physical_excluding_supply_count"] == 1
    assert result["physical_excluding_supply_pct"] == 100
    assert "excluding supply" in result["physical_excluding_supply_note"]


def test_fql_physical_when_supply_is_logged():
    d = decision(vm.INCREASE, None, physical_ratio=0.9)
    result = measures().ibr_summary([d], {("A", 1): {"request": 50, "water_right": 100}},
                                   {"A": 80}, behavioural=False)
    assert result["physical_ibr_pct"] == 100
    assert result["supply_count"] == 1
    assert result["ibr_scope"] == "not applicable"
    assert result["ibr_count"] is result["ibr_pct"] is None
    assert result["physical_excluding_supply_count"] == 0


def test_fql_union_excluding_supply_counts_overlapping_bounds_once():
    ds = [decision(vm.INCREASE, None, physical_ratio=None, year=1),
          decision(vm.DECREASE, None, physical_ratio=None, year=2)]
    rows = {("A", 1): {"request": 101, "water_right": 100},
            ("A", 2): {"request": 9, "water_right": 100}}
    result = measures().ibr_summary(ds, rows, {"A": 80}, behavioural=False)
    assert result["ibr_count"] is result["ibr_pct"] is None
    assert result["physical_count"] is result["supply_count"] is None
    assert result["limit_count"] == result["right_count"] == result["floor_count"] == 1
    assert result["physical_excluding_supply_count"] == 2
    assert result["physical_excluding_supply_pct"] == 100


@pytest.mark.parametrize("actions,expected,shares", [
    ([vm.KEEP] * 3, 0, (0, 1, 0)),
    ([vm.INCREASE, vm.KEEP, vm.DECREASE], 1, (1/3, 1/3, 1/3)),
    ([vm.INCREASE, vm.DECREASE], math.log2(2)/math.log2(3), (0.5, 0, 0.5)),
])
def test_entropy(actions, expected, shares):
    result = measures().action_entropy(actions)
    assert result["ehe"] == pytest.approx(expected)
    assert tuple(result[f"{name}_share"] for name in ("increase", "keep", "decrease")) == pytest.approx(shares)


def test_entropy_empty_and_invalid():
    assert measures().action_entropy([])["ehe"] is None
    with pytest.raises(vm.MetricsError, match="action"):
        measures().action_entropy(["unknown"])


def test_hand_computed_hindcast_scores():
    # At least the repository KGE's minimum number of years; sim = ref + 2.
    years = list(range(2001, 2001 + vm.KGE_MIN_YEARS))
    obs = [1000 + 10 * i for i in range(len(years))]
    result = measures().hindcast_scores(years, [x + 2 for x in obs], obs,
                                        [0, 1] + [0] * (len(years) - 2))
    beta = (sum(obs)/len(obs) + 2)/(sum(obs)/len(obs))
    assert result["kge"] == pytest.approx(1 - abs(beta - 1))
    assert result["r"] == pytest.approx(1)
    assert result["alpha"] == pytest.approx(1)
    assert result["beta"] == pytest.approx(beta)
    assert result["mae_ft"] == result["bias_ft"] == result["max_abs_departure_ft"] == 2
    assert result["max_abs_departure_date"] == "2001-01-01"
    assert result["n_above_19_9_ft"] == 0
    assert result["n_shortage_years"] == 1


def test_hindcast_threshold_and_invalid_series():
    # Subtracting zero preserves the exact same float as the threshold literal.
    result = measures().hindcast_scores([2001, 2002, 2003], [19.9, 20, -19.9], [0, 0, 0], [0, 2, 0])
    assert result["n_above_19_9_ft"] == 1
    assert result["max_abs_departure_date"] == "2002-01-01"
    for years, sim, obs, tiers in [([2001], [], [1], [0]),
                                    ([2001, 2001], [1, 2], [1, 2], [0, 0]),
                                    ([2001], [float("nan")], [1], [0])]:
        with pytest.raises(vm.MetricsError):
            measures().hindcast_scores(years, sim, obs, tiers)


def test_largest_departure_uses_absolute_value():
    result = measures().hindcast_scores([2001, 2002], [975, 1010], [1000, 1000], [0, 0])
    assert result["max_abs_departure_ft"] == 25
    assert result["max_abs_departure_date"] == "2001-01-01"


def test_recorded_replay_regression():
    rows = measures().hindcast_references()
    assert [r["run"] for r in rows] == ["recorded_diversion_replay", "keep_1999", "request_B", "constant_level_jan1_2000"]
    recorded = rows[0]
    assert recorded["mae_ft"] == pytest.approx(10.24, abs=0.005)
    assert recorded["max_abs_departure_ft"] == pytest.approx(19.86, abs=0.005)
    assert recorded["max_abs_departure_date"] == "2003-01-01"
    assert recorded["n_years"] == 19
    assert recorded["scored_dates"].split(";") == [f"{y}-01-01" for y in range(2001, 2020)]
    assert recorded["n_above_19_9_ft"] == 0
    for row, mae, maximum, date in [(rows[1], 15.87, 30.55, "2015-01-01"),
                                     (rows[2], 67.49, 141.89, "2018-01-01")]:
        assert row["mae_ft"] == pytest.approx(mae, abs=0.005)
        assert row["max_abs_departure_ft"] == pytest.approx(maximum, abs=0.005)
        assert row["max_abs_departure_date"] == date
    assert all(isinstance(row["git_dirty"], bool) for row in rows)


def test_constant_level_benchmark():
    from examples.irrigation_abm.analysis import hindcast_v3 as hv
    record = hv.load_observed()
    row = measures().hindcast_references()[-1]
    anchor = record[1999]["mead_elev_ft_eoy"]
    obs = [record[y]["mead_elev_ft_eoy"] for y in range(2000, 2019)]
    errors = [abs(anchor - value) for value in obs]
    beta = anchor / (sum(obs) / len(obs))
    assert row["run"] == "constant_level_jan1_2000"
    assert row["r"] == row["alpha"] == 0
    assert row["beta"] == pytest.approx(beta)
    assert row["kge"] == pytest.approx(1 - math.sqrt(2 + (beta - 1)**2))
    assert row["kge_note"] == vm.CONSTANT_SIM_NOTE
    assert row["mae_ft"] == pytest.approx(sum(errors) / 19)
    assert row["bias_ft"] == pytest.approx(sum(anchor - value for value in obs) / 19)
    assert row["max_abs_departure_ft"] == max(errors)
    assert row["max_abs_departure_date"] == f"{2001 + errors.index(max(errors))}-01-01"
    assert row["n_above_19_9_ft"] == sum(error > 19.9 for error in errors)
    assert row["n_shortage_years"] == 0


def fql_fixture(tmp_path, monkeypatch):
    path = tmp_path / "fql"
    path.mkdir()
    # The executed action is `yearly_decision`; the raw FQL proposal differs in year 2 (increase proposed,
    # keep executed), so reading `fql_raw_skill` instead would change the mix and fail the EHE assertion.
    rows = {("A", y): {"yearly_decision": action, "request": 50, "water_right": 100,
                       "fql_raw_skill": vm.INCREASE if action == vm.KEEP else action}
            for y, action in enumerate((vm.INCREASE, vm.KEEP, vm.DECREASE), 1)}
    info = vm.RunInfo(path, "fql", "fql", 42, {"git_head": "a" * 40})
    run = vm.LoadedRun(info, SimpleNamespace(rows=rows, agents=("A",)))
    monkeypatch.setattr(vm, "load_run", lambda *args, **kwargs: run)
    return path


def test_projection_fql_logs_final_action(tmp_path, monkeypatch):
    path = fql_fixture(tmp_path, monkeypatch)
    result = measures().projection_run(path, profiles=[SimpleNamespace(agent_id="A", peak_obs_af=80)])
    assert result["ehe"] == pytest.approx(1)
    assert result["behavioural_ibr_pct"] is None
    assert result["physical_ibr_pct"] is None
    assert result["run"] == "fql" and result["commit"] == "a" * 40


def write_hindcast(path, *, offset_year=2006, offset_ft=7):
    from examples.irrigation_abm.analysis import hindcast_v3 as hv
    from examples.irrigation_abm.hindcast_env import hindcast_provenance, hindcast_config_kwargs
    path.mkdir()
    config = vm.WaterSystemConfig(**hindcast_config_kwargs())
    (path / vm.MANIFEST).write_text(json.dumps({"runner": vm.FQL_RUNNER, "seed": 42,
        "git_head": "b" * 40, "fql_init": "calibrated", "git_dirty": False,
        "hindcast": hindcast_provenance(config, fql_init="calibrated",
                                         code_commit="b"*40, git_dirty=False)}))
    record = hv.load_observed()
    with (path / vm.SIM_LOG).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["agent_id", "year", "calendar_year",
                                                    "mead_storage_end_maf", "shortage_tier"])
        writer.writeheader()
        for loop, year in enumerate(range(2000, 2019), 1):
            for aid in ("A", "B"):
                writer.writerow(dict(agent_id=aid, year=loop, calendar_year=year,
                                     mead_storage_end_maf=hv.mead_total_maf(
                                         record[year]["mead_elev_ft_eoy"] +
                                         (offset_ft if year == offset_year else 0)),
                                     shortage_tier=int(loop == 19)))


def test_hindcast_run_dates_final_storage_and_read_only(tmp_path):
    path = tmp_path / "fql_hindcast"
    write_hindcast(path)
    before = {p.name: p.read_bytes() for p in path.iterdir()}
    result = measures().hindcast_run(path)
    assert result["scored_dates"].split(";")[0] == "2001-01-01"
    assert result["scored_dates"].split(";")[-1] == "2019-01-01"
    assert result["n_shortage_years"] == 1
    assert result["mae_ft"] == pytest.approx(7 / 19, abs=1e-10)
    assert result["max_abs_departure_ft"] == pytest.approx(7)
    assert result["max_abs_departure_date"] == "2007-01-01"
    assert result["commit"] == "b" * 40
    assert result["git_dirty"] is False
    assert {p.name: p.read_bytes() for p in path.iterdir()} == before


def test_hindcast_rejects_projection_and_disagreement(tmp_path):
    path = tmp_path / "bad"
    write_hindcast(path)
    manifest_path = path / vm.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    del manifest["hindcast"]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(vm.MetricsError, match="hindcast"):
        measures().hindcast_run(path)
    from examples.irrigation_abm.hindcast_env import hindcast_provenance, hindcast_config_kwargs
    manifest["hindcast"] = hindcast_provenance(vm.WaterSystemConfig(**hindcast_config_kwargs()),
        fql_init="calibrated", code_commit="b"*40, git_dirty=False)
    manifest_path.write_text(json.dumps(manifest))
    log = path / vm.SIM_LOG
    with log.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[1]["mead_storage_end_maf"] = float(rows[1]["mead_storage_end_maf"]) + 1
    with log.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    with pytest.raises(vm.MetricsError, match="differ"):
        measures().hindcast_run(path)


@pytest.mark.parametrize("section,key,value,match", [
    ("hindcast", "observed_csv_sha256", "bad", "observed_csv_sha256"),
    ("hindcast", "precip_csv_sha256", "bad", "precip_csv_sha256"),
    ("hindcast", "precip_source_sha256", "bad", "precip_source_sha256"),
    ("hindcast", "mead_levels_sha256", "bad", "mead_levels_sha256"),
    ("hindcast", "ub_depletion_sha256", "bad", "historical pin"),
    ("hindcast", "lb_diversion_sha256", "bad", "historical pin"),
    ("hindcast", "anchor_year", 2000, "anchor_year"),
    ("hindcast", "fql_trained_through", 2017, "fql_trained_through"),
    (None, "fql_init", "cold", "calibrated"),
    ("hindcast", "code_commit", "c"*40, "conflicting code commits"),
    ("hindcast", "git_dirty", "false", "boolean dirty-tree"),
])
def test_hindcast_validates_provenance(tmp_path, section, key, value, match):
    path = tmp_path / "historical"
    write_hindcast(path)
    manifest_path = path / vm.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    (manifest[section] if section else manifest)[key] = value
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(vm.MetricsError, match=match):
        measures().hindcast_run(path)


def test_hindcast_requires_dirty_flag_and_preserves_dirty_true(tmp_path):
    path = tmp_path / "historical"
    write_hindcast(path)
    manifest_path = path / vm.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["hindcast"]["git_dirty"] = True
    manifest_path.write_text(json.dumps(manifest))
    assert measures().hindcast_run(path)["git_dirty"] is True
    del manifest["git_dirty"], manifest["hindcast"]["git_dirty"]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(vm.MetricsError, match="missing dirty-tree"):
        measures().hindcast_run(path)


@pytest.mark.parametrize("key,value", [("lb_non_ag_total_maf", 6),
    ("powell_release_mode", "observed"), ("lb_return_flow_fraction", 0.2)])
def test_cli_refuses_mismatched_reference_physics(tmp_path, key, value):
    path = tmp_path / "historical"
    write_hindcast(path)
    manifest_path = path / vm.MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["hindcast"][key] = value
    manifest_path.write_text(json.dumps(manifest))
    out = tmp_path / "out.csv"
    with pytest.raises(vm.MetricsError, match=key):
        measures().main(["hindcast", "--runs", str(path), "--out", str(out)])
    assert not out.exists()


def test_projection_reads_floor_fraction_and_refuses_config_mismatch(tmp_path, monkeypatch):
    path = fql_fixture(tmp_path, monkeypatch)
    run = vm.load_run(path)
    config_fraction = vm.WaterSystemConfig().min_utilisation_fraction
    run.info.manifest["min_utilisation_fraction"] = str(config_fraction)
    run.sim.rows[("A", 3)]["request"] = config_fraction * 100 - 0.6
    profiles = [SimpleNamespace(agent_id="A", peak_obs_af=80)]
    assert measures().projection_run(path, profiles=profiles)["floor_count"] == 1
    run.info.manifest["min_utilisation_fraction"] = config_fraction + 0.1
    with pytest.raises(vm.MetricsError, match="min_utilisation_fraction"):
        measures().projection_run(path, profiles=profiles)


def test_projection_refuses_nested_floor_mismatch(tmp_path, monkeypatch):
    path = fql_fixture(tmp_path, monkeypatch)
    vm.load_run(path).info.manifest["water_system_config"] = {"min_utilisation_fraction": 0.2}
    with pytest.raises(vm.MetricsError, match="water_system_config.*min_utilisation_fraction"):
        measures().projection_run(path, profiles=[SimpleNamespace(agent_id="A", peak_obs_af=80)])


def test_cli_both_commands_and_protects_run_folders(tmp_path, monkeypatch):
    pm = measures()
    path = fql_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(pm, "_profiles", lambda run: [SimpleNamespace(agent_id="A", peak_obs_af=80)])
    out = tmp_path / "projection.csv"
    assert pm.main(["projection", "--runs", str(path), "--out", str(out)]) == 0
    with out.open() as stream:
        assert list(csv.DictReader(stream))[0]["run"] == "fql"
    with pytest.raises(vm.MetricsError, match="run folder"):
        pm.main(["projection", "--runs", str(path), "--out", str(path / "metrics.csv")])
    historical = tmp_path / "historical"
    write_hindcast(historical)
    out = tmp_path / "hindcast.csv"
    monkeypatch.setattr(pm, "hindcast_references", lambda **kwargs: [{"run": "reference", "commit": "c"*40}])
    assert pm.main(["hindcast", "--runs", str(historical), "--out", str(out)]) == 0
    with out.open() as stream:
        assert [r["run"] for r in csv.DictReader(stream)] == ["historical", "reference"]
