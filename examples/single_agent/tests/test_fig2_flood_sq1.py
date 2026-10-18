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
    monkeypatch.setattr(fig, "_load_rulebased_group", lambda *args: [
        fake_measures(tmp_path / f"Run_{seed}") for seed in range(42, 47)
    ])
    monkeypatch.setattr(fig, "_load_simulations", lambda *args: [[
        state_row("A", year, "Do Nothing") for year in range(1, 11)
    ] for _ in range(5)])
    monkeypatch.setattr(fig, "_load_grid_records", lambda *args: [])
    monkeypatch.setattr(fig, "_load_blocked_counts", lambda *args: fig.blocked_action_counts([]))
    monkeypatch.setattr(fig, "_load_region_counts", lambda *args: {
        bar: {"counts": {"DN": 1, "FI": 7, "HE": 2, "RL": 0}, "dn_by_seed": {42: 10.0}}
        for bar in fig.REGION_BARS
    })
    assert run_main(make_root(tmp_path), tmp_path / "out") == 0
    assert {p.name for p in (tmp_path / "out").iterdir()} == {
        "Fig2_flood_sq1.png", "Fig2_flood_sq1.pdf",
        "FigS_flood_appraisal_grid.png", "FigS_flood_appraisal_grid.pdf",
        "FigS_flood_blocked_decisions.png", "FigS_flood_blocked_decisions.pdf"}


