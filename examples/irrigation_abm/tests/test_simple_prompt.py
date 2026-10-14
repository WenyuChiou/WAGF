"""Pre-registered simple information level; model calls are scripted only."""
import json
import re
from types import SimpleNamespace

import pytest
import yaml

from examples.irrigation_abm import run_experiment as runner
from examples.irrigation_abm.irrigation_personas import (
    DECREASE_STEP_NOTE, INCREASE_STEP_NOTE, OPTION_STEP_NOTE,
    build_action_outcome_feedback, build_option_notes, build_water_situation_text,
)
from examples.irrigation_abm.tests.test_v3_prompt import (
    CONFIG, ScriptedLLM, _lb_ctx, _run, _ub_ctx,
    PERSONA_TEXTS, UT2,
)
from examples.irrigation_abm.analysis.simple_prompt_check import (
    REMOVED_SENTENCE_FAMILIES, check_run, main as check_main, scan_text,
)

IRR = CONFIG.parent.parent
VARIANTS = IRR / "config_variants"


def _config():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _simple_config():
    cfg = _config()
    farmer = cfg["irrigation_farmer"]
    farmer["prompt_information"] = "simple"
    for key in ("S1", "L", "K6", "table"):
        farmer["keepfix_package"][key] = False
    farmer["feedback"]["dashboard_format"] = "none"
    farmer["feedback"]["tracked_metrics"] = []
    return cfg


@pytest.mark.parametrize("key", ["S1", "L", "K6", "table"])
def test_simple_rejects_full_information_flags(key):
    cfg = _simple_config()
    cfg["irrigation_farmer"]["keepfix_package"][key] = True
    with pytest.raises(ValueError, match=rf"keepfix_package\.{key}"):
        runner._validate_prompt_information_config(cfg)


@pytest.mark.parametrize("format", ["table", "summary", "unknown"])
def test_simple_rejects_a_dashboard_that_can_render(format):
    cfg = _simple_config()
    cfg["irrigation_farmer"]["feedback"]["dashboard_format"] = format
    cfg["irrigation_farmer"]["feedback"]["tracked_metrics"] = _config()["irrigation_farmer"]["feedback"]["tracked_metrics"]
    with pytest.raises(ValueError, match="feedback"):
        runner._validate_prompt_information_config(cfg)


@pytest.mark.parametrize("value", ["unknown", "", None, True, ["simple"]])
def test_prompt_information_rejects_unknown_values(value):
    cfg = _config()
    cfg["irrigation_farmer"]["prompt_information"] = value
    with pytest.raises(ValueError, match=r"irrigation_farmer\.prompt_information"):
        runner._validate_prompt_information_config(cfg)


def test_absent_level_is_full_and_simple_is_explicit():
    assert runner._validate_prompt_information_config(_config()) == "full"
    cfg = _config()
    cfg["irrigation_farmer"]["prompt_information"] = "full"
    assert runner._validate_prompt_information_config(cfg) == "full"
    assert runner._validate_prompt_information_config(_simple_config()) == "simple"


@pytest.mark.parametrize("show_trend,assertions", [(True, []), (False, [{"when": "1", "message": "warning"}])])
def test_simple_none_dashboard_still_rejects_trends_and_warnings(show_trend, assertions):
    cfg = _simple_config()
    feedback = cfg["irrigation_farmer"]["feedback"]
    feedback.update(tracked_metrics=[{"name": "request"}], show_trend=show_trend, assertions=assertions)
    with pytest.raises(ValueError, match="feedback"):
        runner._validate_prompt_information_config(cfg)


@pytest.mark.parametrize("junior", [False, True])
def test_simple_tier_status_only_for_senior_and_junior(junior):
    ctx = _lb_ctx(0.8, tier=2, lb_junior_tier_cut_fraction=0.25,
                  year=2029, lake_mead_level=1050,
                  lb_junior_entitlement_af=40_000.0 if junior else 0.0)
    text = build_water_situation_text(ctx, prompt_information="simple")
    assert text.splitlines() == [
        "It is now the year 2029. You divert water in the Lower Colorado River Basin.",
        "Lake Mead was at 1,050 feet above sea level on 1 January (rising from last year).",
        "A Tier 2 Lower Basin shortage applies this year (Lake Mead was below 1,050 feet on 1 January).",
        "In 2028 you diverted 100,000 acre-ft.",
    ]


def test_simple_short_past_year_has_no_reason():
    text = build_water_situation_text(
        _lb_ctx(0.8), {"request": 100_000, "diversion": 80_000,
                       "gap_reason": "lb_mead_availability"},
        prompt_information="simple")
    assert text.splitlines()[-1] == (
        "Last year you requested 100,000 acre-ft and received 80,000 acre-ft (80.0% delivered).")
    assert len(text.splitlines()) == 4


