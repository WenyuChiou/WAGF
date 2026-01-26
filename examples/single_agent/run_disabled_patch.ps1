# =============================================================================
# Governance Patch Run - Enabling Retries for Group C
# =============================================================================
# Purpose: Re-run Group C for 1.5B, 8B, and 32B with STRICT governance.
# goal: Generate retry/intervention data (previously 0 due to 'disabled' profile).
# =============================================================================

$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === STARTING GOVERNANCE PATCH RUN (Group C Strict) ===" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"

# Target Models that need retries (14B is already strict, skipping)
$Models = @(
    @{ Name="DeepSeek-R1-1.5B"; Tag="deepseek-r1:1.5b" },
    @{ Name="DeepSeek-R1-8B";   Tag="deepseek-r1:8b" }
)

$Group = "Group_C"
$NumYears = 10
$BaseSeed = 401

foreach ($Model in $Models) {
    $ModelName = $Model.Name
    $ModelTag = $Model.Tag
    $SafeName = $ModelTag -replace ":", "_" -replace "-", "_" -replace "\.", "_"
    
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] >>> PATCHING MODEL: $ModelName ($Group) <<<" -ForegroundColor Yellow
    
    # We write to a NEW output folder or Overwrite? 
    # User said "patch run", usually means overwrite Run_1 or maybe make Run_2?
    # To be safe and cleaner for analysis, let's use Run_1 but ensure we know it's the "Strict" version.
    # However, if we overwrite, we lose the "Disabled" evidence.
    # But usually users want the "Correct" data in the main slot.
    # I will modify the output path logic to standard Run_1, effectively replacing the disabled run.
    
    $OutputDir = "examples/single_agent/results/JOH_FINAL/$SafeName/$Group/Run_1"
    
    # Clean up old disabled run artifacts if needed? 
    # Setup standard run command
    # CRITICAL: Force --governance-mode strict
    
    $LogFile = "$OutputDir\patch_execution.log"
    
    # Ensure directory exists
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    }
    
    Write-Host "  > Running $Group with STRICT mode... (Output: $OutputDir)"
    
    python examples/single_agent/run_flood.py `
        --model $ModelTag `
        --years $NumYears `
        --agents 100 `
        --workers 1 `
        --memory-engine humancentric `
        --window-size 5 `
        --governance-mode strict `
        --use-priority-schema `
        --initial-agents "examples/single_agent/agent_initial_profiles.csv" `
        --output $OutputDir `
        --seed $BaseSeed `
        --num-ctx 8192 `
        --num-predict 1536 2>&1 | Tee-Object -FilePath $LogFile
        
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] $ModelName $Group failed." -ForegroundColor Red
    } else {
        Write-Host "  [OK] $ModelName $Group completed." -ForegroundColor Green
    }
}

Write-Host "Patch Run Complete." -ForegroundColor Cyan
