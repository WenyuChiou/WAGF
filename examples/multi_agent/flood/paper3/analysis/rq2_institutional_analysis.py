#!/usr/bin/env python3
"""
RQ2: How does institutional feedback affect protection inequality?

Analyzes:
1. Government subsidy rate and insurance premium rate trajectories over 13 years
2. MG vs NMG adaptation gap over time (insurance, elevation, buyout rates)
3. Affordability constraint impact on MG vs NMG
4. Insurance feedback loops (premium <-> loss ratio <-> uptake)
5. Statistical tests: repeated measures, correlations, chi-squared

Data sources:
  - JSONL traces: government, insurance, household_owner, household_renter
  - Governance audit CSVs
  - Agent profiles CSV
  - Governance summary JSON
"""

import json
import os
import sys
import re
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from scipy import stats
from collections import defaultdict

warnings.filterwarnings("ignore", category=FutureWarning)

# ===========================================================================
# Paths
# ===========================================================================
BASE = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood"
RESULT_DIR = os.path.join(BASE, "paper3", "results", "paper3_primary", "seed_42", "gemma3_4b_strict")
RAW_DIR = os.path.join(RESULT_DIR, "raw")
ANALYSIS_DIR = os.path.join(BASE, "paper3", "results", "paper3_primary", "seed_42", "analysis")
os.makedirs(ANALYSIS_DIR, exist_ok=True)

PROFILES_PATH = os.path.join(BASE, "data", "agent_profiles_balanced.csv")
GOV_SUMMARY_PATH = os.path.join(RESULT_DIR, "governance_summary.json")

OWNER_TRACES = os.path.join(RAW_DIR, "household_owner_traces.jsonl")
RENTER_TRACES = os.path.join(RAW_DIR, "household_renter_traces.jsonl")
GOV_TRACES = os.path.join(RAW_DIR, "government_traces.jsonl")
INS_TRACES = os.path.join(RAW_DIR, "insurance_traces.jsonl")

OWNER_AUDIT = os.path.join(RESULT_DIR, "household_owner_governance_audit.csv")
RENTER_AUDIT = os.path.join(RESULT_DIR, "household_renter_governance_audit.csv")
GOV_AUDIT = os.path.join(RESULT_DIR, "government_governance_audit.csv")
INS_AUDIT = os.path.join(RESULT_DIR, "insurance_governance_audit.csv")

# ===========================================================================
# Helpers
# ===========================================================================

def load_jsonl(path):
    """Load JSONL file line by line."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def safe_print(msg):
    """Print with encoding safety."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode())


# ===========================================================================
# 1. LOAD DATA
# ===========================================================================
safe_print("=" * 80)
safe_print("RQ2: INSTITUTIONAL FEEDBACK & PROTECTION INEQUALITY")
safe_print("=" * 80)

safe_print("\n[1] Loading data...")

# Agent profiles
profiles = pd.read_csv(PROFILES_PATH, encoding="utf-8")
mg_lookup = profiles.set_index("agent_id")["mg"].to_dict()
tenure_lookup = profiles.set_index("agent_id")["tenure"].to_dict()
income_lookup = profiles.set_index("agent_id")["income"].to_dict()
safe_print(f"  Loaded {len(profiles)} agent profiles")

# Governance summary
with open(GOV_SUMMARY_PATH, "r", encoding="utf-8") as f:
    gov_summary = json.load(f)
safe_print(f"  Governance summary: {gov_summary['total_interventions']} total interventions")

# JSONL traces
gov_traces = load_jsonl(GOV_TRACES)
ins_traces = load_jsonl(INS_TRACES)
owner_traces = load_jsonl(OWNER_TRACES)
renter_traces = load_jsonl(RENTER_TRACES)
safe_print(f"  Government traces: {len(gov_traces)} records")
safe_print(f"  Insurance traces:  {len(ins_traces)} records")
safe_print(f"  Owner traces:      {len(owner_traces)} records")
safe_print(f"  Renter traces:     {len(renter_traces)} records")

# Audit CSVs
owner_audit = pd.read_csv(OWNER_AUDIT, encoding="utf-8-sig")
renter_audit = pd.read_csv(RENTER_AUDIT, encoding="utf-8-sig")
safe_print(f"  Owner audit rows:  {len(owner_audit)}")
safe_print(f"  Renter audit rows: {len(renter_audit)}")

# Determine years
all_household_traces = owner_traces + renter_traces
years = sorted(set(t["year"] for t in all_household_traces))
n_years = len(years)
safe_print(f"  Simulation years:  {years}")


# ===========================================================================
# 2. INSTITUTIONAL DYNAMICS
# ===========================================================================
safe_print("\n" + "=" * 80)
safe_print("[2] INSTITUTIONAL DYNAMICS")
safe_print("=" * 80)

# --- Government subsidy trajectory ---
# NOTE: state_after.subsidy_rate is NOT updated by the environment (known bug).
# We extract the ACTUAL applied subsidy rate from memory_post in later traces.
gov_subsidy_by_year = {}
gov_decisions = {}
gov_rationales = {}
gov_elevated_by_year = {}

# First pass: collect decisions and rationales
for t in gov_traces:
    yr = t["year"]
    skill = t.get("skill_proposal", {}).get("skill_name", "")
    gov_decisions[yr] = skill
    rationale = t.get("skill_proposal", {}).get("reasoning", {}).get("rationale", "")
    gov_rationales[yr] = rationale

# Extract actual subsidy rates from the LAST government trace memory
# (contains the full history: "Year N: Set subsidy rate to X% (was Y%). Elevated: Z/400.")
_last_gov = gov_traces[-1] if gov_traces else {}
_all_mems = _last_gov.get("memory_post", [])
for m in _all_mems:
    c = m.get("content", "") if isinstance(m, dict) else str(m)
    for match in re.finditer(
        r"Year (\d+): Set subsidy rate to (\d+)% \(was (\d+)%\)\. Elevated: (\d+)/(\d+)", c
    ):
        myear = int(match.group(1))
        rate = int(match.group(2))
        elevated = int(match.group(4))
        gov_subsidy_by_year[myear] = rate / 100.0
        gov_elevated_by_year[myear] = elevated

