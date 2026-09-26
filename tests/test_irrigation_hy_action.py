"""Hung and Yang (2021) action model for irrigation (2026-09-26).

ref/RL-ABM-CRSS/ABM_CRSS_coupling.py (Q_learning):
    actions = (mu + abs(np.random.normal(0, sigma))) * [-1, 1] * bin_size
with per-agent mu, sigma and bin_size = agt_states[2] - agt_states[1].
"""
from pathlib import Path
from statistics import NormalDist
from types import SimpleNamespace

import numpy as np
import pytest

from examples.irrigation_abm.irrigation_env import (
    HALF_NORMAL_MEDIAN_Z,
    IrrigationEnvironment,
    WaterSystemConfig,
    hy_step_af,
    hy_threshold_af,
)

ROOT = Path(__file__).resolve().parents[1]


def test_draw_reproduces_the_hy_formula_on_a_fixed_rng():
    """(mu + |z|) x bin with |z| = sigma * Phi^-1((1 + q) / 2), q from the
    same uniform the function consumes."""
    mu, sigma, b = 0.33, 1.2, 3_000.0
    for cls, q_of in (("small", lambda u: 0.5 * u), ("large", lambda u: 0.5 + 0.5 * u),
                      ("any", lambda u: u)):
        u = float(np.random.default_rng(7).random())
        z = sigma * NormalDist().inv_cdf((1.0 + q_of(u)) / 2.0)
        assert hy_step_af(np.random.default_rng(7), mu, sigma, b, cls) == pytest.approx((mu + z) * b)


def test_pooled_classes_match_the_hy_distribution():
    """Small and large are the two halves of (mu + |N(0, sigma)|) x bin:
    pooled 50/50 their mean and quartiles match a direct H&Y draw."""
    mu, sigma, b = 0.218, 0.923, 1_000.0
    rng = np.random.default_rng(3)
    n = 20_000
    pooled = [hy_step_af(rng, mu, sigma, b, "small") for _ in range(n)] + \
             [hy_step_af(rng, mu, sigma, b, "large") for _ in range(n)]
    direct = (mu + np.abs(np.random.default_rng(4).normal(0, sigma, size=2 * n))) * b
    assert np.mean(pooled) == pytest.approx(np.mean(direct), rel=0.02)
    for qq in (0.25, 0.5, 0.75):
        assert np.quantile(pooled, qq) == pytest.approx(np.quantile(direct, qq), rel=0.03)
    assert np.mean(pooled) == pytest.approx((mu + sigma * np.sqrt(2 / np.pi)) * b, rel=0.02)


def test_small_at_or_below_threshold_below_large():
    mu, sigma, b = 0.2, 0.9, 2_000.0
    t = hy_threshold_af(mu, sigma, b)
    assert t == pytest.approx((mu + HALF_NORMAL_MEDIAN_Z * sigma) * b)
    rng = np.random.default_rng(11)
    small = [hy_step_af(rng, mu, sigma, b, "small") for _ in range(2000)]
    large = [hy_step_af(rng, mu, sigma, b, "large") for _ in range(2000)]
    assert max(small) <= t + 1e-9 < min(large)
    assert min(small) >= mu * b - 1e-9


def _env_one(agent_request=500_000.0):
    env = IrrigationEnvironment(WaterSystemConfig(seed=5))
    env._agents["A"] = {
        "basin": "lower_basin", "diversion": agent_request, "request": agent_request,
        "water_right": 1_000_000.0, "curtailment_ratio": 0.0, "delivery_ratio": 1.0,
        "gap_reason": "none", "at_allocation_cap": False, "has_efficient_system": False,
        "below_minimum_utilisation": False, "cluster": "x",
        "mu": 0.3, "sigma": 1.1, "bin_size_af": 5_000.0,
    }
    return env


