"""
Tests for ``cluster_method`` (2026-09-28, fix/irrigation-persona-clusters-hy2021).

``create_profiles_from_data`` gained a ``cluster_method`` parameter:
- ``"hy2021"`` (new default): look up ``HY2021_CLUSTER_LABELS``, a fixed
  transcription of Hung & Yang (2021, WRR) Figure 7's own published
  per-entity cluster assignment.
- ``"legacy_centroid"``: the pre-existing ``_infer_cluster`` 4-D
  nearest-centroid heuristic, byte-identical to behaviour before
  ``cluster_method`` existed (needed to reproduce the 431adb5e corpus).

Real-ref-data tests need the full ``ref/CRSS_DB`` tree and skip cleanly
when it is not present in this worktree -- same resolution and skip
convention as ``test_water_right_history_anchor.py``. The frozen-corpus
comparison test also needs a sibling checkout of the primary clone
(``governed_broker_framework``) with the pinned 431adb5e results directory;
it is read-only (never written to) and skips cleanly if that path is
absent (e.g. a fresh clone with no sibling primary repo).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Same PROJECT_ROOT convention as test_water_right_history_anchor.py
# (tests/ -> irrigation_abm -> examples -> repo root).
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
# This tests/ directory has no __init__.py (not a package), so import its
# sibling module by bare name -- same reasoning as the PROJECT_ROOT insert
# above, one level down.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from examples.irrigation_abm.irrigation_personas import (
    create_profiles_from_data,
    HY2021_CLUSTER_LABELS,
    _UB_STATE_GROUPS,
    _resolve_cluster,
)
from examples.irrigation_abm.run_experiment import _record_cluster_method_provenance
from test_fql_calibrated_init import _primary_results_dir

# ---------------------------------------------------------------------------
# Real-ref-data availability (mirrors test_water_right_history_anchor.py).
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
    reason="ref/CRSS_DB real data not present in this worktree; CI has no "
           "ref data, skip is expected.",
)

# The primary clone's frozen 431adb5e reference corpus, read-only, used only
# to check that cluster_method='legacy_centroid' reproduces its 'cluster'
# column byte-for-byte. Reuses test_fql_calibrated_init.py's
# _primary_results_dir() (WAGF_PRIMARY_RESULTS-overridable) instead of a
# second hardcoded sibling-clone path, so both tests skip/redirect the same
# way on a machine without that checkout. Skip cleanly if it is not present
# (e.g. CI, or a fresh clone elsewhere).
FROZEN_CORPUS_CSV = (
    _primary_results_dir() / "strict_42yr_gemma3_4b_431adb5e_seed42" / "simulation_log.csv"
)

requires_frozen_corpus = pytest.mark.skipif(
    not FROZEN_CORPUS_CSV.is_file(),
    reason=f"frozen 431adb5e corpus not found at {FROZEN_CORPUS_CSV} (sibling "
           "primary-clone checkout); skip is expected outside this machine.",
)


# ---------------------------------------------------------------------------
# (1) HY2021_CLUSTER_LABELS table shape + the paper's stated facts
# ---------------------------------------------------------------------------
class TestHY2021ClusterLabelsTable:
    def test_table_has_31_entries(self):
        assert len(HY2021_CLUSTER_LABELS) == 31

    def test_all_9_ub_state_groups_aggressive(self):
        """Sec. 4.2 (p.13): '[UB agents] are mostly Aggressive'; Figure 7
        plots all 9 UB state groups (WY, UT1-3, NM, CO1-3, AZ_UB) as blue
        diamonds -- exactly, not just 'mostly', at the state-group level."""
        assert len(_UB_STATE_GROUPS) == 9
        for sg in _UB_STATE_GROUPS:
            assert HY2021_CLUSTER_LABELS[sg] == "aggressive", sg

    def test_lb_aggressive_set_matches_figure7_not_just_the_text(self):
        """Text (p.13) says 'the LB agents are all classified as
        conservative except three tribal water users (Fort Mohave Ind Res
        AZ, FtYumaReservation, and Chemehuevi Ind Res)'. Figure 7 itself
        plots a FOURTH LB agent, CocopahIndRes (also a tribal reservation),
        as a blue diamond (Aggressive) -- confirmed by direct RGB sampling
        of the rendered PDF page (2026-09-28): its marker is RGB
        (91, 155, 212), identical to every other Aggressive marker's fill
        (sampled directly), not the gray of the immediately adjacent CRIR
        CA triangle.
        The text's 'three' undercounts its own figure by one. This table
        follows the figure (the actual per-entity assignment) over the
        text's summary count, so the verified LB-aggressive set has 4
        members, not 3."""
        lb_entries = {k: v for k, v in HY2021_CLUSTER_LABELS.items() if k not in _UB_STATE_GROUPS}
        assert len(lb_entries) == 22
        lb_aggressive = {k for k, v in lb_entries.items() if v == "aggressive"}
        assert lb_aggressive == {
            "Fort Mohave Ind Res AZ",
            "FtYumaReservation",
            "Chemehuevi Ind Res",
            "CocopahIndRes",
        }

    def test_no_unknown_cluster_names(self):
        valid = {"aggressive", "forward_looking_conservative", "myopic_conservative"}
        bad = {k: v for k, v in HY2021_CLUSTER_LABELS.items() if v not in valid}
        assert bad == {}


# ---------------------------------------------------------------------------
# (2) cluster_method validation (no real ref data needed)
# ---------------------------------------------------------------------------
def _write_minimal_synthetic_ref(tmp_path: Path) -> tuple[Path, Path]:
    """One active LB agent, "LB_Only", not present in HY2021_CLUSTER_LABELS
    -- enough to exercise cluster_method without needing real ref data.
    Mirrors test_water_right_history_anchor.py's _write_synthetic_ref, but
    trimmed to the single agent this module's tests need."""
    import csv as csv_mod

    crss_db_dir = tmp_path / "CRSS_DB" / "CRSS_DB"
    (crss_db_dir / "Div_States").mkdir(parents=True, exist_ok=True)
    (crss_db_dir / "HistoricalData").mkdir(parents=True, exist_ok=True)
    (crss_db_dir / "Group_Agt").mkdir(parents=True, exist_ok=True)

    pd.DataFrame({"LB_Only": np.linspace(0, 1000, 5)}).to_csv(
        crss_db_dir / "Div_States" / "LB_discrete_states.csv", index=False)
    pd.DataFrame({"dummy": [0.0]}).to_csv(
        crss_db_dir / "Div_States" / "UB_discrete_states.csv", index=False)
    with open(crss_db_dir / "Group_Agt" / "UB_ABM_Groups_and_Agents.csv", "w",
              newline="", encoding="utf-8") as f:
        csv_mod.writer(f).writerow(["G"] + [str(i) for i in range(58)])

    lb_hist = pd.DataFrame({"LB_Only": [900.0, 700.0, 700.0]}, index=[1971, 2017, 2018])
    lb_hist.to_csv(crss_db_dir / "HistoricalData" / "LB_historical_annual_diversion.csv")
    ub_hist = pd.DataFrame(
        {sg_col: [0.0, 0.0] for sg_col in {"WY", "UT1", "UT2", "UT3", "NM", "CO1", "CO2", "CO3", "AZ"}},
        index=[2017, 2018],
    )
    ub_hist.to_csv(crss_db_dir / "HistoricalData" / "UB_historical_annual_depletion.csv")

    params = pd.DataFrame(
        {"LB_Only": [0.20, 0.70, 0.75, 0.70, 0.15, 1.50, "TRUE"]},
        index=["mu", "sigma", "alpha", "gamma", "epsilon", "regret", "forget"],
    )
    params_dir = tmp_path / "RL-ABM-CRSS"
    params_dir.mkdir(parents=True, exist_ok=True)
    params_path = params_dir / "ALL_colorado_ABM_params_cal_1108.csv"
    params.to_csv(params_path)
    return params_path, crss_db_dir


