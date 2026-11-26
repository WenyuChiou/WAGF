"""python -m broker.run and Invariant 7: governance leaves no trace.

- The runner's memory line has one form on every row ("Year N: Action carried
  out: X."), because broker.run applies ``memory.rejection_line_style:
  executed`` unless the YAML sets a style; ``explicit`` gives back the old
  lines.
- Every memory write carries ``metadata['origin']`` and is logged to
  ``memory_log.jsonl``; an untagged write after the builder's seeding raises.
- A reflection reads only world, decision, seed and social lines, and the
  stored lesson drops the reply's opener (R5 walk finding 18).
"""
from __future__ import annotations

import json
import sys
from textwrap import dedent
from types import SimpleNamespace
from uuid import uuid4

import pytest
import yaml

from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.components.memory.engines.window import WindowMemoryEngine
from broker.components.memory.origin_gate import ORIGINS, install_origin_gate
from broker.run import _entry, main
from broker.run._memory import strip_reply_opener


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


@pytest.fixture
def case(tmp_path, monkeypatch):
    """One agent; ``inspect`` is always blocked, so year 1 (the agent asks to
    inspect) ends in the default ``wait`` and year 2 (it asks to wait once its
    memory holds year 1) is an approved ``wait``."""
    folder = tmp_path / f"case_{uuid4().hex}"
    config_path = folder / "config" / "agent_types.yaml"
    config_path.parent.mkdir(parents=True)
    (folder / "__init__.py").touch()
    (folder / "world.py").write_text(dedent('''
        from broker.interfaces.skill_types import ExecutionResult, ValidationResult
        from broker.utils.llm_utils import LLMStats

        class World:
            year = 0

            def advance_step(self):
                self.year += 1
                return {"current_year": self.year}

            def execute_skill(self, approved_skill):
                return ExecutionResult(success=True, state_changes={})

        def build(ctx):
            return World()

        def block_inspect(proposal, context, registry):
            if proposal.skill_name != "inspect":
                return []
            return [ValidationResult(valid=False, validator_name="no_inspect",
                                     errors=["inspect is not allowed"],
                                     metadata={"rule_id": "no_inspect", "level": "ERROR"})]

        def validators(ctx):
            return (block_inspect,)

        def mock(ctx):
            def invoke(prompt):
                if "Year 1:" in prompt:
                    return '{"decision": 1}', LLMStats(success=True)
                return '{"decision": 2}', LLMStats(success=True)
            return invoke
    '''), encoding="utf-8")
    _write_yaml(config_path.with_name("skill_registry.yaml"), {
        "default_skill": "wait",
        "skills": [
            {"skill_id": "wait", "description": "Wait for the next year"},
            {"skill_id": "inspect", "description": "Inspect the site"},
        ],
    })
    data = {
        "global_config": {"run": {"world": "world:build", "validators": "world:validators",
                                  "mock": "world:mock"}},
        "agent": {
            "psychological_framework": "generic",
            "prompt_template": "Memory:\n{memory}\n\nAvailable actions\n{options_text}\n\n{response_format}",
            "actions": [{"id": "wait", "aliases": ["1"]}, {"id": "inspect", "aliases": ["2"]}],
            "parsing": {"skill_map": {"1": "wait", "2": "inspect"}, "default_skill": "wait"},
            "response_format": {
                "delimiter_start": "<<<DECISION_START>>>",
                "delimiter_end": "<<<DECISION_END>>>",
                "fields": [{"key": "decision", "type": "choice", "required": True}],
            },
        },
    }
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv("GOVERNANCE_PROFILE", "default")
    yield config_path, data
    for name in list(sys.modules):
        if name == folder.name or name.startswith(f"{folder.name}."):
            sys.modules.pop(name, None)


def _run(case, tmp_path, *, style=None, years=2):
    config, data = case
    if style is not None:
        data["agent"]["memory"] = {"rejection_line_style": style}
    _write_yaml(config, data)
    output = tmp_path / "output"
    argv = [str(config), "--model", "mock", "--years", str(years), "--agents", "1",
            "--output", str(output)]
    assert main(argv) == 0
    return output


def _decisions(output):
    lines = (output / "raw" / "agent_traces.jsonl").read_text(encoding="utf-8").splitlines()
    return [r for r in map(json.loads, lines) if "step_id" in r]


