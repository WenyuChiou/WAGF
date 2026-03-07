"""
Cognitive Appraisal Theory framework for irrigation agents.
"""

from typing import Dict, List, Optional

from broker.core.psychometric import (
    PsychologicalFramework,
    ConstructDef,
    ValidationResult,
)


class CognitiveAppraisalFramework(PsychologicalFramework):
    """Cognitive Appraisal Theory framework for irrigation agents."""

    def __init__(self, expected_behavior_map: Optional[Dict[str, List[str]]] = None):
        self._expected_behavior_map = expected_behavior_map

    @property
    def name(self) -> str:
        return "Cognitive Appraisal Theory"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        return {
            "WSA_LABEL": ConstructDef(
                name="Water Scarcity Appraisal",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description="Perceived scarcity or shortage pressure",
            ),
            "ACA_LABEL": ConstructDef(
                name="Adaptive Capacity Appraisal",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description="Perceived ability to adjust demand and operations",
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        wsa = str(appraisals.get("WSA_LABEL", "M")).upper()
        aca = str(appraisals.get("ACA_LABEL", "M")).upper()
        warnings = []
        if wsa in ("H", "VH") and aca in ("H", "VH"):
            warnings.append("High scarcity and high adaptive capacity typically support active adjustment.")

        return ValidationResult(
            valid=True,
            warnings=warnings,
            metadata={"wsa_label": wsa, "aca_label": aca},
        )

    _DEFAULT_BEHAVIOR_MAP: Dict[str, List[str]] = {
        "VH_VH": ["decrease_large", "decrease_small"],
        "VH_H": ["decrease_large", "decrease_small"],
        "H_VH": ["decrease_large", "decrease_small"],
        "H_H": ["decrease_small", "maintain_demand"],
        "M_M": ["maintain_demand", "decrease_small"],
        "L_M": ["maintain_demand", "increase_small"],
        "VL_H": ["increase_small", "maintain_demand"],
    }
    _DEFAULT_FALLBACK = ["maintain_demand"]

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        wsa = str(appraisals.get("WSA_LABEL", "M")).upper()
        aca = str(appraisals.get("ACA_LABEL", "M")).upper()
        key = f"{wsa}_{aca}"
        if self._expected_behavior_map is not None:
            return list(self._expected_behavior_map.get(key, []))
        return list(self._DEFAULT_BEHAVIOR_MAP.get(key, self._DEFAULT_FALLBACK))
