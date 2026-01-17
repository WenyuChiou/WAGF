param (
    [string]$Scenario = "veteran",
    [string]$Model = "llama3.2:3b",
    [int]$Agents = 1,  # Focused tracing on targeted agents
    [int]$Years = 10
)

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "--- JOH Stress Test: Case Study Extraction ---" -ForegroundColor Cyan
Write-Host "Scenario: $Scenario"
Write-Host "Model: $Model"
Write-Host ""

# Run with VERBOSE to capture the "Reject -> Hint -> Correct" loop in stdout
$ModelDir = $Model -replace ":", "_" -replace "-", "_" -replace "\.", "_"
$ScenarioOutput = Join-Path "results\JOH_STRESS" "$Scenario\$ModelDir"
python run_flood.py `
    --model $Model `
    --years $Years `
    --agents $Agents `
    --memory-engine humancentric `
    --governance-mode strict `
    --use-priority-schema `
    --output $ScenarioOutput `
    --stress-test $Scenario `
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
