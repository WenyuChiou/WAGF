"""Irrigation case study v3, Work Package 4: prompt, persona, memory,
reflection and retry text.

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md, WP4 (4.1 to
4.8), 2.6 (option texts and the template line) and PI items 8, 9, 11, 15,
19, 21 to 23 and 28; design record section 9 item 1 (WSA anchoring).

Every test here fails on the pre-WP4 code (HEAD 9f4986c4): there the
persona has two random variants per cluster with invented attributes, the
prompt carries the conservation line and the adaptive-capacity hint, the
headline is keyed on a drought index, shares print as "100%" beside a
shortfall, reasons have one tense, memory lines and the dashboard use loop
years and a drought index, the dashboard shows internal flag columns and a
TREND line, reflections are batched and pile up, the placebo closer points
at absent violations, retry reports name skill ids, and a --real run
crashes in the year after the first declared tier (the last-year snapshot
lacked the junior-cut share).

The review round of 2026-09-30 (spec item 29; review items HIGH 1 to LOW
12) changed the persona sentences (cluster tendencies, no superlatives, no
exploration), the WSA anchor words, the Upper Basin sub-basin reason, the
sharing clause, the lines after the options (shown only when they apply),
the Lower Basin text for agents holding junior-priority water, the Lake Mead
number format and the reflection filter (rounding-tolerant, plain numbers
and percentages, and an agent whose new summary is not stored loses its
old one). The tests for those changes fail on the first WP4 version as well.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import threading
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest
import yaml

import broker.utils.llm_utils as llm_utils
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.llm_utils import LLMStats

from examples.irrigation_abm import run_experiment
from examples.irrigation_abm.irrigation_personas import (
    FULL_SUPPLY_RATIO,
    HY2021_CLUSTER_LABELS,
    _UB_GROUP_AGENT_COUNTS,
    _UB_STATE_GROUPS,
    IrrigationAgentProfile,
    build_action_outcome_feedback,
    build_narrative_persona,
    build_option_notes,
    build_water_situation_text,
    dashboard_sharing_flags,
    describe_gap_reason,
    format_share,
)
from examples.irrigation_abm.validators.irrigation_validators import _sharing_sentence

REPO = Path(__file__).resolve().parents[3]
IRR = REPO / "examples" / "irrigation_abm"
CONFIG = IRR / "config" / "agent_types.yaml"
TEMPLATE = IRR / "config" / "prompts" / "irrigation_farmer.txt"
CRSS_PARAMS_CSV = REPO / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
CRSS_DB_DIR = REPO / "ref" / "CRSS_DB" / "CRSS_DB"
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()
needs_ref = pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")

SKILL_IDS = ("increase_demand", "maintain_demand", "decrease_demand")
_LABEL_CODE = re.compile(r"\b(VL|L|M|H|VH)\b")

# Item 36a (2026-10-05 design-basis audit + fix proposals, spec item 36a):
# TWO headline states only, at FULL_SUPPLY_RATIO. The pre-2026-10-05 five
# bands ("slightly short" / "well short" / "critically short ...") are
# retired from the prompt and survive only as analysis.v3_metrics's
# report-only R5A_BANDS.
HEADLINES = {
    "sufficient": "Water supply is sufficient for your full request this year.",
    "short": "Water supply is short of your request this year.",
}

# Spec 4.x test_banned_phrases_absent, plus the task's "no farmer, crop or
# trust sentences", the retired reason wording and drought headline.
BANNED_PHRASES = (
    "conservation practices", "financial", "technolog", "records", "other water users",
    "operational flexibility", "Drought index", "TREND", "[Rule:", "Bureau of Reclamation",
    "Year 1:", "minimum release", "shared by all Lower Basin users",
    "farmer", "crop", "trust", "pro-rata", "adequate but slightly below normal",
    "Full allocation is available", "drought", "\u2014",
)


# ===========================================================================
# a deterministic stand-in for the model, driving the real runner
# ===========================================================================

Script = Callable[[str, int, int], Tuple[Optional[str], str, str]]


class ScriptedLLM:
    """No Ollama. ``script(agent, year, attempt)`` returns ``(wsa, aca,
    choice)``: choice is "Increase" / "Keep" / "Decrease", mapped through the
    menu the prompt shows ("Keep" if absent); wsa None omits the field.
    Reflection calls get one fixed lesson per agent id. Every prompt is kept."""

    LESSON = "I learned to watch my supply before changing my request."

    def __init__(self, script: Script):
        self.script = script
        self.calls: Counter = Counter()
        self.decisions: Dict[Tuple[str, int, int], str] = {}
        self.reflections: List[str] = []
        self._lock = threading.Lock()

    def __call__(self, prompt: str):
        stats = LLMStats(retries=0, success=True)
        if "Lesson Learned" in prompt:
            with self._lock:
                self.reflections.append(prompt)
            ids = re.findall(r"^(.+?) Memories:", prompt, flags=re.M)
            return json.dumps({aid: self.LESSON for aid in ids}), stats
        agent = re.search(r"You are (.+?), an agricultur", prompt).group(1)
        year = int(re.search(r"It is now the year (\d{4})", prompt).group(1))
        with self._lock:
            attempt = self.calls[(agent, year)]
            self.calls[(agent, year)] += 1
            self.decisions[(agent, year, attempt)] = prompt
        menu = {m.group(2): int(m.group(1)) for m in re.finditer(
            r"^(\d+)\. (Increase|Keep|Decrease) your request", prompt, flags=re.M)}
        wsa, aca, choice = self.script(agent, year, attempt)
        payload: Dict[str, Any] = {"reasoning": "Scripted answer."}
        if wsa is not None:
            payload["water_scarcity_assessment"] = {"label": wsa, "reason": "Scripted."}
        payload["adaptive_capacity_assessment"] = {"label": aca, "reason": "Scripted."}
        payload["decision"] = menu.get(choice, menu["Keep"])
        return "<<<DECISION_START>>>\n" + json.dumps(payload) + "\n<<<DECISION_END>>>", stats

    def retry_blocks(self) -> List[Tuple[str, int, int, str]]:
        """(agent, year, attempt, text before the original prompt) for every
        retry; "<SAME>" when the retry IS the original prompt."""
        out = []
        for (agent, year, attempt), prompt in sorted(self.decisions.items()):
            if attempt == 0:
                continue
            original = self.decisions[(agent, year, 0)]
            i = prompt.find(original)
            out.append((agent, year, attempt,
                        "<SAME>" if prompt == original else prompt[:i] if i > 0 else prompt))
        return out


def _run(mp: pytest.MonkeyPatch, out: Path, llm: ScriptedLLM, *args: str) -> Path:
    mp.setattr(run_experiment, "create_llm_invoke", lambda model, verbose=False: llm)
    mp.setattr(llm_utils, "create_llm_invoke", lambda model, verbose=False, overrides=None: llm)
    mp.setattr(sys, "argv", ["run_experiment.py", "--model", "mock", "--output", str(out),
                             "--workers", "1", *args])
    mp.setenv("GOVERNANCE_PROFILE", "strict")
    run_experiment.main()
    AgentTypeConfig.clear_cache()
    return out


UT2 = "UtahUsesAboveGreenRiverConfluence_UtahAgDNRProjects"


def _golden_script(agent: str, year: int, attempt: int):
    """Everyone keeps with a middle appraisal, except UT2, which increases
    every year. Before item 36g (2026-10-05 design-basis audit + fix
    proposals), UT2's water right was min(grid_top, scaled) = 20,000 AF
    (the grid-top term bound for this one agent), and this always-increase
    script reached it exactly at 2033, the one year its own sub-basin
    supply (17,370 AF) was below that old right, demonstrating "at cap,
    no increase on the menu". Item 36g drops the grid-top term, so UT2's
    right is now 1.4 x its observed peak (38,080 AF); its own sub-basin
    supply never lets an always-increasing request grow past the mid-
    20,000s AF (checked out to simulation year 42 / calendar 2060), so
    UT2 no longer reaches its own water right anywhere in the real
    horizon -- the always-increase script still demonstrates sustained
    growth meeting the supply rule repeatedly (2033 is kept as a golden
    year for that reason), but no real agent in this fixture now
    exercises the water-right-cap menu filter; that filter's own
    coverage is test_v3_governance.py::test_menu_parity_at_cap
    (synthetic, basin-agnostic, unaffected by this change)."""
    if agent == UT2:
        return "M", "M", "Increase"
    return "M", "M", "Keep"


@pytest.fixture(scope="module")
def golden_run(tmp_path_factory):
    """A real 78-agent, 15-year strict run (2019-2033) at seed 42 with the
    scripted model: a deterministic env state for every golden prompt."""
    if not _REAL_REF_AVAILABLE:
        pytest.skip("CRSS reference data not found under ref/")
    llm = ScriptedLLM(_golden_script)
    with pytest.MonkeyPatch.context() as mp:
        out = _run(mp, tmp_path_factory.mktemp("wp4_golden") / "run", llm,
                   "--real", "--years", "15", "--seed", "42")
    return SimpleNamespace(llm=llm, out=out)


def _first_prompt(run, agent: str, year: int) -> str:
    return run.llm.decisions[(agent, year, 0)]


# ===========================================================================
# 4.1 personas
# ===========================================================================

AGG, FLC, MC = "aggressive", "forward_looking_conservative", "myopic_conservative"

PERSONA_TEXTS = {
    AGG: ("Users in your group tend to be less concerned by a shortfall between what they "
          "request and what they receive than more cautious users are. They tend to revise "
          "their expectations more slowly than forward-looking users do and to give future "
          "years less weight than forward-looking users do."),
    FLC: ("Users in your group tend to be more concerned by a shortfall between what they "
          "request and what they receive than other users are. They tend to revise their "
          "expectations more quickly than other users do and to give future years more weight "
          "than other users do."),
    MC: ("Users in your group tend to be more concerned by a shortfall between what they "
         "request and what they receive than aggressive users are, but less than "
         "forward-looking users are. They tend to revise their expectations more slowly than "
         "forward-looking users do and to give future years less weight than other users do."),
}

# Spec item 29d: every comparison a persona makes, as (the words, the Hung
# and Yang parameter, the direction, the clusters compared with). "More
# cautious users" are the two conservative clusters. Every comparison names
# its group (WP4 re-review: an unnamed "less weight" read as true against
# every other group, and aggressive users do not give future years less
# weight than myopic users).
PERSONA_CLAIMS = {
    AGG: (("than more cautious users are", "regret", "<", (FLC, MC)),
          ("revise their expectations more slowly than forward-looking users do", "alpha", "<", (FLC,)),
          ("to give future years less weight than forward-looking users do", "gamma", "<", (FLC,))),
    FLC: (("more concerned by a shortfall between what they request and what they receive than "
           "other users are", "regret", ">", (AGG, MC)),
          ("revise their expectations more quickly than other users do", "alpha", ">", (AGG, MC)),
          ("to give future years more weight than other users do", "gamma", ">", (AGG, MC))),
    MC: (("more concerned by a shortfall between what they request and what they receive than "
          "aggressive users are", "regret", ">", (AGG,)),
         ("but less than forward-looking users are", "regret", "<", (FLC,)),
         ("revise their expectations more slowly than forward-looking users do", "alpha", "<", (FLC,)),
         ("give future years less weight than other users do", "gamma", "<", (AGG, FLC))),
}


def test_persona_texts_exact():
    """One fixed text per cluster (A8), the spec 4.1 opening, the Upper Basin
    volume sentence for Upper Basin agents only, and the item 29d cluster
    sentences, stated about the agent's group ("Users in your group tend
    to ..."); the same text for every rng draw."""
    import numpy as np

    opening = ("You are A1, an agricultural water user (an irrigation district, a tribal "
               "water user, or a group of water users) in the {basin} of the Colorado River, "
               "holding a water right of 123,456 acre-ft/year. The more water you receive, "
               "the more you can produce.")
    for cluster, text in PERSONA_TEXTS.items():
        for basin, name in (("upper_basin", "Upper Basin"), ("lower_basin", "Lower Basin")):
            profile = IrrigationAgentProfile(agent_id="A1", basin=basin, cluster=cluster,
                                             water_right=123_456.0)
            middle = " All volumes shown to you are consumptive use." if basin == "upper_basin" else ""
            expected = opening.format(basin=name) + middle + " " + text
            seen = {build_narrative_persona(profile, rng=np.random.default_rng(s)) for s in range(10)}
            assert seen == {expected}
    with pytest.raises(ValueError, match="cluster"):
        build_narrative_persona(IrrigationAgentProfile(agent_id="A1", basin="lower_basin",
                                                       cluster="bold"))


