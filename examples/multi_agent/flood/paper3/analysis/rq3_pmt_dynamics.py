#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RQ3: PMT (Protection Motivation Theory) Construct Dynamics
==========================================================
Analyzes threat perception (TP) and coping perception (CP) dynamics from
the Full hybrid_v2 experiment (3 seeds: 42, 123, 456).

Sections:
  1. TP Accumulation — TP by year and cumulative flood count
  2. TP Decay — TP by years-since-last-flood
  3. CP Ceiling — CP by year and income bracket; Spearman correlation
  4. TP-CP Gap — Gap trajectory decomposed by MG/NMG and Owner/Renter
  5. Action Exhaustion — % of previously-adaptive agents choosing do_nothing
  6. PMT x Action Heatmap — Protective action rate by TP x CP grid

Figures → paper3/results/paper3_hybrid_v2/analysis/
Tables  → paper3/analysis/tables/
"""

import json
import csv
import os
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats as sp_stats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.colors import LinearSegmentedColormap

_PAPER3_OVERRIDE = os.environ.get("PAPER3_TRACE_DIR")
_PAPER3_OUTPUT_OVERRIDE = os.environ.get("PAPER3_OUTPUT_DIR")


# ---------------------------------------------------------------------------
# Windows-safe print
# ---------------------------------------------------------------------------
def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        print(text.encode("ascii", errors="replace").decode(), **kwargs)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
FLOOD_DIR = BASE / "examples" / "multi_agent" / "flood"
RESULT_BASE = Path(os.path.normpath(_PAPER3_OVERRIDE)).parent.parent if _PAPER3_OVERRIDE else FLOOD_DIR / "paper3" / "results" / "paper3_hybrid_v2"
DATA_DIR = FLOOD_DIR / "data"
FIG_DIR = Path(os.path.normpath(_PAPER3_OUTPUT_OVERRIDE)) if _PAPER3_OUTPUT_OVERRIDE else RESULT_BASE / "analysis"
TABLE_DIR = Path(os.path.normpath(_PAPER3_OUTPUT_OVERRIDE)) if _PAPER3_OUTPUT_OVERRIDE else FLOOD_DIR / "paper3" / "analysis" / "tables"
FIG_DIR.mkdir(parents=True, exist_ok=True)
TABLE_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = [int(Path(os.path.normpath(_PAPER3_OVERRIDE)).parent.name.replace("seed_", ""))] if _PAPER3_OVERRIDE else [42, 123, 456]
PROFILES_CSV = DATA_DIR / "agent_profiles_balanced.csv"

LABEL_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
LABEL_NAMES = {1: "VL", 2: "L", 3: "M", 4: "H", 5: "VH"}

PROTECTIVE_ACTIONS = {
    "buy_insurance", "buy_contents_insurance",
    "elevate_house", "buyout_program", "relocate",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_profiles():
    """Load agent profiles → dict[agent_id] = {mg, tenure, income, income_bracket}."""
    profiles = {}
    with open(PROFILES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            profiles[row["agent_id"]] = {
                "mg": row["mg"].strip().lower() == "true",
                "tenure": row["tenure"].strip(),
                "income": float(row["income"]),
                "income_bracket": row["income_bracket"].strip(),
            }
    return profiles


def income_bucket(income):
    """Map income to bracket string."""
    if income < 25000:
        return "<25K"
    elif income < 50000:
        return "25-50K"
    elif income < 75000:
        return "50-75K"
    else:
        return ">75K"


def load_traces(seed):
    """Load all household traces for a seed. Returns list of dicts."""
    traces = []
    for role in ("owner", "renter"):
        path = (
            RESULT_BASE / f"seed_{seed}" / (Path(os.path.normpath(_PAPER3_OVERRIDE)).name if _PAPER3_OVERRIDE else "gemma3_4b_strict") / "raw"
            / f"household_{role}_traces.jsonl"
        )
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                # Extract key fields
                sp = d.get("skill_proposal") or {}
                reasoning = sp.get("reasoning") or {}
                approved = d.get("approved_skill", {})
                sb = d.get("state_before", {})

                tp_raw = str(reasoning.get("TP_LABEL", "")).strip().upper()
                cp_raw = str(reasoning.get("CP_LABEL", "")).strip().upper()

                rec = {
                    "seed": seed,
                    "year": d.get("year"),
                    "agent_id": d.get("agent_id"),
                    "agent_type": d.get("agent_type", ""),
                    "tp_label": tp_raw,
                    "tp_num": LABEL_MAP.get(tp_raw, np.nan),
                    "cp_label": cp_raw,
                    "cp_num": LABEL_MAP.get(cp_raw, np.nan),
                    "skill_name": approved.get("skill_name", "unknown"),
                    "flooded_this_year": bool(sb.get("flooded_this_year", False)),
                    "flood_count": int(sb.get("flood_count", 0)),
                    "income": float(sb.get("income", 0)),
                    "mg": bool(sb.get("mg", False)),
                    "tenure": str(sb.get("tenure", "")),
                }
                traces.append(rec)
    return traces


def load_all_traces():
    """Load traces for all seeds."""
    all_traces = []
    for seed in SEEDS:
        safe_print(f"  Loading seed {seed} ...")
        all_traces.extend(load_traces(seed))
    safe_print(f"  Total traces: {len(all_traces)}")
    return all_traces


# ---------------------------------------------------------------------------
# Helper: compute cumulative flood count from per-agent yearly data
# ---------------------------------------------------------------------------
def compute_cumulative_floods(traces):
    """Add 'cum_flood' and 'years_since_flood' to each trace."""
    # Group by (seed, agent_id), sort by year
    agent_data = defaultdict(list)
    for t in traces:
        agent_data[(t["seed"], t["agent_id"])].append(t)

    for key, recs in agent_data.items():
        recs.sort(key=lambda x: x["year"])
        cum = 0
        last_flood_year = None
        for r in recs:
            if r["flooded_this_year"]:
                cum += 1
                last_flood_year = r["year"]
            r["cum_flood"] = cum
            if last_flood_year is not None:
                r["years_since_flood"] = r["year"] - last_flood_year
            else:
                r["years_since_flood"] = 99  # never flooded
    return traces


def compute_prior_adaptive(traces):
    """Add 'was_adaptive_before' — True if agent took a protective action in any prior year."""
    agent_data = defaultdict(list)
    for t in traces:
        agent_data[(t["seed"], t["agent_id"])].append(t)

    for key, recs in agent_data.items():
        recs.sort(key=lambda x: x["year"])
        ever_adaptive = False
        for r in recs:
            r["was_adaptive_before"] = ever_adaptive
            if r["skill_name"] in PROTECTIVE_ACTIONS:
                ever_adaptive = True
    return traces


# ---------------------------------------------------------------------------
# Section 1: TP Accumulation
# ---------------------------------------------------------------------------
def section1_tp_accumulation(traces):
    safe_print("\n" + "=" * 60)
    safe_print("SECTION 1: TP Accumulation")
    safe_print("=" * 60)

    years = sorted(set(t["year"] for t in traces))

    # 1a: Mean TP by year per seed
    tp_by_year_seed = {}
    for seed in SEEDS:
        seed_data = [t for t in traces if t["seed"] == seed]
        year_tp = {}
        for y in years:
            vals = [t["tp_num"] for t in seed_data if t["year"] == y and not np.isnan(t["tp_num"])]
            year_tp[y] = np.mean(vals) if vals else np.nan
        tp_by_year_seed[seed] = year_tp

    # Print
    safe_print(f"\n{'Year':<6}", end="")
    for s in SEEDS:
        safe_print(f"{'Seed_'+str(s):<12}", end="")
    safe_print(f"{'Mean':<10}")
    for y in years:
        vals = [tp_by_year_seed[s][y] for s in SEEDS]
        mean_val = np.nanmean(vals)
        safe_print(f"{y:<6}", end="")
        for v in vals:
            safe_print(f"{v:<12.3f}", end="")
        safe_print(f"{mean_val:<10.3f}")

    # 1b: TP by cumulative flood count
    flood_bins = {0: [], 1: [], 2: [], 3: [], 4: [], "5+": []}
    for t in traces:
        if np.isnan(t["tp_num"]):
            continue
        cf = t["cum_flood"]
        if cf >= 5:
            flood_bins["5+"].append(t["tp_num"])
        elif cf in flood_bins:
            flood_bins[cf].append(t["tp_num"])

    safe_print("\nTP by cumulative flood count:")
    safe_print(f"{'CumFlood':<12}{'N':<8}{'Mean_TP':<10}{'Std':<10}")
    table_rows = []
    for k in [0, 1, 2, 3, 4, "5+"]:
        vals = flood_bins[k]
        n = len(vals)
        m = np.mean(vals) if vals else np.nan
        s = np.std(vals) if vals else np.nan
        safe_print(f"{str(k):<12}{n:<8}{m:<10.3f}{s:<10.3f}")
        table_rows.append({"cum_flood": str(k), "n": n, "mean_tp": round(m, 3), "std_tp": round(s, 3)})

    # Save table
    _write_csv(TABLE_DIR / "rq3_tp_by_cumflood.csv", table_rows,
               ["cum_flood", "n", "mean_tp", "std_tp"])

    return tp_by_year_seed, years


# ---------------------------------------------------------------------------
# Section 2: TP Decay
# ---------------------------------------------------------------------------
def section2_tp_decay(traces):
    safe_print("\n" + "=" * 60)
    safe_print("SECTION 2: TP Decay (years since last flood)")
    safe_print("=" * 60)

    # Only traces where agent has been flooded at least once
    flooded_traces = [t for t in traces if t["years_since_flood"] < 99 and not np.isnan(t["tp_num"])]

    bins = {0: [], 1: [], 2: [], 3: [], "4+": []}
    for t in flooded_traces:
        ysf = t["years_since_flood"]
        if ysf >= 4:
            bins["4+"].append(t["tp_num"])
        elif ysf in bins:
            bins[ysf].append(t["tp_num"])

    safe_print(f"\n{'YrsSinceFlood':<16}{'N':<8}{'Mean_TP':<10}{'Std':<10}")
    table_rows = []
    base_tp = None
    for k in [0, 1, 2, 3, "4+"]:
        vals = bins[k]
        n = len(vals)
        m = np.mean(vals) if vals else np.nan
        s = np.std(vals) if vals else np.nan
        if k == 0:
            base_tp = m
        decay_pct = ((base_tp - m) / base_tp * 100) if (base_tp and m and base_tp > 0) else 0.0
        safe_print(f"{str(k):<16}{n:<8}{m:<10.3f}{s:<10.3f}  decay={decay_pct:.1f}%")
        table_rows.append({
            "years_since_flood": str(k), "n": n,
            "mean_tp": round(m, 3), "std_tp": round(s, 3),
            "decay_pct": round(decay_pct, 1),
        })

    _write_csv(TABLE_DIR / "rq3_tp_decay.csv", table_rows,
               ["years_since_flood", "n", "mean_tp", "std_tp", "decay_pct"])

    total_decay = table_rows[-1]["decay_pct"] if table_rows else 0
    safe_print(f"\n  --> Total TP decay over 4+ years: {total_decay:.1f}%")
    safe_print("  --> Traditional ABM reference: 30-50% decay")

    return bins


# ---------------------------------------------------------------------------
# Section 3: CP Ceiling
# ---------------------------------------------------------------------------
def section3_cp_ceiling(traces, profiles):
    safe_print("\n" + "=" * 60)
    safe_print("SECTION 3: CP Ceiling")
    safe_print("=" * 60)

    years = sorted(set(t["year"] for t in traces))

    # 3a: Mean CP by year per seed
    cp_by_year_seed = {}
    for seed in SEEDS:
        seed_data = [t for t in traces if t["seed"] == seed]
        year_cp = {}
        for y in years:
            vals = [t["cp_num"] for t in seed_data if t["year"] == y and not np.isnan(t["cp_num"])]
            year_cp[y] = np.mean(vals) if vals else np.nan
        cp_by_year_seed[seed] = year_cp

    safe_print(f"\n{'Year':<6}", end="")
    for s in SEEDS:
        safe_print(f"{'Seed_'+str(s):<12}", end="")
    safe_print(f"{'Mean':<10}")
    for y in years:
        vals = [cp_by_year_seed[s][y] for s in SEEDS]
        mean_val = np.nanmean(vals)
        safe_print(f"{y:<6}", end="")
        for v in vals:
            safe_print(f"{v:<12.3f}", end="")
        safe_print(f"{mean_val:<10.3f}")

    # 3b: CP by income bracket
    brackets = ["<25K", "25-50K", "50-75K", ">75K"]
    bracket_vals = {b: [] for b in brackets}
    incomes_all = []
    cps_all = []

    for t in traces:
        if np.isnan(t["cp_num"]):
            continue
        inc = t["income"]
        b = income_bucket(inc)
        bracket_vals[b].append(t["cp_num"])
        incomes_all.append(inc)
        cps_all.append(t["cp_num"])

    safe_print(f"\nCP by income bracket:")
    safe_print(f"{'Bracket':<12}{'N':<8}{'Mean_CP':<10}{'Std':<10}")
    table_rows = []
    for b in brackets:
        vals = bracket_vals[b]
        n = len(vals)
        m = np.mean(vals) if vals else np.nan
        s = np.std(vals) if vals else np.nan
        safe_print(f"{b:<12}{n:<8}{m:<10.3f}{s:<10.3f}")
        table_rows.append({"income_bracket": b, "n": n, "mean_cp": round(m, 3), "std_cp": round(s, 3)})

    # Spearman correlation
    rho, p = sp_stats.spearmanr(incomes_all, cps_all)
    safe_print(f"\n  Spearman(income, CP): rho={rho:.4f}, p={p:.2e}")
    table_rows.append({"income_bracket": "Spearman_rho", "n": len(incomes_all),
                        "mean_cp": round(rho, 4), "std_cp": round(p, 6)})

    _write_csv(TABLE_DIR / "rq3_cp_by_income.csv", table_rows,
               ["income_bracket", "n", "mean_cp", "std_cp"])

    return cp_by_year_seed, years


# ---------------------------------------------------------------------------
# Section 4: TP-CP Gap
# ---------------------------------------------------------------------------
def section4_tp_cp_gap(traces):
    safe_print("\n" + "=" * 60)
    safe_print("SECTION 4: TP-CP Gap Trajectory")
    safe_print("=" * 60)

    years = sorted(set(t["year"] for t in traces))

    # Decompose by MG/NMG and Owner/Renter, per seed
    groups = {
        "MG": lambda t: t["mg"],
        "NMG": lambda t: not t["mg"],
        "Owner": lambda t: "owner" in t["agent_type"],
        "Renter": lambda t: "renter" in t["agent_type"],
    }

    gap_data = {}  # group -> seed -> {year: gap}
    for gname, gfunc in groups.items():
        gap_data[gname] = {}
        for seed in SEEDS:
            year_gap = {}
            for y in years:
                recs = [t for t in traces
                        if t["seed"] == seed and t["year"] == y and gfunc(t)
                        and not np.isnan(t["tp_num"]) and not np.isnan(t["cp_num"])]
                if recs:
                    gaps = [r["tp_num"] - r["cp_num"] for r in recs]
                    year_gap[y] = np.mean(gaps)
                else:
                    year_gap[y] = np.nan
            gap_data[gname][seed] = year_gap

    # Print table
    safe_print(f"\n{'Year':<6}", end="")
    for g in groups:
        safe_print(f"{g:<12}", end="")
    safe_print()

    table_rows = []
    for y in years:
        safe_print(f"{y:<6}", end="")
        row = {"year": y}
        for g in groups:
            vals = [gap_data[g][s][y] for s in SEEDS]
            m = np.nanmean(vals)
            safe_print(f"{m:<12.3f}", end="")
            row[f"gap_{g}"] = round(m, 3)
        safe_print()
        table_rows.append(row)

    _write_csv(TABLE_DIR / "rq3_tp_cp_gap.csv", table_rows,
               ["year"] + [f"gap_{g}" for g in groups])

    return gap_data, years


# ---------------------------------------------------------------------------
# Section 5: Action Exhaustion
# ---------------------------------------------------------------------------
def section5_action_exhaustion(traces):
    safe_print("\n" + "=" * 60)
    safe_print("SECTION 5: Action Exhaustion")
    safe_print("=" * 60)

    years = sorted(set(t["year"] for t in traces))

    exhaust_by_seed = {}
    for seed in SEEDS:
        seed_traces = [t for t in traces if t["seed"] == seed]
        year_rate = {}
        for y in years:
            # Among agents who were previously adaptive
            eligible = [t for t in seed_traces if t["year"] == y and t["was_adaptive_before"]]
            if eligible:
                dn_count = sum(1 for t in eligible if t["skill_name"] == "do_nothing")
                year_rate[y] = dn_count / len(eligible) * 100
            else:
                year_rate[y] = np.nan
        exhaust_by_seed[seed] = year_rate

    safe_print(f"\n{'Year':<6}", end="")
    for s in SEEDS:
        safe_print(f"{'Seed_'+str(s):<14}", end="")
    safe_print(f"{'Mean':<10}{'N_eligible':<12}")

    table_rows = []
    for y in years:
        vals = [exhaust_by_seed[s][y] for s in SEEDS]
        m = np.nanmean(vals)
        # Count eligible across all seeds
        n_elig = sum(1 for t in traces if t["year"] == y and t["was_adaptive_before"])
        safe_print(f"{y:<6}", end="")
        for v in vals:
            safe_print(f"{v:<14.1f}" if not np.isnan(v) else f"{'N/A':<14}", end="")
        safe_print(f"{m:<10.1f}{n_elig:<12}")
        table_rows.append({
            "year": y,
            "exhaustion_pct_mean": round(m, 1) if not np.isnan(m) else "",
            "n_eligible": n_elig,
            **{f"seed_{s}": round(exhaust_by_seed[s][y], 1)
               if not np.isnan(exhaust_by_seed[s][y]) else ""
               for s in SEEDS},
        })

    _write_csv(TABLE_DIR / "rq3_action_exhaustion.csv", table_rows,
               ["year", "exhaustion_pct_mean", "n_eligible"] + [f"seed_{s}" for s in SEEDS])

    return exhaust_by_seed, years


# ---------------------------------------------------------------------------
# Section 6: PMT x Action Heatmap
# ---------------------------------------------------------------------------
def section6_pmt_action_heatmap(traces):
    safe_print("\n" + "=" * 60)
    safe_print("SECTION 6: PMT x Action Heatmap")
    safe_print("=" * 60)

    # Bin TP and CP into L/M/H (collapse VL->L, VH->H)
    def coarse(num):
        if num <= 2:
            return "L"
        elif num == 3:
            return "M"
        else:
            return "H"

    tp_labels = ["L", "M", "H"]
    cp_labels = ["L", "M", "H"]

    grid_total = defaultdict(int)
    grid_protective = defaultdict(int)

    for t in traces:
        if np.isnan(t["tp_num"]) or np.isnan(t["cp_num"]):
            continue
        tp_c = coarse(t["tp_num"])
        cp_c = coarse(t["cp_num"])
        grid_total[(tp_c, cp_c)] += 1
        if t["skill_name"] in PROTECTIVE_ACTIONS:
            grid_protective[(tp_c, cp_c)] += 1

    safe_print(f"\nProtective action rate (%) by TP x CP:")
    safe_print(f"{'TP\\CP':<8}", end="")
    for cp in cp_labels:
        safe_print(f"{'CP='+cp:<12}", end="")
    safe_print()

    heatmap = np.zeros((3, 3))
    for i, tp in enumerate(tp_labels):
        safe_print(f"{'TP='+tp:<8}", end="")
        for j, cp in enumerate(cp_labels):
            total = grid_total[(tp, cp)]
            prot = grid_protective[(tp, cp)]
            rate = (prot / total * 100) if total > 0 else 0
            heatmap[i, j] = rate
            safe_print(f"{rate:<12.1f}", end="")
        safe_print()

    safe_print(f"\nCell counts (total):")
    for i, tp in enumerate(tp_labels):
        for j, cp in enumerate(cp_labels):
            safe_print(f"  TP={tp}, CP={cp}: N={grid_total[(tp, cp)]}, "
                        f"protective={grid_protective[(tp, cp)]}")

    return heatmap, tp_labels, cp_labels


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------
def plot_figure1(tp_by_year_seed, cp_by_year_seed, gap_data, exhaust_by_seed, years):
    """Figure 1 (2x2): TP accumulation, CP ceiling, TP-CP gap (MG vs NMG), Action exhaustion."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    seed_colors = {42: "#2196F3", 123: "#FF9800", 456: "#4CAF50"}

    # (a) TP Accumulation
    ax = axes[0, 0]
    for seed in SEEDS:
        ys = [tp_by_year_seed[seed][y] for y in years]
        ax.plot(years, ys, color=seed_colors[seed], alpha=0.4, linewidth=1,
                label=f"Seed {seed}")
    # Mean
    mean_tp = [np.nanmean([tp_by_year_seed[s][y] for s in SEEDS]) for y in years]
    ax.plot(years, mean_tp, color="black", linewidth=2.5, label="Mean")
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean TP (1=VL ... 5=VH)")
    ax.set_title("(a) Threat Perception Accumulation")
    ax.legend(fontsize=8)
    ax.set_xticks(years)
    ax.grid(alpha=0.3)

    # (b) CP Ceiling
    ax = axes[0, 1]
    for seed in SEEDS:
        ys = [cp_by_year_seed[seed][y] for y in years]
        ax.plot(years, ys, color=seed_colors[seed], alpha=0.4, linewidth=1,
                label=f"Seed {seed}")
    mean_cp = [np.nanmean([cp_by_year_seed[s][y] for s in SEEDS]) for y in years]
    ax.plot(years, mean_cp, color="black", linewidth=2.5, label="Mean")
    ax.axhline(y=3.0, color="red", linestyle="--", alpha=0.5, label="M ceiling")
    ax.set_xlabel("Year")
    ax.set_ylabel("Mean CP (1=VL ... 5=VH)")
    ax.set_title("(b) Coping Perception Ceiling")
    ax.legend(fontsize=8)
    ax.set_xticks(years)
    ax.grid(alpha=0.3)

    # (c) TP-CP Gap: MG vs NMG
    ax = axes[1, 0]
    for gname, style in [("MG", "-"), ("NMG", "--")]:
        for seed in SEEDS:
            ys = [gap_data[gname][seed].get(y, np.nan) for y in years]
            ax.plot(years, ys, linestyle=style, color=seed_colors[seed],
                    alpha=0.3, linewidth=1)
        mean_gap = [np.nanmean([gap_data[gname][s].get(y, np.nan) for s in SEEDS])
                    for y in years]
        ax.plot(years, mean_gap, linestyle=style, color="black", linewidth=2.5,
                label=f"{gname} (mean)")
    ax.axhline(y=0, color="gray", linestyle=":", alpha=0.5)
    ax.set_xlabel("Year")
    ax.set_ylabel("TP - CP gap")
    ax.set_title("(c) TP-CP Gap: MG vs NMG")
    ax.legend(fontsize=8)
    ax.set_xticks(years)
    ax.grid(alpha=0.3)

    # (d) Action Exhaustion
    ax = axes[1, 1]
    for seed in SEEDS:
        ys = [exhaust_by_seed[seed][y] for y in years]
        ax.plot(years, ys, color=seed_colors[seed], alpha=0.4, linewidth=1,
                label=f"Seed {seed}")
    mean_ex = [np.nanmean([exhaust_by_seed[s][y] for s in SEEDS]) for y in years]
    ax.plot(years, mean_ex, color="black", linewidth=2.5, label="Mean")
    ax.set_xlabel("Year")
    ax.set_ylabel("% choosing do_nothing")
    ax.set_title("(d) Action Exhaustion (previously adaptive agents)")
    ax.legend(fontsize=8)
    ax.set_xticks(years)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    outpath = FIG_DIR / "rq3_fig1_pmt_dynamics_4panel.png"
    fig.savefig(outpath, dpi=200, bbox_inches="tight")
    plt.close(fig)
    safe_print(f"\n  Saved: {outpath}")


