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

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Re-export types and stats for backward compatibility
from .psychometric_types import (  # noqa: F401
    VIGNETTE_DIR,
    LABEL_TO_ORDINAL,
    Vignette,
    ProbeResponse,
    ICCResult,
    ConsistencyResult,
    VignetteReport,
    EffectSizeResult,
    ConvergentValidityResult,
    BatteryReport,
)
from .psychometric_stats import (  # noqa: F401
    compute_icc_2_1,
    compute_cronbach_alpha,
    compute_fleiss_kappa,
)


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
        Directory containing vignette YAML files.  If ``None``,
        ``load_vignettes()`` returns an empty list.  Callers performing
        ICC probing must provide a domain-specific vignette directory.
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
        if self._vignette_dir is None:
            return []
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
            Filter to specific vignette (None = all).  When ``None`` and
            multiple vignettes are present, subjects are compound
            (archetype x vignette) pairs so that replicate slots do not
            collide across vignettes.
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
        if ordinal_col not in df.columns or df.empty:
            return ICCResult(construct=construct, icc_value=0.0)

        # Determine subject key: single vignette -> archetype only,
        # multiple vignettes -> (archetype, vignette_id) compound key
        # to avoid replicate-slot collisions.
        n_vignettes = df["vignette_id"].nunique()
        if n_vignettes > 1 and not vignette_id:
            df = df.copy()
            df["_subject"] = df["archetype"] + "|" + df["vignette_id"]
        else:
            df = df.copy()
            df["_subject"] = df["archetype"]

        subjects = sorted(df["_subject"].unique())
        max_rep = int(df["replicate"].max())

        # Pivot to matrix form: subjects x replicates
        matrix = np.full((len(subjects), max_rep), np.nan)
        for i, subj in enumerate(subjects):
            subj_df = df[df["_subject"] == subj].sort_values("replicate")
            for _, row in subj_df.iterrows():
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
        """Compute Fleiss' kappa for action agreement across replicates."""
        df = self.responses_to_dataframe()
        if df.empty:
            return 0.0

        if vignette_id:
            df = df[df["vignette_id"] == vignette_id]
        if governed is not None:
            df = df[df["governed"] == governed]

        decision_lists = []
        for arch, arch_df in df.groupby("archetype"):
            decisions = arch_df.sort_values("replicate")["decision"].tolist()
            if len(decisions) >= 2:
                decision_lists.append(decisions)

        if not decision_lists:
            return 0.0
        max_len = max(len(d) for d in decision_lists)
        padded = [
            d + [d[-1]] * (max_len - len(d))
            for d in decision_lists
        ]

        return compute_fleiss_kappa(padded)

    def evaluate_coherence(
        self,
        vignette_id: str,
        governed: Optional[bool] = None,
    ) -> Tuple[float, float]:
        """Evaluate response coherence against vignette expectations.

        Returns
        -------
        (coherence_rate, incoherence_rate)
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
            tp_expected = expected.get("TP_LABEL", {})
            tp_incoherent = tp_expected.get("incoherent", [])
            if row["tp_label"] in tp_incoherent:
                n_incoherent += 1
                continue

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
        """Compute ICC on decision choices (construct-free)."""
        df = self.responses_to_dataframe()
        if df.empty:
            return ICCResult(construct="decision", icc_value=0.0)

        if vignette_id:
            df = df[df["vignette_id"] == vignette_id]
        if governed is not None:
            df = df[df["governed"] == governed]

        if "decision" not in df.columns or df.empty:
            return ICCResult(construct="decision", icc_value=0.0)

        if action_ordinal_map is None:
            unique_actions = sorted(df["decision"].dropna().unique())
            action_ordinal_map = {
                a: i + 1 for i, a in enumerate(unique_actions)
            }

        df = df.copy()
        df["decision_ordinal"] = df["decision"].map(
            lambda x: action_ordinal_map.get(x, 0)
        )

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
        """Compute reasoning consistency across replicates (Jaccard overlap)."""
        responses = [r for r in self._responses if r.reasoning]
        if vignette_id:
            responses = [r for r in responses if r.vignette_id == vignette_id]
        if governed is not None:
            responses = [r for r in responses if r.governed == governed]

        if not responses:
            return {"mean_consistency": 0.0, "per_archetype": {}, "n_pairs": 0}

        groups: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for r in responses:
            groups[(r.vignette_id, r.archetype)].append(r.reasoning)

        all_similarities: List[float] = []
        per_archetype: Dict[str, List[float]] = defaultdict(list)

        for (vid, arch), texts in groups.items():
            if len(texts) < 2:
                continue

            token_sets = [set(t.lower().split()) for t in texts]

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
    # Effect size and validity (R3-D)
    # ------------------------------------------------------------------

    def compute_effect_size(
        self,
        construct: str = "tp",
        governed: Optional[bool] = None,
    ) -> EffectSizeResult:
        """Compute eta-squared (between-archetype effect size)."""
        df = self.responses_to_dataframe()
        if df.empty:
            return EffectSizeResult(construct=construct, eta_squared=0.0)

        if governed is not None:
            df = df[df["governed"] == governed]

        ordinal_col = f"{construct}_ordinal"
        if ordinal_col not in df.columns or df.empty:
            return EffectSizeResult(construct=construct, eta_squared=0.0)

        groups = [g[ordinal_col].values for _, g in df.groupby("archetype")]
        groups = [g for g in groups if len(g) > 0]

        if len(groups) < 2:
            return EffectSizeResult(construct=construct, eta_squared=0.0)

        all_vals = np.concatenate(groups)
        grand_mean = np.mean(all_vals)
        n_total = len(all_vals)

        ss_total = np.sum((all_vals - grand_mean) ** 2)
        ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
        ss_within = ss_total - ss_between

        k = len(groups)
        df_between = k - 1
        df_within = n_total - k

        if df_within <= 0 or ss_within <= 0:
            eta_sq = 1.0 if ss_between > 0 else 0.0
            return EffectSizeResult(
                construct=construct, eta_squared=eta_sq,
                ss_between=float(ss_between), ss_total=float(ss_total),
            )

        ms_between = ss_between / df_between
        ms_within = ss_within / df_within
        f_val = ms_between / ms_within

        try:
            from scipy import stats as sp_stats
            p_val = 1 - sp_stats.f.cdf(f_val, df_between, df_within)
        except ImportError:
            p_val = 1.0

        eta_sq = ss_between / ss_total if ss_total > 0 else 0.0

        return EffectSizeResult(
            construct=construct,
            eta_squared=float(eta_sq),
            ss_between=float(ss_between),
            ss_total=float(ss_total),
            f_value=float(f_val),
            p_value=float(p_val),
        )

    def compute_convergent_validity(
        self,
        governed: Optional[bool] = None,
    ) -> ConvergentValidityResult:
        """Compute convergent validity: TP ordinal vs vignette severity."""
        severity_ordinal = {"low": 1, "medium": 2, "high": 3, "extreme": 4}

        df = self.responses_to_dataframe()
        if df.empty:
            return ConvergentValidityResult(
                construct="tp", criterion="vignette_severity",
                spearman_rho=0.0,
            )

        if governed is not None:
            df = df[df["governed"] == governed]

        vig_severity = {}
        for vid, vig in self._vignettes.items():
            vig_severity[vid] = severity_ordinal.get(vig.severity, 2)

        df = df.copy()
        df["severity_ordinal"] = df["vignette_id"].map(vig_severity)
        df = df.dropna(subset=["severity_ordinal", "tp_ordinal"])

        if len(df) < 3:
            return ConvergentValidityResult(
                construct="tp", criterion="vignette_severity",
                spearman_rho=0.0, n_observations=len(df),
            )

        try:
            from scipy import stats as sp_stats
            rho, p_val = sp_stats.spearmanr(
                df["severity_ordinal"].values,
                df["tp_ordinal"].values,
            )
        except ImportError:
            rho = float(np.corrcoef(
                df["severity_ordinal"].values,
                df["tp_ordinal"].values,
            )[0, 1])
            p_val = 1.0

        return ConvergentValidityResult(
            construct="tp",
            criterion="vignette_severity",
            spearman_rho=float(rho) if not np.isnan(rho) else 0.0,
            p_value=float(p_val) if not np.isnan(p_val) else 1.0,
            n_observations=len(df),
        )

    def compute_discriminant(
        self,
        governed: Optional[bool] = None,
    ) -> float:
        """Compute TP-CP discriminant correlation."""
        df = self.responses_to_dataframe()
        if df.empty:
            return 0.0

        if governed is not None:
            df = df[df["governed"] == governed]

        tp = df["tp_ordinal"].values.astype(float)
        cp = df["cp_ordinal"].values.astype(float)

        if len(tp) < 3:
            return 0.0

        corr = np.corrcoef(tp, cp)
        r = float(corr[0, 1]) if not np.isnan(corr[0, 1]) else 0.0
        return r

    # ------------------------------------------------------------------
    # Full report
    # ------------------------------------------------------------------

    def compute_full_report(
        self,
        governed: Optional[bool] = None,
    ) -> BatteryReport:
        """Compute complete psychometric battery report."""
        report = BatteryReport()
        report.n_total_probes = len([
            r for r in self._responses
            if governed is None or r.governed == governed
        ])

        for vid, vignette in self.vignettes.items():
            n_resp = len([
                r for r in self._responses
                if r.vignette_id == vid
                and (governed is None or r.governed == governed)
            ])
            if n_resp == 0:
                continue

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
                n_responses=n_resp,
                tp_icc=tp_icc,
                cp_icc=cp_icc,
                decision_agreement=agreement,
                coherence_rate=coh,
                incoherence_rate=incoh,
            ))

        report.overall_tp_icc = self.compute_icc(
            construct="tp", governed=governed
        )
        report.overall_cp_icc = self.compute_icc(
            construct="cp", governed=governed
        )
        report.consistency = self.compute_consistency(governed=governed)
        report.tp_effect_size = self.compute_effect_size(
            construct="tp", governed=governed
        )
        report.cp_effect_size = self.compute_effect_size(
            construct="cp", governed=governed
        )
        report.convergent_validity = self.compute_convergent_validity(
            governed=governed
        )
        report.tp_cp_discriminant = self.compute_discriminant(governed=governed)

        return report

    def compute_governance_effect(self) -> Dict[str, Any]:
        """Compare governed vs ungoverned probe responses."""
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

        df = self.responses_to_dataframe()
        gov_tp = df[df["governed"] == True]["tp_ordinal"].values  # noqa: E712
        ungov_tp = df[df["governed"] == False]["tp_ordinal"].values  # noqa: E712

        if len(gov_tp) >= 2 and len(ungov_tp) >= 2:
            try:
                from scipy import stats as sp_stats
                u_stat, p_val = sp_stats.mannwhitneyu(
                    gov_tp, ungov_tp, alternative="two-sided"
                )
                n1, n2 = len(gov_tp), len(ungov_tp)
                r_rb = 1 - (2 * u_stat) / (n1 * n2)

                result["mann_whitney_u"] = float(u_stat)
                result["p_value"] = float(p_val)
                result["rank_biserial_r"] = float(r_rb)
            except ImportError:
                pass

        return result
