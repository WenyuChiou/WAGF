"""
Compute authoritative metrics for production v20 (78 agents × 42yr).
Outputs: v20_metrics.json + v20_metrics_report.md
"""
import csv
import json
import math
import statistics
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
RESULTS = ROOT / "examples" / "irrigation_abm" / "results" / "production_v20_42yr"
CRSS_CSV = ROOT / "ref" / "CRSS_DB" / "CRSS_DB" / "annual_baseline_time_series.csv"
OUT_DIR = pathlib.Path(__file__).parent
YEAR_OFFSET = 2018  # sim year 1 = calendar 2019
CRSS_TARGET_MAF = 5.86

# ── Load audit CSV ──
audit_rows = []
with open(RESULTS / "irrigation_farmer_governance_audit.csv", "r", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        audit_rows.append(row)

# ── Load simulation log ──
sim_rows = []
with open(RESULTS / "simulation_log.csv", "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        sim_rows.append(row)

# ── Load CRSS baseline ──
crss = {}
with open(CRSS_CSV, "r", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        y = int(row["year"])
        crss[y] = (float(row["ub_baseline_af"]) + float(row["lb_baseline_af"])) / 1e6

print(f"Loaded: {len(audit_rows)} audit rows, {len(sim_rows)} sim rows, {len(crss)} CRSS years")

# ══════════════════════════════════════════════
# 1. GOVERNANCE OUTCOMES
# ══════════════════════════════════════════════
total = len(audit_rows)
approved_first = sum(1 for r in audit_rows if r["status"] == "APPROVED" and int(r["retry_count"]) == 0)
retry_success = sum(1 for r in audit_rows if r["status"] == "APPROVED" and int(r["retry_count"]) > 0)
rejected = sum(1 for r in audit_rows if r["status"] in ("REJECTED", "REJECTED_FALLBACK"))

outcomes = {
    "total_decisions": total,
    "approved_first_attempt": approved_first,
    "approved_first_pct": round(approved_first / total * 100, 1),
    "retry_success": retry_success,
    "retry_success_pct": round(retry_success / total * 100, 1),
    "rejected": rejected,
    "rejected_pct": round(rejected / total * 100, 1),
    "total_approved": approved_first + retry_success,
    "total_approved_pct": round((approved_first + retry_success) / total * 100, 1),
}
print(f"\nOutcomes: APPROVED={outcomes['approved_first_pct']}% RETRY={outcomes['retry_success_pct']}% REJECTED={outcomes['rejected_pct']}%")

# ── Per-year outcomes ──
yearly_outcomes = {}
for r in audit_rows:
    y = int(r["year"])
    if y not in yearly_outcomes:
        yearly_outcomes[y] = {"total": 0, "approved": 0, "retry": 0, "rejected": 0}
    yearly_outcomes[y]["total"] += 1
    if r["status"] == "APPROVED" and int(r["retry_count"]) == 0:
        yearly_outcomes[y]["approved"] += 1
    elif r["status"] == "APPROVED" and int(r["retry_count"]) > 0:
        yearly_outcomes[y]["retry"] += 1
    else:
        yearly_outcomes[y]["rejected"] += 1

yearly_outcome_pcts = {}
for y in sorted(yearly_outcomes):
    d = yearly_outcomes[y]
    n = d["total"]
    yearly_outcome_pcts[y] = {
        "approved_pct": round(d["approved"] / n * 100, 1),
        "retry_pct": round(d["retry"] / n * 100, 1),
        "rejected_pct": round(d["rejected"] / n * 100, 1),
    }

# ══════════════════════════════════════════════
# 2. RULE FREQUENCIES (from failed_rules column)
# ══════════════════════════════════════════════
rule_counts = {}
for r in audit_rows:
    rules = r.get("failed_rules", "")
    if rules:
        for rule in rules.split("|"):
            rule = rule.strip()
            if rule:
                rule_counts[rule] = rule_counts.get(rule, 0) + 1

rules_sorted = sorted(rule_counts.items(), key=lambda x: -x[1])
print(f"\nRule frequencies (from audit CSV failed_rules):")
for name, count in rules_sorted:
    print(f"  {name}: {count}")

# Also check warning_rules column
warning_rule_counts = {}
for r in audit_rows:
    wrules = r.get("warning_rules", "")
    if wrules:
        for rule in wrules.split("|"):
            rule = rule.strip()
            if rule:
                warning_rule_counts[rule] = warning_rule_counts.get(rule, 0) + 1

# ══════════════════════════════════════════════
# 3. SKILL DISTRIBUTION & H_NORM
# ══════════════════════════════════════════════
SKILLS = ["increase_large", "increase_small", "maintain_demand", "decrease_small", "decrease_large"]

# 3a. Proposed (what LLM chose)
proposed = {}
for r in audit_rows:
    sk = r["proposed_skill"]
    proposed[sk] = proposed.get(sk, 0) + 1

# 3b. Approved-only (among APPROVED outcomes, what was the final_skill)
approved_skills = {}
for r in audit_rows:
    if r["status"] == "APPROVED":
        sk = r["final_skill"]
        approved_skills[sk] = approved_skills.get(sk, 0) + 1

# 3c. Executed (including REJECTED → maintain_demand fallback)
executed = {}
for r in audit_rows:
    if r["status"] == "APPROVED":
        sk = r["final_skill"]
    else:
        sk = "maintain_demand"  # fallback
    executed[sk] = executed.get(sk, 0) + 1

def compute_h_norm(dist, n_categories=5):
    total_d = sum(dist.values())
    if total_d == 0:
        return 0.0
    probs = [dist.get(s, 0) / total_d for s in SKILLS]
    H = -sum(p * math.log2(p) for p in probs if p > 0)
    return round(H / math.log2(n_categories), 4)

h_proposed = compute_h_norm(proposed)
h_approved = compute_h_norm(approved_skills)
h_executed = compute_h_norm(executed)

print(f"\nH_norm: proposed={h_proposed}, approved={h_approved}, executed={h_executed}")
print(f"Proposed: {proposed}")
print(f"Approved: {approved_skills}")
print(f"Executed: {executed}")

# ══════════════════════════════════════════════
# 4. DEMAND TRAJECTORY & CRSS ALIGNMENT
# ══════════════════════════════════════════════
yearly_demand = {}
yearly_diversion = {}
yearly_tiers = {}
yearly_mead = {}
for r in sim_rows:
    y = int(r["year"])
    req = float(r["request"])
    div = float(r["diversion"])
    tier = int(r["shortage_tier"])
    mead = float(r["lake_mead_level"])
    if y not in yearly_demand:
        yearly_demand[y] = 0
        yearly_diversion[y] = 0
        yearly_tiers[y] = []
        yearly_mead[y] = []
    yearly_demand[y] += req
    yearly_diversion[y] += div
    yearly_tiers[y].append(tier)
    yearly_mead[y].append(mead)

demand_maf = {y: yearly_demand[y] / 1e6 for y in yearly_demand}
diversion_maf = {y: yearly_diversion[y] / 1e6 for y in yearly_diversion}
years_sorted = sorted(demand_maf.keys())

demand_values = [demand_maf[y] for y in years_sorted]
mean_demand = statistics.mean(demand_values)
stdev_demand = statistics.stdev(demand_values) if len(demand_values) > 1 else 0
cov = round(stdev_demand / mean_demand * 100, 1) if mean_demand else 0

# CRSS comparison
within_10pct = 0
crss_values = []
for y in years_sorted:
    crss_val = crss.get(y, CRSS_TARGET_MAF)
    crss_values.append(crss_val)
    lower = crss_val * 0.90
    upper = crss_val * 1.10
    if lower <= demand_maf[y] <= upper:
        within_10pct += 1

crss_mean = statistics.mean(crss_values) if crss_values else CRSS_TARGET_MAF
ratio = round(mean_demand / crss_mean, 4) if crss_mean else 0

# Cold-start vs steady-state
cold_start = [demand_maf[y] for y in years_sorted if y <= 5]
steady_state = [demand_maf[y] for y in years_sorted if y > 5]
cold_cov = round(statistics.stdev(cold_start) / statistics.mean(cold_start) * 100, 1) if len(cold_start) > 1 else 0
steady_cov = round(statistics.stdev(steady_state) / statistics.mean(steady_state) * 100, 1) if len(steady_state) > 1 else 0

demand_stats = {
    "mean_maf": round(mean_demand, 3),
    "stdev_maf": round(stdev_demand, 3),
    "cov_pct": cov,
    "crss_mean_maf": round(crss_mean, 3),
    "ratio_to_crss": ratio,
    "within_10pct_count": within_10pct,
    "within_10pct_pct": round(within_10pct / len(years_sorted) * 100, 1),
    "min_maf": round(min(demand_values), 3),
    "max_maf": round(max(demand_values), 3),
    "cold_start_mean_y1_5": round(statistics.mean(cold_start), 3),
    "cold_start_cov_y1_5": cold_cov,
    "steady_state_mean_y6_42": round(statistics.mean(steady_state), 3),
    "steady_state_cov_y6_42": steady_cov,
}

print(f"\nDemand: Mean={demand_stats['mean_maf']} MAF, CoV={cov}%, Ratio={ratio}x, Within±10%={within_10pct}/{len(years_sorted)}")
print(f"Cold-start Y1-5: Mean={demand_stats['cold_start_mean_y1_5']}, CoV={cold_cov}%")
print(f"Steady Y6-42: Mean={demand_stats['steady_state_mean_y6_42']}, CoV={steady_cov}%")

# ══════════════════════════════════════════════
# 5. SHORTAGE TIER DISTRIBUTION
# ══════════════════════════════════════════════
tier_by_year = {}
mead_by_year = {}
for y in years_sorted:
    # All agents share the same tier in a given year, take the first
    tier_by_year[y] = yearly_tiers[y][0]
    mead_by_year[y] = round(yearly_mead[y][0], 1)

tier_counts = {}
for t in tier_by_year.values():
    tier_counts[t] = tier_counts.get(t, 0) + 1

print(f"\nTier distribution: {tier_counts}")
print(f"Mead range: {min(mead_by_year.values())} - {max(mead_by_year.values())} ft")

# ══════════════════════════════════════════════
# 6. CLUSTER-LEVEL BEHAVIOR
# ══════════════════════════════════════════════
# Get cluster from sim_log, match to audit by agent_id+year
agent_cluster = {}
for r in sim_rows:
    agent_cluster[(r["agent_id"], int(r["year"]))] = r["cluster"]

cluster_proposed = {}
cluster_executed = {}
cluster_count = {}
for r in audit_rows:
    key = (r["agent_id"], int(r["year"]))
    cl = agent_cluster.get(key, "unknown")
    if cl not in cluster_proposed:
        cluster_proposed[cl] = {}
        cluster_executed[cl] = {}
        cluster_count[cl] = 0
    cluster_count[cl] += 1

    # Proposed
    psk = r["proposed_skill"]
    cluster_proposed[cl][psk] = cluster_proposed[cl].get(psk, 0) + 1

    # Executed
    if r["status"] == "APPROVED":
        esk = r["final_skill"]
    else:
        esk = "maintain_demand"
    cluster_executed[cl][esk] = cluster_executed[cl].get(esk, 0) + 1

cluster_stats = {}
for cl in sorted(cluster_count):
    n = cluster_count[cl]
    inc_p = sum(cluster_proposed[cl].get(s, 0) for s in ["increase_large", "increase_small"])
    maint_p = cluster_proposed[cl].get("maintain_demand", 0)
    dec_p = sum(cluster_proposed[cl].get(s, 0) for s in ["decrease_large", "decrease_small"])
    inc_e = sum(cluster_executed[cl].get(s, 0) for s in ["increase_large", "increase_small"])
    maint_e = cluster_executed[cl].get("maintain_demand", 0)
    dec_e = sum(cluster_executed[cl].get(s, 0) for s in ["decrease_large", "decrease_small"])
    cluster_stats[cl] = {
        "n": n,
        "n_agents": n // 42,  # assuming 42 years
        "proposed_increase_pct": round(inc_p / n * 100, 1),
        "proposed_maintain_pct": round(maint_p / n * 100, 1),
        "proposed_decrease_pct": round(dec_p / n * 100, 1),
        "executed_increase_pct": round(inc_e / n * 100, 1),
        "executed_maintain_pct": round(maint_e / n * 100, 1),
        "executed_decrease_pct": round(dec_e / n * 100, 1),
    }
    print(f"\n{cl} (n={n}, agents={n//42}):")
    print(f"  Proposed: inc={inc_p/n*100:.0f}% maint={maint_p/n*100:.0f}% dec={dec_p/n*100:.0f}%")
    print(f"  Executed: inc={inc_e/n*100:.0f}% maint={maint_e/n*100:.0f}% dec={dec_e/n*100:.0f}%")

# ══════════════════════════════════════════════
# 7. CEILING TRIGGER × TIER CROSS-ANALYSIS
# ══════════════════════════════════════════════
ceiling_by_year = {}
for r in audit_rows:
    rules = r.get("failed_rules", "")
    y = int(r["year"])
    if "demand_ceiling_stabilizer" in rules:
        ceiling_by_year[y] = ceiling_by_year.get(y, 0) + 1

ceiling_tier_cross = {}
for y in sorted(ceiling_by_year):
    tier = tier_by_year.get(y, -1)
    ceiling_tier_cross[y] = {"ceiling_triggers": ceiling_by_year[y], "tier": tier}

print(f"\nCeiling triggers by year (top 10):")
for y in sorted(ceiling_by_year, key=lambda x: -ceiling_by_year[x])[:10]:
    print(f"  Y{y} (Tier {tier_by_year.get(y, '?')}): {ceiling_by_year[y]} triggers")

# ══════════════════════════════════════════════
# 8. CONSTRUCT COVERAGE
# ══════════════════════════════════════════════
valid_labels = {"VL", "L", "M", "H", "VH"}
wsa_valid = sum(1 for r in audit_rows if r.get("construct_WSA_LABEL", "").upper() in valid_labels)
aca_valid = sum(1 for r in audit_rows if r.get("construct_ACA_LABEL", "").upper() in valid_labels)
construct_coverage = {
    "wsa_valid_pct": round(wsa_valid / total * 100, 1),
    "aca_valid_pct": round(aca_valid / total * 100, 1),
}
print(f"\nConstruct coverage: WSA={construct_coverage['wsa_valid_pct']}%, ACA={construct_coverage['aca_valid_pct']}%")

# ══════════════════════════════════════════════
# ASSEMBLE & SAVE
# ══════════════════════════════════════════════
metrics = {
    "experiment": {
        "model": "gemma3:4b",
        "seed": 42,
        "agents": 78,
        "years": 42,
        "total_decisions": total,
        "finalized": "2026-02-08T22:45:06",
    },
    "governance_outcomes": outcomes,
    "rule_frequencies": dict(rules_sorted),
    "warning_rule_frequencies": warning_rule_counts,
    "skill_distribution": {
        "proposed": proposed,
        "approved_only": approved_skills,
        "executed_with_fallback": executed,
    },
    "h_norm": {
        "proposed": h_proposed,
        "approved_only": h_approved,
        "executed_with_fallback": h_executed,
    },
    "demand_trajectory": demand_stats,
    "yearly_demand_maf": {str(y): round(demand_maf[y], 3) for y in years_sorted},
    "yearly_diversion_maf": {str(y): round(diversion_maf[y], 3) for y in years_sorted},
    "yearly_outcomes": {str(y): yearly_outcome_pcts[y] for y in sorted(yearly_outcome_pcts)},
    "shortage_tiers": {
        "distribution": {str(k): v for k, v in tier_counts.items()},
        "by_year": {str(y): tier_by_year[y] for y in years_sorted},
        "mead_by_year": {str(y): mead_by_year[y] for y in years_sorted},
    },
    "cluster_behavior": cluster_stats,
    "construct_coverage": construct_coverage,
    "ceiling_tier_cross": {str(y): v for y, v in ceiling_tier_cross.items()},
}

# Save JSON
json_path = OUT_DIR / "v20_metrics.json"
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)
print(f"\n[OK] Saved: {json_path}")

# ══════════════════════════════════════════════
# GENERATE REPORT
# ══════════════════════════════════════════════
report_lines = []
report_lines.append("# v20 Production Metrics Report")
report_lines.append(f"\n**Experiment**: {metrics['experiment']['agents']} agents × {metrics['experiment']['years']} years, {metrics['experiment']['model']}, seed {metrics['experiment']['seed']}")
report_lines.append(f"**Total decisions**: {total}")
report_lines.append(f"**Finalized**: {metrics['experiment']['finalized']}")

report_lines.append("\n## 1. Governance Outcomes")
report_lines.append(f"| Category | Count | % |")
report_lines.append(f"|----------|-------|---|")
report_lines.append(f"| Approved (1st attempt) | {approved_first} | {outcomes['approved_first_pct']}% |")
report_lines.append(f"| Retry Success | {retry_success} | {outcomes['retry_success_pct']}% |")
report_lines.append(f"| Rejected | {rejected} | {outcomes['rejected_pct']}% |")
report_lines.append(f"| **Total Approved** | **{approved_first + retry_success}** | **{outcomes['total_approved_pct']}%** |")

report_lines.append("\n## 2. Rule Frequencies (ERROR triggers)")
report_lines.append(f"| Rule | Triggers |")
report_lines.append(f"|------|----------|")
for name, count in rules_sorted:
    report_lines.append(f"| {name} | {count} |")

if warning_rule_counts:
    report_lines.append("\n### Warning Rules")
    for name, count in sorted(warning_rule_counts.items(), key=lambda x: -x[1]):
        report_lines.append(f"| {name} | {count} |")

report_lines.append("\n## 3. Behavioral Diversity (H_norm)")
report_lines.append(f"| Version | H_norm | Interpretation |")
report_lines.append(f"|---------|--------|----------------|")
report_lines.append(f"| Proposed (LLM choice) | {h_proposed} | What agents wanted to do |")
report_lines.append(f"| Approved only | {h_approved} | Among those that passed governance |")
report_lines.append(f"| Executed (with fallback) | {h_executed} | What actually happened |")

report_lines.append("\n### Skill Distribution")
report_lines.append(f"| Skill | Proposed | Approved | Executed |")
report_lines.append(f"|-------|----------|----------|----------|")
for sk in SKILLS:
    p = proposed.get(sk, 0)
    a = approved_skills.get(sk, 0)
    e = executed.get(sk, 0)
    report_lines.append(f"| {sk} | {p} ({p/total*100:.1f}%) | {a} ({a/max(sum(approved_skills.values()),1)*100:.1f}%) | {e} ({e/total*100:.1f}%) |")

report_lines.append("\n## 4. Demand Trajectory")
report_lines.append(f"| Metric | Value |")
report_lines.append(f"|--------|-------|")
for k, v in demand_stats.items():
    report_lines.append(f"| {k} | {v} |")

report_lines.append("\n## 5. Shortage Tier Distribution")
report_lines.append(f"| Tier | Years |")
report_lines.append(f"|------|-------|")
for t in sorted(tier_counts):
    report_lines.append(f"| Tier {t} | {tier_counts[t]} |")
report_lines.append(f"\nLake Mead range: {min(mead_by_year.values())} - {max(mead_by_year.values())} ft")

report_lines.append("\n## 6. Cluster Behavior")
report_lines.append(f"| Cluster | Agents | Proposed inc% | Proposed maint% | Executed inc% | Executed maint% |")
report_lines.append(f"|---------|--------|---------------|-----------------|---------------|-----------------|")
for cl, st in cluster_stats.items():
    report_lines.append(f"| {cl} | {st['n_agents']} | {st['proposed_increase_pct']}% | {st['proposed_maintain_pct']}% | {st['executed_increase_pct']}% | {st['executed_maintain_pct']}% |")

report_lines.append("\n## 7. Construct Coverage")
report_lines.append(f"- WSA valid labels: {construct_coverage['wsa_valid_pct']}%")
report_lines.append(f"- ACA valid labels: {construct_coverage['aca_valid_pct']}%")

report_lines.append("\n## 8. Ceiling × Tier Cross-Analysis")
report_lines.append(f"| Year | Tier | Ceiling Triggers |")
report_lines.append(f"|------|------|-----------------|")
for y in sorted(ceiling_by_year, key=lambda x: -ceiling_by_year[x])[:15]:
    report_lines.append(f"| Y{y} | {tier_by_year.get(y, '?')} | {ceiling_by_year[y]} |")

md_path = OUT_DIR / "v20_metrics_report.md"
with open(md_path, "w", encoding="utf-8") as f:
    f.write("\n".join(report_lines) + "\n")
print(f"[OK] Saved: {md_path}")
