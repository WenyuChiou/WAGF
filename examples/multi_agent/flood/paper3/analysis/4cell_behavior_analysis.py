"""
4-Cell Household Behavior Distribution Analysis
Reads owner/renter JSONL traces, groups by MG x Tenure, computes skill distributions,
approval rates, adaptation trends, rejection reasons, and MG vs NMG gaps.
"""

import json
import os
from collections import defaultdict, Counter

# Paths
BASE = r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
RAW_DIR = os.path.join(BASE, "examples", "multi_agent", "flood", "paper3",
                       "results", "paper3_hybrid_v2", "seed_42", "gemma3_4b_strict", "raw")
OWNER_FILE = os.path.join(RAW_DIR, "household_owner_traces.jsonl")
RENTER_FILE = os.path.join(RAW_DIR, "household_renter_traces.jsonl")
OUTPUT_FILE = os.path.join(BASE, "examples", "multi_agent", "flood", "paper3",
                           "analysis", "working", "reviews", "4cell_behavior_distribution.md")

# Data structures
# cell -> { skill_counts, skill_outcome[skill][APPROVED/REJECTED], year_skills[year][skill], rejection_reasons }
cells = {}
for cell_name in ["MG-Owner", "MG-Renter", "NMG-Owner", "NMG-Renter"]:
    cells[cell_name] = {
        "skill_counts": Counter(),
        "skill_outcome": defaultdict(lambda: Counter()),
        "year_skills": defaultdict(lambda: Counter()),
        "rejection_reasons": Counter(),
        "agent_ids": set(),
        "total_records": 0,
    }


def get_cell(agent_type, mg):
    if agent_type == "household_owner":
        return "MG-Owner" if mg else "NMG-Owner"
    else:
        return "MG-Renter" if mg else "NMG-Renter"


def process_file(filepath):
    count = 0
    skipped = 0
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            agent_id = rec.get("agent_id", "")
            agent_type = rec.get("agent_type", "")
            year = rec.get("year")
            outcome = rec.get("outcome", "UNKNOWN")

            # Get mg from state_before
            state_before = rec.get("state_before") or {}
            mg = state_before.get("mg", False)

            # Get skill name
            sp = rec.get("skill_proposal") or {}
            skill = sp.get("skill_name")
            if not skill:
                # Try approved_skill
                approved = rec.get("approved_skill") or {}
                skill = approved.get("skill_name")
            if not skill:
                skipped += 1
                continue

            cell_name = get_cell(agent_type, mg)
            cell = cells[cell_name]
            cell["skill_counts"][skill] += 1
            cell["skill_outcome"][skill][outcome] += 1
            cell["year_skills"][year][skill] += 1
            cell["agent_ids"].add(agent_id)
            cell["total_records"] += 1

            # Rejection reasons
            if outcome == "REJECTED":
                vis = rec.get("validation_issues") or []
                for vi in vis:
                    errors = vi.get("errors", [])
                    validator = vi.get("validator", "unknown")
                    rule_id = vi.get("rule_id", "")
                    for err in errors:
                        # Truncate long error messages
                        short = err[:120] if len(err) > 120 else err
                        cell["rejection_reasons"][short] += 1

            count += 1
            if count % 100000 == 0:
                print(f"  Processed {count:,} records from {os.path.basename(filepath)}...")

    print(f"  Done: {count:,} records, {skipped} skipped from {os.path.basename(filepath)}")
    return count


# Process both files
print("Processing owner traces...")
n_owner = process_file(OWNER_FILE)
print("Processing renter traces...")
n_renter = process_file(RENTER_FILE)
print(f"Total records processed: {n_owner + n_renter:,}")

# Generate report
lines = []
lines.append("# 4-Cell Household Behavior Distribution Analysis")
lines.append("")
lines.append(f"**Source**: `seed_42/gemma3_4b_strict` | **Total records**: {n_owner + n_renter:,}")
lines.append("")

