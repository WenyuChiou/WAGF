"""The key-collision diagnostic in SkillBrokerEngine.process_step (R5 walk
finding 10): only keys the agent state and the world state carry with
different values are reported."""


def test_key_collision_reports_only_keys_with_different_values():
    import numpy as np

    from broker.core.skill_broker_engine import _conflicting_keys

    state = {"storage": 236.4, "storage_now": 236.4, "year": 3, "grid": np.array([1, 2])}
    env = {"storage": 236.41433141136787, "storage_now": 236.4, "year": 3,
           "grid": np.array([1, 2]), "only_env": 1}
    # storage differs; equal copies (storage_now, year) are not reported;
    # arrays cannot be compared to one truth value, so they are reported
    assert _conflicting_keys(state, env) == ["grid", "storage"]
    assert _conflicting_keys({"a": 1}, {"a": 1}) == []
