"""The irrigation runner stores one domain outcome per year and filters routine
outcomes from the next decision prompt. Exercise both paths with the mock model.
"""
from __future__ import annotations

import csv
import json
import re
import sys

import broker.utils.llm_utils as llm_utils
from broker.utils.llm_utils import LLMStats
from examples.irrigation_abm import run_experiment




def _smart_mock_invoke(prompt: str):
    """Deterministic stand-in for both LLM call sites this run makes:
    the per-year household decision call (numbered-option JSON, the
    framework's standard domain-agnostic mock) and the batch reflection
    call (``{"answer": ...}``), distinguished by the reflection prompt's
    fixed last line ("Answer with this JSON object only: {"answer" ...",
    ``broker/components/cognitive/reflection.py
    (ReflectionEngine.generate_reflection_prompt_one_agent)``), which never appears in the decision prompt (the persona instruction no
    longer says "Lesson Learned" since irrigation spec item 45d).
    """
    stats = LLMStats(retries=0, success=True)
    if 'Answer with this JSON object only: {"answer"' in prompt:
        return json.dumps({"answer": "I learned to manage water demand carefully after last year."}), stats
    options = re.findall(r"(\d+)\.\s+\w+", prompt)
    decision_id = int(options[0]) if options else 1
    return json.dumps({"decision": decision_id}), stats


def _run_three_years(monkeypatch, tmp_path):
    """Drive main() for 3 years / 2 synthetic agents with the mock LLM,
    spying on every memory_engine.retrieve() call so the exact composed
    memory block at each (year, agent) checkpoint can be inspected."""
    calls = []
    captured = {}

    real_build = run_experiment.ExperimentBuilder.build

    def spy_build(self):
        runner = real_build(self)
        captured["runner"] = runner
        orig_retrieve = runner.memory_engine.retrieve

        def spy_retrieve(agent, *a, **kw):
            result = orig_retrieve(agent, *a, **kw)
            calls.append((getattr(runner, "_current_year", None), agent.id, list(result)))
            return result

        runner.memory_engine.retrieve = spy_retrieve
        return runner

    # Two independent LLM call sites in this module (see docstring): the
    # main decision loop uses the module-local `create_llm_invoke` alias
    # (broker.utils.llm_utils.create_legacy_invoke); the reflection engine
    # (ExperimentRunner.get_llm_invoke) does its own fresh import of
    # broker.utils.llm_utils.create_llm_invoke (a DIFFERENT function of the
    # same alias name). Both must be patched or reflection silently no-ops.
    monkeypatch.setattr(run_experiment, "create_llm_invoke",
                        lambda model, verbose=False: _smart_mock_invoke)
    monkeypatch.setattr(llm_utils, "create_llm_invoke",
                        lambda model, verbose=False, overrides=None: _smart_mock_invoke)
    monkeypatch.setattr(run_experiment.ExperimentBuilder, "build", spy_build)

    argv = [
        "run_experiment.py", "--model", "mock", "--years", "3", "--agents", "2",
        "--output", str(tmp_path), "--workers", "1", "--seed", "7",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    run_experiment.main()
    return calls


def test_year3_memory_block_has_no_generic_runner_lines(monkeypatch, tmp_path):
    calls = _run_three_years(monkeypatch, tmp_path)
    assert calls, "memory_engine.retrieve was never called"

    agent_ids = sorted({aid for (_year, aid, _mems) in calls})
    assert agent_ids, "no agents produced a retrieve() call"
    target = agent_ids[0]

    year3_calls = [mems for (year, aid, mems) in calls if aid == target and year == 3]
    assert year3_calls, f"no year-3 retrieve() call recorded for {target}: {calls}"
    year3_block = year3_calls[0]

    contents = [
        m.get("content") if isinstance(m, dict) else str(m) for m in year3_block
    ]
    assert contents, "year-3 memory block is empty"

    # Runner lines use simulation years; domain outcomes use calendar years.
    assert not any(c.startswith(("Year 1: Action carried out:", "Year 2: Action carried out:"))
                   for c in contents)

    # These fully delivered keeps are routine. The log records both outcomes
    # even though the composed decision memory omits them.
    with (tmp_path / "simulation_log.csv").open(encoding="utf-8", newline="") as stream:
        row = next(r for r in csv.DictReader(stream) if r["year"] == "3" and r["agent_id"] == target)
    stored = row["memory"].split(" | ")
    assert len(stored) == 3
    for year in (2019, 2020):
        assert sum(line.startswith(f"Year {year}: Action carried out: maintain demand.") for line in stored) == 1

    # Plus the reflection written at the end of year 2 (2020); the one
    # written at the end of 2019 was replaced (reflection.keep_latest_only).
    reflection_lines = [c for c in contents
                        if c.startswith("Consolidated Reflection (written in 2020): ")]
    assert len(reflection_lines) == 1, contents

    assert contents == reflection_lines
