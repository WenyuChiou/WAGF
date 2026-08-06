#!/usr/bin/env python3
"""Inventory the exact LLM-run metadata available to the TAE release.

The experiment corpus predates one uniform manifest schema.  This script makes
that fact explicit instead of silently filling missing fields: it selects the
same 42 irrigation runs as ``_data.py``, validates each JSON manifest, and
emits one machine-readable row per run.  Rich fields are reported when they
exist; older manifests remain visibly incomplete.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAE = HERE.parent
ROOT = TAE.parent.parent
OUT = HERE / "reproducibility_inventory.csv"
PROMPT = ROOT / "examples" / "irrigation_abm" / "config" / "prompts" / "irrigation_farmer.txt"

sys.path.insert(0, str(HERE))
import _data as D  # noqa: E402

REQUIRED_FIELDS = (
    "model",
    "seed",
    "num_years",
    "governance_profile",
    "agent_types_config",
)
RICH_FIELDS = (
    "model_digest",
    "model_family",
    "model_parameter_size",
    "model_quantization",
    "num_ctx",
    "num_predict",
    "config_hash",
    "git_commit",
    "git_dirty",
    "timestamp",
    "python_version",
)
FIELDNAMES = (
    "arm",
    "model_cell",
    "seed",
    "run_dir",
    "manifest",
    "model_tag",
    "model_family",
    "model_parameter_size",
    "model_quantization",
    "model_digest",
    "temperature",
    "top_p",
    "top_k",
    "num_ctx",
    "num_predict",
    "thinking_mode",
    "config_hash",
    "git_commit",
    "git_dirty",
    "timestamp",
    "python_version",
    "agent_types_config",
    "prompt_template",
    "rich_fields_present",
)


def _display(value) -> str:
    """Keep nulls explicit in the CSV rather than turning them into blanks."""
    return "<absent>" if value is None else str(value)


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _runs() -> list[tuple[str, str, int, Path]]:
    rows: list[tuple[str, str, int, Path]] = []
    for model in D.IRRIGATION_MODELS:
        for arm, data_arm in (("governed", "gov"), ("no-validator", "noval")):
            for seed, run_dir in sorted(D.irrigation_runs(data_arm, model.prefix).items()):
                rows.append((arm, model.label, int(seed), Path(run_dir)))
    return rows


def main() -> int:
    if not PROMPT.is_file():
        raise SystemExit(f"missing shared prompt template: {PROMPT}")

    selected = _runs()
    if len(selected) != 42:
        raise SystemExit(f"selected {len(selected)} irrigation runs, expected 42")

    output_rows: list[dict[str, str]] = []
    rich_count = 0
    missing_required: list[str] = []

    for arm, model_cell, seed, run_dir in selected:
        manifest_path = run_dir / "reproducibility_manifest.json"
        if not manifest_path.is_file():
            raise SystemExit(f"missing manifest: {manifest_path}")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSON in {manifest_path}: {exc}") from exc
        missing = [field for field in REQUIRED_FIELDS if field not in manifest]
        if missing:
            missing_required.append(f"{manifest_path}: {', '.join(missing)}")
        if int(manifest.get("seed", -1)) != seed:
            raise SystemExit(f"seed mismatch in {manifest_path}: manifest={manifest.get('seed')} path={seed}")

        present_rich = [field for field in RICH_FIELDS if field in manifest]
        if len(present_rich) == len(RICH_FIELDS):
            rich_count += 1

        output_rows.append({
            "arm": arm,
            "model_cell": model_cell,
            "seed": str(seed),
            "run_dir": _relative(run_dir),
            "manifest": _relative(manifest_path),
            "model_tag": _display(manifest.get("model")),
            "model_family": _display(manifest.get("model_family")),
            "model_parameter_size": _display(manifest.get("model_parameter_size")),
            "model_quantization": _display(manifest.get("model_quantization")),
            "model_digest": _display(manifest.get("model_digest")),
            "temperature": _display(manifest.get("temperature")),
            "top_p": _display(manifest.get("top_p")),
            "top_k": _display(manifest.get("top_k")),
            "num_ctx": _display(manifest.get("num_ctx")),
            "num_predict": _display(manifest.get("num_predict")),
            "thinking_mode": _display(manifest.get("thinking_mode")),
            "config_hash": _display(manifest.get("config_hash")),
            "git_commit": _display(manifest.get("git_commit")),
            "git_dirty": _display(manifest.get("git_dirty")),
            "timestamp": _display(manifest.get("timestamp")),
            "python_version": _display(manifest.get("python_version")),
            "agent_types_config": _relative(Path(manifest.get("agent_types_config", "<absent>"))),
            "prompt_template": _relative(PROMPT),
            "rich_fields_present": ",".join(present_rich) if present_rich else "<none>",
        })

    if missing_required:
        raise SystemExit("required manifest fields missing:\n" + "\n".join(missing_required))

    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"PASS: inventoried {len(output_rows)} selected irrigation manifests")
    print(f"      rich manifest schema: {rich_count}/{len(output_rows)}; missing rich fields are marked <absent>")
    print(f"      shared prompt: {_relative(PROMPT)}")
    print(f"      wrote: {_relative(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
