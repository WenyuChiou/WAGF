"""
Pilot Experiment Cross-Phase Comparison Analysis
=================================================
Compares Phase A (WARNING baseline), Phase B (BLOCK+retry),
Phase C (+consecutive_cap), Phase D (+zero_escape) results.

Usage:
    python examples/irrigation_abm/analysis/pilot_comparison.py
"""

import json
import pathlib
import sys

import pandas as pd

PILOT_DIR = pathlib.Path(__file__).resolve().parent.parent / "results" / "pilot"
PHASES = ["phase_a", "phase_b", "phase_c", "phase_d"]
PHASE_LABELS = {
    "phase_a": "A: WARNING",
    "phase_b": "B: BLOCK+retry",
    "phase_c": "C: +consec_cap",
    "phase_d": "D: +zero_escape",
}


def load_traces(phase: str) -> pd.DataFrame:
    """Load JSONL traces for a phase, extracting key fields."""
    path = PILOT_DIR / phase / "raw" / "irrigation_farmer_traces.jsonl"
    if not path.exists():
        print(f"[WARN] Missing traces: {path}")
        return pd.DataFrame()
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw = json.loads(line.strip())
            # Extract flat fields for analysis
            sp = raw.get("skill_proposal", {}) or {}
            ar = raw.get("approved_skill", {}) or {}
            rows.append({
                "year": raw.get("year"),
                "agent_id": raw.get("agent_id"),
                "outcome": raw.get("outcome"),
                "skill_name": sp.get("skill_name", ar.get("skill_name", "unknown")),
                "approved_skill": ar.get("skill_name", "unknown"),
                "status": ar.get("status", "unknown"),
                "retry_count": raw.get("retry_count", 0),
                "magnitude_pct": sp.get("magnitude_pct"),
            })
    return pd.DataFrame(rows)


def load_governance(phase: str) -> dict:
    """Load governance summary JSON."""
    path = PILOT_DIR / phase / "governance_summary.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def action_distribution(df: pd.DataFrame) -> dict:
    """Compute action distribution from traces."""
    if df.empty or "skill_name" not in df.columns:
        return {}
    counts = df["skill_name"].value_counts()
    total = counts.sum()
    return {k: {"count": int(v), "pct": round(100 * v / total, 1)} for k, v in counts.items()}