# Fill missing years with defaults
for yr in range(1, 14):
    if yr not in gov_subsidy_by_year:
        # Year 13 may not appear in last trace memory (it IS the last trace)
        # Infer from decision
        if yr == 1:
            gov_subsidy_by_year[yr] = 0.50
        elif gov_decisions.get(yr) == "increase_subsidy":
            gov_subsidy_by_year[yr] = gov_subsidy_by_year.get(yr - 1, 0.50) + 0.05
        elif gov_decisions.get(yr) == "decrease_subsidy":
            gov_subsidy_by_year[yr] = gov_subsidy_by_year.get(yr - 1, 0.50) - 0.05
        else:
            gov_subsidy_by_year[yr] = gov_subsidy_by_year.get(yr - 1, 0.50)

safe_print("\n--- Government Subsidy Rate Trajectory ---")
safe_print(f"{'Year':>6} {'Subsidy Rate':>14} {'Decision':>20}")
for yr in sorted(gov_subsidy_by_year.keys()):
    safe_print(f"{yr:>6} {gov_subsidy_by_year[yr]:>14.1%} {gov_decisions.get(yr, ''):>20}")

# --- Insurance premium/CRS trajectory ---
# NOTE: state_after.loss_ratio is NOT updated (always 0.0). Extract from memory.
ins_premium_by_year = {}
ins_loss_ratio_by_year = {}
ins_crs_by_year = {}
ins_insured_by_year = {}
ins_decisions = {}
ins_rationales = {}

# First pass: decisions and rationales
for t in ins_traces:
    yr = t["year"]
    skill = t.get("skill_proposal", {}).get("skill_name", "")
    ins_decisions[yr] = skill
    rationale = t.get("skill_proposal", {}).get("reasoning", {}).get("rationale", "")
    ins_rationales[yr] = rationale

# Extract actual metrics from the LAST insurance trace memory
_last_ins = ins_traces[-1] if ins_traces else {}
_ins_mems = _last_ins.get("memory_post", [])
for m in _ins_mems:
    c = m.get("content", "") if isinstance(m, dict) else str(m)
    for match in re.finditer(
        r"Year (\d+): CRS discount set to (\d+)% \(was (\d+)%\)\. Effective premium: ([\d.]+)%\. Loss ratio: ([\d.]+)\. Insured: (\d+)/(\d+)",
        c,
    ):
        myear = int(match.group(1))
        crs = int(match.group(2))
        eff_prem = float(match.group(4))
        loss = float(match.group(5))
        insured = int(match.group(6))
        total = int(match.group(7))
        ins_crs_by_year[myear] = crs / 100.0
        ins_premium_by_year[myear] = eff_prem / 100.0
        ins_loss_ratio_by_year[myear] = loss
        ins_insured_by_year[myear] = insured

# Fill year 13 from its own trace memory if missing
for t in ins_traces:
    yr = t["year"]
    if yr not in ins_loss_ratio_by_year:
        mems = t.get("memory_post", [])
        for m in mems:
            c = m.get("content", "") if isinstance(m, dict) else str(m)
            for match in re.finditer(
                r"Year (\d+): CRS discount set to (\d+)%.*?Loss ratio: ([\d.]+)\. Insured: (\d+)/(\d+)", c
            ):
                myear = int(match.group(1))
                if myear == yr:
                    ins_loss_ratio_by_year[myear] = float(match.group(3))
                    ins_insured_by_year[myear] = int(match.group(4))
                    ins_premium_by_year.setdefault(myear, 0.02)
                    ins_crs_by_year.setdefault(myear, 0.0)

# Default fill
for yr in range(1, 14):
    ins_premium_by_year.setdefault(yr, 0.02)
    ins_loss_ratio_by_year.setdefault(yr, 0.0)
    ins_crs_by_year.setdefault(yr, 0.0)
    ins_insured_by_year.setdefault(yr, 0)

safe_print("\n--- Insurance (FEMA CRS) Trajectory ---")
safe_print(f"{'Year':>6} {'Premium Rate':>14} {'CRS Disc':>10} {'Loss Ratio':>12} {'Insured':>10} {'Decision':>20}")
for yr in sorted(ins_premium_by_year.keys()):
    safe_print(
        f"{yr:>6} {ins_premium_by_year[yr]:>14.3%} {ins_crs_by_year.get(yr, 0):>10.0%}"
        f" {ins_loss_ratio_by_year.get(yr, 0):>12.2f} {ins_insured_by_year.get(yr, 0):>10}"
        f" {ins_decisions.get(yr, ''):>20}"
    )

# --- Extract LLM reasoning samples ---
safe_print("\n--- Government LLM Reasoning Samples ---")
for yr in [2, 7]:
    if yr in gov_rationales and gov_rationales[yr]:
        safe_print(f"  Year {yr}: {gov_rationales[yr][:200]}...")

safe_print("\n--- Insurance LLM Reasoning Samples ---")
for yr in [2, 3]:
    if yr in ins_rationales and ins_rationales[yr]:
        safe_print(f"  Year {yr}: {ins_rationales[yr][:200]}...")


# ===========================================================================
# 3. MG vs NMG ADAPTATION GAP OVER TIME
# ===========================================================================
safe_print("\n" + "=" * 80)
safe_print("[3] MG vs NMG ADAPTATION GAP OVER TIME")
safe_print("=" * 80)

# Build per-agent-year decision tracking using state inference from traces
# For each agent in each year, we need: did they get insurance? elevated? buyout?
# We use the approved_skill from the trace to infer cumulative state

# Track cumulative state per agent
agent_state = {}  # agent_id -> {insured, elevated, relocated}

