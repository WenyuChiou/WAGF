"""
RQ3 Analysis: Dynamic Feedback Loops Between Psychological Constructs and Adaptation Actions
===============================================================================================
Key questions:
  1. Does action at time t change constructs at time t+1?
  2. Do constructs at time t predict action at t+1?
  3. Are there identifiable positive/negative feedback loops?

Data: governance audit CSVs pooled across 3 seeds (42, 123, 456).
Executed action: proposed_skill if APPROVED, else do_nothing.
Construct labels mapped: VL=1, L=2, M=3, H=4, VH=5.
"""

import os
import warnings
import pandas as pd
import numpy as np
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/results/paper3_hybrid_v2"
PROFILE_PATH = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/data/agent_initialization_complete.csv"
OUT_DIR = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/multi_agent/flood/paper3/analysis/tables"
os.makedirs(OUT_DIR, exist_ok=True)

SEEDS = ["seed_42", "seed_123", "seed_456"]
LABEL_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}
CONSTRUCTS = ["construct_TP_LABEL", "construct_CP_LABEL", "construct_SP_LABEL",
              "construct_SC_LABEL", "construct_PA_LABEL"]

# ── Load & clean ───────────────────────────────────────────────────────────
def load_audit(seed, agent_type):
    path = f"{BASE}/{seed}/gemma3_4b_strict/household_{agent_type}_governance_audit.csv"
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["seed"] = seed
    df["agent_type"] = agent_type
    return df

frames = []
for seed in SEEDS:
    for atype in ["owner", "renter"]:
        try:
            frames.append(load_audit(seed, atype))
        except FileNotFoundError:
            print(f"  WARNING: missing {seed}/{atype}")
df = pd.concat(frames, ignore_index=True)

# Map construct labels to numeric
for c in CONSTRUCTS:
    df[c + "_num"] = df[c].map(LABEL_MAP)

# Executed action: APPROVED → proposed_skill, REJECTED → do_nothing
df["executed_action"] = np.where(df["status"] == "APPROVED", df["proposed_skill"], "do_nothing")

# Unique agent key (seed + agent_id)
df["uid"] = df["seed"] + "_" + df["agent_id"]

# Sort for lag computation
df = df.sort_values(["uid", "year"]).reset_index(drop=True)

# Load profiles for tenure info
profiles = pd.read_csv(PROFILE_PATH)

# Classify protective vs non-protective
PROTECTIVE_ACTIONS = [
    "buy_insurance", "buy_contents_insurance",
    "elevate_house",
    "relocate",
    "buyout_program",
]

df["is_protective"] = df["executed_action"].isin(PROTECTIVE_ACTIONS)

# ── Create lagged columns ──────────────────────────────────────────────────
# For each agent, add t+1 constructs and t+1 action
for c in CONSTRUCTS:
    col = c + "_num"
    df[col + "_next"] = df.groupby("uid")[col].shift(-1)
    df[col + "_delta"] = df[col + "_next"] - df[col]

df["action_next"] = df.groupby("uid")["executed_action"].shift(-1)
df["is_protective_next"] = df.groupby("uid")["is_protective"].shift(-1)

# Short names for readability
df["SP"] = df["construct_SP_LABEL_num"]
df["SP_next"] = df["construct_SP_LABEL_num_next"]
df["SP_delta"] = df["construct_SP_LABEL_num_delta"]
df["PA"] = df["construct_PA_LABEL_num"]
df["PA_next"] = df["construct_PA_LABEL_num_next"]
df["PA_delta"] = df["construct_PA_LABEL_num_delta"]
df["TP"] = df["construct_TP_LABEL_num"]
df["TP_next"] = df["construct_TP_LABEL_num_next"]
df["TP_delta"] = df["construct_TP_LABEL_num_delta"]

# ── Helper ─────────────────────────────────────────────────────────────────
results_rows = []

def paired_test(group_a, group_b, label_a, label_b, metric_name):
    """Wilcoxon signed-rank or Mann-Whitney for unpaired groups."""
    a = group_a.dropna()
    b = group_b.dropna()
    n_a, n_b = len(a), len(b)
    if n_a < 3 or n_b < 3:
        return {"metric": metric_name, "group_a": label_a, "group_b": label_b,
                "mean_a": a.mean() if n_a else np.nan, "mean_b": b.mean() if n_b else np.nan,
                "n_a": n_a, "n_b": n_b, "test": "insufficient_n", "p_value": np.nan}
    stat, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"metric": metric_name, "group_a": label_a, "group_b": label_b,
            "mean_a": a.mean(), "mean_b": b.mean(), "median_a": a.median(), "median_b": b.median(),
            "n_a": n_a, "n_b": n_b, "test": "Mann-Whitney U", "U_stat": stat, "p_value": p}

