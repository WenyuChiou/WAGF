#!/usr/bin/env python3
"""ABM ↔ external-model schema diff.

Reads two YAML schemas and emits a side-by-side mismatch report:
- fields present in one but not the other
- fields present in both but with different types or units

Usage:
    python contract_diff.py <abm_schema.yml> <external_schema.yml> [--out coupling_schema_findings.yml]

Schema YAML format (lenient — accepts the field list as a flat dict
or as `{fields: {<name>: {type, unit, range, missing_policy}}}`):

```yaml
fields:
  request:
    type: float
    unit: MAF
    range: [0, 1.0]
    missing_policy: clip_zero
  diversion:
    type: float
    unit: MAF
```
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def load_fields(path: Path) -> Dict[str, Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected mapping at top level")
    fields = data.get("fields", data)
    if not isinstance(fields, dict):
        raise ValueError(f"{path}: 'fields' must be a mapping")
    out = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            out[k] = v
        else:
            out[k] = {"type": str(v)}
    return out


def diff(abm: Dict[str, Dict[str, Any]],
         ext: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for name in sorted(set(abm) | set(ext)):
        a = abm.get(name)
        e = ext.get(name)
        if a is None:
            findings.append({"field": name, "status": "EXTERNAL_ONLY",
                             "abm": None, "external": e})
            continue
        if e is None:
            findings.append({"field": name, "status": "ABM_ONLY",
                             "abm": a, "external": None})
            continue
        # Both present
        a_type = str(a.get("type", "?"))
        e_type = str(e.get("type", "?"))
        a_unit = str(a.get("unit", "?"))
        e_unit = str(e.get("unit", "?"))
        if a_type != e_type or a_unit != e_unit:
            findings.append({
                "field": name,
                "status": "MISMATCH",
                "abm": {"type": a_type, "unit": a_unit},
                "external": {"type": e_type, "unit": e_unit},
            })
        else:
            findings.append({
                "field": name, "status": "OK",
                "abm": {"type": a_type, "unit": a_unit},
                "external": {"type": e_type, "unit": e_unit},
            })
    return findings


def write_yaml(findings: List[Dict[str, Any]], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        yaml.safe_dump({"findings": findings}, f, sort_keys=False)


def write_md_summary(findings: List[Dict[str, Any]]) -> str:
    lines = ["| Field | Status | ABM type / unit | External type / unit |",
             "|---|---|---|---|"]
    for f_ in findings:
        a = f_.get("abm") or {}
        e = f_.get("external") or {}
        a_str = f"{a.get('type','-')} / {a.get('unit','-')}" if a else "-"
        e_str = f"{e.get('type','-')} / {e.get('unit','-')}" if e else "-"
        marker = {"OK": "✓", "MISMATCH": "⚠", "ABM_ONLY": "→ABM",
                  "EXTERNAL_ONLY": "→ext"}.get(f_["status"], "?")
        lines.append(f"| {f_['field']} | {marker} {f_['status']} | {a_str} | {e_str} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("abm", type=Path, help="ABM state schema YAML")
    ap.add_argument("external", type=Path, help="external model schema YAML")
    ap.add_argument("--out", type=Path,
                    default=Path("analysis/coupling/coupling_schema_findings.yml"))
    args = ap.parse_args()

    abm = load_fields(args.abm)
    ext = load_fields(args.external)
    findings = diff(abm, ext)
    write_yaml(findings, args.out)
    print(f"Wrote {args.out}")
    print()
    print(write_md_summary(findings))

    # Exit code reflects severity
    has_mismatch = any(f["status"] == "MISMATCH" for f in findings)
    has_missing = any(f["status"] in ("ABM_ONLY", "EXTERNAL_ONLY") for f in findings)
    if has_mismatch:
        return 2
    if has_missing:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
