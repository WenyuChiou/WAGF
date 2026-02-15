"""
Compare seed43 in-progress traces vs seed42 completed simulation.
Seed43: JSONL traces (up to ~year 32)
Seed42: simulation_log.csv (42 years complete)
"""

import json
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\irrigation_abm\results")
SEED43_TRACES = BASE / "production_v20_42yr_seed43" / "raw" / "irrigation_farmer_traces.jsonl"
SEED42_CSV = BASE / "production_v20_42yr_seed42" / "simulation_log.csv"

SKILLS = ["increase_large", "increase_small", "maintain", "decrease_small", "decrease_large"]
N_SKILLS = len(SKILLS)


def entropy_normalized(counts: dict) -> float:
    """Shannon entropy H / log2(N_SKILLS)."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c > 0:
            p = c / total
            h -= p * math.log2(p)
    return h / math.log2(N_SKILLS)


# ── 1. Parse seed43 JSONL ──────────────────────────────────────────────
print("=" * 70)
print("PARSING SEED43 TRACES")
print("=" * 70)

seed43_records = []
with open(SEED43_TRACES, "r", encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"  [WARN] line {line_no}: JSON parse error: {e}")
            continue

        proposed = d.get("skill_proposal", {})
        approved = d.get("approved_skill", {})
        proposed_skill = proposed.get("skill_name", "UNKNOWN") if isinstance(proposed, dict) else "UNKNOWN"
        final_skill = approved.get("skill_name", proposed_skill) if isinstance(approved, dict) else proposed_skill
        outcome = d.get("outcome", "UNKNOWN")

        # Governance / validation
        validation_issues = d.get("validation_issues")
        gov_triggered = (
            outcome == "REJECTED"
            or d.get("retry_count", 0) > 0
            or (validation_issues is not None and validation_issues != "" and validation_issues != [])
        )

        # Governance rule names from validation_issues
        rule_names = []
        if isinstance(validation_issues, list):
            for issue in validation_issues:
                if isinstance(issue, dict):
                    rule_names.append(issue.get("rule_id", issue.get("rule", "unknown_rule")))
                elif isinstance(issue, str):
                    rule_names.append(issue)
        elif isinstance(validation_issues, str) and validation_issues:
            rule_names.append(validation_issues)

        seed43_records.append({
            "agent_id": d.get("agent_id"),
            "year": d.get("year"),
            "proposed_skill": proposed_skill,
            "final_skill": final_skill,
            "outcome": outcome,
            "gov_triggered": gov_triggered,
            "retry_count": d.get("retry_count", 0),
            "rule_names": rule_names,
        })

max_year_43 = max(r["year"] for r in seed43_records)
agents_43 = set(r["agent_id"] for r in seed43_records)
print(f"  Total records: {len(seed43_records)}")
print(f"  Agents: {len(agents_43)}")
print(f"  Years covered: 1-{max_year_43}")

# ── 2. Parse seed42 CSV ────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("PARSING SEED42 SIMULATION LOG")
print("=" * 70)

seed42_records = []
with open(SEED42_CSV, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        seed42_records.append({
            "agent_id": row["agent_id"],
            "year": int(row["year"]),
            "final_skill": row["yearly_decision"],
        })

max_year_42 = max(r["year"] for r in seed42_records)
agents_42 = set(r["agent_id"] for r in seed42_records)
print(f"  Total records: {len(seed42_records)}")
print(f"  Agents: {len(agents_42)}")
print(f"  Years covered: 1-{max_year_42}")

# ── 3. Seed43 analysis ─────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("SEED43 ANALYSIS (years 1-{})".format(max_year_43))
print("=" * 70)

# 3a. Overall skill distribution
final_skill_counts_43 = Counter(r["final_skill"] for r in seed43_records)
total_43 = len(seed43_records)
print("\n── Overall Skill Distribution (final skills) ──")
for sk in SKILLS:
    c = final_skill_counts_43.get(sk, 0)
    print(f"  {sk:20s}: {c:5d}  ({100*c/total_43:.1f}%)")
# Any unexpected skills
for sk, c in final_skill_counts_43.items():
    if sk not in SKILLS:
        print(f"  {sk:20s}: {c:5d}  ({100*c/total_43:.1f}%)  [UNEXPECTED]")

# 3b. EHE per year
print("\n── EHE (Entropy) per Year ──")
year_skill_43 = defaultdict(Counter)
for r in seed43_records:
    year_skill_43[r["year"]][r["final_skill"]] += 1

ehe_43 = {}
for y in sorted(year_skill_43.keys()):
    ehe_43[y] = entropy_normalized(year_skill_43[y])

for y in sorted(ehe_43.keys()):
    bar = "#" * int(ehe_43[y] * 40)
    print(f"  Year {y:2d}: EHE={ehe_43[y]:.4f}  {bar}")
mean_ehe_43 = sum(ehe_43.values()) / len(ehe_43) if ehe_43 else 0
print(f"  Mean EHE: {mean_ehe_43:.4f}")

# 3c. Governance intervention rate
gov_triggered = sum(1 for r in seed43_records if r["gov_triggered"])
print(f"\n── Governance Intervention ──")
print(f"  Total decisions: {total_43}")
print(f"  Governance triggered: {gov_triggered} ({100*gov_triggered/total_43:.1f}%)")

# 3d. Outcome distribution
outcome_counts = Counter(r["outcome"] for r in seed43_records)
print(f"\n── Outcome Distribution ──")
for o, c in outcome_counts.most_common():
    print(f"  {o:20s}: {c:5d}  ({100*c/total_43:.1f}%)")

# 3e. Retry stats
retry_counts = [r["retry_count"] for r in seed43_records]
retried = [r for r in seed43_records if r["retry_count"] > 0]
print(f"\n── Retry Statistics ──")
print(f"  Decisions with retries: {len(retried)} ({100*len(retried)/total_43:.1f}%)")
if retried:
    retry_approved = sum(1 for r in retried if r["outcome"] == "APPROVED")
    retry_rejected = sum(1 for r in retried if r["outcome"] == "REJECTED")
    print(f"  After retry → APPROVED: {retry_approved} ({100*retry_approved/len(retried):.1f}%)")
    print(f"  After retry → REJECTED: {retry_rejected} ({100*retry_rejected/len(retried):.1f}%)")
    max_retry = max(r["retry_count"] for r in retried)
    avg_retry = sum(r["retry_count"] for r in retried) / len(retried)
    print(f"  Max retry count: {max_retry}")
    print(f"  Avg retry count (among retried): {avg_retry:.2f}")

# 3f. Top governance rules
all_rules = []
for r in seed43_records:
    all_rules.extend(r["rule_names"])
rule_counts = Counter(all_rules)
print(f"\n── Top Governance Rules Fired ──")
for rule, c in rule_counts.most_common(15):
    print(f"  {rule:50s}: {c:5d}")

# ── 4. Comparison: seed43 vs seed42 (overlapping years) ────────────────
overlap_years = min(max_year_43, max_year_42)
print(f"\n{'=' * 70}")
print(f"COMPARISON: SEED43 vs SEED42 (years 1-{overlap_years})")
print("=" * 70)

# Seed42 year-level skill counts
year_skill_42 = defaultdict(Counter)
for r in seed42_records:
    if r["year"] <= overlap_years:
        year_skill_42[r["year"]][r["final_skill"]] += 1

# Overall skill distribution for overlapping years
s43_overlap = Counter()
s42_overlap = Counter()
for y in range(1, overlap_years + 1):
    s43_overlap += year_skill_43.get(y, Counter())
    s42_overlap += year_skill_42.get(y, Counter())

total_43_ov = sum(s43_overlap.values())
total_42_ov = sum(s42_overlap.values())

print(f"\n── Skill Distribution (years 1-{overlap_years}) ──")
print(f"  {'Skill':20s}  {'Seed43':>10s}  {'%43':>6s}  {'Seed42':>10s}  {'%42':>6s}  {'Diff':>7s}")
print(f"  {'-'*20}  {'-'*10}  {'-'*6}  {'-'*10}  {'-'*6}  {'-'*7}")
for sk in SKILLS:
    c43 = s43_overlap.get(sk, 0)
    c42 = s42_overlap.get(sk, 0)
    p43 = 100 * c43 / total_43_ov if total_43_ov else 0
    p42 = 100 * c42 / total_42_ov if total_42_ov else 0
    print(f"  {sk:20s}  {c43:10d}  {p43:5.1f}%  {c42:10d}  {p42:5.1f}%  {p43-p42:+6.1f}%")

# EHE comparison
ehe_42 = {}
for y in sorted(year_skill_42.keys()):
    ehe_42[y] = entropy_normalized(year_skill_42[y])

print(f"\n── EHE Trajectory Comparison (years 1-{overlap_years}) ──")
print(f"  {'Year':>4s}  {'EHE_43':>8s}  {'EHE_42':>8s}  {'Diff':>8s}")
print(f"  {'-'*4}  {'-'*8}  {'-'*8}  {'-'*8}")
diffs = []
for y in range(1, overlap_years + 1):
    e43 = ehe_43.get(y, 0)
    e42 = ehe_42.get(y, 0)
    diff = e43 - e42
    diffs.append(diff)
    marker = ""
    if abs(diff) > 0.1:
        marker = " <<<" if diff < 0 else " >>>"
    print(f"  {y:4d}  {e43:8.4f}  {e42:8.4f}  {diff:+8.4f}{marker}")

mean_43 = sum(ehe_43.get(y, 0) for y in range(1, overlap_years + 1)) / overlap_years
mean_42 = sum(ehe_42.get(y, 0) for y in range(1, overlap_years + 1)) / overlap_years
print(f"\n  Mean EHE (1-{overlap_years}):  seed43={mean_43:.4f}  seed42={mean_42:.4f}  diff={mean_43-mean_42:+.4f}")

# ── 5. Notable differences ─────────────────────────────────────────────
print(f"\n{'=' * 70}")
print("NOTABLE DIFFERENCES")
print("=" * 70)

# Proposed vs final skill mismatch in seed43
mismatches = [r for r in seed43_records if r["proposed_skill"] != r["final_skill"]]
print(f"\n  Proposed != Final skill (governance overrides): {len(mismatches)} / {total_43} ({100*len(mismatches)/total_43:.1f}%)")
if mismatches:
    mismatch_pairs = Counter((r["proposed_skill"], r["final_skill"]) for r in mismatches)
    print(f"  Top override patterns (proposed → final):")
    for (prop, fin), c in mismatch_pairs.most_common(10):
        print(f"    {prop} → {fin}: {c}")

# Year-by-year agent count check
agents_per_year_43 = Counter(r["year"] for r in seed43_records)
print(f"\n  Agents per year (seed43):")
for y in sorted(agents_per_year_43.keys()):
    n = agents_per_year_43[y]
    flag = "" if n == len(agents_43) else f"  [INCOMPLETE: expected {len(agents_43)}]"
    if y <= 3 or y >= max_year_43 - 1 or n != len(agents_43):
        print(f"    Year {y:2d}: {n} agents{flag}")
if all(agents_per_year_43[y] == len(agents_43) for y in range(1, max_year_43)):
    incomplete_year = max_year_43
    n = agents_per_year_43[max_year_43]
    if n < len(agents_43):
        print(f"    Year {max_year_43} is in-progress: {n}/{len(agents_43)} agents completed")

# Biggest EHE divergence years
if diffs:
    sorted_diffs = sorted(range(len(diffs)), key=lambda i: abs(diffs[i]), reverse=True)
    print(f"\n  Largest EHE divergences:")
    for i in sorted_diffs[:5]:
        y = i + 1
        print(f"    Year {y}: seed43={ehe_43.get(y,0):.4f}  seed42={ehe_42.get(y,0):.4f}  diff={diffs[i]:+.4f}")

print(f"\n{'=' * 70}")
print("DONE")
print("=" * 70)