class TestClusterMethodValidation:
    def test_invalid_cluster_method_raises(self, tmp_path):
        params_path, crss_db_dir = _write_minimal_synthetic_ref(tmp_path)
        with pytest.raises(ValueError, match="cluster_method"):
            create_profiles_from_data(
                params_csv_path=str(params_path), crss_db_dir=str(crss_db_dir),
                rng=np.random.default_rng(0), cluster_method="bogus",
            )

    def test_hy2021_raises_on_entity_not_in_table(self, tmp_path):
        """A parameters CSV with an entity absent from HY2021_CLUSTER_LABELS
        must fail loud under cluster_method='hy2021', not silently guess."""
        params_path, crss_db_dir = _write_minimal_synthetic_ref(tmp_path)
        assert "LB_Only" not in HY2021_CLUSTER_LABELS
        with pytest.raises(ValueError, match="HY2021_CLUSTER_LABELS"):
            create_profiles_from_data(
                params_csv_path=str(params_path), crss_db_dir=str(crss_db_dir),
                rng=np.random.default_rng(0), cluster_method="hy2021",
            )

    def test_legacy_centroid_does_not_need_the_table(self, tmp_path):
        """legacy_centroid computes from parameters directly, so an entity
        name absent from HY2021_CLUSTER_LABELS is fine under this method."""
        params_path, crss_db_dir = _write_minimal_synthetic_ref(tmp_path)
        profiles = create_profiles_from_data(
            params_csv_path=str(params_path), crss_db_dir=str(crss_db_dir),
            rng=np.random.default_rng(0), cluster_method="legacy_centroid",
        )
        assert len(profiles) == 1
        assert profiles[0].cluster in (
            "aggressive", "forward_looking_conservative", "myopic_conservative")

    def test_resolve_cluster_direct(self):
        assert _resolve_cluster("WY", 0, 0, 0, 0, "hy2021") == "aggressive"
        with pytest.raises(ValueError, match="cluster_method"):
            _resolve_cluster("WY", 0, 0, 0, 0, "bogus")