def test_each_direction_applies_its_own_draw_with_its_sign():
    """An increase adds its own H&Y draw and a decrease subtracts its own
    (the skill is part of the RNG key, so the two draws differ); the sign
    is the only difference in how a draw is applied, away from the caps."""
    for size in ("small", "large"):
        up, down = _env_one(), _env_one()
        a = up.execute_skill(SimpleNamespace(skill_name=f"increase_{size}", agent_id="A", parameters={}))
        # same (seed, year, agent) key, but the skill is part of the key, so
        # draw the decrease with the increase's stream to compare signs
        step = hy_step_af(down._decision_rng("A", f"increase_{size}"), 0.3, 1.1, 5_000.0, size)
        assert a.state_changes["request"] == pytest.approx(500_000.0 + step)
        d = down.execute_skill(SimpleNamespace(skill_name=f"decrease_{size}", agent_id="A", parameters={}))
        step_d = hy_step_af(up._decision_rng("A", f"decrease_{size}"), 0.3, 1.1, 5_000.0, size)
        assert d.state_changes["request"] == pytest.approx(500_000.0 - step_d)
        assert a.state_changes["magnitude_class"] == d.state_changes["magnitude_class"] == size
        assert a.state_changes["magnitude_af"] == pytest.approx(step)
        assert d.state_changes["magnitude_af"] == pytest.approx(step_d)


def test_maintain_is_zero_and_no_magnitude():
    env = _env_one()
    r = env.execute_skill(SimpleNamespace(skill_name="maintain_demand", agent_id="A", parameters={}))
    assert r.state_changes["request"] == 500_000.0
    assert "magnitude_af" not in r.state_changes


def test_increase_capped_at_water_right():
    env = _env_one(agent_request=999_000.0)
    r = env.execute_skill(SimpleNamespace(skill_name="increase_large", agent_id="A", parameters={}))
    assert r.state_changes["request"] == 1_000_000.0
    assert r.state_changes["magnitude_af"] == pytest.approx(1_000.0)


def test_persona_scale_gone_from_config_and_code():
    import yaml
    text = (ROOT / "examples/irrigation_abm/config/agent_types.yaml").read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    assert "skill_magnitude" not in cfg
    for persona in cfg["personas"].values():
        for gone in ("persona_scale", "magnitude_default", "magnitude_min", "magnitude_max",
                     "magnitude_sigma", "exploration_rate"):
            assert gone not in persona
    reg = yaml.safe_load((ROOT / "examples/irrigation_abm/config/skill_registry.yaml").read_text(encoding="utf-8"))
    for sk in reg["skills"]:
        ic = sk.get("institutional_constraints") or {}
        assert not {"magnitude_type", "max_magnitude_pct", "magnitude_default"} & set(ic)
    for rel in ("irrigation_env.py", "irrigation_personas.py", "run_experiment.py", "run_fql_baseline.py"):
        src = (ROOT / "examples/irrigation_abm" / rel).read_text(encoding="utf-8")
        code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
        assert "persona_scale" not in code.replace("persona_scale / skill_magnitude", "")


CRSS = ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
PARAMS = ROOT / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"


@pytest.mark.skipif(not (CRSS.exists() and PARAMS.exists()), reason="CRSS data not present")
def test_real_profiles_carry_per_agent_hy_parameters():
    import pandas as pd
    from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

    profiles = create_profiles_from_data(str(PARAMS), str(CRSS), rng=np.random.default_rng(1))
    assert len(profiles) == 78
    lb = pd.read_csv(CRSS / "Div_States" / "LB_discrete_states.csv")
    ub = pd.read_csv(CRSS / "Div_States" / "UB_discrete_states.csv")
    params = pd.read_csv(PARAMS, index_col=0)
    for p in profiles:
        col = (lb if p.basin == "lower_basin" else ub)[p.agent_id]
        assert p.bin_size_af == pytest.approx(float(col.iloc[2] - col.iloc[1]))
        assert p.bin_size_af > 0
        assert p.mu >= 0 and p.sigma >= 0
    mohave = next(p for p in profiles if p.agent_id == "MohaveValleyIDD")
    assert mohave.mu == pytest.approx(float(params.loc["mu", "MohaveValleyIDD"]))
    assert mohave.sigma == pytest.approx(float(params.loc["sigma", "MohaveValleyIDD"]))
    env = IrrigationEnvironment(WaterSystemConfig(seed=1))
    env.initialize_from_profiles(profiles)
    assert env._agents["MohaveValleyIDD"]["bin_size_af"] == pytest.approx(mohave.bin_size_af)


def test_zero_request_logs_no_percent():
    env = _env_one(agent_request=0.0)
    r = env.execute_skill(SimpleNamespace(skill_name="increase_small", agent_id="A", parameters={}))
    assert r.state_changes["magnitude_af"] > 0
    assert r.state_changes["magnitude_pct_applied"] is None
    assert r.action_context["magnitude_pct"] is None


def test_negative_mu_cannot_flip_direction():
    rng = np.random.default_rng(0)
    assert hy_step_af(rng, -5.0, 0.5, 1_000.0, "small") >= 0.0