# The groups a persona may compare with: the two conservative clusters
# together, all other clusters, or one named cluster.
COMPARISON_GROUPS = ("more cautious users", "other users", "aggressive users",
                     "forward-looking users")


def _csv_cluster_means() -> Dict[str, Dict[Tuple[str, str], float]]:
    """Each cluster's mean of each parameter in the calibrated parameter file
    (tracked in git), two ways: over its calibrated entities (22 Lower Basin
    agents and 9 Upper Basin groups, one column each) and over its agents
    (each Upper Basin group weighted by its number of agent slots)."""
    import csv

    with CRSS_PARAMS_CSV.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    names = rows[0][1:]
    params = {row[0]: row[1:] for row in rows[1:]}
    slots = dict(zip(_UB_STATE_GROUPS, _UB_GROUP_AGENT_COUNTS))
    means: Dict[str, Dict[Tuple[str, str], float]] = {"entity": {}, "agent": {}}
    for param in ("regret", "alpha", "gamma", "epsilon"):
        for cluster in (AGG, FLC, MC):
            vals = [(float(params[param][i]), slots.get(n, 1))
                    for i, n in enumerate(names) if HY2021_CLUSTER_LABELS[n] == cluster]
            means["entity"][(cluster, param)] = sum(v for v, _ in vals) / len(vals)
            means["agent"][(cluster, param)] = sum(v * w for v, w in vals) / sum(w for _, w in vals)
    return means


def _holds(means, cluster, param, op, others) -> bool:
    mine = means[(cluster, param)]
    return all((mine < means[(o, param)]) if op == "<" else (mine > means[(o, param)])
               for o in others)


def test_persona_claims_hold_for_cluster_means():
    """Spec item 29d: every agent's persona states, for its cluster, only
    comparisons that hold for the cluster means of the calibrated parameter
    file, whether taken over entities or over agents. Checked for every one
    of the 80 agent slots (22 Lower Basin entities, 58 Upper Basin slots in
    9 groups). Every trait sentence is about the agent's group, never about
    the agent ("you"): an agent's own parameter can sit on the other side of
    a comparison its cluster's mean satisfies. Exploration (epsilon) is not
    mentioned because its cluster ordering flips between the two means; nor
    is any superlative."""
    means = _csv_cluster_means()
    slots = dict(zip(_UB_STATE_GROUPS, _UB_GROUP_AGENT_COUNTS))
    checked = 0
    for name, cluster in HY2021_CLUSTER_LABELS.items():
        basin = "upper_basin" if name in slots else "lower_basin"
        persona = build_narrative_persona(IrrigationAgentProfile(
            agent_id=name, basin=basin, cluster=cluster, water_right=1000.0))
        for _ in range(slots.get(name, 1)):
            for words, param, op, others in PERSONA_CLAIMS[cluster]:
                assert words in persona, (name, words)
                for kind in ("entity", "agent"):
                    assert _holds(means[kind], cluster, param, op, others), (name, words, kind)
            checked += 1
        trait_text = persona.split("The more water you receive, the more you can produce.")[1]
        trait_text = trait_text.replace(" All volumes shown to you are consumptive use.", "")
        sentences = [s.strip() for s in trait_text.split(". ") if s.strip()]
        assert sentences[0].startswith("Users in your group tend to ")
        assert all(s.startswith("They tend to ") for s in sentences[1:]), (name, sentences)
        # every comparative clause names the group it compares with
        for sentence in sentences:
            for clause in re.split(r", but | and to ", sentence):
                if re.search(r"(?<!the )\b(less|more|slowly|quickly)\b", clause):
                    assert re.search(r"\bthan (" + "|".join(COMPARISON_GROUPS) + r")\b",
                                     clause), (name, clause)
        assert re.search(r"\byou\b", trait_text, flags=re.I) is None, (name, trait_text)
        for word in ("any other", "of all", "explor", "try an option", "see what happens",
                     "what you already know"):
            assert word not in trait_text, (name, word)
        superlative = re.search(r"[a-z]+(?<!requ)est[.,;: ]|[Mm]ost |[Ll]east ", trait_text)
        assert superlative is None, (name, superlative)
    assert checked == 22 + sum(_UB_GROUP_AGENT_COUNTS)
    # why exploration is left out: the two means order the clusters differently
    eps = {kind: sorted((AGG, FLC, MC), key=lambda c: means[kind][(c, "epsilon")])
           for kind in means}
    assert eps["entity"] != eps["agent"]
    # and why aggressive and myopic learning speeds are not compared
    assert _holds(means["entity"], AGG, "alpha", ">", (MC,))
    assert _holds(means["agent"], AGG, "alpha", "<", (MC,))


@needs_ref
def test_persona_claims_hold_for_every_real_agent():
    """The same check on the 78 real agents: each persona's comparisons hold
    for the cluster means of the agents' own calibrated parameters."""
    import numpy as np
    from examples.irrigation_abm.irrigation_personas import create_profiles_from_data

    profiles = create_profiles_from_data(str(CRSS_PARAMS_CSV), str(CRSS_DB_DIR),
                                         rng=np.random.default_rng(42))
    assert len(profiles) == 78
    attr = {"regret": "regret", "alpha": "alpha", "gamma": "gamma_param"}
    means = {(c, p): float(np.mean([getattr(q, a) for q in profiles if q.cluster == c]))
             for c in (AGG, FLC, MC) for p, a in attr.items()}
    for profile in profiles:
        persona = build_narrative_persona(profile)
        assert persona.endswith(PERSONA_TEXTS[profile.cluster])
        for words, param, op, others in PERSONA_CLAIMS[profile.cluster]:
            assert words in persona and _holds(means, profile.cluster, param, op, others), (
                profile.agent_id, words)


# ===========================================================================
# 4.2 template: WSA anchoring, ACA questions, option note, item 23
# ===========================================================================

WSA_WORDS = ("abundant", "adequate", "tight", "scarce", "very scarce")


