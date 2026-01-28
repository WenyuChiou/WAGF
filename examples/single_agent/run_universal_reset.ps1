
# Universal Reset & Rerun for Governance Verification
# Models: 1.5B, 8B, 14B
# Groups: B (Strict, No Social), C (Strict, Social)
# Mode: Strict, No Priority Schema

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === STARTING UNIVERSAL GOVERNANCE RESET ===" -ForegroundColor Cyan

$RunPlan = @(
    @{ Tag = "deepseek-r1:1.5b"; Name = "deepseek_r1_1_5b" },
    @{ Tag = "deepseek-r1:8b";   Name = "deepseek_r1_8b" },
    @{ Tag = "deepseek-r1:14b";  Name = "deepseek_r1_14b" }
)

$Groups = @("Group_B", "Group_C")
$SAPath = "examples/single_agent"

foreach ($Item in $RunPlan) {
    foreach ($Group in $Groups) {
        $ModelTag = $Item.Tag
        $ModelName = $Item.Name
        $OutputDir = "$SAPath/results/JOH_FINAL/$ModelName/$Group/Run_1"
        
        Write-Host ">>> PROCESSING: $ModelName | $Group <<<" -ForegroundColor Yellow
        
        # 1. Kill old data
        if (Test-Path $OutputDir) {
            Write-Host "  [Cleaning] Deleting $OutputDir..."
            Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
        
        # 2. Config
        $MemEngine = if ($Group -eq "Group_B") { "window" } else { "humancentric" }
        $LogFile = "$OutputDir\execution.log"
        
        # 3. Clean Run (No Cache, Strict, No Priority)
        Write-Host "  > Executing $ModelName ($Group)..."
        # Wrap in cmd /c to properly handle stderr redirection without triggering PowerShell NativeCommandError
        $cmd = "cmd /c python $SAPath/run_flood.py --model $ModelTag --years 10 --agents 100 --workers 1 --memory-engine $MemEngine --governance-mode strict --no-cache --initial-agents `"$SAPath/agent_initial_profiles.csv`" --output $OutputDir --seed 401 --num-ctx 8192 --num-predict 1536 2>&1"
        
        Invoke-Expression "$cmd | Tee-Object -FilePath `"$LogFile`""
            
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [SUCCESS] $ModelName $Group Finished." -ForegroundColor Green
        } else {
             Write-Host "  [FAILURE] $ModelName $Group Failed." -ForegroundColor Red
        }
    }
}
