# Run flood experiments for Run_2 and Run_3 (all models x groups)
# Safe mode: skip if target run already has simulation_log.csv

$ErrorActionPreference = "Continue"
$BASE = "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
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

function Invoke-Run {
    param(
        [string]$Model,
        [string]$OutDir,
        [int]$Seed,
        [string]$GovMode,
        [string]$MemEngine,
        [bool]$UsePriority
    )

    $csvPath = "$OutDir/simulation_log.csv"
    if (Test-Path $csvPath) {
        Write-Host "[SKIP] Exists: $csvPath" -ForegroundColor Yellow
        return
    }

    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

    $baseArgs = @(
        "examples/single_agent/run_flood.py",
        "--model", $Model,
        "--years", "$YEARS",
        "--agents", "$AGENTS",
        "--workers", "$WORKERS",
        "--governance-mode", $GovMode,
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
        $baseArgs += "--use-priority-schema"
    }

    Write-Host "[RUN] python $($baseArgs -join ' ')" -ForegroundColor Cyan
    & python @baseArgs

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] $Model -> $OutDir" -ForegroundColor Red
    } else {
        Write-Host "[DONE] $Model -> $OutDir" -ForegroundColor Green
    }
}

foreach ($r in $runs) {
    Write-Host "============================================" -ForegroundColor Magenta
    Write-Host "Starting $($r.name) with seed=$($r.seed)" -ForegroundColor Magenta
    Write-Host "============================================" -ForegroundColor Magenta

    foreach ($m in $models) {
        $baseOut = "examples/single_agent/results/JOH_FINAL/$($m.dir)"

        # Group A
        Invoke-Run -Model $m.tag -OutDir "$baseOut/Group_A/$($r.name)" -Seed $r.seed `
            -GovMode "disabled" -MemEngine "window" -UsePriority:$false

        # Group B
        Invoke-Run -Model $m.tag -OutDir "$baseOut/Group_B/$($r.name)" -Seed $r.seed `
            -GovMode "strict" -MemEngine "window" -UsePriority:$false

        # Group C
        Invoke-Run -Model $m.tag -OutDir "$baseOut/Group_C/$($r.name)" -Seed $r.seed `
            -GovMode "strict" -MemEngine "humancentric" -UsePriority:$true
    }
}

Write-Host "All requested Run_2/Run_3 jobs processed." -ForegroundColor Cyan
