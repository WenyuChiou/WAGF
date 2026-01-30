"""
RQ1 Experiment: Adaptation Continuation vs Inaction

Research Question:
How does continued adaptation, compared with no action, differentially affect
long-term flood outcomes for renters and homeowners?

Hypothesis:
Homeowners benefit more from continued adaptation due to structure ownership,
while renters face mobility constraints that may limit sustained investment.

Metrics:
- Cumulative damage over 10 years by tenure
- Adaptation state distribution (None/Insurance/Elevation/Both/Relocate)
- Financial recovery trajectories

Usage:
    python run_rq1_adaptation_impact.py --results path/to/simulation_log.csv
    python run_rq1_adaptation_impact.py --model mock  # Mock data for testing
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
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

from examples.multi_agent.flood.experiments.rq_analysis import RQAnalyzer, TenureMetrics

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AdaptationImpactResult:
    """Results for RQ1 analysis."""
    # Population
    total_agents: int
    owner_count: int
    renter_count: int
    years_simulated: int

    # Adaptation rates by tenure
    owner_adaptation_rate: float
    renter_adaptation_rate: float
    adaptation_gap: float

    # Cumulative damage by tenure
    owner_cumulative_damage: float
    renter_cumulative_damage: float
    owner_mean_annual_damage: float
    renter_mean_annual_damage: float

    # Damage by adaptation status
    adapted_owner_damage: float
    unadapted_owner_damage: float
    adapted_renter_damage: float
    unadapted_renter_damage: float

    # Adaptation benefit
    owner_adaptation_benefit: float  # % damage reduction from adapting
    renter_adaptation_benefit: float

    # State distribution
    owner_state_distribution: Dict[str, float]
    renter_state_distribution: Dict[str, float]


class RQ1Analyzer(RQAnalyzer):
    """
    RQ1: Adaptation Impact Analysis

    Compares outcomes between adapted and unadapted agents by tenure.
    """

    ADAPTATION_STATES = [
        "None",
        "Insurance Only",
        "Elevation Only",
        "Both (Ins+Elev)",
        "Relocated"
    ]

    def classify_adaptation_state(self, row: pd.Series) -> str:
        """Classify agent into adaptation state category."""
        has_ins = row.get('has_insurance', False) or row.get('insured', False)
        elevated = row.get('elevated', False)
        relocated = row.get('relocated', False)

        if relocated:
            return "Relocated"
        elif has_ins and elevated:
            return "Both (Ins+Elev)"
        elif elevated:
            return "Elevation Only"
        elif has_ins:
            return "Insurance Only"
        else:
            return "None"

    def analyze(self) -> AdaptationImpactResult:
        """Run RQ1 analysis."""
        if self.df is None:
            self.load_data()

        owners, renters = self.get_tenure_groups()

        # Get unique agents for final year (end state)
        final_year = self.df['year'].max() if 'year' in self.df.columns else None
        if final_year:
            final_df = self.df[self.df['year'] == final_year]
        else:
            final_df = self.df

        final_owners = final_df[final_df['tenure'] == 'Owner'] if 'tenure' in final_df.columns else pd.DataFrame()
        final_renters = final_df[final_df['tenure'] == 'Renter'] if 'tenure' in final_df.columns else pd.DataFrame()

        # Calculate metrics
        owner_metrics = self.calculate_tenure_metrics(owners, 'Owner')
        renter_metrics = self.calculate_tenure_metrics(renters, 'Renter')

        # State distribution (final year)
        owner_states = self._get_state_distribution(final_owners)
        renter_states = self._get_state_distribution(final_renters)

        # Damage by adaptation status
        adapted_owner_dmg, unadapted_owner_dmg = self._damage_by_adaptation(owners)
        adapted_renter_dmg, unadapted_renter_dmg = self._damage_by_adaptation(renters)

        # Calculate adaptation benefit
        owner_benefit = self._calc_adaptation_benefit(adapted_owner_dmg, unadapted_owner_dmg)
        renter_benefit = self._calc_adaptation_benefit(adapted_renter_dmg, unadapted_renter_dmg)

        years_sim = int(self.df['year'].nunique()) if 'year' in self.df.columns else 1

        return AdaptationImpactResult(
            total_agents=len(self.df['agent_id'].unique()) if 'agent_id' in self.df.columns else len(self.df),
            owner_count=owner_metrics.agent_count,
            renter_count=renter_metrics.agent_count,
            years_simulated=years_sim,
            owner_adaptation_rate=owner_metrics.any_adaptation_rate,
            renter_adaptation_rate=renter_metrics.any_adaptation_rate,
            adaptation_gap=round(owner_metrics.any_adaptation_rate - renter_metrics.any_adaptation_rate, 4),
            owner_cumulative_damage=owner_metrics.cumulative_damage,
            renter_cumulative_damage=renter_metrics.cumulative_damage,
            owner_mean_annual_damage=round(owner_metrics.mean_damage / max(years_sim, 1), 2),
            renter_mean_annual_damage=round(renter_metrics.mean_damage / max(years_sim, 1), 2),
            adapted_owner_damage=adapted_owner_dmg,
            unadapted_owner_damage=unadapted_owner_dmg,
            adapted_renter_damage=adapted_renter_dmg,
            unadapted_renter_damage=unadapted_renter_dmg,
            owner_adaptation_benefit=owner_benefit,
            renter_adaptation_benefit=renter_benefit,
            owner_state_distribution=owner_states,
            renter_state_distribution=renter_states
        )

    def _get_state_distribution(self, df: pd.DataFrame) -> Dict[str, float]:
        """Get adaptation state distribution."""
        if len(df) == 0:
            return {state: 0.0 for state in self.ADAPTATION_STATES}

        states = df.apply(self.classify_adaptation_state, axis=1)
        counts = states.value_counts(normalize=True)

        return {
            state: round(counts.get(state, 0.0), 4)
            for state in self.ADAPTATION_STATES
        }

    def _damage_by_adaptation(self, df: pd.DataFrame) -> tuple:
        """Calculate mean damage for adapted vs unadapted agents."""
        if len(df) == 0:
            return 0.0, 0.0

        # Determine adaptation status
        df = df.copy()
        df['adapted'] = df.apply(
            lambda r: r.get('has_insurance', False) or r.get('elevated', False),
            axis=1
        )

        damage_col = 'damage' if 'damage' in df.columns else 'total_damage'
        if damage_col not in df.columns:
            return 0.0, 0.0

        adapted_dmg = df[df['adapted']][damage_col].mean() if df['adapted'].any() else 0
        unadapted_dmg = df[~df['adapted']][damage_col].mean() if (~df['adapted']).any() else 0

        return round(adapted_dmg, 2), round(unadapted_dmg, 2)

    def _calc_adaptation_benefit(self, adapted_dmg: float, unadapted_dmg: float) -> float:
        """Calculate % damage reduction from adapting."""
        if unadapted_dmg == 0:
            return 0.0
        return round((unadapted_dmg - adapted_dmg) / unadapted_dmg, 4)

    def print_results(self, result: AdaptationImpactResult) -> None:
        """Print analysis results."""
        print("\n" + "="*60)
        print("RQ1: ADAPTATION IMPACT ANALYSIS")
        print("="*60)

        print(f"\nPopulation: {result.total_agents} agents over {result.years_simulated} years")
        print(f"  Owners: {result.owner_count}, Renters: {result.renter_count}")

        print("\n--- ADAPTATION RATES ---")
        print(f"  Owners: {result.owner_adaptation_rate:.1%}")
        print(f"  Renters: {result.renter_adaptation_rate:.1%}")
        print(f"  Gap: {result.adaptation_gap:.1%}")

        print("\n--- CUMULATIVE DAMAGE ---")
        print(f"  Owners: ${result.owner_cumulative_damage:,.0f}")
        print(f"  Renters: ${result.renter_cumulative_damage:,.0f}")

        print("\n--- DAMAGE BY ADAPTATION STATUS ---")
        print(f"  Adapted Owners: ${result.adapted_owner_damage:,.0f}")
        print(f"  Unadapted Owners: ${result.unadapted_owner_damage:,.0f}")
        print(f"  Adapted Renters: ${result.adapted_renter_damage:,.0f}")
        print(f"  Unadapted Renters: ${result.unadapted_renter_damage:,.0f}")

        print("\n--- ADAPTATION BENEFIT ---")
        print(f"  Owner benefit (damage reduction): {result.owner_adaptation_benefit:.1%}")
        print(f"  Renter benefit (damage reduction): {result.renter_adaptation_benefit:.1%}")

        print("\n--- STATE DISTRIBUTION (OWNERS) ---")
        for state, pct in result.owner_state_distribution.items():
            print(f"  {state}: {pct:.1%}")

        print("\n--- STATE DISTRIBUTION (RENTERS) ---")
        for state, pct in result.renter_state_distribution.items():
            print(f"  {state}: {pct:.1%}")

        print("\n" + "="*60)


def generate_mock_data(n_agents: int = 100, n_years: int = 10) -> pd.DataFrame:
    """Generate mock simulation data for testing."""
    np.random.seed(42)

    records = []
    agent_ids = [f"HH_{i:03d}" for i in range(n_agents)]
    tenures = np.random.choice(['Owner', 'Renter'], n_agents, p=[0.65, 0.35])

    for year in range(1, n_years + 1):
        flood_occurred = year in [3, 4, 7, 9]  # Flood years
        flood_depth = np.random.uniform(0.5, 3.0) if flood_occurred else 0

        for i, agent_id in enumerate(agent_ids):
            tenure = tenures[i]

            # Simulate adaptation probability (owners more likely)
            adapt_prob = 0.4 if tenure == 'Owner' else 0.2
            has_insurance = np.random.random() < adapt_prob * (1 + year * 0.05)
            elevated = np.random.random() < 0.15 if tenure == 'Owner' else False
            relocated = np.random.random() < 0.05 if tenure == 'Renter' else False

            # Damage (reduced if adapted)
            base_damage = flood_depth * 10000 if flood_occurred else 0
            if has_insurance:
                base_damage *= 0.3
            if elevated:
                base_damage *= 0.1

            records.append({
                'year': year,
                'agent_id': agent_id,
                'tenure': tenure,
                'has_insurance': has_insurance,
                'elevated': elevated,
                'relocated': relocated,
                'flood_occurred': flood_occurred,
                'flood_depth': flood_depth,
                'damage': base_damage,
                'cumulative_damage': 0  # Would be calculated in real sim
            })

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="RQ1: Adaptation Impact Analysis")
    parser.add_argument("--results", help="Path to simulation results (CSV/JSONL)")
    parser.add_argument("--model", default=None, help="Use 'mock' for test data")
    parser.add_argument("--output", default="rq1_results.json", help="Output JSON path")

    args = parser.parse_args()

    if args.model == 'mock' or args.results is None:
        logger.info("Using mock data for testing")
        mock_df = generate_mock_data()
        mock_path = Path("mock_rq1_data.csv")
        mock_df.to_csv(mock_path, index=False)
        analyzer = RQ1Analyzer(str(mock_path))
    else:
        analyzer = RQ1Analyzer(args.results)

    result = analyzer.analyze()
    analyzer.print_results(result)

    # Export
    analyzer.export_results({
        "research_question": "RQ1: Adaptation Continuation vs Inaction",
        "hypothesis": "Homeowners benefit more from continued adaptation due to structure ownership",
        "results": asdict(result)
    }, args.output)

    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
