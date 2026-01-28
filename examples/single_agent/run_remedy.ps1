# Remedy Script: 1.5B No-Cache Re-run
# Purpose: Eliminate "Cache Deduplication" for Small Model traces.
# Targets: DeepSeek R1 1.5B (Group B & Group C)

$ErrorActionPreference = "Stop"
$Root = "C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
Set-Location $Root

# --- Configuration ---
$NumYears = 10
$BaseSeed = 401

# --- Plan ---
$RunPlan = @(
    # @{ Tag = "deepseek-r1:1.5b"; Name = "deepseek_r1_1_5b"; Group = "Group_B"; Governance = "strict"; UsePriority = $false },
    @{ Tag = "deepseek-r1:1.5b"; Name = "deepseek_r1_1_5b"; Group = "Group_C"; Governance = "strict"; UsePriority = $true }
)

Write-Host "=== STARTING 1.5B NO-CACHE REMEDY RUN ===" -ForegroundColor Cyan

foreach ($Run in $RunPlan) {
    $ModelTag = $Run.Tag
    $ModelName = $Run.Name
    $Group = $Run.Group
    $Mode = $Run.Governance
    $UsePriority = $Run.UsePriority
    
    Write-Host "`n[Target] Model: $ModelName | Group: $Group | Mode: $Mode" -ForegroundColor Yellow
    
    # Construct Arguments
    $Args = @(
        "examples/single_agent/run_flood.py",
        "--model", $ModelTag,
        "--years", $NumYears,
        "--agents", 50,
        "--seed", $BaseSeed,
        "--governance-mode", $Mode,
        "--no-cache",  # Force full computation
        "--output", "examples/single_agent/results/JOH_FINAL/$ModelName/$Group/Run_1"
    )

    # Priority Schema is NOT requested for this remedy run
    # if ($UsePriority) {
    #     $Args += "--use-priority-schema"
    #     Write-Host " -> Enabled Priority Schema for Group C" -ForegroundColor Gray
    # }

    # Execute
    Write-Host " -> Python Command: python $($Args -join ' ')" -ForegroundColor DarkGray
    python @Args
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Run Failed! Halting."
    }
    
    Write-Host " -> Success! Run completed." -ForegroundColor Green
}

Write-Host "`n=== 1.5B REMEDY COMPLETE ===" -ForegroundColor Cyan
