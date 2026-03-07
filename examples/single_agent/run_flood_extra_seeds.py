#!/usr/bin/env python3
"""
Batch runner: Add 2 extra seeds (Run_4, Run_5) to all 6 flood models.
Runs both governed (Group_C, HumanCentric memory) and no-validator (Group_C_disabled) conditions.

Existing: Run_1 (seed 42), Run_2 (seed 43), Run_3 (seed 44)
New:      Run_4 (seed 45), Run_5 (seed 46)

Usage:
  python run_flood_extra_seeds.py
  python run_flood_extra_seeds.py --skip-existing
  python run_flood_extra_seeds.py --dry-run
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────
MODELS = [
    ("ministral-3:3b",  "ministral3_3b"),
    ("gemma3:4b",       "gemma3_4b"),
    ("ministral-3:8b",  "ministral3_8b"),
    ("gemma3:12b",      "gemma3_12b"),
    ("ministral-3:14b", "ministral3_14b"),
    ("gemma3:27b",      "gemma3_27b"),
]

EXTRA_SEEDS = [
    (45, "Run_4"),
    (46, "Run_5"),
]

CONDITIONS = [
    {
        "label": "governed",
        "governance_mode": "strict",
        "memory_engine": "humancentric",
        "use_priority_schema": True,
        "results_base": "JOH_FINAL",
        "group_dir": "Group_C",
    },
    {
        "label": "no-validator",
        "governance_mode": "disabled",
        "memory_engine": "humancentric",
        "use_priority_schema": True,
        "results_base": "JOH_ABLATION_DISABLED",
        "group_dir": "Group_C_disabled",
    },
]

YEARS = 10
AGENTS = 100
WINDOW_SIZE = 5

BASE_DIR = Path(__file__).resolve().parent
RUN_SCRIPT = BASE_DIR / "run_flood.py"

# ── Parse args ────────────────────────────────────────────────────────────────
skip_existing = "--skip-existing" in sys.argv
dry_run = "--dry-run" in sys.argv

# ── Build job list ────────────────────────────────────────────────────────────
jobs = []
for cond in CONDITIONS:
    for model_name, model_dir in MODELS:
        for seed, run_name in EXTRA_SEEDS:
            output_dir = (BASE_DIR / "results" / cond["results_base"]
                          / model_dir / cond["group_dir"] / run_name)

            if skip_existing:
                sim_log = output_dir / "simulation_log.csv"
                traces = output_dir / "raw" / "household_traces.jsonl"
                if sim_log.exists():
                    print(f"  SKIP (complete): {cond['label']}/{model_dir}/{run_name}")
                    continue
                if traces.exists():
                    import json
                    try:
                        max_year = 0
                        with open(traces, encoding='utf-8') as f:
                            for line in f:
                                y = json.loads(line).get('year', 0)
                                if y > max_year:
                                    max_year = y
                        if max_year >= YEARS:
                            print(f"  SKIP (traces complete): {cond['label']}/{model_dir}/{run_name}")
                            continue
                    except Exception:
                        pass

            jobs.append({
                'cond_label': cond['label'],
                'model': model_name,
                'model_dir': model_dir,
                'seed': seed,
                'run_name': run_name,
                'output': str(output_dir),
                'governance_mode': cond['governance_mode'],
                'memory_engine': cond['memory_engine'],
                'use_priority_schema': cond['use_priority_schema'],
            })

print(f"\n{'='*60}")
print(f"Flood Extra Seeds Batch — {len(jobs)} jobs to run")
print(f"Models: {', '.join(m[0] for m in MODELS)}")
print(f"Extra seeds: {[s[0] for s in EXTRA_SEEDS]}")
print(f"Conditions: governed + no-validator")
print(f"{'='*60}\n")

if dry_run:
    for i, job in enumerate(jobs, 1):
        print(f"[{i}/{len(jobs)}] {job['cond_label']:12s} | {job['model_dir']:15s} | {job['run_name']}")
    print(f"\n(dry run — {len(jobs)} commands listed)")
    sys.exit(0)

# ── Run jobs ──────────────────────────────────────────────────────────────────
failed = []
for i, job in enumerate(jobs, 1):
    print(f"\n{'─'*60}")
    print(f"[{i}/{len(jobs)}] {job['cond_label']} | {job['model_dir']}/{job['run_name']} "
          f"(seed={job['seed']})")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'─'*60}")

    cmd = [
        sys.executable, str(RUN_SCRIPT),
        "--model", job['model'],
        "--years", str(YEARS),
        "--agents", str(AGENTS),
        "--governance-mode", job['governance_mode'],
        "--memory-engine", job['memory_engine'],
        "--seed", str(job['seed']),
        "--window-size", str(WINDOW_SIZE),
        "--output", job['output'],
    ]
    if job['use_priority_schema']:
        cmd.append("--use-priority-schema")

    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR))
        if result.returncode != 0:
            print(f"  FAILED (exit code {result.returncode})")
            failed.append(f"{job['cond_label']}/{job['model_dir']}/{job['run_name']}")
        else:
            print(f"  DONE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"  ERROR: {e}")
        failed.append(f"{job['cond_label']}/{job['model_dir']}/{job['run_name']} ({e})")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"COMPLETE: {len(jobs) - len(failed)}/{len(jobs)} succeeded")
if failed:
    print(f"FAILED ({len(failed)}):")
    for f in failed:
        print(f"  - {f}")
print(f"{'='*60}")
