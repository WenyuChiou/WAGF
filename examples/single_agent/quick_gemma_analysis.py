"""
Quick Gemma Window Memory Analysis
"""
import pandas as pd
from pathlib import Path

# Load data
WINDOW_PATH = Path("examples/single_agent/results_window/gemma3_4b_strict/simulation_log.csv")
OLD_PATH = Path("examples/single_agent/old_results/Gemma_3_4B/flood_adaptation_simulation_log.csv")

print("=" * 60)
print("GEMMA 3 (4B) - Window Memory Analysis")
print("=" * 60)

# Load Window results
if WINDOW_PATH.exists():
    window_df = pd.read_csv(WINDOW_PATH)
    print(f"\n[Window Memory Results]")
    print(f"  Total Records: {len(window_df)}")
    print(f"  Years: {sorted(window_df['year'].unique().tolist())}")
    print(f"  Agents: {window_df['agent_id'].nunique()}")
    
    # Decision distribution across all years
    print(f"\n[Overall Decision Distribution]")
    dist = window_df['cumulative_state'].value_counts()
    for state, count in dist.items():
        pct = count / len(window_df) * 100
        print(f"  {state}: {count} ({pct:.1f}%)")
    
    # Yearly breakdown
    print(f"\n[Yearly Breakdown]")
    flood_years = [3, 4, 9]
    for year in range(1, 11):
        year_df = window_df[window_df['year'] == year]
        decisions = year_df['cumulative_state'].value_counts().to_dict()
        
        flood_marker = " [FLOOD]" if year in flood_years else ""
        print(f"\n  Year {year}{flood_marker}:")
        
        dn = decisions.get('Do Nothing', 0)
        he = decisions.get('Only House Elevation', 0)
        fi = decisions.get('Only Flood Insurance', 0)
        both = decisions.get('Both Flood Insurance and House Elevation', 0)
        reloc = decisions.get('Relocate', 0)
        
        # Active agents
        elevated = year_df[year_df['elevated'] == True].shape[0]
        relocated = year_df[year_df['relocated'] == True].shape[0]
        active = len(year_df) - relocated
        
        print(f"    Active: {active} | Elevated: {elevated} | Relocated Total: {relocated}")
        print(f"    DN: {dn} | HE: {he} | FI: {fi} | Both: {both} | Reloc: {reloc}")
    
    # Final state summary
    print(f"\n[Final Year (Year 10) Summary]")
    final_df = window_df[window_df['year'] == 10]
    elevated_final = final_df[final_df['elevated'] == True].shape[0]
    relocated_final = final_df[final_df['relocated'] == True].shape[0]
    insured_final = final_df[final_df['has_insurance'] == True].shape[0]
    print(f"  Elevated Homes: {elevated_final}")
    print(f"  Relocated Agents: {relocated_final}")
    print(f"  Currently Insured: {insured_final}")
else:
    print(f"ERROR: Window results not found at {WINDOW_PATH}")

# Compare with Old baseline
print("\n" + "=" * 60)
print("BASELINE COMPARISON")
print("=" * 60)

if OLD_PATH.exists():
    old_df = pd.read_csv(OLD_PATH)
    
    # Normalize column names
    old_df.columns = [c.lower() for c in old_df.columns]
    
    print(f"\n[Baseline Results]")
    print(f"  Total Records: {len(old_df)}")
    
    # Decision column name check
    dec_col = 'cumulative_state' if 'cumulative_state' in old_df.columns else 'decision'
    
    if dec_col in old_df.columns:
        old_dist = old_df[dec_col].value_counts()
        print(f"\n[Baseline Decision Distribution]")
        for state, count in old_dist.items():
            pct = count / len(old_df) * 100
            print(f"  {state}: {count} ({pct:.1f}%)")
        
        # Compare final relocations 
        old_final = old_df[old_df['year'] == 10]
        old_reloc = old_final[old_final[dec_col] == 'Relocate'].shape[0] if len(old_final) > 0 else 0
        
        print(f"\n[Key Comparison]")
        print(f"  Baseline Final Relocations: Check year 10 data")
        print(f"  Window Final Relocations: {relocated_final}")
else:
    print(f"  Baseline not found at {OLD_PATH}")

print("\n" + "=" * 60)
print("ANALYSIS COMPLETE")
print("=" * 60)