def one_sample_test(values, label, metric_name):
    """Wilcoxon signed-rank test for delta != 0."""
    v = values.dropna()
    n = len(v)
    non_zero = v[v != 0]
    if len(non_zero) < 3:
        return {"metric": metric_name, "group": label,
                "mean": v.mean() if n else np.nan, "n": n,
                "test": "insufficient_non_zero", "p_value": np.nan}
    stat, p = stats.wilcoxon(non_zero)
    return {"metric": metric_name, "group": label,
            "mean": v.mean(), "median": v.median(), "n": n,
            "test": "Wilcoxon signed-rank", "W_stat": stat, "p_value": p}

separator = "=" * 80

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 1: Action → Construct Change
# ══════════════════════════════════════════════════════════════════════════════
print(separator)
print("ANALYSIS 1: ACTION at t → CONSTRUCT CHANGE at t+1")
print(separator)

# 1a) SP after insurance purchase vs do_nothing
print("\n--- 1a) SP change after insurance purchase vs do_nothing ---")
insurance_actions = ["buy_insurance", "buy_contents_insurance"]
mask_ins = df["executed_action"].isin(insurance_actions) & df["SP_delta"].notna()
mask_dn = (df["executed_action"] == "do_nothing") & df["SP_delta"].notna()

sp_after_ins = df.loc[mask_ins, "SP_delta"]
sp_after_dn = df.loc[mask_dn, "SP_delta"]

r = paired_test(sp_after_ins, sp_after_dn, "insurance", "do_nothing", "1a_SP_delta_insurance_vs_donothing")
results_rows.append(r)
print(f"  Insurance buyers: N={len(sp_after_ins)}, mean ΔSP={sp_after_ins.mean():.3f}, median={sp_after_ins.median():.1f}")
print(f"  Do-nothing:       N={len(sp_after_dn)}, mean ΔSP={sp_after_dn.mean():.3f}, median={sp_after_dn.median():.1f}")
print(f"  Mann-Whitney p={r['p_value']:.4f}" if not np.isnan(r.get('p_value', np.nan)) else "  Insufficient data")

# Also: within-agent SP level after insurance vs after do_nothing
print("\n  SP level at t+1:")
sp_next_ins = df.loc[mask_ins, "SP_next"].dropna()
sp_next_dn = df.loc[mask_dn, "SP_next"].dropna()
print(f"    After insurance: mean SP(t+1)={sp_next_ins.mean():.2f}, N={len(sp_next_ins)}")
print(f"    After do_nothing: mean SP(t+1)={sp_next_dn.mean():.2f}, N={len(sp_next_dn)}")

# 1b) SP after REJECTION vs APPROVAL (institutional betrayal)
print("\n--- 1b) SP change after REJECTION vs APPROVAL ---")
mask_rej = (df["status"] == "REJECTED") & df["SP_delta"].notna()
mask_app = (df["status"] == "APPROVED") & df["SP_delta"].notna()

sp_after_rej = df.loc[mask_rej, "SP_delta"]
sp_after_app = df.loc[mask_app, "SP_delta"]

r = paired_test(sp_after_rej, sp_after_app, "rejected", "approved", "1b_SP_delta_rejected_vs_approved")
results_rows.append(r)
print(f"  Rejected: N={len(sp_after_rej)}, mean ΔSP={sp_after_rej.mean():.3f}, median={sp_after_rej.median():.1f}")
print(f"  Approved: N={len(sp_after_app)}, mean ΔSP={sp_after_app.mean():.3f}, median={sp_after_app.median():.1f}")
print(f"  Mann-Whitney p={r['p_value']:.4f}" if not np.isnan(r.get('p_value', np.nan)) else "  Insufficient data")

# SP level at t+1
sp_next_rej = df.loc[mask_rej, "SP_next"].dropna()
sp_next_app = df.loc[mask_app, "SP_next"].dropna()
print(f"  SP(t+1) after rejection: mean={sp_next_rej.mean():.2f}, N={len(sp_next_rej)}")
print(f"  SP(t+1) after approval: mean={sp_next_app.mean():.2f}, N={len(sp_next_app)}")

