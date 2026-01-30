from pathlib import Path


def test_initial_memory_split_structure():
    base = Path("examples/multi_agent/flood")
    memory_dir = base / "memory"

    assert (memory_dir / "templates.py").exists()
    assert (memory_dir / "pmt_mapper.py").exists()

    runner = base / "initial_memory.py"
    text = runner.read_text(encoding="utf-8")

    assert "memory.templates" in text
    assert "memory.pmt_mapper" in text
