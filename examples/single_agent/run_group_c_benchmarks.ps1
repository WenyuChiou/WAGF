# Re-run Group C Benchmarks in STRICT MODE
# Goal: Measure Intervention Rate for 8B and 14B models.
# If they are smart (SQ3 Hypothesis), Intv Rate should be near 0%.

# 1. DeepSeek-R1-8B (Mid-Tier)
Write-Host "[BENCHMARK] Starting deepseek_r1_8b (Strict Mode)..."
python examples/single_agent/run_flood.py `
    --model deepseek_r1_8b `
    --years 10 `
    --agents 100 `
    --governance-mode strict `
    --output examples/single_agent/results/JOH_FINAL/deepseek_r1_8b/Group_C `
    --workers 4

# 2. DeepSeek-R1-14B (High-Tier)
Write-Host "[BENCHMARK] Starting deepseek_r1_14b (Strict Mode)..."
python examples/single_agent/run_flood.py `
    --model deepseek_r1_14b `
    --years 10 `
    --agents 100 `
    --governance-mode strict `
    --output examples/single_agent/results/JOH_FINAL/deepseek_r1_14b/Group_C `
    --workers 4

Write-Host "[SUCCESS] All Benchmark Baselines Complete."
