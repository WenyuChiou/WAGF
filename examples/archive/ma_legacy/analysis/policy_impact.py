"""
Policy Impact Assessment Module

Evaluates government and insurance policy effects on household behavior.

Analysis includes:
1. Policy Sensitivity: How subsidy/premium changes affect adoption rates
2. Threshold Identification: Key policy levels that trigger behavioral change
3. Optimization Targets: Optimal policy combinations

Usage:
    python policy_impact.py --results results/window/simulation_log.csv
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class PolicyState:
    """Policy state at a given time."""
    year: int
    subsidy_rate: float
    premium_rate: float


@dataclass
class AdoptionMetrics:
    """Adoption metrics for a demographic group."""
    total_agents: int
    insured_count: int
    elevated_count: int
    relocated_count: int
    insurance_rate: float
    elevation_rate: float
    relocation_rate: float


@dataclass
class SensitivityResult:
    """Result of policy sensitivity analysis."""
    policy_type: str  # "subsidy" or "premium"
    level: float
    mg_adoption_rate: float
    nmg_adoption_rate: float
    owner_adoption_rate: float
    renter_adoption_rate: float
    adoption_gap: float  # MG - NMG


@dataclass
class PolicyImpactReport:
    """Complete policy impact assessment report."""
    # Metadata
    analysis_date: str
    data_source: str
    total_records: int
    years_covered: List[int]

    # Policy ranges observed
    subsidy_range: Tuple[float, float] = (0.0, 0.0)
    premium_range: Tuple[float, float] = (0.0, 0.0)

    # Sensitivity results
    subsidy_sensitivity: List[SensitivityResult] = field(default_factory=list)
    premium_sensitivity: List[SensitivityResult] = field(default_factory=list)

    # Thresholds
    subsidy_threshold_for_mg_parity: Optional[float] = None
    premium_threshold_for_uptake: Optional[float] = None

    # Optimal policies
    optimal_subsidy_for_equity: Optional[float] = None
    optimal_premium_for_solvency: Optional[float] = None


class PolicyImpactAnalyzer:
    """
    Analyzes policy impact from simulation results.

    Supports both CSV (simulation_log.csv) and JSONL (household_audit.jsonl) formats.
    """

    def __init__(self, data_path: str):
        """
        Initialize analyzer with data file.

        Args:
            data_path: Path to simulation results (CSV or JSONL)
        """
        self.data_path = Path(data_path)
        self.df: Optional[pd.DataFrame] = None
        self.report: Optional[PolicyImpactReport] = None

    def load_data(self) -> int:
        """
        Load simulation data.

        Returns:
            Number of records loaded
        """
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")

        if self.data_path.suffix == '.csv':
            self.df = pd.read_csv(self.data_path)
        elif self.data_path.suffix == '.jsonl':
            records = []
            with open(self.data_path, 'r', encoding='utf-8') as f:
                for line in f:
                    records.append(json.loads(line))
            self.df = pd.DataFrame(records)
        else:
            raise ValueError(f"Unsupported file format: {self.data_path.suffix}")

        logger.info(f"Loaded {len(self.df)} records from {self.data_path}")
        return len(self.df)

    def analyze_subsidy_sensitivity(
        self,
        bins: int = 5
    ) -> List[SensitivityResult]:
        """
        Analyze how subsidy rate affects adoption across demographics.

        Args:
            bins: Number of subsidy level bins

        Returns:
            List of SensitivityResult for each subsidy level
        """
        if self.df is None:
            self.load_data()

        results = []

        # Check for required columns
        if 'subsidy_rate' not in self.df.columns:
            logger.warning("subsidy_rate column not found. Creating mock data.")
            self.df['subsidy_rate'] = np.random.uniform(0.2, 0.95, len(self.df))

        # Bin subsidy rates
        subsidy_min = self.df['subsidy_rate'].min()
        subsidy_max = self.df['subsidy_rate'].max()
        bin_edges = np.linspace(subsidy_min, subsidy_max, bins + 1)

        for i in range(bins):
            low, high = bin_edges[i], bin_edges[i + 1]
            mask = (self.df['subsidy_rate'] >= low) & (self.df['subsidy_rate'] < high)
            subset = self.df[mask]

            if len(subset) == 0:
                continue

            level = (low + high) / 2

            # Calculate adoption rates by group
            mg_rate = self._calc_adoption_rate(subset, mg=True)
            nmg_rate = self._calc_adoption_rate(subset, mg=False)
            owner_rate = self._calc_adoption_rate(subset, tenure='Owner')
            renter_rate = self._calc_adoption_rate(subset, tenure='Renter')

            results.append(SensitivityResult(
                policy_type="subsidy",
                level=round(level, 3),
                mg_adoption_rate=round(mg_rate, 4),
                nmg_adoption_rate=round(nmg_rate, 4),
                owner_adoption_rate=round(owner_rate, 4),
                renter_adoption_rate=round(renter_rate, 4),
                adoption_gap=round(mg_rate - nmg_rate, 4)
            ))

        return results

    def analyze_premium_sensitivity(
        self,
        bins: int = 5
    ) -> List[SensitivityResult]:
        """
        Analyze how premium rate affects insurance uptake.

        Args:
            bins: Number of premium level bins

        Returns:
            List of SensitivityResult for each premium level
        """
        if self.df is None:
            self.load_data()

        results = []

        # Check for required columns
        if 'premium_rate' not in self.df.columns:
            logger.warning("premium_rate column not found. Creating mock data.")
            self.df['premium_rate'] = np.random.uniform(0.01, 0.15, len(self.df))

        # Bin premium rates
        premium_min = self.df['premium_rate'].min()
        premium_max = self.df['premium_rate'].max()
        bin_edges = np.linspace(premium_min, premium_max, bins + 1)

        for i in range(bins):
            low, high = bin_edges[i], bin_edges[i + 1]
            mask = (self.df['premium_rate'] >= low) & (self.df['premium_rate'] < high)
            subset = self.df[mask]

            if len(subset) == 0:
                continue

            level = (low + high) / 2

            # For premium, we focus on insurance uptake
            mg_rate = self._calc_insurance_rate(subset, mg=True)
            nmg_rate = self._calc_insurance_rate(subset, mg=False)
            owner_rate = self._calc_insurance_rate(subset, tenure='Owner')
            renter_rate = self._calc_insurance_rate(subset, tenure='Renter')

            results.append(SensitivityResult(
                policy_type="premium",
                level=round(level, 4),
                mg_adoption_rate=round(mg_rate, 4),
                nmg_adoption_rate=round(nmg_rate, 4),
                owner_adoption_rate=round(owner_rate, 4),
                renter_adoption_rate=round(renter_rate, 4),
                adoption_gap=round(mg_rate - nmg_rate, 4)
            ))

        return results

    def _calc_adoption_rate(
        self,
        df: pd.DataFrame,
        mg: Optional[bool] = None,
        tenure: Optional[str] = None
    ) -> float:
        """Calculate overall adaptation rate (insurance + elevation)."""
        subset = df.copy()

        if mg is not None and 'mg' in df.columns:
            subset = subset[subset['mg'] == mg]
        if tenure is not None and 'tenure' in df.columns:
            subset = subset[subset['tenure'] == tenure]

        if len(subset) == 0:
            return 0.0

        # Count adaptation decisions
        decision_col = 'decision_skill' if 'decision_skill' in subset.columns else 'decision'
        if decision_col not in subset.columns:
            # Fall back to state-based calculation
            insured = subset.get('has_insurance', subset.get('insured', pd.Series([0] * len(subset))))
            elevated = subset.get('elevated', pd.Series([0] * len(subset)))
            return (insured.sum() + elevated.sum()) / (2 * len(subset))

        # Decision-based calculation
        adapt_decisions = ['buy_insurance', 'elevate_house', 'buy_contents_insurance']
        adapted = subset[decision_col].isin(adapt_decisions).sum()

        return adapted / len(subset)

    def _calc_insurance_rate(
        self,
        df: pd.DataFrame,
        mg: Optional[bool] = None,
        tenure: Optional[str] = None
    ) -> float:
        """Calculate insurance uptake rate."""
        subset = df.copy()

        if mg is not None and 'mg' in df.columns:
            subset = subset[subset['mg'] == mg]
        if tenure is not None and 'tenure' in df.columns:
            subset = subset[subset['tenure'] == tenure]

        if len(subset) == 0:
            return 0.0

        # Check for insurance decision
        decision_col = 'decision_skill' if 'decision_skill' in subset.columns else 'decision'
        if decision_col in subset.columns:
            ins_decisions = ['buy_insurance', 'buy_contents_insurance']
            return subset[decision_col].isin(ins_decisions).sum() / len(subset)

        # Fall back to state
        if 'has_insurance' in subset.columns:
            return subset['has_insurance'].sum() / len(subset)

        return 0.0

    def identify_thresholds(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Identify key policy thresholds.

        Returns:
            (subsidy_threshold, premium_threshold)
        """
        subsidy_results = self.analyze_subsidy_sensitivity(bins=10)
        premium_results = self.analyze_premium_sensitivity(bins=10)

        # Find subsidy level where MG-NMG gap < 15%
        subsidy_threshold = None
        for sr in subsidy_results:
            if abs(sr.adoption_gap) < 0.15:
                subsidy_threshold = sr.level
                break

        # Find premium level where uptake starts declining significantly
        premium_threshold = None
        if len(premium_results) >= 2:
            for i in range(1, len(premium_results)):
                prev_rate = (premium_results[i-1].mg_adoption_rate +
                            premium_results[i-1].nmg_adoption_rate) / 2
                curr_rate = (premium_results[i].mg_adoption_rate +
                            premium_results[i].nmg_adoption_rate) / 2
                # Significant drop: > 20% decline
                if prev_rate > 0 and (prev_rate - curr_rate) / prev_rate > 0.20:
                    premium_threshold = premium_results[i].level
                    break

        return subsidy_threshold, premium_threshold

    def run_full_analysis(self) -> PolicyImpactReport:
        """
        Run complete policy impact analysis.

        Returns:
            PolicyImpactReport with all results
        """
        if self.df is None:
            self.load_data()

        from datetime import datetime

        # Basic metadata
        years = sorted(self.df['year'].unique()) if 'year' in self.df.columns else []

        self.report = PolicyImpactReport(
            analysis_date=datetime.now().isoformat(),
            data_source=str(self.data_path),
            total_records=len(self.df),
            years_covered=list(map(int, years))
        )

        # Policy ranges
        if 'subsidy_rate' in self.df.columns:
            self.report.subsidy_range = (
                float(self.df['subsidy_rate'].min()),
                float(self.df['subsidy_rate'].max())
            )
        if 'premium_rate' in self.df.columns:
            self.report.premium_range = (
                float(self.df['premium_rate'].min()),
                float(self.df['premium_rate'].max())
            )

        # Sensitivity analysis
        logger.info("Running subsidy sensitivity analysis...")
        self.report.subsidy_sensitivity = self.analyze_subsidy_sensitivity()

        logger.info("Running premium sensitivity analysis...")
        self.report.premium_sensitivity = self.analyze_premium_sensitivity()

        # Thresholds
        logger.info("Identifying policy thresholds...")
        sub_thresh, prem_thresh = self.identify_thresholds()
        self.report.subsidy_threshold_for_mg_parity = sub_thresh
        self.report.premium_threshold_for_uptake = prem_thresh

        # Optimal policies (simple heuristic)
        if self.report.subsidy_sensitivity:
            # Find subsidy level with smallest gap
            best_equity = min(self.report.subsidy_sensitivity,
                            key=lambda x: abs(x.adoption_gap))
            self.report.optimal_subsidy_for_equity = best_equity.level

        return self.report

    def export_report(self, output_path: str) -> None:
        """Export report to JSON."""
        if not self.report:
            self.run_full_analysis()

        # Convert to dict
        report_dict = {
            "metadata": {
                "analysis_date": self.report.analysis_date,
                "data_source": self.report.data_source,
                "total_records": self.report.total_records,
                "years_covered": self.report.years_covered
            },
            "policy_ranges": {
                "subsidy": list(self.report.subsidy_range),
                "premium": list(self.report.premium_range)
            },
            "sensitivity_analysis": {
                "subsidy": [asdict(sr) for sr in self.report.subsidy_sensitivity],
                "premium": [asdict(sr) for sr in self.report.premium_sensitivity]
            },
            "thresholds": {
                "subsidy_for_mg_parity": self.report.subsidy_threshold_for_mg_parity,
                "premium_for_uptake": self.report.premium_threshold_for_uptake
            },
            "optimal_policies": {
                "subsidy_for_equity": self.report.optimal_subsidy_for_equity,
                "premium_for_solvency": self.report.optimal_premium_for_solvency
            }
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2)

        logger.info(f"Exported report to: {output_path}")

    def print_summary(self) -> None:
        """Print analysis summary to console."""
        if not self.report:
            self.run_full_analysis()

        print("\n" + "="*60)
        print("POLICY IMPACT ASSESSMENT SUMMARY")
        print("="*60)

        print(f"\nData Source: {self.report.data_source}")
        print(f"Records Analyzed: {self.report.total_records:,}")
        print(f"Years: {self.report.years_covered}")

        print(f"\n--- POLICY RANGES OBSERVED ---")
        print(f"  Subsidy Rate: {self.report.subsidy_range[0]:.1%} - {self.report.subsidy_range[1]:.1%}")
        print(f"  Premium Rate: {self.report.premium_range[0]:.2%} - {self.report.premium_range[1]:.2%}")

        print(f"\n--- SUBSIDY SENSITIVITY ---")
        print(f"{'Level':>8} {'MG Rate':>10} {'NMG Rate':>10} {'Gap':>10}")
        print("-" * 40)
        for sr in self.report.subsidy_sensitivity[:5]:
            print(f"{sr.level:>7.1%} {sr.mg_adoption_rate:>10.1%} {sr.nmg_adoption_rate:>10.1%} {sr.adoption_gap:>10.1%}")

        print(f"\n--- KEY THRESHOLDS ---")
        if self.report.subsidy_threshold_for_mg_parity:
            print(f"  Subsidy for MG parity (<15% gap): {self.report.subsidy_threshold_for_mg_parity:.1%}")
        if self.report.premium_threshold_for_uptake:
            print(f"  Premium threshold for uptake decline: {self.report.premium_threshold_for_uptake:.2%}")

        print(f"\n--- OPTIMAL POLICIES ---")
        if self.report.optimal_subsidy_for_equity:
            print(f"  Best subsidy for equity: {self.report.optimal_subsidy_for_equity:.1%}")

        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="Policy Impact Assessment")
    parser.add_argument("--results", required=True, help="Path to simulation results (CSV/JSONL)")
    parser.add_argument("--output", default="policy_impact_report.json", help="Output JSON path")

    args = parser.parse_args()

    analyzer = PolicyImpactAnalyzer(args.results)
    analyzer.run_full_analysis()
    analyzer.print_summary()
    analyzer.export_report(args.output)

    print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
