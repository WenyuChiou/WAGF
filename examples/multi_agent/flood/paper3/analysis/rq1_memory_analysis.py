#!/usr/bin/env python3
"""
RQ1 Analysis: How does flood memory affect within-group adaptation divergence?

Paper 3 - Flood ABM governed broker framework
Analyzes:
  1. Decision trajectories by flood exposure (flooded_ever vs never_flooded x MG vs NMG)
  2. Within-group heterogeneity (Shannon entropy, CoV of adaptation rates)
  3. Threat Perception (TP) decay post-flood (exponential fit)
  4. Statistical tests (Chi-squared, Mann-Whitney U, Kruskal-Wallis)
"""

import json
import csv
import os
import sys
import warnings
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from scipy import stats
from scipy.optimize import curve_fit

# ============================================================
# PATHS
# ============================================================
BASE = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
RESULT_DIR = BASE / "examples" / "multi_agent" / "flood" / "paper3" / "results" / "paper3_primary" / "seed_42" / "gemma3_4b_strict"
RAW_DIR = RESULT_DIR / "raw"

OWNER_TRACES = RAW_DIR / "household_owner_traces.jsonl"
RENTER_TRACES = RAW_DIR / "household_renter_traces.jsonl"
OWNER_AUDIT = RESULT_DIR / "household_owner_governance_audit.csv"
RENTER_AUDIT = RESULT_DIR / "household_renter_governance_audit.csv"
PROFILES = BASE / "examples" / "multi_agent" / "flood" / "data" / "agent_profiles_balanced.csv"

OUT_DIR = RESULT_DIR.parent / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Map TP labels to numeric
TP_MAP = {"L": 1, "M": 2, "H": 3}

# Canonical skill order for consistent plotting
OWNER_SKILLS = ["buy_insurance", "elevate_house", "buyout_program", "do_nothing"]
RENTER_SKILLS = ["buy_contents_insurance", "relocate", "do_nothing"]

# ============================================================
# 1. LOAD DATA
# ============================================================
print("=" * 72)
print("RQ1 ANALYSIS: FLOOD MEMORY & WITHIN-GROUP HETEROGENEITY")
print("=" * 72)


