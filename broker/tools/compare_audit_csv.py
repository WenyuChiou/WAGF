"""Column-aware governance_audit CSV diff tool (Phase 6R-C-0).

Background
==========
The broker's audit writer emits ``*_governance_audit.csv`` files with
two sources of non-determinism that prevent direct SHA256 byte-identity
checks across runs:

1. **Wall-clock timestamps** — every row ends with a column like
   ``2026-05-26T14:44:24.795081`` captured via ``datetime.now()`` at
   decision-write time.
2. **Python set iteration order** — error messages embedding sets
   (e.g. ``Missing constructs for 'household': ['CP_LABEL',
   'CP_REASON', 'TP_LABEL', 'TP_REASON']``) drift between runs because
   set iteration is hash-seed-dependent.

Two consecutive runs at the SAME commit produce different hashes (see
``.baselines/BASELINE_HASHES.md`` for evidence). This tool normalises
both sources of drift to enable structural byte-identity verification
for Phase 6R-C (AgentProfile / SyntheticLoader split) and 6R-D-5
(FloodDomainPack internal refactor).

Normalisation strategy
======================
- **Timestamp column**: detected by header name containing ``"timestamp"``
  (case-insensitive). All values in that column are replaced by the
  literal ``"<TIMESTAMP>"``.
- **Set-repr in any cell**: any value matching ``[...]`` containing
  comma-separated quoted items is parsed and the items are
  alphabetically sorted before re-formatting. Example:
  ``"['CP_LABEL', 'TP_LABEL']"`` → ``"['CP_LABEL', 'TP_LABEL']"``
  (already sorted) and ``"['TP_LABEL', 'CP_LABEL']"`` →
  ``"['CP_LABEL', 'TP_LABEL']"`` (re-sorted).

Use
===
::

    python -m broker.tools.compare_audit_csv \\
        .baselines/pre_6r_flood_mock_seed42/household_governance_audit.csv \\
        .baselines/check_post_6r_flood/household_governance_audit.csv

Exits 0 if normalised content is identical, 1 if it differs. Prints
the first 3 differing rows to stdout.

The tool is also importable for unit tests; see
``broker/tests/test_compare_audit_csv.py``.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

#: Pattern matching `['a', 'b']` or `["a", "b"]` style set/list reprs
#: embedded in a CSV cell. The bracketed content must contain at least
#: one comma + one quoted token to qualify (avoids false positives on
#: empty lists or single-item lists).
_SET_REPR_RE = re.compile(
    r"""\[                          # opening bracket
        \s*
        (?P<items>
          (?:'[^']*'|\"[^\"]*\")   # first quoted token
          (?:\s*,\s*
             (?:'[^']*'|\"[^\"]*\")
          )+                       # one or more additional tokens
        )
        \s*
        \]                          # closing bracket
    """,
    re.VERBOSE,
)


def _sort_set_repr_in_cell(cell: str) -> str:
    """Sort the contents of every set-repr-like fragment inside ``cell``.

    Multiple fragments in the same cell are each sorted independently;
    surrounding text is preserved verbatim.
    """
    def replacer(match: re.Match) -> str:
        items_str = match.group("items")
        # Split on commas but tolerate whitespace.
        tokens = [t.strip() for t in items_str.split(",")]
        tokens.sort()
        return "[" + ", ".join(tokens) + "]"

    return _SET_REPR_RE.sub(replacer, cell)


def _timestamp_columns(header: Sequence[str]) -> List[int]:
    """Return indices of columns whose header contains 'timestamp'
    (case-insensitive). Captures the canonical
    ``timestamp`` column written by the audit writer."""
    return [
        i for i, col in enumerate(header)
        if "timestamp" in (col or "").lower()
    ]


def normalise_rows(
    header: Sequence[str], rows: Iterable[Sequence[str]],
) -> Tuple[List[str], List[List[str]]]:
    """Apply both normalisations to the rows. Returns ``(header,
    normalised_rows)`` — header is returned as-is so callers can
    pass it back into ``csv.writer``."""
    ts_cols = _timestamp_columns(header)
    out: List[List[str]] = []
    for row in rows:
        norm = list(row)
        # Replace timestamp columns.
        for idx in ts_cols:
            if idx < len(norm):
                norm[idx] = "<TIMESTAMP>"
        # Sort any set-repr fragments in every cell.
        norm = [_sort_set_repr_in_cell(cell) for cell in norm]
        out.append(norm)
    return list(header), out


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------

def _load_normalised(path: Path) -> Tuple[List[str], List[List[str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return [], []
        rows = list(reader)
    return normalise_rows(header, rows)


def compare(left: Path, right: Path, max_samples: int = 3) -> int:
    """Compare two governance_audit CSVs. Returns 0 if normalised
    contents match, 1 otherwise. Prints up to ``max_samples`` differing
    rows (first divergence onward)."""
    l_header, l_rows = _load_normalised(left)
    r_header, r_rows = _load_normalised(right)

    if l_header != r_header:
        print(f"HEADER MISMATCH")
        print(f"  left:  {l_header}")
        print(f"  right: {r_header}")
        return 1

    if len(l_rows) != len(r_rows):
        print(
            f"ROW COUNT MISMATCH: left={len(l_rows)}  right={len(r_rows)}"
        )
        return 1

    diffs: List[Tuple[int, List[str], List[str]]] = []
    for i, (lr, rr) in enumerate(zip(l_rows, r_rows)):
        if lr != rr:
            diffs.append((i, lr, rr))
            if len(diffs) >= max_samples:
                break

    if not diffs:
        # SHA256 of canonical representation, for the curious.
        h = hashlib.sha256()
        h.update(",".join(l_header).encode("utf-8"))
        for row in l_rows:
            h.update(",".join(row).encode("utf-8"))
        print(f"IDENTICAL ({len(l_rows)} rows, canonical sha256={h.hexdigest()})")
        return 0

    print(f"DIFFERS — first {len(diffs)} divergent rows of {len(l_rows)}:")
    for i, lr, rr in diffs:
        print(f"\n[row {i}]")
        for col, lv, rv in zip(l_header, lr, rr):
            if lv != rv:
                print(f"  {col!r}: {lv!r}  ->  {rv!r}")
    return 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m broker.tools.compare_audit_csv",
        description=(
            "Column-aware diff for broker governance_audit CSVs. Strips "
            "wall-clock timestamps and sorts set-repr fragments before "
            "comparing — enables byte-identity-equivalent checks across "
            "runs whose only differences are run-time noise. Phase 6R-C-0."
        ),
    )
    parser.add_argument("left", type=Path, help="reference (pre-refactor) CSV")
    parser.add_argument("right", type=Path, help="candidate (post-refactor) CSV")
    parser.add_argument(
        "--max-samples", type=int, default=3,
        help="how many divergent rows to print (default: 3)",
    )
    args = parser.parse_args(argv)

    for p in (args.left, args.right):
        if not p.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            return 2

    return compare(args.left, args.right, max_samples=args.max_samples)


if __name__ == "__main__":
    sys.exit(main())
