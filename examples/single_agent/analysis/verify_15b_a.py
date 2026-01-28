
import sys
import os
sys.path.append(os.getcwd())
from examples.single_agent.analysis.master_report import get_stats

stats = get_stats("deepseek_r1_1_5b", "Group_A")
print(stats)