def plot_figure2(heatmap, tp_labels, cp_labels):
    """Figure 2: PMT x Action heatmap."""
    fig, ax = plt.subplots(figsize=(6, 5))
    cmap = LinearSegmentedColormap.from_list("rg", ["#FFFFFF", "#4CAF50", "#1B5E20"])
    im = ax.imshow(heatmap, cmap=cmap, aspect="auto", vmin=0, vmax=100)

    ax.set_xticks(range(len(cp_labels)))
    ax.set_xticklabels([f"CP={c}" for c in cp_labels])
    ax.set_yticks(range(len(tp_labels)))
    ax.set_yticklabels([f"TP={t}" for t in tp_labels])
    ax.set_title("Protective Action Rate (%) by TP x CP")

    for i in range(len(tp_labels)):
        for j in range(len(cp_labels)):
            val = heatmap[i, j]
            color = "white" if val > 60 else "black"
            ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                    fontsize=14, fontweight="bold", color=color)

    fig.colorbar(im, ax=ax, label="Protective action rate (%)")
    plt.tight_layout()
    outpath = FIG_DIR / "rq3_fig2_pmt_action_heatmap.png"
    fig.savefig(outpath, dpi=200, bbox_inches="tight")
    plt.close(fig)
    safe_print(f"  Saved: {outpath}")