def test_wsa_anchoring_words():
    """Design record section 9 item 1, spec item 29a: one plain word per
    level, rating an amount of water ("very scarce", not "dire", which rates
    urgency), in the question itself, none tied to the delivery-ratio
    headline; the reason hint names the same five. TR1 (H, VH) and TR3 (VL,
    L) retry texts say "scarce" / "not scarce", which the words agree with."""
    template = TEMPLATE.read_text(encoding="utf-8")
    assert ("- Water Supply Outlook: Is your water supply abundant (VL), adequate (L), "
            "tight (M), scarce (H), or very scarce (VH) this season?") in template
    assert "dire" not in template and "critically short this season" not in template
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    (wsa_field,) = [f for f in cfg["shared"]["response_format"]["fields"]
                    if f["key"] == "water_scarcity_assessment"]
    assert wsa_field["reason_hint"] == (
        "One sentence on whether your water supply is abundant, adequate, tight, scarce, "
        "or very scarce.")
    headlines = " ".join(HEADLINES.values()).lower()
    for word in WSA_WORDS:
        assert word not in headlines, word


def test_template_lines_spec_4_2():
    template = TEMPLATE.read_text(encoding="utf-8")
    for gone in ("{conservation_status}", "{aca_hint}", "financial", "technical, labor",
                 "Benefit of Current Path", "\u2013", "\u2014",
                 # spec item 29e: the unsourced closer
                 "water management style", "risk tolerance"):
        assert gone not in template, gone
    assert ("- Capacity to Adjust: How much can you change your request this year, given the "
            "options below?") in template
    assert ("- Cost of Change: What would you risk by changing your request (a larger "
            "shortfall if you ask for more than is delivered, or less water to produce with "
            "if you ask for less)?") in template
    assert ("- Benefit of Keeping: What is the advantage of requesting the same amount you "
            "received last year?") in template
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert cfg["shared"]["template_vars"] == ["water_situation_text", "feedback_dashboard",
                                              "option_notes"]


MAINTAIN_SENTENCE = (
    "If you received less than you requested last year, keeping your request asks only "
    "for the amount you received; an increase is the only option that asks for more.")
OPTION_NOTE = "The exact size of an increase or a decrease is drawn at random around your typical step."
INCREASE_NOTE = "The exact size of an increase is drawn at random around your typical step."
DECREASE_NOTE = "The exact size of a decrease is drawn at random around your typical step."


def test_option_notes_only_where_they_apply():
    """Spec item 29e, refined 2026-09-30: the random-step line (spec 2.6)
    names only the directions the menu offers ("an increase" at the floor,
    "a decrease" at the cap), and the item-23 sentence follows only when an
    increase is offered and last year's delivery was below its request (the
    FULL_SUPPLY_RATIO edge of "Demand fully met."). The template holds none
    of these sentences, only the variable right after the options."""
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "{options_text}{option_notes}" + chr(10) + chr(10) + "{rating_scale}" in template
    for line in (OPTION_NOTE, INCREASE_NOTE, DECREASE_NOTE, MAINTAIN_SENTENCE):
        assert line not in template
    short = {"request": 100_000.0, "diversion": 84_000.0}
    full = {"request": 100_000.0, "diversion": 100_000.0}
    nl = chr(10)
    assert build_option_notes(True, True, short) == nl + OPTION_NOTE + nl + MAINTAIN_SENTENCE
    assert build_option_notes(True, True, full) == nl + OPTION_NOTE
    assert build_option_notes(True, True, None) == nl + OPTION_NOTE  # the first year
    edge = {"request": 100_000.0, "diversion": 100_000.0 * FULL_SUPPLY_RATIO}
    assert build_option_notes(True, True, edge) == nl + OPTION_NOTE
    below = {"request": 100_000.0, "diversion": 99_899.9}
    assert build_option_notes(True, True, below).endswith(MAINTAIN_SENTENCE)


def test_option_notes_at_the_floor_name_only_an_increase():
    """At the minimum-use floor the menu offers no decrease: the random-step
    line names an increase only; the item-23 sentence still follows a short
    year, since an increase is offered."""
    nl = chr(10)
    short = {"request": 100_000.0, "diversion": 84_000.0}
    assert build_option_notes(True, False, None) == nl + INCREASE_NOTE
    assert build_option_notes(True, False, short) == nl + INCREASE_NOTE + nl + MAINTAIN_SENTENCE


def test_option_notes_at_the_cap_name_only_a_decrease():
    """At the water right the menu offers no increase: the random-step line
    names a decrease only, and the item-23 sentence (about an increase) is
    left out even after a short year."""
    nl = chr(10)
    short = {"request": 100_000.0, "diversion": 84_000.0}
    for last_year in (short, None):
        assert build_option_notes(False, True, last_year) == nl + DECREASE_NOTE
    assert build_option_notes(False, False, short) == ""  # neither direction: no line


def _pre_year_option_notes(agent_id: str, water_right: float, use_2018: float) -> str:
    """``{option_notes}`` as IrrigationLifecycleHooks.pre_year sets it for a
    hand-built agent in 2019 (no reference data needed)."""
    from broker.agents import AgentConfig, BaseAgent
    from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
    from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig
    from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

    profile = IrrigationAgentProfile(agent_id=agent_id, basin="lower_basin",
                                     cluster="myopic_conservative", water_right=water_right,
                                     actual_2018_diversion=use_2018)
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    env.initialize_from_profiles([profile])
    agent = BaseAgent(AgentConfig(name=agent_id, agent_type="irrigation_farmer", state_params=[],
                                  objectives=[], constraints=[], skills=[]))
    agent.custom_attributes = {}
    agent.is_active = True
    runner = SimpleNamespace(broker=SimpleNamespace(_retry_feedback_mode="full"),
                             agents={agent_id: agent},
                             memory_engine=HumanCentricMemoryEngine(window_size=5, top_k_significant=2, seed=1))
    hooks = IrrigationLifecycleHooks(env, runner, [profile], None, None)
    env.advance_year()
    hooks.pre_year(1, {}, {agent_id: agent})
    return agent.option_notes


def test_pre_year_names_the_offered_directions_at_the_floor_and_the_cap():
    """The wiring: pre_year reads the same flags the identity rules read
    (at_allocation_cap hides an increase, below_minimum_utilisation hides a
    decrease), so an agent whose 2018 use is at its floor reads the
    increase-only line and one at its water right the decrease-only line."""
    nl = chr(10)
    assert _pre_year_option_notes("WelltonMohawkIDD", 490_000.0, 49_000.0) == nl + INCREASE_NOTE
    assert _pre_year_option_notes("WelltonMohawkIDD", 490_000.0, 490_000.0) == nl + DECREASE_NOTE
    assert _pre_year_option_notes("WelltonMohawkIDD", 490_000.0, 373_081.0) == nl + OPTION_NOTE


def _after_menu(prompt: str) -> str:
    """The prompt text from the options to the rating scale."""
    start = prompt.index("Now, choose one of the following water management actions:")
    return prompt[start:prompt.index("Please respond using the EXACT JSON format")]


@needs_ref
def test_option_notes_rendered(golden_run):
    """A year after a cut: both lines right after the options; a year after
    full delivery: the random-step line only.

    Item 36g (2026-10-05 design-basis audit + fix proposals): this test
    used to add a third real-run demonstration here, an agent at its own
    water right (UT2 in 2033, no increase on the menu, so only the
    decrease-only line). Dropping the grid-top term raised UT2's water
    right from 20,000 to 38,080 AF, and UT2's own sub-basin supply never
    lets its request grow anywhere near that (checked to the end of the
    real 2019-2060 horizon), so no real agent in this golden run reaches
    its water right any more. The decrease-only-at-cap rendering itself
    is covered directly and exhaustively (every governance profile) by
    test_v3_governance.py::test_menu_parity_at_cap (synthetic, basin-
    agnostic) and by the synthetic test_pre_year_option_notes above
    (the 490,000-at-490,000 case) -- so this real-run demonstration is
    retired rather than chasing a cap this agent no longer reaches.
    """
    nl = chr(10)
    mohave = _first_prompt(golden_run, "MohaveValleyIDD", 2022)
    options_end = mohave.index(nl, mohave.index("3. Decrease your request"))
    assert mohave[options_end + 1:].startswith(OPTION_NOTE + nl + MAINTAIN_SENTENCE + nl + nl)
    # MohaveValleyIDD's 2021 request was cut: keep asks for what it received.
    assert "2. Keep your request at 20,155 acre-ft, the amount you received last year." in mohave
    wellton = _first_prompt(golden_run, "WelltonMohawkIDD", 2022)
    options_end = wellton.index(nl, wellton.index("3. Decrease your request"))
    assert wellton[options_end + 1:].startswith(OPTION_NOTE + nl + nl)


