$parallel_models = @(
    @{model = "llama3.2:3b"; engine = "window" },
    @{model = "gemma3:4b"; engine = "window" }
)

$others = @(
    @{model = "llama3.2:3b"; engine = "humancentric" },
    @{model = "gemma3:4b"; engine = "humancentric" },
    @{model = "gpt-oss:latest"; engine = "window" },
    @{model = "gpt-oss:latest"; engine = "humancentric" },
    @{model = "deepseek-r1:8b"; engine = "window" },
    @{model = "deepseek-r1:8b"; engine = "humancentric" }
)

$ErrorActionPreference = "Stop"

Write-Host "--- STARTING PARALLEL BATCH (Llama & Gemma Window) ---"
$jobs = @()

foreach ($run in $parallel_models) {
    $m = $run["model"]
    $e = $run["engine"]
    $out_base = "examples/single_agent/results_window"
    
    # Clean directory
    $sanitized_model = $m -replace ":", "_" -replace "\.", "_"
    $target_dir = Join-Path $out_base "${sanitized_model}_strict"
    if (Test-Path $target_dir) { 
        Write-Host "Cleaning: $target_dir"
        cmd /c "rmdir /s /q `"$target_dir`""
        Start-Sleep -Seconds 2
        if (Test-Path $target_dir) {
            Write-Host "WARNING: Could not fully remove $target_dir. Some files may remain locked."
        }
    }
    
    Write-Host ">>> LAUNCHING PARALLEL: Model=$m | Engine=$e <<<"
    # Using Start-Process without -Wait for parallel execution
    $p = Start-Process python -ArgumentList "examples/single_agent/run_flood.py", "--model", "$m", "--output", "$out_base", "--memory-engine", "$e", "--years", "10", "--agents", "100", "--window-size", "5", "--workers", "4" -PassThru -NoNewWindow
    $jobs += $p
}

Write-Host "Waiting for parallel jobs to complete..."
$jobs | Wait-Process
Write-Host ">>> PARALLEL BATCH COMPLETE <<<"
Write-Host ""

Write-Host "--- STARTING SEQUENTIAL BATCH ---"
foreach ($run in $others) {
    $m = $run["model"]
    $e = $run["engine"]
    $out_base = if ($e -eq "window") { "examples/single_agent/results_window" } else { "examples/single_agent/results_humancentric" }
    
    # Clean directory
    $sanitized_model = $m -replace ":", "_" -replace "\.", "_"
    $target_dir = Join-Path $out_base "${sanitized_model}_strict"
    if (Test-Path $target_dir) { 
        Write-Host "Cleaning: $target_dir"
        cmd /c "rmdir /s /q `"$target_dir`""
        Start-Sleep -Seconds 2
        if (Test-Path $target_dir) {
            Write-Host "WARNING: Could not fully remove $target_dir. Some files may remain locked."
        }
    }

    Write-Host ">>> RUNNING SEQUENTIAL: Model=$m | Engine=$e <<<"
    Start-Process python -ArgumentList "examples/single_agent/run_flood.py", "--model", "$m", "--output", "$out_base", "--memory-engine", "$e", "--years", "10", "--agents", "100", "--window-size", "5", "--workers", "4" -Wait -NoNewWindow
    Write-Host ">>> COMPLETED: Model=$m | Engine=$e <<<"
    Write-Host ""
}

Write-Host "--- ALL BENCHMARKS COMPLETE ---"
