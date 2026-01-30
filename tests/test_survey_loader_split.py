from pathlib import Path


def test_survey_loader_split_structure():
    base = Path("examples/multi_agent/flood")
    survey_dir = base / "survey"

    assert (survey_dir / "pmt_calculator.py").exists()
    assert (survey_dir / "mg_classifier.py").exists()
    assert (survey_dir / "stratified_sampler.py").exists()

    runner = base / "survey_loader.py"
    text = runner.read_text(encoding="utf-8")

    assert "survey.pmt_calculator" in text
    assert "survey.mg_classifier" in text
    assert "survey.stratified_sampler" in text