def plot_figure3(decay_bins):
    """Figure 3: TP decay curve."""
    fig, ax = plt.subplots(figsize=(7, 5))
    keys = [0, 1, 2, 3, "4+"]
    means = []
    stds = []
    for k in keys:
        vals = decay_bins[k]
        means.append(np.mean(vals) if vals else np.nan)
        stds.append(np.std(vals) / np.sqrt(len(vals)) if len(vals) > 1 else 0)

    x = range(len(keys))
    ax.errorbar(x, means, yerr=stds, marker="o", linewidth=2.5, capsize=5,
                color="#E91E63", markersize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([str(k) for k in keys])
    ax.set_xlabel("Years since last flood")
    ax.set_ylabel("Mean TP (1=VL ... 5=VH)")
    ax.set_title("TP Decay After Flood Event")

    # Annotate decay %
    if means[0] and means[0] > 0:
        for i, k in enumerate(keys):
            if i > 0 and not np.isnan(means[i]):
                decay = (means[0] - means[i]) / means[0] * 100
                ax.annotate(f"-{decay:.1f}%", (i, means[i]),
                            textcoords="offset points", xytext=(10, 5),
                            fontsize=9, color="#880E4F")

    ax.grid(alpha=0.3)
    plt.tight_layout()
    outpath = FIG_DIR / "rq3_fig3_tp_decay.png"
    fig.savefig(outpath, dpi=200, bbox_inches="tight")
    plt.close(fig)
    safe_print(f"  Saved: {outpath}")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    safe_print(f"  Saved table: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    safe_print("RQ3: PMT Construct Dynamics Analysis")
    safe_print("=" * 60)

    profiles = load_profiles()
    safe_print(f"Loaded {len(profiles)} agent profiles")

    safe_print("\nLoading traces ...")
    traces = load_all_traces()

    safe_print("\nComputing cumulative flood counts ...")
    traces = compute_cumulative_floods(traces)

    safe_print("Computing prior adaptive flags ...")
    traces = compute_prior_adaptive(traces)

    # Run sections
    tp_by_year_seed, years = section1_tp_accumulation(traces)
    decay_bins = section2_tp_decay(traces)
    cp_by_year_seed, _ = section3_cp_ceiling(traces, profiles)
    gap_data, _ = section4_tp_cp_gap(traces)
    exhaust_by_seed, _ = section5_action_exhaustion(traces)
    heatmap, tp_labels, cp_labels = section6_pmt_action_heatmap(traces)

    # Figures
    safe_print("\n" + "=" * 60)
    safe_print("Generating figures ...")
    safe_print("=" * 60)
    plot_figure1(tp_by_year_seed, cp_by_year_seed, gap_data, exhaust_by_seed, years)
    plot_figure2(heatmap, tp_labels, cp_labels)
    plot_figure3(decay_bins)

    safe_print("\n" + "=" * 60)
    safe_print("DONE. All tables and figures saved.")
    safe_print("=" * 60)


if __name__ == "__main__":
    main()
