# Run 4-model experiment with WindowMemoryEngine (window_size=3)
# Output: examples/single_agent/results/

$models = @("gemma3:4b", "llama3.2:3b", "deepseek-r1:8b")

foreach ($model in $models) {
    Write-Host "========================================="
    Write-Host "Running: $model with Window Memory (Size=3)"
    Write-Host "========================================="
    
    python examples/single_agent/run_modular_experiment.py `
        --model $model `
        --agents 100 `
        --years 10 `
        --memory-engine window `
        --output examples/single_agent/results `
        --verbose
    
    Write-Host "Completed: $model"
    Write-Host ""
}

Write-Host "All 4 models completed!"

Write-Host "========================================="
Write-Host "Regenerating 2x4 Comparison Chart..."
Write-Host "========================================="
python examples/single_agent/generate_2x4_comparison.py

Write-Host "Batch process finished. All data and charts updated."
