
# Resume Governance Simulations (JOH_FINAL)
# This script resumes the universal reset plan from the point of failure (8B Group B)

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === RESUMING GOVERNANCE SIMULATIONS ===" -ForegroundColor Cyan

$RunPlan = @(
    @{ Tag = "deepseek-r1:8b";   Name = "deepseek_r1_8b";   Groups = @("Group_B", "Group_C") },
    @{ Tag = "deepseek-r1:14b";  Name = "deepseek_r1_14b";  Groups = @("Group_B", "Group_C") }
)

$SAPath = "examples/single_agent"

:outer foreach ($Item in $RunPlan) {
    foreach ($Group in $Item.Groups) {
        $ModelTag = $Item.Tag
        $ModelName = $Item.Name
        $OutputDir = "$SAPath/results/JOH_FINAL/$ModelName/$Group/Run_1"
        
        Write-Host ">>> CHECKING: $ModelName | $Group <<<" -ForegroundColor Yellow
        
        # 0. SMART RESUME: Skip if simulation_log.csv exists
        if (Test-Path "$OutputDir\simulation_log.csv") {
            Write-Host "  [SKIPPING] $ModelName $Group already completed (found simulation_log.csv)." -ForegroundColor Gray
            continue
        }

        # 1. Clean partially completed data if it exists
        if (Test-Path $OutputDir) {
            Write-Host "  [Cleaning] Deleting partial data in $OutputDir..."
            Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
        
        # 2. Config
        $MemEngine = if ($Group -eq "Group_B") { "window" } else { "humancentric" }
        $LogFile = "$OutputDir\execution.log"
        
        # 3. Clean Run (Strict, No Priority)
        Write-Host "  > Executing $ModelName ($Group)..." -ForegroundColor Cyan
        $cmd = "cmd /c python $SAPath/run_flood.py --model $ModelTag --years 10 --agents 100 --workers 1 --memory-engine $MemEngine --governance-mode strict --initial-agents `"$SAPath/agent_initial_profiles.csv`" --output $OutputDir --seed 401 --num-ctx 8192 --num-predict 1536 2>&1"
        
        Invoke-Expression "$cmd | Tee-Object -FilePath `"$LogFile`""
            
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [SUCCESS] $ModelName $Group Finished." -ForegroundColor Green
        } else {
             Write-Host "  [FAILURE] $ModelName $Group Failed." -ForegroundColor Red
             break outer # Stop the ENTIRE marathon on error
        }
    }
}
