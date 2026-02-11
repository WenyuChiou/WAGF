# WRR flood rerun helper: execute ONLY missing result cells.
# Default scope is Run_3 across the 6 target models x 3 groups.
#
# Usage examples:
#   powershell -ExecutionPolicy Bypass -File examples/single_agent/run_wrr_missing_only.ps1
#   powershell -ExecutionPolicy Bypass -File examples/single_agent/run_wrr_missing_only.ps1 -ListOnly
#   powershell -ExecutionPolicy Bypass -File examples/single_agent/run_wrr_missing_only.ps1 -Runs Run_2,Run_3

param(
    [string[]]$Runs = @("Run_3"),
    [switch]$ListOnly
)

$ErrorActionPreference = "Continue"

$BASE = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$BASELINE_SCRIPT = "ref/LLMABMPMT-Final.py"
$RUNNER_SCRIPT = "examples/single_agent/run_flood.py"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$FLOOD_YEARS = "examples/single_agent/flood_years.csv"
$OUT_ROOT = "examples/single_agent/results/JOH_FINAL"

$YEARS = 10
$AGENTS = 100
$WORKERS = 1
$CTX = 8192
$PRED = 1536

# Keep the seed convention aligned with the existing WRR run setup.
$runSeed = @{
    "Run_1" = 42
    "Run_2" = 4202
    "Run_3" = 4203
}

$models = @(
    @{tag = "ministral-3:3b"; dir = "ministral3_3b"},
    @{tag = "ministral-3:8b"; dir = "ministral3_8b"},
    @{tag = "ministral-3:14b"; dir = "ministral3_14b"},
    @{tag = "gemma3:4b"; dir = "gemma3_4b"},
    @{tag = "gemma3:12b"; dir = "gemma3_12b"},
    @{tag = "gemma3:27b"; dir = "gemma3_27b"}
)

$groups = @("Group_A", "Group_B", "Group_C")

Set-Location $BASE

function Build-Task {
    param(
        [hashtable]$Model,
        [string]$Group,
        [string]$RunName,
        [int]$Seed
    )
    $outDir = "$OUT_ROOT/$($Model.dir)/$Group/$RunName"
    $simCsv = "$outDir/simulation_log.csv"
    if (Test-Path $simCsv) {
        return $null
    }
    return @{
        modelTag = $Model.tag
        modelDir = $Model.dir
        group = $Group
        run = $RunName
        seed = $Seed
        outDir = $outDir
    }
}

function Invoke-GroupA {
    param([hashtable]$Task)
    New-Item -ItemType Directory -Path $Task.outDir -Force | Out-Null

    $args = @(
        $BASELINE_SCRIPT,
        "--model", $Task.modelTag,
        "--years", "$YEARS",
        "--agents", "$AGENTS",
        "--output", $Task.outDir,
        "--seed", "$($Task.seed)",
        "--agents-path", $PROFILES,
        "--flood-years-path", $FLOOD_YEARS
    )

    Write-Host "[RUN-A] python $($args -join ' ')" -ForegroundColor Cyan
    & python @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL-A] $($Task.modelDir) $($Task.group) $($Task.run)" -ForegroundColor Red
        return $false
    }
    Write-Host "[DONE-A] $($Task.modelDir) $($Task.group) $($Task.run)" -ForegroundColor Green
    return $true
}

function Invoke-GroupBC {
    param([hashtable]$Task)
    New-Item -ItemType Directory -Path $Task.outDir -Force | Out-Null

    $memEngine = if ($Task.group -eq "Group_B") { "window" } else { "humancentric" }
    $usePriority = $Task.group -eq "Group_C"

    $args = @(
        $RUNNER_SCRIPT,
        "--model", $Task.modelTag,
        "--years", "$YEARS",
        "--agents", "$AGENTS",
        "--workers", "$WORKERS",
        "--governance-mode", "strict",
        "--memory-engine", $memEngine,
        "--window-size", "5",
        "--initial-agents", $PROFILES,
        "--output", $Task.outDir,
        "--seed", "$($Task.seed)",
        "--memory-seed", "$($Task.seed)",
        "--num-ctx", "$CTX",
        "--num-predict", "$PRED"
    )
    if ($usePriority) {
        $args += "--use-priority-schema"
    }

    Write-Host "[RUN-BC] python $($args -join ' ')" -ForegroundColor Cyan
    & python @args
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL-BC] $($Task.modelDir) $($Task.group) $($Task.run)" -ForegroundColor Red
        return $false
    }
    Write-Host "[DONE-BC] $($Task.modelDir) $($Task.group) $($Task.run)" -ForegroundColor Green
    return $true
}

# Build missing-task list
$tasks = @()
foreach ($runName in $Runs) {
    if (-not $runSeed.ContainsKey($runName)) {
        Write-Host "[WARN] Unknown run name: $runName (skip)" -ForegroundColor Yellow
        continue
    }
    $seed = [int]$runSeed[$runName]
    foreach ($m in $models) {
        foreach ($g in $groups) {
            $task = Build-Task -Model $m -Group $g -RunName $runName -Seed $seed
            if ($null -ne $task) {
                $tasks += $task
            }
        }
    }
}

if ($tasks.Count -eq 0) {
    Write-Host "[OK] No missing cells found for runs: $($Runs -join ', ')" -ForegroundColor Green
    exit 0
}

Write-Host "============================================" -ForegroundColor Magenta
Write-Host "Missing cells to run: $($tasks.Count)" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
foreach ($t in $tasks) {
    Write-Host (" - {0} {1} {2} seed={3}" -f $t.modelDir, $t.group, $t.run, $t.seed)
}

if ($ListOnly) {
    Write-Host "[LIST-ONLY] No jobs executed." -ForegroundColor Yellow
    exit 0
}

$ok = 0
$fail = 0
foreach ($t in $tasks) {
    if ($t.group -eq "Group_A") {
        $result = Invoke-GroupA -Task $t
    } else {
        $result = Invoke-GroupBC -Task $t
    }
    if ($result) { $ok++ } else { $fail++ }
}

Write-Host "============================================" -ForegroundColor Magenta
Write-Host "Done. Success=$ok Fail=$fail" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