@needs_ref
def test_random_step_line_names_the_offered_directions_in_every_prompt(golden_run):
    """Over every decision prompt of the real run: the random-step line
    names exactly the directions the menu offers, and the item-23 sentence
    appears exactly when an increase is offered and last year's delivery was
    short; with no increase offered nothing after the menu mentions one.

    Item 36g (2026-10-05 design-basis audit + fix proposals): before this
    item, UT2 (the always-increasing agent) reached its own water right
    by 2033 (see _golden_script's docstring), so this loop always found
    at least one at-cap prompt here. Dropping the grid-top term raised
    UT2's right to 38,080 AF, which its own sub-basin supply never lets
    it approach, so no real agent in this 15-year run is at cap any
    more; the branch below is still exercised (and still asserted) if
    one ever is, but it is no longer REQUIRED to fire -- the governance-
    level invariant itself (at cap -> decrease-only, no "increase"
    anywhere after the menu) is covered unconditionally by
    test_v3_governance.py::test_menu_parity_at_cap.
    """
    at_cap = 0
    for (agent, year, attempt), prompt in golden_run.llm.decisions.items():
        after = _after_menu(prompt)
        up = "Increase your request" in after
        down = "Decrease your request" in after
        expected = OPTION_NOTE if up and down else INCREASE_NOTE if up else DECREASE_NOTE
        for line in (OPTION_NOTE, INCREASE_NOTE, DECREASE_NOTE):
            assert (line in after) == (line == expected), (agent, year, line)
        last = re.search(r"\((\d+(?:\.\d)?)% delivered\)", prompt)
        short_last_year = last is not None and last.group(1) != "100"
        assert (MAINTAIN_SENTENCE in after) == (up and short_last_year), (agent, year)
        if not up:
            at_cap += 1
            assert "increase" not in after.lower(), (agent, year)


# ===========================================================================
# 4.3 situation text: headline, share format, basin lines
# ===========================================================================

def _lb_ctx(ratio: float, *, drought_index: float = 0.3, tier: int = 0,
            gap: Optional[str] = None, request: float = 100_000.0, **extra) -> Dict[str, Any]:
    if gap is None:
        gap = "none" if ratio >= 1.0 else "lb_mead_availability"
    ctx = {"year": 2030, "basin": "lower_basin", "drought_index": drought_index,
           "lake_mead_level": 1080.0, "preceding_factor": 1, "shortage_tier": tier,
           "lb_shortage_volume_maf": {0: 0.0, 1: 0.333, 2: 0.417, 3: 0.5}[tier],
           "shortage_tier_threshold_ft": {1: 1075.0, 2: 1050.0, 3: 1025.0}.get(tier),
           "current_request": request, "current_diversion": request * ratio,
           "delivery_ratio": ratio, "water_right": 200_000.0, "gap_reason": gap,
           "lb_junior_request_af": 0.0, "lb_junior_tier_cut_fraction": 0.0,
           "lb_senior_entitlement_af": 200_000.0, "lb_junior_entitlement_af": 0.0}
    ctx.update(extra)
    return ctx


def _headline(text: str) -> str:
    return text.split(chr(10))[1]


@pytest.mark.parametrize("ratio,band", [
    (1.0, "sufficient"), (FULL_SUPPLY_RATIO, "sufficient"), (0.998999, "short"),
    (0.97, "short"), (0.95, "short"), (0.949999, "short"), (0.949, "short"),
    (0.80, "short"), (0.799999, "short"), (0.79, "short"), (0.50, "short"),
    (0.499999, "short"), (0.49, "short"), (0.0, "short"),
])
@pytest.mark.parametrize("drought_index", [0.05, 0.3, 0.6, 0.9])
def test_headline_bands(ratio, band, drought_index):
    """Item 36a (2026-10-05): the headline reads r alone, in TWO states,
    the single edge FULL_SUPPLY_RATIO (the supply rule's own edge); pinned
    on both sides at r's 6-place rounding (review LOW 9). No drought
    headline such as "adequate but slightly below normal" sits beside a
    supply-rule block: below the edge the headline is never "sufficient",
    whatever the old drought index says, and no drought wording appears at
    all. The retired three-way split within "short" (slightly/well/
    critically) is a report-only analysis bin now
    (analysis.v3_metrics.R5A_BANDS / r5a_headline_band), never read by the
    agent -- see test_v3_metrics.py::test_r5a_band_edges_are_the_five_retired_prompt_bands."""
    text = build_water_situation_text(_lb_ctx(ratio, drought_index=drought_index))
    assert _headline(text) == HEADLINES[band]
    for drought_word in ("drought", "dryness", "adequate but", "favorable", "below normal",
                         "Precipitation is near", "reservoir levels are healthy"):
        assert drought_word not in text, drought_word
    if ratio < FULL_SUPPLY_RATIO:
        assert HEADLINES["sufficient"] not in text
        assert "you can expect full delivery" not in text


def test_share_format():
    """Spec 4.3: a share at or above FULL_SUPPLY_RATIO is full ("100%", no
    reason); a share in [0.995, 0.999) prints with one decimal, never
    "100%", next to its shortfall and its reason (the pre-WP4 ".0%" printed
    "100%" for 0.9985 beside a stated shortfall)."""
    assert format_share(1.0) == "100%"
    assert format_share(0.9995) == "100%"
    assert format_share(FULL_SUPPLY_RATIO) == "100%"
    assert format_share(0.9985) == "99.9%"  # the spec's own example
    assert format_share(0.997) == "99.7%"
    for i in range(0, 4000):
        share = round(0.995 + i * 1e-6, 6)
        if share >= FULL_SUPPLY_RATIO:
            break
        assert format_share(share) != "100%" and format_share(share).startswith("99."), share
    for ratio in (0.995, 0.9975, 0.9985, 0.998999):
        text = build_water_situation_text(
            _lb_ctx(ratio), last_year={"request": 100_000.0, "diversion": 100_000.0 * ratio,
                                       "gap_reason": "lb_mead_availability"})
        assert "100%" not in text
        assert f"({format_share(round(ratio, 6))}) this year, because Lake Mead cannot" in text
        assert f"({format_share(round(ratio, 6))} delivered), because Lake Mead could not" in text
        mem = build_action_outcome_feedback({"skill_name": "maintain_demand"}, 2029,
                                            100_000.0, 100_000.0 * ratio, 1, basin="lower_basin",
                                            gap_reason=describe_gap_reason(
                                                {"gap_reason": "lb_mead_availability"}, "past"))
        assert "Demand fully met" not in mem and "% unmet), because Lake Mead could not" in mem
    full = build_water_situation_text(_lb_ctx(0.9995, gap="lb_mead_availability"),
                                      last_year={"request": 100_000.0, "diversion": 99_950.0,
                                                 "gap_reason": "lb_mead_availability"})
    assert "(100% delivered)." in full and "you can expect full delivery this year." in full
    assert "because" not in full


def test_numbers_formatted_alike_and_no_silent_defaults():
    """Review LOW 8: the Lake Mead level carries a thousands separator like
    every other number in the prompt. LOW 10: a context without the tier or
    the agent's own flag raises instead of reading as tier 0 or "below"."""
    text = build_water_situation_text(_lb_ctx(1.0, lake_mead_level=1034.4))
    assert "Lake Mead was at 1,034 feet above sea level on 1 January (rising from last year)." in text
    for missing in ("shortage_tier", "preceding_factor"):
        ctx = _lb_ctx(1.0)
        del ctx[missing]
        with pytest.raises(KeyError, match=missing):
            build_water_situation_text(ctx)
    ub = _ub_ctx()
    del ub["preceding_factor"]
    with pytest.raises(KeyError, match="preceding_factor"):
        build_water_situation_text(ub)


def test_lb_shortage_line_item14_and_22():
    """Spec 4.3's tier sentence (no agency named, 'Lake Mead was below ...
    feet'), made true under item 22: in split mode part of the volume falls
    on junior-priority farm water, so both takers are named; a senior agent
    is told only a physical shortage reduces its delivery; a junior-holding
    agent is told its own cut."""
    senior = build_water_situation_text(_lb_ctx(1.0, tier=2, lb_junior_tier_cut_fraction=0.2532))
    assert ("A Tier 2 Lower Basin shortage applies this year (Lake Mead was below 1,050 feet on "
            "1 January): it reduces Lower Basin deliveries by 417,000 acre-ft in total, taken "
            "from non-agricultural users and from junior-priority agricultural water. Your "
            "delivery is reduced only if Lake Mead cannot supply all Lower Basin withdrawals "
            "this year.") in senior
    senior_all = build_water_situation_text(_lb_ctx(1.0, tier=1))
    assert ("A Tier 1 Lower Basin shortage applies this year (Lake Mead was below 1,075 feet on "
            "1 January): it reduces deliveries to Lower Basin non-agricultural users by 333,000 "
            "acre-ft in total. Your delivery is reduced only if") in senior_all
    junior = build_water_situation_text(_lb_ctx(
        0.7468, tier=2, gap="lb_junior_tier_cut", lb_junior_tier_cut_fraction=0.2532,
        lb_junior_request_af=100_000.0, lb_senior_entitlement_af=0.0,
        lb_junior_entitlement_af=100_000.0))
    assert ("All of your water right is junior-priority, and this tier cuts your "
            "junior-priority water by about 25%. The rest of your delivery is reduced only if "
            "Lake Mead cannot supply all Lower Basin withdrawals this year.") in junior
    assert "No Lower Basin shortage applies this year." in build_water_situation_text(_lb_ctx(1.0))
    for text in (senior, senior_all, junior):
        assert "Bureau of Reclamation" not in text and "has declared" not in text
    with pytest.raises(ValueError, match="shortage_tier_threshold_ft"):
        build_water_situation_text(_lb_ctx(1.0, tier=2, shortage_tier_threshold_ft=None))