# 1c) PA after relocation (renters) vs do_nothing
print("\n--- 1c) PA change after relocation attempt (renters) ---")
renter_mask = df["agent_type"] == "renter"
reloc_actions = ["relocate"]
mask_reloc = renter_mask & df["executed_action"].isin(reloc_actions) & df["PA_delta"].notna()
mask_renter_dn = renter_mask & (df["executed_action"] == "do_nothing") & df["PA_delta"].notna()

pa_after_reloc = df.loc[mask_reloc, "PA_delta"]
pa_after_renter_dn = df.loc[mask_renter_dn, "PA_delta"]

r = paired_test(pa_after_reloc, pa_after_renter_dn, "relocate", "do_nothing", "1c_PA_delta_renter_relocate_vs_donothing")
results_rows.append(r)
print(f"  Relocated renters: N={len(pa_after_reloc)}, mean ΔPA={pa_after_reloc.mean():.3f}" if len(pa_after_reloc) > 0 else "  Relocated renters: N=0")
print(f"  Do-nothing renters: N={len(pa_after_renter_dn)}, mean ΔPA={pa_after_renter_dn.mean():.3f}" if len(pa_after_renter_dn) > 0 else "  Do-nothing renters: N=0")
if not np.isnan(r.get('p_value', np.nan)):
    print(f"  Mann-Whitney p={r['p_value']:.4f}")

# PA trajectory for renters who stay
print("\n  PA trajectory for renters by consecutive years of do_nothing:")
renter_df = df[renter_mask].copy()
# Count consecutive do_nothing streaks
renter_df = renter_df.sort_values(["uid", "year"])
renter_df["is_dn"] = renter_df["executed_action"] == "do_nothing"
# Group consecutive do_nothing
renter_df["dn_group"] = (~renter_df["is_dn"]).groupby(renter_df["uid"]).cumsum()
renter_df["dn_streak"] = renter_df.groupby(["uid", "dn_group"]).cumcount() + 1
renter_df.loc[~renter_df["is_dn"], "dn_streak"] = 0

for streak_yr in [1, 2, 3, 4, 5]:
    subset = renter_df[renter_df["dn_streak"] == streak_yr]
    if len(subset) > 0:
        pa_vals = subset["PA"].dropna()
        print(f"    Year {streak_yr} of do_nothing streak: mean PA={pa_vals.mean():.2f}, N={len(pa_vals)}")

# 1d) PA after flooding (use TP as proxy: TP >= H means flooded)
print("\n--- 1d) PA change after high TP (proxy for flooding) ---")
mask_flooded = (df["TP"] >= 4) & df["PA_delta"].notna()  # H or VH
mask_not_flooded = (df["TP"] < 4) & df["PA_delta"].notna()

pa_after_flood = df.loc[mask_flooded, "PA_delta"]
pa_after_no_flood = df.loc[mask_not_flooded, "PA_delta"]

r = paired_test(pa_after_flood, pa_after_no_flood, "TP>=H(flooded)", "TP<H(not_flooded)", "1d_PA_delta_flooded_vs_not")
results_rows.append(r)
print(f"  TP>=H (flooded proxy): N={len(pa_after_flood)}, mean ΔPA={pa_after_flood.mean():.3f}")
print(f"  TP<H  (not flooded):   N={len(pa_after_no_flood)}, mean ΔPA={pa_after_no_flood.mean():.3f}")
if not np.isnan(r.get('p_value', np.nan)):
    print(f"  Mann-Whitney p={r['p_value']:.4f}")

# Also check TP → PA cross-construct effect
print("\n  Cross-construct: TP level vs PA(t+1)")
for tp_level in [2, 3, 4, 5]:
    subset = df[df["TP"] == tp_level]
    pa_next = subset["PA_next"].dropna()
    if len(pa_next) > 0:
        tp_label = {1: "VL", 2: "L", 3: "M", 4: "H", 5: "VH"}[tp_level]
        print(f"    TP={tp_label}: mean PA(t+1)={pa_next.mean():.2f}, N={len(pa_next)}")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 2: Construct → Action Transition
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{separator}")
print("ANALYSIS 2: CONSTRUCT at t → ACTION at t+1")
print(separator)

