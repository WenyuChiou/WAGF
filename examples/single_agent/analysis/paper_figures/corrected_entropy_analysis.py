"""
SAGE Paper — Corrected Entropy & EBE Analysis (v2)
===================================================
Computes hallucination-corrected Shannon entropy for the flood ABM experiment
using the PostHocValidator framework for unified hallucination detection.

Methodology changes from v1:
  - Insurance renewal EXCLUDED from R_H (annual renewable policy, not hallucination)
  - Thinking violations (V1/V2/V3) INCLUDED in R_H via KeywordClassifier
  - R_H = (physical + thinking) / N_active

Metrics:
  H_norm   = H / log2(k),  k=5 actions, range [0,1]
  R_H      = (physical_hallucinations + thinking_violations) / N_active
  EBE      = H_norm * (1 - R_H)   "Effective Behavioral Entropy"

Outputs:
  corrected_entropy_gemma3_4b.csv
  summary printed to console

Usage:
  python corrected_entropy_analysis.py
"""

import math
import os
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
pd.set_option('future.no_silent_downcasting', True)

# PostHocValidator components
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from broker.validators.posthoc import KeywordClassifier, ThinkingRulePostHoc
from broker.validators.posthoc.unified_rh import _compute_physical_hallucinations

# ---------- configuration ----------
BASE = Path(__file__).resolve().parents[2]  # examples/single_agent
RESULTS = BASE / "results" / "JOH_FINAL" / "gemma3_4b"
OUT_DIR = Path(__file__).resolve().parent
K = 5  # number of possible actions (DoNothing, Insurance, Elevation, Both, Relocate)


# ---------- helpers ----------
def shannon_entropy_norm(counts: dict, n: int, k: int = K) -> float:
    """Normalised Shannon entropy H / log2(k)."""
    if n == 0 or k <= 1:
        return 0.0
    probs = [c / n for c in counts.values() if c > 0]
    h = -sum(p * math.log2(p) for p in probs)
    return h / math.log2(k)


def _normalise_decision(raw: str) -> str:
    """Map verbose Group-A decision names to canonical labels."""
    low = str(raw).strip().lower()
    if "both" in low:
        return "Both"
    if "elevation" in low or "elevat" in low:
        return "Elevation"
    if "insurance" in low or "insur" in low:
        return "Insurance"
    if "relocat" in low:
        return "Relocate"
    return "DoNothing"


def _normalise_decision_bc(raw: str) -> str:
    """Map Group-B/C coded decision names to canonical labels."""
    low = str(raw).strip().lower()
    if low in ("elevate_house",):
        return "Elevation"
    if low in ("buy_insurance",):
        return "Insurance"
    if low in ("relocate",):
        return "Relocate"
    if low in ("relocated",):
        return "Relocated"
    if low in ("do_nothing",):
        return "DoNothing"
    if "both" in low:
        return "Both"
    return "DoNothing"


