"""Read-back checks for the simple irrigation prompt information level."""

from __future__ import annotations

import json

import pytest

from examples.irrigation_abm.analysis.simple_prompt_check import (
    REMOVED_SENTENCE_FAMILIES,
    check_run,
    main,
    scan_text,
)


FAMILY_EXAMPLES = {
    "k6_senior_tier_text": (
        "A shortage tier is set from Lake Mead's level on 1 January, before anyone's "
        "request for the year is known."
    ),
    "supply_headline": "Water supply is short of your request this year.",
    "keep_request_expectation": (
        "If you request the 12,000 acre-ft you received last year, you can expect "
        "full delivery this year."
    ),
    "increase_request_expectation": (
        "If you increase your request to about 13,000 acre-ft, you can expect full "
        "delivery this year."
    ),
    "lower_basin_tier_details": (
        "This tier limits your junior-priority water this year to about 7,500 acre-ft."
    ),
    "shortfall_reason": (
        "Shortfall: 2,000 acre-ft (20.0% unmet), because Lake Mead could not supply it."
    ),
    "upper_basin_natural_flow": (
        "The natural flow of the rivers your sub-basin draws on is 70% of its "
        "1971-2018 average this year."
    ),
    "water_right_delivery_share": (
        "Your water right is 20,000 acre-ft/year; last year's delivery was 50% of it."
    ),
    "land_need": (
        "Your fields can use about 14,000 acre-ft of water a year: that is the most "
        "water you have diverted in any year."
    ),
    "field_use_clause": (
        "The more water you receive, up to what your fields can use, the more you can produce."
    ),
    "feedback_dashboard": "## PERFORMANCE HISTORY\nYear | request (AF) | received (AF)",
    "appraisal_guidance": "First, assess your WATER SUPPLY situation by considering:",
    "keep_asks_received_note": (
        "If you received less than you requested last year, keeping your request asks "
        "only for the amount you received."
    ),
    "floor_no_decrease_note": (
        "A decrease is not offered because your request is at or below the minimum-use "
        "floor of 4,000 acre-ft (10% of your water right)."
    ),
    "allocation_rules": "Rules that apply to Agent_000:",
    "sharing_sentence": (
        "When water is short it is shared in proportion to requests, so a larger "
        "request would raise your share only by lowering other deliveries."
    ),
}


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )


def test_examples_cover_every_exported_removed_family():
    assert set(FAMILY_EXAMPLES) == set(REMOVED_SENTENCE_FAMILIES)
    for family, text in FAMILY_EXAMPLES.items():
        assert family in scan_text(text), family


def test_dashboard_warning_without_table_is_detected():
    warning = (
        "WARNING: You requested 10,000 AF and received 8,000 AF (20.0% unmet). "
        "The reason is stated in your water situation above."
    )
    assert "feedback_dashboard" in scan_text(warning)


def test_single_user_sharing_rule_is_detected():
    assert "sharing_sentence" in scan_text(
        "When water is short, a larger request would not add water."
    )


@pytest.mark.parametrize(
    "retained",
    [
        "Increase your request to 10,000 acre-ft (the water right stops it at 10,000 acre-ft).",
        "Decrease your request to 4,000 acre-ft (the minimum-use floor stops it at 4,000 acre-ft).",
        "The more water you receive, the more you can produce.",
        "You are a senior-priority irrigator in the Lower Basin with a 20,000 acre-ft water right.",
        "Year 2029: maintain demand was applied under the water-right cap.",
        "A Tier 2 Lower Basin shortage applies this year (Lake Mead was below 1,050 feet on 1 January).",
        "Shortfall: 2,000 acre-ft (20.0% unmet).",
        "First, rate your water_scarcity_assessment: is your water supply abundant (VL), adequate (L), tight (M), scarce (H), or very scarce (VH) this year?",
    ],
)
def test_retained_simple_text_is_not_classified(retained):
    assert scan_text(retained) == ()