# 2a) SP at t → action at t+1
print("\n--- 2a) SP at t → protective action at t+1 ---")
sp_action = df[df["is_protective_next"].notna()].copy()
print(f"  {'SP(t)':<8} {'N':>6} {'% protective at t+1':>20} {'mean SP':>10}")
for sp_level in sorted(sp_action["SP"].dropna().unique()):
    if np.isnan(sp_level):
        continue
    subset = sp_action[sp_action["SP"] == sp_level]
    n = len(subset)
    pct = subset["is_protective_next"].mean() * 100
    sp_label = {1: "VL", 2: "L", 3: "M", 4: "H", 5: "VH"}.get(sp_level, "?")
    print(f"  {sp_label:<8} {n:>6} {pct:>19.1f}% {sp_level:>10.0f}")

# Chi-squared test: SP_high vs SP_low → protective action
sp_high = sp_action[sp_action["SP"] >= 4]["is_protective_next"].dropna()
sp_low = sp_action[sp_action["SP"] <= 2]["is_protective_next"].dropna()
if len(sp_high) > 5 and len(sp_low) > 5:
    ct = pd.crosstab(
        pd.Series(np.where(sp_action["SP"] >= 4, "SP_high", np.where(sp_action["SP"] <= 2, "SP_low", "mid")),
                  index=sp_action.index),
        sp_action["is_protective_next"]
    )
    ct = ct.loc[["SP_high", "SP_low"]]
    chi2, p_chi, dof, _ = stats.chi2_contingency(ct)
    print(f"\n  Chi-squared (SP_high vs SP_low → protective): chi2={chi2:.2f}, p={p_chi:.4f}")
    results_rows.append({"metric": "2a_SP_to_protective_action", "test": "chi2",
                         "pct_protective_SP_high": sp_high.mean()*100, "pct_protective_SP_low": sp_low.mean()*100,
                         "n_high": len(sp_high), "n_low": len(sp_low), "chi2": chi2, "p_value": p_chi})

# 2b) PA at t → relocation at t+1 (renters)
print("\n--- 2b) PA at t → relocation at t+1 (renters) ---")
renter_action = df[(df["agent_type"] == "renter") & df["action_next"].notna()].copy()
renter_action["relocate_next"] = renter_action["action_next"].isin(reloc_actions)

print(f"  {'PA(t)':<8} {'N':>6} {'% relocate at t+1':>20}")
for pa_level in sorted(renter_action["PA"].dropna().unique()):
    if np.isnan(pa_level):
        continue
    subset = renter_action[renter_action["PA"] == pa_level]
    n = len(subset)
    pct = subset["relocate_next"].mean() * 100
    pa_label = {1: "VL", 2: "L", 3: "M", 4: "H", 5: "VH"}.get(pa_level, "?")
    print(f"  {pa_label:<8} {n:>6} {pct:>19.1f}%")

# Test
pa_high = renter_action[renter_action["PA"] >= 4]["relocate_next"].dropna()
pa_low = renter_action[renter_action["PA"] <= 2]["relocate_next"].dropna()
if len(pa_high) > 5 and len(pa_low) > 5:
    ct = pd.crosstab(
        pd.Series(np.where(renter_action["PA"] >= 4, "PA_high",
                          np.where(renter_action["PA"] <= 2, "PA_low", "mid")),
                  index=renter_action.index),
        renter_action["relocate_next"]
    )
    ct = ct.loc[ct.index.isin(["PA_high", "PA_low"])]
    if ct.shape == (2, 2):
        chi2, p_chi, dof, _ = stats.chi2_contingency(ct)
        print(f"\n  Chi-squared (PA_high vs PA_low → relocate): chi2={chi2:.2f}, p={p_chi:.4f}")
        results_rows.append({"metric": "2b_PA_to_relocation", "test": "chi2",
                             "pct_relocate_PA_high": pa_high.mean()*100, "pct_relocate_PA_low": pa_low.mean()*100,
                             "n_high": len(pa_high), "n_low": len(pa_low), "chi2": chi2, "p_value": p_chi})
    else:
        print(f"\n  Crosstab not 2x2, skipping chi2. Shape: {ct.shape}")
        # Try Fisher exact if available
        results_rows.append({"metric": "2b_PA_to_relocation", "test": "insufficient_variance",
                             "pct_relocate_PA_high": pa_high.mean()*100, "pct_relocate_PA_low": pa_low.mean()*100,
                             "n_high": len(pa_high), "n_low": len(pa_low), "p_value": np.nan})

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 3: Full Feedback Loop Detection
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{separator}")
print("ANALYSIS 3: FEEDBACK LOOP DETECTION")
print(separator)

