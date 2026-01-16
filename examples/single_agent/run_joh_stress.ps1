# JOH Experiment 2: Stress Test (Qualitative Case Study)
# Focus: Explainability & Trace Generation (The "Impulsive Relocator" Scenario)
# Output Directory: results/JOH_Stress
# Config: experiments/JOH_Stress/config.yaml

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ExperimentDir "experiments\JOH_Stress\config.yaml"

Write-Host "--- Starting JOH Stress Test (Micro Case Study) ---" -ForegroundColor Cyan
Write-Host "Config: $ConfigPath"

# Group C Configuration with VERBOSE logging enabled
# We need verbose logs to see the "Reject -> Hint -> Correct" dialogue

$Model = "llama3.2:3b"
$Agents = 20  # Smaller batch to focus on trace quality
$Years = 5    # Shorter duration

Write-Host "Running Stress Test: Collecting Explainability Traces..."
Write-Host "Looking for 'The Impulsive Relocator' scenario..."

python run_flood.py `
    --model $Model `
    --years $Years `
    --agents $Agents `
    --memory-engine humancentric `
    --governance-mode strict `
    --use-priority-schema `
    --output results/JOH_Stress `
    --survey-mode `
    --verbose

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Stress Test Complete!" -ForegroundColor Green
Write-Host " Results: results/JOH_Stress" -ForegroundColor Green
Write-Host "" -ForegroundColor Yellow
Write-Host " Next Steps:" -ForegroundColor Yellow
Write-Host " 1. Check raw/household_traces.jsonl for" -ForegroundColor Yellow
Write-Host "    'Intervention' entries" -ForegroundColor Yellow
Write-Host " 2. Look for 'Fixed after N retries' logs" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
