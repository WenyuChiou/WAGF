import argparse

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

from viz_utils import (
    DECISION_COLORS,
    DECISION_ORDER,
    DEFAULT_RESULTS_DIR,
    ensure_output_dir,
    load_household_df,
)


def plot_agent_trajectories(results_dir, output_dir, sample_n):
    df = load_household_df(results_dir)
    if df.empty:
        print("No household traces found.")
        return

    df = df[df["agent_id"].notna() & df["step_id"].notna()]
    if df.empty:
        print("No valid agent or step data found.")
        return

    df = df.sort_values(["agent_id", "step_id"])
    agents = sorted(df["agent_id"].unique())[:sample_n]
    df = df[df["agent_id"].isin(agents)]

    if df.empty:
        print("No data after sampling agents.")
        return

    pivot = df.pivot(index="agent_id", columns="step_id", values="decision")
    present = set(df["decision"].unique())
    decisions = [d for d in DECISION_ORDER if d in present]
    decisions.extend(sorted(present - set(decisions)))

    mapping = {decision: idx for idx, decision in enumerate(decisions)}
    numeric = pivot.apply(lambda col: col.map(mapping))

    cmap = ListedColormap([DECISION_COLORS.get(d, "#cccccc") for d in decisions])

    fig, ax = plt.subplots(figsize=(12, max(4, 0.4 * len(agents))))
    ax.imshow(numeric.values, aspect="auto", interpolation="nearest", cmap=cmap)

    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_xlabel("Year")
    ax.set_ylabel("Agent ID")
    ax.set_title("Agent Decision Trajectories")

    handles = [Patch(facecolor=DECISION_COLORS.get(d, "#cccccc"), label=d) for d in decisions]
    ax.legend(handles=handles, title="Decision", bbox_to_anchor=(1.02, 1), loc="upper left")

    fig.tight_layout()

    output_dir = ensure_output_dir(output_dir)
    png_path = output_dir / "agent_trajectories.png"
    pdf_path = output_dir / "agent_trajectories.pdf"
    fig.savefig(png_path, dpi=150)
    fig.savefig(pdf_path)
    print(f"Saved {png_path} and {pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--output", default="examples/multi_agent/tests/reports/figures")
    parser.add_argument("--sample", type=int, default=20)
    args = parser.parse_args()

    plot_agent_trajectories(args.results, args.output, args.sample)
