"""Round-2 P5(b) numeric read-back for full and simple prompt levels."""
from __future__ import annotations

import dataclasses
import csv
import json
import re

import pytest

from examples.irrigation_abm.analysis import v3_metrics as vm
from examples.irrigation_abm.tests.test_v3_prompt import CONFIG, ScriptedLLM, _run


VARIANTS = CONFIG.parent.parent / "config_variants"


def _audit(run: vm.LoadedRun) -> vm.PromptAudit:
    config = vm.analysis_config()
    audit = vm.PromptAudit()
    checker = vm.PromptChecker(run, config, config.ub_subbasin_supply_variant)
    for key in sorted(run.traces, key=lambda item: (item[1], item[0])):
        trace = run.traces[key]
        if not trace.crashed:
            checker.audit(key, trace.prompt or "", audit)
    checker.audit_persisted_sources(audit)
    return audit


def _p5b(run: vm.LoadedRun):
    config = vm.analysis_config()
    return vm.gate_p5([run], config, None, config.ub_subbasin_supply_variant)["details"]


@pytest.fixture(params=("full", "simple"))
def numeric_run(request, tmp_path, monkeypatch):
    level = request.param
    llm = ScriptedLLM(lambda *_args: ("M", "M", "Increase"))
    args = ["--years", "4", "--agents", "4", "--seed", "42", "--memory-seed", "42"]
    if level == "simple":
        args += ["--config-dir", str(VARIANTS / "simple")]
    out = _run(monkeypatch, tmp_path / level, llm, *args)
    run = vm.load_run(out, keep_prompts=True)
    assert run.info.manifest["prompt_information"] == level
    return run


def _tamper_first(run: vm.LoadedRun, pattern: str, replacement) -> None:
    regex = re.compile(pattern, re.M)
    for key, trace in sorted(run.traces.items(), key=lambda item: (item[0][1], item[0][0])):
        prompt = trace.prompt or ""
        changed, count = regex.subn(replacement, prompt, count=1)
        if count:
            run.traces[key] = dataclasses.replace(trace, prompt=changed)
            return
    raise AssertionError(f"mock run had no prompt text matching {pattern!r}")


def _increment(match: re.Match[str]) -> str:
    value = int(match.group("value").replace(",", "")) + 1
    return match.group(0).replace(match.group("value"), f"{value:,}")


def test_p5b_accepts_clean_program_numbers_at_both_levels(numeric_run):
    """Decision text, outcome memories, signals and grounded facts read back."""
    audit = _audit(numeric_run)
    assert audit.mismatches == []
    assert audit.unchecked == []
    assert audit.numeric_lines > 0
    assert audit.grounded_reflection_lines > 0
    details = _p5b(numeric_run)
    assert details["b_passed"] is True
    assert details["b_stored_memory_lines_checked"] > 0
    assert details["b_reflection_prompt_fact_lines_checked"] > 0


def test_p5b_rejects_tampered_outcome_memory_at_both_levels(numeric_run):
    _tamper_first(
        numeric_run,
        r"^- Year \d{4}: .*?You requested (?P<value>[\d,]+) acre-ft and received",
        _increment,
    )
    audit = _audit(numeric_run)
    assert any("memory line" in mismatch and "request" in mismatch for mismatch in audit.mismatches)


def test_p5b_rejects_tampered_grounded_reflection_fact_at_both_levels(numeric_run):
    _tamper_first(
        numeric_run,
        r"^- Consolidated Reflection .*?you asked for (?P<value>[\d,]+) acre-ft.*? Lesson: ",
        _increment,
    )
    audit = _audit(numeric_run)
    assert any("reflection fact request" in mismatch for mismatch in audit.mismatches)


def test_p5b_rejects_malformed_grounded_reflection_number_at_both_levels(numeric_run):
    _tamper_first(
        numeric_run,
        r"(^- Consolidated Reflection .*?you asked for )(?P<value>[\d,]+)( acre-ft.*? Lesson: )",
        lambda match: match.group(1) + match.group("value") + "x" + match.group(3),
    )
    audit = _audit(numeric_run)
    assert any("Consolidated Reflection" in line for line in audit.unchecked)


def test_tier_pattern_accepts_full_and_simple_endings():
    prefix = "A Tier 1 Lower Basin shortage applies this year (Lake Mead was below 1,075 feet on 1 January)"
    assert vm._R["tier"].match(prefix + ".").group("ending") == "."
    assert vm._R["tier"].match(prefix + ": the tier reduces deliveries.").group("ending") == ": "


