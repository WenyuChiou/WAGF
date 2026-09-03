"""Parametric household decider for the Paper 3 SQ1 controlled baseline."""

from __future__ import annotations

import copy
import math
import random
import zlib
from typing import Any, Dict, Iterable, List, Optional, Tuple

from broker.interfaces.skill_types import SkillProposal
from examples.multi_agent.flood.environment.hazard import VulnerabilityModule
from examples.multi_agent.flood.environment.tp_decay import create_engine_for_group
from examples.multi_agent.flood.environment.tp_state import TPState


PARAMETRIC_CALIBRATION: Dict[str, Any] = {
    "base_rates": {
        "flood_prone_owner": 0.25,
        "flood_prone_renter": 0.08,
        "non_flood_prone_owner": 0.03,
        "non_flood_prone_renter": 0.01,
    },
    "slopes": {
        "threat": 2.0,
        "coping": 1.0,
        "cost": 1.5,
    },
    "anchors": {
        "tp0": 0.5,
        "cp0": 0.5,
    },
    "gates": {
        "elevate": {
            "min_flood_count": 2,
            "requires_not_elevated": True,
            "blocked_zones": ["LOW"],
        },
        "buyout": {
            "min_flood_count": 3,
            "blocked_zones": ["LOW"],
        },
        "relocate": {
            "min_flood_count": 1,
        },
    },
    "costs": {
        "default_effective_premium_rate": 0.008,
        "elevation_cost_usd": 80_000.0,
    },
}

OWNER_HIERARCHY = ("buy_insurance", "elevate_house", "buyout_program", "do_nothing")
RENTER_HIERARCHY = ("buy_contents_insurance", "relocate", "do_nothing")
PARAMETRIC_REASONING = "parametric PMT decision"
FEET_PER_METER = 3.28084


