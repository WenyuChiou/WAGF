"""vaccination_demo Tier-2 showcase batch summary (Phase L3-1F, 2026-05-24).

Loads the 6 result dirs produced by `run_vaccination_batch.sh` /
`run_vaccination_batch.bat` and prints per-seed/model decision
statistics + per-year vaccination coverage. Mirrors what
`examples/irrigation_abm/analysis/compute_ibr.py` does for irrigation
but at the smallest possible scope (no plotting, no bootstrap CI —
just a clean ASCII table).

Run from the repo root:
  python examples/vaccination_demo/summary.py

To target a specific glob (e.g. one model):
  python examples/vaccination_demo/summary.py "examples/vaccination_demo/results/showcase_v1_*gemma3_4b"

NOT a paper-grade analysis pipeline — for showcase audit only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

DEFAULT_GLOB = "examples/vaccination_demo/results/showcase_v1_*"


def main(arg_glob: str = DEFAULT_GLOB) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    pattern = arg_glob
    if not Path(pattern).is_absolute():
        pattern = str(repo_root / pattern)
    # Glob-style expansion through pathlib
    base = Path(pattern).parent
    name_pattern = Path(pattern).name
    dirs = sorted(p for p in base.glob(name_pattern) if p.is_dir())
    if not dirs:
        print(f"No result dirs matched: {pattern}")
        sys.exit(1)

    rows = []
    for d in dirs:
        audit_csv = d / "individual_governance_audit.csv"
        if not audit_csv.exists():
            print(f"  [SKIP] {d.name}: no audit CSV")
            continue
        df = pd.read_csv(audit_csv)
        # Parse seed + model from directory name
        # Format: showcase_v1_seed<S>_<M_slug>
        name = d.name
        parts = name.replace("showcase_v1_seed", "").split("_", 1)
        seed = parts[0] if parts else "?"
        model_slug = parts[1] if len(parts) > 1 else "?"
        n = len(df)
        approved = (df["status"] == "APPROVED").sum()
        approved_pct = 100.0 * approved / n if n else 0.0
        skill_counts = df["final_skill"].value_counts().to_dict()
        gv = skill_counts.get("get_vaccinated", 0)
        delay = skill_counts.get("delay", 0)
        refuse = skill_counts.get("refuse", 0)
        coverage_pct = 100.0 * gv / n if n else 0.0
        rows.append({
            "seed": seed,
            "model": model_slug,
            "n": n,
            "approved_%": f"{approved_pct:.1f}",
            "vacc_coverage_%": f"{coverage_pct:.1f}",
            "get_vacc": gv,
            "delay": delay,
            "refuse": refuse,
        })

    if not rows:
        print("No usable audit CSVs found.")
        sys.exit(1)

    summary_df = pd.DataFrame(rows)
    print("=== Tier-2 vaccination_demo batch summary ===\n")
    print(summary_df.to_string(index=False))
    print()
    if len(summary_df) >= 2:
        cov_vals = summary_df["vacc_coverage_%"].astype(float)
        print(
            f"Across {len(summary_df)} runs: vaccination coverage "
            f"mean={cov_vals.mean():.1f}%  std={cov_vals.std(ddof=1):.1f}%  "
            f"min={cov_vals.min():.1f}%  max={cov_vals.max():.1f}%"
        )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GLOB)
