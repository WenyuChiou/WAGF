"""Paper measures use recorded decisions, never cumulative adaptation states."""
import csv
import json
import math
import pytest

from examples.single_agent.analysis import flood_ibr_v2 as audit
from examples.single_agent.analysis import paper_measures as pm


def row(action="do_nothing", tp="H", cp="M", **changes):
    labels = f"TP_LABEL={tp}|CP_LABEL={cp}"
    result = dict(agent_id="A", year="1", status="APPROVED", execution_path="approved",
                  executed_skill=action, initial_skill=action, final_skill=action,
                  initial_labels=labels, final_labels=labels, attempt_skills=action,
                  attempt_labels=labels.replace("|", ","), appraisal_relabeled="False",
                  retry_count="0", failed_rules="")
    result.update(changes)
    return result


def decision(**changes):
    return audit.parse_decision(row(**changes), "fixture")


@pytest.mark.parametrize("action,tp,cp,elevated,expected", [
    ("do_nothing", "H", "M", False, {"R1"}),
    ("do_nothing", "VH", "H", False, {"R1"}),
    ("do_nothing", "H", "VH", False, {"R1"}),
    ("do_nothing", "H", "VL", False, set()),
    ("do_nothing", "H", "L", False, set()),
    ("do_nothing", "H", "", False, set()),
    ("do_nothing", "H", "unknown", False, set()),
    ("do_nothing", "M", "H", False, set()),
    ("relocate", "VL", "M", False, {"R3"}),
    ("relocate", "L", "L", False, {"R3"}),
    ("relocate", "M", "L", False, set()),
    ("elevate_house", "L", "H", False, {"R4"}),
    ("elevate_house", "VL", "M", True, {"R4", "R5"}),
    ("elevate_house", "H", "L", False, set()),
    ("elevate_house", "M", "M", True, {"R5"}),
    ("buy_insurance", "L", "M", True, set()),
])
def test_enforced_rule_predicates(action, tp, cp, elevated, expected):
    flags = pm.rule_flags(decision(action=action, tp=tp, cp=cp), elevated)
    assert {rule for rule, hit in flags.items() if hit} == expected


def test_union_aborted_and_executed_default():
    overlap = decision(action="elevate_house", tp="L")
    exhausted = decision(action="do_nothing", initial_skill="buy_insurance",
                         final_skill="buy_insurance", attempt_skills="buy_insurance",
                         status="REJECTED", execution_path="default")
    aborted = decision(status="ABORTED_EXCEPTION", execution_path="aborted",
                       executed_skill="", initial_skill="", attempt_skills="",
                       initial_labels="", final_labels="", attempt_labels="")
    result = pm.ibr_summary([overlap, exhausted, aborted], {("A", "1"): True})
    assert result["n"] == 2 and result["n_aborted"] == 1
    assert result["ibr_executed_count"] == 2
    assert result["ibr_executed_pct"] == 100
    assert result["behavioural_count"] == 2 and result["physical_count"] == 1
    assert result["R4_count"] == result["R5_count"] == result["R1_count"] == 1
    assert result["first_behavioural_count"] == 1


def test_first_stated_labels_and_pi_first_attempt_are_distinct():
    raw = row(tp="H", cp="", action="do_nothing", retry_count="1",
              attempt_skills="do_nothing|do_nothing",
              attempt_labels="TP_LABEL=H,CP_LABEL=|TP_LABEL=L,CP_LABEL=L",
              final_labels="TP_LABEL=L|CP_LABEL=L", appraisal_relabeled="True")
    d = audit.parse_decision(raw, "fixture")
    assert d.first_labels == {"TP_LABEL": "H", "CP_LABEL": "L"}
    assert pm.ibr_summary([d], {("A", "1"): False})["ibr_executed_count"] == 0
    # r44 treats first-attempt missing coping as not low; it never reads retry CP.
    assert pm.pi_ibr_summary([raw])["ibr_final_proposal_pi_count"] == 1


