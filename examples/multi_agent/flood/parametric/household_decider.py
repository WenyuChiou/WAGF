"""A non-LLM household decider for the flood domain, on the same seam.

``parametric_decider.PARAMETRIC_CALIBRATION`` holds the numeric surface
a household adoption rule needs — per-(zone, tenure) base rates, PMT
slopes, eligibility gates, cost constants — and
``parametric_decider.aggregate_rates`` evaluates it in closed form over
a synthetic population, which is what makes the calibration search fast.
This module is the OTHER consumer of that same surface: the per-agent,
per-year form that runs inside the simulation loop, so that a household
whose action came from the calibrated logistic and a household whose
action came from a language model appear in the same audit CSV, having
passed the same validators, and can be compared without an asterisk.

The two consumers share one calibration dict on purpose. Re-typing the
base rates here would mean a calibration search that improves the
aggregate fit while the agents in the simulation keep deciding from the
old numbers — a drift that produces perfectly plausible results.

DETERMINISM. Every draw comes from ``hashlib.blake2b`` over
``(seed, agent_id, year, action)``. No shared RNG object, so the answer
does not depend on how many agents ran before this one, on whether the
run used a thread pool, or on Python's hash randomisation. Re-running a
seed reproduces every household's decision exactly, which is the
property that lets a parametric arm serve as the fixed reference an
LLM arm is measured against.

WHAT IT REQUIRES. ``tenure``, ``flood_zone``, ``tp_score``, ``cp_score``
and ``property_value`` must be readable off the agent (the flood domain
puts them in ``fixed_attributes``); a missing one RAISES, naming the
agent and the holders searched. There is no honest default for a field
that moves the decision — a fallback gives every unreadable agent the
same plausible answer, and the only symptom is that the population
decides alike. ``flood_count``, ``elevated``, ``has_insurance`` and
``year`` are optional, each with a documented default in
``OPTIONAL_FIELD_DEFAULTS``, and every use of one is named in the row's
``fields_defaulted``.

WHAT IT IS NOT. This is a decision RULE, not a cognitive model: it
reports no threat or coping appraisal because it has none to report.
See ``docs/guides/mixed_populations.md`` for how that shows up in the
audit columns and what it means for a rule the governance layer writes
against self-reported constructs.
"""

from __future__ import annotations

import hashlib
import math
import struct
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .parametric_decider import (
    OWNER_HIERARCHY,
    PARAMETRIC_CALIBRATION,
    RENTER_HIERARCHY,
    _logit,
    _sigmoid,
)

# Zones considered flood-prone. Mirrors ``aggregate_rates``, which
# treats every zone but LOW as prone.
NON_PRONE_ZONE = "LOW"

# Label -> position on the five-level scale the flood configs use, so a
# construct the agent carries as text can move the logistic. An agent
# that reports nothing sits at the calibration anchor and the term is
# zero, which is the same place ``aggregate_rates`` evaluates.
_LABEL_SCALE = {"VL": 0.1, "L": 0.3, "M": 0.5, "H": 0.7, "VH": 0.9}

# The scale the agents' NUMERIC appraisals are recorded on. The flood
# survey instrument (and `generate_agents.generate_pmt_scores`) records
# tp_score / cp_score as 1-5 Likert means; the logistic's anchors and
# `_LABEL_SCALE` are 0-1. Converting is not cosmetic: at 1-5 the term
# `slope * (tp - tp0)` reads 2.0 * (2.8 - 0.5) = +4.6 in the logit, which
# saturates the sigmoid for every agent in the population, and `_band`
# reports VH for all of them. The pre-review code never noticed because
# it could not READ tp_score at all (finding P0-A) and every agent sat at
# the anchor — one constant hiding another. Likert 3 (neutral) maps to
# 0.5, which is exactly the anchor the aggregate estimator evaluates at,
# so the two forms still agree where the docstring says they do.
# Overridable per config via `params: {appraisal_scale: [min, max]}`.
APPRAISAL_SCALE: Tuple[float, float] = (1.0, 5.0)


