
$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

Log-Progress "STARTING MASTER RERUN BATCH (Target N=10 for Groups A & B)"

# Configuration
$GemmaModel = "gemma3:4b"  # Confirmed tag
$LlamaModel = "llama3.2:3b" # Confirmed tag

# -------------------------------------------------------------
# PHASE 1: GEMMA 3 4B (Fill Gaps)
# -------------------------------------------------------------
Log-Progress "--- Phase 1: Gemma 3 4B ---"

# Group A: Baseline (Naive) - Run 8 times (Seeds 301-308)
Log-Progress "Running Gemma Group A (Naive)..."
for ($i = 1; $i -le 8; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Gemma Group A Run $i (Seed $seed)"
    python run_baseline_original.py --model $GemmaModel --output "results/JOH_FINAL/gemma3_4b/Group_A/Run_Master_$i" --seed $seed
}

# Group B: Governed (Window) - Run 6 times (Seeds 301-306)
Log-Progress "Running Gemma Group B (Window)..."
for ($i = 1; $i -le 6; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Gemma Group B Run $i (Seed $seed)"
    python run_flood.py --model $GemmaModel --years 10 --agents 100 --memory-engine window --governance-mode strict --output "results/JOH_FINAL/gemma3_4b/Group_B/Run_Master_$i" --seed $seed
}

# -------------------------------------------------------------
# PHASE 2: LLAMA 3.2 3B (Fill Gaps)
# -------------------------------------------------------------
Log-Progress "--- Phase 2: Llama 3.2 3B ---"

# Group A: Baseline (Naive) - Run 7 times (Seeds 301-307)
Log-Progress "Running Llama Group A (Naive)..."
for ($i = 1; $i -le 7; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Llama Group A Run $i (Seed $seed)"
    python run_baseline_original.py --model $LlamaModel --output "results/JOH_FINAL/llama3_2_3b/Group_A/Run_Master_$i" --seed $seed
}

# Group B: Governed (Window) - Run 7 times (Seeds 301-307)
Log-Progress "Running Llama Group B (Window)..."
for ($i = 1; $i -le 7; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Llama Group B Run $i (Seed $seed)"
    python run_flood.py --model $LlamaModel --years 10 --agents 100 --memory-engine window --governance-mode strict --output "results/JOH_FINAL/llama3_2_3b/Group_B/Run_Master_$i" --seed $seed
}

Log-Progress "MASTER RERUN COMPLETE. Data gaps filled."
