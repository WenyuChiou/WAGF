"""
Tests for the FQL calibrated (Hung & Yang 2021) warm-start init.

--fql-init calibrated (2026-09-27 fidelity fix) replaces
FQLState.initialize()'s zero-initialised Q/count/P_Tran tables with
Hung & Yang's own calibrated agent state
(ref/CRSS_DB/CRSS_DB/Initial_Files/All-1109 -- the CLI default since the
2026-09-27 snapshot-choice decision: this is the only Initial_Files
variant whose Q tables are dated the same day, 2020-11-08, as
ALL_colorado_ABM_params_cal_1108.csv; see run_fql_baseline.py's
--fql-init-dir help / create_fql_agents docstring and
docs/irrigation_model_caveats.md item 13 for the other undocumented
variants and the rationale), matching ABM_CRSS_coupling.py's
Q_learning(), which always loads these three files and never
zero-initialises.

Covers:
  (a) synthetic Hung-and-Yang-layout files round-trip into our arrays
      with the documented axis mapping (fql.load_calibrated_tables).
  (b) a missing / NUL-filled / non-finite / wrong-shape file raises
      FQLCalibratedInitError -- no silent zero fallback.
  (c) --fql-init zero reproduces the pre-fix (commit 00654d14, the
      parent of this branch) run_fql_baseline.py output byte for byte
      on a 2-year synthetic run.
  (d) real data (skipped if ref/ is missing): all 78 agents load from
      Initial_Files/All-1109 with no all-zero Q table, and a 1-year
      --real --no-governance calibrated run no longer shows 73/78
      agents mechanically choosing decrease in year 1.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from examples.irrigation_abm.learning.fql import (
    FQLConfig,
    FQLState,
    FQLAgent,
    FQLCalibratedInitError,
    load_calibrated_tables,
    _hy_div_to_state,
)
from examples.irrigation_abm.run_fql_baseline import (
    create_fql_agents,
    run_simulation,
    resolve_prev_action,
)
from examples.irrigation_abm.irrigation_env import (
    IrrigationEnvironment,
    WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

CRSS_PARAMS_CSV = PROJECT_ROOT / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
CRSS_DB_DIR = PROJECT_ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
FQL_INIT_DIR = CRSS_DB_DIR / "Initial_Files" / "All-1109"  # matches the CLI default
_REAL_REF_AVAILABLE = (
    CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir() and FQL_INIT_DIR.is_dir()
)


def _save_array_like_hy(path: Path, data: np.ndarray, fmt: str) -> None:
    """Reproduce ABM_CRSS_coupling.py's Save_Array on-disk layout: a
    '# Array shape: ...' header, then per-slice whitespace-delimited
    float rows with a '# New slice' comment after every 2D slice (3D
    arrays: one slice per outer index; 4D: one slice per (outer, second)
    index pair). np.loadtxt(comments='#') skips both comment forms, which
    is exactly what load_calibrated_tables relies on.
    """
    shape = data.shape
    with open(path, "w") as f:
        f.write(f"# Array shape: {shape}\n")
        if len(shape) == 3:
            for slice1 in data:
                np.savetxt(f, slice1, fmt=fmt)
                f.write("# New slice\n")
        elif len(shape) == 4:
            for slice1 in data:
                for slice2 in slice1:
                    np.savetxt(f, slice2, fmt=fmt)
                    f.write("# New slice\n")
        else:
            raise ValueError(f"unsupported shape {shape}")


# ── (a) axis mapping round-trip ──

class TestLoadCalibratedTablesAxisMapping:
    """Synthetic Hung & Yang-layout files round-trip with the exact axis
    mapping documented in fql.py / ABM_CRSS_coupling.py: Q_Table ->
    (n_preceding, n_states, n_actions); count/P_Tran ->
    (n_preceding, n_actions, n_states, n_states)."""

    def test_round_trip_axis_mapping(self, tmp_path):
        config = FQLConfig()
        nf, ns, na = config.n_preceding, config.n_states, config.n_actions

        # Distinct per-cell values so a transposed axis is caught.
        q = np.zeros((nf, ns, na))
        for f in range(nf):
            for s in range(ns):
                for a in range(na):
                    q[f, s, a] = f * 1000 + s * 10 + a

        count = np.zeros((nf, na, ns, ns))
        p_tran = np.zeros((nf, na, ns, ns))
        for f in range(nf):
            for a in range(na):
                for s0 in range(ns):
                    for st in range(ns):
                        count[f, a, s0, st] = f * 100000 + a * 10000 + s0 * 100 + st
                        p_tran[f, a, s0, st] = f * 1000 + a * 100 + s0 + st * 0.001

        # Agent name with a space, mirroring real CRSS agent ids
        # (e.g. "Fort Mohave Ind Res AZ") that must round-trip too.
        agent_id = "Test Agent With Space"
        _save_array_like_hy(tmp_path / f"Q_Table_{agent_id}.txt", q, fmt="%10.3f")
        _save_array_like_hy(tmp_path / f"count_{agent_id}.txt", count, fmt="%-10.6f")
        _save_array_like_hy(tmp_path / f"P_Tran_{agent_id}.txt", p_tran, fmt="%-10.6f")

        loaded_q, loaded_count, loaded_p, hashes = load_calibrated_tables(
            agent_id=agent_id, init_dir=tmp_path, config=config,
        )

        assert loaded_q.shape == (nf, ns, na)
        assert loaded_count.shape == (nf, na, ns, ns)
        assert loaded_p.shape == (nf, na, ns, ns)
        np.testing.assert_allclose(loaded_q, q, atol=1e-6)
        np.testing.assert_allclose(loaded_count, count, atol=1e-6)
        np.testing.assert_allclose(loaded_p, p_tran, atol=1e-6)

        for key, fname in [
            ("q_table", f"Q_Table_{agent_id}.txt"),
            ("count", f"count_{agent_id}.txt"),
            ("p_transition", f"P_Tran_{agent_id}.txt"),
        ]:
            expected = hashlib.sha256((tmp_path / fname).read_bytes()).hexdigest()
            assert hashes[key] == expected

    def test_wrong_shape_raises_clear_message(self, tmp_path):
        config = FQLConfig()
        agent_id = "BadShapeAgent"
        bad_q = np.zeros((3, 21, 2))  # wrong n_f -- should be 2
        _save_array_like_hy(tmp_path / f"Q_Table_{agent_id}.txt", bad_q, fmt="%10.3f")
        ok_count = np.ones(
            (config.n_preceding, config.n_actions, config.n_states, config.n_states)
        )
        _save_array_like_hy(tmp_path / f"count_{agent_id}.txt", ok_count, fmt="%-10.6f")
        _save_array_like_hy(tmp_path / f"P_Tran_{agent_id}.txt", ok_count, fmt="%-10.6f")

        with pytest.raises(FQLCalibratedInitError, match="values, expected"):
            load_calibrated_tables(agent_id=agent_id, init_dir=tmp_path, config=config)


# ── (b) no silent zero fallback ──

class TestLoadCalibratedTablesRaisesNoSilentFallback:
    """Missing / NUL-filled / non-finite files raise
    FQLCalibratedInitError; never silently substitute zeros."""

    @staticmethod
    def _write_valid_triplet(tmp_path, agent_id, config):
        nf, ns, na = config.n_preceding, config.n_states, config.n_actions
        q = np.ones((nf, ns, na))
        c = np.ones((nf, na, ns, ns))
        _save_array_like_hy(tmp_path / f"Q_Table_{agent_id}.txt", q, fmt="%10.3f")
        _save_array_like_hy(tmp_path / f"count_{agent_id}.txt", c, fmt="%-10.6f")
        _save_array_like_hy(tmp_path / f"P_Tran_{agent_id}.txt", c, fmt="%-10.6f")

    def test_missing_file_raises(self, tmp_path):
        config = FQLConfig()
        with pytest.raises(FQLCalibratedInitError, match="not found"):
            load_calibrated_tables(agent_id="MissingAgent", init_dir=tmp_path, config=config)

    def test_nul_filled_file_raises(self, tmp_path):
        config = FQLConfig()
        agent_id = "NulAgent"
        self._write_valid_triplet(tmp_path, agent_id, config)
        # Simulate a truncated/crashed write leaving a NUL-filled file.
        (tmp_path / f"Q_Table_{agent_id}.txt").write_bytes(b"\x00" * 64)
        with pytest.raises(FQLCalibratedInitError, match="NUL"):
            load_calibrated_tables(agent_id=agent_id, init_dir=tmp_path, config=config)

    def test_non_finite_file_raises(self, tmp_path):
        config = FQLConfig()
        agent_id = "NonFiniteAgent"
        nf, ns, na = config.n_preceding, config.n_states, config.n_actions
        q = np.ones((nf, ns, na))
        q[0, 0, 0] = np.nan
        c = np.ones((nf, na, ns, ns))
        _save_array_like_hy(tmp_path / f"Q_Table_{agent_id}.txt", q, fmt="%10.3f")
        _save_array_like_hy(tmp_path / f"count_{agent_id}.txt", c, fmt="%-10.6f")
        _save_array_like_hy(tmp_path / f"P_Tran_{agent_id}.txt", c, fmt="%-10.6f")
        with pytest.raises(FQLCalibratedInitError, match="non-finite"):
            load_calibrated_tables(agent_id=agent_id, init_dir=tmp_path, config=config)


# ── P1-a (2026-09-27 review): H&Y-exact state grid ──

class TestHYExactStateGrid:
    """19 of 22 LB agents' real Div_States columns are NOT a 0-to-top
    linspace (e.g. MohaveValleyIDD = [0, 12000, 14000, ..., 50000]), so
    np.linspace(0, grid_top_af, 21) reads the wrong FQL state for them.
    --fql-init calibrated must use the agent's REAL column via
    _hy_div_to_state; --fql-init zero must keep the legacy linspace rule,
    and the two must never mix within one FQLState."""

    def test_synthetic_nonuniform_grid_boundaries(self):
        # A small H&Y-shaped grid: state 0 is a wide catch-all below
        # agt_states[1]=100; states 1-4 are uniform 20-wide bins.
        agt_states = np.array([0.0, 100.0, 120.0, 140.0, 160.0])
        bin_size = agt_states[2] - agt_states[1]  # 20.0
        n_states = len(agt_states)  # 5

        cases = [
            (0.0, 0), (99.9, 0),      # below first bin -> state 0
            (100.0, 1), (119.9, 1),   # [agt_states[1], agt_states[2])
            (120.0, 2), (139.9, 2),
            (140.0, 3), (159.9, 3),
            (160.0, 4),               # top of the real grid -> last state
            (500.0, 4),               # saturates, never out of range
        ]
        for div, expected in cases:
            got = _hy_div_to_state(div, agt_states, bin_size, n_states)
            assert got == expected, f"div={div}: expected state {expected}, got {got}"

    def test_fqlagent_routes_through_state_grid_mode_not_mixed(self):
        agt_states = np.array([0.0, 100.0, 120.0, 140.0, 160.0])
        config = FQLConfig(n_states=5)
        state_hy = FQLState(
            state_bounds=agt_states, state_grid_mode="hy_exact", hy_bin_size=20.0,
        )
        state_hy.initialize(config)
        agent = FQLAgent(config, rng=np.random.default_rng(0))

        # state_bounds[1]-state_bounds[0] would be 100 (WRONG bin size for
        # this grid); hy_bin_size (20) is what must actually get used.
        assert state_hy.bin_size == 100.0
        assert agent._div_to_state(130.0, state_hy) == _hy_div_to_state(130.0, agt_states, 20.0, 5) == 2

        # A "linspace" (legacy, default) FQLState with the SAME
        # state_bounds array must give a DIFFERENT answer for this
        # non-uniform grid, proving the two modes are not accidentally
        # equivalent and cannot be mixed.
        state_legacy = FQLState(state_bounds=agt_states)
        state_legacy.initialize(config)
        assert agent._div_to_state(130.0, state_legacy) != agent._div_to_state(130.0, state_hy)

        # _sample_actions must scale by hy_bin_size (20), not
        # state_bounds[1]-state_bounds[0] (100): same rng draw, exactly a
        # 20/100 = 0.2 ratio between the two modes' magnitudes.
        actions_hy = FQLAgent(config, rng=np.random.default_rng(7))._sample_actions(state_hy)
        actions_legacy = FQLAgent(config, rng=np.random.default_rng(7))._sample_actions(state_legacy)
        np.testing.assert_allclose(actions_hy, actions_legacy * 0.2, atol=1e-9)


@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason="CRSS reference data not found under ref/CRSS_DB/CRSS_DB/",
)
class TestHYExactStateGridRealAgents:
    """Pin the two agents the 2026-09-27 review flagged by name: their
    2018 diversion must land at H&Y's own state index under the real
    (non-uniform) grid, not the wrong, higher linspace index (11 and 13
    respectively -- what --fql-init zero's legacy rule would give)."""

    @staticmethod
    def _profiles_by_id():
        profiles = create_profiles_from_data(
            params_csv_path=str(CRSS_PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), paper_water_margin=0.4,
        )
        return {p.agent_id: p for p in profiles}

    def test_mohave_valley_idd_state_9(self):
        p = self._profiles_by_id()["MohaveValleyIDD"]
        state = _hy_div_to_state(p.actual_2018_diversion, p.div_states_grid, p.bin_size_af, 21)
        assert state == 9, f"expected H&Y state 9, got {state} (div={p.actual_2018_diversion})"

    def test_crir_az_state_5(self):
        p = self._profiles_by_id()["CRIR AZ"]
        state = _hy_div_to_state(p.actual_2018_diversion, p.div_states_grid, p.bin_size_af, 21)
        assert state == 5, f"expected H&Y state 5, got {state} (div={p.actual_2018_diversion})"


# ── P1-b (2026-09-27 review): prev_diversion = 2017, zero deviation ──

class TestFirstStepPrevDiversionIs2017:
    """H&Y's first Q-update (yi==0) reads s_0 = state(Div_y0=2017),
    s_t = state(Div_y=2018), and a_t = Div_y - Div_y0 -- giving an exact
    zero reward deviation. prev_diversion must be the 2017 value for
    this to hold; using 2018 (the pre-fix behavior) breaks both the
    deviation and which count-table row gets credited."""

    def test_reward_deviation_is_exactly_zero(self):
        """_compute_reward's deviation term is 0 when prev_action is
        EXACTLY the observed Div_y - Div_y0 change (H&Y's own
        construction), regardless of the regret coefficient."""
        config = FQLConfig(regret=2.5)  # any regret; deviation is 0 either way
        agent = FQLAgent(config, rng=np.random.default_rng(0))
        div_y0 = 100.0   # 2017
        a_t = 20.0       # observed 2017->2018 change
        div_y = div_y0 + a_t  # 2018 = 120.0, by H&Y's own construction
        reward = agent._compute_reward(div_y, div_y0, a_t)
        # deviation = div_y - (div_y0 + a_t) = 0 -> no penalty -> reward = div_y
        assert reward == pytest.approx(div_y)

    def test_count_row_credited_at_2017_state_not_2018(self):
        """The Bayesian posterior update must increment
        count_table[f_t, a_t_idx, state(2017), state(2018)] -- crediting
        the PRIOR (2017) state as the "from" row. Setting
        state.prev_diversion to 2018 (the pre-fix bug) would credit a
        different, wrong cell whenever 2017 and 2018 fall in different
        states, as they deliberately do here."""
        agt_states = np.array([0.0, 100.0, 120.0, 140.0, 160.0])
        config = FQLConfig(n_states=5, forget=False)  # forget=False: no decay noise
        state = FQLState(
            state_bounds=agt_states, state_grid_mode="hy_exact", hy_bin_size=20.0,
        )
        state.initialize(config)
        agent = FQLAgent(config, rng=np.random.default_rng(0))

        div_2017 = 110.0   # state 1: [100, 120)
        div_2018 = 150.0   # state 3: [140, 160) -- deliberately different
        a_t = div_2018 - div_2017
        state.prev_diversion = div_2017   # P1-b fix under test
        state.prev_action = a_t
        f_t = 0
        a_t_idx = int(a_t > 0)  # H&Y's int(a_t > 0); 40 > 0 -> 1

        s_0_expected = _hy_div_to_state(div_2017, agt_states, 20.0, 5)
        s_t_expected = _hy_div_to_state(div_2018, agt_states, 20.0, 5)
        assert (s_0_expected, s_t_expected) == (1, 3)

        before = state.count_table[f_t, a_t_idx, s_0_expected, s_t_expected]
        agent.step(state, current_diversion=div_2018, preceding_factor=(f_t, f_t))
        after = state.count_table[f_t, a_t_idx, s_0_expected, s_t_expected]
        assert after == before + 1, (
            f"expected count_table[{f_t},{a_t_idx},{s_0_expected},{s_t_expected}] "
            f"to increment by 1 (credited to the 2017 state row); "
            f"before={before} after={after}"
        )
        # The WRONG (pre-fix) row -- crediting 2018's own state as s_0 --
        # must NOT have moved.
        wrong_row = state.count_table[f_t, a_t_idx, s_t_expected, :]
        assert np.allclose(wrong_row, 1.0), (
            "count_table row at state(2018) changed -- the update credited "
            "the wrong (2018, not 2017) state as s_0"
        )


@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason="CRSS reference data not found under ref/CRSS_DB/CRSS_DB/",
)
class TestCreateFQLAgentsSetsPrevDiversionTo2017:
    """End-to-end: create_fql_agents(fql_init='calibrated') itself must
    set FQLState.prev_diversion to the OBSERVED 2017 value, not 2018 --
    the actual site of the pre-fix bug (step()'s own math was already
    correct; it was the caller that fed it the wrong prev_diversion)."""

    def test_mohave_valley_idd_prev_diversion_is_2017(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(CRSS_PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), paper_water_margin=0.4,
        )
        p = {pr.agent_id: pr for pr in profiles}["MohaveValleyIDD"]
        assert p.actual_2017_diversion != p.actual_2018_diversion  # not a tie agent

        agents = create_fql_agents(
            profiles, seed=42, fql_init="calibrated",
            fql_init_dir=FQL_INIT_DIR, crss_db_dir=CRSS_DB_DIR,
        )
        _, state = agents["MohaveValleyIDD"]
        assert state.prev_diversion == pytest.approx(p.actual_2017_diversion)
        assert state.prev_diversion != pytest.approx(p.actual_2018_diversion)
        assert state.init_provenance["prev_diversion_2017"] == pytest.approx(p.actual_2017_diversion)


