
# Overnight Simulation Schedule
# Target Duration: ~8 hours
# Hardware: 1x Local GPU (Sequential execution required)

$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

Log-Progress "STARTING OVERNIGHT BATCH"

# 1. Fill Baseline Gaps (Priority 1: Stats for Paper)
# Llama A/B/C and Gemma A/B/C -> Target N=10
# Estimated time: 30 mins per run x ~20 runs = ~10 hours (Might be too long, let's target N=5 first assuredly, then N=10)

Log-Progress "--- Phase 1: Robust Baseline (Target N=10) ---"

# Gemma Group A (Current: ~5 runs) -> Add 5
# Log-Progress "Running Gemma Group A (5 runs)..."
# python run_baseline_original.py --model "gemma2:9b" --output "results/JOH_FINAL/gemma2_9b/Group_A" --seed 101
# ... (Removed Deprecated Model)


# Llama Group A (Current: ~3 runs) -> Add 5
Log-Progress "Running Llama Group A (5 runs)..."
python run_baseline_original.py --model "llama3.2:3b" --output "results/JOH_FINAL/llama3_2_3b/Group_A" --seed 201
python run_baseline_original.py --model "llama3.2:3b" --output "results/JOH_FINAL/llama3_2_3b/Group_A" --seed 202
python run_baseline_original.py --model "llama3.2:3b" --output "results/JOH_FINAL/llama3_2_3b/Group_A" --seed 203
python run_baseline_original.py --model "llama3.2:3b" --output "results/JOH_FINAL/llama3_2_3b/Group_A" --seed 204
python run_baseline_original.py --model "llama3.2:3b" --output "results/JOH_FINAL/llama3_2_3b/Group_A" --seed 205

# 2. Governed Runs (Group C is Critical)
Log-Progress "--- Phase 2: Governed Runs (Target N=5+) ---"

# Llama Group C (Current: 3 runs) -> Add 2
Log-Progress "Running Llama Group C (2 runs)..."
python run_flood.py --model "llama3.2:3b" --governance "full" --output "results/JOH_FINAL/llama3_2_3b/Group_C/Run_Overnight_1"
python run_flood.py --model "llama3.2:3b" --governance "full" --output "results/JOH_FINAL/llama3_2_3b/Group_C/Run_Overnight_2"

# Gemma Group C (Current: 5 runs) -> Add 2 (Buffer)
# Log-Progress "Running Gemma Group C (2 runs)..."
# (Removed Deprecated Model)


# 3. Stress Tests (Extension)
Log-Progress "--- Phase 3: Stress Test Extension ---"
# Check if previous stress test finished, if so, run format breaker (most intensive)
# run_stress_marathon.ps1 is already running in background. 
# We will queue a specific "Format Breaker" deeply for Llama (prone to failure)
Log-Progress "Running specialized Format Breaker stress for Llama..."
python run_flood.py --model "llama3.2:3b" --governance "full" --stress-test "format" --output "results/JOH_STRESS/llama3_2_3b/format/Overnight"

Log-Progress "OVERNIGHT BATCH COMPLETE"
