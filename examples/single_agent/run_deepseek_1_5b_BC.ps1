# =============================================================================
# DeepSeek 1.5B - Groups B and C
# =============================================================================
# Purpose: Complete the 1.5B tier ABC matrix.
# =============================================================================

$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === STARTING DEEPSEEK 1.5B Group B/C RUN ===" -ForegroundColor Cyan

# Prevent PowerShell from stopping on stderr output (PerformanceTuner logs to stderr)
$ErrorActionPreference = "Continue"

$ModelTag = "deepseek-r1:1.5b"
$SafeName = "deepseek_r1_1_5b"
$Groups = @("Group_B", "Group_C")
$NumYears = 10
$BaseSeed = 401

foreach ($Group in $Groups) {
    $OutputDir = "results/JOH_FINAL/$SafeName/$Group/Run_1"
    
    if (Test-Path $OutputDir) {
        Write-Host "  [Skip] $OutputDir already exists." -ForegroundColor DarkGray
        continue
    }
    
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $LogFile = "$OutputDir\execution.log"
    Write-Host "  > Running $Group... (Logs: $LogFile)"
    
    $MemEngine = if ($Group -eq "Group_B") { "window" } else { "humancentric" }
    $GovMode = if ($Group -eq "Group_B") { "strict" } else { "disabled" }
    $UseSchema = ($Group -eq "Group_C")

    python run_flood.py `
        --model $ModelTag --years $NumYears --agents 100 --workers 1 `
        --memory-engine $MemEngine --window-size 5 --governance-mode $GovMode `
        $(if ($UseSchema) { "--use-priority-schema" }) `
        --output $OutputDir --seed $BaseSeed --num-ctx 8192 --num-predict 1536 2>&1 | Tee-Object -FilePath $LogFile

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] $Group execution failed." -ForegroundColor Red
    } else {
        Write-Host "  [OK] $Group completed successfully." -ForegroundColor Green
    }
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] === 1.5B Group B/C COMPLETE ===" -ForegroundColor Cyan
