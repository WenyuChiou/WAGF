param (
    [int]$Runs = 10,
    [int]$Agents = 100,
    [int]$Years = 10,
    [switch]$DryRun
)

if ($DryRun) {
    $Runs = 1
    Write-Host ">>> DRY RUN MODE ENABLED (Runs=1) <<<" -ForegroundColor Yellow
}

$SmallModels = @("deepseek-r1:8b", "llama3.2:3b", "gemma3:4b")
$LargeModels = @() 
$Scenarios = @("panic", "veteran", "goldfish", "format")
$BaseSeed = 42

Write-Host "--- Stress Test Marathon: Parallel & Sequential Execution (Base: Group C) ---" -ForegroundColor Cyan
Write-Host "Priority Models (Parallel): $($SmallModels -join ', ')"
Write-Host "Configuration: $Agents Agents, $Years Years, $Runs Runs per Scenario"
Write-Host ""

$StartTime = Get-Date

# Helper function for Stress Test Execution (to be used in background jobs)
$StressBlock = {
    param($Model, $Scenarios, $Runs, $Agents, $Years, $BaseSeed, $ExperimentDir)
    Set-Location $ExperimentDir
    $ModelFolder = $Model -replace ':', '_' -replace '-', '_' -replace '\.', '_'
    
    foreach ($Scenario in $Scenarios) {
        for ($i = 1; $i -le $Runs; $i++) {
            $CurrentSeed = $BaseSeed + $i
            $OutputPath = "results/JOH_STRESS/$ModelFolder/$Scenario/Run_$i"
            
            if (Test-Path $OutputPath) { continue }
            
            # Ensure directory exists
            New-Item -ItemType Directory -Force $OutputPath | Out-Null
            
            # Run Stress Test with Group C Baseline (Memory + Governance + Priority Schema)
            # Workers set to 4 for throughput
            python -u run_flood.py --model $Model --years $Years --agents $Agents --memory-engine humancentric --use-priority-schema --governance-mode strict --output $OutputPath --workers 4 --stress-test $Scenario --seed $CurrentSeed --memory-ranking-mode legacy
        }
    }
}

# 1. Process Small Models in Parallel
Write-Host ">>> Launching Small Models stress suite parallel..." -ForegroundColor Magenta
$Jobs = @()
foreach ($Model in $SmallModels) {
    # We pass $PSScriptRoot so the jobs know where run_flood.py is
    $Jobs += Start-Job -ScriptBlock $StressBlock -ArgumentList $Model, $Scenarios, $Runs, $Agents, $Years, $BaseSeed, $PSScriptRoot
}
Receive-Job -Job $Jobs -Wait | Out-Default
Remove-Job $Jobs

# 2. Process Large Models Sequentially
foreach ($Model in $LargeModels) {
    Write-Host "`n>>> Processing Large Model Sequentially: [ $Model ]" -ForegroundColor Magenta
    & $StressBlock -Model $Model -Scenarios $Scenarios -Runs $Runs -Agents $Agents -Years $Years -BaseSeed $BaseSeed -ExperimentDir $PSScriptRoot
}

$EndTime = Get-Date
$Duration = $EndTime - $StartTime
Write-Host "`n--- Stress Test Marathon Complete! ---" -ForegroundColor Green
Write-Host "Total Duration: $($Duration.TotalMinutes) minutes"
python analysis_tools/analyze_stress.py
