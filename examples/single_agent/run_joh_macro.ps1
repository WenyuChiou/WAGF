# JOH Experiment 1: Macro Benchmark (Quantitative)
# Focus: Statistical metrics (Rationality Score, Adaptation Density)
# Output Directory: results/JOH_Macro

$Model = "llama3.2:3b"
$Agents = 100
$Years = 10

Write-Host "--- Starting JOH Macro Benchmark (Group C) ---" -ForegroundColor Cyan

# Group C: Full Cognitive Framework
# Features: 
# 1. Strict Governance (Pillar 1)
# 2. Human-Centric Memory (Pillar 2)
# 3. Priority Schema (Pillar 3) - NEW via --use-priority-schema
Write-Host "Running Group C: Full Cognitive Framework..."
python run_flood.py --model $Model --years $Years --agents $Agents --memory-engine humancentric --governance-mode strict --use-priority-schema --output results/JOH_Macro --survey-mode

Write-Host "Macro Benchmark Complete. Results saved to results/JOH_Macro" -ForegroundColor Green
