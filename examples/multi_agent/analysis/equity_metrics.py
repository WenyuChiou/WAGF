"""
Equity Metrics Module

Tracks equity metrics for flood adaptation outcomes:
1. MG/NMG adoption gap (target: <15%)
2. Renter vs Owner adaptation gap
3. Income-stratified outcomes
4. Vulnerable population metrics

Usage:
    python equity_metrics.py --results results/simulation_log.csv
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class GroupMetrics:
    """Metrics for a demographic group."""
    group_name: str
    population_count: int
    population_share: float

    # Adaptation rates
    insurance_rate: float
    elevation_rate: float
    relocation_rate: float
    any_adaptation_rate: float

    # Financial outcomes
    mean_damage: float
    mean_uninsured_loss: float
    cumulative_damage: float

    # Vulnerability
    vulnerability_score: float  # Combined metric


@dataclass
class EquityReport:
    """Complete equity assessment report."""
    # Metadata
    analysis_date: str
    data_source: str
    total_agents: int
    years_covered: List[int]

    # Group metrics
    mg_metrics: Optional[GroupMetrics] = None
    nmg_metrics: Optional[GroupMetrics] = None
    owner_metrics: Optional[GroupMetrics] = None
    renter_metrics: Optional[GroupMetrics] = None

    # Income stratified
    income_metrics: Dict[str, GroupMetrics] = field(default_factory=dict)

    # Gap metrics
    mg_nmg_gap: float = 0.0  # Target: < 0.15
    owner_renter_gap: float = 0.0
    income_gap: float = 0.0  # High income - Low income

    # Equity indices
    gini_adaptation: float = 0.0  # 0=perfect equality, 1=max inequality
    vulnerability_index: float = 0.0  # % of vulnerable population without adaptation


class EquityAnalyzer:
    """
    Analyzes equity metrics from simulation results.

    Tracks disparities across:
    - MG (Marginalized Group) vs NMG (Non-Marginalized)
    - Owners vs Renters
    - Income levels
    """

    # Target equity thresholds
    TARGET_MG_GAP = 0.15  # 15% max gap between MG and NMG
    TARGET_TENURE_GAP = 0.20  # 20% max gap between owner and renter

    def __init__(self, data_path: str):
        """
        Initialize analyzer.

        Args:
            data_path: Path to simulation results
        """
        self.data_path = Path(data_path)
        self.df: Optional[pd.DataFrame] = None
        self.report: Optional[EquityReport] = None

    def load_data(self) -> int:
        """Load simulation data."""
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
            raise ValueError(f"Unsupported format: {self.data_path.suffix}")

        logger.info(f"Loaded {len(self.df)} records")
        return len(self.df)

    def calculate_group_metrics(
        self,
        group_name: str,
        group_df: pd.DataFrame,
        total_population: int
    ) -> GroupMetrics:
        """
        Calculate metrics for a demographic group.

        Args:
            group_name: Name of the group
            group_df: DataFrame subset for this group
            total_population: Total population for share calculation

        Returns:
            GroupMetrics dataclass
        """
        n = len(group_df)
        if n == 0:
            return GroupMetrics(
                group_name=group_name,
                population_count=0,
                population_share=0.0,
                insurance_rate=0.0,
                elevation_rate=0.0,
                relocation_rate=0.0,
                any_adaptation_rate=0.0,
                mean_damage=0.0,
                mean_uninsured_loss=0.0,
                cumulative_damage=0.0,
                vulnerability_score=1.0
            )

        # Adaptation rates
        decision_col = 'decision_skill' if 'decision_skill' in group_df.columns else 'decision'

        if decision_col in group_df.columns:
            ins_decisions = ['buy_insurance', 'buy_contents_insurance']
            ins_rate = group_df[decision_col].isin(ins_decisions).sum() / n

            elev_rate = (group_df[decision_col] == 'elevate_house').sum() / n

            reloc_decisions = ['relocate', 'buyout_program']
            reloc_rate = group_df[decision_col].isin(reloc_decisions).sum() / n

            any_adapt = group_df[decision_col].isin(
                ins_decisions + ['elevate_house'] + reloc_decisions
            ).sum() / n
        else:
            # State-based fallback
            ins_rate = group_df.get('has_insurance', pd.Series([0]*n)).mean()
            elev_rate = group_df.get('elevated', pd.Series([0]*n)).mean()
            reloc_rate = group_df.get('relocated', pd.Series([0]*n)).mean()
            any_adapt = max(ins_rate, elev_rate, reloc_rate)

        # Financial outcomes
        mean_damage = group_df.get('damage', group_df.get('total_damage', pd.Series([0]*n))).mean()
        mean_uninsured = group_df.get('uninsured_loss', pd.Series([0]*n)).mean()
        cumulative = group_df.get('cumulative_damage', pd.Series([0]*n)).sum()

        # Vulnerability score: high if low adaptation and high damage
        # Score from 0 (not vulnerable) to 1 (very vulnerable)
        vuln_score = (1 - any_adapt) * 0.5 + min(mean_damage / 50000, 1.0) * 0.5

        return GroupMetrics(
            group_name=group_name,
            population_count=n,
            population_share=round(n / total_population, 4),
            insurance_rate=round(ins_rate, 4),
            elevation_rate=round(elev_rate, 4),
            relocation_rate=round(reloc_rate, 4),
            any_adaptation_rate=round(any_adapt, 4),
            mean_damage=round(mean_damage, 2),
            mean_uninsured_loss=round(mean_uninsured, 2),
            cumulative_damage=round(cumulative, 2),
            vulnerability_score=round(vuln_score, 4)
        )

    def analyze_mg_nmg(self) -> Tuple[GroupMetrics, GroupMetrics, float]:
        """
        Analyze MG vs NMG adaptation gap.

        Returns:
            (mg_metrics, nmg_metrics, gap)
        """
        if self.df is None:
            self.load_data()

        total = len(self.df)

        if 'mg' not in self.df.columns:
            logger.warning("'mg' column not found. Creating random assignment.")
            self.df['mg'] = np.random.choice([True, False], size=len(self.df), p=[0.35, 0.65])

        mg_df = self.df[self.df['mg'] == True]
        nmg_df = self.df[self.df['mg'] == False]

        mg_metrics = self.calculate_group_metrics("MG (Marginalized)", mg_df, total)
        nmg_metrics = self.calculate_group_metrics("NMG (Non-Marginalized)", nmg_df, total)

        gap = nmg_metrics.any_adaptation_rate - mg_metrics.any_adaptation_rate

        return mg_metrics, nmg_metrics, round(gap, 4)

    def analyze_tenure(self) -> Tuple[GroupMetrics, GroupMetrics, float]:
        """
        Analyze Owner vs Renter adaptation gap.

        Returns:
            (owner_metrics, renter_metrics, gap)
        """
        if self.df is None:
            self.load_data()

        total = len(self.df)

        if 'tenure' not in self.df.columns:
            logger.warning("'tenure' column not found. Creating random assignment.")
            self.df['tenure'] = np.random.choice(['Owner', 'Renter'], size=len(self.df), p=[0.65, 0.35])

        owner_df = self.df[self.df['tenure'] == 'Owner']
        renter_df = self.df[self.df['tenure'] == 'Renter']

        owner_metrics = self.calculate_group_metrics("Owner", owner_df, total)
        renter_metrics = self.calculate_group_metrics("Renter", renter_df, total)

        gap = owner_metrics.any_adaptation_rate - renter_metrics.any_adaptation_rate

        return owner_metrics, renter_metrics, round(gap, 4)

    def analyze_income_strata(self) -> Dict[str, GroupMetrics]:
        """
        Analyze adaptation by income level.

        Returns:
            Dict mapping income level to GroupMetrics
        """
        if self.df is None:
            self.load_data()

        total = len(self.df)
        results = {}

        if 'income' not in self.df.columns:
            logger.warning("'income' column not found. Creating random income levels.")
            self.df['income'] = np.random.choice(
                ['Low', 'Medium', 'High'],
                size=len(self.df),
                p=[0.30, 0.50, 0.20]
            )

        for income_level in ['Low', 'Medium', 'High']:
            subset = self.df[self.df['income'] == income_level]
            metrics = self.calculate_group_metrics(f"Income: {income_level}", subset, total)
            results[income_level] = metrics

        return results

    def calculate_gini_adaptation(self) -> float:
        """
        Calculate Gini coefficient for adaptation distribution.

        Returns:
            Gini coefficient (0=perfect equality, 1=max inequality)
        """
        if self.df is None:
            self.load_data()

        # Get adaptation rates by agent
        decision_col = 'decision_skill' if 'decision_skill' in self.df.columns else 'decision'

        if decision_col not in self.df.columns:
            return 0.0

        # Group by agent and count adaptations
        adapt_decisions = ['buy_insurance', 'buy_contents_insurance', 'elevate_house',
                          'relocate', 'buyout_program']

        agent_col = 'agent_id' if 'agent_id' in self.df.columns else 'id'
        if agent_col not in self.df.columns:
            return 0.0

        agent_adaptations = self.df.groupby(agent_col).apply(
            lambda x: x[decision_col].isin(adapt_decisions).sum()
        ).values

        if len(agent_adaptations) == 0:
            return 0.0

        # Gini calculation
        sorted_vals = np.sort(agent_adaptations)
        n = len(sorted_vals)
        cumsum = np.cumsum(sorted_vals)
        total = cumsum[-1]

        if total == 0:
            return 0.0

        gini = (n + 1 - 2 * np.sum(cumsum) / total) / n
        return round(max(0, min(1, gini)), 4)

    def run_full_analysis(self) -> EquityReport:
        """
        Run complete equity analysis.

        Returns:
            EquityReport with all metrics
        """
        if self.df is None:
            self.load_data()

        from datetime import datetime

        # Basic metadata
        years = sorted(self.df['year'].unique()) if 'year' in self.df.columns else []

        self.report = EquityReport(
            analysis_date=datetime.now().isoformat(),
            data_source=str(self.data_path),
            total_agents=len(self.df),
            years_covered=list(map(int, years)) if years else []
        )

        # MG/NMG analysis
        logger.info("Analyzing MG vs NMG...")
        mg, nmg, mg_gap = self.analyze_mg_nmg()
        self.report.mg_metrics = mg
        self.report.nmg_metrics = nmg
        self.report.mg_nmg_gap = mg_gap

        # Tenure analysis
        logger.info("Analyzing Owner vs Renter...")
        owner, renter, tenure_gap = self.analyze_tenure()
        self.report.owner_metrics = owner
        self.report.renter_metrics = renter
        self.report.owner_renter_gap = tenure_gap

        # Income analysis
        logger.info("Analyzing income strata...")
        income_metrics = self.analyze_income_strata()
        self.report.income_metrics = income_metrics

        if 'High' in income_metrics and 'Low' in income_metrics:
            self.report.income_gap = round(
                income_metrics['High'].any_adaptation_rate -
                income_metrics['Low'].any_adaptation_rate, 4
            )

        # Gini coefficient
        logger.info("Calculating Gini coefficient...")
        self.report.gini_adaptation = self.calculate_gini_adaptation()

        # Vulnerability index
        # % of MG + Renters + Low income without adaptation
        vulnerable_groups = []
        if mg:
            vulnerable_groups.append(1 - mg.any_adaptation_rate)
        if renter:
            vulnerable_groups.append(1 - renter.any_adaptation_rate)
        if 'Low' in income_metrics:
            vulnerable_groups.append(1 - income_metrics['Low'].any_adaptation_rate)

        if vulnerable_groups:
            self.report.vulnerability_index = round(np.mean(vulnerable_groups), 4)

        return self.report

    def export_report(self, output_path: str) -> None:
        """Export report to JSON."""
        if not self.report:
            self.run_full_analysis()

        def metrics_to_dict(m: Optional[GroupMetrics]) -> Optional[Dict]:
            return asdict(m) if m else None

        report_dict = {
            "metadata": {
                "analysis_date": self.report.analysis_date,
                "data_source": self.report.data_source,
                "total_agents": self.report.total_agents,
                "years_covered": self.report.years_covered
            },
            "group_metrics": {
                "mg": metrics_to_dict(self.report.mg_metrics),
                "nmg": metrics_to_dict(self.report.nmg_metrics),
                "owner": metrics_to_dict(self.report.owner_metrics),
                "renter": metrics_to_dict(self.report.renter_metrics)
            },
            "income_metrics": {
                level: metrics_to_dict(metrics)
                for level, metrics in self.report.income_metrics.items()
            },
            "gap_metrics": {
                "mg_nmg_gap": self.report.mg_nmg_gap,
                "owner_renter_gap": self.report.owner_renter_gap,
                "income_gap": self.report.income_gap,
                "target_mg_gap": self.TARGET_MG_GAP,
                "mg_gap_meets_target": abs(self.report.mg_nmg_gap) < self.TARGET_MG_GAP
            },
            "equity_indices": {
                "gini_adaptation": self.report.gini_adaptation,
                "vulnerability_index": self.report.vulnerability_index
            }
        }

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report_dict, f, indent=2)

        logger.info(f"Exported report to: {output_path}")

    def print_summary(self) -> None:
        """Print equity summary to console."""
        if not self.report:
            self.run_full_analysis()

        print("\n" + "="*60)
        print("EQUITY METRICS SUMMARY")
        print("="*60)

        print(f"\nTotal Agents: {self.report.total_agents:,}")

        print("\n--- MG vs NMG ---")
        if self.report.mg_metrics and self.report.nmg_metrics:
            mg = self.report.mg_metrics
            nmg = self.report.nmg_metrics
            print(f"  MG Population: {mg.population_count:,} ({mg.population_share:.1%})")
            print(f"    Adaptation Rate: {mg.any_adaptation_rate:.1%}")
            print(f"    Vulnerability: {mg.vulnerability_score:.2f}")
            print(f"  NMG Population: {nmg.population_count:,} ({nmg.population_share:.1%})")
            print(f"    Adaptation Rate: {nmg.any_adaptation_rate:.1%}")
            print(f"    Vulnerability: {nmg.vulnerability_score:.2f}")
            print(f"  GAP: {self.report.mg_nmg_gap:.1%} (Target: <{self.TARGET_MG_GAP:.0%})")
            status = "MEETS TARGET" if abs(self.report.mg_nmg_gap) < self.TARGET_MG_GAP else "EXCEEDS TARGET"
            print(f"  Status: {status}")

        print("\n--- Owner vs Renter ---")
        if self.report.owner_metrics and self.report.renter_metrics:
            owner = self.report.owner_metrics
            renter = self.report.renter_metrics
            print(f"  Owner: {owner.any_adaptation_rate:.1%} adaptation")
            print(f"  Renter: {renter.any_adaptation_rate:.1%} adaptation")
            print(f"  GAP: {self.report.owner_renter_gap:.1%}")

        print("\n--- Income Stratification ---")
        for level, metrics in self.report.income_metrics.items():
            print(f"  {level}: {metrics.any_adaptation_rate:.1%} adaptation")
        print(f"  High-Low GAP: {self.report.income_gap:.1%}")

        print("\n--- Equity Indices ---")
        print(f"  Gini (Adaptation): {self.report.gini_adaptation:.3f}")
        print(f"  Vulnerability Index: {self.report.vulnerability_index:.1%}")

        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="Equity Metrics Analysis")
    parser.add_argument("--results", required=True, help="Path to simulation results")
    parser.add_argument("--output", default="equity_report.json", help="Output JSON path")

    args = parser.parse_args()

    analyzer = EquityAnalyzer(args.results)
    analyzer.run_full_analysis()
    analyzer.print_summary()
    analyzer.export_report(args.output)

    print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    main()
