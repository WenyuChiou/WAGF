Write-Host "============================================="
Write-Host "STARTING COMPARATIVE BENCHMARK (PHASE 16)"
Write-Host "============================================="

Write-Host "--- Model 1: Gemma 3 (4B) ---"
python examples/v2-2_clean_skill_governed/run_experiment.py --model gemma3:4b

Write-Host "--- Model 2: Llama 3.2 (3B) ---"
python examples/v2-2_clean_skill_governed/run_experiment.py --model llama3.2:3b

Write-Host "--- Model 3: DeepSeek R1 (1.5B) ---"
python examples/v2-2_clean_skill_governed/run_experiment.py --model deepseek-r1:1.5b

Write-Host "--- Model 4: GPT-OSS (Validation) ---"
python examples/v2-2_clean_skill_governed/run_experiment.py --model gpt-oss:latest

Write-Host "============================================="
Write-Host "BENCHMARK COMPLETED"
Write-Host "============================================="
