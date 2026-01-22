import pandas as pd
df = pd.read_csv('results/BENCHMARK_2026/deepseek_r1_8b/Group_A/Run_1/simulation_log.csv')
for col in ['elevated', 'relocated', 'has_insurance']:
    df[col] = df[col].astype(str).str.lower() == 'true'

y1 = df[df['year']==1]
y10 = df[df['year']==10]

print(f"--- YEAR 1 ---")
print(f"Protected: {y1[(y1['elevated']) | (y1['has_insurance'])].shape[0]} / {y1.shape[0]}")
print(f"Relocated: {y1[y1['relocated']].shape[0]} / {y1.shape[0]}")

print(f"\n--- YEAR 10 ---")
print(f"Protected: {y10[(y10['elevated']) | (y10['has_insurance'])].shape[0]} / {y10.shape[0]}")
print(f"Relocated: {y10[y10['relocated']].shape[0]} / {y10.shape[0]}")

print(f"\n--- REASONING ---")
print(f"Avg Threat Len: {df['threat_appraisal'].str.len().mean():.1f} chars")
print(f"Avg Coping Len: {df['coping_appraisal'].str.len().mean():.1f} chars")
