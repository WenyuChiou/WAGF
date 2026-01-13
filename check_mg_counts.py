
import pandas as pd
import numpy as np

def analyze_data_quality(file_path):
    df = pd.read_excel(file_path, sheet_name='Sheet0', header=None)
    headers = df.iloc[0]
    data_df = df.iloc[2:].copy()
    
    total_raw = len(data_df)
    skipped_tenure = 0
    skipped_income = 0
    skipped_both = 0
    
    valid_agents = []
    
    income_map = {
        "Less than $25,000": 1,
        "$25,000 to $29,999": 2,
        "$30,000 to $34,999": 3,
        "$35,000 to $39,999": 4,
        "$40,000 to $44,999": 5,
        "$45,000 to $49,999": 6,
        "$50,000 to $54,999": 7,
        "$55,000 to $59,999": 8,
        "$60,000 to $74,999": 9,
        "More than $74,999": 10
    }
    
    mg_count = 0
    nmg_count = 0
    
    # Track missingness in other key columns for "unprocessed" analysis
    missing_size = 0
    missing_burden = 0
    missing_vehicle = 0
    missing_generations = 0
    
    for _, row in data_df.iterrows():
        tenure_val = str(row[22]).strip().lower() if pd.notna(row[22]) else ""
        inc_label = str(row[104]).strip() if pd.notna(row[104]) else ""
        
        # 1. Strict Loading Filter
        if not tenure_val or not inc_label:
            if not tenure_val and not inc_label: skipped_both += 1
            elif not tenure_val: skipped_tenure += 1
            else: skipped_income += 1
            continue
            
        # 2. MG Classification Logic
        size_val = str(row[28]).strip().lower()
        if "more than" in size_val: hh_size = 9
        elif not size_val or size_val == "nan": 
            hh_size = 1
            missing_size += 1
        else: hh_size = int(size_val) if size_val.isdigit() else 1
        
        inc_opt = income_map.get(inc_label, 10)
        
        is_poverty = False
        if hh_size == 1 and inc_opt <= 1: is_poverty = True
        elif hh_size == 2 and inc_opt <= 2: is_poverty = True
        elif hh_size == 3 and inc_opt <= 4: is_poverty = True
        elif hh_size == 4 and inc_opt <= 5: is_poverty = True
        elif hh_size == 5 and inc_opt <= 7: is_poverty = True
        elif (hh_size == 6 or hh_size == 7) and inc_opt <= 8: is_poverty = True
        elif hh_size >= 8 and inc_opt <= 9: is_poverty = True
        
        if pd.isna(row[101]): missing_burden += 1
        is_burdened = (str(row[101]).strip().lower() == "yes")
        
        if pd.isna(row[26]): missing_vehicle += 1
        no_vehicle = (str(row[26]).strip().lower() == "no")
        
        if pd.isna(row[30]): missing_generations += 1
        
        if (int(is_poverty) + int(is_burdened) + int(no_vehicle)) >= 2:
            mg_count += 1
        else:
            nmg_count += 1
            
        valid_agents.append(row)

    print(f"=== Data Quality Report ===")
    print(f"Total Raw Samples: {total_raw}")
    print(f"Skipped (Missing Tenure): {skipped_tenure}")
    print(f"Skipped (Missing Income): {skipped_income}")
    print(f"Skipped (Missing Both):   {skipped_both}")
    print(f"---")
    print(f"Total Valid Agents:      {len(valid_agents)} ({(len(valid_agents)/total_raw):.1%})")
    print(f"Marginalized (MG):       {mg_count} ({(mg_count/len(valid_agents)):.1%})")
    print(f"Non-Marginalized (NMG):  {nmg_count} ({(nmg_count/len(valid_agents)):.1%})")
    print(f"\n=== Unprocessed Issues in Valid Samples ===")
    print(f"Missing HH Size:         {missing_size}")
    print(f"Missing Housing Burden:  {missing_burden}")
    print(f"Missing Vehicle Info:    {missing_vehicle}")
    print(f"Missing Generations:     {missing_generations}")

if __name__ == "__main__":
    analyze_data_quality("examples/multi_agent/input/initial_household data.xlsx")
