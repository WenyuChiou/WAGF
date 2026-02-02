# Run Ministral 8b/14b Groups B and C using run_flood.py (broker pipeline)
# Group A is handled separately by run_ministral_groupA_baseline.ps1
#
# Usage: powershell -ExecutionPolicy Bypass -File run_ministral_8b14b_BC.ps1

$BASE = "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$YEARS = 10
$AGENTS = 100
$SEED = 42
$CTX = 8192
$PRED = 1536

Set-Location $BASE

$models = @(
    @{tag="8b"; dir="ministral3_8b"; ollama="ministral-3:8b"},
    @{tag="14b"; dir="ministral3_14b"; ollama="ministral-3:14b"}
)

foreach ($m in $models) {
    $OUT_BASE = "examples/single_agent/results/JOH_FINAL/$($m.dir)"

    # Group B: Governed + Window Memory
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  $($m.ollama) - Group B (governed + window)" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    python examples/single_agent/run_flood.py `
        --model $($m.ollama) --years $YEARS --agents $AGENTS --workers 1 `
        --governance-mode strict --memory-engine window --window-size 5 `
        --initial-agents $PROFILES `
        --output "$OUT_BASE/Group_B/Run_1" `
        --seed $SEED --num-ctx $CTX --num-predict $PRED

    # Group C: Governed + HumanCentric + Priority Schema
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  $($m.ollama) - Group C (governed + humancentric)" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    python examples/single_agent/run_flood.py `
        --model $($m.ollama) --years $YEARS --agents $AGENTS --workers 1 `
        --governance-mode strict --memory-engine humancentric --window-size 5 `
        --use-priority-schema `
        --initial-agents $PROFILES `
        --output "$OUT_BASE/Group_C/Run_1" `
        --seed $SEED --num-ctx $CTX --num-predict $PRED
}

Write-Host ""
Write-Host "All Ministral 8b/14b Groups B/C complete." -ForegroundColor Cyan
