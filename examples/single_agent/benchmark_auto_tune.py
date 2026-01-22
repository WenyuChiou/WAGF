#!/usr/bin/env python
"""
Auto-Tune A/B Benchmark
=======================
Tests whether the Adaptive Performance Module improves efficiency
while maintaining correct JSON parsing across different model sizes.

Metrics tracked:
- Runtime (seconds per agent-year)
- JSON Parse Success Rate (%)
- Action Rate (sanity check)

Usage:
    python benchmark_auto_tune.py
"""
import subprocess
import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from broker.utils.performance_tuner import get_optimal_config, parse_model_size, get_available_vram

# ============================================================================
# Configuration
# ============================================================================
MODELS = [
    "qwen3:1.7b",
    "qwen3:4b",
]

# Short test: 10 agents, 3 years (for quick benchmark)
NUM_AGENTS = 10
NUM_YEARS = 3

OUTPUT_BASE = Path(__file__).parent / "benchmark_autotune"

def run_experiment(model: str, use_auto_tune: bool, output_dir: Path) -> dict:
    """Run a single experiment and return metrics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build command
    workers_arg = "0" if use_auto_tune else "4"  # 0 = auto-tune, 4 = default
    
    cmd = [
        "python", "run_flood.py",
        "--model", model,
        "--workers", workers_arg,
        "--agents", str(NUM_AGENTS),
        "--years", str(NUM_YEARS),
        "--governance-mode", "strict",
        "--output", str(output_dir),
    ]
    
    print(f"\n{'='*60}")
    print(f"Running: {model} | AutoTune: {use_auto_tune}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    result = subprocess.run(
        cmd,
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True
    )
    
    elapsed = time.time() - start_time
    
    # Parse results from output directory
    metrics = {
        "model": model,
        "auto_tune": use_auto_tune,
        "runtime_seconds": elapsed,
        "runtime_per_agent_year": elapsed / (NUM_AGENTS * NUM_YEARS),
        "success": result.returncode == 0,
        "error": result.stderr if result.returncode != 0 else None
    }
    
    # Try to extract JSON parse success from logs
    if result.returncode == 0:
        metrics.update(parse_experiment_results(output_dir, model))
    
    return metrics


def parse_experiment_results(output_dir: Path, model: str) -> dict:
    """Parse experiment output to extract parse success and action rates."""
    model_folder = model.replace(":", "_").replace("-", "_").replace(".", "_") + "_strict"
    result_path = output_dir / model_folder
    
    # Look for simulation_log.csv
    log_file = result_path / "simulation_log.csv"
    
    if not log_file.exists():
        return {"parse_success_rate": None, "action_rate": None}
    
    import pandas as pd
    df = pd.read_csv(log_file)
    
    # Count JSON errors (if any rejected/aborted due to parse failures)
    total = len(df)
    
    # Parse success = approved or rejected (both mean JSON was valid)
    # Failed parse = usually shows as "aborted" or error in reasoning
    if "decision_status" in df.columns:
        approved = (df["decision_status"] == "APPROVED").sum()
        rejected = (df["decision_status"] == "REJECTED").sum()
        parse_success = (approved + rejected) / total if total > 0 else 0
    else:
        parse_success = None
    
    # Action rate (any non-"Do Nothing" action)
    if "action" in df.columns:
        actions = df["action"].apply(lambda x: x != "Do Nothing" if pd.notna(x) else False).sum()
        action_rate = actions / total if total > 0 else 0
    else:
        action_rate = None
    
    return {
        "parse_success_rate": parse_success,
        "action_rate": action_rate,
        "total_decisions": total
    }


def format_results(results: list) -> str:
    """Format results as a markdown table."""
    lines = [
        "# Auto-Tune A/B Benchmark Results",
        "",
        f"**Test Config**: {NUM_AGENTS} agents × {NUM_YEARS} years",
        f"**VRAM Detected**: {get_available_vram():.1f} GB",
        "",
        "## Results Table",
        "",
        "| Model | Auto-Tune | Runtime (s) | Per Agent-Year (s) | Parse Success | Action Rate |",
        "|-------|-----------|-------------|---------------------|---------------|-------------|",
    ]
    
    for r in results:
        auto = "✅ Yes" if r["auto_tune"] else "❌ No"
        runtime = f"{r['runtime_seconds']:.1f}"
        per_ay = f"{r['runtime_per_agent_year']:.2f}"
        parse = f"{r.get('parse_success_rate', 0)*100:.1f}%" if r.get('parse_success_rate') else "N/A"
        action = f"{r.get('action_rate', 0)*100:.1f}%" if r.get('action_rate') else "N/A"
        
        lines.append(f"| {r['model']} | {auto} | {runtime} | {per_ay} | {parse} | {action} |")
    
    # Calculate speedup
    lines.extend(["", "## Speedup Analysis", ""])
    
    for model in MODELS:
        baseline = next((r for r in results if r["model"] == model and not r["auto_tune"]), None)
        tuned = next((r for r in results if r["model"] == model and r["auto_tune"]), None)
        
        if baseline and tuned and tuned["runtime_seconds"] > 0:
            speedup = baseline["runtime_seconds"] / tuned["runtime_seconds"]
            lines.append(f"- **{model}**: {speedup:.2f}x speedup")
    
    return "\n".join(lines)


def main():
    print("="*60)
    print("Auto-Tune A/B Benchmark")
    print("="*60)
    print(f"Models: {MODELS}")
    print(f"Agents: {NUM_AGENTS}, Years: {NUM_YEARS}")
    print(f"VRAM: {get_available_vram():.1f} GB")
    print()
    
    # Show recommended configs
    print("Recommended Configs:")
    for model in MODELS:
        config = get_optimal_config(model)
        print(f"  {model}: workers={config.workers}, num_ctx={config.num_ctx}")
    print()
    
    results = []
    
    # Run A/B tests for each model
    for model in MODELS:
        # A: Default settings (workers=4, default num_ctx)
        output_a = OUTPUT_BASE / "default" / model.replace(":", "_")
        result_a = run_experiment(model, use_auto_tune=False, output_dir=output_a)
        results.append(result_a)
        
        # B: Auto-tuned settings
        output_b = OUTPUT_BASE / "autotune" / model.replace(":", "_")
        result_b = run_experiment(model, use_auto_tune=True, output_dir=output_b)
        results.append(result_b)
    
    # Generate report
    report = format_results(results)
    print("\n" + report)
    
    # Save report
    report_path = OUTPUT_BASE / "benchmark_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\n📊 Report saved to: {report_path}")
    
    # Save raw results as JSON
    json_path = OUTPUT_BASE / "benchmark_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"📋 Raw data saved to: {json_path}")


if __name__ == "__main__":
    main()
