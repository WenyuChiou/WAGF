"""
Audit schema regression tests (Pillar 2 Action C, 2026-05-09).

Locks down three properties of the audit pipeline that, if regressed,
would silently corrupt headline experiment results:

1. **Sentinel detector** (``detect_audit_sentinels``) — flags constant
   placeholder columns. This was the 2026-04-19 NW flood post-mortem
   trigger and the seed of ``broker/INVARIANTS.md`` Invariant 2.

2. **Proposed-vs-approved column separation** — Paper 3 headline rule
   (MEMORY 2026-04-14): ``proposed_skill`` and ``final_skill`` MUST
   stay structurally distinct in the audit CSV. Collapsing them would
   destroy the EXECUTED-ONLY discipline.

3. **Aggregate-dict startup warning** — when an upstream pipeline
   (memory / social / cognitive / rule_breakdown) is absent, the audit
   writer must warn at first trace rather than silently emit hardcoded
   placeholder defaults.

Companion to ``tests/test_audit_modular.py`` (which tests forward-path
correctness) and ``tests/test_validator_pipeline_interaction.py``
(which tests the upstream side of the pipeline).
"""
from __future__ import annotations

import csv
import logging
import tempfile
from pathlib import Path

import pytest

from broker.components.analytics.audit import (
    AuditConfig,
    GenericAuditWriter,
    detect_audit_sentinels,
    detect_audit_sentinels_in_csv,
    _SENTINEL_MIN_ROWS,
    _SUSPICIOUS_COLUMN_DEFAULTS,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def writer_and_dir():
    """Audit writer with a fresh temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = AuditConfig(
            output_dir=tmpdir,
            experiment_name="test_audit_schema_regression",
            clear_existing_traces=True,
        )
        yield GenericAuditWriter(config), tmpdir


def _rows_constant(column: str, value, n: int = 60) -> list:
    """Build n synthetic rows where every row has the same value for *column*."""
    return [{column: value, "agent_id": f"a{i}"} for i in range(n)]


def _rows_varied(column: str, values: list, n: int = 60) -> list:
    """Build n synthetic rows cycling through *values*."""
    return [{column: values[i % len(values)], "agent_id": f"a{i}"} for i in range(n)]


# ─────────────────────────────────────────────────────────────────────
# C-1: detect_audit_sentinels positive cases (catches real leaks)
# ─────────────────────────────────────────────────────────────────────

class TestSentinelDetectorPositive:
    """Constant placeholder values → detector must flag them."""

    @pytest.mark.parametrize("column,placeholder", [
        ("mem_top_emotion", "neutral"),
        ("mem_top_source", "personal"),
        ("mem_surprise", 0.0),
        ("cog_is_novel_state", False),
        ("cog_surprise_value", 0.0),
        ("cog_system_mode", ""),
        ("social_gossip_count", 0),
        ("social_network_density", 0.0),
    ])
    def test_constant_placeholder_is_flagged(self, column, placeholder):
        """Each declared suspicious column + its placeholder = warning."""
        rows = _rows_constant(column, placeholder, n=60)
        warnings = detect_audit_sentinels(rows)
        flagged = [w for w in warnings if column in w]
        assert flagged, (
            f"Expected sentinel detector to flag '{column}={placeholder!r}' "
            f"but got warnings: {warnings}"
        )

    def test_pipeline_leak_pattern_2026_04_19(self):
        """Reconstruct the 2026-04-19 NW flood failure pattern: memory pipeline
        silently absent, audit fields wrote hardcoded placeholders for every
        agent-year. Detector must flag at least the four mem_* columns."""
        rows = []
        for i in range(60):
            rows.append({
                "agent_id": f"a{i}",
                "mem_top_emotion": "neutral",
                "mem_top_source": "personal",
                "mem_surprise": 0.0,
                "mem_cognitive_system": "",
            })
        warnings = detect_audit_sentinels(rows)
        flagged_columns = {
            col for col in ("mem_top_emotion", "mem_top_source",
                            "mem_surprise", "mem_cognitive_system")
            if any(col in w for w in warnings)
        }
        assert len(flagged_columns) >= 3, (
            f"2026-04-19 leak pattern should flag at least 3 of 4 mem_* "
            f"columns. Flagged: {flagged_columns}, warnings: {warnings}"
        )


# ─────────────────────────────────────────────────────────────────────
# C-2: detect_audit_sentinels negative cases (no false positives)
# ─────────────────────────────────────────────────────────────────────

class TestSentinelDetectorNegative:
    """Varied or non-placeholder values → detector must stay silent."""

    def test_varied_values_not_flagged(self):
        rows = _rows_varied("mem_top_emotion", ["major", "minor", "neutral"], n=60)
        warnings = detect_audit_sentinels(rows)
        assert not [w for w in warnings if "mem_top_emotion" in w], (
            f"Varied values incorrectly flagged: {warnings}"
        )

    def test_below_min_rows_skipped(self):
        """Sanity runs (e.g. quickstart smoke) must not trip the detector."""
        rows = _rows_constant("mem_top_emotion", "neutral", n=_SENTINEL_MIN_ROWS - 1)
        warnings = detect_audit_sentinels(rows)
        assert not warnings, (
            f"Detector should skip below {_SENTINEL_MIN_ROWS} rows; "
            f"got: {warnings}"
        )

    def test_constant_non_placeholder_not_flagged(self):
        """A column constantly = 'major' (not a known placeholder) is fine.
        Some experiments legitimately produce constant non-default values."""
        rows = _rows_constant("mem_top_emotion", "major", n=60)
        warnings = detect_audit_sentinels(rows)
        assert not [w for w in warnings if "mem_top_emotion" in w], (
            "'major' is not a placeholder default — should not be flagged."
        )

    def test_missing_column_not_flagged(self):
        """If the column doesn't appear in the rows, detector ignores it."""
        rows = [{"agent_id": f"a{i}", "year": i} for i in range(60)]
        warnings = detect_audit_sentinels(rows)
        # No mem_*, cog_*, social_* fields present at all
        assert not warnings

    def test_empty_rows_returns_empty(self):
        assert detect_audit_sentinels([]) == []


# ─────────────────────────────────────────────────────────────────────
# C-3: Sentinel column registry locked
# ─────────────────────────────────────────────────────────────────────

class TestSentinelRegistryStability:
    """The list of suspicious columns is part of the public invariant
    contract. Adding/removing columns silently would weaken (or break)
    leak detection — this test catches accidental edits."""

    def test_canonical_suspect_columns_present(self):
        canonical = {
            "mem_top_emotion", "mem_top_source", "mem_surprise",
            "mem_cognitive_system",
            "cog_is_novel_state", "cog_surprise_value",
            "cog_margin_to_switch", "cog_system_mode",
            "social_gossip_count", "social_network_density",
        }
        assert canonical.issubset(_SUSPICIOUS_COLUMN_DEFAULTS.keys()), (
            f"Missing suspect columns: {canonical - _SUSPICIOUS_COLUMN_DEFAULTS.keys()}"
        )


# ─────────────────────────────────────────────────────────────────────
# C-4: Proposed vs final skill columns — Paper 3 EXECUTED-ONLY rule
# ─────────────────────────────────────────────────────────────────────

class TestProposedFinalSkillSeparation:
    """``proposed_skill`` and ``final_skill`` are structurally separate
    in the audit CSV. They MUST not collapse, because Paper 3 headline
    rule (MEMORY 2026-04-14) requires EXECUTED-ONLY metrics built from
    ``final_skill`` while reasoning labels stay in proposed-stage form."""

    def test_proposed_and_final_kept_distinct(self, writer_and_dir):
        """Write a trace where the validator rejects the proposal and the
        executed action differs. CSV must record both values separately."""
        writer, tmpdir = writer_and_dir
        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "year": 2024,
            "skill_proposal": {
                "skill_name": "elevate_house",
                "parse_layer": "test",
                "raw_output": "{'skill': 'elevate_house'}",
                "reasoning": {"TP_LABEL": "VH", "CP_LABEL": "H"},
            },
            "approved_skill": {
                "skill_name": "do_nothing",  # validator rerouted
                "status": "REJECTED",
            },
            "memory_audit": {"retrieved_count": 0, "memories": []},
            "social_audit": {},
            "cognitive_audit": {},
            "rule_breakdown": {},
        }
        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        assert csv_path.exists()
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            row = next(csv.DictReader(f))

        assert "proposed_skill" in row
        assert "final_skill" in row
        assert row["proposed_skill"] == "elevate_house"
        assert row["final_skill"] == "do_nothing"
        assert row["proposed_skill"] != row["final_skill"], (
            "Paper 3 EXECUTED-ONLY rule: proposed and final must stay separable"
        )

    def test_status_column_distinct_from_skill_columns(self, writer_and_dir):
        """The ``status`` column carries the validator outcome and is its
        own field — it must not be conflated with skill_name."""
        writer, tmpdir = writer_and_dir
        trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "year": 2024,
            "skill_proposal": {"skill_name": "buy_insurance", "parse_layer": "test"},
            "approved_skill": {"skill_name": "buy_insurance", "status": "APPROVED"},
            "memory_audit": {"retrieved_count": 0, "memories": []},
            "social_audit": {},
            "cognitive_audit": {},
            "rule_breakdown": {},
        }
        writer.write_trace("household", trace)
        writer.finalize()

        csv_path = Path(tmpdir) / "household_governance_audit.csv"
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            row = next(csv.DictReader(f))

        assert row["status"] == "APPROVED"
        assert row["proposed_skill"] == "buy_insurance"
        assert row["final_skill"] == "buy_insurance"