def _as_float(value: Any, default: float) -> float:
    if isinstance(value, str):
        scaled = _LABEL_SCALE.get(value.strip().upper())
        if scaled is not None:
            return scaled
        try:
            return float(value)
        except ValueError:
            return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _appraisal_to_unit(value: Any, scale: Tuple[float, float], *,
                       field: str, agent_id: str) -> float:
    """Put one appraisal on the 0-1 scale the logistic is calibrated on.

    A LABEL (``H``) is already 0-1 via ``_LABEL_SCALE``. A NUMBER is read
    as being on ``scale`` — declared, not sniffed, because a bare ``1.0``
    is a valid reading on both scales and guessing would silently pick
    the wrong one for a whole population.

    Review P1 (silent-failure hunter). Two things this function used to
    do quietly:

    A value that is present but UNUSABLE — ``NaN`` (a blank survey cell
    read by pandas), ``None``, ``""``, ``"N/A"``, ``"abc"`` — is not a
    reading of anything. The old code ran it through ``_as_float`` with a
    ``default`` fallback, which for every one of those inputs resolved to
    the UNIT-scale anchor (0.5) being read as a RAW Likert value: on a
    1-5 scale, ``(0.5 - 1.0) / 4.0`` clamps to 0.0, and every one of
    those five distinct "I could not read this" inputs banded to the
    SAME plausible label, VL — indistinguishable from an agent who
    genuinely reported no threat at all. This function now RAISES,
    naming the agent, the field and the raw value, the same way
    ``_require`` does for an absent field: there is no honest default for
    "this cell did not parse", any more than there is for "this cell was
    empty".

    A number OUTSIDE the declared scale (a Likert cell that somehow holds
    0, 6 or -2) used to be silently clamped into range with
    ``min(1.0, max(0.0, ...))`` — which turns a data-entry error into a
    real-looking VL or VH, indistinguishable from an agent who actually
    reported the extreme. This function now raises instead.
    """
    if isinstance(value, str) and value.strip().upper() in _LABEL_SCALE:
        return _LABEL_SCALE[value.strip().upper()]
    raw: Optional[float] = None
    if isinstance(value, bool):
        raw = float(value)
    elif isinstance(value, (int, float)):
        raw = float(value)
    elif isinstance(value, str):
        try:
            raw = float(value)
        except ValueError:
            raw = None
    if raw is None or math.isnan(raw) or math.isinf(raw):
        raise ValueError(
            f"AnchoredLogisticHouseholdDecider: agent {agent_id!r} carries "
            f"an unusable '{field}' value {value!r}. Expected a label in "
            f"{sorted(_LABEL_SCALE)} or a number on the declared "
            f"appraisal_scale {scale!r}; {value!r} is neither. There is no "
            f"honest default for an unreadable appraisal — a fallback here "
            f"would give every agent with a blank or malformed cell the "
            f"same plausible label. Fix the source data, or drop this "
            f"agent from the run."
        )
    low, high = float(scale[0]), float(scale[1])
    if high <= low:
        raise ValueError(
            f"AnchoredLogisticHouseholdDecider: appraisal_scale {scale!r} "
            f"is not an increasing interval."
        )
    if raw < low or raw > high:
        raise ValueError(
            f"AnchoredLogisticHouseholdDecider: agent {agent_id!r} carries "
            f"'{field}'={raw!r}, outside the declared appraisal_scale "
            f"{scale!r}. Clamping it would turn an out-of-range reading "
            f"into a plausible VL/VH label, indistinguishable from an "
            f"agent who genuinely reported the extreme. Fix the source "
            f"data, or correct appraisal_scale if the declared scale is "
            f"the one that is wrong."
        )
    return (raw - low) / (high - low)


def _band(value: float) -> str:
    """Put a 0-1 appraisal input back on the five-level scale."""
    for label, cut in (("VL", 0.2), ("L", 0.4), ("M", 0.6), ("H", 0.8)):
        if value < cut:
            return label
    return "VH"


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y")
    return bool(value)


_MISSING = object()

