"""
Tests for the water-right history-anchor (2026-09-26).

Change 1: create_profiles_from_data's water_right ceiling becomes
min(grid_top_af, (1 + paper_water_margin) * peak_obs_af) for every agent
in both basins, instead of always the top of the H&Y discretisation grid.
Change 2: the AZ_UB state group's historical-column lookup bug (the CSV
column is "AZ", not "AZ_UB") is fixed.
Change 3: run_fql_baseline.py's FQL path shares the same profile
water_right / IrrigationEnvironment.execute_skill() clip as the LLM path.

Real-data tests (b), (c) need the full ref/CRSS_DB tree and skip cleanly
when it is not present in this worktree -- the same resolution
run_experiment.py --real uses (PROJECT_ROOT / "ref", PROJECT_ROOT two
levels above run_experiment.py / three levels above this tests/ file).
CI has no ref data, so those tests are expected to skip there.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import pytest

# Same PROJECT_ROOT convention as test_coupling.py / test_fql_baseline.py
# (tests/ -> irrigation_abm -> examples -> repo root), matching
# run_experiment.py's own `Path(__file__).resolve().parents[2]` one level
# closer to the repo root (run_experiment.py lives one directory up from
# this tests/ file).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.irrigation_personas import (
    create_profiles_from_data,
    IrrigationAgentProfile,
    _UB_STATE_GROUPS,
    _UB_HIST_COLUMN_BY_GROUP,
)
from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
from examples.irrigation_abm.run_experiment import _record_paper_water_margin_provenance
from examples.irrigation_abm.run_fql_baseline import create_fql_agents
from broker.interfaces.skill_types import ApprovedSkill

# ---------------------------------------------------------------------------
# Real-ref-data availability (mirrors run_experiment.py --real's own
# resolution: PROJECT_ROOT / "ref" / "CRSS_DB" / "CRSS_DB", plus the
# RL-ABM-CRSS params CSV).
# ---------------------------------------------------------------------------
REF_DIR = PROJECT_ROOT / "ref"
CRSS_DB_DIR = REF_DIR / "CRSS_DB" / "CRSS_DB"
PARAMS_CSV = REF_DIR / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"


def _real_ref_available() -> bool:
    needed = [
        PARAMS_CSV,
        CRSS_DB_DIR / "Div_States" / "UB_discrete_states.csv",
        CRSS_DB_DIR / "Div_States" / "LB_discrete_states.csv",
        CRSS_DB_DIR / "Group_Agt" / "UB_ABM_Groups_and_Agents.csv",
        CRSS_DB_DIR / "HistoricalData" / "UB_historical_annual_depletion.csv",
        CRSS_DB_DIR / "HistoricalData" / "LB_historical_annual_diversion.csv",
    ]
    return all(p.is_file() for p in needed)


requires_real_ref = pytest.mark.skipif(
    not _real_ref_available(),
    reason="ref/CRSS_DB real data not present in this worktree (same resolution "
           "as run_experiment.py --real); CI has no ref data, skip is expected.",
)


# ---------------------------------------------------------------------------
# (a) Synthetic profile test of the ceiling formula
# ---------------------------------------------------------------------------
def _write_ub_agent_group_fixture(path: Path) -> None:
    """Minimal Group_Agt/UB_ABM_Groups_and_Agents.csv: one row, 58 slots.

    _build_ub_state_group_map only needs len(agent_names) == 58 (the sum of
    _UB_GROUP_AGENT_COUNTS); the row's own group label and slot names are
    never read back by the water_right formula this test exercises (the
    synthetic UB_discrete_states.csv fixture below uses a single unrelated
    "dummy" column with grid_top 0, so every UB agent is skipped as
    inactive before any group lookup happens). This file only exists to
    satisfy the module-level assertion in _build_ub_state_group_map.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["G"] + [str(i) for i in range(58)])


