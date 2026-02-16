"""
B1 Insurance Premium Doubling — Batch Runner
Runs all 9 experiments sequentially (3 groups × 3 seeds).
Skips any run that already has a simulation_log.csv.

Usage: python examples/single_agent/run_b1_batch.py
"""
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
RESULTS_BASE = BASE_DIR / "results" / "B1_doubled_premium" / "gemma3_4b"
RUN_SCRIPT = BASE_DIR / "run_flood.py"
PROFILES = BASE_DIR / "agent_initial_profiles.csv"

# Group configs: (group_name, governance_mode, memory_engine, extra_args)
GROUPS = [
    ("Group_A", "disabled", "window", []),
    ("Group_B", "strict", "window", []),
    ("Group_C", "strict", "humancentric", ["--use-priority-schema"]),
]

SEEDS = [(1, 42), (2, 4202), (3, 4203)]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    total = len(GROUPS) * len(SEEDS)
    done = 0
    skipped = 0

    log(f"B1 Batch: {total} runs planned")
    log(f"Premium rate: 0.04 (doubled from 0.02 baseline)")
    log("=" * 60)

    for group_name, gov_mode, mem_engine, extra in GROUPS:
        for run_num, seed in SEEDS:
            out_dir = RESULTS_BASE / group_name / f"Run_{run_num}"
            log_file = out_dir / "simulation_log.csv"

            # Skip if already done
            if log_file.exists():
                lines = sum(1 for _ in open(log_file, encoding='utf-8'))
                if lines >= 1000:
                    done += 1
                    skipped += 1
                    log(f"SKIP {group_name}/Run_{run_num} (already complete, {lines} lines)")
                    continue

            done += 1
            log(f"START {group_name}/Run_{run_num} (seed={seed}) [{done}/{total}]")

            cmd = [
                sys.executable, str(RUN_SCRIPT),
                "--model", "gemma3:4b",
                "--years", "10",
                "--agents", "100",
                "--workers", "1",
                "--governance-mode", gov_mode,
                "--memory-engine", mem_engine,
                "--initial-agents", str(PROFILES),
                "--output", str(out_dir),
                "--seed", str(seed),
                "--num-ctx", "8192",
                "--num-predict", "1536",
                "--premium-rate", "0.04",
            ] + extra

            start = datetime.now()
            result = subprocess.run(cmd, capture_output=False)
            elapsed = (datetime.now() - start).total_seconds() / 3600

            if result.returncode == 0:
                log(f"DONE  {group_name}/Run_{run_num} ({elapsed:.1f}h)")
            else:
                log(f"FAIL  {group_name}/Run_{run_num} (exit={result.returncode}, {elapsed:.1f}h)")

    log("=" * 60)
    log(f"Batch complete: {done} runs, {skipped} skipped")

if __name__ == "__main__":
    main()
