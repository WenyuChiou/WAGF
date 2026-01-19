param (
    [int]$Agents = 100,
    [int]$Years = 10
)

# Configuration
$TargetRuns = 5
$GemmaGroupCTarget = 6 # Special case for Gemma Group C to include "Run 2" and preserve existing 13456

Write-Host "--- JOH Extension: Increasing Sample Size (N=5) ---" -ForegroundColor Cyan
Write-Host "This script will ensure all models have at least 5 runs."

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ExperimentDir

# 1. Extend Llama 3.2 3B to 5 Runs
Write-Host "`n>>> Processing Llama 3.2 3B (Target: $TargetRuns Runs) <<<" -ForegroundColor Yellow
.\run_joh_triple.ps1 -Model "llama3.2:3b" -Agents $Agents -Years $Years -Runs $TargetRuns

# 2. Fix Gemma 3 4B - Group C Missing Run 2
Write-Host "`n>>> Fixing Gemma 3 4B (Group C Run 2) <<<" -ForegroundColor Yellow
$GemmaDir = Join-Path $ExperimentDir "results\JOH_FINAL\gemma3_4b"
$CurrentSeed = 42 + 2 # Seed for Run 2
$GroupCPath = Join-Path $GemmaDir "Group_C\Run_2"

if (-not (Test-Path $GroupCPath)) {
    New-Item -ItemType Directory -Force $GroupCPath | Out-Null
    Write-Host "Running Gemma Group C Run 2..."
    python -u run_flood.py --model "gemma3:4b" --years $Years --agents $Agents --memory-engine humancentric --governance-mode strict --use-priority-schema --output $GroupCPath --survey-mode --workers 5 --seed $CurrentSeed
}
else {
    Write-Host "Gemma Group C Run 2 already exists."
}

Write-Host "`n--- Extension Complete ---" -ForegroundColor Green
Write-Host "Llama now has $TargetRuns runs."
Write-Host "Gemma Group C gap filled."
