"""
Statistical tests for SAGE governance-middleware entropy analysis.
Produces bootstrap CIs, Mann-Whitney U tests, and effect sizes
for a WRR submission.

Output
------
- statistical_tests_results.csv  (machine-readable)
- formatted summary table        (stdout)
"""

import pathlib
import sys

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
INPUT_CSV = SCRIPT_DIR / "corrected_entropy_gemma3_4b.csv"
OUTPUT_CSV = SCRIPT_DIR / "statistical_tests_results.csv"

N_BOOTSTRAP = 10_000
CI_LEVEL = 0.95
RNG_SEED = 42

GROUPS = ["Group_A", "Group_B", "Group_C"]
GROUP_PAIRS = [
    ("Group_A", "Group_B"),
    ("Group_A", "Group_C"),
    ("Group_B", "Group_C"),
]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def bootstrap_ci(data: np.ndarray, stat_fn=np.mean, n_boot: int = N_BOOTSTRAP,
                 ci: float = CI_LEVEL, seed: int = RNG_SEED):
    """Return (estimate, ci_lower, ci_upper) via percentile bootstrap."""
    rng = np.random.default_rng(seed)
    estimate = stat_fn(data)
    boot_stats = np.empty(n_boot)
    n = len(data)
    for i in range(n_boot):
        sample = rng.choice(data, size=n, replace=True)
        boot_stats[i] = stat_fn(sample)
    alpha = (1 - ci) / 2
    ci_lower = np.percentile(boot_stats, 100 * alpha)
    ci_upper = np.percentile(boot_stats, 100 * (1 - alpha))
    return estimate, ci_lower, ci_upper


def rank_biserial_r(u_stat: float, n1: int, n2: int):
    """
    Rank-biserial correlation  r = 1 - 2U / (n1*n2).
    Appropriate non-parametric effect size for Mann-Whitney U.
    """
    return 1.0 - (2.0 * u_stat) / (n1 * n2)