def _write_synthetic_ref(tmp_path: Path) -> Path:
    """Build a minimal ref/CRSS_DB/CRSS_DB tree with two LB agents:

    - LB_Below: grid_top (1000) below (1 + margin) * peak (1260 at
      margin=0.4) -> keeps the grid top, source "grid_top".
    - LB_Above: grid_top (5000) above (1 + margin) * peak (1260) ->
      capped, source "peak_scaled".

    Both agents share the same 1971/2018 historical series (peak 900,
    2018 use 700) so only grid_top differs between the two branches. A
    UB historical file is still written (Review P2: both historical files
    are now required even when, as here, every UB agent is inactive).
    """
    crss_db_dir = tmp_path / "CRSS_DB" / "CRSS_DB"
    (crss_db_dir / "Div_States").mkdir(parents=True, exist_ok=True)
    (crss_db_dir / "HistoricalData").mkdir(parents=True, exist_ok=True)

    # LB discrete-states grid: 5-point linspace(0, grid_top)
    lb_states = pd.DataFrame({
        "LB_Below": np.linspace(0, 1000, 5),
        "LB_Above": np.linspace(0, 5000, 5),
    })
    lb_states.to_csv(crss_db_dir / "Div_States" / "LB_discrete_states.csv", index=False)

    # UB discrete-states grid: one inactive ("dummy") column, skipped
    # before any group lookup (grid_top <= 0).
    ub_states = pd.DataFrame({"dummy": [0.0]})
    ub_states.to_csv(crss_db_dir / "Div_States" / "UB_discrete_states.csv", index=False)

    _write_ub_agent_group_fixture(crss_db_dir / "Group_Agt" / "UB_ABM_Groups_and_Agents.csv")

    # LB historical series: peak 900 (in 1971), 2017 use 700, 2018 use
    # 700, both agents. 2017 row required (mirrors the 2018 check,
    # P1-b/(v) 2026-09-27 review) even though this fixture's tests don't
    # exercise the FQL calibrated warm-start itself.
    lb_hist = pd.DataFrame(
        {"LB_Below": [900.0, 700.0, 700.0], "LB_Above": [900.0, 700.0, 700.0]},
        index=[1971, 2017, 2018],
    )
    lb_hist.to_csv(crss_db_dir / "HistoricalData" / "LB_historical_annual_diversion.csv")

    # UB historical file (Review P2: required even with no active UB
    # agents) -- one row per required column, all values irrelevant here.
    # 2017 row required alongside 2018 (P1-b/(v) 2026-09-27 review).
    ub_hist = pd.DataFrame(
        {sg_col: [0.0, 0.0] for sg_col in {"WY", "UT1", "UT2", "UT3", "NM", "CO1", "CO2", "CO3", "AZ"}},
        index=[2017, 2018],
    )
    ub_hist.to_csv(crss_db_dir / "HistoricalData" / "UB_historical_annual_depletion.csv")

    # FQL params CSV: index = parameter rows, columns = agent names.
    params = pd.DataFrame(
        {
            "LB_Below": [0.20, 0.70, 0.75, 0.70, 0.15, 1.50, "TRUE"],
            "LB_Above": [0.20, 0.70, 0.75, 0.70, 0.15, 1.50, "TRUE"],
        },
        index=["mu", "sigma", "alpha", "gamma", "epsilon", "regret", "forget"],
    )
    params_dir = tmp_path / "RL-ABM-CRSS"
    params_dir.mkdir(parents=True, exist_ok=True)
    params_path = params_dir / "ALL_colorado_ABM_params_cal_1108.csv"
    params.to_csv(params_path)

    return params_path, crss_db_dir


