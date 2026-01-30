"""
RQ3 Experiment: Insurance Coverage & Financial Outcomes

Research Question:
How do tenure-based insurance coverage differences shape long-term financial
outcomes under repeated flood exposure?

Hypothesis:
Contents-only coverage for renters provides less financial protection than
full structure+contents coverage for owners.

Metrics:
- Insured vs uninsured losses by tenure
- Insurance persistence (renewal rates)
- Out-of-pocket expenses ratio

Usage:
    python run_rq3_insurance_outcomes.py --results path/to/simulation_log.csv
    python run_rq3_insurance_outcomes.py --model mock  # Mock data for testing
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any
from collections import defaultdict

import pandas as pd
import numpy as np

# Setup path
CURRENT_DIR = Path(__file__).parent
MA_DIR = CURRENT_DIR.parent
ROOT_DIR = MA_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from examples.multi_agent.flood.experiments.rq_analysis import RQAnalyzer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class InsuranceMetrics:
    """Insurance-related metrics for a tenure group."""
    tenure: str
    coverage_type: str  # "Structure+Contents" or "Contents Only"

    # Coverage rates
    insured_rate: float
    persistence_rate: float  # % who maintain coverage across years

    # Loss metrics
    total_losses: float
    insured_losses: float
    uninsured_losses: float
    payout_received: float

    # Financial ratios
    coverage_ratio: float  # payout / total_losses
    oop_ratio: float  # out_of_pocket / total_losses


@dataclass
class InsuranceOutcomeResult:
    """Complete RQ3 analysis results."""
    total_agents: int
    years_simulated: int

    # Owner metrics
    owner_metrics: InsuranceMetrics
    # Renter metrics
    renter_metrics: InsuranceMetrics

    # Comparison
    coverage_gap: float  # Owner coverage_ratio - Renter coverage_ratio
    oop_gap: float  # Renter oop_ratio - Owner oop_ratio
    persistence_gap: float

    # Vulnerable population
    uninsured_owners_pct: float
    uninsured_renters_pct: float
    high_oop_agents_pct: float  # OOP > 50% of losses


class RQ3Analyzer(RQAnalyzer):
    """
    RQ3: Insurance & Financial Outcomes Analysis

    Compares insurance coverage effectiveness by tenure.
    """

    def analyze(self) -> InsuranceOutcomeResult:
        """Run RQ3 analysis."""
        if self.df is None:
            self.load_data()

        owners, renters = self.get_tenure_groups()

        # Calculate metrics
        owner_metrics = self._calc_insurance_metrics(owners, 'Owner')
        renter_metrics = self._calc_insurance_metrics(renters, 'Renter')

        # Gaps
        coverage_gap = owner_metrics.coverage_ratio - renter_metrics.coverage_ratio
        oop_gap = renter_metrics.oop_ratio - owner_metrics.oop_ratio
        persistence_gap = owner_metrics.persistence_rate - renter_metrics.persistence_rate

        # Vulnerable populations
        unins_owners = 1 - owner_metrics.insured_rate
        unins_renters = 1 - renter_metrics.insured_rate
        high_oop = self._calc_high_oop_rate()

        years_sim = int(self.df['year'].nunique()) if 'year' in self.df.columns else 1

        return InsuranceOutcomeResult(
            total_agents=len(self.df['agent_id'].unique()) if 'agent_id' in self.df.columns else len(self.df),
            years_simulated=years_sim,
            owner_metrics=owner_metrics,
            renter_metrics=renter_metrics,
            coverage_gap=round(coverage_gap, 4),
            oop_gap=round(oop_gap, 4),
            persistence_gap=round(persistence_gap, 4),
            uninsured_owners_pct=round(unins_owners, 4),
            uninsured_renters_pct=round(unins_renters, 4),
            high_oop_agents_pct=high_oop
        )

    def _calc_insurance_metrics(self, df: pd.DataFrame, tenure: str) -> InsuranceMetrics:
        """Calculate insurance metrics for a tenure group."""
        if len(df) == 0:
            return InsuranceMetrics(
                tenure=tenure,
                coverage_type="Structure+Contents" if tenure == 'Owner' else "Contents Only",
                insured_rate=0, persistence_rate=0,
                total_losses=0, insured_losses=0, uninsured_losses=0, payout_received=0,
                coverage_ratio=0, oop_ratio=1.0
            )

        # Insurance status
        insured_col = 'has_insurance' if 'has_insurance' in df.columns else 'insured'
        insured = df.get(insured_col, pd.Series([False] * len(df)))
        insured_rate = insured.mean()

        # Persistence (agents who remain insured across years)
        persistence = self._calc_persistence_rate(df)

        # Losses
        damage_col = 'damage' if 'damage' in df.columns else 'total_damage'
        total_losses = df.get(damage_col, pd.Series([0] * len(df))).sum()

        # Insured vs uninsured losses
        insured_df = df[insured == True]
        uninsured_df = df[insured == False]

        insured_losses = insured_df.get(damage_col, pd.Series([0])).sum()
        uninsured_losses = uninsured_df.get(damage_col, pd.Series([0])).sum()

        # Payouts
        payout_col = 'payout' if 'payout' in df.columns else 'insurance_payout'
        payout_received = df.get(payout_col, pd.Series([0] * len(df))).sum()

        # Ratios
        coverage_ratio = payout_received / total_losses if total_losses > 0 else 0
        oop = total_losses - payout_received
        oop_ratio = oop / total_losses if total_losses > 0 else 1.0

        return InsuranceMetrics(
            tenure=tenure,
            coverage_type="Structure+Contents" if tenure == 'Owner' else "Contents Only",
            insured_rate=round(insured_rate, 4),
            persistence_rate=round(persistence, 4),
            total_losses=round(total_losses, 2),
            insured_losses=round(insured_losses, 2),
            uninsured_losses=round(uninsured_losses, 2),
            payout_received=round(payout_received, 2),
            coverage_ratio=round(coverage_ratio, 4),
            oop_ratio=round(oop_ratio, 4)
        )

    def _calc_persistence_rate(self, df: pd.DataFrame) -> float:
        """Calculate insurance persistence rate."""
        if 'agent_id' not in df.columns or 'year' not in df.columns:
            return 0.0

        insured_col = 'has_insurance' if 'has_insurance' in df.columns else 'insured'
        if insured_col not in df.columns:
            return 0.0

        # Group by agent and check if ever insured then remained insured
        agent_histories = df.groupby('agent_id')[insured_col].apply(list)

        persistent = 0
        ever_insured = 0

        for agent_id, history in agent_histories.items():
            if any(history):
                ever_insured += 1
                # Check if maintained from first insurance year
                first_ins_idx = next((i for i, v in enumerate(history) if v), None)
                if first_ins_idx is not None:
                    # Did they stay insured?
                    remaining = history[first_ins_idx:]
                    if all(remaining):
                        persistent += 1

        return persistent / ever_insured if ever_insured > 0 else 0.0

    def _calc_high_oop_rate(self) -> float:
        """Calculate % of agents with high out-of-pocket expenses."""
        damage_col = 'damage' if 'damage' in self.df.columns else 'total_damage'
        payout_col = 'payout' if 'payout' in self.df.columns else 'insurance_payout'

        if damage_col not in self.df.columns:
            return 0.0

        total_losses = self.df.get(damage_col, pd.Series([0]))
        payouts = self.df.get(payout_col, pd.Series([0] * len(self.df)))

        oop = total_losses - payouts
        oop_ratio = oop / total_losses.replace(0, np.nan)

        # High OOP = > 50% of losses
        high_oop_count = (oop_ratio > 0.5).sum()

        return round(high_oop_count / len(self.df), 4)

    def print_results(self, result: InsuranceOutcomeResult) -> None:
        """Print analysis results."""
        print("\n" + "="*60)
        print("RQ3: INSURANCE & FINANCIAL OUTCOMES")
        print("="*60)

        print(f"\nTotal Agents: {result.total_agents}, Years: {result.years_simulated}")

        print("\n--- OWNER INSURANCE METRICS ---")
        om = result.owner_metrics
        print(f"  Coverage Type: {om.coverage_type}")
        print(f"  Insured Rate: {om.insured_rate:.1%}")
        print(f"  Persistence Rate: {om.persistence_rate:.1%}")
        print(f"  Total Losses: ${om.total_losses:,.0f}")
        print(f"  Payout Received: ${om.payout_received:,.0f}")
        print(f"  Coverage Ratio: {om.coverage_ratio:.1%}")
        print(f"  OOP Ratio: {om.oop_ratio:.1%}")

        print("\n--- RENTER INSURANCE METRICS ---")
        rm = result.renter_metrics
        print(f"  Coverage Type: {rm.coverage_type}")
        print(f"  Insured Rate: {rm.insured_rate:.1%}")
        print(f"  Persistence Rate: {rm.persistence_rate:.1%}")
        print(f"  Total Losses: ${rm.total_losses:,.0f}")
        print(f"  Payout Received: ${rm.payout_received:,.0f}")
        print(f"  Coverage Ratio: {rm.coverage_ratio:.1%}")
        print(f"  OOP Ratio: {rm.oop_ratio:.1%}")

        print("\n--- GAPS (Owner - Renter) ---")
        print(f"  Coverage Gap: {result.coverage_gap:+.1%} (Owner advantage)")
        print(f"  OOP Gap: {result.oop_gap:+.1%} (Renter disadvantage)")
        print(f"  Persistence Gap: {result.persistence_gap:+.1%}")

        print("\n--- VULNERABLE POPULATIONS ---")
        print(f"  Uninsured Owners: {result.uninsured_owners_pct:.1%}")
        print(f"  Uninsured Renters: {result.uninsured_renters_pct:.1%}")
        print(f"  High OOP Agents (>50%): {result.high_oop_agents_pct:.1%}")

        print("\n" + "="*60)


def generate_mock_data(n_agents: int = 100, n_years: int = 10) -> pd.DataFrame:
    """Generate mock simulation data with insurance details."""
    np.random.seed(42)

    records = []
    agent_ids = [f"HH_{i:03d}" for i in range(n_agents)]
    tenures = np.random.choice(['Owner', 'Renter'], n_agents, p=[0.65, 0.35])

    # Insurance persistence tracking
    agent_insurance = {aid: False for aid in agent_ids}

    flood_years = {3: 1.5, 4: 2.8, 7: 1.2, 9: 3.5}

    for year in range(1, n_years + 1):
        flood_occurred = year in flood_years
        flood_depth = flood_years.get(year, 0)

        for i, agent_id in enumerate(agent_ids):
            tenure = tenures[i]

            # Insurance decision (owners more likely)
            base_prob = 0.5 if tenure == 'Owner' else 0.25
            # Persistence boost if already insured
            if agent_insurance[agent_id]:
                base_prob = min(base_prob + 0.3, 0.9)

            has_insurance = np.random.random() < base_prob
            agent_insurance[agent_id] = has_insurance

            # Damage calculation
            if flood_occurred:
                base_damage = flood_depth * 8000
                # Owners have more exposure (structure)
                if tenure == 'Owner':
                    base_damage *= 2.5
            else:
                base_damage = 0

            # Payout calculation
            if has_insurance and base_damage > 0:
                # Owners get structure+contents, renters get contents only
                if tenure == 'Owner':
                    coverage_ratio = 0.7  # 70% coverage
                else:
                    coverage_ratio = 0.3  # Contents only = 30%
                payout = base_damage * coverage_ratio
            else:
                payout = 0

            records.append({
                'year': year,
                'agent_id': agent_id,
                'tenure': tenure,
                'has_insurance': has_insurance,
                'flood_occurred': flood_occurred,
                'flood_depth': flood_depth,
                'damage': base_damage,
                'payout': payout
            })

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="RQ3: Insurance & Financial Outcomes")
    parser.add_argument("--results", help="Path to simulation results")
    parser.add_argument("--model", default=None, help="Use 'mock' for test data")
    parser.add_argument("--output", default="rq3_financial.json", help="Output JSON path")

    args = parser.parse_args()

    if args.model == 'mock' or args.results is None:
        logger.info("Using mock data for testing")
        mock_df = generate_mock_data()
        mock_path = Path("mock_rq3_data.csv")
        mock_df.to_csv(mock_path, index=False)
        analyzer = RQ3Analyzer(str(mock_path))
    else:
        analyzer = RQ3Analyzer(args.results)

    result = analyzer.analyze()
    analyzer.print_results(result)

    # Export
    export_data = {
        "research_question": "RQ3: Insurance Coverage & Financial Outcomes",
        "hypothesis": "Contents-only coverage for renters provides less financial protection",
        "results": {
            "total_agents": result.total_agents,
            "years_simulated": result.years_simulated,
            "owner_metrics": asdict(result.owner_metrics),
            "renter_metrics": asdict(result.renter_metrics),
            "gaps": {
                "coverage_gap": result.coverage_gap,
                "oop_gap": result.oop_gap,
                "persistence_gap": result.persistence_gap
            },
            "vulnerability": {
                "uninsured_owners_pct": result.uninsured_owners_pct,
                "uninsured_renters_pct": result.uninsured_renters_pct,
                "high_oop_agents_pct": result.high_oop_agents_pct
            }
        }
    }
    analyzer.export_results(export_data, args.output)

    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