def test_lb_partly_junior_within_senior_is_told_about_an_increase():
    """Spec item 29f: an agent holding junior-priority water whose keep
    request lies within its senior entitlement has no junior part cut this
    year, but an increase beyond the entitlement would be junior-priority
    water, and the tier would cut it; it is told so (MohaveValleyIDD's
    published 5,940 AF senior entitlement). In senior_all mode (no junior
    cut) it reads the senior sentence."""
    within = dict(tier=1, lb_junior_tier_cut_fraction=0.2026, request=5_000.0,
                  lb_senior_entitlement_af=5_940.0, lb_junior_entitlement_af=35_060.0)
    text = build_water_situation_text(_lb_ctx(1.0, **within))
    assert ("Part of your water right is junior-priority: this tier would cut any part of a "
            "request above 5,940 acre-ft by about 20%. Up to that amount, your delivery is "
            "reduced only if Lake Mead cannot supply all Lower Basin withdrawals this year.") in text
    assert "Your delivery is reduced only if" not in text
    senior_all = build_water_situation_text(_lb_ctx(1.0, **dict(within, lb_junior_tier_cut_fraction=0.0)))
    assert "Your delivery is reduced only if Lake Mead cannot supply" in senior_all
    assert "junior-priority" not in senior_all
    ctx = _lb_ctx(1.0, **within)
    del ctx["lb_junior_entitlement_af"]
    with pytest.raises(ValueError, match="lb_junior_entitlement_af"):
        build_water_situation_text(ctx)


def _ub_ctx(**extra) -> Dict[str, Any]:
    ctx = {"year": 2030, "basin": "upper_basin", "precipitation": 61.4, "preceding_factor": 0,
           "supply_group": "UT1", "ub_subbasin_member_count": 11, "ub_subbasin_flow_share": 0.654,
           "powell_storage_maf": 10.44, "powell_dead_pool_maf": 1.89,
           "current_request": 91_435.0, "current_diversion": 82_945.0, "delivery_ratio": 0.907,
           "water_right": 128_009.0, "gap_reason": "ub_subbasin_supply"}
    ctx.update(extra)
    return ctx


def test_ub_subbasin_flow_line():
    text = build_water_situation_text(_ub_ctx())
    lines = text.split(chr(10))
    assert lines[0] == "It is now the year 2030. You use water in the Upper Colorado River Basin."
    assert lines[2] == "Winter precipitation in your sub-basin this year was 61 mm (below last year)."
    assert lines[3] == ("The natural flow of the rivers your sub-basin draws on is 65% of its "
                        "1971-2018 average this year.")
    # Item 36d (2026-10-05 design-basis audit + fix proposals, spec item
    # 36d, G5): no Lake Powell sentence for an Upper Basin agent at all --
    # under item 4/E14 the Upper Basin is never cut for a Powell release,
    # so Powell's level cannot affect this agent's delivery. The line
    # that followed the flow line (line index 4) is now the "last year"
    # sentence instead.
    assert "Lake Powell" not in text
    assert lines[4] == "In 2029 you used 91,435 acre-ft."
    assert "Lees Ferry" not in text and "forecast" not in text
    mock = build_water_situation_text(_ub_ctx(supply_group=None, ub_subbasin_flow_share=None,
                                              natural_flow_maf=9.87))
    assert "Winter precipitation averaged over the Upper Basin this year was 61 mm" in mock
    assert "your sub-basin this year" not in mock
    assert "Lake Powell" not in mock


# ===========================================================================
# 4.4 reasons: present and past
# ===========================================================================

def test_past_and_present_reasons():
    """Spec item 29b: what falls short in a sub-basin is the water it can
    draw, a fixed share of the natural flow at its gauges (A_s = c_s Q_s),
    not the natural flow itself."""
    ub = {"gap_reason": "ub_subbasin_supply", "ub_subbasin_member_count": 11}
    assert describe_gap_reason(ub, "present") == (
        "because the water your sub-basin can draw this year, a fixed share of the natural "
        "flow of its rivers, is below the combined requests of its users, and the shortfall "
        "is shared in proportion to requests")
    assert describe_gap_reason(ub, "past") == (
        "because the water your sub-basin could draw that year, a fixed share of the natural "
        "flow of its rivers, was below the combined requests of its users, and the shortfall "
        "was shared in proportion to requests")
    alone = dict(ub, ub_subbasin_member_count=1)
    assert describe_gap_reason(alone, "present") == (
        "because the water your sub-basin can draw this year, a fixed share of the natural "
        "flow of its rivers, is below your own request")
    assert describe_gap_reason(alone, "past") == (
        "because the water your sub-basin could draw that year, a fixed share of the natural "
        "flow of its rivers, was below your own request")
    assert describe_gap_reason({"gap_reason": "ub_natural_flow"}, "present") == (
        "because Upper Basin deliveries are limited by this year's natural flow at Lees Ferry, "
        "after Upper Basin non-farm use, and shared in proportion to requests")
    assert describe_gap_reason({"gap_reason": "lb_mead_availability"}, "present") == (
        "because Lake Mead cannot meet all Lower Basin withdrawals without falling below its "
        "minimum pool, so all Lower Basin deliveries are reduced in proportion to requests")
    # the situation text: present for this year, past for last year
    text = build_water_situation_text(_ub_ctx(), last_year={
        "request": 91_435.0, "diversion": 80_000.0, "gap_reason": "ub_subbasin_supply",
        "ub_subbasin_member_count": 11})
    assert ("(87.5% delivered), because the water your sub-basin could draw that year, a fixed "
            "share of the natural flow of its rivers, was below") in text
    assert ("(90.7%) this year, because the water your sub-basin can draw this year, a fixed "
            "share of the natural flow of its rivers, is below") in text
    assert "natural flow of the rivers your sub-basin draws on is below" not in text
    assert "natural flow of the rivers your sub-basin draws on was below" not in text
    for retired in ("ub_powell_release", "lb_shortage_tier"):
        with pytest.raises(ValueError, match="unknown gap_reason code"):
            describe_gap_reason({"gap_reason": retired}, "past")


def test_dashboard_sharing_flags_match_the_supply_rule_sentence():
    """Spec 4.6: the dashboard warning names who shares a shortage as the
    supply-rule message does; the flags pick the same pool _sharing_sentence
    names, in the item 29c clause. Item 29f: a Lower Basin agent holding
    junior-priority water gets its own flag (its warning cannot say that a
    declared shortage never reduces its delivery)."""
    lb = {"basin": "lower_basin", "lb_junior_entitlement_af": 0.0}
    cases = [
        ({"basin": "upper_basin", "gap_reason": "ub_subbasin_supply",
          "ub_subbasin_member_count": 11}, "shortage_subbasin",
         "raise your share only by lowering the deliveries of other users in your sub-basin; "
         "it would not add water to your sub-basin."),
        ({"basin": "upper_basin", "gap_reason": "ub_subbasin_supply",
          "ub_subbasin_member_count": 1}, "shortage_alone",
         "When water is short, a larger request would not add water."),
        ({"basin": "upper_basin", "gap_reason": "ub_capacity"}, "shortage_upper_basin",
         "other users in the Upper Basin; it would not add water to the Upper Basin."),
        (dict(lb, gap_reason="lb_mead_availability"), "shortage_lower_basin",
         "other users in the Lower Basin; it would not add water to the Lower Basin."),
        (dict(lb, gap_reason="lb_mead_availability", lb_junior_entitlement_af=35_060.0),
         "shortage_lower_basin_junior_holder",
         "other users in the Lower Basin; it would not add water to the Lower Basin."),
        (dict(lb, gap_reason="lb_mead_availability", lb_junior_entitlement_af=None),
         "shortage_lower_basin",
         "other users in the Lower Basin; it would not add water to the Lower Basin."),
        (dict(lb, gap_reason="lb_junior_tier_cut+lb_mead_availability",
              lb_junior_tier_cut_fraction=0.25, lb_junior_entitlement_af=35_060.0),
         "shortage_junior", "about 25% of which the declared shortage tier cuts"),
    ]
    for state, flag, words in cases:
        flags = dashboard_sharing_flags(state)
        assert [k for k, v in flags.items() if v == 1.0] == [flag]
        assert words in _sharing_sentence(state), (flag, _sharing_sentence(state))
    for state in ({"basin": "upper_basin", "gap_reason": "none"}, dict(lb, gap_reason="none")):
        assert set(dashboard_sharing_flags(state).values()) == {0.0}
    with pytest.raises(ValueError, match="lb_junior_entitlement_af"):
        dashboard_sharing_flags({"basin": "lower_basin", "gap_reason": "lb_mead_availability"})


def test_dashboard_warning_edge_pins_to_full_supply_ratio():
    """Item 36h (2026-10-05 design-basis audit + fix proposals, spec item
    36h, provenance G12a): the dashboard warning's edge is FULL_SUPPLY_RATIO
    (0.999), the SAME edge the supply rule and the situation-text headline
    use -- not the old, unsourced 0.85. The YAML cannot import the Python
    constant, so it is written out as a literal; this pins that literal
    against the constant so the two can never silently drift apart again."""
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assertions = raw["irrigation_farmer"]["feedback"]["assertions"]
    assert len(assertions) >= 6
    edges = set()
    for a in assertions:
        m = re.search(r"supply / request < (\d+\.\d+)", a["when"])
        assert m, a["when"]
        edges.add(float(m.group(1)))
    assert edges == {FULL_SUPPLY_RATIO}
    assert FULL_SUPPLY_RATIO == 0.999  # sanity: the literal this pins against