class TestSyntheticCeilingFormula:
    """(a) Formula test: min(grid_top, (1 + margin) * peak) on a fixture."""

    def test_grid_top_and_peak_scaled_branches(self, tmp_path):
        params_path, crss_db_dir = _write_synthetic_ref(tmp_path)

        # cluster_method="legacy_centroid": this fixture's synthetic agent
        # names (LB_Below/LB_Above) are not in HY2021_CLUSTER_LABELS (a
        # fixed table of the 31 real calibrated entities), and this test is
        # about the water-right ceiling formula, not clustering.
        profiles = create_profiles_from_data(
            params_csv_path=str(params_path),
            crss_db_dir=str(crss_db_dir),
            rng=np.random.default_rng(0),
            paper_water_margin=0.4,
            cluster_method="legacy_centroid",
        )
        by_id = {p.agent_id: p for p in profiles}
        assert set(by_id) == {"LB_Below", "LB_Above"}

        below = by_id["LB_Below"]
        above = by_id["LB_Above"]

        # Common history: peak 900, threshold (1 + 0.4) * 900 = 1260.
        assert below.peak_obs_af == pytest.approx(900.0)
        assert above.peak_obs_af == pytest.approx(900.0)

        # grid_top (1000) <= 1260 -> keeps the grid top.
        assert below.grid_top_af == pytest.approx(1000.0)
        assert below.water_right == pytest.approx(1000.0)
        assert below.water_right_source == "grid_top"

        # grid_top (5000) > 1260 -> capped at the peak-scaled ceiling.
        assert above.grid_top_af == pytest.approx(5000.0)
        assert above.water_right == pytest.approx(1260.0)
        assert above.water_right_source == "peak_scaled"

        # bin_size_af (the H&Y step) always comes from the grid, unaffected
        # by which ceiling won: grid_top / 4 in this 5-point linspace.
        assert below.bin_size_af == pytest.approx(250.0)
        assert above.bin_size_af == pytest.approx(1250.0)

        # actual_2018_diversion is read independently of the ceiling.
        assert below.actual_2018_diversion == pytest.approx(700.0)
        assert above.actual_2018_diversion == pytest.approx(700.0)

    def test_paper_water_margin_out_of_range_raises(self, tmp_path):
        """Review P2: paper_water_margin outside [0, 1] must raise before
        any file is even read."""
        params_path, crss_db_dir = _write_synthetic_ref(tmp_path)
        for bad in (-0.01, 1.01, -5.0, 2.0):
            with pytest.raises(ValueError, match="paper_water_margin"):
                create_profiles_from_data(
                    params_csv_path=str(params_path),
                    crss_db_dir=str(crss_db_dir),
                    rng=np.random.default_rng(0),
                    paper_water_margin=bad,
                )

    def test_peak_window_ignores_years_after_2018(self, tmp_path):
        """Review P2: an historical file extended past 2018 must not move
        peak_obs_af -- a 2019 spike is excluded from the max()."""
        params_path, crss_db_dir = _write_synthetic_ref(tmp_path)
        lb_hist_path = crss_db_dir / "HistoricalData" / "LB_historical_annual_diversion.csv"
        extended = pd.DataFrame(
            {"LB_Below": [900.0, 700.0, 700.0, 999999.0], "LB_Above": [900.0, 700.0, 700.0, 999999.0]},
            index=[1971, 2017, 2018, 2019],
        )
        extended.to_csv(lb_hist_path)

        # cluster_method="legacy_centroid": see the same note in
        # test_grid_top_and_peak_scaled_branches above.
        profiles = create_profiles_from_data(
            params_csv_path=str(params_path),
            crss_db_dir=str(crss_db_dir),
            rng=np.random.default_rng(0),
            paper_water_margin=0.4,
            cluster_method="legacy_centroid",
        )
        by_id = {p.agent_id: p for p in profiles}
        # Peak stays 900 (the pre-2019 max), not 999999 (the 2019 spike).
        assert by_id["LB_Below"].peak_obs_af == pytest.approx(900.0)
        assert by_id["LB_Above"].peak_obs_af == pytest.approx(900.0)

    def test_missing_historical_files_raise(self, tmp_path):
        """Review P2: create_profiles_from_data requires both historical
        files for its real-data path; the water_right*0.8 fallback is for
        profiles that skip this function entirely (synthetic builders)."""
        params_path, crss_db_dir = _write_synthetic_ref(tmp_path)
        (crss_db_dir / "HistoricalData" / "LB_historical_annual_diversion.csv").unlink()
        with pytest.raises(ValueError, match="LB_historical_annual_diversion"):
            create_profiles_from_data(
                params_csv_path=str(params_path), crss_db_dir=str(crss_db_dir),
                rng=np.random.default_rng(0),
            )

    def test_lb_agent_missing_historical_column_raises(self, tmp_path):
        """Review P2: an active LB agent absent from the historical file's
        columns must raise, mirroring the UB group-column check."""
        params_path, crss_db_dir = _write_synthetic_ref(tmp_path)
        lb_hist_path = crss_db_dir / "HistoricalData" / "LB_historical_annual_diversion.csv"
        # Drop LB_Above's column entirely (still an active, params-listed agent).
        truncated = pd.DataFrame({"LB_Below": [900.0, 700.0, 700.0]}, index=[1971, 2017, 2018])
        truncated.to_csv(lb_hist_path)
        with pytest.raises(ValueError, match="LB_Above"):
            create_profiles_from_data(
                params_csv_path=str(params_path), crss_db_dir=str(crss_db_dir),
                rng=np.random.default_rng(0),
            )


