"""Executed baseline actions and append-only compatibility with the old runner."""
import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from examples.single_agent import run_flood_rulebased as rb
from examples.single_agent.analysis import paper_measures as pm


NEW_COLUMNS = ("executed_action", "elevated_before", "relocated_before")
LEGACY = Path(__file__).parent / "fixtures/flood_rulebased_seed42_legacy.txt"


def legacy_bytes():
    """The fixture with LF line ends: a Windows checkout (core.autocrlf) turns them into CRLF."""
    return LEGACY.read_bytes().replace(b"\r\n", b"\n")


def short_run(tmp_path, monkeypatch):
    profiles = rb.pd.DataFrame([
        dict(id=f"A{i}", elevated=i == 1, has_insurance=i % 2 == 0,
             relocated=i == 0, flood_threshold=0.8, trust_in_insurance=0.4,
             trust_in_neighbors=0.5, memory="")
        for i in range(8)
    ])
    profiles.to_csv(tmp_path / "agent_initial_profiles.csv", index=False)
    rb.pd.DataFrame({"Flood_Years": [1, 2, 3, 4]}).to_csv(tmp_path / "flood_years.csv", index=False)
    monkeypatch.setattr(rb, "__file__", str(tmp_path / "runner.py"))
    monkeypatch.setattr(rb, "NUM_YEARS", 4)
    monkeypatch.setattr(rb, "rng", rb.np.random.default_rng(42))
    return rb.run()[0]


def test_existing_columns_are_byte_identical_to_untouched_runner(tmp_path, monkeypatch):
    frame = short_run(tmp_path, monkeypatch)
    assert tuple(frame.columns[-3:]) == NEW_COLUMNS
    # Both sides with LF line ends: pandas writes os.linesep on Windows, and a checkout may convert the fixture.
    assert frame.drop(columns=list(NEW_COLUMNS)).to_csv(index=False, lineterminator="\n").encode() == legacy_bytes()
    # Final PCG64 state recorded from the untouched runner, same inputs and seed.
    assert rb.rng.bit_generator.state == {
        "bit_generator": "PCG64", "has_uint32": 0, "uinteger": 0,
        "state": {"inc": 332724090758049132448979897138935081983,
                  "state": 190529239273649073813237551818912421220},
    }


def test_one_executed_action_per_active_household_year(tmp_path, monkeypatch):
    frame = short_run(tmp_path, monkeypatch)
    before = {f"A{i}": (i == 1, i == 0) for i in range(8)}
    for _, row in frame.iterrows():
        elevated, relocated = before[row.agent_id]
        assert bool(row.elevated_before) == elevated
        assert bool(row.relocated_before) == relocated
        if relocated:
            assert row.executed_action == ""
            assert row.decision == "Already relocated"
        else:
            assert row.executed_action in pm.ACTIONS
            if row.executed_action == "elevate_house":
                assert not elevated and bool(row.elevated)
            if row.executed_action == "relocate":
                assert bool(row.relocated)
            if row.executed_action == "buy_insurance":
                assert bool(row.has_insurance)
        before[row.agent_id] = (bool(row.elevated), bool(row.relocated))
    frame.to_csv(tmp_path / "simulation_log.csv", index=False)
    result = pm.projection_run(tmp_path)
    active = frame[~frame.relocated_before]
    assert result["n"] == len(active) == 28
    assert result["n_no_decision"] == 4
    assert result["R5_count"] == result["physical_count"] == 0
    assert result["ibr_scope"] == "not applicable"
    assert result["ibr_executed_pct"] is None
    for action in pm.ACTIONS:
        assert result[f"{action}_share"] == pytest.approx((active.executed_action == action).mean())
    for year in range(1, 5):
        assert result[f"year_{year}_n"] == 7


def test_same_year_relocation_counts_and_retained_insurance_is_not_action(tmp_path, monkeypatch):
    class ScriptedRng:
        choices = iter(["Insurance", "Elevate", "Relocate", "DoNothing",
                        "Insurance", "DoNothing", "DoNothing"])

        def random(self):
            return 0.0

        def choice(self, options, p):
            action = next(self.choices, "DoNothing")
            assert action in options
            return action

    short_run(tmp_path, monkeypatch)  # create the same controlled input profiles
    monkeypatch.setattr(rb, "rng", ScriptedRng())
    frame, _ = rb.run()
    elevated = frame[(frame.agent_id == "A2") & (frame.year == 1)].iloc[0]
    assert elevated.executed_action == "elevate_house" and bool(elevated.has_insurance)
    moving = frame[(frame.agent_id == "A3") & (frame.year == 1)].iloc[0]
    assert moving.executed_action == "relocate" and not bool(moving.relocated_before)
    later = frame[(frame.agent_id == "A3") & (frame.year > 1)]
    assert all(later.relocated_before) and all(later.executed_action == "")
    frame.to_csv(tmp_path / "simulation_log.csv", index=False)
    result = pm.projection_run(tmp_path)
    assert result["n"] == 25 and result["n_no_decision"] == 7
    assert result["year_1_n"] == 7 and result["year_2_n"] == 6
    assert result["relocate_share"] == pytest.approx(1 / 25)


