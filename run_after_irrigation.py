#!/usr/bin/env python3
"""
Pipeline: Wait for irrigation v21 seed42 → run flood disabled Run_1 + Run_2 + Run_3.

After R5 bug fix (Session AO): all 3 seeds need re-run because _skill_filtering.py
was overwriting context builder's pre-filtered available_skills.

Usage:
    python run_after_irrigation.py
    python run_after_irrigation.py --skip-wait   # Skip irrigation wait, run flood immediately
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import argparse
import subprocess
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SA_DIR = PROJECT_ROOT / "examples" / "single_agent"
IRR_DIR = PROJECT_ROOT / "examples" / "irrigation_abm"
LOG_FILE = PROJECT_ROOT / "pipeline_after_irrigation_log.txt"

# ── Paths ────────────────────────────────────────────────────────────────
FLOOD_SCRIPT = SA_DIR / "run_flood.py"
FLOOD_PROFILES = SA_DIR / "agent_initial_profiles.csv"
FLOOD_DISABLED_BASE = SA_DIR / "results" / "JOH_ABLATION_DISABLED" / "gemma3_4b" / "Group_C_disabled"

IRR_V21_LOG = IRR_DIR / "results" / "production_v21_42yr_seed42" / "simulation_log.csv"
IRR_MIN_LINES = 3000  # 78 agents × 42 years ≈ 3276 lines


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_complete(log_path: Path, min_lines: int) -> bool:
    if not log_path.exists():
        return False
    try:
        return sum(1 for _ in open(log_path, encoding='utf-8')) >= min_lines
    except Exception:
        return False


def wait_for_irrigation():
    """Poll until irrigation v21 seed42 simulation_log.csv is complete."""
    log("Waiting for irrigation v21 seed42 to complete...")
    log(f"  Watching: {IRR_V21_LOG}")
    log(f"  Required: ≥{IRR_MIN_LINES} lines")

    check_interval = 120  # check every 2 min
    while True:
        if is_complete(IRR_V21_LOG, IRR_MIN_LINES):
            log("  ✓ Irrigation v21 seed42 COMPLETE!")
            return True

        # Show progress
        if IRR_V21_LOG.exists():
            try:
                n = sum(1 for _ in open(IRR_V21_LOG, encoding='utf-8'))
                log(f"  ... {n}/{IRR_MIN_LINES} lines")
            except Exception:
                log("  ... file exists but can't read")
        else:
            log("  ... simulation_log.csv not yet created")

        time.sleep(check_interval)


def run_flood_disabled(run_num: int, seed: int, force: bool = False) -> bool:
    """Run one flood disabled experiment."""
    name = f"flood_disabled_Run_{run_num}"
    out_dir = FLOOD_DISABLED_BASE / f"Run_{run_num}"

    if not force and is_complete(out_dir / "simulation_log.csv", 1000):
        log(f"  SKIP {name}: already complete (use --force to re-run)")
        return True

    # Archive old results if they exist (R5 bug fix re-run)
    old_log = out_dir / "simulation_log.csv"
    if old_log.exists():
        archive = out_dir / "simulation_log_pre_r5fix.csv"
        log(f"  Archiving old data → {archive.name}")
        old_log.rename(archive)

    log(f"  Starting {name} (seed={seed})...")
    cmd = [
        sys.executable, str(FLOOD_SCRIPT),
        "--model", "gemma3:4b",
        "--years", "10", "--agents", "100", "--workers", "1",
        "--governance-mode", "disabled",
        "--memory-engine", "humancentric",
        "--initial-agents", str(FLOOD_PROFILES),
        "--output", str(out_dir),
        "--seed", str(seed),
        "--num-ctx", "8192", "--num-predict", "1536",
        "--use-priority-schema",
    ]

    log(f"  CMD: {' '.join(str(c) for c in cmd[-8:])}")
    start = time.time()
    try:
        result = subprocess.run(cmd, capture_output=False, timeout=12 * 3600)
        elapsed_h = (time.time() - start) / 3600
        if result.returncode == 0:
            log(f"  ✓ {name} DONE ({elapsed_h:.1f}h)")
            return True
        else:
            log(f"  ✗ {name} FAILED (exit={result.returncode}, {elapsed_h:.1f}h)")
            return False
    except subprocess.TimeoutExpired:
        log(f"  ✗ {name} TIMEOUT (12h)")
        return False
    except Exception as e:
        log(f"  ✗ {name} ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Post-irrigation flood pipeline")
    parser.add_argument("--skip-wait", action="store_true",
                        help="Skip waiting for irrigation, run flood immediately")
    parser.add_argument("--force", action="store_true",
                        help="Force re-run even if results exist (for R5 bug fix)")
    args = parser.parse_args()

    log("")
    log("=" * 60)
    log("PIPELINE: irrigation v21 → flood disabled Run_1 + Run_2 + Run_3")
    log("=" * 60)

    # Phase 1: Wait for irrigation
    if not args.skip_wait:
        wait_for_irrigation()
        log("  Cooldown 60s...")
        time.sleep(60)
    else:
        log("  Skipping irrigation wait (--skip-wait)")

    # Phase 2: Flood disabled Run_1 + Run_2 + Run_3 (all re-run after R5 bug fix)
    results = {}
    for run_num, seed in [(1, 42), (2, 4202), (3, 4203)]:
        log(f"\n{'─' * 60}")
        log(f"FLOOD DISABLED Run_{run_num} (seed={seed})")
        log(f"{'─' * 60}")
        ok = run_flood_disabled(run_num, seed, force=args.force)
        results[f"Run_{run_num}"] = "PASS" if ok else "FAIL"

        if run_num < 3:
            log("  Cooldown 60s...")
            time.sleep(60)

    # Summary
    log("")
    log("=" * 60)
    log("PIPELINE COMPLETE")
    log("=" * 60)
    for name, status in results.items():
        log(f"  {status}: flood_disabled_{name}")

    n_pass = sum(1 for s in results.values() if s == "PASS")
    n_fail = sum(1 for s in results.values() if s == "FAIL")
    log(f"\n  {n_pass} passed, {n_fail} failed")


if __name__ == "__main__":
    main()