# Create lagged action
df["action_next2"] = df.groupby("uid")["executed_action"].shift(-1)

# 3a) Positive feedback: insurance → SP increases → insurance again
print("\n--- 3a) Positive feedback: insurance → SP↑ → insurance again ---")
ins_mask = df["executed_action"].isin(insurance_actions)
ins_rows = df[ins_mask & df["SP_delta"].notna() & df["action_next"].notna()].copy()

# Agent buys insurance, SP goes up, buys insurance again next year
pos_loop = ins_rows[
    (ins_rows["SP_delta"] > 0) &
    (ins_rows["action_next"].isin(insurance_actions))
]
# Agent buys insurance, SP goes up, does NOT buy again
pos_no_repeat = ins_rows[
    (ins_rows["SP_delta"] > 0) &
    (~ins_rows["action_next"].isin(insurance_actions))
]
# Agent buys insurance, SP doesn't go up
no_sp_increase = ins_rows[ins_rows["SP_delta"] <= 0]

n_total_ins = len(ins_rows)
n_pos_loop = len(pos_loop)
n_pos_no_repeat = len(pos_no_repeat)
n_no_sp_inc = len(no_sp_increase)

print(f"  Total insurance purchases (with next-year data): {n_total_ins}")
print(f"  Insurance → SP↑ → insurance again: {n_pos_loop} ({n_pos_loop/max(n_total_ins,1)*100:.1f}%)")
print(f"  Insurance → SP↑ → other action:    {n_pos_no_repeat} ({n_pos_no_repeat/max(n_total_ins,1)*100:.1f}%)")
print(f"  Insurance -> SP<=0:                  {n_no_sp_inc} ({n_no_sp_inc/max(n_total_ins,1)*100:.1f}%)")

# Unique agents in positive loop
pos_loop_agents = pos_loop["uid"].nunique()
print(f"  Unique agents showing positive loop: {pos_loop_agents}")

results_rows.append({"metric": "3a_positive_feedback_loop",
                      "n_loop": n_pos_loop, "n_total": n_total_ins,
                      "pct": n_pos_loop/max(n_total_ins,1)*100,
                      "unique_agents": pos_loop_agents})

# 3b) Negative feedback: rejected → SP decreases → stops trying
print("\n--- 3b) Negative feedback: rejection → SP↓ → stops trying ---")
rej_rows = df[(df["status"] == "REJECTED") & df["SP_delta"].notna() & df["action_next"].notna()].copy()

neg_loop = rej_rows[
    (rej_rows["SP_delta"] < 0) &
    (rej_rows["action_next"] == "do_nothing")
]
neg_no_quit = rej_rows[
    (rej_rows["SP_delta"] < 0) &
    (rej_rows["action_next"] != "do_nothing")
]
rej_sp_no_drop = rej_rows[rej_rows["SP_delta"] >= 0]

n_total_rej = len(rej_rows)
n_neg_loop = len(neg_loop)

print(f"  Total rejections (with next-year data): {n_total_rej}")
print(f"  Rejected → SP↓ → do_nothing:  {n_neg_loop} ({n_neg_loop/max(n_total_rej,1)*100:.1f}%)")
print(f"  Rejected → SP↓ → tries again: {len(neg_no_quit)} ({len(neg_no_quit)/max(n_total_rej,1)*100:.1f}%)")
print(f"  Rejected → SP≥0:              {len(rej_sp_no_drop)} ({len(rej_sp_no_drop)/max(n_total_rej,1)*100:.1f}%)")

neg_loop_agents = neg_loop["uid"].nunique()
print(f"  Unique agents showing negative loop: {neg_loop_agents}")

results_rows.append({"metric": "3b_negative_feedback_loop",
                      "n_loop": n_neg_loop, "n_total": n_total_rej,
                      "pct": n_neg_loop/max(n_total_rej,1)*100,
                      "unique_agents": neg_loop_agents})

# 3c) Erosion loop: do_nothing 3+ years → PA decreases over time
print("\n--- 3c) Erosion loop: consecutive do_nothing → PA trajectory ---")
# Use renter_df computed earlier (with dn_streak)
renter_df_pa = renter_df[renter_df["PA"].notna()].copy()

