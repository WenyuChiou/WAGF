"""Validator arms: Invariant 7 for the irrigation case (mock only).

A year a rule overruled and a year the same action was simply chosen leave the
same memory line and the same memory metadata, so the next year's prompt is
the same across both variants.
"""
import pytest
import yaml

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from examples.irrigation_abm import irrigation_personas as text
from examples.irrigation_abm import run_experiment as runner
from examples.irrigation_abm.tests.test_v3_prompt import CONFIG, ScriptedLLM, _run

VARIANTS = CONFIG.parent.parent / "config_variants"


def _line(ctx, **extra):
    return text.build_action_outcome_feedback(
        ctx, 2019, 100_000.0, 80_000.0, 1, basin="upper_basin",
        rejection_line_style="executed", **extra)


def test_executed_line_names_only_the_action_that_ran():
    approved = _line({"skill_name": "maintain_demand", "year": 1})
    overruled = _line({"skill_name": "maintain_demand", "year": 1, "was_fallback": True,
                       "proposed_skill": "increase_demand",
                       "blocking_rules": ["supply_gap_block_increase"]})
    assert approved == overruled
    assert approved.startswith("Year 2019: Action carried out: maintain demand. You requested")
    changed = _line({"skill_name": "decrease_demand", "year": 1, "magnitude_pct": 10.0})
    assert changed.startswith("Year 2019: Action carried out: decrease demand (by 10%). ")
    for banned in ("You chose", "rejected", "applied under", "proposal", "rule"):
        assert banned not in approved and banned not in changed


def test_the_reflection_check_parser_reads_the_executed_lead():
    from examples.irrigation_abm.reflection_checks import parse_outcome_line

    assert parse_outcome_line(_line({"skill_name": "decrease_demand", "year": 1,
                                     "magnitude_pct": 10.0})).direction == "decrease"
    assert parse_outcome_line(_line({"skill_name": "increase_demand", "year": 1,
                                     "magnitude_pct": 5.0})).direction == "increase"


def test_executed_context_reads_the_executed_skill_for_salience():
    # What ExperimentRunner leaves on the context under the executed style.
    assert runner._proposed_and_fallback({"skill_name": "maintain_demand", "year": 1}) == (
        "maintain_demand", False)


def test_validator_arm_settings_differ_only_in_beneficial_use_limit():
    configs = []
    for arm, enabled in (("with_validator", True), ("without_validator", False)):
        cfg = yaml.safe_load((VARIANTS / arm / "agent_types.yaml").read_text(encoding="utf-8"))
        assert cfg["irrigation_farmer"]["beneficial_use_limit"].pop("enabled") is enabled
        configs.append(cfg)
    assert configs[0] == configs[1]


def _increase(agent, year, attempt):
    return "H", "M", "Increase"


def _keep(agent, year, attempt):
    return "H", "M", "Keep"


def _twin(tmp_path, variant):
    """Run A: every agent asks to increase in a scarce year (blocked, the
    default keep runs). Run B: every agent asks to keep. Return, per run, the
    first decision prompt of the second year and the outcome memories written."""
    out = {}
    original = HumanCentricMemoryEngine.add_memory_for_agent
    for name, script in (("A", _increase), ("B", _keep)):
        writes = []

        def record(engine, agent, content, metadata=None, _writes=writes):
            if (metadata or {}).get("type") == "outcome":
                _writes.append((agent.id, content, dict(metadata)))
            return original(engine, agent, content, metadata)

        llm = ScriptedLLM(script)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(HumanCentricMemoryEngine, "add_memory_for_agent", record)
            _run(mp, tmp_path / f"{variant}_{name}" / "run", llm, "--agents", "3", "--years", "2",
                 "--seed", "7", "--config-dir", str(VARIANTS / variant))
        years = sorted({year for (_agent, year, _attempt) in llm.decisions})
        prompts = {agent: p for (agent, year, attempt), p in llm.decisions.items()
                   if year == years[1] and attempt == 0}
        retried = {agent for (agent, year, attempt) in llm.decisions if year == years[0] and attempt > 0}
        out[name] = (prompts, writes, retried, list(llm.reflections))
    return out


def test_an_overruled_year_and_a_chosen_year_give_the_same_next_prompt(tmp_path):
    runs = _twin(tmp_path, "with_validator")
    prompts_a, writes_a, retried_a = runs["A"][:3]
    prompts_b, writes_b, retried_b = runs["B"][:3]
    assert retried_a and not retried_b          # rules stepped in on run A only
    assert prompts_a and prompts_a == prompts_b
    assert writes_a and writes_a == writes_b    # same lines, importance, emotion, routine
    assert runs["A"][3] and runs["A"][3] == runs["B"][3]   # same reflection prompts
    assert all(": Action carried out: maintain demand" in content for _a, content, _m in writes_a)


def test_the_without_rules_arm_variant_runs_with_executed_lines(tmp_path):
    original = HumanCentricMemoryEngine.add_memory_for_agent
    writes = []

    def record(engine, agent, content, metadata=None):
        if (metadata or {}).get("type") == "outcome":
            writes.append(content)
        return original(engine, agent, content, metadata)

    llm = ScriptedLLM(_increase)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(HumanCentricMemoryEngine, "add_memory_for_agent", record)
        _run(mp, tmp_path / "run", llm, "--agents", "3", "--years", "2", "--seed", "7",
             "--governance-mode", "disabled",
             "--config-dir", str(VARIANTS / "without_validator"))
    assert writes and all(": Action carried out: increase demand" in w for w in writes)


@pytest.mark.parametrize("variant", ["with_validator", "without_validator"])
def test_simple_prompt_has_no_generic_rating_scale_block(variant):
    """Owner decision 2026-11-27: the simple prompt explains each five-level
    rating in plain words, so the generic "### RATING SCALE ... VL = Very Low"
    block is not shown (it repeated those levels, and "Very Low" reads backwards
    for water scarcity, where VL means abundant). The full-information prompt
    under config/ keeps the block: it does not explain the levels itself."""
    assert "{rating_scale}" not in runner.SIMPLE_PROMPT_TEMPLATE
    folder = VARIANTS / variant
    assert "{rating_scale}" not in (folder / "prompts" / "irrigation_farmer.txt").read_text(encoding="utf-8")
    shared = yaml.safe_load((folder / "agent_types.yaml").read_text(encoding="utf-8"))["shared"]
    assert "rating_scale" not in shared
    full = CONFIG.parent / "prompts" / "irrigation_farmer.txt"
    assert "{rating_scale}" in full.read_text(encoding="utf-8")
