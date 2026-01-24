# =============================================================================
# DeepSeek Scaling Law - Large Tiers (8B, 14B, 32B)
# =============================================================================
# Purpose: Run ABC matrix for mid-to-large DeepSeek tiers.
# Strategy: Skip if directory exists. Uses universal Capability-based AutoTune.
# =============================================================================

$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === STARTING DEEPSEEK LARGE TIER RUN (8B, 14B, 32B) ===" -ForegroundColor Cyan

# Prevent PowerShell from stopping on stderr output (PerformanceTuner logs to stderr)
$ErrorActionPreference = "Continue"
$Models = @(
    # Tier 2: Mid-Small (8B)
    @{ Name="DeepSeek-R1-8B"; Tag="deepseek-r1:8b" },

    # Tier 3: Mid-Large (14B)
    @{ Name="DeepSeek-R1-14B"; Tag="deepseek-r1:14b" },

    # Tier 4: Large (32B)
    @{ Name="DeepSeek-R1-32B"; Tag="deepseek-r1:32b" }
)

$Groups = @("Group_A", "Group_B", "Group_C")
$NumYears = 10
$BaseSeed = 401

# --- MAIN LOOP ---
foreach ($Model in $Models) {
    $ModelName = $Model.Name
    $ModelTag = $Model.Tag
    $SafeName = $ModelTag -replace ":", "_" -replace "-", "_" -replace "\.", "_"
    
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] >>> MODEL: $ModelName <<<" -ForegroundColor Yellow
    
    foreach ($Group in $Groups) {
        $OutputDir = "results/JOH_FINAL/$SafeName/$Group/Run_1"
        
        # SIMPLE SKIP: If directory exists, we assume it's done or in progress.
        if (Test-Path $OutputDir) {
            Write-Host "  [Skip] $OutputDir already exists." -ForegroundColor DarkGray
            continue
        }
        
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
        $LogFile = "$OutputDir\execution.log"
        Write-Host "  > Running $Group... (Logs: $LogFile)"
        
        if ($Group -eq "Group_A") {
            # --- GROUP A: LEGACY BASELINE ---
            $BaselinePath = "..\..\ref\LLMABMPMT-Final.py"
            python $BaselinePath --model $ModelTag --output $OutputDir --seed $BaseSeed --agents 100 --years $NumYears 2>&1 | Tee-Object -FilePath $LogFile
        }
        else {
            # --- GROUP B/C: MODERN FRAMEWORK ---
            $MemEngine = if ($Group -eq "Group_B") { "window" } else { "humancentric" }
            $GovMode = if ($Group -eq "Group_B") { "strict" } else { "disabled" }
            $UseSchema = ($Group -eq "Group_C")

            python run_flood.py `
                --model $ModelTag --years $NumYears --agents 100 --workers 1 `
                --memory-engine $MemEngine --window-size 5 --governance-mode $GovMode `
                $(if ($UseSchema) { "--use-priority-schema" }) `
                --output $OutputDir --seed $BaseSeed --num-ctx 8192 --num-predict 1536 2>&1 | Tee-Object -FilePath $LogFile
        }

        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [ERROR] $Group execution failed." -ForegroundColor Red
        } else {
            Write-Host "  [OK] $Group completed successfully." -ForegroundColor Green
        }
    }
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] === LARGE TIER EXPERIMENTS COMPLETE ===" -ForegroundColor Cyan
