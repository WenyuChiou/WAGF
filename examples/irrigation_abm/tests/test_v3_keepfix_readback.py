"""Offline read-back checks added by the item-47 round-2 review."""

import json
from types import SimpleNamespace

from examples.irrigation_abm.analysis import v3_metrics as vm
from examples.irrigation_abm.irrigation_personas import K6_SENIOR_TIER_TEXT
from examples.irrigation_abm.validators import irrigation_validators as validators


def test_menu_increase_target_uses_the_printed_option_one_value():
    prompt = (
        "If you increase your request to about 26,879 acre-ft, you can expect full delivery this year.\n"
        "1. Increase your request to about 26,878 acre-ft: the 20,001 acre-ft you received last year "
        "plus your typical step of about 6,877 acre-ft.\n"
        "2. Keep your request."
    )
    assert vm._menu_increase_target(prompt) == 26878
    assert vm._s1_increase_target(prompt) == 26879


def test_keepfix_context_settles_at_menu_rounded_target(monkeypatch):
    settled_targets = []

    class FakeEnv:
        def __init__(self, _cfg):
            self.agent_ids = ["A"]
            self._agents = {"A": {}}
            self._mead_storage = [0.0]

        def initialize_from_profiles(self, _profiles):
            pass

        def advance_year(self):
            self._snapshot = object()

        def get_agent_context(self, _agent):
            return {"current_request": 100.6, "water_right": 200.4}

        def get_agent_state(self, _agent):
            return {}

        def _settle(self, _snapshot, *, requests):
            settled_targets.append(requests["A"])
            return {"agents": {"A": {"delivered": requests["A"]}}}

    monkeypatch.setattr(vm, "IrrigationEnvironment", FakeEnv)
    monkeypatch.setattr(validators, "supply_rule_fields", lambda _ctx, _state: {})
    sim = SimpleNamespace(
        agents=["A"],
        system={1: {"powell_storage_maf": 1.0, "mead_storage_maf": 2.0}},
        num=lambda _agent, _tick, _field: 10.6,
    )
    checker = vm.PromptChecker.__new__(vm.PromptChecker)
    checker.cfg = vm.WaterSystemConfig()
    checker.profiles = {"A": SimpleNamespace(agent_id="A")}
    checker._contexts = {}
    checker.run = SimpleNamespace(
        info=SimpleNamespace(manifest={"seed": 42}), sim=sim,
        decisions={("A", 1): SimpleNamespace(keep_request_af=100.6)},
        traces={("A", 1): SimpleNamespace(menu=("increase", "keep"))},
    )
    assert checker._keepfix_context("A", 1)["increase_request_af"] == 112
    assert settled_targets == [112]


def test_disabled_keepfix_text_detects_k6_persona_and_table_cells():
    prompt = "\n".join([
        "The more water you receive, up to what your fields can use, the more you can produce.",
        K6_SENIOR_TIER_TEXT,
        "Year | request (AF) | received (AF) | Lake Mead on 1 January (vs a year earlier)",
        "  2019 | 1,000 | 1,000 | higher",
    ])
    assert vm._disabled_keepfix_text(prompt, {"L": False, "K6": False, "table": False}) == [
        "land-bound persona clause while L is off",
        "K6 while K6 is off",
        "item-47 table heading while table is off",
        "item-47 table cell while table is off",
    ]


def test_land_numeric_line_is_rejected_when_only_L_is_off():
    # Realistic independent-toggle tamper: another enabled element can cause
    # profiles to be loaded, but that must not authorize L's numeric sentence.
    prompt = "\n".join([
        "The more water you receive, the more you can produce.",
        "Your fields can use about 28,295 acre-ft of water a year: that is the most water you "
        "have diverted in any year from 1971 to 2018. Water beyond that would have no fields "
        "to irrigate. Last year's delivery was 100% of that amount.",
    ])
    package = {"L": False, "S1": True, "K6": True, "table": True}
    assert vm._disabled_keepfix_text(prompt, package) == [
        "land-need numeric line while L is off"]


class _FakeSim:
    sim_start_year = 2019
    basin = {"senior": "lower_basin"}

    def __init__(self):
        self.rows = {
            ("senior", 1): {
                "request": "100", "diversion": "100", "base_af": "100",
                "shortage_tier": "0", "magnitude_pct": "",
            },
            ("senior", 2): {
                "request": "100", "diversion": "80", "base_af": "100",
                "shortage_tier": "0", "magnitude_pct": "",
            },
            ("senior", 3): {"memory": ""},
        }

    def num(self, agent, tick, field):
        return float(self.rows[(agent, tick)][field])

    def opt_num(self, agent, tick, field):
        value = self.rows[(agent, tick)].get(field, "")
        return None if value == "" else float(value)


