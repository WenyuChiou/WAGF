"""Irrigation's runner-decision-line opt-out (2026-09-26), end-to-end.

Irrigation's ``pre_year`` hook already writes its own per-year outcome line
(``build_action_outcome_feedback``), so the generic "Decided to: X" /
"default action applied: X" line ``ExperimentRunner._apply_state_changes``
writes every period doubled every year up in the composed 5-recent-memory
retrieval window (SI section 3.8), covering ~2.5 years of history instead of
5. ``examples/irrigation_abm/config/agent_types.yaml`` now sets
``irrigation_farmer.memory.runner_decision_line: false`` to suppress the
generic line (see ``broker/tests/test_runner_decision_line_optout.py`` for
the framework-level unit tests of that mechanism).

This test drives a REAL 3-year, 2-agent run through
``examples.irrigation_abm.run_experiment.main()`` with a deterministic mock
LLM (no Ollama / network), and inspects the actual composed memory block a
target agent sees at year 3 — one line per prior year (years 1 and 2) plus
the reflection written at the end of year 2, and none of the runner's own
generic markers.
"""
from __future__ import annotations

import json
import re
import sys

import broker.utils.llm_utils as llm_utils
from broker.utils.llm_utils import LLMStats
from examples.irrigation_abm import run_experiment

DECISION_MEMORY_MARKER = "Decided to:"
FALLBACK_MEMORY_MARKER = "default action applied:"


def _smart_mock_invoke(prompt: str):
    """Deterministic stand-in for both LLM call sites this run makes:
    the per-year household decision call (numbered-option JSON, the
    framework's standard domain-agnostic mock) and the batch reflection
    call (JSON keyed by agent id, matching ReflectionEngine's Stage-1
    parser), distinguished by the reflection prompt's fixed opening line
    ("You are a Reflection Assistant", ``broker/components/cognitive/
    reflection.py (ReflectionEngine.generate_batch_reflection_prompt)``),
    which never appears in the decision prompt (the persona instruction no
    longer says "Lesson Learned" since irrigation spec item 45d).
    """
    stats = LLMStats(retries=0, success=True)
    if "You are a Reflection Assistant" in prompt:
        ids = sorted(set(re.findall(r"Agent_\d+", prompt)))
        payload = {
            aid: "I learned to manage water demand carefully after last year."
            for aid in ids
        }
        return json.dumps(payload), stats
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

    # No generic runner line of either shape.
    assert not any(DECISION_MEMORY_MARKER in c for c in contents), contents
    assert not any(FALLBACK_MEMORY_MARKER in c for c in contents), contents

    # Exactly one domain outcome line per prior year (years 1 and 2), each
    # written by build_action_outcome_feedback (irrigation_personas.py),
    # not the runner's suppressed generic line.
    # WP4 (spec 4.5): memory lines name calendar years (loop years 1 and 2
    # are 2019 and 2020).
    year1_lines = [c for c in contents if c.startswith("Year 2019:")]
    year2_lines = [c for c in contents if c.startswith("Year 2020:")]
    assert len(year1_lines) == 1, contents
    assert len(year2_lines) == 1, contents

    # Plus the reflection written at the end of year 2 (2020); the one
    # written at the end of 2019 was replaced (reflection.keep_latest_only).
    reflection_lines = [c for c in contents
                        if c.startswith("Consolidated Reflection (written in 2020): ")]
    assert len(reflection_lines) == 1, contents

    # Exactly these three lines: no duplication, no stray fourth item.
    assert len(contents) == 3, contents
