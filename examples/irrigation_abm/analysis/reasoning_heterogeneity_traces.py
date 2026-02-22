"""
Reasoning-Generated Heterogeneity Analysis
===========================================
Find cases where governed agents in the SAME year and SAME shortage tier
make DIFFERENT decisions with qualitatively different reasoning strategies.

Output: 3-5 best paired examples showing diverse reasoning under identical conditions.
"""

import pandas as pd
import re
import textwrap
from pathlib import Path
from itertools import combinations

BASE = Path(__file__).resolve().parent.parent / "results"
SEEDS = [42, 43, 44]


def load_seed(seed: int) -> pd.DataFrame:
    """Load and merge audit + simulation_log for one seed."""
    folder = BASE / f"production_v20_42yr_seed{seed}"
    audit = pd.read_csv(
        folder / "irrigation_farmer_governance_audit.csv",
        encoding="utf-8",
    )
    sim = pd.read_csv(
        folder / "simulation_log.csv",
        encoding="utf-8",
    )
    # Keep relevant sim columns for merge
    sim_cols = sim[["agent_id", "year", "shortage_tier", "lake_mead_level",
                     "curtailment_ratio", "wsa_label"]].copy()
    merged = audit.merge(sim_cols, on=["agent_id", "year"], how="left")
    merged["seed"] = seed
    return merged


def extract_key_sentences(text: str, max_sentences: int = 2) -> str:
    """Extract the most reasoning-rich 1-2 sentences from reasoning text."""
    if pd.isna(text) or not text.strip():
        return "[no reasoning]"
    text = str(text).strip()
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Prefer sentences with reasoning keywords
    keywords = [
        "risk", "conserv", "cautious", "aggressive", "optimi", "pessimi",
        "protect", "exploit", "prudent", "gambl", "hedge", "balance",
        "long-term", "short-term", "neighbor", "community", "system",
        "future", "past", "experience", "curtail", "shortage", "drought",
        "sustain", "surviv", "opportun", "adapt", "resili", "vulnerab",
        "yield", "profit", "loss", "allocat", "scarc", "surplus",
        "uncertain", "forecast", "bet", "wager", "given my",
    ]
    scored = []
    for s in sentences:
        s_lower = s.lower()
        score = sum(1 for kw in keywords if kw in s_lower)
        # Bonus for longer, more substantive sentences
        if len(s.split()) > 8:
            score += 1
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    picked = scored[:max_sentences]
    # Return in original order
    picked_texts = [p[1] for p in picked]
    ordered = [s for s in sentences if s in picked_texts][:max_sentences]
    result = " ".join(ordered)
    # Truncate if still too long
    if len(result) > 350:
        result = result[:347] + "..."
    return result


def classify_reasoning_style(text: str) -> set:
    """Classify reasoning into conceptual categories."""
    if pd.isna(text):
        return set()
    t = str(text).lower()
    tags = set()
    # Risk-averse vs opportunistic
    if any(w in t for w in ["cautious", "conserv", "protect", "risk",
                             "prudent", "hedge", "careful", "safeguard"]):
        tags.add("risk_averse")
    if any(w in t for w in ["opportun", "aggressive", "maximiz", "exploit",
                             "push", "capitalize", "take advantage", "gambl"]):
        tags.add("opportunistic")
    # Past-driven vs forward-looking
    if any(w in t for w in ["experience", "past", "history", "learned",
                             "previously", "last year", "track record"]):
        tags.add("past_driven")
    if any(w in t for w in ["future", "forecast", "anticipat", "expect",
                             "long-term", "outlook", "predict", "prepare"]):
        tags.add("forward_looking")
    # Individual vs system-aware
    if any(w in t for w in ["my yield", "my allocation", "my farm",
                             "my water", "my crop", "personal", "i need"]):
        tags.add("individual_focus")
    if any(w in t for w in ["community", "neighbor", "system", "basin",
                             "collective", "downstream", "other farmer",
                             "shared", "common"]):
        tags.add("system_aware")
    # Conservation vs exploitation
    if any(w in t for w in ["conserv", "reduc", "cut back", "decrease",
                             "save water", "limit", "restrain", "sustain"]):
        tags.add("conservation")
    if any(w in t for w in ["increase", "expand", "grow more", "boost",
                             "ramp up", "intensif"]):
        tags.add("exploitation")
    return tags


def qualitative_distance(tags_a: set, tags_b: set) -> tuple:
    """Score how qualitatively different two reasoning styles are.
    Returns (score, explanation)."""
    # Opposing pairs
    opposites = [
        ("risk_averse", "opportunistic"),
        ("past_driven", "forward_looking"),
        ("individual_focus", "system_aware"),
        ("conservation", "exploitation"),
    ]
    score = 0
    reasons = []
    for a_tag, b_tag in opposites:
        if (a_tag in tags_a and b_tag in tags_b) or \
           (b_tag in tags_a and a_tag in tags_b):
            score += 2
            reasons.append(f"{a_tag} vs {b_tag}")
    # Also reward having different tag sets in general
    symmetric_diff = len(tags_a.symmetric_difference(tags_b))
    score += symmetric_diff * 0.5
    return score, "; ".join(reasons) if reasons else "different reasoning emphasis"


