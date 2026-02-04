# Auto-run: Wait for irrigation experiment to finish, then launch Ministral 14B Group C
# Usage: powershell -File auto_run_ministral14b_groupC.ps1
# Created: 2026-02-03

$IRRIGATION_PID = 209932
$BASE = "c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Auto-Run Monitor" -ForegroundColor Cyan
Write-Host "  Watching: PID $IRRIGATION_PID (Irrigation v11 gemma3:4b)" -ForegroundColor Cyan
Write-Host "  Next:     Ministral-3:14b Group C (Flood)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Phase 1: Wait for irrigation experiment to complete
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Waiting for irrigation experiment (PID $IRRIGATION_PID) to finish..." -ForegroundColor Yellow

while ($true) {
    try {
        $proc = Get-Process -Id $IRRIGATION_PID -ErrorAction Stop
        $elapsed = (Get-Date) - $proc.StartTime
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Still running... (elapsed: $([math]::Round($elapsed.TotalHours, 1))h)" -ForegroundColor Gray
        Start-Sleep -Seconds 120  # Check every 2 minutes
    }
    catch {
        Write-Host ""
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Irrigation experiment (PID $IRRIGATION_PID) has completed!" -ForegroundColor Green
        break
    }
}

# Phase 2: Brief cooldown (let Ollama release model memory)
Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Cooling down for 30 seconds before switching models..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Phase 3: Launch Ministral 14B Group C
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Launching: Ministral-3:14b Group C" -ForegroundColor Cyan
Write-Host "  Config: governed + humancentric + priority-schema" -ForegroundColor Cyan
Write-Host "  Output: JOH_FINAL/ministral3_14b/Group_C/Run_1/" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $BASE

python examples/single_agent/run_flood.py `
    --model "ministral-3:14b" `
    --years 10 `
    --agents 100 `
    --workers 1 `
    --governance-mode strict `
    --memory-engine humancentric `
    --window-size 5 `
    --use-priority-schema `
    --initial-agents "examples/single_agent/agent_initial_profiles.csv" `
    --output "examples/single_agent/results/JOH_FINAL/ministral3_14b/Group_C/Run_1" `
    --seed 42 `
    --num-ctx 8192 `
    --num-predict 1536

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Ministral-3:14b Group C COMPLETE" -ForegroundColor Green
Write-Host "  $(Get-Date)" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
