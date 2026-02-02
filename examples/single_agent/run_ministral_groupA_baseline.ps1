# Re-run Ministral Group A experiments using LLMABMPMT-Final.py baseline
# This matches the Gemma Group A experimental condition (ungoverned, no broker)
#
# Usage: powershell -ExecutionPolicy Bypass -File run_ministral_groupA_baseline.ps1

$BASE = "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$BASELINE_SCRIPT = "$BASE/ref/LLMABMPMT-Final.py"
$PROFILES = "$BASE/examples/single_agent/agent_initial_profiles.csv"
$FLOOD_YEARS = "$BASE/examples/single_agent/flood_years.csv"
$YEARS = 10
$AGENTS = 100
$SEED = 42

Set-Location $BASE

$models = @(
    @{tag="3b"; dir="ministral3_3b"; ollama="ministral-3:3b"},
    @{tag="8b"; dir="ministral3_8b"; ollama="ministral-3:8b"},
    @{tag="14b"; dir="ministral3_14b"; ollama="ministral-3:14b"}
)

foreach ($m in $models) {
    $OUT_DIR = "examples/single_agent/results/JOH_FINAL/$($m.dir)/Group_A/Run_1"

    # Backup existing data if present
    if (Test-Path $OUT_DIR) {
        $BACKUP = "$OUT_DIR.bak_broker"
        if (Test-Path $BACKUP) { Remove-Item -Recurse -Force $BACKUP }
        Rename-Item $OUT_DIR $BACKUP
        Write-Host "[Backup] Moved existing $($m.dir)/Group_A to .bak_broker" -ForegroundColor Yellow
    }
    New-Item -ItemType Directory -Force -Path $OUT_DIR | Out-Null

    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  $($m.ollama) - Group A (LLMABMPMT-Final baseline)" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan

    python $BASELINE_SCRIPT `
        --model $($m.ollama) `
        --years $YEARS `
        --agents $AGENTS `
        --output $OUT_DIR `
        --seed $SEED `
        --agents-path $PROFILES `
        --flood-years-path $FLOOD_YEARS

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [SUCCESS] $($m.dir) Group_A baseline complete." -ForegroundColor Green
    } else {
        Write-Host "  [FAILURE] $($m.dir) Group_A baseline failed!" -ForegroundColor Red
    }
    Write-Host ""
}

Write-Host "All Ministral Group A baseline runs complete." -ForegroundColor Cyan
Write-Host "Now run Groups B/C with: run_ministral_all.ps1 (skip Group A)" -ForegroundColor Yellow