def load_profiles():
    """Load agent profiles, return dict agent_id -> {mg, tenure, ...}."""
    profiles = {}
    with open(PROFILES, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = row["agent_id"]
            profiles[aid] = {
                "mg": row["mg"].strip().lower() == "true",
                "tenure": row["tenure"].strip(),
                "income": float(row["income"]) if row["income"] else 0,
                "flood_zone": row["flood_zone"].strip(),
                "flood_experience": row["flood_experience"].strip().lower() == "true",
            }
    return profiles


def load_traces(path):
    """Load JSONL traces, return list of dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def load_audit(path):
    """Load governance audit CSV, return list of dicts."""
    rows = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


print("\n[1] Loading data...")
profiles = load_profiles()
owner_traces = load_traces(OWNER_TRACES)
renter_traces = load_traces(RENTER_TRACES)
owner_audit = load_audit(OWNER_AUDIT)
renter_audit = load_audit(RENTER_AUDIT)

all_traces = owner_traces + renter_traces
all_audit = owner_audit + renter_audit

n_owners = len(set(t["agent_id"] for t in owner_traces))
n_renters = len(set(t["agent_id"] for t in renter_traces))
years = sorted(set(t["year"] for t in all_traces))
print(f"  Owners : {n_owners} agents, {len(owner_traces)} trace records")
print(f"  Renters: {n_renters} agents, {len(renter_traces)} trace records")
print(f"  Years  : {years[0]}-{years[-1]} ({len(years)} years)")
print(f"  Profiles loaded: {len(profiles)}")

# ============================================================
# 2. FLOOD EXPOSURE TRACKING
# ============================================================
print("\n[2] Flood exposure tracking...")

# Build: agent_id -> set of years flooded
flood_years_map = defaultdict(set)  # agent_id -> {year, ...}
agent_year_flood = {}  # (agent_id, year) -> bool

for t in all_traces:
    aid = t["agent_id"]
    yr = t["year"]
    sa = t.get("state_after", {})
    flooded = bool(sa.get("flooded_this_year", False))
    agent_year_flood[(aid, yr)] = flooded
    if flooded:
        flood_years_map[aid].add(yr)

# Classify agents
all_agents = sorted(set(t["agent_id"] for t in all_traces))
flooded_ever = {a for a in all_agents if len(flood_years_map[a]) > 0}
never_flooded = {a for a in all_agents if a not in flooded_ever}

print(f"  Total agents: {len(all_agents)}")
print(f"  Flooded ever: {len(flooded_ever)}")
print(f"  Never flooded: {len(never_flooded)}")

# Flood events by year (aggregate)
print("\n  Flood events by year:")
for yr in years:
    n_flooded = sum(1 for a in all_agents if agent_year_flood.get((a, yr), False))
    print(f"    Year {yr:2d}: {n_flooded:3d}/{len(all_agents)} agents flooded "
          f"({100 * n_flooded / len(all_agents):.1f}%)")

# ============================================================
# 3. DECISION TRAJECTORY BY FLOOD EXPOSURE
# ============================================================
print("\n[3] Decision trajectories by flood exposure x demographic group...")

# Build cell labels: flood_status x demographic
# Cells: MG-O (MG Owner), MG-R (MG Renter), NMG-O, NMG-R
# Crossed with: flooded_ever vs never_flooded
def get_cell(agent_id):
    p = profiles.get(agent_id, {})
    mg = "MG" if p.get("mg", False) else "NMG"
    tenure = "O" if p.get("tenure", "Owner") == "Owner" else "R"
    return f"{mg}-{tenure}"


def get_flood_group(agent_id):
    return "Flooded" if agent_id in flooded_ever else "Never"


# Get the FINAL decision for each agent-year (approved or last proposed)
def get_decision(trace):
    """Return the effective decision skill name."""
    ask = trace.get("approved_skill")
    if ask and isinstance(ask, dict) and ask.get("skill_name"):
        return ask["skill_name"]
    sp = trace.get("skill_proposal")
    if sp and isinstance(sp, dict) and sp.get("skill_name"):
        return sp["skill_name"]
    return "do_nothing"


# Build decision matrix: (cell, flood_group, year) -> Counter of decisions
decision_counts = defaultdict(Counter)  # (cell, flood_group, year) -> Counter
agent_decisions = {}  # (agent_id, year) -> skill_name

for t in all_traces:
    aid = t["agent_id"]
    yr = t["year"]
    decision = get_decision(t)
    cell = get_cell(aid)
    fg = get_flood_group(aid)
    decision_counts[(cell, fg, yr)][decision] += 1
    agent_decisions[(aid, yr)] = decision

cells = ["MG-O", "MG-R", "NMG-O", "NMG-R"]
flood_groups = ["Flooded", "Never"]

# Print decision distributions
for cell in cells:
    print(f"\n  --- {cell} ---")
    for fg in flood_groups:
        agents_in = [a for a in all_agents if get_cell(a) == cell and get_flood_group(a) == fg]
        print(f"  [{fg}] n={len(agents_in)}")
        for yr in years:
            c = decision_counts.get((cell, fg, yr), Counter())
            total = sum(c.values())
            if total == 0:
                continue
            parts = []
            all_skills = OWNER_SKILLS if "O" in cell else RENTER_SKILLS
            for s in all_skills:
                pct = 100 * c.get(s, 0) / total
                if pct > 0:
                    parts.append(f"{s}={pct:.0f}%")
            print(f"    Y{yr:2d}: {' | '.join(parts)}  (n={total})")

# ============================================================
# 3a. ADOPTION RATE OVER TIME (figure)
# ============================================================
print("\n  Generating adoption rate figures...")

# Owner adaptation = buy_insurance OR elevate_house OR buyout_program (anything except do_nothing)
def is_adaptation(decision, tenure):
    if tenure == "Owner":
        return decision in ("buy_insurance", "elevate_house", "buyout_program")
    else:
        return decision in ("buy_contents_insurance", "relocate")


# Build adaptation rates per cell x flood_group x year
adaptation_rate = {}  # (cell, fg, yr) -> rate
for cell in cells:
    tenure = "Owner" if "O" in cell else "Renter"
    for fg in flood_groups:
        agents_in = [a for a in all_agents if get_cell(a) == cell and get_flood_group(a) == fg]
        for yr in years:
            n_adapt = sum(1 for a in agents_in
                         if is_adaptation(agent_decisions.get((a, yr), "do_nothing"), tenure))
            n_total = sum(1 for a in agents_in if (a, yr) in agent_decisions)
            if n_total > 0:
                adaptation_rate[(cell, fg, yr)] = n_adapt / n_total
            else:
                adaptation_rate[(cell, fg, yr)] = np.nan

# Figure: 2x2 grid (MG-O, MG-R, NMG-O, NMG-R), flooded vs never lines
fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True)
fig.suptitle("RQ1: Adaptation Rate by Flood Exposure & Demographic Group", fontsize=14, fontweight="bold")

for idx, cell in enumerate(cells):
    ax = axes[idx // 2][idx % 2]
    for fg, color, ls in [("Flooded", "#d62728", "-"), ("Never", "#1f77b4", "--")]:
        rates = [adaptation_rate.get((cell, fg, yr), np.nan) for yr in years]
        ax.plot(years, rates, marker="o", color=color, linestyle=ls, linewidth=2, label=fg, markersize=5)
    ax.set_title(cell, fontsize=12, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Adaptation Rate")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.set_ylim(-0.05, 1.05)
    ax.set_xticks(years)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(OUT_DIR / "rq1_adaptation_rate_by_group.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print(f"  Saved: {OUT_DIR / 'rq1_adaptation_rate_by_group.png'}")

# ============================================================
# 4. WITHIN-GROUP HETEROGENEITY
# ============================================================
print("\n[4] Within-group heterogeneity analysis...")


def shannon_entropy(counter):
    """Compute Shannon entropy (base 2) from a Counter."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in counter.values() if c > 0]
    return -sum(p * np.log2(p) for p in probs)


# 4a. Shannon entropy per group per year
entropy_results = {}  # (cell, fg, yr) -> entropy
print("\n  Shannon Entropy of Decisions (bits):")
print(f"  {'Cell':<8} {'FloodGrp':<10} " + " ".join([f"Y{yr:2d}" for yr in years]))
for cell in cells:
    for fg in flood_groups:
        row_parts = []
        for yr in years:
            c = decision_counts.get((cell, fg, yr), Counter())
            e = shannon_entropy(c)
            entropy_results[(cell, fg, yr)] = e
            row_parts.append(f"{e:4.2f}")
        print(f"  {cell:<8} {fg:<10} " + "  ".join(row_parts))

# Figure: entropy over time
fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharey=True)
fig.suptitle("RQ1: Decision Entropy (Within-Group Heterogeneity) Over Time",
             fontsize=14, fontweight="bold")