# ===========================================================================
# 4.5 to 4.7 across a real run: memory, dashboard, reflection, banned phrases
# ===========================================================================

@needs_ref
def test_calendar_year_memory_and_dashboard(golden_run):
    prompt = _first_prompt(golden_run, "MohaveValleyIDD", 2022)
    memory = prompt[prompt.index("Your memory includes:"):prompt.index("First, assess")]
    for year in (2019, 2020, 2021):
        assert f"- Year {year}: You chose to maintain demand." in memory
    assert re.search(r"- Year \d{1,2}:", memory) is None
    assert ("- Year 2020: You chose to maintain demand. You requested 28,295 acre-ft and received "
            "23,766 acre-ft. Shortfall: 4,529 acre-ft (16.0% unmet), because the declared Lower "
            "Basin shortage tier cut your junior-priority water by about 20%. On 1 January that "
            "year Lake Mead was lower than a year earlier.") in memory
    dashboard = prompt[prompt.index("PERFORMANCE HISTORY:"):prompt.index("Your memory includes:")]
    assert "Year | request (AF) | supply (AF)\n" in dashboard
    for row in ("2019 |       28,295 |      28,295", "2020 |       28,295 |      23,766",
                "2021 |       23,766 |      20,155"):
        assert row in dashboard
    assert "shortage_" not in dashboard and "TREND" not in dashboard
    # the unmet share with one decimal, as in the memory line (review LOW 8),
    # and the item 29c sharing clause
    assert "You requested 23,766 AF and received 20,155 AF (15.2% unmet)." in dashboard
    assert ("If Lake Mead is also physically short, the rest is shared in proportion to "
            "requests, and a larger request would raise your share only by lowering the "
            "deliveries of other users in the Lower Basin; it would not add water to the "
            "Lower Basin.") in " ".join(dashboard.split())
    assert "Shortfall: 3,611 acre-ft (15.2% unmet)" in memory


@needs_ref
def test_banned_phrases_absent(golden_run):
    """Spec 4.x: no rendered prompt (decision or reflection) of the real run
    carries an invented attribute, a rule id, an agency, a loop year, a
    drought index, a TREND word or an em dash."""
    prompts = list(golden_run.llm.decisions.values()) + golden_run.llm.reflections
    assert len(golden_run.llm.decisions) >= 78 * 15
    for prompt in prompts:
        for phrase in BANNED_PHRASES:
            assert phrase not in prompt, (phrase, prompt[:300])


@needs_ref
def test_reflection_input_excludes_reflections_and_is_one_agent(golden_run):
    reflections = golden_run.llm.reflections
    # none at the end of 2019: no agent has a memory line until 2020
    assert len(reflections) == 78 * 14
    for prompt in reflections:
        assert re.search(r"for 1 agent in a simulation \(Year 20\d\d\)\.", prompt), prompt[:200]
        assert "Consolidated Reflection" not in prompt
        assert len(re.findall(r"^.+? Memories: ", prompt, flags=re.M)) == 1
    assert "Did the direction you chose (increase, keep or decrease) match the outcome?" in reflections[0]


@needs_ref
def test_single_reflection_kept_from_the_previous_year(golden_run):
    """Spec 4.7, S10: a prompt shows at most one reflection line, written at
    the end of the previous calendar year (pilot check P6)."""
    for (agent, year, attempt), prompt in golden_run.llm.decisions.items():
        lines = re.findall(r"^- Consolidated Reflection.*$", prompt, flags=re.M)
        if year <= 2020:  # the first reflection is written at the end of 2020
            assert lines == []
            continue
        assert lines == [f"- Consolidated Reflection (written in {year - 1}): {ScriptedLLM.LESSON}"], (
            agent, year, lines)


# ===========================================================================
# golden prompts (spec 4.x): a deterministic env state, the whole prompt
# ===========================================================================

UT1 = "AgUsesAboveGreenRUt_NonIndian"
GOLDEN = {
    # (agent, calendar year): (what the year is, sha256 of the full prompt)
    # Items 36a/36d/36g (2026-10-05) changed the four Upper Basin entries
    # below: the two-state headline, the removed Lake Powell sentence, and
    # (UT2 only) the new 1.4x-peak-only water right (38,080 AF, was
    # 20,000 AF) all change the rendered text.
    # Opus review (2026-10-06): all EIGHT entries changed again, Upper AND
    # Lower Basin alike, because `config/prompts/irrigation_farmer.txt`
    # now starts with `{system_prompt}{priority_section}` (both always
    # empty for irrigation) instead of implicitly picking up
    # TieredContextBuilder.format_prompt's own auto-prepended
    # "{system_prompt}\n\n{priority_section}\n\n" (broker/components/
    # context/tiered.py) -- removing 4 leading blank lines every real
    # prompt was sending (confirmed: not render-only, the actual LLM
    # input). See examples/irrigation_abm/tests/test_v3_prompt.py::
    # test_no_leading_blank_lines for the regression pin.
    (UT1, 2019): ("UB, normal year", "f7a58305f4f24325874261e0f13c019eae2895f8591e1ce8f61a2348a2ca560c"),
    (UT1, 2020): ("UB, own sub-basin short at 2018 use", "c1d8f051824f693e83c964ed37bde91e9469cbc886968cc8535b620893923b20"),
    (UT2, 2019): ("UT2 alone in its sub-basin, normal year", "d9e8dc70fcaff57af6c4a1fba3a6f2f721224f951415cb64366eccf8b1c5b27b"),
    (UT2, 2033): ("UT2 alone in its sub-basin, short (its own right no longer binds)",
                  "8ba8618b172f80b4536f5d486007c91720e03dd303082936cbde76461d6acc2c"),
    ("WelltonMohawkIDD", 2019): ("LB senior, normal year", "b8984b49c172983a0e68aea9edaead391c36188c1201e804a59fba3c368cee80"),
    ("WelltonMohawkIDD", 2022): ("LB senior, Tier 2", "49062ccdb7224233b7c148c9f34b96b6a434d3dc545d23ae407ca74ffcd1d699"),
    ("MohaveValleyIDD", 2019): ("LB partly junior, normal year", "ff5476449efe16faa5292097db715a0a952c467c60bf5436666524ff435180a3"),
    ("MohaveValleyIDD", 2022): ("LB partly junior, Tier 2 cuts its junior water", "a0c5373fe16ae7d3c7d09c19d4b43ebdb29e368031016a881901c16a25866f82"),
}


@needs_ref
@pytest.mark.parametrize("key", sorted(GOLDEN), ids=lambda k: f"{k[0][:12]}-{k[1]}")
def test_golden_prompt(golden_run, key):
    prompt = _first_prompt(golden_run, *key)
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert digest == GOLDEN[key][1], f"{key} ({GOLDEN[key][0]}) changed; prompt:\n{prompt}"


@needs_ref
def test_no_leading_blank_lines(golden_run):
    """Opus review (2026-10-06): every real prompt used to start with 4
    blank lines, for BOTH basins -- not a rendering artifact of any one
    extraction script, but TieredContextBuilder.format_prompt
    (broker/components/context/tiered.py) auto-prepending
    "{system_prompt}\\n\\n{priority_section}\\n\\n" whenever a template
    does not itself reference "{system_prompt}"; irrigation's template
    never did, and neither var is ever set for this domain (no
    SystemPromptProvider, no PrioritySchemaProvider in
    TieredContextBuilder's own default provider list), so both render
    empty and only the 4 newlines survived. Fixed template-side only
    (config/prompts/irrigation_farmer.txt now starts with
    "{system_prompt}{priority_section}{narrative_persona}"), not in
    tiered.py itself, so no other domain's prompt is touched."""
    for (agent, year, attempt), prompt in golden_run.llm.decisions.items():
        assert not prompt.startswith("\n"), (agent, year, attempt, repr(prompt[:20]))
        if attempt == 0:  # a retry (attempt > 0) legitimately prepends its own header
            assert prompt.startswith("You are "), (agent, year, attempt, repr(prompt[:20]))
    for prompt in golden_run.llm.reflections:
        assert not prompt.startswith("\n"), repr(prompt[:20])


@needs_ref
def test_golden_prompts_shortage_years_read_short(golden_run):
    """Readable companions of the hashes: each shortage year's headline and
    reason; each normal year's full-delivery wording and 2018 use."""
    ut1 = _first_prompt(golden_run, UT1, 2020)
    assert HEADLINES["short"] in ut1
    assert ("If you request the 91,435 acre-ft you received last year, you can expect 82,945 "
            "acre-ft (90.7%) this year, because the water your sub-basin can draw this year, a "
            "fixed share of the natural flow of its rivers, is below the combined requests of "
            "its users") in ut1
    ut2 = _first_prompt(golden_run, UT2, 2033)
    # Item 36g (2026-10-05): UT2's water right is now 38,080 AF (1.4 x
    # peak only, was 20,000 AF under the old min(grid_top, scaled) rule),
    # so its 2033 request (24,098 AF, grown by the always-increase
    # script) is no longer capped at the right; the delivered acre-ft
    # (17,370, the sub-basin's own supply) is unchanged, but the
    # percentage of the (now larger) request is lower: 72.1%, not 86.9%.
    assert ("you can expect 17,370 acre-ft (72.1%) this year, because the water your sub-basin "
            "can draw this year, a fixed share of the natural flow of its rivers, is below your "
            "own request.") in ut2
    wm = _first_prompt(golden_run, "WelltonMohawkIDD", 2022)
    assert HEADLINES["sufficient"] in wm and "A Tier 2 Lower Basin shortage applies" in wm
    for agent, used in ((UT1, "In 2018 you used 91,435 acre-ft."),
                        (UT2, "In 2018 you used 11,400 acre-ft."),
                        ("WelltonMohawkIDD", "In 2018 you diverted 373,081 acre-ft."),
                        ("MohaveValleyIDD", "In 2018 you diverted 28,295 acre-ft.")):
        first = _first_prompt(golden_run, agent, 2019)
        assert used in first and HEADLINES["sufficient"] in first
        assert "PERFORMANCE HISTORY" not in first and "Your memory includes:\nNo memories yet." in first