# Summary table
lines.append("## Summary by Cell")
lines.append("")
lines.append("| Cell | Agents | Records | Records/Agent |")
lines.append("|------|--------|---------|---------------|")
for cn in ["MG-Owner", "NMG-Owner", "MG-Renter", "NMG-Renter"]:
    c = cells[cn]
    n_agents = len(c["agent_ids"])
    n_recs = c["total_records"]
    rpa = f"{n_recs / n_agents:.1f}" if n_agents > 0 else "N/A"
    lines.append(f"| {cn} | {n_agents} | {n_recs:,} | {rpa} |")
lines.append("")

# Section: Skill distributions per cell
for cn in ["MG-Owner", "NMG-Owner", "MG-Renter", "NMG-Renter"]:
    c = cells[cn]
    total = c["total_records"]
    if total == 0:
        continue

    lines.append(f"## {cn}")
    lines.append("")

    # 4a: Overall skill distribution
    lines.append("### Skill Distribution (All Years)")
    lines.append("")
    lines.append("| Skill | Count | % |")
    lines.append("|-------|-------|---|")
    for skill, cnt in c["skill_counts"].most_common():
        pct = cnt / total * 100
        lines.append(f"| {skill} | {cnt:,} | {pct:.1f}% |")
    lines.append("")

    # 4b: Approval/rejection per skill
    lines.append("### Approval vs Rejection by Skill")
    lines.append("")
    lines.append("| Skill | Approved | Rejected | Approval Rate |")
    lines.append("|-------|----------|----------|---------------|")
    for skill in sorted(c["skill_outcome"].keys()):
        oc = c["skill_outcome"][skill]
        approved = oc.get("APPROVED", 0)
        rejected = oc.get("REJECTED", 0)
        stotal = approved + rejected
        rate = f"{approved / stotal * 100:.1f}%" if stotal > 0 else "N/A"
        lines.append(f"| {skill} | {approved:,} | {rejected:,} | {rate} |")
    lines.append("")

    # 4c: Year-by-year adaptation rate
    years = sorted(c["year_skills"].keys())
    lines.append("### Year-by-Year Adaptation Rate (% non-do_nothing)")
    lines.append("")
    lines.append("| Year | Total | do_nothing | Adaptive | Adaptation Rate |")
    lines.append("|------|-------|------------|----------|-----------------|")
    for yr in years:
        ys = c["year_skills"][yr]
        yr_total = sum(ys.values())
        dn = ys.get("do_nothing", 0)
        adaptive = yr_total - dn
        rate = f"{adaptive / yr_total * 100:.1f}%" if yr_total > 0 else "N/A"
        lines.append(f"| {yr} | {yr_total:,} | {dn:,} | {adaptive:,} | {rate} |")
    lines.append("")

    # 4d: Top rejection reasons
    lines.append("### Top 10 Rejection Reasons")
    lines.append("")
    lines.append("| Reason | Count |")
    lines.append("|--------|-------|")
    for reason, cnt in c["rejection_reasons"].most_common(10):
        # Escape pipes in reason text
        safe = reason.replace("|", "\\|")
        lines.append(f"| {safe} | {cnt:,} |")
    lines.append("")

# Section 5: MG vs NMG adaptation gap
lines.append("## MG vs NMG Adaptation Gap")
lines.append("")

# Owner gap
lines.append("### Owner Gap")
lines.append("")
lines.append("| Metric | MG-Owner | NMG-Owner | Gap (MG - NMG) |")
lines.append("|--------|----------|-----------|----------------|")

for metric_skill, label in [("buy_insurance", "Insurance Rate"),
                             ("elevate_house", "Elevation Rate"),
                             ("buyout_program", "Buyout Rate")]:
    mg_total = cells["MG-Owner"]["total_records"]
    nmg_total = cells["NMG-Owner"]["total_records"]
    mg_cnt = cells["MG-Owner"]["skill_counts"].get(metric_skill, 0)
    nmg_cnt = cells["NMG-Owner"]["skill_counts"].get(metric_skill, 0)
    mg_pct = mg_cnt / mg_total * 100 if mg_total > 0 else 0
    nmg_pct = nmg_cnt / nmg_total * 100 if nmg_total > 0 else 0
    gap = mg_pct - nmg_pct
    lines.append(f"| {label} | {mg_pct:.1f}% | {nmg_pct:.1f}% | {gap:+.1f}pp |")