# ---------- analysis ----------
def analyse_group(group: str, sim_path: Path) -> pd.DataFrame:
    """Return per-year metrics for one group."""
    df = pd.read_csv(sim_path)

    # Detect decision column
    if "decision" in df.columns:
        dec_col = "decision"
        norm_fn = _normalise_decision
    elif "yearly_decision" in df.columns:
        dec_col = "yearly_decision"
        norm_fn = _normalise_decision_bc
    else:
        raise KeyError(f"No decision column found in {sim_path}")

    df["decision_norm"] = df[dec_col].apply(norm_fn)
    group_letter = group.replace("Group_", "")

    # --- Classify appraisals for thinking-rule checks ---
    classifier = KeywordClassifier()
    rule_checker = ThinkingRulePostHoc()

    ta_col = "threat_appraisal" if "threat_appraisal" in df.columns else None
    ca_col = "coping_appraisal" if "coping_appraisal" in df.columns else None
    if ta_col and ca_col:
        df = classifier.classify_dataframe(df, ta_col, ca_col)
    else:
        df["ta_level"] = "M"
        df["ca_level"] = "M"

    # --- Physical hallucination mask (re-elevation + post-relocation) ---
    # NOTE: Insurance renewal excluded — annual renewable, not hallucination
    has_elevated = "elevated" in df.columns
    has_relocated = "relocated" in df.columns
    if has_elevated and has_relocated:
        phys_mask = _compute_physical_hallucinations(df)
    else:
        phys_mask = pd.Series(False, index=df.index)

    # --- Active agent tracking ---
    df_sorted = df.sort_values(["agent_id", "year"]).copy()
    if has_relocated:
        df_sorted["prev_relocated"] = (
            df_sorted.groupby("agent_id")["relocated"]
            .shift(1).fillna(False).infer_objects(copy=False)
        )
    else:
        df_sorted["prev_relocated"] = False

    # --- Pre-compute thinking violations on FULL time series ---
    # ThinkingRulePostHoc uses shift(1) to detect state transitions, so it
    # must receive the complete multi-year DataFrame, not single-year slices.
    active_mask = (~df_sorted["prev_relocated"]) & (df_sorted["year"] >= 2)
    df_active_all = df_sorted[active_mask]
    if len(df_active_all) > 0:
        think_results_all = rule_checker.apply(
            df_active_all, group=group_letter,
            decision_col=dec_col, ta_level_col="ta_level"
        )
        # Build a boolean Series (True = thinking violation) aligned to df_active_all index
        think_violation_mask = pd.Series(False, index=df_active_all.index)
        for r in think_results_all:
            if r.mask is not None and len(r.mask) > 0:
                think_violation_mask.loc[r.mask.index[r.mask]] = True
    else:
        think_violation_mask = pd.Series(False, index=df_sorted.index)

    rows = []
    for yr in sorted(df["year"].unique()):
        yr_all = df[df["year"] == yr].copy()
        n = len(yr_all)

        # --- raw entropy ---
        raw_counts = Counter(yr_all["decision_norm"])
        raw_hnorm = shannon_entropy_norm(raw_counts, n)

        # --- active agents (not previously relocated) ---
        yr_sorted = df_sorted[df_sorted["year"] == yr]
        yr_active = yr_sorted[~yr_sorted["prev_relocated"]]
        n_active = len(yr_active)

        if yr < 2 or n_active == 0:
            dominant = raw_counts.most_common(1)[0] if raw_counts else ("None", 0)
            rows.append({
                "Model": "gemma3_4b", "Group": group, "Year": int(yr),
                "N": n, "N_Active": n_active if n_active > 0 else n,
                "Raw_H_norm": round(raw_hnorm, 4),
                "Corrected_H_norm": round(raw_hnorm, 4),
                "Hallucination_Count": 0, "Hallucination_Rate": 0.0,
                "Physical_Hall": 0, "Thinking_Hall": 0,
                "EBE": round(raw_hnorm, 4),
                "Raw_Dominant": dominant[0],
                "Raw_Dominant_Freq": round(dominant[1] / n, 4) if n else 0,
                "Corrected_Dominant": dominant[0],
                "Corrected_Dominant_Freq": round(dominant[1] / n, 4) if n else 0,
            })
            continue

        # --- physical hallucinations this year ---
        yr_phys = int(phys_mask.reindex(yr_active.index, fill_value=False).sum())

        # --- thinking violations this year (from pre-computed full-series mask) ---
        yr_think = int(think_violation_mask.reindex(yr_active.index, fill_value=False).sum())

        yr_hall = yr_phys + yr_think
        yr_rh = yr_hall / n_active if n_active > 0 else 0.0

        # --- active-only entropy ---
        active_decisions = yr_active[dec_col].apply(norm_fn).tolist()
        active_counts = Counter(active_decisions)
        corr_hnorm = shannon_entropy_norm(active_counts, n_active)

        ebe = raw_hnorm * (1.0 - yr_rh)

        dominant = raw_counts.most_common(1)[0] if raw_counts else ("None", 0)
        corr_dominant = active_counts.most_common(1)[0] if active_counts else ("None", 0)

        rows.append({
            "Model": "gemma3_4b", "Group": group, "Year": int(yr),
            "N": n, "N_Active": n_active,
            "Raw_H_norm": round(raw_hnorm, 4),
            "Corrected_H_norm": round(corr_hnorm, 4),
            "Hallucination_Count": yr_hall,
            "Hallucination_Rate": round(yr_rh, 4),
            "Physical_Hall": yr_phys, "Thinking_Hall": yr_think,
            "EBE": round(ebe, 4),
            "Raw_Dominant": dominant[0],
            "Raw_Dominant_Freq": round(dominant[1] / n, 4) if n else 0,
            "Corrected_Dominant": corr_dominant[0],
            "Corrected_Dominant_Freq": round(corr_dominant[1] / n_active, 4) if n_active else 0,
        })

    return pd.DataFrame(rows)