def test_check_run_scans_actual_sources_and_separates_retry_and_lesson(tmp_path):
    run = tmp_path / "sample-run"
    clean_prompt = (
        "A retained first-attempt prompt.\n"
        "- Consolidated Reflection (written in 2028): Program facts. Lesson: "
        + FAMILY_EXAMPLES["field_use_clause"] + "\n"
        + FAMILY_EXAMPLES["supply_headline"]
    )
    _write_jsonl(
        run / "raw" / "irrigation_farmer_traces.jsonl",
        [
            {"_metadata": {"audit_schema_version": "2"}, "agent_type": "irrigation_farmer"},
            {
                "run_id": "recorded-run",
                "agent_id": "Farmer_A",
                "year": 2029,
                "input": clean_prompt,
                "memory_pre": [
                    {"content": FAMILY_EXAMPLES["shortfall_reason"]},
                    {"content": "Program facts. Lesson: " + FAMILY_EXAMPLES["field_use_clause"]},
                ],
                "retry_prompts": [FAMILY_EXAMPLES["sharing_sentence"] + "\n\n" + clean_prompt],
            },
        ],
    )
    _write_jsonl(
        run / "reflection_checks.jsonl",
        [
            {
                "agent_id": "Farmer_B",
                "period": 2030,
                "reflection_input": [{
                    "content": "Program facts. Lesson: "
                    + FAMILY_EXAMPLES["field_use_clause"] + "\n"
                    + FAMILY_EXAMPLES["allocation_rules"]
                }],
            }
        ],
    )
    _write_jsonl(run / "reflection_log.jsonl", [{
        "agent_id": "Farmer_C", "year_created": 12,
        "reflection_input": [FAMILY_EXAMPLES["land_need"]],
        "summary": FAMILY_EXAMPLES["field_use_clause"],
    }])
    reflection_prompt = (
        "Program facts. Lesson: " + FAMILY_EXAMPLES["field_use_clause"] + "\n"
        + FAMILY_EXAMPLES["upper_basin_natural_flow"]
    )
    _write_jsonl(run / "reflection_prompts.jsonl", [
        {"agent_id": "Farmer_B", "year": 2030, "attempt": 0, "prompt": reflection_prompt},
        {"agent_id": "Farmer_B", "year": 2030, "attempt": 1,
         "prompt": reflection_prompt + "\n" + FAMILY_EXAMPLES["sharing_sentence"]},
    ])
    (run / "irrigation_farmer_governance_audit.csv").write_text(
        'agent_id,year,error_messages\nFarmer_A,2029,"'
        + FAMILY_EXAMPLES["keep_request_expectation"].replace("12,000", "12000")
        + '"\n',
        encoding="utf-8",
    )

    result = check_run(run)

    assert result.complete
    assert result.readable_prompts == 8
    assert {(hit.agent, hit.year, hit.family) for hit in result.occurrences} == {
        ("Farmer_A", 2029, "supply_headline"),
        ("Farmer_A", 2029, "shortfall_reason"),
        ("Farmer_B", 2030, "allocation_rules"),
        ("Farmer_B", 2030, "upper_basin_natural_flow"),
        ("Farmer_B", 2030, "sharing_sentence"),
        ("Farmer_C", 12, "land_need"),
    }
    assert {hit.family for hit in result.retry_feedback_occurrences} == {
        "sharing_sentence", "keep_request_expectation",
    }
    assert {hit.family for hit in result.lesson_occurrences} == {"field_use_clause"}


def test_check_run_reports_repeated_family_occurrences(tmp_path):
    run = tmp_path / "repeated"
    sentence = FAMILY_EXAMPLES["supply_headline"]
    _write_jsonl(
        run / "raw" / "irrigation_farmer_traces.jsonl",
        [{"agent_id": "A", "year": 1, "input": sentence + "\n" + sentence}],
    )

    result = check_run(run)

    assert [hit.family for hit in result.occurrences] == [
        "supply_headline", "supply_headline"
    ]


def test_retry_without_exact_input_suffix_fails_closed(tmp_path):
    run = tmp_path / "mismatch"
    _write_jsonl(run / "raw" / "irrigation_farmer_traces.jsonl", [{
        "agent_id": "A", "year": 1, "input": "Original prompt.",
        "retry_prompts": ["Feedback plus a different prompt."],
    }])

    result = check_run(run)

    assert result.retry_suffix_mismatches == 1
    assert main([str(run)]) == 1


