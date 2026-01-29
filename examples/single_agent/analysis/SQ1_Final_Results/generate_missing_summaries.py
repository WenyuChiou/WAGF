
import json
import os
from pathlib import Path

def generate_missing_summaries():
    root = Path("examples/single_agent/results/JOH_FINAL")
    models = ["deepseek_r1_1_5b", "deepseek_r1_8b", "deepseek_r1_14b", "deepseek_r1_32b"]
    groups = ["Group_A"] # Only backfill Group A which has no governance logs

    for m in models:
        for g in groups:
            run_dir = root / m / g / "Run_1"
            if not run_dir.exists(): continue
            
            summary_path = run_dir / "governance_summary.json"
            if not summary_path.exists():
                print(f"Generating placeholder summary for {m}/{g}...")
                
                # Default "clean" summary for Control Group
                data = {
                    "total_interventions": 0,
                    "outcome_stats": {
                        "retry_success": 0,
                        "retry_exhausted": 0,
                        "parse_errors": 0
                    },
                    "rule_frequency": {
                        "relocation_threat_low": 0,
                        "elevation_threat_low": 0,
                        "extreme_threat_block": 0,
                        "builtin_high_tp_cp_action": 0
                    }
                }
                
                with open(summary_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

if __name__ == "__main__":
    generate_missing_summaries()
