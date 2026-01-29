
import os
import sys
from pathlib import Path

# Add the directory to path so we can import get_stats
sys.path.append(str(Path("examples/single_agent/analysis/SQ1_Final_Results")))
from master_report import get_stats

models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b"]
groups = ["Group_A", "Group_B"]

print(f"{'Model':<15} {'Grp':<7} {'V1_Int':<7} {'V1_Act':<7} {'V2_Int':<7} {'V2_Act':<7} {'V3_Int':<7} {'V3_Act':<7} {'Intv_S':<7}")
print("-" * 80)

for m in models:
    for g in groups:
        stats = get_stats(m, g)
        if stats:
             m_short = m.replace("deepseek_r1_", "")
             print(f"{m_short:<15} {g:<7} {stats['V1_N']:<7} {stats['V1_Act']:<7} {stats['V2_N']:<7} {stats['V2_Act']:<7} {stats['V3_N']:<7} {stats['V3_Act']:<7} {stats['Intv_S']:<7}")
