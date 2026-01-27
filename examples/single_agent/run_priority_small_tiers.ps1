# Priority Re-run for Small-to-Mid Tiers
# Target Configuration:
# - DeepSeek-R1-1.5B: Group B (Strict), Group C (Social+Strict)
# - DeepSeek-R1-8B: Group C (Social+Strict)
# - DeepSeek-R1-14B: Group C (Social+Strict)

$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === STARTING CUSTOM PRIORITY RUN ===" -ForegroundColor Cyan

# Define the run plan
$RunPlan = @(
    @{ Tag = "deepseek-r1:1.5b"; Name = "deepseek_r1_1_5b"; Groups = @("Group_B", "Group_C") },
    @{ Tag = "deepseek-r1:8b"; Name = "deepseek_r1_8b"; Groups = @("Group_C") },
    @{ Tag = "deepseek-r1:14b"; Name = "deepseek_r1_14b"; Groups = @("Group_C") }
)

$NumYears = 10
$BaseSeed = 401
$SAPath = "examples/single_agent"

foreach ($Item in $RunPlan) {
    $ModelTag = $Item.Tag
    $ModelName = $Item.Name
    
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] >>> MODEL: $ModelName <<<" -ForegroundColor Yellow
    
    foreach ($Group in $Item.Groups) {
        $OutputDir = "examples/single_agent/results/JOH_FINAL/$ModelName/$Group/Run_1"
        
        # Clean up existing data to ensure fresh logs
        if (Test-Path $OutputDir) {
            Write-Host "  [Cleaning] Resetting $OutputDir..." -ForegroundColor Gray
            try {
                Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction Stop
            }
            catch {
                Write-Host "  [Warning] Could not remove $OutputDir. Ensure no files are open." -ForegroundColor Red
                continue 
            }
        }
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
        
        $LogFile = "$OutputDir\execution.log"
        Write-Host "  > Running $Group... (Logs: $LogFile)"
        
        $MemEngine = if ($Group -eq "Group_B") { "window" } else { "humancentric" }
        $GovMode = "strict"
        $UseSchema = ($Group -eq "Group_C")

        # Execute Simulation
        python examples/single_agent/run_flood.py `
            --model $ModelTag --years $NumYears --agents 100 --workers 1 `
            --memory-engine $MemEngine --window-size 5 --governance-mode $GovMode `
        $(if ($UseSchema) { "--use-priority-schema" }) `
            --initial-agents "$SAPath/agent_initial_profiles.csv" `
            --output $OutputDir --seed $BaseSeed --num-ctx 8192 --num-predict 1536 2>&1 | Tee-Object -FilePath $LogFile

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [ERROR] $Group execution failed." -ForegroundColor Red
        }
        else {
            Write-Host "  [OK] $Group completed successfully." -ForegroundColor Green
        }
    }
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] === PRIORITY RUN COMPLETE ===" -ForegroundColor Cyan
