"""
Level 3 — COGNITIVE Validation: Psychometric Battery.

Implements standardized vignette probes for evaluating LLM agent
psychological construct fidelity.  Each agent archetype responds to
standardized flood scenarios multiple times to assess:

    1. Test-retest reliability (ICC)
    2. Internal consistency (Cronbach's alpha analogue)
    3. Governance effect on construct fidelity (paired comparison)

Protocol (from C&V plan Section 4):
    P1: 6 archetypes x 3 vignettes x 30 replicates = 540 LLM calls
    P2: With/without governance = 1,080 calls

References:
    Huang et al. (2025) — "A psychometric framework for evaluating
        and shaping personality traits in large language models"
        Nature Machine Intelligence. doi:10.1038/s42256-025-01115-6
    Grothmann & Reusswig (2006) — PMT + flood preparedness scenarios

Part of SAGE C&V Framework (feature/calibration-validation).
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

VIGNETTE_DIR = Path(__file__).parent / "vignettes"

# PMT label ordinal mapping for ICC computation
LABEL_TO_ORDINAL: Dict[str, int] = {
    "VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Vignette:
    """Standardized flood scenario for psychometric probing.

    Attributes:
        id: Unique vignette identifier.
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
    def from_yaml(cls, path: str | Path) -> Vignette:
        """Load vignette from YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        v = data["vignette"]
        return cls(
            id=v["id"],
            severity=v["severity"],
            description=v["description"],
            scenario=v["scenario"],
            state_overrides=v.get("state_overrides", {}),
            expected_responses=v.get("expected_responses", {}),
        )


@dataclass
class ProbeResponse:
    """Single response from an agent to a vignette probe.

    Supports both construct-rich mode (PMT with tp_label/cp_label)
    and construct-free mode (decision-only or generic constructs).

    Attributes:
        vignette_id: Which vignette was presented.
        archetype: Agent archetype (e.g., "risk_averse_homeowner").
        replicate: Replicate number (1-30).
        tp_label: Reported Threat Perception (PMT shorthand).
        cp_label: Reported Coping Perception (PMT shorthand).
        decision: Chosen action.
        reasoning: Full reasoning text.
        governed: Whether SAGE governance was active.
        raw_response: Full LLM response text.
        construct_labels: Generic construct label dict for non-PMT use.
    """
    vignette_id: str
    archetype: str
    replicate: int
    tp_label: str = ""
    cp_label: str = ""
    decision: str = ""
    reasoning: str = ""
    governed: bool = False
    raw_response: str = ""
    construct_labels: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        # Sync tp_label/cp_label into construct_labels for uniform access
        if self.tp_label and "TP_LABEL" not in self.construct_labels:
            self.construct_labels["TP_LABEL"] = self.tp_label
        if self.cp_label and "CP_LABEL" not in self.construct_labels:
            self.construct_labels["CP_LABEL"] = self.cp_label

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
            Custom label→ordinal mapping.  Default: LABEL_TO_ORDINAL.

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
    and action coherence across replicates — analogous to Cronbach's
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
class VignetteReport:
    """Report for a single vignette across all archetypes.

    Attributes:
        vignette_id: Vignette identifier.
        severity: Vignette severity level.
        n_responses: Total responses collected.
        tp_icc: ICC for Threat Perception.
        cp_icc: ICC for Coping Perception.
        decision_agreement: Fleiss' kappa for action agreement.
        coherence_rate: Fraction of responses with coherent action.
        incoherence_rate: Fraction with incoherent (hallucinated) action.
    """
    vignette_id: str
    severity: str
    n_responses: int
    tp_icc: Optional[ICCResult] = None
    cp_icc: Optional[ICCResult] = None
    decision_agreement: float = 0.0
    coherence_rate: float = 0.0
    incoherence_rate: float = 0.0


@dataclass
class BatteryReport:
    """Complete psychometric battery report.

    Attributes:
        vignette_reports: Per-vignette results.
        overall_tp_icc: ICC for TP across all vignettes.
        overall_cp_icc: ICC for CP across all vignettes.
        consistency: Internal consistency (Cronbach's alpha).
        governance_effect: Paired comparison results (governed vs not).
        n_total_probes: Total LLM calls made.
    """
    vignette_reports: List[VignetteReport] = field(default_factory=list)
    overall_tp_icc: Optional[ICCResult] = None
    overall_cp_icc: Optional[ICCResult] = None
    consistency: Optional[ConsistencyResult] = None
    governance_effect: Dict[str, Any] = field(default_factory=dict)
    n_total_probes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "n_total_probes": self.n_total_probes,
            "n_vignettes": len(self.vignette_reports),
        }
        if self.overall_tp_icc:
            d["overall_tp_icc"] = self.overall_tp_icc.to_dict()
        if self.overall_cp_icc:
            d["overall_cp_icc"] = self.overall_cp_icc.to_dict()
        if self.consistency:
            d["consistency"] = self.consistency.to_dict()
        if self.governance_effect:
            d["governance_effect"] = self.governance_effect
        return d


# ---------------------------------------------------------------------------
# Statistical computations
# ---------------------------------------------------------------------------

def compute_icc_2_1(
    ratings: np.ndarray,
    construct_name: str = "",
) -> ICCResult:
    """Compute ICC(2,1) — two-way random, single measures.

    This is the standard ICC for test-retest reliability where both
    subjects (archetypes) and raters (replicates) are random effects.

    Parameters
    ----------
    ratings : ndarray, shape (n_subjects, n_raters)
        Rating matrix where rows = subjects, columns = replicates.
    construct_name : str
        Label for the construct being measured.

    Returns
    -------
    ICCResult

    References
    ----------
    Shrout & Fleiss (1979). Intraclass Correlations: Uses in Assessing
        Rater Reliability. Psychological Bulletin, 86(2), 420-428.
    """
    n, k = ratings.shape  # n subjects, k raters

    if n < 2 or k < 2:
        return ICCResult(
            construct=construct_name,
            icc_value=0.0,
            n_subjects=n,
            n_raters=k,
        )

    # Grand mean
    grand_mean = np.mean(ratings)

    # Between-subjects sum of squares
    subject_means = np.mean(ratings, axis=1)
    ss_between = k * np.sum((subject_means - grand_mean) ** 2)

    # Within-subjects sum of squares
    ss_within = np.sum((ratings - subject_means[:, np.newaxis]) ** 2)

    # Between-raters sum of squares
    rater_means = np.mean(ratings, axis=0)
    ss_raters = n * np.sum((rater_means - grand_mean) ** 2)

    # Residual (error) sum of squares
    ss_error = ss_within - ss_raters

    # Mean squares
    ms_between = ss_between / (n - 1) if n > 1 else 0
    ms_raters = ss_raters / (k - 1) if k > 1 else 0
    ms_error = ss_error / ((n - 1) * (k - 1)) if (n > 1 and k > 1) else 0

    # ICC(2,1) = (MS_between - MS_error) / (MS_between + (k-1)*MS_error + k*(MS_raters - MS_error)/n)
    denom = (
        ms_between
        + (k - 1) * ms_error
        + k * (ms_raters - ms_error) / n
    )

    if denom == 0:
        icc = 0.0
    else:
        icc = (ms_between - ms_error) / denom

    # F-value for significance test
    f_val = ms_between / ms_error if ms_error > 0 else 0.0

    # Approximate p-value from F distribution
    try:
        from scipy import stats as sp_stats
        df1 = n - 1
        df2 = (n - 1) * (k - 1)
        p_val = 1 - sp_stats.f.cdf(f_val, df1, df2) if f_val > 0 else 1.0

        # 95% CI using Shrout-Fleiss formulas
        fl = f_val / sp_stats.f.ppf(0.975, df1, df2) if f_val > 0 else 0
        fu = f_val * sp_stats.f.ppf(0.975, df2, df1) if f_val > 0 else 0

        ci_lower = max(-1.0, (fl - 1) / (fl + k - 1)) if fl > 0 else -1.0
        ci_upper = min(1.0, (fu - 1) / (fu + k - 1)) if fu > 0 else 1.0
    except ImportError:
        p_val = 1.0
        ci_lower = 0.0
        ci_upper = 0.0

    return ICCResult(
        construct=construct_name,
        icc_value=float(np.clip(icc, -1.0, 1.0)),
        f_value=float(f_val),
        p_value=float(p_val),
        n_subjects=n,
        n_raters=k,
        ci_lower=float(ci_lower),
        ci_upper=float(ci_upper),
    )


def compute_cronbach_alpha(items: np.ndarray) -> float:
    """Compute Cronbach's alpha for internal consistency.

    Parameters
    ----------
    items : ndarray, shape (n_observations, n_items)
        Each column is an "item" (construct rating), each row is
        a response.

    Returns
    -------
    float
        Cronbach's alpha (0-1, target > 0.7).
    """
    n_items = items.shape[1]
    if n_items < 2:
        return 0.0

    item_vars = np.var(items, axis=0, ddof=1)
    total_var = np.var(np.sum(items, axis=1), ddof=1)

    if total_var == 0:
        return 0.0

    alpha = (n_items / (n_items - 1)) * (1 - np.sum(item_vars) / total_var)
    return float(np.clip(alpha, 0.0, 1.0))


def compute_fleiss_kappa(
    decisions: List[List[str]],
) -> float:
    """Compute Fleiss' kappa for nominal agreement.

    Parameters
    ----------
    decisions : list of list of str
        Outer list = subjects (archetype-vignette combos),
        inner list = rater decisions (replicates).

    Returns
    -------
    float
        Fleiss' kappa (-1 to 1, target > 0.4 for moderate agreement).
    """
    if not decisions:
        return 0.0

    # Collect all unique categories
    categories = sorted(set(d for sublist in decisions for d in sublist))
    n_cat = len(categories)
    cat_idx = {c: i for i, c in enumerate(categories)}

    n_subjects = len(decisions)
    n_raters = len(decisions[0]) if decisions else 0

    if n_subjects < 2 or n_raters < 2 or n_cat < 2:
        return 0.0

    # Build rating matrix: n_subjects x n_categories
    rating_matrix = np.zeros((n_subjects, n_cat), dtype=float)
    for i, subject_decisions in enumerate(decisions):
        for d in subject_decisions:
            if d in cat_idx:
                rating_matrix[i, cat_idx[d]] += 1

    # Proportion of ratings per category
    p_j = np.sum(rating_matrix, axis=0) / (n_subjects * n_raters)

    # Per-subject agreement
    p_i = np.sum(rating_matrix ** 2, axis=1) - n_raters
    p_i = p_i / (n_raters * (n_raters - 1))

    # Overall agreement
    p_bar = np.mean(p_i)

    # Expected agreement by chance
    p_e = np.sum(p_j ** 2)

    if p_e == 1.0:
        return 1.0

    kappa = (p_bar - p_e) / (1 - p_e)
    return float(np.clip(kappa, -1.0, 1.0))


# ---------------------------------------------------------------------------
# Psychometric Battery
# ---------------------------------------------------------------------------

class PsychometricBattery:
    """Level 3 cognitive validation: standardized vignette probes.

    This module manages vignette loading, probe execution, and
    statistical analysis of probe responses.

    **Note**: Actual LLM inference is handled externally (the caller
    passes a probe function).  This module only handles:
    - Vignette management
    - Response collection
    - Statistical analysis (ICC, Cronbach, Fleiss)
    - Report generation

    Parameters
    ----------
    vignette_dir : Path, optional
        Directory containing vignette YAML files.
    """

    def __init__(self, vignette_dir: Optional[Path] = None):
        self._vignette_dir = vignette_dir or VIGNETTE_DIR
        self._vignettes: Dict[str, Vignette] = {}
        self._responses: List[ProbeResponse] = []

    # ------------------------------------------------------------------
    # Vignette management
    # ------------------------------------------------------------------

    def load_vignettes(self) -> List[Vignette]:
        """Load all vignette YAML files from the vignette directory."""
        self._vignettes.clear()
        vdir = Path(self._vignette_dir)
        if not vdir.exists():
            return []

        for yaml_file in sorted(vdir.glob("*.yaml")):
            try:
                v = Vignette.from_yaml(yaml_file)
                self._vignettes[v.id] = v
            except Exception:
                continue

        return list(self._vignettes.values())

    @property
    def vignettes(self) -> Dict[str, Vignette]:
        """Return loaded vignettes."""
        if not self._vignettes:
            self.load_vignettes()
        return self._vignettes

    # ------------------------------------------------------------------
    # Response collection
    # ------------------------------------------------------------------

    def add_response(self, response: ProbeResponse) -> None:
        """Add a single probe response."""
        self._responses.append(response)

    def add_responses(self, responses: List[ProbeResponse]) -> None:
        """Add multiple probe responses."""
        self._responses.extend(responses)

    @property
    def responses(self) -> List[ProbeResponse]:
        return list(self._responses)

    def responses_to_dataframe(self) -> pd.DataFrame:
        """Convert collected responses to DataFrame."""
        if not self._responses:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "vignette_id": r.vignette_id,
                "archetype": r.archetype,
                "replicate": r.replicate,
                "tp_label": r.tp_label,
                "cp_label": r.cp_label,
                "tp_ordinal": r.tp_ordinal,
                "cp_ordinal": r.cp_ordinal,
                "decision": r.decision,
                "governed": r.governed,
            }
            for r in self._responses
        ])

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def compute_icc(
        self,
        vignette_id: Optional[str] = None,
        construct: str = "tp",
        governed: Optional[bool] = None,
    ) -> ICCResult:
        """Compute ICC(2,1) for a construct across archetypes.

        Parameters
        ----------
        vignette_id : str, optional
            Filter to specific vignette (None = all).
        construct : str
            "tp" or "cp" (which construct to analyze).
        governed : bool, optional
            Filter to governed or ungoverned responses.

        Returns
        -------
        ICCResult
        """
        df = self.responses_to_dataframe()
        if df.empty:
            return ICCResult(construct=construct, icc_value=0.0)

        # Filter
        if vignette_id:
            df = df[df["vignette_id"] == vignette_id]
        if governed is not None:
            df = df[df["governed"] == governed]

        ordinal_col = f"{construct}_ordinal"
        if ordinal_col not in df.columns:
            return ICCResult(construct=construct, icc_value=0.0)

        # Build rating matrix: archetypes (subjects) x replicates (raters)
        archetypes = sorted(df["archetype"].unique())
        max_rep = df["replicate"].max()

        # Pivot to matrix form
        matrix = np.full((len(archetypes), max_rep), np.nan)
        for i, arch in enumerate(archetypes):
            arch_df = df[df["archetype"] == arch].sort_values("replicate")
            for _, row in arch_df.iterrows():
                rep = int(row["replicate"]) - 1
                if rep < max_rep:
                    matrix[i, rep] = row[ordinal_col]

        # Remove columns (replicates) with any NaN
        valid_cols = ~np.any(np.isnan(matrix), axis=0)
        matrix = matrix[:, valid_cols]

        if matrix.shape[0] < 2 or matrix.shape[1] < 2:
            return ICCResult(
                construct=construct, icc_value=0.0,
                n_subjects=matrix.shape[0], n_raters=matrix.shape[1],
            )

        return compute_icc_2_1(matrix, construct_name=construct)

    def compute_consistency(
        self,
        governed: Optional[bool] = None,
    ) -> ConsistencyResult:
        """Compute internal consistency (Cronbach's alpha analogue).

        Treats TP and CP ordinal ratings as two "items" in a scale.

        Parameters
        ----------
        governed : bool, optional
            Filter to governed or ungoverned responses.

        Returns
        -------
        ConsistencyResult
        """
        df = self.responses_to_dataframe()
        if df.empty:
            return ConsistencyResult(alpha=0.0)

        if governed is not None:
            df = df[df["governed"] == governed]

        items = df[["tp_ordinal", "cp_ordinal"]].values
        if len(items) < 3:
            return ConsistencyResult(alpha=0.0, n_items=2)

        alpha = compute_cronbach_alpha(items)

        # Pairwise correlations
        tp = items[:, 0].astype(float)
        cp = items[:, 1].astype(float)
        corr_matrix = np.corrcoef(tp, cp)
        tp_cp_corr = float(corr_matrix[0, 1]) if not np.isnan(corr_matrix[0, 1]) else 0.0

        return ConsistencyResult(
            alpha=alpha,
            n_items=2,
            item_correlations={"tp_cp": tp_cp_corr},
        )

    def compute_decision_agreement(
        self,
        vignette_id: Optional[str] = None,
        governed: Optional[bool] = None,
    ) -> float:
        """Compute Fleiss' kappa for action agreement across replicates.

        Parameters
        ----------
        vignette_id : str, optional
            Filter to specific vignette.
        governed : bool, optional
            Filter to governed or ungoverned responses.

        Returns
        -------
        float
            Fleiss' kappa value.
        """
        df = self.responses_to_dataframe()
        if df.empty:
            return 0.0

        if vignette_id:
            df = df[df["vignette_id"] == vignette_id]
        if governed is not None:
            df = df[df["governed"] == governed]

        # Group by archetype — each archetype's replicates form a "subject"
        decision_lists = []
        for arch, arch_df in df.groupby("archetype"):
            decisions = arch_df.sort_values("replicate")["decision"].tolist()
            if len(decisions) >= 2:
                decision_lists.append(decisions)

        # Pad to same length
        if not decision_lists:
            return 0.0
        max_len = max(len(d) for d in decision_lists)
        padded = [
            d + [d[-1]] * (max_len - len(d))  # Repeat last decision to pad
            for d in decision_lists
        ]

        return compute_fleiss_kappa(padded)

    def evaluate_coherence(
        self,
        vignette_id: str,
        governed: Optional[bool] = None,
    ) -> Tuple[float, float]:
        """Evaluate response coherence against vignette expectations.

        Parameters
        ----------
        vignette_id : str
            Which vignette to evaluate.
        governed : bool, optional
            Filter to governed or ungoverned.

        Returns
        -------
        (coherence_rate, incoherence_rate)
            Fraction of responses in expected vs incoherent ranges.
        """
        vignette = self._vignettes.get(vignette_id)
        if not vignette:
            return 0.0, 0.0

        df = self.responses_to_dataframe()
        if df.empty:
            return 0.0, 0.0

        df = df[df["vignette_id"] == vignette_id]
        if governed is not None:
            df = df[df["governed"] == governed]

        if df.empty:
            return 0.0, 0.0

        n = len(df)
        expected = vignette.expected_responses
        n_coherent = 0
        n_incoherent = 0

        for _, row in df.iterrows():
            # Check TP
            tp_expected = expected.get("TP_LABEL", {})
            tp_incoherent = tp_expected.get("incoherent", [])
            if row["tp_label"] in tp_incoherent:
                n_incoherent += 1
                continue

            # Check decision
            dec_expected = expected.get("decision", {})
            dec_incoherent = dec_expected.get("incoherent", [])
            dec_acceptable = dec_expected.get("acceptable", [])
            if row["decision"] in dec_incoherent:
                n_incoherent += 1
            elif row["decision"] in dec_acceptable:
                n_coherent += 1

        return (
            n_coherent / n if n > 0 else 0.0,
            n_incoherent / n if n > 0 else 0.0,
        )

    # ------------------------------------------------------------------
    # Construct-free cognitive metrics
    # ------------------------------------------------------------------

    def compute_decision_icc(
        self,
        vignette_id: Optional[str] = None,
        governed: Optional[bool] = None,
        action_ordinal_map: Optional[Dict[str, int]] = None,
    ) -> ICCResult:
        """Compute ICC on decision choices (construct-free).

        Maps action names to ordinal values (e.g., by aggressiveness)
        and computes ICC across replicates per archetype.

        Parameters
        ----------
        vignette_id : str, optional
            Filter to specific vignette.
        governed : bool, optional
            Filter to governed or ungoverned.
        action_ordinal_map : dict, optional
            Custom action→ordinal mapping.  If not provided, actions
            are mapped alphabetically (1, 2, 3, ...).

        Returns
        -------
        ICCResult
        """
        df = self.responses_to_dataframe()
        if df.empty:
            return ICCResult(construct="decision", icc_value=0.0)

        if vignette_id:
            df = df[df["vignette_id"] == vignette_id]
        if governed is not None:
            df = df[df["governed"] == governed]

        if "decision" not in df.columns or df.empty:
            return ICCResult(construct="decision", icc_value=0.0)

        # Build ordinal mapping
        if action_ordinal_map is None:
            unique_actions = sorted(df["decision"].dropna().unique())
            action_ordinal_map = {
                a: i + 1 for i, a in enumerate(unique_actions)
            }

        # Map decisions to ordinals
        df = df.copy()
        df["decision_ordinal"] = df["decision"].map(
            lambda x: action_ordinal_map.get(x, 0)
        )

        # Build rating matrix: archetypes x replicates
        archetypes = sorted(df["archetype"].unique())
        max_rep = int(df["replicate"].max()) if not df.empty else 0

        matrix = np.full((len(archetypes), max_rep), np.nan)
        for i, arch in enumerate(archetypes):
            arch_df = df[df["archetype"] == arch].sort_values("replicate")
            for _, row in arch_df.iterrows():
                rep = int(row["replicate"]) - 1
                if 0 <= rep < max_rep:
                    matrix[i, rep] = row["decision_ordinal"]

        valid_cols = ~np.any(np.isnan(matrix), axis=0)
        matrix = matrix[:, valid_cols]

        if matrix.shape[0] < 2 or matrix.shape[1] < 2:
            return ICCResult(
                construct="decision", icc_value=0.0,
                n_subjects=matrix.shape[0], n_raters=matrix.shape[1],
            )

        return compute_icc_2_1(matrix, construct_name="decision")

    def compute_reasoning_consistency(
        self,
        vignette_id: Optional[str] = None,
        governed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Compute reasoning consistency across replicates (keyword overlap).

        For each archetype-vignette pair, measures how similar the
        reasoning text is across replicates using Jaccard keyword overlap.

        Parameters
        ----------
        vignette_id : str, optional
            Filter to specific vignette.
        governed : bool, optional
            Filter to governed or ungoverned.

        Returns
        -------
        dict
            mean_consistency: Average pairwise Jaccard similarity.
            per_archetype: Per-archetype mean consistency.
            n_pairs: Total pairs compared.
        """
        responses = [r for r in self._responses if r.reasoning]
        if vignette_id:
            responses = [r for r in responses if r.vignette_id == vignette_id]
        if governed is not None:
            responses = [r for r in responses if r.governed == governed]

        if not responses:
            return {
                "mean_consistency": 0.0,
                "per_archetype": {},
                "n_pairs": 0,
            }

        # Group by (vignette, archetype)
        from collections import defaultdict
        groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for r in responses:
            groups[(r.vignette_id, r.archetype)].append(r.reasoning)

        all_similarities: List[float] = []
        per_archetype: Dict[str, List[float]] = defaultdict(list)

        for (vid, arch), texts in groups.items():
            if len(texts) < 2:
                continue

            # Keyword extraction (simple word-level)
            token_sets = [
                set(t.lower().split()) for t in texts
            ]

            # Pairwise Jaccard
            for i in range(len(token_sets)):
                for j in range(i + 1, len(token_sets)):
                    intersection = len(token_sets[i] & token_sets[j])
                    union = len(token_sets[i] | token_sets[j])
                    sim = intersection / union if union > 0 else 0.0
                    all_similarities.append(sim)
                    per_archetype[arch].append(sim)

        mean_consistency = (
            float(np.mean(all_similarities)) if all_similarities else 0.0
        )

        archetype_means = {
            arch: round(float(np.mean(sims)), 4)
            for arch, sims in per_archetype.items()
        }

        return {
            "mean_consistency": round(mean_consistency, 4),
            "per_archetype": archetype_means,
            "n_pairs": len(all_similarities),
        }

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def compute_full_report(
        self,
        governed: Optional[bool] = None,
    ) -> BatteryReport:
        """Compute complete psychometric battery report.

        Parameters
        ----------
        governed : bool, optional
            Filter to governed or ungoverned responses.

        Returns
        -------
        BatteryReport
        """
        report = BatteryReport()
        report.n_total_probes = len([
            r for r in self._responses
            if governed is None or r.governed == governed
        ])

        # Per-vignette reports
        for vid, vignette in self.vignettes.items():
            tp_icc = self.compute_icc(vignette_id=vid, construct="tp",
                                      governed=governed)
            cp_icc = self.compute_icc(vignette_id=vid, construct="cp",
                                      governed=governed)
            agreement = self.compute_decision_agreement(
                vignette_id=vid, governed=governed
            )
            coh, incoh = self.evaluate_coherence(vid, governed=governed)

            report.vignette_reports.append(VignetteReport(
                vignette_id=vid,
                severity=vignette.severity,
                n_responses=len([
                    r for r in self._responses
                    if r.vignette_id == vid
                    and (governed is None or r.governed == governed)
                ]),
                tp_icc=tp_icc,
                cp_icc=cp_icc,
                decision_agreement=agreement,
                coherence_rate=coh,
                incoherence_rate=incoh,
            ))

        # Overall ICC (across all vignettes)
        report.overall_tp_icc = self.compute_icc(
            construct="tp", governed=governed
        )
        report.overall_cp_icc = self.compute_icc(
            construct="cp", governed=governed
        )

        # Internal consistency
        report.consistency = self.compute_consistency(governed=governed)

        return report

    def compute_governance_effect(self) -> Dict[str, Any]:
        """Compare governed vs ungoverned probe responses.

        Computes paired statistics for P2 experiment.

        Returns
        -------
        dict with keys:
            cacr_governed, cacr_ungoverned: Coherence rates.
            tp_icc_governed, tp_icc_ungoverned: ICC values.
            mann_whitney_u: Test statistic for TP ordinal comparison.
            p_value: p-value for the comparison.
        """
        gov_report = self.compute_full_report(governed=True)
        ungov_report = self.compute_full_report(governed=False)

        result: Dict[str, Any] = {
            "tp_icc_governed": (
                gov_report.overall_tp_icc.icc_value
                if gov_report.overall_tp_icc else 0.0
            ),
            "tp_icc_ungoverned": (
                ungov_report.overall_tp_icc.icc_value
                if ungov_report.overall_tp_icc else 0.0
            ),
            "n_governed": gov_report.n_total_probes,
            "n_ungoverned": ungov_report.n_total_probes,
        }

        # Mann-Whitney U on TP ordinals
        df = self.responses_to_dataframe()
        gov_tp = df[df["governed"] == True]["tp_ordinal"].values
        ungov_tp = df[df["governed"] == False]["tp_ordinal"].values

        if len(gov_tp) >= 2 and len(ungov_tp) >= 2:
            try:
                from scipy import stats as sp_stats
                u_stat, p_val = sp_stats.mannwhitneyu(
                    gov_tp, ungov_tp, alternative="two-sided"
                )
                # Rank-biserial r (effect size)
                n1, n2 = len(gov_tp), len(ungov_tp)
                r_rb = 1 - (2 * u_stat) / (n1 * n2)

                result["mann_whitney_u"] = float(u_stat)
                result["p_value"] = float(p_val)
                result["rank_biserial_r"] = float(r_rb)
            except ImportError:
                pass

        return result
