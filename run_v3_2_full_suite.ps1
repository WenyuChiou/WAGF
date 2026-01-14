# v3.2 Full Assessment Suite (v2 Parity Edition)
# Sequentially runs 8 benchmark cases (4 models x 2 memory engines)

$models = @("llama3.2:3b", "gemma3:4b", "deepseek-r1:8b", "gpt-oss:latest")
$engines = @("window", "hierarchical")

# Safety Check: We now use _v2 suffix to avoid sync conflicts in Google Drive
Write-Host "🚀 Preparing v3.2 Evaluation (Window & Hierarchical)..." -ForegroundColor Magenta

foreach ($engine in $engines) {
    foreach ($model in $models) {
        Write-Host "=========================================================" -ForegroundColor Cyan
        Write-Host "🚀 Running Benchmark: $model | Memory: $engine" -ForegroundColor Green
        Write-Host "=========================================================" -ForegroundColor Cyan
        
        # Result directories with _v2 safety suffix
        $output_dir = if ($engine -eq "window") { "examples/single_agent/results_window_v2" } else { "examples/single_agent/results_hierarchical_v2" }
        
        python examples/single_agent/run_flood.py `
            --model $model `
            --years 10 `
            --agents 100 `
            --memory-engine $engine `
            --output $output_dir `
            --verbose
            
        Write-Host "✅ Completed $model ($engine)" -ForegroundColor Yellow
        Write-Host ""
    }
}

Write-Host "🎉 Full v3.2 Assessment Suite (v2) Completed!" -ForegroundColor Green

