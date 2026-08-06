#!/usr/bin/env bash
# Launch one first-attempt seed. The ONLY argument is the seed number.
#
#     bash SUBMISSION_2026/TAE/runs/launch_seed.sh 43
#
# WHY THIS EXISTS
# ---------------
# The five launch commands in launch_firstattempt.md differ in exactly three places:
# --seed, --memory-seed and the --output suffix. Editing two of the three is one
# keystroke away, and the consequence is not a failed run:
#
#   broker/components/analytics/audit.py:164  clear_existing_traces defaults to True
#   broker/components/analytics/audit.py:492  unlinks raw/*_traces.jsonl at construction
#
# so pointing --output at a finished seed's directory DELETES that seed's only durable
# artifact within seconds of launch -- everything else is written at finalize. And
# e3_run_integrity.py never compares the manifest's seed to the directory name, so the
# resulting directory would be certified under the wrong seed.
#
# Here the three fields are derived from one argument, so they cannot disagree.
#
# --memory-seed is pinned to 42 for every seed by the author's decision of 2026-08-06,
# matching the archival v21 batch scripts, which never passed the flag at all. See
# examples/irrigation_abm/experiments/firstattempt_gov_2026-08.md section 2a. It is NOT
# recorded in any artifact the run produces (hazard sweep item A3), which is why this
# script writes it to LAUNCH_COMMAND.txt beside the output.
set -u

SEED="${1:-}"
if [[ ! "$SEED" =~ ^[0-9]+$ ]]; then
    echo "usage: bash $0 <seed>    e.g. bash $0 43" >&2
    exit 2
fi

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO" || exit 1

CONFIG="SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt"
OUT="SUBMISSION_2026/TAE/runs/firstattempt_gov_seed${SEED}"
LOGDIR="SUBMISSION_2026/TAE/runs/_logs"
LOG="${LOGDIR}/seed${SEED}.log"
MEMORY_SEED=42

fail() { echo "  REFUSED: $*" >&2; exit 1; }
ok()   { echo "  ok    $*"; }

echo "=== pre-launch checks, seed ${SEED} ==="

# 1. The output directory must not exist. This is the check that matters most: without it,
#    a mistyped seed silently destroys the previous run's traces.
[[ -e "$OUT" ]] && fail "$OUT already exists. Refusing -- launching here would delete its raw/*_traces.jsonl."
ok "output path is free: $OUT"

# 2. The log must not exist either, or a crash leaves two runs' output interleaved in one file.
[[ -e "$LOG" ]] && fail "$LOG already exists. Move or rename it first."
mkdir -p "$LOGDIR" || fail "cannot create $LOGDIR"
ok "log path is free: $LOG"

# 3. The isolated config must carry BOTH audit keys. Missing executed_skill_columns cannot be
#    added retroactively, and the run would finish 10 hours later without the primary reading.
[[ -d "$CONFIG" ]] || fail "config tree missing: $CONFIG"
for KEY in initial_proposal_columns executed_skill_columns; do
    grep -q "^\s*${KEY}:\s*true" "$CONFIG/agent_types.yaml" \
        || fail "$KEY is not true in $CONFIG/agent_types.yaml"
done
ok "config carries initial_proposal_columns and executed_skill_columns"

# 4. e3_run_integrity.py matches on this directory name. A run against any other config tree
#    fails the gate on every seed, ten hours after the GPU time is spent.
grep -q 'ISOLATED_CONFIG_MARKER = "config_irrigation_firstattempt"' \
    SUBMISSION_2026/TAE/evidence/e3_run_integrity.py \
    || fail "e3's ISOLATED_CONFIG_MARKER no longer matches this config directory name"
ok "config directory name matches e3's marker"

# 5. The model must be resident on the GPU. A driver update moved inference to CPU silently on
#    2026-05-13 and cost four hours before anyone noticed.
GPU="$(PYTHONIOENCODING=utf-8 python -c "
import urllib.request, json
try:
    d = json.load(urllib.request.urlopen('http://localhost:11434/api/ps', timeout=10))
except Exception as e:
    print('UNREACHABLE', e); raise SystemExit
for m in d.get('models', []):
    size = m.get('size', 0)
    print(m['name'], int(100 * m.get('size_vram', 0) / size) if size else 0)
" 2>&1)"
echo "$GPU" | grep -q "gemma3:4b 100" || echo "  WARN  ollama does not report gemma3:4b at 100% GPU -- got: ${GPU:-nothing}"
echo "$GPU" | grep -q "gemma3:4b 100" && ok "gemma3:4b resident at 100% GPU"

# 6. Nothing else may be running. Two concurrent runs evict each other's model.
RUNNING="$(ls -d SUBMISSION_2026/TAE/runs/firstattempt_gov_seed*/ 2>/dev/null \
           | while read -r d; do [[ -f "$d/reproducibility_manifest.json" ]] || echo "$d"; done)"
[[ -n "$RUNNING" ]] && fail "these seed directories have no manifest, so a run may still be live:
$RUNNING"
ok "no unfinished seed directory"

# 7. Disk. Four more runs at roughly 51 MB each is trivial, but ENOSPC at year 38 is the worst
#    failure available, so it costs nothing to look.
AVAIL_KB="$(df -Pk . | awk 'NR==2 {print $4}')"
(( AVAIL_KB < 1048576 )) && fail "under 1 GB free on this volume"
ok "$(( AVAIL_KB / 1048576 )) GB free"

CMD=(python -u examples/irrigation_abm/run_experiment.py
     --model gemma3:4b --real --years 42
     --seed "$SEED" --memory-seed "$MEMORY_SEED" --workers 1
     --governance-mode strict
     --num-ctx 8192 --num-predict 4096
     --config-dir "$CONFIG"
     --output "$OUT")

echo
echo "=== launching ==="
printf '  %s\n' "${CMD[*]}"

# The command is written beside the output BEFORE launching, because --memory-seed reaches no
# artifact the run produces and would otherwise be unrecoverable from the corpus.
mkdir -p "$OUT" 2>/dev/null
{
    echo "# launched $(date -Iseconds)"
    echo "# HEAD $(git rev-parse HEAD)   tag: $(git describe --tags --always 2>/dev/null)"
    echo "# git status --porcelain: $(git status --porcelain | wc -l) entries"
    echo "# broker/ drift since launch tag: $(git status --porcelain -- broker/ | wc -l) uncommitted"
    printf '%s\n' "${CMD[*]}"
} > "$OUT/LAUNCH_COMMAND.txt"
echo "  recorded: $OUT/LAUNCH_COMMAND.txt"

# -u so the runner's print() banner reaches the log. Without it the log captures stderr only,
# and the only human-readable confirmation of seed, agent count and config dir is lost
# (hazard sweep item A4).
echo
PYTHONIOENCODING=utf-8 "${CMD[@]}" > "$LOG" 2>&1
STATUS=$?
echo "  exit=$STATUS   log: $LOG"
exit $STATUS