def _first_prompt(output, year):
    return next(r["input"] for r in _decisions(output) if r["year"] == year)


def _memory_log(output):
    text = (output / "memory_log.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def _audit_status(output):
    import csv
    path = next((output).glob("*governance_audit.csv"))
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return [row["status"] for row in csv.DictReader(handle)]


# -- the default: executed -------------------------------------------------

def test_default_year_and_approved_year_get_the_same_line(case, tmp_path):
    output = _run(case, tmp_path)
    assert _audit_status(output) == ["REJECTED", "APPROVED"]
    log = _memory_log(output)
    decisions = [e for e in log if e["origin"] == "decision"]
    assert [e["content"] for e in decisions] == [
        "Year 1: Action carried out: Wait.", "Year 2: Action carried out: Wait."]
    assert [e["period"] for e in decisions] == [1, 2]
    # Same metadata on the default year and the approved year.
    strip = lambda e: {k: v for k, v in e.items() if k not in ("content", "period")}
    assert strip(decisions[0]) == strip(decisions[1])
    prompt = _first_prompt(output, 2)
    assert "Year 1: Action carried out: Wait." in prompt
    for word in ("reject", "default action", "inspect is not allowed", "no_inspect", "Proposal"):
        assert word not in prompt.split("Available actions", 1)[0]
    record = json.loads((output / "broker_run.json").read_text(encoding="utf-8"))
    assert record["rejection_line_style"] == {"agent": "executed"}
    assert record["memory_writes_by_origin"]["decision"] == 2


def test_explicit_gives_back_the_old_lines(case, tmp_path):
    output = _run(case, tmp_path, style="explicit")
    contents = [e["content"] for e in _memory_log(output) if e["origin"] == "decision"]
    assert contents == [
        "Year 1: Proposal to inspect was rejected; default action applied: Wait",
        "Year 2: Decided to: Wait"]
    record = json.loads((output / "broker_run.json").read_text(encoding="utf-8"))
    assert record["rejection_line_style"] == {"agent": "explicit"}


def test_unknown_style_is_refused_before_the_run(case, tmp_path, capsys):
    config, data = case
    data["agent"]["memory"] = {"rejection_line_style": "quiet"}
    _write_yaml(config, data)
    assert main([str(config), "--model", "mock", "--output", str(tmp_path / "out")]) == 2
    assert "rejection_line_style 'quiet'" in capsys.readouterr().err


# -- the write gate ----------------------------------------------------------

def test_gate_refuses_an_untagged_write_after_seeding(tmp_path):
    engine = WindowMemoryEngine(window_size=3)
    gate = install_origin_gate(engine, tmp_path, period=lambda: 4)
    engine.add_memory("a1", "profile line")                     # seeding: tagged seed
    gate.seeding = False
    with pytest.raises(ValueError, match="origin None"):
        engine.add_memory("a1", "Year 4: you were blocked")
    with pytest.raises(ValueError, match="origin 'governance'"):
        engine.add_memory("a1", "Year 4: x", {"origin": "governance"})
    engine.add_memory("a1", "Year 4: the river rose", {"origin": "world", "importance": 0.4})
    log = [json.loads(l) for l in (tmp_path / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(e["origin"], e["period"], e["content"]) for e in log] == [
        ("seed", 0, "profile line"), ("world", 4, "Year 4: the river rose")]
    assert log[1]["importance"] == 0.4
    # A refused write never reached the engine.
    assert engine.retrieve(SimpleNamespace(id="a1"), top_k=5) == [
        "profile line", "Year 4: the river rose"]
    assert gate.counts == {**{o: 0 for o in ORIGINS}, "seed": 1, "world": 1}


def test_gate_keeps_the_engine_class_and_logs_a_nested_write_once(tmp_path):
    engine = HumanCentricMemoryEngine(window_size=3, top_k_significant=2, seed=1)
    install_origin_gate(engine, tmp_path, period=lambda: 2).seeding = False
    assert type(engine) is HumanCentricMemoryEngine
    agent = SimpleNamespace(id="a1", agent_type="agent")
    engine.add_memory_for_agent(agent, "Year 2: Action carried out: Wait.",
                                {"origin": "decision", "importance": 0.1, "emotion": "routine"})
    log = (tmp_path / "memory_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log) == 1 and json.loads(log[0])["origin"] == "decision"


def test_an_earlier_log_is_replaced_at_the_first_write(tmp_path):
    (tmp_path / "memory_log.jsonl").write_text('{"old": true}\n', encoding="utf-8")
    engine = WindowMemoryEngine(window_size=3)
    install_origin_gate(engine, tmp_path, period=lambda: 1)
    assert "old" in (tmp_path / "memory_log.jsonl").read_text(encoding="utf-8")
    engine.add_memory("a1", "profile line")
    assert "old" not in (tmp_path / "memory_log.jsonl").read_text(encoding="utf-8")


def test_gate_refuses_a_reflection_line_without_the_prefix(tmp_path):
    engine = WindowMemoryEngine(window_size=3)
    install_origin_gate(engine, tmp_path, period=lambda: 1,
                        reflection_prefix="Reflection (year").seeding = False
    with pytest.raises(ValueError, match="does not start with"):
        engine.add_memory("a1", "a lesson without the prefix", {"origin": "reflection"})
    engine.add_memory("a1", "Reflection (year 1): keep watch", {"origin": "reflection"})
    assert engine.retrieve(SimpleNamespace(id="a1"), top_k=5) == ["Reflection (year 1): keep watch"]


def test_an_untagged_write_from_a_case_hook_stops_the_run(case, tmp_path):
    config, data = case
    _write_yaml(config, data)
    prepared = _entry.prepare([str(config), "--model", "mock", "--years", "2", "--agents", "1",
                               "--output", str(tmp_path / "output")])
    runner = prepared.runner

    def post_year(year, agents):
        for agent in agents.values():
            runner.memory_engine.add_memory(agent.id, f"Year {year}: you were blocked")

    runner.hooks["post_year"] = post_year
    with pytest.raises(ValueError, match="origin None"):
        runner.run()


# -- reflection ----------------------------------------------------------------

def test_reflection_reads_no_reflection_origin_and_stores_its_own(case, tmp_path):
    config, data = case
    data["global_config"]["memory"] = {"engine_type": "humancentric"}
    data["global_config"]["reflection"] = {"enabled": True}
    _write_yaml(config, data)
    output = tmp_path / "output"
    prepared = _entry.prepare([str(config), "--model", "mock", "--years", "1", "--agents", "1",
                               "--output", str(output)])
    hook, agent = prepared.reflection_hook, prepared.runner.agents["agent_1"]
    engine = hook.memory_engine
    engine.add_memory(agent.id, "Year 1: the site flooded", {"origin": "world", "importance": 0.5})
    with pytest.raises(ValueError, match="does not start with"):
        engine.add_memory(agent.id, "a lesson someone stored without the prefix",
                          {"origin": "reflection", "importance": 0.9})
    engine.add_memory(agent.id, "Reflection (year 0): an earlier lesson",
                      {"origin": "reflection", "importance": 0.9})
    prompts = []

    def invoke(prompt):
        prompts.append(prompt)
        return "Okay, here's my reflection:\nInspect before the wet season.", {"tokens": 1}

    hook.model = "some-real-model"
    hook.runner = SimpleNamespace(get_llm_invoke=lambda agent_type: invoke)
    hook(1, {agent.id: agent})
    assert "Year 1: the site flooded" in prompts[0]
    assert "an earlier lesson" not in prompts[0]
    entry = json.loads((output / "reflection_log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert entry["summary"] == "Inspect before the wet season."
    log = _memory_log(output)
    assert log[-1]["origin"] == "reflection"
    assert log[-1]["content"] == "Reflection (year 1): Inspect before the wet season."


@pytest.mark.parametrize("text, expected", [
    ("Okay, here's my reflection:\nPumping less kept storage up.", "Pumping less kept storage up."),
    ("Here is my lesson: cut early.", "cut early."),
    ("Sure! Here are my reflections:\n\n- a", "- a"),
    ("Pumping less kept storage up.", "Pumping less kept storage up."),
    ("Okay, here's my reflection:", "Okay, here's my reflection:"),   # nothing after it: kept
    ("Storage note: keep 180", "Storage note: keep 180"),
    ("Hereafter: x", "Hereafter: x"),
    ("Okay, here’s my reflection:\nCut early.", "Cut early."),        # curly apostrophe
    ("Here is the key takeaway: cut early.", "cut early."),
    ("Here is what happened: storage fell.", "Here is what happened: storage fell."),
])
def test_strip_reply_opener(text, expected):
    assert strip_reply_opener(text) == expected


@pytest.mark.parametrize("physical_only", [False, True])
def test_scaffold_writes_the_executed_style(physical_only):
    from broker.tools.scaffold_domain import gen_agent_types_yaml

    data = yaml.safe_load(gen_agent_types_yaml(
        "demo", ["act", "hold"], "generic", physical_only=physical_only))
    assert data["agent"]["memory"]["rejection_line_style"] == "executed"


# -- run_integrity.json governance_carryover block (S4, design 5.2) -------------

def _integrity(output):
    return json.loads((output / "run_integrity.json").read_text(encoding="utf-8"))


def test_an_executed_run_records_a_clean_carryover_block(case, tmp_path):
    output = _run(case, tmp_path)
    data = _integrity(output)
    block = data["governance_carryover"]
    assert block["checked_agent_types"] == ["agent"]
    assert block["decision_rows"] == 2
    assert block["rejected_or_unreadable_rows"] == 1
    assert block["default_applied_rows"] == 1
    assert block["default_year_line_shapes_not_seen_in_approved_years"] == 0
    assert block["memory_writes_by_origin"].get("decision") == 2
    assert block["governance_terms_checked"] > len(("was rejected",))
    assert (block["governance_terms_in_memory"], block["governance_terms_in_reflection_input"],
            block["governance_terms_in_reflection_output"]) == (0, 0, 0)
    assert block["ok"] is True and data["integrity_ok"] is True


def test_an_explicit_run_is_not_checked(case, tmp_path):
    output = _run(case, tmp_path, style="explicit")
    block = _integrity(output)["governance_carryover"]
    assert block["checked_agent_types"] == []
    assert block["ok"] is True


def test_rule_wording_written_by_a_hook_fails_the_run_integrity_check(case, tmp_path, capsys):
    from broker.tools.check_run_integrity import main as check_main

    config, data = case
    _write_yaml(config, data)
    output = tmp_path / "output"
    prepared = _entry.prepare([str(config), "--model", "mock", "--years", "2", "--agents", "1",
                               "--output", str(output)])
    runner = prepared.runner

    def post_year(year, agents):
        for agent in agents.values():
            runner.memory_engine.add_memory(
                agent.id, f"Year {year}: inspect is not allowed here",
                {"origin": "world", "period": year})

    runner.hooks["post_year"] = post_year
    runner.run()
    data = _integrity(output)
    block = data["governance_carryover"]
    assert block["governance_terms_in_memory"] == 2
    assert block["examples"][0]["terms"] == ["inspect is not allowed"]
    assert block["ok"] is False and data["integrity_ok"] is False
    with pytest.raises(SystemExit) as stop:
        check_main([str(output)])
    assert stop.value.code == 1
    out = capsys.readouterr().out
    assert "governance_carryover (Invariant 7): rule wording in 2 memory writes" in out


def test_a_rejected_year_line_in_a_form_approved_years_never_have_is_counted(tmp_path):
    from broker.core.run_integrity import governance_carryover_block

    lines = [
        {"agent_id": "a1", "period": 1, "intervened": True, "default_ran": True,
         "line": "Year 1: Action carried out: wait (fallback).", "action": "wait", "number": ""},
        {"agent_id": "a1", "period": 2, "intervened": False, "default_ran": False,
         "line": "Year 2: Action carried out: cut by 10%.", "action": "cut", "number": " by 10%"},
        {"agent_id": "a1", "period": 3, "intervened": True, "default_ran": False,
         "line": "Year 3: Action carried out: cut by 20%.", "action": "cut", "number": " by 20%"},
    ]
    kwargs = dict(agent_types={"a1": "farmer"}, writes_by_origin={"decision": 3},
                  decision_lines=lines)
    block = governance_carryover_block(tmp_path, styles={"farmer": "executed"}, **kwargs)
    assert block["default_year_line_shapes_not_seen_in_approved_years"] == 1
    assert block["ok"] is False
    # Only executed agent types are checked.
    other = governance_carryover_block(tmp_path, styles={"farmer": "explicit"}, **kwargs)
    assert other["checked_agent_types"] == [] and other["ok"] is True
    # Nothing to compare against: no count, no failure.
    alone = governance_carryover_block(tmp_path, styles={"farmer": "executed"},
                                       agent_types={"a1": "farmer"}, writes_by_origin={},
                                       decision_lines=lines[:1])
    assert alone["default_year_line_shapes_not_seen_in_approved_years"] is None
    assert alone["ok"] is True


def test_record_run_integrity_without_the_block_keeps_its_keys(tmp_path):
    from broker.core.run_integrity import record_run_integrity

    audit = record_run_integrity(tmp_path)
    assert "governance_carryover" not in audit


def test_a_block_that_cannot_be_built_fails_the_run(tmp_path):
    from broker.core.run_integrity import record_run_integrity

    audit = record_run_integrity(tmp_path, governance_carryover={"styles": None})
    assert audit["governance_carryover"]["ok"] is False
    assert audit["governance_carryover"]["error"]
    assert audit["integrity_ok"] is False


def _block_inputs(tmp_path, memory_rows, writes):
    (tmp_path / "memory_log.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in memory_rows), encoding="utf-8")
    return dict(styles={"farmer": "executed"}, agent_types={"a1": "farmer"},
                writes_by_origin={"decision": writes}, decision_lines=[])


def test_rule_wording_in_reflection_input_and_lessons_is_counted(tmp_path):
    from dataclasses import fields

    from broker.components.cognitive.reflection import ReflectionInsight
    from broker.core.run_integrity import governance_carryover_block

    kwargs = _block_inputs(tmp_path, [{"agent_id": "a1", "period": 1, "origin": "decision",
                                       "content": "Year 1: Action carried out: Wait."}], 1)
    # The shape ReflectionHook._log writes: asdict(insight) + reflection_input + agent_id.
    assert {"summary", "year_created"} <= {f.name for f in fields(ReflectionInsight)}
    entry = {"summary": "Reflection (year 2): my proposal to inspect was rejected.",
             "year_created": 2, "reflection_input": ["Year 1: your proposal to inspect was rejected."],
             "agent_id": "a1"}
    (tmp_path / "reflection_log.jsonl").write_text(json.dumps(entry) + "\n", encoding="utf-8")
    block = governance_carryover_block(tmp_path, **kwargs)
    assert block["governance_terms_in_memory"] == 0
    assert block["governance_terms_in_reflection_input"] == 1
    assert block["governance_terms_in_reflection_output"] == 1
    assert {e["period"] for e in block["examples"]} == {2}
    assert block["ok"] is False


@pytest.mark.parametrize("damage", ["short", "bad_line"])
def test_a_short_or_damaged_memory_log_fails_the_block(tmp_path, damage):
    from broker.core.run_integrity import governance_carryover_block

    row = {"agent_id": "a1", "period": 1, "origin": "decision",
           "content": "Year 1: Action carried out: Wait."}
    kwargs = _block_inputs(tmp_path, [row], 2 if damage == "short" else 1)
    if damage == "bad_line":
        with open(tmp_path / "memory_log.jsonl", "a", encoding="utf-8") as handle:
            handle.write('{"agent_id": "a1", "content": "Year 2: your pro\n')
    block = governance_carryover_block(tmp_path, **kwargs)
    assert block["ok"] is False
    if damage == "short":
        assert block["memory_log_short"] is True and block["memory_log_rows"] == 1
    else:
        assert block["memory_log_short"] is False
        assert block["unreadable_files"] == ["memory_log.jsonl"]


def test_multi_digit_years_and_prefix_actions_keep_line_shape_stable(tmp_path):
    from broker.core.run_integrity import governance_carryover_block

    lines = [
        {"agent_id": "a1", "period": 9, "intervened": False, "default_ran": False,
         "line": "Year 9: Action carried out: Act.", "action": "Act", "number": ""},
        {"agent_id": "a1", "period": 10, "intervened": True, "default_ran": True,
         "line": "Year 10: Action carried out: Hold.", "action": "Hold", "number": ""},
    ]
    block = governance_carryover_block(
        tmp_path,
        styles={"farmer": "executed"},
        agent_types={"a1": "farmer"},
        writes_by_origin={},
        decision_lines=lines,
    )
    assert block["default_year_line_shapes_not_seen_in_approved_years"] == 0
    assert block["ok"] is True

