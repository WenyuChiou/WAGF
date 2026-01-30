"""
RQ2 Experiment: Post-Flood Adaptation Trajectories

Research Question:
How do renters and homeowners differ in their adaptation trajectories
following major flood events?

Hypothesis:
Major flood events trigger faster adaptation in homeowners (elevation, insurance)
vs renters (relocation preference).

Metrics:
- Adaptation action within 1 year post-flood
- Trajectory divergence (owner vs renter paths)
- Memory salience of flood events

Usage:
    python run_rq2_postflood_trajectory.py --results path/to/simulation_log.csv
    python run_rq2_postflood_trajectory.py --model mock  # Mock data for testing
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

# Setup path
CURRENT_DIR = Path(__file__).parent
MA_DIR = CURRENT_DIR.parent
ROOT_DIR = MA_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from examples.multi_agent.experiments.rq_analysis import RQAnalyzer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class FloodEvent:
    """Information about a flood event."""
    year: int
    severity: str  # "Minor", "Moderate", "Major"
    mean_depth_ft: float


@dataclass
class PostFloodTrajectory:
    """Trajectory analysis for a flood event."""
    flood_year: int
    flood_severity: str

    # Pre-flood rates
    pre_owner_adaptation_rate: float
    pre_renter_adaptation_rate: float

    # Post-flood rates (1 year after)
    post_owner_adaptation_rate: float
    post_renter_adaptation_rate: float

    # Change
    owner_adaptation_change: float
    renter_adaptation_change: float

    # Action breakdown
    owner_actions_post_flood: Dict[str, float]
    renter_actions_post_flood: Dict[str, float]


@dataclass
class TrajectoryResult:
    """Complete RQ2 analysis results."""
    total_agents: int
    flood_events: List[FloodEvent]
    trajectories: List[PostFloodTrajectory]

    # Summary metrics
    avg_owner_response_rate: float
    avg_renter_response_rate: float
    response_gap: float

    # Trajectory divergence
    owner_preferred_response: str
    renter_preferred_response: str
    divergence_score: float  # 0=same paths, 1=completely different


class RQ2Analyzer(RQAnalyzer):
    """
    RQ2: Post-Flood Trajectory Analysis

    Tracks adaptation decisions before and after flood events by tenure.
    """

    ADAPTATION_ACTIONS = {
        'insurance': ['buy_insurance', 'buy_contents_insurance'],
        'elevation': ['elevate_house'],
        'relocation': ['relocate', 'buyout_program'],
        'nothing': ['do_nothing']
    }

    def identify_flood_events(self) -> List[FloodEvent]:
        """Identify and classify flood events by severity."""
        if self.df is None:
            self.load_data()

        flood_years = self.identify_flood_years()
        events = []

        for year in flood_years:
            year_df = self.df[self.df['year'] == year]
            depth = year_df.get('flood_depth', year_df.get('flood_depth_ft', pd.Series([0]))).mean()

            # Classify severity
            if depth < 1:
                severity = "Minor"
            elif depth < 2.5:
                severity = "Moderate"
            else:
                severity = "Major"

            events.append(FloodEvent(
                year=int(year),
                severity=severity,
                mean_depth_ft=round(float(depth), 2)
            ))

        return events

    def analyze_trajectory(self, flood_event: FloodEvent) -> PostFloodTrajectory:
        """Analyze adaptation trajectory around a flood event."""
        if self.df is None:
            self.load_data()

        flood_year = flood_event.year

        # Get data for pre-flood and post-flood years
        pre_df = self.df[self.df['year'] == flood_year - 1] if flood_year > 1 else pd.DataFrame()
        post_df = self.df[self.df['year'] == flood_year + 1]

        # Split by tenure
        pre_owners = pre_df[pre_df['tenure'] == 'Owner'] if 'tenure' in pre_df.columns else pd.DataFrame()
        pre_renters = pre_df[pre_df['tenure'] == 'Renter'] if 'tenure' in pre_df.columns else pd.DataFrame()
        post_owners = post_df[post_df['tenure'] == 'Owner'] if 'tenure' in post_df.columns else pd.DataFrame()
        post_renters = post_df[post_df['tenure'] == 'Renter'] if 'tenure' in post_df.columns else pd.DataFrame()

        # Calculate rates
        pre_owner_rate = self._calc_adaptation_rate(pre_owners)
        pre_renter_rate = self._calc_adaptation_rate(pre_renters)
        post_owner_rate = self._calc_adaptation_rate(post_owners)
        post_renter_rate = self._calc_adaptation_rate(post_renters)

        # Action breakdown
        owner_actions = self._get_action_distribution(post_owners)
        renter_actions = self._get_action_distribution(post_renters)

        return PostFloodTrajectory(
            flood_year=flood_year,
            flood_severity=flood_event.severity,
            pre_owner_adaptation_rate=pre_owner_rate,
            pre_renter_adaptation_rate=pre_renter_rate,
            post_owner_adaptation_rate=post_owner_rate,
            post_renter_adaptation_rate=post_renter_rate,
            owner_adaptation_change=round(post_owner_rate - pre_owner_rate, 4),
            renter_adaptation_change=round(post_renter_rate - pre_renter_rate, 4),
            owner_actions_post_flood=owner_actions,
            renter_actions_post_flood=renter_actions
        )

    def _calc_adaptation_rate(self, df: pd.DataFrame) -> float:
        """Calculate adaptation rate for a dataframe."""
        if len(df) == 0:
            return 0.0

        decision_col = 'decision_skill' if 'decision_skill' in df.columns else 'decision'
        if decision_col not in df.columns:
            return 0.0

        adapt_decisions = (
            self.ADAPTATION_ACTIONS['insurance'] +
            self.ADAPTATION_ACTIONS['elevation'] +
            self.ADAPTATION_ACTIONS['relocation']
        )

        return round(df[decision_col].isin(adapt_decisions).mean(), 4)

    def _get_action_distribution(self, df: pd.DataFrame) -> Dict[str, float]:
        """Get distribution of adaptation actions."""
        dist = {cat: 0.0 for cat in self.ADAPTATION_ACTIONS}

        if len(df) == 0:
            return dist

        decision_col = 'decision_skill' if 'decision_skill' in df.columns else 'decision'
        if decision_col not in df.columns:
            return dist

        n = len(df)
        for cat, actions in self.ADAPTATION_ACTIONS.items():
            count = df[decision_col].isin(actions).sum()
            dist[cat] = round(count / n, 4)

        return dist

    def analyze(self) -> TrajectoryResult:
        """Run complete RQ2 analysis."""
        if self.df is None:
            self.load_data()

        flood_events = self.identify_flood_events()

        if not flood_events:
            logger.warning("No flood events found in data")
            return TrajectoryResult(
                total_agents=0,
                flood_events=[],
                trajectories=[],
                avg_owner_response_rate=0,
                avg_renter_response_rate=0,
                response_gap=0,
                owner_preferred_response="N/A",
                renter_preferred_response="N/A",
                divergence_score=0
            )

        # Analyze trajectory for each flood event
        trajectories = []
        for event in flood_events:
            traj = self.analyze_trajectory(event)
            trajectories.append(traj)

        # Calculate summary metrics
        owner_changes = [t.owner_adaptation_change for t in trajectories]
        renter_changes = [t.renter_adaptation_change for t in trajectories]

        avg_owner = np.mean(owner_changes) if owner_changes else 0
        avg_renter = np.mean(renter_changes) if renter_changes else 0

        # Aggregate action distributions
        owner_action_totals = defaultdict(float)
        renter_action_totals = defaultdict(float)

        for traj in trajectories:
            for action, rate in traj.owner_actions_post_flood.items():
                owner_action_totals[action] += rate
            for action, rate in traj.renter_actions_post_flood.items():
                renter_action_totals[action] += rate

        # Find preferred responses
        owner_preferred = max(owner_action_totals, key=owner_action_totals.get) if owner_action_totals else "N/A"
        renter_preferred = max(renter_action_totals, key=renter_action_totals.get) if renter_action_totals else "N/A"

        # Divergence score (how different are the paths?)
        # 0 = same preferred action, 1 = completely different
        divergence = 1.0 if owner_preferred != renter_preferred else 0.0

        return TrajectoryResult(
            total_agents=len(self.df['agent_id'].unique()) if 'agent_id' in self.df.columns else len(self.df),
            flood_events=flood_events,
            trajectories=trajectories,
            avg_owner_response_rate=round(avg_owner, 4),
            avg_renter_response_rate=round(avg_renter, 4),
            response_gap=round(avg_owner - avg_renter, 4),
            owner_preferred_response=owner_preferred,
            renter_preferred_response=renter_preferred,
            divergence_score=divergence
        )

    def print_results(self, result: TrajectoryResult) -> None:
        """Print analysis results."""
        print("\n" + "="*60)
        print("RQ2: POST-FLOOD ADAPTATION TRAJECTORIES")
        print("="*60)

        print(f"\nTotal Agents: {result.total_agents}")
        print(f"Flood Events: {len(result.flood_events)}")

        print("\n--- FLOOD EVENTS ---")
        for event in result.flood_events:
            print(f"  Year {event.year}: {event.severity} (depth={event.mean_depth_ft}ft)")

        print("\n--- TRAJECTORIES BY EVENT ---")
        for traj in result.trajectories:
            print(f"\n  Year {traj.flood_year} ({traj.flood_severity}):")
            print(f"    Owner change: {traj.pre_owner_adaptation_rate:.1%} -> {traj.post_owner_adaptation_rate:.1%} ({traj.owner_adaptation_change:+.1%})")
            print(f"    Renter change: {traj.pre_renter_adaptation_rate:.1%} -> {traj.post_renter_adaptation_rate:.1%} ({traj.renter_adaptation_change:+.1%})")
            print(f"    Owner actions: insurance={traj.owner_actions_post_flood['insurance']:.0%}, elev={traj.owner_actions_post_flood['elevation']:.0%}, reloc={traj.owner_actions_post_flood['relocation']:.0%}")
            print(f"    Renter actions: insurance={traj.renter_actions_post_flood['insurance']:.0%}, reloc={traj.renter_actions_post_flood['relocation']:.0%}")

        print("\n--- SUMMARY ---")
        print(f"  Avg Owner Response Rate: {result.avg_owner_response_rate:+.1%}")
        print(f"  Avg Renter Response Rate: {result.avg_renter_response_rate:+.1%}")
        print(f"  Response Gap: {result.response_gap:+.1%}")

        print("\n--- TRAJECTORY DIVERGENCE ---")
        print(f"  Owner preferred response: {result.owner_preferred_response}")
        print(f"  Renter preferred response: {result.renter_preferred_response}")
        print(f"  Divergence score: {result.divergence_score:.1f}")

        print("\n" + "="*60)


def generate_mock_data(n_agents: int = 100, n_years: int = 10) -> pd.DataFrame:
    """Generate mock data with flood events."""
    np.random.seed(42)

    records = []
    agent_ids = [f"HH_{i:03d}" for i in range(n_agents)]
    tenures = np.random.choice(['Owner', 'Renter'], n_agents, p=[0.65, 0.35])

    flood_years = {3: 1.5, 4: 2.8, 9: 3.5}  # year: depth

    for year in range(1, n_years + 1):
        flood_occurred = year in flood_years
        flood_depth = flood_years.get(year, 0)

        for i, agent_id in enumerate(agent_ids):
            tenure = tenures[i]

            # Post-flood adaptation more likely
            prev_flood = any(fy < year and year - fy <= 1 for fy in flood_years)
            base_adapt = 0.3 if prev_flood else 0.1

            if tenure == 'Owner':
                # Owners more likely to buy insurance/elevate
                decision = np.random.choice(
                    ['buy_insurance', 'elevate_house', 'do_nothing'],
                    p=[base_adapt * 1.5, base_adapt * 0.5, 1 - base_adapt * 2]
                )
            else:
                # Renters more likely to relocate or do nothing
                decision = np.random.choice(
                    ['buy_contents_insurance', 'relocate', 'do_nothing'],
                    p=[base_adapt, base_adapt * 0.5, 1 - base_adapt * 1.5]
                )

            records.append({
                'year': year,
                'agent_id': agent_id,
                'tenure': tenure,
                'decision_skill': decision,
                'flood_occurred': flood_occurred,
                'flood_depth': flood_depth
            })

    return pd.DataFrame(records)


def main():
    parser = argparse.ArgumentParser(description="RQ2: Post-Flood Trajectory Analysis")
    parser.add_argument("--results", help="Path to simulation results")
    parser.add_argument("--model", default=None, help="Use 'mock' for test data")
    parser.add_argument("--output", default="rq2_trajectories.json", help="Output JSON path")

    args = parser.parse_args()

    if args.model == 'mock' or args.results is None:
        logger.info("Using mock data for testing")
        mock_df = generate_mock_data()
        mock_path = Path("mock_rq2_data.csv")
        mock_df.to_csv(mock_path, index=False)
        analyzer = RQ2Analyzer(str(mock_path))
    else:
        analyzer = RQ2Analyzer(args.results)

    result = analyzer.analyze()
    analyzer.print_results(result)

    # Export
    export_data = {
        "research_question": "RQ2: Post-Flood Adaptation Trajectories",
        "hypothesis": "Major flood events trigger faster adaptation in homeowners vs renters",
        "results": {
            "total_agents": result.total_agents,
            "flood_events": [asdict(e) for e in result.flood_events],
            "trajectories": [asdict(t) for t in result.trajectories],
            "summary": {
                "avg_owner_response_rate": result.avg_owner_response_rate,
                "avg_renter_response_rate": result.avg_renter_response_rate,
                "response_gap": result.response_gap,
                "owner_preferred_response": result.owner_preferred_response,
                "renter_preferred_response": result.renter_preferred_response,
                "divergence_score": result.divergence_score
            }
        }
    }
    analyzer.export_results(export_data, args.output)

    print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
