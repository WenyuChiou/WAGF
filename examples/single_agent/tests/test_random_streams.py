"""Paired flood environments must survive arm-specific household relocation."""

import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from examples.single_agent import run_flood as rf
from broker.utils.llm_utils import LLMStats


def _stream_draws(seed):
    return {
        (year, household, purpose): rf._flood_random_stream(
            seed, year, purpose, household
        ).random()
        for year in range(1, 11)
        for household, purpose in [
            (None, "flood_event"), (None, "grant"),
            ("Agent_2", "damage"), ("Agent_2", "recall"),
            ("Agent_2", "options"), ("Agent_3", "damage"),
            ("Agent_2", "gossip"),
        ]
    }


def test_streams_repeat_and_separate_seed_year_household_and_purpose():
    first = _stream_draws(42)
    random.seed(991)
    for _ in range(100):
        random.random()
    assert _stream_draws(42) == first
    assert _stream_draws(43) != first
    assert len(set(first.values())) == len(first)


def test_stream_keys_are_unambiguous():
    assert rf._flood_random_stream(1, 2, "b:c", "a").random() != (
        rf._flood_random_stream(1, 2, "c", "a:b").random()
    )


def test_streams_ignore_pythonhashseed():
    code = """
import json
from examples.single_agent.run_flood import _flood_random_stream
samples = []
for year in range(1, 6):
    for household in (None, 'Agent_2', 'household:雪'):
        for purpose in ('flood_event', 'grant', 'damage', 'recall', 'options', 'gossip'):
            rng = _flood_random_stream(42, year, purpose, household)
            options = list(range(4))
            value = rng.random()
            rng.shuffle(options)
            samples.append([value, options])
print(json.dumps(samples))
"""
    outputs = []
    for hash_seed in ("1", "999"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONDONTWRITEBYTECODE="1")
        completed = subprocess.run(
            [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[3],
            env=env, capture_output=True, text=True, encoding="utf-8",
            timeout=60, check=True,
        )
        outputs.append(json.loads(completed.stdout.splitlines()[-1]))
    assert outputs[0] == outputs[1]


def test_fixed_hazard_schedule_and_global_rng_independence():
    sim = rf.ResearchSimulation({}, flood_years=[2, 4], seed=0)
    states = [sim.advance_year() for _ in range(6)]
    assert [state["flood_event"] for state in states] == [False, True, False, True, False, False]
    random.seed(998)
    again = rf.ResearchSimulation({}, flood_years=[2, 4], seed=0)
    assert [again.advance_year() for _ in range(6)] == states


def test_option_shuffle_without_override_uses_simulation_seed(monkeypatch):
    agent = SimpleNamespace(id="Agent_2", elevated=False, has_insurance=False)
    sim = rf.ResearchSimulation({agent.id: agent}, seed=99)
    sim.current_year = 4
    monkeypatch.setattr(rf.TieredContextBuilder, "build", lambda *args, **kwargs: {"personal": {}})
    args = dict(agents=sim.agents, sim=sim, shuffle_skills=True)
    implicit = rf.FinalContextBuilder(**args).build(agent.id)
    explicit = rf.FinalContextBuilder(**args, shuffle_seed_base=99).build(agent.id)
    assert implicit["personal"]["dynamic_skill_map"] == explicit["personal"]["dynamic_skill_map"]


def _mock_run(monkeypatch, output, *, seed, relocate, arm="strict", years=10):
    """Run real hooks/context/execution with only model replies mocked."""
    capture = {
        "years": {}, "households": {}, "options": {}, "actions": {}, "draws": {},
        "gossip": {}, "gossip_inputs": {}, "context_gossip": {},
    }
    advance = rf.ResearchSimulation.advance_year
    pre_year = rf.FinalParityHook.pre_year
    build = rf.FinalContextBuilder.build
    execute = rf.ResearchSimulation.execute_skill
    stream = rf._flood_random_stream
    social = rf.InteractionHub.get_social_context
    decision_year = None
    last_context_key = None

    def record_stream(run_seed, year, purpose, household_id=None):
        # Key shape at every call site: only the two year-level draws have
        # no household (a key that drops the household would correlate
        # every household's draws within a year).
        assert (household_id is None) == (purpose in {"flood_event", "grant"}), (purpose, household_id)
        if purpose == "gossip":
            assert year == decision_year
        rng = stream(run_seed, year, purpose, household_id)
        state = rng.getstate()
        capture["draws"][(year, household_id, purpose)] = rng.random()
        rng.setstate(state)
        return rng

    def record_year(sim):
        state = advance(sim)
        capture["years"][sim.current_year] = dict(state)
        return state

    def record_events(hook, year, env, agents):
        memory = hook.runner.memory_engine
        add_memory = memory.add_memory
        calls = []

        def record_memory(agent_id, content, metadata=None):
            calls.append((agent_id, content))
            return add_memory(agent_id, content, metadata)

        memory.add_memory = record_memory
        try:
            pre_year(hook, year, env, agents)
        finally:
            memory.add_memory = add_memory
        for agent_id, agent in hook.sim.agents.items():
            if agent.relocated:
                continue
            capture["households"][(year, agent_id)] = {
                "damaged": agent.flood_history[-1],
                "event": agent._flood_year_record[year]["event_line"],
                "recall": [line for owner, line in calls
                           if owner == agent_id and line.startswith("Suddenly recalled:")],
            }

    def record_social(hub, agent_id, agents, max_gossip=2):
        # Observe the real retrievals without extra reads or synthetic memories.
        neighbor_ids = hub.graph.get_neighbors(agent_id)
        retrieve = hub.memory_engine.retrieve
        candidates = []
        retrievals = 0

        def record_retrieve(neighbor, *args, **kwargs):
            nonlocal retrievals
            memories = retrieve(neighbor, *args, **kwargs)
            if retrievals < len(neighbor_ids):
                items = (memories.get("episodic", []) or memories.get("semantic", [])
                         if isinstance(memories, dict) else memories)
                if items:
                    latest = items[0]
                    content = latest.get("content", str(latest)) if isinstance(latest, dict) else str(latest)
                    candidates.append((neighbor.id, content))
            retrievals += 1
            return memories

        hub.memory_engine.retrieve = record_retrieve
        try:
            result = social(hub, agent_id, agents, max_gossip)
        finally:
            hub.memory_engine.retrieve = retrieve
        key = decision_year, agent_id
        capture["gossip_inputs"].setdefault(key, []).append(tuple(sorted(candidates)))
        capture["gossip"].setdefault(key, []).append(list(result["gossip"]))
        return result

    def record_context(builder, agent_id, **kwargs):
        nonlocal decision_year, last_context_key
        decision_year = kwargs["env_context"]["current_year"]
        assert builder.sim.current_year == decision_year
        try:
            context = build(builder, agent_id, **kwargs)
        finally:
            decision_year = None
        key = builder.sim.current_year, agent_id
        capture["context_gossip"][key] = [
            line for line in context["local"]["social"]
            if line.startswith("Neighbor ") and " mentioned: " in line
        ]
        # The option order is read from the prompt the model receives (see
        # mock_reply), not from the builder's map: the broker rewrites the
        # options text after build in fixed registry order.
        last_context_key = key
        return context

    def controlled_action(sim, approved):
        # Hold every household's decisions constant except this year-2 action.
        skill = "relocate" if relocate and approved.agent_id == "Agent_1" and sim.current_year == 2 else "do_nothing"
        capture["actions"][(sim.current_year, approved.agent_id)] = skill
        return execute(sim, SimpleNamespace(agent_id=approved.agent_id, skill_name=skill))

    def mock_reply(prompt):
        if "You are a Reflection Assistant" in prompt:
            agent_id = re.search(r"Agent_\d+", prompt).group(0)
            reply = {agent_id: "I learned to review flood protection each year."}
        else:
            block = prompt.split("Now, choose one of the following actions:", 1)[1].split("\nNote:", 1)[0]
            capture["options"][last_context_key] = [line.strip() for line in block.strip().splitlines()]
            choice = re.search(r"(?m)^(\d+)\. Do nothing", prompt).group(1)
            reply = {"threat_appraisal": "M", "coping_appraisal": "M", "decision": choice}
        return json.dumps(reply), LLMStats(retries=0, success=True)

    with monkeypatch.context() as patch:
        import broker.utils.llm_utils as llm_utils
        patch.setattr(llm_utils, "create_llm_invoke", lambda *args, **kwargs: mock_reply)
        patch.setattr(rf, "_flood_random_stream", record_stream)
        patch.setattr(rf.ResearchSimulation, "advance_year", record_year)
        patch.setattr(rf.FinalParityHook, "pre_year", record_events)
        patch.setattr(rf.FinalContextBuilder, "build", record_context)
        patch.setattr(rf.InteractionHub, "get_social_context", record_social)
        patch.setattr(rf.ResearchSimulation, "execute_skill", controlled_action)
        rf.run_parity_benchmark(
            # Eight households leave some four-neighbor rings unaffected by
            # Agent_1's changed memories, so gossip comparisons are non-vacuous.
            model="mock", years=years, agents_count=8, workers=1, seed=seed,
            flood_mode="prob", governance_mode="strict" if arm == "silent" else arm,
            retry_feedback_mode="silent" if arm == "silent" else None, shuffle_skills=True,
            custom_output=str(output),
        )
    capture["manifest"] = json.loads((output / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    return capture


@pytest.fixture(scope="module")
def paired_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("keyed_flood")
    with pytest.MonkeyPatch.context() as patch:
        return [
            _mock_run(patch, root / "baseline", seed=42, relocate=False),
            _mock_run(patch, root / "relocated", seed=42, relocate=True),
            _mock_run(patch, root / "disabled", seed=42, relocate=True, arm="disabled"),
            _mock_run(patch, root / "silent", seed=42, relocate=True, arm="silent"),
            _mock_run(patch, root / "repeat", seed=42, relocate=False),
            _mock_run(patch, root / "different", seed=43, relocate=False),
        ]


@pytest.mark.parametrize("arm_index", [1, 2, 3], ids=["strict", "disabled", "silent"])
def test_mock_relocation_does_not_shift_other_households(paired_runs, arm_index):
    baseline, relocated = paired_runs[0], paired_runs[arm_index]
    assert relocated["actions"][(2, "Agent_1")] == "relocate"
    assert baseline["actions"][(2, "Agent_1")] == "do_nothing"
    assert (3, "Agent_1") not in relocated["households"]
    assert baseline["years"] == relocated["years"]
    for key, value in baseline["draws"].items():
        if key[1] != "Agent_1":
            assert relocated["draws"][key] == value
    households = {household for _, household in baseline["households"]} - {"Agent_1"}
    for year in range(3, 11):
        for household in households:
            key = year, household
            assert baseline["households"][key] == relocated["households"][key]
            assert baseline["options"][key] == relocated["options"][key]
    assert any(row["recall"] for key, row in baseline["households"].items() if key[0] > 2)
    assert any(row["damaged"] for key, row in baseline["households"].items() if key[0] > 2)
    assert {purpose for _, _, purpose in baseline["draws"]} == {
        "flood_event", "grant", "damage", "recall", "options", "gossip"}
    assert baseline["options"] and all(baseline["options"].values())
    assert all(re.match(r"^\d+\. ", line) for lines in baseline["options"].values() for line in lines)


def test_mock_runs_repeat_and_change_with_seed(paired_runs):
    baseline, repeat, different = paired_runs[0], paired_runs[-2], paired_runs[-1]
    for field in ("years", "households", "options", "actions", "draws",
                  "gossip", "gossip_inputs", "context_gossip"):
        assert baseline[field] == repeat[field]
    assert baseline["years"] != different["years"]
    assert baseline["households"] != different["households"]
    # The model-facing option order does not change with the seed: the broker
    # writes the options in fixed registry order, so --shuffle-skills does not
    # reach the prompt (reported 2026-10-14; not changed here).
    assert baseline["options"] == different["options"]


@pytest.mark.parametrize("arm_index", [1, 2, 3], ids=["strict", "disabled", "silent"])
def test_mock_relocation_preserves_gossip_with_identical_inputs(paired_runs, arm_index):
    baseline, relocated = paired_runs[0], paired_runs[arm_index]
    households = {household for _, household in baseline["households"]} - {"Agent_1"}
    for year in range(3, 11):
        compared = 0
        for household in households:
            key = year, household
            if baseline["gossip_inputs"][key] == relocated["gossip_inputs"][key]:
                assert baseline["gossip"][key] == relocated["gossip"][key]
                assert baseline["context_gossip"][key] == relocated["context_gossip"][key]
                assert any(len(candidates) > 2 for candidates in baseline["gossip_inputs"][key])
                compared += 1
        # Require real comparisons in every later year, rather than a vacuous pass.
        assert compared > 0, f"No identical gossip inputs in year {year}"


def test_mock_gossip_streams_use_current_decision_year(paired_runs):
    for run in paired_runs:
        assert {year for year, _ in run["gossip"]} == set(range(1, 11))
        for (year, household), calls in run["gossip"].items():
            assert (year, household, "gossip") in run["draws"]
            assert calls[-1] == run["context_gossip"][(year, household)]
            assert run["draws"][(year, household, "gossip")] == rf._flood_random_stream(
                run["manifest"]["seed"], year, "gossip", household
            ).random()


def test_mock_run_manifest_records_stream_scheme_and_seed(paired_runs):
    for run, seed in zip(paired_runs, (42, 42, 42, 42, 42, 43)):
        assert run["manifest"]["seed"] == seed
        assert run["manifest"]["random_streams"] == "keyed_per_year_household"
    assert paired_runs[3]["manifest"]["retry_feedback_mode"] == "silent"


def test_omitted_run_seed_is_resolved_once_and_recorded(tmp_path, monkeypatch):
    run = _mock_run(monkeypatch, tmp_path / "generated_seed", seed=None, relocate=False, years=2)
    seed = run["manifest"]["seed"]
    assert isinstance(seed, int) and 0 <= seed <= 1000000
    assert run["manifest"]["random_streams"] == "keyed_per_year_household"
    for (year, household, purpose), value in run["draws"].items():
        assert value == rf._flood_random_stream(seed, year, purpose, household).random()


def test_stream_key_casts_and_refuses_missing_seed():
    assert rf._flood_random_stream("42", 3, "damage", "Agent_2").random() == \
        rf._flood_random_stream(42, 3, "damage", "Agent_2").random()
    with pytest.raises(ValueError, match="seed is None"):
        rf._flood_random_stream(None, 3, "damage", "Agent_2")


def test_aborted_run_still_records_stream_scheme(tmp_path, monkeypatch):
    """An abort mid-run must leave the draw-scheme marker in the manifest."""
    pre_year = rf.FinalParityHook.pre_year

    def failing_pre_year(hook, year, env, agents):
        if year == 2:
            raise RuntimeError("abort in year 2 (test)")
        return pre_year(hook, year, env, agents)

    def mock_reply(prompt):
        if "You are a Reflection Assistant" in prompt:
            agent_id = re.search(r"Agent_\d+", prompt).group(0)
            reply = {agent_id: "I learned to review flood protection each year."}
        else:
            choice = re.search(r"(?m)^(\d+)\. Do nothing", prompt).group(1)
            reply = {"threat_appraisal": "M", "coping_appraisal": "M", "decision": choice}
        return json.dumps(reply), LLMStats(retries=0, success=True)

    import broker.utils.llm_utils as llm_utils
    monkeypatch.setattr(llm_utils, "create_llm_invoke", lambda *args, **kwargs: mock_reply)
    monkeypatch.setattr(rf.FinalParityHook, "pre_year", failing_pre_year)
    out = tmp_path / "aborted"
    with pytest.raises(Exception):
        rf.run_parity_benchmark(model="mock", years=4, agents_count=4, workers=1, seed=7,
                                custom_output=str(out))
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == 7
    assert manifest["random_streams"] == "keyed_per_year_household"