# The three dicts an agent hangs its state on. ``fixed_attributes`` is
# where ``orchestration/agent_factories.wrap_household`` puts the profile
# fields this decider runs on — flood_zone, tenure, tp_score, cp_score,
# property_value — and its absence from this tuple was review finding
# P0-A: every one of those reads fell through to a default, so every
# owner in the shipped mixed-population arm got the same anchored
# probability and the arm was a constant with a calibrated name.
_STATE_HOLDERS = ("custom_attributes", "fixed_attributes", "dynamic_state")

# Fields with a MEANINGFUL absence: an agent that carries no
# ``flood_count`` has not flooded, one with no ``has_insurance`` is
# uninsured. Each is listed here with the default it takes and why, and
# each use of a default is recorded on the row (see ``fields_defaulted``)
# so a reader can tell a real zero from an absent field.
OPTIONAL_FIELD_DEFAULTS: Dict[str, Any] = {
    "flood_count": 0,      # no recorded flood history == no floods
    "elevated": False,     # not recorded as elevated == not elevated
    "has_insurance": False,  # not recorded as insured == uninsured
    "year": 0,             # only enters the deterministic draw
}


def _read(agent: Any, env: Mapping[str, Any], *names: str) -> Any:
    """First of ``names`` the agent or the environment carries, or _MISSING."""
    for name in names:
        for holder_name in _STATE_HOLDERS:
            holder = getattr(agent, holder_name, None)
            if isinstance(holder, Mapping) and name in holder:
                return holder[name]
        sentinel = object()
        value = getattr(agent, name, sentinel)
        if value is not sentinel:
            return value
        if name in env:
            return env[name]
    return _MISSING


#: What a required field's value stringifies to when the source cell was
#: blank or absent but a row still got WRITTEN for it — a pandas ``NaN``
#: read into a plain Python object, or a literal ``None``. Neither is a
#: real reading; both are the same "nothing was here" as the ``_MISSING``
#: sentinel below, just wearing a value that survives a presence check.
_BLANK_LIKE_STRINGS = frozenset({"", "NAN", "NONE"})


def _require(agent: Any, env: Mapping[str, Any], *names: str,
             field: str, agent_id: str, reject_blank: bool = False) -> Any:
    """Read a REQUIRED field, or raise naming what was searched.

    Review P0-B. These four — tenure, flood_zone, tp_score, cp_score,
    property_value — used to fall back to a silent default: MEDIUM zone,
    the calibration anchor, a 400k reference property. Each of those is a
    plausible number, so a population the decider could not read produced
    a full CSV of plausible decisions, and the only symptom was that
    every agent decided alike. There is no honest default for "I could
    not find this agent's own value"; the run stops instead.

    ``reject_blank`` (review P1): a value can be PRESENT and still carry
    no real reading — a pandas ``NaN`` from a blank survey cell, or a
    literal ``None``. Left unguarded, ``str(value).upper()`` turns either
    into ``"NAN"`` / ``"NONE"``, which is not a real zone code and reads
    downstream as an ordinary (if unusual-looking) one — a blank cell
    that silently becomes a flood-prone zone. Pass ``True`` for a field
    with no code that legitimately means "blank" (``flood_zone`` has
    none); leave it ``False`` for a field where the raw value is used as
    a number rather than stringified for membership tests.
    """
    value = _read(agent, env, *names)
    if value is _MISSING:
        raise ValueError(
            f"AnchoredLogisticHouseholdDecider: agent {agent_id!r} carries no "
            f"'{field}'. Searched, in order, {list(names)} on the agent's "
            f"{list(_STATE_HOLDERS)}, its plain attributes, and this period's "
            f"environment. This field moves the decision, and there is no "
            f"honest default for it — a fallback here would give every "
            f"unreadable agent the same plausible answer. Load it onto the "
            f"agent (the flood domain puts it in fixed_attributes), or use a "
            f"decider that does not read it."
        )
    if reject_blank:
        is_blank = isinstance(value, float) and math.isnan(value)
        if not is_blank:
            is_blank = str(value).strip().upper() in _BLANK_LIKE_STRINGS
        if is_blank:
            raise ValueError(
                f"AnchoredLogisticHouseholdDecider: agent {agent_id!r} "
                f"carries a blank '{field}' value ({value!r}), which "
                f"stringifies to {str(value).strip().upper()!r} — not a "
                f"real reading. Searched, in order, {list(names)} on the "
                f"agent's {list(_STATE_HOLDERS)}, its plain attributes, "
                f"and this period's environment. Treated the same as a "
                f"missing field: there is no honest default for a blank "
                f"cell either."
            )
    return value


