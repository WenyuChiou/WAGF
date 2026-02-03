"""
Paper 3 Experiment Runner

Wraps run_unified_experiment.py with Paper 3 specific configurations.
Reads YAML configs and translates to CLI arguments for the unified runner.

Usage:
    python paper3/run_paper3.py --config paper3/configs/primary_experiment.yaml --seed 42
    python paper3/run_paper3.py --config paper3/configs/primary_experiment.yaml --all-seeds
    python paper3/run_paper3.py --config paper3/configs/si_ablations.yaml --ablation si1_window_memory
"""

import argparse
import subprocess
import sys
import yaml
from pathlib import Path

MULTI_AGENT_DIR = Path(__file__).parent.parent
RUNNER = MULTI_AGENT_DIR / "run_unified_experiment.py"


def load_config(config_path: str) -> dict:
    """Load experiment configuration from YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def config_to_cli_args(cfg: dict, seed: int) -> list:
    """Translate Paper 3 config dict to CLI arguments for run_unified_experiment.py."""
    args = []

    # Model
    model = cfg.get("model", {}).get("name", "gemma3:4b")
    if model != "none":
        args.extend(["--model", model])

    # Simulation
    sim = cfg.get("simulation", {})
    args.extend(["--years", str(sim.get("years", 13))])
    args.extend(["--agents", str(sim.get("agents", 100))])

    # Agent composition — detect balanced mode
    agent_comp = cfg.get("agent_composition", {})
    if agent_comp.get("balanced", False):
        args.extend(["--mode", "balanced"])
        # Pass agent profiles and initial memories paths if specified
        balanced_dir = cfg.get("balanced_dir", "examples/multi_agent/flood/paper3/output")
        profiles = agent_comp.get("profiles_csv", f"{balanced_dir}/agent_profiles_balanced.csv")
        memories = agent_comp.get("memories_json", f"{balanced_dir}/initial_memories_balanced.json")
        args.extend(["--agent-profiles", profiles])
        args.extend(["--initial-memories-file", memories])
    else:
        args.extend(["--mode", sim.get("mode", "survey")])

    # Memory
    mem = cfg.get("memory", {})
    engine = mem.get("engine", "universal")
    if engine != "parametric":
        args.extend(["--memory-engine", engine])

    # Hazard
    hazard = cfg.get("hazard", {})
    grid_dir = hazard.get("grid_dir")
    if grid_dir:
        args.extend(["--grid-dir", grid_dir])
    if hazard.get("per_agent_depth", False):
        args.append("--per-agent-depth")
    neighbor_mode = hazard.get("neighbor_mode", "ring")
    args.extend(["--neighbor-mode", neighbor_mode])
    if neighbor_mode == "spatial":
        args.extend(["--neighbor-radius", str(hazard.get("neighbor_radius", 3.0))])

    # Institutions
    inst = cfg.get("institutions", {})
    gov = inst.get("government", {})
    ins = inst.get("insurance", {})
    args.extend(["--initial-subsidy", str(gov.get("initial_subsidy", 0.50))])
    args.extend(["--initial-premium", str(ins.get("initial_premium", 0.02))])

    # Social
    social = cfg.get("social", {})
    if social.get("gossip", False):
        args.append("--gossip")
    if social.get("news_media", False):
        args.append("--enable-news-media")
    if social.get("social_media", False):
        args.append("--enable-social-media")
    news_delay = social.get("news_delay", 1)
    args.extend(["--news-delay", str(news_delay)])

    # Governance
    gov_cfg = cfg.get("governance", {})
    if gov_cfg.get("financial_constraints", False):
        args.append("--enable-financial-constraints")
    if gov_cfg.get("cross_validation", False):
        args.append("--enable-cross-validation")
    if gov_cfg.get("communication", False):
        args.append("--enable-communication")

    # Seed
    args.extend(["--seed", str(seed)])

    # Skill ordering randomization
    if cfg.get("governance", {}).get("shuffle_skills", False):
        args.append("--shuffle-skills")

    # Output
    output = cfg.get("output", {})
    base_dir = output.get("base_dir", "examples/multi_agent/flood/paper3/results")
    exp_name = cfg.get("experiment", {}).get("name", "experiment")
    if output.get("per_seed_dir", True):
        output_dir = f"{base_dir}/{exp_name}/seed_{seed}"
    else:
        output_dir = f"{base_dir}/{exp_name}"
    args.extend(["--output", output_dir])

    return args


def run_experiment(config_path: str, seed: int, dry_run: bool = False):
    """Run a single experiment with the given config and seed."""
    cfg = load_config(config_path)
    cli_args = config_to_cli_args(cfg, seed)

    cmd = [sys.executable, str(RUNNER)] + cli_args
    exp_name = cfg.get("experiment", {}).get("name", "unknown")

    print(f"\n{'='*60}")
    print(f"Paper 3 Experiment: {exp_name} | Seed: {seed}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")

    if dry_run:
        print("[DRY RUN] Skipping execution")
        return

    result = subprocess.run(cmd, cwd=str(MULTI_AGENT_DIR.parent.parent.parent))
    if result.returncode != 0:
        print(f"[ERROR] Experiment failed with return code {result.returncode}")
    else:
        print(f"[OK] Experiment completed: {exp_name} seed={seed}")


def main():
    parser = argparse.ArgumentParser(description="Paper 3 Experiment Runner")
    parser.add_argument("--config", required=True, help="Path to experiment config YAML")
    parser.add_argument("--seed", type=int, default=None, help="Run single seed")
    parser.add_argument("--all-seeds", action="store_true", help="Run all seeds from config")
    parser.add_argument("--ablation", type=str, default=None, help="Ablation name (for SI configs)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Handle ablation configs
    if args.ablation:
        ablations = cfg.get("ablations", {})
        if args.ablation not in ablations:
            print(f"[ERROR] Ablation '{args.ablation}' not found. Available: {list(ablations.keys())}")
            sys.exit(1)
        abl = ablations[args.ablation]

        # Load base config and apply overrides
        base_name = abl.get("base", "primary_experiment")
        base_path = Path(args.config).parent / f"{base_name}.yaml"
        cfg = load_config(str(base_path))

        # Deep merge overrides
        for section, overrides in abl.get("override", {}).items():
            if section in cfg:
                if isinstance(cfg[section], dict) and isinstance(overrides, dict):
                    cfg[section].update(overrides)
                else:
                    cfg[section] = overrides

        cfg["experiment"]["name"] = f"paper3_{args.ablation}"
        seeds = abl.get("seeds", [42, 123, 456])
    else:
        seeds = cfg.get("experiment", {}).get("seeds", [42])

    # Determine which seeds to run
    if args.seed is not None:
        seeds = [args.seed]
    elif not args.all_seeds:
        seeds = [seeds[0]]  # Default: run first seed only

    # Write effective config to temp file for the run
    import tempfile
    for seed in seeds:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(cfg, f)
            temp_path = f.name
        run_experiment(temp_path, seed, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
