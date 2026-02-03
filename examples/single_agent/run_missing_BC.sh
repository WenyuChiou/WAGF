#!/bin/bash
# Run missing Group B+C experiments for gemma3:12b + ministral-3 (3b, 8b, 14b)
# Total: 8 experiments (4 models × 2 groups)
# Estimated: ~2-3 hours per experiment → ~16-24 hours total
#
# Prerequisites: Ollama running, no other heavy LLM job active

BASE="c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework"
PROFILES="examples/single_agent/agent_initial_profiles.csv"
YEARS=10
AGENTS=100
SEED=42
CTX=8192
PRED=1536

cd "$BASE"

run_group_b() {
  local MODEL="$1"
  local OUT_DIR="$2"
  echo "============================================"
  echo "  ${MODEL} — Group B (governed + window)"
  echo "  Output: ${OUT_DIR}/Group_B/Run_1"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model "$MODEL" --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode strict --memory-engine window --window-size 5 \
    --initial-agents "$PROFILES" \
    --output "${OUT_DIR}/Group_B/Run_1" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED
}

run_group_c() {
  local MODEL="$1"
  local OUT_DIR="$2"
  echo "============================================"
  echo "  ${MODEL} — Group C (governed + humancentric)"
  echo "  Output: ${OUT_DIR}/Group_C/Run_1"
  echo "============================================"
  python examples/single_agent/run_flood.py \
    --model "$MODEL" --years $YEARS --agents $AGENTS --workers 1 \
    --governance-mode strict --memory-engine humancentric --window-size 5 \
    --use-priority-schema \
    --initial-agents "$PROFILES" \
    --output "${OUT_DIR}/Group_C/Run_1" \
    --seed $SEED --num-ctx $CTX --num-predict $PRED
}

echo "================================================================"
echo "  Starting 8 missing experiments: 4 models × Group B+C"
echo "  $(date)"
echo "================================================================"

# ── 1. gemma3:12b ──
run_group_b "gemma3:12b" "examples/single_agent/results/JOH_FINAL/gemma3_12b"
run_group_c "gemma3:12b" "examples/single_agent/results/JOH_FINAL/gemma3_12b"

# ── 2. ministral-3:3b ──
run_group_b "ministral-3:3b" "examples/single_agent/results/JOH_FINAL/ministral3_3b"
run_group_c "ministral-3:3b" "examples/single_agent/results/JOH_FINAL/ministral3_3b"

# ── 3. ministral-3:8b ──
run_group_b "ministral-3:8b" "examples/single_agent/results/JOH_FINAL/ministral3_8b"
run_group_c "ministral-3:8b" "examples/single_agent/results/JOH_FINAL/ministral3_8b"

# ── 4. ministral-3:14b ──
run_group_b "ministral-3:14b" "examples/single_agent/results/JOH_FINAL/ministral3_14b"
run_group_c "ministral-3:14b" "examples/single_agent/results/JOH_FINAL/ministral3_14b"

echo ""
echo "================================================================"
echo "  All 8 experiments complete."
echo "  $(date)"
echo "================================================================"