def _write_ub_two_agent_group_fixture(tmp_path: Path) -> Path:
    """Two active UB agents (Agent_A grid_top=600, Agent_B grid_top=400)
    sharing state group ``_UB_STATE_GROUPS[0]`` ("WY", the first 5-slot
    group) -- covers the UB proportional group-split in CI without ref
    data. The group's historical peak (1971) is 800 AF; each agent's
    peak_obs_af should be 800 * (its own grid_top / group total 1000).
    """
    crss_db_dir = tmp_path / "CRSS_DB" / "CRSS_DB"
    (crss_db_dir / "Div_States").mkdir(parents=True, exist_ok=True)
    (crss_db_dir / "HistoricalData").mkdir(parents=True, exist_ok=True)
    (crss_db_dir / "Group_Agt").mkdir(parents=True, exist_ok=True)

    # LB: no active agents, but both files must still exist (Review P2),
    # and both the 2017 and 2018 rows are required file-wide regardless
    # of whether any LB agent is active (P1-b/(v) 2026-09-27 review).
    pd.DataFrame({"LBDummy": [0.0]}).to_csv(crss_db_dir / "Div_States" / "LB_discrete_states.csv", index=False)
    pd.DataFrame({"LBDummy": [0.0, 0.0]}, index=[2017, 2018]).to_csv(
        crss_db_dir / "HistoricalData" / "LB_historical_annual_diversion.csv")

    # 58-slot Group_Agt fixture: slots 1-2 of the first (WY) group are the
    # two controllable agents; every other slot is filler (never given a
    # column in UB_discrete_states.csv below, so never touched).
    with open(crss_db_dir / "Group_Agt" / "UB_ABM_Groups_and_Agents.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["G", "Agent_A", "Agent_B"] + [f"s{i}" for i in range(3, 59)])

    ub_states = pd.DataFrame({
        "G_Agent_A": np.linspace(0, 600, 5),
        "G_Agent_B": np.linspace(0, 400, 5),
    })
    ub_states.to_csv(crss_db_dir / "Div_States" / "UB_discrete_states.csv", index=False)

    # All 9 required historical columns (mapped via _UB_HIST_COLUMN_BY_GROUP,
    # e.g. AZ_UB -> "AZ") must exist; only "WY" (the group under test)
    # carries a real series -- 1971 peak 800, 2018 use 500 (thousand AF,
    # matching the real file's units -- *1000 in the loader).
    # 2017 row required alongside 2018 (P1-b/(v) 2026-09-27 review);
    # WY's 2017 use set equal to its 2018 use (0.5) since this fixture's
    # own tests only exercise peak_obs_af / grid-top-share, not the FQL
    # calibrated warm-start's prev_action.
    ub_hist_data = {
        _UB_HIST_COLUMN_BY_GROUP[sg]: [0.0, 0.0, 0.0] for sg in _UB_STATE_GROUPS if sg != "WY"
    }
    ub_hist_data["WY"] = [0.8, 0.5, 0.5]
    ub_hist = pd.DataFrame(ub_hist_data, index=[1971, 2017, 2018])
    ub_hist.to_csv(crss_db_dir / "HistoricalData" / "UB_historical_annual_depletion.csv")

    params = pd.DataFrame(
        {"WY": [0.20, 0.70, 0.75, 0.70, 0.15, 1.50, "TRUE"]},
        index=["mu", "sigma", "alpha", "gamma", "epsilon", "regret", "forget"],
    )
    params_dir = tmp_path / "RL-ABM-CRSS"
    params_dir.mkdir(parents=True, exist_ok=True)
    params_path = params_dir / "ALL_colorado_ABM_params_cal_1108.csv"
    params.to_csv(params_path)

    return params_path, crss_db_dir


class TestUBGroupProportionalSplit:
    """Suggested test: a synthetic UB two-agent group, asserting
    peak_obs_af == group_max * grid_top_share -- covers the UB
    proportional split (Change 1) in CI without needing ref data."""

    def test_peak_obs_af_matches_grid_top_share(self, tmp_path):
        params_path, crss_db_dir = _write_ub_two_agent_group_fixture(tmp_path)
        profiles = create_profiles_from_data(
            params_csv_path=str(params_path),
            crss_db_dir=str(crss_db_dir),
            rng=np.random.default_rng(0),
        )
        by_id = {p.agent_id: p for p in profiles}
        assert set(by_id) == {"G_Agent_A", "G_Agent_B"}

        group_peak_af = 800.0
        group_total = 1000.0  # 600 + 400
        assert by_id["G_Agent_A"].peak_obs_af == pytest.approx(group_peak_af * (600.0 / group_total))
        assert by_id["G_Agent_B"].peak_obs_af == pytest.approx(group_peak_af * (400.0 / group_total))


# ---------------------------------------------------------------------------
# (b) AZ_UB regression: real ref data, all 78 agents resolve
# ---------------------------------------------------------------------------
@requires_real_ref
class TestAZUBRegression:
    """Change 2: the AZ_UB history-column bug no longer leaves any UB
    group's agents with None actual_2018_diversion / peak_obs_af."""

    def test_all_78_agents_have_real_values(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV),
            crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42),
        )
        assert len(profiles) == 78

        none_2018 = [p.agent_id for p in profiles if p.actual_2018_diversion is None]
        none_peak = [p.agent_id for p in profiles if p.peak_obs_af is None]
        none_wr = [p.agent_id for p in profiles if p.water_right is None or p.water_right <= 0]

        assert none_2018 == [], f"agents with None actual_2018_diversion: {none_2018}"
        assert none_peak == [], f"agents with None peak_obs_af: {none_peak}"
        assert none_wr == [], f"agents with non-positive water_right: {none_wr}"

    def test_arizona_ub_agents_resolve(self):
        """The 3 ArizonaMiscUses_* (AZ_UB) agents specifically -- these were
        the ones silently left at None before Change 2."""
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV),
            crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42),
        )
        by_id = {p.agent_id: p for p in profiles}
        az_agents = [
            "ArizonaMiscUses_PLArizonaAgriculture",
            "ArizonaMiscUses_PLArizonaAdditionalAg",
            "ArizonaMiscUses_UnidentifiedUse",
        ]
        for aid in az_agents:
            assert aid in by_id, f"{aid} missing from profiles entirely"
            p = by_id[aid]
            assert p.actual_2018_diversion is not None, aid
            assert p.actual_2018_diversion > 0, aid
            assert p.peak_obs_af is not None, aid
            assert p.peak_obs_af > 0, aid
            # 2018 use should be a small fraction of the grid top for these
            # historically minor AZ_UB agents (real 2018 use ~500-260 AF vs
            # 18,000-40,000 AF grid tops) -- the pre-fix bug used to feed
            # the ENVIRONMENT 80% of the grid top instead.
            assert p.actual_2018_diversion < 0.1 * p.grid_top_af, (
                aid, p.actual_2018_diversion, p.grid_top_af)


