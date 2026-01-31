"""
SAGE Paper — Corrected Entropy & EBE Analysis
===============================================
Computes hallucination-corrected Shannon entropy for the flood ABM experiment.

Key finding: Group A (ungoverned) Gemma3 4B has 33% hallucination rate.
When corrected, its apparent diversity (H_norm ~ 0.5-0.7) drops to near-zero,
while governed groups (B, C) maintain genuine diversity (H_norm 0.17-0.80).

Metrics:
  H_norm   = H / log2(k),  k=5 actions, range [0,1]
  R_H      = hallucinated decisions / total decisions
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

    # Detect state columns
    has_elevated = "elevated" in df.columns
    has_insurance = "has_insurance" in df.columns
    has_relocated = "relocated" in df.columns

    rows = []
    for yr in sorted(df["year"].unique()):
        yr_df = df[df["year"] == yr].copy()
        n = len(yr_df)

        # --- raw entropy ---
        raw_counts = Counter(yr_df["decision_norm"])
        raw_hnorm = shannon_entropy_norm(raw_counts, n)

        # --- hallucination detection (prior-year state) ---
        hall_count = 0
        corrected = yr_df["decision_norm"].tolist()

        if yr > 1 and (has_elevated or has_insurance or has_relocated):
            prev_yr = df[df["year"] == yr - 1]
            for idx_i, (_, row) in enumerate(yr_df.iterrows()):
                agent = row["agent_id"]
                decision = row["decision_norm"]
                prev = prev_yr[prev_yr["agent_id"] == agent]
                if prev.empty:
                    continue
                prev = prev.iloc[0]

                is_hall = False
                if has_elevated and prev["elevated"] and decision == "Elevation":
                    is_hall = True
                if has_insurance and prev["has_insurance"] and decision == "Insurance":
                    is_hall = True
                if has_elevated and has_insurance:
                    # "Both" when already have both
                    if prev["elevated"] and prev["has_insurance"] and decision == "Both":
                        is_hall = True
                    # "Both" when already elevated (insurance part valid, elevation not)
                    elif prev["elevated"] and decision == "Both":
                        is_hall = True
                    # "Both" when already insured (elevation part valid, insurance not)
                    elif prev["has_insurance"] and decision == "Both":
                        is_hall = True
                if has_relocated and prev.get("relocated", False):
                    is_hall = True

                if is_hall:
                    # For B/C: "relocated" is a STATUS marker, not a decision.
                    # Don't count status markers as hallucinations.
                    if decision == "Relocated":
                        # Agent already relocated; this row is just a status.
                        # Exclude from active population (don't count in entropy).
                        corrected[idx_i] = "__EXCLUDED__"
                    else:
                        hall_count += 1
                        corrected[idx_i] = "DoNothing"

        # --- corrected entropy (excluding relocated status markers) ---
        active_corrected = [d for d in corrected if d != "__EXCLUDED__"]
        n_active = len(active_corrected)
        corr_counts = Counter(active_corrected)
        corr_hnorm = shannon_entropy_norm(corr_counts, n_active)

        # --- rates (hallucination rate based on active agents only) ---
        r_h = hall_count / n_active if n_active > 0 else 0.0
        ebe = raw_hnorm * (1.0 - r_h)

        # --- dominant action ---
        dominant = raw_counts.most_common(1)[0] if raw_counts else ("None", 0)
        corr_dominant = corr_counts.most_common(1)[0] if corr_counts else ("None", 0)

        rows.append({
            "Model": "gemma3_4b",
            "Group": group,
            "Year": int(yr),
            "N": n,
            "N_Active": n_active,
            "Raw_H_norm": round(raw_hnorm, 4),
            "Corrected_H_norm": round(corr_hnorm, 4),
            "Hallucination_Count": hall_count,
            "Hallucination_Rate": round(r_h, 4),
            "EBE": round(ebe, 4),
            "Raw_Dominant": dominant[0],
            "Raw_Dominant_Freq": round(dominant[1] / n, 4) if n else 0,
            "Corrected_Dominant": corr_dominant[0],
            "Corrected_Dominant_Freq": round(corr_dominant[1] / n, 4) if n else 0,
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
    print("=" * 72)

    for group in ["Group_A", "Group_B", "Group_C"]:
        g = result[result["Group"] == group]
        if g.empty:
            continue
        mean_raw = g["Raw_H_norm"].mean()
        mean_corr = g["Corrected_H_norm"].mean()
        mean_rh = g["Hallucination_Rate"].mean()
        mean_ebe = g["EBE"].mean()
        print(f"\n{group}:")
        print(f"  Mean Raw H_norm      = {mean_raw:.4f}")
        print(f"  Mean Corrected H_norm= {mean_corr:.4f}")
        print(f"  Mean Hallucination   = {mean_rh:.1%}")
        print(f"  Mean EBE             = {mean_ebe:.4f}")
        print(f"  Year-by-year:")
        for _, r in g.iterrows():
            hall_str = f" Hall={r['Hallucination_Rate']:.0%}" if r["Hallucination_Rate"] > 0 else ""
            print(
                f"    Y{r['Year']:2d}: Raw={r['Raw_H_norm']:.3f}  "
                f"Corr={r['Corrected_H_norm']:.3f}  "
                f"EBE={r['EBE']:.3f}{hall_str}"
            )

    # ---------- key comparison ----------
    print("\n" + "=" * 72)
    print("KEY COMPARISON: Mean EBE by Group")
    print("=" * 72)
    for group in ["Group_A", "Group_B", "Group_C"]:
        g = result[result["Group"] == group]
        if g.empty:
            continue
        print(f"  {group}: EBE = {g['EBE'].mean():.4f}")
    print()


if __name__ == "__main__":
    main()
