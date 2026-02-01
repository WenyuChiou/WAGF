# =============================================================================
# SAGE v6 Full Pipeline — Irrigation v6 + Flood Experiments
# =============================================================================
# Stage 1: Irrigation v6 production run (78 agents, 42 years, gemma3:4b)
# Stage 2: Ministral flood experiments (3 sizes x 3 groups = 9 runs)
# Stage 3: Gemma3:27b Group C flood experiment (1 run)
#
# Each stage checks exit code before proceeding.
# Usage: powershell -ExecutionPolicy Bypass -File examples/run_v6_full_pipeline.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$BASE = "c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
Set-Location $BASE

$SEED = 42
$FLOOD_PROFILES = "examples/single_agent/agent_initial_profiles.csv"
$FLOOD_YEARS = 10
$FLOOD_AGENTS = 100
$FLOOD_CTX = 8192
$FLOOD_PRED = 1536

# =============================================================================
# STAGE 1: Irrigation v6 Production Run
# =============================================================================
Write-Host ""
Write-Host "================================================================"
Write-Host "  STAGE 1: Irrigation v6 Production (gemma3:4b, 78 agents, 42yr)"
Write-Host "================================================================"

python examples/irrigation_abm/run_experiment.py `
    --model gemma3:4b --years 42 --real --seed $SEED `
    --output examples/irrigation_abm/results/production_4b_42yr_v6

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Irrigation v6 failed with exit code $LASTEXITCODE"
    exit 1
}
Write-Host "Irrigation v6 complete."

# =============================================================================
# STAGE 2: Ministral Flood Experiments (3 sizes x 3 groups)
# =============================================================================
Write-Host ""
Write-Host "================================================================"
Write-Host "  STAGE 2: Ministral Flood Experiments (9 runs)"
Write-Host "================================================================"

$ministral_models = @(
    @{tag="3b"; dir="ministral3_3b"},
    @{tag="8b"; dir="ministral3_8b"},
    @{tag="14b"; dir="ministral3_14b"}
)

foreach ($m in $ministral_models) {
    $MODEL = "ministral-3:$($m.tag)"
    $OUT_DIR = "examples/single_agent/results/JOH_FINAL/$($m.dir)"

    Write-Host "--------------------------------------------"
    Write-Host "  $MODEL - Group A (ungoverned)"
    Write-Host "--------------------------------------------"
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $FLOOD_YEARS --agents $FLOOD_AGENTS --workers 1 `
        --governance-mode disabled --memory-engine window `
        --initial-agents $FLOOD_PROFILES `
        --output "$OUT_DIR/Group_A/Run_1" `
        --seed $SEED --num-ctx $FLOOD_CTX --num-predict $FLOOD_PRED

    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: $MODEL Group A failed (exit=$LASTEXITCODE), continuing..."
    }

    Write-Host "--------------------------------------------"
    Write-Host "  $MODEL - Group B (governed + window)"
    Write-Host "--------------------------------------------"
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $FLOOD_YEARS --agents $FLOOD_AGENTS --workers 1 `
        --governance-mode strict --memory-engine window --window-size 5 `
        --initial-agents $FLOOD_PROFILES `
        --output "$OUT_DIR/Group_B/Run_1" `
        --seed $SEED --num-ctx $FLOOD_CTX --num-predict $FLOOD_PRED

    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: $MODEL Group B failed (exit=$LASTEXITCODE), continuing..."
    }

    Write-Host "--------------------------------------------"
    Write-Host "  $MODEL - Group C (governed + humancentric)"
    Write-Host "--------------------------------------------"
    python examples/single_agent/run_flood.py `
        --model $MODEL --years $FLOOD_YEARS --agents $FLOOD_AGENTS --workers 1 `
        --governance-mode strict --memory-engine humancentric --window-size 5 `
        --use-priority-schema `
        --initial-agents $FLOOD_PROFILES `
        --output "$OUT_DIR/Group_C/Run_1" `
        --seed $SEED --num-ctx $FLOOD_CTX --num-predict $FLOOD_PRED

    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: $MODEL Group C failed (exit=$LASTEXITCODE), continuing..."
    }
}

Write-Host ""
Write-Host "Ministral experiments complete (9 runs)."

# =============================================================================
# STAGE 3: Gemma3:27b Group C (missing slot)
# =============================================================================
Write-Host ""
Write-Host "================================================================"
Write-Host "  STAGE 3: Gemma3:27b Group C (governed + humancentric)"
Write-Host "================================================================"

python examples/single_agent/run_flood.py `
    --model gemma3:27b --years $FLOOD_YEARS --agents $FLOOD_AGENTS --workers 1 `
    --governance-mode strict --memory-engine humancentric --window-size 5 `
    --use-priority-schema `
    --initial-agents $FLOOD_PROFILES `
    --output "examples/single_agent/results/JOH_FINAL/gemma3_27b/Group_C/Run_1" `
    --seed $SEED --num-ctx $FLOOD_CTX --num-predict $FLOOD_PRED

if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Gemma3:27b Group C failed (exit=$LASTEXITCODE)"
}

# =============================================================================
# DONE
# =============================================================================
Write-Host ""
Write-Host "================================================================"
Write-Host "  ALL STAGES COMPLETE"
Write-Host "  - Irrigation v6: examples/irrigation_abm/results/production_4b_42yr_v6/"
Write-Host "  - Ministral floods: examples/single_agent/results/JOH_FINAL/ministral3_*/"
Write-Host "  - Gemma3:27b C: examples/single_agent/results/JOH_FINAL/gemma3_27b/Group_C/"
Write-Host "================================================================"
