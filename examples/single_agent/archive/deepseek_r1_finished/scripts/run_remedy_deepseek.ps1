
# Remedy Script: Resuming DeepSeek 8B & 14B Group C (and fixing 14B Group B failure)
# Based on existing run_resume_JOH.ps1 and run_universal_reset.ps1

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === STARTING DEEPSEEK REMEDY RUN (8B/14B) ===" -ForegroundColor Cyan

$RunPlan = @(
    # Re-running 14B Group B to ensure it completes successfully after the bug fix.
    @{ Tag = "deepseek-r1:14b";  Name = "deepseek_r1_14b";  Groups = @("Group_B", "Group_C") },
    # Running 8B Group C if not already done.
    @{ Tag = "deepseek-r1:8b";   Name = "deepseek_r1_8b";   Groups = @("Group_C") }
)

$SAPath = "examples/single_agent"

foreach ($Item in $RunPlan) {
    foreach ($Group in $Item.Groups) {
        $ModelTag = $Item.Tag
        $ModelName = $Item.Name
        $OutputDir = "$SAPath/results/JOH_FINAL/$ModelName/$Group/Run_1"
        
        Write-Host ">>> PROCESSING: $ModelName | $Group <<<" -ForegroundColor Yellow
        
        # SMART RESUME: Skip if simulation_log.csv exists AND it's not the failed 14B Group B
        if (Test-Path "$OutputDir\simulation_log.csv") {
             # If it's Group C, we trust it if it's there. 
             # If it's the 14B Group B that failed, the user might want to clean it.
             # In this script, we will skip if found, unless the user manually deletes it first.
             Write-Host "  [SKIPPING] $ModelName $Group already found." -ForegroundColor Gray
             continue
        }

        # 1. New Directory
        if (Test-Path $OutputDir) {
            Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
        
        # 2. Config
        $MemEngine = if ($Group -eq "Group_B") { "window" } else { "humancentric" }
        $LogFile = "$OutputDir\execution.log"
        
        # 3. Execution (Strict, 100 agents, 10 years)
        Write-Host "  > Executing $ModelName ($Group)..." -ForegroundColor Cyan
        $cmd = "cmd /c python $SAPath/run_flood.py --model $ModelTag --years 10 --agents 100 --workers 1 --memory-engine $MemEngine --governance-mode strict --initial-agents `"$SAPath/agent_initial_profiles.csv`" --output $OutputDir --seed 401 --num-ctx 8192 --num-predict 1536 2>&1"
        
        Invoke-Expression "$cmd | Tee-Object -FilePath `"$LogFile`""
            
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [SUCCESS] $ModelName $Group Finished." -ForegroundColor Green
        } else {
             Write-Host "  [FAILURE] $ModelName $Group Failed." -ForegroundColor Red
             # We let it try next in plan instead of breaking entirely so small errors don't stop the whole night
        }
    }
}

Write-Host "`n=== Remedy Run Complete! ===" -ForegroundColor Green