# ---------------------------------------------------------------------------
# (c) Real data, default paper_water_margin: UB sum + no-below-2018 check
# ---------------------------------------------------------------------------
@requires_real_ref
class TestRealDataDefaultMargin:
    def test_ub_water_right_sum_in_range(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV),
            crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42),
        )
        ub = [p for p in profiles if p.basin == "upper_basin"]
        assert len(ub) == 56
        ub_sum_maf = sum(p.water_right for p in ub) / 1e6
        # Default paper_water_margin = 0.4; see irrigation_personas.
        # create_profiles_from_data docstring / docs/irrigation_physics.md
        # for the derivation (4.86 / 3.536 = 1.374 -> rounded margin 0.4).
        assert 4.90 <= ub_sum_maf <= 5.00, f"UB water_right sum {ub_sum_maf:.4f} MAF out of range"

    def test_no_agent_water_right_below_2018_use(self):
        """No agent's new ceiling should fall below what it actually used
        in 2018 -- if this ever fires, do NOT silently raise the affected
        agents; report the list to the operator (this test intentionally
        asserts on the exact list rather than clamping anything)."""
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV),
            crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42),
        )
        below = [
            (p.agent_id, p.water_right, p.actual_2018_diversion)
            for p in profiles
            if p.actual_2018_diversion is not None and p.water_right < p.actual_2018_diversion
        ]
        assert below == [], f"agents with water_right below their 2018 use: {below}"


