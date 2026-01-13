
import pandas as pd
import sys
import os

# Mock AgentConfig and BaseAgent to run load_agents_from_excel locally
class AgentConfig:
    def __init__(self, **kwargs):
        pass

class BaseAgent:
    def __init__(self, config):
        self.fixed_attributes = {}
        self.dynamic_state = {}

# Import the actual function logic (simplified for validation)
def validate_sampling(file_path):
    df = pd.read_excel(file_path, sheet_name='Sheet0', header=None)
    data_df = df.iloc[2:].copy()
    
    all_categorized = {
        "household_owner_mg": [],
        "household_owner_nmg": [],
        "household_renter_mg": [],
        "household_renter_nmg": []
    }
    
    income_map = {
        "Less than $25,000": 1, "$25,000 to $29,999": 2, "$30,000 to $34,999": 3,
        "$35,000 to $39,999": 4, "$40,000 to $44,999": 5, "$45,000 to $49,999": 6,
        "$50,000 to $54,999": 7, "$55,000 to $59,999": 8, "$60,000 to $74,999": 9,
        "More than $74,999": 10
    }

    for idx, row in data_df.iterrows():
        tenure_val = str(row[22]).lower() if pd.notna(row[22]) else ""
        income_label = str(row[104]).strip() if pd.notna(row[104]) else ""
        if not tenure_val or not income_label: continue
        
        base_type = "household_owner" if "own" in tenure_val else "household_renter"
        
        size_val = str(row[28]).strip().lower()
        if "more than" in size_val: hh_size = 9
        else: hh_size = int(size_val) if size_val.isdigit() else 1
        
        inc_opt = income_map.get(income_label, 10)
        is_poverty = False
        if hh_size == 1 and inc_opt <= 1: is_poverty = True
        elif hh_size == 2 and inc_opt <= 2: is_poverty = True
        elif hh_size == 3 and inc_opt <= 4: is_poverty = True
        elif hh_size == 4 and inc_opt <= 5: is_poverty = True
        elif hh_size == 5 and inc_opt <= 7: is_poverty = True
        elif (hh_size == 6 or hh_size == 7) and inc_opt <= 8: is_poverty = True
        elif hh_size >= 8 and inc_opt <= 9: is_poverty = True
        
        is_burdened = (str(row[101]).strip().lower() == "yes")
        no_vehicle = (str(row[26]).strip().lower() == "no")
        is_mg = (int(is_poverty) + int(is_burdened) + int(no_vehicle)) >= 2
        
        cat = f"{base_type}_{'mg' if is_mg else 'nmg'}"
        all_categorized[cat].append(idx)

    targets = {
        "household_owner_mg": 4,
        "household_owner_nmg": 55,
        "household_renter_mg": 12,
        "household_renter_nmg": 29
    }
    
    actual = {}
    for cat, target in targets.items():
        pool = all_categorized[cat]
        actual[cat] = len(pool[:target])
        
    print(f"=== Sampling Verification (Target 100) ===")
    for cat, count in actual.items():
        print(f"{cat:20}: {count} (Target: {targets[cat]})")
    print(f"Total Loaded: {sum(actual.values())}")

if __name__ == "__main__":
    validate_sampling("examples/multi_agent/input/initial_household data.xlsx")