def test_relabelling_does_not_change_executed_or_first_proposal_checks():
    raw = row(action="buy_insurance", tp="L", initial_skill="relocate",
              attempt_skills="relocate|buy_insurance", retry_count="1",
              attempt_labels="TP_LABEL=L,CP_LABEL=M|TP_LABEL=H,CP_LABEL=M",
              final_labels="TP_LABEL=H|CP_LABEL=M", appraisal_relabeled="True")
    result = pm.ibr_summary([audit.parse_decision(raw, "fixture")], {("A", "1"): False})
    assert result["ibr_executed_count"] == 0
    assert result["first_behavioural_count"] == result["first_R3_count"] == 1


def test_executed_ibr_judges_first_stated_not_final_labels():
    # The owner's choice (2026-10-14): a retry that relabels the threat must not hide an R1 breach.
    raw = row(action="do_nothing", tp="H", cp="M", retry_count="1",
              attempt_skills="do_nothing|do_nothing",
              attempt_labels="TP_LABEL=H,CP_LABEL=M|TP_LABEL=M,CP_LABEL=M",
              final_labels="TP_LABEL=M|CP_LABEL=M", appraisal_relabeled="True")
    result = pm.ibr_summary([audit.parse_decision(raw, "fixture")], {("A", "1"): False})
    assert result["R1_count"] == 1


def test_pi_r1_requires_coping_not_low():
    assert pm.pi_ibr_summary([row(action="do_nothing", tp="H", cp="L")])["ibr_final_proposal_pi_count"] == 0


def test_pi_final_proposal_ignores_execution_and_r5():
    raw = row(action="do_nothing", tp="L", initial_skill="elevate_house",
              final_skill="elevate_house", attempt_skills="elevate_house",
              status="REJECTED", execution_path="default")
    assert pm.pi_ibr_summary([raw])["ibr_final_proposal_pi_count"] == 1
    raw["initial_labels"] = "TP_LABEL=M|CP_LABEL=M"
    assert pm.pi_ibr_summary([raw])["ibr_final_proposal_pi_count"] == 0


def test_pi_r44_fallback_convention_and_all_decisions_denominator():
    r1 = row(status="REJECTED_FALLBACK", initial_skill="do_nothing",
             final_skill="do_nothing", attempt_skills="do_nothing|",
             failed_rules="extreme_threat_block", retry_count="1")
    r4 = row(tp="L", status="REJECTED_FALLBACK", initial_skill="elevate_house",
             final_skill="do_nothing", attempt_skills="elevate_house|",
             failed_rules="elevation_threat_low", retry_count="1")
    aborted = row(status="ABORTED", initial_skill="", initial_labels="")
    result = pm.pi_ibr_summary([r1, r4, aborted])
    assert result["n_pi"] == 3
    assert result["ibr_final_proposal_pi_count"] == 1
    assert result["pi_fallback_excluded_count"] == result["pi_unresolved_count"] == 1
    r1["attempt_skills"] = "buy_insurance|"
    with pytest.raises(pm.MetricsError, match="R1-only"):
        pm.pi_ibr_summary([r1])


@pytest.mark.parametrize("actions,expected", [
    (pm.ACTIONS, 1.0),
    (["do_nothing"] * 4, 0.0),
    (["do_nothing", "relocate"], 0.5),
    (["do_nothing"] * 3 + ["relocate"], -(0.75 * math.log2(0.75) + 0.25 * math.log2(0.25)) / 2),
])
def test_four_action_entropy(actions, expected):
    result = pm.action_entropy(actions)
    assert result["ehe"] == pytest.approx(expected)
    assert sum(result[f"{action}_share"] for action in pm.ACTIONS) == pytest.approx(1)


