"""Regression lock for the options-text parity fix (2026-09).

THE BUG: vaccination_demo's ``config/prompts/individual.txt`` rendered
``Available actions: {skills}`` -- a placeholder the context builder never
fills -- so the model only ever saw the hardcoded YAML legend that used to
live at ``agent_types.yaml``'s ``decision`` field description
("1=get_vaccinated, 2=delay, 3=refuse"). Meanwhile RAG skill retrieval
(``broker/core/skill_broker_engine.py`` "Phase 28" block ->
``broker/components/governance/retriever.py``) re-ranks the eligible skills
per call, and ``_inject_options_text``
(``broker/core/_skill_filtering.py``) rebuilds ``dynamic_skill_map`` in
THAT re-ranked order. ``broker/utils/parsing/unified_adapter.py`` decodes
the model's digit answer against ``dynamic_skill_map`` -- so whenever the
map order differed from the static legend the model was actually shown,
the decoded skill was WRONG. Year 1 (empty memory, nothing to rank on)
always matched; verified 57-63% mismatch from year 2 on across three runs.

THE FIX (two parts, both locked here):
  1. Config (examples/vaccination_demo): ``prompts/individual.txt`` now
     renders ``{options_text}`` (the SAME list ``dynamic_skill_map`` is
     built from) and ``agent_types.yaml`` sets
     ``parsing.full_disclosure: true`` (keeps the retriever from
     re-ranking at all, mirroring ``examples/irrigation_abm``).
  2. Runtime (broker/core/_skill_filtering.py): ``_inject_options_text``
     now calls ``_assert_options_text_parity``, which raises loud whenever
     the installed map order differs from the registry (YAML ``actions:``)
     order AND the agent's prompt template renders neither
     ``{options_text}`` nor ``{skills_text}``.

Falsification: every test in this file that exercises the guard was run
against the PRE-FIX ``_inject_options_text`` (no ``agent_type`` param, no
guard call) and failed as expected (guard tests: no ``RuntimeError``
raised; config tests: ``{skills}`` present / ``full_disclosure`` absent).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from broker.core._skill_filtering import SkillFilterMixin
from broker.utils.agent_config import AgentTypeConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
VAX_CONFIG = REPO_ROOT / "examples" / "vaccination_demo" / "config" / "agent_types.yaml"
VAX_PROMPT = REPO_ROOT / "examples" / "vaccination_demo" / "config" / "prompts" / "individual.txt"


# ---------------------------------------------------------------------------
# Minimal fakes -- just enough surface for SkillFilterMixin's guard to run
# ---------------------------------------------------------------------------

class _FakeSkillDef:
    def __init__(self, skill_id: str):
        self.skill_id = skill_id
        self.description = skill_id


class _FakeSkillRegistry:
    def get(self, skill_id: str):
        return _FakeSkillDef(skill_id)


class _FakeAgentConfig:
    """Stand-in for AgentTypeConfig: fixed registry (YAML actions:) order."""

    def __init__(
        self, action_ids: List[str], decision_type: str = None,
        decision_key: str = "decision",
    ):
        self._action_ids = action_ids
        self._decision_type = decision_type
        self._decision_key = decision_key

    def get_base_type(self, agent_type: str) -> str:
        return agent_type

    def get(self, agent_type: str) -> Dict[str, Any]:
        block: Dict[str, Any] = {"actions": [{"id": a} for a in self._action_ids]}
        if self._decision_type is not None:
            block["response_format"] = {
                "fields": [{"key": self._decision_key, "type": self._decision_type}],
            }
        return block

    def get_shared(self, key: str, default: Any = None) -> Any:
        return default


class _BoomAgentConfig:
    """Config stand-in whose lookup always raises -- exercises item 5:
    an unresolvable agent_type must RAISE, never silently pass."""

    def get_base_type(self, agent_type: str) -> str:
        raise ValueError(f"boom resolving {agent_type!r}")

    def get(self, agent_type: str) -> Dict[str, Any]:
        raise ValueError(f"boom resolving {agent_type!r}")


class _FakeContextBuilder:
    def __init__(self, prompt_templates: Dict[str, str]):
        self.prompt_templates = prompt_templates


class _Engine(SkillFilterMixin):
    """Host object mimicking the SkillBrokerEngine attrs the mixin reads."""

    def __init__(self, config, skill_registry, context_builder):
        self.config = config
        self.skill_registry = skill_registry
        self.context_builder = context_builder


def _engine(
    action_ids: List[str], template: str, decision_type: str = None,
    decision_key: str = "decision",
) -> _Engine:
    return _Engine(
        config=_FakeAgentConfig(action_ids, decision_type=decision_type, decision_key=decision_key),
        skill_registry=_FakeSkillRegistry(),
        context_builder=_FakeContextBuilder({"individual": template}),
    )


def _engine_with_config(config, template: str) -> _Engine:
    return _Engine(
        config=config,
        skill_registry=_FakeSkillRegistry(),
        context_builder=_FakeContextBuilder({"individual": template}),
    )


REGISTRY_ORDER = ["get_vaccinated", "delay", "refuse"]
RERANKED_ORDER = ["refuse", "get_vaccinated", "delay"]  # what RAG handed back


# ---------------------------------------------------------------------------
# Runtime guard: unit tests
# ---------------------------------------------------------------------------

def test_guard_raises_when_reranked_order_hidden_from_template():
    """Core falsification: a re-ranked map + a template with NO
    {options_text}/{skills_text} placeholder (the pre-fix vaccination_demo
    shape, ``Available actions: {skills}``) must raise loud."""
    engine = _engine(
        action_ids=REGISTRY_ORDER,
        template="Available actions: {skills}\n{response_format}",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


def test_guard_silent_when_template_renders_options_text():
    """Same re-rank, but the template DOES render {options_text} -- the
    fixed vaccination_demo shape. Must not raise, and the map must reflect
    the actual (re-ranked) order the model was shown."""
    engine = _engine(
        action_ids=REGISTRY_ORDER,
        template="Available actions:\n{options_text}\n{response_format}",
    )
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")
    assert context["personal"]["dynamic_skill_map"] == {
        "1": "refuse", "2": "get_vaccinated", "3": "delay",
    }


def test_guard_silent_when_order_matches_registry():
    """No re-rank happened (installed order == registry order) -- must not
    raise even though the template lacks {options_text}: a static legend
    built from registry order would still be correct in this case."""
    engine = _engine(
        action_ids=REGISTRY_ORDER,
        template="Available actions: {skills}\n{response_format}",
    )
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(context, list(REGISTRY_ORDER), agent_type="individual")
    assert context["personal"]["dynamic_skill_map"] == {
        "1": "get_vaccinated", "2": "delay", "3": "refuse",
    }


def test_option_text_overrides_used_when_present_in_state():
    """WP2 (irrigation v3, spec 2.6): a per-decision ``option_text_overrides``
    dict in ``context["state"]`` -- set from an agent's ``custom_attributes``
    by ``AttributeProvider``, e.g. ``irrigation_personas.build_option_texts``
    -- overrides the registry's static description, by skill id. A skill
    absent from the override dict still falls back to its registry
    description."""
    engine = _engine(
        action_ids=REGISTRY_ORDER,
        template="Available actions:\n{options_text}\n{response_format}",
    )
    context: Dict[str, Any] = {
        "personal": {},
        "state": {
            "option_text_overrides": {
                "get_vaccinated": "Get the shot now.",
                "delay": "Wait one more month.",
            },
        },
    }
    engine._inject_options_text(context, list(REGISTRY_ORDER), agent_type="individual")
    options_text = context["personal"]["options_text"]
    assert "1. Get the shot now." in options_text
    assert "2. Wait one more month." in options_text
    # "refuse" has no override entry -- falls back to the registry
    # description (the fake registry echoes the skill id back).
    assert "3. refuse" in options_text


def test_no_option_text_overrides_falls_back_to_registry_description():
    """WP2 review round 1 (LOW 10): renamed from test_flood_options_unchanged
    -- this uses the generic fake vaccination-style registry/engine harness
    above, not flood's real config, so the old name overclaimed what it
    checks. No ``state`` key at all -- every domain that never sets
    ``option_text_overrides`` (flood included, but not exercised here)
    renders byte-identically to before this override existed: the
    registry description, verbatim."""
    engine = _engine(
        action_ids=REGISTRY_ORDER,
        template="Available actions:\n{options_text}\n{response_format}",
    )
    context: Dict[str, Any] = {"personal": {}}  # no "state" key at all
    engine._inject_options_text(context, list(REGISTRY_ORDER), agent_type="individual")
    assert context["personal"]["options_text"] == "1. get_vaccinated\n2. delay\n3. refuse"


def test_guard_silent_for_name_based_decision_templates():
    """Discovered mid-fix: MA flood's government/insurance institutional
    agents render NO {options_text} placeholder at all -- they hand-write
    every skill's literal id into the template's own static text (an
    options bullet list, an inline JSON example asking for the literal
    NAME) and the model answers with that name, not a digit.
    unified_adapter.py resolves a name-based answer by alias match, not by
    ``dynamic_skill_map`` position, so a re-ranked map order carries no
    decode risk there. The guard must stay silent whenever every installed
    skill's literal id is spelled out in the template -- this is what let
    `broker/tests/test_mixed_population_pr8.py` (a real MA-flood run) pass
    with the guard installed."""
    engine = _engine(
        action_ids=["large_increase_subsidy", "maintain_subsidy", "large_decrease_subsidy"],
        template=(
            "### YOUR OPTIONS\n"
            "- large_increase_subsidy: expand\n"
            "- maintain_subsidy: hold\n"
            "- large_decrease_subsidy: shrink\n"
            '{{"decision": "large_increase_subsidy | maintain_subsidy | large_decrease_subsidy"}}'
        ),
    )
    context: Dict[str, Any] = {"personal": {}}
    # Re-ranked order, same as the RAG path would install.
    engine._inject_options_text(
        context,
        ["large_decrease_subsidy", "large_increase_subsidy", "maintain_subsidy"],
        agent_type="individual",
    )
    # no raise -- and the map still reflects the real (re-ranked) order,
    # since the parser resolves this agent type by name, not by position.
    assert context["personal"]["dynamic_skill_map"]["1"] == "large_decrease_subsidy"


def test_guard_still_raises_when_only_some_names_are_spelled_out():
    """The name-based exemption requires ALL installed skills to be
    spelled out literally -- a template documenting only some of them is
    still vulnerable for the undocumented ones."""
    engine = _engine(
        action_ids=["large_increase_subsidy", "maintain_subsidy", "large_decrease_subsidy"],
        template="### YOUR OPTIONS\n- large_increase_subsidy: expand\n{response_format}",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(
            context,
            ["large_decrease_subsidy", "large_increase_subsidy", "maintain_subsidy"],
            agent_type="individual",
        )


def test_guard_skipped_without_agent_type():
    """Backward-compat: existing callers that never pass agent_type (e.g. a
    test driving _inject_options_text directly) keep working exactly as
    before the fix -- the guard is opt-in via the new keyword."""
    engine = _engine(
        action_ids=REGISTRY_ORDER,
        template="Available actions: {skills}\n{response_format}",
    )
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(context, RERANKED_ORDER)  # no agent_type
    assert context["personal"]["dynamic_skill_map"]["1"] == "refuse"


# ---------------------------------------------------------------------------
# Config-level locks
# ---------------------------------------------------------------------------

def test_vaccination_prompt_renders_options_text():
    """individual.txt must render {options_text}, not the never-filled
    {skills} placeholder."""
    text = VAX_PROMPT.read_text(encoding="utf-8")
    assert "{options_text}" in text
    assert "{skills}" not in text


def test_vaccination_config_wires_individual_into_full_disclosure():
    """Belt-and-braces: the retriever must never re-rank vaccination's
    3-skill menu at all (mirrors examples/irrigation_abm)."""
    cfg = AgentTypeConfig.load(str(VAX_CONFIG))
    assert "individual" in cfg.get_full_disclosure_agent_types()


def test_vaccination_decision_field_has_no_hardcoded_legend():
    """The removed BLOCKER: agent_types.yaml's decision field must not
    hand-roll a digit legend that can drift from the live options order."""
    import yaml

    cfg = yaml.safe_load(VAX_CONFIG.read_text(encoding="utf-8"))
    decision_field = next(
        f for f in cfg["shared"]["response_format"]["fields"] if f.get("key") == "decision"
    )
    assert "description" not in decision_field or "=" not in decision_field.get("description", "")


# ---------------------------------------------------------------------------
# Parity property: decode a digit against a RE-RANKED map
# ---------------------------------------------------------------------------

def test_decoded_digit_matches_numbered_prompt_order():
    """End-to-end parity property: decoding a digit answer against a
    RE-RANKED dynamic_skill_map must equal what the NUMBERED prompt
    actually listed at that position -- NOT what the registry (YAML
    actions:) order would imply. This is the exact property that was
    violated 57-63% of the time pre-fix.
    """
    # A real dynamic_skill_map as _inject_options_text builds it after a
    # RAG re-rank: refuse first, get_vaccinated second, delay third --
    # deliberately NOT the registry order (get_vaccinated, delay, refuse).
    dynamic_map = {"1": "refuse", "2": "get_vaccinated", "3": "delay"}
    numbered_prompt_lines = {k: f"{k}. {v}" for k, v in dynamic_map.items()}

    context = {"personal": {"dynamic_skill_map": dynamic_map}}
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)  # get_skill_map's dynamic-map
    # branch returns before touching any other instance state -- see
    # broker/utils/agent_config.py:get_skill_map priority-0 check.
    resolved = cfg.get_skill_map("individual", context)

    assert resolved == dynamic_map
    for digit, skill in resolved.items():
        assert numbered_prompt_lines[digit] == f"{digit}. {skill}"

    # The bug: decoding "1" against the REGISTRY order would have produced
    # "get_vaccinated" (registry position 1). The fix decodes "1" as what
    # the prompt ACTUALLY listed at position 1 in this call: "refuse".
    assert resolved["1"] == "refuse"
    assert resolved["1"] != REGISTRY_ORDER[0]


# ---------------------------------------------------------------------------
# Silent-failure review hardening (2026-09): every branch that cannot
# verify parity must RAISE, never silently return. Fail-open holes found
# in the first version of this guard, closed here.
# ---------------------------------------------------------------------------

def test_p0_missing_template_evaluates_real_base_default_and_raises():
    """Item 1 (P0): a missing prompt_templates lookup used to `return`
    silently. The REAL fallback for BaseAgentContextBuilder is
    DEFAULT_PROMPT_TEMPLATE ('ACT:{skills}') -- the exact vaccination_demo
    shape. The guard must evaluate against that real fallback and raise,
    not assume safety it never checked."""
    from broker.components.context.builder import BaseAgentContextBuilder

    cb = BaseAgentContextBuilder(agents={}, prompt_templates={})  # no template registered
    engine = _Engine(
        config=_FakeAgentConfig(REGISTRY_ORDER),
        skill_registry=_FakeSkillRegistry(),
        context_builder=cb,
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


def test_p0_missing_template_tiered_default_is_safe_and_does_not_raise():
    """Companion: TieredContextBuilder's OWN built-in default already
    carries {options_text}, so the same missing-lookup case must NOT
    raise when that is the builder actually in play -- proving the guard
    evaluates the real per-class fallback, not a blanket assumption
    either way."""
    from broker.components.context.builder import TieredContextBuilder

    cb = TieredContextBuilder(agents={}, prompt_templates={})  # no template registered
    engine = _Engine(
        config=_FakeAgentConfig(REGISTRY_ORDER),
        skill_registry=_FakeSkillRegistry(),
        context_builder=cb,
    )
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")  # no raise


def test_p0_missing_template_unrecognized_builder_class_raises():
    """A context_builder that is neither known class (e.g. a bespoke or
    future builder) must fail closed -- the guard cannot know what will
    actually render, so it must not guess "safe"."""
    class _MysteryBuilder:
        prompt_templates: Dict[str, str] = {}

    engine = _Engine(
        config=_FakeAgentConfig(REGISTRY_ORDER),
        skill_registry=_FakeSkillRegistry(),
        context_builder=_MysteryBuilder(),
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


def test_p1_substring_exemption_requires_whole_token_match():
    """Item 4: a bare `sid in template` substring test is satisfiable by a
    LONGER id containing the shorter one as a substring (e.g. "insurance"
    inside "reinsurance_program"). The word-boundary regex must reject
    that and still raise."""
    engine = _engine(
        action_ids=["insurance", "no_insurance"],
        # "insurance" is only ever present as a substring of
        # "reinsurance_program" / "no_insurance_program" -- never as its
        # own whole token -- so the (correct) regex exemption must fail.
        template="Consult the reinsurance_program guidelines.\n{response_format}",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(
            context, ["no_insurance", "insurance"], agent_type="individual",
        )


def test_p1_substring_exemption_pure_regex_falsification():
    """Item 4, isolated from the digit-ask signal: BOTH skill ids are
    present as a bare substring of a longer word in the template (so the
    OLD `sid in template` check would have wrongly exempted this and NOT
    raised), but NEITHER is present as its own whole token. The
    word-boundary regex must still raise."""
    engine = _engine(
        action_ids=["insurance", "refuse"],
        # "insurance" only ever appears inside "reinsurance_program";
        # "refuse" only ever appears inside "refuse_case_pending" --
        # never as a standalone word.
        template=(
            "See the reinsurance_program notes and the "
            "refuse_case_pending queue.\n{response_format}"
        ),
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(
            context, ["refuse", "insurance"], agent_type="individual",
        )


def test_p1_name_based_exemption_denied_when_decision_field_is_numeric_choice():
    """Item 4: a template can legitimately spell out every skill name AND
    still ask for a digit (response_format.decision declared type:
    "choice"). Spelled-out names alone must not exempt that shape."""
    engine = _engine(
        action_ids=["get_vaccinated", "delay", "refuse"],
        template=(
            "Options: get_vaccinated, delay, refuse.\n"
            '{{"decision": "<Numeric ID, choose ONE from: {valid_choices_text}>"}}'
        ),
        decision_type="choice",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


def test_p1_name_based_exemption_denied_when_valid_choices_text_present():
    """Item 4: same disqualifier, signalled directly by a literal
    {valid_choices_text} placeholder in the template rather than a
    declared response_format type."""
    engine = _engine(
        action_ids=["get_vaccinated", "delay", "refuse"],
        template=(
            "Options: get_vaccinated, delay, refuse. Answer with one of: "
            "{valid_choices_text}"
        ),
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


def test_p1_name_based_exemption_still_applies_without_digit_ask():
    """Companion: the SAME spelled-out template, with no digit-ask signal
    at all (no {valid_choices_text}, decision field not type: "choice"),
    is still safely exempt -- the tightened rule must not have broken the
    legitimate MA-flood-shaped case."""
    engine = _engine(
        action_ids=["get_vaccinated", "delay", "refuse"],
        template="Options: get_vaccinated, delay, refuse.\n{{\"decision\": \"<name>\"}}",
        decision_type="text",
    )
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")  # no raise


def test_p1_unresolvable_agent_type_raises_named():
    """Item 5, first branch: an agent_type with NO resolvable registry
    (actions:) list -- ``_get_action_ids`` returns [] rather than raising
    -- used to silently ``return`` (exempt) while RAG can still install a
    re-ranked map for it. Must raise instead, naming the agent_type."""
    engine = _engine(action_ids=[], template="{options_text}")
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="no resolvable registry"):
        engine._inject_options_text(
            context, ["some_skill", "other_skill"], agent_type="unknown_type",
        )


def test_p1_get_action_ids_exception_raises_with_agent_type_named():
    """Item 5, second branch: _get_action_ids itself raising (not just
    returning empty) must also raise with the agent_type named, never a
    bare `except Exception: return`."""
    engine = _engine_with_config(
        _BoomAgentConfig(), template="{options_text}",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="cannot verify agent_type='individual'"):
        engine._inject_options_text(context, ["a", "b"], agent_type="individual")


# ---------------------------------------------------------------------------
# Item 2: TieredContextBuilder's OWN fallback dynamic_skill_map builder
# (a SECOND, previously unchecked choke point) must also be checked.
# ---------------------------------------------------------------------------

class _FakeAgentWithSkills:
    """Stand-in for the Agent object TieredContextBuilder.format_prompt's
    fallback branch reads via `agent.get_available_skills()` -- a
    DIFFERENT source than SkillFilterMixin's registry-driven list."""

    def __init__(self, skills: List[str]):
        self._skills = skills

    def get_available_skills(self) -> List[str]:
        return self._skills


