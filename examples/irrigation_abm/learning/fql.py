"""
Farmer's Q-Learning (FQL) — Reinforcement learning for water demand adaptation.

Implements the Q-learning variant from Hung & Yang (2021):
  "Assessing Adaptive Irrigation Impacts on Water Scarcity in
   Nonstationary Environments — A Multi-Agent Reinforcement Learning Approach"
   Water Resources Research, 57, e2020WR029262.

Key features:
- POMDP-aware: agents cannot observe max available supply directly
- Bayesian transition probability learning with optional forgetting
- Preceding factor (binary signal) conditions Q-values
- Asymmetric reward: only penalizes unmet demand
- Epsilon-greedy action selection based on Q-value ordering

References:
- Sutton & Barto (1998). Reinforcement Learning: An Introduction.
- Watkins & Dayan (1992). Q-learning. Machine Learning.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List, Union

import numpy as np


class FQLCalibratedInitError(ValueError):
    """Raised by ``load_calibrated_tables`` when a Hung & Yang (2021)
    warm-start file (Q_Table/count/P_Tran) is missing, NUL-filled/corrupt,
    the wrong size, or contains non-finite values. Never silently
    substituted with a zero-initialised table -- see ``--fql-init`` in
    ``run_fql_baseline.py``.
    """


@dataclass
class FQLConfig:
    """Configuration for a single FQL agent.

    Calibrated parameter ranges from Hung & Yang 2021 Table 1:
        mu:      [0, 0.5]      Diversion change mean
        sigma:   [0.5, 1.5]    Diversion change std
        alpha:   [0.5, 0.95]   Learning rate
        gamma:   [0.5, 0.95]   Discount rate
        epsilon: [0.05, 0.3]   Exploration rate
        regret:  [0.5, 3.0]    Penalty sensitivity
    """

    mu: float = 0.20
    sigma: float = 0.70
    alpha: float = 0.75
    gamma: float = 0.70
    epsilon: float = 0.15
    regret: float = 1.50
    forget: bool = True
    n_states: int = 21
    n_actions: int = 2
    n_preceding: int = 2

    def validate(self) -> None:
        """Raise ValueError if parameters are out of calibrated range."""
        checks = [
            (0 <= self.mu <= 0.5, f"mu={self.mu} outside [0, 0.5]"),
            (0.5 <= self.sigma <= 1.5, f"sigma={self.sigma} outside [0.5, 1.5]"),
            (0.5 <= self.alpha <= 0.95, f"alpha={self.alpha} outside [0.5, 0.95]"),
            (0.5 <= self.gamma <= 0.95, f"gamma={self.gamma} outside [0.5, 0.95]"),
            (0.05 <= self.epsilon <= 0.3, f"epsilon={self.epsilon} outside [0.05, 0.3]"),
            (0.5 <= self.regret <= 3.0, f"regret={self.regret} outside [0.5, 3.0]"),
            (self.n_states > 0, "n_states must be positive"),
            (self.n_actions == 2, "n_actions must be 2 (increase/decrease)"),
        ]
        for ok, msg in checks:
            if not ok:
                raise ValueError(f"FQLConfig validation failed: {msg}")


# Three canonical behavioral clusters from Hung & Yang 2021 Section 4.1
CLUSTER_AGGRESSIVE = FQLConfig(
    mu=0.36, sigma=1.22, alpha=0.62, gamma=0.77,
    epsilon=0.16, regret=0.78, forget=True,
)
CLUSTER_FORWARD_LOOKING = FQLConfig(
    mu=0.20, sigma=0.60, alpha=0.85, gamma=0.78,
    epsilon=0.19, regret=2.22, forget=True,
)
CLUSTER_MYOPIC = FQLConfig(
    mu=0.16, sigma=0.87, alpha=0.67, gamma=0.64,
    epsilon=0.09, regret=1.54, forget=True,
)


@dataclass
class FQLState:
    """Mutable state carried by an FQL agent across time steps.

    Includes Q-table, transition count table, and the agent's
    discretised state boundaries.
    """

    # Agent-specific discrete state boundaries (n_states values,
    # evenly spaced between historical min and max diversion) under
    # state_grid_mode="linspace" (default; --fql-init zero). Under
    # state_grid_mode="hy_exact" (--fql-init calibrated) this instead
    # holds the agent's ACTUAL Div_States column (often NOT a 0-to-top
    # linspace -- see state_grid_mode below), and hy_bin_size must also
    # be set.
    state_bounds: np.ndarray = field(default_factory=lambda: np.linspace(0, 200, 21))

    # "linspace" (default): today's legacy discretisation --
    # _div_to_state()/_sample_actions() use state_bounds[0]/bin_size
    # directly, byte-identical to pre-2026-09-27 behavior.
    # "hy_exact": ABM_CRSS_coupling.py's own Div_to_State rule (lines
    # 122-132) against the real Div_States column in state_bounds, and
    # hy_bin_size (= agt_states[2] - agt_states[1], NOT
    # state_bounds[1]-state_bounds[0]) for the action-magnitude step.
    # P1-a fix (2026-09-27 review): 19 of 22 LB agents' Div_States
    # columns are "[0, first_bin, first_bin+step, ..., top]" -- index 0
    # is a wide catch-all down to first_bin, NOT part of a uniform
    # 0-to-top sequence -- so treating them as np.linspace(0, top, 21)
    # (the "linspace" mode) reads the wrong state index. A flag, not a
    # per-call parameter, so the two rules can never be mixed within one
    # agent's lifetime.
    state_grid_mode: str = "linspace"

    # H&Y's own bin size (agt_states[2] - agt_states[1]); only read when
    # state_grid_mode == "hy_exact". None under "linspace" (bin_size
    # property below is used instead).
    hy_bin_size: Optional[float] = None

    # WP5 spec 5.4 (irrigation_v3_spec_2026-09-28.md): the v3 action-
    # magnitude bin, step_bin_af / demand_per_grid_unit (k) -- SEPARATE
    # from hy_bin_size above. hy_bin_size still drives the STATE grid
    # (_hy_div_to_state) on H&Y's own unconverted diversion-unit grid;
    # action_bin_size drives only _sample_actions' magnitude draw, on the
    # v3 environment's own (possibly WP2 2.4-rescaled) step_bin_af, so an
    # Upper Basin FQL agent's request-size distribution matches the
    # language-model arms' typical step for the same 8 rescaled agents.
    # None (the default) preserves every pre-WP5 caller byte-for-byte:
    # _sample_actions then falls back to hy_bin_size (hy_exact mode) or
    # bin_size (linspace mode), exactly as before this field existed.
    action_bin_size: Optional[float] = None

    # Q-table: (n_preceding, n_states, n_actions)
    q_table: Optional[np.ndarray] = None

    # Transition count table: (n_preceding, n_actions, n_states, n_states)
    count_table: Optional[np.ndarray] = None

    # Transition probability: (n_preceding, n_actions, n_states, n_states)
    p_transition: Optional[np.ndarray] = None

    # Previous-step values for temporal-difference learning
    prev_diversion: float = 0.0
    prev_action: float = 0.0
    prev_diversion_request: float = 0.0

    # Provenance for calibrated (Hung & Yang warm-start) initialization;
    # populated by run_fql_baseline.create_fql_agents() only when
    # --fql-init calibrated. Empty dict under --fql-init zero (today's
    # zero-initialised construction path).
    init_provenance: Dict[str, Any] = field(default_factory=dict)

    def initialize(self, config: FQLConfig, rng: Optional[np.random.Generator] = None) -> None:
        """Allocate Q-table and count tables with initial values."""
        nf = config.n_preceding
        ns = config.n_states
        na = config.n_actions

        if self.q_table is None:
            self.q_table = np.zeros((nf, ns, na))
        if self.count_table is None:
            # Initialize with 1 to avoid division-by-zero in posterior
            self.count_table = np.ones((nf, na, ns, ns))
        if self.p_transition is None:
            # Uniform initial transition probabilities
            self.p_transition = np.ones((nf, na, ns, ns)) / ns

    @property
    def bin_size(self) -> float:
        """Width of each discretisation bin."""
        if len(self.state_bounds) < 2:
            return 1.0
        return float(self.state_bounds[1] - self.state_bounds[0])


def _hy_div_to_state(
    div_y: float,
    agt_states: np.ndarray,
    bin_size: float,
    n_states: int,
) -> int:
    """Exact port of ABM_CRSS_coupling.py's Div_to_State (lines 122-132).

        bin_size = agt_states[2] - agt_states[1]
        temp = int((div_y - agt_states[1]) / bin_size)
        if temp <= (n_states-2) and div_y >= agt_states[1]:
            s_i = temp + 1
        elif div_y < agt_states[1]:
            s_i = 0
        else:
            s_i = n_states - 1
        return s_i

    ``agt_states`` is the agent's real Div_States column (21 values);
    ``bin_size`` must be passed in (state.hy_bin_size, = agt_states[2] -
    agt_states[1]) rather than recomputed here, so the same number the
    caller used for _sample_actions' magnitude step is also the one used
    for discretisation -- exactly as Q_learning() computes it once and
    reuses it for both (line 191).

    Deliberately NOT a 0-to-top linspace read: state 0 is a wide
    catch-all for anything below agt_states[1] (P1-a fix, 2026-09-27
    review -- 19 of 22 LB agents' real grids have this shape, e.g.
    MohaveValleyIDD = [0, 12000, 14000, ..., 50000], where the [0,12000)
    range collapses to state 0 and states 1-20 are then uniform
    2000-AF-wide bins from 12000 to 50000).
    """
    temp = int((div_y - agt_states[1]) / bin_size)
    if temp <= (n_states - 2) and div_y >= agt_states[1]:
        return temp + 1
    elif div_y < agt_states[1]:
        return 0
    else:
        return n_states - 1


# -----------------------------------------------------------------------
# Calibrated (Hung & Yang 2021) warm-start table loading
# -----------------------------------------------------------------------
#
# Hung & Yang's own coupling script (ref/RL-ABM-CRSS/ABM_CRSS_coupling.py,
# Q_learning()) always loads three per-agent text files at every step,
# never zero-initialised tables:
#
#   Q_Table_<agt>.txt   -- data = np.loadtxt(Q_path)
#                           Q = data.reshape((n_f, n_states, n_a))          (line 203)
#   count_<agt>.txt      -- data = np.loadtxt(count_path)
#                           count = data.reshape((n_f, n_a, n_states, n_states))  (line 208)
#   P_Tran_<agt>.txt      -- written (Save_Array) but never read back inside
#                           Q_learning(): Posterior() rebuilds P_tran fully
#                           from `count` on every call, nested (n_f, n_a,
#                           n_states, n_states) exactly like count (lines
#                           148-155). We still load and validate it (it is
#                           part of the same on-disk state and
#                           initialization_ABM_CRSS_v3.py copies it
#                           alongside the other two), but functionally the
#                           first _update_posterior() call overwrites it.
#
# Those three files are seeded, at t=0, by
# initialization_ABM_CRSS_v3.py copying every file in
# CRSS_DB/Initial_Files/All into the coupling working directory (lines
# 23-27) -- i.e. Initial_Files/All *is* Hung & Yang's calibrated
# end-of-2018 agent state.
#
# Axis mapping: our FQLState conventions (q_table: (n_preceding,
# n_states, n_actions); count_table / p_transition: (n_preceding,
# n_actions, n_states, n_states)) are IDENTICAL to the reshape calls
# above -- no permutation is needed, only a straight reshape after
# stripping Save_Array's "# Array shape: ..." / "# New slice" comment
# lines (np.loadtxt's default comments='#' already does this).
def _read_hy_array(
    path: Path,
    expected_shape: Tuple[int, ...],
    label: str,
    agent_id: str,
) -> Tuple[np.ndarray, str]:
    """Load and validate one Hung & Yang state-table text file.

    Raises FQLCalibratedInitError (never falls back to zeros) when the
    file is missing, NUL-filled/corrupt, the wrong size for
    ``expected_shape``, or contains non-finite values.

    Returns (array reshaped to expected_shape, sha256 hex digest of the
    raw file bytes).
    """
    if not path.is_file():
        raise FQLCalibratedInitError(
            f"[{agent_id}] {label} calibrated-init file not found: {path}"
        )

    raw = path.read_bytes()
    if b"\x00" in raw:
        raise FQLCalibratedInitError(
            f"[{agent_id}] {label} file is NUL-filled/corrupted "
            f"(contains a NUL byte): {path}"
        )
    digest = hashlib.sha256(raw).hexdigest()

    try:
        data = np.loadtxt(path, comments="#")
    except Exception as exc:  # malformed / non-numeric content
        raise FQLCalibratedInitError(
            f"[{agent_id}] {label} file could not be parsed as "
            f"whitespace-delimited floats: {path} ({exc})"
        ) from exc

    expected_size = int(np.prod(expected_shape))
    if data.size != expected_size:
        raise FQLCalibratedInitError(
            f"[{agent_id}] {label} file {path} has {data.size} values, "
            f"expected {expected_size} for shape {expected_shape} "
            f"(our FQLState convention); Hung & Yang's own reshape at "
            f"ABM_CRSS_coupling.py Q_learning() uses the same shape, so a "
            f"mismatch here means this file does not belong to this "
            f"agent/n_states configuration."
        )

    array = data.reshape(expected_shape)
    if not np.all(np.isfinite(array)):
        raise FQLCalibratedInitError(
            f"[{agent_id}] {label} file contains non-finite (NaN/inf) "
            f"values: {path}"
        )
    return array, digest


def load_calibrated_tables(
    agent_id: str,
    init_dir: Union[str, Path],
    config: "FQLConfig",
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, str]]:
    """Load one agent's calibrated Q_Table / count / P_Tran tables.

    Mirrors ``ABM_CRSS_coupling.py``'s ``Q_learning()``, which always
    loads ``Q_Table_<agt>.txt`` / ``count_<agt>.txt`` / ``P_Tran_<agt>.txt``
    (see the module-level comment above for the exact reshape lines and
    axis mapping). ``agent_id`` must match Hung & Yang's own agent naming
    exactly (spaces preserved, e.g. ``"Fort Mohave Ind Res AZ"``) -- the
    same identifier our ``IrrigationAgentProfile.agent_id`` already uses
    (both come from the same ``Div_States/{UB,LB}_discrete_states.csv``
    column headers).

    Raises FQLCalibratedInitError on any missing/corrupt/malformed/
    non-finite file (see ``_read_hy_array``) -- no silent zero fallback.

    Returns (q_table, count_table, p_transition, file_hashes) where
    file_hashes = {"q_table": sha256, "count": sha256, "p_transition": sha256}
    of each file's raw bytes (provenance).
    """
    base = Path(init_dir)
    nf, ns, na = config.n_preceding, config.n_states, config.n_actions

    q_table, q_sha = _read_hy_array(
        base / f"Q_Table_{agent_id}.txt", (nf, ns, na), "Q_Table", agent_id
    )
    count_table, c_sha = _read_hy_array(
        base / f"count_{agent_id}.txt", (nf, na, ns, ns), "count", agent_id
    )
    p_transition, p_sha = _read_hy_array(
        base / f"P_Tran_{agent_id}.txt", (nf, na, ns, ns), "P_Tran", agent_id
    )

    return (
        q_table,
        count_table,
        p_transition,
        {"q_table": q_sha, "count": c_sha, "p_transition": p_sha},
    )


class FQLAgent:
    """Farmer's Q-Learning agent.

    Usage::

        config = FQLConfig(mu=0.36, sigma=1.22, alpha=0.62,
                           gamma=0.77, epsilon=0.16, regret=0.78)
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        state.initialize(config)

        agent = FQLAgent(config)

        # Each simulation year:
        action = agent.step(
            state=state,
            current_diversion=actual_div,
            preceding_factor=(f_t, f_t_next),
        )
        new_request = actual_div + action
    """

    def __init__(
        self,
        config: FQLConfig,
        rng: Optional[np.random.Generator] = None,
    ):
        self.config = config
        self.rng = rng or np.random.default_rng()

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def step(
        self,
        state: FQLState,
        current_diversion: float,
        preceding_factor: Tuple[int, int],
    ) -> float:
        """Execute one FQL step and return the action (change in diversion).

        Args:
            state: Mutable FQLState with Q-table and history.
            current_diversion: Actual diversion received this period (Div_y).
            preceding_factor: (f_t, f_t_next) — binary preceding factor
                at time *t* and *t+1*.  For Lower Basin agents this is
                derived from Lake Mead water level change; for Upper Basin
                agents from winter precipitation change.

        Returns:
            a_t_new: Signed diversion change.  Positive = increase request,
            negative = decrease.  The new diversion request should be
            ``current_diversion + a_t_new``.
        """
        cfg = self.config
        ns = cfg.n_states
        f_t, f_next = preceding_factor

        # --- Discretise current and previous diversions ---
        s_t = self._div_to_state(current_diversion, state)
        s_0 = self._div_to_state(state.prev_diversion, state)

        # Previous action index: 0 = decrease, 1 = increase
        a_t_idx = int(state.prev_action > 0)

        # --- Bayesian posterior update on transition probabilities ---
        self._update_posterior(state, a_t_idx, f_t, s_0, s_t)

        # --- Reward ---
        reward = self._compute_reward(
            current_diversion, state.prev_diversion, state.prev_action
        )

        # --- Expected future Q ---
        e_future_q = self._expected_future_q(state, f_next, s_t)

        # --- Q-update (TD(0)) ---
        old_q = state.q_table[f_t, s_0, a_t_idx]
        state.q_table[f_t, s_0, a_t_idx] = old_q + cfg.alpha * (
            reward + cfg.gamma * e_future_q - old_q
        )

        # --- Action selection (epsilon-greedy) ---
        actions = self._sample_actions(state)
        a_t_new = self._epsilon_greedy(state, f_next, s_t, actions)

        # Enforce non-negative diversion
        if current_diversion + a_t_new <= 0:
            a_t_new = -current_diversion

        # --- Update history ---
        state.prev_diversion = current_diversion
        state.prev_action = a_t_new
        state.prev_diversion_request = current_diversion + a_t_new

        return float(a_t_new)

    # -----------------------------------------------------------------
    # Internal methods
    # -----------------------------------------------------------------

    def _div_to_state(self, div_y: float, state: FQLState) -> int:
        """Map continuous diversion to discrete state index [0, n_states-1].

        state.state_grid_mode gates which rule applies (never mixed):
        "hy_exact" uses ABM_CRSS_coupling.py's own Div_to_State exactly
        (see _hy_div_to_state); "linspace" (default) is today's legacy
        rule, byte-identical to pre-2026-09-27 behavior.
        """
        if state.state_grid_mode == "hy_exact":
            return _hy_div_to_state(
                div_y, state.state_bounds, state.hy_bin_size, self.config.n_states
            )
        ns = self.config.n_states
        bounds = state.state_bounds
        bs = state.bin_size
        if bs == 0:
            return 0
        idx = int((div_y - bounds[0]) / bs)
        return max(0, min(ns - 1, idx))

    def _update_posterior(
        self,
        state: FQLState,
        a_t_idx: int,
        f_t: int,
        s_0: int,
        s_t: int,
    ) -> None:
        """Bayesian update of transition count and probability tables."""
        ct = state.count_table

        # Optional forgetting factor
        if self.config.forget:
            row_sum = ct[f_t, a_t_idx, s_0, :].sum()
            if row_sum > 1:
                decay = (row_sum - 1) / row_sum
                ct[f_t, a_t_idx, s_0, :] *= decay

        # Increment observation
        ct[f_t, a_t_idx, s_0, s_t] += 1

        # Recompute full transition probability table
        nf, na = self.config.n_preceding, self.config.n_actions
        for j in range(nf):
            for k in range(na):
                row_sums = ct[j, k, :, :].sum(axis=1, keepdims=True)
                row_sums = np.where(row_sums == 0, 1, row_sums)
                state.p_transition[j, k, :, :] = ct[j, k, :, :] / row_sums

    def _compute_reward(
        self,
        div_y: float,
        div_y0: float,
        a_t: float,
    ) -> float:
        """Asymmetric reward: penalises unmet demand only.

        reward = Div_y + regret * min(0, Div_y - (Div_y0 + a_t))
        """
        deviation = div_y - (div_y0 + a_t)
        if deviation >= 0:
            deviation = 0.0
        penalty = self.config.regret * deviation
        return div_y + penalty

    def _expected_future_q(
        self, state: FQLState, f_next: int, s_t: int
    ) -> float:
        """Compute max expected future Q-value across actions.

        E_Q_a(k) = sum_s'[ P(s'|s_t, a=k, f_next) * Q(f_next, s', k) ]
        """
        na = self.config.n_actions
        e_q = np.zeros(na)
        for k in range(na):
            p_action = state.p_transition[f_next, k, s_t, :]
            e_q[k] = np.dot(state.q_table[f_next, :, k], p_action)
        return float(np.max(e_q))

    def _sample_actions(self, state: FQLState) -> np.ndarray:
        """Sample action magnitudes from N(mu, sigma) * bin_size.

        WP5 spec 5.4: state.action_bin_size, when set, takes priority over
        both other sources -- it is the v3 request-formula's own bin
        (step_bin_af / k), independent of the state grid. When it is None
        (every pre-WP5 caller, and every "zero"-init/synthetic FQLState),
        this falls back to the pre-WP5 rule: under state_grid_mode ==
        "hy_exact" the bin size is state.hy_bin_size (H&Y's
        agt_states[2] - agt_states[1], the same number _hy_div_to_state
        uses -- P1-a fix), not state.bin_size (= state_bounds[1] -
        state_bounds[0], which for a non-uniform real grid is a different,
        wrong value). Under "linspace" (default) this is state.bin_size,
        unchanged from pre-2026-09-27 behavior.

        Returns array of length 2: [decrease_magnitude, increase_magnitude].
        """
        cfg = self.config
        if state.action_bin_size is not None:
            bs = state.action_bin_size
        elif state.state_grid_mode == "hy_exact":
            bs = state.hy_bin_size
        else:
            bs = state.bin_size
        raw = np.abs(self.rng.normal(0, cfg.sigma, size=2))
        magnitudes = (cfg.mu + raw) * bs
        return np.array([-magnitudes[0], magnitudes[1]])

    def _epsilon_greedy(
        self,
        state: FQLState,
        f_next: int,
        s_t: int,
        actions: np.ndarray,
    ) -> float:
        """Select action using epsilon-greedy based on Q-value ordering."""
        eps = self.config.epsilon
        q_decrease = state.q_table[f_next, s_t, 0]
        q_increase = state.q_table[f_next, s_t, 1]

        if q_decrease <= q_increase:
            # Increase has higher Q → exploit increase, explore decrease
            chosen = self.rng.choice(actions, p=[eps, 1 - eps])
        else:
            # Decrease has higher Q → exploit decrease, explore increase
            chosen = self.rng.choice(actions, p=[1 - eps, eps])

        return float(chosen)

    # -----------------------------------------------------------------
    # Serialization
    # -----------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize config (not state) for audit/logging."""
        cfg = self.config
        return {
            "algorithm": "FQL",
            "mu": cfg.mu,
            "sigma": cfg.sigma,
            "alpha": cfg.alpha,
            "gamma": cfg.gamma,
            "epsilon": cfg.epsilon,
            "regret": cfg.regret,
            "forget": cfg.forget,
            "n_states": cfg.n_states,
        }
