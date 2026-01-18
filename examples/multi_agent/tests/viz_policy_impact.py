import argparse

import matplotlib.pyplot as plt
from viz_utils import DEFAULT_RESULTS_DIR, ensure_output_dir, load_household_df, load_institutional_df


def plot_policy_impact(results_dir, output_dir):
    households = load_household_df(results_dir)
    if households.empty:
        print("No household traces found.")
        return

    households = households[households["step_id"].notna()]
    if households.empty:
        print("No household step data found.")
        return

    institutional = load_institutional_df(results_dir)
    if institutional.empty:
        print("No institutional traces found.")
        return

    subsidy = (
        institutional[institutional["agent_type"] == "government"]
        .set_index("step_id")["subsidy_rate"]
        .sort_index()
    )
    premium = (
        institutional[institutional["agent_type"] == "insurance"]
        .set_index("step_id")["premium_rate"]
        .sort_index()
    )

    elevation_counts = (
        households[households["decision"] == "elevate_house"]
        .groupby("step_id")
        .size()
        .sort_index()
    )
    insurance_counts = (
        households[households["decision"].isin(["buy_insurance", "buy_contents_insurance"])]
        .groupby("step_id")
        .size()
        .sort_index()
    )

    steps = sorted(set(subsidy.index) | set(premium.index) | set(elevation_counts.index) | set(insurance_counts.index))
    if not steps:
        print("No overlapping policy/adoption data found.")
        return

    fig, axes = plt.subplots(2, 1, figsize=(12, 9))

    if not subsidy.empty:
        subsidy_pct = subsidy.reindex(steps).astype(float) * 100.0
        axes[0].plot(steps, subsidy_pct, marker="o", color="#1f77b4", label="Subsidy Rate (%)")
        axes[0].set_ylabel("Subsidy Rate (%)")
    axes[0].set_title("Subsidy Rate vs Elevation Adoption")
    axes[0].set_xlabel("Year")

    ax0_twin = axes[0].twinx()
    cum_elevations = elevation_counts.reindex(steps).fillna(0).cumsum()
    ax0_twin.plot(steps, cum_elevations, marker="s", color="#2ca02c", label="Cumulative Elevations")
    ax0_twin.set_ylabel("Cumulative Elevations")

    if not premium.empty:
        premium_pct = premium.reindex(steps).astype(float) * 100.0
        axes[1].plot(steps, premium_pct, marker="o", color="#d62728", label="Premium Rate (%)")
        axes[1].set_ylabel("Premium Rate (%)")
    axes[1].set_title("Premium Rate vs Insurance Take-up")
    axes[1].set_xlabel("Year")

    ax1_twin = axes[1].twinx()
    takeup_counts = insurance_counts.reindex(steps).fillna(0)
    ax1_twin.bar(steps, takeup_counts, alpha=0.3, color="#9467bd", label="Insurance Purchases")
    ax1_twin.set_ylabel("Insurance Purchases")

    fig.tight_layout()

    output_dir = ensure_output_dir(output_dir)
    png_path = output_dir / "policy_impact.png"
    pdf_path = output_dir / "policy_impact.pdf"
    fig.savefig(png_path, dpi=150)
    fig.savefig(pdf_path)
    print(f"Saved {png_path} and {pdf_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default=str(DEFAULT_RESULTS_DIR))
    parser.add_argument("--output", default="examples/multi_agent/tests/reports/figures")
    args = parser.parse_args()

    plot_policy_impact(args.results, args.output)
