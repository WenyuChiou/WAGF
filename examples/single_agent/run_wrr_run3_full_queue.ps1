param(
    [switch]$ListOnly,
    [int]$MaxRetries = 2
)

$ErrorActionPreference = "Continue"

$BASE = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$RUNNER_SCRIPT = "examples/single_agent/run_flood.py"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$OUT_ROOT = "examples/single_agent/results/JOH_FINAL"
$LOG_ROOT = "examples/single_agent/results/JOH_FINAL/_logs/scheduler_run3"
$SEED = 4203
$YEARS = 10
$AGENTS = 100
$WORKERS = 1

# Ordered queue: 8B -> 14B -> 27B, B then C
$queue = @(
    @{ modelTag = "ministral-3:8b";  modelDir = "ministral3_8b";  group = "Group_B"; mem = "window";      priority = $false; ctx = 4096; pred = 1024 },
    @{ modelTag = "ministral-3:8b";  modelDir = "ministral3_8b";  group = "Group_C"; mem = "humancentric"; priority = $true;  ctx = 4096; pred = 1024 },
    @{ modelTag = "ministral-3:14b"; modelDir = "ministral3_14b"; group = "Group_B"; mem = "window";      priority = $false; ctx = 8192; pred = 1536 },
    @{ modelTag = "ministral-3:14b"; modelDir = "ministral3_14b"; group = "Group_C"; mem = "humancentric"; priority = $true;  ctx = 8192; pred = 1536 },
    @{ modelTag = "gemma3:27b";      modelDir = "gemma3_27b";     group = "Group_B"; mem = "window";      priority = $false; ctx = 8192; pred = 1536 },
    @{ modelTag = "gemma3:27b";      modelDir = "gemma3_27b";     group = "Group_C"; mem = "humancentric"; priority = $true;  ctx = 8192; pred = 1536 }
)

Set-Location $BASE
New-Item -ItemType Directory -Path $LOG_ROOT -Force | Out-Null

function Get-SimPath {
    param([hashtable]$Task)
    return "$OUT_ROOT/$($Task.modelDir)/$($Task.group)/Run_3/simulation_log.csv"
}

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

function Run-Task {
    param([hashtable]$Task)

    $outDir = "$OUT_ROOT/$($Task.modelDir)/$($Task.group)/Run_3"
    $simPath = Get-SimPath -Task $Task
    if (Test-Path $simPath) {
        Write-Host "[SKIP] $($Task.modelDir) $($Task.group) Run_3 (already done)" -ForegroundColor Yellow
        return $true
    }

    New-Item -ItemType Directory -Path $outDir -Force | Out-Null

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $logOut = "$LOG_ROOT/$($Task.modelDir)_$($Task.group)_Run_3_attempt$attempt`_$stamp.out.log"
        $logErr = "$LOG_ROOT/$($Task.modelDir)_$($Task.group)_Run_3_attempt$attempt`_$stamp.err.log"

        # Clean partial outputs to avoid mixed traces
        if (Test-Path $outDir) {
            Remove-Item -Recurse -Force "$outDir\*" -ErrorAction SilentlyContinue
        }

        Write-Host "[RUN] $($Task.modelDir) $($Task.group) Run_3 attempt=$attempt" -ForegroundColor Cyan
        Write-Host "      logs: $logOut" -ForegroundColor DarkCyan

        $args = @(
            $RUNNER_SCRIPT,
            "--model", $Task.modelTag,
            "--years", "$YEARS",
            "--agents", "$AGENTS",
            "--workers", "$WORKERS",
            "--governance-mode", "strict",
            "--memory-engine", $Task.mem,
            "--window-size", "5",
            "--initial-agents", $PROFILES,
            "--output", $outDir,
            "--seed", "$SEED",
            "--memory-seed", "$SEED",
            "--num-ctx", "$($Task.ctx)",
            "--num-predict", "$($Task.pred)"
        )
        if ($Task.priority) {
            $args += "--use-priority-schema"
        }

        & python @args 1> $logOut 2> $logErr
        $code = $LASTEXITCODE

        if ($code -eq 0 -and (Test-Path $simPath)) {
            $size = (Get-Item $simPath).Length
            if ($size -gt 0) {
                Write-Host "[DONE] $($Task.modelDir) $($Task.group) Run_3" -ForegroundColor Green
                return $true
            }
        }

        Write-Host "[RETRY] $($Task.modelDir) $($Task.group) failed (code=$code), restarting Ollama..." -ForegroundColor Red
        Restart-Ollama
    }

    Write-Host "[FAIL] $($Task.modelDir) $($Task.group) Run_3 exhausted retries." -ForegroundColor Red
    return $false
}

$missing = @()
foreach ($task in $queue) {
    $simPath = Get-SimPath -Task $task
    if (-not (Test-Path $simPath)) {
        $missing += $task
    }
}

if ($missing.Count -eq 0) {
    Write-Host "[OK] No missing Run_3 cells in queue." -ForegroundColor Green
    exit 0
}

Write-Host "============================================" -ForegroundColor Magenta
Write-Host "Run_3 queue size (missing): $($missing.Count)" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
foreach ($t in $missing) {
    Write-Host (" - {0} {1}" -f $t.modelDir, $t.group)
}

if ($ListOnly) {
    Write-Host "[LIST-ONLY] No jobs executed." -ForegroundColor Yellow
    exit 0
}

# Ensure this scheduler is the only experiment runner
Stop-StrayExperimentProcs
Restart-Ollama

$ok = 0
$fail = 0
foreach ($t in $missing) {
    $result = Run-Task -Task $t
    if ($result) { $ok++ } else { $fail++ }
}

Write-Host "============================================" -ForegroundColor Magenta
Write-Host "Scheduler done. Success=$ok Fail=$fail" -ForegroundColor Magenta
Write-Host "Logs: $LOG_ROOT" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
