$CheckIntervalSeconds = 60
$TargetProcessName = "python"
# We look for the main experiment script signature if possible, or just wait for python to idle.
# A simpler heuristic: Wait until NO python process contains "run_flood.py" with "gemma" or "llama"

Write-Host ">>> QUEUE MODE ACTIVATED <<<" -ForegroundColor Cyan
Write-Host "Monitoring for completion of existing 'run_all_joh.ps1' experiment..."

while ($true) {
    # Get all python command lines
    $RunningSims = Get-WmiObject Win32_Process -Filter "Name = 'python.exe'" | 
                   Where-Object { $_.CommandLine -like "*run_flood.py*" -and ($_.CommandLine -like "*gemma*" -or $_.CommandLine -like "*llama*") }
    
    $Count = @($RunningSims).Count
    $Timestamp = Get-Date -Format "HH:mm:ss"

    if ($Count -eq 0) {
        Write-Host "[$Timestamp] No active simulation processes detected! Experiment likely finished." -ForegroundColor Green
        Write-Host "[$Timestamp] Waiting 60s cooldown to ensure full release..." -ForegroundColor Yellow
        Start-Sleep -Seconds 60
        
        Write-Host ">>> LAUNCHING STRESS MARATHON <<<" -ForegroundColor White -BackgroundColor DarkGreen
        # Starting the Stress Test
        & ".\run_stress_marathon.ps1"
        break
    } else {
        Write-Host "[$Timestamp] Active Simulations Detected: $Count processes. Waiting..." -ForegroundColor DarkGray
        Start-Sleep -Seconds $CheckIntervalSeconds
    }
}
