"""Tests for broker.tools.compare_audit_csv (Phase 6R-C-0).

The diff tool must:
1. Normalise timestamp columns (replace with sentinel).
2. Sort set-repr fragments alphabetically inside cells.
3. Return 0 for normalised-identical CSVs, 1 for genuine diffs.
4. Detect header mismatches + row-count mismatches.
5. Handle empty files + missing files gracefully.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from broker.tools.compare_audit_csv import (
    _sort_set_repr_in_cell,
    _timestamp_columns,
    compare,
    main,
    normalise_rows,
)


# ---------------------------------------------------------------------------
# Set-repr sorting
# ---------------------------------------------------------------------------

class TestSortSetReprInCell:
    def test_alphabetises_unsorted_tokens(self):
        out = _sort_set_repr_in_cell("['TP_LABEL', 'CP_LABEL']")
        assert out == "['CP_LABEL', 'TP_LABEL']"

    def test_idempotent_on_sorted_tokens(self):
        already = "['CP_LABEL', 'TP_LABEL']"
        assert _sort_set_repr_in_cell(already) == already

    def test_preserves_surrounding_text(self):
        out = _sort_set_repr_in_cell(
            "Missing constructs: ['B', 'A']|CRITICAL: ['Y', 'X']"
        )
        assert "Missing constructs: ['A', 'B']" in out
        assert "CRITICAL: ['X', 'Y']" in out

    def test_ignores_single_item_lists(self):
        # Single-item lists have no sort ambiguity AND the regex
        # requires at least one comma. Such cells pass through unchanged.
        out = _sort_set_repr_in_cell("['only_one']")
        assert out == "['only_one']"

    def test_handles_double_quoted_tokens(self):
        out = _sort_set_repr_in_cell('["TP_LABEL", "CP_LABEL"]')
        assert out == '["CP_LABEL", "TP_LABEL"]'

    def test_no_change_for_cells_without_lists(self):
        for cell in ("plain text", "42", "", "no [brackets here"):
            assert _sort_set_repr_in_cell(cell) == cell


# ---------------------------------------------------------------------------
# Timestamp-column detection
# ---------------------------------------------------------------------------

class TestTimestampColumns:
    def test_finds_canonical_name(self):
        assert _timestamp_columns(["x", "timestamp", "y"]) == [1]

    def test_case_insensitive(self):
        assert _timestamp_columns(["Timestamp"]) == [0]
        assert _timestamp_columns(["TIMESTAMP_ISO"]) == [0]

    def test_substring_match(self):
        # "decision_timestamp" should match.
        assert _timestamp_columns(["agent_id", "decision_timestamp"]) == [1]

    def test_empty_header(self):
        assert _timestamp_columns([]) == []

    def test_no_timestamp_column(self):
        assert _timestamp_columns(["agent_id", "skill_name"]) == []


# ---------------------------------------------------------------------------
# normalise_rows
# ---------------------------------------------------------------------------

class TestNormaliseRows:
    def test_replaces_timestamp_with_sentinel(self):
        header = ["a", "timestamp"]
        rows = [["x", "2026-05-26T14:44:24.795081"]]
        _, out = normalise_rows(header, rows)
        assert out == [["x", "<TIMESTAMP>"]]

    def test_sorts_set_repr_per_cell(self):
        header = ["msg"]
        rows = [["Missing: ['B', 'A']"]]
        _, out = normalise_rows(header, rows)
        assert out == [["Missing: ['A', 'B']"]]

    def test_both_transforms_combined(self):
        header = ["msg", "timestamp"]
        rows = [["['Z', 'A']", "2026-05-26T14:44:24"]]
        _, out = normalise_rows(header, rows)
        assert out == [["['A', 'Z']", "<TIMESTAMP>"]]

    def test_header_returned_unchanged(self):
        header = ["a", "timestamp", "b"]
        out_header, _ = normalise_rows(header, [])
        assert out_header == header


# ---------------------------------------------------------------------------
# compare() — end-to-end against tmp files
# ---------------------------------------------------------------------------

def _write_csv(path: Path, header, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


class TestCompareEndToEnd:
    def test_identical_normalised_returns_0(self, tmp_path: Path, capsys):
        header = ["agent", "msg", "timestamp"]
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        _write_csv(a, header, [["x", "['A', 'B']", "2026-05-26T01:00:00"]])
        _write_csv(b, header, [["x", "['B', 'A']", "2026-05-26T99:99:99"]])
        rc = compare(a, b)
        captured = capsys.readouterr()
        assert rc == 0
        assert "IDENTICAL" in captured.out

    def test_genuine_diff_returns_1(self, tmp_path: Path, capsys):
        header = ["agent", "skill"]
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        _write_csv(a, header, [["x", "buy_insurance"]])
        _write_csv(b, header, [["x", "elevate_house"]])
        rc = compare(a, b)
        captured = capsys.readouterr()
        assert rc == 1
        assert "DIFFERS" in captured.out
        assert "buy_insurance" in captured.out
        assert "elevate_house" in captured.out

    def test_header_mismatch_returns_1(self, tmp_path: Path, capsys):
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        _write_csv(a, ["agent", "skill"], [["x", "y"]])
        _write_csv(b, ["agent", "skill", "extra"], [["x", "y", "z"]])
        rc = compare(a, b)
        captured = capsys.readouterr()
        assert rc == 1
        assert "HEADER MISMATCH" in captured.out

    def test_row_count_mismatch_returns_1(self, tmp_path: Path, capsys):
        header = ["agent"]
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        _write_csv(a, header, [["x"], ["y"]])
        _write_csv(b, header, [["x"]])
        rc = compare(a, b)
        captured = capsys.readouterr()
        assert rc == 1
        assert "ROW COUNT MISMATCH" in captured.out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestCLI:
    def test_main_happy_path_returns_0(self, tmp_path: Path):
        header = ["agent"]
        a = tmp_path / "a.csv"
        b = tmp_path / "b.csv"
        _write_csv(a, header, [["x"]])
        _write_csv(b, header, [["x"]])
        assert main([str(a), str(b)]) == 0

    def test_main_missing_file_returns_2(self, tmp_path: Path, capsys):
        rc = main([str(tmp_path / "missing.csv"), str(tmp_path / "also_missing.csv")])
        captured = capsys.readouterr()
        assert rc == 2
        assert "file not found" in captured.err
