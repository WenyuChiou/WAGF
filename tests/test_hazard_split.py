from pathlib import Path


def test_hazard_split_structure():
    base = Path("examples/multi_agent/environment")
    assert (base / "vulnerability.py").exists()
    assert (base / "year_mapping.py").exists()

    hazard = base / "hazard.py"
    text = hazard.read_text(encoding="utf-8")
    assert "vulnerability" in text
    assert "year_mapping" in text