def write_log(tmp_path, rows):
    path = tmp_path / "simulation_log.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def record(action="do_nothing", **changes):
    row = dict(agent_id="A", year="1", decision="Do Nothing", elevated="False",
               executed_action=action, elevated_before="False", relocated_before="False")
    row.update(changes)
    return row


def test_recorded_mix_r5_and_yearly_denominators(tmp_path):
    rows = [record(action, agent_id=f"A{i}", elevated_before=str(action == "elevate_house"),
                   elevated=str(action == "elevate_house")) for i, action in enumerate(pm.ACTIONS)]
    rows.append(record("", agent_id="A2", year="2", decision="Already relocated", relocated_before="True"))
    write_log(tmp_path, rows)
    result = pm.projection_run(tmp_path)
    assert result["n"] == 4 and result["n_no_decision"] == 1
    assert result["physical_count"] == result["R5_count"] == 1
    assert result["physical_ibr_pct"] == 25
    assert result["ehe"] == result["year_1_ehe"] == 1
    assert all(result[f"{action}_share"] == 0.25 for action in pm.ACTIONS)
    assert result["year_2_n"] == 0 and result["year_2_ehe"] is None
    assert result["ibr_executed_count"] is result["behavioural_count"] is None


@pytest.mark.parametrize("changes,match", [
    ({"executed_action": ""}, "action"),
    ({"executed_action": "Only House Elevation"}, "action"),
    ({"elevated_before": "maybe"}, "boolean"),
    ({"relocated_before": ""}, "boolean"),
    ({"relocated_before": "True"}, "no decision"),
])
def test_rulebased_reader_refuses_corrupt_decision_evidence(tmp_path, changes, match):
    write_log(tmp_path, [record(**changes)])
    with pytest.raises(pm.MetricsError, match=match):
        pm.projection_run(tmp_path)


def test_rulebased_reader_refuses_partial_and_duplicate_records(tmp_path):
    row = record()
    row.pop("elevated_before")
    write_log(tmp_path, [row])
    with pytest.raises(pm.MetricsError, match="missing"):
        pm.projection_run(tmp_path)
    write_log(tmp_path, [record(), record()])
    with pytest.raises(pm.MetricsError, match="duplicate"):
        pm.projection_run(tmp_path)


def test_old_format_keeps_unavailable_result(tmp_path):
    (tmp_path / "simulation_log.csv").write_bytes(legacy_bytes())
    result = pm.projection_run(tmp_path)
    assert result["n"] is result["ehe"] is result["physical_count"] is None
    assert "unavailable" in result["action_note"]


def test_projection_cli_mixes_new_and_old_baselines(tmp_path):
    new, old = tmp_path / "new", tmp_path / "old"
    new.mkdir()
    old.mkdir()
    write_log(new, [record("buy_insurance")])
    (old / "simulation_log.csv").write_bytes(legacy_bytes())
    output = tmp_path / "projection.csv"
    assert pm.main(["projection", "--runs", str(new), str(old), "--out", str(output)]) == 0
    rows = list(csv.DictReader(io.StringIO(output.read_text())))
    assert rows[0]["buy_insurance_share"] == "1.0"
    assert rows[1]["buy_insurance_share"] == ""


def test_cli_records_versioned_logging_provenance(tmp_path):
    script = Path(rb.__file__).resolve()
    result = subprocess.run(
        [sys.executable, str(script), "--seed", "42", "--output", str(tmp_path)],
        cwd=tmp_path, env={**os.environ, "MPLBACKEND": "Agg"},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((tmp_path / "reproducibility_manifest.json").read_text())
    assert manifest["kind"] == "rulebased" and manifest["seed"] == 42
    assert manifest["simulation_log_schema_version"] == 2
    assert manifest["simulation_log"]["added_columns"] == list(NEW_COLUMNS)
    assert set(manifest["simulation_log"]["executed_actions"]) == set(pm.ACTIONS)
    assert pm.projection_run(tmp_path)["n"] > 0