for idx, cell in enumerate(cells):
    ax = axes[idx // 2][idx % 2]
    for fg, color, ls in [("Flooded", "#d62728", "-"), ("Never", "#1f77b4", "--")]:
        ent = [entropy_results.get((cell, fg, yr), 0) for yr in years]
        ax.plot(years, ent, marker="s", color=color, linestyle=ls, linewidth=2, label=fg, markersize=5)
    ax.set_title(cell, fontsize=12, fontweight="bold")
    ax.set_xlabel("Year")
    ax.set_ylabel("Shannon Entropy (bits)")
    ax.set_xticks(years)
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

plt.tight_layout()
fig.savefig(OUT_DIR / "rq1_entropy_by_group.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print(f"\n  Saved: {OUT_DIR / 'rq1_entropy_by_group.png'}")

# 4b. Coefficient of Variation of adaptation rates WITHIN groups
print("\n  Coefficient of Variation (CoV) of per-agent adaptation frequency:")
cov_results = {}
for cell in cells:
    tenure = "Owner" if "O" in cell else "Renter"
    for fg in flood_groups:
        agents_in = [a for a in all_agents if get_cell(a) == cell and get_flood_group(a) == fg]
        if not agents_in:
            continue
        # Per-agent: fraction of years with adaptation decision
        agent_adapt_fracs = []
        for a in agents_in:
            n_adapt = sum(1 for yr in years
                         if is_adaptation(agent_decisions.get((a, yr), "do_nothing"), tenure))
            n_total = sum(1 for yr in years if (a, yr) in agent_decisions)
            if n_total > 0:
                agent_adapt_fracs.append(n_adapt / n_total)
        arr = np.array(agent_adapt_fracs)
        mean_val = np.mean(arr)
        std_val = np.std(arr)
        cov = std_val / mean_val if mean_val > 0 else np.nan
        cov_results[(cell, fg)] = cov
        print(f"  {cell:<8} {fg:<10}: mean={mean_val:.3f}, std={std_val:.3f}, "
              f"CoV={cov:.3f}, n={len(agents_in)}")

# 4c. Compare flooded vs non-flooded within same cell
print("\n  Entropy difference (Flooded - Never) by cell and year:")
for cell in cells:
    diffs = []
    for yr in years:
        e_f = entropy_results.get((cell, "Flooded", yr), 0)
        e_n = entropy_results.get((cell, "Never", yr), 0)
        diffs.append(e_f - e_n)
    mean_diff = np.mean(diffs)
    print(f"  {cell:<8}: mean diff = {mean_diff:+.3f} bits  "
          f"(+ve = flooded more heterogeneous)")

# ============================================================
# 5. THREAT PERCEPTION (TP) DECAY ANALYSIS
# ============================================================
print("\n[5] Threat Perception decay analysis...")

# Build TP records from audit CSVs (more reliable parsing)
tp_records = []  # list of (agent_id, year, tp_numeric, cell, years_since_last_flood)
for audit_row in all_audit:
    aid = audit_row.get("agent_id", "")
    yr_str = audit_row.get("year", "0")
    try:
        yr = int(yr_str)
    except ValueError:
        continue
    tp_label = audit_row.get("construct_TP_LABEL", "").strip().upper()
    if tp_label not in TP_MAP:
        continue
    tp_num = TP_MAP[tp_label]
    cell = get_cell(aid)
    # Compute years since last flood for this agent at this year
    flood_yrs = flood_years_map.get(aid, set())
    past_floods = [fy for fy in flood_yrs if fy <= yr]
    if past_floods:
        years_since = yr - max(past_floods)
    else:
        years_since = None  # never flooded up to this year
    tp_records.append({
        "agent_id": aid,
        "year": yr,
        "tp": tp_num,
        "tp_label": tp_label,
        "cell": cell,
        "years_since": years_since,
    })

print(f"  Total TP records: {len(tp_records)}")
print(f"  With flood history (years_since != None): "
      f"{sum(1 for r in tp_records if r['years_since'] is not None)}")

# 5a. Mean TP by years-since-last-flood (for agents who have been flooded)
tp_by_since = defaultdict(list)
for r in tp_records:
    if r["years_since"] is not None and r["years_since"] >= 0:
        tp_by_since[r["years_since"]].append(r["tp"])

print("\n  Mean TP by years since last flood:")
max_since = max(tp_by_since.keys()) if tp_by_since else 0
for t in range(min(max_since + 1, 15)):
    vals = tp_by_since.get(t, [])
    if vals:
        print(f"    t={t:2d}: mean={np.mean(vals):.3f}, std={np.std(vals):.3f}, n={len(vals)}")

# 5b. Exponential decay fit: TP(t) = TP_0 * exp(-lambda * t)
def exp_decay(t, tp0, lam):
    return tp0 * np.exp(-lam * t)


# Fit on aggregated data
t_values = []
tp_means = []
for t in sorted(tp_by_since.keys()):
    if len(tp_by_since[t]) >= 5:  # require minimum sample
        t_values.append(t)
        tp_means.append(np.mean(tp_by_since[t]))

print("\n  Exponential decay fit (all agents with flood history):")
if len(t_values) >= 3:
    try:
        popt, pcov = curve_fit(exp_decay, np.array(t_values), np.array(tp_means),
                               p0=[3.0, 0.1], maxfev=5000,
                               bounds=([0.5, 0.0], [3.5, 2.0]))
        tp0_fit, lam_fit = popt
        perr = np.sqrt(np.diag(pcov))
        # R-squared
        residuals = np.array(tp_means) - exp_decay(np.array(t_values), *popt)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((np.array(tp_means) - np.mean(tp_means)) ** 2)
        r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
        print(f"    TP(t) = {tp0_fit:.3f} * exp(-{lam_fit:.4f} * t)")
        print(f"    TP_0 = {tp0_fit:.3f} +/- {perr[0]:.3f}")
        print(f"    lambda = {lam_fit:.4f} +/- {perr[1]:.4f}")
        print(f"    R^2 = {r_sq:.4f}")
        print(f"    Half-life = {np.log(2) / lam_fit:.1f} years" if lam_fit > 0 else "    No decay")
    except Exception as e:
        print(f"    Fit failed: {e}")
        tp0_fit, lam_fit, r_sq = None, None, None
else:
    print("    Insufficient data for fitting")
    tp0_fit, lam_fit, r_sq = None, None, None

# 5c. Decay by demographic group (MG vs NMG, and by cell)
print("\n  TP decay by demographic group (MG vs NMG):")
for mg_label in ["MG", "NMG"]:
    tp_by_since_grp = defaultdict(list)
    for r in tp_records:
        if r["years_since"] is not None and r["years_since"] >= 0:
            cell_mg = r["cell"].split("-")[0]
            if cell_mg == mg_label:
                tp_by_since_grp[r["years_since"]].append(r["tp"])

    t_vals_g = []
    tp_means_g = []
    for t in sorted(tp_by_since_grp.keys()):
        if len(tp_by_since_grp[t]) >= 3:
            t_vals_g.append(t)
            tp_means_g.append(np.mean(tp_by_since_grp[t]))

    if len(t_vals_g) >= 3:
        try:
            popt_g, pcov_g = curve_fit(exp_decay, np.array(t_vals_g), np.array(tp_means_g),
                                       p0=[3.0, 0.1], maxfev=5000,
                                       bounds=([0.5, 0.0], [3.5, 2.0]))
            tp0_g, lam_g = popt_g
            perr_g = np.sqrt(np.diag(pcov_g))
            res_g = np.array(tp_means_g) - exp_decay(np.array(t_vals_g), *popt_g)
            ss_res_g = np.sum(res_g ** 2)
            ss_tot_g = np.sum((np.array(tp_means_g) - np.mean(tp_means_g)) ** 2)
            r_sq_g = 1 - ss_res_g / ss_tot_g if ss_tot_g > 0 else np.nan
            half_life_g = np.log(2) / lam_g if lam_g > 0 else float("inf")
            print(f"    {mg_label}: TP_0={tp0_g:.3f}, lambda={lam_g:.4f} +/- {perr_g[1]:.4f}, "
                  f"R^2={r_sq_g:.4f}, half-life={half_life_g:.1f}yr")
        except Exception as e:
            print(f"    {mg_label}: Fit failed: {e}")
    else:
        print(f"    {mg_label}: Insufficient data")

# 5d. TP decay figure
fig, ax = plt.subplots(1, 1, figsize=(10, 6))
ax.set_title("RQ1: Threat Perception Decay After Flood Event", fontsize=14, fontweight="bold")

# Plot raw data points
for t in sorted(tp_by_since.keys()):
    vals = tp_by_since[t]
    if vals:
        jitter = np.random.RandomState(42).normal(0, 0.08, len(vals))
        ax.scatter([t + j for j in jitter], vals, alpha=0.15, s=10, color="gray", zorder=1)

# Plot means
if t_values and tp_means:
    ax.plot(t_values, tp_means, "ko-", linewidth=2, markersize=8, label="Mean TP", zorder=3)

# Plot fit
if tp0_fit is not None and lam_fit is not None:
    t_smooth = np.linspace(0, max(t_values), 100)
    ax.plot(t_smooth, exp_decay(t_smooth, tp0_fit, lam_fit), "r--", linewidth=2,
            label=f"Fit: {tp0_fit:.2f}*exp(-{lam_fit:.3f}t), R$^2$={r_sq:.3f}", zorder=2)

ax.set_xlabel("Years Since Last Flood", fontsize=12)
ax.set_ylabel("Threat Perception Score (1=L, 2=M, 3=H)", fontsize=12)
ax.set_yticks([1, 2, 3])
ax.set_yticklabels(["Low", "Medium", "High"])
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(OUT_DIR / "rq1_tp_decay.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print(f"\n  Saved: {OUT_DIR / 'rq1_tp_decay.png'}")

# 5e. TP decay by MG vs NMG figure
fig, ax = plt.subplots(1, 1, figsize=(10, 6))
ax.set_title("RQ1: TP Decay by Marginalization Status (MG vs NMG)",
             fontsize=14, fontweight="bold")

for mg_label, color, marker in [("MG", "#d62728", "o"), ("NMG", "#1f77b4", "s")]:
    tp_by_since_grp = defaultdict(list)
    for r in tp_records:
        if r["years_since"] is not None and r["years_since"] >= 0:
            cell_mg = r["cell"].split("-")[0]
            if cell_mg == mg_label:
                tp_by_since_grp[r["years_since"]].append(r["tp"])

    t_vals_g = sorted(t for t in tp_by_since_grp if len(tp_by_since_grp[t]) >= 3)
    means_g = [np.mean(tp_by_since_grp[t]) for t in t_vals_g]

    if t_vals_g:
        ax.plot(t_vals_g, means_g, marker=marker, color=color, linewidth=2,
                markersize=7, label=f"{mg_label} (mean TP)")

    # Fit and overlay
    if len(t_vals_g) >= 3:
        try:
            popt_g, _ = curve_fit(exp_decay, np.array(t_vals_g), np.array(means_g),
                                  p0=[3.0, 0.1], maxfev=5000,
                                  bounds=([0.5, 0.0], [3.5, 2.0]))
            t_smooth = np.linspace(0, max(t_vals_g), 100)
            ax.plot(t_smooth, exp_decay(t_smooth, *popt_g), color=color, linestyle="--",
                    linewidth=1.5, alpha=0.7,
                    label=f"{mg_label} fit: lam={popt_g[1]:.4f}")
        except Exception:
            pass

ax.set_xlabel("Years Since Last Flood", fontsize=12)
ax.set_ylabel("Threat Perception Score", fontsize=12)
ax.set_yticks([1, 2, 3])
ax.set_yticklabels(["Low", "Medium", "High"])
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig(OUT_DIR / "rq1_tp_decay_mg_vs_nmg.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print(f"  Saved: {OUT_DIR / 'rq1_tp_decay_mg_vs_nmg.png'}")

# ============================================================
# 6. STATISTICAL TESTS
# ============================================================
print("\n[6] Statistical tests...")

# 6a. Chi-squared: decision distributions, flooded vs never (per cell)
print("\n  6a. Chi-squared test: decision distribution (Flooded vs Never)")
for cell in cells:
    all_skills = OWNER_SKILLS if "O" in cell else RENTER_SKILLS
    # Aggregate across all years
    flooded_counts = Counter()
    never_counts = Counter()
    for yr in years:
        for skill in all_skills:
            flooded_counts[skill] += decision_counts.get((cell, "Flooded", yr), Counter()).get(skill, 0)
            never_counts[skill] += decision_counts.get((cell, "Never", yr), Counter()).get(skill, 0)

    # Build contingency table
    table = []
    for skill in all_skills:
        table.append([flooded_counts[skill], never_counts[skill]])
    table = np.array(table)

    # Check if any row/col is all zeros
    if table.sum() == 0 or np.any(table.sum(axis=0) == 0):
        print(f"    {cell}: SKIPPED (empty cell)")
        continue

    chi2, p, dof, expected = stats.chi2_contingency(table)
    sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
    # Cramers V
    n = table.sum()
    k = min(table.shape)
    cramers_v = np.sqrt(chi2 / (n * (k - 1))) if n > 0 and k > 1 else 0
    print(f"    {cell}: chi2={chi2:.2f}, p={p:.4f} {sig}, dof={dof}, "
          f"Cramer's V={cramers_v:.3f}")
    # Print observed table
    print(f"      {'Skill':<25} {'Flooded':>8} {'Never':>8}")
    for i, skill in enumerate(all_skills):
        print(f"      {skill:<25} {table[i, 0]:8d} {table[i, 1]:8d}")

# 6b. Mann-Whitney U: TP scores by flood exposure
print("\n  6b. Mann-Whitney U: TP scores (Flooded vs Never)")
tp_flooded = [r["tp"] for r in tp_records if r["agent_id"] in flooded_ever]
tp_never = [r["tp"] for r in tp_records if r["agent_id"] in never_flooded]

if tp_flooded and tp_never:
    u_stat, p_mw = stats.mannwhitneyu(tp_flooded, tp_never, alternative="two-sided")
    r_rbc = 1 - (2 * u_stat) / (len(tp_flooded) * len(tp_never))  # rank-biserial
    sig = "***" if p_mw < 0.001 else "**" if p_mw < 0.01 else "*" if p_mw < 0.05 else "ns"
    print(f"    Flooded: mean={np.mean(tp_flooded):.3f}, n={len(tp_flooded)}")
    print(f"    Never:   mean={np.mean(tp_never):.3f}, n={len(tp_never)}")
    print(f"    U={u_stat:.0f}, p={p_mw:.6f} {sig}")
    print(f"    Rank-biserial r={r_rbc:.4f}")
else:
    print("    Insufficient data for Mann-Whitney U")

# Per-cell
print("\n    Per-cell Mann-Whitney U:")
for cell in cells:
    tp_f = [r["tp"] for r in tp_records if r["cell"] == cell and r["agent_id"] in flooded_ever]
    tp_n = [r["tp"] for r in tp_records if r["cell"] == cell and r["agent_id"] in never_flooded]
    if tp_f and tp_n:
        u, p_val = stats.mannwhitneyu(tp_f, tp_n, alternative="two-sided")
        sig = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else "ns"
        print(f"      {cell}: U={u:.0f}, p={p_val:.4f} {sig} "
              f"(flooded mean={np.mean(tp_f):.3f} n={len(tp_f)}, "
              f"never mean={np.mean(tp_n):.3f} n={len(tp_n)})")
    else:
        print(f"      {cell}: Insufficient data (flooded={len(tp_f) if tp_f else 0}, "
              f"never={len(tp_n) if tp_n else 0})")

# 6c. Kruskal-Wallis: TP across 4 cells
print("\n  6c. Kruskal-Wallis: TP scores across 4 demographic cells")
cell_tp_groups = []
cell_labels_for_kw = []
for cell in cells:
    vals = [r["tp"] for r in tp_records if r["cell"] == cell]
    if vals:
        cell_tp_groups.append(vals)
        cell_labels_for_kw.append(cell)
        print(f"    {cell}: mean={np.mean(vals):.3f}, median={np.median(vals):.1f}, n={len(vals)}")

if len(cell_tp_groups) >= 2:
    h_stat, p_kw = stats.kruskal(*cell_tp_groups)
    sig = "***" if p_kw < 0.001 else "**" if p_kw < 0.01 else "*" if p_kw < 0.05 else "ns"
    # Effect size: eta-squared
    n_total_kw = sum(len(g) for g in cell_tp_groups)
    eta_sq = (h_stat - len(cell_tp_groups) + 1) / (n_total_kw - len(cell_tp_groups))
    print(f"\n    H={h_stat:.2f}, p={p_kw:.6f} {sig}")
    print(f"    eta^2 = {eta_sq:.4f}")

# 6d. Kruskal-Wallis: TP across 8 cells (flood x demographic)
print("\n  6d. Kruskal-Wallis: TP across 8 cells (Flood x Demographic)")
groups_8 = []
labels_8 = []
for cell in cells:
    for fg in flood_groups:
        agents_fg = flooded_ever if fg == "Flooded" else never_flooded
        vals = [r["tp"] for r in tp_records if r["cell"] == cell and r["agent_id"] in agents_fg]
        if vals:
            groups_8.append(vals)
            labels_8.append(f"{cell}-{fg}")
            print(f"    {cell}-{fg}: mean={np.mean(vals):.3f}, n={len(vals)}")

if len(groups_8) >= 2:
    h_stat_8, p_kw_8 = stats.kruskal(*groups_8)
    sig = "***" if p_kw_8 < 0.001 else "**" if p_kw_8 < 0.01 else "*" if p_kw_8 < 0.05 else "ns"
    n_total_8 = sum(len(g) for g in groups_8)
    eta_sq_8 = (h_stat_8 - len(groups_8) + 1) / (n_total_8 - len(groups_8))
    print(f"\n    H={h_stat_8:.2f}, p={p_kw_8:.6f} {sig}")
    print(f"    eta^2 = {eta_sq_8:.4f}")

# ============================================================
# 7. SUMMARY FIGURE: Multi-panel
# ============================================================
print("\n[7] Generating summary multi-panel figure...")

fig, axes = plt.subplots(2, 3, figsize=(20, 12))
fig.suptitle("RQ1: Flood Memory & Within-Group Adaptation Divergence\n"
             "(Paper 3 — Flood ABM, seed 42, gemma3:4b-strict, 13 years)",
             fontsize=15, fontweight="bold")

# Panel A: Adaptation rate (MG owners)
ax = axes[0, 0]
ax.set_title("(a) Adaptation Rate — MG Owners", fontsize=11)
for fg, color, ls in [("Flooded", "#d62728", "-"), ("Never", "#1f77b4", "--")]:
    rates = [adaptation_rate.get(("MG-O", fg, yr), np.nan) for yr in years]
    ax.plot(years, rates, marker="o", color=color, linestyle=ls, linewidth=2, label=fg)
ax.set_xlabel("Year")
ax.set_ylabel("Adaptation Rate")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.legend()
ax.grid(True, alpha=0.3)

# Panel B: Adaptation rate (NMG owners)
ax = axes[0, 1]
ax.set_title("(b) Adaptation Rate — NMG Owners", fontsize=11)
for fg, color, ls in [("Flooded", "#d62728", "-"), ("Never", "#1f77b4", "--")]:
    rates = [adaptation_rate.get(("NMG-O", fg, yr), np.nan) for yr in years]
    ax.plot(years, rates, marker="o", color=color, linestyle=ls, linewidth=2, label=fg)
ax.set_xlabel("Year")
ax.set_ylabel("Adaptation Rate")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.legend()
ax.grid(True, alpha=0.3)

# Panel C: Entropy comparison (all owners)
ax = axes[0, 2]
ax.set_title("(c) Decision Entropy — Owners", fontsize=11)
for cell, color in [("MG-O", "#d62728"), ("NMG-O", "#1f77b4")]:
    for fg, ls, marker in [("Flooded", "-", "o"), ("Never", "--", "s")]:
        ent = [entropy_results.get((cell, fg, yr), 0) for yr in years]
        ax.plot(years, ent, marker=marker, color=color, linestyle=ls, linewidth=1.5,
                label=f"{cell} {fg}", markersize=4)
ax.set_xlabel("Year")
ax.set_ylabel("Shannon Entropy (bits)")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Panel D: Adaptation rate (renters)
ax = axes[1, 0]
ax.set_title("(d) Adaptation Rate — Renters", fontsize=11)
for cell, color in [("MG-R", "#d62728"), ("NMG-R", "#1f77b4")]:
    for fg, ls in [("Flooded", "-"), ("Never", "--")]:
        rates = [adaptation_rate.get((cell, fg, yr), np.nan) for yr in years]
        ax.plot(years, rates, marker="o", color=color, linestyle=ls, linewidth=1.5,
                label=f"{cell} {fg}", markersize=4)
ax.set_xlabel("Year")
ax.set_ylabel("Adaptation Rate")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0))
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Panel E: TP decay
ax = axes[1, 1]
ax.set_title("(e) TP Decay Post-Flood", fontsize=11)
for mg_label, color, marker in [("MG", "#d62728", "o"), ("NMG", "#1f77b4", "s")]:
    tp_by_since_grp = defaultdict(list)
    for r in tp_records:
        if r["years_since"] is not None and r["years_since"] >= 0:
            cell_mg = r["cell"].split("-")[0]
            if cell_mg == mg_label:
                tp_by_since_grp[r["years_since"]].append(r["tp"])
    t_vals = sorted(t for t in tp_by_since_grp if len(tp_by_since_grp[t]) >= 3)
    means = [np.mean(tp_by_since_grp[t]) for t in t_vals]
    if t_vals:
        ax.plot(t_vals, means, marker=marker, color=color, linewidth=2, markersize=6,
                label=f"{mg_label}")
ax.set_xlabel("Years Since Last Flood")
ax.set_ylabel("Mean TP Score")
ax.set_yticks([1, 2, 3])
ax.set_yticklabels(["Low", "Med", "High"])
ax.legend()
ax.grid(True, alpha=0.3)

# Panel F: CoV bar chart
ax = axes[1, 2]
ax.set_title("(f) CoV of Per-Agent Adaptation Rate", fontsize=11)
x_pos = []
x_labels = []
colors_bar = []
cov_vals = []
i = 0
for cell in cells:
    for fg in flood_groups:
        cv = cov_results.get((cell, fg), 0)
        x_pos.append(i)
        x_labels.append(f"{cell}\n{fg}")
        colors_bar.append("#d62728" if fg == "Flooded" else "#1f77b4")
        cov_vals.append(cv)
        i += 1

bars = ax.bar(x_pos, cov_vals, color=colors_bar, edgecolor="black", linewidth=0.5)
ax.set_xticks(x_pos)
ax.set_xticklabels(x_labels, fontsize=8)
ax.set_ylabel("Coefficient of Variation")
ax.grid(True, alpha=0.3, axis="y")
# Add value labels
for bar, val in zip(bars, cov_vals):
    if not np.isnan(val):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.2f}", ha="center", va="bottom", fontsize=8)

plt.tight_layout()
fig.savefig(OUT_DIR / "rq1_summary_multipanel.png", dpi=200, bbox_inches="tight")
plt.close(fig)
print(f"  Saved: {OUT_DIR / 'rq1_summary_multipanel.png'}")

# ============================================================
# 8. YEAR-OVER-YEAR TRANSITION ANALYSIS
# ============================================================
print("\n[8] Decision transition analysis (year-over-year)...")

# Build transition matrices per flood group
transitions = defaultdict(Counter)  # (flood_group, from_skill) -> Counter(to_skill)
for a in all_agents:
    fg = get_flood_group(a)
    for i in range(len(years) - 1):
        yr_from = years[i]
        yr_to = years[i + 1]
        d_from = agent_decisions.get((a, yr_from))
        d_to = agent_decisions.get((a, yr_to))
        if d_from and d_to:
            transitions[(fg, d_from)][d_to] += 1

print("\n  Transition probabilities (Flooded agents):")
all_skills_combined = sorted(set(OWNER_SKILLS + RENTER_SKILLS))
for from_s in all_skills_combined:
    total = sum(transitions[("Flooded", from_s)].values())
    if total == 0:
        continue
    probs = {to_s: transitions[("Flooded", from_s)][to_s] / total
             for to_s in all_skills_combined if transitions[("Flooded", from_s)][to_s] > 0}
    parts = [f"{s}={p:.0%}" for s, p in sorted(probs.items(), key=lambda x: -x[1])]
    print(f"    {from_s:>25} -> {', '.join(parts)}  (n={total})")

print("\n  Transition probabilities (Never-flooded agents):")
for from_s in all_skills_combined:
    total = sum(transitions[("Never", from_s)].values())
    if total == 0:
        continue
    probs = {to_s: transitions[("Never", from_s)][to_s] / total
             for to_s in all_skills_combined if transitions[("Never", from_s)][to_s] > 0}
    parts = [f"{s}={p:.0%}" for s, p in sorted(probs.items(), key=lambda x: -x[1])]
    print(f"    {from_s:>25} -> {', '.join(parts)}  (n={total})")

# Persistence rate (same decision as previous year)
print("\n  Decision persistence rate (same action as previous year):")
for fg in flood_groups:
    agents_fg = flooded_ever if fg == "Flooded" else never_flooded
    same_count = 0
    total_count = 0
    for a in agents_fg:
        for i in range(len(years) - 1):
            d1 = agent_decisions.get((a, years[i]))
            d2 = agent_decisions.get((a, years[i + 1]))
            if d1 and d2:
                total_count += 1
                if d1 == d2:
                    same_count += 1
    if total_count > 0:
        print(f"    {fg}: {same_count}/{total_count} = {same_count / total_count:.1%}")

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 72)
print("RQ1 ANALYSIS COMPLETE")
print("=" * 72)
print(f"\nOutput directory: {OUT_DIR}")
print("Figures saved:")
for f in sorted(OUT_DIR.glob("rq1_*.png")):
    print(f"  - {f.name}")
print(f"\nTotal agents: {len(all_agents)} ({n_owners} owners + {n_renters} renters)")
print(f"Years analyzed: {years[0]}-{years[-1]} ({len(years)} years)")
print(f"Flooded ever: {len(flooded_ever)} | Never flooded: {len(never_flooded)}")
print(f"Total trace records: {len(all_traces)}")
