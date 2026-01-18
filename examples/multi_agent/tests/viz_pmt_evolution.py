import argparse

import matplotlib.pyplot as plt

from viz_utils import DEFAULT_RESULTS_DIR, ensure_output_dir, load_household_df


def plot_pmt_evolution(results_dir, output_dir):
    df = load_household_df(results_dir)
    if df.empty:
        print("No household traces found.")
        return

    constructs = ["tp_score", "cp_score", "sp_score", "sc_score", "pa_score"]
    df = df[df["step_id"].notna()]
    if df.empty:
        print("No step data found.")
        return

    yearly = df.groupby("step_id")[constructs].mean().sort_index()
    if yearly.dropna(how="all").empty:
        print("No PMT construct data found.")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    labels = {
        "tp_score": "Threat Perception",
        "cp_score": "Coping Perception",
        "sp_score": "Stakeholder Perception",
        "sc_score": "Social Capital",
        "pa_score": "Place Attachment",
    }

    for col in constructs:
        ax.plot(yearly.index, yearly[col], marker="o", linewidth=2, label=labels[col])

    ax.set_title("PMT Construct Evolution")
    ax.set_xlabel("Year")
    ax.set_ylabel("Average Score")
    ax.set_ylim(0, 5)
    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()

    output_dir = ensure_output_dir(output_dir)
    png_path = output_dir / "pmt_construct_evolution.png"
    pdf_path = output_dir / "pmt_construct_evolution.pdf"
    fig.savefig(png_path, dpi=150)
    fig.savefig(pdf_path)
    print(f"Saved {png_path} and {pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--output", default="examples/multi_agent/tests/reports/figures")
    args = parser.parse_args()

    plot_pmt_evolution(args.results, args.output)
