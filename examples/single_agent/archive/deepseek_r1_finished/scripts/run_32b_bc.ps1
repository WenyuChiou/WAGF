
# DeepSeek R1 32B - Group B & C Experiments
# Memory Engine: B=window, C=humancentric
# Governance: Strict mode

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] === STARTING DEEPSEEK R1 32B (Group B & C) ===" -ForegroundColor Cyan

$RunPlan = @(
    @{ Tag = "deepseek-r1:32b"; Name = "deepseek_r1_32b"; Groups = @("Group_B", "Group_C") }
)

$SAPath = "examples/single_agent"

foreach ($Item in $RunPlan) {
    foreach ($Group in $Item.Groups) {
        $ModelTag = $Item.Tag
        $ModelName = $Item.Name
        $OutputDir = "$SAPath/results/JOH_FINAL/$ModelName/$Group/Run_1"

        Write-Host ">>> PROCESSING: $ModelName | $Group <<<" -ForegroundColor Yellow

        # Skip if already completed
        if (Test-Path "$OutputDir\simulation_log.csv") {
            $lineCount = (Get-Content "$OutputDir\simulation_log.csv" | Measure-Object -Line).Lines
            if ($lineCount -gt 900) {  # 100 agents * 10 years = 1000 rows (with header ~1001)
                Write-Host "  [SKIPPING] $ModelName $Group already completed ($lineCount rows)." -ForegroundColor Gray
                continue
            }
        }

        # 1. Clean Directory
        if (Test-Path $OutputDir) {
            Write-Host "  [Cleaning] Deleting $OutputDir..."
            Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

        # 2. Config
        $MemEngine = if ($Group -eq "Group_B") { "window" } else { "humancentric" }
        $LogFile = "$OutputDir\execution.log"

        # 3. Execute (32B needs more context/predict for longer reasoning)
        Write-Host "  > Executing $ModelName ($Group)..." -ForegroundColor Cyan
        $cmd = "cmd /c python $SAPath/run_flood.py --model $ModelTag --years 10 --agents 100 --workers 1 --memory-engine $MemEngine --governance-mode strict --initial-agents `"$SAPath/agent_initial_profiles.csv`" --output $OutputDir --seed 401 --num-ctx 16384 --num-predict 2048 2>&1"

        Invoke-Expression "$cmd | Tee-Object -FilePath `"$LogFile`""

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [SUCCESS] $ModelName $Group Finished." -ForegroundColor Green
        } else {
            Write-Host "  [FAILURE] $ModelName $Group Failed." -ForegroundColor Red
        }
    }
}

Write-Host "`n=== DeepSeek R1 32B Run Complete! ===" -ForegroundColor Green
