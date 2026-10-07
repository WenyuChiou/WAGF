"""Regression guard for the leading-blank-lines fix (P3-a / item 5).

Mirrors irrigation's own `test_no_leading_blank_lines`
(examples/irrigation_abm/tests/test_v3_prompt.py): every real prompt used to
start with 4 blank lines, for every domain whose template does not itself
reference ``{system_prompt}`` -- `TieredContextBuilder.format_prompt`
(broker/components/context/tiered.py) auto-prepends
``"{system_prompt}\\n\\n{priority_section}\\n\\n"`` in that case, and both
vars render empty (no SystemPromptProvider / PrioritySchemaProvider in
flood's provider list), leaving just the 4 newlines. Fixed template-side
(``config/prompts/household.txt`` now starts with
``{system_prompt}{priority_section}{narrative_persona}``), not in
``tiered.py`` itself, so no other domain's prompt is touched by this fix.

A real (scripted-mock) simulation, not a template-string unit test, because
the earlier version of this bug was confirmed NOT a render-only artifact --
the actual LLM input carried the 4 blank lines -- and a static check of the
template file's first line would not catch a regression introduced anywhere
else in the render path (e.g. tiered.py's fallback being reverted).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scripted_mock_driver import run_scripted_mock, reset_state  # noqa: E402


def _traces(output_dir: Path):
    path = output_dir / "raw" / "household_traces.jsonl"
    assert path.exists(), f"no trace file written to {output_dir}"
    with path.open(encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[1:]]  # line 0 is the _metadata header


@pytest.fixture
def mini_run(tmp_path):
    reset_state()
    output = tmp_path / "run"
    run_scripted_mock(governance_mode="strict", output=str(output), agents=5, years=3, seed=42)
    return _traces(output)


def test_no_leading_blank_lines_on_first_attempt(mini_run):
    for rec in mini_run:
        prompt = rec.get("input") or ""
        assert prompt, rec.get("agent_id")
        assert not prompt.startswith("\n"), (rec["agent_id"], rec["year"], repr(prompt[:20]))
        assert prompt.startswith("You are a homeowner"), (rec["agent_id"], rec["year"], repr(prompt[:40]))


def test_no_leading_blank_lines_on_retry_prompts(mini_run):
    """A retry prompt legitimately prepends its own governance header before
    the original prompt text (not a blank-line regression); what must never
    happen is the retry prompt ALSO carrying the old 4-blank-line gap
    between that header and "You are a homeowner...", or starting with a
    blank line itself."""
    retried = [rec for rec in mini_run if rec.get("retry_prompts")]
    assert retried, "fixture produced no retries; the scenario mix changed upstream"
    for rec in retried:
        for retry_prompt in rec["retry_prompts"]:
            assert not retry_prompt.startswith("\n"), (rec["agent_id"], rec["year"])
            assert "\n\n\n\n" not in retry_prompt, (rec["agent_id"], rec["year"])


def test_use_priority_schema_is_refused_not_silently_garbled(tmp_path):
    """P3-6 (opus review round 3): household.txt's first line
    "{system_prompt}{priority_section}{narrative_persona}" has no separator
    between {priority_section} and {narrative_persona} -- a non-empty
    {priority_section} (PrioritySchemaProvider) would glue its block
    directly onto "You are a homeowner..." with no blank line. Rather than
    patch the template, --use-priority-schema is refused outright."""
    with pytest.raises(ValueError, match="use-priority-schema"):
        import examples.single_agent.run_flood as run_flood_mod
        run_flood_mod.run_parity_benchmark(
            model="mock", years=1, agents_count=1,
            custom_output=str(tmp_path / "never_written"),
            use_priority_schema=True,
        )
    assert not (tmp_path / "never_written").exists()
