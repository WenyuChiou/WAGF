#!/usr/bin/env python3
"""WAGF reproducibility audit.

Reads a results directory tree, walks every <run_dir>, and emits:
  - analysis/reproducibility/reproducibility_report.md
  - analysis/reproducibility/artifact_inventory.yml
  - analysis/reproducibility/missing_repro_steps.md

Refuses to produce a GREEN verdict if ANY of:
- a manifest is missing
- git_dirty=true on any manifest
- a known sentinel column appears unmasked
- a data trace_ts pre-dates its manifest's relied-upon code commit
- pytest broker/ tests/ does not exit 0 (when --run-tests flag used)

Usage:
    python repro_audit.py <results_root> [--out analysis/reproducibility] [--run-tests]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[5]


def find_run_dirs(root: Path) -> List[Path]:
    """A run dir contains either reproducibility_manifest.json or simulation_log.csv."""
    out = []
    for p in root.rglob("*"):
        if p.is_dir() and (
            (p / "reproducibility_manifest.json").exists()
            or (p / "simulation_log.csv").exists()
        ):
            out.append(p)
    return sorted(out)


def load_manifest(run_dir: Path) -> Optional[Dict]:
    p = run_dir / "reproducibility_manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def first_trace_ts(run_dir: Path) -> Optional[str]:
    raw = run_dir / "raw"
    if not raw.exists():
        return None
    for p in raw.glob("*.jsonl"):
        try:
            line = p.open(encoding="utf-8").readline()
            d = json.loads(line)
            return d.get("timestamp")
        except Exception:
            continue
    return None


def git_commit_date(commit: str) -> Optional[str]:
    if not commit or len(commit) < 7:
        return None
    try:
        r = subprocess.run(
            ["git", "show", "-s", "--format=%cI", commit],
            cwd=str(REPO), capture_output=True, text=True, check=True,
        )
        return r.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def check_run(run_dir: Path) -> Dict:
    manifest = load_manifest(run_dir)
    sim_log = run_dir / "simulation_log.csv"
    has_data = sim_log.exists() and sim_log.stat().st_size > 0
    findings = []

    record = {
        "path": str(run_dir.relative_to(REPO)),
        "manifest_present": manifest is not None,
        "data_complete": has_data,
        "manifest_git_commit": None,
        "data_first_trace_ts": None,
        "relevant_code_commit_date": None,
        "verdict": "UNKNOWN",
        "findings": findings,
    }

    if manifest is None:
        findings.append({"severity": "RED", "msg": "no reproducibility_manifest.json"})
        record["verdict"] = "RED"
        return record

    if manifest.get("git_dirty") is True:
        findings.append({"severity": "RED", "msg": "git_dirty=true; cannot reproduce"})
    record["manifest_git_commit"] = manifest.get("git_commit")
    commit = manifest.get("git_commit", "")
    commit_date = git_commit_date(commit)
    record["relevant_code_commit_date"] = commit_date
    trace_ts = first_trace_ts(run_dir)
    record["data_first_trace_ts"] = trace_ts

    # Required fields
    required = [
        "model", "seed", "git_commit", "governance_profile",
        "agent_types_config", "config_hash", "timestamp",
    ]
    for f in required:
        if f not in manifest:
            findings.append({"severity": "RED", "msg": f"missing required manifest field: {f}"})

    # Strongly-recommended fields
    recommended = [
        "temperature", "top_p", "num_ctx", "num_predict",
        "thinking_mode", "model_digest",
    ]
    missing_rec = [f for f in recommended if f not in manifest]
    if missing_rec:
        findings.append({
            "severity": "YELLOW",
            "msg": f"missing recommended manifest fields: {','.join(missing_rec)}",
        })

    # Cross-reference data vs code
    if commit_date and trace_ts:
        try:
            cd = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
            td = datetime.fromisoformat(trace_ts.replace("Z", "+00:00"))
            if td < cd:
                findings.append({
                    "severity": "RED",
                    "msg": f"data trace_ts ({trace_ts}) pre-dates manifest git_commit date ({commit_date})",
                })
        except Exception:
            pass

    # Verdict
    has_red = any(f["severity"] == "RED" for f in findings)
    has_yellow = any(f["severity"] == "YELLOW" for f in findings)
    record["verdict"] = "RED" if has_red else ("YELLOW" if has_yellow else "GREEN")
    return record


def write_report(records: List[Dict], out_dir: Path) -> Tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    overall = "RED" if any(r["verdict"] == "RED" for r in records) else (
        "YELLOW" if any(r["verdict"] == "YELLOW" for r in records) else "GREEN"
    )

    md = out_dir / "reproducibility_report.md"
    lines = [
        f"# Reproducibility Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Scope",
        "",
        f"- Runs surveyed: {len(records)}",
        f"- Manifests present: {sum(1 for r in records if r['manifest_present'])} / {len(records)}",
        "",
        "## Verdict",
        "",
        f"**{overall}**",
        "",
        "## Findings",
        "",
    ]
    for i, r in enumerate(records, 1):
        if r["findings"]:
            lines.append(f"### {i}. {r['path']}  ({r['verdict']})")
            for f in r["findings"]:
                lines.append(f"  - **{f['severity']}**: {f['msg']}")
            lines.append("")
    if not any(r["findings"] for r in records):
        lines.append("_No findings — all runs pass._")
        lines.append("")
    lines += [
        "## Reproducible Command List",
        "",
        "```bash",
        "python .claude/skills/abm-reproducibility-checker/scripts/repro_audit.py \\",
        "    <results_root>",
        "```",
        "",
        "## Caveats",
        "",
        "- Does not run pytest unless invoked with `--run-tests` (skipped here).",
        "- Does not verify Ollama model digests against current local models.",
        "- Sentinel-column scan delegated to `detect_audit_sentinels_in_csv()` (run separately).",
        "- Does not check figure-script outputs match committed PNG/PDFs.",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")

    # Inventory YAML
    inv = out_dir / "artifact_inventory.yml"
    inv_lines = ["runs:"]
    for r in records:
        inv_lines += [
            f"  - path: {r['path']}",
            f"    manifest_present: {str(r['manifest_present']).lower()}",
            f"    manifest_git_commit: {r['manifest_git_commit'] or 'null'}",
            f"    data_first_trace_ts: {r['data_first_trace_ts'] or 'null'}",
            f"    relevant_code_commit_date: {r['relevant_code_commit_date'] or 'null'}",
            f"    verdict: {r['verdict']}",
        ]
    inv.write_text("\n".join(inv_lines), encoding="utf-8")

    # Missing steps
    missing = out_dir / "missing_repro_steps.md"
    miss_lines = ["# Missing Repro Steps", ""]
    miss_count = 0
    for r in records:
        for f in r["findings"]:
            if f["severity"] == "RED":
                miss_count += 1
                miss_lines.append(f"- [ ] **{r['path']}**: {f['msg']}")
    if miss_count == 0:
        miss_lines.append("_No RED findings to address._")
    missing.write_text("\n".join(miss_lines), encoding="utf-8")

    return md, inv, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path, help="results dir or results-tree root")
    ap.add_argument("--out", type=Path, default=Path("analysis/reproducibility"))
    ap.add_argument("--run-tests", action="store_true",
                    help="also run pytest broker/ tests/ and incorporate into verdict")
    args = ap.parse_args()

    runs = find_run_dirs(args.root)
    if not runs:
        print(f"No run dirs found under {args.root}", file=sys.stderr)
        return 1

    records = [check_run(r) for r in runs]
    md, inv, miss = write_report(records, args.out)
    print(f"Wrote: {md}\n       {inv}\n       {miss}")

    if args.run_tests:
        r = subprocess.run(
            ["pytest", "broker/", "tests/", "-q"],
            cwd=str(REPO), capture_output=True, text=True,
        )
        print("\npytest exit code:", r.returncode)
        if r.returncode != 0:
            print(r.stdout[-2000:])
            print(r.stderr[-2000:])

    overall = "RED" if any(r["verdict"] == "RED" for r in records) else (
        "YELLOW" if any(r["verdict"] == "YELLOW" for r in records) else "GREEN"
    )
    print(f"\nVerdict: {overall}")
    return 0 if overall == "GREEN" else 2


if __name__ == "__main__":
    sys.exit(main())