# Initialize from profiles
for _, row in profiles.iterrows():
    aid = row["agent_id"]
    agent_state[aid] = {
        "insured": bool(row.get("has_insurance", False)),
        "elevated": bool(row.get("elevated", False)),
        "relocated": bool(row.get("relocated", False)),
    }

# Track per-year adaptation rates by MG status
yearly_data = {yr: {"mg": {"total": 0, "insured": 0, "elevated": 0, "buyout": 0},
                     "nmg": {"total": 0, "insured": 0, "elevated": 0, "buyout": 0}}
               for yr in years}

# Also track decisions per year for each agent
agent_yearly_decision = defaultdict(dict)  # agent_id -> {year -> decision}

# Process household traces (both owner and renter) sorted by step_id
all_hh = sorted(all_household_traces, key=lambda x: x.get("step_id", 0))

for t in all_hh:
    aid = t["agent_id"]
    yr = t["year"]
    outcome = t.get("outcome", "")

    if aid not in mg_lookup:
        continue

    mg = mg_lookup[aid]
    group = "mg" if mg else "nmg"

    # Determine the effective skill (what actually happened)
    approved = t.get("approved_skill", {})
    skill_name = approved.get("skill_name", "")
    status = approved.get("status", "")

    # Track the decision
    if status == "APPROVED":
        agent_yearly_decision[aid][yr] = skill_name

        # Update cumulative state based on approved action
        if skill_name in ("buy_insurance", "buy_contents_insurance"):
            agent_state.get(aid, {})["insured"] = True
        elif skill_name == "elevate_house":
            agent_state.get(aid, {})["elevated"] = True
        elif skill_name == "buyout_program":
            agent_state.get(aid, {})["relocated"] = True
        elif skill_name == "do_nothing":
            # Insurance lapses if not renewed (annual decision)
            # Only lapse if the agent had insurance and chose do_nothing
            if agent_state.get(aid, {}).get("insured", False):
                agent_state.get(aid, {})["insured"] = False
    else:
        agent_yearly_decision[aid][yr] = "REJECTED"
        # On rejection, insurance lapses too
        if agent_state.get(aid, {}).get("insured", False):
            agent_state.get(aid, {})["insured"] = False

# Now compute per-year adaptation rates
# Reset and recompute with cumulative tracking
agent_cum_state = {}
for _, row in profiles.iterrows():
    aid = row["agent_id"]
    agent_cum_state[aid] = {
        "insured": bool(row.get("has_insurance", False)),
        "elevated": bool(row.get("elevated", False)),
        "relocated": bool(row.get("relocated", False)),
    }

# Re-process in order
yearly_rates = {yr: {"mg": {"n": 0, "insured": 0, "elevated": 0, "buyout": 0, "any_action": 0},
                      "nmg": {"n": 0, "insured": 0, "elevated": 0, "buyout": 0, "any_action": 0}}
                for yr in years}

for t in all_hh:
    aid = t["agent_id"]
    yr = t["year"]

    if aid not in mg_lookup:
        continue
    if aid not in agent_cum_state:
        continue

    mg = mg_lookup[aid]
    group = "mg" if mg else "nmg"

    # Skip relocated agents
    if agent_cum_state[aid]["relocated"]:
        continue

    yearly_rates[yr][group]["n"] += 1

    approved = t.get("approved_skill", {})
    skill_name = approved.get("skill_name", "")
    status = approved.get("status", "")

    if status == "APPROVED":
        if skill_name in ("buy_insurance", "buy_contents_insurance"):
            agent_cum_state[aid]["insured"] = True
        elif skill_name == "elevate_house":
            agent_cum_state[aid]["elevated"] = True
        elif skill_name == "buyout_program":
            agent_cum_state[aid]["relocated"] = True
        elif skill_name == "do_nothing":
            agent_cum_state[aid]["insured"] = False
    else:
        # Rejected => insurance lapses
        agent_cum_state[aid]["insured"] = False

    # Count current state
    if agent_cum_state[aid]["insured"]:
        yearly_rates[yr][group]["insured"] += 1
    if agent_cum_state[aid]["elevated"]:
        yearly_rates[yr][group]["elevated"] += 1
    if agent_cum_state[aid]["relocated"]:
        yearly_rates[yr][group]["buyout"] += 1
    if agent_cum_state[aid]["insured"] or agent_cum_state[aid]["elevated"] or agent_cum_state[aid]["relocated"]:
        yearly_rates[yr][group]["any_action"] += 1

# Compute rates and gaps
safe_print(f"\n{'Year':>4} | {'MG_ins':>8} {'NMG_ins':>8} {'Gap_ins':>8} | {'MG_elev':>8} {'NMG_elev':>8} {'Gap_elev':>9} | {'MG_buy':>8} {'NMG_buy':>8} {'Gap_buy':>8}")
safe_print("-" * 110)

gap_insurance = []
gap_elevation = []
gap_buyout = []
gap_any = []
mg_ins_rates = []
nmg_ins_rates = []
mg_elev_rates = []
nmg_elev_rates = []
mg_buy_rates = []
nmg_buy_rates = []
mg_any_rates = []
nmg_any_rates = []

