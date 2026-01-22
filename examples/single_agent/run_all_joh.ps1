# JOH Full Experiment Suite - All 60 Runs
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
Set-Location $PSScriptRoot

Log-Progress "=== STARTING FULL JOH EXPERIMENT SUITE (60 RUNS) ==="

# --- GEMMA (30 RUNS) ---
$Groups = @("Group_A", "Group_B", "Group_C")
foreach ($group in $Groups) {
    Log-Progress ">>> GEMMA $group <<<"
    for ($i = 1; $i -le 10; $i++) {
        $seed = 300 + $i
        $outputDir = "results/JOH_FINAL/gemma3_4b/$group/Run_$i"
        
        if (Test-Path $outputDir) { Log-Progress "  [Skip] Run $i already exists"; continue }
        
        Log-Progress "  > Gemma Run $i (Seed $seed)"
        
        if ($group -eq "Group_A") {
            # Use Baseline script for Group A
            python $BaselinePath --output $outputDir --seed $seed --model $GemmaModel
        } elseif ($group -eq "Group_B") {
            # Use Framework (Strict) for Group B
            python run_flood.py --model $GemmaModel --years $NumYears --agents $NumAgents --workers 8 --memory-engine window --governance-mode strict --output $outputDir --seed $seed
        } else {
            # Use Framework (Human-Centric / JOH v1) for Group C
            python run_flood.py --model $GemmaModel --years $NumYears --agents $NumAgents --workers 8 --memory-engine humancentric --governance-mode strict --output $outputDir --seed $seed
        }
    }
}

# --- LLAMA (30 RUNS) ---
foreach ($group in $Groups) {
    Log-Progress ">>> LLAMA $group <<<"
    for ($i = 1; $i -le 10; $i++) {
        $seed = 300 + $i
        $outputDir = "results/JOH_FINAL/llama3_2_3b/$group/Run_$i"
        
        if (Test-Path $outputDir) { Log-Progress "  [Skip] Run $i already exists"; continue }
        
        Log-Progress "  > Llama Run $i (Seed $seed)"
        
        if ($group -eq "Group_A") {
            # Use Baseline script for Group A
            python $BaselinePath --output $outputDir --seed $seed --model $LlamaModel
        } elseif ($group -eq "Group_B") {
            # Use Framework (Strict) for Group B
            python run_flood.py --model $LlamaModel --years $NumYears --agents $NumAgents --workers 8 --memory-engine window --governance-mode strict --output $outputDir --seed $seed
        } else {
            # Use Framework (Human-Centric / JOH v1) for Group C
            python run_flood.py --model $LlamaModel --years $NumYears --agents $NumAgents --workers 8 --memory-engine humancentric --governance-mode strict --output $outputDir --seed $seed
        }
    }
}

Log-Progress "=== FULL JOH EXPERIMENT SUITE COMPLETE ==="
