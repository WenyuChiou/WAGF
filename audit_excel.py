import pandas as pd
import json

def audit_columns(file_path):
    df = pd.read_excel(file_path, sheet_name='Sheet0', header=None)
    row_1 = df.iloc[1].tolist()
    
    audit = {}
    for i, val in enumerate(row_1):
        audit[i] = str(val)
        
    with open('column_audit.json', 'w', encoding='utf-8') as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)
    
    print(f"Audit complete. Extracted {len(audit)} columns.")

if __name__ == "__main__":
    audit_columns('examples/multi_agent/input/initial_household data.xlsx')