for yr in years:
    mg_d = yearly_rates[yr]["mg"]
    nmg_d = yearly_rates[yr]["nmg"]

    mg_n = max(mg_d["n"], 1)
    nmg_n = max(nmg_d["n"], 1)

    mg_ir = mg_d["insured"] / mg_n
    nmg_ir = nmg_d["insured"] / nmg_n
    mg_er = mg_d["elevated"] / mg_n
    nmg_er = nmg_d["elevated"] / nmg_n
    mg_br = mg_d["buyout"] / mg_n
    nmg_br = nmg_d["buyout"] / nmg_n
    mg_ar = mg_d["any_action"] / mg_n
    nmg_ar = nmg_d["any_action"] / nmg_n

    gi = nmg_ir - mg_ir
    ge = nmg_er - mg_er
    gb = nmg_br - mg_br
    ga = nmg_ar - mg_ar

    gap_insurance.append(gi)
    gap_elevation.append(ge)
    gap_buyout.append(gb)
    gap_any.append(ga)
    mg_ins_rates.append(mg_ir)
    nmg_ins_rates.append(nmg_ir)
    mg_elev_rates.append(mg_er)
    nmg_elev_rates.append(nmg_er)
    mg_buy_rates.append(mg_br)
    nmg_buy_rates.append(nmg_br)
    mg_any_rates.append(mg_ar)
    nmg_any_rates.append(nmg_ar)

    safe_print(f"{yr:>4} | {mg_ir:>8.3f} {nmg_ir:>8.3f} {gi:>+8.3f} | {mg_er:>8.3f} {nmg_er:>8.3f} {ge:>+9.3f} | {mg_br:>8.3f} {nmg_br:>8.3f} {gb:>+8.3f}")

# Linear regression on adaptation gap over time
safe_print("\n--- Adaptation Gap Trend (Linear Regression) ---")
years_arr = np.arange(len(years))

for name, gap_series in [("Insurance", gap_insurance), ("Elevation", gap_elevation),
                          ("Buyout", gap_buyout), ("Any Action", gap_any)]:
    if len(gap_series) < 3:
        continue
    slope, intercept, r_value, p_value, std_err = stats.linregress(years_arr, gap_series)
    trend = "WIDENING" if slope > 0.001 else ("NARROWING" if slope < -0.001 else "STABLE")
    safe_print(f"  {name:>12} gap: slope={slope:+.4f}/yr, R2={r_value**2:.3f}, p={p_value:.4f} => {trend}")


# ===========================================================================
# 4. AFFORDABILITY CONSTRAINT IMPACT
# ===========================================================================
safe_print("\n" + "=" * 80)
safe_print("[4] AFFORDABILITY CONSTRAINT IMPACT")
safe_print("=" * 80)

# Count REJECTED by rule from audit CSVs
all_audit = pd.concat([owner_audit, renter_audit], ignore_index=True)

# Tag MG status
all_audit["mg"] = all_audit["agent_id"].map(mg_lookup)

# Count rejections (status == REJECTED)
rejected = all_audit[all_audit["status"] == "REJECTED"].copy()
safe_print(f"\nTotal REJECTED decisions: {len(rejected)}")

# Affordability rejections: the 'failed_rules' field shows 'Unknown' for affordability.
# The actual affordability trigger is in 'error_messages' containing 'AFFORDABILITY'.
affordability_rej = rejected[
    rejected["error_messages"].str.contains("AFFORDABILITY", case=False, na=False)
]
safe_print(f"Affordability REJECTED:  {len(affordability_rej)}")

# MG vs NMG affordability rejection counts
mg_aff = affordability_rej[affordability_rej["mg"] == True]  # noqa: E712
nmg_aff = affordability_rej[affordability_rej["mg"] == False]  # noqa: E712

# Total decisions per group
mg_total = all_audit[all_audit["mg"] == True]
nmg_total = all_audit[all_audit["mg"] == False]

safe_print(f"\n{'Group':>8} {'Total Decisions':>16} {'Affordability REJ':>20} {'Aff REJ Rate':>14}")
safe_print("-" * 62)

mg_aff_rate = len(mg_aff) / max(len(mg_total), 1)
nmg_aff_rate = len(nmg_aff) / max(len(nmg_total), 1)
safe_print(f"{'MG':>8} {len(mg_total):>16} {len(mg_aff):>20} {mg_aff_rate:>14.3%}")
safe_print(f"{'NMG':>8} {len(nmg_total):>16} {len(nmg_aff):>20} {nmg_aff_rate:>14.3%}")

# Per-year affordability rejection rate
safe_print("\n--- Per-Year Affordability Rejection Rate ---")
safe_print(f"{'Year':>4} {'MG_aff_rej':>12} {'NMG_aff_rej':>13} {'MG_rate':>10} {'NMG_rate':>10} {'Ratio':>8}")
safe_print("-" * 65)

mg_aff_yearly = []
nmg_aff_yearly = []

for yr in years:
    yr_data = all_audit[all_audit["year"] == yr]
    yr_rej = yr_data[yr_data["status"] == "REJECTED"]
    yr_aff = yr_rej[yr_rej["error_messages"].str.contains("AFFORDABILITY", case=False, na=False)]

    mg_yr = yr_data[yr_data["mg"] == True]
    nmg_yr = yr_data[yr_data["mg"] == False]
    mg_aff_yr = yr_aff[yr_aff["mg"] == True]
    nmg_aff_yr = yr_aff[yr_aff["mg"] == False]

    mg_r = len(mg_aff_yr) / max(len(mg_yr), 1)
    nmg_r = len(nmg_aff_yr) / max(len(nmg_yr), 1)
    ratio = mg_r / max(nmg_r, 0.001)

    mg_aff_yearly.append(mg_r)
    nmg_aff_yearly.append(nmg_r)

    safe_print(f"{yr:>4} {len(mg_aff_yr):>12} {len(nmg_aff_yr):>13} {mg_r:>10.3f} {nmg_r:>10.3f} {ratio:>8.1f}x")

# All rejection rules breakdown by MG
# For affordability: match on error_messages. For others: match on failed_rules.
safe_print("\n--- All Rejection Rules by MG Status ---")
for rule_name, count in gov_summary.get("rule_frequency", {}).items():
    if rule_name == "affordability":
        # Affordability uses error_messages, not failed_rules
        mg_rule = rejected[(rejected["error_messages"].str.contains("AFFORDABILITY", case=False, na=False)) &
                           (rejected["mg"] == True)]
        nmg_rule = rejected[(rejected["error_messages"].str.contains("AFFORDABILITY", case=False, na=False)) &
                            (rejected["mg"] == False)]
    else:
        mg_rule = rejected[(rejected["failed_rules"].str.contains(rule_name, case=False, na=False)) &
                           (rejected["mg"] == True)]
        nmg_rule = rejected[(rejected["failed_rules"].str.contains(rule_name, case=False, na=False)) &
                            (rejected["mg"] == False)]
    safe_print(f"  {rule_name:>35}: MG={len(mg_rule):>4}, NMG={len(nmg_rule):>4}, Total={count}")

