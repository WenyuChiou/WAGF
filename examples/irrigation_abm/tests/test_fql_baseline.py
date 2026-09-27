"""
Tests for FQL baseline runner and skill mapper.

Verifies:
1. fql_action_to_skill mapping correctness (2-action model)
2. WSA/ACA label computation
3. Validator fallback logic
4. Smoke test: 5 agents × 5 years produces valid output
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.learning.fql_skill_mapper import (
    fql_action_to_skill,
    compute_wsa_label,
    compute_aca_label,
)
from examples.irrigation_abm.run_fql_baseline import (
    create_fql_agents,
    validate_skill,
    _create_synthetic_profiles,
    run_simulation,
    FQL_SKILLS,
    main as fql_baseline_main,
)
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import (
    build_simulation_log_row,
    create_profiles_from_data,
)

# CRSS reference data (gitignored; copied by hand from the paper's data
# bundle -- see run_fql_baseline.py --real / docs/irrigation_physics.md).
# ALL_colorado_ABM_params_cal_1108.csv IS tracked in git despite the
# ref/RL-ABM-CRSS/ gitignore pattern (git ls-files confirms it); only the
# CRSS_DB/ directory needs to be supplied locally.
CRSS_PARAMS_CSV = PROJECT_ROOT / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
CRSS_DB_DIR = PROJECT_ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()


# ── fql_action_to_skill tests ──

class TestFQLActionToSkill:
    """Test the FQL action → 2-action mapping (Hung & Yang 2021)."""

    def test_positive_is_increase(self):
        """Any positive action → increase_demand."""
        assert fql_action_to_skill(1.0) == "increase_demand"
        assert fql_action_to_skill(100) == "increase_demand"
        assert fql_action_to_skill(50000) == "increase_demand"
        assert fql_action_to_skill(0.001) == "increase_demand"

    def test_negative_is_decrease(self):
        """Any negative action → decrease_demand."""
        assert fql_action_to_skill(-1.0) == "decrease_demand"
        assert fql_action_to_skill(-100) == "decrease_demand"
        assert fql_action_to_skill(-50000) == "decrease_demand"
        assert fql_action_to_skill(-0.001) == "decrease_demand"

    def test_exact_zero_is_maintain(self):
        """Only action == 0.0 exactly → maintain_demand (degenerate case)."""
        assert fql_action_to_skill(0.0) == "maintain_demand"

    def test_no_large_small_distinction(self):
        """FQL has no large/small — all positive → increase_demand."""
        # These would have been increase_small vs increase_large in 5-skill
        assert fql_action_to_skill(100) == "increase_demand"    # 0.1% of 100k
        assert fql_action_to_skill(50000) == "increase_demand"  # 50% of 100k
        assert fql_action_to_skill(-100) == "decrease_demand"
        assert fql_action_to_skill(-50000) == "decrease_demand"


# ── WSA/ACA label tests ──

class TestLabels:
    """Test WSA and ACA label computation."""

    def test_wsa_labels(self):
        assert compute_wsa_label(0.0) == "VL"
        assert compute_wsa_label(0.1) == "VL"
        assert compute_wsa_label(0.3) == "L"
        assert compute_wsa_label(0.5) == "M"
        assert compute_wsa_label(0.7) == "H"
        assert compute_wsa_label(0.9) == "VH"

    def test_aca_labels(self):
        assert compute_aca_label("aggressive") == "H"
        assert compute_aca_label("forward_looking_conservative") == "M"
        assert compute_aca_label("myopic_conservative") == "L"
        assert compute_aca_label("unknown") == "M"  # default


# ── Validator fallback tests ──

class TestValidatorFallback:
    """Test validate_skill fallback logic."""

    def test_valid_skill_passes(self):
        """A valid skill in normal conditions passes through."""
        ctx = {
            "agent_id": "test",
            "at_allocation_cap": False,
            "has_efficient_system": False,
            "below_minimum_utilisation": False,
            "water_right": 100_000,
            "current_diversion": 50_000,
            "current_request": 50_000,
            "curtailment_ratio": 0,
            "shortage_tier": 0,
            "drought_index": 0.3,
            "cluster": "aggressive",
            "basin": "lower_basin",
            "total_basin_demand": 5_000_000,
            "loop_year": 5,
        }
        valid, skill = validate_skill("maintain_demand", ctx)
        assert valid
        assert skill == "maintain_demand"

    def test_increase_blocked_at_cap(self):
        """Increase at allocation cap → fallback to maintain_demand."""
        ctx = {
            "agent_id": "test",
            "at_allocation_cap": True,
            "has_efficient_system": False,
            "below_minimum_utilisation": False,
            "water_right": 100_000,
            "current_diversion": 99_000,
            "current_request": 100_000,
            "curtailment_ratio": 0,
            "shortage_tier": 0,
            "drought_index": 0.3,
            "cluster": "aggressive",
            "basin": "lower_basin",
            "total_basin_demand": 5_000_000,
            "loop_year": 5,
        }
        valid, skill = validate_skill("increase_demand", ctx)
        assert valid
        assert skill != "increase_demand"

    def test_decrease_blocked_at_floor(self):
        """Decrease at minimum utilisation → fallback."""
        ctx = {
            "agent_id": "test",
            "at_allocation_cap": False,
            "has_efficient_system": False,
            "below_minimum_utilisation": True,
            "water_right": 100_000,
            "current_diversion": 5_000,
            "current_request": 5_000,
            "curtailment_ratio": 0,
            "shortage_tier": 0,
            "drought_index": 0.3,
            "cluster": "myopic_conservative",
            "basin": "lower_basin",
            "total_basin_demand": 5_000_000,
            "loop_year": 5,
        }
        valid, skill = validate_skill("decrease_demand", ctx)
        assert valid
        assert skill != "decrease_demand"


# ── FQL agent creation tests ──

class TestFQLAgentCreation:
    """Test create_fql_agents from profiles."""

    def test_creates_agents(self):
        profiles = _create_synthetic_profiles(5, seed=42)
        agents = create_fql_agents(profiles, seed=42)
        assert len(agents) == 5
        for aid, (agent, state) in agents.items():
            assert state.q_table is not None
            assert state.prev_diversion > 0


# ── Smoke test ──

class TestSmokeRun:
    """Smoke test: 5 agents × 5 years."""

    def test_smoke_run(self):
        """Full pipeline: profiles → env → FQL agents → simulate → CSV."""
        seed = 42
        np.random.seed(seed)

        profiles = _create_synthetic_profiles(5, seed=seed)

        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)

        fql_agents = create_fql_agents(profiles, seed=seed)
        profiles_dict = {p.agent_id: p for p in profiles}

        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            logs = run_simulation(
                env=env,
                fql_agents=fql_agents,
                profiles=profiles_dict,
                n_years=5,
                output_dir=output_dir,
                seed=seed,
            )

        # Basic checks
        assert len(logs) == 25  # 5 agents × 5 years
        assert all(log["yearly_decision"] in FQL_SKILLS for log in logs
                   if log["yearly_decision"] is not None)

        # Check columns match expected
        expected_cols = {
            "agent_id", "year", "cluster", "basin", "yearly_decision",
            "request", "diversion", "water_right", "drought_index",
            "shortage_tier", "lake_mead_level", "utilisation_pct",
        }
        actual_cols = set(logs[0].keys())
        assert expected_cols.issubset(actual_cols), f"Missing columns: {expected_cols - actual_cols}"

        # Mead level should be plausible
        final_mead = logs[-1]["lake_mead_level"]
        assert 800 < final_mead < 1300, f"Mead level {final_mead} out of plausible range"

        # All agents should have positive water_right
        for log in logs:
            assert log["water_right"] > 0


def _llm_simulation_log_columns():
    """Canonical LLM simulation-log column set/order, derived from the
    shared row builder (``build_simulation_log_row``) rather than from a
    results file on disk -- this test tracks the builder itself, so a
    future column added there is automatically required of the FQL
    baseline too, instead of drifting the way the two runners' inline
    dict literals drifted after the 2026-09-25 supply-side redesign.
    """
    dummy_agent_state = {
        "request": 100.0,
        "diversion": 90.0,
        "water_right": 200.0,
        "curtailment_ratio": 0.1,
        "delivery_ratio": 0.9,
        "gap_reason": "none",
        "has_efficient_system": False,
        "below_minimum_utilisation": False,
    }
    dummy_settlement = {
        "mead_storage_end_maf": 10.0,
        "powell_storage_maf": 12.0,
        "powell_storage_end_maf": 11.5,
        "powell_release_maf": 8.0,
        "natural_flow_maf": 9.0,
        "ub_delivered_maf": 3.0,
        "lb_phys_ratio": 1.0,
    }
    row = build_simulation_log_row(
        agent_id="A",
        year=1,
        cluster="aggressive",
        basin="upper_basin",
        yearly_decision="maintain_demand",
        wsa_label="M",
        aca_label="H",
        agent_state=dummy_agent_state,
        drought_index=0.3,
        shortage_tier=0,
        lake_mead_level=1050.0,
        mead_storage_maf=10.5,
        settlement=dummy_settlement,
        basin_request_af=1_000_000.0,
    )
    return list(row.keys())


class TestSimulationLogHeaderParity:
    """FQL baseline CSVs must carry every column the LLM runs carry, or
    downstream analysis that concatenates both arms silently drops the
    FQL rows' extra fields as NaN (the bug this fix addresses)."""

    def test_fql_header_is_superset_of_llm_header(self):
        llm_cols = set(_llm_simulation_log_columns())
        assert llm_cols, "sanity: the row builder must return columns at all"

        seed = 42
        np.random.seed(seed)
        profiles = _create_synthetic_profiles(5, seed=seed)

        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)

        fql_agents = create_fql_agents(profiles, seed=seed)
        profiles_dict = {p.agent_id: p for p in profiles}

        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            logs = run_simulation(
                env=env,
                fql_agents=fql_agents,
                profiles=profiles_dict,
                n_years=2,
                output_dir=Path(tmpdir),
                seed=seed,
            )

        assert logs, "2-year synthetic FQL run produced no rows"
        fql_cols = set(logs[0].keys())
        missing = llm_cols - fql_cols
        assert not missing, f"FQL simulation log is missing LLM columns: {sorted(missing)}"

        # FQL-only columns must still be present (not dropped by the fix).
        assert {"fql_raw_skill", "fql_action", "fql_blocked"}.issubset(fql_cols)


