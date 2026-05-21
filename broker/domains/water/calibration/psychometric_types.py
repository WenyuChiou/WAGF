"""
Psychometric Battery — Data types and constants.

Extracted from psychometric_battery.py for modularity.
Contains all dataclass definitions and shared constants used by
the psychometric battery and statistical computation modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# No default scenario directory — callers must provide domain-specific scenarios.
SCENARIO_DIR = None

# Backward compatibility alias
VIGNETTE_DIR = SCENARIO_DIR

# PMT label ordinal mapping for ICC computation
LABEL_TO_ORDINAL: Dict[str, int] = {
    "VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Scenario:
    """Standardized flood scenario for psychometric probing.

    Attributes:
        id: Unique scenario identifier.
        severity: "high", "medium", or "low".
        description: Human-readable description.
        scenario: Full scenario text presented to the agent.
        state_overrides: Agent state values for this scenario.
        expected_responses: Expected construct/action ranges.
    """
    id: str
    severity: str
    description: str
    scenario: str
    state_overrides: Dict[str, Any]
    expected_responses: Dict[str, Dict[str, List[str]]]

    @classmethod
    def from_yaml(cls, path: str | Path) -> Scenario:
        """Load scenario from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        v = data["scenario"]
        return cls(
            id=v["id"],
            severity=v["severity"],
            description=v["description"],
            scenario=v["scenario"],
            state_overrides=v.get("state_overrides", {}),
            expected_responses=v.get("expected_responses", {}),
        )


# Backward compatibility alias
Vignette = Scenario


@dataclass
class ProbeResponse:
    """Single response from an agent to a scenario probe.

    Supports both construct-rich mode (PMT with tp_label/cp_label)
    and construct-free mode (decision-only or generic constructs).

    Attributes:
        scenario_id: Which scenario was presented.
        archetype: Agent archetype (e.g., "risk_averse_homeowner").
        replicate: Replicate number (1-30).
        tp_label: Reported Threat Perception (PMT shorthand).
        cp_label: Reported Coping Perception (PMT shorthand).
        decision: Chosen action.
        reasoning: Full reasoning text.
        governed: Whether WAGF governance was active.
        raw_response: Full LLM response text.
        construct_labels: Generic construct label dict for non-PMT use.
    """
    scenario_id: str
    archetype: str
    replicate: int
    tp_label: str = ""
    cp_label: str = ""
    decision: str = ""
    reasoning: str = ""
    governed: bool = False
    raw_response: str = ""
    construct_labels: Dict[str, str] = field(default_factory=dict)

    # Backward compatibility: accept vignette_id as alias
    def __init__(self, scenario_id: str = "", archetype: str = "",
                 replicate: int = 0, tp_label: str = "",
                 cp_label: str = "", decision: str = "",
                 reasoning: str = "", governed: bool = False,
                 raw_response: str = "",
                 construct_labels: Optional[Dict[str, str]] = None,
                 vignette_id: str = ""):
        self.scenario_id = scenario_id or vignette_id
        self.archetype = archetype
        self.replicate = replicate
        self.tp_label = tp_label
        self.cp_label = cp_label
        self.decision = decision
        self.reasoning = reasoning
        self.governed = governed
        self.raw_response = raw_response
        self.construct_labels = construct_labels if construct_labels is not None else {}
        # Sync tp_label/cp_label into construct_labels for uniform access
        if self.tp_label and "TP_LABEL" not in self.construct_labels:
            self.construct_labels["TP_LABEL"] = self.tp_label
        if self.cp_label and "CP_LABEL" not in self.construct_labels:
            self.construct_labels["CP_LABEL"] = self.cp_label

    @property
    def vignette_id(self) -> str:
        """Backward compatibility alias for scenario_id."""
        return self.scenario_id

    @property
    def tp_ordinal(self) -> int:
        """Convert TP label to ordinal (1-5)."""
        return LABEL_TO_ORDINAL.get(self.tp_label.upper(), 3)

    @property
    def cp_ordinal(self) -> int:
        """Convert CP label to ordinal (1-5)."""
        return LABEL_TO_ORDINAL.get(self.cp_label.upper(), 3)

    def get_ordinal(
        self,
        construct: str,
        label_map: Optional[Dict[str, int]] = None,
    ) -> int:
        """Get ordinal value for any construct.

        Parameters
        ----------
        construct : str
            Construct name (e.g., "TP_LABEL", "WSA_LABEL").
        label_map : dict, optional
            Custom label->ordinal mapping.  Default: LABEL_TO_ORDINAL.

        Returns
        -------
        int
        """
        lmap = label_map or LABEL_TO_ORDINAL
        label = self.construct_labels.get(construct, "")
        return lmap.get(label.upper(), 0) if label else 0


@dataclass
class ICCResult:
    """Intraclass Correlation Coefficient result.

    Attributes:
        construct: Which construct was measured.
        icc_value: ICC(2,1) value (-1 to 1, target > 0.6).
        f_value: F-statistic from one-way ANOVA.
        p_value: p-value of F-test.
        n_subjects: Number of subjects (archetypes).
        n_raters: Number of raters (replicates).
        ci_lower: Lower bound of 95% CI.
        ci_upper: Upper bound of 95% CI.
    """
    construct: str
    icc_value: float
    f_value: float = 0.0
    p_value: float = 1.0
    n_subjects: int = 0
    n_raters: int = 0
    ci_lower: float = 0.0
    ci_upper: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "construct": self.construct,
            "icc": self.icc_value,
            "f_value": self.f_value,
            "p_value": self.p_value,
            "n_subjects": self.n_subjects,
            "n_raters": self.n_raters,
            "ci_95": [self.ci_lower, self.ci_upper],
        }


