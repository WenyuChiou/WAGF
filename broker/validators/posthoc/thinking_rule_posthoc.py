"""
Post-hoc thinking-rule verification (V1/V2/V3).

Applies the same verification rules as the runtime ThinkingValidator
but on already-classified trace DataFrames.  This enables fair
cross-group comparison:

    Group A:  free text → KeywordClassifier → ta/ca_level → V1/V2/V3
    Group B/C: structured TP/CP labels      → ta/ca_level → V1/V2/V3

The three rules mirror ``ThinkingValidator`` built-in PMT checks:

    V1 (relocation_threat_low)   Relocated under low TP  → hallucination
    V2 (elevation_threat_low)    Elevated under low TP   → hallucination
    V3 (extreme_threat_block)    Do-nothing under VH TP  → hallucination
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import pandas as pd


@dataclass
class RuleResult:
    """Result of applying a single verification rule to a DataFrame."""
    rule_id: str
    description: str
    count: int
    mask: Optional[pd.Series] = field(default=None, repr=False)


class ThinkingRulePostHoc:
    """Apply V1/V2/V3 verification rules to classified trace DataFrames.

    Parameters
    ----------
    low_threat_levels : set, optional
        TP levels considered "low" for V1/V2 (default: ``{"L", "VL"}``).
    low_threat_levels_group_a : set, optional
        TP levels for Group A V1/V2 (default: ``{"L", "VL", "M"}``).
        Group A uses keyword-inferred labels with lower confidence,
        so "M" is included as cautious threshold.
    extreme_threat_levels : set, optional
        TP levels considered "extreme" for V3 (default: ``{"VH"}``).
    """

    def __init__(
        self,
        low_threat_levels: Optional[Set[str]] = None,
        low_threat_levels_group_a: Optional[Set[str]] = None,
        extreme_threat_levels: Optional[Set[str]] = None,
    ):
        self.low_tp = low_threat_levels or {"L", "VL"}
        self.low_tp_a = low_threat_levels_group_a or {"L", "VL", "M"}
        self.extreme_tp = extreme_threat_levels or {"VH"}

    def apply(
        self,
        df: pd.DataFrame,
        group: str = "B",
        decision_col: str = "yearly_decision",
        ta_level_col: str = "ta_level",
    ) -> List[RuleResult]:
        """Apply all verification rules.

        Parameters
        ----------
        df : DataFrame
            Must have columns: agent_id, year, relocated, elevated,
            *decision_col*, *ta_level_col*.
        group : str
            ``"A"`` uses relaxed low-threat threshold; ``"B"``/``"C"`` use strict.
        decision_col : str
            Column with the decision (e.g. ``"yearly_decision"``).
        ta_level_col : str
            Column with classified threat level.

        Returns
        -------
        List[RuleResult]
        """
        df_sorted = df.sort_values(["agent_id", "year"]).copy()
        df_sorted["relocated_prev"] = (
            df_sorted.groupby("agent_id")["relocated"].shift(1).fillna(False).infer_objects(copy=False)
        )
        df_sorted["elevated_prev"] = (
            df_sorted.groupby("agent_id")["elevated"].shift(1).fillna(False).infer_objects(copy=False)
        )

        low_set = self.low_tp_a if group.upper() == "A" else self.low_tp

        results = []

        # V1: Relocation transition under low threat
        v1_mask = (
            (df_sorted["relocated"] == True)
            & (df_sorted["relocated_prev"] == False)
            & df_sorted[ta_level_col].isin(low_set)
        )
        results.append(RuleResult(
            rule_id="V1_relocation_threat_low",
            description="Relocated under low threat perception",
            count=int(v1_mask.sum()),
            mask=v1_mask,
        ))

        # V2: Elevation transition under low threat
        v2_mask = (
            (df_sorted["elevated"] == True)
            & (df_sorted["elevated_prev"] == False)
            & df_sorted[ta_level_col].isin(low_set)
        )
        results.append(RuleResult(
            rule_id="V2_elevation_threat_low",
            description="Elevated under low threat perception",
            count=int(v2_mask.sum()),
            mask=v2_mask,
        ))

        # V3: Do-nothing under extreme threat
        def _is_do_nothing(d):
            d_str = str(d).lower()
            return any(x in d_str for x in ["do nothing", "do_nothing", "nothing", "no action"])

        v3_extreme = df_sorted[df_sorted[ta_level_col].isin(self.extreme_tp)]
        if len(v3_extreme) > 0:
            v3_mask_local = v3_extreme[decision_col].apply(_is_do_nothing)
            v3_count = int(v3_mask_local.sum())
        else:
            v3_count = 0
            v3_mask_local = pd.Series(dtype=bool)

        results.append(RuleResult(
            rule_id="V3_extreme_threat_block",
            description="Do-nothing under VH threat perception",
            count=v3_count,
            mask=v3_mask_local,
        ))

        return results

    def total_violations(self, results: List[RuleResult]) -> int:
        """Sum violations across all rules."""
        return sum(r.count for r in results)

    def summary_dict(self, results: List[RuleResult]) -> Dict[str, int]:
        """Return {rule_id: count} dict."""
        return {r.rule_id: r.count for r in results}
