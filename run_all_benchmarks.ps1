# Multi-Model Benchmark Suite
# Runs 100-agent, 10-year simulations for 4 major models sequentially.

$models = @("gemma3:4b", "llama3.2:3b", "deepseek-r1:8b", "gpt-oss:latest")
$years = 10
$agents = 100

foreach ($model in $models) {
    Write-Host "=========================================================" -ForegroundColor Cyan
    Write-Host "🚀 Starting Benchmark for Model: $model" -ForegroundColor Green
    Write-Host "=========================================================" -ForegroundColor Cyan
    
    python examples/single_agent/run_flood.py --model $model --years $years --agents $agents
    
    Write-Host "✅ Completed $model" -ForegroundColor Yellow
}

Write-Host "🎉 All benchmarks completed!" -ForegroundColor Green