# For agents with 3+ consecutive do_nothing, track PA over the streak
long_streaks = renter_df_pa[renter_df_pa["dn_streak"] >= 3]
streak_groups = long_streaks.groupby("uid")

erosion_agents = 0
stable_agents = 0
increase_agents = 0

for uid, grp in streak_groups:
    if len(grp) < 3:
        continue
    pa_vals = grp.sort_values("year")["PA"].values
    # Compare first and last PA in streak
    if pa_vals[-1] < pa_vals[0]:
        erosion_agents += 1
    elif pa_vals[-1] == pa_vals[0]:
        stable_agents += 1
    else:
        increase_agents += 1

total_long = erosion_agents + stable_agents + increase_agents
print(f"  Renters with 3+ consecutive do_nothing years: {total_long}")
print(f"    PA decreased (erosion): {erosion_agents} ({erosion_agents/max(total_long,1)*100:.1f}%)")
print(f"    PA stable:              {stable_agents} ({stable_agents/max(total_long,1)*100:.1f}%)")
print(f"    PA increased:           {increase_agents} ({increase_agents/max(total_long,1)*100:.1f}%)")

results_rows.append({"metric": "3c_erosion_loop",
                      "n_erosion": erosion_agents, "n_stable": stable_agents,
                      "n_increase": increase_agents, "n_total": total_long})

# Also do this for ALL agents (owners + renters)
print("\n  All agents with 3+ consecutive do_nothing (PA trajectory):")
all_df = df.copy().sort_values(["uid", "year"])
all_df["is_dn"] = all_df["executed_action"] == "do_nothing"
all_df["dn_group"] = (~all_df["is_dn"]).groupby(all_df["uid"]).cumsum()
all_df["dn_streak"] = all_df.groupby(["uid", "dn_group"]).cumcount() + 1
all_df.loc[~all_df["is_dn"], "dn_streak"] = 0

long_all = all_df[(all_df["dn_streak"] >= 3) & all_df["PA"].notna()]
e, s, i = 0, 0, 0
for uid, grp in long_all.groupby("uid"):
    if len(grp) < 3:
        continue
    pa_vals = grp.sort_values("year")["PA"].values
    if pa_vals[-1] < pa_vals[0]:
        e += 1
    elif pa_vals[-1] == pa_vals[0]:
        s += 1
    else:
        i += 1
total_all = e + s + i
print(f"  Total agents: {total_all}")
print(f"    PA decreased: {e} ({e/max(total_all,1)*100:.1f}%)")
print(f"    PA stable:    {s} ({s/max(total_all,1)*100:.1f}%)")
print(f"    PA increased: {i} ({i/max(total_all,1)*100:.1f}%)")

# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS 4: Transition Matrix
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{separator}")
print("ANALYSIS 4: ACTION → CONSTRUCT CHANGE TRANSITION MATRIX")
print(separator)

actions_of_interest = ["buy_insurance", "buy_contents_insurance",
                       "elevate_house", "relocate",
                       "buyout_program", "do_nothing"]

print(f"\n{'Action':<30} {'N':>5} {'mean ΔSP':>9} {'med ΔSP':>8} {'p(SP)':>8} {'mean ΔPA':>9} {'med ΔPA':>8} {'p(PA)':>8}")
print("-" * 95)

for action in actions_of_interest:
    mask = df["executed_action"] == action
    sp_d = df.loc[mask, "SP_delta"].dropna()
    pa_d = df.loc[mask, "PA_delta"].dropna()

    n = len(sp_d)
    if n < 3:
        continue

    sp_mean = sp_d.mean()
    sp_med = sp_d.median()
    pa_mean = pa_d.mean()
    pa_med = pa_d.median()

    # Wilcoxon on SP delta
    sp_nz = sp_d[sp_d != 0]
    if len(sp_nz) >= 3:
        _, p_sp = stats.wilcoxon(sp_nz)
    else:
        p_sp = np.nan

    # Wilcoxon on PA delta
    pa_nz = pa_d[pa_d != 0]
    if len(pa_nz) >= 3:
        _, p_pa = stats.wilcoxon(pa_nz)
    else:
        p_pa = np.nan

    p_sp_str = f"{p_sp:.4f}" if not np.isnan(p_sp) else "   n/a"
    p_pa_str = f"{p_pa:.4f}" if not np.isnan(p_pa) else "   n/a"

    print(f"  {action:<28} {n:>5} {sp_mean:>+9.3f} {sp_med:>+8.1f} {p_sp_str:>8} {pa_mean:>+9.3f} {pa_med:>+8.1f} {p_pa_str:>8}")

    results_rows.append({
        "metric": f"4_transition_{action}", "n": n,
        "mean_SP_delta": sp_mean, "median_SP_delta": sp_med, "p_SP": p_sp,
        "mean_PA_delta": pa_mean, "median_PA_delta": pa_med, "p_PA": p_pa
    })

