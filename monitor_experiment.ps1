# Monitor Task-028-G Flood Verification Experiment
# Usage: .\monitor_experiment.ps1

$outputFile = "C:\Users\wenyu\AppData\Local\Temp\claude\c--Users-wenyu-Desktop-Lehigh-governed-broker-framework\tasks\bac167a.output"
$lastSize = 0
$checkInterval = 30  # seconds

Write-Host "=== Task-028-G Experiment Monitor ===" -ForegroundColor Cyan
Write-Host "Output file: $outputFile" -ForegroundColor Gray
Write-Host "Checking every ${checkInterval}s for updates..." -ForegroundColor Gray
Write-Host ""

while ($true) {
    if (Test-Path $outputFile) {
        $currentSize = (Get-Item $outputFile).Length

        if ($currentSize -ne $lastSize) {
            # File has new content
            $newLines = Get-Content $outputFile -Tail 20

            # Check for key events
            $floodEvents = $newLines | Select-String -Pattern "\[ENV\].*flood" -CaseSensitive:$false
            $systemActivation = $newLines | Select-String -Pattern "System [12]" -CaseSensitive:$false
            $crisisEvent = $newLines | Select-String -Pattern "crisis_event" -CaseSensitive:$false
            $yearProgress = $newLines | Select-String -Pattern "--- Year \d+ ---"

            # Display updates
            $timestamp = Get-Date -Format "HH:mm:ss"

            if ($yearProgress) {
                Write-Host "[$timestamp] $($yearProgress[-1])" -ForegroundColor Green
            }

            if ($floodEvents) {
                Write-Host "[$timestamp] FLOOD EVENT DETECTED!" -ForegroundColor Yellow
                $floodEvents | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
            }

            if ($crisisEvent) {
                Write-Host "[$timestamp] CRISIS MECHANISM ACTIVATED!" -ForegroundColor Magenta
                $crisisEvent | ForEach-Object { Write-Host "  $_" -ForegroundColor Magenta }
            }

            if ($systemActivation) {
                Write-Host "[$timestamp] COGNITIVE SYSTEM SWITCH!" -ForegroundColor Cyan
                $systemActivation | ForEach-Object { Write-Host "  $_" -ForegroundColor Cyan }
            }

            # Check if experiment completed
            $completed = $newLines | Select-String -Pattern "Experiment completed|finalized_at"
            if ($completed) {
                Write-Host ""
                Write-Host "=== EXPERIMENT COMPLETED ===" -ForegroundColor Green
                Write-Host $completed -ForegroundColor Green
                break
            }

            $lastSize = $currentSize
        }
    } else {
        Write-Host "Waiting for output file to be created..." -ForegroundColor Gray
    }

    Start-Sleep -Seconds $checkInterval
}

Write-Host ""
Write-Host "Monitor finished. Check results at:" -ForegroundColor Cyan
Write-Host "  examples/multi_agent/results_unified/v028_flood_test/" -ForegroundColor White
