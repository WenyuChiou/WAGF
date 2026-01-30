
import pandas as pd
from pathlib import Path

file_path = Path(r"examples/multi_agent/input/initial_household data.xlsx")

try:
    # Load Excel File
    xls = pd.ExcelFile(file_path)
    print(f"Sheet names: {xls.sheet_names}")
    
    # Load Sheet0 (Case Sensitive)
    sheet_name = "Sheet0"
    # Skip the first 2 rows (header descriptions) usually found in Qualtrics
    # But first, let's look at row 0 and 1 to see the questions
    # Load raw to get question text in row 1 (index 0 is codes, index 1 is text)
    df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    
    # Load raw to get question text in row 1
    df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    
    targets = ["Q41", "Q44", "G1", "G2", "G3", "Q21_1", "Q21_2", "Q21_3", "Q21_4", "Q21_5"]
    
    print("\n--- Final Mapping Check ---")
    for i in range(len(df_raw.columns)):
        col_code = str(df_raw.iloc[0, i])
        if col_code in targets:
            col_text = str(df_raw.iloc[1, i])
            values = df_raw.iloc[2:12, i].tolist() # Top 10 values
            print(f"\nCOLUMN: [{col_code}]")
            print(f"TEXT: {col_text[:100]}...")
            print(f"VALUES: {values}")
except Exception as e:
    print(f"Error reading excel: {e}")
