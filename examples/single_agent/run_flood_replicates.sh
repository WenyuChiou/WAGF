#!/bin/bash
# Run 9 flood replicates: 3 seeds × 3 groups (Gemma3 4B)
# Each run: 100 agents × 10 years
# Seeds: 43, 44, 45 (original Run_1 used seed 401)

BASE="c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
PROFILES="examples/single_agent/agent_initial_profiles.csv"
MODEL="gemma3:4b"
YEARS=10
AGENTS=100
CTX=8192
PRED=1536

cd "$BASE"

for SEED in 43 44 45; do
  echo "============================================"
  echo "  SEED $SEED — Group A (ungoverned)"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model $MODEL --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode disabled --memory-engine window \
    --initial-agents "$PROFILES" \
    --output "examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_A/Seed_${SEED}" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED

  echo "============================================"
  echo "  SEED $SEED — Group B (governed + window)"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model $MODEL --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode strict --memory-engine window --window-size 5 \
    --initial-agents "$PROFILES" \
    --output "examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_B/Seed_${SEED}" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED

  echo "============================================"
  echo "  SEED $SEED — Group C (governed + humancentric)"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model $MODEL --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode strict --memory-engine humancentric --window-size 5 \
    --use-priority-schema \
    --initial-agents "$PROFILES" \
    --output "examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_C/Seed_${SEED}" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED
done

echo ""
echo "All 9 replicates complete."
