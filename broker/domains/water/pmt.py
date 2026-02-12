"""
Protection Motivation Theory (PMT) framework for household agents.

PMT models protective behavior through two cognitive processes:
- Threat Appraisal (TP): Perceived severity and vulnerability
- Coping Appraisal (CP): Self-efficacy and response efficacy

Key coherence rules:
- High TP + High CP should not result in do_nothing
- Low TP should not justify extreme actions
- VH TP requires protective action

Optional constructs:
- Stakeholder Perception (SP): Trust in external actors

Domain-specific skill names (extreme_actions, complex_actions)
are configurable via constructor.  Defaults are provided for
backward compatibility; new domains should override via arguments.
"""

from typing import Dict, List, Optional

from broker.core.psychometric import (
    PsychologicalFramework,
    ConstructDef,
    ValidationResult,
)

# PMT Label ordering for comparison
PMT_LABEL_ORDER = {"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4}


class PMTFramework(PsychologicalFramework):
    """Protection Motivation Theory framework for household agents."""

    def __init__(
        self,
        extreme_actions: Optional[set] = None,
        complex_actions: Optional[set] = None,
        expected_behavior_map: Optional[Dict[str, List[str]]] = None,
    ):
        self._extreme_actions = extreme_actions or {
            "relocate", "elevate_house", "buyout_program"
        }
        self._complex_actions = complex_actions or {
            "elevate_house", "relocate", "buyout_program"
        }
        self._expected_behavior_map = expected_behavior_map

    @property
    def name(self) -> str:
        return "Protection Motivation Theory (PMT)"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        """Return PMT constructs: TP, CP, and optional SP."""
        return {
            "TP_LABEL": ConstructDef(
                name="Threat Perception",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description="Perceived severity and vulnerability to threat"
            ),
            "CP_LABEL": ConstructDef(
                name="Coping Perception",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description="Perceived ability to cope with threat"
            ),
            "SP_LABEL": ConstructDef(
                name="Stakeholder Perception",
                values=["VL", "L", "M", "H", "VH"],
                required=False,
                description="Perceived support from stakeholders (government, insurance)"
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """Validate PMT coherence rules."""
        errors = []
        warnings = []
        violations = []

        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        if tp in ("H", "VH") and cp in ("H", "VH"):
            warnings.append("High threat + high coping typically leads to protective action")

        if tp == "VH":
            warnings.append("Very high threat typically requires protective action")

        return ValidationResult(
            valid=True,
            errors=errors,
            warnings=warnings,
            rule_violations=violations,
            metadata={
                "tp_label": tp,
                "cp_label": cp,
                "sp_label": appraisals.get("SP_LABEL", ""),
            }
        )

    def validate_action_coherence(
        self,
        appraisals: Dict[str, str],
        proposed_skill: str
    ) -> ValidationResult:
        """Validate that a proposed action is coherent with PMT appraisals."""
        errors = []
        warnings = []
        violations = []

        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        # Rule 1: High TP + High CP should not do_nothing
        if tp in ("H", "VH") and cp in ("H", "VH"):
            if proposed_skill == "do_nothing":
                errors.append("High threat + high coping should lead to protective action")
                violations.append("high_tp_high_cp_should_act")

        # Rule 2: VH TP requires action
        if tp == "VH":
            if proposed_skill == "do_nothing":
                errors.append("Very high threat perception requires protective action")
                violations.append("extreme_threat_requires_action")

        # Rule 3: Low TP should not justify extreme measures
        if tp in ("VL", "L"):
            if proposed_skill in self._extreme_actions:
                errors.append(f"Low threat ({tp}) does not justify extreme measure: {proposed_skill}")
                violations.append("low_tp_blocks_extreme_action")

        # Rule 4: Low CP limits complex actions
        if cp == "VL":
            if proposed_skill in self._complex_actions:
                warnings.append(f"Very low coping may limit ability to execute: {proposed_skill}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            rule_violations=violations,
            metadata={
                "tp_label": tp,
                "cp_label": cp,
                "proposed_skill": proposed_skill,
            }
        )

    # Default expected-behavior map keyed by "TP_CP" pair.
    _DEFAULT_BEHAVIOR_MAP: Dict[str, List[str]] = {
        "H_H":  ["elevate_house", "buy_insurance", "buyout_program", "relocate"],
        "VH_H": ["elevate_house", "buy_insurance", "buyout_program", "relocate"],
        "H_VH": ["elevate_house", "buy_insurance", "buyout_program", "relocate"],
        "VH_VH": ["elevate_house", "buy_insurance", "buyout_program", "relocate"],
        "H_VL": ["buy_insurance", "buyout_program"],
        "H_L":  ["buy_insurance", "buyout_program"],
        "H_M":  ["buy_insurance", "buyout_program"],
        "VH_VL": ["buy_insurance", "buyout_program"],
        "VH_L": ["buy_insurance", "buyout_program"],
        "VH_M": ["buy_insurance", "buyout_program"],
        "M_VL": ["buy_insurance", "do_nothing"],
        "M_L":  ["buy_insurance", "do_nothing"],
        "M_M":  ["buy_insurance", "do_nothing"],
        "M_H":  ["buy_insurance", "do_nothing"],
        "M_VH": ["buy_insurance", "do_nothing"],
    }
    _DEFAULT_FALLBACK = ["do_nothing", "buy_insurance"]

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """Return expected skills given PMT appraisals."""
        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        key = f"{tp}_{cp}"

        if self._expected_behavior_map is not None:
            return list(self._expected_behavior_map.get(key, []))

        return list(self._DEFAULT_BEHAVIOR_MAP.get(key, self._DEFAULT_FALLBACK))

    def get_blocked_skills(self, appraisals: Dict[str, str]) -> List[str]:
        """Return skills that should be blocked given PMT appraisals."""
        tp = self._normalize_label(appraisals.get("TP_LABEL", "M"))
        cp = self._normalize_label(appraisals.get("CP_LABEL", "M"))

        blocked = []

        if tp in ("H", "VH") and cp in ("H", "VH"):
            blocked.append("do_nothing")

        if tp == "VH":
            if "do_nothing" not in blocked:
                blocked.append("do_nothing")

        if tp in ("VL", "L"):
            blocked.extend(self._extreme_actions)

        return list(set(blocked))

    def _normalize_label(self, label: Optional[str]) -> str:
        """Normalize PMT label to standard format."""
        if not label:
            return "M"
        label = str(label).upper().strip()
        mappings = {
            "VERY LOW": "VL", "VERYLOW": "VL", "VERY_LOW": "VL",
            "LOW": "L",
            "MEDIUM": "M", "MED": "M", "MODERATE": "M",
            "HIGH": "H",
            "VERY HIGH": "VH", "VERYHIGH": "VH", "VERY_HIGH": "VH"
        }
        return mappings.get(label, label)

    def compare_labels(self, label1: str, label2: str) -> int:
        """Compare two PMT labels (-1, 0, or 1)."""
        order1 = PMT_LABEL_ORDER.get(self._normalize_label(label1), 2)
        order2 = PMT_LABEL_ORDER.get(self._normalize_label(label2), 2)
        if order1 < order2:
            return -1
        elif order1 > order2:
            return 1
        return 0
