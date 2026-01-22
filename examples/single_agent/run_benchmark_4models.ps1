# Multi-Model Benchmark: DeepSeek & GPT-OSS (Groups A/B/C)
# 2 Models x 3 Groups x 1 Run = 6 Simulations
$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

# --- CONFIGURATION ---
$Models = @(
    @{ Name="DeepSeek-R1-8b"; Tag="deepseek-r1:8b" },
    @{ Name="GPT-OSS-20b";   Tag="gpt-oss:latest" }
)

$Groups = @("Group_A", "Group_B", "Group_C")
$NumYears = 10
$NumAgents = 100
$Seeds = @(301) # Single Run

# Use run_flood.py for ALL groups to ensure DeepSeek <think> tags are stripped correctly
# Group A: Governance=None (Baseline Equivalent)
# Group B: Governance=Strict, Memory=Window
# Group C: Governance=Strict, Memory=HumanCentric

Set-Location $PSScriptRoot

Log-Progress "=== STARTING FOCUSED BENCHMARK: DEEPSEEK & GPT-OSS ==="

foreach ($model in $Models) {
    Log-Progress ">>> MODEL: $($model.Name) ($($model.Tag)) <<<"
    
    foreach ($group in $Groups) {
        foreach ($seed in $Seeds) {
            $modelSafeName = $model.Tag -replace ":","_" -replace "-","_" -replace "\.","_"
            $outputDir = "results/BENCHMARK_2026/$modelSafeName/$group/Run_1"
            
            if (Test-Path $outputDir) { 
                Log-Progress "  [Skip] $outputDir already exists"
                continue
            }
            
            Log-Progress "  > Running $group with seed $seed..."
            
            if ($group -eq "Group_A") {
                # Group A: Baseline (No Governance, Window Memory)
                # Using legacy script directly for 100% parity
                Log-Progress "  > Using legacy baseline (PMT-Final) for Group A parity..."
                $BaselinePath = "../../ref/LLMABMPMT-Final.py"
                python $BaselinePath --output $outputDir --seed $seed --model $model.Tag
            } elseif ($group -eq "Group_B") {
                # Group B: Strict Governance, Window Memory
                python run_flood.py --model $model.Tag --years $NumYears --agents $NumAgents --workers 12 --memory-engine window --governance-mode strict --output $outputDir --seed $seed
            } elseif ($group -eq "Group_C") {
                # Group C: Strict Governance, Human-Centric Memory
                python run_flood.py --model $model.Tag --years $NumYears --agents $NumAgents --workers 12 --memory-engine humancentric --governance-mode strict --output $outputDir --seed $seed
            }
        }
    }
}

Log-Progress "=== BENCHMARK COMPLETE ==="