@pytest.mark.parametrize("changes", [
    {"retry_feedback_mode": "silent"},  # a silent run in a strict folder
    {"governance_profile": "strict"},  # a strict run in the disabled folder
    {"model": "gemma4:12b"},
    {"commit": "186abb29"},
    {"n_aborted": 1},
    {"physical_count": 1},
    {"seed": 99},
    {"ehe": float("nan")},
    {"first_behavioural_pct": float("inf")},
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


def state_row(agent, year, state, *, relocated=False, elevated=False, insured=False):
    return {"agent_id": agent, "year": str(year), "cumulative_state": state,
            "relocated": str(relocated), "elevated": str(elevated),
            "has_insurance": str(insured)}


@pytest.mark.parametrize("raw, expected", [
    ("Do Nothing", "DN"), ("Only Flood Insurance", "FI"),
    ("Only House Elevation", "HE"),
    ("Both Flood Insurance and House Elevation", "FI+HE"),
    ("Relocate", "RL"), ("Already relocated", "RL"),
])
def test_protection_state_uses_earlier_mapping(raw, expected):
    assert fig.protection_state({"cumulative_state": raw, "decision": "Relocate"}) == expected
    assert fig.protection_state({"decision": raw}) == expected


def test_protection_state_refuses_unknown_state():
    with pytest.raises(MetricsError, match="Unknown protection state"):
        fig.protection_state({"cumulative_state": "unknown"})


def test_state_counts_drop_only_years_after_relocation_and_average_seeds():
    first = [state_row("A", 1, "Do Nothing"), state_row("A", 2, "Relocate"),
             state_row("A", 3, "Already relocated"),
             state_row("B", 1, "Both Flood Insurance and House Elevation"),
             state_row("B", 2, "Only House Elevation")]
    second = [state_row("A", year, "Only Flood Insurance") for year in range(1, 4)]
    counts = fig.state_counts([first, second])
    assert counts[1] == {"DN": 0.5, "FI": 0.5, "HE": 0.0, "FI+HE": 0.5, "RL": 0.0}
    assert counts[2]["RL"] == 0.5
    assert counts[2]["HE"] == 0.5
    assert sum(counts[3].values()) == 0.5
    assert sum(counts[10].values()) == 0


def test_state_agreement_checks_post_relocation_rows_too():
    rows = [state_row("A", 1, "Relocate", relocated=True),
            state_row("A", 2, "Already relocated", relocated=False)]
    with pytest.raises(MetricsError, match="disagreement.*A"):
        fig._check_state_agreement([rows], "Governed LLM")


def test_state_agreement_handles_combined_state_and_relocation(capsys):
    rows = [state_row("A", 1, "Both Flood Insurance and House Elevation", elevated=True, insured=True),
            state_row("A", 2, "Relocate", relocated=True, elevated=True, insured=True)]
    fig._check_state_agreement([rows], "Governed LLM")
    assert "2/2 agreements; 0 disagreements" in capsys.readouterr().out


def test_grid_counts_shares_actions_and_masking():
    records = ([{"ta": "H", "ca": "M", "action": "do_nothing", "flagged": True}] * 6
               + [{"ta": "H", "ca": "M", "action": "buy_insurance", "flagged": False}] * 24
               + [{"ta": "VL", "ca": "L", "action": "relocate", "flagged": True}] * 29
               + [{"ta": "", "ca": "M", "action": "buy_insurance", "flagged": False}])
    cells = fig.grid_cells(records)
    assert len(cells) == 25
    assert cells["H", "M"]["n"] == 30
    assert cells["H", "M"]["flagged"] == 6
    assert cells["H", "M"]["share"] == pytest.approx(0.2)
    assert cells["H", "M"]["actions"] == {
        "do_nothing": 6, "buy_insurance": 24, "elevate_house": 0, "relocate": 0}
    assert cells["H", "M"]["mask"] is None
    assert cells["VL", "L"]["mask"] == "n<30"
    assert cells["M", "M"]["mask"] == "n=0"
    assert cells["M", "M"]["share"] is None
    assert fig._grid_vmax([cells]) == 0.25  # masked high shares do not stretch the scale
    cells["H", "M"]["share"] = 0.26
    assert fig._grid_vmax([cells]) == pytest.approx(0.30)


def test_refuses_rulebased_commit_mismatch(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    folder = root / "custom_rulebased"
    for seed in range(42, 47):
        (folder / f"Run_{seed}").mkdir(parents=True)
    use(monkeypatch)
    with pytest.raises(MetricsError, match="186abb29"):
        fig._load_rulebased_group(root, "custom_rulebased")


def test_loads_custom_rulebased_directory_with_expected_commit(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    for seed in range(42, 47):
        (root / "custom_rulebased" / f"Run_{seed}").mkdir(parents=True)
    monkeypatch.setattr(fig, "projection_run", lambda run: fake_measures(run, commit="186abb29abcd"))
    rows = fig._load_rulebased_group(root, "custom_rulebased")
    assert {row["seed"] for row in rows} == set(range(42, 47))
    assert all(row["run"].parent.name == "custom_rulebased" for row in rows)


def test_refuses_no_validator_first_proposal_difference(tmp_path, monkeypatch):
    root = make_root(tmp_path)
    use(monkeypatch, first_behavioural_pct=4.0, behavioural_ibr_pct=4.1)
    with pytest.raises(MetricsError, match="must equal"):
        fig._load_group(root, "disabled", COMMIT)


def test_grid_loader_uses_first_stated_labels_and_crosschecks(tmp_path, monkeypatch):
    from types import SimpleNamespace

    raw = {"agent_id": "A", "year": "1"}
    decision = SimpleNamespace(agent_id="A", year="1", aborted=False,
                               executed_skill="do_nothing", first_labels={"TP_LABEL": "H", "CP_LABEL": "M"})
    monkeypatch.setattr(fig.measures, "_csv", lambda path: (set(raw), [raw]))
    monkeypatch.setattr(fig.audit, "parse_decision", lambda row, where: decision)
    monkeypatch.setattr(fig.measures, "_pre_elevation", lambda path, keys: {("A", "1"): False})
    run = {"run": tmp_path, "behavioural_count": 1}
    records = fig._load_grid_records([run], "Governed LLM")
    assert records == [{"ta": "H", "ca": "M", "action": "do_nothing", "flagged": True}]
    run["behavioural_count"] = 0
    with pytest.raises(MetricsError, match="flagged.*behavioural_count"):
        fig._load_grid_records([run], "Governed LLM")


def test_grid_records_exclude_aborts_and_preserve_missing_labels_for_crosscheck(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    decisions = {
        "A": SimpleNamespace(agent_id="A", year="1", aborted=False, executed_skill="do_nothing",
                             first_labels={"TP_LABEL": "H", "CP_LABEL": "L"}),  # no R1 with low coping
        "B": SimpleNamespace(agent_id="B", year="1", aborted=False, executed_skill="relocate",
                             first_labels={"TP_LABEL": "L"}),  # R3 even without coping
        "C": SimpleNamespace(agent_id="C", year="1", aborted=False, executed_skill="elevate_house",
                             first_labels={"TP_LABEL": "L", "CP_LABEL": "M"}),  # R4
        "D": SimpleNamespace(agent_id="D", year="1", aborted=False, executed_skill="elevate_house",
                             first_labels={"TP_LABEL": "M", "CP_LABEL": "M"}),  # R5 alone excluded
        "E": SimpleNamespace(agent_id="E", year="1", aborted=True, executed_skill=None, first_labels={}),
    }
    raw = [{"agent_id": agent, "year": "1"} for agent in decisions]
    monkeypatch.setattr(fig.measures, "_csv", lambda path: (set(raw[0]), raw))
    monkeypatch.setattr(fig.audit, "parse_decision", lambda row, where: decisions[row["agent_id"]])
    monkeypatch.setattr(fig.measures, "_pre_elevation", lambda path, keys: {key: True for key in keys})
    records = fig._load_grid_records([{"run": tmp_path, "behavioural_count": 2}], "Governed LLM")
    assert len(records) == 4
    assert [record["flagged"] for record in records] == [False, True, True, False]
    assert "1 decisions omitted for missing first-stated labels" in capsys.readouterr().out
    cells = fig.grid_cells(records)
    assert sum(cell["n"] for cell in cells.values()) == 3
    assert sum(cell["flagged"] for cell in cells.values()) == 1


def proposal(proposed="do_nothing", executed="buy_insurance", tp="H", cp="M",
             path="validated", aborted=False):
    from types import SimpleNamespace

    return SimpleNamespace(first_proposal=proposed, executed_skill=executed,
                           first_labels={"TP_LABEL": tp, "CP_LABEL": cp},
                           execution_path=path, aborted=aborted)


@pytest.mark.parametrize("action,tp,cp,expected", [
    ("do_nothing", "H", "M", "R1"), ("do_nothing", "VH", "VH", "R1"),
    ("do_nothing", "H", "L", None), ("do_nothing", "H", "VL", None),
    ("do_nothing", "M", "H", None), ("do_nothing", " h ", " m ", "R1"),
    ("relocate", "VL", "", "R3"), ("relocate", "L", "M", "R3"),
    ("elevate_house", "VL", "L", "R4"), ("elevate_house", "L", "M", "R4"),
    ("elevate_house", "M", "M", None),  # R5 alone is outside behavioural rules.
])
def test_first_proposal_rule(action, tp, cp, expected):
    assert fig.first_proposal_rule(proposal(action, tp=tp, cp=cp)) == expected


def test_blocked_counts_split_default_do_nothing_and_exclude_aborts():
    counts = fig.blocked_action_counts([
        proposal(executed="do_nothing", path="rejected_default"),
        proposal(executed="do_nothing", path="validated"),
        proposal(executed="buy_insurance"),
        proposal("relocate", "elevate_house", "L", "M"),
        proposal("elevate_house", "do_nothing", "L", "M", path="rejected_default"),
        proposal(aborted=True),
    ])
    # A default following an R4 proposal stays hatched even outside the R1 region.
    assert counts["blocked"] == {"DN": 1, "DN_default": 2, "FI": 1, "HE": 1, "RL": 0}
    assert counts["blocked_outside_r1"] == 2
    assert sum(counts["accepted"].values()) == 0


def test_accepted_counts_require_r1_region_and_no_first_proposal_rule():
    counts = fig.blocked_action_counts([
        proposal("buy_insurance", "buy_insurance"),
        proposal("elevate_house", "elevate_house", "VH", "H"),
        proposal("relocate", "relocate", "H", "VH"),
        proposal(),  # R1: blocked cohort only.
        proposal("buy_insurance", "buy_insurance", "M", "M"),
        proposal("buy_insurance", "buy_insurance", "H", "L"),
    ])
    assert counts["accepted"] == {"DN": 0, "DN_default": 0, "FI": 1, "HE": 1, "RL": 1}
    assert sum(counts["blocked"].values()) == 1


def test_blocked_loader_crosschecks_first_behavioural_count(tmp_path, monkeypatch, capsys):
    raw = [{"agent_id": "A", "year": "1"}, {"agent_id": "B", "year": "1"}]
    monkeypatch.setattr(fig.measures, "_csv", lambda path: (set(raw[0]), raw))
    monkeypatch.setattr(fig.audit, "parse_decision", lambda row, where: proposal(
        aborted=row["agent_id"] == "B"))
    run = {"run": tmp_path / "Run_42", "seed": 42,
           "first_behavioural_count": 1, "behavioural_count": 0}
    assert fig._load_blocked_counts([run])["blocked"]["FI"] == 1
    assert "first_behavioural_count 1" in capsys.readouterr().out
    run["first_behavioural_count"] = 2
    with pytest.raises(MetricsError, match="first_behavioural_count"):
        fig._load_blocked_counts([run])


@pytest.mark.parametrize("tp,cp,included", [
    (tp, cp, True) for tp in ("H", "VH") for cp in ("M", "H", "VH")
] + [(" h ", " m ", True), ("M", "H", False), ("H", "L", False),
     (None, "M", False), ("H", None, False)])
def test_region_filter_uses_first_stated_labels(tp, cp, included):
    decision = proposal(tp=tp, cp=cp)
    decision.final_labels = {"TP_LABEL": "L", "CP_LABEL": "L"}
    if tp is None:
        del decision.first_labels["TP_LABEL"]
    if cp is None:
        del decision.first_labels["CP_LABEL"]
    counts = fig.region_action_counts([decision], "executed_skill")
    assert sum(counts.values()) == int(included)


def test_region_composition_distinguishes_proposal_and_execution_and_excludes_aborts():
    decisions = [proposal(), proposal("buy_insurance", "elevate_house"),
                 proposal("relocate", "relocate"), proposal(aborted=True),
                 proposal(tp="M"), proposal(cp="L")]
    assert fig.region_action_counts(decisions, "first_proposal") == {
        "DN": 1, "FI": 1, "HE": 0, "RL": 1}
    assert fig.region_action_counts(decisions, "executed_skill") == {
        "DN": 0, "FI": 1, "HE": 1, "RL": 1}


@pytest.mark.parametrize("field", ["first_proposal", "executed_skill"])
def test_region_counts_refuse_missing_action(field):
    decision = proposal()
    setattr(decision, field, None)
    with pytest.raises(MetricsError, match="action"):
        fig.region_action_counts([decision], field)


@pytest.mark.parametrize("metric", ["first_R1_count", "R1_count"])
def test_region_crosscheck_raises_and_prints_comparison(tmp_path, capsys, metric):
    run = {"run": tmp_path, "first_R1_count": 1, "R1_count": 0}
    first = {"DN": 1, "FI": 1, "HE": 0, "RL": 0}
    executed = {"DN": 0, "FI": 2, "HE": 0, "RL": 0}
    fig._check_region_counts(run, executed, first)
    assert metric in capsys.readouterr().out
    run[metric] += 1
    with pytest.raises(MetricsError, match=metric):
        fig._check_region_counts(run, executed, first)
    assert metric in capsys.readouterr().out


def test_region_crosscheck_rejects_different_governed_cohort_counts(tmp_path, capsys):
    run = {"run": tmp_path, "first_R1_count": 1, "R1_count": 0}
    with pytest.raises(MetricsError, match="same decisions"):
        fig._check_region_counts(run, {"DN": 0, "FI": 1}, {"DN": 1, "FI": 1})
    assert "same decisions" in capsys.readouterr().out


def test_region_no_validator_crosscheck_raises(tmp_path, capsys):
    with pytest.raises(MetricsError, match="R1_count"):
        fig._check_region_counts({"run": tmp_path, "R1_count": 2}, {"DN": 1})
    assert "R1_count" in capsys.readouterr().out


def test_region_loader_pools_counts_before_shares(tmp_path, monkeypatch, capsys):
    runs = [tmp_path / f"Run_{seed}" for seed in (42, 43)]
    decisions = {runs[0]: [proposal(executed="do_nothing")],
                 runs[1]: [proposal("buy_insurance")] * 3}
    monkeypatch.setattr(fig, "_load_executed_decisions", decisions.__getitem__)
    rows = [{"run": run, "seed": seed, "first_R1_count": first, "R1_count": first}
            for run, seed, first in zip(runs, (42, 43), (1, 0))]
    bars = fig._load_region_counts({"strict": rows, "disabled": rows})
    for bar in bars.values():
        assert bar["counts"] == {"DN": 1, "FI": 3, "HE": 0, "RL": 0}
        assert bar["dn_by_seed"] == {42: 100.0, 43: 0.0}
    output = capsys.readouterr().out
    assert "DN=1 (25.00%)" in output
    assert "DN per seed" in output


def test_region_loader_refuses_empty_region(tmp_path, monkeypatch):
    monkeypatch.setattr(fig, "_load_executed_decisions", lambda run: [proposal(tp="M")])
    rows = [{"run": tmp_path, "seed": 42, "R1_count": 0, "first_R1_count": 0}]
    with pytest.raises(MetricsError, match="[Ee]mpty"):
        fig._load_region_counts({"strict": rows, "disabled": rows})
