"""
Recompute 4-cell behavior distribution using EXECUTED (final) actions
instead of PROPOSED actions.

EXECUTED logic:
  - If status=APPROVED -> executed = proposed_skill
  - If status=REJECTED -> executed = "do_nothing" (fallback)
"""

import pandas as pd
import os
from pathlib import Path

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3")
RESULTS = BASE / "results" / "paper3_hybrid_v2"
PROFILES = BASE / "data" / "agent_initialization_complete.csv"
OUT_CSV = BASE / "analysis" / "tables" / "rq2_4cell_proposed_vs_executed.csv"

SEEDS = ["seed_42", "seed_123", "seed_456"]
AGENT_TYPES = ["household_owner", "household_renter"]

# Load agent profiles for MG status
profiles = pd.read_csv(PROFILES, usecols=["agent_id", "cell", "mg", "tenure"])
print(f"Loaded {len(profiles)} agent profiles")
print(f"  Cells: {profiles['cell'].value_counts().to_dict()}")

# Load all audit CSVs
frames = []
for seed in SEEDS:
    for atype in AGENT_TYPES:
        csv_path = RESULTS / seed / "gemma3_4b_strict" / f"{atype}_governance_audit.csv"
        if not csv_path.exists():
            print(f"  WARNING: missing {csv_path}")
            continue
        df = pd.read_csv(csv_path, usecols=["agent_id", "year", "proposed_skill", "final_skill", "status"])
        df["seed"] = seed
        df["agent_type"] = atype
        frames.append(df)
        print(f"  Loaded {len(df)} rows from {seed}/{atype}")

audit = pd.concat(frames, ignore_index=True)
print(f"\nTotal audit rows: {len(audit)}")

# Determine executed action
# APPROVED -> proposed_skill is what ran; REJECTED -> fallback = do_nothing
audit["executed_skill"] = audit.apply(
    lambda r: r["proposed_skill"] if r["status"] == "APPROVED" else "do_nothing", axis=1
)

# Join with profiles to get cell
audit = audit.merge(profiles[["agent_id", "cell"]], on="agent_id", how="left")
missing_cell = audit["cell"].isna().sum()
if missing_cell > 0:
    print(f"WARNING: {missing_cell} rows have no cell mapping")

# Quick status summary
print("\n=== STATUS SUMMARY ===")
status_counts = audit.groupby("status").size()
print(status_counts)
print(f"Rejection rate: {status_counts.get('REJECTED', 0) / len(audit) * 100:.1f}%")

# Normalize skill names for cleaner grouping
def normalize_skill(s):
    s = str(s).lower().strip()
    mapping = {
        "buy_flood_insurance": "insurance",
        "buy_contents_insurance": "contents_insurance",
        "elevate_house": "elevation",
        "accept_buyout": "buyout",
        "relocate": "relocate",
        "do_nothing": "do_nothing",
        "retrofit_property": "retrofit",
    }
    return mapping.get(s, s)

audit["proposed_norm"] = audit["proposed_skill"].apply(normalize_skill)
audit["executed_norm"] = audit["executed_skill"].apply(normalize_skill)

# Compute distributions per cell
cells = ["MG-Owner", "MG-Renter", "NMG-Owner", "NMG-Renter"]

# Get all unique skills across proposed and executed
all_skills = sorted(set(audit["proposed_norm"].unique()) | set(audit["executed_norm"].unique()))

rows = []
for cell in cells:
    cell_data = audit[audit["cell"] == cell]
    n = len(cell_data)
    if n == 0:
        continue

    for skill in all_skills:
        proposed_count = (cell_data["proposed_norm"] == skill).sum()
        executed_count = (cell_data["executed_norm"] == skill).sum()
        proposed_pct = proposed_count / n * 100
        executed_pct = executed_count / n * 100
        gap = proposed_pct - executed_pct
        rows.append({
            "cell": cell,
            "skill": skill,
            "proposed_count": proposed_count,
            "proposed_pct": round(proposed_pct, 2),
            "executed_count": executed_count,
            "executed_pct": round(executed_pct, 2),
            "gap_pp": round(gap, 2),  # percentage points
            "n_decisions": n,
        })

result = pd.DataFrame(rows)

# Print the comparison table
print("\n" + "=" * 100)
print("4-CELL BEHAVIOR DISTRIBUTION: PROPOSED vs EXECUTED (all seeds pooled)")
print("=" * 100)

for cell in cells:
    cdf = result[result["cell"] == cell].sort_values("proposed_pct", ascending=False)
    n = cdf["n_decisions"].iloc[0] if len(cdf) > 0 else 0
    print(f"\n--- {cell} (N={n}) ---")
    print(f"  {'Skill':<22} {'Proposed%':>10} {'Executed%':>10} {'Gap(pp)':>10} {'Proposed_N':>10} {'Executed_N':>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for _, r in cdf.iterrows():
        if r["proposed_count"] > 0 or r["executed_count"] > 0:
            print(f"  {r['skill']:<22} {r['proposed_pct']:>9.1f}% {r['executed_pct']:>9.1f}% {r['gap_pp']:>+9.1f} {r['proposed_count']:>10} {r['executed_count']:>10}")

# Also show rejection by cell
print("\n" + "=" * 100)
print("REJECTION RATES BY CELL")
print("=" * 100)
for cell in cells:
    cell_data = audit[audit["cell"] == cell]
    n = len(cell_data)
    rejected = (cell_data["status"] == "REJECTED").sum()
    print(f"  {cell:<15} {rejected:>5} / {n:>5} = {rejected/n*100:>5.1f}% rejected")

# Show what skills are being blocked
print("\n" + "=" * 100)
print("REJECTED PROPOSALS BY CELL x SKILL (top blockers)")
print("=" * 100)
rejected = audit[audit["status"] == "REJECTED"]
for cell in cells:
    cell_rej = rejected[rejected["cell"] == cell]
    if len(cell_rej) == 0:
        continue
    cell_total = len(audit[audit["cell"] == cell])
    print(f"\n--- {cell} ---")
    skill_counts = cell_rej["proposed_norm"].value_counts()
    for skill, count in skill_counts.items():
        pct_of_cell = count / cell_total * 100
        print(f"  {skill:<22} {count:>5} blocked ({pct_of_cell:.1f}% of cell decisions)")

# Aggregate summary: proposed vs executed across ALL cells
print("\n" + "=" * 100)
print("AGGREGATE SUMMARY (all cells, all seeds)")
print("=" * 100)
agg_proposed = audit["proposed_norm"].value_counts(normalize=True) * 100
agg_executed = audit["executed_norm"].value_counts(normalize=True) * 100
all_s = sorted(set(agg_proposed.index) | set(agg_executed.index))
print(f"  {'Skill':<22} {'Proposed%':>10} {'Executed%':>10} {'Gap(pp)':>10}")
print(f"  {'-'*22} {'-'*10} {'-'*10} {'-'*10}")
for s in all_s:
    p = agg_proposed.get(s, 0)
    e = agg_executed.get(s, 0)
    print(f"  {s:<22} {p:>9.1f}% {e:>9.1f}% {p-e:>+9.1f}")

# Save
result.to_csv(OUT_CSV, index=False)
print(f"\nSaved to: {OUT_CSV}")
