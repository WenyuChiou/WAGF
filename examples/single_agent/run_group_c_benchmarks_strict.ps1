# Re-run Group C Benchmarks with STRICT Governance
# Models: 1.5B, 8B, 14B
# Mode: strict
# Parameters: --num-ctx 8192 --num-predict 1536

$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

$Models = @(
    @{ Tag = "deepseek-r1:1.5b"; Name = "deepseek_r1_1_5b" },
    @{ Tag = "deepseek-r1:8b"; Name = "deepseek_r1_8b" },
    @{ Tag = "deepseek-r1:14b"; Name = "deepseek_r1_14b" }
)

$NumYears = 10
$BaseSeed = 401 # Using 401 as per user request/standard
$SAPath = "examples/single_agent"

Log-Progress "=== STARTING GROUP C STRICT BENCHMARKS ==="

foreach ($Model in $Models) {
    $ModelTag = $Model.Tag
    $ModelName = $Model.Name
    $OutputDir = "$SAPath/results/JOH_FINAL/$ModelName/Group_C/Run_1"
    
    # 1. Clear existing data to force re-run
    if (Test-Path $OutputDir) {
        Log-Progress "  [Cleaning] Deleting existing Group C for $ModelName"
        Remove-Item -Path $OutputDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

    Log-Progress "  > Running $ModelName Group C (Social + Strict)..."
    python $SAPath/run_flood.py `
        --model $ModelTag --years $NumYears --agents 100 --workers 1 `
        --memory-engine humancentric --governance-mode strict --use-priority-schema `
        --initial-agents "$SAPath/agent_initial_profiles.csv" `
        --output $OutputDir --seed $BaseSeed --num-ctx 8192 --num-predict 1536
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] $ModelName failed." -ForegroundColor Red
    }
    else {
        Write-Host "  [OK] $ModelName completed." -ForegroundColor Green
    }
}

Log-Progress "=== GROUP C STRICT BENCHMARKS COMPLETE ==="