@pytest.mark.parametrize("subbasin", [True, False])
def test_simple_upper_water_signal_without_flow(subbasin):
    ctx = _ub_ctx(ub_subbasin_flow_share=0.7, natural_flow_maf=12.3)
    if not subbasin:
        ctx["supply_group"] = None
        ctx["ub_subbasin_flow_share"] = None
    text = build_water_situation_text(ctx, prompt_information="simple")
    assert len(text.splitlines()) == 3
    assert "Winter precipitation" in text
    assert "natural flow" not in text.lower()
    assert "water right" not in text.lower()


@pytest.mark.parametrize("increase,decrease,expected", [
    (True, True, OPTION_STEP_NOTE), (True, False, INCREASE_STEP_NOTE),
    (False, True, DECREASE_STEP_NOTE), (False, False, ""),
])
def test_simple_option_notes_only_random_step(increase, decrease, expected):
    text = build_option_notes(increase, decrease, {"request": 100_000, "diversion": 80_000},
                              floor_af=10_000, floor_share=0.1,
                              prompt_information="simple")
    assert text == ("\n" + expected if expected else "")


@pytest.mark.parametrize("basin,signal", [
    ("lower_basin", "On 1 January that year Lake Mead was lower than a year earlier."),
    ("upper_basin", "That winter's precipitation in your sub-basin was below the previous winter's."),
])
def test_simple_memory_preserves_outcomes_and_keep_change(basin, signal):
    text = build_action_outcome_feedback(
        {"skill_name": "maintain_demand"}, 2029, 80_000, 64_000, 0,
        basin=basin, gap_reason="because a removed allocation reason",
        flow_share=0.7, previous_request=100_000, previous_diversion=80_000,
        prompt_information="simple")
    assert text == (
        "Year 2029: You chose to maintain demand, so your request fell from 100,000 acre-ft "
        "to the 80,000 acre-ft you received the year before. You requested 80,000 acre-ft "
        "and received 64,000 acre-ft. Shortfall: 16,000 acre-ft (20.0% unmet). " + signal)


@pytest.mark.parametrize("variant", ["simple", "simple_nolimit"])
def test_variant_exact_overrides_and_frozen_copies(variant):
    expected = _simple_config()
    expected['irrigation_farmer']['prompt_template_file'] = 'prompts/irrigation_farmer.txt'
    if variant == "simple_nolimit":
        expected["irrigation_farmer"]["beneficial_use_limit"]["enabled"] = False
    directory = VARIANTS / variant
    actual = yaml.safe_load((directory / "agent_types.yaml").read_text(encoding="utf-8"))
    assert actual == expected
    from broker.tools.validate_prompt import resolve_prompt_path
    assert resolve_prompt_path(directory / 'agent_types.yaml',
                               actual['irrigation_farmer']['prompt_template_file']) == (
                                   directory / 'prompts/irrigation_farmer.txt').resolve()
    default = CONFIG.parent
    assert {str(p.relative_to(directory)) for p in directory.rglob("*")
            if p.is_file() and p.name != 'NOTES.md'} == {
        str(p.relative_to(default)) for p in default.rglob("*") if p.is_file()}
    for path in default.rglob("*"):
        if path.is_file() and path.name not in ("agent_types.yaml", "irrigation_farmer.txt"):
            assert (directory / path.relative_to(default)).read_bytes() == path.read_bytes()


@pytest.fixture(scope="module")
def simple_runs(tmp_path_factory):
    runs = {}
    original = runner.IrrigationLifecycleHooks.pre_year
    for variant in ("simple", "simple_nolimit"):
        for mode in ("strict", "disabled"):
            contexts, profiles = {}, {}

            def capture(hooks, year, env_state, agents):
                original(hooks, year, env_state, agents)
                profiles.update(hooks.profiles)
                contexts.update({(aid, year): dict(hooks.env.get_agent_context(aid)) for aid in agents})

            llm = ScriptedLLM(lambda agent, year, attempt: ("M", "M", "Keep"))
            out = tmp_path_factory.mktemp(f"{variant}_{mode}") / "run"
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(runner.IrrigationLifecycleHooks, "pre_year", capture)
                _run(mp, out, llm, "--real", "--years", "4", "--seed", "42", "--memory-seed", "42",
                     "--governance-mode", mode, "--config-dir", str(VARIANTS / variant))
            runs[(variant, mode)] = SimpleNamespace(out=out, llm=llm, contexts=contexts, profiles=profiles)
    return runs


