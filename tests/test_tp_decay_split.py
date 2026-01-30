from pathlib import Path


def test_tp_decay_split_structure():
    base = Path("examples/multi_agent/flood/environment")
    assert (base / "decay_models.py").exists()
    assert (base / "tp_state.py").exists()

    tp_decay = base / "tp_decay.py"
    text = tp_decay.read_text(encoding="utf-8")
    assert "decay_models" in text
    assert "tp_state" in text
