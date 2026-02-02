# Run ALL flood B/C experiments with v7 code (action feedback + reasoning-before-rating)
# 6 models x 2 groups = 12 runs, sequential, smallest first
#
# Usage: powershell -ExecutionPolicy Bypass -File run_flood_BC_v7.ps1

$BASE = "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$YEARS = 10
$AGENTS = 100
$SEED = 42
$CTX = 8192
$PRED = 1536

Set-Location $BASE

$models = @(
    @{tag="gemma3:4b";     dir="gemma3_4b"},
    @{tag="gemma3:12b";    dir="gemma3_12b"},
    @{tag="ministral-3:3b"; dir="ministral3_3b"},
    @{tag="ministral-3:8b"; dir="ministral3_8b"},
    @{tag="ministral-3:14b"; dir="ministral3_14b"},
    @{tag="gemma3:27b";    dir="gemma3_27b"}
)

foreach ($m in $models) {
    $MODEL = $m.tag
    $OUT_BASE = "examples/single_agent/results/JOH_FINAL/$($m.dir)"

    # Group B: Governed + Window Memory
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  $MODEL - Group B (governed + window)" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $YEARS --agents $AGENTS --workers 1 `
        --governance-mode strict --memory-engine window --window-size 5 `
        --initial-agents $PROFILES `
        --output "$OUT_BASE/Group_B/Run_1" `
        --seed $SEED --num-ctx $CTX --num-predict $PRED

    # Group C: Governed + HumanCentric Memory
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  $MODEL - Group C (governed + humancentric)" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $YEARS --agents $AGENTS --workers 1 `
        --governance-mode strict --memory-engine humancentric --window-size 5 `
        --initial-agents $PROFILES `
        --output "$OUT_BASE/Group_C/Run_1" `
        --seed $SEED --num-ctx $CTX --num-predict $PRED
}

Write-Host ""
Write-Host "All 12 flood B/C v7 experiments complete." -ForegroundColor Cyan
