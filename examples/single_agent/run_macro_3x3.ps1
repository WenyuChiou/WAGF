param (
    [int]$Agents = 100,
    [int]$Years = 10
)

# Macro Benchmark 3x3: Comparing Model Scale (Small vs Large)
# Tiers: Small (~5B) vs Large (~20B)
# Conditions: Group A (Baseline), Group B (Strict Governance), Group C (Memory Enhanced)

$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

# --- CONFIGURATION ---
$SmallModels = @(
    @{ Name="Llama-3.2-3b"; Tag="llama3.2:3b" },
    @{ Name="Gemma-3-4b";   Tag="gemma3:4b" },
    @{ Name="DeepSeek-R1-8b"; Tag="deepseek-r1:8b" }
)

$LargeModels = @(
    @{ Name="GPT-OSS-20b";   Tag="gpt-oss:latest" },
    @{ Name="GPT-OSS-Safe";  Tag="gpt-oss-safeguard:20b" },
    @{ Name="Ministral-8b";  Tag="ministral-3:latest" }
)

$Groups = @("Group_A", "Group_B", "Group_C")
$NumYears = $Years
$NumAgents = $Agents
$Seed = 301 # Consistent seed for comparison

Set-Location $PSScriptRoot

Log-Progress "=== STARTING MACRO BENCHMARK 3X3 ==="

function Run-Model-Matrix {
    param($ModelList, $TierName)
    
    foreach ($model in $ModelList) {
        Log-Progress ">>> [$TierName] MODEL: $($model.Name) ($($model.Tag)) <<<"
        
        foreach ($group in $Groups) {
            $modelSafeName = $model.Tag -replace ":","_" -replace "-","_" -replace "\.","_"
            $outputDir = "results/MACRO_3X3/$TierName/$modelSafeName/$group/Run_1"
            
            if (Test-Path $outputDir) { 
                Log-Progress "  [Skip] $outputDir already exists"
                continue
            }
            
            Log-Progress "  > Running $group (Tier: $TierName)..."
            
            if ($group -eq "Group_A") {
                # Group A: Baseline (No Governance, Window Memory)
                # Using the patched legacy script for exact baseline parity
                $BaselinePath = "../../ref/LLMABMPMT-Final.py"
                python $BaselinePath --output $outputDir --seed $Seed --model $model.Tag --agents $NumAgents --years $NumYears
            } elseif ($group -eq "Group_B") {
                # Group B: Strict Governance, Window Memory
                python run_flood.py --model $model.Tag --years $NumYears --agents $NumAgents --workers 10 --memory-engine window --governance-mode strict --output $outputDir --seed $Seed
            } elseif ($group -eq "Group_C") {
                # Group C: Strict Governance, Human-Centric Memory
                python run_flood.py --model $model.Tag --years $NumYears --agents $NumAgents --workers 10 --memory-engine humancentric --governance-mode strict --output $outputDir --seed $Seed
            }
        }
    }
}

# Run both tiers
Run-Model-Matrix -ModelList $SmallModels -TierName "Small"
Run-Model-Matrix -ModelList $LargeModels -TierName "Large"

Log-Progress "=== MACRO BENCHMARK 3X3 COMPLETE ==="
