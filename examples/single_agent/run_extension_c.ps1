$ModelName = "ollama_gemma3_4b_strict"
$Group = "Group_C"
$BaseDir = "results/JOH_FINAL/gemma3_4b/$Group"
$BaseSeed = 42

# Ensure typical error action
$ErrorActionPreference = "Stop"

Write-Host "Starting Extended Runs (4 to 10) for $Group..." -ForegroundColor Cyan

# Loop from Run 4 to 10
4..10 | ForEach-Object {
    $run_id = $_
    $CurrentSeed = $BaseSeed + $run_id
    
    Write-Host "------------------------------------------------" -ForegroundColor Yellow
    Write-Host "Executing Run: $run_id (Seed: $CurrentSeed)" -ForegroundColor Yellow
    Write-Host "------------------------------------------------"

    # Define paths
    # Note: run_missing_group_c.ps1 uses "Group_C\Run_$i".
    # But here $BaseDir already includes "Group_C". So we append "Run_$run_id".
    # Wait, the BaseDir in run_missing is "results.../gemma_...".
    # Let's simple check the path. 
    # If BaseDir is ".../Group_C", then we want ".../Group_C/Run_4".
    # But run_missing seems to use Join-Path "Group_C\Run_$i".
    # I will stick to "Run_$run_id" suffix.
    
    # Actually, let's use the explicit path structure to be safe.
    $RunDir = "$BaseDir/${ModelName}_Run_$run_id"
    # Wait, run_missing used "Group_C\Run_$i". It did NOT put ModelName in the folder *name* usually?
    # Let's check line 25 of run_missing: Join-Path $BaseDir "Group_C\Run_$i".
    # $BaseDir there was "results/JOH_FINAL/$ModelFolder".
    # So the full path is ".../Group_C/Run_3".
    
    # In my script: $BaseDir = "results/JOH_FINAL/gemma3_4b/$Group" (Includes Group_C)
    # So I should use "$BaseDir/ollama_gemma3_4b_strict_Run_$run_id" ??
    # NO. The user's specific pathing convention is "ollama_gemma3_4b_strict" inside Group C?
    # Let's look at the "Run 2" folder created by run_missing.
    # It created "$GroupCPath".
    # I will trust the "Run_$run_id" convention inside "Group_C".
    
    # Correct Path Construction based on run_missing:
    # 1. Root: results/JOH_FINAL/gemma3_4b/Group_C
    # 2. Run Folder: Run_4 (etc) -> Wait, run_missing makes "Run_2".
    # However, existing folders might have had model names?
    # The user's list from `run_command` output showed `gemma3_4b_strict_Run_4`??
    # Ah, the `run_extension` failure output showed `gemma3_4b_strict_Run_4`.
    # I'll stick to a simple "Run_$run_id" inside the Group_C folder if that's what run_missing does.
    # But `run_missing` uses `Join-Path`.
    
    # Re-evaluating path logic.
    # $BaseDir in run_missing = results/JOH_FINAL/gemma3_4b
    # $GroupCPath = Join-Path $BaseDir "Group_C\Run_$i"
    # Result: results/JOH_FINAL/gemma3_4b/Group_C/Run_2
    
    # So I should create "results/JOH_FINAL/gemma3_4b/Group_C/Run_$run_id".
    
    $TargetRunDir = "$BaseDir/Run_$run_id"
    
    # Ensure directory
    if (!(Test-Path $TargetRunDir)) {
        New-Item -ItemType Directory -Force -Path $TargetRunDir | Out-Null
    }

    # Execute Python Simulation
    python -u run_flood.py `
        --model "gemma3:4b" `
        --years 10 `
        --agents 100 `
        --memory-engine humancentric `
        --governance-mode strict `
        --use-priority-schema `
        --output $TargetRunDir `
        --survey-mode `
        --workers 5 `
        --seed $CurrentSeed

    if ($LASTEXITCODE -eq 0) {
        Write-Host "Run $run_id Completed Successfully." -ForegroundColor Green
    }
    else {
        Write-Host "Run $run_id Failed!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "All Extended Runs (4-10) Completed!" -ForegroundColor Green
