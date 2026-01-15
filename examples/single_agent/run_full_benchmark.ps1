$models = @("llama3.2:3b", "gemma3:4b", "gpt-oss:latest", "deepseek-r1:8b")
$engines = @("window", "humancentric")
$ErrorActionPreference = "Stop"

Write-Host "--- STARTING FULL 8-RUN BENCHMARK ---"

foreach ($m in $models) {
    foreach ($e in $engines) {
        $out_base = if ($e -eq "window") { "examples/single_agent/results_window" } else { "examples/single_agent/results_humancentric" }
        
        Write-Host ">>> RUNNING: Model=$m | Engine=$e | Output=$out_base <<<"
        
        # Determine strict output path for cleanup
        $sanitized_model = $m -replace ":", "_" -replace "\.", "_"
        $target_dir = Join-Path $out_base "${sanitized_model}_strict"
        
        # Clean specific directory before start (safety)
        if (Test-Path $target_dir) {
            Write-Host "   Cleaning $target_dir..."
            Remove-Item -Path $target_dir -Recurse -Force
        }
        
        # Execute Python (Blocks until finished)
        Start-Process python -ArgumentList "examples/single_agent/run_flood.py", "--model", "$m", "--output", "$out_base", "--memory-engine", "$e", "--years", "10", "--agents", "100" -Wait -NoNewWindow
        
        Write-Host ">>> COMPLETED: Model=$m | Engine=$e <<<"
        Write-Host ""
    }
}

Write-Host "--- ALL BENCHMARKS COMPLETE ---"
