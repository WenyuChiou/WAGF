$experiments = @(
    # Primary Window/Human-Centric Comparison
    @{model = "llama3.2:3b"; engine = "window" },
    @{model = "llama3.2:3b"; engine = "humancentric" },
    @{model = "gemma3:4b"; engine = "window" },
    @{model = "gemma3:4b"; engine = "humancentric" },
    @{model = "llama3.1:latest"; engine = "window" },
    @{model = "llama3.1:latest"; engine = "humancentric" },
    @{model = "deepseek-r1:8b"; engine = "window" },
    @{model = "deepseek-r1:8b"; engine = "humancentric" }
)

$ErrorActionPreference = "Stop"

Write-Host "--- STARTING FULL SEQUENTIAL BENCHMARK (With Parity Randomness) ---"
Write-Host "Total Experiments: $($experiments.Count)"
Write-Host ""

foreach ($run in $experiments) {
    $m = $run["model"]
    $e = $run["engine"]
    
    # Correct output base directories for analysis script
    $out_base = if ($e -eq "window") { "results_window" } else { "results_humancentric" }
    
    # Clean directory
    $sanitized_model = $m -replace ":", "_" -replace "\.", "_"
    $target_dir = Join-Path $out_base "${sanitized_model}_strict"
    
    if (Test-Path $target_dir) { 
        Write-Host "Cleaning existing directory: $target_dir"
        cmd /c "rmdir /s /q `"$target_dir`""
        Start-Sleep -Seconds 2
    }
    
    Write-Host ">>> RUNNING: Model=$m | Engine=$e <<<"
    Write-Host ">>> Output Base: $out_base"
    
    # Run with 4 workers for speed, seed=None for randomness, window-size=5 for parity
    # Note: --seed is omitted to use dynamic system-time based seed
    python ./run_flood.py --model "$m" --output "$out_base" --memory-engine "$e" --years 10 --agents 100 --window-size 5 --workers 4
    
    Write-Host ">>> COMPLETED: Model=$m | Engine=$e <<<"
    Write-Host "-------------------------------------------"
    Write-Host ""
}

Write-Host "--- ALL BENCHMARKS COMPLETE ---"
