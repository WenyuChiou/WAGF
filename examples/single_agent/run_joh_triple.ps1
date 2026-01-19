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
    
    # Check if run exists before running
    
    # 1. Group A (Baseline)
    $GroupAPath = Join-Path $BaseDir "Group_A\Run_$i"
    if (-not (Test-Path $GroupAPath)) {
        New-Item -ItemType Directory -Force $GroupAPath | Out-Null
        Write-Host "  > [1/3] Group A (Baseline: Ungoverned via Original Code)..."
        try {
            # Catch errors in individual runs to ensure marathon continues
            python -u run_baseline_original.py --model $Model --seed $CurrentSeed --output $GroupAPath
        }
        catch {
            Write-Host "Error in Group A Run $i" -ForegroundColor Red
        }
    }
    else {
        Write-Host "  > [1/3] Group A Run $i exists. Skipping." -ForegroundColor Gray
    }
    
    # 2. Group B (Governance + Window)
    $GroupBPath = Join-Path $BaseDir "Group_B\Run_$i"
    if (-not (Test-Path $GroupBPath)) {
        New-Item -ItemType Directory -Force $GroupBPath | Out-Null
        Write-Host "  > [2/3] Group B (Governance + Window)..."
        try {
            python -u run_flood.py --model $Model --years $Years --agents $Agents --memory-engine window --governance-mode strict --output $GroupBPath --survey-mode --workers 5 --seed $CurrentSeed
        }
        catch {
            Write-Host "Error in Group B Run $i" -ForegroundColor Red
        }
    }
    else {
        Write-Host "  > [2/3] Group B Run $i exists. Skipping." -ForegroundColor Gray
    }
    
    # 3. Group C (Full: Tiered Memory + Priority)
    $GroupCPath = Join-Path $BaseDir "Group_C\Run_$i"
    if (-not (Test-Path $GroupCPath)) {
        New-Item -ItemType Directory -Force $GroupCPath | Out-Null
        Write-Host "  > [3/3] Group C (Full: Tiered + Priority)..."
        try {
            python -u run_flood.py --model $Model --years $Years --agents $Agents --memory-engine humancentric --governance-mode strict --use-priority-schema --output $GroupCPath --survey-mode --workers 5 --seed $CurrentSeed
        }
        catch {
            Write-Host "Error in Group C Run $i" -ForegroundColor Red
        }
    }
    else {
        Write-Host "  > [3/3] Group C Run $i exists. Skipping." -ForegroundColor Gray
    }
    
    Write-Host ""
}

Write-Host "--- All Triple-Run Benchmarks Complete! ---" -ForegroundColor Green
Write-Host "Use analyze_stress.py to calculate AC metrics across these runs."
