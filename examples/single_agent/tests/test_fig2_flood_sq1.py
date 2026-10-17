"""Fig 2 (flood, SQ1) draws only the intended runs and refuses anything else."""
import pytest

from examples.single_agent.analysis import fig2_flood_sq1 as fig
from examples.single_agent.analysis.paper_measures import MetricsError

COMMIT = "9c4ba160"


def make_root(tmp_path, seeds=range(42, 47)):
    root = tmp_path / "results"
    for profile in ("strict", "disabled"):
        for seed in seeds:
            (root / f"JOH_{profile}_defaults_gemma3_4b_{COMMIT}" / f"Run_{seed}").mkdir(parents=True)
    return root


def fake_measures(run, **changes):
    profile = "strict" if "_strict_" in run.parent.name else "disabled"
    seed = int(run.name.split("_")[1])
    first = 4.0 + (seed - 42) * 0.1
    result = {"seed": seed, "governance_profile": profile, "retry_feedback_mode": "full", "model": "gemma3:4b",
              "commit": COMMIT + "996428117dfe72d0a54053cc1d550ff7", "n_aborted": 0, "physical_count": 0,
              "first_behavioural_pct": first, "behavioural_ibr_pct": 0.5 if profile == "strict" else first,
              "ehe": 0.67, **{f"year_{year}_ehe": 0.5 for year in range(1, 11)}}
    result.update(changes)
    return result


def use(monkeypatch, **changes):
    monkeypatch.setattr(fig, "projection_run", lambda run: fake_measures(run, **changes))


def run_main(root, out):
    return fig.main(["--results-root", str(root), "--out-dir", str(out)])


def test_writes_png_and_pdf(tmp_path, monkeypatch):
    use(monkeypatch)
    assert run_main(make_root(tmp_path), tmp_path / "out") == 0
    assert {p.name for p in (tmp_path / "out").iterdir()} == {"Fig2_flood_sq1.png", "Fig2_flood_sq1.pdf"}


@pytest.mark.parametrize("changes", [
    {"retry_feedback_mode": "silent"},  # a silent run in a strict folder
    {"governance_profile": "strict"},  # a strict run in the disabled folder
    {"model": "gemma4:12b"},
    {"commit": "186abb29"},
    {"n_aborted": 1},
    {"year_11_ehe": 0.4},  # a year beyond the ten drawn would be dropped silently
    {"year_5_ehe": None},
])
def test_refuses_runs_that_do_not_match(tmp_path, monkeypatch, changes):
    use(monkeypatch, **changes)
    with pytest.raises(MetricsError):
        run_main(make_root(tmp_path), tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_refuses_missing_seed(tmp_path, monkeypatch):
    use(monkeypatch)
    with pytest.raises(MetricsError, match="expected exactly 5 run folders"):
        run_main(make_root(tmp_path, seeds=range(42, 46)), tmp_path / "out")


def test_refuses_out_dir_inside_results(tmp_path, monkeypatch):
    use(monkeypatch)
    root = make_root(tmp_path)
    with pytest.raises(MetricsError, match="--out-dir"):
        run_main(root, root / "figs")