def _optional(agent: Any, env: Mapping[str, Any], *names: str,
              field: str, defaulted: List[str]) -> Any:
    """Read an OPTIONAL field, recording the fallback when one is used."""
    value = _read(agent, env, *names)
    if value is _MISSING:
        defaulted.append(field)
        return OPTIONAL_FIELD_DEFAULTS[field]
    return value


class AnchoredLogisticHouseholdDecider:
    """Decide one household's action from the calibrated logistic.

    ``calibration`` defaults to the shared ``PARAMETRIC_CALIBRATION``.
    ``seed`` enters every draw, so two deciders with the same seed and
    the same population produce the same trajectory.
    """

    def __init__(
        self,
        seed: int = 0,
        calibration: Optional[Dict[str, Any]] = None,
        appraisal_scale: Optional[Sequence[float]] = None,
    ) -> None:
        self.seed = int(seed)
        self.calibration = calibration or PARAMETRIC_CALIBRATION
        scale = tuple(appraisal_scale or APPRAISAL_SCALE)
        if len(scale) != 2:
            raise ValueError(
                f"AnchoredLogisticHouseholdDecider: appraisal_scale must be "
                f"[min, max]; got {appraisal_scale!r}."
            )
        self.appraisal_scale = (float(scale[0]), float(scale[1]))

    # -- the numbers ----------------------------------------------------

    def base_rate(self, flood_prone: bool, tenure: str) -> float:
        key = f"{'flood_prone' if flood_prone else 'non_flood_prone'}_{tenure.lower()}"
        rates = self.calibration["base_rates"]
        if key not in rates:
            raise KeyError(
                f"AnchoredLogisticHouseholdDecider: no base_rate for "
                f"key={key!r}; calibration['base_rates'] has {sorted(rates)}"
            )
        return float(rates[key])

    def action_probability(
        self,
        *,
        flood_prone: bool,
        tenure: str,
        threat: float,
        coping: float,
        cost_burden: float,
    ) -> float:
        """The anchored logistic ``aggregate_rates`` evaluates at its anchor.

        At ``threat == tp0`` and ``coping == cp0`` the two appraisal
        terms vanish and this collapses to
        ``sigmoid(logit(base) - cost_slope * cost_burden)`` — the exact
        expression the aggregate estimator uses. That correspondence is
        what makes a calibration fitted on aggregates meaningful for the
        per-agent path.
        """
        slopes = self.calibration["slopes"]
        anchors = self.calibration["anchors"]
        base = self.base_rate(flood_prone, tenure)
        z = (
            _logit(base)
            + float(slopes["threat"]) * (threat - float(anchors["tp0"]))
            + float(slopes["coping"]) * (coping - float(anchors["cp0"]))
            - float(slopes["cost"]) * cost_burden
        )
        return _sigmoid(z)

    # -- determinism ----------------------------------------------------

    def draw(self, agent_id: str, year: Any, action: str) -> float:
        """A reproducible uniform in [0, 1) for one (agent, year, action)."""
        material = f"{self.seed}|{agent_id}|{year}|{action}".encode("utf-8")
        digest = hashlib.blake2b(material, digest_size=8).digest()
        return struct.unpack(">Q", digest)[0] / float(1 << 64)

    # -- eligibility ----------------------------------------------------

    def _gate_open(self, action: str, *, zone: str, flood_count: int, elevated: bool) -> bool:
        gate = self.calibration["gates"].get(action)
        if not gate:
            return True
        if flood_count < int(gate.get("min_flood_count", 0)):
            return False
        if zone in set(gate.get("blocked_zones", [])):
            return False
        if gate.get("requires_not_elevated") and elevated:
            return False
        return True

    def _eligible(self, action: str, *, zone: str, flood_count: int,
                  elevated: bool, insured: bool) -> bool:
        if action == "do_nothing":
            return True
        if action in ("buy_insurance", "buy_contents_insurance") and insured:
            return False
        if action == "elevate_house":
            return self._gate_open("elevate", zone=zone, flood_count=flood_count,
                                   elevated=elevated)
        if action == "buyout_program":
            return self._gate_open("buyout", zone=zone, flood_count=flood_count,
                                   elevated=elevated)
        if action == "relocate":
            return self._gate_open("relocate", zone=zone, flood_count=flood_count,
                                   elevated=elevated)
        return True

    # -- the decision ---------------------------------------------------

    def decide(
        self,
        *,
        agent: Any = None,
        env: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
        agent_id: str = "",
        agent_type: str = "",
        **_ignored: Any,
    ):
        """Return ``(skill_id, reasoning)`` for this household this year.

        The signature is the one ``broker.agents.deciders``'
        ``parametric`` adapter and the flood pack's own factory call.
        """
        env = dict(env or {})
        aid = str(agent_id or getattr(agent, "id", "") or "unknown")
        defaulted: List[str] = []
        tenure = str(_require(agent, env, "tenure", field="tenure", agent_id=aid))
        tenure = "Renter" if tenure.strip().lower().startswith("rent") else "Owner"
        zone = str(_require(agent, env, "flood_zone",
                            field="flood_zone", agent_id=aid,
                            reject_blank=True)).upper()
        flood_prone = zone != NON_PRONE_ZONE
        flood_count = int(_as_float(_optional(
            agent, env, "flood_count", "prior_flood_count", "flood_experience",
            field="flood_count", defaulted=defaulted), 0.0))
        elevated = _as_bool(_optional(agent, env, "elevated", "is_elevated",
                                      field="elevated", defaulted=defaulted))
        insured = _as_bool(_optional(agent, env, "has_insurance",
                                     field="has_insurance", defaulted=defaulted))
        # No anchor fallback (P0-B). The anchor is where the AGGREGATE
        # estimator evaluates because it has no per-agent appraisals; a
        # per-agent path that quietly substituted it would report a
        # middling TP_LABEL / CP_LABEL the agent never held. Nor is there
        # an anchor fallback for a PRESENT but unusable reading (P1) — a
        # blank cell or an out-of-range Likert value raises inside
        # `_appraisal_to_unit` rather than sitting at the anchor either.
        threat = _appraisal_to_unit(
            _require(agent, env, "tp_score", "TP_LABEL",
                     field="tp_score", agent_id=aid),
            self.appraisal_scale, field="tp_score", agent_id=aid)
        coping = _appraisal_to_unit(
            _require(agent, env, "cp_score", "CP_LABEL",
                     field="cp_score", agent_id=aid),
            self.appraisal_scale, field="cp_score", agent_id=aid)
        year = _optional(agent, env, "current_year", "year",
                         field="year", defaulted=defaulted)

        hierarchy: Sequence[str] = (
            RENTER_HIERARCHY if tenure == "Renter" else OWNER_HIERARCHY
        )
        costs = self.calibration["costs"]
        property_value = _as_float(
            _require(agent, env, "property_value",
                     field="property_value", agent_id=aid), 0.0)

        chosen = "do_nothing"
        chosen_p = 0.0
        for action in hierarchy:
            if action == "do_nothing":
                continue
            if not self._eligible(action, zone=zone, flood_count=flood_count,
                                  elevated=elevated, insured=insured):
                continue
            if action in ("buy_insurance", "buy_contents_insurance"):
                burden = float(costs["default_effective_premium_rate"]) * 5.0
            elif action == "elevate_house":
                # The aggregate estimator divides by a fixed 400k reference
                # because it has no per-agent property values. This form
                # does, and uses them — that is the refinement the
                # per-agent path exists for — falling back to the same
                # reference when an agent carries no value, so a
                # population with none reproduces the aggregate exactly.
                # (`max(property_value, 400k)` would have been wrong: it
                # discards every value below the reference, which is
                # most of them.)
                if property_value > 0:
                    reference = property_value
                else:
                    reference = 400_000.0
                    if "property_value_reference" not in defaulted:
                        defaulted.append("property_value_reference")
                burden = float(costs["elevation_cost_usd"]) / reference
            else:
                # Buyout and relocation are last-resort moves, damped by a
                # unit cost burden. NOTE this is NOT the aggregate
                # estimator's damping: `aggregate_rates` multiplies the
                # base rate by 0.5 for buyout, whereas one unit of burden
                # here subtracts `cost_slope` inside the logit and lands
                # lower. The two are not calibrated against each other and
                # the buyout rate is the one benchmark where the per-agent
                # and aggregate forms are expected to disagree.
                burden = 1.0
            probability = self.action_probability(
                flood_prone=flood_prone, tenure=tenure,
                threat=threat, coping=coping, cost_burden=burden,
            )
            if self.draw(agent_id or str(getattr(agent, "id", "")), year, action) < probability:
                chosen, chosen_p = action, probability
                break

        reasoning = {
            # TP_LABEL / CP_LABEL are the logistic's OWN inputs, banded
            # back onto the five-level scale — not a self-report and not
            # an invention. Whatever the agent carried as tp_score /
            # cp_score is what moved the two appraisal terms; an agent
            # carrying neither sits at the calibration anchor, which
            # bands to M, and the terms contributed nothing.
            "TP_LABEL": _band(threat),
            "CP_LABEL": _band(coping),
            "decision_rule": "anchored_logistic",
            "tenure": tenure,
            "flood_zone": zone,
            "flood_count": flood_count,
            "action_probability": round(chosen_p, 6),
        }
        if defaulted:
            # P0-B: which OPTIONAL fields this row fell back on. Carried in
            # the reasoning dict (so it becomes a column) and into
            # raw_output by the factory below, because "the agent carried
            # no flood history" and "the agent has flooded zero times"
            # produce the same 0 and are not the same fact.
            reasoning["fields_defaulted"] = ",".join(sorted(set(defaulted)))
        return chosen, reasoning


