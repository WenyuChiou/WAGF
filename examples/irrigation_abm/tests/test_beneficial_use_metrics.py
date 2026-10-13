"""Focused item-49 reporting, P5(b), and reflection-input tests."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.irrigation_abm.analysis import v3_metrics as vm


def _decision(skill: str = vm.INCREASE) -> vm.Decision:
    attempt = vm.Attempt(skill, {}, ())
    return vm.Decision(
        agent_id="A", year=1, status="ACCEPTED", execution_path="accepted",
        executed_skill=skill, proposed_skill=skill, attempts=(attempt,), retry_count=0,
        format_retries=0, llm_success=True, keep_request_af=90.0,
        expected_at_keep_af=90.0, supply_ratio=1.0, physical_ratio=1.0,
        first_wsa="L", first_aca="L", final_wsa="L", wsa_relabeled=False,
        error_messages="", timestamp="",
    )


def _manifest() -> dict:
    return {
        "beneficial_use_limit": {
            "spec_item": 49, "enabled": True, "beneficial_use_margin": 0.0,
        }
    }


@pytest.mark.parametrize("cut", [9., .1])
def test_beneficial_use_metrics_reports_exposure_attempts_and_clamp(cut) -> None:
    row = {
        "base_af": "99", "water_right": "140", "beneficial_use_limit_af": "100",
        "at_beneficial_use_limit": "True", "beneficial_use_clamp_cut_af": str(cut),
        "beneficial_use_clamped": "True",
    }
    run = SimpleNamespace(
        info=SimpleNamespace(manifest=_manifest()), label="strict_seed42",
        sim=SimpleNamespace(path=Path("simulation_log.csv"), rows={("A", 1): row}),
        decisions={("A", 1): _decision()},
    )

    result = vm.beneficial_use_metrics(run)

    assert result["beneficial_use_at_limit_agent_years"] == 1
    assert result["beneficial_use_off_menu_increase_attempts"] == 1
    assert result["beneficial_use_clamped_increases"] == 1
    assert result["beneficial_use_clamp_removed_af"] == pytest.approx(cut)
    assert result["beneficial_use_executed_increase_at_limit_pct"] == 100.0


def _prompt_checker(base: float, menu: tuple[str, ...]) -> tuple[vm.PromptChecker, tuple[str, int]]:
    key = ("A", 1)
    row = {
        "beneficial_use_limit_af": "100", "typical_step_af": "20", "memory": "",
    }

    def num(agent: str, year: int, column: str) -> float:
        values = {"water_right": 140.0, "typical_step_af": 20.0}
        return values[column]

    def opt_num(agent: str, year: int, column: str):
        value = row.get(column)
        return None if value is None or value == "" else float(value)

    sim = SimpleNamespace(
        rows={key: row}, basin={"A": "upper_basin"}, subbasin={"A": None},
        system={1: {}}, num=num, opt_num=opt_num, sim_year=lambda year: 2018 + year,
    )
    trace = vm.TraceRecord(
        "A", 1, False, False, base, 140.0, menu,
        at_beneficial_use_limit=base >= 99.0,
    )
    run = SimpleNamespace(
        label="strict_seed42", info=SimpleNamespace(manifest=_manifest()), sim=sim,
        decisions={key: SimpleNamespace(keep_request_af=base)}, traces={key: trace},
    )
    checker = object.__new__(vm.PromptChecker)
    checker.run = run
    checker.cfg = SimpleNamespace(min_utilisation_fraction=0.1)
    checker.variant = "mean"
    checker.fragments = []
    checker.priority = {}
    checker.package = {}
    checker.beneficial_use = vm.beneficial_use_config(run.info.manifest)
    checker._contexts = {}
    checker.profiles = {"A": SimpleNamespace(peak_obs_af=100.0)}
    return checker, key


def test_p5b_accepts_exact_beneficial_use_clause_and_catches_tampering() -> None:
    checker, key = _prompt_checker(90.0, ("increase", "keep", "decrease"))
    good_text = (
        "1. Increase your request to about 100 acre-ft: the 90 acre-ft you received last year "
        "plus your typical step of about 20 acre-ft (it stops at 100 acre-ft, about the most "
        "water your fields can use)."
    )
    good = vm.PromptAudit()
    checker.audit(key, good_text, good)
    assert good.mismatches == []

    bad = vm.PromptAudit()
    checker.audit(key, good_text.replace("stops at 100", "stops at 101"), bad)
    assert any("beneficial-use option clause" in message for message in bad.mismatches)


def test_p5b_rejects_increase_offered_at_effective_cap() -> None:
    checker, key = _prompt_checker(99.0, ("increase", "keep", "decrease"))
    prompt = (
        "1. Increase your request to about 100 acre-ft: the 99 acre-ft you received last year "
        "plus your typical step of about 20 acre-ft (it stops at 100 acre-ft, about the most "
        "water your fields can use)."
    )
    audit = vm.PromptAudit()
    checker.audit(key, prompt, audit)
    assert any("increase menu presence present, expected absent" in message
               for message in audit.mismatches)


def _reflection_run(path: Path, agent_ids: tuple[str, ...] = ("A",)) -> SimpleNamespace:
    prompt = (
        "Your memory includes:\n"
        "- Consolidated Reflection (written in 2019): learned from 123 acre-ft\n"
    )
    sim = SimpleNamespace(sim_start_year=2019, sim_year=lambda year: 2018 + year)
    return SimpleNamespace(
        label="strict_seed42", info=SimpleNamespace(path=path, manifest={}),
        traces={
            (agent_id, 2): vm.TraceRecord(
                agent_id, 2, False, False, 100.0, 140.0,
                ("increase", "keep", "decrease"), prompt,
                at_beneficial_use_limit=False,
            )
            for agent_id in agent_ids
        },
        sim=sim,
    )


@pytest.mark.parametrize("period_field,period", [("period", 2019), ("year_created", 1)])
def test_p6_prefers_reflection_input_and_explicitly_skips_legacy(
    tmp_path: Path, period_field: str, period: int,
) -> None:
    current = tmp_path / "current"
    current.mkdir()
    (current / "reflection_log.jsonl").write_text(json.dumps({
        "agent_id": "A", period_field: period, "reflection_input": "memory contains 123 acre-ft",
    }) + "\n", encoding="utf-8")
    checked = vm.reflection_checks(_reflection_run(current))
    assert checked["reflection_inputs_read"] == 1
    assert checked["reflection_input_check_skipped"] == 0
    assert checked["foreign_figure_reflections"] == 0

    legacy = tmp_path / "legacy"
    legacy.mkdir()
    skipped = vm.reflection_checks(_reflection_run(legacy))
    assert skipped["reflection_inputs_read"] == 0
    assert skipped["reflection_input_check_skipped"] == 1
    assert skipped["reflection_input_skip_reason"] == (
        "legacy reflection record has no reflection_input")


@pytest.mark.parametrize("logged", [True, False], ids=["all", "legacy-none"])
def test_p6_gate_accepts_complete_or_legacy_reflection_input_logging(
    tmp_path: Path, logged: bool,
) -> None:
    if logged:
        (tmp_path / "reflection_log.jsonl").write_text(json.dumps({
            "agent_id": "A", "period": 2019,
            "reflection_input": "memory contains 123 acre-ft",
        }) + "\n", encoding="utf-8")

    check = vm.gate_p6([_reflection_run(tmp_path)])

    assert check["passed"] is True
    assert "reflection_input_check_skipped" in check["reason"]


def test_p6_gate_rejects_partial_reflection_input_logging(tmp_path: Path) -> None:
    (tmp_path / "reflection_log.jsonl").write_text(json.dumps({
        "agent_id": "A", "period": 2019,
        "reflection_input": "memory contains 123 acre-ft",
    }) + "\n", encoding="utf-8")

    check = vm.gate_p6([_reflection_run(tmp_path, ("A", "B"))])

    assert check["passed"] is False
    assert "reflection_input_check_skipped = 1 of 2 reflection lines" in check["reason"]
