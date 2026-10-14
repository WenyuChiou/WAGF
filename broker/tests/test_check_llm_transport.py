"""Content checks for the read-only transport report and CLI."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from broker.tools.check_llm_transport import main, transport_report


GIVE_UP = (
    "[LLM:Safeguard] transport failure persisted after 6 attempt(s); "
    "giving up -- the existing failure path continues.\n"
)


def call(step, *, transport=False, success=True, exception=None):
    # broker/utils/llm_journal.py (LLMJournalWriter.record_call).
    return {
        "type": "call", "step": step, "agent_type": "test",
        "raised": exception is not None, "exception_type": exception,
        "stats": {"success": success, "transport_error": transport},
    }


def journal(run, *records, name="llm_journal.jsonl"):
    run.mkdir(parents=True, exist_ok=True)
    path = run / name
    rows = [{"type": "header", "format_version": 1}, *records]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def end(step):
    return {"type": "step_end", "step": step}


def test_completed_failure_and_json_match_api(tmp_path, capsys):
    journal(tmp_path, call(22, transport=True, success=False), end(22))
    (tmp_path / "run_integrity.json").write_text('{"audit_aborted_rows": 5}', encoding="utf-8")
    report = transport_report(tmp_path)
    assert report["exit_code"] == 3
    assert report["steps"][0]["step"] == 22
    assert report["steps"][0]["has_step_end"] is True
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["audit_aborted_rows"] == 5
    assert main([str(tmp_path), "--json"]) == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["runs"] == [report]
    assert payload["summary"]["failures"] == 1


def test_failure_after_last_end_marker(tmp_path, capsys):
    journal(tmp_path, call(1), end(1), call(2, transport=True, success=False))
    report = transport_report(tmp_path)
    assert report["exit_code"] == 4
    assert [(s["step"], s["has_step_end"]) for s in report["steps"]] == [(1, True), (2, False)]
    assert main([str(tmp_path)]) == 4
    text = capsys.readouterr().out
    assert "exit_4_runs=1" in text
    assert "step=2 " in text
    assert "step=1 " not in text


def test_other_failure_is_not_transport(tmp_path, capsys):
    journal(tmp_path, call(7, success=False), call(7, success=False), end(7))
    report = transport_report(tmp_path)
    assert report["exit_code"] == 0
    assert report["totals"]["other_failed_calls"] == 2
    assert report["steps"][0]["transport_failed_calls"] == 0
    assert main([str(tmp_path)]) == 0
    text = capsys.readouterr().out
    warning = "WARNING: other_failed_calls=2"
    assert text.count(warning) == 1
    assert "step=7 " in text


@pytest.mark.parametrize("exception", [
    "LLMTransportStopped", "OSError", "ConnectionError", "ConnectionRefusedError",
    "ConnectionResetError", "BrokenPipeError", "PermissionError", "builtins.ConnectionAbortedError",
])
def test_transport_exception_family(tmp_path, exception):
    journal(tmp_path, call(3, exception=exception), end(3))
    report = transport_report(tmp_path)
    assert report["exit_code"] == 3
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["totals"]["other_failed_calls"] == 0


@pytest.mark.parametrize("exception", ["Timeout", "ConnectTimeout", "ReadTimeout", "timeout"])
def test_known_timeout_is_other(tmp_path, exception):
    journal(tmp_path, call(3, exception=exception), end(3))
    report = transport_report(tmp_path)
    assert report["exit_code"] == 0
    assert report["totals"]["transport_failed_calls"] == 0
    assert report["totals"]["other_failed_calls"] == 1
    assert report["totals"]["unclassified_failed_calls"] == 0
    assert report["totals"]["unclassified_exception_types"] == {}


def test_builtin_timeout_follows_safeguard_oserror_handler(tmp_path):
    # broker/utils/llm_safeguard.py (wrap_llm_invoke_with_backoff) catches
    # requests timeouts first; builtin TimeoutError reaches the OSError handler.
    journal(tmp_path, call(3, exception="builtins.TimeoutError"), end(3))
    report = transport_report(tmp_path)
    assert report["exit_code"] == 3
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["totals"]["other_failed_calls"] == 0


@pytest.mark.parametrize("exception", [
    "SSLError", "ProxyError", "ChunkedEncodingError", "urllib.error.URLError",
    "ProtocolError", "NewConnectionError", "NameResolutionError", "MaxRetryError",
    "ClosedPoolError", "http.client.RemoteDisconnected", "IncompleteRead", "BadStatusLine",
])
def test_connection_library_exception_names(tmp_path, exception):
    journal(tmp_path, call(3, exception=exception), end(3))
    report = transport_report(tmp_path)
    assert report["exit_code"] == 3
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["totals"]["other_failed_calls"] == 0
    assert report["totals"]["unclassified_failed_calls"] == 0


@pytest.mark.parametrize("completed", [True, False])
@pytest.mark.parametrize("exception", ["ValueError", "custom.ProviderFailure", None, ""])
def test_unknown_raised_exception_alarms_and_names_types(tmp_path, completed, exception):
    record = call(8, success=False, exception=exception)
    record["raised"] = True
    journal(tmp_path, record, *([end(8)] if completed else []))
    report = transport_report(tmp_path)
    assert report["exit_code"] == (3 if completed else 4)
    assert report["totals"]["calls"] == 1
    assert report["totals"]["transport_failed_calls"] == 0
    assert report["totals"]["other_failed_calls"] == 0
    assert report["totals"]["unclassified_failed_calls"] == 1
    assert report["totals"]["unclassified_exception_types"] == {exception or "<unknown>": 1}
    assert report["steps"][0]["unclassified_exception_types"] == report["totals"]["unclassified_exception_types"]
    assert report["steps"][0]["has_step_end"] is completed


def test_unclassified_type_counts_combine_across_steps(tmp_path):
    journal(tmp_path, call(1, exception="ValueError"), call(1, exception="ValueError"), end(1),
            call(2, exception="custom.ProviderFailure"), call(2, exception="ValueError"))
    report = transport_report(tmp_path)
    assert report["exit_code"] == 3
    assert report["totals"]["unclassified_failed_calls"] == 4
    assert report["totals"]["unclassified_exception_types"] == {"ValueError": 3, "custom.ProviderFailure": 1}
    assert report["steps"][0]["unclassified_exception_types"] == {"ValueError": 2}
    assert report["steps"][1]["unclassified_exception_types"] == {"ValueError": 1, "custom.ProviderFailure": 1}


def test_transport_flag_takes_precedence(tmp_path):
    journal(tmp_path, call(3, transport=True, exception="TimeoutError"), end(3))
    report = transport_report(tmp_path)
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["totals"]["other_failed_calls"] == 0


def test_log_only_assigns_nearest_marker_and_ignores_retries(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(
        "--- Year 21 ---\n[LLM:Safeguard] transport failure (attempt 1/6); retrying in 2s.\n"
        "--- Year 22 ---\n" + GIVE_UP + "--- Step 23 ---\n" + GIVE_UP,
        encoding="utf-8",
    )
    report = transport_report(tmp_path, logs=[log])
    assert report["exit_code"] == 4
    assert report["totals"]["transport_failed_calls"] == 2
    assert [(s["step"], s["transport_failed_calls"]) for s in report["steps"]] == [(21, 0), (22, 1), (23, 1)]
    assert report["sources"]["journal"] is None
    assert "journal absent, result from log only" in report["warnings"]
    assert "giving up" in report["log_patterns"]["give_up"]


def test_followup_notices_do_not_duplicate_calls(tmp_path):
    journal(tmp_path, call(22, transport=True, success=False), end(22))
    log = tmp_path / "run.log"
    log.write_text("--- Year 22 ---\n" + GIVE_UP +
                   " [LLM:Error] Transport failure persisted through backoff for test; not re-prompting the same endpoint.\n",
                   encoding="utf-8")
    report = transport_report(tmp_path, logs=[log])
    assert report["exit_code"] == 3
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["totals"]["log_transport_failures"] == 1
    assert report["log_notices"]["transport"] == 1
    assert report["log_failures_by_step"][0]["step"] == 22


def test_log_notice_fallback_and_other_errors(tmp_path):
    log = tmp_path / "run.log"
    log.write_text("--- Year 4 ---\n[LLM:Error] Transport failure persisted through backoff for test\n"
                   "[Reflection:Error] invalid response\n[Reflection:Batch:Error] invalid response\n", encoding="utf-8")
    report = transport_report(tmp_path, logs=[log])
    assert report["exit_code"] == 4
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["totals"]["other_failed_calls"] == 2
    assert report["log_failures_by_step"][0]["count_pattern"] == "transport_notice"


def test_log_failure_without_marker_stays_unassigned(tmp_path):
    log = tmp_path / "run.log"
    log.write_text(GIVE_UP, encoding="utf-8")
    report = transport_report(tmp_path, logs=[log])
    assert report["steps"][0]["step"] is None
    assert report["steps"][0]["has_step_end"] is False
    assert report["totals"]["transport_failed_calls"] == 1
    assert report["exit_code"] == 4


def test_no_sources_summary(tmp_path, capsys):
    report = transport_report(tmp_path)
    assert report["exit_code"] == 2
    assert report["sources"]["journal"] is None
    assert report["steps"] == []
    assert report["audit_aborted_rows"] is None
    assert main([str(tmp_path)]) == 2
    assert "exit_2_runs=1" in capsys.readouterr().out


def test_header_without_calls_is_not_clean(tmp_path, capsys):
    journal(tmp_path)
    report = transport_report(tmp_path)
    assert report["exit_code"] == 2
    assert report["sources"]["journal"] == str(tmp_path / "llm_journal.jsonl")
    assert report["totals"]["calls"] == 0
    assert report["steps"] == []
    assert main([str(tmp_path)]) == 2
    assert "journal has no calls" in capsys.readouterr().out


def test_truncated_last_line_is_reported(tmp_path):
    path = journal(tmp_path, call(1), end(1))
    with path.open("ab") as output:
        output.write(b'{"type":"call","step":2')
    report = transport_report(tmp_path)
    assert report["exit_code"] == 0
    assert report["totals"]["calls"] == 1
    assert any("line 4" in warning for warning in report["warnings"])


def test_broken_middle_line_is_error_with_number(tmp_path, capsys):
    path = journal(tmp_path, call(1), end(1))
    path.write_text(path.read_text(encoding="utf-8").replace('"type": "call"', '"type": invalid'), encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        transport_report(tmp_path)
    assert main([str(tmp_path), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert "line 2" in payload["runs"][0]["error"]


def test_journal_override(tmp_path):
    journal(tmp_path, call(1), end(1))
    alternate = journal(tmp_path, call(22, transport=True, success=False), end(22), name="full.jsonl")
    assert transport_report(tmp_path)["totals"]["transport_failed_calls"] == 0
    report = transport_report(tmp_path, journal=alternate)
    assert report["sources"]["journal"] == str(alternate)
    assert report["exit_code"] == 3


@pytest.mark.parametrize("codes, expected", [((3, 4), 3), ((3, 2), 3), ((4, 2), 2), ((1, 4), 1), ((0, 4), 4), ((1, 3), 3)])
def test_multiple_runs_use_failure_priority_and_count_codes(tmp_path, capsys, codes, expected):
    runs = [tmp_path / str(index) for index in range(2)]
    for run, code in zip(runs, codes):
        if code == 2:
            run.mkdir()
        elif code == 1:
            path = journal(run, call(1), end(1))
            path.write_text('bad middle line\n' + path.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            journal(run, call(1, transport=code in (3, 4)), *([end(1)] if code != 4 else []))
    args = [str(run) for run in runs]
    assert main([*args, "--json"]) == expected
    payload = json.loads(capsys.readouterr().out)
    assert [run["exit_code"] for run in payload["runs"]] == list(codes)
    assert payload["summary"]["exit_code_counts"] == {str(code): codes.count(code) for code in range(5)}
    assert main(args) == expected
    text = capsys.readouterr().out
    for code in range(5):
        assert f"exit_{code}_runs={codes.count(code)}" in text


@pytest.mark.parametrize("all_steps", [False, True])
def test_text_step_filter_and_json_always_keep_all_steps(tmp_path, capsys, all_steps):
    journal(tmp_path, call(1), end(1), call(2, exception="ProviderFailure"), end(2),
            call(3, success=False), end(3), call(4, transport=True), end(4), call(5))
    args = [str(tmp_path), *(["--all-steps"] if all_steps else [])]
    assert main(args) == 3
    text = capsys.readouterr().out
    assert ("step=1 " in text) is all_steps
    for step in (2, 3, 4, 5):
        assert f"step={step} " in text
    assert "unclassified_exception_types={\"ProviderFailure\": 1}" in text
    assert main([*args, "--json"]) == 3
    report = json.loads(capsys.readouterr().out)["runs"][0]
    assert [row["step"] for row in report["steps"]] == [1, 2, 3, 4, 5]
    assert report == transport_report(tmp_path)


def test_module_docstring_states_blind_spot_and_log_overlap():
    import broker.tools.check_llm_transport as tool
    assert "failure recorded only in that broken line cannot be seen" in tool.__doc__
    assert "overlapping logs can count one event twice" in tool.__doc__


def test_multiple_logs_and_repeated_option(tmp_path, capsys):
    logs = [tmp_path / f"log{n}.txt" for n in (1, 2)]
    for n, log in enumerate(logs, 1):
        log.write_text(f"--- Step {n} ---\n" + GIVE_UP, encoding="utf-8")
    assert main([str(tmp_path), "--log", str(logs[0]), "--log", str(logs[1]), "--json"]) == 4
    report = json.loads(capsys.readouterr().out)["runs"][0]
    assert report["sources"]["logs"] == [str(log) for log in logs]
    assert report["totals"]["log_transport_failures"] == 2


def test_report_never_changes_run_files(tmp_path):
    journal(tmp_path, call(22, transport=True), end(22))
    (tmp_path / "run_integrity.json").write_text('{"audit_aborted_rows": 0}', encoding="utf-8")
    (tmp_path / "reproducibility_manifest.json").write_text('{"run_status":"done","resumed_from":"source"}', encoding="utf-8")
    def hashes():
        return {str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in tmp_path.rglob("*") if p.is_file()}
    before = hashes()
    report = transport_report(tmp_path)
    assert report["manifest"]["run_status"] == "done"
    assert report["totals"]["transport_failed_calls"] == 1
    assert hashes() == before


@pytest.mark.parametrize("argv", [[], ["--unknown"], ["run", "--journal"]])
def test_usage_error_is_one(argv, capsys):
    assert main(argv) == 1
    assert "ERROR:" in capsys.readouterr().err


@pytest.mark.parametrize("record", [[], {"type":"call","step":"22"}, {"type":"call","step":1,"stats":[]}])
def test_malformed_records_are_not_silently_ignored(tmp_path, record):
    journal(tmp_path, record)
    with pytest.raises(ValueError, match="line 2"):
        transport_report(tmp_path)


def test_log_transport_evidence_still_flags_healthy_journal(tmp_path):
    journal(tmp_path, call(3), end(3))
    log = tmp_path / "run.log"
    log.write_text("--- Step 3 ---\n" + GIVE_UP, encoding="utf-8")
    report = transport_report(tmp_path, logs=[log])
    assert report["totals"]["transport_failed_calls"] == 0
    assert report["totals"]["log_transport_failures"] == 1
    assert report["exit_code"] == 3


def test_later_giveup_does_not_hide_completed_step_notice(tmp_path):
    journal(tmp_path, call(1), end(1), call(2))
    log = tmp_path / "run.log"
    log.write_text(
        "--- Year 1 ---\n[LLM:Error] Transport failure persisted through backoff for test\n"
        "--- Year 2 ---\n" + GIVE_UP,
        encoding="utf-8",
    )
    report = transport_report(tmp_path, logs=[log])
    assert report["exit_code"] == 3
    assert report["steps"][0]["has_step_end"] is True
    assert report["steps"][0]["log_transport_failures"] == 1
    assert report["steps"][1]["has_step_end"] is False
    assert report["steps"][1]["log_transport_failures"] == 1
    assert report["totals"]["log_transport_failures"] == 2
    assert [item["count_pattern"] for item in report["log_failures_by_step"]] == ["transport_notice", "give_up"]