@dataclass
class ConsistencyResult:
    """Internal consistency (Cronbach's alpha analogue).

    For LLM agents, we compute the correlation between TP/CP ratings
    and action coherence across replicates -- analogous to Cronbach's
    alpha for multi-item scales.

    Attributes:
        alpha: Cronbach's alpha value (target > 0.7).
        n_items: Number of items (constructs).
        item_correlations: Pairwise correlations between constructs.
    """
    alpha: float
    n_items: int = 0
    item_correlations: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha": self.alpha,
            "n_items": self.n_items,
            "item_correlations": self.item_correlations,
        }


@dataclass
class ScenarioReport:
    """Report for a single scenario across all archetypes.

    Attributes:
        scenario_id: Scenario identifier.
        severity: Scenario severity level.
        n_responses: Total responses collected.
        tp_icc: ICC for Threat Perception.
        cp_icc: ICC for Coping Perception.
        decision_agreement: Fleiss' kappa for action agreement.
        coherence_rate: Fraction of responses with coherent action.
        incoherence_rate: Fraction with incoherent (hallucinated) action.
    """
    scenario_id: str
    severity: str
    n_responses: int
    tp_icc: Optional[ICCResult] = None
    cp_icc: Optional[ICCResult] = None
    decision_agreement: float = 0.0
    coherence_rate: float = 0.0
    incoherence_rate: float = 0.0

    @property
    def vignette_id(self) -> str:
        """Backward compatibility alias."""
        return self.scenario_id


# Backward compatibility alias
VignetteReport = ScenarioReport


@dataclass
class EffectSizeResult:
    """Between-archetype effect size (eta-squared).

    Measures how much variance in construct ratings is explained by
    archetype identity (between-group variance / total variance).

    Attributes:
        construct: Construct name ("tp" or "cp").
        eta_squared: Eta-squared value (0-1, target >= 0.25).
        ss_between: Sum of squares between archetypes.
        ss_total: Total sum of squares.
        f_value: F-statistic from one-way ANOVA.
        p_value: p-value of F-test.
    """
    construct: str
    eta_squared: float
    ss_between: float = 0.0
    ss_total: float = 0.0
    f_value: float = 0.0
    p_value: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "construct": self.construct,
            "eta_squared": round(self.eta_squared, 4),
            "ss_between": round(self.ss_between, 2),
            "ss_total": round(self.ss_total, 2),
            "f_value": round(self.f_value, 3),
            "p_value": round(self.p_value, 6),
        }


@dataclass
class ConvergentValidityResult:
    """Convergent validity -- correlation between construct and external criterion.

    For flood domain: TP ordinal should correlate with scenario severity.

    Attributes:
        construct: Construct name.
        criterion: External criterion name.
        spearman_rho: Spearman rank correlation.
        p_value: p-value of the correlation.
        n_observations: Number of observations.
    """
    construct: str
    criterion: str
    spearman_rho: float
    p_value: float = 1.0
    n_observations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "construct": self.construct,
            "criterion": self.criterion,
            "spearman_rho": round(self.spearman_rho, 4),
            "p_value": round(self.p_value, 6),
            "n_observations": self.n_observations,
        }


@dataclass
class BatteryReport:
    """Complete psychometric battery report.

    Attributes:
        scenario_reports: Per-scenario results.
        overall_tp_icc: ICC for TP across all scenarios.
        overall_cp_icc: ICC for CP across all scenarios.
        consistency: Internal consistency (Cronbach's alpha).
        governance_effect: Paired comparison results (governed vs not).
        n_total_probes: Total LLM calls made.
        tp_effect_size: Eta-squared for TP between archetypes.
        cp_effect_size: Eta-squared for CP between archetypes.
        convergent_validity: TP vs scenario severity correlation.
        tp_cp_discriminant: TP-CP inter-construct correlation.
    """
    scenario_reports: List[ScenarioReport] = field(default_factory=list)
    overall_tp_icc: Optional[ICCResult] = None
    overall_cp_icc: Optional[ICCResult] = None
    consistency: Optional[ConsistencyResult] = None
    governance_effect: Dict[str, Any] = field(default_factory=dict)
    n_total_probes: int = 0
    tp_effect_size: Optional[EffectSizeResult] = None
    cp_effect_size: Optional[EffectSizeResult] = None
    convergent_validity: Optional[ConvergentValidityResult] = None
    tp_cp_discriminant: float = 0.0

    @property
    def vignette_reports(self) -> List[ScenarioReport]:
        """Backward compatibility alias."""
        return self.scenario_reports

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "n_total_probes": self.n_total_probes,
            "n_scenarios": len(self.scenario_reports),
        }
        if self.overall_tp_icc:
            d["overall_tp_icc"] = self.overall_tp_icc.to_dict()
        if self.overall_cp_icc:
            d["overall_cp_icc"] = self.overall_cp_icc.to_dict()
        if self.consistency:
            d["consistency"] = self.consistency.to_dict()
        if self.governance_effect:
            d["governance_effect"] = self.governance_effect
        if self.tp_effect_size:
            d["tp_effect_size"] = self.tp_effect_size.to_dict()
        if self.cp_effect_size:
            d["cp_effect_size"] = self.cp_effect_size.to_dict()
        if self.convergent_validity:
            d["convergent_validity"] = self.convergent_validity.to_dict()
        d["tp_cp_discriminant_r"] = round(self.tp_cp_discriminant, 4)
        return d