class ParametricHouseholdDecider:
    """FLOODABM-style PMT decision rule for household agents.

    The decider returns a broker ``SkillProposal`` so validation, audit,
    execution, lifecycle hooks, and state updates stay on the normal WAGF path.
    Random draws are keyed by experiment seed, agent id, and year, making
    decisions deterministic and independent of iteration order.
    """

    def __init__(
        self,
        seed: Optional[int] = 42,
        calibration: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.seed = 42 if seed is None else int(seed)
        self.calibration = copy.deepcopy(PARAMETRIC_CALIBRATION)
        if calibration:
            self._deep_update(self.calibration, calibration)
        self._vulnerability = VulnerabilityModule()
        self._tp_by_agent: Dict[str, float] = {}
        self._tp_update_cache: Dict[Tuple[str, int], float] = {}
        self._proposal_cache: Dict[Tuple[str, int], Dict[str, Any]] = {}

    def decide(
        self,
        agent: Any,
        env_state: Optional[Dict[str, Any]] = None,
        *,
        year: Optional[int] = None,
        agent_depth_m: Optional[float] = None,
    ) -> SkillProposal:
        """Return the parametric household decision as a broker proposal."""
        env = env_state or {}
        decision_year = self._resolve_year(env, year)
        agent_id = str(getattr(agent, "id", ""))
        cache_key = (agent_id, decision_year)
        if cache_key in self._proposal_cache:
            return self._proposal_from_dict(self._proposal_cache[cache_key])

        tp = self._update_tp(agent, env, decision_year, agent_depth_m)
        fixed = self._fixed(agent)
        cp = self._score_to_unit(fixed.get("cp_score", 3.0))

        skill_name = self._draw_decision(agent, env, decision_year, tp, cp)
        reasoning = self._reasoning(agent, skill_name, tp, cp)
        proposal = SkillProposal(
            skill_name=skill_name,
            agent_id=agent_id,
            agent_type=str(getattr(agent, "agent_type", "default")),
            reasoning=reasoning,
            confidence=1.0,
            raw_output=PARAMETRIC_REASONING,
            parse_layer="parametric",
            parse_confidence=1.0,
            construct_completeness=1.0,
        )
        data = proposal.to_dict()
        self._proposal_cache[cache_key] = data
        return self._proposal_from_dict(data)

    def eligible_actions(self, agent: Any) -> List[str]:
        """Return hierarchy-ordered actions after hard eligibility gates."""
        fixed = self._fixed(agent)
        dynamic = self._dynamic(agent)
        tenure = self._tenure(agent)
        flood_count = self._flood_count(agent)
        flood_zone = str(fixed.get("flood_zone", "MEDIUM")).upper()
        elevated = bool(dynamic.get("elevated", False))
        relocated = bool(dynamic.get("relocated", False))

        if relocated:
            return ["do_nothing"]

        if tenure == "Renter":
            actions = ["buy_contents_insurance"]
            if flood_count >= self.calibration["gates"]["relocate"]["min_flood_count"]:
                actions.append("relocate")
            actions.append("do_nothing")
            return actions

        actions = ["buy_insurance"]
        elevate_gate = self.calibration["gates"]["elevate"]
        if (
            flood_count >= int(elevate_gate["min_flood_count"])
            and not elevated
            and flood_zone not in set(elevate_gate.get("blocked_zones", []))
        ):
            actions.append("elevate_house")

        buyout_gate = self.calibration["gates"]["buyout"]
        if (
            flood_count >= int(buyout_gate["min_flood_count"])
            and flood_zone not in set(buyout_gate.get("blocked_zones", []))
        ):
            actions.append("buyout_program")

        actions.append("do_nothing")
        return actions

    def action_probability(
        self,
        action: str,
        agent: Any,
        env_state: Optional[Dict[str, Any]],
        tp: float,
        cp: float,
    ) -> float:
        """Compute anchored logistic probability for one eligible action."""
        if action == "do_nothing":
            return 1.0

        base_rate = self._base_rate(agent)
        slopes = self.calibration["slopes"]
        anchors = self.calibration["anchors"]
        cost_burden = self._cost_burden(action, agent, env_state or {})
        log_odds = (
            self._logit(base_rate)
            + float(slopes["threat"]) * (tp - float(anchors["tp0"]))
            + float(slopes["coping"]) * (cp - float(anchors["cp0"]))
            - float(slopes["cost"]) * cost_burden
        )
        return self._sigmoid(log_odds)

    def _draw_decision(
        self,
        agent: Any,
        env_state: Dict[str, Any],
        year: int,
        tp: float,
        cp: float,
    ) -> str:
        rng = random.Random(self._stable_seed(agent, year))
        for action in self.eligible_actions(agent):
            if action == "do_nothing":
                return "do_nothing"
            if rng.random() < self.action_probability(action, agent, env_state, tp, cp):
                return action
        return "do_nothing"

    def _update_tp(
        self,
        agent: Any,
        env_state: Dict[str, Any],
        year: int,
        agent_depth_m: Optional[float],
    ) -> float:
        agent_id = str(getattr(agent, "id", ""))
        cache_key = (agent_id, year)
        if cache_key in self._tp_update_cache:
            return self._tp_update_cache[cache_key]

        fixed = self._fixed(agent)
        previous_tp = self._tp_by_agent.get(
            agent_id,
            self._score_to_unit(fixed.get("tp_score", 3.0)),
        )
        pa = self._score_to_unit(fixed.get("pa_score", 3.0))
        sc = self._score_to_unit(fixed.get("sc_score", 3.0))
        damage, total_rcv = self._damage_for_tp(agent, env_state, agent_depth_m)

        engine = create_engine_for_group(bool(fixed.get("mg", False)))
        result = engine.update_tp(
            TPState(
                tp=previous_tp,
                pa=pa,
                sc=sc,
                year=max(year - 1, 0),
                is_mg=bool(fixed.get("mg", False)),
            ),
            total_damage=damage,
            total_rcv=total_rcv,
        )
        self._tp_by_agent[agent_id] = result.tp_new
        self._tp_update_cache[cache_key] = result.tp_new
        return result.tp_new

    def _damage_for_tp(
        self,
        agent: Any,
        env_state: Dict[str, Any],
        agent_depth_m: Optional[float],
    ) -> Tuple[float, float]:
        fixed = self._fixed(agent)
        dynamic = self._dynamic(agent)
        depth_m = self._depth_m(agent, env_state, agent_depth_m)
        rcv_building = float(fixed.get("rcv_building", 0.0) or 0.0)
        rcv_contents = float(fixed.get("rcv_contents", 0.0) or 0.0)
        total_rcv = max(rcv_building + rcv_contents, 1.0)
        if depth_m <= 0:
            return 0.0, total_rcv

        elev_ft = dynamic.get("elevation_feet") if dynamic.get("elevated") else None
        damage = self._vulnerability.calculate_damage(
            depth_ft=depth_m * FEET_PER_METER,
            rcv_building=rcv_building,
            rcv_contents=rcv_contents,
            is_elevated=bool(dynamic.get("elevated", False)),
            elevation_height_ft=elev_ft,
        )
        return float(damage.get("total_damage", 0.0) or 0.0), total_rcv

    def _depth_m(
        self,
        agent: Any,
        env_state: Dict[str, Any],
        agent_depth_m: Optional[float],
    ) -> float:
        if agent_depth_m is not None:
            return max(float(agent_depth_m), 0.0)
        dynamic = self._dynamic(agent)
        flooded_this_year = dynamic.get("flooded_this_year")
        if flooded_this_year is False:
            return 0.0
        if flooded_this_year is None and not env_state.get("flood_occurred", False):
            return 0.0
        if env_state.get("flood_depth_m") is not None:
            return max(float(env_state.get("flood_depth_m") or 0.0), 0.0)
        if env_state.get("flood_depth_ft") is not None:
            return max(float(env_state.get("flood_depth_ft") or 0.0) / FEET_PER_METER, 0.0)
        return 0.0

    def _reasoning(self, agent: Any, skill_name: str, tp: float, cp: float) -> Dict[str, str]:
        fixed = self._fixed(agent)
        reasoning = {
            "TP_LABEL": self._unit_to_label(tp),
            "CP_LABEL": self._unit_to_label(cp),
            "SP_LABEL": self._unit_to_label(self._score_to_unit(fixed.get("sp_score", 3.0))),
            "SC_LABEL": self._unit_to_label(self._score_to_unit(fixed.get("sc_score", 3.0))),
            "PA_LABEL": self._unit_to_label(self._score_to_unit(fixed.get("pa_score", 3.0))),
            "TP_NUMERIC": f"{tp:.4f}",
            "CP_NUMERIC": f"{cp:.4f}",
            "reasoning": PARAMETRIC_REASONING,
            "decision": skill_name,
        }
        if skill_name == "elevate_house":
            reasoning["elevation_feet"] = "5"
        elif skill_name == "buy_insurance":
            reasoning["insurance_coverage"] = "1"
        elif skill_name == "buy_contents_insurance":
            reasoning["insurance_coverage"] = "2"
        elif skill_name == "relocate":
            reasoning["relocation_destination"] = "1"
        return reasoning

    def _base_rate(self, agent: Any) -> float:
        fixed = self._fixed(agent)
        tenure = self._tenure(agent).lower()
        flood_prone = str(fixed.get("flood_zone", "MEDIUM")).upper() != "LOW"
        key = f"{'flood_prone' if flood_prone else 'non_flood_prone'}_{tenure}"
        base_rates = self.calibration["base_rates"]
        if key not in base_rates:
            # Fail loud: a partial calibration override that drops a base_rates
            # key would otherwise raise KeyError into the broker's per-agent
            # isolation, silently collapsing the affected agents to do_nothing
            # and understating the SQ1 parametric-vs-LLM divergence.
            raise KeyError(
                f"ParametricHouseholdDecider: no base_rate for key={key!r}; "
                f"calibration['base_rates'] has {sorted(base_rates)}. A partial "
                f"calibration override must not drop a base_rates key."
            )
        return float(base_rates[key])

    def _cost_burden(self, action: str, agent: Any, env_state: Dict[str, Any]) -> float:
        fixed = self._fixed(agent)
        income = max(float(fixed.get("income", 0.0) or 0.0), 1.0)
        rcv_building = float(fixed.get("rcv_building", 0.0) or 0.0)
        rcv_contents = float(fixed.get("rcv_contents", 0.0) or 0.0)

        if action in {"buy_insurance", "buy_contents_insurance"}:
            default_rate = float(self.calibration["costs"]["default_effective_premium_rate"])
            effective_rate = float(
                env_state.get("effective_rate", env_state.get("premium_rate", default_rate))
                or default_rate
            )
            coverage_base = (
                rcv_contents
                if action == "buy_contents_insurance"
                else rcv_building + rcv_contents
            )
            return max(effective_rate * coverage_base / income, 0.0)

        if action == "elevate_house":
            subsidy = float(env_state.get("subsidy_rate", 0.5) or 0.0)
            subsidy = min(max(subsidy, 0.0), 1.0)
            elevation_cost = float(self.calibration["costs"]["elevation_cost_usd"])
            return max(elevation_cost * (1.0 - subsidy) / income, 0.0)

        return 0.0

    def _stable_seed(self, agent: Any, year: int) -> int:
        agent_id = str(getattr(agent, "id", ""))
        return zlib.crc32(f"{self.seed}:{agent_id}:{year}".encode("utf-8"))

    def _flood_count(self, agent: Any) -> int:
        dynamic = self._dynamic(agent)
        fixed = self._fixed(agent)
        raw = dynamic.get("flood_count", fixed.get("flood_frequency", 0))
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _tenure(agent: Any) -> str:
        fixed = ParametricHouseholdDecider._fixed(agent)
        tenure = str(fixed.get("tenure", "") or "")
        if tenure in {"Owner", "Renter"}:
            return tenure
        return "Renter" if getattr(agent, "agent_type", "") == "household_renter" else "Owner"

    @staticmethod
    def _fixed(agent: Any) -> Dict[str, Any]:
        fixed = getattr(agent, "fixed_attributes", None)
        return fixed if isinstance(fixed, dict) else {}

    @staticmethod
    def _dynamic(agent: Any) -> Dict[str, Any]:
        dynamic = getattr(agent, "dynamic_state", None)
        return dynamic if isinstance(dynamic, dict) else {}

    @staticmethod
    def _resolve_year(env_state: Dict[str, Any], year: Optional[int]) -> int:
        raw = year
        if raw is None:
            raw = env_state.get("current_year", env_state.get("year", 1))
        try:
            return max(int(raw), 1)
        except (TypeError, ValueError):
            return 1

    @staticmethod
    def _score_to_unit(value: Any) -> float:
        try:
            raw = float(value)
        except (TypeError, ValueError):
            raw = 3.0
        return min(max((raw - 1.0) / 4.0, 0.0), 1.0)

    @staticmethod
    def _unit_to_label(value: float) -> str:
        v = min(max(float(value), 0.0), 1.0)
        if v < 0.2:
            return "VL"
        if v < 0.4:
            return "L"
        if v < 0.6:
            return "M"
        if v < 0.8:
            return "H"
        return "VH"

    @staticmethod
    def _sigmoid(value: float) -> float:
        if value >= 0:
            z = math.exp(-value)
            return 1.0 / (1.0 + z)
        z = math.exp(value)
        return z / (1.0 + z)

    @staticmethod
    def _logit(probability: float) -> float:
        p = min(max(float(probability), 1e-9), 1.0 - 1e-9)
        return math.log(p / (1.0 - p))

    @staticmethod
    def _proposal_from_dict(data: Dict[str, Any]) -> SkillProposal:
        copied = dict(data)
        copied["reasoning"] = dict(copied.get("reasoning") or {})
        copied["parsing_warnings"] = list(copied.get("parsing_warnings") or [])
        return SkillProposal(**copied)

    @classmethod
    def _deep_update(cls, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                cls._deep_update(target[key], value)
            else:
                target[key] = copy.deepcopy(value)