def _write_minimal_individual_yaml(tmp_path: Path) -> str:
    import textwrap
    yaml_path = tmp_path / "agent_types.yaml"
    yaml_path.write_text(textwrap.dedent("""
        shared: {}
        individual:
          agent_type: individual
          actions:
            - id: get_vaccinated
              aliases: ["1"]
            - id: delay
              aliases: ["2"]
            - id: refuse
              aliases: ["3"]
          parsing:
            default_skill: delay
    """).strip(), encoding="utf-8")
    return str(yaml_path)


def test_p1_tiered_own_fallback_map_builder_is_checked_and_raises(tmp_path: Path):
    """Item 2: format_prompt's `if not options_text and agent:` branch
    (broker/components/context/tiered.py) builds a dynamic_skill_map from
    `agent.get_available_skills()` -- a re-ranked order here -- and used
    to render it with NO parity check at all. Must now raise exactly like
    the SkillFilterMixin path."""
    from broker.components.context.tiered import TieredContextBuilder

    yaml_path = _write_minimal_individual_yaml(tmp_path)
    template = "Available actions: {skills}\n{response_format}"  # no {options_text}
    agent = _FakeAgentWithSkills(["refuse", "get_vaccinated", "delay"])  # re-ranked

    cb = TieredContextBuilder(
        agents={"A1": agent},
        skill_registry=_FakeSkillRegistry(),
        prompt_templates={"individual": template},
        yaml_path=yaml_path,
    )
    context: Dict[str, Any] = {"agent_type": "individual", "personal": {"id": "A1"}}
    with pytest.raises(RuntimeError, match="Options-text parity"):
        cb.format_prompt(context)


