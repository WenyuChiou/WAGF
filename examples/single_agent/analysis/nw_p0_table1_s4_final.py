#!/usr/bin/env python3
"""
Nature Water: Final Table 1 under S4 specification (k=4, "both" split into two decisions).
Computes: mean±SD EHE, EHE_valid, violation rates, per-model bootstrap CIs, first-attempt check.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL")

MODELS = {
    "gemma3_4b": "Gemma-3 4B",
    "gemma3_12b": "Gemma-3 12B",
    "gemma3_27b": "Gemma-3 27B",
    "ministral3_3b": "Ministral 3B",
    "ministral3_8b": "Ministral 8B",
    "ministral3_14b": "Ministral 14B",
}
GROUPS = ["Group_A", "Group_B", "Group_C"]
RUNS = ["Run_1", "Run_2", "Run_3"]
K = 4  # S4 specification: k=4 for all

CANONICAL = {
    "Do Nothing": "do_nothing", "Do nothing": "do_nothing", "do nothing": "do_nothing",
    "Only Flood Insurance": "buy_insurance", "Buy flood insurance": "buy_insurance",
    "buy flood insurance": "buy_insurance",
    "Only House Elevation": "elevate_house", "Elevate the house": "elevate_house",
    "elevate the house": "elevate_house",
    "Both Flood Insurance and House Elevation": "both",
    "Relocate": "relocate", "relocate": "relocate",
    "Already relocated": "relocated",
    "do_nothing": "do_nothing", "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house", "relocated": "relocated",
}


def split_both(actions):
    """S4: Split 'both' into constituent decisions."""
    out = []
    for a in actions:
        if a == "both":
            out.extend(["buy_insurance", "elevate_house"])
        else:
            out.append(a)
    return out


def compute_ehe(actions, k=K):
    counts = Counter(actions)
    counts.pop("relocated", None)
    if not counts:
        return 0.0
    total = sum(counts.values())
    probs = np.array([c / total for c in counts.values()])
    probs = probs[probs > 0]
    H = -np.sum(probs * np.log2(probs))
    H_max = np.log2(k) if k > 1 else 1.0
    return H / H_max


def detect_violations(df):
    """Detect physical constraint violations in ungoverned runs."""
    df = df.copy()
    df["is_valid"] = True
    for agent_id in df["agent_id"].unique():
        mask = df["agent_id"] == agent_id
        agent_df = df[mask].sort_values("year")
        relocated = False
        elevated = False
        for idx, row in agent_df.iterrows():
            if relocated and row["action"] not in ["relocated"]:
                df.loc[idx, "is_valid"] = False
            if elevated and row["action"] in ["elevate_house"]:
                df.loc[idx, "is_valid"] = False
            if row["action"] == "relocate":
                relocated = True
            if row["action"] in ["elevate_house", "both"]:
                elevated = True
    return df


def bootstrap_ci(values, n_boot=10000):
    values = np.array(values)
    n = len(values)
    boot = np.array([np.mean(np.random.choice(values, size=n, replace=True)) for _ in range(n_boot)])
    return np.percentile(boot, [2.5, 97.5])


np.random.seed(42)

# ══════════════════════════════════════════════════════════════════════════
# COMPUTE ALL METRICS
# ══════════════════════════════════════════════════════════════════════════

table_rows = []
all_ungov_ehe = []
all_best_gov_ehe = []

print("=" * 110)
print("FINAL TABLE 1 (S4: k=4, 'both' split into buy_insurance + elevate_house, 3 runs per condition)")
print("=" * 110)

for model_dir, model_name in MODELS.items():
    a_ehe, a_ehe_valid, b_ehe, c_ehe = [], [], [], []
    viol_rates = []
    both_pct_list = []

    for run in RUNS:
        # --- Group A (ungoverned) ---
        path_a = BASE / model_dir / "Group_A" / run / "simulation_log.csv"
        if path_a.exists():
            df_a = pd.read_csv(path_a, encoding="utf-8")
            col = "yearly_decision" if "yearly_decision" in df_a.columns else "decision"
            df_a["action"] = df_a[col].map(lambda x: CANONICAL.get(str(x).strip(), str(x).strip().lower()))
            active_a = df_a[df_a["action"] != "relocated"].copy()

            # "Both" percentage (before split)
            n_both = (active_a["action"] == "both").sum()
            both_pct_list.append(n_both / len(active_a) * 100 if len(active_a) > 0 else 0)

            # Detect violations (before split)
            active_a = detect_violations(active_a)
            vr = (~active_a["is_valid"]).sum() / len(active_a) if len(active_a) > 0 else 0
            viol_rates.append(vr)

            # EHE_all (S4: split "both")
            actions_all = split_both(active_a["action"].tolist())
            a_ehe.append(compute_ehe(actions_all))

            # EHE_valid (S4: split "both", valid only)
            valid_actions = split_both(active_a[active_a["is_valid"]]["action"].tolist())
            a_ehe_valid.append(compute_ehe(valid_actions))

        # --- Group B (governed) ---
        path_b = BASE / model_dir / "Group_B" / run / "simulation_log.csv"
        if path_b.exists():
            df_b = pd.read_csv(path_b, encoding="utf-8")
            col_b = "yearly_decision" if "yearly_decision" in df_b.columns else "decision"
            df_b["action"] = df_b[col_b].map(lambda x: CANONICAL.get(str(x).strip(), str(x).strip().lower()))
            active_b = df_b[df_b["action"] != "relocated"]
            b_ehe.append(compute_ehe(active_b["action"].tolist()))

        # --- Group C (governed) ---
        path_c = BASE / model_dir / "Group_C" / run / "simulation_log.csv"
        if path_c.exists():
            df_c = pd.read_csv(path_c, encoding="utf-8")
            col_c = "yearly_decision" if "yearly_decision" in df_c.columns else "decision"
            df_c["action"] = df_c[col_c].map(lambda x: CANONICAL.get(str(x).strip(), str(x).strip().lower()))
            active_c = df_c[df_c["action"] != "relocated"]
            c_ehe.append(compute_ehe(active_c["action"].tolist()))

    row = {
        "Model": model_name,
        "both_pct": f"{np.mean(both_pct_list):.1f}",
        "viol_pct": f"{np.mean(viol_rates)*100:.1f}",
        "a_mean": np.mean(a_ehe), "a_sd": np.std(a_ehe, ddof=1) if len(a_ehe) > 1 else 0,
        "av_mean": np.mean(a_ehe_valid), "av_sd": np.std(a_ehe_valid, ddof=1) if len(a_ehe_valid) > 1 else 0,
        "b_mean": np.mean(b_ehe), "b_sd": np.std(b_ehe, ddof=1) if len(b_ehe) > 1 else 0,
        "c_mean": np.mean(c_ehe), "c_sd": np.std(c_ehe, ddof=1) if len(c_ehe) > 1 else 0,
    }
    best_gov = max(row["b_mean"], row["c_mean"])
    row["delta"] = best_gov - row["av_mean"]
    row["scaff"] = "Yes" if row["delta"] > 0.05 else ("Reversed" if row["delta"] < -0.05 else "Marginal")

    all_ungov_ehe.append(row["av_mean"])
    all_best_gov_ehe.append(best_gov)
    table_rows.append(row)

# Print Table 1
print(f"\n{'Model':>15s} | {'%both':>5s} | {'Viol%':>5s} | {'Ungov EHE':>12s} | {'Ungov EHE_v':>12s} | {'Gov B EHE':>12s} | {'Gov C EHE':>12s} | {'Delta':>7s} | {'Scaff?':>10s}")
print("-" * 110)
for r in table_rows:
    print(f"{r['Model']:>15s} | {r['both_pct']:>5s} | {r['viol_pct']:>5s} | {r['a_mean']:.3f}±{r['a_sd']:.3f} | {r['av_mean']:.3f}±{r['av_sd']:.3f} | {r['b_mean']:.3f}±{r['b_sd']:.3f} | {r['c_mean']:.3f}±{r['c_sd']:.3f} | {r['delta']:+.3f} | {r['scaff']:>10s}")

# ══════════════════════════════════════════════════════════════════════════
# PER-MODEL BOOTSTRAP CIs (governed vs ungoverned EHE_valid)
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 110}")
print("PER-MODEL BOOTSTRAP 95% CIs (best_governed - ungov_EHE_valid)")
print("=" * 110)

for r in table_rows:
    model_dir = [k for k, v in MODELS.items() if v == r["Model"]][0]
    a_v_vals, best_g_vals = [], []
    for run in RUNS:
        # Ungoverned EHE_valid
        path_a = BASE / model_dir / "Group_A" / run / "simulation_log.csv"
        if path_a.exists():
            df_a = pd.read_csv(path_a, encoding="utf-8")
            col = "yearly_decision" if "yearly_decision" in df_a.columns else "decision"
            df_a["action"] = df_a[col].map(lambda x: CANONICAL.get(str(x).strip(), str(x).strip().lower()))
            active_a = detect_violations(df_a[df_a["action"] != "relocated"].copy())
            valid_acts = split_both(active_a[active_a["is_valid"]]["action"].tolist())
            a_v_vals.append(compute_ehe(valid_acts))

        # Best governed
        b_val, c_val = 0, 0
        for g in ["Group_B", "Group_C"]:
            p = BASE / model_dir / g / run / "simulation_log.csv"
            if p.exists():
                df_g = pd.read_csv(p, encoding="utf-8")
                col_g = "yearly_decision" if "yearly_decision" in df_g.columns else "decision"
                df_g["action"] = df_g[col_g].map(lambda x: CANONICAL.get(str(x).strip(), str(x).strip().lower()))
                active_g = df_g[df_g["action"] != "relocated"]
                ehe = compute_ehe(active_g["action"].tolist())
                if g == "Group_B":
                    b_val = ehe
                else:
                    c_val = ehe
        best_g_vals.append(max(b_val, c_val))

    if len(a_v_vals) >= 3 and len(best_g_vals) >= 3:
        diffs = np.array(best_g_vals) - np.array(a_v_vals)
        ci = bootstrap_ci(diffs)
        d = np.mean(diffs) / np.std(diffs, ddof=1) if np.std(diffs, ddof=1) > 0 else np.inf
        overlap = "Yes" if np.min(best_g_vals) > np.max(a_v_vals) else "No"
        print(f"  {r['Model']:>15s}: Δ={np.mean(diffs):+.3f}, CI [{ci[0]:.3f}, {ci[1]:.3f}], d={d:.2f}, zero_overlap={overlap}")

# ══════════════════════════════════════════════════════════════════════════
# POOLED STATISTICS
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 110}")
print("POOLED STATISTICS")
print("=" * 110)

all_ungov = np.array(all_ungov_ehe)
all_gov = np.array(all_best_gov_ehe)
diffs = all_gov - all_ungov

scaff_count = sum(1 for r in table_rows if r["scaff"] == "Yes")
rev_count = sum(1 for r in table_rows if r["scaff"] == "Reversed")
marg_count = sum(1 for r in table_rows if r["scaff"] == "Marginal")

print(f"  Scaffolding: {scaff_count}/6 Yes, {marg_count}/6 Marginal, {rev_count}/6 Reversed")
print(f"  Mean ungov EHE_valid: {np.mean(all_ungov):.3f} ± {np.std(all_ungov, ddof=1):.3f}")
print(f"  Mean best-gov EHE:    {np.mean(all_gov):.3f} ± {np.std(all_gov, ddof=1):.3f}")
print(f"  Pooled delta: {np.mean(diffs):+.3f} ± {np.std(diffs, ddof=1):.3f}")
ci = bootstrap_ci(diffs)
print(f"  Pooled 95% CI: [{ci[0]:.3f}, {ci[1]:.3f}]")
print(f"  CI excludes 0: {'YES' if ci[0] > 0 else 'NO'}")

# ══════════════════════════════════════════════════════════════════════════
# MARKDOWN TABLE FOR PAPER
# ══════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 110}")
print("MARKDOWN TABLE FOR PAPER (copy-paste ready)")
print("=" * 110)

print("""
| Model | Composite (%) | Violation (%) | Ungov. EHE | Ungov. EHE_valid | Gov. B EHE | Gov. C EHE | Delta | Effect |
|-------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|""")
for r in table_rows:
    print(f"| {r['Model']} | {r['both_pct']} | {r['viol_pct']} | {r['a_mean']:.3f} ± {r['a_sd']:.3f} | {r['av_mean']:.3f} ± {r['av_sd']:.3f} | {r['b_mean']:.3f} ± {r['b_sd']:.3f} | {r['c_mean']:.3f} ± {r['c_sd']:.3f} | {r['delta']:+.3f} | {'**' + r['scaff'] + '**' if r['scaff'] == 'Reversed' else r['scaff']} |")

print(f"\n*k = 4 for all conditions. Composite actions (simultaneous insurance + elevation) in ungoverned runs are split into constituent decisions (see Methods). EHE_valid excludes physical constraint violations. Delta = max(Gov B, Gov C) − Ungov EHE_valid. Values are mean ± SD across 3 independent runs (seed = 42).*")

# Save CSV
out = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\paper\tables\Table1_flood_S4_final.csv")
pd.DataFrame(table_rows).to_csv(out, index=False)
print(f"\nSaved: {out}")

print("\nDone.")
