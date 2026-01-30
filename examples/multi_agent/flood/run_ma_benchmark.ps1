# MA Benchmark Runner
# Runs 3 modes: Isolated, Window, HumanCentric
# Target Model: generic (e.g., llama3.2:3b)

$MODELS = @("llama3.2:3b", "gemma:2b", "deepseek-r1:8b")
$MODES = @("isolated", "window", "humancentric")
$YEARS = 10
$AGENTS = 50 # Smaller batch for MA complexity? Or stay with 100? Let's use 50 for speed parity check first.

# Ensure output dir exists
$BASE_DIR = "examples/multi_agent/results_benchmark"
if (-not (Test-Path $BASE_DIR)) { New-Item -ItemType Directory -Path $BASE_DIR | Out-Null }

foreach ($model in $MODELS) {
    foreach ($mode in $MODES) {
        $runName = "${model}_${mode}".Replace(":", "_").Replace("-", "_")
        $outDir = "$BASE_DIR\$runName"
        
        Write-Host "Starting MA Run: $runName" -ForegroundColor Cyan
        
        # Construct arguments
        $cmdArgs = @(
            "examples/multi_agent/run_unified_experiment.py",
            "--model", $model,
            "--years", $YEARS,
            "--agents", $AGENTS,
            "--output", $outDir,
            "--verbose" # Enable verify log checks
        )
        
        # Mode Logic
        if ($mode -eq "isolated") {
            # No gossip, Window=1 (or just ignore memory)
            # We simulate "Isolated" by disabling gossip and using Window=1
            $cmdArgs += "--memory-engine", "window"
            # Gossip is disabled by default in run_unified_experiment unless --gossip is passed
        }
        elseif ($mode -eq "window") {
            # Standard Window Memory + Gossip
            $cmdArgs += "--memory-engine", "window"
            $cmdArgs += "--gossip"
        }
        elseif ($mode -eq "humancentric") {
            # HumanCentric Memory + Gossip
            $cmdArgs += "--memory-engine", "humancentric"
            $cmdArgs += "--gossip"
        }
        
        # Execution
        Write-Host "Running: python $($cmdArgs -join ' ')"
        # We run sequentially to avoid overloading
        python @cmdArgs
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error in run $runName" -ForegroundColor Red
        } else {
            Write-Host "Finished: $runName" -ForegroundColor Green
        }
    }
}

Write-Host "MA Benchmark Complete."