def test_p1_tiered_own_fallback_map_builder_safe_with_options_text(tmp_path: Path):
    """Companion: the SAME re-ranked fallback map, but the template DOES
    render {options_text} -- must not raise, and the rendered prompt must
    show the live (re-ranked) order."""
    from broker.components.context.tiered import TieredContextBuilder

    yaml_path = _write_minimal_individual_yaml(tmp_path)
    template = "{system_prompt}\nAvailable actions:\n{options_text}\n{response_format}"
    agent = _FakeAgentWithSkills(["refuse", "get_vaccinated", "delay"])  # re-ranked

    cb = TieredContextBuilder(
        agents={"A1": agent},
        skill_registry=_FakeSkillRegistry(),
        prompt_templates={"individual": template},
        yaml_path=yaml_path,
    )
    context: Dict[str, Any] = {"agent_type": "individual", "personal": {"id": "A1"}}
    formatted = cb.format_prompt(context)  # no raise
    assert "1. refuse" in formatted
    assert "2. get_vaccinated" in formatted


def test_p1_name_based_exemption_denied_when_id_contains_a_digit():
    """Second-round hardening: a digit-bearing skill id disqualifies the
    name-based exemption on its own, regardless of everything else being
    safe. Rationale: unified_adapter.py Case 2 extracts the FIRST digit
    ANYWHERE in the model's answer string and decodes POSITIONALLY if
    that digit is a dynamic_skill_map key, before ever trying name/alias
    resolution -- a digit-bearing id like "phase_2_skill" could get
    silently mis-decoded via that embedded digit even with every name
    spelled out in full and no numbered-choice instruction anywhere."""
    engine = _engine(
        action_ids=["phase_1_skill", "phase_2_skill"],
        template="Options: phase_1_skill, phase_2_skill.\n{{\"decision\": \"<name>\"}}",
        decision_type="text",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(
            context, ["phase_2_skill", "phase_1_skill"], agent_type="individual",
        )


# ---------------------------------------------------------------------------
# Precision pass (2026-09, second round): the declared response_format
# decision type only matters when the template actually RENDERS the
# placeholder that could turn it into a numeric instruction
# ({response_format}); {valid_choices_text} is unconditionally a digit
# invitation regardless of declared type. Resolves the MA flood
# government/insurance conflict WITHOUT touching the frozen config.
# ---------------------------------------------------------------------------

def test_p2_type_choice_never_rendered_is_exempt():
    """A template can declare the decision field type: "choice" in YAML
    (even a stale, dead declaration) and still be safely name-based, AS
    LONG AS it never renders {response_format} (or any other placeholder)
    to actually turn that declaration into a numeric-ID instruction. This
    is exactly MA flood's government.txt/insurance.txt shape: type:
    "choice" declared, but the template hand-writes its own JSON and
    never references {response_format} -- the declaration is inert."""
    engine = _engine(
        action_ids=["get_vaccinated", "delay", "refuse"],
        template=(
            "Options: get_vaccinated, delay, refuse.\n"
            '{{"decision": "<name>"}}'  # hand-written, no {response_format}
        ),
        decision_type="choice",  # declared, but never rendered
    )
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")  # no raise


def test_p2_valid_choices_text_disqualifies_even_with_all_names_spelled_out():
    """Companion / regression lock: {valid_choices_text} is UNCONDITIONALLY
    a digit-count string ("1, 2, or 3") built by _inject_options_text,
    independent of any declared response_format type. Its presence must
    disqualify the name-based exemption even when every skill name is
    ALSO spelled out in full and even with type: "choice" declared (so a
    future refactor cannot accidentally make this placeholder's
    disqualifying effect conditional on the declared type, mirroring the
    {response_format} treatment -- it must stay unconditional)."""
    engine = _engine(
        action_ids=["get_vaccinated", "delay", "refuse"],
        template=(
            "Options: get_vaccinated, delay, refuse. Answer with one of: "
            "{valid_choices_text}"
        ),
        decision_type="choice",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


# ---------------------------------------------------------------------------
# Round 3 (2026-09, full-suite regression + silent-failure hunter round 2):
# fixing 5 false BLOCKs the tightened guard introduced, plus 2 hunter
# findings and one drift-risk closure.
# ---------------------------------------------------------------------------

def test_p3a_unresolvable_registry_single_skill_returns_early():
    """Item A(1): a single-skill dynamic_skill_map has no ordering that
    could ever mis-decode, whether or not a registry is resolvable at
    all. Reproduces tests/test_skill_retrieval.py::test_skill_broker_integration's
    real shape: agent_type with zero YAML config (registry_ids == [])
    and a one-skill installed order."""
    engine = _engine(action_ids=[], template="ACT:{skills}")  # no {options_text}
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(context, ["s1"], agent_type="default")  # no raise


def test_p3a_unresolvable_registry_multi_skill_falls_through_to_options_text():
    """Item A(2): reproduces tests/test_v3_2_features.py::test_v3_2_full_integration's
    real shape -- skills sourced from AgentConfig.skills directly (no YAML
    actions: block at all, so registry_ids == []), multi-skill order, and
    a template that DOES render a live legend ({skills}, filled by
    BaseAgentContextBuilder for this exact usage pattern). Must fall
    through to the template check instead of raising unconditionally."""
    engine = _engine(action_ids=[], template="CORE:{memory}\nSKILLS:{skills}")
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(
        context, ["buy_insurance", "do_nothing"], agent_type="individual",
    )  # no raise


def test_p3a_unresolvable_registry_multi_skill_no_signal_still_raises():
    """Companion: fail-safe direction preserved. Unresolvable registry +
    multi-skill order + a template with NO live legend and NO safe
    name-based shape must still raise -- the fall-through is not a
    blanket exemption for every unresolvable-registry agent_type."""
    engine = _engine(action_ids=[], template="Decide now.\n{response_format}")
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity"):
        engine._inject_options_text(
            context, ["buy_insurance", "do_nothing"], agent_type="individual",
        )


def test_p3c_secondary_choice_type_is_also_numeric():
    """Item C (hunter NEW-1): response_format.py's `secondary_choice`
    type ALSO renders a numeric-ID instruction
    ("OPTIONAL: Numeric ID from: ..., or 0 for none",
    response_format.py:150-153) -- the first version of this check only
    recognized `type: "choice"`, missing `secondary_choice` entirely, so
    a template rendering {response_format} with a secondary_choice
    decision field could pass the name-based exemption despite inviting
    a digit answer."""
    engine = _engine(
        action_ids=["get_vaccinated", "delay", "refuse"],
        template=(
            "Options: get_vaccinated, delay, refuse.\n{response_format}"
        ),
        decision_type="secondary_choice",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


def test_p3d_choice_type_under_non_decision_key_is_still_numeric():
    """Item D (hunter NEW-2): the numeric-choice check used to require
    the field's key to be in a guessed decision_keywords set (defaulting
    to just {"decision"}), but unified_adapter.py's OWN default decision
    keyword list is wider (["decision", "choice", "action"],
    unified_adapter.py:427) and a YAML need not declare
    parsing.decision_keywords explicitly to use it. A choice-typed field
    keyed "action" (in the parser's default list, but NOT in the old
    hardcoded {"decision"} default) must still be detected as
    numeric-choice."""
    engine = _engine(
        action_ids=["get_vaccinated", "delay", "refuse"],
        template=(
            "Options: get_vaccinated, delay, refuse.\n{response_format}"
        ),
        decision_type="choice",
        decision_key="action",  # not "decision" -- and parsing.decision_keywords is unset
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity violation"):
        engine._inject_options_text(context, RERANKED_ORDER, agent_type="individual")


def test_p3e_tiered_default_fallback_imports_the_real_constant():
    """Item E (hunter NEW-4): the guard's TieredContextBuilder no-template
    fallback must import broker.components.context.tiered's
    TIERED_DEFAULT_PROMPT_TEMPLATE constant directly, not re-type a copy
    of it -- proven by monkeypatching the re-exported constant on
    broker.components.context.builder (the exact name _skill_filtering.py
    imports) and confirming the guard's resolved fallback template
    reflects the patched value. A hand-typed copy would be blind to this
    change and keep returning its own frozen string."""
    import broker.components.context.builder as builder_mod
    from broker.components.context.builder import TieredContextBuilder

    original = builder_mod.TIERED_DEFAULT_PROMPT_TEMPLATE
    sentinel = "SENTINEL_TEMPLATE_{options_text}_MARKER"
    builder_mod.TIERED_DEFAULT_PROMPT_TEMPLATE = sentinel
    try:
        cb = TieredContextBuilder(agents={}, prompt_templates={})  # no template registered
        engine = _Engine(
            config=_FakeAgentConfig(REGISTRY_ORDER),
            skill_registry=_FakeSkillRegistry(),
            context_builder=cb,
        )
        template, _path = engine._resolve_template_for_parity_check("individual")
        assert template == sentinel, (
            f"expected the guard to resolve the LIVE (patched) constant, got: {template!r}"
        )
    finally:
        builder_mod.TIERED_DEFAULT_PROMPT_TEMPLATE = original


# ---------------------------------------------------------------------------
# Round 4 (2026-09, reviewer APPROVE + hunter REQUEST CHANGES on the same
# spot): {skills} in the no-registry fall-through was accepted
# unconditionally -- it is not a safe legend on its own.
# ---------------------------------------------------------------------------

def test_p4_1_skills_placeholder_not_accepted_when_template_invites_digit():
    """Item 1: a template rendering {skills} (unnumbered, safe for a pure
    name-based decision) but ALSO {response_format} with a numeric-choice
    decision field invites a digit answer just like the vaccination_demo
    shape did -- {skills} showing an unnumbered list does not tell the
    model which digit maps to which name. Must still raise for a
    re-ranked, unresolvable-registry, multi-skill map."""
    engine = _engine(
        action_ids=[],  # unresolvable registry -- the fall-through path
        template="CORE:{memory}\nSKILLS:{skills}\n{response_format}",
        decision_type="choice",
    )
    context: Dict[str, Any] = {"personal": {}}
    with pytest.raises(RuntimeError, match="Options-text parity"):
        engine._inject_options_text(
            context, ["buy_insurance", "do_nothing", "wait_and_see"],
            agent_type="individual",
        )


def test_p4_1_skills_placeholder_still_accepted_without_digit_invitation():
    """Companion: the SAME {skills}-only template, with no digit-invitation
    signal anywhere (no {response_format}, no {valid_choices_text}, no
    hand-written numbered list) -- still safely accepted. Proves the fix
    narrows the {skills} exemption rather than removing it outright
    (tests/test_v3_2_features.py::test_v3_2_full_integration's real shape
    -- see test_p3a_unresolvable_registry_multi_skill_falls_through_to_options_text
    above -- must keep passing)."""
    engine = _engine(action_ids=[], template="CORE:{memory}\nSKILLS:{skills}")
    context: Dict[str, Any] = {"personal": {}}
    engine._inject_options_text(
        context, ["buy_insurance", "do_nothing"], agent_type="individual",
    )  # no raise


# ---------------------------------------------------------------------------
# Round 4, item 2: the residual P2 close -- a POST-RENDER assertion at the
# single point the final prompt string is handed to the LLM
# (broker/core/skill_broker_engine.py, right after format_prompt()).
# Everything above only verifies the un-rendered TEMPLATE; this verifies
# what the model actually received.
# ---------------------------------------------------------------------------

def test_p4_2_post_render_check_raises_for_base_agent_context_builder_gap():
    """The exact real-world shape this check exists for: examples/cat_model's
    run_cat.py (pre-fix) kept ExperimentBuilder's DEFAULT context builder
    (BaseAgentContextBuilder, no hub) with a template rendering
    {options_text} -- but BaseAgentContextBuilder.format_prompt NEVER
    reads context["personal"] at all (only top-level context keys), so
    {options_text} rendered as SafeFormatter's "[N/A]" default. Every
    earlier (template-only) check reports this as SAFE ({options_text} is
    present in the template) -- only a check on the ACTUAL rendered
    string catches it."""
    from broker.core._skill_filtering import assert_rendered_prompt_shows_options

    rendered_prompt = (
        "You are a flood-insurance claims manager...\n\n"
        "### YOUR OPTIONS\n[N/A]\n\n"
        "<<<DECISION_START>>>\n{\"decision\": \"...\"}\n<<<DECISION_END>>>\n"
    )
    dynamic_skill_map = {"1": "approve_payout", "2": "deny_payout"}
    options_text = (
        "1. Pay the policyholder's flood claim in full from the shared catastrophe pool\n"
        "2. Deny the claim — pay nothing this period (preserves pool solvency)"
    )
    with pytest.raises(RuntimeError, match=r"Options-text parity violation \(POST-RENDER\)"):
        assert_rendered_prompt_shows_options(
            "insurer", rendered_prompt, dynamic_skill_map, options_text,
        )


def test_p4_2_post_render_check_passes_when_options_actually_rendered():
    """Companion: the SAME map and options_text, but the rendered prompt
    DOES carry the live numbered legend through (the fixed run_cat.py
    shape, via an explicit TieredContextBuilder) -- must not raise."""
    from broker.core._skill_filtering import assert_rendered_prompt_shows_options

    options_text = (
        "1. Pay the policyholder's flood claim in full from the shared catastrophe pool\n"
        "2. Deny the claim — pay nothing this period (preserves pool solvency)"
    )
    rendered_prompt = (
        "You are a flood-insurance claims manager...\n\n"
        f"### YOUR OPTIONS\n{options_text}\n\n"
        "<<<DECISION_START>>>\n{\"decision\": \"...\"}\n<<<DECISION_END>>>\n"
    )
    dynamic_skill_map = {"1": "approve_payout", "2": "deny_payout"}
    assert_rendered_prompt_shows_options(
        "insurer", rendered_prompt, dynamic_skill_map, options_text,
    )  # no raise


def test_p4_2_post_render_check_passes_for_name_based_rendering():
    """Companion: a name-based agent (MA flood's government/insurance
    shape) whose rendered prompt spells out every skill id by name, with
    NO numbered legend at all -- still safe, no raise."""
    from broker.core._skill_filtering import assert_rendered_prompt_shows_options

    rendered_prompt = (
        "### YOUR OPTIONS\n"
        "- large_increase_subsidy: expand\n"
        "- maintain_subsidy: hold\n"
        "- large_decrease_subsidy: shrink\n"
        '{"decision": "large_increase_subsidy | maintain_subsidy | large_decrease_subsidy"}'
    )
    dynamic_skill_map = {"1": "large_decrease_subsidy", "2": "large_increase_subsidy", "3": "maintain_subsidy"}
    options_text = "1. large_decrease_subsidy\n2. large_increase_subsidy\n3. maintain_subsidy"
    assert_rendered_prompt_shows_options(
        "government", rendered_prompt, dynamic_skill_map, options_text,
    )  # no raise


def test_p4_2_post_render_check_skipped_for_single_skill_map():
    """A single-skill (or empty) map has no ordering that could
    mis-decode -- the post-render check must not even look at the
    rendered prompt."""
    from broker.core._skill_filtering import assert_rendered_prompt_shows_options

    assert_rendered_prompt_shows_options(
        "individual", "anything at all, no options shown", {"1": "only_skill"}, "1. only_skill",
    )  # no raise
    assert_rendered_prompt_shows_options(
        "individual", "anything at all", None, None,
    )  # no raise


class _FakeSkillRegistryWithLabels:
    """Like _FakeSkillRegistry, but returns a DESCRIPTION LABEL that is
    NOT the skill id verbatim -- forces the post-render check's
    name-based path (word-boundary on the id) to fail, so passing here
    can only come from the exact-option-lines path (proving
    personal["options_text"] was actually written back by the tiered
    fallback builder, NEW-8's fix), not from the id happening to be
    spelled out."""

    _LABELS = {
        "buy_widget": "Purchase the widget at market price",
        "hold_widget": "Keep the widget, take no action this period",
        "sell_widget": "Liquidate the widget position",
    }

    def get(self, skill_id: str):
        return _FakeSkillDef2(skill_id, self._LABELS.get(skill_id, skill_id))


class _FakeSkillDef2:
    def __init__(self, skill_id: str, description: str):
        self.skill_id = skill_id
        self.description = description


def test_p4_2b_tiered_fallback_writes_back_options_text_and_does_not_raise(tmp_path: Path):
    """NEW-8 (hunter, round 5): TieredContextBuilder.format_prompt's OWN
    fallback dynamic_skill_map builder (the `if not options_text and
    agent:` branch) writes `personal["dynamic_skill_map"]` but used to
    never write `personal["options_text"]` back -- so a post-render check
    reading `personal["options_text"]` (the fast, exact-match path) saw
    nothing, even though the template correctly rendered the live
    numbered list built right here. A 3-skill menu with DESCRIPTION
    LABELS (not the bare ids) coming from this exact fallback path must
    not raise, and `context["personal"]["options_text"]` must be
    populated with the same numbered text that got rendered."""
    import textwrap
    from broker.components.context.tiered import TieredContextBuilder

    yaml_path = tmp_path / "agent_types.yaml"
    yaml_path.write_text(textwrap.dedent("""
        shared: {}
        individual:
          agent_type: individual
          actions:
            - id: buy_widget
              aliases: ["1"]
            - id: hold_widget
              aliases: ["2"]
            - id: sell_widget
              aliases: ["3"]
          parsing:
            default_skill: hold_widget
    """).strip(), encoding="utf-8")

    template = "{system_prompt}\nAvailable actions:\n{options_text}\n{response_format}"
    agent = _FakeAgentWithSkills(["buy_widget", "hold_widget", "sell_widget"])

    cb = TieredContextBuilder(
        agents={"A1": agent},
        skill_registry=_FakeSkillRegistryWithLabels(),
        prompt_templates={"individual": template},
        yaml_path=str(yaml_path),
    )
    context: Dict[str, Any] = {"agent_type": "individual", "personal": {"id": "A1"}}
    formatted = cb.format_prompt(context)  # no raise

    assert "1. Purchase the widget at market price" in formatted
    assert "2. Keep the widget, take no action this period" in formatted
    assert "3. Liquidate the widget position" in formatted

    # The actual NEW-8 assertion: the fallback path must write options_text
    # back into personal, not just dynamic_skill_map.
    written = context["personal"].get("options_text")
    assert written, "expected personal['options_text'] to be written back by the tiered fallback path"
    assert "1. Purchase the widget at market price" in written
    assert "3. Liquidate the widget position" in written


def test_p4_3_post_render_check_runs_inside_process_step():
    """Coverage gap (round 5, reviewer): every other test in this file
    calls `_inject_options_text`, `check_options_text_parity`, or
    `assert_rendered_prompt_shows_options` directly -- none of them prove
    the post-render check is actually WIRED IN to
    `SkillBrokerEngine.process_step`'s real call path. This one drives
    `process_step` itself, end to end, with a mock LLM, on a
    BaseAgentContextBuilder-shaped domain whose rendered prompt is a bare
    `[N/A]` (the cat_model / run_cat.py real-world shape) -- and asserts
    the RuntimeError surfaces from the actual production code path, not
    just from calling the guard function in isolation.

    Falsification for this specific test lives in the round-5 report
    (not re-executed here): swapping ONLY broker/core/skill_broker_engine.py
    to origin/main (pre-round-4, no call site for
    assert_rendered_prompt_shows_options at all) turns this test red --
    deleting the wiring, not just the guard function, is what this test
    is for.
    """
    from unittest.mock import MagicMock
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.components.governance.registry import SkillRegistry
    from broker.interfaces.skill_types import SkillDefinition

    registry = SkillRegistry()
    registry.register(SkillDefinition("buy_widget", "Purchase the widget", ["*"], [], {}, [], ""))
    registry.register(SkillDefinition("hold_widget", "Keep the widget", ["*"], [], {}, [], ""))

    cb = MagicMock()
    # No "available_skills" key -> should_rag is falsy -> RAG never
    # touches this pre-set personal.dynamic_skill_map/options_text, so
    # the scenario is fully controlled: a real, >1-entry map exists, but
    # the "rendered" prompt (below) never shows it -- the exact
    # BaseAgentContextBuilder + {options_text} gap run_cat.py had.
    cb.build.return_value = {
        "agent_type": "widget_trader",
        "personal": {
            "id": "a1",
            "dynamic_skill_map": {"1": "buy_widget", "2": "hold_widget"},
            "options_text": "1. Purchase the widget\n2. Keep the widget",
        },
    }
    cb.format_prompt.return_value = (
        "You are a widget trader.\n\nAvailable actions:\n[N/A]\n\n"
        '{"decision": "..."}'
    )

    engine = SkillBrokerEngine(
        skill_registry=registry,
        model_adapter=MagicMock(),
        validators=[],
        simulation_engine=MagicMock(),
        context_builder=cb,
        skill_retriever=None,
    )

    llm = MagicMock(return_value='<decision>{"decision": "buy_widget"}</decision>')

    with pytest.raises(RuntimeError, match=r"Options-text parity violation \(POST-RENDER\)"):
        engine.process_step("a1", 1, "r1", 42, llm, agent_type="widget_trader")


def test_p4_3_post_render_check_can_be_opted_out_via_render_check_false():
    """Companion: the SAME broken-rendering scenario, but with
    render_check=False (replay.py's documented opt-out) -- must NOT
    raise. Proves the opt-out actually short-circuits the check rather
    than merely being an unused parameter."""
    from unittest.mock import MagicMock
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.components.governance.registry import SkillRegistry
    from broker.interfaces.skill_types import SkillDefinition

    registry = SkillRegistry()
    registry.register(SkillDefinition("buy_widget", "Purchase the widget", ["*"], [], {}, [], ""))
    registry.register(SkillDefinition("hold_widget", "Keep the widget", ["*"], [], {}, [], ""))

    cb = MagicMock()
    cb.build.return_value = {
        "agent_type": "widget_trader",
        "personal": {
            "id": "a1",
            "dynamic_skill_map": {"1": "buy_widget", "2": "hold_widget"},
            "options_text": "1. Purchase the widget\n2. Keep the widget",
        },
    }
    cb.format_prompt.return_value = "Available actions:\n[N/A]\n" + '{"decision": "..."}'

    engine = SkillBrokerEngine(
        skill_registry=registry,
        model_adapter=MagicMock(),
        validators=[],
        simulation_engine=MagicMock(),
        context_builder=cb,
        skill_retriever=None,
    )
    llm = MagicMock(return_value='<decision>{"decision": "buy_widget"}</decision>')

    engine.process_step(
        "a1", 1, "r1", 42, llm, agent_type="widget_trader", render_check=False,
    )  # no raise


def test_p6_1_instruction_list_of_matching_length_does_not_mask_missing_menu():
    """Round 6 (silent-failure hunter NEW-9): the round-5 shape/arity path
    accepted ANY numbered list whose count matched
    len(dynamic_skill_map), regardless of what the list's lines actually
    said -- so an UNRELATED 3-item instruction block ("1. Review your
    situation / 2. Assess the threat / 3. Answer in JSON") could mask a
    genuinely missing [N/A] menu for a 3-skill map (or irrigation's 1-5
    rating-scale legend for its 5-skill menu). Removed in round 6:
    neither the exact option lines nor every skill name by word boundary
    is present here, so this must RAISE."""
    from broker.core._skill_filtering import assert_rendered_prompt_shows_options

    rendered_prompt = (
        "You are a widget trader.\n\n"
        "### YOUR OPTIONS\n[N/A]\n\n"
        "Consider your situation, then respond using this process:\n"
        "1. Review your situation\n"
        "2. Assess the threat\n"
        "3. Answer in JSON\n\n"
        '{"decision": "..."}'
    )
    dynamic_skill_map = {"1": "buy_widget", "2": "hold_widget", "3": "sell_widget"}
    options_text = (
        "1. Purchase the widget at market price\n"
        "2. Keep the widget, take no action this period\n"
        "3. Liquidate the widget position"
    )
    with pytest.raises(RuntimeError, match=r"Options-text parity violation \(POST-RENDER\)"):
        assert_rendered_prompt_shows_options(
            "widget_trader", rendered_prompt, dynamic_skill_map, options_text,
        )


def test_p6_2_render_check_skipped_is_countable_in_run_integrity():
    """Item 3 (round 6): a replayed decision (render_check=False) must be
    distinguishable by a FIELD, not only by the `replay_` run_id prefix
    convention. broker/core/run_integrity.get_render_check_skipped_count()
    increments once per process_step call made with render_check=False,
    and stays at 0 (the key is OMITTED from run_integrity.json, not
    written as 0 -- see record_run_integrity) for every ordinary call."""
    from unittest.mock import MagicMock
    from broker.core.run_integrity import get_render_check_skipped_count
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.components.governance.registry import SkillRegistry
    from broker.interfaces.skill_types import SkillDefinition

    registry = SkillRegistry()
    registry.register(SkillDefinition("buy_widget", "Purchase the widget", ["*"], [], {}, [], ""))
    registry.register(SkillDefinition("hold_widget", "Keep the widget", ["*"], [], {}, [], ""))

    def _make_engine():
        cb = MagicMock()
        cb.build.return_value = {
            "agent_type": "widget_trader",
            "personal": {
                "id": "a1",
                "dynamic_skill_map": {"1": "buy_widget", "2": "hold_widget"},
                "options_text": "1. Purchase the widget\n2. Keep the widget",
            },
        }
        cb.format_prompt.return_value = "Available actions:\n1. Purchase the widget\n2. Keep the widget\n"
        # Constructing a fresh engine resets the round-6 counter via
        # reset_decider_row_counts() in SkillBrokerEngine.__init__ --
        # isolates this test from any other test's engine construction.
        return SkillBrokerEngine(
            skill_registry=registry,
            model_adapter=MagicMock(),
            validators=[],
            simulation_engine=MagicMock(),
            context_builder=cb,
            skill_retriever=None,
        )

    llm = MagicMock(return_value='<decision>{"decision": "buy_widget"}</decision>')

    engine = _make_engine()
    assert get_render_check_skipped_count() == 0

    engine.process_step("a1", 1, "r1", 42, llm, agent_type="widget_trader")  # render_check=True default
    assert get_render_check_skipped_count() == 0, "an ordinary (non-replay) call must not tally as skipped"

    engine.process_step("a1", 2, "r1", 42, llm, agent_type="widget_trader", render_check=False)
    assert get_render_check_skipped_count() == 1, "a render_check=False call must tally exactly once"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "known gap: post-render name path does not check digit invitation; "
        "fix must compare against the rendered personal['options_text'] "
        "-- see CHANGELOG known issues"
    ),
)
def test_p7_1_name_path_rejects_digit_invitation_without_menu():
    """Round 7 (hunter P2 symmetry finding, fix REVERTED): assert_rendered_prompt_shows_options's
    name-based branch accepts "every skill id present by word boundary"
    unconditionally -- unlike _is_name_based_and_safe, which also
    requires `not _invites_digit(...)`. A rendered prompt that spells out
    every skill name in prose AND separately says "Numeric ID, choose
    ONE from: 1, 2, or 3" (the literal text ResponseFormatBuilder.build()
    renders for a numeric-choice field, with no visible number->name
    mapping) SHOULD raise -- the model may answer with a bare digit,
    which decodes POSITIONALLY against dynamic_skill_map, not by the name
    it saw in prose. A round-7 fix closing this gap (an added
    `_invites_digit` check on this branch) false-blocked the cat MA /
    reservoir domains and was reverted; this test is xfail(strict=True)
    to document the gap without blocking the suite. No shipped template
    exercises this shape today."""
    from broker.core._skill_filtering import assert_rendered_prompt_shows_options

    rendered_prompt = (
        "Options: buy_widget, hold_widget, sell_widget.\n"
        '{"decision": "<Numeric ID, choose ONE from: 1, 2, or 3>"}'
    )
    dynamic_skill_map = {"1": "sell_widget", "2": "buy_widget", "3": "hold_widget"}
    with pytest.raises(RuntimeError, match=r"Options-text parity violation \(POST-RENDER\)"):
        assert_rendered_prompt_shows_options(
            "widget_trader", rendered_prompt, dynamic_skill_map, None,
        )