# ---------------------------------------------------------------------------
# (d) Manifest / config-snapshot records paper_water_margin
# ---------------------------------------------------------------------------
class TestManifestRecordsMargin:
    def test_record_paper_water_margin_provenance(self, tmp_path):
        manifest_path = tmp_path / "reproducibility_manifest.json"
        manifest_path.write_text(json.dumps({"seed": 42}), encoding="utf-8")
        snapshot_path = tmp_path / "config_snapshot.yaml"
        snapshot_path.write_text("metadata:\n  seed: 42\n", encoding="utf-8")

        _record_paper_water_margin_provenance(tmp_path, 0.4, True)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["paper_water_margin"] == 0.4
        assert manifest["paper_water_margin_applied"] is True

        import yaml
        snapshot = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
        assert snapshot["metadata"]["paper_water_margin"] == 0.4
        assert snapshot["metadata"]["paper_water_margin_applied"] is True

    def test_missing_files_do_not_raise(self, tmp_path):
        """No manifest/snapshot on disk yet (e.g. a run that failed before
        _finalize_experiment) -- must not raise."""
        _record_paper_water_margin_provenance(tmp_path, 0.4, False)  # no exception

    def test_fql_baseline_manifest_records_margin(self, tmp_path):
        """run_fql_baseline.py has no ExperimentRunner/broker manifest, so
        it writes its own reproducibility_manifest.json; verify
        paper_water_margin lands in it via a real (synthetic, fast) run."""
        import examples.irrigation_abm.run_fql_baseline as run_fql_baseline

        argv = [
            "run_fql_baseline.py",
            "--agents", "3",
            "--years", "1",
            "--seed", "1",
            "--output", str(tmp_path),
            "--paper-water-margin", "0.4",
            # Synthetic agent ids (Agent_000, ...) have no calibrated
            # Q/count/P_Tran files under ref/CRSS_DB; --fql-init calibrated
            # is the CLI default but only applies to real CRSS agent ids
            # (see run_fql_baseline.py --fql-init help).
            "--fql-init", "zero",
        ]
        old_argv = sys.argv
        sys.argv = argv
        try:
            run_fql_baseline.main()
        finally:
            sys.argv = old_argv

        manifest_path = tmp_path / "reproducibility_manifest.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["paper_water_margin"] == 0.4
        assert manifest["paper_water_margin_applied"] is False  # synthetic, not --real


