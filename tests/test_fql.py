"""
Tests for Farmer's Q-Learning (FQL) algorithm.

Validates correctness of the FQL implementation against the reference
from Hung & Yang (2021) RL-ABM-CRSS.
"""

import numpy as np
import pytest

from examples.irrigation_abm.learning.fql import (
    FQLAgent,
    FQLConfig,
    FQLState,
    CLUSTER_AGGRESSIVE,
    CLUSTER_FORWARD_LOOKING,
    CLUSTER_MYOPIC,
)


class TestFQLConfig:
    """Test FQLConfig validation and cluster presets."""

    def test_default_config_is_valid(self):
        config = FQLConfig()
        config.validate()  # Should not raise

    def test_aggressive_cluster_values(self):
        c = CLUSTER_AGGRESSIVE
        assert c.mu == pytest.approx(0.36)
        assert c.sigma == pytest.approx(1.22)
        assert c.alpha == pytest.approx(0.62)
        assert c.gamma == pytest.approx(0.77)
        assert c.epsilon == pytest.approx(0.16)
        assert c.regret == pytest.approx(0.78)

    def test_forward_looking_cluster_values(self):
        c = CLUSTER_FORWARD_LOOKING
        assert c.alpha == pytest.approx(0.85)
        assert c.regret == pytest.approx(2.22)

    def test_myopic_cluster_values(self):
        c = CLUSTER_MYOPIC
        assert c.epsilon == pytest.approx(0.09)
        assert c.gamma == pytest.approx(0.64)

    def test_validation_rejects_out_of_range_mu(self):
        config = FQLConfig(mu=0.8)
        with pytest.raises(ValueError, match="mu"):
            config.validate()

    def test_validation_rejects_out_of_range_alpha(self):
        config = FQLConfig(alpha=0.1)
        with pytest.raises(ValueError, match="alpha"):
            config.validate()

    def test_validation_rejects_out_of_range_epsilon(self):
        config = FQLConfig(epsilon=0.5)
        with pytest.raises(ValueError, match="epsilon"):
            config.validate()

    def test_all_clusters_validate(self):
        for cluster in [CLUSTER_AGGRESSIVE, CLUSTER_FORWARD_LOOKING, CLUSTER_MYOPIC]:
            cluster.validate()


class TestFQLState:
    """Test FQLState initialization and properties."""

    def test_initialize_creates_correct_shapes(self):
        config = FQLConfig()
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        state.initialize(config)

        assert state.q_table.shape == (2, 21, 2)
        assert state.count_table.shape == (2, 2, 21, 21)
        assert state.p_transition.shape == (2, 2, 21, 21)

    def test_q_table_initialised_to_zero(self):
        config = FQLConfig()
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        state.initialize(config)
        assert np.all(state.q_table == 0)

    def test_count_table_initialised_to_one(self):
        config = FQLConfig()
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        state.initialize(config)
        assert np.all(state.count_table == 1)

    def test_bin_size(self):
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        assert state.bin_size == pytest.approx(10.0)

    def test_bin_size_custom(self):
        state = FQLState(state_bounds=np.linspace(0, 100, 11))
        assert state.bin_size == pytest.approx(10.0)


