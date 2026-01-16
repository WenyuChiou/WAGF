# JOH Experiment 1: Macro Benchmark (Quantitative)
# Focus: Statistical metrics (Rationality Score, Adaptation Density)
# Output Directory: results/JOH_Macro
# Config: experiments/JOH_Macro/config.yaml

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ExperimentDir "experiments\JOH_Macro\config.yaml"

Write-Host "--- Starting JOH Macro Benchmark (Group C) ---" -ForegroundColor Cyan
Write-Host "Config: $ConfigPath"

# Group C: Full Cognitive Framework
# Features: 
# 1. Strict Governance (Pillar 1)
# 2. Human-Centric Memory (Pillar 2)
# 3. Priority Schema (Pillar 3)

$Model = "llama3.2:3b"
$Agents = 100
$Years = 10

Write-Host "Running Group C: Full Cognitive Framework (Macro)..."
python run_flood.py `
    --model $Model `
    --years $Years `
    --agents $Agents `
    --memory-engine humancentric `
    --governance-mode strict `
    --use-priority-schema `
    --output results/JOH_Macro `
    --survey-mode

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Macro Benchmark Complete!" -ForegroundColor Green
Write-Host " Results: results/JOH_Macro" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