# ---------------------------------------------------------------------------
# (e) FQL parity: the ceiling binds the FQL path exactly as the LLM path
# ---------------------------------------------------------------------------
class TestFQLClipParity:
    """Change 3, corrected per review P1 (2026-09-27): the capped
    water_right reaches the FQL only through the environment and
    validator context shared with the LLM path -- the increase clip in
    IrrigationEnvironment.execute_skill, the 10 percent decrease floor,
    and the allocation-cap and minimum-use flags the validators read.
    create_fql_agents's own Q-grid (state discretisation + regret-step
    scale) stays on the ORIGINAL H&Y grid top (grid_top_af), never on the
    capped water_right: building the Q-grid from the capped value would
    shrink the FQL's internal bins for every peak-scaled agent, changing
    the FQL reference model itself rather than just clipping its
    requests. Both tests below are constructed on a peak-scaled profile
    (grid_top_af > water_right) so
    they FAIL on the pre-fix code (which built the Q-grid from
    water_right).
    """

    def _make_profile(self, grid_top_af: float, water_right: float) -> IrrigationAgentProfile:
        return IrrigationAgentProfile(
            agent_id="TestAgent",
            basin="upper_basin",
            cluster="aggressive",
            mu=10.0,        # deliberately huge: (mu + |z|) * bin_size_af
            sigma=0.7,      # always dwarfs the small water_right below,
            water_right=water_right,
            grid_top_af=grid_top_af,
            bin_size_af=1_000_000.0,  # so the increase clip is guaranteed
            # WP1b (item 20): initialize_from_profiles now requires every
            # Upper Basin profile to carry a sub-basin -- this test is
            # about the Q-grid/water-right clip, unrelated to which one.
            precip_group="WY",
        )                             # to engage regardless of the RNG draw.

    def test_q_grid_stays_on_grid_top_not_capped_water_right(self):
        """A peak-scaled profile (grid_top_af=5000 > water_right=100):
        the Q-grid must span [0, grid_top_af], NOT [0, water_right] --
        fails on the pre-fix code, which used water_right here."""
        profile = self._make_profile(grid_top_af=5000.0, water_right=100.0)
        agents = create_fql_agents([profile], seed=1)
        _, state = agents["TestAgent"]
        assert state.state_bounds[-1] == pytest.approx(5000.0)
        assert state.state_bounds[-1] > profile.water_right
        assert state.state_bounds[0] == pytest.approx(0.0)
        assert len(state.state_bounds) == 21  # Q-grid structure unchanged

    def test_execution_clips_at_water_right_while_q_grid_top_unchanged(self):
        """The environment clip (irrigation_env.py, IrrigationEnvironment.
        execute_skill: new_req = min(current + step_af, wr)) is the SAME
        branch for skill == "increase_demand" (FQL) and "increase_small"/
        "increase_large" (LLM). An increase executed on a peak-scaled
        profile must never exceed water_right, even though the FQL's own
        Q-grid (built from grid_top_af, asserted above) is wider."""
        profile = self._make_profile(grid_top_af=5000.0, water_right=100.0)
        config = WaterSystemConfig(seed=1)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles([profile])

        approved = ApprovedSkill(
            skill_name="increase_demand", agent_id="TestAgent", approval_status="APPROVED"
        )
        env.execute_skill(approved)

        state = env.get_agent_state("TestAgent")
        assert state["request"] == pytest.approx(100.0), (
            "FQL's increase_demand must clip at profile water_right, same as the LLM path"
        )
        assert state["request"] <= state["water_right"] + 1e-9

        # The Q-grid itself is untouched by execution.
        agents = create_fql_agents([profile], seed=1)
        _, fql_state = agents["TestAgent"]
        assert fql_state.state_bounds[-1] == pytest.approx(5000.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
