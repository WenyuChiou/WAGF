"""
Exp3 Multi-Agent Simulation Analysis
Generate visualizations from audit logs
"""

import json
import os
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np

# Read audit log
audit_path = 'examples/exp3_multi_agent/results/household_audit.jsonl'
records = []
with open(audit_path, 'r', encoding='utf-8') as f:
    for line in f:
        records.append(json.loads(line))

print(f"Total records: {len(records)}")

# =============================================================================
# 1. DECISION DISTRIBUTION OVER TIME
# =============================================================================

year_decisions = defaultdict(lambda: defaultdict(int))
for r in records:
    y = r['year']
    skill = r['decision_skill']
    year_decisions[y][skill] += 1

years = sorted(year_decisions.keys())
skills = ['buy_insurance', 'elevate_house', 'buyout_program', 'relocate', 'do_nothing']
colors = ['#2ecc71', '#3498db', '#e74c3c', '#9b59b6', '#95a5a6']

fig, ax = plt.subplots(figsize=(12, 6))
bottom = np.zeros(len(years))

for skill, color in zip(skills, colors):
    values = [year_decisions[y].get(skill, 0) for y in years]
    ax.bar(years, values, bottom=bottom, label=skill.replace('_', ' ').title(), color=color)
    bottom += values

ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('Number of Decisions', fontsize=12)
ax.set_title('Decision Distribution Over 10 Years (LLM: llama3.2:3b)', fontsize=14)
ax.legend(loc='upper right')
ax.set_xticks(years)
plt.tight_layout()
plt.savefig('examples/exp3_multi_agent/results/decision_over_time.png', dpi=150)
print("Saved: decision_over_time.png")

# =============================================================================
# 2. CONSTRUCT DISTRIBUTION (TP, CP, PA)
# =============================================================================

construct_dist = {
    'TP': defaultdict(int),
    'CP': defaultdict(int),
    'PA': defaultdict(int)
}

for r in records:
    for c in ['TP', 'CP', 'PA']:
        level = r['constructs'][c]['level']
        construct_dist[c][level] += 1

fig, axes = plt.subplots(1, 3, figsize=(14, 5))

# TP
tp_levels = ['LOW', 'MODERATE', 'HIGH']
tp_values = [construct_dist['TP'][l] for l in tp_levels]
axes[0].bar(tp_levels, tp_values, color=['#27ae60', '#f39c12', '#e74c3c'])
axes[0].set_title('Threat Perception (TP)', fontsize=12)
axes[0].set_ylabel('Count')

# CP
cp_levels = ['LOW', 'MODERATE', 'HIGH']
cp_values = [construct_dist['CP'][l] for l in cp_levels]
axes[1].bar(cp_levels, cp_values, color=['#e74c3c', '#f39c12', '#27ae60'])
axes[1].set_title('Coping Perception (CP)', fontsize=12)

# PA
pa_levels = ['NONE', 'PARTIAL', 'FULL']
pa_values = [construct_dist['PA'][l] for l in pa_levels]
axes[2].bar(pa_levels, pa_values, color=['#e74c3c', '#f39c12', '#27ae60'])
axes[2].set_title('Prior Adaptation (PA)', fontsize=12)

plt.suptitle('PMT Construct Distribution (N=1,058 decisions)', fontsize=14, y=1.02)
plt.tight_layout()
plt.savefig('examples/exp3_multi_agent/results/construct_distribution.png', dpi=150)
print("Saved: construct_distribution.png")

# =============================================================================
# 3. VALIDATION WARNINGS BY YEAR
# =============================================================================

year_total = defaultdict(int)
year_warnings = defaultdict(int)
for r in records:
    y = r['year']
    year_total[y] += 1
    if not r['validated']:
        year_warnings[y] += 1

fig, ax = plt.subplots(figsize=(10, 5))
warning_rates = [year_warnings[y] / year_total[y] * 100 if year_total[y] > 0 else 0 for y in years]
bars = ax.bar(years, warning_rates, color='#e67e22')
ax.axhline(y=25, color='red', linestyle='--', label='Threshold (25%)')
ax.set_xlabel('Year', fontsize=12)
ax.set_ylabel('Validation Warning Rate (%)', fontsize=12)
ax.set_title('Validation Warning Rate Over Time', fontsize=14)
ax.set_xticks(years)
ax.legend()

for bar, rate in zip(bars, warning_rates):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, 
            f'{rate:.1f}%', ha='center', fontsize=9)

plt.tight_layout()
plt.savefig('examples/exp3_multi_agent/results/validation_warnings.png', dpi=150)
print("Saved: validation_warnings.png")

# =============================================================================
# 4. TP vs DECISION HEATMAP
# =============================================================================

tp_decision = defaultdict(lambda: defaultdict(int))
for r in records:
    tp = r['constructs']['TP']['level']
    skill = r['decision_skill']
    if skill in ['buy_insurance', 'elevate_house', 'buyout_program', 'relocate', 'do_nothing']:
        tp_decision[tp][skill] += 1

fig, ax = plt.subplots(figsize=(10, 4))
tp_levels = ['LOW', 'MODERATE', 'HIGH']
skills_short = ['buy_insurance', 'elevate_house', 'buyout_program', 'relocate', 'do_nothing']

data = [[tp_decision[tp].get(s, 0) for s in skills_short] for tp in tp_levels]
im = ax.imshow(data, cmap='YlOrRd', aspect='auto')

ax.set_xticks(range(len(skills_short)))
ax.set_xticklabels([s.replace('_', '\n') for s in skills_short], fontsize=10)
ax.set_yticks(range(len(tp_levels)))
ax.set_yticklabels(tp_levels)
ax.set_xlabel('Decision', fontsize=12)
ax.set_ylabel('Threat Perception', fontsize=12)
ax.set_title('TP Level vs Decision Choice', fontsize=14)

# Add text annotations
for i in range(len(tp_levels)):
    for j in range(len(skills_short)):
        ax.text(j, i, str(data[i][j]), ha='center', va='center', color='black', fontsize=11)

plt.colorbar(im, ax=ax, label='Count')
plt.tight_layout()
plt.savefig('examples/exp3_multi_agent/results/tp_decision_heatmap.png', dpi=150)
print("Saved: tp_decision_heatmap.png")

print("\n=== Analysis Complete ===")
print(f"Total decisions: {len(records)}")
print(f"Unique years: {len(years)}")