@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason=(
        "CRSS reference data not found under ref/CRSS_DB/CRSS_DB/ "
        "(copy Div_States/{UB,LB}_discrete_states.csv, "
        "Group_Agt/UB_ABM_Groups_and_Agents.csv, and the HistoricalData "
        "series -- see run_fql_baseline.py --real)"
    ),
)
class TestRealDataFQLRun:
    """A short --real run must produce physically sane settlement columns:
    finite reservoir storage and delivered water never exceeding what was
    requested."""

    def test_two_year_real_run_finite_storage_and_delivered_le_request(self):
        seed = 42
        np.random.seed(seed)

        profiles = create_profiles_from_data(
            params_csv_path=str(CRSS_PARAMS_CSV),
            crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(seed),
            paper_water_margin=0.4,
        )

        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)

        precip_csv = CRSS_DB_DIR / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
        if precip_csv.exists():
            env.load_crss_precipitation(str(precip_csv))

        fql_agents = create_fql_agents(profiles, seed=seed)
        profiles_dict = {p.agent_id: p for p in profiles}

        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            logs = run_simulation(
                env=env,
                fql_agents=fql_agents,
                profiles=profiles_dict,
                n_years=2,
                output_dir=Path(tmpdir),
                seed=seed,
            )

        assert logs, "2-year --real FQL run produced no rows"
        for row in logs:
            assert np.isfinite(row["powell_storage_maf"]), (
                f"non-finite powell_storage_maf for {row['agent_id']} year {row['year']}"
            )
            assert row["delivered"] <= row["request"] + 1e-6, (
                f"delivered ({row['delivered']}) exceeds request ({row['request']}) "
                f"for {row['agent_id']} year {row['year']}"
            )


