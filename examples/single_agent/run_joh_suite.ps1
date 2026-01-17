param (
    [string]$Model = "llama3.2:3b",
    [int]$Agents = 100,
    [int]$Years = 10
)

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelFolder = $Model -replace ':', '_' -replace '-', '_' -replace '\.', '_'

$BaseDir = Join-Path $ExperimentDir "results\JOH_FINAL\$ModelFolder"
$GroupBPath = Join-Path $BaseDir "Group_B"
$GroupCPath = Join-Path $BaseDir "Group_C"

Write-Host "--- JOH Master Suite: Concurrent Execution ---" -ForegroundColor Cyan
Write-Host "Model: $Model"
Write-Host "Agents: $Agents"
Write-Host "Years: $Years"
Write-Host "Output Root: $BaseDir"
Write-Host ""

# Create directories
New-Item -ItemType Directory -Force $GroupBPath | Out-Null
New-Item -ItemType Directory -Force $GroupCPath | Out-Null

Write-Host "[1/2] Launching Group B (Governance + Window)..." -ForegroundColor Yellow
Write-Host "Logs will stream plainly below..." -ForegroundColor Gray

# Logic: Run strictly SEQUENTIAL so logs are visible
Set-Location $ExperimentDir
python -u run_flood.py `
    --model $Model `
    --years $Years `
    --agents $Agents `
    --memory-engine window `
    --governance-mode strict `
    --output $GroupBPath `
    --survey-mode `
    --workers 5 `
    --verbose

Write-Host ""
Write-Host "[2/2] Launching Group C (Full: Human-Centric + Reflection)..." -ForegroundColor Yellow
Set-Location $ExperimentDir
python -u run_flood.py `
    --model $Model `
    --years $Years `
    --agents $Agents `
    --memory-engine humancentric `
    --governance-mode strict `
    --use-priority-schema `
    --output $GroupCPath `
    --survey-mode `
    --workers 5 `
    --verbose

Write-Host ""
Write-Host "--- All JOH Benchmarks Complete! ---" -ForegroundColor Green
Write-Host "Group B Logs: $GroupBPath"
Write-Host "Group C Logs: $GroupCPath"
