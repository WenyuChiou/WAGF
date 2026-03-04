#!/usr/bin/env python3
"""
Nature Water Irrigation Pipeline v21 — waits for flood ablation to finish,
then runs all irrigation experiments with the v21 execute_skill fix.

v21 fix: All skills use agent["request"] as base (symmetric).
Previous v20 used diversion for increase, water_right for decrease.

Usage:
    python examples/irrigation_abm/run_nw_pipeline.py

    # Skip wait (if flood ablation already finished):
    python examples/irrigation_abm/run_nw_pipeline.py --skip-wait

    # Resume from experiment N:
    python examples/irrigation_abm/run_nw_pipeline.py --skip-wait --start-from 6
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IRRIGATION_DIR = PROJECT_ROOT / "examples" / "irrigation_abm"
RESULTS_DIR = IRRIGATION_DIR / "results"
LOG_FILE = RESULTS_DIR / "pipeline_v21_log.txt"

# Flood ablation process to wait for (disabled governance, last in queue)
FLOOD_ABLATION_SCRIPT = "run_ablation_disabled.py"

SEEDS = [42, 43, 44, 45, 46]

# ── v21 Experiment definitions ─────────────────────────────────────────
EXPERIMENTS = []

# 1. Governed × 5 seeds (~10-12h each)
for s in SEEDS:
    EXPERIMENTS.append({
        "name": f"governed_v21_seed{s}",
        "script": "run_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real",
                 "--seed", str(s),
                 "--output", str(RESULTS_DIR / f"production_v21_42yr_seed{s}")],
    })

# 2. Ungoverned × 5 seeds (~5-6h each)
for s in SEEDS:
    EXPERIMENTS.append({
        "name": f"ungoverned_v21_seed{s}",
        "script": "run_ungoverned_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real",
                 "--seed", str(s),
                 "--output", str(RESULTS_DIR / f"ungoverned_v21_42yr_seed{s}")],
    })

# 3. No-ceiling ablation × 5 seeds (~10-12h each)
for s in SEEDS:
    EXPERIMENTS.append({
        "name": f"noceil_v21_seed{s}",
        "script": "run_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real",
                 "--seed", str(s),
                 "--ablation-mode", "no_demand_ceiling",
                 "--output", str(RESULTS_DIR / f"ablation_no_ceiling_v21_seed{s}")],
    })


def log(msg: str):
    """Print and append to log file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_flood_ablation_running() -> bool:
    """Check if the flood ablation process is still alive."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f"Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             f"Where-Object {{ $_.CommandLine -like '*{FLOOD_ABLATION_SCRIPT}*' }} | "
             f"Select-Object ProcessId"],
            capture_output=True, text=True, timeout=30
        )
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        pids = [l for l in lines if l.isdigit()]
        return len(pids) > 0
    except Exception as e:
        log(f"  WARNING: Could not check process status: {e}")
        return True  # Assume still running on error


def wait_for_flood_ablation(poll_interval: int):
    """Poll until the flood ablation experiment finishes."""
    log("=" * 70)
    log("PIPELINE: Waiting for flood ablation to finish...")
    log(f"  Polling every {poll_interval}s for process: {FLOOD_ABLATION_SCRIPT}")
    log("=" * 70)

    check_count = 0
    while is_flood_ablation_running():
        check_count += 1
        if check_count % 10 == 0:
            log(f"  Still waiting... (check #{check_count})")
        time.sleep(poll_interval)

    log("Flood ablation FINISHED. Starting irrigation v21 pipeline.")
    log("  Waiting 30s for GPU memory release...")
    time.sleep(30)


def run_experiment(exp: dict, index: int, total: int) -> bool:
    """Run a single experiment and return success status."""
    name = exp["name"]
    script = IRRIGATION_DIR / exp["script"]
    args = exp["args"]

    # Skip if output already has a complete simulation log
    out_idx = None
    for j, a in enumerate(args):
        if a == "--output" and j + 1 < len(args):
            out_idx = j + 1
            break
    if out_idx is not None:
        out_dir = Path(args[out_idx])
        sim_log = out_dir / "simulation_log.csv"
        if sim_log.exists():
            try:
                n_lines = sum(1 for _ in open(sim_log, encoding="utf-8"))
                if n_lines >= 3000:  # 78 agents × 42 years = 3276 + header
                    log(f"  SKIP {name}: already complete ({n_lines} lines)")
                    return True
            except Exception:
                pass

    log("-" * 70)
    log(f"EXPERIMENT {index}/{total}: {name}")
    log(f"  Args: {' '.join(args)}")
    log("-" * 70)

    start = time.time()
    cmd = [sys.executable, str(script)] + args

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=86400,  # 24h max
            capture_output=False,
        )
        elapsed = time.time() - start
        hours = elapsed / 3600

        if result.returncode == 0:
            log(f"  DONE: {name} ({hours:.1f}h)")
            return True
        else:
            log(f"  FAILED: {name} (exit={result.returncode}, {hours:.1f}h)")
            return False

    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT: {name} exceeded 24h limit")
        return False
    except Exception as e:
        log(f"  ERROR: {name} — {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="NW Irrigation v21 Pipeline (wait for flood ablation)")
    parser.add_argument("--poll", type=int, default=120,
                        help="Poll interval in seconds (default: 120)")
    parser.add_argument("--skip-wait", action="store_true",
                        help="Skip waiting for flood ablation")
    parser.add_argument("--start-from", type=int, default=1,
                        help="Start from experiment N (1-indexed, for resuming)")
    parser.add_argument("--stop-at", type=int, default=None,
                        help="Stop after experiment N (1-indexed, e.g. 10 = skip no-ceiling)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    total = len(EXPERIMENTS)
    log("=" * 70)
    log("NATURE WATER IRRIGATION v21 PIPELINE")
    log(f"  Fix: execute_skill base unified to agent['request']")
    log(f"  Total experiments: {total}")
    log(f"    Governed:   5 seeds × 42yr  (~50-60h)")
    log(f"    Ungoverned: 5 seeds × 42yr  (~25-30h)")
    log(f"    No-ceiling: 5 seeds × 42yr  (~50-60h)")
    log(f"  Start from: #{args.start_from}")
    log(f"  Estimated total time: 125-150 hours")
    log("=" * 70)

    # Phase 1: Wait for flood ablation (3 seeds)
    if not args.skip_wait:
        if is_flood_ablation_running():
            wait_for_flood_ablation(args.poll)
        else:
            log("Flood ablation not running. Starting immediately.")
    else:
        log("--skip-wait: Starting immediately.")

    # Phase 2: Run irrigation experiments
    results = {}
    pipeline_start = time.time()

    for i, exp in enumerate(EXPERIMENTS, 1):
        if i < args.start_from:
            log(f"  Skipping #{i} {exp['name']} (--start-from={args.start_from})")
            continue
        if args.stop_at is not None and i > args.stop_at:
            log(f"  Stopping at #{args.stop_at} (--stop-at)")
            break

        success = run_experiment(exp, i, total)
        results[exp["name"]] = "PASS" if success else "FAIL"

        if not success:
            log(f"  WARNING: {exp['name']} failed. Continuing with next.")

        # GPU cooldown between experiments
        if i < total:
            log("  Cooling down 15s...")
            time.sleep(15)

    # Phase 3: Summary
    pipeline_elapsed = (time.time() - pipeline_start) / 3600
    log("")
    log("=" * 70)
    log(f"PIPELINE COMPLETE — {pipeline_elapsed:.1f}h total")
    log("=" * 70)
    for name, status in results.items():
        log(f"  {status}: {name}")

    n_pass = sum(1 for s in results.values() if s == "PASS")
    n_fail = sum(1 for s in results.values() if s == "FAIL")
    log(f"  {n_pass}/{n_pass + n_fail} experiments succeeded")

    if n_fail > 0:
        log("  NOTE: Resume with --start-from=N --skip-wait")

    log("")
    log("NEXT STEPS:")
    log("  1. Run analysis: python examples/irrigation_abm/analysis/nw_data_verification.py")
    log("  2. Regenerate figures: python paper/nature_water/scripts/gen_fig2_irrigation.py")
    log("  3. Update results section with v21 numbers")


if __name__ == "__main__":
    main()
