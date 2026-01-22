# =============================================================================
# DeepSeek Scaling Law Experiment Script
# =============================================================================
# Purpose: Run multi-group experiments across DeepSeek-R1 model sizes
# Output: results/JOH_FINAL/deepseek_r1_{size}/Group_{X}/Run_1/
# =============================================================================

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] === STARTING DEEPSEEK SCALING LAW EXPERIMENT ===" -ForegroundColor Cyan

# --- CONFIGURATION ---
$Models = @(
    # Tier 1: Tiny (1.5B)
    @{ Name="DeepSeek-R1-1.5B"; Tag="deepseek-r1:1.5b" },
    
    # Tier 2: Base (8B) - Already downloaded
    @{ Name="DeepSeek-R1-8B"; Tag="deepseek-r1:8b" },
    
    # Tier 3: Mid (14B)
    @{ Name="DeepSeek-R1-14B"; Tag="deepseek-r1:14b" },
    
    # Tier 4: Large (32B)
    @{ Name="DeepSeek-R1-32B"; Tag="deepseek-r1:32b" }
)

$Groups = @("Group_A", "Group_B", "Group_C")
$NumYears = 10
$NumAgents = 100
$BaseSeed = 401

# --- MAIN LOOP ---
foreach ($Model in $Models) {
    $ModelName = $Model.Name
    $ModelTag = $Model.Tag
    $SafeName = $ModelTag -replace ":", "_" -replace "-", "_" -replace "\.", "_"
    
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] >>> MODEL: $ModelName ($ModelTag) <<<" -ForegroundColor Yellow
    
    # Pre-flight: Ensure model is available
    Write-Host "  > Pre-flight: Pulling model $ModelTag..."
    $pullResult = ollama pull $ModelTag 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [WARNING] Could not pull model automatically. Assuming it exists." -ForegroundColor Yellow
    }
    
    foreach ($Group in $Groups) {
        $OutputDir = "results/JOH_FINAL/$SafeName/$Group/Run_1"
        
        # Skip if already completed
        if (Test-Path $OutputDir) {
            Write-Host "  [Skip] $OutputDir already exists" -ForegroundColor DarkGray
            continue
        }
        
        Write-Host "  > Running $Group with seed $BaseSeed..."
        
        python run_flood.py `
            --model $ModelTag `
            --years $NumYears `
            --agents $NumAgents `
            --workers 1 `
            --memory-engine humancentric `
            --output $OutputDir `
            --seed $BaseSeed
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  [ERROR] $Group failed for $ModelName" -ForegroundColor Red
        } else {
            Write-Host "  [OK] $Group completed" -ForegroundColor Green
        }
    }
}

Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] === DEEPSEEK SCALING EXPERIMENT COMPLETE ===" -ForegroundColor Cyan
