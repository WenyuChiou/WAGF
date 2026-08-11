from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "ICLR2027"
    / "submission"
    / "checks"
    / "forensic_irrigation_provenance.py"
)
SPEC = importlib.util.spec_from_file_location("forensic_irrigation_provenance", MODULE_PATH)
assert SPEC and SPEC.loader
audit_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_module
SPEC.loader.exec_module(audit_module)


def _record(agent_id: str, year: int, request: float = 1.0) -> dict:
    return {
        "agent_id": agent_id,
        "year": year,
        "timestamp": f"2026-01-{year:02d}T00:00:00",
        "model": "gemma3:4b",
        "input": "prompt",
        "state_before": {},
        "environment_context": {},
        "state_after": {"request": request},
    }


def test_read_trace_separates_metadata_invalid_and_duplicate_rows(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    lines = [
        json.dumps({"_metadata": {"schema": 1}}),
        json.dumps(_record("a", 1, 2.0)),
        json.dumps(_record("a", 1, 3.0)),
        json.dumps({"agent_id": "missing-year"}),
        "{not-json",
    ]
    trace.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = audit_module._read_trace(trace)

    assert result["nonblank_lines"] == 5
    assert result["parsed_records"] == 4
    assert result["metadata_records"] == 1
    assert result["malformed_json_lines"] == 1
    assert result["invalid_data_records"] == 1
    assert result["data_rows"] == 2
    assert result["duplicate_key_rows"] == 1
    assert len(result["requests"]) == 2


def test_critical_fingerprint_fails_closed_on_missing_path(monkeypatch) -> None:
    monkeypatch.setattr(audit_module, "CRITICAL_SHARED_PATHS", ("present.py", "missing.py"))
    monkeypatch.setattr(
        audit_module,
        "_blob",
        lambda _commit, path: "abc" if path == "present.py" else "MISSING_PATH",
    )

    fingerprint, blobs, missing = audit_module._critical_fingerprint("deadbeef")

    assert fingerprint is None
    assert blobs["present.py"] == "abc"
    assert missing == ["missing.py"]


def test_unattested_gemma_worker_settings_remain_unknown() -> None:
    for seed in (45, 46):
        for arm in ("strict", "no_validator"):
            workers, _evidence, strength = audit_module._known_workers("gemma3:4b", seed, arm)
            assert workers is None
            assert strength == "unknown"


def test_governed_gemma_seed42_is_not_claimed_by_launcher() -> None:
    workers, evidence, strength = audit_module._known_workers("gemma3:4b", 42, "strict")

    assert workers is None
    assert "does not launch" in evidence
    assert strength == "unknown"


def test_sentinel_status_does_not_claim_estimand_usage() -> None:
    assert audit_module.SENTINEL_STATUS == "UNRESOLVED_USAGE_NOT_AUDITED"
    assert "NOT_USED" not in audit_module.SENTINEL_STATUS
