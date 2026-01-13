# Run Memory Benchmark (Window vs Importance vs HumanCentric)
$ErrorActionPreference = "Stop"

# Configuration
$Model = "llama3.2:3b"
$Years = 10
$Agents = 50 

Write-Host "--- Starting Memory System Benchmark ---" -ForegroundColor Cyan

# 1. Window Memory (Baseline)
# Skip if already exists or force rerun? Let's assume we want fresh comparable runs.
Write-Host "[1/3] Running Window Memory (Baseline)..." -ForegroundColor Yellow
python examples/single_agent/run_flood.py --model $Model --years $Years --agents $Agents --memory-engine window --output examples/single_agent/results_window

# 2. Importance Memory
Write-Host "[2/3] Running Importance Memory (Active Retrieval)..." -ForegroundColor Yellow
python examples/single_agent/run_flood.py --model $Model --years $Years --agents $Agents --memory-engine importance --output examples/single_agent/results_importance

# 3. Human-Centric Memory (Skipped per user request)
# Write-Host "[3/3] Running Human-Centric Memory (Emotional Decay)..." -ForegroundColor Yellow
# python examples/single_agent/run_flood.py --model $Model --years $Years --agents $Agents --memory-engine humancentric --output examples/single_agent/results_humancentric

Write-Host "--- Benchmark Complete! ---" -ForegroundColor Green
Write-Host "Results are in examples/single_agent/results_*"