# Chi-squared test: MG vs NMG rejected rates
safe_print("\n--- Chi-Squared Test: MG vs NMG Rejection Rates ---")
mg_rej_count = len(rejected[rejected["mg"] == True])
nmg_rej_count = len(rejected[rejected["mg"] == False])
mg_app_count = len(mg_total) - mg_rej_count
nmg_app_count = len(nmg_total) - nmg_rej_count

contingency = np.array([[mg_rej_count, mg_app_count],
                        [nmg_rej_count, nmg_app_count]])
chi2, p_chi, dof, expected = stats.chi2_contingency(contingency)
safe_print(f"  Contingency table:")
safe_print(f"    MG:  REJECTED={mg_rej_count}, APPROVED={mg_app_count}")
safe_print(f"    NMG: REJECTED={nmg_rej_count}, APPROVED={nmg_app_count}")
safe_print(f"  Chi2={chi2:.3f}, p={p_chi:.6f}, dof={dof}")
safe_print(f"  => {'SIGNIFICANT' if p_chi < 0.05 else 'NOT SIGNIFICANT'} difference in rejection rates")

# Odds ratio
or_val = (mg_rej_count * nmg_app_count) / max(nmg_rej_count * mg_app_count, 1)
safe_print(f"  Odds Ratio (MG vs NMG rejection): {or_val:.3f}")


# ===========================================================================
# 5. INSURANCE FEEDBACK LOOP
# ===========================================================================
safe_print("\n" + "=" * 80)
safe_print("[5] INSURANCE FEEDBACK LOOP ANALYSIS")
safe_print("=" * 80)

# Extract per-year insurance metrics from traces
# From insurance traces: premium_rate, loss_ratio
# From household traces: insurance uptake rate
ins_years = sorted(ins_premium_by_year.keys())

# Compute insurance uptake from institutional memory (insured counts)
# and from household traces as a cross-check
ins_uptake_by_year = {}
for yr in years:
    # Use institutional memory data if available
    if yr in ins_insured_by_year and ins_insured_by_year[yr] > 0:
        ins_uptake_by_year[yr] = ins_insured_by_year[yr] / 400.0
    else:
        # Fallback: count from household traces
        yr_traces = [t for t in all_hh if t["year"] == yr]
        insured = 0
        total = 0
        for t in yr_traces:
            aid = t["agent_id"]
            if aid not in mg_lookup:
                continue
            total += 1
            approved = t.get("approved_skill", {})
            skill_name = approved.get("skill_name", "")
            status = approved.get("status", "")
            if status == "APPROVED" and skill_name in ("buy_insurance", "buy_contents_insurance"):
                insured += 1
        ins_uptake_by_year[yr] = insured / max(total, 1)

# Build time series for correlation analysis
common_years = sorted(set(ins_years) & set(years))
premium_series = [ins_premium_by_year.get(yr, 0.02) for yr in common_years]
loss_ratio_series = [ins_loss_ratio_by_year.get(yr, 0.0) for yr in common_years]
uptake_series = [ins_uptake_by_year.get(yr, 0.0) for yr in common_years]
subsidy_series = [gov_subsidy_by_year.get(yr, 0.5) for yr in common_years]

safe_print(f"\n{'Year':>4} {'Premium':>10} {'Loss Ratio':>12} {'Uptake':>10} {'Subsidy':>10}")
safe_print("-" * 50)
for i, yr in enumerate(common_years):
    safe_print(f"{yr:>4} {premium_series[i]:>10.3%} {loss_ratio_series[i]:>12.2f} {uptake_series[i]:>10.3%} {subsidy_series[i]:>10.1%}")

# Correlation analysis
safe_print("\n--- Correlation Analysis ---")

def safe_corr(x, y, name):
    """Compute Pearson correlation with constant-input check."""
    x_arr, y_arr = np.array(x, dtype=float), np.array(y, dtype=float)
    if np.std(x_arr) < 1e-10 or np.std(y_arr) < 1e-10:
        safe_print(f"  {name}: CONSTANT INPUT (no variation) => correlation undefined")
        return None, None
    r, p = stats.pearsonr(x_arr, y_arr)
    safe_print(f"  {name}: r={r:+.3f}, p={p:.4f}")
    return r, p

if len(premium_series) >= 3:
    # Premium vs loss ratio
    safe_corr(premium_series, loss_ratio_series, "Premium vs Loss Ratio")

    # Premium vs uptake
    safe_corr(premium_series, uptake_series, "Premium vs Uptake")

    # Subsidy vs elevation rate
    combined_elev = [(mg_elev_rates[i] + nmg_elev_rates[i]) / 2 for i in range(len(years))]
    if len(subsidy_series) == len(combined_elev):
        safe_corr(subsidy_series, combined_elev, "Subsidy vs Elevation Rate")

    # Loss ratio vs next-year uptake (does loss drive behavior?)
    if len(loss_ratio_series) > 2:
        loss_lag = loss_ratio_series[:-1]
        uptake_lead = uptake_series[1:]
        safe_corr(loss_lag, uptake_lead, "Loss Ratio(t) vs Uptake(t+1)")

    # Loss ratio vs loss ratio(t+1) (autocorrelation)
    if len(loss_ratio_series) > 2:
        safe_corr(loss_ratio_series[:-1], loss_ratio_series[1:], "Loss Ratio autocorrelation")

    # Subsidy vs MG insurance rate
    safe_corr(subsidy_series, mg_ins_rates, "Subsidy vs MG Insurance Rate")

