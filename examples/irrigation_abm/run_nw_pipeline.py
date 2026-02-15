#!/usr/bin/env python3
"""
Nature Water Irrigation Pipeline — waits for MA flood to finish, then runs
5 irrigation experiments sequentially (2 governed + 3 ungoverned).

Usage:
    python examples/irrigation_abm/run_nw_pipeline.py

    # Or with a custom poll interval (default 120s):
    python examples/irrigation_abm/run_nw_pipeline.py --poll 60

    # Skip wait (if MA flood already finished):
    python examples/irrigation_abm/run_nw_pipeline.py --skip-wait
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import argparse
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IRRIGATION_DIR = PROJECT_ROOT / "examples" / "irrigation_abm"
RESULTS_DIR = IRRIGATION_DIR / "results"
LOG_FILE = RESULTS_DIR / "pipeline_log.txt"

# MA flood experiment identifier
MA_FLOOD_SCRIPT = "run_unified_experiment.py"

# ── Experiment definitions ──────────────────────────────────────────────
EXPERIMENTS = [
    # Governed replicates (seed 43, 44) — seed 42 already exists
    {
        "name": "governed_seed43",
        "script": "run_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real", "--seed", "43",
                 "--output", str(RESULTS_DIR / "production_v20_42yr_seed43")],
    },
    {
        "name": "governed_seed44",
        "script": "run_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real", "--seed", "44",
                 "--output", str(RESULTS_DIR / "production_v20_42yr_seed44")],
    },
    # Ungoverned replicates (seeds 42, 43, 44)
    {
        "name": "ungoverned_seed42",
        "script": "run_ungoverned_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real", "--seed", "42"],
    },
    {
        "name": "ungoverned_seed43",
        "script": "run_ungoverned_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real", "--seed", "43"],
    },
    {
        "name": "ungoverned_seed44",
        "script": "run_ungoverned_experiment.py",
        "args": ["--model", "gemma3:4b", "--years", "42", "--real", "--seed", "44"],
    },
]


def log(msg: str):
    """Print and append to log file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_ma_flood_running() -> bool:
    """Check if the MA flood experiment process is still alive."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             f"Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             f"Where-Object {{ $_.CommandLine -like '*{MA_FLOOD_SCRIPT}*' }} | "
             f"Select-Object ProcessId"],
            capture_output=True, text=True, timeout=30
        )
        # If any PID returned, it's still running
        lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
        # Filter out headers
        pids = [l for l in lines if l.isdigit()]
        return len(pids) > 0
    except Exception as e:
        log(f"  WARNING: Could not check process status: {e}")
        return True  # Assume still running on error (safer)


def wait_for_ma_flood(poll_interval: int):
    """Poll until the MA flood experiment finishes."""
    log("=" * 70)
    log("PIPELINE: Waiting for MA flood experiment to finish...")
    log(f"  Polling every {poll_interval}s for process: {MA_FLOOD_SCRIPT}")
    log("=" * 70)

    check_count = 0
    while is_ma_flood_running():
        check_count += 1
        if check_count % 10 == 0:
            log(f"  Still waiting... (check #{check_count})")
        time.sleep(poll_interval)

    log("MA flood experiment FINISHED. Starting irrigation pipeline.")
    # Grace period for GPU memory release
    log("  Waiting 30s for GPU memory release...")
    time.sleep(30)


def run_experiment(exp: dict, index: int, total: int) -> bool:
    """Run a single experiment and return success status."""
    name = exp["name"]
    script = IRRIGATION_DIR / exp["script"]
    args = exp["args"]

    log("-" * 70)
    log(f"EXPERIMENT {index}/{total}: {name}")
    log(f"  Script: {script}")
    log(f"  Args: {' '.join(args)}")
    log("-" * 70)

    start = time.time()
    cmd = [sys.executable, str(script)] + args

    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            timeout=86400,  # 24h max per experiment
            capture_output=False,  # Let output stream to console
        )
        elapsed = time.time() - start
        hours = elapsed / 3600

        if result.returncode == 0:
            log(f"  DONE: {name} completed in {hours:.1f}h (exit code 0)")
            return True
        else:
            log(f"  FAILED: {name} exit code {result.returncode} after {hours:.1f}h")
            return False

    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT: {name} exceeded 24h limit")
        return False
    except Exception as e:
        log(f"  ERROR: {name} — {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="NW Irrigation Pipeline")
    parser.add_argument("--poll", type=int, default=120,
                        help="Poll interval in seconds (default: 120)")
    parser.add_argument("--skip-wait", action="store_true",
                        help="Skip waiting for MA flood")
    parser.add_argument("--start-from", type=int, default=1,
                        help="Start from experiment N (1-indexed, for resuming)")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    log("=" * 70)
    log("NATURE WATER IRRIGATION PIPELINE")
    log(f"  Total experiments: {len(EXPERIMENTS)}")
    log(f"  Start from: #{args.start_from}")
    log(f"  Estimated total time: 40-60 hours")
    log("=" * 70)

    # Phase 1: Wait for MA flood
    if not args.skip_wait:
        if is_ma_flood_running():
            wait_for_ma_flood(args.poll)
        else:
            log("MA flood not running. Starting immediately.")
    else:
        log("--skip-wait: Starting immediately.")

    # Phase 2: Run irrigation experiments
    results = {}
    total = len(EXPERIMENTS)
    pipeline_start = time.time()

    for i, exp in enumerate(EXPERIMENTS, 1):
        if i < args.start_from:
            log(f"  Skipping #{i} {exp['name']} (--start-from={args.start_from})")
            continue

        success = run_experiment(exp, i, total)
        results[exp["name"]] = "PASS" if success else "FAIL"

        if not success:
            log(f"  WARNING: {exp['name']} failed. Continuing with next experiment.")

        # Brief pause between experiments for GPU cooldown
        if i < total:
            log("  Cooling down 15s before next experiment...")
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
        log("  NOTE: Failed experiments can be resumed with --start-from=N --skip-wait")

    log("")
    log("NEXT STEPS:")
    log("  1. Run IBR/EHE analysis: python examples/irrigation_abm/compute_ibr.py")
    log("  2. Update paper/nature_water/drafts/section2_v3_results.md with new numbers")
    log("  3. Compute bootstrap CIs + Mann-Whitney U tests")


if __name__ == "__main__":
    main()