def cohens_d(x: np.ndarray, y: np.ndarray):
    """Cohen's d with pooled SD (for reference alongside rank-biserial)."""
    nx, ny = len(x), len(y)
    pooled_std = np.sqrt(
        ((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1))
        / (nx + ny - 2)
    )
    if pooled_std == 0:
        return 0.0
    return (np.mean(x) - np.mean(y)) / pooled_std


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    df = pd.read_csv(INPUT_CSV)

    # Separate group data
    group_data = {}
    for g in GROUPS:
        group_data[g] = df[df["Group"] == g]

    results = []

    # ------------------------------------------------------------------
    # 1. Bootstrap CIs for EBE per group
    # ------------------------------------------------------------------
    print("=" * 80)
    print("  Bootstrap 95% Confidence Intervals for EBE (mean) per Group")
    print("=" * 80)
    for g in GROUPS:
        ebe = group_data[g]["EBE"].values
        est, lo, hi = bootstrap_ci(ebe)
        results.append({
            "comparison": g,
            "metric": "EBE_mean",
            "statistic": est,
            "p_value": np.nan,
            "effect_size": np.nan,
            "effect_size_type": "",
            "CI_lower": lo,
            "CI_upper": hi,
            "n": len(ebe),
        })
        print(f"  {g:10s}:  mean = {est:.4f}   95% CI = [{lo:.4f}, {hi:.4f}]  (n={len(ebe)})")

    # ------------------------------------------------------------------
    # 2. Bootstrap CIs for Hallucination Rate per group
    # ------------------------------------------------------------------
    print()
    print("=" * 80)
    print("  Bootstrap 95% Confidence Intervals for Hallucination Rate (mean) per Group")
    print("=" * 80)
    for g in GROUPS:
        hr = group_data[g]["Hallucination_Rate"].values
        est, lo, hi = bootstrap_ci(hr)
        results.append({
            "comparison": g,
            "metric": "Hallucination_Rate_mean",
            "statistic": est,
            "p_value": np.nan,
            "effect_size": np.nan,
            "effect_size_type": "",
            "CI_lower": lo,
            "CI_upper": hi,
            "n": len(hr),
        })
        print(f"  {g:10s}:  mean = {est:.4f}   95% CI = [{lo:.4f}, {hi:.4f}]  (n={len(hr)})")

    # ------------------------------------------------------------------
    # 3. Mann-Whitney U tests for EBE (pairwise)
    # ------------------------------------------------------------------
    print()
    print("=" * 80)
    print("  Mann-Whitney U Tests  --  EBE  (two-sided)")
    print("=" * 80)
    header = (f"  {'Comparison':<22s} {'U':>8s} {'p-value':>10s} "
              f"{'rank-bis r':>12s} {'Cohen d':>10s} {'Signif':>8s}")
    print(header)
    print("  " + "-" * 74)

    for g1, g2 in GROUP_PAIRS:
        x = group_data[g1]["EBE"].values
        y = group_data[g2]["EBE"].values
        u_stat, p_val = stats.mannwhitneyu(x, y, alternative="two-sided")
        r_rb = rank_biserial_r(u_stat, len(x), len(y))
        d = cohens_d(x, y)
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"

        results.append({
            "comparison": f"{g1}_vs_{g2}",
            "metric": "EBE_MannWhitneyU",
            "statistic": u_stat,
            "p_value": p_val,
            "effect_size": r_rb,
            "effect_size_type": "rank_biserial_r",
            "CI_lower": np.nan,
            "CI_upper": np.nan,
            "n": len(x) + len(y),
        })
        # Also store Cohen's d row
        results.append({
            "comparison": f"{g1}_vs_{g2}",
            "metric": "EBE_CohensD",
            "statistic": d,
            "p_value": p_val,
            "effect_size": d,
            "effect_size_type": "cohens_d",
            "CI_lower": np.nan,
            "CI_upper": np.nan,
            "n": len(x) + len(y),
        })

        label = f"{g1} vs {g2}"
        print(f"  {label:<22s} {u_stat:8.1f} {p_val:10.4f} {r_rb:12.4f} {d:10.4f} {sig:>8s}")

    # ------------------------------------------------------------------
    # 4. Mann-Whitney U tests for Hallucination Rate (pairwise)
    # ------------------------------------------------------------------
    print()
    print("=" * 80)
    print("  Mann-Whitney U Tests  --  Hallucination Rate  (two-sided)")
    print("=" * 80)
    print(header)
    print("  " + "-" * 74)

    for g1, g2 in GROUP_PAIRS:
        x = group_data[g1]["Hallucination_Rate"].values
        y = group_data[g2]["Hallucination_Rate"].values
        u_stat, p_val = stats.mannwhitneyu(x, y, alternative="two-sided")
        r_rb = rank_biserial_r(u_stat, len(x), len(y))
        d = cohens_d(x, y)
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"

        results.append({
            "comparison": f"{g1}_vs_{g2}",
            "metric": "HallucinationRate_MannWhitneyU",
            "statistic": u_stat,
            "p_value": p_val,
            "effect_size": r_rb,
            "effect_size_type": "rank_biserial_r",
            "CI_lower": np.nan,
            "CI_upper": np.nan,
            "n": len(x) + len(y),
        })
        results.append({
            "comparison": f"{g1}_vs_{g2}",
            "metric": "HallucinationRate_CohensD",
            "statistic": d,
            "p_value": p_val,
            "effect_size": d,
            "effect_size_type": "cohens_d",
            "CI_lower": np.nan,
            "CI_upper": np.nan,
            "n": len(x) + len(y),
        })

        label = f"{g1} vs {g2}"
        print(f"  {label:<22s} {u_stat:8.1f} {p_val:10.4f} {r_rb:12.4f} {d:10.4f} {sig:>8s}")

    # ------------------------------------------------------------------
    # 5. Kruskal-Wallis omnibus test (non-parametric one-way ANOVA)
    # ------------------------------------------------------------------
    print()
    print("=" * 80)
    print("  Kruskal-Wallis H Test (omnibus) -- all three groups")
    print("=" * 80)

    for metric_name, col in [("EBE", "EBE"), ("Hallucination_Rate", "Hallucination_Rate")]:
        arrays = [group_data[g][col].values for g in GROUPS]
        h_stat, p_val = stats.kruskal(*arrays)
        # Eta-squared for Kruskal-Wallis: eta^2_H = (H - k + 1) / (N - k)
        k = len(GROUPS)
        N_total = sum(len(a) for a in arrays)
        eta_sq = (h_stat - k + 1) / (N_total - k)
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"

        results.append({
            "comparison": "omnibus_A_B_C",
            "metric": f"{metric_name}_KruskalWallis",
            "statistic": h_stat,
            "p_value": p_val,
            "effect_size": eta_sq,
            "effect_size_type": "eta_squared_H",
            "CI_lower": np.nan,
            "CI_upper": np.nan,
            "n": N_total,
        })
        print(f"  {metric_name:25s}  H = {h_stat:.4f},  p = {p_val:.4f},  "
              f"eta^2_H = {eta_sq:.4f}  {sig}")

    # ------------------------------------------------------------------
    # 6. Bootstrap CIs for EBE difference between group pairs
    # ------------------------------------------------------------------
    print()
    print("=" * 80)
    print("  Bootstrap 95% CIs for Pairwise EBE Mean Differences")
    print("=" * 80)

    for g1, g2 in GROUP_PAIRS:
        x = group_data[g1]["EBE"].values
        y = group_data[g2]["EBE"].values
        diff_fn = lambda d1=x, d2=y: None  # placeholder
        rng = np.random.default_rng(RNG_SEED)
        boot_diffs = np.empty(N_BOOTSTRAP)
        for i in range(N_BOOTSTRAP):
            bx = rng.choice(x, size=len(x), replace=True)
            by = rng.choice(y, size=len(y), replace=True)
            boot_diffs[i] = np.mean(bx) - np.mean(by)
        obs_diff = np.mean(x) - np.mean(y)
        alpha = (1 - CI_LEVEL) / 2
        lo = np.percentile(boot_diffs, 100 * alpha)
        hi = np.percentile(boot_diffs, 100 * (1 - alpha))

        results.append({
            "comparison": f"{g1}_vs_{g2}",
            "metric": "EBE_mean_diff_bootstrap",
            "statistic": obs_diff,
            "p_value": np.nan,
            "effect_size": np.nan,
            "effect_size_type": "",
            "CI_lower": lo,
            "CI_upper": hi,
            "n": len(x) + len(y),
        })
        label = f"{g1} - {g2}"
        ci_contains_zero = "contains 0" if lo <= 0 <= hi else "excludes 0"
        print(f"  {label:<22s}  diff = {obs_diff:+.4f}   95% CI = [{lo:+.4f}, {hi:+.4f}]  ({ci_contains_zero})")

    # ------------------------------------------------------------------
    # Write CSV
    # ------------------------------------------------------------------
    out_df = pd.DataFrame(results)
    col_order = ["comparison", "metric", "statistic", "p_value",
                 "effect_size", "effect_size_type", "CI_lower", "CI_upper", "n"]
    out_df = out_df[col_order]
    out_df.to_csv(OUTPUT_CSV, index=False, float_format="%.6f")
    print()
    print(f"  Results written to: {OUTPUT_CSV}")
    print()

    # ------------------------------------------------------------------
    # Compact summary table
    # ------------------------------------------------------------------
    print("=" * 80)
    print("  COMPACT SUMMARY FOR PAPER")
    print("=" * 80)
    print()
    print("  Group-level EBE summary:")
    for g in GROUPS:
        row = [r for r in results if r["comparison"] == g and r["metric"] == "EBE_mean"][0]
        print(f"    {g}: {row['statistic']:.3f}  [{row['CI_lower']:.3f}, {row['CI_upper']:.3f}]")
    print()
    print("  Group-level Hallucination Rate summary:")
    for g in GROUPS:
        row = [r for r in results if r["comparison"] == g and r["metric"] == "Hallucination_Rate_mean"][0]
        print(f"    {g}: {row['statistic']:.3f}  [{row['CI_lower']:.3f}, {row['CI_upper']:.3f}]")
    print()
    print("  Pairwise Mann-Whitney U (EBE):")
    for g1, g2 in GROUP_PAIRS:
        key = f"{g1}_vs_{g2}"
        row_u = [r for r in results if r["comparison"] == key and r["metric"] == "EBE_MannWhitneyU"][0]
        row_d = [r for r in results if r["comparison"] == key and r["metric"] == "EBE_CohensD"][0]
        p = row_u["p_value"]
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
        print(f"    {key}: U={row_u['statistic']:.1f}, p={p:.4f} {sig}, "
              f"r_rb={row_u['effect_size']:.3f}, d={row_d['effect_size']:.3f}")
    print()


if __name__ == "__main__":
    main()
