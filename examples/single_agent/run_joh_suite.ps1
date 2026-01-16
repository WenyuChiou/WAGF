param (
    [string]$Model = "llama3.2:3b",
    [int]$Agents = 100,
    [int]$Years = 10
)

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelFolder = $Model -replace ':', '_' -replace '-', '_' -replace '\.', '_'

$BaseDir = Join-Path $ExperimentDir "results\JOH\$ModelFolder"
$GroupBPath = Join-Path $BaseDir "baseline"
$GroupCPath = Join-Path $BaseDir "full"

Write-Host "--- JOH Master Suite: Concurrent Execution ---" -ForegroundColor Cyan
Write-Host "Model: $Model"
Write-Host "Agents: $Agents"
Write-Host "Years: $Years"
Write-Host "Output Root: $BaseDir"
Write-Host ""

# Create directories
New-Item -ItemType Directory -Force $GroupBPath | Out-Null
New-Item -ItemType Directory -Force $GroupCPath | Out-Null

Write-Host "[1/2] Launching Group B (Baseline: Window Memory)..." -ForegroundColor Yellow
$JobB = Start-Job -ScriptBlock {
    param($Model, $Agents, $Years, $GroupBPath, $ExperimentDir)
    Set-Location $ExperimentDir
    python run_flood.py `
        --model $Model `
        --years $Years `
        --agents $Agents `
        --memory-engine window `
        --governance-mode strict `
        --output $GroupBPath `
        --survey-mode `
        --workers 5
} -ArgumentList $Model, $Agents, $Years, $GroupBPath, $ExperimentDir

Write-Host "[2/2] Launching Group C (Full: Human-Centric + Reflection)..." -ForegroundColor Yellow
$JobC = Start-Job -ScriptBlock {
    param($Model, $Agents, $Years, $GroupCPath, $ExperimentDir)
    Set-Location $ExperimentDir
    python run_flood.py `
        --model $Model `
        --years $Years `
        --agents $Agents `
        --memory-engine humancentric `
        --governance-mode strict `
        --use-priority-schema `
        --output $GroupCPath `
        --survey-mode `
        --workers 5
} -ArgumentList $Model, $Agents, $Years, $GroupCPath, $ExperimentDir

Write-Host ""
Write-Host "Both experiments are running in the background." -ForegroundColor Green
Write-Host "Use 'Get-Job' to check status or 'Receive-Job' to see output." -ForegroundColor DarkGray
Write-Host "Group B Logs: $GroupBPath"
Write-Host "Group C Logs: $GroupCPath"
Write-Host ""
Write-Host "Monitoring starting... (Ctrl+C to stop monitoring, jobs will continue)"
Write-Host "=========================================="

while ($JobB.State -eq 'Running' -or $JobC.State -eq 'Running') {
    $date = Get-Date -Format "HH:mm:ss"
    Write-Host "[$date] Group B: $($JobB.State) | Group C: $($JobC.State)"
    Start-Sleep -Seconds 30
}

Write-Host "--- All JOH Benchmarks Complete! ---" -ForegroundColor Green
