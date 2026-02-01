# Run Ministral-3 flood experiments: 3 model sizes x 3 groups x 1 seed
# Models: ministral-3:3b, ministral-3:8b, ministral-3:14b

$BASE = "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
$PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$YEARS = 10
$AGENTS = 100
$SEED = 42
$CTX = 8192
$PRED = 1536

Set-Location $BASE

$models = @(
    @{tag="3b"; dir="ministral3_3b"},
    @{tag="8b"; dir="ministral3_8b"},
    @{tag="14b"; dir="ministral3_14b"}
)

foreach ($m in $models) {
    $MODEL = "ministral-3:$($m.tag)"
    $OUT_DIR = "examples/single_agent/results/JOH_FINAL/$($m.dir)"

    Write-Host "============================================"
    Write-Host "  $MODEL - Group A (ungoverned)"
    Write-Host "============================================"
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $YEARS --agents $AGENTS --workers 1 `
        --governance-mode disabled --memory-engine window `
        --initial-agents $PROFILES `
        --output "$OUT_DIR/Group_A/Run_1" `
        --seed $SEED --num-ctx $CTX --num-predict $PRED

    Write-Host "============================================"
    Write-Host "  $MODEL - Group B (governed + window)"
    Write-Host "============================================"
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $YEARS --agents $AGENTS --workers 1 `
        --governance-mode strict --memory-engine window --window-size 5 `
        --initial-agents $PROFILES `
        --output "$OUT_DIR/Group_B/Run_1" `
        --seed $SEED --num-ctx $CTX --num-predict $PRED

    Write-Host "============================================"
    Write-Host "  $MODEL - Group C (governed + humancentric)"
    Write-Host "============================================"
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $YEARS --agents $AGENTS --workers 1 `
        --governance-mode strict --memory-engine humancentric --window-size 5 `
        --use-priority-schema `
        --initial-agents $PROFILES `
        --output "$OUT_DIR/Group_C/Run_1" `
        --seed $SEED --num-ctx $CTX --num-predict $PRED
}

Write-Host ""
Write-Host "All 9 Ministral experiments complete (3 sizes x 3 groups)."
