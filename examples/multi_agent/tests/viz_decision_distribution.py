import argparse

import matplotlib.pyplot as plt
import numpy as np

from viz_utils import (
    DECISION_COLORS,
    DECISION_ORDER,
    DEFAULT_RESULTS_DIR,
    ensure_output_dir,
    load_household_df,
)


def _entropy(counts):
    total = float(counts.sum())
    if total <= 0:
        return 0.0
    probs = counts / total
    return -float(np.sum([p * np.log2(p) for p in probs if p > 0]))


def plot_decision_distribution(results_dir, output_dir):
    df = load_household_df(results_dir)
    if df.empty:
        print("No household traces found.")
        return

    df = df[df["agent_id"].notna() & df["step_id"].notna()]
    if df.empty:
        print("No valid agent or step data found.")
        return

    pivot = df.pivot_table(index="step_id", columns="decision", aggfunc="size", fill_value=0)
    if pivot.empty:
        print("No decision data found.")
        return

    columns = [d for d in DECISION_ORDER if d in pivot.columns]
    columns.extend(sorted(set(pivot.columns) - set(columns)))
    pivot = pivot.reindex(columns=columns)

    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    colors = [DECISION_COLORS.get(col, "#cccccc") for col in pivot.columns]
    pivot.plot(kind="bar", stacked=True, ax=axes[0], color=colors)
    axes[0].set_title("Yearly Decision Distribution")
    axes[0].set_xlabel("Year")
    axes[0].set_ylabel("Count")
    axes[0].legend(title="Decision", bbox_to_anchor=(1.02, 1), loc="upper left")

    entropies = [_entropy(pivot.loc[idx]) for idx in pivot.index]
    axes[1].plot(pivot.index, entropies, marker="o", linewidth=2, color="#2a6fbb")
    axes[1].axhline(y=1.0, color="#d9534f", linestyle="--", label="Min threshold")
    axes[1].set_title("Decision Diversity (Shannon Entropy)")
    axes[1].set_xlabel("Year")
    axes[1].set_ylabel("Entropy (bits)")
    axes[1].legend()

    fig.tight_layout()

    output_dir = ensure_output_dir(output_dir)
    png_path = output_dir / "decision_distribution.png"
    pdf_path = output_dir / "decision_distribution.pdf"
    fig.savefig(png_path, dpi=150)
    fig.savefig(pdf_path)
    print(f"Saved {png_path} and {pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--output", default="examples/multi_agent/tests/reports/figures")
    args = parser.parse_args()

    plot_decision_distribution(args.results, args.output)
