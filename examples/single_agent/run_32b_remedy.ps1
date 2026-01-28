# Remedy Script: 32B Missing Data
# Purpose: Generate missing simulation data for Large Model.
# Targets: DeepSeek R1 32B (Group B & Group C)

$ErrorActionPreference = "Stop"
$Root = "C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
Set-Location $Root

# --- Configuration ---
$NumYears = 10
$BaseSeed = 401

# --- Plan ---
$RunPlan = @(
    @{ Tag = "deepseek-r1:32b"; Name = "deepseek_r1_32b"; Group = "Group_B"; Governance = "strict"; UsePriority = $false },
    @{ Tag = "deepseek-r1:32b"; Name = "deepseek_r1_32b"; Group = "Group_C"; Governance = "social"; UsePriority = $true }
)

Write-Host "=== STARTING 32B REMEDY RUN ===" -ForegroundColor Cyan

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
        "--governance", $Mode,
        "--no-cache",  # Use no-cache for consistency, though less critical for 32B
        "--output", "examples/single_agent/results/JOH_FINAL/$ModelName/$Group/Run_1"
    )

    if ($UsePriority) {
        $Args += "--use_priority_schema"
        Write-Host " -> Enabled Priority Schema for Group C" -ForegroundColor Gray
    }

    # Execute
    Write-Host " -> Python Command: python $($Args -join ' ')" -ForegroundColor DarkGray
    python @Args
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Run Failed! Halting."
    }
    
    Write-Host " -> Success! Run completed." -ForegroundColor Green
}

Write-Host "`n=== 32B REMEDY COMPLETE ===" -ForegroundColor Cyan