@pytest.mark.parametrize("variant,mode", [
    ("simple", "strict"), ("simple", "disabled"),
    ("simple_nolimit", "strict"), ("simple_nolimit", "disabled"),
])
def test_simple_four_year_runs_are_clean_and_recorded(simple_runs, variant, mode):
    run = simple_runs[(variant, mode)]
    assert len(run.llm.decisions) >= 78 * 4
    assert len(run.llm.reflections) == 78 * 4
    result = check_run(run.out)
    assert result.readable_prompts >= len(run.llm.decisions) + len(run.llm.reflections)
    assert result.occurrences == ()
    assert check_main([str(run.out)]) == 0
    for (agent, year, attempt), text in run.llm.decisions.items():
        if attempt == 0:
            assert scan_text(text) == ()
        else:
            original = run.llm.decisions[(agent, year, 0)]
            assert text.endswith(original)
            # Retry feedback is unchanged by design and audited separately.
            scan_text(text[:-len(original)])
    for text in run.llm.reflections:
        assert scan_text(text) == ()
    records = [json.loads(line) for line in (run.out / "reflection_prompts.jsonl").read_text().splitlines()]
    assert [row["prompt"] for row in records] == run.llm.reflections
    assert all(2019 <= row["year"] <= 2022 for row in records)
    manifest = json.loads((run.out / "reproducibility_manifest.json").read_text())
    assert manifest["prompt_information"] == "simple"
    assert manifest["keepfix_package"]["MB"] is True
    snapshot = yaml.safe_load((run.out / "config_snapshot.yaml").read_text())
    assert snapshot["metadata"]["prompt_information"] == "simple"
    assert snapshot["irrigation_farmer"]["prompt_information"] == "simple"
    assert snapshot["irrigation_farmer"]["beneficial_use_limit"]["enabled"] is (variant == "simple")


@pytest.mark.parametrize("agent", ["WelltonMohawkIDD", UT2])
def test_simple_full_golden_prompt_from_fixture_numbers(simple_runs, agent):
    """Build the entire expected first-year prompt without calling text builders."""
    from examples.irrigation_abm.irrigation_personas import hy_threshold_af, resolve_step_bin_af

    run = simple_runs[("simple", "strict")]
    profile, ctx = run.profiles[agent], run.contexts[(agent, 1)]
    actual = run.llm.decisions[(agent, 2019, 0)]
    upper = profile.basin == "upper_basin"
    basin = "Upper" if upper else "Lower"
    persona = (f"You are {agent}, an agricultural water user (an irrigation district, a tribal water user, "
               f"or a group of water users) in the {basin} Basin of the Colorado River, holding a water "
               f"right of {profile.water_right:,.0f} acre-ft/year. The more water you receive, the more you can produce.")
    if upper:
        persona += " All volumes shown to you are consumptive use."
    persona += " " + PERSONA_TEXTS[profile.cluster]
    year = ctx["year"]
    lines = [persona, f"It is now the year {year}. You {'use' if upper else 'divert'} water in the {basin} Colorado River Basin."]
    if upper:
        where = "in your sub-basin" if ctx["supply_group"] is not None else "averaged over the Upper Basin"
        lines.append(f"Winter precipitation {where} this year was {ctx['precipitation']:.0f} mm "
                     f"({'above' if ctx['preceding_factor'] else 'below'} last year).")
    else:
        assert ctx["shortage_tier"] == 0
        lines.extend([f"Lake Mead was at {ctx['lake_mead_level']:,.0f} feet above sea level on 1 January "
                      f"({'rising' if ctx['preceding_factor'] else 'declining'} from last year).",
                      "No Lower Basin shortage applies this year."])
    base = round(ctx["current_request"])
    step = round(hy_threshold_af(profile.mu, profile.sigma,
                                resolve_step_bin_af(profile.step_bin_af, profile.bin_size_af, profile.water_right)))
    floor = round(profile.water_right * 0.1)
    limit = round(ctx["beneficial_use_limit_af"])
    increase = (f"Increase your request to about {min(base + step, limit):,.0f} acre-ft: the {base:,.0f} acre-ft "
                f"you received last year plus your typical step of about {step:,.0f} acre-ft")
    if base + step > limit:
        increase += f" (it stops at {limit:,.0f} acre-ft, about the most water your fields can use)"
    increase += "."
    decrease = (f"Decrease your request to about {max(base - step, floor):,.0f} acre-ft: the {base:,.0f} acre-ft "
                f"you received last year minus your typical step of about {step:,.0f} acre-ft")
    if base - step < floor:
        decrease += f" (the minimum-use floor stops it at {floor:,.0f} acre-ft)"
    decrease += "."
    options = {"Increase": increase, "Keep": f"Keep your request at {base:,.0f} acre-ft, the amount you received last year.",
               "Decrease": decrease}
    # Menu order is randomized independently of the information level. Only
    # IDs/directions come from the fixture; every option sentence is assembled above.
    menu = re.findall(r"^(\d+)\. (Increase|Keep|Decrease) your request", actual, flags=re.M)
    ids = [number for number, _ in menu]
    choices = ", ".join(ids[:-1]) + ", or " + ids[-1]
    directions = {direction for _, direction in menu}
    note = (OPTION_STEP_NOTE if {"Increase", "Decrease"} <= directions else
            INCREASE_STEP_NOTE if "Increase" in directions else DECREASE_STEP_NOTE)
    lines.extend([f"In {year - 1} you {'used' if upper else 'diverted'} {base:,.0f} acre-ft.",
                  "Your memory includes:", "No memories yet.", "",
                  "First, rate your water_scarcity_assessment: is your water supply abundant (VL), adequate (L), tight (M), scarce (H), or very scarce (VH) this year?",
                  "Next, rate your adaptive_capacity_assessment: how much can you change your request this year?", "",
                  "Now, choose one of the following water management actions:"])
    lines.extend(f"{number}. {options[direction]}" for number, direction in menu)
    lines.extend([note, "", "### RATING SCALE (You MUST use EXACTLY one of these codes):",
                  "VL = Very Low | L = Low | M = Medium | H = High | VH = Very High", "", "",
                  "Please respond using the EXACT JSON format below.",
                  "- Use EXACTLY one of: VL, L, M, H, VH for each appraisal label.",
                  f'- "decision" MUST be the NUMERIC ID ({choices}) from the options list.',
                  "- Ensure all keys match the format exactly.", "<<<DECISION_START>>>", "{",
                  '  "reasoning": "Explain your thought process in 2-3 sentences BEFORE making a decision.",',
                  '  "water_scarcity_assessment": {"label": "VL/L/M/H/VH", "reason": "One sentence on whether your water supply is abundant, adequate, tight, scarce, or very scarce."},',
                  '  "adaptive_capacity_assessment": {"label": "VL/L/M/H/VH", "reason": "One sentence on how well you can adapt your water use."},',
                  f'  "decision": "<Numeric ID, choose ONE from: {choices}>"', "}", "<<<DECISION_END>>>", ""])
    assert actual == "\n".join(lines)