def make_decider_factory(**defaults: Any):
    """A :class:`DeciderRegistry` factory bound to this decider.

    Used by ``FloodDomainPack.decider_factories()`` so the flood domain
    can offer ``decider: flood_household_parametric`` in its configs
    without a line of it living in ``broker/``.
    """
    from broker.agents.deciders import make_proposal, note_decider_path

    def factory(agent_type_config: Dict[str, Any], runtime: Dict[str, Any]):
        params = dict(defaults)
        params.update(runtime.get("decider_params") or {})
        decider = AnchoredLogisticHouseholdDecider(
            seed=int(params.get("seed", runtime.get("seed") or 0)),
            calibration=params.get("calibration"),
            appraisal_scale=params.get("appraisal_scale"),
        )
        agent = runtime.get("agent")
        agent_id = str(runtime.get("agent_id") or getattr(agent, "id", "unknown"))
        agent_type = str(runtime.get("agent_type") or "default")
        env = runtime.get("env")
        # Constructs the logistic does NOT model (stakeholder perception,
        # social capital, place attachment). The decider will not invent
        # them; a model builder who wants this agent type evaluated by
        # rules that read them declares the value here, in config, where
        # it is visible and reviewable. Absent, those rules do not fire
        # on these rows — which is a fact about the comparison, and is
        # recorded rather than papered over.
        declared_reasoning = dict(params.get("reasoning") or {})

        def decide(prompt: str = "", **_kwargs: Any):
            note_decider_path("parametric")
            skill, reasoning = decider.decide(
                agent=agent, env=env, agent_id=agent_id, agent_type=agent_type,
            )
            payload_extra = (
                {"fields_defaulted": reasoning["fields_defaulted"]}
                if reasoning.get("fields_defaulted") else None
            )
            return make_proposal(
                skill_name=skill, agent_id=agent_id, agent_type=agent_type,
                decider="flood_household_parametric", path="parametric",
                reasoning={**declared_reasoning, **reasoning},
                payload_extra=payload_extra,
            )

        return decide

    return factory


__all__ = [
    "AnchoredLogisticHouseholdDecider",
    "make_decider_factory",
]