def test_entropy_empty_and_invalid():
    assert all(value is None for value in pm.action_entropy([]).values())
    with pytest.raises(pm.MetricsError, match="action"):
        pm.action_entropy(["Already relocated"])


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fixture_run(path):
    path.mkdir()
    raw = [row(action="elevate_house", tp="M"),
           row(action="elevate_house", tp="L", year="2"),
           row(action="buy_insurance", year="3"),
           row(year="4", status="ABORTED", execution_path="aborted", executed_skill="",
               initial_skill="", initial_labels="", final_labels="", attempt_labels="", attempt_skills="")]
    write_csv(path / "household_governance_audit.csv", raw)
    trace_dir = path / "raw"
    trace_dir.mkdir()
    traces = [dict(_metadata={"audit_schema_version": "2"}, agent_type="household")]
    traces += [dict(agent_id="A", year=str(i + 1), state_before={"elevated": i > 0}) for i in range(3)]
    (trace_dir / "household_traces.jsonl").write_text("\n".join(json.dumps(t) for t in traces), encoding="utf-8")
    # POST-decision state cannot establish whether the first elevation was a repeat.
    write_csv(path / "simulation_log.csv", [dict(agent_id="A", year=1, elevated=True)])
    return path


def test_projection_reads_predecision_trace_and_yearly_shares(tmp_path):
    path = fixture_run(tmp_path / "run")
    before = {p: p.read_bytes() for p in path.rglob("*") if p.is_file()}
    result = pm.projection_run(path)
    assert result["n"] == 3 and result["n_aborted"] == 1
    assert result["R5_count"] == result["ibr_executed_count"] == 1
    assert result["ibr_final_proposal_pi_count"] == 1
    assert result["year_1_elevate_house_share"] == 1
    assert result["year_2_elevate_house_share"] == 1
    assert result["year_3_buy_insurance_share"] == 1
    assert result["year_4_n"] == 0 and result["year_4_do_nothing_share"] is None
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize("corruption,match", [
    ("missing_trace", "pre-decision"), ("duplicate_trace", "duplicate"),
    ("invalid_boolean", "boolean"), ("missing_audit_column", "missing"),
    ("duplicate_audit", "duplicate"), ("invalid_executed_action", "action"),
])
def test_projection_refuses_missing_or_corrupt_evidence(tmp_path, corruption, match):
    path = fixture_run(tmp_path / "run")
    traces = path / "raw/household_traces.jsonl"
    audit_csv = path / "household_governance_audit.csv"
    if corruption == "missing_trace":
        traces.unlink()
    elif corruption == "duplicate_trace":
        traces.write_text(traces.read_text() + "\n" + traces.read_text().splitlines()[1])
    elif corruption == "invalid_boolean":
        traces.write_text(traces.read_text().replace('"elevated": false', '"elevated": "maybe"'))
    else:
        rows = list(csv.DictReader(audit_csv.open(encoding="utf-8")))
        if corruption == "missing_audit_column":
            for r in rows:
                r.pop("executed_skill")
        elif corruption == "duplicate_audit":
            rows.append(rows[0])
        else:
            rows[0]["executed_skill"] = "Only House Elevation"
        write_csv(audit_csv, rows)
    with pytest.raises(pm.MetricsError, match=match):
        pm.projection_run(path)


def test_rulebased_state_only_logs_are_not_actions(tmp_path):
    path = tmp_path / "baseline"
    path.mkdir()
    write_csv(path / "simulation_log.csv", [dict(agent_id="A", year=1,
              decision="Only House Elevation", elevated=True)])
    result = pm.projection_run(path)
    assert result["kind"] == "rulebased"
    assert result["ibr_scope"] == "not applicable"
    assert result["ehe"] is result["physical_count"] is result["n"] is None
    assert "cumulative" in result["action_note"]


def test_cli_and_output_protection(tmp_path):
    path = fixture_run(tmp_path / "run")
    output = tmp_path / "measures.csv"
    assert pm.main(["projection", "--runs", str(path), "--out", str(output)]) == 0
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert len(rows) == 1 and rows[0]["n"] == "3"
    assert "year_2_elevate_house_share" in rows[0]
    with pytest.raises(pm.MetricsError, match="outside"):
        pm.main(["projection", "--runs", str(path), "--out", str(path / "analysis.csv")])
