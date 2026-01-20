# JOH Recovery Script - Resuming Interrupted/Missing Runs
$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

$GemmaModel = "gemma3:4b"
$LlamaModel = "llama3.2:3b"
$NumYears = 10
$NumAgents = 100
$BaselinePath = Join-Path $PSScriptRoot "..\..\ref\LLMABMPMT-Final.py"

Log-Progress "=== STARTING JOH RECOVERY SUITE ==="

# --- GEMMA RECOVERY ---
Log-Progress ">>> GEMMA RECOVERY <<<"

# Gemma Group B: Runs 3 to 10
Log-Progress "--- Gemma Group B (Governed) - Resuming 3-10 ---"
for ($i = 3; $i -le 10; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Gemma B Run $i (Seed $seed)"
    python run_flood.py --model $GemmaModel --years $NumYears --agents $NumAgents --workers 10 --memory-engine window --governance-mode strict --output "results/JOH_FINAL/gemma3_4b/Group_B/Run_$i" --seed $seed
}

# Gemma Group C: Runs 4 to 10
Log-Progress "--- Gemma Group C (Priority) - Resuming 4-10 ---"
for ($i = 4; $i -le 10; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Gemma C Run $i (Seed $seed)"
    python run_flood.py --model $GemmaModel --years $NumYears --agents $NumAgents --workers 10 --memory-engine humancentric --governance-mode strict --use-priority-schema --output "results/JOH_FINAL/gemma3_4b/Group_C/Run_$i" --seed $seed
}

# --- LLAMA RECOVERY ---
Log-Progress ">>> LLAMA RECOVERY <<<"

# Llama Group A: Run 7-10 (Run 7 was partial)
Log-Progress "--- Llama Group A (Baseline) - Resuming 7-10 ---"
for ($i = 7; $i -le 10; $i++) {
    $seed = 300 + $i
    $outputDir = "results/JOH_FINAL/llama3_2_3b/Group_A/Run_$i"
    Log-Progress "  > Llama A Run $i (Seed $seed) - Using LLMABMPMT-Final.py"
    if (Test-Path $outputDir) { Remove-Item -Recurse -Force $outputDir }
    python $BaselinePath --output $outputDir --seed $seed --model $LlamaModel
}

# Llama Group B: Runs 1 to 10
Log-Progress "--- Llama Group B (Governed) - Resuming 1-10 ---"
for ($i = 1; $i -le 10; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Llama B Run $i (Seed $seed)"
    python run_flood.py --model $LlamaModel --years $NumYears --agents $NumAgents --workers 12 --memory-engine window --governance-mode strict --output "results/JOH_FINAL/llama3_2_3b/Group_B/Run_$i" --seed $seed
}

# Llama Group C: Runs 1 to 6
Log-Progress "--- Llama Group C (Priority) - Resuming 1-6 ---"
for ($i = 1; $i -le 6; $i++) {
    $seed = 300 + $i
    Log-Progress "  > Llama C Run $i (Seed $seed)"
    python run_flood.py --model $LlamaModel --years $NumYears --agents $NumAgents --workers 12 --memory-engine humancentric --governance-mode strict --use-priority-schema --output "results/JOH_FINAL/llama3_2_3b/Group_C/Run_$i" --seed $seed
}

Log-Progress "=== JOH RECOVERY SUITE COMPLETE ==="