def test_cli_exit_codes_for_clean_contaminated_and_empty_runs(tmp_path, capsys):
    clean = tmp_path / "clean"
    _write_jsonl(
        clean / "raw" / "irrigation_farmer_traces.jsonl",
        [{"agent_id": "A", "year": 1, "input": "A retained prompt."}],
    )
    contaminated = tmp_path / "contaminated"
    _write_jsonl(
        contaminated / "raw" / "irrigation_farmer_traces.jsonl",
        [{"agent_id": "B", "year": 2, "input": FAMILY_EXAMPLES["land_need"]}],
    )
    empty = tmp_path / "empty"
    empty.mkdir()

    assert main([str(clean)]) == 0
    assert main([str(contaminated)]) == 1
    assert "contaminated\tB\t2\tland_need" in capsys.readouterr().out
    assert main([str(empty)]) == 2


@pytest.mark.parametrize(
    "condition",
    [
        "missing_raw", "missing_reflection_prompts", "recorder_flag", "malformed",
        "malformed_reflection_log",
    ],
)
def test_incomplete_evidence_exits_two(tmp_path, condition):
    run = tmp_path / condition
    _write_jsonl(run / "raw" / "irrigation_farmer_traces.jsonl", [
        {"agent_id": "A", "year": 1, "input": "Clean prompt."}
    ])
    if condition == "missing_raw":
        (run / "raw" / "irrigation_farmer_traces.jsonl").write_text(
            '{"_metadata": {}}\n', encoding="utf-8")
    elif condition == "missing_reflection_prompts":
        _write_jsonl(run / "reflection_checks.jsonl", [
            {"agent_id": "A", "period": 1, "reflection_input": ["Clean memory."]}
        ])
    elif condition == "recorder_flag":
        (run / "reproducibility_manifest.json").write_text(
            json.dumps({"reflection_prompt_log_complete": False}), encoding="utf-8")
    elif condition == "malformed":
        with (run / "raw" / "irrigation_farmer_traces.jsonl").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write("{truncated\n")
    else:
        (run / "reflection_log.jsonl").write_text("{truncated\n", encoding="utf-8")
        _write_jsonl(run / "reflection_prompts.jsonl", [
            {"agent_id": "A", "year": 1, "attempt": 0, "prompt": "Clean prompt."}
        ])

    assert not check_run(run).complete
    assert main([str(run)]) == 2


def test_malformed_or_non_prompt_records_do_not_count_as_readable(tmp_path):
    run = tmp_path / "unreadable"
    path = run / "raw" / "irrigation_farmer_traces.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text('{bad json}\n{"agent_id": "A", "input": null}\n', encoding="utf-8")

    result = check_run(run)

    assert result.readable_prompts == 0
    assert result.occurrences == ()
    assert result.malformed_records == 1
    assert not result.complete


def test_invalid_utf8_prompt_file_is_unreadable(tmp_path):
    run = tmp_path / "invalid-utf8"
    path = run / "raw" / "irrigation_farmer_traces.jsonl"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe\x00")

    result = check_run(run)

    assert result.readable_prompts == 0
    assert result.occurrences == ()
    assert result.malformed_records == 1


def test_strict_simple_always_increase_run_separates_supply_rule_feedback(
    tmp_path, monkeypatch
):
    from pathlib import Path

    from examples.irrigation_abm import run_experiment
    from examples.irrigation_abm.tests.test_v3_prompt import ScriptedLLM, _run

    variant = Path(run_experiment.__file__).parent / "config_variants" / "simple"
    llm = ScriptedLLM(lambda agent, year, attempt: ("M", "M", "Increase"))
    out = _run(
        monkeypatch, tmp_path / "run", llm, "--real", "--years", "6",
        "--seed", "42", "--memory-seed", "42", "--governance-mode", "strict",
        "--config-dir", str(variant),
    )

    result = check_run(out)

    assert result.complete
    assert result.occurrences == ()
    assert result.retry_suffix_mismatches == 0
    assert len(result.retry_feedback_occurrences) > 0
    assert main([str(out)]) == 0
