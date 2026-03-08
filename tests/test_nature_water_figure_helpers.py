import importlib.util
from pathlib import Path

import pandas as pd


def _load_irrigation_fig_module():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "paper" / "nature_water" / "scripts" / "gen_fig2_case1_irrigation.py"
    spec = importlib.util.spec_from_file_location("nw_fig2_irrigation", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_compute_pie_matrix_returns_counts_totals_and_violations():
    mod = _load_irrigation_fig_module()

    df = pd.DataFrame(
        [
            {
                "construct_WSA_LABEL": "H",
                "construct_ACA_LABEL": "M",
                "proposed_skill": "increase_small",
                "status": "APPROVED",
            },
            {
                "construct_WSA_LABEL": "H",
                "construct_ACA_LABEL": "M",
                "proposed_skill": "increase_large",
                "status": "REJECTED",
            },
            {
                "construct_WSA_LABEL": "H",
                "construct_ACA_LABEL": "M",
                "proposed_skill": "maintain_demand",
                "status": "REJECTED_FALLBACK",
            },
            {
                "construct_WSA_LABEL": "L",
                "construct_ACA_LABEL": "H",
                "proposed_skill": "decrease_small",
                "status": "APPROVED",
            },
        ]
    )

    counts, totals, violations = mod.compute_pie_matrix(df)

    assert totals[("H", "M")] == 3
    assert counts[("H", "M")]["increase_small"] == 1
    assert counts[("H", "M")]["increase_large"] == 1
    assert counts[("H", "M")]["maintain_demand"] == 1
    assert violations[("H", "M")] == 2

    assert totals[("L", "H")] == 1
    assert counts[("L", "H")]["decrease_small"] == 1
    assert violations[("L", "H")] == 0


def test_flood_fig3_panel_a_order_is_governed_then_rulebased_then_ungoverned():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "paper" / "nature_water" / "scripts" / "gen_fig3_case2_flood.py"
    spec = importlib.util.spec_from_file_location("nw_fig3_flood", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    panel_order = [item[0] for item in module.get_panel_a_configs()]
    assert panel_order == ["gov", "rulebased", "disabled"]


def test_flood_violation_annotation_style_is_high_contrast():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "paper" / "nature_water" / "scripts" / "gen_fig3_case2_flood.py"
    spec = importlib.util.spec_from_file_location("nw_fig3_flood", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    style = module.get_violation_annotation_style()

    assert style["fontsize"] >= 7.5
    assert style["fontweight"] == "bold"
    assert "bbox" in style
    assert style["bbox"]["facecolor"] == "white"


def test_flood_panel_a_legend_is_top_right_of_first_subplot():
    repo = Path(__file__).resolve().parents[1]
    path = repo / "paper" / "nature_water" / "scripts" / "gen_fig3_case2_flood.py"
    spec = importlib.util.spec_from_file_location("nw_fig3_flood", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    cfg = module.get_panel_a_legend_config()

    assert cfg["target_axis_index"] == 0
    assert cfg["loc"] == "upper right"


def test_irrigation_fig2_bottom_row_uses_two_pie_panels():
    mod = _load_irrigation_fig_module()

    panel_cfgs = mod.get_irrigation_pie_panel_configs()

    assert [cfg["key"] for cfg in panel_cfgs] == ["gov", "disabled"]
    assert [cfg["title"] for cfg in panel_cfgs] == [
        "Governed LLM",
        "Governed LLM (no validator)",
    ]


def test_irrigation_violation_annotation_style_matches_flood_badge_pattern():
    mod = _load_irrigation_fig_module()

    style = mod.get_irrigation_violation_annotation_style()

    assert style["fontsize"] >= 7.5
    assert style["fontweight"] == "bold"
    assert style["bbox"]["facecolor"] == "white"
    assert style["bbox"]["edgecolor"] == "#B22222"


def test_irrigation_center_count_style_matches_fig3_overlay():
    mod = _load_irrigation_fig_module()

    style = mod.get_irrigation_center_count_style()

    assert style["fontsize"] == 6.0
    assert style["fontweight"] == "bold"
    assert style["bbox"]["facecolor"] == "#00000055"


def test_irrigation_title_sits_above_aca_axis_label():
    mod = _load_irrigation_fig_module()

    layout = mod.get_irrigation_pie_text_layout()

    assert layout["title_y"] > layout["aca_label_y"]
    assert layout["aca_label_y"] < 0.0
    assert layout["title_y"] <= 1.02


def test_irrigation_uses_shared_violation_colorbar():
    mod = _load_irrigation_fig_module()

    cfg = mod.get_irrigation_colorbar_config()

    assert cfg["orientation"] == "vertical"
    assert cfg["label"] == "Violations"
    assert cfg["width"] > 0


def test_irrigation_violation_badges_use_figure_overlay():
    mod = _load_irrigation_fig_module()

    cfg = mod.get_irrigation_violation_badge_layout()

    assert cfg["use_figure_overlay"] is True
    assert cfg["x_ratio"] >= 0.94


def test_irrigation_action_legend_is_shared_between_two_panels():
    mod = _load_irrigation_fig_module()

    cfg = mod.get_irrigation_action_legend_config()

    assert cfg["use_figure_legend"] is True
    assert cfg["anchor_x"] >= 0.75
    assert cfg["anchor_y"] >= 0.80
    assert cfg["ncol"] == 2
