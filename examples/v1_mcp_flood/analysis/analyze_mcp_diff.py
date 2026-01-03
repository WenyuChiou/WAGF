# -*- coding: utf-8 -*-
"""
MCP Before/After Analysis - Detailed Comparison
"""
import pandas as pd
import json
from pathlib import Path

print("=" * 70)
print("MCP Before/After Results Analysis")
print("=" * 70)

# Paths
baseline_dir = Path('../2_model_comparison/results')
mcp_fixed_dir = Path('results_fixed')

models = {
    'Llama 3.2:3b': ('Llama_3.2_3B', 'llama3.2_3b'),
    'Gemma 3:4b': ('Gemma_3_4B', 'gemma3_4b')
}

for model_name, (baseline_folder, mcp_folder) in models.items():
    print(f"\n{'='*70}")
    print(f"Model: {model_name}")
    print("=" * 70)
    
    # Load data
    baseline_path = baseline_dir / baseline_folder / 'flood_adaptation_simulation_log.csv'
    mcp_path = mcp_fixed_dir / mcp_folder / 'simulation_log.csv'
    audit_path = mcp_fixed_dir / mcp_folder / 'governed_audit.jsonl'
    
    if not baseline_path.exists() or not mcp_path.exists():
        print(f"  Data not found")
        continue
    
    baseline = pd.read_csv(baseline_path)
    mcp = pd.read_csv(mcp_path)
    
    # === 1. Basic Statistics ===
    print("\n[1] Basic Statistics")
    print("-" * 50)
    print(f"  {'Metric':<30} {'Baseline':<15} {'With MCP':<15}")
    print(f"  {'-'*60}")
    print(f"  {'Total decisions':<30} {len(baseline):<15} {len(mcp):<15}")
    
    # Final year agents
    baseline_y10 = len(baseline[baseline.year == 10])
    mcp_y10 = len(mcp[mcp.year == 10])
    print(f"  {'Agents in Year 10':<30} {baseline_y10:<15} {mcp_y10:<15}")
    
    # Relocated count
    baseline_reloc = len(baseline[baseline.decision.str.contains('Relocate', na=False)])
    mcp_reloc = len(mcp[mcp.decision.str.contains('Relocate', na=False)])
    print(f"  {'Relocations (cumulative)':<30} {baseline_reloc:<15} {mcp_reloc:<15}")
    
    # === 2. Decision Distribution Comparison ===
    print("\n[2] Decision Distribution (All Years)")
    print("-" * 50)
    
    baseline_dist = baseline.decision.value_counts(normalize=True) * 100
    mcp_dist = mcp.decision.value_counts(normalize=True) * 100
    
    all_decisions = set(baseline_dist.index) | set(mcp_dist.index)
    print(f"  {'Decision':<45} {'Baseline':<10} {'MCP':<10}")
    print(f"  {'-'*65}")
    for d in sorted(all_decisions):
        b_pct = baseline_dist.get(d, 0)
        m_pct = mcp_dist.get(d, 0)
        diff = m_pct - b_pct
        arrow = "+" if diff > 0 else "-" if diff < 0 else "="
        print(f"  {d:<45} {b_pct:>5.1f}%    {m_pct:>5.1f}%   {arrow}")
    
    # === 3. Year-by-Year Comparison ===
    print("\n[3] Year-by-Year Agent Count")
    print("-" * 50)
    print(f"  {'Year':<6} {'Baseline':<12} {'MCP':<12} {'Diff':<12}")
    for y in range(1, 11):
        b_count = len(baseline[baseline.year == y])
        m_count = len(mcp[mcp.year == y])
        diff = m_count - b_count
        print(f"  {y:<6} {b_count:<12} {m_count:<12} {diff:+d}")
    
    # === 4. Audit Analysis (MCP only) ===
    if audit_path.exists():
        print("\n[4] MCP Audit Analysis")
        print("-" * 50)
        
        traces = [json.loads(l) for l in open(audit_path, encoding='utf-8')]
        outcomes = {}
        for t in traces:
            o = t.get('outcome', 'UNKNOWN')
            outcomes[o] = outcomes.get(o, 0) + 1
        
        total = sum(outcomes.values())
        print(f"  Total decisions: {total}")
        for outcome, count in sorted(outcomes.items()):
            pct = count / total * 100
            print(f"  {outcome}: {count} ({pct:.1f}%)")
        
        consistency = outcomes.get('EXECUTED', 0) / total * 100
        retry_rate = outcomes.get('RETRY_SUCCESS', 0) / total * 100
        print(f"\n  First-pass consistency: {consistency:.1f}%")
        print(f"  Retry success rate: {retry_rate:.1f}%")
        print(f"  Total consistency: {consistency + retry_rate:.1f}%")
    
    # === 5. Key Findings ===
    print("\n[5] Key Findings")
    print("-" * 50)
    
    # Insurance reset effect
    baseline_both = baseline[baseline.decision.str.contains('Both', na=False)]
    mcp_both = mcp[mcp.decision.str.contains('Both', na=False)]
    b_both_pct = len(baseline_both) / len(baseline) * 100
    m_both_pct = len(mcp_both) / len(mcp) * 100
    
    if m_both_pct < b_both_pct:
        print(f"  * 'Both' decreased from {b_both_pct:.1f}% to {m_both_pct:.1f}%")
        print(f"    -> Insurance reset logic now working correctly")
    
    if mcp_reloc > baseline_reloc:
        print(f"  * Relocations increased from {baseline_reloc} to {mcp_reloc}")
        print(f"    -> MCP governance may encourage more decisive actions")

print("\n" + "=" * 70)
print("Analysis Complete")
print("=" * 70)
