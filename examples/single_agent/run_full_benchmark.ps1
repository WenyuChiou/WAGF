$parallel_models = @(
    @{model = "llama3.2:3b"; engine = "window" },
    @{model = "gemma3:4b"; engine = "window" }
)

# Temporarily disabled sequential batch to focus on parallel runs as requested
$others = @()

$ErrorActionPreference = "Stop"

Write-Host "--- STARTING PARALLEL BATCH (Llama & Gemma Window) ---"
$jobs = @()

foreach ($run in $parallel_models) {
    $m = $run["model"]
    $e = $run["engine"]
    
    # Standard output paths
    $out_base = if ($e -eq "window") { "examples/single_agent/results_window" } else { "examples/single_agent/results_humancentric" }
    
    # Clean directory
    $sanitized_model = $m -replace ":", "_" -replace "\.", "_"
    $target_dir = Join-Path $out_base "${sanitized_model}_strict"
    # Cleaner cleanup via cmd
    if (Test-Path $target_dir) { 
        Write-Host "Cleaning: $target_dir"
        cmd /c "rmdir /s /q `"$target_dir`""
        Start-Sleep -Seconds 2
    }
    
    Write-Host ">>> LAUNCHING PARALLEL: Model=$m | Engine=$e <<<"
    $p = Start-Process python -ArgumentList "examples/single_agent/run_flood.py", "--model", "$m", "--output", "$out_base", "--memory-engine", "$e", "--years", "10", "--agents", "100", "--window-size", "5", "--workers", "4" -PassThru -NoNewWindow
    $jobs += $p
}

Write-Host "Waiting for parallel jobs to complete..."
$jobs | Wait-Process
Write-Host ">>> PARALLEL BATCH COMPLETE <<<"
Write-Host ""

if ($others.Count -gt 0) {
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
        }

        Write-Host ">>> RUNNING SEQUENTIAL: Model=$m | Engine=$e <<<"
        Start-Process python -ArgumentList "examples/single_agent/run_flood.py", "--model", "$m", "--output", "$out_base", "--memory-engine", "$e", "--years", "10", "--agents", "100", "--window-size", "5", "--workers", "4" -Wait -NoNewWindow
        Write-Host ">>> COMPLETED: Model=$m | Engine=$e <<<"
        Write-Host ""
    }
}

Write-Host "--- ALL BENCHMARKS COMPLETE ---"
