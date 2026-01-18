param (
    [string]$Model = "llama3.2:3b",
    [int]$Agents = 100,
    [int]$Years = 10
)

$ExperimentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelFolder = $Model -replace ':', '_' -replace '-', '_' -replace '\.', '_'
$BaseSeed = 42

$BaseDir = Join-Path $ExperimentDir "results\JOH_FINAL\$ModelFolder"

Write-Host "--- Supplementing Missing Group C Runs (Run 2 & 3) ---" -ForegroundColor Cyan
Write-Host "Model: $Model"
Write-Host "Output Root: $BaseDir"

Set-Location $ExperimentDir

# Run 2 and 3 ONLY
for ($i = 2; $i -le 3; $i++) {
    $CurrentSeed = $BaseSeed + $i
    Write-Host ">>> Starting Run $i/3 (Seed: $CurrentSeed) <<<" -ForegroundColor Yellow
    
    # 3. Group C (Full: Tiered Memory + Priority)
    $GroupCPath = Join-Path $BaseDir "Group_C\Run_$i"
    if (Test-Path $GroupCPath) {
        Write-Host "  Skipping existing directory $GroupCPath"
        continue
    }
    New-Item -ItemType Directory -Force $GroupCPath | Out-Null
    
    Write-Host "  > [Group C Only] Full Human-Centric Context..."
    python -u run_flood.py --model $Model --years $Years --agents $Agents --memory-engine humancentric --governance-mode strict --use-priority-schema --output $GroupCPath --survey-mode --workers 5 --seed $CurrentSeed
    
    Write-Host ""
}
Write-Host "Done."
