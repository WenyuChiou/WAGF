"""
Level 1 — MICRO Validation: Individual Agent Reasoning Coherence.

Metrics:
    CACR (Construct-Action Coherence Rate):
        Fraction of agent-year observations where the chosen action is
        coherent with the agent's reported psychological constructs.
        Wraps ``PMTFramework.validate_action_coherence()`` for batch
        post-hoc computation.

    EGS (Evidence Grounding Score):
        Fraction of reasoning traces that reference factual information
        from the agent's context window (flood depth, income, prior
        experience, etc.).  Adapted from SeekBench (2025) epistemic
        competence framework.

    TCS (Temporal Consistency Score):
        Imported from ``temporal_coherence.py`` — measures absence of
        impossible construct transitions between years.

References:
    Grimm et al. (2005) — Pattern-oriented validation at micro level
    SeekBench (2025) — Evidence-grounded reasoning evaluation
    Huang et al. (2025) — LLM psychometric measurement (Nature MI)

Part of SAGE C&V Framework (feature/calibration-validation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from broker.core.psychometric import (
    PsychologicalFramework,
    PMTFramework,
    ValidationResult,
    get_framework,
)
from broker.validators.posthoc.keyword_classifier import KeywordClassifier


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CACRResult:
    """Construct-Action Coherence Rate for a single observation.

    Attributes:
        agent_id: Agent identifier.
        year: Simulation year.
        coherent: Whether the action matched construct expectations.
        proposed_skill: The action taken.
        appraisals: Construct labels used for validation.
        errors: Error messages from coherence check.
        warnings: Warning messages from coherence check.
        rule_violations: IDs of violated rules.
    """
    agent_id: str
    year: int
    coherent: bool
    proposed_skill: str
    appraisals: Dict[str, str]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rule_violations: List[str] = field(default_factory=list)


@dataclass
class EGSResult:
    """Evidence Grounding Score for a single reasoning trace.

    Attributes:
        agent_id: Agent identifier.
        year: Simulation year.
        grounded: Whether the reasoning references context-window facts.
        evidence_count: Number of context facts referenced.
        total_context_facts: Number of facts available in context window.
        score: evidence_count / total_context_facts (0-1).
        matched_keywords: Context keywords found in reasoning.
    """
    agent_id: str
    year: int
    grounded: bool
    evidence_count: int
    total_context_facts: int
    score: float
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class TCSResult:
    """Temporal Consistency Score placeholder — see temporal_coherence.py."""
    agent_id: str
    score: float
    impossible_transitions: int
    total_transitions: int


@dataclass
class BRCResult:
    """Behavioral Reference Concordance result.

    Attributes:
        brc: Overall BRC (fraction of observations concordant with
            the traditional ABM's expected action set).
        concordant: Number of concordant observations.
        total: Total observations evaluated.
        brc_by_year: Per-year BRC values.
        brc_by_agent_type: Per-agent-type BRC (for MA).
    """
    brc: float
    concordant: int = 0
    total: int = 0
    brc_by_year: Dict[int, float] = field(default_factory=dict)
    brc_by_agent_type: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "brc": self.brc,
            "concordant": self.concordant,
            "total": self.total,
            "brc_by_year": self.brc_by_year,
            "brc_by_agent_type": self.brc_by_agent_type,
        }


@dataclass
class MicroReport:
    """Aggregated Level-1 micro validation report.

    Attributes:
        cacr: Overall CACR (fraction coherent).
        cacr_by_year: Per-year CACR values.
        cacr_by_agent_type: Per-agent-type CACR (for MA).
        brc: Behavioral Reference Concordance result.
        egs: Overall EGS (mean evidence grounding score).
        egs_by_year: Per-year EGS values.
        tcs: Overall TCS (fraction of agents with no impossible transitions).
        n_observations: Total agent-year observations evaluated.
        cacr_results: Per-observation CACR details.
        egs_results: Per-observation EGS details.
    """
    cacr: float
    cacr_by_year: Dict[int, float] = field(default_factory=dict)
    cacr_by_agent_type: Dict[str, float] = field(default_factory=dict)
    brc: Optional[BRCResult] = None
    egs: float = 0.0
    egs_by_year: Dict[int, float] = field(default_factory=dict)
    tcs: float = 0.0
    n_observations: int = 0
    cacr_results: List[CACRResult] = field(default_factory=list)
    egs_results: List[EGSResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for reporting."""
        d = {
            "cacr": self.cacr,
            "cacr_by_year": self.cacr_by_year,
            "cacr_by_agent_type": self.cacr_by_agent_type,
            "egs": self.egs,
            "egs_by_year": self.egs_by_year,
            "tcs": self.tcs,
            "n_observations": self.n_observations,
        }
        if self.brc:
            d["brc"] = self.brc.to_dict()
        return d


# ---------------------------------------------------------------------------
# CACR computation
# ---------------------------------------------------------------------------

class MicroValidator:
    """Level 1 micro-validation: CACR + EGS for trace DataFrames.

    Wraps ``PsychologicalFramework.validate_action_coherence()`` for batch
    post-hoc evaluation of simulation trace CSVs.

    Parameters
    ----------
    framework : str or PsychologicalFramework
        Framework name (``"pmt"``, ``"utility"``, ``"financial"``) or
        pre-instantiated framework object.
    classifier : KeywordClassifier, optional
        For classifying free-text appraisals (Group A).  Not needed if
        the DataFrame already has label columns.
    ta_col : str
        Column name for threat/primary appraisal (raw text or label).
    ca_col : str
        Column name for coping/secondary appraisal (raw text or label).
    decision_col : str
        Column name for the chosen action.
    context_keywords : list[str], optional
        Domain-specific keywords for EGS evidence grounding.
        Default: flood-domain keywords.
    """

    # Default context keywords for flood domain EGS
    DEFAULT_FLOOD_KEYWORDS: List[str] = [
        "flood depth", "flood level", "water level", "inundation",
        "income", "savings", "mortgage", "property value",
        "elevation cost", "insurance premium", "deductible",
        "neighbor", "community", "FEMA", "NFIP",
        "previous flood", "flood experience", "prior experience",
        "year", "annual", "decade",
        "damage", "loss", "recovery",
    ]

    DEFAULT_IRRIGATION_KEYWORDS: List[str] = [
        "water supply", "allocation", "curtailment", "shortage",
        "drought", "streamflow", "reservoir", "lake mead", "lake powell",
        "compact", "water right", "acre-feet",
        "crop", "yield", "acreage", "irrigation efficiency",
        "neighbor", "upstream", "downstream", "basin",
        "price", "revenue", "cost", "subsidy",
    ]

    def __init__(
        self,
        framework: str | PsychologicalFramework = "pmt",
        classifier: Optional[KeywordClassifier] = None,
        ta_col: str = "threat_appraisal",
        ca_col: str = "coping_appraisal",
        decision_col: str = "yearly_decision",
        context_keywords: Optional[List[str]] = None,
    ):
        if isinstance(framework, str):
            self._framework = get_framework(framework)
        else:
            self._framework = framework

        self._classifier = classifier or KeywordClassifier()
        self._ta_col = ta_col
        self._ca_col = ca_col
        self._decision_col = decision_col
        self._context_keywords = context_keywords or self.DEFAULT_FLOOD_KEYWORDS

    # ------------------------------------------------------------------
    # CACR: Construct-Action Coherence Rate
    # ------------------------------------------------------------------

    def compute_cacr(
        self,
        df: pd.DataFrame,
        start_year: int = 1,
        agent_type_col: Optional[str] = None,
    ) -> MicroReport:
        """Compute CACR across all agent-year observations.

        Parameters
        ----------
        df : DataFrame
            Simulation log with agent_id, year, decision, and appraisal
            columns (either raw text or pre-classified labels).
        start_year : int
            First year to include (default 1).
        agent_type_col : str, optional
            Column identifying agent type (for MA decomposition).

        Returns
        -------
        MicroReport
            With cacr, cacr_by_year, cacr_by_agent_type, and per-row details.
        """
        df = df[df["year"] >= start_year].copy()

        # Ensure we have label columns
        if "ta_level" not in df.columns:
            if self._ta_col in df.columns and self._ca_col in df.columns:
                df = self._classifier.classify_dataframe(
                    df, self._ta_col, self._ca_col
                )
            else:
                df["ta_level"] = "M"
                df["ca_level"] = "M"

        results: List[CACRResult] = []

        for _, row in df.iterrows():
            appraisals = self._extract_appraisals(row)
            skill = str(row.get(self._decision_col, "")).strip().lower()

            vr = self._framework.validate_action_coherence(appraisals, skill)

            results.append(CACRResult(
                agent_id=str(row["agent_id"]),
                year=int(row["year"]),
                coherent=vr.valid,
                proposed_skill=skill,
                appraisals=appraisals,
                errors=vr.errors,
                warnings=vr.warnings,
                rule_violations=vr.rule_violations,
            ))

        # Aggregate
        n = len(results)
        n_coherent = sum(1 for r in results if r.coherent)
        cacr = n_coherent / n if n > 0 else 0.0

        # By year
        cacr_by_year: Dict[int, float] = {}
        year_groups: Dict[int, List[CACRResult]] = {}
        for r in results:
            year_groups.setdefault(r.year, []).append(r)
        for yr, items in sorted(year_groups.items()):
            yr_n = len(items)
            yr_coh = sum(1 for r in items if r.coherent)
            cacr_by_year[yr] = yr_coh / yr_n if yr_n > 0 else 0.0

        # By agent type (MA decomposition)
        cacr_by_type: Dict[str, float] = {}
        if agent_type_col and agent_type_col in df.columns:
            type_groups: Dict[str, List[CACRResult]] = {}
            for r, (_, row) in zip(results, df.iterrows()):
                atype = str(row[agent_type_col])
                type_groups.setdefault(atype, []).append(r)
            for atype, items in type_groups.items():
                t_n = len(items)
                t_coh = sum(1 for r in items if r.coherent)
                cacr_by_type[atype] = t_coh / t_n if t_n > 0 else 0.0

        return MicroReport(
            cacr=cacr,
            cacr_by_year=cacr_by_year,
            cacr_by_agent_type=cacr_by_type,
            n_observations=n,
            cacr_results=results,
        )

    def _extract_appraisals(self, row: pd.Series) -> Dict[str, str]:
        """Extract framework-appropriate appraisals from a DataFrame row."""
        appraisals: Dict[str, str] = {}

        # Map ta_level/ca_level to framework construct keys
        framework_name = self._framework.name.lower()

        if "pmt" in framework_name or "protection" in framework_name:
            appraisals["TP_LABEL"] = str(row.get("ta_level", "M"))
            appraisals["CP_LABEL"] = str(row.get("ca_level", "M"))
            if "sp_level" in row.index:
                appraisals["SP_LABEL"] = str(row["sp_level"])

        elif "utility" in framework_name:
            appraisals["BUDGET_UTIL"] = str(row.get("budget_util", "NEUTRAL"))
            appraisals["EQUITY_GAP"] = str(row.get("equity_gap", "MEDIUM"))

        elif "financial" in framework_name:
            appraisals["LOSS_RATIO"] = str(row.get("loss_ratio", "MEDIUM"))
            appraisals["SOLVENCY"] = str(row.get("solvency", "STABLE"))

        else:
            # Generic dual-appraisal: use ta_level/ca_level as TP/CP
            appraisals["TP_LABEL"] = str(row.get("ta_level", "M"))
            appraisals["CP_LABEL"] = str(row.get("ca_level", "M"))

        return appraisals

    # ------------------------------------------------------------------
    # BRC: Behavioral Reference Concordance
    # ------------------------------------------------------------------

    def compute_brc(
        self,
        df: pd.DataFrame,
        start_year: int = 2,
        agent_type_col: Optional[str] = None,
    ) -> BRCResult:
        """Compute Behavioral Reference Concordance.

        BRC measures the fraction of agent-year observations where the
        LLM's chosen action is in the expected action set predicted by
        the traditional ABM's calibrated model (e.g.,
        ``PMTFramework.get_expected_behavior()``).

        This provides a per-observation L2 metric that works at any
        sample size, unlike distributional tests (KS, chi²) which
        require N >= 200 for adequate statistical power.

        Parameters
        ----------
        df : DataFrame
            Simulation log with agent_id, year, ta/ca columns, and
            decision column.
        start_year : int
            First year to include (default 2).
        agent_type_col : str, optional
            Column for agent-type decomposition.

        Returns
        -------
        BRCResult
            With brc, concordant, total, and per-year/type breakdowns.
        """
        df = df[df["year"] >= start_year].copy()

        # Ensure we have label columns
        if "ta_level" not in df.columns:
            if self._ta_col in df.columns and self._ca_col in df.columns:
                df = self._classifier.classify_dataframe(
                    df, self._ta_col, self._ca_col
                )
            else:
                return BRCResult(brc=0.0)

        concordant = 0
        total = 0
        year_conc: Dict[int, int] = {}
        year_tot: Dict[int, int] = {}
        type_conc: Dict[str, int] = {}
        type_tot: Dict[str, int] = {}

        for _, row in df.iterrows():
            appraisals = self._extract_appraisals(row)
            expected = self._framework.get_expected_behavior(appraisals)
            actual = str(row.get(self._decision_col, "")).strip().lower()
            yr = int(row["year"])

            is_concordant = actual in expected
            if is_concordant:
                concordant += 1
            total += 1

            # Per-year tracking
            year_conc[yr] = year_conc.get(yr, 0) + (1 if is_concordant else 0)
            year_tot[yr] = year_tot.get(yr, 0) + 1

            # Per-agent-type tracking
            if agent_type_col and agent_type_col in row.index:
                atype = str(row[agent_type_col])
                type_conc[atype] = type_conc.get(atype, 0) + (
                    1 if is_concordant else 0
                )
                type_tot[atype] = type_tot.get(atype, 0) + 1

        brc_by_year = {
            yr: year_conc[yr] / year_tot[yr]
            for yr in sorted(year_tot)
            if year_tot[yr] > 0
        }
        brc_by_type = {
            atype: type_conc[atype] / type_tot[atype]
            for atype in sorted(type_tot)
            if type_tot[atype] > 0
        }

        return BRCResult(
            brc=round(concordant / total, 4) if total > 0 else 0.0,
            concordant=concordant,
            total=total,
            brc_by_year=brc_by_year,
            brc_by_agent_type=brc_by_type,
        )

    # ------------------------------------------------------------------
    # EGS: Evidence Grounding Score
    # ------------------------------------------------------------------

    def compute_egs(
        self,
        df: pd.DataFrame,
        reasoning_col: str = "reasoning",
        context_cols: Optional[List[str]] = None,
        start_year: int = 1,
    ) -> List[EGSResult]:
        """Compute Evidence Grounding Score for reasoning traces.

        Checks whether agent reasoning references factual information
        available in its context window.

        Parameters
        ----------
        df : DataFrame
            Must have agent_id, year, and *reasoning_col*.
        reasoning_col : str
            Column containing the agent's reasoning text.
        context_cols : list[str], optional
            Additional columns whose values should appear in reasoning.
            E.g., ``["flood_depth", "income", "prior_flood_count"]``.
        start_year : int
            First year to include.

        Returns
        -------
        list[EGSResult]
            Per-observation evidence grounding details.
        """
        df = df[df["year"] >= start_year].copy()
        results: List[EGSResult] = []

        for _, row in df.iterrows():
            reasoning = str(row.get(reasoning_col, "")).lower()
            if not reasoning or reasoning in ("nan", "none", ""):
                results.append(EGSResult(
                    agent_id=str(row["agent_id"]),
                    year=int(row["year"]),
                    grounded=False,
                    evidence_count=0,
                    total_context_facts=len(self._context_keywords),
                    score=0.0,
                ))
                continue

            # Check domain keywords
            matched = [
                kw for kw in self._context_keywords
                if kw.lower() in reasoning
            ]

            # Check context column values referenced in reasoning
            if context_cols:
                for col in context_cols:
                    if col in row.index:
                        val = str(row[col]).lower()
                        if val and val not in ("nan", "none", "") and val in reasoning:
                            matched.append(f"@{col}={val}")

            total_facts = len(self._context_keywords)
            if context_cols:
                total_facts += len([
                    c for c in context_cols if c in row.index
                ])

            score = len(matched) / total_facts if total_facts > 0 else 0.0

            results.append(EGSResult(
                agent_id=str(row["agent_id"]),
                year=int(row["year"]),
                grounded=len(matched) > 0,
                evidence_count=len(matched),
                total_context_facts=total_facts,
                score=score,
                matched_keywords=matched,
            ))

        return results

    def compute_egs_summary(
        self, egs_results: List[EGSResult]
    ) -> Dict[str, Any]:
        """Aggregate EGS results into summary statistics.

        Returns
        -------
        dict with keys:
            egs_mean: Mean evidence grounding score.
            egs_grounded_rate: Fraction with at least one grounded reference.
            egs_by_year: Per-year mean EGS.
            n: Total observations.
        """
        if not egs_results:
            return {"egs_mean": 0.0, "egs_grounded_rate": 0.0,
                    "egs_by_year": {}, "n": 0}

        scores = [r.score for r in egs_results]
        grounded = [r.grounded for r in egs_results]

        year_groups: Dict[int, List[float]] = {}
        for r in egs_results:
            year_groups.setdefault(r.year, []).append(r.score)

        egs_by_year = {
            yr: float(np.mean(vals))
            for yr, vals in sorted(year_groups.items())
        }

        return {
            "egs_mean": float(np.mean(scores)),
            "egs_grounded_rate": float(np.mean(grounded)),
            "egs_by_year": egs_by_year,
            "n": len(egs_results),
        }

    # ------------------------------------------------------------------
    # Combined micro report
    # ------------------------------------------------------------------

    def compute_full_report(
        self,
        df: pd.DataFrame,
        reasoning_col: str = "reasoning",
        context_cols: Optional[List[str]] = None,
        start_year: int = 1,
        agent_type_col: Optional[str] = None,
    ) -> MicroReport:
        """Compute full Level-1 micro validation report (CACR + EGS).

        Parameters
        ----------
        df : DataFrame
            Simulation log with all required columns.
        reasoning_col : str
            Column with agent reasoning text (for EGS).
        context_cols : list[str], optional
            Context columns for EGS cross-referencing.
        start_year : int
            First year to include.
        agent_type_col : str, optional
            Column for MA agent-type decomposition.

        Returns
        -------
        MicroReport
            Complete Level-1 report with CACR and EGS.
        """
        report = self.compute_cacr(
            df, start_year=start_year, agent_type_col=agent_type_col
        )

        if reasoning_col in df.columns:
            egs_results = self.compute_egs(
                df,
                reasoning_col=reasoning_col,
                context_cols=context_cols,
                start_year=start_year,
            )
            egs_summary = self.compute_egs_summary(egs_results)
            report.egs = egs_summary["egs_mean"]
            report.egs_by_year = egs_summary["egs_by_year"]
            report.egs_results = egs_results

        return report
