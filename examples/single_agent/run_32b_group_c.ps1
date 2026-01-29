
# DeepSeek-R1 32B - Group C (Governed + Human-centric Memory)
# This script executes the 10-year, 100-agent simulation with optimized scientific parameters.

$OutputDir = "examples/single_agent/results/JOH_FINAL/deepseek_r1_32b/Group_C/Run_1"
$InitialAgents = "examples/single_agent/agent_initial_profiles.csv"

# Ensure directory exists
if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Force -Path $OutputDir
}

Write-Host ">>> Starting 32B Group C Simulation (Human-centric Memory) <<<" -ForegroundColor Cyan

python examples/single_agent/run_flood.py `
    --model deepseek-r1:32b `
    --years 10 `
    --agents 100 `
    --workers 1 `
    --memory-engine humancentric `
    --governance-mode strict `
    --initial-agents $InitialAgents `
    --output $OutputDir `
    --seed 401 `
    --num-ctx 16384 `
    --num-predict 2048

Write-Host ">>> Simulation Complete! Results saved to $OutputDir <<<" -ForegroundColor Green
