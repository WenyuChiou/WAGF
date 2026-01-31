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

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, List

import numpy as np


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
    # evenly spaced between historical min and max diversion).
    state_bounds: np.ndarray = field(default_factory=lambda: np.linspace(0, 200, 21))

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
        """Map continuous diversion to discrete state index [0, n_states-1]."""
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

        Returns array of length 2: [decrease_magnitude, increase_magnitude].
        """
        cfg = self.config
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
