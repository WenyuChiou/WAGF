param (
    [string]$Model = "llama3.2:3b",
    [int]$Agents = 100,
    [int]$Years = 10,
    [int]$Runs = 3
)

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelFolder = $Model -replace ':', '_' -replace '-', '_' -replace '\.', '_'
$BaseSeed = 42

$BaseDir = Join-Path $ExperimentDir "results\JOH_FINAL\$ModelFolder"

Write-Host "--- JOH Triple-Run Suite (Scenario B: AC Metric) ---" -ForegroundColor Cyan
Write-Host "Model: $Model"
Write-Host "Agents: $Agents"
Write-Host "Years: $Years"
Write-Host "Total Runs: $Runs"
Write-Host "Output Root: $BaseDir"
Write-Host ""

Set-Location $ExperimentDir

for ($i = 1; $i -le $Runs; $i++) {
    $CurrentSeed = $BaseSeed + $i
    Write-Host ">>> Starting Run $i/$Runs (Seed: $CurrentSeed) <<<" -ForegroundColor Yellow
    
    # 1. Group A (Baseline)
    $GroupAPath = Join-Path $BaseDir "Group_A\Run_$i"
    New-Item -ItemType Directory -Force $GroupAPath | Out-Null
    Write-Host "  > [1/3] Group A (Baseline: Ungoverned via Original Code)..."
    python -u run_baseline_original.py --model $Model --seed $CurrentSeed --output $GroupAPath
    
    # 2. Group B (Governance + Window)
    $GroupBPath = Join-Path $BaseDir "Group_B\Run_$i"
    New-Item -ItemType Directory -Force $GroupBPath | Out-Null
    Write-Host "  > [2/3] Group B (Governance + Window)..."
    python -u run_flood.py --model $Model --years $Years --agents $Agents --memory-engine window --governance-mode strict --output $GroupBPath --survey-mode --workers 5 --seed $CurrentSeed
    
    # 3. Group C (Full: Tiered Memory + Priority)
    $GroupCPath = Join-Path $BaseDir "Group_C\Run_$i"
    New-Item -ItemType Directory -Force $GroupCPath | Out-Null
    Write-Host "  > [3/3] Group C (Full: Tiered + Priority)..."
    python -u run_flood.py --model $Model --years $Years --agents $Agents --memory-engine humancentric --governance-mode strict --use-priority-schema --output $GroupCPath --survey-mode --workers 5 --seed $CurrentSeed
    
    Write-Host ""
}

Write-Host "--- All Triple-Run Benchmarks Complete! ---" -ForegroundColor Green
Write-Host "Use analyze_stress.py to calculate AC metrics across these runs."