def test_simple_rejects_full_template_before_model_call(tmp_path, monkeypatch):
    import shutil

    directory = tmp_path / "mixed"
    shutil.copytree(VARIANTS / "simple", directory)
    shutil.copyfile(CONFIG.parent / "prompts/irrigation_farmer.txt", directory / "prompts/irrigation_farmer.txt")
    llm = ScriptedLLM(lambda agent, year, attempt: ("M", "M", "Keep"))
    with pytest.raises(ValueError, match="prompt_information"):
        _run(monkeypatch, tmp_path / "run", llm, "--years", "1", "--config-dir", str(directory))
    assert not llm.decisions and not llm.reflections


def test_default_mock_run_exercises_every_removed_family(tmp_path, monkeypatch):
    from examples.irrigation_abm.irrigation_env import IrrigationEnvironment

    original = IrrigationEnvironment.initialize_from_profiles

    def at_floor(env, profiles):
        for profile in profiles:
            if profile.agent_id == "WelltonMohawkIDD":
                profile.actual_2018_diversion = profile.water_right * env.config.min_utilisation_fraction
        return original(env, profiles)

    monkeypatch.setattr(IrrigationEnvironment, "initialize_from_profiles", at_floor)
    llm = ScriptedLLM(lambda agent, year, attempt: ("M", "M", "Keep" if agent == "WelltonMohawkIDD" else "Increase"))
    out = _run(monkeypatch, tmp_path / "default", llm, "--real", "--years", "6", "--seed", "42", "--memory-seed", "42",
               "--governance-mode", "disabled")
    result = check_run(out)
    assert {hit.family for hit in result.occurrences} == set(REMOVED_SENTENCE_FAMILIES)
    assert check_main([str(out)]) == 1
    manifest = json.loads((out / "reproducibility_manifest.json").read_text())
    assert manifest["prompt_information"] == "full"


def test_reflection_recorder_captures_retry_bytes(tmp_path):
    seen = []
    hooks = runner.IrrigationLifecycleHooks(SimpleNamespace(), None, [], None, tmp_path)
    invoke = hooks._record_reflection_call(lambda prompt: seen.append(prompt) or "reply", ["A"], 2029)
    assert invoke("base prompt") == "reply"
    assert invoke("base prompt\n\nretry note") == "reply"
    records = [json.loads(line) for line in (tmp_path / "reflection_prompts.jsonl").read_text().splitlines()]
    assert [row["prompt"] for row in records] == seen
    assert [row["attempt"] for row in records] == [0, 1]