# ===========================================================================
# 4.5 and 4.8 across the retry-feedback arms (synthetic agents, fast)
# ===========================================================================

def _always_increase_scarce(agent, year, attempt):
    return "H", "M", "Increase"


def _decrease_not_scarce_then_keep(agent, year, attempt):
    return ("L", "M", "Decrease") if attempt == 0 else ("L", "M", "Keep")


def _omit_wsa_then_keep(agent, year, attempt):
    return (None, "M", "Keep") if attempt < 3 else ("M", "M", "Keep")


@pytest.fixture(scope="module")
def arm_runs(tmp_path_factory):
    """Strict, placebo and silent (and an omitted-field strict run), 3
    synthetic agents x 2 years, TR1 blocking every attempt in year 1."""
    runs = {}
    with pytest.MonkeyPatch.context() as mp:
        for name, script, extra in (
            ("strict", _always_increase_scarce, ()),
            ("placebo", _always_increase_scarce, ("--retry-feedback-mode", "placebo")),
            ("silent", _always_increase_scarce, ("--retry-feedback-mode", "silent")),
            ("strict_tr3", _decrease_not_scarce_then_keep, ()),
            ("strict_omit", _omit_wsa_then_keep, ()),
        ):
            llm = ScriptedLLM(script)
            _run(mp, tmp_path_factory.mktemp(f"wp4_{name}") / "run", llm,
                 "--agents", "3", "--years", "2", "--seed", "7", *extra)
            runs[name] = llm
    return runs


def test_retry_texts_no_label_codes_or_skill_ids(arm_runs):
    """Items 11, 15; spec 3.7, 4.8: no retry text shows a label code, a skill
    id or a rule id, in any arm; the report names the plain action."""
    seen = 0
    for name, llm in arm_runs.items():
        for agent, year, attempt, block in llm.retry_blocks():
            if block == "<SAME>":
                continue
            seen += 1
            assert not _LABEL_CODE.search(block), (name, block)
            for skill_id in SKILL_IDS:
                assert skill_id not in block, (name, block)
            assert "[Rule:" not in block
    assert seen > 0
    strict = [b for (_a, _y, _t, b) in arm_runs["strict"].retry_blocks()]
    assert all("Your proposed action 'increase demand' was BLOCKED." in b for b in strict)
    tr3 = [b for (_a, _y, _t, b) in arm_runs["strict_tr3"].retry_blocks()]
    assert tr3 and all("Your proposed action 'decrease demand' was BLOCKED." in b for b in tr3)


def test_placebo_closer_and_silent_resend(arm_runs):
    placebo = arm_runs["placebo"].retry_blocks()
    assert placebo and all(
        b == "Your previous response was flagged by the governance layer.\n\n"
             "Please reconsider your decision.\n\n" for (_a, _y, _t, b) in placebo)
    silent = arm_runs["silent"].retry_blocks()
    assert silent and all(b == "<SAME>" for (_a, _y, _t, b) in silent)


def test_generic_rejection_line_placebo_silent(arm_runs):
    """Spec 4.5 (L3 M13): an overruled year names the rule in strict only;
    placebo and silent read "under a governance rule"."""
    def memory_lines(llm):
        return [line for (agent, year, attempt), p in llm.decisions.items()
                if year == 2020 and attempt == 0
                for line in p.splitlines() if line.startswith("- Year 2019:")]
    strict = memory_lines(arm_runs["strict"])
    assert strict and all(
        line.startswith("- Year 2019: maintain demand was applied under the rule on increases "
                        "under scarcity.") for line in strict)
    for arm in ("placebo", "silent"):
        lines = memory_lines(arm_runs[arm])
        assert lines and all(
            line.startswith("- Year 2019: maintain demand was applied under a governance rule.")
            for line in lines), (arm, lines)


def test_no_action_line_after_omitted_field_is_true(arm_runs):
    """Task item 5: after an attempt that left out a required field, the
    feasible-action line names that cause (no action can pass the format
    check without the field); it no longer implies every action is ruled
    out by the rules."""
    blocks = [b for (_a, _y, attempt, b) in arm_runs["strict_omit"].retry_blocks()
              if "Response missing required fields" in b]
    assert blocks
    for b in blocks:
        assert ("No action passes every rule this step, because your response did not include "
                "every required field; if this continues, the default action (maintain demand) "
                "will be applied.") in b
        assert "No action passes every rule this step;" not in b


# ===========================================================================
# 4.5 a year in which nothing executed (WP6 fix round: an ABORTED decision)
# ===========================================================================

NO_DECISION_LEAD = ("no valid decision was read; your request stayed at the amount you received "
                    "the year before.")


def test_memory_line_of_a_year_without_a_decision():
    """The line names no action: the environment left the request at the
    base, last year's receipt (spec 2.1). An action context, even one passed
    by mistake, is not reported."""
    line = build_action_outcome_feedback({"skill_name": "increase_demand", "magnitude_pct": 8.0}, 2020,
                                         60_085.0, 60_085.0, 1, basin="upper_basin", decision_read=False)
    assert line == ("Year 2020: no valid decision was read; your request stayed at the amount you "
                    "received the year before. You requested 60,085 acre-ft and received 60,085 "
                    "acre-ft. Demand fully met. That winter's precipitation in your sub-basin was "
                    "above the previous winter's.")
    short = build_action_outcome_feedback(None, 2047, 1_000.0, 800.0, 0, basin="lower_basin",
                                          gap_reason=describe_gap_reason(
                                              {"gap_reason": "lb_mead_availability"}, "past"),
                                          decision_read=False)
    assert short.startswith(f"Year 2047: {NO_DECISION_LEAD} You requested 1,000 acre-ft and received "
                            "800 acre-ft. Shortfall: 200 acre-ft (20.0% unmet), because Lake Mead could not")


class _UnreadableIn2020(ScriptedLLM):
    """Agent_000 answers nothing readable in 2020: every format retry fails,
    so its 2020 decision is ABORTED and nothing executes."""

    def __call__(self, prompt: str):
        if ("Lesson Learned" not in prompt and "You are Agent_000," in prompt
                and "It is now the year 2020." in prompt):
            with self._lock:
                attempt = self.calls[("Agent_000", 2020)]
                self.calls[("Agent_000", 2020)] += 1
                self.decisions[("Agent_000", 2020, attempt)] = prompt
            return "no decision here", LLMStats(retries=0, success=True)
        return super().__call__(prompt)


def test_aborted_year_memory_line_states_no_decision(tmp_path):
    """Before the fix the 2021 and 2022 prompts said "Year 2020: You chose to
    increase demand (by N%)", the 2019 action, though nothing was decided or
    executed in 2020 (IrrigationLifecycleHooks.pre_year read the action
    context the runner had left from 2019)."""
    llm = _UnreadableIn2020(lambda agent, year, attempt: ("M", "M", "Increase") if year == 2019
                            else ("M", "M", "Keep"))
    with pytest.MonkeyPatch.context() as mp:
        out = _run(mp, tmp_path / "run", llm, "--agents", "3", "--years", "4", "--seed", "7")
    with open(out / "irrigation_farmer_governance_audit.csv", encoding="utf-8-sig") as fh:
        audit = {(r["agent_id"], r["year"]): r for r in csv.DictReader(fh)}
    assert audit[("Agent_000", "2")]["execution_path"] == "aborted"
    with open(out / "simulation_log.csv", encoding="utf-8") as fh:
        log = {(r["agent_id"], r["year"]): r for r in csv.DictReader(fh)}
    request_2020 = float(log[("Agent_000", "2")]["request"])
    assert request_2020 == float(log[("Agent_000", "2")]["base_af"])  # the request stayed at the base
    for year in (2021, 2022):
        memory = {line[:12]: line for line in llm.decisions[("Agent_000", year, 0)].splitlines()
                  if line.startswith("- Year ")}
        assert memory["- Year 2019:"].startswith("- Year 2019: You chose to increase demand (by ")
        assert memory["- Year 2020:"].startswith(
            f"- Year 2020: {NO_DECISION_LEAD} You requested {request_2020:,.0f} acre-ft and received ")
        assert "You chose to" not in memory["- Year 2020:"]
    # a later year with a decision reads normally again
    assert "- Year 2021: You chose to maintain demand." in llm.decisions[("Agent_000", 2022, 0)]


# ===========================================================================
# 4.7 reflection unit behaviour
# ===========================================================================

