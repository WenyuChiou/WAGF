"""
RQ Analysis Utilities

Shared analysis functions for RQ1, RQ2, and RQ3 experiments.
"""

import sys
import json
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
class TenureMetrics:
    """Metrics for a tenure group (Owner/Renter)."""
    tenure: str
    agent_count: int

    # Adaptation metrics
    insurance_rate: float
    elevation_rate: float
    relocation_rate: float
    any_adaptation_rate: float

    # Financial metrics
    mean_damage: float
    cumulative_damage: float
    mean_uninsured_loss: float

    # Trajectory metrics
    adaptation_changes: int = 0
    post_flood_adaptations: int = 0


@dataclass
class YearlySnapshot:
    """Snapshot of metrics for a single year."""
    year: int
    flood_occurred: bool
    flood_depth: float

    # Owner metrics
    owner_insurance_rate: float
    owner_elevation_rate: float
    owner_adaptation_rate: float
    owner_mean_damage: float

    # Renter metrics
    renter_insurance_rate: float
    renter_relocation_rate: float
    renter_adaptation_rate: float
    renter_mean_damage: float

    # Gap metrics
    adaptation_gap: float  # Owner - Renter
    damage_gap: float  # Renter - Owner (renters typically have more damage)


class RQAnalyzer:
    """
    Base analyzer for Research Questions.

    Provides common data loading and metrics calculation.
    """

    def __init__(self, data_path: str):
        """
        Initialize analyzer.

        Args:
            data_path: Path to simulation results (CSV or JSONL)
        """
        self.data_path = Path(data_path)
        self.df: Optional[pd.DataFrame] = None

    def load_data(self) -> int:
        """Load simulation data."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data not found: {self.data_path}")

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

    def get_tenure_groups(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Split data by tenure."""
        if self.df is None:
            self.load_data()

        if 'tenure' not in self.df.columns:
            logger.warning("'tenure' column not found. Creating random assignment.")
            self.df['tenure'] = np.random.choice(['Owner', 'Renter'], len(self.df), p=[0.65, 0.35])

        owners = self.df[self.df['tenure'] == 'Owner']
        renters = self.df[self.df['tenure'] == 'Renter']

        return owners, renters

    def calculate_tenure_metrics(self, df: pd.DataFrame, tenure: str) -> TenureMetrics:
        """Calculate metrics for a tenure group."""
        n = len(df)
        if n == 0:
            return TenureMetrics(
                tenure=tenure, agent_count=0,
                insurance_rate=0, elevation_rate=0, relocation_rate=0,
                any_adaptation_rate=0, mean_damage=0, cumulative_damage=0,
                mean_uninsured_loss=0
            )

        # Decision column
        decision_col = 'decision_skill' if 'decision_skill' in df.columns else 'decision'

        if decision_col in df.columns:
            ins_decisions = ['buy_insurance', 'buy_contents_insurance']
            ins_rate = df[decision_col].isin(ins_decisions).sum() / n
            elev_rate = (df[decision_col] == 'elevate_house').sum() / n
            reloc_rate = df[decision_col].isin(['relocate', 'buyout_program']).sum() / n
            any_adapt = df[decision_col].isin(
                ins_decisions + ['elevate_house', 'relocate', 'buyout_program']
            ).sum() / n
        else:
            ins_rate = df.get('has_insurance', pd.Series([0]*n)).mean()
            elev_rate = df.get('elevated', pd.Series([0]*n)).mean()
            reloc_rate = df.get('relocated', pd.Series([0]*n)).mean()
            any_adapt = max(ins_rate, elev_rate, reloc_rate)

        # Financial
        mean_dmg = df.get('damage', df.get('total_damage', pd.Series([0]*n))).mean()
        cum_dmg = df.get('cumulative_damage', pd.Series([0]*n)).sum()
        mean_unins = df.get('uninsured_loss', pd.Series([0]*n)).mean()

        return TenureMetrics(
            tenure=tenure,
            agent_count=n,
            insurance_rate=round(ins_rate, 4),
            elevation_rate=round(elev_rate, 4),
            relocation_rate=round(reloc_rate, 4),
            any_adaptation_rate=round(any_adapt, 4),
            mean_damage=round(mean_dmg, 2),
            cumulative_damage=round(cum_dmg, 2),
            mean_uninsured_loss=round(mean_unins, 2)
        )

    def get_yearly_snapshots(self) -> List[YearlySnapshot]:
        """Get metrics for each year."""
        if self.df is None:
            self.load_data()

        if 'year' not in self.df.columns:
            logger.warning("'year' column not found")
            return []

        snapshots = []
        years = sorted(self.df['year'].unique())

        for year in years:
            year_df = self.df[self.df['year'] == year]

            # Check flood
            flood_occurred = year_df.get('flood_occurred', pd.Series([False])).any()
            flood_depth = year_df.get('flood_depth', year_df.get('flood_depth_ft', pd.Series([0]))).mean()

            # Tenure splits
            owners = year_df[year_df['tenure'] == 'Owner'] if 'tenure' in year_df.columns else pd.DataFrame()
            renters = year_df[year_df['tenure'] == 'Renter'] if 'tenure' in year_df.columns else pd.DataFrame()

            owner_metrics = self.calculate_tenure_metrics(owners, 'Owner')
            renter_metrics = self.calculate_tenure_metrics(renters, 'Renter')

            snapshots.append(YearlySnapshot(
                year=int(year),
                flood_occurred=bool(flood_occurred),
                flood_depth=round(float(flood_depth), 2),
                owner_insurance_rate=owner_metrics.insurance_rate,
                owner_elevation_rate=owner_metrics.elevation_rate,
                owner_adaptation_rate=owner_metrics.any_adaptation_rate,
                owner_mean_damage=owner_metrics.mean_damage,
                renter_insurance_rate=renter_metrics.insurance_rate,
                renter_relocation_rate=renter_metrics.relocation_rate,
                renter_adaptation_rate=renter_metrics.any_adaptation_rate,
                renter_mean_damage=renter_metrics.mean_damage,
                adaptation_gap=round(owner_metrics.any_adaptation_rate - renter_metrics.any_adaptation_rate, 4),
                damage_gap=round(renter_metrics.mean_damage - owner_metrics.mean_damage, 2)
            ))

        return snapshots

    def identify_flood_years(self) -> List[int]:
        """Identify years when floods occurred."""
        if self.df is None:
            self.load_data()

        flood_years = []

        if 'year' in self.df.columns and 'flood_occurred' in self.df.columns:
            year_flood = self.df.groupby('year')['flood_occurred'].any()
            flood_years = year_flood[year_flood].index.tolist()

        return [int(y) for y in flood_years]

    def export_results(self, results: Dict[str, Any], output_path: str) -> None:
        """Export results to JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Exported results to: {output_path}")
