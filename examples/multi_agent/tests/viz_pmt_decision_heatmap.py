import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from viz_utils import DEFAULT_RESULTS_DIR, ensure_output_dir, load_household_df


def _point_biserial(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if np.nanstd(x) == 0 or np.nanstd(y) == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def plot_pmt_decision_heatmap(results_dir, output_dir):
    df = load_household_df(results_dir)
    if df.empty:
        print("No household traces found.")
        return

    constructs = ["tp_score", "cp_score", "sp_score", "sc_score", "pa_score"]
    df = df[df["decision"].notna()]
    df = df.dropna(subset=constructs, how="all")
    if df.empty:
        print("No decision/construct data found.")
        return

    decisions = sorted(df["decision"].unique())
    if not decisions:
        print("No decisions found.")
        return

    corr_matrix = []
    for construct in constructs:
        row = []
        for decision in decisions:
            binary = (df["decision"] == decision).astype(int)
            row.append(_point_biserial(df[construct], binary))
        corr_matrix.append(row)

    corr = np.array(corr_matrix, dtype=float)
    corr_df = pd.DataFrame(
        corr,
        index=["TP", "CP", "SP", "SC", "PA"],
        columns=decisions,
    )

    plt.figure(figsize=(10, 6))
    sns.heatmap(
        corr_df,
        annot=True,
        cmap="RdBu_r",
        center=0,
        vmin=-0.5,
        vmax=0.5,
        fmt=".2f",
        linewidths=0.5,
        linecolor="#f0f0f0",
    )
    plt.title("PMT Construct vs Decision Type Correlation")
    plt.tight_layout()

    output_dir = ensure_output_dir(output_dir)
    png_path = output_dir / "pmt_decision_heatmap.png"
    pdf_path = output_dir / "pmt_decision_heatmap.pdf"
    plt.savefig(png_path, dpi=150)
    plt.savefig(pdf_path)
    plt.close()
    print(f"Saved {png_path} and {pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--output", default="examples/multi_agent/tests/reports/figures")
    args = parser.parse_args()

    plot_pmt_decision_heatmap(args.results, args.output)
