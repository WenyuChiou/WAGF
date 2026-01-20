# Master JOH Experiment Runner (TRUE BASELINE)
# Group A: Uses ref/LLMABMPMT-Final.py directly (100% original code)
# Group B/C: Uses run_flood.py with governance/priority schema
# N=10 runs per group, Total: 60 runs

$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

# Configuration
$GemmaModel = "gemma3:4b"
$LlamaModel = "llama3.2:3b"
$NumYears = 10
$NumAgents = 100
$BaselinePath = "..\..\ref\LLMABMPMT-Final.py"

Log-Progress "=== STARTING JOH EXPERIMENT SUITE (N=10 per group) ==="
Log-Progress "NOTE: Group A uses ref/LLMABMPMT-Final.py DIRECTLY for 100% parity"

# =============================================================================
# PHASE 1: GEMMA 3 4B
# =============================================================================
Log-Progress ">>> PHASE 1: Gemma 3 4B <<<"

# --- Group A: TRUE BASELINE (LLMABMPMT-Final.py directly) ---
Log-Progress "--- Gemma Group A (TRUE Baseline - LLMABMPMT-Final.py) ---"
for ($i = 1; $i -le 10; $i++) {
    $seed = 300 + $i
    $outputDir = "results/JOH_FINAL/gemma3_4b/Group_A/Run_$i"
    Log-Progress "  > Gemma A Run $i (Seed $seed) - Using LLMABMPMT-Final.py"
    python $BaselinePath --output $outputDir --seed $seed
}

# --- Group B: Governed (Pillar 1+2) ---
Log-Progress "--- Gemma Group B (Governed) ---"
for ($i = 1; $i -le 10; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Gemma B Run $i (Seed $seed)"
    python run_flood.py --model $GemmaModel --years $NumYears --agents $NumAgents --workers 10 --memory-engine window --governance-mode strict --output "results/JOH_FINAL/gemma3_4b/Group_B/Run_$i" --seed $seed
}

# =============================================================================
# PHASE 2: LLAMA 3.2 3B
# =============================================================================
Log-Progress ">>> PHASE 2: Llama 3.2 3B <<<"

# --- Group B: Governed (Pillar 1+2) ---
Log-Progress "--- Llama Group B (Governed) ---"
for ($i = 1; $i -le 10; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Llama B Run $i (Seed $seed)"
    python run_flood.py --model $LlamaModel --years $NumYears --agents $NumAgents --workers 12 --memory-engine window --governance-mode strict --output "results/JOH_FINAL/llama3_2_3b/Group_B/Run_$i" --seed $seed
}

# --- Group C: Priority Schema (Pillar 1+2+3) ---
Log-Progress "--- Llama Group C (Priority Schema) ---"
for ($i = 1; $i -le 10; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Llama C Run $i (Seed $seed)"
    python run_flood.py --model $LlamaModel --years $NumYears --agents $NumAgents --workers 12 --memory-engine humancentric --governance-mode strict --use-priority-schema --output "results/JOH_FINAL/llama3_2_3b/Group_C/Run_$i" --seed $seed
}

# --- Group A: TRUE BASELINE (LLMABMPMT-Final.py directly) ---
Log-Progress "--- Llama Group A (TRUE Baseline - LLMABMPMT-Final.py) ---"
for ($i = 1; $i -le 10; $i++) {
    $seed = 300 + $i
    $outputDir = "results/JOH_FINAL/llama3_2_3b/Group_A/Run_$i"
    Log-Progress "  > Llama A Run $i (Seed $seed) - Using LLMABMPMT-Final.py"
    python $BaselinePath --output $outputDir --seed $seed
}

Log-Progress "=== JOH EXPERIMENT SUITE COMPLETE ==="
Log-Progress "Run 'python check_progress.py' to verify results."
