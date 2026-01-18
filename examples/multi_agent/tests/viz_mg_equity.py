import argparse

import matplotlib.pyplot as plt

from viz_utils import DEFAULT_RESULTS_DIR, ensure_output_dir, load_household_df


def plot_mg_equity(results_dir, output_dir):
    df = load_household_df(results_dir)
    if df.empty:
        print("No household traces found.")
        return

    df = df[df["agent_id"].notna() & df["step_id"].notna()]
    if df.empty:
        print("No valid agent or step data found.")
        return

    df = df.sort_values(["agent_id", "step_id"])
    final = df.groupby("agent_id", as_index=False).tail(1).copy()

    def mg_group(value):
        if value is True:
            return "MG"
        if value is False:
            return "Non-MG"
        return "Unknown"

    final["mg_group"] = final["mg"].apply(mg_group)
    final[["elevated", "has_insurance", "relocated"]] = final[["elevated", "has_insurance", "relocated"]].fillna(False)
    final["no_adaptation"] = (~final[["elevated", "has_insurance", "relocated"]].any(axis=1)).astype(float)

    rates = final.groupby("mg_group")[["elevated", "has_insurance", "relocated", "no_adaptation"]].mean()
    rates = rates.rename(
        columns={
            "elevated": "Elevated",
            "has_insurance": "Insured",
            "relocated": "Relocated",
            "no_adaptation": "No Adaptation",
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    rates.T.plot(kind="bar", ax=axes[0])
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Rate")
    axes[0].set_title("Adaptation Rates by MG Status")
    axes[0].legend(title="Group")

    if final["cumulative_damage"].notna().any():
        groups = list(final["mg_group"].unique())
        data = [final[final["mg_group"] == group]["cumulative_damage"] for group in groups]
        axes[1].boxplot(data, tick_labels=groups, showmeans=True)
        axes[1].set_title("Cumulative Damage Distribution")
        axes[1].set_ylabel("Cumulative Damage")
    else:
        axes[1].axis("off")
        axes[1].text(0.5, 0.5, "No cumulative_damage data", ha="center", va="center")

    fig.tight_layout()

    output_dir = ensure_output_dir(output_dir)
    png_path = output_dir / "mg_equity_analysis.png"
    pdf_path = output_dir / "mg_equity_analysis.pdf"
    fig.savefig(png_path, dpi=150)
    fig.savefig(pdf_path)
    print(f"Saved {png_path} and {pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--output", default="examples/multi_agent/tests/reports/figures")
    args = parser.parse_args()

    plot_mg_equity(args.results, args.output)
