param(
    [switch]$ListOnly,
    [int]$MaxRetries = 2
)

$ErrorActionPreference = "Continue"

$BASE = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$BASELINE_SCRIPT = "ref/LLMABMPMT-Final.py"
$RUNNER_SCRIPT = "examples/single_agent/run_flood.py"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$FLOOD_YEARS = "examples/single_agent/flood_years.csv"
$OUT_ROOT = "examples/single_agent/results/JOH_FINAL"
$LOG_ROOT = "examples/single_agent/results/JOH_FINAL/_logs/scheduler_repair_run3_run45"

$YEARS = 10
$AGENTS = 100
$WORKERS = 1
$WINDOW_SIZE = 5

$runSeed = @{
    "Run_3" = 4203
    "Run_4" = 4204
    "Run_5" = 4205
}

# Model order requested by user: Ministral family first, then Gemma (27b last naturally).
$modelConfigs = @(
    @{ tag = "ministral-3:3b";  dir = "ministral3_3b";  ctx = 4096; pred = 1024 },
    @{ tag = "ministral-3:8b";  dir = "ministral3_8b";  ctx = 4096; pred = 1024 },
    @{ tag = "ministral-3:14b"; dir = "ministral3_14b"; ctx = 8192; pred = 1536 },
    @{ tag = "gemma3:4b";       dir = "gemma3_4b";      ctx = 4096; pred = 1024 },
    @{ tag = "gemma3:12b";      dir = "gemma3_12b";     ctx = 8192; pred = 1536 },
    @{ tag = "gemma3:27b";      dir = "gemma3_27b";     ctx = 8192; pred = 1536 }
)

$groups = @("Group_A", "Group_B", "Group_C")

Set-Location $BASE
New-Item -ItemType Directory -Path $LOG_ROOT -Force | Out-Null

function Stop-StrayExperimentProcs {
    $procs = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -eq "python.exe" -and (
            $_.CommandLine -match "examples/single_agent/run_flood.py" -or
            $_.CommandLine -match "ref/LLMABMPMT-Final.py"
        )
    }
    foreach ($p in $procs) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Restart-Ollama {
    cmd /c "taskkill /IM ollama.exe /F" | Out-Null
    Start-Sleep -Seconds 2
    Start-Process -FilePath "C:\Users\wenyu\AppData\Local\Programs\Ollama\ollama.exe" -ArgumentList "serve" | Out-Null
    Start-Sleep -Seconds 2
}

function New-Task {
    param(
        [hashtable]$Model,
        [string]$Group,
        [string]$RunName
    )
    $seed = [int]$runSeed[$RunName]
    $outDir = "$OUT_ROOT/$($Model.dir)/$Group/$RunName"
    $simCsv = "$outDir/simulation_log.csv"
    return @{
        modelTag = $Model.tag
        modelDir = $Model.dir
        group = $Group
        run = $RunName
        seed = $seed
        outDir = $outDir
        simCsv = $simCsv
        ctx = [int]$Model.ctx
        pred = [int]$Model.pred
    }
}

function Invoke-Task {
    param([hashtable]$Task)

    New-Item -ItemType Directory -Path $Task.outDir -Force | Out-Null
    $runId = "$($Task.modelDir)_$($Task.group)_$($Task.run)"

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $logOut = "$LOG_ROOT/$runId`_attempt$attempt`_$stamp.out.log"
        $logErr = "$LOG_ROOT/$runId`_attempt$attempt`_$stamp.err.log"

        if (Test-Path $Task.outDir) {
            Remove-Item -Recurse -Force "$($Task.outDir)\*" -ErrorAction SilentlyContinue
        }

        if ($Task.group -eq "Group_A") {
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
        } else {
            $mem = if ($Task.group -eq "Group_B") { "window" } else { "humancentric" }
            $usePriority = $Task.group -eq "Group_C"

            $args = @(
                $RUNNER_SCRIPT,
                "--model", $Task.modelTag,
                "--years", "$YEARS",
                "--agents", "$AGENTS",
                "--workers", "$WORKERS",
                "--governance-mode", "strict",
                "--memory-engine", $mem,
                "--window-size", "$WINDOW_SIZE",
                "--initial-agents", $PROFILES,
                "--output", $Task.outDir,
                "--seed", "$($Task.seed)",
                "--memory-seed", "$($Task.seed)",
                "--num-ctx", "$($Task.ctx)",
                "--num-predict", "$($Task.pred)"
            )
            if ($usePriority) {
                $args += "--use-priority-schema"
            }
        }

        Write-Host "[RUN] $runId attempt=$attempt" -ForegroundColor Cyan
        Write-Host "      logs: $logOut" -ForegroundColor DarkCyan
        & python @args 1> $logOut 2> $logErr
        $code = $LASTEXITCODE

        if ($code -eq 0 -and (Test-Path $Task.simCsv)) {
            $size = (Get-Item $Task.simCsv).Length
            if ($size -gt 0) {
                Write-Host "[DONE] $runId" -ForegroundColor Green
                return $true
            }
        }

        Write-Host "[RETRY] $runId failed (code=$code), restarting Ollama..." -ForegroundColor Red
        Restart-Ollama
    }

    Write-Host "[FAIL] $runId exhausted retries." -ForegroundColor Red
    return $false
}

# Queue part 1: repair only the two known broken Run_3 cells.
$queue = @()
$queue += (New-Task -Model $modelConfigs[0] -Group "Group_B" -RunName "Run_3")
$queue += (New-Task -Model $modelConfigs[0] -Group "Group_C" -RunName "Run_3")

# Queue part 2: full matrix for Run_4 and Run_5.
foreach ($runName in @("Run_4", "Run_5")) {
    foreach ($m in $modelConfigs) {
        foreach ($g in $groups) {
            $queue += (New-Task -Model $m -Group $g -RunName $runName)
        }
    }
}

# Keep only tasks with missing simulation outputs.
$missing = @()
foreach ($t in $queue) {
    if (-not (Test-Path $t.simCsv)) {
        $missing += $t
    } else {
        # For the two repair tasks, force rerun if trace/audit are absent.
        $forceRepair = (
            $t.modelDir -eq "ministral3_3b" -and
            $t.run -eq "Run_3" -and
            ($t.group -eq "Group_B" -or $t.group -eq "Group_C")
        )
        if ($forceRepair) {
            $trace = "$($t.outDir)/raw/household_traces.jsonl"
            $audit = "$($t.outDir)/household_governance_audit.csv"
            if ((-not (Test-Path $trace)) -or (-not (Test-Path $audit))) {
                $missing += $t
            }
        }
    }
}

if ($missing.Count -eq 0) {
    Write-Host "[OK] No pending repair/run tasks." -ForegroundColor Green
    exit 0
}

Write-Host "============================================" -ForegroundColor Magenta
Write-Host "Pending tasks: $($missing.Count)" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
foreach ($t in $missing) {
    Write-Host (" - {0} {1} {2} seed={3}" -f $t.modelDir, $t.group, $t.run, $t.seed)
}

if ($ListOnly) {
    Write-Host "[LIST-ONLY] No jobs executed." -ForegroundColor Yellow
    exit 0
}

Stop-StrayExperimentProcs
Restart-Ollama

$ok = 0
$fail = 0
foreach ($t in $missing) {
    $result = Invoke-Task -Task $t
    if ($result) { $ok++ } else { $fail++ }
}

Write-Host "============================================" -ForegroundColor Magenta
Write-Host "Scheduler done. Success=$ok Fail=$fail" -ForegroundColor Magenta
Write-Host "Logs: $LOG_ROOT" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
