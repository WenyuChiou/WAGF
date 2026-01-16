$experiments = @(
    @{model = "gemma3:4b"; engine = "window" }
)

$ErrorActionPreference = "Stop"

Write-Host "--- STARTING GEMMA WINDOW BENCHMARK ---"

foreach ($run in $experiments) {
    $m = $run["model"]
    $e = $run["engine"]
    
    $out_base = "examples/single_agent/results_window"
    
    # Clean directory
    $sanitized_model = $m -replace ":", "_" -replace "\.", "_"
    $target_dir = Join-Path $out_base "${sanitized_model}_strict"
    
    if (Test-Path $target_dir) { 
        Write-Host "Cleaning existing directory: $target_dir"
        cmd /c "rmdir /s /q `"$target_dir`""
        Start-Sleep -Seconds 2
    }
    
    Write-Host ">>> RUNNING: Model=$m | Engine=$e <<<"
    
    # Run with 4 workers, 10 years
    python examples/single_agent/run_flood.py --model "$m" --output "$out_base" --memory-engine "$e" --years 10 --agents 100 --window-size 5 --workers 4
    
    Write-Host ">>> COMPLETED: Model=$m | Engine=$e <<<"
}
