"""Tests for broker.tools.appraisal_grounding_audit."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from broker.domains.registry import DomainPackRegistry
from broker.tools import appraisal_grounding_audit


class GroundingPack:
    name = "grounding_test"

    def appraisal_grounding_map(self):
        return {
            "construct": "WSA_LABEL",
            "shortage_tier_to_wsa": {0: "L", 1: "M", 2: "H", 3: "VH"},
            "drought_index_bump_threshold": 0.6,
        }


class NoGroundingPack:
    name = "no_grounding"

    def appraisal_grounding_map(self):
        return None


def _make_record(
    *,
    step_id: int = 1,
    wsa: str | None = "M",
    shortage_tier: int | None = 1,
    drought_index: float = 0.1,
    curtailment_ratio: float = 0.0,
    model: str = "test-model",
) -> dict:
    reasoning = {}
    if wsa is not None:
        reasoning["WSA_LABEL"] = wsa
    state_before = {"curtailment_ratio": curtailment_ratio}
    if shortage_tier is not None:
        state_before["shortage_tier"] = shortage_tier
    return {
        "step_id": step_id,
        "agent_id": f"agent_{step_id}",
        "year": 2026,
        "model": model,
        "skill_proposal": {"reasoning": reasoning},
        "state_before": state_before,
        "environment_context": {"drought_index": drought_index},
    }


def _write_jsonl(output_dir: Path, agent_type: str, records: list[dict]) -> None:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir()
    jsonl_path = raw_dir / f"{agent_type}_traces.jsonl"
    metadata = {
        "_metadata": {
            "framework_version": "test-framework",
            "audit_schema_version": "test-schema",
            "git_commit_short": "abc123",
        }
    }
    with open(jsonl_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(metadata) + "\n")
        for record in records:
            f.write(json.dumps(record) + "\n")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_matching_self_and_env_wsa_scores_with_full_fidelity(tmp_path, capsys):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(tmp_path, "irrigation_farmer", [_make_record()])

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        rows = _read_csv(tmp_path / "appraisal_grounding.csv")
        assert len(rows) == 1
        assert rows[0]["self_wsa"] == "M"
        assert rows[0]["env_wsa"] == "M"
        assert rows[0]["drift"] == "0"
        assert rows[0]["label_inconsistent"] == "False"

        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert len(summary) == 1
        assert summary[0]["scored"] == "1"
        assert summary[0]["skipped"] == "0"
        assert float(summary[0]["fidelity"]) == 1.0
        assert float(summary[0]["mean_drift"]) == 0.0
        assert float(summary[0]["pct_label_inconsistent"]) == 0.0

        stdout = capsys.readouterr().out
        assert (
            "[OK] irrigation_farmer: 1 scored, "
            "0 skipped (+0 malformed lines), fidelity=1.0"
        ) in stdout
        assert "schema: framework=test-framework audit_schema=test-schema git=abc123" in stdout
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_large_drift_flags_qualitative_inconsistency(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(
            tmp_path,
            "irrigation_farmer",
            [_make_record(wsa="VL", shortage_tier=3)],
        )

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        rows = _read_csv(tmp_path / "appraisal_grounding.csv")
        assert rows[0]["self_wsa"] == "VL"
        assert rows[0]["env_wsa"] == "VH"
        assert rows[0]["drift"] == "4"
        assert rows[0]["label_inconsistent"] == "True"

        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert float(summary[0]["fidelity"]) == 0.0
        assert float(summary[0]["pct_label_inconsistent"]) == 1.0
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_drift_one_is_scored_but_not_inconsistent(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(
            tmp_path,
            "irrigation_farmer",
            [_make_record(wsa="H", shortage_tier=1)],
        )

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        rows = _read_csv(tmp_path / "appraisal_grounding.csv")
        assert rows[0]["self_wsa"] == "H"
        assert rows[0]["env_wsa"] == "M"
        assert rows[0]["drift"] == "1"
        assert rows[0]["label_inconsistent"] == "False"

        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert summary[0]["scored"] == "1"
        assert float(summary[0]["fidelity"]) == 1.0
        assert float(summary[0]["pct_label_inconsistent"]) == 0.0
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_missing_wsa_is_skipped_not_imputed(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(
            tmp_path,
            "irrigation_farmer",
            [_make_record(wsa=None), _make_record(step_id=2, wsa="M")],
        )

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        rows = _read_csv(tmp_path / "appraisal_grounding.csv")
        assert len(rows) == 1
        assert rows[0]["step_id"] == "2"

        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert summary[0]["scored"] == "1"
        assert summary[0]["skipped"] == "1"
        assert float(summary[0]["fidelity"]) == 1.0
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_unregistered_or_unmapped_domain_refuses_without_csv(tmp_path, capsys):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        _write_jsonl(tmp_path, "irrigation_farmer", [_make_record()])

        missing_exit = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "missing_domain"]
        )
        assert missing_exit == 2
        assert not (tmp_path / "appraisal_grounding.csv").exists()
        assert not (tmp_path / "appraisal_grounding_summary.csv").exists()

        DomainPackRegistry.register("no_grounding", NoGroundingPack())
        unmapped_exit = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "no_grounding"]
        )
        assert unmapped_exit == 2
        assert not (tmp_path / "appraisal_grounding.csv").exists()
        assert not (tmp_path / "appraisal_grounding_summary.csv").exists()

        stderr = capsys.readouterr().err
        assert "ERROR:" in stderr
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_tier_above_max_key_clamps(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(
            tmp_path,
            "irrigation_farmer",
            [_make_record(wsa="VH", shortage_tier=5, drought_index=0.1)],
        )

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        rows = _read_csv(tmp_path / "appraisal_grounding.csv")
        assert len(rows) == 1
        assert rows[0]["env_wsa"] == "VH"

        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert summary[0]["scored"] == "1"
        assert summary[0]["skipped"] == "0"
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_drought_bump_capped_at_vh(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(
            tmp_path,
            "irrigation_farmer",
            [_make_record(wsa="H", shortage_tier=3, drought_index=0.9)],
        )

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        rows = _read_csv(tmp_path / "appraisal_grounding.csv")
        assert rows[0]["env_wsa"] == "VH"
        assert rows[0]["drift"] == "1"
        assert rows[0]["label_inconsistent"] == "False"
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_two_models_aggregate_into_two_summary_rows(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(
            tmp_path,
            "irrigation_farmer",
            [
                _make_record(step_id=1, wsa="M", shortage_tier=1, model="model-a"),
                _make_record(step_id=2, wsa="H", shortage_tier=2, model="model-b"),
            ],
        )

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert len(summary) == 2
        by_model = {row["model"]: row for row in summary}
        assert by_model["model-a"]["scored"] == "1"
        assert by_model["model-a"]["skipped"] == "0"
        assert float(by_model["model-a"]["fidelity"]) == 1.0
        assert by_model["model-b"]["scored"] == "1"
        assert by_model["model-b"]["skipped"] == "0"
        assert float(by_model["model-b"]["fidelity"]) == 1.0
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_missing_drought_index_still_scores_via_base_tier(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        record = _make_record(wsa="M", shortage_tier=1)
        record["environment_context"] = {}
        _write_jsonl(tmp_path, "irrigation_farmer", [record])

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 0
        rows = _read_csv(tmp_path / "appraisal_grounding.csv")
        assert len(rows) == 1
        assert rows[0]["env_wsa"] == "M"

        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert summary[0]["scored"] == "1"
        assert summary[0]["skipped"] == "0"
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_zero_scoreable_records_refuses_without_header_only_csv(tmp_path, capsys):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        _write_jsonl(tmp_path, "irrigation_farmer", [_make_record(wsa=None)])

        exit_code = appraisal_grounding_audit.main(
            [str(tmp_path), "--domain", "grounding_test"]
        )

        assert exit_code == 2
        assert not (tmp_path / "appraisal_grounding.csv").exists()
        assert not (tmp_path / "appraisal_grounding_summary.csv").exists()
        stderr = capsys.readouterr().err
        assert (
            "ERROR: 0 scoreable records (check --domain and trace schema)"
            in stderr
        )
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)


def test_malformed_lines_are_separate_from_record_skips(tmp_path):
    saved_packs = dict(DomainPackRegistry._packs)
    saved_missing_warned = set(DomainPackRegistry._missing_warned)
    DomainPackRegistry._packs.clear()
    DomainPackRegistry._missing_warned.clear()
    try:
        DomainPackRegistry.register("grounding_test", GroundingPack())
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        jsonl_path = raw_dir / "irrigation_farmer_traces.jsonl"
        metadata = {
            "_metadata": {
                "framework_version": "test-framework",
                "audit_schema_version": "test-schema",
                "git_commit_short": "abc123",
            }
        }
        with open(jsonl_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(metadata) + "\n")
            f.write(json.dumps(_make_record(wsa=None)) + "\n")
            f.write("{malformed\n")
            f.write(json.dumps(_make_record(step_id=2, wsa="M")) + "\n")

        report = appraisal_grounding_audit.run_audit(tmp_path, "grounding_test")

        file_report = report["file_reports"][0]
        assert file_report["scored"] + file_report["record_skipped"] == 2
        assert file_report["record_skipped"] == 1
        assert file_report["parse_skipped"] == 1
        assert report["total_record_skipped"] == 1
        assert report["total_parse_skipped"] == 1

        summary = _read_csv(tmp_path / "appraisal_grounding_summary.csv")
        assert summary[0]["scored"] == "1"
        assert summary[0]["skipped"] == "1"
    finally:
        DomainPackRegistry._packs.clear()
        DomainPackRegistry._packs.update(saved_packs)
        DomainPackRegistry._missing_warned.clear()
        DomainPackRegistry._missing_warned.update(saved_missing_warned)