def year_level_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Create per-year action counts."""
    if df.empty:
        return pd.DataFrame()
    year_col = "year" if "year" in df.columns else "loop_year"
    if year_col not in df.columns:
        return pd.DataFrame()
    return df.groupby([year_col, "skill_name"]).size().unstack(fill_value=0)


def compute_increase_rate_by_year(df: pd.DataFrame) -> list:
    """Compute increase_demand proportion per year."""
    if df.empty:
        return []
    year_col = "year" if "year" in df.columns else "loop_year"
    if year_col not in df.columns:
        return []
    rates = []
    for yr in sorted(df[year_col].unique()):
        yr_df = df[df[year_col] == yr]
        total = len(yr_df)
        inc = len(yr_df[yr_df["skill_name"] == "increase_demand"])
        rates.append({"year": yr, "increase_pct": round(100 * inc / total, 1) if total > 0 else 0})
    return rates


def main():
    print("=" * 70)
    print("  IRRIGATION ABM PILOT EXPERIMENT — CROSS-PHASE COMPARISON")
    print("=" * 70)

    # ── Section 1: Governance Summary ──
    print("\n--- 1. GOVERNANCE INTERVENTION SUMMARY ---\n")
    header = f"{'Phase':<25} {'Interventions':>13} {'Retry OK':>10} {'Exhausted':>10} {'Warnings':>10}"
    print(header)
    print("-" * len(header))

    for phase in PHASES:
        gov = load_governance(phase)
        if not gov:
            print(f"{PHASE_LABELS[phase]:<25} {'N/A':>13}")
            continue
        total_intv = gov.get("total_interventions", 0)
        retry_ok = gov.get("outcome_stats", {}).get("retry_success", 0)
        exhausted = gov.get("outcome_stats", {}).get("retry_exhausted", 0)
        warnings = gov.get("warnings", {}).get("total_warnings", 0)
        print(f"{PHASE_LABELS[phase]:<25} {total_intv:>13} {retry_ok:>10} {exhausted:>10} {warnings:>10}")

    # ── Section 2: Rule Frequency ──
    print("\n--- 2. RULE VIOLATION FREQUENCY ---\n")
    all_rules = set()
    gov_data = {}
    for phase in PHASES:
        gov = load_governance(phase)
        gov_data[phase] = gov
        if gov:
            all_rules.update(gov.get("rule_frequency", {}).keys())
            warn_rules = gov.get("warnings", {}).get("warning_rule_frequency", {})
            all_rules.update(warn_rules.keys())

    if all_rules:
        header2 = f"{'Rule':<45} " + " ".join(f"{PHASE_LABELS[p]:>16}" for p in PHASES)
        print(header2)
        print("-" * len(header2))
        for rule in sorted(all_rules):
            vals = []
            for phase in PHASES:
                gov = gov_data.get(phase, {})
                count = gov.get("rule_frequency", {}).get(rule, 0)
                warn_count = gov.get("warnings", {}).get("warning_rule_frequency", {}).get(rule, 0)
                if count > 0:
                    vals.append(f"{count} BLOCK")
                elif warn_count > 0:
                    vals.append(f"{warn_count} WARN")
                else:
                    vals.append("—")
            line = f"{rule:<45} " + " ".join(f"{v:>16}" for v in vals)
            print(line)

    # ── Section 3: Action Distribution ──
    print("\n--- 3. ACTION DISTRIBUTION (% of total decisions) ---\n")
    all_actions = set()
    phase_dists = {}
    for phase in PHASES:
        df = load_traces(phase)
        dist = action_distribution(df)
        phase_dists[phase] = dist
        all_actions.update(dist.keys())

    if all_actions:
        header3 = f"{'Action':<25} " + " ".join(f"{PHASE_LABELS[p]:>16}" for p in PHASES)
        print(header3)
        print("-" * len(header3))
        for action in sorted(all_actions):
            vals = []
            for phase in PHASES:
                d = phase_dists[phase].get(action, {})
                if d:
                    vals.append(f"{d['count']:>3} ({d['pct']:>5.1f}%)")
                else:
                    vals.append("—")
            line = f"{action:<25} " + " ".join(f"{v:>16}" for v in vals)
            print(line)

    # ── Section 4: Year-level increase rate trend ──
    print("\n--- 4. INCREASE_DEMAND RATE BY YEAR (%) ---\n")
    header4 = f"{'Year':<6} " + " ".join(f"{PHASE_LABELS[p]:>16}" for p in PHASES)
    print(header4)
    print("-" * len(header4))

    phase_rates = {}
    for phase in PHASES:
        df = load_traces(phase)
        rates = compute_increase_rate_by_year(df)
        phase_rates[phase] = {r["year"]: r["increase_pct"] for r in rates}

    all_years = set()
    for rates in phase_rates.values():
        all_years.update(rates.keys())

    for yr in sorted(all_years):
        vals = []
        for phase in PHASES:
            r = phase_rates[phase].get(yr)
            if r is not None:
                vals.append(f"{r:>5.1f}%")
            else:
                vals.append("—")
        line = f"{yr:<6} " + " ".join(f"{v:>16}" for v in vals)
        print(line)

    # ── Section 5: Retry Success Rate ──
    print("\n--- 5. GOVERNANCE EFFECTIVENESS SUMMARY ---\n")
    for phase in PHASES:
        gov = gov_data.get(phase, {})
        if not gov:
            continue
        total = gov.get("total_interventions", 0)
        ok = gov.get("outcome_stats", {}).get("retry_success", 0)
        exh = gov.get("outcome_stats", {}).get("retry_exhausted", 0)
        warnings = gov.get("warnings", {}).get("total_warnings", 0)
        attempted = ok + exh
        success_rate = round(100 * ok / attempted, 1) if attempted > 0 else 0
        print(f"  {PHASE_LABELS[phase]}:")
        print(f"    Total interventions: {total}")
        print(f"    Warnings (no retry): {warnings}")
        print(f"    Retry attempts:      {attempted}")
        print(f"    Retry success rate:  {success_rate}% ({ok}/{attempted})")
        print()

    print("=" * 70)
    print("  Analysis complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
