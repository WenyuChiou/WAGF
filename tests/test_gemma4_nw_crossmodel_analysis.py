import importlib.util
from pathlib import Path

import pandas as pd


def _load_module():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "examples" / "single_agent" / "analysis" / "gemma4_nw_crossmodel_analysis.py"
    spec = importlib.util.spec_from_file_location("gemma4_nw_crossmodel_analysis", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_summarize_pooled_metrics_counts_ibr_ehe_and_rates():
    mod = _load_module()
    df = pd.DataFrame(
        [
            {
                "construct_TP_LABEL": "H",
                "final_skill": "do_nothing",
                "status": "APPROVED",
                "retry_count": 0,
            },
            {
                "construct_TP_LABEL": "VH",
                "final_skill": "buy insurance",
                "status": "REJECTED",
                "retry_count": 1,
            },
            {
                "construct_TP_LABEL": "L",
                "final_skill": "elevate_house",
                "status": "APPROVED",
                "retry_count": 2,
            },
            {
                "construct_TP_LABEL": "M",
                "final_skill": "relocated",
                "status": "APPROVED",
                "retry_count": 0,
            },
        ]
    )

    summary = mod.summarize_pooled_metrics(df)

    assert summary["n"] == 4
    assert summary["ibr"] == 0.25
    assert round(summary["ehe"], 6) == 1.0
    assert summary["rejection_rate"] == 0.25
    assert summary["retry_rate"] == 0.5
    assert summary["action_distribution"]["buy_insurance"] == 0.25
    assert summary["action_distribution"]["relocate"] == 0.25
    assert summary["tp_distribution"]["H"] == 0.25
    assert summary["tp_distribution"]["VH"] == 0.25


def test_build_governance_effect_uses_seed_level_ibr_and_ehe():
    mod = _load_module()
    seed_rows = [
        {"model": "gemma4_e4b", "condition": "governed", "run": "Run_1", "ibr": 0.10, "ehe": 0.70},
        {"model": "gemma4_e4b", "condition": "governed", "run": "Run_2", "ibr": 0.20, "ehe": 0.75},
        {"model": "gemma4_e4b", "condition": "governed", "run": "Run_3", "ibr": 0.15, "ehe": 0.72},
        {"model": "gemma4_e4b", "condition": "disabled", "run": "Run_1", "ibr": 0.40, "ehe": 0.82},
        {"model": "gemma4_e4b", "condition": "disabled", "run": "Run_2", "ibr": 0.35, "ehe": 0.85},
        {"model": "gemma4_e4b", "condition": "disabled", "run": "Run_3", "ibr": 0.45, "ehe": 0.80},
    ]

    effect = mod.build_governance_effect(pd.DataFrame(seed_rows))

    row = effect.loc[effect["model"] == "gemma4_e4b"].iloc[0]
    assert round(row["delta_ibr"], 6) == 0.25
    assert round(row["delta_ehe"], 6) == 0.10
    assert row["n_governed"] == 3
    assert row["n_disabled"] == 3
    assert 0.0 <= row["p_value"] <= 1.0


def test_compare_distributions_reports_percentage_point_differences():
    mod = _load_module()
    baseline = {
        "action_distribution": {
            "do_nothing": 0.50,
            "buy_insurance": 0.25,
            "elevate_house": 0.25,
            "relocate": 0.0,
        },
        "tp_distribution": {"VL": 0.0, "L": 0.25, "M": 0.25, "H": 0.25, "VH": 0.25},
        "ibr": 0.25,
    }
    candidate = {
        "action_distribution": {
            "do_nothing": 0.20,
            "buy_insurance": 0.40,
            "elevate_house": 0.30,
            "relocate": 0.10,
        },
        "tp_distribution": {"VL": 0.05, "L": 0.15, "M": 0.20, "H": 0.30, "VH": 0.30},
        "ibr": 0.20,
    }

    diff = mod.compare_distribution_summaries(baseline, candidate)

    assert diff["action_pp"]["do_nothing"] == -30.0
    assert diff["action_pp"]["buy_insurance"] == 15.0
    assert diff["tp_pp"]["VL"] == 5.0
    assert diff["ibr_pp"] == -5.0
