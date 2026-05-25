"""Phase 6O-C-1 — Tests for the readiness report CLI + profile loader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from broker.components.validation.readiness_profile import (
    PROFILE_NAMES,
    ReadinessProfile,
    ReadinessThresholds,
    load_readiness_profile,
)
from broker.tools.readiness_report import (
    ReadinessMetrics,
    ReadinessReport,
    ThresholdCheck,
    compute_readiness_report,
    main,
)


# ---------------------------------------------------------------------------
# Profile loader
# ---------------------------------------------------------------------------


def test_profile_names_are_three():
    """Production deferred per user decision — shipped profiles are exactly
    functional / behavioral / stress."""
    assert PROFILE_NAMES == ("functional", "behavioral", "stress")
    assert "production" not in PROFILE_NAMES


def test_load_functional_profile_defaults():
    p = load_readiness_profile("functional")
    assert p.name == "functional"
    assert p.description.startswith("Verifies the pipeline")
    assert p.thresholds.min_approval_rate == 0.80
    assert p.thresholds.max_format_retry_rate == 0.30
    # Behavioral-only fields are None for functional:
    assert p.thresholds.min_action_coverage is None
    assert p.thresholds.max_dead_validators is None


def test_load_behavioral_profile_defaults():
    p = load_readiness_profile("behavioral")
    assert p.thresholds.min_action_coverage == 3
    assert p.thresholds.min_validator_firing_diversity == 2


def test_load_stress_profile_strict_dead_validators():
    p = load_readiness_profile("stress")
    # 6O-C-1 round-1: was require_no_dead_validators=True; now
    # max_dead_validators=0 (still strict, but cross-domain runs can
    # override to a small int > 0 via --profile-yaml).
    assert p.thresholds.max_dead_validators == 0
    assert p.thresholds.max_terminal_rate == 0.20


def test_load_unknown_profile_raises():
    with pytest.raises(ValueError, match="Unknown profile"):
        load_readiness_profile("production")


def test_load_custom_yaml_override(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        yaml.safe_dump(
            {
                "profiles": {
                    "functional": {
                        "description": "custom",
                        "thresholds": {"min_approval_rate": 0.50},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    p = load_readiness_profile("functional", yaml_path=custom)
    assert p.description == "custom"
    assert p.thresholds.min_approval_rate == 0.50


def test_load_yaml_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_readiness_profile("functional", yaml_path=tmp_path / "nonexistent.yaml")


# ---------------------------------------------------------------------------
# Synthetic results-dir fixtures + compute_readiness_report
# ---------------------------------------------------------------------------


def _write_audit_summary(d: Path, total: int, format_retries: int = 0, health=None):
    summary = {
        "total_traces": total,
        "validation_errors": 0,
        "validation_warnings": 0,
        "total_format_retries": format_retries,
        "validator_health": health or {},
    }
    (d / "audit_summary.json").write_text(json.dumps(summary), encoding="utf-8")


def _write_audit_csv(d: Path, rows):
    """rows: list of dicts with at least status + final_skill."""
    if not rows:
        return
    cols = sorted(set().union(*[r.keys() for r in rows]))
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(str(r.get(c, "")) for c in cols))
    (d / "agent_governance_audit.csv").write_text("\n".join(lines), encoding="utf-8")


def _write_jsonl_traces(d: Path, traces):
    raw = d / "raw"
    raw.mkdir(exist_ok=True)
    with (raw / "traces.jsonl").open("w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t) + "\n")


def test_compute_metrics_minimal_approved(tmp_path):
    _write_audit_summary(tmp_path, total=2)
    _write_audit_csv(
        tmp_path,
        [
            {"status": "APPROVED", "final_skill": "do_nothing", "retry_count": 0},
            {"status": "APPROVED", "final_skill": "take_action", "retry_count": 0},
        ],
    )
    p = load_readiness_profile("functional")
    report = compute_readiness_report(tmp_path, p)
    assert report.metrics.total_traces == 2
    assert report.metrics.approved_count == 2
    assert report.metrics.approval_rate == 1.0
    assert report.metrics.action_coverage == 2
    assert sorted(report.metrics.distinct_actions) == ["do_nothing", "take_action"]
    assert report.overall_passed is True


def test_compute_metrics_with_retries(tmp_path):
    _write_audit_summary(tmp_path, total=10, format_retries=4)
    _write_audit_csv(
        tmp_path,
        [
            {"status": "APPROVED", "final_skill": "skill_a", "retry_count": 0}
            for _ in range(9)
        ]
        + [{"status": "REJECTED", "final_skill": "", "retry_count": 3}],
    )
    p = load_readiness_profile("functional")
    report = compute_readiness_report(tmp_path, p)
    assert report.metrics.approval_rate == 0.9
    assert report.metrics.format_retry_rate == 0.4
    # functional threshold: max_format_retry_rate=0.30 — 0.4 > 0.3 → FAIL
    assert report.overall_passed is False
    failing = [c for c in report.checks if not c.passed]
    assert any(c.metric_name == "format_retry_rate" for c in failing)


def test_compute_metrics_terminal_taxonomy_from_jsonl(tmp_path):
    """W3 fix (6O-C-1 round-1): explicit agent_id + year per row so the
    (agent_id, year) JSONL <-> CSV join key is unique and disambiguated."""
    _write_audit_summary(tmp_path, total=3)
    _write_audit_csv(
        tmp_path,
        [
            {"agent_id": "A1", "year": "1", "status": "APPROVED", "final_skill": "x", "retry_count": 0},
            {"agent_id": "A2", "year": "1", "status": "REJECTED", "final_skill": "x", "retry_count": 0},
            {"agent_id": "A3", "year": "1", "status": "APPROVED", "final_skill": "y", "retry_count": 2},
        ],
    )
    _write_jsonl_traces(
        tmp_path,
        [
            {"agent_id": "A1", "year": 1, "status": "APPROVED", "retry_count": 0},
            {
                "agent_id": "A2", "year": 1,
                "status": "REJECTED",
                "retry_count": 0,
                "validation_issues": [
                    {"metadata": {"expected_terminal": True}},
                ],
            },
            {"agent_id": "A3", "year": 1, "status": "APPROVED", "retry_count": 2},
        ],
    )
    p = load_readiness_profile("functional")
    report = compute_readiness_report(tmp_path, p)
    assert report.metrics.terminal_taxonomy["approved"] == 1
    assert report.metrics.terminal_taxonomy["retry_recovered"] == 1
    assert report.metrics.terminal_taxonomy["expected_hard_block"] == 1
    # terminal_rate = (3 - 2) / 3 = 0.333 (one expected_hard_block)
    assert report.metrics.terminal_rate == 0.3333


def test_compute_metrics_missing_inputs_degrade(tmp_path):
    """Empty results-dir → empty metrics + report with overall_passed=True
    (no checks fired against missing data per the design contract)."""
    p = load_readiness_profile("functional")
    report = compute_readiness_report(tmp_path, p)
    assert report.metrics.total_traces is None
    # Functional has 2 thresholds; both fail because observed=None.
    failing = [c for c in report.checks if not c.passed]
    assert len(failing) >= 1


def test_validator_firing_diversity_and_dead_detection(tmp_path):
    health = {
        "rule_a": {"error_count": 5, "warn_count": 0, "hit_count": 5},
        "rule_b": {"error_count": 0, "warn_count": 0, "hit_count": 0},  # dead
        "rule_c": {"warn_count": 3, "hit_count": 3},
    }
    _write_audit_summary(tmp_path, total=10, health=health)
    _write_audit_csv(
        tmp_path,
        [
            {"status": "APPROVED", "final_skill": f"skill_{i % 3}", "retry_count": 0}
            for i in range(10)
        ],
    )
    p = load_readiness_profile("stress")
    report = compute_readiness_report(tmp_path, p)
    assert report.metrics.validator_firing_diversity == 2  # rule_a + rule_c
    assert report.metrics.dead_validators == ["rule_b"]
    # stress profile requires no dead validators → FAIL
    dead_check = next(c for c in report.checks if c.metric_name == "dead_validators")
    assert dead_check.passed is False


def test_main_cli_passes_when_thresholds_met(tmp_path, capsys):
    _write_audit_summary(tmp_path, total=10, format_retries=0)
    _write_audit_csv(
        tmp_path,
        [
            {"status": "APPROVED", "final_skill": "s", "retry_count": 0}
            for _ in range(10)
        ],
    )
    rc = main(
        [
            "--results",
            str(tmp_path),
            "--profile",
            "functional",
            "--no-json",
        ]
    )
    out = capsys.readouterr().out
    assert "Readiness report" in out
    assert "Overall: PASS" in out
    assert rc == 0


def test_main_cli_writes_json_by_default(tmp_path):
    _write_audit_summary(tmp_path, total=10)
    _write_audit_csv(
        tmp_path,
        [
            {"status": "APPROVED", "final_skill": "s", "retry_count": 0}
            for _ in range(10)
        ],
    )
    rc = main(["--results", str(tmp_path), "--profile", "functional"])
    assert rc == 0
    assert (tmp_path / "readiness_report.json").is_file()
    with (tmp_path / "readiness_report.json").open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["profile_name"] == "functional"
    assert data["overall_passed"] is True


def test_main_cli_returns_2_on_missing_results_dir(capsys, tmp_path):
    bogus = tmp_path / "does_not_exist"
    rc = main(["--results", str(bogus), "--profile", "functional", "--no-json"])
    err = capsys.readouterr().err
    assert "results dir not found" in err
    assert rc == 2