def test_p5b_real_simple_run_does_not_require_removed_flow_text(tmp_path, monkeypatch):
    llm = ScriptedLLM(lambda *_args: ('M', 'M', 'Keep'))
    out = _run(monkeypatch, tmp_path / 'real-simple', llm,
               '--real', '--years', '4', '--seed', '42', '--memory-seed', '42',
               '--config-dir', str(VARIANTS / 'simple'))
    details = _p5b(vm.load_run(out, keep_prompts=True))
    assert details['b_passed'] is True, details['b_mismatches'] + details['b_unchecked']


def test_p5b_rejects_number_tampered_only_in_simulation_memory(numeric_run):
    path = numeric_run.info.path / vm.SIM_LOG
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames
        rows = list(reader)
    assert fieldnames is not None
    changed = False
    for row in rows:
        memory, count = re.subn(
            r"(Year \d{4}: .*?You requested )(?P<value>[\d,]+)( acre-ft and received)",
            lambda match: match.group(1) + f"{int(match.group('value').replace(',', '')) + 1:,}" + match.group(3),
            row.get("memory", ""), count=1)
        if count:
            row["memory"] = memory
            changed = True
            break
    assert changed
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    run = vm.load_run(numeric_run.info.path, keep_prompts=True)
    details = _p5b(run)
    assert details["b_passed"] is False
    assert any("simulation_log.csv" in mismatch and "memory line" in mismatch
               for mismatch in details["b_mismatches"])


def test_p5b_rejects_final_stored_reflection_fact_tamper_outside_decision_prompt(numeric_run):
    path = numeric_run.info.path / "reflection_prompts.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    final_year = max(int(row["year"]) for row in rows)
    changed = False
    for row in rows:
        if int(row["year"]) != final_year or int(row.get("attempt", 0)) != 0:
            continue
        prompt, count = re.subn(
            r"(?P<prefix>\d{4}: you asked for )(?P<value>[\d,]+)(?P<suffix> acre-ft)",
            lambda match: (match.group("prefix")
                           + f"{int(match.group('value').replace(',', '')) + 1:,}"
                           + match.group("suffix")),
            row["prompt"], count=1)
        if count:
            row["prompt"] = prompt
            changed = True
            break
    assert changed
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    details = _p5b(vm.load_run(numeric_run.info.path, keep_prompts=True))
    assert details["b_passed"] is False
    assert any("reflection_prompts.jsonl" in mismatch and "reflection fact request" in mismatch
               for mismatch in details["b_mismatches"])


def test_p5b_excludes_model_lesson_digits_in_csv_memory(numeric_run):
    for row in numeric_run.sim.rows.values():
        if ' Lesson: ' in row.get('memory', ''):
            row['memory'] = row['memory'].split(' Lesson: ', 1)[0] + ' Lesson: I learned 987654321 things.'
            break
    else:
        pytest.fail('fixture has no stored reflection in memory')
    assert _p5b(numeric_run)['b_passed'] is True


@pytest.mark.parametrize('filename', ['reflection_checks.jsonl', 'reflection_log.jsonl'])
def test_p5b_checks_final_reflection_input_numbers(numeric_run, filename):
    path = numeric_run.info.path / filename
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    row = rows[-1]
    inputs = row['reflection_input']
    inputs[-1], changed = re.subn(
        r'(?P<prefix>You requested )(?P<value>[\d,]+)(?P<suffix> acre-ft)',
        lambda m: m['prefix'] + f"{int(m['value'].replace(',', '')) + 1:,}" + m['suffix'],
        inputs[-1], count=1)
    assert changed == 1
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    details = _p5b(numeric_run)
    assert details['b_passed'] is False
    assert any(filename in message and 'request' in message for message in details['b_mismatches'])


def test_p5b_rejects_malformed_final_stored_fact(numeric_run):
    path = numeric_run.info.path / 'reflection_prompts.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    row = rows[-1]
    row['prompt'], changed = re.subn(
        r'(you asked for )([\d,]+)( acre-ft)', r'\g<1>\g<2>x\g<3>', row['prompt'], count=1)
    assert changed == 1
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    details = _p5b(numeric_run)
    assert details['b_passed'] is False
    assert any('reflection_prompts.jsonl' in message for message in details['b_unchecked'])
