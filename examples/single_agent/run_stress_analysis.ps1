param ()

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "--- JOH Stress Test Analysis ---" -ForegroundColor Cyan

# Check if analyze_stress.py exists
if (-not (Test-Path "analyze_stress.py")) {
    Write-Error "analyze_stress.py not found in $ScriptDir"
    exit 1
}

# Run the analysis
python analyze_stress.py

Write-Host ""
Write-Host "Analysis Complete." -ForegroundColor Green
