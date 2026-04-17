from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
from scipy.stats import linregress, pearsonr


REPO_ROOT = Path(__file__).resolve().parents[5]
ANALYSIS_DIR = Path(__file__).resolve().parent
INPUT_CSV = ANALYSIS_DIR / "deep_synthesis" / "figures" / "fig_rq1_dual_timeseries.csv"
OUTPUT_DIR = ANALYSIS_DIR / "deep_synthesis" / "rq_deep"
OUTPUT_CSV = OUTPUT_DIR / "rq1_cross_paradigm_stats.csv"
OUTPUT_MD = OUTPUT_DIR / "rq1_cross_paradigm_report.md"

TRADITIONAL_ARM = "Traditional_FLOODABM"
LLM_ARMS = ["LEGACY_Full", "CLEAN_Full", "CLEAN_Flat"]


def classify(mad_pp: float, pearson_r_value: float) -> str:
    if math.isnan(pearson_r_value):
        return "MAGNITUDE_CONVERGE" if mad_pp < 5 else "DIVERGE"
    if mad_pp < 5 and abs(pearson_r_value) > 0.5:
        return "CONVERGE"
    if mad_pp >= 5 and pearson_r_value > 0.5:
        return "TRAJECTORY_CONVERGE"
    if mad_pp < 5 and abs(pearson_r_value) <= 0.5:
        return "MAGNITUDE_CONVERGE"
    return "DIVERGE"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT_CSV)
    rows: list[dict[str, object]] = []

    llm_slice = df[df["arm"].isin(LLM_ARMS)]
    combos = (
        llm_slice[["agent_type", "action", "arm"]]
        .drop_duplicates()
        .sort_values(["agent_type", "action", "arm"])
        .itertuples(index=False)
    )

    for combo in combos:
        agent_type = combo.agent_type
        action = combo.action
        llm_arm = combo.arm

        trad = (
            df[
                (df["arm"] == TRADITIONAL_ARM)
                & (df["agent_type"] == agent_type)
                & (df["action"] == action)
            ][["year", "mean_rate"]]
            .rename(columns={"mean_rate": "traditional_rate"})
        )
        llm = (
            df[
                (df["arm"] == llm_arm)
                & (df["agent_type"] == agent_type)
                & (df["action"] == action)
            ][["year", "mean_rate"]]
            .rename(columns={"mean_rate": "llm_rate"})
        )
        merged = trad.merge(llm, on="year", how="inner").sort_values("year")
        if len(merged) < 2:
            continue

        if merged["traditional_rate"].nunique() < 2 or merged["llm_rate"].nunique() < 2:
            pearson_r_value, pearson_p = float("nan"), float("nan")
        else:
            pearson_r_value, pearson_p = pearsonr(merged["traditional_rate"], merged["llm_rate"])
        trad_slope = linregress(merged["year"], merged["traditional_rate"]).slope
        llm_slope = linregress(merged["year"], merged["llm_rate"]).slope
        mad_pp = (merged["traditional_rate"] - merged["llm_rate"]).abs().mean() * 100.0

        rows.append(
            {
                "action": action,
                "agent_type": agent_type,
                "llm_arm": llm_arm,
                "traditional_mean_13yr": merged["traditional_rate"].mean(),
                "llm_mean_13yr": merged["llm_rate"].mean(),
                "mad_pp": mad_pp,
                "pearson_r": pearson_r_value,
                "pearson_p": pearson_p,
                "llm_trend_slope": llm_slope,
                "trad_trend_slope": trad_slope,
                "classification": classify(mad_pp, pearson_r_value),
            }
        )

    result = pd.DataFrame(rows).sort_values(["agent_type", "action", "llm_arm"]).reset_index(drop=True)
    result.to_csv(OUTPUT_CSV, index=False)

    class_matrix = (
        result.pivot(index=["agent_type", "action"], columns="llm_arm", values="classification")
        .fillna("NA")
        .sort_index()
    )
    strongest = result.sort_values(["classification", "mad_pp", "pearson_r"], ascending=[True, True, False]).head(5)
    worst = result.sort_values(["mad_pp", "pearson_r"], ascending=[False, True]).head(5)

    md_lines = [
        "# RQ1 Deep Cross-Paradigm Comparison",
        "",
        f"Source: `{INPUT_CSV.relative_to(REPO_ROOT).as_posix()}`",
        "",
        "All rates use the existing yearly means from `fig_rq1_dual_timeseries.csv`. ",
        "Mean values are stored as 0-1 rates; `mad_pp` is reported in percentage points.",
        "",
        "## Classification Matrix",
        "",
        class_matrix.to_markdown(),
        "",
        "## Lowest-MAD Pairings",
        "",
        strongest[
            ["agent_type", "action", "llm_arm", "mad_pp", "pearson_r", "classification"]
        ].to_markdown(index=False),
        "",
        "## Highest-Divergence Pairings",
        "",
        worst[
            ["agent_type", "action", "llm_arm", "mad_pp", "pearson_r", "classification"]
        ].to_markdown(index=False),
        "",
    ]
    OUTPUT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"rq1_deep_cross_paradigm: rc=0 rows={len(result)} files=2 out={OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
