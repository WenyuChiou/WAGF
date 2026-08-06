#!/usr/bin/env python3
"""Cross-check the rendered Table 1 source against the canonical evidence CSV.

The manuscript keeps a compact, human-readable table rather than importing a
generated fragment into the LaTeX build.  That is useful for review, but it
creates a transcription boundary.  This checker closes that boundary: it
resolves the manuscript's claim markers in memory, parses the Markdown table,
and compares every displayed irrigation value plus the aggregate flood range
with ``table1_cells.csv`` emitted by ``table1_cells.py``.

The checker writes nothing.  A source-table mismatch is a hard failure.
"""

from __future__ import annotations

import csv
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parent / "paper"
MANUSCRIPT = PAPER / "manuscript.md"
CSV_PATH = HERE / "table1_cells.csv"

sys.path.insert(0, str(PAPER))
from substitute import CLAIMS  # noqa: E402

CLAIM_RE = re.compile(r"\{\{CLAIM:([a-zA-Z0-9_]+)\}\}")
TABLE_HEADER = "| testbed | model | *n* | HIGH, on | HIGH, off | Δ HIGH | cond., on | cond., off | Δ cond. |"
TOL = 0.006


def _resolve_claims(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in CLAIMS:
            raise AssertionError(f"unresolved claim marker in Table 1: {name}")
        return CLAIMS[name]["value"]

    return CLAIM_RE.sub(replace, text)


def _fields(line: str) -> list[str]:
    parts = line.split("|")
    if len(parts) < 3 or not line.lstrip().startswith("|"):
        raise AssertionError(f"not a Markdown table row: {line!r}")
    return [part.strip() for part in parts[1:-1]]


def _number(value: str) -> float:
    cleaned = value.replace("*", "").replace("−", "-").strip()
    try:
        return float(cleaned)
    except ValueError as exc:
        raise AssertionError(f"expected a number, got {value!r}") from exc


def _assert_close(label: str, actual: str, expected: float) -> None:
    observed = _number(actual)
    if not math.isclose(observed, expected, abs_tol=TOL):
        raise AssertionError(f"{label}: manuscript={observed:.4f}, evidence={expected:.4f}")


def _load_evidence() -> dict[tuple[str, str], dict[str, str]]:
    with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 14:
        raise AssertionError(f"canonical Table 1 CSV has {len(rows)} rows, expected 14")
    return {(row["testbed"], row["model"]): row for row in rows}


def _table_rows() -> list[list[str]]:
    text = _resolve_claims(MANUSCRIPT.read_text(encoding="utf-8"))
    lines = text.splitlines()
    try:
        start = lines.index(TABLE_HEADER)
    except ValueError as exc:
        raise AssertionError("Table 1 header not found in manuscript.md") from exc

    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append(_fields(line))
    if len(rows) != 6:
        raise AssertionError(f"manuscript Table 1 has {len(rows)} data rows, expected 6")
    if any(len(row) != 9 for row in rows):
        raise AssertionError("one or more Table 1 rows has the wrong number of columns")
    return rows


def main() -> int:
    evidence = _load_evidence()
    rows = _table_rows()
    seen_irrigation: set[str] = set()

    for row in rows:
        testbed, model, n, high_on, high_off, high_delta, cond_on, cond_off, cond_delta = row
        if testbed == "irrigation":
            key = (testbed, model)
            if key not in evidence:
                raise AssertionError(f"no canonical row for {testbed}/{model}")
            source = evidence[key]
            seen_irrigation.add(model)
            if int(n) != int(source["n_paired"]):
                raise AssertionError(f"{model}: manuscript n={n}, evidence n={source['n_paired']}")
            _assert_close(f"{model} HIGH on", high_on, float(source["high_gov"]))
            _assert_close(f"{model} HIGH off", high_off, float(source["high_noval"]))
            _assert_close(f"{model} Δ HIGH", high_delta, float(source["high_delta"]))
            _assert_close(f"{model} conditional on", cond_on, float(source["cond_gov"]))
            _assert_close(f"{model} conditional off", cond_off, float(source["cond_noval"]))
            _assert_close(f"{model} Δ conditional", cond_delta, float(source["cond_delta"]))
        elif testbed == "flood":
            if model != "9 cells" or int(n) != 5:
                raise AssertionError("flood aggregate row changed its documented scope")
            if high_on != "—" or high_off != "—" or cond_on != "—" or cond_off != "—" or cond_delta != "—":
                raise AssertionError("flood aggregate row must not expose a conformance rate")
            flood = [row for (tb, _), row in evidence.items() if tb == "flood"]
            low = min(float(item["high_delta"]) for item in flood)
            high = max(float(item["high_delta"]) for item in flood)
            observed = re.fullmatch(r"([+−-]?\d+\.\d+)\s+to\s+([+−-]?\d+\.\d+)", high_delta)
            if observed is None:
                raise AssertionError(f"flood aggregate range is not parseable: {high_delta!r}")
            _assert_close("flood HIGH range lower", observed.group(1), low)
            _assert_close("flood HIGH range upper", observed.group(2), high)
        else:
            raise AssertionError(f"unknown Table 1 testbed: {testbed!r}")

    expected_irrigation = {model for testbed, model in evidence if testbed == "irrigation"}
    if seen_irrigation != expected_irrigation:
        raise AssertionError(
            f"irrigation rows differ: manuscript={sorted(seen_irrigation)}, "
            f"evidence={sorted(expected_irrigation)}"
        )

    print("PASS: manuscript Table 1 matches the canonical evidence CSV (5 irrigation rows + flood range).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