def find_heterogeneity_pairs(df: pd.DataFrame) -> list:
    """Find the best reasoning-heterogeneity pairs within same year+tier."""
    # Filter to approved decisions only
    approved = df[df["status"] == "APPROVED"].copy()

    # Prefer drought years (shortage_tier > 0)
    candidates = []

    for (year, tier), group in approved.groupby(["year", "shortage_tier"]):
        skills_present = group["final_skill"].nunique()
        if skills_present < 2:
            continue  # Need at least 2 different decisions

        # Classify all reasoning
        group = group.copy()
        group["tags"] = group["reason_reasoning"].apply(classify_reasoning_style)

        # Try all pairs of agents with different decisions
        agents = group.to_dict("records")
        for a, b in combinations(agents, 2):
            if a["final_skill"] == b["final_skill"]:
                continue
            dist, explanation = qualitative_distance(a["tags"], b["tags"])
            if dist < 2:
                continue  # Not qualitatively different enough

            mead = a.get("lake_mead_level", 0)
            # Bonus for higher shortage tiers
            priority = dist + (tier * 1.5)

            candidates.append({
                "seed": a["seed"],
                "year": year,
                "tier": int(tier),
                "mead": mead,
                "agent_a_id": a["agent_id"],
                "agent_a_skill": a["final_skill"],
                "agent_a_reasoning": a["reason_reasoning"],
                "agent_a_tags": a["tags"],
                "agent_b_id": b["agent_id"],
                "agent_b_skill": b["final_skill"],
                "agent_b_reasoning": b["reason_reasoning"],
                "agent_b_tags": b["tags"],
                "qual_distance": dist,
                "explanation": explanation,
                "priority": priority,
            })

    # Sort by priority (higher = better)
    candidates.sort(key=lambda x: -x["priority"])
    return candidates


def deduplicate_pairs(all_pairs: list, top_n: int = 5) -> list:
    """Pick top N pairs, ensuring seed diversity and avoiding repeats."""
    selected = []
    used_keys = set()       # (seed, year, tier)
    used_agents = set()     # agent_ids already featured
    seeds_used = {}         # seed -> count (max 2 per seed)

    for p in all_pairs:
        seed = p["seed"]
        key = (seed, p["year"], p["tier"])
        if key in used_keys:
            continue
        # Limit per-seed to encourage cross-seed diversity
        if seeds_used.get(seed, 0) >= 2:
            continue
        # Avoid featuring same agent pair repeatedly
        pair_key = frozenset([p["agent_a_id"], p["agent_b_id"]])
        if p["agent_a_id"] in used_agents and p["agent_b_id"] in used_agents:
            continue

        used_keys.add(key)
        used_agents.add(p["agent_a_id"])
        used_agents.add(p["agent_b_id"])
        seeds_used[seed] = seeds_used.get(seed, 0) + 1
        selected.append(p)
        if len(selected) >= top_n:
            break
    return selected


def main():
    print("=" * 80)
    print("REASONING-GENERATED HETEROGENEITY IN GOVERNED IRRIGATION AGENTS")
    print("=" * 80)
    print()
    print("Finding cases where agents in the SAME year and SAME shortage tier")
    print("make DIFFERENT decisions with qualitatively different reasoning.\n")

    all_pairs = []
    for seed in SEEDS:
        print(f"Loading seed {seed}...")
        df = load_seed(seed)
        approved_count = (df["status"] == "APPROVED").sum()
        total = len(df)
        print(f"  {total} rows, {approved_count} APPROVED")

        # Show year-tier diversity stats
        approved = df[df["status"] == "APPROVED"]
        diverse = approved.groupby(["year", "shortage_tier"])["final_skill"].nunique()
        diverse_count = (diverse >= 2).sum()
        print(f"  {diverse_count} year-tier combos with 2+ different decisions")

        pairs = find_heterogeneity_pairs(df)
        print(f"  {len(pairs)} candidate heterogeneity pairs found")
        all_pairs.extend(pairs)

    print(f"\nTotal candidate pairs across all seeds: {len(all_pairs)}")
    best = deduplicate_pairs(all_pairs, top_n=5)

    print(f"\n{'=' * 80}")
    print(f"TOP {len(best)} REASONING-HETEROGENEITY EXAMPLES")
    print(f"{'=' * 80}\n")

    for i, p in enumerate(best, 1):
        print(f"--- Example {i} ---")
        print(f"Seed: {p['seed']} | Year: {p['year']} | "
              f"Shortage Tier: {p['tier']} | Mead: {p['mead']:.1f} ft")
        print()

        excerpt_a = extract_key_sentences(p["agent_a_reasoning"])
        excerpt_b = extract_key_sentences(p["agent_b_reasoning"])

        print(f"Agent A: {p['agent_a_id']} | Decision: {p['agent_a_skill']}")
        wrapped_a = textwrap.fill(f'Reasoning: "{excerpt_a}"', width=90,
                                   subsequent_indent="  ")
        print(wrapped_a)
        print(f"  Tags: {p['agent_a_tags']}")
        print()

        print(f"Agent B: {p['agent_b_id']} | Decision: {p['agent_b_skill']}")
        wrapped_b = textwrap.fill(f'Reasoning: "{excerpt_b}"', width=90,
                                   subsequent_indent="  ")
        print(wrapped_b)
        print(f"  Tags: {p['agent_b_tags']}")
        print()

        print(f"Why this pair matters: {p['explanation']} "
              f"(qualitative distance: {p['qual_distance']:.1f})")
        print()

    # Summary statistics
    print(f"\n{'=' * 80}")
    print("SUMMARY STATISTICS")
    print(f"{'=' * 80}")
    tag_counts = {}
    for p in all_pairs:
        for t in p["agent_a_tags"] | p["agent_b_tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    print("\nReasoning style frequency across all heterogeneous pairs:")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        print(f"  {tag:25s}: {count}")


if __name__ == "__main__":
    main()
