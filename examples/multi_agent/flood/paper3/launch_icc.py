"""Standalone ICC probing launcher.

Ensures gemma3:4b is loaded, stops competing models, then runs ICC probing.
Designed to be run detached via: start /B python paper3/launch_icc.py > paper3/results/cv/icc_log.txt 2>&1

Usage:
    python paper3/launch_icc.py [--replicates 30] [--model gemma3:4b]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

def stop_other_models(target_model: str):
    """Stop all Ollama models except target."""
    try:
        result = subprocess.run(
            ["ollama", "ps"], capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if parts and parts[0] != target_model:
                model_name = parts[0]
                print(f"Stopping {model_name}...")
                subprocess.run(["ollama", "stop", model_name], timeout=120)
                time.sleep(2)
    except Exception as e:
        print(f"Warning: could not check running models: {e}")


def preload_model(model: str):
    """Pre-load target model into GPU memory."""
    import requests
    print(f"Pre-loading {model}...")
    try:
        resp = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": "Say hello.",
                "stream": False,
                "keep_alive": "120m",
                "options": {"num_predict": 5},
            },
            timeout=120,
        )
        if resp.status_code == 200:
            print(f"Model {model} loaded successfully.")
        else:
            print(f"Warning: model load returned {resp.status_code}")
    except Exception as e:
        print(f"Warning: pre-load failed: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemma3:4b")
    parser.add_argument("--replicates", type=int, default=30)
    args = parser.parse_args()

    # Setup paths
    flood_dir = Path(__file__).resolve().parent.parent
    project_root = flood_dir
    while not (project_root / "broker").is_dir():
        project_root = project_root.parent

    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(flood_dir))

    print(f"Project root: {project_root}")
    print(f"Flood dir: {flood_dir}")
    print(f"Model: {args.model}, Replicates: {args.replicates}")
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    sys.stdout.flush()

    # Step 1: Stop competing models
    stop_other_models(args.model)

    # Step 2: Pre-load target model
    preload_model(args.model)

    # Step 3: Run ICC probing
    from paper3.run_cv import run_icc_probing

    output_dir = flood_dir / "paper3" / "results" / "cv"
    archetypes_path = flood_dir / "paper3" / "configs" / "icc_archetypes.yaml"

    print(f"\n{'='*60}")
    print(f"Starting ICC Probing")
    print(f"  Archetypes: {archetypes_path}")
    print(f"  Output: {output_dir}")
    print(f"{'='*60}\n")
    sys.stdout.flush()

    t0 = time.time()
    run_icc_probing(
        archetypes_path=str(archetypes_path),
        model=args.model,
        replicates=args.replicates,
        output_dir=str(output_dir),
        governed=True,
    )
    dt = time.time() - t0
    print(f"\nTotal time: {dt:.1f}s ({dt/60:.1f} min)")
    print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