# ─────────────────────────────────────────────────────────────────────
# C-5: First-trace warning when upstream aggregate dict is absent
# ─────────────────────────────────────────────────────────────────────

class TestStartupAggregateWarning:
    """When an upstream pipeline (memory / social / cognitive /
    rule_breakdown) does not populate its dict, the audit writer warns
    at first trace. Without this guard, the 2026-04-19 leak pattern
    would not have surfaced for several days of runs."""

    def test_missing_aggregate_dicts_emit_startup_warning(self, writer_and_dir, caplog):
        writer, _ = writer_and_dir
        bare_trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "year": 2024,
            "skill_proposal": {"skill_name": "do_nothing", "parse_layer": "test"},
            "approved_skill": {"skill_name": "do_nothing", "status": "APPROVED"},
            # Intentionally omit memory_audit, social_audit, cognitive_audit,
            # rule_breakdown.
        }
        with caplog.at_level(logging.WARNING):
            writer.write_trace("household", bare_trace)

        warning_text = "\n".join(rec.getMessage() for rec in caplog.records)
        # Must mention at least one of the missing aggregate keys
        assert any(key in warning_text for key in
                   ("memory_audit", "social_audit", "cognitive_audit",
                    "rule_breakdown")), (
            f"Expected first-trace warning about missing aggregates. "
            f"Captured: {warning_text!r}"
        )

    def test_warning_fires_only_once_per_writer(self, writer_and_dir, caplog):
        """First-trace warning is one-shot — subsequent traces with the
        same gap don't spam logs."""
        writer, _ = writer_and_dir
        bare_trace = {
            "step_id": 1,
            "agent_id": "agent_001",
            "year": 2024,
            "skill_proposal": {"skill_name": "do_nothing", "parse_layer": "test"},
            "approved_skill": {"skill_name": "do_nothing", "status": "APPROVED"},
        }
        with caplog.at_level(logging.WARNING):
            writer.write_trace("household", bare_trace)
            n_warnings_after_first = len([r for r in caplog.records
                                          if "AuditInvariant" in r.getMessage()])
            writer.write_trace("household", bare_trace)
            writer.write_trace("household", bare_trace)
            n_warnings_after_third = len([r for r in caplog.records
                                          if "AuditInvariant" in r.getMessage()])

        assert n_warnings_after_first == n_warnings_after_third, (
            "Startup warning should fire once, not on every trace"
        )


