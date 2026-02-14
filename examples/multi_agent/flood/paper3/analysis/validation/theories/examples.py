"""
Example BehavioralTheory Implementations.

These demonstrate how to extend the framework for new domains:
  - TPBTheory: Theory of Planned Behavior (3 dimensions)
  - IrrigationWSATheory: Water Scarcity Awareness (2 dimensions)
"""

from typing import Dict, List


class TPBTheory:
    """Theory of Planned Behavior (Ajzen 1991).

    3 dimensions: attitude, subjective_norm, perceived_behavioral_control.
    Paradigm A: Construct-Action Mapping.
    """

    @property
    def name(self) -> str:
        return "tpb"

    @property
    def dimensions(self) -> List[str]:
        return ["attitude", "norm", "pbc"]

    @property
    def agent_types(self) -> List[str]:
        return ["individual"]

    def get_coherent_actions(
        self, construct_levels: Dict[str, str], agent_type: str
    ) -> List[str]:
        att = construct_levels.get("attitude", "M")
        norm = construct_levels.get("norm", "M")
        pbc = construct_levels.get("pbc", "M")

        high = {"H", "VH"}
        if att in high and norm in high and pbc in high:
            return ["adopt", "invest", "cooperate"]
        elif att in high and pbc in high:
            return ["adopt", "invest"]
        elif pbc in {"VL", "L"}:
            return ["do_nothing", "seek_help"]
        else:
            return ["do_nothing", "adopt"]

    def extract_constructs(self, trace: Dict) -> Dict[str, str]:
        reasoning = trace.get("skill_proposal", {}).get("reasoning", {})
        if isinstance(reasoning, dict):
            return {
                "attitude": reasoning.get("ATTITUDE_LABEL", "UNKNOWN"),
                "norm": reasoning.get("NORM_LABEL", "UNKNOWN"),
                "pbc": reasoning.get("PBC_LABEL", "UNKNOWN"),
            }
        return {"attitude": "UNKNOWN", "norm": "UNKNOWN", "pbc": "UNKNOWN"}

    def is_sensible_action(
        self, construct_levels: Dict[str, str], action: str, agent_type: str
    ) -> bool:
        return True


class IrrigationWSATheory:
    """Irrigation Water Scarcity Awareness theory.

    2 dimensions: WSA (Water Scarcity Awareness), ACA (Adaptive Capacity Assessment).
    Extracted from example_cv_usage.py Example 4.
    """

    RULES = {
        ("VH", "VH"): ["decrease_large", "decrease_small"],
        ("VH", "H"):  ["decrease_large", "decrease_small"],
        ("VH", "M"):  ["decrease_small", "maintain_demand"],
        ("VH", "L"):  ["maintain_demand", "decrease_small"],
        ("VH", "VL"): ["maintain_demand"],
        ("H", "VH"):  ["decrease_small", "decrease_large"],
        ("H", "H"):   ["decrease_small", "maintain_demand"],
        ("H", "M"):   ["decrease_small", "maintain_demand"],
        ("H", "L"):   ["maintain_demand"],
        ("H", "VL"):  ["maintain_demand"],
        ("M", "VH"):  ["maintain_demand", "increase_small", "decrease_small"],
        ("M", "H"):   ["maintain_demand", "increase_small"],
        ("M", "M"):   ["maintain_demand"],
        ("M", "L"):   ["maintain_demand"],
        ("M", "VL"):  ["maintain_demand"],
        ("L", "VH"):  ["increase_small", "increase_large", "maintain_demand"],
        ("L", "H"):   ["increase_small", "maintain_demand"],
        ("L", "M"):   ["maintain_demand", "increase_small"],
        ("L", "L"):   ["maintain_demand"],
        ("L", "VL"):  ["maintain_demand"],
        ("VL", "VH"): ["increase_large", "increase_small"],
        ("VL", "H"):  ["increase_large", "increase_small"],
        ("VL", "M"):  ["increase_small", "maintain_demand"],
        ("VL", "L"):  ["maintain_demand"],
        ("VL", "VL"): ["maintain_demand"],
    }

    @property
    def name(self) -> str:
        return "irrigation_wsa"

    @property
    def dimensions(self) -> List[str]:
        return ["WSA", "ACA"]

    @property
    def agent_types(self) -> List[str]:
        return ["farmer"]

    def get_coherent_actions(
        self, construct_levels: Dict[str, str], agent_type: str
    ) -> List[str]:
        key = (construct_levels.get("WSA", "M"), construct_levels.get("ACA", "M"))
        return self.RULES.get(key, ["maintain_demand"])

    def extract_constructs(self, trace: Dict) -> Dict[str, str]:
        reasoning = trace.get("skill_proposal", {}).get("reasoning", {})
        if isinstance(reasoning, dict):
            return {
                "WSA": reasoning.get("WSA_LABEL", "UNKNOWN"),
                "ACA": reasoning.get("ACA_LABEL", "UNKNOWN"),
            }
        return {"WSA": "UNKNOWN", "ACA": "UNKNOWN"}

    def is_sensible_action(
        self, construct_levels: Dict[str, str], action: str, agent_type: str
    ) -> bool:
        return True
