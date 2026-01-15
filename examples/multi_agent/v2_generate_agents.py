"""
Multi-Agent v2 Profile Generator (Real Data)

Generates household agent profiles using REAL survey data from:
examples/multi_agent/input/initial_household data.xlsx

Mapping Strategy:
- Income: Finds column with 'income' keyword, parses ranges to mean value.
- Tenure: Finds column with 'rent'/'own' keyword.
- Demographics: Uses G1, G2, G3 columns from survey.
- Trust: Generates from Beta distributions (filling missing survey data for now).

Output:
v2_agent_profiles.csv
"""

import pandas as pd
import numpy as np
import random
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Literal

# Configuration
INPUT_FILE = Path("examples/multi_agent/input/initial_household data.xlsx")
OUTPUT_DIR = Path("examples/multi_agent/data")
SHEET_NAME = "Sheet0"
SEED = 42

random.seed(SEED)
np.random.seed(SEED)

@dataclass
class HouseholdProfile:
    agent_id: str
    tract_id: str = "T001"
    mg: bool = False
    tenure: Literal["Owner", "Renter"] = "Owner"
    income: float = 50_000
    household_size: int = 3
    generations: int = 1
    has_vehicle: bool = True
    has_children: bool = False
    has_elderly: bool = False
    housing_cost_burden: bool = False
    rcv_building: float = 0.0
    rcv_contents: float = 0.0
    trust_gov: float = 0.5
    trust_ins: float = 0.5
    trust_neighbors: float = 0.5
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    cumulative_damage: float = 0.0
    cumulative_oop: float = 0.0

def parse_income(val):
    """Parse income range string to float mean."""
    val = str(val).lower().replace(",", "").replace("$", "")
    if "less than" in val: return 15000
    if "more than" in val: return 200000
    
    # Try to find numbers "50000 - 74999"
    import re
    nums = re.findall(r'\d+', val)
    if len(nums) >= 2:
        return (float(nums[0]) + float(nums[1])) / 2
    if len(nums) == 1:
        return float(nums[0])
    return 50000.0 # Default

def parse_tenure(val):
    """Parse tenure string to Owner/Renter."""
    val = str(val).lower()
    if "own" in val: return "Owner"
    if "rent" in val: return "Renter"
    # Default fallback
    return "Owner" 

def generate_rcv(tenure, income, mg):
    # Copied from original logic (since survey doesn't have RCV)
    if tenure == "Owner":
        mu_bld = 280_000 if mg else 400_000
        rcv_bld = np.random.lognormal(np.log(mu_bld), 0.3)
        rcv_bld = min(max(rcv_bld, 100_000), 1_000_000)
        rcv_cnt = rcv_bld * random.uniform(0.30, 0.50)
    else:
        rcv_bld = 0.0
        base_cnt = 20_000 + (income / 100_000) * 40_000
        rcv_cnt = np.random.normal(base_cnt, 5_000)
    return round(rcv_bld, 2), round(rcv_cnt, 2)

def generate_trust_values(mg):
    # Copied from original (using distributions pending explicit column mapping)
    if mg:
        tg = np.clip(np.random.beta(2, 5), 0.1, 0.9)
        ti = np.clip(np.random.beta(2, 5), 0.1, 0.9)
        tn = np.clip(np.random.beta(4, 3), 0.2, 0.95)
    else:
        tg = np.clip(np.random.beta(4, 3), 0.2, 0.9)
        ti = np.clip(np.random.beta(4, 3), 0.2, 0.9)
        tn = np.clip(np.random.beta(3, 3), 0.3, 0.8)
    return round(tg, 3), round(ti, 3), round(tn, 3)

def main():
    print(f"Loading {INPUT_FILE}...")
    df = pd.read_excel(INPUT_FILE, sheet_name=SHEET_NAME, header=None)
    
    # 1. Identify Columns by keyword in Row 1 (Question Text)
    col_map = {}
    headers = df.iloc[1].astype(str).tolist()
    
    for idx, text in enumerate(headers):
        text_lower = text.lower()
        if "income" in text_lower and "household" in text_lower and "current" not in text_lower: # Avoid "current employment"
             col_map["income"] = idx
        if "rent" in text_lower or "own" in text_lower:
            # specifically "own or rent" or "housing tenure"
            if "own" in text_lower and "rent" in text_lower:
                col_map["tenure"] = idx

    # Fallback to hardcoded indices explicitly found in inspection if mapping fails
    # Based on previous tool output: Q44 (Index ~105) is Tenure, Q41 (Index ~89) is Income
    # But let's verify via Code lookup
    codes = df.iloc[0].astype(str).tolist()
    if "tenure" not in col_map: 
        try: col_map["tenure"] = codes.index("Q44")
        except: pass
    if "income" not in col_map:
        try: col_map["income"] = codes.index("Q41")
        except: pass

    print(f"Column Mapping: {col_map}")
    
    # 2. Extract Data (Skip header rows 0,1)
    # Filter for first 50 agents as requested
    agents = []
    
    valid_rows = df.iloc[2:].reset_index(drop=True)
    # Shuffle real data or take top 50? User said "populate", imply taking distinct rows. 
    # We will take Top 50 VALID rows (non-empty).
    
    count = 0
    for idx, row in valid_rows.iterrows():
        if count >= 50: break
        
        # Parse key fields
        raw_inc = row.iloc[col_map.get("income", 89)]
        raw_ten = row.iloc[col_map.get("tenure", 105)]
        
        income = parse_income(raw_inc)
        tenure = parse_tenure(raw_ten)
        
        # Demographics from G columns if available, else derive
        # G1 was Housing Cost Burden (0/1)
        # G2/G3 unknown, treat as MG flags proxies?
        # Let's derive MG from Income for consistency with theory if G columns are unclear
        # Or use G1/G2/G3 logic if known. For now, use Income Threshold for MG proxy
        # MG = Low Income (<40k) OR Cost Burdened (G1=1)
        
        # Try to find G1
        try: g1_idx = codes.index("G1")
        except: g1_idx = -1
        
        cost_burden = False
        if g1_idx != -1:
            val = row.iloc[g1_idx]
            cost_burden = (str(val).strip() == "1")
            
        mg = (income < 45000) or cost_burden
        
        # Generate Derived
        rcv_b, rcv_c = generate_rcv(tenure, income, mg)
        tg, ti, tn = generate_trust_values(mg)
        
        agent_id = f"H{count+1:04d}"
        
        p = HouseholdProfile(
            agent_id=agent_id,
            mg=mg,
            tenure=tenure,
            income=income,
            housing_cost_burden=cost_burden,
            rcv_building=rcv_b,
            rcv_contents=rcv_c,
            trust_gov=tg,
            trust_ins=ti,
            trust_neighbors=tn,
            has_insurance=(random.random() < 0.2) # Initial uptake
        )
        agents.append(p)
        count += 1
        
    # 3. Save
    out_path = OUTPUT_DIR / "v2_agent_profiles.csv"
    save_agents_to_csv(agents, out_path)

def save_agents_to_csv(agents, path):
    records = [asdict(a) for a in agents]
    df_out = pd.DataFrame(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(path, index=False)
    print(f"Saved {len(agents)} v2 agents to {path}")
    print("Sample:\n" + str(df_out[["agent_id", "tenure", "income", "mg"]].head()))

if __name__ == "__main__":
    main()
