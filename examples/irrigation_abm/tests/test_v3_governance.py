"""Irrigation case study v3, Work Package 3: governance.

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md, section 3
(WP3, 3.1 to 3.9) and PI items 1, 2, 9, 10, 11, 15, 16, 19 and 22.

Two rule families, the same menu in every arm:
- feasibility: the supply rule (``supply_gap_block_increase``; blocks an
  increase when the expected delivery at the keep request, net of a declared
  junior-priority cut, is below ``FULL_SUPPLY_RATIO`` of it) and the two
  identity rules (water-right cap, minimum-use floor), which are menu
  filters in every profile, disabled included;
- thinking: TR1 (WSA H/VH blocks an increase) and TR3 (WSA VL/L blocks a
  decrease), strict only, read on the WSA as FIRST STATED in the decision
  (appraisal freeze).

Every test here fails on the pre-WP3 code (HEAD 5fe1ccf7): there the strict
profile carries R1/R2/R4, the disabled profile has no identity rules (its
menu offers an increase at the cap and renders the registry's fallback text
for a decrease at the floor), the supply rule blocks below 0.70 and skips
Tier 2+, curtailment_awareness_check is dispatched, retry messages carry a
"[Rule: <id>]" prefix, no appraisal freeze exists, no FULL_SUPPLY_RATIO,
no supply_rule_fields and none of the per-attempt or state audit columns.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import threading
import tokenize
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest
import yaml

import broker.utils.llm_utils as llm_utils
from broker.components.governance.registry import SkillRegistry
from broker.core._advise import build_intervention_reports, render_intervention_prompt
from broker.core._audit_helpers import _safe_rules_by_grounding
from broker.core._skill_filtering import SkillFilterMixin
from broker.interfaces.skill_types import SkillProposal
from broker.utils.agent_config import AgentTypeConfig, declared_governance_profiles
from broker.utils.llm_utils import LLMStats
from broker.utils.parsing.unified_adapter import UnifiedAdapter
from broker.validators import AgentValidator

from examples.irrigation_abm import irrigation_personas as personas
from examples.irrigation_abm import run_experiment
from examples.irrigation_abm.irrigation_env import (
    MIN_UTIL,
    UB_SUBBASINS,
    IrrigationEnvironment,
    WaterSystemConfig,
    _lb_junior_tier_fraction,
    _load_lb_priority_split_table,
)
from examples.irrigation_abm.irrigation_personas import (
    FULL_SUPPLY_RATIO,
    IrrigationAgentProfile,
    _RULE_LABELS,
    _precondition_violation_label,
    build_option_texts,
    build_water_situation_text,
)
from examples.irrigation_abm.validators import irrigation_validators as iv
from examples.irrigation_abm.validators.irrigation_validators import (
    ALL_IRRIGATION_CHECKS,
    IRRIGATION_BEHAVIORAL_CHECKS,
    IRRIGATION_PHYSICAL_CHECKS,
    IRRIGATION_SOCIAL_CHECKS,
    IRRIGATION_TEMPORAL_CHECKS,
    SUPPLY_RULE_FIELDS,
    irrigation_governance_validator,
    supply_gap_block_increase,
    supply_rule_fields,
)

REPO = Path(__file__).resolve().parents[3]
IRR = REPO / "examples" / "irrigation_abm"
CONFIG = IRR / "config" / "agent_types.yaml"
REGISTRY = IRR / "config" / "skill_registry.yaml"
TEMPLATE = IRR / "config" / "prompts" / "irrigation_farmer.txt"
AGENT_TYPE = "irrigation_farmer"
PROFILES = ("strict", "feasibility_only", "disabled")

CRSS_PARAMS_CSV = REPO / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
CRSS_DB_DIR = REPO / "ref" / "CRSS_DB" / "CRSS_DB"
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()

TR1 = "high_scarcity_no_increase"
TR3 = "low_scarcity_no_decrease"
SUPPLY = "supply_gap_block_increase"

TR1_MESSAGE = (
    "Demand increase blocked under the rule on increases under scarcity: at "
    "the start of this decision you judged water to be scarce this year, and "
    "a larger request when water is scarce draws more from a supply you share "
    "with other users."
)
TR1_SUGGESTION = "Under this rule an increase is not available in this decision."
TR3_MESSAGE = (
    "Demand decrease blocked under the rule on decreases without scarcity: at "
    "the start of this decision you judged that water is not scarce this year, "
    "and cutting your request when water is not scarce gives up water you could "
    "use for production."
)
TR3_SUGGESTION = "Under this rule a decrease is not available in this decision."
CAP_MESSAGE = "Increase not available: your request is already at your water right."
FLOOR_MESSAGE = (
    "Decrease not available: your request is already at the minimum-use floor "
    "(10% of your water right)."
)
SUPPLY_SUGGESTION = "The shortage-sharing rule blocks increases this year."

# Words no retry text may contain (spec 3.7, item 15; spec 4.2 test list).
_LABEL_CODE = re.compile(r"\b(VL|L|M|H|VH)\b")
_BANNED_IN_RETRY_TEXT = (
    "Very High", "Very Low", "water_scarcity_assessment",
    "adaptive_capacity_assessment", "WSA", "ACA", "_LABEL", "[Rule:",
    "may not increase requests", "Bureau of Reclamation",
)


@pytest.fixture(autouse=True)
def _restore_profile_env(monkeypatch):
    """Every test sets GOVERNANCE_PROFILE through monkeypatch, so a value a
    run writes into os.environ (ExperimentBuilder.build) is undone too."""
    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    yield


def _config(monkeypatch, profile: str) -> AgentTypeConfig:
    monkeypatch.setenv("GOVERNANCE_PROFILE", profile)
    return AgentTypeConfig.load(str(CONFIG))


# ===========================================================================
# 3.1 profiles and rule sets
# ===========================================================================

def test_profile_list():
    """strict, feasibility_only and disabled; placebo and silent are strict
    with --retry-feedback-mode; relaxed and grounded_v1 are gone."""
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert declared_governance_profiles(raw, AGENT_TYPE) == set(PROFILES)


def test_profile_rule_sets(monkeypatch):
    expected_identity = [
        ("water_right_cap", "at_allocation_cap", ["increase_demand"], "ERROR",
         "world", CAP_MESSAGE),
        ("beneficial_use_limit", "at_beneficial_use_limit", ["increase_demand"], "ERROR",
         "world", "Increase not available: your request is already at about the most water your fields can use."),
        ("minimum_utilisation_floor", "below_minimum_utilisation",
         ["decrease_demand"], "ERROR", "world", FLOOR_MESSAGE),
    ]
    for profile in PROFILES:
        cfg = _config(monkeypatch, profile)
        identity = cfg.get_identity_rules(AGENT_TYPE)
        assert [(r.id, r.metadata["precondition"], r.blocked_skills, r.level,
                 r.grounding, r.message) for r in identity] == expected_identity
        thinking = cfg.get_thinking_rules(AGENT_TYPE)
        if profile == "strict":
            assert [(r.id, r.conditions, r.blocked_skills, r.level, r.grounding,
                     r.message, r.metadata) for r in thinking] == [
                (TR1, [{"construct": "WSA_LABEL", "values": ["H", "VH"]}],
                 ["increase_demand"], "ERROR", "self_report", TR1_MESSAGE,
                 {"suggestion": TR1_SUGGESTION}),
                (TR3, [{"construct": "WSA_LABEL", "values": ["VL", "L"]}],
                 ["decrease_demand"], "ERROR", "self_report", TR3_MESSAGE,
                 {"suggestion": TR3_SUGGESTION}),
            ]
        else:
            assert thinking == []
        # the freeze and the prefix are global: on / off in every profile
        assert cfg.get_governance_appraisal_freeze() is True
        assert cfg.get_governance_rule_id_prefix() is False
    # No thinking rule reads ACA, none blocks keep, and none of the retired
    # rules (R1, R2, R4, the grounded rule) or profiles survives anywhere.
    text = CONFIG.read_text(encoding="utf-8")
    for retired in ("high_threat_no_maintain", "low_threat_no_increase",
                    "high_threat_high_cope_no_increase",
                    "observed_scarcity_low_wsa_increase", "relaxed:", "grounded_v1:"):
        assert retired not in text, retired
    raw = yaml.safe_load(text)
    for body in raw[AGENT_TYPE]["governance"].values():
        for rule in body["thinking_rules"]:
            assert "ACA_LABEL" not in json.dumps(rule)
            assert "maintain_demand" not in rule["blocked_skills"]


@pytest.mark.parametrize("wsa", ["VL", "L", "M", "H", "VH"])
@pytest.mark.parametrize("aca", ["VL", "M", "VH"])
@pytest.mark.parametrize("skill", ["increase_demand", "maintain_demand", "decrease_demand"])
def test_thinking_rules_truth_table(monkeypatch, wsa, aca, skill):
    """TR1: WSA H or VH blocks an increase. TR3: WSA VL or L blocks a
    decrease. ACA never matters, keep is never blocked, nothing is a
    warning; feasibility_only and disabled run neither rule."""
    expected = set()
    if skill == "increase_demand" and wsa in ("H", "VH"):
        expected.add(TR1)
    if skill == "decrease_demand" and wsa in ("VL", "L"):
        expected.add(TR3)
    for profile in PROFILES:
        _config(monkeypatch, profile)
        validator = AgentValidator(config_path=str(CONFIG))
        results = validator.validate_thinking(
            AGENT_TYPE, "A1", skill, {}, {"WSA_LABEL": wsa, "ACA_LABEL": aca})
        assert {r.metadata["rule_id"] for r in results if not r.valid} == (
            expected if profile == "strict" else set())
        assert not [r for r in results if r.valid and r.warnings]


def test_runner_refuses_retired_profiles(monkeypatch, tmp_path):
    for retired in ("relaxed", "grounded_v1"):
        monkeypatch.setattr(sys, "argv", [
            "run_experiment.py", "--model", "mock", "--years", "1", "--agents", "2",
            "--output", str(tmp_path / retired), "--governance-mode", retired])
        with pytest.raises(SystemExit):
            run_experiment.main()


@pytest.mark.parametrize("flag,value", [("--pilot-phase", "C"), ("--ablation-mode", "no_demand_ceiling")])
def test_runner_refuses_pilot_phase_and_ablation_mode(monkeypatch, tmp_path, flag, value):
    """Spec 3.2: both flags switched checks v3 no longer dispatches; they are
    refused before anything is written, never silently ignored."""
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "run_experiment.py", "--model", "mock", "--years", "1", "--agents", "2",
        "--output", str(out), flag, value])
    with pytest.raises(SystemExit, match="retired in the v3"):
        run_experiment.main()
    assert not out.exists()


@pytest.mark.parametrize("fraction", [0.0, 0.05, 0.2, 1.0])
def test_runner_refuses_non_default_min_utilisation_fraction(monkeypatch, tmp_path, fraction):
    """2026-10-06 Opus review P2-1: config/agent_types.yaml's
    minimum_utilisation_floor rule message hard-codes "10% of your water
    right" and is not templated, so this LLM-governed runner refuses any
    --min-utilisation-fraction other than the config default (0.10) --
    those sensitivities are FQL-only (run_fql_baseline.py) for now."""
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "run_experiment.py", "--model", "mock", "--years", "1", "--agents", "2",
        "--output", str(out), "--min-utilisation-fraction", str(fraction)])
    with pytest.raises(SystemExit, match="FQL-only"):
        run_experiment.main()
    assert not out.exists()


def test_runner_accepts_the_default_min_utilisation_fraction_explicitly(monkeypatch, tmp_path):
    """Passing the default value explicitly (0.10) is NOT refused -- only a
    value that actually differs from the config default is."""
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", [
        "run_experiment.py", "--model", "mock", "--years", "1", "--agents", "2",
        "--output", str(out), "--min-utilisation-fraction", "0.10"])
    try:
        run_experiment.main()
    except SystemExit as exc:
        assert "FQL-only" not in str(exc)


# ===========================================================================
# 3.2 dispatch and 3.6 labels
# ===========================================================================

def test_dispatch_list_exact():
    assert ALL_IRRIGATION_CHECKS == [supply_gap_block_increase]
    assert IRRIGATION_PHYSICAL_CHECKS == [supply_gap_block_increase]
    assert IRRIGATION_SOCIAL_CHECKS == []
    assert IRRIGATION_TEMPORAL_CHECKS == []
    assert IRRIGATION_BEHAVIORAL_CHECKS == []
    for retired in ("curtailment_awareness_check", "water_right_cap_check",
                    "minimum_utilisation_check", "non_negative_diversion_check",
                    "consecutive_increase_cap_check", "zero_escape_check"):
        assert "NOT DISPATCHED IN v3" in getattr(iv, retired).__doc__, retired
    # The bridge runs the supply rule only: an at-cap increase with a full
    # supply is left to the identity rule (menu filter), not blocked here.
    ctx = _supply_ctx(basin="upper_basin", physical=1.0)
    ctx["at_allocation_cap"] = True
    proposal = SkillProposal(skill_name="increase_demand", agent_id="A1",
                             agent_type=AGENT_TYPE, reasoning={})
    assert irrigation_governance_validator(proposal, ctx) == []


def test_rule_labels_six_entries():
    assert _RULE_LABELS == {
        SUPPLY: "the shortage-sharing rule",
        "water_right_cap": "the water-right cap",
        "beneficial_use_limit": "the beneficial-use limit",
        "minimum_utilisation_floor": "the minimum-use floor",
        TR1: "the rule on increases under scarcity",
        TR3: "the rule on decreases without scarcity",
    }
    assert _precondition_violation_label("precondition_violation", "increase_demand") == "the request-increase limit"
    assert _precondition_violation_label("precondition_violation", "decrease_demand") == "the minimum-use floor"
    assert _precondition_violation_label("curtailment_awareness", "increase_demand") == "a governance rule"


# ===========================================================================
# 3.1 menu parity (identity rules are menu filters in EVERY profile)
# ===========================================================================

class _TemplateBuilder:
    def __init__(self):
        self.prompt_templates = {AGENT_TYPE: TEMPLATE.read_text(encoding="utf-8")}


class _MenuHost(SkillFilterMixin):
    """The broker's real menu code (SkillFilterMixin) on the real config,
    registry and prompt template."""

    def __init__(self, config, registry):
        self.config = config
        self.skill_registry = registry
        self.context_builder = _TemplateBuilder()


def _menu(monkeypatch, profile: str, base: float, water_right: float = 100_000.0):
    """The options one agent with last year's receipt ``base`` is offered:
    the flags come from IrrigationEnvironment._reset_requests_to_base (the
    real rule), the texts from build_option_texts (the real overrides)."""
    config = _config(monkeypatch, profile)
    registry = SkillRegistry()
    registry.register_from_yaml(str(REGISTRY))
    env = IrrigationEnvironment(WaterSystemConfig(seed=1))
    env._agents["A1"] = {"basin": "lower_basin", "diversion": base, "request": base,
                         "water_right": water_right}
    env._reset_requests_to_base()
    agent = env._agents["A1"]
    profile_obj = IrrigationAgentProfile(agent_id="A1", basin="lower_basin",
                                         cluster="aggressive", water_right=water_right)
    overrides = build_option_texts(profile_obj, base=base, water_right=water_right,
                                   floor=water_right * MIN_UTIL)
    context = {"agent_id": "A1", "state": {
        "at_allocation_cap": agent["at_allocation_cap"],
        "below_minimum_utilisation": agent["below_minimum_utilisation"],
        "option_text_overrides": overrides,
    }}
    _MenuHost(config, registry)._inject_filtered_skills(context, AGENT_TYPE)
    personal = context["personal"]
    offered = [personal["dynamic_skill_map"][str(i + 1)]
               for i in range(len(personal["dynamic_skill_map"]))]
    registry_texts = [registry.get(s).description.strip() for s in
                      ("increase_demand", "maintain_demand", "decrease_demand")]
    return offered, personal["options_text"], overrides, registry_texts


def _assert_menu(monkeypatch, base, expected):
    menus = set()
    for profile in PROFILES:
        offered, options_text, overrides, registry_texts = _menu(monkeypatch, profile, base)
        assert offered == expected, (profile, offered)
        lines = options_text.split("\n")
        assert lines == [f"{i + 1}. {overrides[s]}" for i, s in enumerate(offered)], profile
        # WP2 review carry-over: the registry's fallback description never
        # renders for irrigation -- every offered option has its own text.
        for text in registry_texts:
            assert text not in options_text, (profile, text)
        menus.add(tuple(offered))
    assert len(menus) == 1  # the same menu in every arm


def test_menu_parity_at_cap(monkeypatch):
    """Base at the water right: keep and decrease only, in every profile
    (at HEAD the disabled profile offered an increase)."""
    _assert_menu(monkeypatch, 100_000.0, ["maintain_demand", "decrease_demand"])


def test_menu_parity_at_floor(monkeypatch):
    """Base at the minimum-use floor: increase and keep only, in every
    profile, and no registry fallback text (at HEAD the disabled profile
    offered a decrease rendered with "Reduce your diversion request.")."""
    _assert_menu(monkeypatch, 100_000.0 * MIN_UTIL, ["increase_demand", "maintain_demand"])


def test_menu_parity_between(monkeypatch):
    _assert_menu(monkeypatch, 50_000.0, ["increase_demand", "maintain_demand", "decrease_demand"])


# ===========================================================================
# 3.3 the supply rule
# ===========================================================================

def _supply_ctx(*, basin: str, keep: float = 100_000.0, expected: Optional[float] = None,
                physical: Optional[float] = None, gap_reason: Optional[str] = None,
                member_count: Optional[int] = 5, junior_fraction=None) -> Dict[str, Any]:
    """A validation context carrying the rule's inputs the way pre_year
    writes them (supply_rule_fields) plus the message fields."""
    if expected is None:
        expected = keep * (physical if physical is not None else 1.0)
    ratio = personas.supply_ratio(expected, keep)
    phys = ratio if physical is None else physical
    if gap_reason is None:
        gap_reason = "none" if phys >= 1.0 else (
            "lb_mead_availability" if basin == "lower_basin" else "ub_subbasin_supply")
    return {
        "basin": basin, "gap_reason": gap_reason,
        "ub_subbasin_member_count": member_count,
        "lb_junior_tier_cut_fraction": junior_fraction,
        "lb_junior_entitlement_af": 100_000.0 if junior_fraction is not None else None,
        "lb_junior_ceiling_af": 100_000.0 * (1-junior_fraction) if junior_fraction is not None else None,
        "lb_tier_ceiling_af": 100_000.0 * (1-junior_fraction) if junior_fraction is not None else None,
        "supply_keep_request_af": keep, "supply_expected_at_keep_af": expected,
        "supply_ratio": ratio, "supply_physical_ratio": phys,
        "full_supply_ratio": FULL_SUPPLY_RATIO,
    }


@pytest.mark.parametrize("basin", ["upper_basin", "lower_basin"])
@pytest.mark.parametrize("physical", [1.0, 0.999, 0.998999, 0.9, 0.5, 0.0])
@pytest.mark.parametrize("skill", ["increase_demand", "maintain_demand", "decrease_demand"])
def test_supply_rule_truth_table(basin, physical, skill):
    """Blocks exactly an increase with the physical share below
    FULL_SUPPLY_RATIO; nothing else, in either basin (at HEAD the edge was
    0.70, and a Lower Basin row in a declared Tier 2 or 3 was skipped)."""
    ctx = _supply_ctx(basin=basin, physical=physical)
    results = supply_gap_block_increase(skill, [], ctx)
    blocked = skill == "increase_demand" and physical < FULL_SUPPLY_RATIO
    assert bool(results) == blocked
    if blocked:
        (result,) = results
        assert not result.valid
        assert result.metadata["rule_id"] == SUPPLY
        assert result.metadata["grounding"] == "world"
        assert result.metadata["suggestion"] == SUPPLY_SUGGESTION


def test_supply_rule_tolerance():
    """r = 0.999 is full (not blocked; the situation text calls it full
    delivery and adds no shortage headline); r = 0.998999 is blocked and
    the text reads short -- one constant, one edge."""
    allowed = _supply_ctx(basin="lower_basin", physical=0.999)
    blocked = _supply_ctx(basin="lower_basin", physical=0.998999)
    assert supply_gap_block_increase("increase_demand", [], allowed) == []
    assert supply_gap_block_increase("increase_demand", [], blocked) != []

    def text(ratio):
        return build_water_situation_text({
            "year": 2030, "basin": "lower_basin", "drought_index": 0.05,
            "lake_mead_level": 1080.0, "shortage_tier": 0, "preceding_factor": 1,
            "current_request": 100_000.0, "current_diversion": 100_000.0 * ratio,
            "delivery_ratio": ratio, "water_right": 200_000.0,
            "gap_reason": "none" if ratio >= 1.0 else "lb_mead_availability",
        })
    full, short = text(0.999), text(0.998999)
    assert "you can expect full delivery this year" in full
    assert "Water supply is sufficient for your full request this year." in full
    # Item 36a (2026-10-05 design-basis audit + fix proposals): just below
    # FULL_SUPPLY_RATIO the headline is the one surviving "short" state
    # (the pre-2026-10-05 five-band text, "slightly short", is retired
    # from the prompt); the share still prints with one decimal, never
    # as 100%.
    assert "Water supply is short of your request this year." in short
    assert "(99.9%) this year" in short
    assert "you can expect full delivery" not in short


def test_supply_rule_keep_request_zero_is_never_short():
    """r = 1 when the keep request is 0 (spec conventions), in both basins,
    even under a physical Lower Basin shortage."""
    ub = supply_rule_fields({"basin": "upper_basin", "current_request": 0.0,
                             "current_diversion": 0.0}, {"lb_phys_ratio": None})
    lb = supply_rule_fields({"basin": "lower_basin", "current_request": 0.0,
                             "current_diversion": 0.0}, {"lb_phys_ratio": 0.6})
    assert ub["supply_ratio"] == ub["supply_physical_ratio"] == 1.0
    assert lb["supply_ratio"] == lb["supply_physical_ratio"] == 1.0
    ctx = {**lb, "basin": "lower_basin", "gap_reason": "lb_mead_availability"}
    assert supply_gap_block_increase("increase_demand", [], ctx) == []


def test_supply_rule_fields_single_source_and_refusals():
    fields = supply_rule_fields(
        {"basin": "lower_basin", "current_request": 100_000.0, "current_diversion": 80_000.0},
        {"lb_phys_ratio": 1.0})
    assert tuple(fields) == SUPPLY_RULE_FIELDS
    assert fields["supply_ratio"] == 0.8 and fields["supply_physical_ratio"] == 1.0
    assert fields["full_supply_ratio"] is FULL_SUPPLY_RATIO
    with pytest.raises(ValueError, match="lb_phys_ratio"):
        supply_rule_fields({"basin": "lower_basin", "current_request": 1.0,
                            "current_diversion": 1.0}, {"lb_phys_ratio": None})
    with pytest.raises(KeyError):
        supply_rule_fields({"basin": "lower_basin", "current_request": 1.0,
                            "current_diversion": 1.0}, {})
    with pytest.raises(ValueError, match="basin"):
        supply_rule_fields({"basin": "mars", "current_request": 1.0,
                            "current_diversion": 1.0}, {"lb_phys_ratio": None})
    # the YAML's state_columns are exactly these fields, in this order
    raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert tuple(raw["global_config"]["audit"]["state_columns"]) == SUPPLY_RULE_FIELDS + (
        "beneficial_use_limit_af", "at_beneficial_use_limit")


def test_full_supply_ratio_single_source():
    """The validator, the prompt builder and the rule inputs share one
    object; no other numeric 0.999 exists in irrigation code (comments and
    strings do not count). The WP6 metrics module imports it too when it
    lands."""
    assert iv.FULL_SUPPLY_RATIO is personas.FULL_SUPPLY_RATIO
    assert FULL_SUPPLY_RATIO == 0.999
    hits = []
    for path in sorted(IRR.rglob("*.py")):
        if "tests" in path.parts:
            continue
        with open(path, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.NUMBER and tok.string in ("0.999", ".999"):
                    hits.append((path.name, tok.line.strip()))
    assert hits == [("irrigation_personas.py", "FULL_SUPPLY_RATIO = 0.999")]


# ---------------------------------------------------------------------------
# the supply rule on the real water system: phi, the declared tier, the
# junior-priority exemption (item 22)
# ---------------------------------------------------------------------------

_UB_PLACEHOLDER_MAF = {s: 5.0 for s in UB_SUBBASINS}
_HOPI = "HopiTribe"          # 100 percent junior-priority
_CRIR = "CRIR AZ"            # senior only


def _lb_env(requests: Dict[str, float]) -> IrrigationEnvironment:
    env = IrrigationEnvironment(WaterSystemConfig(seed=1, lb_priority_mode="split"))
    table = _load_lb_priority_split_table()
    for aid, request in requests.items():
        env._agents[aid] = {
            "basin": "lower_basin", "diversion": request, "request": request,
            "water_right": table[aid]["water_right_af"], "curtailment_ratio": 0.0,
            "delivery_ratio": 1.0, "gap_reason": "none", "at_allocation_cap": False,
            "has_efficient_system": False, "below_minimum_utilisation": False,
            "cluster": "aggressive",
        }
    return env


def _settle(env: IrrigationEnvironment, *, tier: int, short: bool) -> Dict[str, Any]:
    """Settle one year with a declared ``tier`` and either ample storage
    (phi = 1) or the low-storage state of test_v3_lb_priority (phi < 1),
    then write the deliveries onto the agents as advance_year does."""
    cfg = env.config
    lb_req = sum(a["request"] for a in env._agents.values()) / 1e6
    if short:
        snap = {"powell_storage": 3.75, "mead_storage": 6.0, "natural_flow": 0.3,
                "mexico": 0.1, "lb_tributary": 0.05}
    else:
        snap = {"powell_storage": 20.0, "mead_storage": 25.0, "natural_flow": 15.0,
                "mexico": 1.5, "lb_tributary": 0.8}
    snap.update({"lb_shortage_volume_maf": env._tier_shortage_volume_maf(tier),
                 "lb_shortage_tier": tier, "lb_request_projected_maf": lb_req,
                 "ub_subbasin_available_af": {s: v * 1e6 for s, v in _UB_PLACEHOLDER_MAF.items()}})
    snap["powell_release_planned_maf"] = env._plan_powell_release(
        nf=snap["natural_flow"], s_p=snap["powell_storage"], s_m=snap["mead_storage"],
        trib=snap["lb_tributary"], shortage_volume=snap["lb_shortage_volume_maf"],
        mexico=snap["mexico"], ub_requested_maf=env._basin_request_projected_maf(is_upper_basin=True),
        lb_requested_maf=lb_req, year=env._current_year,
        ub_requested_by_subbasin_maf=env._ub_request_projected_by_subbasin_maf(),
        ub_available_by_subbasin_maf=_UB_PLACEHOLDER_MAF,
    )
    settlement = env._settle(snap)
    env._write_agent_deliveries(settlement)
    return settlement


def _rule_context(env: IrrigationEnvironment, aid: str) -> Dict[str, Any]:
    """What pre_year puts in the validation context for this agent."""
    state = env.get_agent_state(aid)
    agent_context = {"agent_id": aid, "basin": "lower_basin",
                     "current_request": state["request"], "current_diversion": state["diversion"]}
    return {"basin": "lower_basin", "gap_reason": state["gap_reason"],
            "lb_junior_tier_cut_fraction": state["lb_junior_tier_cut_fraction"],
            **{key: state[key] for key in ("lb_junior_ceiling_af", "lb_tier_ceiling_af", "lb_junior_entitlement_af")},
            **supply_rule_fields(agent_context, state)}


def test_supply_rule_ignores_declared_tier_and_junior_cut():
    """Tier 2 declared, Lake Mead physically full (phi = 1): the senior
    agent is untouched and the junior agent binds its entitlement ceiling.
    Neither is blocked by this physical-supply rule: phi remains one.
    Plain TR1 separately blocks high-scarcity increases (item 46)."""
    env = _lb_env({_HOPI: 5_900.0, _CRIR: 880_000.0})
    settlement = _settle(env, tier=2, short=False)
    assert settlement["lb_phys_ratio"] == 1.0
    hopi, crir = _rule_context(env, _HOPI), _rule_context(env, _CRIR)
    assert hopi["gap_reason"] == "lb_junior_tier_cut"
    assert hopi["supply_ratio"] == pytest.approx(0.541479, abs=1e-6)  # 3,194.723 AF ceiling / 5,900 AF request
    assert hopi["supply_ratio"] < FULL_SUPPLY_RATIO <= hopi["supply_physical_ratio"] == 1.0
    assert crir["supply_ratio"] == crir["supply_physical_ratio"] == 1.0
    assert supply_gap_block_increase("increase_demand", [], hopi) == []
    assert supply_gap_block_increase("increase_demand", [], crir) == []


def test_supply_rule_blocks_on_phi_with_the_true_message():
    """Tier 1 declared and Lake Mead physically short (phi < 1): both the
    senior and the junior agent are blocked, each with a true message --
    the junior one names its junior-priority cut as well."""
    env = _lb_env({_HOPI: 5_900.0, _CRIR: 880_000.0})
    settlement = _settle(env, tier=1, short=True)
    phi = settlement["lb_phys_ratio"]
    assert phi < FULL_SUPPLY_RATIO
    hopi, crir = _rule_context(env, _HOPI), _rule_context(env, _CRIR)
    assert hopi["supply_physical_ratio"] == crir["supply_physical_ratio"] == round(phi, 6)
    crir_msg = supply_gap_block_increase("increase_demand", [], crir)[0].errors[0]
    hopi_msg = supply_gap_block_increase("increase_demand", [], hopi)[0].errors[0]
    assert crir_msg == (
        "Demand increase blocked under the shortage-sharing rule: if you request "
        f"the 880,000 acre-ft you received last year, you can expect "
        f"{880_000.0 * crir['supply_ratio']:,.0f} acre-ft this year "
        f"({crir['supply_ratio']:.1%}), because Lake Mead cannot meet all Lower "
        "Basin withdrawals without falling below its minimum pool, so all Lower "
        "Basin deliveries are reduced in proportion to requests after any tier ceiling is applied. When water is short it "
        "is shared in proportion to requests, so a larger request would raise your "
        "share only by lowering the deliveries of other users in the Lower Basin; it "
        "would not add water to the Lower Basin."
    )
    ceiling = hopi["lb_junior_ceiling_af"]
    entitlement = hopi["lb_junior_entitlement_af"]
    assert hopi_msg == (
        "Demand increase blocked under the shortage-sharing rule: if you request "
        f"the 5,900 acre-ft you received last year, you can expect "
        f"{hopi['supply_expected_at_keep_af']:,.0f} acre-ft this year "
        f"({hopi['supply_ratio']:.1%}), because the declared Lower Basin shortage "
        f"tier limits your junior-priority water this year to about {ceiling:,.0f} acre-ft "
        f"({ceiling/entitlement:.0%} of your junior-priority entitlement) and Lake Mead "
        "cannot meet all Lower Basin withdrawals without falling below "
        "its minimum pool, so all Lower Basin deliveries are reduced in proportion to requests after any tier ceiling is applied. "
        "Lake Mead's physical shortage applies after the tier ceiling and is "
        "shared in proportion to requests capped by that ceiling: any increase "
        f"above your {hopi['lb_tier_ceiling_af']:,.0f} acre-ft tier ceiling would add no "
        "deliverable water; within the ceiling, a larger request would raise "
        "your share only by lowering the deliveries of other users in the Lower "
        "Basin; it would not add water "
        "to the Lower Basin."
    )


# ===========================================================================
# 3.7 retry texts
# ===========================================================================

def test_sharing_sentence_golden_junior_priority():
    """Item 46: an increase above the tier ceiling adds no water.
    Refuse a junior-cut code without the ceiling that the warning names."""
    ctx = {"basin": "lower_basin", "gap_reason": "lb_junior_tier_cut+lb_mead_availability",
           "lb_tier_ceiling_af": 3_194.723430}
    assert iv._sharing_sentence(ctx) == (
        "Lake Mead's physical shortage applies after the tier ceiling and is "
        "shared in proportion to requests capped by that ceiling: any increase "
        "above your 3,195 acre-ft tier ceiling would add no deliverable water; "
        "within the ceiling, a larger request would raise your share only by "
        "lowering the deliveries of other users in the Lower Basin; it would not add water to "
        "the Lower Basin."
    )
    for bad in ({**ctx, "lb_tier_ceiling_af": None}, {"basin": "lower_basin", "gap_reason": ctx["gap_reason"]}):
        with pytest.raises(ValueError, match="lb_tier_ceiling_af"):
            iv._sharing_sentence(bad)

def test_retry_texts_golden_upper_basin_variants():
    base = dict(basin="upper_basin", keep=20_000.0, physical=0.674)
    sub = supply_gap_block_increase("increase_demand", [], _supply_ctx(**base))[0]
    assert sub.errors[0] == (
        "Demand increase blocked under the shortage-sharing rule: if you request "
        "the 20,000 acre-ft you received last year, you can expect 13,480 acre-ft "
        "this year (67.4%), because the water your sub-basin can draw this year, a "
        "fixed share of the natural flow of its rivers, is below the combined "
        "requests of its users, and the shortfall is shared in proportion to "
        "requests. When water is short it is shared in proportion to requests, so a "
        "larger request would raise your share only by lowering the deliveries of "
        "other users in your sub-basin; it would not add water to your sub-basin."
    )
    solo = supply_gap_block_increase(
        "increase_demand", [], _supply_ctx(**base, member_count=1))[0]
    assert solo.errors[0].endswith(
        "because the water your sub-basin can draw this year, a fixed share of the "
        "natural flow of its rivers, is below your own request. When water is short, "
        "a larger request would not add water.")
    backstop = supply_gap_block_increase(
        "increase_demand", [], _supply_ctx(**base, gap_reason="ub_natural_flow"))[0]
    assert backstop.errors[0].endswith(
        "so a larger request would raise your share only by lowering the "
        "deliveries of other users in the Upper Basin; it would not add water to "
        "the Upper Basin.")


def test_retry_text_golden_zero_delivery():
    """Nothing expected for anyone in the pool (every share in a pool is the
    same): the message states that a larger request would not add water,
    never that it would lower other users' deliveries (all zero). The
    trigger itself has no separate zero-delivery branch."""
    msg = supply_gap_block_increase(
        "increase_demand", [], _supply_ctx(basin="lower_basin", physical=0.0))[0].errors[0]
    assert msg == (
        "Demand increase blocked under the shortage-sharing rule: if you request "
        "the 100,000 acre-ft you received last year, you can expect 0 acre-ft this "
        "year (0.0%), because Lake Mead cannot meet all Lower Basin withdrawals "
        "without falling below its minimum pool, so all Lower Basin deliveries "
        "are reduced in proportion to requests after any tier ceiling is applied. When water is short, a larger request would not add water."
    )


def test_supply_rule_refuses_a_block_without_a_reason():
    with pytest.raises(ValueError, match="gap_reason"):
        supply_gap_block_increase("increase_demand", [], _supply_ctx(
            basin="lower_basin", physical=0.5, gap_reason="none"))


def test_retry_texts_golden_thinking_and_identity(monkeypatch):
    _config(monkeypatch, "strict")
    validator = AgentValidator(config_path=str(CONFIG))
    tr1 = validator.validate_thinking(AGENT_TYPE, "A1", "increase_demand", {},
                                      {"WSA_LABEL": "H", "ACA_LABEL": "M"})
    tr3 = validator.validate_thinking(AGENT_TYPE, "A1", "decrease_demand", {},
                                      {"WSA_LABEL": "L", "ACA_LABEL": "M"})
    cap = validator.validate_identity(AGENT_TYPE, "A1", "increase_demand",
                                      {"at_allocation_cap": True})
    floor = validator.validate_identity(AGENT_TYPE, "A1", "decrease_demand",
                                        {"below_minimum_utilisation": True})
    assert [r.errors for r in tr1] == [[TR1_MESSAGE]]
    assert [r.metadata["suggestion"] for r in tr1] == [TR1_SUGGESTION]
    assert [r.errors for r in tr3] == [[TR3_MESSAGE]]
    assert [r.metadata["suggestion"] for r in tr3] == [TR3_SUGGESTION]
    assert [r.errors for r in cap] == [[CAP_MESSAGE]]
    assert [r.errors for r in floor] == [[FLOOR_MESSAGE]]


def _retry_block(results, skill) -> str:
    """The rule part of a full-mode retry prompt (everything before the
    original prompt, which carries the rating scale and field names)."""
    proposal = SkillProposal(skill_name=skill, agent_id="A1", agent_type=AGENT_TYPE, reasoning={})
    reports = build_intervention_reports(results, proposal, source="errors")
    text, _ = render_intervention_prompt(
        UnifiedAdapter.__new__(UnifiedAdapter), "<<ORIGINAL>>", reports, max_reports=3,
        feasible_line="Actions that pass every rule this step: 1 (maintain demand).")
    return text[:text.index("<<ORIGINAL>>")]


def _assert_plain(text: str):
    assert not _LABEL_CODE.search(text), _LABEL_CODE.search(text)
    for banned in _BANNED_IN_RETRY_TEXT:
        assert banned not in text, banned


def test_retry_texts_no_label_codes(monkeypatch):
    """No retry text names a label code as a word, "Very High"/"Very Low",
    an appraisal field, a rule id, a law or agency."""
    _config(monkeypatch, "strict")
    validator = AgentValidator(config_path=str(CONFIG))
    blocks = [
        _retry_block(validator.validate_thinking(
            AGENT_TYPE, "A1", "increase_demand", {}, {"WSA_LABEL": "VH", "ACA_LABEL": "VH"}),
            "increase_demand"),
        _retry_block(validator.validate_thinking(
            AGENT_TYPE, "A1", "decrease_demand", {}, {"WSA_LABEL": "VL", "ACA_LABEL": "VL"}),
            "decrease_demand"),
        _retry_block(validator.validate_identity(
            AGENT_TYPE, "A1", "increase_demand", {"at_allocation_cap": True}), "increase_demand"),
        _retry_block(validator.validate_identity(
            AGENT_TYPE, "A1", "decrease_demand", {"below_minimum_utilisation": True}),
            "decrease_demand"),
    ]
    for ctx in (_supply_ctx(basin="upper_basin", physical=0.5),
                _supply_ctx(basin="upper_basin", physical=0.5, member_count=1),
                _supply_ctx(basin="upper_basin", physical=0.5, gap_reason="ub_capacity"),
                _supply_ctx(basin="lower_basin", physical=0.5),
                _supply_ctx(basin="lower_basin", physical=0.5,
                            gap_reason="lb_junior_tier_cut+lb_mead_availability",
                            junior_fraction=0.203)):
        blocks.append(_retry_block(supply_gap_block_increase("increase_demand", [], ctx),
                                   "increase_demand"))
    for block in blocks:
        assert "Reason:" in block
        _assert_plain(block)


# ===========================================================================
# 3.9 grounding
# ===========================================================================

def test_grounding_stamps(monkeypatch):
    """Feasibility blocks are filed as world-grounded, TR1/TR3 as
    self-report; every profile writes the grounding columns."""
    _config(monkeypatch, "strict")
    validator = AgentValidator(config_path=str(CONFIG))
    supply = supply_gap_block_increase(
        "increase_demand", [], _supply_ctx(basin="lower_basin", physical=0.5))
    cap = validator.validate_identity(AGENT_TYPE, "A1", "increase_demand",
                                      {"at_allocation_cap": True})
    floor = validator.validate_identity(AGENT_TYPE, "A1", "decrease_demand",
                                        {"below_minimum_utilisation": True})
    tr1 = validator.validate_thinking(AGENT_TYPE, "A1", "increase_demand", {},
                                      {"WSA_LABEL": "H"})
    tr3 = validator.validate_thinking(AGENT_TYPE, "A1", "decrease_demand", {},
                                      {"WSA_LABEL": "VL"})
    assert [r.metadata["grounding"] for r in supply + cap + floor] == ["world"] * 3
    assert [r.metadata["grounding"] for r in tr1 + tr3] == ["self_report"] * 2
    world, self_report = _safe_rules_by_grounding([supply, cap, floor, tr1, tr3])
    assert world == sorted([SUPPLY, "water_right_cap", "minimum_utilisation_floor"])
    assert self_report == sorted([TR1, TR3])
    for profile in PROFILES:
        assert _config(monkeypatch, profile).get_audit_grounding_columns() is True


# ===========================================================================
# end to end: the runner, a scripted mock LLM, the audit trail
# ===========================================================================

Script = Callable[[str, int, int, Dict[str, int]], Tuple[str, str, Any]]


class ScriptedIrrigationLLM:
    """A deterministic stand-in for the model (no Ollama). ``script(agent,
    year, attempt, menu)`` returns ``(wsa, aca, choice)``: ``choice`` is
    "Increase" / "Keep" / "Decrease" (mapped through the menu the prompt
    actually shows; "Keep" if absent) or an explicit option number. The
    attempt index counts every decision call of one agent-year, so it also
    works under ``retry_feedback_mode: silent``, whose retry prompt is the
    original prompt. Batch reflection calls get a one-line lesson."""

    def __init__(self, script: Script):
        self.script = script
        self.calls: Counter = Counter()
        self.prompts: List[Tuple[str, int, int, str]] = []
        self._lock = threading.Lock()

    def __call__(self, prompt: str):
        stats = LLMStats(retries=0, success=True)
        if "You are a Reflection Assistant" in prompt:
            ids = re.findall(r"^(.+?) Memories:", prompt, flags=re.M)
            return json.dumps({aid: "I learned to watch my supply before changing my request."
                               for aid in ids}), stats
        agent = re.search(r"You are (.+?), an agricultur", prompt).group(1)
        year = int(re.search(r"It is now the year (\d{4})", prompt).group(1))
        with self._lock:
            attempt = self.calls[(agent, year)]
            self.calls[(agent, year)] += 1
            self.prompts.append((agent, year, attempt, prompt))
        menu = {m.group(2): int(m.group(1)) for m in re.finditer(
            r"^(\d+)\. (Increase|Keep|Decrease) your request", prompt, flags=re.M)}
        wsa, aca, choice = self.script(agent, year, attempt, menu)
        decision = choice if isinstance(choice, int) else menu.get(choice, menu["Keep"])
        payload = {"reasoning": "Scripted answer."}
        if wsa is not None:  # None: the answer omits the WSA field entirely
            payload["water_scarcity_assessment"] = {"label": wsa, "reason": "Scripted."}
        payload["adaptive_capacity_assessment"] = {"label": aca, "reason": "Scripted."}
        payload["decision"] = decision
        return "<<<DECISION_START>>>\n" + json.dumps(payload) + "\n<<<DECISION_END>>>", stats


def relabel_script(agent, year, attempt, menu):
    """First attempt: scarce (H) and increase -- TR1 blocks. Retry: relabel
    to M and increase again -- still blocked under the freeze. Then keep."""
    if attempt == 0:
        return "H", "M", "Increase"
    if attempt == 1:
        return "M", "M", "Increase"
    return "M", "M", "Keep"


def _run_main(monkeypatch, out: Path, llm: ScriptedIrrigationLLM, *args: str) -> Path:
    monkeypatch.setattr(run_experiment, "create_llm_invoke", lambda model, verbose=False: llm)
    monkeypatch.setattr(llm_utils, "create_llm_invoke",
                        lambda model, verbose=False, overrides=None: llm)
    monkeypatch.setattr(sys, "argv", ["run_experiment.py", "--model", "mock",
                                      "--output", str(out), "--workers", "1", *args])
    run_experiment.main()
    AgentTypeConfig.clear_cache()
    return out


def _audit_rows(out: Path) -> List[Dict[str, str]]:
    with open(out / "irrigation_farmer_governance_audit.csv", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def test_e2e_freeze_relabel_cannot_pass_and_columns_filled(monkeypatch, tmp_path):
    llm = ScriptedIrrigationLLM(relabel_script)
    out = _run_main(monkeypatch, tmp_path / "strict", llm,
                    "--years", "1", "--agents", "3", "--seed", "7")
    rows = _audit_rows(out)
    assert len(rows) == 3
    for row in rows:
        assert row["initial_skill"] == "increase_demand"
        assert row["initial_labels"] == "WSA_LABEL=H|ACA_LABEL=M"
        assert row["final_labels"] == "WSA_LABEL=M|ACA_LABEL=M"
        assert row["appraisal_drift"] == "WSA_LABEL:H>M"
        assert row["attempt_skills"] == "increase_demand|increase_demand|maintain_demand"
        assert row["attempt_labels"] == (
            "WSA_LABEL=H,ACA_LABEL=M|WSA_LABEL=M,ACA_LABEL=M|WSA_LABEL=M,ACA_LABEL=M")
        assert row["attempt_failed_rules"] == f"{TR1}|{TR1}|"
        assert row["appraisal_relabeled"] == "True"
        assert row["proposed_skill"] == row["executed_skill"] == "maintain_demand"
        assert row["execution_path"] == "approved"
        assert row["rules_self_report"] == TR1 and row["rules_world_grounded"] == ""
        for key in SUPPLY_RULE_FIELDS:
            assert row[f"state_{key}"] not in ("", "unobserved"), key
        assert float(row["state_full_supply_ratio"]) == FULL_SUPPLY_RATIO
    # The retry prompts: plain words, no rule id or label code, and the
    # feasible line computed on the frozen H (increase not listed even after
    # the relabel to M).
    retries = [p for (_, _, attempt, p) in llm.prompts if attempt > 0]
    originals = {(a, y): p for (a, y, attempt, p) in llm.prompts if attempt == 0}
    assert len(retries) == 6
    for agent, year, attempt, prompt in llm.prompts:
        if attempt == 0:
            continue
        block = prompt[:prompt.index(originals[(agent, year)])]
        assert TR1_MESSAGE in block and TR1_SUGGESTION in block
        assert "Actions that pass every rule this step: 2 (maintain demand), 3 (decrease demand)." in block
        _assert_plain(block)
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["appraisal_freeze_resolved"] is True
    assert manifest["rule_id_prefix_resolved"] is False


# ---------------------------------------------------------------------------
# WP3 review round 1, HIGH 1: a label the first parsed attempt omitted is
# frozen the first time the agent states it (the reviewer's scenario: the
# format loop accepts its third answer without a WSA). Pre-fix, the freeze
# held only {ACA} and stripped every later WSA, so the required-field check
# failed on every retry with a false "missing required fields" message.
# ---------------------------------------------------------------------------

def _omit_wsa_first(then):
    """Calls 0-2 omit WSA (two format retries, the third answer is accepted
    as the first parsed attempt); call 3 on follows ``then``."""
    def script(agent, year, attempt, menu):
        if attempt < 3:
            return None, "M", "Keep"
        return then[min(attempt - 3, len(then) - 1)]
    return script


def test_e2e_freeze_recovers_a_label_the_first_attempt_omitted(monkeypatch, tmp_path):
    """The first parsed attempt lacks WSA (a true format failure); the first
    retry states it, and the decision is approved at that retry -- exactly
    as with the freeze off. Stating the WSA for the first time is not a
    relabel. Pre-fix: REJECTED after 3 retries."""
    llm = ScriptedIrrigationLLM(_omit_wsa_first([("M", "M", "Keep")]))
    out = _run_main(monkeypatch, tmp_path / "recover", llm,
                    "--years", "1", "--agents", "2", "--seed", "7")
    for row in _audit_rows(out):
        assert row["status"] == "APPROVED" and row["execution_path"] == "approved"
        assert row["retry_count"] == "1" and row["format_retries"] == "2"
        assert row["initial_labels"] == "ACA_LABEL=M"
        assert row["attempt_labels"] == "ACA_LABEL=M|WSA_LABEL=M,ACA_LABEL=M"
        assert row["attempt_failed_rules"] == "Unknown|"
        assert row["appraisal_relabeled"] == "False"


def test_e2e_first_stated_wsa_is_frozen_after_an_omission(monkeypatch, tmp_path):
    """The WSA first stated on the first retry (H, with an increase) is the
    one TR1 reads from then on: relabelling it to M still cannot pass, and
    only a keep is approved. Pre-fix: the stated WSA was stripped, so TR1
    never fired and every attempt failed the required-field check."""
    llm = ScriptedIrrigationLLM(_omit_wsa_first(
        [("H", "M", "Increase"), ("M", "M", "Increase"), ("M", "M", "Keep")]))
    out = _run_main(monkeypatch, tmp_path / "first_stated", llm,
                    "--years", "1", "--agents", "2", "--seed", "7")
    for row in _audit_rows(out):
        assert row["status"] == "APPROVED" and row["retry_count"] == "3"
        assert row["attempt_skills"] == (
            "maintain_demand|increase_demand|increase_demand|maintain_demand")
        assert row["attempt_failed_rules"] == f"Unknown|{TR1}|{TR1}|"
        assert row["executed_skill"] == "maintain_demand"
        assert row["appraisal_relabeled"] == "True"


# ---------------------------------------------------------------------------
# WP3 review round 1, MEDIUM 2: an off-menu answer blocked by an identity
# rule gets a retry text with the identity rule's message only; the
# registry backstop stays in the audit.
# ---------------------------------------------------------------------------

class _AtCapContext:
    """A context builder for one Lower Basin agent whose base is at its water
    right: the real menu filter, the real option texts, a full supply."""

    def __init__(self, water_right: float = 100_000.0):
        profile = IrrigationAgentProfile(agent_id="A1", basin="lower_basin",
                                         cluster="aggressive", water_right=water_right)
        self.state = {
            "at_allocation_cap": True, "below_minimum_utilisation": False,
            "option_text_overrides": build_option_texts(
                profile, base=water_right, water_right=water_right,
                floor=water_right * MIN_UTIL),
            "basin": "lower_basin", "gap_reason": "none",
            "lb_junior_tier_cut_fraction": 0.0,
            "supply_keep_request_af": water_right,
            "supply_expected_at_keep_af": water_right,
            "supply_ratio": 1.0, "supply_physical_ratio": 1.0,
            "full_supply_ratio": FULL_SUPPLY_RATIO,
        }
        self.prompt_templates = {AGENT_TYPE: TEMPLATE.read_text(encoding="utf-8")}

    def build(self, agent_id, env_context=None, **kwargs):
        return {"agent_id": agent_id, "state": dict(self.state)}

    def format_prompt(self, context):
        return "PROMPT\n" + context["personal"]["options_text"]


def test_retry_text_hides_registry_backstop_after_identity_block(monkeypatch, tmp_path):
    """At the cap the menu offers keep and decrease; the model answers
    "increase" anyway. A FULL _run_validators pass (the real irrigation
    config, registry, AgentValidator and supply rule) blocks it three ways:
    the water-right cap identity rule, the registry precondition and the
    registry output schema. The retry prompt states the cap message only --
    no internal field name, rule id or label code -- while the audit keeps
    all three blocks. With the flag off the backstop text leaks (why the
    option exists)."""
    from broker.components.analytics.audit import AuditConfig, GenericAuditWriter, trace_to_csv_row
    from broker.core.skill_broker_engine import SkillBrokerEngine

    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    AgentTypeConfig.clear_cache()
    config = AgentTypeConfig.load(str(CONFIG))
    registry = SkillRegistry()
    registry.register_from_yaml(str(REGISTRY))

    def run(hide: bool):
        adapter = UnifiedAdapter.__new__(UnifiedAdapter)
        answers = [("increase_demand", "M"), ("maintain_demand", "M")]

        def parse(_raw, _ctx):
            skill, wsa = answers.pop(0)
            return SkillProposal(skill_name=skill, agent_id="A1", agent_type=AGENT_TYPE,
                                 reasoning={"WSA_LABEL": wsa, "ACA_LABEL": "M",
                                            "WSA_REASON": "x", "ACA_REASON": "x"})
        adapter.parse_output = parse
        engine = SkillBrokerEngine(
            skill_registry=registry, model_adapter=adapter,
            validators=[AgentValidator(config_path=str(CONFIG))],
            simulation_engine=None, context_builder=_AtCapContext(), config=config,
            custom_validators=[irrigation_governance_validator],
        )
        assert engine._hide_registry_backstop_reports is True  # from the YAML
        engine._hide_registry_backstop_reports = hide
        engine.audit_writer = GenericAuditWriter(AuditConfig(
            output_dir=str(tmp_path / f"audit_{hide}"), experiment_name="wp3-backstop"))
        prompts: List[str] = []
        engine.process_step(agent_id="A1", step_id=1, run_id="r", seed=1,
                            llm_invoke=lambda p: prompts.append(p) or "raw",
                            agent_type=AGENT_TYPE)
        # prompts[0] is the first attempt; prompts[1] the retry.
        retry = prompts[1]
        block = retry[:retry.index("PROMPT\n")]
        row = trace_to_csv_row(engine.audit_writer._trace_buffer[AGENT_TYPE][-1])
        return block, row

    block, row = run(hide=True)
    assert [line.strip() for line in block.splitlines() if "Reason:" in line] == [
        f"- Reason: {CAP_MESSAGE}"]
    for internal in ("Precondition", "at_allocation_cap", "Required field", "'decision'",
                     "output_schema", "precondition_violation", "Suggestion"):
        assert internal not in block, internal
    _assert_plain(block)
    assert "Actions that pass every rule this step: 1 (maintain demand), 2 (decrease demand)." in block
    # the audit keeps all three blocks of the off-menu attempt
    assert {"water_right_cap", "precondition_violation", "output_schema_violation"} <= set(
        row["failed_rules"].split("|"))
    assert row["final_skill"] == "maintain_demand"
    # grounding split: the identity rule is world-grounded; the registry
    # backstops carry no grounding stamp and are filed under
    # rules_self_report (irrigation_physics.md, "Post hoc")
    assert row["rules_world_grounded"] == "water_right_cap"
    assert set(row["rules_self_report"].split("|")) == {
        "output_schema_violation", "precondition_violation"}

    leaked, _ = run(hide=False)
    assert "Precondition failed" in leaked and "Required field 'decision'" in leaked
    AgentTypeConfig.clear_cache()


def _arm_script(agent, year, attempt, menu):
    """Exercises TR1 and TR3 once each per agent-year pair, then keeps."""
    if attempt == 0:
        return ("H", "M", "Increase") if agent.endswith(("0", "2", "4")) else ("L", "M", "Decrease")
    return "M", "M", "Keep"


@pytest.mark.parametrize("arm,args,thinking,dispatched", [
    ("strict", (), [TR1, TR3], [SUPPLY]),
    ("placebo", ("--retry-feedback-mode", "placebo"), [TR1, TR3], [SUPPLY]),
    ("silent", ("--retry-feedback-mode", "silent"), [TR1, TR3], [SUPPLY]),
    ("feasibility_only", ("--governance-mode", "feasibility_only"), [], [SUPPLY]),
    ("disabled", ("--governance-mode", "disabled"), [], []),
])
def test_e2e_every_arm_completes_with_its_resolved_rules(monkeypatch, tmp_path, arm, args,
                                                         thinking, dispatched):
    """Spec 3.1 acceptance: each arm's manifest shows its thinking rules
    (2, 2, 2, 0, 0), the three identity rules, the dispatched checks and the
    freeze; the audit columns are filled in every arm, and the thinking
    rules fire only where they are enforced."""
    llm = ScriptedIrrigationLLM(_arm_script)
    out = _run_main(monkeypatch, tmp_path / arm, llm,
                    "--years", "2", "--agents", "4", "--seed", "11", *args)
    manifest = json.loads((out / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert manifest["thinking_rules_resolved"] == {AGENT_TYPE: thinking}
    assert manifest["thinking_rules_resolved_counts"] == {AGENT_TYPE: len(thinking)}
    assert manifest["identity_rules_resolved"] == {
        AGENT_TYPE: ["water_right_cap", "beneficial_use_limit", "minimum_utilisation_floor"]}
    assert manifest["irrigation_dispatched_checks"] == dispatched
    assert manifest["appraisal_freeze_resolved"] is True
    rows = _audit_rows(out)
    assert len(rows) == 8
    fired = set()
    for row in rows:
        for key in ("initial_labels", "final_labels", "attempt_labels", "attempt_skills",
                    "executed_skill", *(f"state_{k}" for k in SUPPLY_RULE_FIELDS)):
            assert row[key] not in ("", "unobserved"), (arm, key)
        fired.update(r for attempt in row["attempt_failed_rules"].split("|")
                     for r in attempt.split(",") if r)
    assert fired & {TR1, TR3} == set(thinking)


@pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")
def test_e2e_live_supply_rule_agrees_with_post_hoc_predicate(monkeypatch, tmp_path):
    """Every agent asks for more every year with a neutral appraisal (TR1
    and TR3 never apply). On the real 78 agents, the live supply rule must
    block exactly the first attempts the post hoc predicate flags from the
    logged state_* inputs and FULL_SUPPLY_RATIO (pilot check P7: zero
    disagreements), and block at least once."""
    llm = ScriptedIrrigationLLM(lambda a, y, attempt, menu: (
        "M", "M", "Increase" if attempt == 0 else "Keep"))
    out = _run_main(monkeypatch, tmp_path / "real", llm,
                    "--real", "--years", "42", "--seed", "42")
    rows = _audit_rows(out)
    assert len(rows) == 3276
    disagreements, blocks = [], 0
    for row in rows:
        predicate = (row["initial_skill"] == "increase_demand"
                     and float(row["state_supply_physical_ratio"]) < FULL_SUPPLY_RATIO)
        live = SUPPLY in row["attempt_failed_rules"].split("|")[0].split(",")
        blocks += live
        if predicate != live:
            disagreements.append((row["agent_id"], row["year"]))
        if live:
            assert row["executed_skill"] == "maintain_demand"
            assert row["rules_world_grounded"] == SUPPLY
    assert disagreements == []
    assert blocks > 0