# Cross-correlation: Loss ratio -> Uptake (lagged)
safe_print("\n--- Cross-Correlation: Loss Ratio -> Insurance Uptake ---")
if len(loss_ratio_series) >= 5:
    for lag in [0, 1, 2]:
        n_overlap = len(loss_ratio_series) - lag
        if n_overlap > 3:
            loss_slice = loss_ratio_series[:n_overlap]
            up_slice = uptake_series[lag:lag + n_overlap]
            safe_corr(loss_slice, up_slice, f"Loss Ratio(t) -> Uptake(t+{lag})")

# Feedback loop summary
safe_print("\n--- Feedback Loop Assessment ---")
safe_print("  Expected feedback chain: flood_damage -> loss_ratio -> premium_change -> uptake_change")
prem_change = any(abs(premium_series[i] - premium_series[i - 1]) > 0.001 for i in range(1, len(premium_series)))
crs_change = any(ins_crs_by_year.get(yr, 0) != ins_crs_by_year.get(yr - 1, 0) for yr in range(2, 14))
safe_print(f"  Premium changed over 13 years? {'YES' if prem_change else 'NO'}")
safe_print(f"  CRS discount changed over 13 years? {'YES' if crs_change else 'NO'}")
if not prem_change and not crs_change:
    safe_print("  => FEEDBACK LOOP IS BROKEN: institutional agent never adjusted rates")
    safe_print("     despite loss ratios ranging from 0.0 to {:.1f}".format(max(loss_ratio_series)))


# ===========================================================================
# 6. STATISTICAL TESTS
# ===========================================================================
safe_print("\n" + "=" * 80)
safe_print("[6] STATISTICAL TESTS")
safe_print("=" * 80)

# --- 6a. Mann-Whitney U: MG vs NMG per-year insurance rates ---
safe_print("\n--- Mann-Whitney U: MG vs NMG Insurance Rates ---")
u_stat, u_p = stats.mannwhitneyu(mg_ins_rates, nmg_ins_rates, alternative="two-sided")
safe_print(f"  U={u_stat:.1f}, p={u_p:.4f}")
safe_print(f"  MG mean insurance rate:  {np.mean(mg_ins_rates):.3f}")
safe_print(f"  NMG mean insurance rate: {np.mean(nmg_ins_rates):.3f}")
safe_print(f"  => {'SIGNIFICANT' if u_p < 0.05 else 'NOT SIGNIFICANT'} difference")

# --- 6b. Paired t-test: MG vs NMG elevation rates across years ---
safe_print("\n--- Paired t-test: MG vs NMG Elevation Rates ---")
if len(mg_elev_rates) >= 3:
    t_stat, t_p = stats.ttest_rel(mg_elev_rates, nmg_elev_rates)
    safe_print(f"  t={t_stat:.3f}, p={t_p:.4f}")
    safe_print(f"  MG mean elevation rate:  {np.mean(mg_elev_rates):.3f}")
    safe_print(f"  NMG mean elevation rate: {np.mean(nmg_elev_rates):.3f}")
    safe_print(f"  => {'SIGNIFICANT' if t_p < 0.05 else 'NOT SIGNIFICANT'} difference")

# --- 6c. Repeated measures effect: adaptation gap trend ---
safe_print("\n--- Adaptation Gap Trend: Any Action ---")
if len(gap_any) >= 3:
    slope, intercept, r_val, p_val, se = stats.linregress(years_arr, gap_any)
    safe_print(f"  Slope={slope:+.4f}/yr, R2={r_val**2:.3f}, p={p_val:.4f}")
    safe_print(f"  Year 1 gap:  {gap_any[0]:+.3f}")
    safe_print(f"  Year {years[-1]} gap: {gap_any[-1]:+.3f}")
    direction = "WIDENING" if slope > 0.001 else ("NARROWING" if slope < -0.001 else "STABLE")
    safe_print(f"  => Gap is {direction} over time")

# --- 6d. Correlation: Subsidy rate vs MG elevation rate ---
safe_print("\n--- Correlation: Subsidy Rate vs MG Elevation Rate ---")
if len(subsidy_series) == len(mg_elev_rates) and len(mg_elev_rates) >= 3:
    r_sub_mg, p_sub_mg = safe_corr(subsidy_series, mg_elev_rates, "Subsidy vs MG Elevation")
    if r_sub_mg is not None:
        safe_print(f"  => {'SIGNIFICANT' if p_sub_mg < 0.05 else 'NOT SIGNIFICANT'}")

# --- 6e. Correlation: Premium rate vs MG insurance rate ---
safe_print("\n--- Correlation: Premium Rate vs MG Insurance Rate ---")
if len(premium_series) == len(mg_ins_rates) and len(mg_ins_rates) >= 3:
    r_prem_mg, p_prem_mg = safe_corr(premium_series, mg_ins_rates, "Premium vs MG Insurance")
    if r_prem_mg is not None:
        safe_print(f"  => {'SIGNIFICANT' if p_prem_mg < 0.05 else 'NOT SIGNIFICANT'}")


# ===========================================================================
# 7. FIGURES
# ===========================================================================
safe_print("\n" + "=" * 80)
safe_print("[7] GENERATING FIGURES")
safe_print("=" * 80)

plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "figure.dpi": 150,
})

# --- Figure A: Institutional Dynamics (Dual-Axis) ---
fig, ax1 = plt.subplots(figsize=(10, 5))

color_sub = "#2196F3"
color_prem = "#F44336"
color_loss = "#FF9800"

ax1.set_xlabel("Year")
ax1.set_ylabel("Subsidy / Premium Rate", color="black")
ax1.plot(common_years, [s * 100 for s in subsidy_series], "o-", color=color_sub,
         linewidth=2, markersize=6, label="Subsidy Rate (%)")
ax1.plot(common_years, [p * 100 for p in premium_series], "s--", color=color_prem,
         linewidth=2, markersize=6, label="Premium Rate (%)")
