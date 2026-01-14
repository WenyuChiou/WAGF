import os
import numpy as np
import pandas as pd

def analyze_flood_grids(directory):
    files = [f for f in os.listdir(directory) if f.endswith('.asc')]
    results = []
    
    for f in sorted(files):
        # Extract year from filename like maxDepth2012.asc
        filename_part = f.replace('maxDepth', '').replace('.asc', '')
        year = filename_part.split('_')[0][:4]
        
        file_path = os.path.join(directory, f)
        data = np.loadtxt(file_path, skiprows=6)
        data_valid = data[data != -9999]
        
        if len(data_valid) > 0:
            results.append({
                'Year': year,
                'Max_Depth_m': round(float(np.max(data_valid)), 3),
                'Mean_Depth_m': round(float(np.mean(data_valid)), 4),
                'Flooded_Area_Fraction': round(float(np.sum(data_valid > 0.05) / len(data_valid)), 4),
                'Max_Depth_ft': round(float(np.max(data_valid) * 3.28084), 3)
            })
            
    return pd.DataFrame(results)

if __name__ == "__main__":
    input_dir = 'h:/我的雲端硬碟/github/governed_broker_framework/examples/multi_agent/input/temp_flood_data'
    df = analyze_flood_grids(input_dir)
    print("\n--- Pompton River Basin (PRB) Flood Analysis (2011-2023) ---")
    print(df.to_string(index=False))