# ---------------------------------------------------------------------------
# (2b) --rebalance-clusters refused together with --cluster-method hy2021
# ---------------------------------------------------------------------------
class TestRebalanceHY2021Refusal:
    """Rebalancing reassigns clusters by FQL-parameter distance toward a
    target distribution, which would silently overwrite Figure 7's
    published per-entity assignment; hy2021 (default) + --rebalance-clusters
    must refuse rather than let one silently undo the other."""

    def _run(self, tmp_path, script_module, extra_argv):
        argv = [
            "prog", "--agents", "3", "--years", "1", "--seed", "1",
            "--output", str(tmp_path), "--rebalance-clusters",
        ] + extra_argv
        old_argv = sys.argv
        sys.argv = argv
        try:
            with pytest.raises(SystemExit, match="rebalance-clusters"):
                script_module.main()
        finally:
            sys.argv = old_argv

    def test_run_experiment_refuses_default_hy2021(self, tmp_path):
        import examples.irrigation_abm.run_experiment as run_experiment
        self._run(tmp_path, run_experiment, [])  # cluster_method defaults to hy2021

    def test_run_experiment_allows_legacy_centroid(self, tmp_path):
        import examples.irrigation_abm.run_experiment as run_experiment
        argv = [
            "prog", "--model", "mock", "--agents", "3", "--years", "1",
            "--seed", "1", "--output", str(tmp_path), "--rebalance-clusters",
            "--cluster-method", "legacy_centroid",
        ]
        old_argv = sys.argv
        sys.argv = argv
        try:
            run_experiment.main()  # must NOT raise
        finally:
            sys.argv = old_argv

    def test_fql_baseline_refuses_default_hy2021(self, tmp_path):
        import examples.irrigation_abm.run_fql_baseline as run_fql_baseline
        self._run(tmp_path, run_fql_baseline, ["--fql-init", "zero"])


