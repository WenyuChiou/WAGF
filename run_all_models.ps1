# Run All Models Batch Script
$models = @("gemma3:4b", "llama3.2:3b")

foreach ($model in $models) {
    Write-Host "Starting simulation for model: $model"
    $clean_model = $model -replace ":", "_"
    # Run simulation (Default 100 agents)
    python examples/single_agent/run_experiment.py --model $model --output-dir "results"
    
    # Generate Yearly Plot immediately
    Write-Host "Generating Yearly Cumulative Plot for $model..."
    python analyze_yearly_behavior.py --results-dir "results/$clean_model"
    
    Write-Host "Finished $model"
}