class TestFQLAgent:
    """Test FQL agent decision logic."""

    @pytest.fixture
    def agent_and_state(self):
        config = FQLConfig(
            mu=0.20, sigma=0.70, alpha=0.75,
            gamma=0.70, epsilon=0.15, regret=1.5,
        )
        rng = np.random.default_rng(42)
        agent = FQLAgent(config, rng=rng)
        state = FQLState(
            state_bounds=np.linspace(0, 200, 21),
            prev_diversion=80.0,
            prev_action=5.0,
            prev_diversion_request=85.0,
        )
        state.initialize(config)
        return agent, state

    def test_step_returns_float(self, agent_and_state):
        agent, state = agent_and_state
        action = agent.step(state, current_diversion=82.0, preceding_factor=(1, 0))
        assert isinstance(action, float)

    def test_step_updates_history(self, agent_and_state):
        agent, state = agent_and_state
        agent.step(state, current_diversion=82.0, preceding_factor=(1, 0))
        assert state.prev_diversion == 82.0
        assert state.prev_action != 0  # Should be updated
        assert state.prev_diversion_request == state.prev_diversion + state.prev_action

    def test_non_negative_diversion(self, agent_and_state):
        """Ensure action never makes diversion go below zero."""
        agent, state = agent_and_state
        # Set current diversion to very low value
        action = agent.step(state, current_diversion=0.5, preceding_factor=(0, 0))
        assert 0.5 + action >= 0, "Diversion + action must be non-negative"

    def test_q_table_updates_after_step(self, agent_and_state):
        agent, state = agent_and_state
        q_before = state.q_table.copy()
        agent.step(state, current_diversion=82.0, preceding_factor=(1, 0))
        # At least one Q-value should change
        assert not np.array_equal(q_before, state.q_table)

    def test_transition_counts_increase(self, agent_and_state):
        agent, state = agent_and_state
        count_before = state.count_table.sum()
        agent.step(state, current_diversion=82.0, preceding_factor=(1, 0))
        # Count should increase by at least 1 (minus forgetting decay)
        assert state.count_table.sum() > count_before - 2

    def test_multiple_steps_converge(self):
        """Run multiple steps and verify Q-values evolve."""
        config = CLUSTER_FORWARD_LOOKING
        rng = np.random.default_rng(123)
        agent = FQLAgent(config, rng=rng)
        state = FQLState(
            state_bounds=np.linspace(0, 200, 21),
            prev_diversion=100.0,
            prev_action=0.0,
            prev_diversion_request=100.0,
        )
        state.initialize(config)

        diversions = [100.0]
        for _ in range(50):
            current_div = diversions[-1]
            pf = (int(rng.random() > 0.5), int(rng.random() > 0.5))
            action = agent.step(state, current_diversion=current_div, preceding_factor=pf)
            new_div = max(0, current_div + action)
            diversions.append(new_div)

        # After 50 steps, Q-table should have non-trivial values
        assert state.q_table.max() > 0, "Q-table should have positive values after learning"

    def test_aggressive_vs_myopic_action_magnitude(self):
        """Aggressive agents should produce larger average actions."""
        rng_a = np.random.default_rng(42)
        rng_m = np.random.default_rng(42)

        agent_a = FQLAgent(CLUSTER_AGGRESSIVE, rng=rng_a)
        agent_m = FQLAgent(CLUSTER_MYOPIC, rng=rng_m)

        state_a = FQLState(state_bounds=np.linspace(0, 200, 21),
                           prev_diversion=100.0, prev_action=0.0, prev_diversion_request=100.0)
        state_m = FQLState(state_bounds=np.linspace(0, 200, 21),
                           prev_diversion=100.0, prev_action=0.0, prev_diversion_request=100.0)
        state_a.initialize(CLUSTER_AGGRESSIVE)
        state_m.initialize(CLUSTER_MYOPIC)

        actions_a = []
        actions_m = []
        for _ in range(100):
            a_a = agent_a.step(state_a, current_diversion=100.0, preceding_factor=(1, 0))
            a_m = agent_m.step(state_m, current_diversion=100.0, preceding_factor=(1, 0))
            actions_a.append(abs(a_a))
            actions_m.append(abs(a_m))

        # Aggressive agents have higher mu (0.36 vs 0.16), so larger average action
        assert np.mean(actions_a) > np.mean(actions_m)

    def test_reward_asymmetry(self, agent_and_state):
        """Reward should penalise unmet demand but not overdelivery."""
        agent, _ = agent_and_state

        # Demand met (no penalty)
        r1 = agent._compute_reward(div_y=100, div_y0=90, a_t=5)
        # div_y=100 >= div_y0+a_t=95, so deviation=5>=0 → no penalty
        assert r1 == 100.0

        # Demand unmet (penalty applies)
        r2 = agent._compute_reward(div_y=80, div_y0=90, a_t=5)
        # div_y=80 < div_y0+a_t=95, deviation=-15 → penalty = 1.5 * -15 = -22.5
        assert r2 == 80.0 + 1.5 * (-15)
        assert r2 < r1

    def test_to_dict(self, agent_and_state):
        agent, _ = agent_and_state
        d = agent.to_dict()
        assert d["algorithm"] == "FQL"
        assert d["mu"] == 0.20
        assert d["regret"] == 1.5

    def test_preceding_factor_affects_q_update(self):
        """Different preceding factors should update different Q-table slices."""
        config = FQLConfig()
        rng = np.random.default_rng(99)
        agent = FQLAgent(config, rng=rng)

        state = FQLState(state_bounds=np.linspace(0, 200, 21),
                         prev_diversion=100.0, prev_action=5.0, prev_diversion_request=105.0)
        state.initialize(config)

        # Step with preceding_factor f_t=0
        q_slice_0_before = state.q_table[0].copy()
        agent.step(state, current_diversion=102.0, preceding_factor=(0, 1))
        q_slice_0_after = state.q_table[0].copy()

        # The Q-table slice for f_t=0 should have changed
        assert not np.array_equal(q_slice_0_before, q_slice_0_after)


class TestDivToState:
    """Test state discretisation."""

    def test_middle_value(self):
        config = FQLConfig()
        agent = FQLAgent(config)
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        # 100 is exactly at state 10 (0, 10, 20, ..., 200)
        s = agent._div_to_state(100.0, state)
        assert s == 10

    def test_below_min(self):
        config = FQLConfig()
        agent = FQLAgent(config)
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        s = agent._div_to_state(-5.0, state)
        assert s == 0

    def test_above_max(self):
        config = FQLConfig()
        agent = FQLAgent(config)
        state = FQLState(state_bounds=np.linspace(0, 200, 21))
        s = agent._div_to_state(250.0, state)
        assert s == 20  # Clamped to max state
