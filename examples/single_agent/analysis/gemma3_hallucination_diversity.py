"""
Task-053: Gemma 3 Hallucination + Diversity Analysis

Cross-model comparison of hallucination rates and behavioral diversity
across Gemma 3 parameter sizes (1B, 4B, 12B, 27B) and governance groups (A/B/C).

Group A: Original LLMABMPMT-Final.py (no governance audit)
Group B: Strict governance, window memory
Group C: Full cognitive (humancentric + priority schema)

Usage:
    python gemma3_hallucination_diversity.py
    python gemma3_hallucination_diversity.py --base-dir path/to/results
    python gemma3_hallucination_diversity.py --models gemma3_1b gemma3_4b
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import entropy

# MCC calculation (reused from SQ1 analyze_joh_mcc.py)
try:
    from sklearn.metrics import matthews_corrcoef, confusion_matrix
except ImportError:
    print("Warning: scikit-learn not installed. MCC analysis disabled.")
    matthews_corrcoef = None

# --- CONFIGURATION ---
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman"] + plt.rcParams["font.serif"]
sns.set_theme(style="whitegrid", context="paper")

GEMMA3_MODELS = [
    ("gemma3_1b", "Gemma 3 (1B)", 1e9),
    ("gemma3_4b", "Gemma 3 (4B)", 4e9),
    ("gemma3_12b", "Gemma 3 (12B)", 12e9),
    ("gemma3_27b", "Gemma 3 (27B)", 27e9),
]

GROUPS = ["Group_A", "Group_B", "Group_C"]

GROUP_COLORS = {
    "Group_A": "crimson",
    "Group_B": "forestgreen",
    "Group_C": "steelblue",
}

GROUP_LABELS = {
    "Group_A": "Group A (Original)",
    "Group_B": "Group B (Strict)",
    "Group_C": "Group C (Full Cognitive)",
}


# =============================================================================
# Keyword Extraction (from SQ1 analyze_joh_mcc.py)
# =============================================================================

def parse_binary_threat(memory_str):
    """Parse memory to determine binary internal threat (SQ1 keyword extraction)."""
    if pd.isna(memory_str):
        return 0
    mem = str(memory_str).lower()
    if "got flooded" in mem or "damage on my house" in mem:
        return 1
    if "severe enough to cause damage" in mem:
        return 1
    return 0


def parse_binary_action(decision_str):
    """Parse decision to determine binary action."""
    if pd.isna(decision_str):
        return 0
    d = str(decision_str).lower().strip()

    # Inaction
    if d in ["do nothing", "do_nothing", "n/a"]:
        return 0
    if "do nothing" in d:
        return 0
    if "nothing" == d:
        return 0

    # Active action
    if "reloc" in d:
        return 1
    if "elev" in d:
        return 1
    if "insur" in d:
        return 1

    # Legacy format (original script uses full phrases)
    if "only flood insurance" in d or "only house elevation" in d:
        return 1
    if "both" in d:
        return 1

    return 0


def normalize_decision(d):
    """Normalize decision to standard categories."""
    d = str(d).lower().strip()
    if "reloc" in d:
        return "relocate"
    if "elev" in d:
        return "elevate"
    if "insur" in d and "elev" in d:
        return "both"
    if "both" in d:
        return "both"
    if "insur" in d:
        return "insurance"
    return "do_nothing"


def calculate_shannon_entropy(series):
    """Calculate Shannon entropy in bits."""
    pk = series.value_counts(normalize=True).values
    return entropy(pk, base=2)


# =============================================================================
# MCC Analysis
# =============================================================================

def calculate_mcc(df):
    """Calculate Matthews Correlation Coefficient from simulation log."""
    if matthews_corrcoef is None:
        return np.nan

    # Handle column name differences between original and broker scripts
    dec_col = "yearly_decision" if "yearly_decision" in df.columns else "decision"
    mem_col = "memory" if "memory" in df.columns else None

    if mem_col is None or dec_col not in df.columns:
        return np.nan

    y_true = df[mem_col].apply(parse_binary_threat)
    y_pred = df[dec_col].apply(parse_binary_action)

    # Filter N/A
    valid_mask = df[dec_col] != "N/A"
    y_true = y_true[valid_mask]
    y_pred = y_pred[valid_mask]

    if len(y_true) < 5:
        return np.nan
    if len(np.unique(y_true)) < 2 or len(np.unique(y_pred)) < 2:
        if np.array_equal(y_true.values, y_pred.values):
            return 1.0
        return 0.0

    return matthews_corrcoef(y_true, y_pred)


# =============================================================================
# Data Loading
# =============================================================================

def load_simulation_log(base_dir, model_name, group):
    """Load simulation_log.csv from results directory."""
    # Try standard path first
    path = base_dir / model_name / group / "Run_1" / "simulation_log.csv"
    if path.exists():
        df = pd.read_csv(path)
        df.columns = [c.lower() for c in df.columns]
        return df

    # Try recursive search (nested output dirs like "gemma3_4b_disabled/")
    run_dir = base_dir / model_name / group / "Run_1"
    if run_dir.exists():
        found = list(run_dir.rglob("simulation_log.csv"))
        if found:
            df = pd.read_csv(found[0])
            df.columns = [c.lower() for c in df.columns]
            return df

    return None


def load_governance_audit(base_dir, model_name, group):
    """Load household_governance_audit.csv (only exists for Groups B/C)."""
    path = base_dir / model_name / group / "Run_1" / "household_governance_audit.csv"
    if path.exists():
        df = pd.read_csv(path)
        df.columns = [c.lower() for c in df.columns]
        return df

    # Try recursive search
    run_dir = base_dir / model_name / group / "Run_1"
    if run_dir.exists():
        found = list(run_dir.rglob("household_governance_audit.csv"))
        if found:
            df = pd.read_csv(found[0])
            df.columns = [c.lower() for c in df.columns]
            return df

    return None


# =============================================================================
# Hallucination Analysis
# =============================================================================

def analyze_hallucination(base_dir, model_name, group, param_count):
    """Compute hallucination metrics for a single model-group cohort."""
    result = {
        "model": model_name,
        "group": group,
        "param_count": param_count,
    }

    # MCC from simulation_log (works for all groups)
    sim_df = load_simulation_log(base_dir, model_name, group)
    if sim_df is not None:
        result["mcc"] = calculate_mcc(sim_df)
        result["has_sim_log"] = True
    else:
        result["mcc"] = np.nan
        result["has_sim_log"] = False

    # Governance metrics (only for Groups B/C)
    audit_df = load_governance_audit(base_dir, model_name, group)
    if audit_df is not None:
        result["has_audit"] = True
        result["mean_format_retries"] = (
            audit_df["format_retries"].mean()
            if "format_retries" in audit_df.columns
            else np.nan
        )
        result["mean_parse_confidence"] = (
            audit_df["parse_confidence"].mean()
            if "parse_confidence" in audit_df.columns
            else np.nan
        )

        # Rule violation counts
        for col in ["rules_personal_hit", "rules_social_hit", "rules_thinking_hit"]:
            if col in audit_df.columns:
                result[col] = audit_df[col].sum()
            else:
                result[col] = 0

        result["total_rule_violations"] = (
            result.get("rules_personal_hit", 0)
            + result.get("rules_social_hit", 0)
            + result.get("rules_thinking_hit", 0)
        )
        result["total_steps"] = len(audit_df)
        result["rule_violation_rate"] = (
            result["total_rule_violations"] / result["total_steps"]
            if result["total_steps"] > 0
            else 0
        )

        # Fallback / hallucination interventions
        if "fallback_activated" in audit_df.columns:
            result["intv_h_count"] = audit_df["fallback_activated"].sum()
        else:
            result["intv_h_count"] = 0

        # Invalid skill rate
        if "status" in audit_df.columns:
            result["invalid_skill_rate"] = (
                (audit_df["status"] == "invalid_skill").mean()
            )
        else:
            result["invalid_skill_rate"] = np.nan
    else:
        result["has_audit"] = False
        for k in [
            "mean_format_retries",
            "mean_parse_confidence",
            "rules_personal_hit",
            "rules_social_hit",
            "rules_thinking_hit",
            "total_rule_violations",
            "total_steps",
            "rule_violation_rate",
            "intv_h_count",
            "invalid_skill_rate",
        ]:
            result[k] = np.nan

    return result


# =============================================================================
# Diversity Analysis
# =============================================================================

def analyze_diversity(base_dir, model_name, group, param_count):
    """Compute diversity metrics for a single model-group cohort."""
    result = {
        "model": model_name,
        "group": group,
        "param_count": param_count,
    }

    sim_df = load_simulation_log(base_dir, model_name, group)
    if sim_df is None:
        result["has_data"] = False
        return result

    result["has_data"] = True

    # Find decision column
    dec_col = next(
        (c for c in sim_df.columns if c in ["yearly_decision", "decision"]),
        None,
    )
    if dec_col is None:
        result["has_data"] = False
        return result

    # Year column
    year_col = "year" if "year" in sim_df.columns else None
    if year_col is None:
        result["has_data"] = False
        return result

    # Per-year entropy
    entropy_series = []
    max_year = int(sim_df[year_col].max())
    for year in range(max_year + 1):
        year_data = sim_df[sim_df[year_col] == year]
        if year_data.empty:
            continue
        norm_decs = year_data[dec_col].apply(normalize_decision)
        h_val = calculate_shannon_entropy(norm_decs)
        pop_size = len(year_data)
        entropy_series.append(
            {"year": year, "entropy": h_val, "population": pop_size}
        )

    if not entropy_series:
        result["has_data"] = False
        return result

    result["entropy_series"] = entropy_series
    entropies = [e["entropy"] for e in entropy_series]
    result["mean_entropy"] = np.mean(entropies)
    result["final_entropy"] = entropies[-1] if entropies else np.nan

    # Entropy trend (linear fit)
    years = [e["year"] for e in entropy_series]
    if len(years) >= 2:
        result["entropy_trend"] = np.polyfit(years, entropies, 1)[0]
    else:
        result["entropy_trend"] = 0.0

    # Decision distribution
    all_decisions = sim_df[dec_col].apply(normalize_decision)
    result["decision_dist"] = all_decisions.value_counts(normalize=True).to_dict()

    # Sawtooth: flood vs non-flood entropy difference
    # (Requires flood_years.csv to identify flood years)
    flood_years_path = (
        Path(base_dir).parent / "flood_years.csv"
    )
    if flood_years_path.exists():
        flood_df = pd.read_csv(flood_years_path)
        flood_years_set = set(flood_df.iloc[:, 0].values)

        flood_entropies = [
            e["entropy"] for e in entropy_series if e["year"] in flood_years_set
        ]
        nonflood_entropies = [
            e["entropy"]
            for e in entropy_series
            if e["year"] not in flood_years_set
        ]
        if flood_entropies and nonflood_entropies:
            result["sawtooth_amplitude"] = np.mean(flood_entropies) - np.mean(
                nonflood_entropies
            )
        else:
            result["sawtooth_amplitude"] = np.nan
    else:
        result["sawtooth_amplitude"] = np.nan

    return result


# =============================================================================
# Plotting Functions
# =============================================================================

def plot_hallucination_charts(h_results, output_dir, models_config):
    """Generate H1-H5 hallucination analysis charts."""
    df = pd.DataFrame(h_results)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # H1: Format Retries by Model Size (Groups B/C only)
    ax = axes[0]
    bc_data = df[df["group"].isin(["Group_B", "Group_C"]) & df["has_audit"]]
    if not bc_data.empty:
        bc_pivot = bc_data.pivot(
            index="model", columns="group", values="mean_format_retries"
        )
        bc_pivot.plot(kind="bar", ax=ax, color=[GROUP_COLORS.get(g, "gray") for g in bc_pivot.columns])
        ax.set_title("H1: Format Retries by Model Size", fontweight="bold")
        ax.set_ylabel("Mean Format Retries")
        ax.set_xlabel("")
        ax.legend(
            [GROUP_LABELS.get(g, g) for g in bc_pivot.columns],
            fontsize=8,
        )
        ax.tick_params(axis="x", rotation=45)
    else:
        ax.text(0.5, 0.5, "No audit data", ha="center", va="center")
        ax.set_title("H1: Format Retries (No Data)")

    # H3: MCC by Model Size (All Groups)
    ax = axes[1]
    mcc_data = df[df["mcc"].notna()]
    if not mcc_data.empty:
        mcc_pivot = mcc_data.pivot(index="model", columns="group", values="mcc")
        mcc_pivot.plot(
            kind="bar",
            ax=ax,
            color=[GROUP_COLORS.get(g, "gray") for g in mcc_pivot.columns],
        )
        ax.set_title("H3: MCC by Model Size", fontweight="bold")
        ax.set_ylabel("MCC [-1, 1]")
        ax.set_xlabel("")
        ax.axhline(y=0, color="black", linestyle="--", alpha=0.3)
        ax.legend(
            [GROUP_LABELS.get(g, g) for g in mcc_pivot.columns],
            fontsize=8,
        )
        ax.tick_params(axis="x", rotation=45)
    else:
        ax.text(0.5, 0.5, "No MCC data", ha="center", va="center")
        ax.set_title("H3: MCC (No Data)")

    # H4: Hallucination Rate vs Parameters (log-x)
    ax = axes[2]
    bc_scaling = df[df["group"].isin(["Group_B", "Group_C"]) & df["has_audit"]]
    if not bc_scaling.empty:
        for group in ["Group_B", "Group_C"]:
            gdata = bc_scaling[bc_scaling["group"] == group].sort_values(
                "param_count"
            )
            if not gdata.empty:
                ax.plot(
                    gdata["param_count"],
                    gdata["mean_format_retries"],
                    "o-",
                    color=GROUP_COLORS.get(group, "gray"),
                    label=GROUP_LABELS.get(group, group),
                    linewidth=2,
                    markersize=8,
                )
        ax.set_xscale("log")
        ax.set_title("H4: Hallucination vs Parameters", fontweight="bold")
        ax.set_xlabel("Parameter Count")
        ax.set_ylabel("Mean Format Retries")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, "No scaling data", ha="center", va="center")
        ax.set_title("H4: Scaling (No Data)")

    plt.suptitle(
        "Hallucination Analysis: Gemma 3 Family",
        fontsize=16,
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()
    plt.savefig(output_dir / "hallucination_analysis.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Saved] {output_dir / 'hallucination_analysis.png'}")


def plot_diversity_charts(d_results, output_dir, models_config):
    """Generate D1-D5 diversity analysis charts."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # D1: Entropy Time Series (all model-group combos)
    ax = axes[0]
    line_styles = {"Group_A": "-", "Group_B": "--", "Group_C": "-."}
    for r in d_results:
        if not r.get("has_data") or "entropy_series" not in r:
            continue
        es = r["entropy_series"]
        years = [e["year"] for e in es]
        ents = [e["entropy"] for e in es]
        model_label = r["model"].replace("gemma3_", "").upper()
        ax.plot(
            years,
            ents,
            line_styles.get(r["group"], "-"),
            color=GROUP_COLORS.get(r["group"], "gray"),
            label=f"{model_label} {r['group'][-1]}",
            linewidth=1.2,
            alpha=0.8,
        )
    ax.set_title("D1: Entropy Time Series", fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Shannon Entropy (bits)")
    ax.set_ylim(0, 2.5)
    ax.legend(fontsize=6, ncol=3, loc="lower left")
    ax.grid(True, alpha=0.3)

    # D2: Final Year Entropy by Model Size
    ax = axes[1]
    df_div = pd.DataFrame(
        [
            {"model": r["model"], "group": r["group"], "final_entropy": r.get("final_entropy", np.nan)}
            for r in d_results
            if r.get("has_data")
        ]
    )
    if not df_div.empty:
        pivot = df_div.pivot(index="model", columns="group", values="final_entropy")
        pivot.plot(
            kind="bar",
            ax=ax,
            color=[GROUP_COLORS.get(g, "gray") for g in pivot.columns],
        )
        ax.set_title("D2: Final Year Entropy", fontweight="bold")
        ax.set_ylabel("H(Year 10) bits")
        ax.set_xlabel("")
        ax.legend(
            [GROUP_LABELS.get(g, g) for g in pivot.columns],
            fontsize=8,
        )
        ax.tick_params(axis="x", rotation=45)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_title("D2: Final Entropy (No Data)")

    # D4: Entropy vs Parameters (scaling)
    ax = axes[2]
    for group in GROUPS:
        gdata = [
            r
            for r in d_results
            if r.get("has_data") and r["group"] == group
        ]
        if gdata:
            gdata.sort(key=lambda x: x["param_count"])
            ax.plot(
                [r["param_count"] for r in gdata],
                [r["mean_entropy"] for r in gdata],
                "o-",
                color=GROUP_COLORS.get(group, "gray"),
                label=GROUP_LABELS.get(group, group),
                linewidth=2,
                markersize=8,
            )
    ax.set_xscale("log")
    ax.set_title("D4: Entropy vs Parameters", fontweight="bold")
    ax.set_xlabel("Parameter Count")
    ax.set_ylabel("Mean Entropy (bits)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.suptitle(
        "Diversity Analysis: Gemma 3 Family",
        fontsize=16,
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()
    plt.savefig(output_dir / "diversity_analysis.png", dpi=300, bbox_inches="tight")
    plt.close()
    print(f"  [Saved] {output_dir / 'diversity_analysis.png'}")


def plot_decision_distribution(d_results, output_dir):
    """Generate D3: Decision Distribution Stacked Bar."""
    categories = ["do_nothing", "insurance", "elevate", "relocate", "both"]
    data = []
    for r in d_results:
        if not r.get("has_data") or "decision_dist" not in r:
            continue
        row = {
            "model_group": f"{r['model'].replace('gemma3_', '').upper()}\n{r['group'][-1]}",
        }
        dist = r["decision_dist"]
        for cat in categories:
            row[cat] = dist.get(cat, 0.0)
        data.append(row)

    if not data:
        return

    df = pd.DataFrame(data)
    df = df.set_index("model_group")

    fig, ax = plt.subplots(figsize=(14, 6))
    df[categories].plot(kind="bar", stacked=True, ax=ax, colormap="Set2")
    ax.set_title(
        "D3: Decision Distribution Across Models and Groups",
        fontweight="bold",
        fontsize=14,
    )
    ax.set_ylabel("Proportion")
    ax.set_xlabel("")
    ax.legend(title="Decision", bbox_to_anchor=(1.02, 1), fontsize=9)
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    plt.savefig(
        output_dir / "decision_distribution.png", dpi=300, bbox_inches="tight"
    )
    plt.close()
    print(f"  [Saved] {output_dir / 'decision_distribution.png'}")


def plot_parse_confidence_heatmap(h_results, output_dir):
    """Generate H2: Parse Confidence Heatmap."""
    bc_data = [
        r
        for r in h_results
        if r["has_audit"] and not np.isnan(r.get("mean_parse_confidence", np.nan))
    ]
    if not bc_data:
        return

    df = pd.DataFrame(bc_data)
    pivot = df.pivot(index="model", columns="group", values="mean_parse_confidence")

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.heatmap(
        pivot,
        annot=True,
        fmt=".3f",
        cmap="RdYlGn",
        vmin=0,
        vmax=1,
        ax=ax,
        linewidths=0.5,
    )
    ax.set_title(
        "H2: Parse Confidence Heatmap (Groups B/C)", fontweight="bold", fontsize=14
    )
    ax.set_ylabel("Model")
    ax.set_xlabel("Group")
    plt.tight_layout()
    plt.savefig(
        output_dir / "parse_confidence_heatmap.png", dpi=300, bbox_inches="tight"
    )
    plt.close()
    print(f"  [Saved] {output_dir / 'parse_confidence_heatmap.png'}")


def plot_rule_violations(h_results, output_dir):
    """Generate H5: Rule Violation Distribution."""
    bc_data = [r for r in h_results if r["has_audit"]]
    if not bc_data:
        return

    df = pd.DataFrame(bc_data)
    fig, ax = plt.subplots(figsize=(10, 5))

    x_labels = [
        f"{r['model'].replace('gemma3_', '').upper()}\n{r['group'][-1]}"
        for r in bc_data
    ]
    x = np.arange(len(x_labels))
    width = 0.25

    personal = [r.get("rules_personal_hit", 0) for r in bc_data]
    social = [r.get("rules_social_hit", 0) for r in bc_data]
    thinking = [r.get("rules_thinking_hit", 0) for r in bc_data]

    ax.bar(x - width, personal, width, label="Personal", color="salmon")
    ax.bar(x, social, width, label="Social", color="lightskyblue")
    ax.bar(x + width, thinking, width, label="Thinking", color="lightgreen")

    ax.set_title(
        "H5: Rule Violation Distribution (Groups B/C)",
        fontweight="bold",
        fontsize=14,
    )
    ax.set_ylabel("Total Violations")
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=8)
    ax.legend()
    plt.tight_layout()
    plt.savefig(
        output_dir / "rule_violations.png", dpi=300, bbox_inches="tight"
    )
    plt.close()
    print(f"  [Saved] {output_dir / 'rule_violations.png'}")


# =============================================================================
# Summary Report
# =============================================================================

def print_summary_report(h_results, d_results):
    """Print consolidated summary to console."""
    print("\n" + "=" * 70)
    print("GEMMA 3 HALLUCINATION + DIVERSITY ANALYSIS REPORT")
    print("=" * 70)

    # Hallucination Summary
    print("\n--- HALLUCINATION METRICS ---")
    h_df = pd.DataFrame(h_results)
    print("\nMCC (Memory-Action Consistency) [-1 to 1, higher = more rational):")
    mcc_pivot = h_df.pivot(index="model", columns="group", values="mcc")
    print(mcc_pivot.to_string())

    bc = h_df[h_df["has_audit"]]
    if not bc.empty:
        print("\nFormat Retries (Groups B/C only):")
        fr_pivot = bc.pivot(
            index="model", columns="group", values="mean_format_retries"
        )
        print(fr_pivot.to_string())

        print("\nParse Confidence (Groups B/C only):")
        pc_pivot = bc.pivot(
            index="model", columns="group", values="mean_parse_confidence"
        )
        print(pc_pivot.to_string())

    # Diversity Summary
    print("\n--- DIVERSITY METRICS ---")
    d_df = pd.DataFrame(
        [
            {
                "model": r["model"],
                "group": r["group"],
                "mean_entropy": r.get("mean_entropy", np.nan),
                "final_entropy": r.get("final_entropy", np.nan),
                "entropy_trend": r.get("entropy_trend", np.nan),
                "sawtooth_amplitude": r.get("sawtooth_amplitude", np.nan),
            }
            for r in d_results
            if r.get("has_data")
        ]
    )
    if not d_df.empty:
        print("\nMean Shannon Entropy (bits) [0 = uniform, 2.32 = max for 5 categories]:")
        ent_pivot = d_df.pivot(index="model", columns="group", values="mean_entropy")
        print(ent_pivot.to_string())

        print("\nEntropy Trend (slope) [+ = diversifying, - = converging]:")
        trend_pivot = d_df.pivot(
            index="model", columns="group", values="entropy_trend"
        )
        print(trend_pivot.to_string())

    print("\n" + "=" * 70)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Gemma 3 Hallucination + Diversity Analysis (Task-053)"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=str(
            Path(__file__).parent.parent / "results" / "JOH_FINAL"
        ),
        help="Base directory containing model results",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).parent / "Task053_Results"),
        help="Output directory for charts and CSVs",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=None,
        help="Specific model names to analyze (e.g., gemma3_1b gemma3_4b)",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter models if specified
    if args.models:
        models = [m for m in GEMMA3_MODELS if m[0] in args.models]
    else:
        models = GEMMA3_MODELS

    print("=" * 60)
    print("Gemma 3 Hallucination + Diversity Analysis")
    print(f"Base: {base_dir}")
    print(f"Output: {output_dir}")
    print(f"Models: {[m[0] for m in models]}")
    print("=" * 60)

    # 1. Collect hallucination metrics
    print("\n[Phase 1] Collecting Hallucination Metrics...")
    h_results = []
    for model_name, model_label, param_count in models:
        for group in GROUPS:
            r = analyze_hallucination(base_dir, model_name, group, param_count)
            h_results.append(r)
            status = "OK" if r["has_sim_log"] else "MISS"
            audit_status = "audit=OK" if r["has_audit"] else "audit=N/A"
            print(
                f"  [{status}] {model_name} / {group}: MCC={r['mcc']:.3f if not np.isnan(r['mcc']) else 'N/A'} {audit_status}"
            )

    # 2. Collect diversity metrics
    print("\n[Phase 2] Collecting Diversity Metrics...")
    d_results = []
    for model_name, model_label, param_count in models:
        for group in GROUPS:
            r = analyze_diversity(base_dir, model_name, group, param_count)
            d_results.append(r)
            if r.get("has_data"):
                print(
                    f"  [OK] {model_name} / {group}: H_mean={r['mean_entropy']:.3f}, H_final={r['final_entropy']:.3f}"
                )
            else:
                print(f"  [MISS] {model_name} / {group}: No data")

    # 3. Save raw data
    print("\n[Phase 3] Saving Raw Data...")
    h_df = pd.DataFrame(h_results)
    h_df.to_csv(output_dir / "hallucination_metrics.csv", index=False)
    print(f"  [Saved] {output_dir / 'hallucination_metrics.csv'}")

    d_flat = [
        {
            k: v
            for k, v in r.items()
            if k != "entropy_series" and k != "decision_dist"
        }
        for r in d_results
    ]
    d_df = pd.DataFrame(d_flat)
    d_df.to_csv(output_dir / "diversity_metrics.csv", index=False)
    print(f"  [Saved] {output_dir / 'diversity_metrics.csv'}")

    # Save entropy time series
    all_entropy = []
    for r in d_results:
        if r.get("has_data") and "entropy_series" in r:
            for e in r["entropy_series"]:
                all_entropy.append(
                    {
                        "model": r["model"],
                        "group": r["group"],
                        "year": e["year"],
                        "entropy": e["entropy"],
                        "population": e["population"],
                    }
                )
    if all_entropy:
        pd.DataFrame(all_entropy).to_csv(
            output_dir / "entropy_time_series.csv", index=False
        )
        print(f"  [Saved] {output_dir / 'entropy_time_series.csv'}")

    # 4. Generate plots
    print("\n[Phase 4] Generating Charts...")
    plot_hallucination_charts(h_results, output_dir, models)
    plot_parse_confidence_heatmap(h_results, output_dir)
    plot_rule_violations(h_results, output_dir)
    plot_diversity_charts(d_results, output_dir, models)
    plot_decision_distribution(d_results, output_dir)

    # 5. Print summary
    print_summary_report(h_results, d_results)

    print(f"\nAll outputs saved to: {output_dir}")
    print("Done!")


if __name__ == "__main__":
    main()