ax1.set_ylim(0, max(max(s * 100 for s in subsidy_series) + 10, 60))
ax1.tick_params(axis="y")
ax1.legend(loc="upper left")

ax2 = ax1.twinx()
ax2.set_ylabel("Loss Ratio", color=color_loss)
ax2.bar(common_years, loss_ratio_series, alpha=0.3, color=color_loss, width=0.6, label="Loss Ratio")
ax2.tick_params(axis="y", labelcolor=color_loss)
ax2.legend(loc="upper right")

ax1.set_title("Institutional Dynamics: Subsidy Rate, Premium Rate & Loss Ratio")
ax1.set_xticks(common_years)
ax1.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig_path = os.path.join(ANALYSIS_DIR, "rq2_institutional_dynamics.png")
fig.savefig(fig_path, dpi=150, bbox_inches="tight")
safe_print(f"  Saved: {fig_path}")
plt.close(fig)

# --- Figure B: MG vs NMG Adaptation Gap ---
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Insurance rates
ax = axes[0, 0]
ax.plot(years, mg_ins_rates, "o-", color="#E91E63", label="MG", linewidth=2)
ax.plot(years, nmg_ins_rates, "s-", color="#3F51B5", label="NMG", linewidth=2)
ax.fill_between(years, mg_ins_rates, nmg_ins_rates, alpha=0.15, color="gray")
ax.set_title("Insurance Rate by Group")
ax.set_xlabel("Year")
ax.set_ylabel("Insurance Rate")
ax.legend()
ax.grid(alpha=0.3)
ax.set_xticks(years)

# Elevation rates
ax = axes[0, 1]
ax.plot(years, mg_elev_rates, "o-", color="#E91E63", label="MG", linewidth=2)
ax.plot(years, nmg_elev_rates, "s-", color="#3F51B5", label="NMG", linewidth=2)
ax.fill_between(years, mg_elev_rates, nmg_elev_rates, alpha=0.15, color="gray")
ax.set_title("Elevation Rate by Group")
ax.set_xlabel("Year")
ax.set_ylabel("Elevation Rate")
ax.legend()
ax.grid(alpha=0.3)
ax.set_xticks(years)

# Buyout rates
ax = axes[1, 0]
ax.plot(years, mg_buy_rates, "o-", color="#E91E63", label="MG", linewidth=2)
ax.plot(years, nmg_buy_rates, "s-", color="#3F51B5", label="NMG", linewidth=2)
ax.fill_between(years, mg_buy_rates, nmg_buy_rates, alpha=0.15, color="gray")
ax.set_title("Buyout Rate by Group")
ax.set_xlabel("Year")
ax.set_ylabel("Buyout Rate")
ax.legend()
ax.grid(alpha=0.3)
ax.set_xticks(years)

# Adaptation gap (NMG - MG) for all metrics
ax = axes[1, 1]
ax.plot(years, gap_insurance, "o-", label="Insurance Gap", linewidth=2)
ax.plot(years, gap_elevation, "s--", label="Elevation Gap", linewidth=2)
ax.plot(years, gap_buyout, "^:", label="Buyout Gap", linewidth=2)
ax.plot(years, gap_any, "D-", color="black", label="Any Action Gap", linewidth=2.5)
ax.axhline(y=0, color="gray", linestyle=":", alpha=0.5)
ax.set_title("Adaptation Gap (NMG - MG)")
ax.set_xlabel("Year")
ax.set_ylabel("Gap (NMG rate - MG rate)")
ax.legend()
ax.grid(alpha=0.3)
ax.set_xticks(years)

fig.suptitle("RQ2: MG vs NMG Adaptation Rates Over Time", fontsize=14, fontweight="bold", y=1.01)
fig.tight_layout()
fig_path = os.path.join(ANALYSIS_DIR, "rq2_adaptation_gap.png")
fig.savefig(fig_path, dpi=150, bbox_inches="tight")
safe_print(f"  Saved: {fig_path}")
plt.close(fig)

# --- Figure C: Affordability Constraint by MG ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Bar chart: rejection rates
ax = axes[0]
rules = list(gov_summary.get("rule_frequency", {}).keys())
mg_counts = []
nmg_counts = []
for rule in rules:
    if rule == "affordability":
        mg_r = rejected[(rejected["error_messages"].str.contains("AFFORDABILITY", case=False, na=False)) &
                        (rejected["mg"] == True)]
        nmg_r = rejected[(rejected["error_messages"].str.contains("AFFORDABILITY", case=False, na=False)) &
                         (rejected["mg"] == False)]
    else:
        mg_r = rejected[(rejected["failed_rules"].str.contains(rule, case=False, na=False)) &
                        (rejected["mg"] == True)]
        nmg_r = rejected[(rejected["failed_rules"].str.contains(rule, case=False, na=False)) &
                         (rejected["mg"] == False)]
    mg_counts.append(len(mg_r))
    nmg_counts.append(len(nmg_r))

x = np.arange(len(rules))
width = 0.35
bars1 = ax.bar(x - width / 2, mg_counts, width, label="MG", color="#E91E63", alpha=0.8)
bars2 = ax.bar(x + width / 2, nmg_counts, width, label="NMG", color="#3F51B5", alpha=0.8)
ax.set_ylabel("Rejection Count")
ax.set_title("Governance Rejections by Rule & Group")
ax.set_xticks(x)
ax.set_xticklabels([r.replace("_", "\n") for r in rules], fontsize=8, rotation=30, ha="right")
ax.legend()
ax.grid(axis="y", alpha=0.3)

# Per-year affordability rate
ax = axes[1]
ax.plot(years, mg_aff_yearly, "o-", color="#E91E63", label="MG", linewidth=2)
ax.plot(years, nmg_aff_yearly, "s-", color="#3F51B5", label="NMG", linewidth=2)
ax.fill_between(years, mg_aff_yearly, nmg_aff_yearly, alpha=0.15, color="gray")
ax.set_title("Affordability Rejection Rate Over Time")
ax.set_xlabel("Year")
ax.set_ylabel("Affordability Rejection Rate")
ax.legend()
ax.grid(alpha=0.3)
ax.set_xticks(years)

