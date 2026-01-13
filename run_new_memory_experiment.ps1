# Run 4-model experiment with HumanCentricMemoryEngine
# Output: results_new_memory/

$models = @("gemma3:4b", "llama3.2:3b", "deepseek-r1:8b", "gpt-oss:latest")

foreach ($model in $models) {
    Write-Host "========================================="
    Write-Host "Running: $model with HumanCentric Memory"
    Write-Host "========================================="
    
    python examples/single_agent/run_flood.py `
        --model $model `
        --agents 100 `
        --years 10 `
        --memory-engine humancentric `
        --output examples/single_agent/results_humancentric
    
    Write-Host "Completed: $model"
    Write-Host ""
}

Write-Host "All 4 models completed!"
