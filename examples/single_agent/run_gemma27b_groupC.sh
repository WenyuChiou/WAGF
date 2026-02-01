#!/bin/bash
# Fill missing gemma3:27b Group_C slot
BASE="c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
PROFILES="examples/single_agent/agent_initial_profiles.csv"

cd "$BASE"

echo "============================================"
echo "  gemma3:27b — Group C (governed + humancentric)"
echo "============================================"
python examples/single_agent/run_flood.py \
  --model gemma3:27b --years 10 --agents 100 --workers 1 \
  --governance-mode strict --memory-engine humancentric --window-size 5 \
  --use-priority-schema \
  --initial-agents "$PROFILES" \
  --output "examples/single_agent/results/JOH_FINAL/gemma3_27b/Group_C/Run_1" \
  --seed 42 --num-ctx 8192 --num-predict 1536

echo "Done."
