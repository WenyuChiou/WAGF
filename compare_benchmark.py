import json
import os
from pathlib import Path

MODELS = ["gemma3_4b", "llama3.2_3b", "deepseek-r1_1.5b", "gpt-oss_latest"]
LEGACY_DIR = "results_legacy_v2"
NEW_DIR = "results"

def load_summary(path):
if not os.path.exists(path):
return None
try:
with open(path, 'r', encoding='utf-8') as f:
return json.load(f)
except:
return None

def get_stats(data):
if not data: return {}
    
# Try 'default' or 'household'
agent_data = data.get('agent_types', {}).get('default') or data.get('agent_types', {}).get('household')
if not agent_data: return {}
    
total = agent_data.get('total', 1)
decisions = agent_data.get('decisions', {})
    
return {
    "relocate": decisions.get('relocate', 0) / total * 100,
    "do_nothing": decisions.get('do_nothing', 0) / total * 100,
    "insurance": decisions.get('buy_insurance', 0) / total * 100,
    "elevate": decisions.get('elevate_house', 0) / total * 100,
    "total": total
}

print("# Phase 16: Comparative Benchmark Results\n")
print("| Model | Metric | Before (Legacy) | After (Unified) | Delta |")
print("|---|---|---|---|---|")

for model in MODELS:
legacy_path = f"{LEGACY_DIR}/{model}/audit_summary.json"
new_path = f"{NEW_DIR}/{model}/audit_summary.json"
    
s_old = get_stats(load_summary(legacy_path))
s_new = get_stats(load_summary(new_path))
    
# metrics = ["relocate", "do_nothing", "insurance", "elevate"]
metrics = {
    "Relocation %": "relocate", 
    "Do Nothing %": "do_nothing",
    "Insurance %": "insurance",
    "Elevation %": "elevate"
}
    
first_row = True
for label, key in metrics.items():
val_old = s_old.get(key, -1)
val_new = s_new.get(key, -1)
        
# Formatting
str_old = f"{val_old:.1f}%" if val_old >= 0 else "N/A"
str_new = f"{val_new:.1f}%" if val_new >= 0 else "N/A"
        
delta = ""
if val_old >= 0 and val_new >= 0:
d = val_new - val_old
delta = f"{d:+.1f}%"
        
prefix = f"**{model}**" if first_row else ""
print(f"| {prefix} | {label} | {str_old} | {str_new} | {delta} |")
first_row = False
print("| | | | | |") # Separator row