def test_retries_name_rules_reads_the_broker_mode_or_raises():
    """Review LOW 10: the memory line of an overruled year names the rule
    only in full mode; a runner whose broker carries no retry-feedback mode
    raises instead of falling back to "full", which would name rules in a
    placebo or silent run."""
    from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

    def hooks(runner):
        return IrrigationLifecycleHooks(SimpleNamespace(), runner, [], None, None)

    def with_mode(mode):
        return SimpleNamespace(broker=SimpleNamespace(_retry_feedback_mode=mode))

    assert hooks(with_mode("full"))._retries_name_rules() is True
    for mode in ("placebo", "silent"):
        assert hooks(with_mode(mode))._retries_name_rules() is False
    for runner in (SimpleNamespace(), SimpleNamespace(broker=SimpleNamespace())):
        with pytest.raises(RuntimeError, match="_retry_feedback_mode"):
            hooks(runner)._retries_name_rules()
    with pytest.raises(ValueError, match="unknown"):
        hooks(with_mode("loud"))._retries_name_rules()


def _reflect_once(summaries, memories, *, keep_latest_only=True, years=(2021,)):
    """Drive IrrigationLifecycleHooks._batch_reflect on one agent with a real
    engine and a stub reflection engine returning ``summaries`` in turn, one
    per year: a string is the summary, None an unreadable reply (no insight
    for the agent), an exception instance a failed call."""
    from broker.agents import AgentConfig, BaseAgent
    from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
    from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

    engine = HumanCentricMemoryEngine(window_size=5, top_k_significant=2, seed=1)
    agent = BaseAgent(AgentConfig(name="A1", agent_type="irrigation_farmer", state_params=[],
                                  objectives=[], constraints=[], skills=[]))
    agent.custom_attributes = {}
    agent.is_active = True
    for m in memories:
        engine.add_memory_for_agent(agent, m, {"importance": 0.5, "type": "outcome"})
    queue = list(summaries)
    prompts = []

    class _Engine:
        adapter = None

        def generate_batch_reflection_prompt(self, batch, year, reflection_questions=None,
                                             persona_instruction=None):
            prompts.append(" ".join(m["content"] for m in batch[0]["memories"]))
            return "PROMPT"

        def parse_batch_reflection_response(self, text, batch_ids, year):
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            if item is None:
                return {}
            return {batch_ids[0]: SimpleNamespace(importance=0.6, summary=item)}

        def store_insight(self, aid, ins):
            pass

    env = SimpleNamespace(get_agent_state=lambda aid: {}, current_year=years[0])
    runner = SimpleNamespace(
        broker=SimpleNamespace(config=SimpleNamespace(
            get_reflection_config=lambda: {"batch_size": 1},
            get_reflection_keep_latest_only=lambda: keep_latest_only)),
        agents={"A1": agent}, memory_engine=engine, get_llm_invoke=lambda t: (lambda p: "x"))
    hooks = IrrigationLifecycleHooks(env, runner, [], _Engine(), None)
    for y in years:
        env.current_year = y
        hooks._batch_reflect(year=y - 2018)
    return engine, prompts


def _reflections(engine) -> List[str]:
    """The agent's stored reflections, working and long-term memory together
    (a consolidated item sits in both), each text once."""
    stores = list(engine.working.get("A1", [])) + list(engine.longterm.get("A1", []))
    return list(dict.fromkeys(m["content"] for m in stores if m["content"].startswith("Consolidated")))


def test_single_reflection_kept_and_input_excludes_it():
    engine, prompts = _reflect_once(
        ["I learned one thing.", "I learned a second thing."],
        ["Year 2020: You requested 1,000 acre-ft and received 1,000 acre-ft."],
        years=(2020, 2021))
    contents = [m["content"] for m in engine.working["A1"]]
    assert [c for c in contents if c.startswith("Consolidated")] == [
        "Consolidated Reflection (written in 2021): I learned a second thing."]
    assert "Consolidated" not in prompts[1]  # the 2020 reflection is not in the 2021 input


def test_keep_latest_off_keeps_both():
    engine, _ = _reflect_once(
        ["I learned one thing.", "I learned a second thing."],
        ["Year 2020: You requested 1,000 acre-ft."], keep_latest_only=False, years=(2020, 2021))
    assert [m["content"] for m in engine.working["A1"] if m["content"].startswith("Consolidated")] == [
        "Consolidated Reflection (written in 2020): I learned one thing.",
        "Consolidated Reflection (written in 2021): I learned a second thing."]


def test_reflection_trailing_comma_stripped():
    engine, _ = _reflect_once(['  "I learned to keep my request steady.",  '],
                              ["Year 2020: You requested 1,000 acre-ft."])
    assert engine.working["A1"][-1]["content"] == (
        "Consolidated Reflection (written in 2021): I learned to keep my request steady.")


def test_foreign_figure_not_stored(capsys):
    """Spec 4.7: a summary quoting an acre-ft figure that matches nothing in
    the agent's own memory text is not stored; the drop is counted and
    printed with the figure."""
    engine, _ = _reflect_once(
        ["Requesting 14,420 acre-ft satisfied my needs."],
        ["Year 2020: You requested 160,566 acre-ft and received 160,566 acre-ft."])
    assert _reflections(engine) == []
    out = capsys.readouterr().out
    assert "not stored 1 with a figure foreign to the agent's memory" in out
    assert "[reflect] A1: not stored, 14,420 acre-ft matches no figure in its memory" in out
    engine, _ = _reflect_once(
        ["Requesting 160,566 acre-ft satisfied my needs."],
        ["Year 2020: You requested 160,566 acre-ft and received 160,566 acre-ft."])
    assert engine.working["A1"][-1]["content"].endswith("Requesting 160,566 acre-ft satisfied my needs.")


MOHAVE_2019 = "Year 2019: You requested 20,155 acre-ft and received 20,155 acre-ft."


@pytest.mark.parametrize("dropped", [
    "Requesting 14,420 acre-ft satisfied my needs.",  # a foreign figure
    "   ",                                            # an empty summary
    None,                                             # no readable reply
    RuntimeError("model call failed"),               # a failed call
], ids=["foreign", "empty", "unparsed", "call_failed"])
def test_summary_not_stored_removes_the_old_reflection(dropped, capsys):
    """Review HIGH 1 (the reviewer's probe scratchpad/rv/stale_reflection.py):
    under keep_latest_only the earlier reflection went only when a new one
    was stored, so a summary dropped at the end of 2021 left the 2020
    reflection in the 2022 prompt, older than the previous year (S10). Now
    every path that stores nothing removes it."""
    engine, _ = _reflect_once(["I learned to keep my request steady.", dropped],
                              [MOHAVE_2019], years=(2020, 2021))
    assert _reflections(engine) == []
    removed = re.findall(r"removed (\d+) earlier reflection items of agents with no new one",
                         capsys.readouterr().out)
    assert [int(n) > 0 for n in removed] == [False, True]  # nothing in 2020, the 2020 one in 2021


def test_summary_not_stored_keeps_the_old_one_when_keep_latest_is_off():
    """The removal belongs to keep_latest_only; with it off (the framework
    default) reflections accumulate as before."""
    engine, _ = _reflect_once(["I learned to keep my request steady.", None],
                              [MOHAVE_2019], keep_latest_only=False, years=(2020, 2021))
    assert _reflections(engine) == [
        "Consolidated Reflection (written in 2020): I learned to keep my request steady."]


def test_rounded_own_figure_is_stored():
    """Review HIGH 1: "about 20,000 acre-ft" for the memory line's 20,155 is
    the agent's own figure rounded (within 5 percent), so it is stored and
    replaces the 2020 reflection (the probe's end-of-2021 summary)."""
    engine, _ = _reflect_once(["I learned to keep my request steady.",
                               "I requested about 20,000 acre-ft and it worked."],
                              [MOHAVE_2019], years=(2020, 2021))
    assert _reflections(engine) == [
        "Consolidated Reflection (written in 2021): I requested about 20,000 acre-ft and it worked."]


@pytest.mark.parametrize("summary,foreign", [
    ("I requested about 20,000 acre-ft and it worked.", []),
    ("Requesting 20155 acre-ft worked.", []),
    ("Requesting 14420 acre-ft would have been better.", ["14420 acre-ft"]),
    ("Requesting 14,420 acre-ft would have been better.", ["14,420 acre-ft"]),
    ("Requesting 18,000 acre-ft would have been better.", ["18,000 acre-ft"]),
    ("Lake Powell held 10.4 million acre-ft.", ["10.4 million"]),
    ("I received 85% of my request.", []),          # 100 minus the stated 15.0% unmet
    ("About 15% of my request was not delivered.", []),
    ("I received 70% of my request.", ["70%"]),
    ("I received 70 percent of my request.", ["70 percent"]),
    ("I received 100% of my request in 2019.", []),
    ("In 2021 I kept my request for 2 years under Tier 2.", []),
])
def test_foreign_figures_tolerate_rounding_and_read_every_format(summary, foreign):
    """Review HIGH 1: a figure within 5 percent of one of the agent's own
    figures is its own; figures without separators and percentages are read
    too; years, counts and tier numbers are not figures."""
    from examples.irrigation_abm.run_experiment import _foreign_figures

    own = (MOHAVE_2019 + " Year 2020: You chose to maintain demand. You requested 20,155 "
           "acre-ft and received 17,132 acre-ft. Shortfall: 3,023 acre-ft (15.0% unmet).")
    assert _foreign_figures(summary, own) == foreign