def main():
    all_frames = []

    groups = {
        "Group_A": RESULTS / "Group_A" / "Run_1" / "simulation_log.csv",
        "Group_B": RESULTS / "Group_B" / "Run_1" / "simulation_log.csv",
        "Group_C": RESULTS / "Group_C" / "Run_1" / "simulation_log.csv",
    }

    for group, path in groups.items():
        if not path.exists():
            print(f"WARNING: {path} not found, skipping {group}")
            continue
        print(f"Analysing {group} ...")
        frame = analyse_group(group, path)
        all_frames.append(frame)

    result = pd.concat(all_frames, ignore_index=True)

    # ---------- save ----------
    out_csv = OUT_DIR / "corrected_entropy_gemma3_4b.csv"
    result.to_csv(out_csv, index=False)
    print(f"\nSaved: {out_csv}")

    # ---------- summary ----------
    print("\n" + "=" * 72)
    print("SAGE Paper — Corrected Entropy Summary (Gemma3 4B)")
    print("  R_H = physical + thinking (insurance renewal excluded)")
    print("=" * 72)

    for group in ["Group_A", "Group_B", "Group_C"]:
        g = result[result["Group"] == group]
        if g.empty:
            continue
        mean_raw = g["Raw_H_norm"].mean()
        mean_corr = g["Corrected_H_norm"].mean()
        mean_rh = g["Hallucination_Rate"].mean()
        mean_ebe = g["EBE"].mean()
        total_phys = int(g["Physical_Hall"].sum())
        total_think = int(g["Thinking_Hall"].sum())
        print(f"\n{group}:")
        print(f"  Mean Raw H_norm      = {mean_raw:.4f}")
        print(f"  Mean Corrected H_norm= {mean_corr:.4f}")
        print(f"  Mean Hallucination   = {mean_rh:.1%}")
        print(f"  Mean EBE             = {mean_ebe:.4f}")
        print(f"  Breakdown: Physical={total_phys}, Thinking={total_think}")
        print(f"  Year-by-year:")
        for _, r in g.iterrows():
            hall_str = f" Hall={r['Hallucination_Rate']:.0%}" if r["Hallucination_Rate"] > 0 else ""
            detail = f" (P={int(r['Physical_Hall'])},T={int(r['Thinking_Hall'])})" if r["Hallucination_Count"] > 0 else ""
            print(
                f"    Y{r['Year']:2d}: Raw={r['Raw_H_norm']:.3f}  "
                f"Corr={r['Corrected_H_norm']:.3f}  "
                f"EBE={r['EBE']:.3f}{hall_str}{detail}"
            )

    # ---------- key comparison ----------
    print("\n" + "=" * 72)
    print("KEY COMPARISON: Mean EBE by Group")
    print("=" * 72)
    for group in ["Group_A", "Group_B", "Group_C"]:
        g = result[result["Group"] == group]
        if g.empty:
            continue
        rh_mean = g["Hallucination_Rate"].mean()
        print(f"  {group}: EBE = {g['EBE'].mean():.4f}  R_H = {rh_mean:.1%}")
    print()


if __name__ == "__main__":
    main()
