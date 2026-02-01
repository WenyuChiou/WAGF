#!/bin/bash
# Run Ministral-3 flood experiments: 3 model sizes × 3 groups × 1 seed
# Models: ministral-3:3b, ministral-3:8b, ministral-3:14b
# No Chinese models (no DeepSeek, no Qwen)

BASE="c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
PROFILES="examples/single_agent/agent_initial_profiles.csv"
YEARS=10
AGENTS=100
SEED=42
CTX=8192
PRED=1536

cd "$BASE"

for MODEL_TAG in 3b 8b 14b; do
  MODEL="ministral-3:${MODEL_TAG}"
  OUT_DIR="examples/single_agent/results/JOH_FINAL/ministral3_${MODEL_TAG}"

  echo "============================================"
  echo "  ${MODEL} — Group A (ungoverned)"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model "$MODEL" --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode disabled --memory-engine window \
    --initial-agents "$PROFILES" \
    --output "${OUT_DIR}/Group_A/Run_1" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED

  echo "============================================"
  echo "  ${MODEL} — Group B (governed + window)"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model "$MODEL" --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode strict --memory-engine window --window-size 5 \
    --initial-agents "$PROFILES" \
    --output "${OUT_DIR}/Group_B/Run_1" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED

  echo "============================================"
  echo "  ${MODEL} — Group C (governed + humancentric)"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model "$MODEL" --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode strict --memory-engine humancentric --window-size 5 \
    --use-priority-schema \
    --initial-agents "$PROFILES" \
    --output "${OUT_DIR}/Group_C/Run_1" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED

done

echo ""
echo "All 9 Ministral experiments complete (3 sizes × 3 groups)."
