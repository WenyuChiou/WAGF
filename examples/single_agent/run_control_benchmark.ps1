$models = @("llama3.2:3b", "gemma3:4b", "deepseek-r1:8b", "llama3.1:latest")
$ErrorActionPreference = "Stop"

Write-Host "--- STARTING CONTROL GROUP (GROUP A) BENCHMARK ---"
Write-Host "Target: Generate Baseline Data (No Governance)"
Write-Host ""

foreach ($m in $models) {
    # Output directory for Group A
    $out_base = "results_control"
    
    # Clean directory
    $sanitized_model = $m -replace ":", "_" -replace "\.", "_"
    # Verified: run_flood.py now uses _{governance_mode} suffix
    $target_dir = Join-Path $out_base "${sanitized_model}_disabled" 
    
    if (Test-Path $target_dir) { 
        Write-Host "Cleaning existing directory: $target_dir"
        cmd /c "rmdir /s /q `"$target_dir`""
        Start-Sleep -Seconds 2
    }
    
    Write-Host ">>> RUNNING CONTROL: Model=$m | Governance=DISABLED <<<"
    
    # Run with governance disabled
    python ./run_flood.py --model "$m" --output "$out_base" --memory-engine "window" --governance-mode "disabled" --years 10 --agents 100 --window-size 5 --workers 4
    
    Write-Host ">>> COMPLETED: Model=$m <<<"
    Write-Host "-------------------------------------------"
}

Write-Host "--- CONTROL BENCHMARK COMPLETE ---"