class TestResolvePrevActionNoSilentFallback:
    """(v)/2026-09-27 review: resolve_prev_action must never silently
    default prev_action/prev_diversion to 0.0; it raises when neither
    Hung & Yang's own QL_Div files nor the historical annual series have
    data for this agent."""

    def test_raises_when_no_source_available(self):
        from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile
        profile = IrrigationAgentProfile(
            agent_id="NoHistoryAgent", basin="lower_basin", cluster="aggressive",
            actual_2017_diversion=None, actual_2018_diversion=None,
        )
        with pytest.raises(FQLCalibratedInitError, match="could not resolve"):
            resolve_prev_action(profile, crss_db_dir=None)

    @pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found")
    def test_real_agents_never_fall_back_to_zero(self):
        profiles = create_profiles_from_data(
            params_csv_path=str(CRSS_PARAMS_CSV), crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(42), paper_water_margin=0.4,
        )
        for p in profiles:
            prev_action, prev_div_2017, source = resolve_prev_action(p, CRSS_DB_DIR)
            assert source in {"ql_div_csv", "historical_annual_series"}
            assert prev_div_2017 == pytest.approx(p.actual_2017_diversion)


# ── (c) --fql-init zero byte-identical to pre-fix ──

class TestZeroInitByteIdenticalToPreFix:
    """--fql-init zero must reproduce the pre-fix (commit 00654d14, the
    parent of feat/fql-calibrated-warm-start) run_fql_baseline.py output
    byte for byte on a 2-year synthetic run.

    (iv)/2026-09-27 review: the 00654d14 snapshot is written under
    tmp_path (not the source tree) and the repo root is put on
    PYTHONPATH instead -- the snapshot's own top-of-file
    ``PROJECT_ROOT = Path(__file__).resolve().parents[2]`` then resolves
    to some unrelated tmp_path ancestor and is silently unused (no
    ``examples`` package there to collide with), while the PYTHONPATH
    entry lets ``from examples.irrigation_abm...`` still resolve to the
    real repo. This test only exercises the synthetic (non --real) path,
    which never reads PROJECT_ROOT for anything besides that sys.path
    insert, so the mismatch has no other effect.
    """

    def test_zero_init_matches_pre_fix_commit(self, tmp_path):
        old_script = tmp_path / "_snapshot_00654d14_run_fql_baseline.py"
        show = subprocess.run(
            ["git", "show", "00654d14:examples/irrigation_abm/run_fql_baseline.py"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
        )
        assert show.returncode == 0, show.stderr
        assert show.stdout, "git show returned empty content for the pre-fix script"
        # WP1b compatibility shim (2026-09-29, spec item 20; re-review
        # MEDIUM 2, same date): this 00654d14 snapshot predates
        # IrrigationEnvironment.initialize_from_profiles requiring every
        # Upper Basin profile to carry a sub-basin (precip_group), so its
        # own frozen _create_synthetic_profiles never sets one and would
        # otherwise raise when run against the CURRENT environment -- a
        # real invariant this snapshot cannot know about, unrelated to the
        # --fql-init zero fix this test verifies. Patched here, in this
        # test-owned copy only (never in production code): mark each Upper
        # Basin profile ``synthetic_no_subbasin`` (the SAME marker the
        # current run_fql_baseline.py's own _create_synthetic_profiles now
        # sets, MEDIUM 2), routing it to the unconstrained pool bucket
        # instead of raising or (the pre-MEDIUM-2 bug) round-robinning it
        # into a real sub-basin's request cap -- so both sides of the
        # comparison see the same, mode-consistent treatment.
        # WP1c review round 2 (2026-09-29): the SAME shim, extended for the
        # Lower Basin priority-split table -- this 00654d14 snapshot also
        # predates initialize_from_profiles requiring every Lower Basin
        # profile to be one of the 22 real lb_priority_split_v3.csv names
        # (item 22), so its frozen _create_synthetic_profiles ("Agent_NNN"
        # ids, never one of the 22) would otherwise raise. Marks
        # synthetic_no_priority_split=True for any Lower Basin profile not
        # in the table, the same "this agent has no real entitlement"
        # treatment run_fql_baseline.py's CURRENT _create_synthetic_profiles
        # now sets unconditionally.
        compat_shim = (
            "import examples.irrigation_abm.irrigation_env as _irr_env\n"
            "_orig_init_from_profiles = _irr_env.IrrigationEnvironment.initialize_from_profiles\n"
            "def _patched_init_from_profiles(self, profiles):\n"
            "    _lb_table = _irr_env._load_lb_priority_split_table()\n"
            "    for _p in profiles:\n"
            "        if getattr(_p, 'basin', None) == 'upper_basin' and not getattr(_p, 'precip_group', None):\n"
            "            _p.synthetic_no_subbasin = True\n"
            "        if getattr(_p, 'basin', None) == 'lower_basin' and _p.agent_id not in _lb_table:\n"
            "            _p.synthetic_no_priority_split = True\n"
            "    return _orig_init_from_profiles(self, profiles)\n"
            "_irr_env.IrrigationEnvironment.initialize_from_profiles = _patched_init_from_profiles\n"
        )
        # "from __future__ import annotations" must stay the first
        # statement in the file, so the shim is spliced in right after it
        # rather than prepended.
        future_line = "from __future__ import annotations\n"
        assert future_line in show.stdout, "old script has no future-annotations import to splice after"
        old_text = show.stdout.replace(future_line, future_line + compat_shim, 1)
        old_script.write_text(old_text, encoding="utf-8")

        import os
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

        out_old = tmp_path / "old"
        out_new = tmp_path / "new"
        common = ["--years", "2", "--agents", "5", "--seed", "42"]

        res_old = subprocess.run(
            [sys.executable, str(old_script), *common, "--output", str(out_old)],
            cwd=str(tmp_path), capture_output=True, text=True, env=env,
        )
        assert res_old.returncode == 0, res_old.stderr

        new_script = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_fql_baseline.py"
        res_new = subprocess.run(
            [sys.executable, str(new_script), *common,
             "--fql-init", "zero", "--output", str(out_new)],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
        )
        assert res_new.returncode == 0, res_new.stderr

        # Review fix 5 (2026-09-28, after 00654d14): run_fql_baseline.py
        # now wires precipitation_mm / precipitation_flag into the log
        # row from get_agent_context; the pre-fix (00654d14) script never
        # passed those kwargs to build_simulation_log_row at all, so they
        # were always blank there. That is the ONLY deliberate difference
        # this comparison allows -- everything else, including the
        # --fql-init zero path itself, must still be byte-for-byte
        # identical. Re-review 2026-09-29 (NIT): compare RAW CSV text via
        # the csv module, not a pandas round-trip -- to_csv on a
        # freshly-parsed DataFrame can reformat a cell (float precision,
        # quoting) differently from what the two scripts actually wrote on
        # disk, which could mask a real difference or manufacture a fake
        # one.
        import csv as csv_module

        def _read_csv_rows(path):
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv_module.DictReader(f)
                return reader.fieldnames, list(reader)

        old_fields, old_rows = _read_csv_rows(out_old / "simulation_log.csv")
        new_fields, new_rows = _read_csv_rows(out_new / "simulation_log.csv")
        assert new_fields == old_fields, (
            "the column set itself changed -- expected only the values of "
            "precipitation_mm/precipitation_flag to differ, not the schema"
        )
        assert len(old_rows) == len(new_rows), "row count diverged"

        precip_cols = ["precipitation_mm", "precipitation_flag"]
        # WP2 (2026-09-29, spec 2.1): run_fql_baseline.py now also passes
        # base_af=agent_state.get("base_af") to build_simulation_log_row --
        # populated by IrrigationEnvironment._reset_requests_to_base, which
        # did not exist at 00654d14 (nor anywhere before this WP2 commit),
        # so the pre-fix script always left it blank. A SECOND deliberate
        # difference this comparison allows, on top of review fix 5's
        # precipitation columns.
        base_af_cols = ["base_af"]
        other_cols = [c for c in old_fields if c not in precip_cols and c not in base_af_cols]

        for i, (old_row, new_row) in enumerate(zip(old_rows, new_rows)):
            for col in other_cols:
                assert old_row[col] == new_row[col], (
                    f"row {i} column {col!r} diverged from the pre-fix "
                    f"(00654d14) simulation_log.csv: {old_row[col]!r} != "
                    f"{new_row[col]!r} -- 'zero' must be byte-identical to "
                    "today's default behavior everywhere except the "
                    "deliberately added precipitation columns"
                )
            # The pre-fix script never populated these for ANY agent.
            for col in precip_cols:
                assert old_row[col] == "", (
                    f"row {i} column {col!r}: the pre-fix (00654d14) script "
                    "is expected to never populate this field"
                )
            # base_af (WP2): blank pre-fix, populated for EVERY agent
            # (unlike precipitation, not basin-restricted) in the new run.
            for col in base_af_cols:
                assert old_row[col] == "", (
                    f"row {i} column {col!r}: the pre-fix (00654d14) script "
                    "predates _reset_requests_to_base and is expected to "
                    "never populate this field"
                )
                assert new_row[col] != "", (
                    f"row {i} ({new_row['agent_id']}): WP2's "
                    "_reset_requests_to_base must populate base_af for "
                    "every agent, every year"
                )
            # Re-review 2026-09-29 (MEDIUM 4): get_agent_context now returns
            # None (a blank CSV cell) for a Lower Basin agent's
            # precipitation / precipitation_flag -- this basin has no
            # precipitation signal in this model at all -- so review fix 5
            # is only required to POPULATE these for an Upper Basin agent;
            # a Lower Basin row stays blank in the new script too.
            if new_row["basin"] == "upper_basin":
                for col in precip_cols:
                    assert new_row[col] != "", (
                        f"row {i} ({new_row['agent_id']}, upper_basin): "
                        f"review fix 5 must populate {col!r}, not just "
                        "avoid crashing"
                    )
            else:
                for col in precip_cols:
                    assert new_row[col] == "", (
                        f"row {i} ({new_row['agent_id']}, {new_row['basin']}): "
                        f"{col!r} should stay blank -- this basin has no "
                        "precipitation signal"
                    )


def _primary_results_dir() -> Path:
    """The primary clone's examples/irrigation_abm/results/ directory.

    Overridable via WAGF_PRIMARY_RESULTS (2026-09-27 review) so this test
    skips cleanly on a machine/CI without that specific clone checked out
    at that path; defaults to the hardcoded path this repo has used so far.
    """
    import os
    override = os.environ.get("WAGF_PRIMARY_RESULTS")
    if override:
        return Path(override)
    return (
        Path("C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework")
        / "examples" / "irrigation_abm" / "results"
    )


_OLD_REF = _primary_results_dir() / "fql_nogov_431adb5e" / "seed42" / "simulation_log.csv"


@pytest.mark.skip(
    reason="Superseded by the irrigation v3 water-system rewrite (WP1, "
           "2026-09-28, irrigation_v3_spec_2026-09-28.md): the "
           "fql_nogov_431adb5e/seed42 reference was captured under the "
           "pre-v3 hydrology, Mead curve, shortage-tier and Upper Basin "
           "priority rules. mead_storage_maf and lake_mead_level now "
           "differ from year 1 (new Mead area-capacity curve, L2 H4); "
           "curtailment_ratio and shortage_tier differ from the declared-"
           "shortage volume mechanism (spec 1.5) onward; and this is a "
           "'--fql-init zero' FQL run, so those water-system differences "
           "feed back into the Q-learning state and cascade into every "
           "later request/decision column too. A new byte-identity "
           "baseline against the v3 water system belongs to WP5 (the FQL "
           "reference), not this pre-v3 regression guard."
)
@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason="CRSS reference data not found under ref/CRSS_DB/CRSS_DB/",
)
@pytest.mark.skipif(
    not _OLD_REF.is_file(),
    reason="primary clone's fql_nogov_431adb5e/seed42 reference run not found "
           "(set WAGF_PRIMARY_RESULTS to override the default path)",
)
class TestZeroInitRealDataRegressionAgainstPrimaryClone:
    """--real --no-governance --fql-init zero --seed 42 --years 42 must
    match the primary clone's fql_nogov_431adb5e/seed42/simulation_log.csv
    (an untouched, read-only reference from an earlier commit whose
    schema predates 00654d14's shared-row-builder column additions)
    EXACTLY, string for string, on the pre-existing 28 columns, same row
    order.

    Root cause of every earlier apparent divergence on this same
    comparison (2026-09-27 review, fully resolved): none of it was a
    real computation difference. `pandas.read_csv()`'s float parser is
    not guaranteed round-trip exact (a documented pandas limitation --
    `float_precision='round_trip'` exists precisely because the default
    parser can shift the last 1-2 significant digits of a float on
    read). Verified directly: reading the FROZEN REFERENCE FILE ITSELF
    with pandas and immediately writing it back with `to_csv()`, with NO
    simulation code involved at all, does not reproduce its own original
    bytes (27337.597290979353 becomes 27337.597290979356). An earlier
    version of this test read the new run's CSV into a DataFrame,
    selected the 28-column subset, and called `to_csv()` on THAT
    subset -- a parse-then-reformat round trip that can shift digits
    even when the underlying float64 values are bit-identical to the
    reference. Comparing at the raw CSV-row string level instead (the
    `csv` module below, values never parsed as floats) shows zero
    differing rows, every time. The interpreter mix on this machine
    (`python` -> C:\\Python314, 3.14.0, numpy 2.4.2; `python3` -> a
    different 3.11.9 install, numpy 2.2.4) was a genuine, separate fact
    checked during the same investigation, but was NOT the cause of this
    specific test's failures -- both interpreters' OWN simulation output
    is string-identical to the reference once compared this way.
    """

    def test_28_column_subset_byte_identical(self, tmp_path):
        import csv

        out_dir = tmp_path / "zero_real_nogov_seed42"
        script = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_fql_baseline.py"
        res = subprocess.run(
            [sys.executable, str(script),
             "--real", "--no-governance", "--fql-init", "zero",
             "--seed", "42", "--years", "42", "--output", str(out_dir),
             # legacy_centroid: the frozen reference predates cluster_method
             # (2026-09-28); its "cluster"/"aca_label" columns were written
             # by the old _infer_cluster heuristic, not the new hy2021
             # default (see irrigation_personas.HY2021_CLUSTER_LABELS).
             "--cluster-method", "legacy_centroid"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True,
        )
        assert res.returncode == 0, res.stderr

        def read_rows(path):
            with open(path, newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            return rows[0], rows[1:]

        old_header, old_rows = read_rows(_OLD_REF)
        assert len(old_header) == 28, (
            f"expected the pre-existing 28-column schema, got "
            f"{len(old_header)}: {old_header}"
        )
        new_header, new_rows = read_rows(out_dir / "simulation_log.csv")

        # Column-select at the raw string level -- no float parsing, so
        # no parse/reformat round trip can shift a digit (see docstring).
        col_idx = [new_header.index(c) for c in old_header]
        new_rows_subset = [[row[i] for i in col_idx] for row in new_rows]

        assert len(new_rows_subset) == len(old_rows), (
            f"row count mismatch: reference has {len(old_rows)}, new run "
            f"has {len(new_rows_subset)}"
        )
        mismatches = [
            (i, o, n) for i, (o, n) in enumerate(zip(old_rows, new_rows_subset))
            if o != n
        ]
        assert not mismatches, (
            f"--fql-init zero real-data output diverged from the primary "
            f"clone's fql_nogov_431adb5e/seed42 reference on the 28 "
            f"pre-existing columns: {len(mismatches)} differing row(s), "
            f"first at row {mismatches[0][0]}: old={mismatches[0][1]!r} "
            f"new={mismatches[0][2]!r}"
        )


# ── (d) real data ──

@pytest.mark.skipif(
    not _REAL_REF_AVAILABLE,
    reason=(
        "CRSS reference data not found under ref/CRSS_DB/CRSS_DB/ "
        "(see run_fql_baseline.py --real / --fql-init-dir default)"
    ),
)
class TestCalibratedInitRealData:
    """All 78 real CRSS agents load from Initial_Files/All-1109 with no
    all-zero Q table, and a 1-year --real --no-governance calibrated run
    no longer shows 73/78 agents mechanically choosing decrease in year
    1 -- the fidelity defect this fix addresses."""

    @staticmethod
    def _build_real_profiles(seed=42):
        return create_profiles_from_data(
            params_csv_path=str(CRSS_PARAMS_CSV),
            crss_db_dir=str(CRSS_DB_DIR),
            rng=np.random.default_rng(seed),
            paper_water_margin=0.4,
        )

    def test_all_78_agents_load_calibrated_no_all_zero_q(self):
        profiles = self._build_real_profiles()
        assert len(profiles) == 78, f"expected 78 real CRSS agents, got {len(profiles)}"

        agents = create_fql_agents(
            profiles, seed=42, fql_init="calibrated",
            fql_init_dir=FQL_INIT_DIR, crss_db_dir=CRSS_DB_DIR,
        )
        assert len(agents) == 78
        for aid, (_, state) in agents.items():
            assert state.q_table is not None
            assert not np.allclose(state.q_table, 0), (
                f"{aid}: calibrated Q_Table loaded as all-zero -- expected "
                "Hung & Yang's own trained end-of-2018 state"
            )
            assert state.init_provenance.get("fql_init") == "calibrated"
            assert state.init_provenance.get("q_table_sha256")
            assert state.init_provenance.get("prev_action_source") in {
                "ql_div_csv", "historical_annual_series",
            }
            assert state.init_provenance.get("state_grid_mode") == "hy_exact"

    def test_one_year_real_nogovernance_decrease_split_not_73_of_78(self, tmp_path):
        seed = 42
        np.random.seed(seed)
        profiles = self._build_real_profiles(seed=seed)

        config = WaterSystemConfig(seed=seed)
        env = IrrigationEnvironment(config)
        env.initialize_from_profiles(profiles)

        precip_csv = CRSS_DB_DIR / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"
        if precip_csv.exists():
            env.load_crss_precipitation(str(precip_csv))

        fql_agents = create_fql_agents(
            profiles, seed=seed, fql_init="calibrated",
            fql_init_dir=FQL_INIT_DIR, crss_db_dir=CRSS_DB_DIR,
        )
        profiles_dict = {p.agent_id: p for p in profiles}

        logs = run_simulation(
            env=env, fql_agents=fql_agents, profiles=profiles_dict,
            n_years=1, output_dir=tmp_path, seed=seed, no_governance=True,
        )
        year1 = [row for row in logs if row["year"] == 1]
        assert len(year1) == 78

        n_increase = sum(1 for r in year1 if r["yearly_decision"] == "increase_demand")
        n_decrease = sum(1 for r in year1 if r["yearly_decision"] == "decrease_demand")
        n_maintain = sum(1 for r in year1 if r["yearly_decision"] == "maintain_demand")
        print(
            f"[calibrated init] year-1 split: increase={n_increase} "
            f"decrease={n_decrease} maintain={n_maintain} / {len(year1)}"
        )
        assert n_decrease != 73, (
            f"calibrated init still mechanically decreases 73/78 agents in "
            f"year 1 (increase={n_increase} decrease={n_decrease} "
            f"maintain={n_maintain}) -- the fidelity fix did not change "
            "behavior"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
