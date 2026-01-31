# Task-053: Gemma 3 Experiment Campaign
# 4 Models x 3 Groups = 12 Runs
# Hallucination + Diversity Study
#
# Group A: Original LLMABMPMT-Final.py (baseline, no broker framework)
# Group B: run_flood.py --governance-mode strict --memory-engine window
# Group C: run_flood.py --governance-mode strict --memory-engine humancentric --use-priority-schema

$ErrorActionPreference = "Continue"
$SAPath = "examples/single_agent"
$RefPath = "ref"

$Models = @(
    @{ Tag = "gemma3:12b"; Name = "gemma3_12b" },
    @{ Tag = "gemma3:27b"; Name = "gemma3_27b" }
)

# Standardized parameters (aligned with DeepSeek R1 experiments)
$Years = 10
$Agents = 100
$Seed = 401
$NumCtx = 8192
$NumPredict = 1536

$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "[$Timestamp] ==========================================" -ForegroundColor Cyan
Write-Host "Starting Gemma 3 Experimental Campaign (Task-053)" -ForegroundColor Cyan
Write-Host "Models: $($Models.Tag -join ', ')" -ForegroundColor Yellow
Write-Host "Groups: 12b=C only; 27b=B and C" -ForegroundColor Yellow
Write-Host "Params: years=$Years, agents=$Agents, seed=$Seed, num-ctx=$NumCtx, num-predict=$NumPredict" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan

$TotalRuns = 3  # 12b: C only (1), 27b: B + C (2)
$CurrentRun = 0

foreach ($Model in $Models) {
    # ===== GROUP B: Strict Governance (Window Memory) =====
    if ($Model.Name -eq "gemma3_27b") {
        $CurrentRun++
        $OutputDir = "$SAPath/results/JOH_FINAL/$($Model.Name)/Group_B/Run_1"
        $Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

        Write-Host "`n[$Timestamp] --------------------------------------------------" -ForegroundColor Green
        Write-Host "[$CurrentRun/$TotalRuns] $($Model.Name) | Group_B (Strict Governance)" -ForegroundColor Green
        Write-Host "  Memory: window | Governance: strict | Priority: False" -ForegroundColor DarkGray
        Write-Host "--------------------------------------------------" -ForegroundColor Green

        if (Test-Path $OutputDir) {
            Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

        $LogFile = "$OutputDir/execution.log"
        $BaseCmd = "python $SAPath/run_flood.py --model $($Model.Tag) --years $Years --agents $Agents --workers 1 --memory-engine window --governance-mode strict --initial-agents `"$SAPath/agent_initial_profiles.csv`" --output $OutputDir --seed $Seed --num-ctx $NumCtx --num-predict $NumPredict"
        $cmd = "cmd /c $BaseCmd 2>&1"
        Invoke-Expression "$cmd | Tee-Object -FilePath `"$LogFile`""

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  [SUCCESS] $($Model.Name) Group_B Finished." -ForegroundColor Green
        }
        else {
            Write-Host "  [FAILURE] $($Model.Name) Group_B Failed. Check: $LogFile" -ForegroundColor Red
        }
        Start-Sleep -Seconds 2
    }

    # ===== GROUP C: Full Cognitive (HumanCentric + Priority Schema) =====
    $CurrentRun++
    $OutputDir = "$SAPath/results/JOH_FINAL/$($Model.Name)/Group_C/Run_1"
    $Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    Write-Host "`n[$Timestamp] --------------------------------------------------" -ForegroundColor Green
    Write-Host "[$CurrentRun/$TotalRuns] $($Model.Name) | Group_C (Full Cognitive)" -ForegroundColor Green
    Write-Host "  Memory: humancentric | Governance: strict | Priority: True" -ForegroundColor DarkGray
    Write-Host "--------------------------------------------------" -ForegroundColor Green

    if (Test-Path $OutputDir) {
        Remove-Item -Path $OutputDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    $LogFile = "$OutputDir/execution.log"
    $BaseCmd = "python $SAPath/run_flood.py --model $($Model.Tag) --years $Years --agents $Agents --workers 1 --memory-engine humancentric --governance-mode strict --use-priority-schema --initial-agents `"$SAPath/agent_initial_profiles.csv`" --output $OutputDir --seed $Seed --num-ctx $NumCtx --num-predict $NumPredict"
    $cmd = "cmd /c $BaseCmd 2>&1"
    Invoke-Expression "$cmd | Tee-Object -FilePath `"$LogFile`""

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [SUCCESS] $($Model.Name) Group_C Finished." -ForegroundColor Green
    }
    else {
        Write-Host "  [FAILURE] $($Model.Name) Group_C Failed. Check: $LogFile" -ForegroundColor Red
    }
    Start-Sleep -Seconds 2
}

$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
Write-Host "`n[$Timestamp] ==========================================" -ForegroundColor Cyan
Write-Host "Gemma 3 Campaign Completed! ($TotalRuns runs)" -ForegroundColor Cyan
Write-Host "Results: $SAPath/results/JOH_FINAL/gemma3_*/" -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