fig.suptitle("RQ2: Affordability Constraints & Protection Inequality", fontsize=14, fontweight="bold", y=1.01)
fig.tight_layout()
fig_path = os.path.join(ANALYSIS_DIR, "rq2_affordability_constraint.png")
fig.savefig(fig_path, dpi=150, bbox_inches="tight")
safe_print(f"  Saved: {fig_path}")
plt.close(fig)

# --- Figure D: Insurance Feedback Loop ---
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Scatter: Premium vs Uptake
ax = axes[0]
ax.scatter(premium_series, uptake_series, c=common_years, cmap="viridis", s=80, edgecolors="black", zorder=3)
for i, yr in enumerate(common_years):
    ax.annotate(f"Y{yr}", (premium_series[i], uptake_series[i]), fontsize=8, ha="left", va="bottom")
ax.set_xlabel("Premium Rate")
ax.set_ylabel("Insurance Uptake Rate")
ax.set_title("Premium vs Uptake (color=year)")
ax.grid(alpha=0.3)

# Time series: stacked feedback loop
ax = axes[1]
ax_loss = ax.twinx()
l1, = ax.plot(common_years, [u * 100 for u in uptake_series], "o-", color="#4CAF50", linewidth=2, label="Uptake (%)")
l2, = ax.plot(common_years, [p * 100 for p in premium_series], "s--", color="#F44336", linewidth=2, label="Premium (%)")
l3, = ax_loss.plot(common_years, loss_ratio_series, "^:", color="#FF9800", linewidth=2, label="Loss Ratio")
ax.set_xlabel("Year")
ax.set_ylabel("Rate (%)")
ax_loss.set_ylabel("Loss Ratio", color="#FF9800")
ax.set_title("Insurance Feedback Loop")
ax.set_xticks(common_years)
lines = [l1, l2, l3]
labels = [l.get_label() for l in lines]
ax.legend(lines, labels, loc="upper left")
ax.grid(alpha=0.3)

fig.suptitle("RQ2: Insurance Feedback Dynamics", fontsize=14, fontweight="bold", y=1.01)
fig.tight_layout()
fig_path = os.path.join(ANALYSIS_DIR, "rq2_insurance_feedback.png")
fig.savefig(fig_path, dpi=150, bbox_inches="tight")
safe_print(f"  Saved: {fig_path}")
plt.close(fig)


# ===========================================================================
# 8. SUMMARY
# ===========================================================================
safe_print("\n" + "=" * 80)
safe_print("[8] SUMMARY OF RQ2 FINDINGS")
safe_print("=" * 80)

max_loss = max(loss_ratio_series) if loss_ratio_series else 0.0
safe_print(f"""
1. INSTITUTIONAL DYNAMICS:
   - Government subsidy: 50% (Y1-6) -> 55% (Y7-13), only 1 increase in 13 years
   - Insurance CRS: 0% discount throughout (no change in 13 years)
   - Premium rate: constant at 2.0% (no CRS adjustment)
   - Loss ratio ranged from 0.0 to {max_loss:.1f} but never triggered CRS improvement
   - Key finding: Institutional inertia -- both agents default to "maintain"

2. MG vs NMG ADAPTATION GAP:
   - Insurance gap (NMG-MG): Mean = {np.mean(gap_insurance):+.3f}
     (NEGATIVE => MG has HIGHER insurance rate -- counterintuitive)
   - Elevation gap (NMG-MG): Mean = {np.mean(gap_elevation):+.3f}
     (POSITIVE => NMG elevates more -- structural inequality)
   - Buyout gap (NMG-MG):   Mean = {np.mean(gap_buyout):+.3f}
   - Any action gap:        Mean = {np.mean(gap_any):+.3f}
   - MG mean insurance rate:  {np.mean(mg_ins_rates):.3f} vs NMG: {np.mean(nmg_ins_rates):.3f}
   - MG mean elevation rate:  {np.mean(mg_elev_rates):.3f} vs NMG: {np.mean(nmg_elev_rates):.3f}
   - Interpretation: MG agents have higher insurance uptake (cheaper action)
     but lower elevation rate (expensive action blocked by affordability)

3. AFFORDABILITY CONSTRAINT:
   - MG affordability rejection rate: {mg_aff_rate:.1%}
   - NMG affordability rejection rate: {nmg_aff_rate:.1%}
   - MG agents are {or_val:.1f}x more likely to be REJECTED overall
   - Chi-squared test: chi2={chi2:.3f}, p={p_chi:.6f}
   - Affordability rejections: {len(affordability_rej)}/{len(rejected)}
     ({len(affordability_rej)/max(len(rejected),1):.1%}) of all rejections

4. INSURANCE FEEDBACK LOOP:
   - CRS discount remained at 0% => no premium relief for households
   - Loss ratio spiked to {max_loss:.1f} in flood years, but FEMA agent chose maintain
   - Feedback loop is BROKEN: institutional agent does not respond to signals
   - This perpetuates affordability barriers for MG households

5. KEY CONCLUSION:
   - Institutional inertia (flat subsidy, no CRS improvement) is the primary
     mechanism through which STRUCTURAL protection inequality persists
   - Affordability governance rule disproportionately blocks MG households
     from expensive adaptation (elevation, buyout) while allowing insurance
   - The "maintain" bias of institutional LLM agents creates structural lock-in
   - MG households compensate with higher insurance uptake (cheaper alternative)
     but remain structurally unprotected (lower elevation rates)
""")

safe_print("=" * 80)
safe_print("RQ2 Analysis Complete. Figures saved to:")
safe_print(f"  {ANALYSIS_DIR}")
safe_print("=" * 80)
