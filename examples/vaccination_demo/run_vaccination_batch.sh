#!/usr/bin/env bash
# vaccination_demo Tier-2 showcase batch runner (Phase L3-1E, 2026-05-24).
#
# Runs the L3-1A → L3-1D vaccination_demo across 3 seeds × 2 models =
# 6 runs, producing per-run audit CSVs + reproducibility_manifest.json
# under examples/vaccination_demo/results/showcase_v1_seed<S>_<M>/.
#
# Models:
#   gemma3:4b     — primary, ~2-3 min/run on RTX 4080 SUPER
#   gemma4:e4b    — secondary, ~5-7 min/run
# Seeds: 42 / 43 / 44 (paper-1b reference triplet).
# Total wall time: ~30-40 min on the reference GPU.
#
# Run from the repo root:
#   bash examples/vaccination_demo/run_vaccination_batch.sh
#
# To run only one model (e.g. for a quick smoke), set MODELS env:
#   MODELS=gemma3:4b bash examples/vaccination_demo/run_vaccination_batch.sh

set -euo pipefail

# Resolve repo root (one level up from examples/vaccination_demo/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

SEEDS="${SEEDS:-42 43 44}"
MODELS="${MODELS:-gemma3:4b gemma4:e4b}"
YEARS="${YEARS:-5}"
AGENTS="${AGENTS:-25}"

OUTPUT_ROOT="examples/vaccination_demo/results"

echo "=== vaccination_demo Tier-2 batch ==="
echo "  seeds  : ${SEEDS}"
echo "  models : ${MODELS}"
echo "  years  : ${YEARS}"
echo "  agents : ${AGENTS}"
echo "  output : ${OUTPUT_ROOT}/showcase_v1_seed<S>_<M>"
echo

for seed in ${SEEDS}; do
    for model in ${MODELS}; do
        # Replace ':' in model name with '_' so it's filesystem-friendly
        model_slug=$(echo "${model}" | tr ':' '_')
        run_dir="${OUTPUT_ROOT}/showcase_v1_seed${seed}_${model_slug}"

        echo "--- launching seed=${seed} model=${model} → ${run_dir} ---"
        python examples/vaccination_demo/run_experiment.py \
            --model "${model}" \
            --years "${YEARS}" \
            --agents "${AGENTS}" \
            --seed "${seed}" \
            --output "${run_dir}"
        echo
    done
done

echo "=== batch complete; results under ${OUTPUT_ROOT}/showcase_v1_seed* ==="
echo "Run summary: python examples/vaccination_demo/summary.py"