# ─────────────────────────────────────────────────────────────────────
# C-6: CSV → sentinel-detector round trip
# ─────────────────────────────────────────────────────────────────────

class TestCSVRoundTrip:
    """detect_audit_sentinels_in_csv must work on a real on-disk CSV
    so post-hoc triage of an old experiment dir is reliable."""

    def test_csv_round_trip_flags_known_leak(self, tmp_path):
        csv_path = tmp_path / "leaky_audit.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["agent_id", "mem_top_emotion"])
            writer.writeheader()
            for i in range(60):
                writer.writerow({"agent_id": f"a{i}", "mem_top_emotion": "neutral"})

        warnings = detect_audit_sentinels_in_csv(str(csv_path))
        assert any("mem_top_emotion" in w for w in warnings), (
            f"CSV round trip should flag 'mem_top_emotion'. Got: {warnings}"
        )

    def test_csv_round_trip_clean_data_silent(self, tmp_path):
        csv_path = tmp_path / "clean_audit.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["agent_id", "mem_top_emotion"])
            writer.writeheader()
            for i in range(60):
                writer.writerow({
                    "agent_id": f"a{i}",
                    "mem_top_emotion": ["major", "minor", "neutral"][i % 3],
                })

        warnings = detect_audit_sentinels_in_csv(str(csv_path))
        assert not [w for w in warnings if "mem_top_emotion" in w]
