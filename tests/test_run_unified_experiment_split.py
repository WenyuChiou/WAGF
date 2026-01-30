from pathlib import Path


def test_run_unified_experiment_split_structure():
    base = Path("examples/multi_agent/flood")
    orchestration = base / "orchestration"

    assert (orchestration / "agent_factories.py").exists()
    assert (orchestration / "lifecycle_hooks.py").exists()
    assert (orchestration / "disaster_sim.py").exists()

    runner = base / "run_unified_experiment.py"
    text = runner.read_text(encoding="utf-8")

    assert "orchestration.agent_factories" in text
    assert "orchestration.lifecycle_hooks" in text