# Also by approval status
print(f"\n{'Status':<30} {'N':>5} {'mean ΔSP':>9} {'med ΔSP':>8} {'p(SP)':>8} {'mean ΔPA':>9} {'med ΔPA':>8} {'p(PA)':>8}")
print("-" * 95)
for status_val in ["APPROVED", "REJECTED"]:
    mask = df["status"] == status_val
    sp_d = df.loc[mask, "SP_delta"].dropna()
    pa_d = df.loc[mask, "PA_delta"].dropna()
    n = len(sp_d)
    if n < 3:
        continue
    sp_mean, sp_med = sp_d.mean(), sp_d.median()
    pa_mean, pa_med = pa_d.mean(), pa_d.median()
    sp_nz = sp_d[sp_d != 0]
    pa_nz = pa_d[pa_d != 0]
    p_sp = stats.wilcoxon(sp_nz)[1] if len(sp_nz) >= 3 else np.nan
    p_pa = stats.wilcoxon(pa_nz)[1] if len(pa_nz) >= 3 else np.nan
    p_sp_str = f"{p_sp:.4f}" if not np.isnan(p_sp) else "   n/a"
    p_pa_str = f"{p_pa:.4f}" if not np.isnan(p_pa) else "   n/a"
    print(f"  {status_val:<28} {n:>5} {sp_mean:>+9.3f} {sp_med:>+8.1f} {p_sp_str:>8} {pa_mean:>+9.3f} {pa_med:>+8.1f} {p_pa_str:>8}")

# ══════════════════════════════════════════════════════════════════════════════
# Additional: TP and CP in the transition matrix
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{separator}")
print("SUPPLEMENTARY: ALL CONSTRUCT DELTAS BY ACTION")
print(separator)

construct_short = {"construct_TP_LABEL_num_delta": "ΔTP",
                   "construct_CP_LABEL_num_delta": "ΔCP",
                   "construct_SP_LABEL_num_delta": "ΔSP",
                   "construct_SC_LABEL_num_delta": "ΔSC",
                   "construct_PA_LABEL_num_delta": "ΔPA"}

header = f"{'Action':<28} {'N':>5}"
for short in construct_short.values():
    header += f" {short:>8}"
print(header)
print("-" * 80)

for action in actions_of_interest:
    mask = df["executed_action"] == action
    n = mask.sum()
    if n < 5:
        continue
    row = f"  {action:<26} {n:>5}"
    for col, short in construct_short.items():
        vals = df.loc[mask, col].dropna()
        if len(vals) > 0:
            row += f" {vals.mean():>+8.3f}"
        else:
            row += f" {'n/a':>8}"
    print(row)

# ══════════════════════════════════════════════════════════════════════════════
# Summary statistics
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{separator}")
print("DATA SUMMARY")
print(separator)
print(f"  Total observations: {len(df)}")
print(f"  Unique agents: {df['uid'].nunique()}")
print(f"  Seeds: {df['seed'].nunique()}")
print(f"  Years: {sorted(df['year'].unique())}")
print(f"  Agent types: owners={len(df[df['agent_type']=='owner'])}, renters={len(df[df['agent_type']=='renter'])}")
print(f"  Status: APPROVED={len(df[df['status']=='APPROVED'])}, REJECTED={len(df[df['status']=='REJECTED'])}")
print(f"\n  Action distribution (executed):")
print(df["executed_action"].value_counts().to_string())
print(f"\n  Construct completeness (non-null rates):")
for c in CONSTRUCTS:
    pct = df[c + "_num"].notna().mean() * 100
    print(f"    {c}: {pct:.1f}%")

# ── Save results ───────────────────────────────────────────────────────────
results_df = pd.DataFrame(results_rows)
out_path = os.path.join(OUT_DIR, "rq3_construct_action_feedback.csv")
results_df.to_csv(out_path, index=False)
print(f"\n  Results saved to: {out_path}")
print(f"\n{'=' * 80}")
print("ANALYSIS COMPLETE")
print(f"{'=' * 80}")
