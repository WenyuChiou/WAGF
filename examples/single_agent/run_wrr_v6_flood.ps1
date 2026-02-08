# WRR v6 canonical flood runner
# Runs Run_2 and Run_3 for all 6 models x 3 groups.
# Group A uses original baseline script (LLMABMPMT-Final.py).
# Group B/C use run_flood.py governed pipeline.
#
# Usage:
# powershell -ExecutionPolicy Bypass -File examples/single_agent/run_wrr_v6_flood.ps1

$ErrorActionPreference = "Continue"
$BASE = "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$BASELINE_SCRIPT = "ref/LLMABMPMT-Final.py"
$RUNNER_SCRIPT = "examples/single_agent/run_flood.py"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$FLOOD_YEARS = "examples/single_agent/flood_years.csv"

$YEARS = 10
$AGENTS = 100
$WORKERS = 1
$CTX = 8192
$PRED = 1536

Set-Location $BASE

$models = @(
    @{tag="gemma3:4b"; dir="gemma3_4b"},
    @{tag="gemma3:12b"; dir="gemma3_12b"},
    @{tag="gemma3:27b"; dir="gemma3_27b"},
    @{tag="ministral-3:3b"; dir="ministral3_3b"},
    @{tag="ministral-3:8b"; dir="ministral3_8b"},
    @{tag="ministral-3:14b"; dir="ministral3_14b"}
)

$runs = @(
    @{name="Run_2"; seed=4202},
    @{name="Run_3"; seed=4203}
)

function Invoke-GroupA {
    param(
        [string]$Model,
        [string]$OutDir,
        [int]$Seed
    )

    $csvPath = "$OutDir/simulation_log.csv"
    if (Test-Path $csvPath) {
        Write-Host "[SKIP] Exists: $csvPath" -ForegroundColor Yellow
        return
    }

    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    $args = @(
        $BASELINE_SCRIPT,
        "--model", $Model,
        "--years", "$YEARS",
        "--agents", "$AGENTS",
        "--output", $OutDir,
        "--seed", "$Seed",
        "--agents-path", $PROFILES,
        "--flood-years-path", $FLOOD_YEARS
    )

    Write-Host "[RUN-A] python $($args -join ' ')" -ForegroundColor Cyan
    & python @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL-A] $Model -> $OutDir" -ForegroundColor Red
    } else {
        Write-Host "[DONE-A] $Model -> $OutDir" -ForegroundColor Green
    }
}

function Invoke-GroupBC {
    param(
        [string]$Model,
        [string]$OutDir,
        [int]$Seed,
        [string]$MemEngine,
        [bool]$UsePriority
    )

    $csvPath = "$OutDir/simulation_log.csv"
    if (Test-Path $csvPath) {
        Write-Host "[SKIP] Exists: $csvPath" -ForegroundColor Yellow
        return
    }

    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
    $args = @(
        $RUNNER_SCRIPT,
        "--model", $Model,
        "--years", "$YEARS",
        "--agents", "$AGENTS",
        "--workers", "$WORKERS",
        "--governance-mode", "strict",
        "--memory-engine", $MemEngine,
        "--window-size", "5",
        "--initial-agents", $PROFILES,
        "--output", $OutDir,
        "--seed", "$Seed",
        "--memory-seed", "$Seed",
        "--num-ctx", "$CTX",
        "--num-predict", "$PRED"
    )

    if ($UsePriority) {
        $args += "--use-priority-schema"
    }

    Write-Host "[RUN-BC] python $($args -join ' ')" -ForegroundColor Cyan
    & python @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL-BC] $Model -> $OutDir" -ForegroundColor Red
    } else {
        Write-Host "[DONE-BC] $Model -> $OutDir" -ForegroundColor Green
    }
}

foreach ($r in $runs) {
    Write-Host "============================================" -ForegroundColor Magenta
    Write-Host "Starting $($r.name) with seed=$($r.seed)" -ForegroundColor Magenta
    Write-Host "============================================" -ForegroundColor Magenta

    foreach ($m in $models) {
        $baseOut = "examples/single_agent/results/JOH_FINAL/$($m.dir)"

        Invoke-GroupA  -Model $m.tag -OutDir "$baseOut/Group_A/$($r.name)" -Seed $r.seed
        Invoke-GroupBC -Model $m.tag -OutDir "$baseOut/Group_B/$($r.name)" -Seed $r.seed -MemEngine "window" -UsePriority:$false
        Invoke-GroupBC -Model $m.tag -OutDir "$baseOut/Group_C/$($r.name)" -Seed $r.seed -MemEngine "humancentric" -UsePriority:$true
    }
}

Write-Host "All WRR v6 Run_2/Run_3 jobs processed." -ForegroundColor Cyan