# ---------------------------------------------------------------------------
# (3) Real ref data: hy2021 assignment on all 78 real agents
# ---------------------------------------------------------------------------
@requires_real_ref
class TestRealDataHY2021Assignment:
    def test_all_56_ub_agents_aggressive(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), cluster_method="hy2021",
        )
        ub = [p for p in profiles if p.basin == "upper_basin"]
        assert len(ub) == 56
        non_aggressive = [p.agent_id for p in ub if p.cluster != "aggressive"]
        assert non_aggressive == []

    def test_lb_aggressive_set_is_the_four_figure7_agents(self):
        """See test_lb_aggressive_set_matches_figure7_not_just_the_text
        above for why this is 4 agents (including CocopahIndRes), not the
        3 the paper's text names."""
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), cluster_method="hy2021",
        )
        lb = [p for p in profiles if p.basin == "lower_basin"]
        assert len(lb) == 22
        lb_aggressive = {p.agent_id for p in lb if p.cluster == "aggressive"}
        assert lb_aggressive == {
            "Fort Mohave Ind Res AZ",
            "FtYumaReservation",
            "Chemehuevi Ind Res",
            "CocopahIndRes",
        }

    def test_78_agents_total(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), cluster_method="hy2021",
        )
        assert len(profiles) == 78


# ---------------------------------------------------------------------------
# (4) legacy_centroid reproduces the frozen 431adb5e corpus, byte-for-byte
# ---------------------------------------------------------------------------
@requires_real_ref
@requires_frozen_corpus
class TestLegacyCentroidReproducesFrozenCorpus:
    def test_all_78_agents_match_frozen_year1_cluster(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), cluster_method="legacy_centroid",
        )
        by_id = {p.agent_id: p.cluster for p in profiles}
        assert len(by_id) == 78

        frozen = pd.read_csv(FROZEN_CORPUS_CSV)
        year1 = frozen[frozen["year"] == 1]
        assert len(year1) == 78

        mismatches = [
            (row.agent_id, by_id.get(row.agent_id), row.cluster)
            for row in year1.itertuples()
            if by_id.get(row.agent_id) != row.cluster
        ]
        assert mismatches == []


# ---------------------------------------------------------------------------
# (5) Manifest / config-snapshot records cluster_method
# ---------------------------------------------------------------------------
class TestManifestRecordsClusterMethod:
    def test_record_cluster_method_provenance(self, tmp_path):
        manifest_path = tmp_path / "reproducibility_manifest.json"
        manifest_path.write_text(json.dumps({"seed": 42}), encoding="utf-8")
        snapshot_path = tmp_path / "config_snapshot.yaml"
        snapshot_path.write_text("metadata:\n  seed: 42\n", encoding="utf-8")

        _record_cluster_method_provenance(tmp_path, "hy2021", True)

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["cluster_method"] == "hy2021"
        assert manifest["cluster_method_applied"] is True

        import yaml
        snapshot = yaml.safe_load(snapshot_path.read_text(encoding="utf-8"))
        assert snapshot["metadata"]["cluster_method"] == "hy2021"
        assert snapshot["metadata"]["cluster_method_applied"] is True

    def test_missing_files_do_not_raise(self, tmp_path):
        _record_cluster_method_provenance(tmp_path, "legacy_centroid", False)  # no exception

    def test_fql_baseline_manifest_records_cluster_method(self, tmp_path):
        """run_fql_baseline.py writes its own reproducibility_manifest.json;
        verify cluster_method lands in it via a real (synthetic, fast) run."""
        import examples.irrigation_abm.run_fql_baseline as run_fql_baseline

        argv = [
            "run_fql_baseline.py",
            "--agents", "3",
            "--years", "1",
            "--seed", "1",
            "--output", str(tmp_path),
            "--cluster-method", "legacy_centroid",
            "--fql-init", "zero",  # synthetic ids have no calibrated tables
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
        assert manifest["cluster_method"] == "legacy_centroid"
        assert manifest["cluster_method_applied"] is False  # synthetic, not --real


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
