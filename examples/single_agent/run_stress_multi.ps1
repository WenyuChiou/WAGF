param (
    [int]$Runs = 3,
    [string]$Model = "llama3.2:3b"
)

$Scenarios = @("panic", "veteran", "goldfish", "format")
$BaseSeed = 42

Write-Host "--- Starting Multi-Run Stress Test Suite (Runs=$Runs, Model=$Model) ---" -ForegroundColor Cyan

foreach ($Scenario in $Scenarios) {
    Write-Host "`n>>> Processing Scenario: [ $Scenario ]" -ForegroundColor Yellow
    
    for ($i = 1; $i -le $Runs; $i++) {
        $CurrentSeed = $BaseSeed + $i
        $OutputPath = "results/JOH_STRESS/$Scenario/Run_$i"
        
        Write-Host "    > Run $i/$Runs (Seed: $CurrentSeed) -> Output: $OutputPath"
        
        # Ensure clean start
        if (Test-Path $OutputPath) { Remove-Item -Recurse -Force $OutputPath }
        
        # Run Stress Test with population-wide injection (N=50 for speed)
        # Note: --workers 2 for stability during parallel exec
        python -u run_flood.py --model $Model --years 10 --agents 50 --memory-engine window --governance-mode strict --output $OutputPath --survey-mode --workers 2 --stress-test $Scenario --seed $CurrentSeed
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Run $i for scenario $Scenario failed!"
            exit 1
        }
    }
}

Write-Host "`n--- Multi-Run Stress Verification Complete ---" -ForegroundColor Green
Write-Host "Creating Summary Table..."
python analyze_stress.py
