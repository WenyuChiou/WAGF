"""
Experiment 3 Results Analysis Script

Analyzes household_audit.jsonl for:
1. Cumulative behavior over time
2. Demographic correlations
3. Validator error rates
4. Reasoning quality
"""

import json
import os
from collections import defaultdict
from typing import Dict, List, Any
import argparse

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

def load_audit_data(filepath: str = None) -> List[Dict[str, Any]]:
    """Load household audit JSONL."""
    if filepath is None:
        filepath = os.path.join(RESULTS_DIR, "household_audit.jsonl")
    
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            records.append(json.loads(line))
    return records


def analyze_cumulative_behavior(records: List[Dict]) -> Dict:
    """Track cumulative adaptation over years."""
    yearly_actions = defaultdict(lambda: defaultdict(int))
    yearly_cumulative = defaultdict(lambda: {"insured": 0, "elevated": 0, "relocated": 0})
    
    for rec in records:
        year = rec["year"]
        decision = rec.get("decision_skill", "unknown")
        yearly_actions[year][decision] += 1
    
    # Sort by year
    years = sorted(yearly_actions.keys())
    
    print("\n=== Cumulative Behavior Analysis ===")
    print(f"{'Year':<6} {'Insurance':<12} {'Elevate':<12} {'Relocate':<12} {'Do Nothing':<12}")
    print("-" * 54)
    
    for y in years:
        actions = yearly_actions[y]
        ins = actions.get("buy_insurance", 0)
        elev = actions.get("elevate_house", 0)
        reloc = actions.get("relocate", 0)
        dn = actions.get("do_nothing", 0)
        print(f"{y:<6} {ins:<12} {elev:<12} {reloc:<12} {dn:<12}")
    
    return dict(yearly_actions)


def analyze_demographics(records: List[Dict]) -> Dict:
    """Analyze behavior by demographic group."""
    mg_actions = defaultdict(int)
    nmg_actions = defaultdict(int)
    owner_actions = defaultdict(int)
    renter_actions = defaultdict(int)
    
    for rec in records:
        decision = rec.get("decision_skill", "unknown")
        mg = rec.get("mg", False)
        tenure = rec.get("tenure", "Owner")
        
        if mg:
            mg_actions[decision] += 1
        else:
            nmg_actions[decision] += 1
        
        if tenure == "Owner":
            owner_actions[decision] += 1
        else:
            renter_actions[decision] += 1
    
    print("\n=== Demographic Analysis ===")
    print("\nMG (Marginalized Group):")
    for k, v in sorted(mg_actions.items()):
        print(f"  {k}: {v}")
    
    print("\nNMG (Non-Marginalized):")
    for k, v in sorted(nmg_actions.items()):
        print(f"  {k}: {v}")
    
    print("\nOwner:")
    for k, v in sorted(owner_actions.items()):
        print(f"  {k}: {v}")
    
    print("\nRenter:")
    for k, v in sorted(renter_actions.items()):
        print(f"  {k}: {v}")
    
    return {
        "mg": dict(mg_actions),
        "nmg": dict(nmg_actions),
        "owner": dict(owner_actions),
        "renter": dict(renter_actions)
    }


def analyze_validation(records: List[Dict]) -> Dict:
    """Analyze validator results."""
    total = len(records)
    validated = sum(1 for r in records if r.get("validated", True))
    errors = total - validated
    
    error_types = defaultdict(int)
    for rec in records:
        for err in rec.get("validation_errors", []):
            error_types[err] += 1
    
    print("\n=== Validation Analysis ===")
    print(f"Total decisions: {total}")
    print(f"Valid: {validated} ({validated/total*100:.1f}%)")
    print(f"Invalid: {errors} ({errors/total*100:.1f}%)")
    
    if error_types:
        print("\nError breakdown:")
        for err, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  {err}: {count}")
    
    return {
        "total": total,
        "valid": validated,
        "invalid": errors,
        "error_rate": errors / total if total > 0 else 0,
        "error_types": dict(error_types)
    }


def analyze_constructs(records: List[Dict]) -> Dict:
    """Analyze PMT construct distributions."""
    construct_levels = {
        "TP": defaultdict(int),
        "CP": defaultdict(int),
        "SP": defaultdict(int),
        "SC": defaultdict(int),
        "PA": defaultdict(int)
    }
    
    for rec in records:
        constructs = rec.get("constructs", {})
        for c_name in ["TP", "CP", "SP", "SC", "PA"]:
            level = constructs.get(c_name, {}).get("level", "UNKNOWN")
            construct_levels[c_name][level] += 1
    
    print("\n=== PMT Construct Distributions ===")
    for c_name, levels in construct_levels.items():
        print(f"\n{c_name}:")
        for level, count in sorted(levels.items()):
            print(f"  {level}: {count}")
    
    return {k: dict(v) for k, v in construct_levels.items()}


def main():
    parser = argparse.ArgumentParser(description="Analyze Exp3 results")
    parser.add_argument("--file", type=str, help="Path to audit JSONL file")
    args = parser.parse_args()
    
    print("Loading audit data...")
    records = load_audit_data(args.file)
    print(f"Loaded {len(records)} records")
    
    # Run all analyses
    cumulative = analyze_cumulative_behavior(records)
    demographics = analyze_demographics(records)
    validation = analyze_validation(records)
    constructs = analyze_constructs(records)
    
    # Summary
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    
    # Save summary
    summary = {
        "total_records": len(records),
        "validation": validation,
        "demographics": demographics,
        "constructs": constructs
    }
    
    summary_path = os.path.join(RESULTS_DIR, "analysis_summary.json")
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