def _visibility_run():
    routine = "Year 2019: You kept your request at 100 acre-ft and received 100 acre-ft."
    eventful = "Year 2020: You kept your request at 100 acre-ft and received 80 acre-ft."
    sim = _FakeSim()
    sim.rows[("senior", 3)]["memory"] = routine + " | " + eventful
    decisions = {
        ("senior", 1): SimpleNamespace(
            executed_skill="maintain_demand", execution_path="approved", aborted=False),
        ("senior", 2): SimpleNamespace(
            executed_skill="maintain_demand", execution_path="approved", aborted=False),
    }
    run = SimpleNamespace(
        label="fake", sim=sim, decisions=decisions,
        info=SimpleNamespace(manifest={
            "keepfix_package": {"MB": True, "routine_tier_scope": "affects_agent"},
            "coupling_retrofit_metadata": {"water_system_lb_priority_mode": "split"},
        }),
    )
    return run, routine, eventful


def test_memory_visibility_matches_unfiltered_log_and_routine_scope():
    run, routine, eventful = _visibility_run()
    priority = {"senior": {"junior_entitlement_af": 0}}
    prompt = "Your memory includes:\n- " + eventful
    assert vm._memory_visibility_mismatches(run, "senior", 3, prompt, priority) == []
    bad = "Your memory includes:\n- " + routine
    problems = vm._memory_visibility_mismatches(run, "senior", 3, bad, priority)
    assert any("routine outcome is visible" in problem for problem in problems)
    assert any("eventful outcome is missing" in problem for problem in problems)


def test_memory_visibility_honours_recorded_tier_scope_and_split_membership():
    run, tier_year, short_year = _visibility_run()
    run.sim.rows[("senior", 1)]["shortage_tier"] = "1"
    senior = {"senior": {"junior_entitlement_af": 0}}
    junior = {"senior": {"junior_entitlement_af": 10}}

    # Under affects_agent the senior tier-year line is routine and hidden.
    prompt = "Your memory includes:\n- " + short_year
    assert vm._memory_visibility_mismatches(run, "senior", 3, prompt, senior) == []

    # any_tier and a split-mode junior holder both make that same line eventful.
    both = "Your memory includes:\n- " + tier_year + "\n- " + short_year
    run.info.manifest["keepfix_package"]["routine_tier_scope"] = "any_tier"
    assert vm._memory_visibility_mismatches(run, "senior", 3, both, senior) == []
    run.info.manifest["keepfix_package"]["routine_tier_scope"] = "affects_agent"
    assert vm._memory_visibility_mismatches(run, "senior", 3, both, junior) == []


def test_memory_visibility_treats_rejected_default_as_runtime_fallback():
    run, fallback_year, short_year = _visibility_run()
    run.decisions[("senior", 1)].execution_path = "rejected_default"
    visible = "Your memory includes:\n- " + fallback_year + "\n- " + short_year
    priority = {"senior": {"junior_entitlement_af": 0}}
    assert vm._memory_visibility_mismatches(run, "senior", 3, visible, priority) == []


def test_memory_visibility_first_year_uses_initial_base_when_no_previous_year():
    run, first_year, short_year = _visibility_run()
    assert run.sim.rows[("senior", 1)]["base_af"] == "100"
    assert vm._memory_visibility_mismatches(
        run, "senior", 3,
        "Your memory includes:\n- " + short_year,
        {"senior": {"junior_entitlement_af": 0}},
    ) == []
    run.sim.rows[("senior", 1)]["base_af"] = "99"
    problems = vm._memory_visibility_mismatches(
        run, "senior", 3,
        "Your memory includes:\n- " + first_year + "\n- " + short_year,
        {"senior": {"junior_entitlement_af": 0}},
    )
    assert problems == []  # request != initial base makes year 1 eventful


def _reflection_run(tmp_path, *, with_input):
    prompt = (
        "Your memory includes:\n"
        "- Consolidated Reflection (written in 2019): I used 999 acre-ft.\n"
    )
    checks = {
        "agent_id": "A", "period": 2019, "outcome": "stored",
        "reflection_input": ["Year 2019: you asked for 100 acre-ft and received 100 acre-ft."],
    }
    if not with_input:
        checks.pop("reflection_input")
    (tmp_path / "reflection_checks.jsonl").write_text(json.dumps(checks) + "\n", encoding="utf-8")
    sim = SimpleNamespace(sim_start_year=2019, sim_year=lambda tick: 2018 + tick)
    trace = SimpleNamespace(prompt=prompt, crashed=False)
    return SimpleNamespace(
        label="fake", sim=sim, traces={("A", 2): trace},
        info=SimpleNamespace(path=tmp_path, manifest={"keepfix_package": {"MB": True}}),
    )


def test_reflection_checks_use_recorded_reflection_input(tmp_path):
    result = vm.reflection_checks(_reflection_run(tmp_path, with_input=True))
    assert result["foreign_figure_reflections"] == 1
    assert result["reflection_inputs_read"] == 1
    assert result["reflection_input_check_skipped"] == 0


def test_reflection_checks_explicitly_skip_missing_input_under_mb(tmp_path):
    result = vm.reflection_checks(_reflection_run(tmp_path, with_input=False))
    assert result["foreign_figure_reflections"] == 0
    assert result["reflection_input_check_skipped"] == 1
    assert "MB hides decision-memory lines" in result["reflection_input_skip_reason"]
