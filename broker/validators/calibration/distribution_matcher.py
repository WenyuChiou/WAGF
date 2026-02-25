"""
Level 2 — MACRO Calibration: Population-Level Distribution Matching.

Statistical tests comparing simulated behavioral distributions against
empirical reference data (FEMA NFIP rates, PMT survey baselines, etc.).

Metrics:
    KS test:           CDF match between simulated and reference distributions
    Wasserstein:       Earth-mover distance for continuous distributions
    Chi-squared GoF:   Categorical action distribution match
    PEBA features:     Distribution shape (mean, var, skew, kurtosis)

References:
    Thiele et al. (2014) — PEBA: Pattern-Extraction-Based ABM calibration
    Windrum et al. (2007) — Empirical validation survey for ABMs
    Bubeck et al. (2012) — Flood adaptation empirical baseline data

Part of WAGF C&V Framework (feature/calibration-validation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    from scipy import stats as sp_stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DistributionTestResult:
    """Result of a single statistical test.

    Attributes:
        test_name: Name of the statistical test.
        statistic: Test statistic value.
        p_value: p-value (None for distance metrics without null hypothesis).
        significant: Whether the test is significant at the given alpha.
        alpha: Significance level used.
        effect_size: Optional effect size measure.
        details: Additional test-specific information.
    """
    test_name: str
    statistic: float
    p_value: Optional[float] = None
    significant: Optional[bool] = None
    alpha: float = 0.05
    effect_size: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "test_name": self.test_name,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "significant": self.significant,
            "alpha": self.alpha,
        }
        if self.effect_size is not None:
            d["effect_size"] = self.effect_size
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class PEBAFeatures:
    """PEBA distributional features for a time series.

    Attributes:
        mean: Mean of the distribution.
        variance: Variance.
        skewness: Skewness (Fisher).
        kurtosis: Excess kurtosis (Fisher).
        n: Sample size.
        label: Identifier for this feature set.
    """
    mean: float
    variance: float
    skewness: float
    kurtosis: float
    n: int
    label: str = ""

    def to_dict(self) -> Dict[str, float]:
        return {
            "mean": self.mean,
            "variance": self.variance,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "n": self.n,
        }

    def distance_to(self, other: PEBAFeatures) -> float:
        """Euclidean distance in (mean, var, skew, kurt) feature space."""
        return float(np.sqrt(
            (self.mean - other.mean) ** 2
            + (self.variance - other.variance) ** 2
            + (self.skewness - other.skewness) ** 2
            + (self.kurtosis - other.kurtosis) ** 2
        ))


@dataclass
class MacroReport:
    """Aggregated Level-2 macro calibration report.

    Attributes:
        ks_results: KS test results per variable.
        wasserstein_results: Wasserstein distance results per variable.
        chi2_results: Chi-squared GoF results per variable.
        peba_simulated: PEBA features from simulation.
        peba_reference: PEBA features from reference data.
        peba_distance: Euclidean distance in PEBA feature space.
        echo_chamber_rate: Fraction of years with echo chamber.
        ebe_decomposition: EBE by agent type (MA).
    """
    ks_results: List[DistributionTestResult] = field(default_factory=list)
    wasserstein_results: List[DistributionTestResult] = field(default_factory=list)
    chi2_results: List[DistributionTestResult] = field(default_factory=list)
    peba_simulated: Optional[PEBAFeatures] = None
    peba_reference: Optional[PEBAFeatures] = None
    peba_distance: Optional[float] = None
    echo_chamber_rate: float = 0.0
    ebe_decomposition: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "ks_results": [r.to_dict() for r in self.ks_results],
            "wasserstein_results": [r.to_dict() for r in self.wasserstein_results],
            "chi2_results": [r.to_dict() for r in self.chi2_results],
            "peba_distance": self.peba_distance,
            "echo_chamber_rate": self.echo_chamber_rate,
            "ebe_decomposition": self.ebe_decomposition,
        }
        if self.peba_simulated:
            d["peba_simulated"] = self.peba_simulated.to_dict()
        if self.peba_reference:
            d["peba_reference"] = self.peba_reference.to_dict()
        return d


# ---------------------------------------------------------------------------
# Distribution Matcher
# ---------------------------------------------------------------------------

class DistributionMatcher:
    """Level 2 macro-calibration: statistical distribution matching.

    All tests are post-hoc and require zero additional LLM calls.

    Parameters
    ----------
    alpha : float
        Significance level for hypothesis tests (default: 0.05).
    echo_threshold : float
        Fraction above which a single dominant action constitutes an
        echo chamber (default: 0.8, matching CrossAgentValidator).
    """

    def __init__(self, alpha: float = 0.05, echo_threshold: float = 0.8):
        self._alpha = alpha
        self._echo_threshold = echo_threshold

    # ------------------------------------------------------------------
    # Kolmogorov-Smirnov test
    # ------------------------------------------------------------------

    def ks_test(
        self,
        simulated: np.ndarray,
        reference: np.ndarray,
        label: str = "",
    ) -> DistributionTestResult:
        """Two-sample KS test comparing simulated vs reference CDFs.

        Parameters
        ----------
        simulated : array-like
            Simulated values (e.g., adoption rates over time).
        reference : array-like
            Empirical reference values.
        label : str
            Variable label for reporting.

        Returns
        -------
        DistributionTestResult
        """
        if not HAS_SCIPY:
            return DistributionTestResult(
                test_name=f"KS_{label}" if label else "KS",
                statistic=float("nan"),
                p_value=float("nan"),
                details={"error": "scipy not available"},
            )

        sim = np.asarray(simulated, dtype=float)
        ref = np.asarray(reference, dtype=float)

        stat, pval = sp_stats.ks_2samp(sim, ref)

        return DistributionTestResult(
            test_name=f"KS_{label}" if label else "KS",
            statistic=float(stat),
            p_value=float(pval),
            significant=pval < self._alpha,
            alpha=self._alpha,
            details={"n_sim": len(sim), "n_ref": len(ref)},
        )

    # ------------------------------------------------------------------
    # Wasserstein distance
    # ------------------------------------------------------------------

    def wasserstein_distance(
        self,
        simulated: np.ndarray,
        reference: np.ndarray,
        label: str = "",
    ) -> DistributionTestResult:
        """Wasserstein-1 (earth mover) distance between distributions.

        Parameters
        ----------
        simulated, reference : array-like
            Sample arrays.
        label : str
            Variable label.

        Returns
        -------
        DistributionTestResult
            statistic = Wasserstein distance (no p-value).
        """
        if not HAS_SCIPY:
            return DistributionTestResult(
                test_name=f"Wasserstein_{label}" if label else "Wasserstein",
                statistic=float("nan"),
                details={"error": "scipy not available"},
            )

        sim = np.asarray(simulated, dtype=float)
        ref = np.asarray(reference, dtype=float)

        w_dist = sp_stats.wasserstein_distance(sim, ref)

        return DistributionTestResult(
            test_name=f"Wasserstein_{label}" if label else "Wasserstein",
            statistic=float(w_dist),
            details={"n_sim": len(sim), "n_ref": len(ref)},
        )

    # ------------------------------------------------------------------
    # Chi-squared goodness of fit
    # ------------------------------------------------------------------

    def chi2_gof(
        self,
        observed_counts: Dict[str, int],
        expected_proportions: Dict[str, float],
        label: str = "",
    ) -> DistributionTestResult:
        """Chi-squared goodness-of-fit test for categorical distributions.

        Parameters
        ----------
        observed_counts : dict
            {category: count} from simulation (e.g., action distribution).
        expected_proportions : dict
            {category: proportion} from reference data.  Must sum to 1.
        label : str
            Variable label.

        Returns
        -------
        DistributionTestResult
        """
        if not HAS_SCIPY:
            return DistributionTestResult(
                test_name=f"Chi2_{label}" if label else "Chi2",
                statistic=float("nan"),
                p_value=float("nan"),
                details={"error": "scipy not available"},
            )

        # Align categories
        all_cats = sorted(set(observed_counts.keys()) | set(expected_proportions.keys()))
        n_total = sum(observed_counts.values())

        if n_total == 0:
            return DistributionTestResult(
                test_name=f"Chi2_{label}" if label else "Chi2",
                statistic=0.0,
                p_value=1.0,
                significant=False,
                alpha=self._alpha,
                details={"error": "no observations"},
            )

        observed = np.array([observed_counts.get(c, 0) for c in all_cats], dtype=float)
        expected = np.array([
            expected_proportions.get(c, 0.0) * n_total for c in all_cats
        ], dtype=float)

        # Avoid zero expected counts
        expected = np.maximum(expected, 0.5)

        stat, pval = sp_stats.chisquare(observed, f_exp=expected)

        return DistributionTestResult(
            test_name=f"Chi2_{label}" if label else "Chi2",
            statistic=float(stat),
            p_value=float(pval),
            significant=pval < self._alpha,
            alpha=self._alpha,
            details={
                "categories": all_cats,
                "observed": observed.tolist(),
                "expected": expected.tolist(),
                "df": len(all_cats) - 1,
            },
        )

    # ------------------------------------------------------------------
    # PEBA features
    # ------------------------------------------------------------------

    def extract_peba_features(
        self,
        values: np.ndarray,
        label: str = "",
    ) -> PEBAFeatures:
        """Extract PEBA distributional features from a sample.

        PEBA (Pattern-Extraction-Based ABM) calibration extracts four
        distributional features: mean, variance, skewness, and kurtosis.

        Reference: Thiele et al. (2014), JASSS 17(3):11.

        Parameters
        ----------
        values : array-like
            Sample values.
        label : str
            Feature set label.

        Returns
        -------
        PEBAFeatures
        """
        vals = np.asarray(values, dtype=float)
        vals = vals[~np.isnan(vals)]
        n = len(vals)

        if n < 4:
            return PEBAFeatures(
                mean=float(np.mean(vals)) if n > 0 else 0.0,
                variance=float(np.var(vals, ddof=1)) if n > 1 else 0.0,
                skewness=0.0,
                kurtosis=0.0,
                n=n,
                label=label,
            )

        if HAS_SCIPY:
            return PEBAFeatures(
                mean=float(np.mean(vals)),
                variance=float(np.var(vals, ddof=1)),
                skewness=float(sp_stats.skew(vals)),
                kurtosis=float(sp_stats.kurtosis(vals)),
                n=n,
                label=label,
            )
        else:
            # Fallback without scipy
            mean = float(np.mean(vals))
            var = float(np.var(vals, ddof=1))
            std = np.sqrt(var) if var > 0 else 1e-12
            skew = float(np.mean(((vals - mean) / std) ** 3))
            kurt = float(np.mean(((vals - mean) / std) ** 4) - 3)
            return PEBAFeatures(
                mean=mean, variance=var, skewness=skew,
                kurtosis=kurt, n=n, label=label,
            )

    def compare_peba(
        self,
        simulated: np.ndarray,
        reference: np.ndarray,
        sim_label: str = "simulated",
        ref_label: str = "reference",
    ) -> Tuple[PEBAFeatures, PEBAFeatures, float]:
        """Compare PEBA features between simulated and reference data.

        Returns
        -------
        (sim_features, ref_features, euclidean_distance)
        """
        sim_f = self.extract_peba_features(simulated, label=sim_label)
        ref_f = self.extract_peba_features(reference, label=ref_label)
        dist = sim_f.distance_to(ref_f)
        return sim_f, ref_f, dist

    # ------------------------------------------------------------------
    # Echo chamber detection
    # ------------------------------------------------------------------

    def compute_echo_chamber_rate(
        self,
        df: pd.DataFrame,
        decision_col: str = "yearly_decision",
    ) -> float:
        """Compute fraction of years with echo chamber (>threshold same action).

        Parameters
        ----------
        df : DataFrame
            Must have year and *decision_col* columns.

        Returns
        -------
        float
            Fraction of years where dominant action exceeds echo threshold.
        """
        echo_years = 0
        total_years = 0

        for year in df["year"].unique():
            yr_df = df[df["year"] == year]
            counts = yr_df[decision_col].value_counts()
            if len(counts) == 0:
                continue
            total_years += 1
            dominant_pct = counts.iloc[0] / counts.sum()
            if dominant_pct > self._echo_threshold:
                echo_years += 1

        return echo_years / total_years if total_years > 0 else 0.0

    # ------------------------------------------------------------------
    # MA-EBE decomposition
    # ------------------------------------------------------------------

    def compute_ebe_decomposition(
        self,
        df: pd.DataFrame,
        agent_type_col: str = "agent_type",
        decision_col: str = "yearly_decision",
        rh_col: Optional[str] = None,
    ) -> Dict[str, float]:
        """Decompose EBE by agent type for multi-agent simulations.

        Computes EBE = H_norm * (1 - R_H) per agent type.

        Parameters
        ----------
        df : DataFrame
            Must have *agent_type_col*, *decision_col*, year.
        rh_col : str, optional
            Column with per-observation hallucination flag (bool).
            If None, R_H defaults to 0 (no hallucination info).

        Returns
        -------
        dict
            {agent_type: ebe_value}
        """
        if agent_type_col not in df.columns:
            return {}

        h_max = np.log2(max(df[decision_col].nunique(), 2))
        result: Dict[str, float] = {}

        for atype, group in df.groupby(agent_type_col):
            counts = group[decision_col].value_counts()
            probs = counts / counts.sum()
            h_raw = float(-np.sum(probs * np.log2(probs + 1e-12)))
            h_norm = h_raw / h_max if h_max > 0 else 0.0

            if rh_col and rh_col in group.columns:
                rh = float(group[rh_col].mean())
            else:
                rh = 0.0

            result[str(atype)] = float(h_norm * (1 - rh))

        return result

    # ------------------------------------------------------------------
    # Full macro report
    # ------------------------------------------------------------------

    def compute_full_report(
        self,
        df: pd.DataFrame,
        reference_data: Optional[Dict[str, Any]] = None,
        decision_col: str = "yearly_decision",
        agent_type_col: str = "agent_type",
        rh_col: Optional[str] = None,
    ) -> MacroReport:
        """Compute complete Level-2 macro calibration report.

        Parameters
        ----------
        df : DataFrame
            Simulation log.
        reference_data : dict, optional
            Reference data for calibration tests.  Expected keys:
            - ``"adoption_rates"``: array of empirical adoption rates
            - ``"action_proportions"``: {action: proportion} dict
            - ``"adoption_timeseries"``: array for PEBA comparison
        decision_col : str
            Decision column name.
        agent_type_col : str
            Agent type column for MA decomposition.
        rh_col : str, optional
            Hallucination flag column.

        Returns
        -------
        MacroReport
        """
        report = MacroReport()

        # Echo chamber rate
        report.echo_chamber_rate = self.compute_echo_chamber_rate(
            df, decision_col=decision_col
        )

        # EBE decomposition
        report.ebe_decomposition = self.compute_ebe_decomposition(
            df, agent_type_col=agent_type_col,
            decision_col=decision_col, rh_col=rh_col,
        )

        if reference_data:
            # KS test on adoption rates
            if "adoption_rates" in reference_data:
                sim_adoption = self._compute_cumulative_adoption(
                    df, decision_col=decision_col
                )
                ref_adoption = np.asarray(reference_data["adoption_rates"])
                report.ks_results.append(
                    self.ks_test(sim_adoption, ref_adoption, label="adoption")
                )
                report.wasserstein_results.append(
                    self.wasserstein_distance(
                        sim_adoption, ref_adoption, label="adoption"
                    )
                )

            # Chi-squared on action proportions
            if "action_proportions" in reference_data:
                obs_counts = df[decision_col].value_counts().to_dict()
                report.chi2_results.append(
                    self.chi2_gof(
                        obs_counts,
                        reference_data["action_proportions"],
                        label="actions",
                    )
                )

            # PEBA comparison
            if "adoption_timeseries" in reference_data:
                sim_ts = self._compute_adoption_timeseries(
                    df, decision_col=decision_col
                )
                ref_ts = np.asarray(reference_data["adoption_timeseries"])
                sim_f, ref_f, dist = self.compare_peba(
                    sim_ts, ref_ts,
                    sim_label="sim_adoption", ref_label="ref_adoption",
                )
                report.peba_simulated = sim_f
                report.peba_reference = ref_f
                report.peba_distance = dist

        return report

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_cumulative_adoption(
        df: pd.DataFrame,
        decision_col: str = "yearly_decision",
        protective_actions: Optional[set] = None,
    ) -> np.ndarray:
        """Compute cumulative protective action adoption rate per year."""
        if protective_actions is None:
            protective_actions = {
                "elevate_house", "buy_insurance", "relocate",
                "buyout_program",
            }

        rates = []
        for year in sorted(df["year"].unique()):
            yr_df = df[df["year"] == year]
            n_total = len(yr_df)
            n_adopt = yr_df[decision_col].isin(protective_actions).sum()
            rates.append(n_adopt / n_total if n_total > 0 else 0.0)

        return np.array(rates, dtype=float)

    @staticmethod
    def _compute_adoption_timeseries(
        df: pd.DataFrame,
        decision_col: str = "yearly_decision",
        protective_actions: Optional[set] = None,
    ) -> np.ndarray:
        """Compute per-year adoption rate as time series for PEBA."""
        return DistributionMatcher._compute_cumulative_adoption(
            df, decision_col, protective_actions
        )
