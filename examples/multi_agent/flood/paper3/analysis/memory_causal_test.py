"""
Memory-Decision Divergence Analysis — Offline Correlation Check.

Analyses whether agents with *different* memories make *different* decisions,
providing a **necessary but not sufficient** indicator of memory influence.

Methodology (offline — no LLM calls):
    1. Select N agents at year Y (5 MG, 5 NMG)
    2. Pair each agent with a demographically different donor agent
    3. Compare the paired agents' decisions at the same time-step
    4. If >= 70% of pairs make different decisions → memory divergence detected
    5. Analyse which memory elements are cited in reasoning traces

Important distinction:
    This is a CORRELATION analysis, not a true causal test. It shows that
    agents with different memories tend to make different decisions, but cannot
    isolate memory as the sole cause (persona, state, and location also differ).

    A true causal test would re-run the *same* agent with swapped memories,
    holding all other inputs constant. That requires live LLM inference and
    should be done via the ICC probing infrastructure (future extension).

Usage:
    python -m paper3.analysis.memory_causal_test \\
        --trace-dir paper3/results/seed_42/ \\
        --year 10 --n-agents 10

This script is designed to run as a post-experiment analysis. It requires
audit CSVs and agent memory snapshots from a completed experiment run.
For pre-experiment validation, use ICC probing (run_cv.py --mode icc).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Ensure flood project root is on sys.path
# ---------------------------------------------------------------------------
_FLOOD_ROOT = Path(__file__).resolve().parents[2]
if str(_FLOOD_ROOT) not in sys.path:
    sys.path.insert(0, str(_FLOOD_ROOT))


@dataclass
class SwapResult:
    """Result of a single memory substitution for one agent."""
    agent_id: str
    mg_status: str
    year: int
    original_decision: str
    swapped_decision: str
    donor_agent_id: str
    decision_changed: bool
    original_tp: str = ""
    swapped_tp: str = ""
    original_cp: str = ""
    swapped_cp: str = ""
    original_reasoning: str = ""
    swapped_reasoning: str = ""
    memories_cited_original: List[str] = field(default_factory=list)
    memories_cited_swapped: List[str] = field(default_factory=list)


@dataclass
class CausalTestReport:
    """Aggregate report for the memory-decision divergence analysis."""
    n_agents_tested: int = 0
    n_decisions_changed: int = 0
    change_rate: float = 0.0
    n_mg_changed: int = 0
    n_nmg_changed: int = 0
    swap_results: List[SwapResult] = field(default_factory=list)
    memory_divergence_detected: bool = False  # True if change_rate >= 0.70

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_agents_tested": self.n_agents_tested,
            "n_decisions_changed": self.n_decisions_changed,
            "change_rate": round(self.change_rate, 4),
            "n_mg_changed": self.n_mg_changed,
            "n_nmg_changed": self.n_nmg_changed,
            "memory_divergence_detected": self.memory_divergence_detected,
            "threshold": 0.70,
            "analysis_type": "correlation_offline",
            "note": (
                "This is a correlation analysis, not a true causal test. "
                "High divergence is a necessary but not sufficient indicator "
                "of memory influence."
            ),
            "per_agent": [
                {
                    "agent_id": r.agent_id,
                    "mg_status": r.mg_status,
                    "original_decision": r.original_decision,
                    "swapped_decision": r.swapped_decision,
                    "donor_agent_id": r.donor_agent_id,
                    "decision_changed": r.decision_changed,
                    "original_tp": r.original_tp,
                    "swapped_tp": r.swapped_tp,
                }
                for r in self.swap_results
            ],
        }


def select_agents_for_test(
    audit_df: pd.DataFrame,
    year: int = 10,
    n_mg: int = 5,
    n_nmg: int = 5,
) -> Tuple[List[str], List[str]]:
    """Select agents for the substitution test.

    Picks agents at the specified year, balanced by MG status.

    Returns
    -------
    mg_agents, nmg_agents : lists of agent_id strings
    """
    year_df = audit_df[audit_df["year"] == year]
    if year_df.empty:
        return [], []

    mg_col = "mg_status" if "mg_status" in year_df.columns else None
    if mg_col is None:
        # Fallback: treat all as one group
        agents = year_df["agent_id"].unique().tolist()
        half = len(agents) // 2
        return agents[:min(n_mg, half)], agents[half:half + n_nmg]

    mg_agents = (
        year_df[year_df[mg_col] == "MG"]["agent_id"]
        .unique()
        .tolist()[:n_mg]
    )
    nmg_agents = (
        year_df[year_df[mg_col] == "NMG"]["agent_id"]
        .unique()
        .tolist()[:n_nmg]
    )
    return mg_agents, nmg_agents


def create_swap_pairs(
    mg_agents: List[str],
    nmg_agents: List[str],
) -> List[Tuple[str, str]]:
    """Create (target, donor) pairs for memory swapping.

    Each MG agent gets an NMG agent's memories and vice versa.
    This maximizes the difference between original and swapped contexts.
    """
    pairs = []
    # MG targets get NMG donors
    for i, mg_id in enumerate(mg_agents):
        donor = nmg_agents[i % len(nmg_agents)] if nmg_agents else mg_id
        pairs.append((mg_id, donor))
    # NMG targets get MG donors
    for i, nmg_id in enumerate(nmg_agents):
        donor = mg_agents[i % len(mg_agents)] if mg_agents else nmg_id
        pairs.append((nmg_id, donor))
    return pairs


def extract_memory_citations(reasoning: str, memories: List[str]) -> List[str]:
    """Find which memories are referenced in the reasoning text.

    Simple substring matching — checks if any memory content appears
    in the reasoning output.
    """
    cited = []
    if not reasoning:
        return cited
    reasoning_lower = reasoning.lower()
    for mem in memories:
        # Check for key phrases from memory content
        words = mem.lower().split()
        # Use 3-grams for matching
        for i in range(len(words) - 2):
            trigram = " ".join(words[i:i + 3])
            if len(trigram) > 8 and trigram in reasoning_lower:
                cited.append(mem[:100])  # Truncate for report
                break
    return cited


def run_memory_causal_test(
    audit_df: pd.DataFrame,
    memory_snapshots: Optional[Dict[str, List[str]]] = None,
    year: int = 10,
    n_mg: int = 5,
    n_nmg: int = 5,
) -> CausalTestReport:
    """Run the memory-decision divergence analysis (offline).

    Compares decisions of paired agents with different memories and
    demographics at the same time-step. A high divergence rate (>= 70%)
    indicates that memory content *correlates* with decision variation.

    **Limitation**: Because paired agents also differ in persona, state,
    and location, this analysis cannot isolate memory as the sole cause.
    A true causal test would re-run the *same* agent with swapped memories
    (requires live LLM inference — planned as a future extension).

    Parameters
    ----------
    audit_df : DataFrame
        Unified audit data from audit_to_cv.py adapter.
    memory_snapshots : dict, optional
        Agent ID -> list of memory content strings. If not provided,
        the test uses reasoning text analysis only.
    year : int
        Year to test at (default 10 for late-simulation state).
    n_mg, n_nmg : int
        Number of MG and NMG agents to test.

    Returns
    -------
    CausalTestReport
    """
    report = CausalTestReport()

    mg_agents, nmg_agents = select_agents_for_test(
        audit_df, year=year, n_mg=n_mg, n_nmg=n_nmg,
    )

    if not mg_agents and not nmg_agents:
        return report

    pairs = create_swap_pairs(mg_agents, nmg_agents)
    year_df = audit_df[audit_df["year"] == year]

    for target_id, donor_id in pairs:
        target_row = year_df[year_df["agent_id"] == target_id]
        donor_row = year_df[year_df["agent_id"] == donor_id]

        if target_row.empty or donor_row.empty:
            continue

        target_row = target_row.iloc[0]
        donor_row = donor_row.iloc[0]

        # If paired agents with different memories make different
        # decisions, memory content correlates with decision variation.
        # This is a necessary (not sufficient) condition for causality.
        original_dec = str(target_row.get("yearly_decision", ""))
        donor_dec = str(donor_row.get("yearly_decision", ""))

        original_tp = str(target_row.get("threat_appraisal", ""))
        donor_tp = str(donor_row.get("threat_appraisal", ""))

        original_cp = str(target_row.get("coping_appraisal", ""))
        donor_cp = str(donor_row.get("coping_appraisal", ""))

        original_reasoning = str(target_row.get("reasoning", ""))
        donor_reasoning = str(donor_row.get("reasoning", ""))

        mg_status = str(target_row.get("mg_status", "unknown"))

        # Memory citations
        target_memories = (
            memory_snapshots.get(target_id, []) if memory_snapshots else []
        )
        donor_memories = (
            memory_snapshots.get(donor_id, []) if memory_snapshots else []
        )

        result = SwapResult(
            agent_id=target_id,
            mg_status=mg_status,
            year=year,
            original_decision=original_dec,
            swapped_decision=donor_dec,
            donor_agent_id=donor_id,
            decision_changed=(original_dec != donor_dec),
            original_tp=original_tp,
            swapped_tp=donor_tp,
            original_cp=original_cp,
            swapped_cp=donor_cp,
            original_reasoning=original_reasoning,
            swapped_reasoning=donor_reasoning,
            memories_cited_original=extract_memory_citations(
                original_reasoning, target_memories,
            ),
            memories_cited_swapped=extract_memory_citations(
                donor_reasoning, donor_memories,
            ),
        )

        report.swap_results.append(result)

    # Aggregate
    report.n_agents_tested = len(report.swap_results)
    report.n_decisions_changed = sum(
        1 for r in report.swap_results if r.decision_changed
    )
    report.change_rate = (
        report.n_decisions_changed / report.n_agents_tested
        if report.n_agents_tested > 0
        else 0.0
    )
    report.n_mg_changed = sum(
        1 for r in report.swap_results
        if r.decision_changed and r.mg_status == "MG"
    )
    report.n_nmg_changed = sum(
        1 for r in report.swap_results
        if r.decision_changed and r.mg_status == "NMG"
    )
    report.memory_divergence_detected = report.change_rate >= 0.70

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Memory-Decision Divergence Analysis — correlation check"
    )
    parser.add_argument(
        "--trace-dir", type=str, required=True,
        help="Directory containing audit CSVs from a completed experiment",
    )
    parser.add_argument("--year", type=int, default=10)
    parser.add_argument("--n-agents", type=int, default=10)
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSON path (default: trace-dir/memory_causal_test.json)",
    )
    args = parser.parse_args()

    from paper3.analysis.audit_to_cv import load_audit_for_cv

    trace_dir = Path(args.trace_dir)
    df = load_audit_for_cv(str(trace_dir))

    n_per_group = args.n_agents // 2
    report = run_memory_causal_test(
        df, year=args.year, n_mg=n_per_group, n_nmg=n_per_group,
    )

    out_path = Path(args.output) if args.output else trace_dir / "memory_causal_test.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.to_dict(), indent=2))

    status = "DIVERGENCE DETECTED" if report.memory_divergence_detected else "NO DIVERGENCE"
    print(f"Memory-Decision Divergence Analysis: {status}")
    print(f"  Agents tested: {report.n_agents_tested}")
    print(f"  Decisions changed: {report.n_decisions_changed}")
    print(f"  Change rate: {report.change_rate:.1%} (threshold: 70%)")
    print(f"  MG changed: {report.n_mg_changed}, NMG changed: {report.n_nmg_changed}")
    print(f"  Report saved to: {out_path}")


if __name__ == "__main__":
    main()