class TestLaunchCommandTiming:
    """LAUNCH_COMMAND.txt must carry the runner's own timing -- the FQL
    references generated at 431adb5e had Started:/Finished: (see
    results/fql_nogov_431adb5e/seed42/LAUNCH_COMMAND.txt); it was written
    by an ad hoc, never-committed launcher rather than by this file, and a
    later launcher for the 78d986ed references dropped that timing. main()
    now appends RunnerStarted:/RunnerFinished:/RunnerWallSeconds: itself
    (namespaced so they never collide with a launcher's own lines), and
    never writes ExitCode: -- only the launcher that invoked this script
    knows the real process exit status."""

    def test_two_year_synthetic_run_writes_launch_command_timing(self, monkeypatch, tmp_path):
        # Simulate an external launcher that already wrote its own header
        # (command line, worktree, commit) before invoking this script --
        # main() must append after it, not overwrite it.
        launcher_header = (
            "python -u run_fql_baseline.py --years 2 --agents 5 --seed 42\n"
            "(run from worktree fake-launcher-worktree, detached HEAD)\n"
            "Commit: deadbeef\n"
        )
        (tmp_path / "LAUNCH_COMMAND.txt").write_text(launcher_header, encoding="utf-8")

        argv = [
            "run_fql_baseline.py",
            "--years", "2",
            "--agents", "5",
            "--seed", "42",
            "--fql-init", "zero",
            "--output", str(tmp_path),
        ]
        monkeypatch.setattr(sys, "argv", argv)

        fql_baseline_main()

        launch_command_path = tmp_path / "LAUNCH_COMMAND.txt"
        assert launch_command_path.is_file(), "main() did not write LAUNCH_COMMAND.txt"
        content = launch_command_path.read_text(encoding="utf-8")

        assert content.startswith(launcher_header), (
            "runner must append after the launcher's header, not overwrite it"
        )
        assert "RunnerStarted:" in content
        assert "RunnerFinished:" in content
        assert "RunnerWallSeconds:" in content
        assert content.index("RunnerStarted:") < content.index("RunnerFinished:"), (
            "RunnerStarted: must precede RunnerFinished:"
        )
        assert "ExitCode:" not in content, (
            "the runner must never claim ExitCode: -- only a launcher knows "
            "the real process exit status"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
