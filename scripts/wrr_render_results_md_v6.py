#!/usr/bin/env python
"""
Render a live WRR v6 results snapshot in Markdown from precomputed CSVs.

Input CSVs:
- docs/wrr_metrics_group_summary_v6.csv
- docs/wrr_metrics_completion_v6.csv

Output:
- docs/wrr_results_live_snapshot_v6.md
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def read_csv(path: Path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def f3(x: float) -> str:
    return f"{x:.3f}"


def render(group_rows, completion_rows) -> str:
    now = datetime.now(timezone.utc).isoformat()

    total = len(completion_rows)
    done = sum(int(r["has_simulation_log"]) for r in completion_rows)

    by_mg = defaultdict(int)
    for r in completion_rows:
        key = (r["model"], r["group"])
        by_mg[key] += int(r["has_simulation_log"])

    lines = []
    lines.append("# WRR v6 Live Results Snapshot")
    lines.append("")
    lines.append(f"- Generated (UTC): {now}")
    lines.append(f"- Completion: {done}/{total} model-group-run cells")
    lines.append("")
    lines.append("## Group Means (Available Runs)")
    lines.append("")
    lines.append("| Group | n_cases | runs | R_H | R_R | Rationality pass | H_norm_k4 | EHE_k4 | retry_rows | retry_sum |")
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for r in sorted(group_rows, key=lambda x: x["group"]):
        lines.append(
            "| {group} | {n_cases} | {runs} | {rh} | {rr} | {rp} | {h4} | {e4} | {rrws} | {rsum} |".format(
                group=r["group"],
                n_cases=r["n_cases"],
                runs=r["runs_observed"],
                rh=pct(float(r["R_H_mean"])),
                rr=pct(float(r["R_R_mean"])),
                rp=pct(float(r["rationality_pass_mean"])),
                h4=f3(float(r["H_norm_k4_mean"])),
                e4=f3(float(r["EHE_k4_mean"])),
                rrws=f"{float(r['retry_rows_mean']):.2f}",
                rsum=f"{float(r['retry_sum_mean']):.2f}",
            )
        )

    lines.append("")
    lines.append("## Completion by Model x Group")
    lines.append("")
    lines.append("| Model | Group_A | Group_B | Group_C |")
    lines.append("|---|---:|---:|---:|")
    models = sorted({r["model"] for r in completion_rows})
    for m in models:
        a = by_mg[(m, "Group_A")]
        b = by_mg[(m, "Group_B")]
        c = by_mg[(m, "Group_C")]
        lines.append(f"| {m} | {a}/3 | {b}/3 | {c}/3 |")

    lines.append("")
    lines.append("## Update Command")
    lines.append("")
    lines.append("```bash")
    lines.append("python scripts/wrr_compute_metrics_v6.py")
    lines.append("python scripts/wrr_render_results_md_v6.py")
    lines.append("```")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This file updates from existing logs only; missing runs are not imputed.")
    lines.append("- Retry metrics are workload diagnostics and are not violation prevalence.")
    lines.append("- EHE_k4 = H_norm_k4 * (1 - R_H).")
    return "\n".join(lines) + "\n"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--group-csv", default="docs/wrr_metrics_group_summary_v6.csv")
    p.add_argument("--completion-csv", default="docs/wrr_metrics_completion_v6.csv")
    p.add_argument("--out-md", default="docs/wrr_results_live_snapshot_v6.md")
    return p.parse_args()


def main():
    args = parse_args()
    group_rows = read_csv(Path(args.group_csv))
    completion_rows = read_csv(Path(args.completion_csv))
    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(group_rows, completion_rows), encoding="utf-8")
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()

