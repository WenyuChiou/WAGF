import json

import pandas as pd

from examples.irrigation_abm.validate_smoke import validate


def test_functional_smoke_validation_accepts_tiny_runs(tmp_path):
    pd.DataFrame([
        {
            "agent_id": "Agent_000",
            "year": 1,
            "yearly_decision": "increase_large",
            "wsa_label": "L",
            "aca_label": "VH",
            "magnitude_pct": 10,
            "is_exploration": False,
            "cluster": "aggressive",
            "request": 100000,
        }
    ]).to_csv(tmp_path / "simulation_log.csv", index=False)
    pd.DataFrame([
        {"agent_id": "Agent_000", "year": 1, "status": "APPROVED"}
    ]).to_csv(tmp_path / "irrigation_farmer_governance_audit.csv", index=False)
    (tmp_path / "audit_summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "governance_summary.json").write_text(
        json.dumps({"total_interventions": 0}),
        encoding="utf-8",
    )
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "irrigation_farmer_traces.jsonl").write_text(
        json.dumps({"agent_id": "Agent_000"}) + "\n",
        encoding="utf-8",
    )

    results = validate(tmp_path, functional_smoke=True)

    assert results
    assert all(results.values())


def test_full_smoke_verdict_does_not_claim_ready_when_critical_checks_fail(tmp_path, capsys):
    pd.DataFrame([
        {
            "agent_id": "Agent_000",
            "year": 1,
            "yearly_decision": "increase_large",
            "wsa_label": "L",
            "aca_label": "VH",
            "magnitude_pct": 10,
            "is_exploration": False,
            "cluster": "aggressive",
            "request": 100000,
        }
    ]).to_csv(tmp_path / "simulation_log.csv", index=False)
    pd.DataFrame([
        {"agent_id": "Agent_000", "year": 1, "status": "APPROVED", "failed_rules": ""}
    ]).to_csv(tmp_path / "irrigation_farmer_governance_audit.csv", index=False)
    (tmp_path / "audit_summary.json").write_text("{}", encoding="utf-8")
    (tmp_path / "governance_summary.json").write_text(
        json.dumps({
            "total_interventions": 30,
            "rule_frequency": {},
            "outcome_stats": {"retry_success": 3, "retry_exhausted": 2},
        }),
        encoding="utf-8",
    )

    validate(tmp_path)
    captured = capsys.readouterr().out

    assert "WARNING: Some CRITICAL checks FAILED!" in captured
    assert "VERDICT: Critical checks failed; not ready for production run." in captured
    assert "VERDICT: Ready for production run." not in captured
