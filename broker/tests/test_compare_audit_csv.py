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
    _VOLATILE_COLUMN_NAMES,
    _sort_set_repr_in_cell,
    _timestamp_columns,
    _volatile_columns,
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


class TestVolatileColumns:
    """Elapsed-time columns (2026-09-15).

    Every other transform in this module has a test class; without one a rename
    or typo in `_VOLATILE_COLUMN_NAMES` silently reverts to comparing raw
    milliseconds, and every real-LLM byte-identity check then fails for a reason
    that has nothing to do with the simulation, with nothing to say so.
    """

    def test_the_named_columns_are_found(self):
        header = ["step_id", "llm_latency_ms", "timestamp", "tokens_per_second"]
        assert _volatile_columns(header) == [1, 3]

    def test_lookup_is_case_insensitive_and_whitespace_tolerant(self):
        assert _volatile_columns([" LLM_Latency_MS "]) == [0]

    def test_unrelated_columns_are_untouched(self):
        assert _volatile_columns(["prompt_tokens", "llm_retries"]) == []

    def test_the_names_match_what_the_audit_writer_emits(self):
        """Guards against the column being renamed on one side only."""
        from broker.components.analytics.audit import trace_to_csv_row

        row = trace_to_csv_row({
            "step_id": 1,
            "approved_skill": {"skill_name": "x", "status": "APPROVED"},
            "llm_stats": {"llm_latency_ms": 12.5, "tokens_per_second": 4.0},
        })
        for name in _VOLATILE_COLUMN_NAMES:
            assert name in row, (
                f"{name} is normalised as volatile but is not a column the "
                f"audit writer emits — one side was renamed"
            )

    def test_two_runs_differing_only_in_timing_compare_identical(self, tmp_path, capsys):
        header = ["step_id", "final_skill", "llm_latency_ms", "tokens_per_second"]
        left, right = tmp_path / "l.csv", tmp_path / "r.csv"
        _write_csv(left, header, [["1", "elevate", "812.5", "41.2"]])
        _write_csv(right, header, [["1", "elevate", "903.1", "38.7"]])
        assert compare(left, right) == 0
        assert "IDENTICAL" in capsys.readouterr().out

    def test_a_real_difference_beside_timing_still_fails(self, tmp_path):
        header = ["step_id", "final_skill", "llm_latency_ms"]
        left, right = tmp_path / "l.csv", tmp_path / "r.csv"
        _write_csv(left, header, [["1", "elevate", "812.5"]])
        _write_csv(right, header, [["1", "relocate", "903.1"]])
        assert compare(left, right) == 1


class TestIgnoreColumns:
    """`--ignore-columns`, added with the v0.10 cost columns.

    A corpus frozen before a schema addition has a narrower header, so the
    header check fails outright and there is otherwise no way to re-verify that
    corpus once the addition lands.
    """

    def test_a_frozen_corpus_verifies_against_a_wider_current_run(self, tmp_path, capsys):
        old_csv, new_csv = tmp_path / "frozen.csv", tmp_path / "current.csv"
        _write_csv(old_csv, ["step_id", "final_skill"], [["1", "elevate"]])
        _write_csv(new_csv, ["step_id", "final_skill", "llm_calls_total"],
                   [["1", "elevate", "6"]])
        assert compare(old_csv, new_csv) == 1  # header mismatch without the flag
        assert compare(old_csv, new_csv, drop_columns=["llm_calls_total"]) == 0
        assert "ignoring ['llm_calls_total']" in capsys.readouterr().out

    def test_the_result_line_says_what_was_ignored(self, tmp_path, capsys):
        """A comparison that dropped columns is a weaker claim than one that did
        not, so the output has to say which it is."""
        p1, p2 = tmp_path / "a.csv", tmp_path / "b.csv"
        _write_csv(p1, ["step_id", "x"], [["1", "9"]])
        _write_csv(p2, ["step_id", "x"], [["1", "9"]])
        compare(p1, p2, drop_columns=["x"])
        assert "ignoring ['x']" in capsys.readouterr().out

    def test_dropping_hides_a_difference_only_in_the_named_column(self, tmp_path):
        p1, p2 = tmp_path / "a.csv", tmp_path / "b.csv"
        _write_csv(p1, ["step_id", "x", "y"], [["1", "9", "same"]])
        _write_csv(p2, ["step_id", "x", "y"], [["1", "8", "same"]])
        assert compare(p1, p2) == 1
        assert compare(p1, p2, drop_columns=["x"]) == 0
        assert compare(p1, p2, drop_columns=["y"]) == 1

    def test_cli_parses_the_comma_list(self, tmp_path, capsys):
        p1, p2 = tmp_path / "a.csv", tmp_path / "b.csv"
        _write_csv(p1, ["step_id", "x", "y"], [["1", "9", "7"]])
        _write_csv(p2, ["step_id", "x", "y"], [["1", "8", "6"]])
        assert main([str(p1), str(p2)]) == 1
        assert main([str(p1), str(p2), "--ignore-columns", "x, y"]) == 0
