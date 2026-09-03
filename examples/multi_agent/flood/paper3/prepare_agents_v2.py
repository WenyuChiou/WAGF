"""
Paper 3 v2: tenure-balanced population generator.

MG is retained only as a backward-compatible reference column. This script does
not use MG to sample the population or to stratify the conditional construct
draw; the v2 design axis is TENURE (Owner/Renter).

Outputs:
    data/agent_profiles_v2.csv
    data/initial_memories_v2.json

Usage:
    python paper3/prepare_agents_v2.py --seed 42 --n-per-cell 200
    python paper3/prepare_agents_v2.py --seed 42 --large-n
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Add flood package root to path.
FLOOD_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FLOOD_DIR))

from generate_agents import HouseholdProfile, save_agents_to_csv
from paper3.prepare_balanced_agents import (
    DEFAULT_PRB_DIR,
    assign_flood_zones,
    generate_initial_memory,
)


TENURE_ORDER = ("Owner", "Renter")
INCOME_TERTILES = ("low", "mid", "high")
CONSTRUCT_COLUMNS = ("sc_score", "pa_score", "tp_score", "cp_score", "sp_score")

# Bracket bounds preserve the existing midpoint convention while adding seeded,
# within-bracket variation. Open-ended survey brackets use bounded support that
# keeps values compatible with the flood profile schema.
INCOME_BRACKET_BOUNDS = {
    "Less than $25,000": (20_000.0, 24_999.99),
    "$25,000 to $29,999": (25_000.0, 29_999.99),
    "$30,000 to $34,999": (30_000.0, 34_999.99),
    "$35,000 to $39,999": (35_000.0, 39_999.99),
    "$40,000 to $44,999": (40_000.0, 44_999.99),
    "$45,000 to $49,999": (45_000.0, 49_999.99),
    "$50,000 to $54,999": (50_000.0, 54_999.99),
    "$55,000 to $59,999": (55_000.0, 59_999.99),
    "$60,000 to $74,999": (60_000.0, 74_999.99),
    "More than $74,999": (75_000.0, 125_000.0),
}

POVERTY_150_PCT = {
    1: 22_110,
    2: 29_940,
    3: 37_770,
    4: 45_600,
    5: 53_430,
    6: 61_260,
    7: 69_090,
    8: 76_920,
}


@dataclass
class ConstructPools:
    """Survey-row pools for the conditional construct draw."""

    full: dict[tuple[str, str, bool], list[dict[str, Any]]]
    tenure_flood: dict[tuple[str, bool], list[dict[str, Any]]]
    tenure: dict[str, list[dict[str, Any]]]
    full_counts: dict[tuple[str, str, bool], int]
    income_cuts: tuple[float, float]


def _as_bool(value: Any, default: bool = False) -> bool:
    """Parse CSV bool-ish values without letting NaN become True."""
    if value is None or pd.isna(value):
        return default
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1"}:
        return True
    if text in {"false", "no", "n", "0", ""}:
        return False
    return default


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or pd.isna(value):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def _normalize_tenure(value: Any) -> str:
    return "Renter" if str(value).strip().lower() == "renter" else "Owner"


def _income_tertile(income: float, cuts: tuple[float, float]) -> str:
    if income <= cuts[0]:
        return "low"
    if income <= cuts[1]:
        return "mid"
    return "high"


def _jitter_income(row: dict[str, Any], rng: random.Random) -> float:
    bracket = str(row.get("income_bracket", "")).strip()
    midpoint = _as_float(row.get("income"), 50_000.0)
    lower, upper = INCOME_BRACKET_BOUNDS.get(
        bracket,
        (max(0.0, midpoint - 2_500.0), midpoint + 2_500.0),
    )
    jittered = midpoint + rng.uniform(lower - midpoint, upper - midpoint)
    return round(min(max(jittered, lower), upper), 2)


def _compute_mg_reference(row: dict[str, Any], income: float) -> tuple[bool, int]:
    """Recompute the legacy MG reference from the existing 2-of-3 criteria."""
    criteria_met = 0
    if _as_bool(row.get("housing_cost_burden")):
        criteria_met += 1
    if not _as_bool(row.get("has_vehicle"), default=True):
        criteria_met += 1

    household_size = max(1, min(8, _as_int(row.get("household_size"), 3)))
    poverty_line = POVERTY_150_PCT.get(household_size, POVERTY_150_PCT[4])
    if income < poverty_line:
        criteria_met += 1

    return criteria_met >= 2, criteria_met


def _sample_by_tenure(
    survey_df: pd.DataFrame,
    n_per_cell: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    sampled: list[dict[str, Any]] = []
    cell_counts: dict[str, int] = {}
    shortfalls: dict[str, int] = {}

    for tenure in TENURE_ORDER:
        members = survey_df[survey_df["tenure"].map(_normalize_tenure) == tenure]
        records = members.to_dict("records")
        available = len(records)
        if available == 0:
            raise ValueError(f"No survey respondents available for tenure={tenure}")

        if available >= n_per_cell:
            selected = rng.sample(records, n_per_cell)
        else:
            selected = [rng.choice(records) for _ in range(n_per_cell)]
            shortfalls[tenure] = n_per_cell - available

        sampled.extend(dict(row) for row in selected)
        cell_counts[tenure] = len(selected)

    return sampled, cell_counts, shortfalls


def _build_construct_pools(survey_df: pd.DataFrame) -> ConstructPools:
    cuts = tuple(float(x) for x in survey_df["income"].quantile([1 / 3, 2 / 3]))
    full: dict[tuple[str, str, bool], list[dict[str, Any]]] = defaultdict(list)
    tenure_flood: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    tenure_only: dict[str, list[dict[str, Any]]] = defaultdict(list)

    required = ["tenure", "income", "flood_experience", *CONSTRUCT_COLUMNS]
    clean_df = survey_df.dropna(subset=required).copy()

    for row in clean_df.to_dict("records"):
        tenure = _normalize_tenure(row.get("tenure"))
        flood = _as_bool(row.get("flood_experience"))
        tertile = _income_tertile(_as_float(row.get("income"), 50_000.0), cuts)
        full[(tenure, tertile, flood)].append(row)
        tenure_flood[(tenure, flood)].append(row)
        tenure_only[tenure].append(row)

    full_counts = {}
    for tenure in TENURE_ORDER:
        for tertile in INCOME_TERTILES:
            for flood in (False, True):
                key = (tenure, tertile, flood)
                full_counts[key] = len(full.get(key, []))

    return ConstructPools(
        full=dict(full),
        tenure_flood=dict(tenure_flood),
        tenure=dict(tenure_only),
        full_counts=full_counts,
        income_cuts=cuts,
    )


def _draw_construct_vector(
    tenure: str,
    income: float,
    flood_experience: bool,
    pools: ConstructPools,
    rng: random.Random,
    fallback_counts: Counter,
    thin_hits: Counter,
) -> dict[str, float]:
    tertile = _income_tertile(income, pools.income_cuts)
    full_key = (tenure, tertile, flood_experience)
    full_pool = pools.full.get(full_key, [])

    if len(full_pool) >= 5:
        fallback_counts["full"] += 1
        chosen = rng.choice(full_pool)
    else:
        thin_hits[f"{tenure}/{tertile}/flood={flood_experience}"] += 1
        tf_key = (tenure, flood_experience)
        tf_pool = pools.tenure_flood.get(tf_key, [])
        if len(tf_pool) >= 5:
            fallback_counts["tenure_flood"] += 1
            chosen = rng.choice(tf_pool)
        else:
            tenure_pool = pools.tenure.get(tenure, [])
            if not tenure_pool:
                raise ValueError(f"No survey rows available for tenure fallback: {tenure}")
            fallback_counts["tenure_only"] += 1
            chosen = rng.choice(tenure_pool)

    return {col: round(_as_float(chosen.get(col), 3.0), 2) for col in CONSTRUCT_COLUMNS}


def _generate_rcv_seeded(
    tenure: str, income: float, mg: bool, np_rng: np.random.Generator
) -> tuple[float, float]:
    """Reproducible RCV — mirrors generate_agents.generate_rcv but draws from a
    SEEDED per-agent Generator instead of the global np.random / random state.

    Review C1 (2026-06-11): the imported generate_rcv used unseeded
    np.random.lognormal/normal + random.uniform, so RCV was reproducible only
    under the exact import/call order of the original run. Drawing from a
    per-agent Generator keyed on (seed, agent_id) makes RCV byte-reproducible
    independent of global state, import order, or parallel use.
    """
    if tenure == "Owner":
        mu_bld = 280_000 if mg else 400_000
        rcv_bld = float(np_rng.lognormal(np.log(mu_bld), 0.3))
        rcv_bld = min(max(rcv_bld, 100_000), 1_000_000)
        rcv_cnt = rcv_bld * float(np_rng.uniform(0.30, 0.50))
    else:
        rcv_bld = 0.0
        base_contents = 20_000 + (income / 100_000) * 40_000
        rcv_cnt = float(np_rng.normal(base_contents, 5_000))
        rcv_cnt = min(max(rcv_cnt, 10_000), 80_000)
    return round(rcv_bld, 2), round(rcv_cnt, 2)


def _profile_from_row(
    row: dict[str, Any],
    agent_id: str,
    income: float,
    constructs: dict[str, float],
    seed: int,
) -> HouseholdProfile:
    tenure = _normalize_tenure(row.get("tenure"))
    mg, _criteria_count = _compute_mg_reference(row, income)
    # Per-agent deterministic RNG keyed on (seed, agent_id): order-independent.
    np_rng = np.random.default_rng(zlib.crc32(f"{seed}:{agent_id}".encode()))
    rcv_bld, rcv_cnt = _generate_rcv_seeded(tenure, income, mg, np_rng)

    insurance_type = _clean_text(row.get("insurance_type"))
    has_insurance = "flood" in insurance_type.lower() or "nfip" in insurance_type.lower()

    return HouseholdProfile(
        agent_id=agent_id,
        survey_id=_clean_text(row.get("survey_id")),
        tract_id="PRB",
        mg=mg,
        tenure=tenure,
        income_bracket=_clean_text(row.get("income_bracket")),
        income=income,
        household_size=_as_int(row.get("household_size"), 3),
        generations=_as_int(row.get("generations"), 1),
        has_vehicle=_as_bool(row.get("has_vehicle"), default=True),
        has_children=_as_bool(row.get("has_children")),
        has_elderly=_as_bool(row.get("has_elderly")),
        housing_cost_burden=_as_bool(row.get("housing_cost_burden")),
        mg_criteria_met=mg,
        zipcode=_clean_text(row.get("zipcode")),
        flood_experience=_as_bool(row.get("flood_experience")),
        flood_frequency=_as_int(row.get("flood_frequency"), 0),
        sfha_awareness=_as_bool(row.get("sfha_awareness")),
        sc_score=constructs["sc_score"],
        pa_score=constructs["pa_score"],
        tp_score=constructs["tp_score"],
        cp_score=constructs["cp_score"],
        sp_score=constructs["sp_score"],
        rcv_building=rcv_bld,
        rcv_contents=rcv_cnt,
        elevated=False,
        has_insurance=has_insurance,
        relocated=False,
        cumulative_damage=0.0,
        cumulative_oop=0.0,
        recent_flood_text=_clean_text(row.get("recent_flood_text")),
        insurance_type=insurance_type,
        post_flood_action=_clean_text(row.get("post_flood_action")),
    )


def _print_thin_strata(full_counts: dict[tuple[str, str, bool], int]) -> None:
    thin = {key: count for key, count in full_counts.items() if count < 5}
    if not thin:
        print("  Full conditional strata with <5 survey rows: none")
        return

    print("  Full conditional strata with <5 survey rows:")
    for key, count in thin.items():
        tenure, tertile, flood = key
        print(f"    {tenure}/{tertile}/flood={flood}: {count}")


def prepare_agents_v2(
    survey_csv: str | Path,
    output_dir: str | Path,
    n_per_cell: int = 200,
    seed: int = 42,
) -> tuple[list[HouseholdProfile], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Generate the v2 tenure-balanced population and initial memories."""
    rng = random.Random(seed)
    random.seed(seed)
    np.random.seed(seed)

    survey_path = Path(survey_csv)
    out_dir = Path(output_dir)

    print(f"[Step 1] Loading survey data from {survey_path}")
    survey_df = pd.read_csv(survey_path)
    survey_df["tenure"] = survey_df["tenure"].map(_normalize_tenure)
    print(f"  Loaded {len(survey_df)} respondents")
    print(f"  Survey tenure counts: {survey_df['tenure'].value_counts().to_dict()}")

    print(f"\n[Step 2] Tenure-balanced sampling ({n_per_cell} per tenure cell)")
    sampled, cell_counts, shortfalls = _sample_by_tenure(survey_df, n_per_cell, rng)
    print(f"  Cell counts: {cell_counts}")
    if shortfalls:
        print(f"  [WARN] Oversampled tenure shortfalls: {shortfalls}")

    print("\n[Step 3] Building conditional construct pools")
    pools = _build_construct_pools(survey_df)
    print(f"  Income tertile cuts: {pools.income_cuts}")
    _print_thin_strata(pools.full_counts)

    print("\n[Step 4] Creating HouseholdProfile objects with continuous income")
    fallback_counts: Counter = Counter({"full": 0, "tenure_flood": 0, "tenure_only": 0})
    thin_hits: Counter = Counter()
    agents: list[HouseholdProfile] = []

    for idx, row in enumerate(sampled):
        tenure = _normalize_tenure(row.get("tenure"))
        income = _jitter_income(row, rng)
        flood = _as_bool(row.get("flood_experience"))
        constructs = _draw_construct_vector(
            tenure=tenure,
            income=income,
            flood_experience=flood,
            pools=pools,
            rng=rng,
            fallback_counts=fallback_counts,
            thin_hits=thin_hits,
        )
        agents.append(_profile_from_row(row, f"H{idx + 1:04d}", income, constructs, seed))

    print(f"  Generated {len(agents)} profiles")
    print(f"  Conditional construct draw levels: {dict(fallback_counts)}")
    if thin_hits:
        print(f"  Thin full-stratum draw hits: {dict(sorted(thin_hits.items()))}")
    else:
        print("  Thin full-stratum draw hits: none")

    print("\n[Step 5] Assigning flood zones from PRB raster")
    agents = assign_flood_zones(agents, rng=rng, prb_dir=DEFAULT_PRB_DIR)

    out_dir.mkdir(parents=True, exist_ok=True)
    profiles_path = out_dir / "agent_profiles_v2.csv"
    memories_path = out_dir / "initial_memories_v2.json"

    print("\n[Step 6] Saving agent profiles")
    save_agents_to_csv(agents, profiles_path)

    print("\n[Step 7] Generating initial memories (6 per agent)")
    all_memories: dict[str, list[dict[str, Any]]] = {}
    for agent in agents:
        all_memories[agent.agent_id] = generate_initial_memory(agent)

    with open(memories_path, "w", encoding="utf-8") as f:
        json.dump(all_memories, f, indent=2, ensure_ascii=False)
    print(f"  Saved {sum(len(v) for v in all_memories.values())} memories to {memories_path}")

    summary = {
        "seed": seed,
        "n_per_cell": n_per_cell,
        "cell_counts": cell_counts,
        "shortfalls": shortfalls,
        "income_tertile_cuts": pools.income_cuts,
        "fallback_counts": dict(fallback_counts),
        "thin_full_strata": {
            f"{k[0]}/{k[1]}/flood={k[2]}": v
            for k, v in pools.full_counts.items()
            if v < 5
        },
        "thin_full_stratum_hits": dict(sorted(thin_hits.items())),
        "profiles_path": str(profiles_path),
        "memories_path": str(memories_path),
    }

    print(f"\n{'=' * 60}")
    print(f"  Paper 3 v2 Population Complete (seed={seed})")
    print(f"{'=' * 60}")
    print(f"  Total agents: {len(agents)}")
    print(f"  Owners:  {sum(1 for a in agents if a.tenure == 'Owner')}")
    print(f"  Renters: {sum(1 for a in agents if a.tenure == 'Renter')}")
    print(f"  Income unique values: {len({a.income for a in agents})}")
    print(f"  Fallback counts: {dict(fallback_counts)}")
    print("  Files:")
    print(f"    {profiles_path}")
    print(f"    {memories_path}")

    return agents, all_memories, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper 3 v2 tenure-balanced population generator")
    parser.add_argument("--survey", type=str, default=None, help="Path to cleaned_survey_full.csv")
    parser.add_argument(
        "--output",
        "--output-dir",
        dest="output_dir",
        type=str,
        default=None,
        help="Output directory for profiles and memories",
    )
    parser.add_argument("--n-per-cell", type=int, default=200, help="Agents per tenure cell")
    parser.add_argument(
        "--large-n",
        action="store_true",
        help="Set n-per-cell to 1000 for the parametric reference population",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    n_per_cell = 1000 if args.large_n else args.n_per_cell
    survey_csv = args.survey or FLOOD_DIR / "data" / "cleaned_survey_full.csv"
    output_dir = args.output_dir or FLOOD_DIR / "data"

    prepare_agents_v2(
        survey_csv=survey_csv,
        output_dir=output_dir,
        n_per_cell=n_per_cell,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
