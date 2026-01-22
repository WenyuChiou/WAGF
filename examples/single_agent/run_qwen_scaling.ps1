# Qwen 2.5 Scaling Law Experiment
# 5 Tiers: Tiny (1.5B), Small (3B), Base (7B), Mid (14B), Large (32B)
$ErrorActionPreference = "Stop"

function Log-Progress {
    param([string]$msg)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $msg" -ForegroundColor Cyan
}

# --- CONFIGURATION (Small-to-Large Order for Stability Testing) ---
$Models = @(
    # Tier 1: Tiny (1.7B)
    @{ Name="Qwen3-1.7B"; Tag="qwen3:1.7b" },
    
    # Tier 2: Small (4B)
    @{ Name="Qwen3-4B";   Tag="qwen3:4b" },
    
    # Tier 3: Base (8B)
    @{ Name="Qwen3-8B";   Tag="qwen3:8b" },
    
    # Tier 4: Mid (14B)
    @{ Name="Qwen3-14B";  Tag="qwen3:14b" },
    
    # Tier 5: Large (30B) - User Custom Quantum
    @{ Name="Qwen3-30B";  Tag="qwen3:30b" }
)

$Groups = @("Group_A", "Group_B", "Group_C")
$NumYears = 10
$NumAgents = 100 # CONFIG: Confirmed 100 Agents for Final Publication
$Seeds = @(401)  # Consistent with existing Group A/B data 

Set-Location $PSScriptRoot

Log-Progress "=== STARTING QWEN SCALING LAW EXPERIMENT (JOH FINAL: 100 Agents) ==="

foreach ($model in $Models) {
    Log-Progress ">>> MODEL: $($model.Name) ($($model.Tag)) <<<"
    
    # Attempt to pull the model first to avoid runtime errors
    Log-Progress "  > Pre-flight: Pulling model $($model.Tag)..."
    try {
        ollama pull $model.Tag 2>&1 | Out-Null
        Log-Progress "  > Model pull successful."
    } catch {
        Log-Progress "  [WARNING] Could not pull model automatically. Assuming it exists."
    }

    foreach ($group in $Groups) {
        foreach ($seed in $Seeds) {
            # Sanitize model name for directory safe path
            $modelSafeName = $model.Tag -replace ":","_" -replace "-","_" -replace "\.","_"
            
            # Save to JOH_FINAL folder as requested
            $outputDir = "results/JOH_FINAL/$modelSafeName/$group/Run_1"
            
            if (Test-Path $outputDir) { 
                Log-Progress "  [Skip] $outputDir already exists"
                continue
            }
            
            Log-Progress "  > Running $group with seed $seed..."
            
            if ($group -eq "Group_A") {
                # Group A: Baseline (No Governance)
                # Legacy script is single threaded by nature, but 50 agents helps.
                $BaselinePath = "../../ref/LLMABMPMT-Final.py"
                python $BaselinePath --output $outputDir --seed $seed --model $model.Tag
                
            } elseif ($group -eq "Group_B") {
                # Group B: Strict Governance (Parallelized)
                python run_flood.py --model $model.Tag --years $NumYears --agents $NumAgents --workers 4 --memory-engine window --governance-mode strict --output $outputDir --seed $seed
                
            } elseif ($group -eq "Group_C") {
                # Group C: Memory (Parallelized)
                python run_flood.py --model $model.Tag --years $NumYears --agents $NumAgents --workers 4 --memory-engine humancentric --governance-mode strict --output $outputDir --seed $seed
            }
        }
    }
}

Log-Progress "=== SCALING LAW EXPERIMENT COMPLETE ==="
Log-Progress "Data saved to: results/SCALING_QWEN/"