# Adaptation rate (non-do_nothing)
mg_dn = cells["MG-Owner"]["skill_counts"].get("do_nothing", 0)
nmg_dn = cells["NMG-Owner"]["skill_counts"].get("do_nothing", 0)
mg_total = cells["MG-Owner"]["total_records"]
nmg_total = cells["NMG-Owner"]["total_records"]
mg_adapt = (mg_total - mg_dn) / mg_total * 100 if mg_total > 0 else 0
nmg_adapt = (nmg_total - nmg_dn) / nmg_total * 100 if nmg_total > 0 else 0
lines.append(f"| Adaptation Rate | {mg_adapt:.1f}% | {nmg_adapt:.1f}% | {mg_adapt - nmg_adapt:+.1f}pp |")
lines.append("")

# Renter gap
lines.append("### Renter Gap")
lines.append("")
lines.append("| Metric | MG-Renter | NMG-Renter | Gap (MG - NMG) |")
lines.append("|--------|-----------|------------|----------------|")

for metric_skill, label in [("buy_contents_insurance", "Insurance Rate"),
                             ("relocate", "Relocation Rate")]:
    mg_total = cells["MG-Renter"]["total_records"]
    nmg_total = cells["NMG-Renter"]["total_records"]
    mg_cnt = cells["MG-Renter"]["skill_counts"].get(metric_skill, 0)
    nmg_cnt = cells["NMG-Renter"]["skill_counts"].get(metric_skill, 0)
    mg_pct = mg_cnt / mg_total * 100 if mg_total > 0 else 0
    nmg_pct = nmg_cnt / nmg_total * 100 if nmg_total > 0 else 0
    gap = mg_pct - nmg_pct
    lines.append(f"| {label} | {mg_pct:.1f}% | {nmg_pct:.1f}% | {gap:+.1f}pp |")

mg_dn = cells["MG-Renter"]["skill_counts"].get("do_nothing", 0)
nmg_dn = cells["NMG-Renter"]["skill_counts"].get("do_nothing", 0)
mg_total = cells["MG-Renter"]["total_records"]
nmg_total = cells["NMG-Renter"]["total_records"]
mg_adapt = (mg_total - mg_dn) / mg_total * 100 if mg_total > 0 else 0
nmg_adapt = (nmg_total - nmg_dn) / nmg_total * 100 if nmg_total > 0 else 0
lines.append(f"| Adaptation Rate | {mg_adapt:.1f}% | {nmg_adapt:.1f}% | {mg_adapt - nmg_adapt:+.1f}pp |")
lines.append("")

# Approval rate gap
lines.append("### Approval Rate Gap (All Skills)")
lines.append("")
lines.append("| Cell | Total Approved | Total Rejected | Approval Rate |")
lines.append("|------|----------------|----------------|---------------|")
for cn in ["MG-Owner", "NMG-Owner", "MG-Renter", "NMG-Renter"]:
    c = cells[cn]
    approved = sum(oc.get("APPROVED", 0) for oc in c["skill_outcome"].values())
    rejected = sum(oc.get("REJECTED", 0) for oc in c["skill_outcome"].values())
    total = approved + rejected
    rate = f"{approved / total * 100:.1f}%" if total > 0 else "N/A"
    lines.append(f"| {cn} | {approved:,} | {rejected:,} | {rate} |")
lines.append("")

# Write output
report = "\n".join(lines)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(report)

print(f"\nReport saved to: {OUTPUT_FILE}")
print(f"Report length: {len(report):,} chars")
