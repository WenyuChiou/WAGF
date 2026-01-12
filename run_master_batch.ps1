# Master Batch RUN: Full Comparison (Window vs HumanCentric Memory)
# This script runs all 4 models across both memory engines to provide a complete comparison dataset.

$models = @("gemma3:4b", "llama3.2:3b", "deepseek-r1:8b", "gpt-oss:latest")
$engines = @("window", "humancentric")

foreach ($engine in $engines) {
    # Define output directory based on engine
    $outputDir = "examples/single_agent/results"
    if ($engine -eq "humancentric") {
        $outputDir = "examples/single_agent/results_humancentric"
    }

    Write-Host "#########################################"
    Write-Host "STARTING PHASE: $engine Memory"
    Write-Host "Output Directory: $outputDir"
    Write-Host "#########################################"

    foreach ($model in $models) {
        Write-Host "-----------------------------------------"
        Write-Host "Running: $model | Engine: $engine"
        Write-Host "-----------------------------------------"
        
        python examples/single_agent/run_modular_experiment.py `
            --model $model `
            --agents 100 `
            --years 10 `
            --memory-engine $engine `
            --output $outputDir `
            --verbose
        
        Write-Host "Completed $model for $engine"
        Write-Host ""
    }

    Write-Host "========================================="
    Write-Host "Generating Summary Chart for $engine..."
    Write-Host "========================================="
    # Temporarily point the generator to the right dir if needed (or we'll update the script to take an arg)
    python examples/single_agent/generate_2x4_comparison.py --results $outputDir
}

Write-Host "MASTER BATCH COMPLETED!"
Write-Host "Experimental results available in 'results' (Baseline) and 'results_humancentric' (Enhanced)."
