#!/bin/bash
# Run Ministral-3 8B flood experiments: 3 groups × 1 seed
# Model: ministral-3:8b (Mistral's Ministral 8B)

BASE="c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
PROFILES="examples/single_agent/agent_initial_profiles.csv"
MODEL="ministral-3:8b"
YEARS=10
AGENTS=100
SEED=42
CTX=8192
PRED=1536

cd "$BASE"

echo "============================================"
echo "  Ministral-3 8B — Group A (ungoverned)"
echo "============================================"
python examples/single_agent/run_flood.py \
  --model $MODEL --years $YEARS --agents $AGENTS --workers 1 \
  --governance-mode disabled --memory-engine window \
  --initial-agents "$PROFILES" \
  --output "examples/single_agent/results/JOH_FINAL/ministral3_8b/Group_A/Run_1" \
  --seed $SEED --num-ctx $CTX --num-predict $PRED

echo "============================================"
echo "  Ministral-3 8B — Group B (governed + window)"
echo "============================================"
python examples/single_agent/run_flood.py \
  --model $MODEL --years $YEARS --agents $AGENTS --workers 1 \
  --governance-mode strict --memory-engine window --window-size 5 \
  --initial-agents "$PROFILES" \
  --output "examples/single_agent/results/JOH_FINAL/ministral3_8b/Group_B/Run_1" \
  --seed $SEED --num-ctx $CTX --num-predict $PRED

echo "============================================"
echo "  Ministral-3 8B — Group C (governed + humancentric)"
echo "============================================"
python examples/single_agent/run_flood.py \
  --model $MODEL --years $YEARS --agents $AGENTS --workers 1 \
  --governance-mode strict --memory-engine humancentric --window-size 5 \
  --use-priority-schema \
  --initial-agents "$PROFILES" \
  --output "examples/single_agent/results/JOH_FINAL/ministral3_8b/Group_C/Run_1" \
  --seed $SEED --num-ctx $CTX --num-predict $PRED

echo ""
echo "All 3 Ministral experiments complete."
