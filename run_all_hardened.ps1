# Run 4-Model Hardened Benchmark (Parallel)

$seeds = 42
$agents = 100
$years = 10
$base_dir = "results/hardened_benchmark"

# 1. Llama 3.2 3B
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "examples/single_agent/run_experiment.py --model llama3.2:3b --num-agents $agents --num-years $years --output-dir $base_dir --seed $seeds"

# 2. Gemma 3 4B (Rerunning for consistency in the same folder structure)
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "examples/single_agent/run_experiment.py --model gemma3:4b --num-agents $agents --num-years $years --output-dir $base_dir --seed $seeds"

# 3. DeepSeek R1 8B
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "examples/single_agent/run_experiment.py --model deepseek-r1:8b --num-agents $agents --num-years $years --output-dir $base_dir --seed $seeds"

# 4. GPT-OSS (Mock/API)
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "examples/single_agent/run_experiment.py --model gpt-oss:latest --num-agents $agents --num-years $years --output-dir $base_dir --seed $seeds"

Write-Host "Launched 4 models in parallel. Output directory: $base_dir"
