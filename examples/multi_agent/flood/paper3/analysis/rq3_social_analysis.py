#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RQ3: Social Information Channel Diffusion Analysis
===================================================
Which social information channel accelerates adaptation diffusion?

Three channels:
  1. Gossip (neighbor-to-neighbor): "Neighbor Hxxxx mentioned: ..."
  2. Social media: "[SOCIAL] ..." posts in LOCAL NEIGHBORHOOD
  3. News media: government/FEMA/NFIP updates, flood warnings, media reports

Analyses:
  (A) Channel citation frequency per year
  (B) Post-flood citation spikes
  (C) Decision correlation with channel citation
  (D) First-mover vs follower analysis
  (E) Spatial autocorrelation (Moran's I) of adaptation
  (F) Behavioral diffusion speed (time-to-adoption, Kaplan-Meier)
  (G) Decision diversity (Shannon entropy)

Data: Paper 3 primary experiment, seed_42, gemma3_4b_strict
"""

import json
import csv
import re
import os
import sys
import math
import warnings
from collections import defaultdict, Counter
from pathlib import Path

import numpy as np

# Matplotlib config
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework")
RESULT_DIR = BASE / "examples" / "multi_agent" / "flood" / "paper3" / "results" / "paper3_primary" / "seed_42"
RAW_DIR = RESULT_DIR / "gemma3_4b_strict" / "raw"
AUDIT_DIR = RESULT_DIR / "gemma3_4b_strict"
DATA_DIR = BASE / "examples" / "multi_agent" / "flood" / "data"
OUT_DIR = RESULT_DIR / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OWNER_TRACES = RAW_DIR / "household_owner_traces.jsonl"
RENTER_TRACES = RAW_DIR / "household_renter_traces.jsonl"
OWNER_AUDIT = AUDIT_DIR / "household_owner_governance_audit.csv"
RENTER_AUDIT = AUDIT_DIR / "household_renter_governance_audit.csv"
PROFILES_CSV = DATA_DIR / "agent_profiles_balanced.csv"

# ---------------------------------------------------------------------------
# Regex patterns for channel detection in LLM reasoning
# ---------------------------------------------------------------------------
GOSSIP_RE = re.compile(
    r"neighbor|gossip|community\s+(?:member|input|mention|report)"
    r"|word.of.mouth|local\s+(?:resident|people|report)"
    r"|fellow\s+(?:resident|homeowner)",
    re.IGNORECASE
)
SOCIAL_MEDIA_RE = re.compile(
    r"social\s+media|social\s+post|social\s+(?:report|commentary|update|network)"
    r"|online\s+(?:report|post|update|discussion)"
    r"|facebook|twitter|nextdoor",
    re.IGNORECASE
)
NEWS_MEDIA_RE = re.compile(
    r"news\s+(?:report|media|coverage|outlet|article)"
    r"|media\s+report|government\s+(?:report|announcement|warning|update)"
    r"|official\s+(?:report|warning|flood)|fema\s+(?:report|update|warning)"
    r"|nfip\s+(?:update|report)|flood\s+warning|emergency\s+(?:alert|report)"
    r"|press|broadcast",
    re.IGNORECASE
)

# Protective actions
OWNER_PROTECTIVE = {"buy_insurance", "elevate_house", "buyout_program"}
RENTER_PROTECTIVE = {"buy_contents_insurance", "relocate"}
ALL_PROTECTIVE = OWNER_PROTECTIVE | RENTER_PROTECTIVE

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def load_traces(filepath):
    """Load JSONL trace file -> list of dicts."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_audit(filepath):
    """Load governance audit CSV -> list of dicts."""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_profiles(filepath):
    """Load agent profiles CSV -> dict keyed by agent_id."""
    profiles = {}
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            profiles[row["agent_id"]] = row
    return profiles


# ---------------------------------------------------------------------------
# (A) Channel detection in reasoning text
# ---------------------------------------------------------------------------

def detect_channels_audit(audit_rows, tenure):
    """
    Parse reasoning fields in audit CSV to detect channel citations.
    Returns list of dicts: {agent_id, year, gossip, social_media, news_media, decision, status}
    """
    results = []
    for row in audit_rows:
        year = int(row["year"])
        agent_id = row["agent_id"]

        # Collect all reasoning text
        if tenure == "Owner":
            text_fields = [
                row.get("reason_reasoning", ""),
                row.get("reason_tp_reason", ""),
                row.get("reason_cp_reason", ""),
                row.get("reason_sc_reason", ""),
                row.get("reason_sp_reason", ""),
                row.get("reason_pa_reason", ""),
            ]
        else:
            text_fields = [
                row.get("reason_reasoning", ""),
                row.get("reason_reason", ""),
            ]

        all_text = " ".join(t for t in text_fields if t)

        gossip = bool(GOSSIP_RE.search(all_text))
        social_media = bool(SOCIAL_MEDIA_RE.search(all_text))
        news_media = bool(NEWS_MEDIA_RE.search(all_text))

        decision = row.get("final_skill", row.get("proposed_skill", "unknown"))
        status = row.get("status", "")

        results.append({
            "agent_id": agent_id,
            "year": year,
            "gossip": gossip,
            "social_media": social_media,
            "news_media": news_media,
            "decision": decision,
            "status": status,
            "tenure": tenure,
        })
    return results


def detect_channels_traces(traces, tenure):
    """
    Parse input prompts in JSONL traces to detect social information
    *provided* to agents (not just cited in reasoning).
    Returns per-agent-year info about what social content was in the prompt.
    """
    results = []
    for rec in traces:
        year = rec["year"]
        agent_id = rec["agent_id"]
        inp = rec.get("input", "")

        # Count neighbor gossip lines
        gossip_lines = re.findall(r"Neighbor\s+H\d+\s+mentioned:", inp)
        n_gossip = len(gossip_lines)

        # Count [SOCIAL] posts
        social_lines = re.findall(r"\[SOCIAL\]", inp)
        n_social = len(social_lines)

        # Check for news/policy content
        has_news = bool(re.search(
            r"NJ Government|FEMA/NFIP|NJDEP|Blue Acres|POLICY UPDATE",
            inp
        ))

        # Get flood-related state
        sb = rec.get("state_before", {})
        flooded = sb.get("flooded_this_year", False) if isinstance(sb, dict) else False
        flood_count = sb.get("flood_count", 0) if isinstance(sb, dict) else 0

        results.append({
            "agent_id": agent_id,
            "year": year,
            "n_gossip": n_gossip,
            "n_social": n_social,
            "has_news": has_news,
            "flooded_this_year": flooded,
            "flood_count": flood_count,
            "tenure": tenure,
        })
    return results


# ---------------------------------------------------------------------------
# (E) Spatial autocorrelation -- Moran's I
# ---------------------------------------------------------------------------

def compute_morans_i(values, coords, k=8):
    """
    Compute Moran's I for spatial autocorrelation using k-nearest-neighbors
    weight matrix.

    Parameters
    ----------
    values : np.ndarray, shape (n,)
        Binary or continuous variable.
    coords : np.ndarray, shape (n, 2)
        [x, y] or [lon, lat].
    k : int
        Number of nearest neighbors.

    Returns
    -------
    float : Moran's I statistic
    float : expected I under randomness
    float : z-score
    """
    n = len(values)
    if n < 5:
        return np.nan, np.nan, np.nan

    mean_val = np.mean(values)
    z = values - mean_val
    ss = np.sum(z ** 2)
    if ss == 0:
        return np.nan, np.nan, np.nan

    # Build k-NN weight matrix
    from scipy.spatial import cKDTree
    tree = cKDTree(coords)
    k_actual = min(k, n - 1)
    _, indices = tree.query(coords, k=k_actual + 1)  # includes self

    W = np.zeros((n, n))
    for i in range(n):
        for j_idx in indices[i, 1:]:  # skip self
            W[i, j_idx] = 1.0

    # Row-standardize
    row_sums = W.sum(axis=1)
    row_sums[row_sums == 0] = 1
    W = W / row_sums[:, np.newaxis]

    S0 = W.sum()
    num = n * np.sum(W * np.outer(z, z))
    I = num / (S0 * ss)

    EI = -1.0 / (n - 1)
    # Variance under normality assumption
    S1 = 0.5 * np.sum((W + W.T) ** 2)
    S2 = np.sum((W.sum(axis=1) + W.sum(axis=0)) ** 2)
    k2 = (np.sum(z ** 4) / n) / ((np.sum(z ** 2) / n) ** 2)
    A = n * ((n ** 2 - 3 * n + 3) * S1 - n * S2 + 3 * S0 ** 2)
    B = k2 * ((n ** 2 - n) * S1 - 2 * n * S2 + 6 * S0 ** 2)
    C = (n - 1) * (n - 2) * (n - 3) * S0 ** 2
    VarI = (A - B) / C - EI ** 2
    VarI = max(VarI, 1e-12)

    z_score = (I - EI) / math.sqrt(VarI)
    return I, EI, z_score


# ---------------------------------------------------------------------------
# (F) Kaplan-Meier survival estimate
# ---------------------------------------------------------------------------

def kaplan_meier(event_times, censor_time=13):
    """
    Simple Kaplan-Meier survival estimate.
    event_times: list of ints (year of first adoption; censor_time if never adopted)
    Returns times, survival probabilities.
    """
    n = len(event_times)
    if n == 0:
        return [], []
    events = sorted(event_times)
    times = sorted(set(t for t in events if t <= censor_time))
    surv = 1.0
    result_t = [0]
    result_s = [1.0]
    at_risk = n
    for t in times:
        d = sum(1 for e in events if e == t and e < censor_time)
        c = sum(1 for e in events if e == t and e == censor_time)
        if at_risk > 0 and d > 0:
            surv *= (1 - d / at_risk)
        at_risk -= (d + c)
        result_t.append(t)
        result_s.append(surv)
    return result_t, result_s


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def main():
    print("=" * 72)
    print("RQ3: Social Information Channel Diffusion Analysis")
    print("=" * 72)

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    print("\n[1] Loading data...")
    owner_traces = load_traces(OWNER_TRACES)
    renter_traces = load_traces(RENTER_TRACES)
    owner_audit = load_audit(OWNER_AUDIT)
    renter_audit = load_audit(RENTER_AUDIT)
    profiles = load_profiles(PROFILES_CSV)

    print(f"  Owner traces:  {len(owner_traces):,} records")
    print(f"  Renter traces: {len(renter_traces):,} records")
    print(f"  Owner audit:   {len(owner_audit):,} rows")
    print(f"  Renter audit:  {len(renter_audit):,} rows")
    print(f"  Agent profiles: {len(profiles)} agents")

    # ------------------------------------------------------------------
    # (A) Channel detection from reasoning
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[A] CHANNEL CITATION FREQUENCY IN AGENT REASONING")
    print("=" * 72)

    owner_channels = detect_channels_audit(owner_audit, "Owner")
    renter_channels = detect_channels_audit(renter_audit, "Renter")
    all_channels = owner_channels + renter_channels

    # Aggregate by year
    years = sorted(set(r["year"] for r in all_channels))
    channel_by_year = {y: {"gossip": 0, "social_media": 0, "news_media": 0, "total": 0}
                       for y in years}

    for r in all_channels:
        y = r["year"]
        channel_by_year[y]["total"] += 1
        if r["gossip"]:
            channel_by_year[y]["gossip"] += 1
        if r["social_media"]:
            channel_by_year[y]["social_media"] += 1
        if r["news_media"]:
            channel_by_year[y]["news_media"] += 1

    print(f"\n{'Year':>4}  {'Gossip':>8}  {'SocMedia':>8}  {'NewsMed':>8}  {'Total':>6}")
    print("-" * 48)
    gossip_pcts, social_pcts, news_pcts = [], [], []
    for y in years:
        c = channel_by_year[y]
        t = c["total"]
        gp = 100 * c["gossip"] / t if t else 0
        sp = 100 * c["social_media"] / t if t else 0
        np_ = 100 * c["news_media"] / t if t else 0
        gossip_pcts.append(gp)
        social_pcts.append(sp)
        news_pcts.append(np_)
        print(f"  {y:2d}   {gp:6.1f}%   {sp:6.1f}%   {np_:6.1f}%   {t:5d}")

    # Separate by tenure
    for tenure_label in ["Owner", "Renter"]:
        subset = [r for r in all_channels if r["tenure"] == tenure_label]
        g = sum(1 for r in subset if r["gossip"])
        s = sum(1 for r in subset if r["social_media"])
        n = sum(1 for r in subset if r["news_media"])
        t = len(subset)
        print(f"\n  {tenure_label}: gossip={100*g/t:.1f}%, social_media={100*s/t:.1f}%, news_media={100*n/t:.1f}% (n={t})")

    # ------------------------------------------------------------------
    # Identify flood years from traces
    # ------------------------------------------------------------------
    flood_intensity = {}
    for rec in owner_traces + renter_traces:
        y = rec["year"]
        sb = rec.get("state_before", {})
        if isinstance(sb, dict):
            flooded = sb.get("flooded_this_year", False)
            if y not in flood_intensity:
                flood_intensity[y] = {"flooded": 0, "total": 0}
            flood_intensity[y]["total"] += 1
            if flooded:
                flood_intensity[y]["flooded"] += 1

    print("\n  Flood intensity by year:")
    flood_years_major = []
    for y in sorted(flood_intensity.keys()):
        fi = flood_intensity[y]
        pct = 100 * fi["flooded"] / fi["total"] if fi["total"] else 0
        tag = " ** MAJOR" if pct > 30 else ""
        if pct > 30:
            flood_years_major.append(y)
        print(f"    Y{y:2d}: {fi['flooded']:3d}/{fi['total']:3d} flooded ({pct:5.1f}%){tag}")

    # ------------------------------------------------------------------
    # (B) Post-flood citation spike analysis
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[B] POST-FLOOD CITATION SPIKE ANALYSIS")
    print("=" * 72)

    # Compute channel citation rate in year AFTER vs BEFORE major floods
    for channel_name in ["gossip", "social_media", "news_media"]:
        pre_rates, post_rates = [], []
        for fy in flood_years_major:
            if fy - 1 in channel_by_year and fy + 1 in channel_by_year:
                pre = channel_by_year[fy - 1]
                post = channel_by_year[fy + 1]
                pre_rate = pre[channel_name] / pre["total"] if pre["total"] else 0
                post_rate = post[channel_name] / post["total"] if post["total"] else 0
                pre_rates.append(pre_rate)
                post_rates.append(post_rate)

        if pre_rates:
            mean_pre = np.mean(pre_rates)
            mean_post = np.mean(post_rates)
            change = mean_post - mean_pre
            print(f"\n  {channel_name}:")
            print(f"    Pre-flood avg:  {100*mean_pre:.1f}%")
            print(f"    Post-flood avg: {100*mean_post:.1f}%")
            print(f"    Change:         {100*change:+.1f} pp")

    # Agent-level: did agents who were flooded cite more social sources?
    # Build per-agent-year flooded status from traces
    agent_flooded = {}
    for rec in owner_traces + renter_traces:
        key = (rec["agent_id"], rec["year"])
        sb = rec.get("state_before", {})
        if isinstance(sb, dict):
            agent_flooded[key] = sb.get("flooded_this_year", False)

    flooded_cites = {"gossip": [0, 0], "social_media": [0, 0], "news_media": [0, 0]}  # [cite_count, total]
    nonflooded_cites = {"gossip": [0, 0], "social_media": [0, 0], "news_media": [0, 0]}

    for r in all_channels:
        key = (r["agent_id"], r["year"])
        was_flooded = agent_flooded.get(key, False)
        target = flooded_cites if was_flooded else nonflooded_cites
        for ch in ["gossip", "social_media", "news_media"]:
            target[ch][1] += 1
            if r[ch]:
                target[ch][0] += 1

    print("\n  Channel citation rate by flood experience (same year):")
    print(f"  {'Channel':>14}  {'Flooded':>10}  {'Not Flooded':>12}  {'Diff':>8}")
    print("  " + "-" * 50)
    for ch in ["gossip", "social_media", "news_media"]:
        fr = flooded_cites[ch][0] / flooded_cites[ch][1] if flooded_cites[ch][1] else 0
        nfr = nonflooded_cites[ch][0] / nonflooded_cites[ch][1] if nonflooded_cites[ch][1] else 0
        print(f"  {ch:>14}  {100*fr:8.1f}%   {100*nfr:10.1f}%   {100*(fr-nfr):+6.1f}pp")

    # ------------------------------------------------------------------
    # (C) Decision correlation with social channel citation
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[C] DECISION CORRELATION WITH SOCIAL CHANNEL CITATION")
    print("=" * 72)

    # For each channel: compare decision distribution of citers vs non-citers
    for ch in ["gossip", "social_media", "news_media"]:
        citers = [r for r in all_channels if r[ch]]
        non_citers = [r for r in all_channels if not r[ch]]

        citer_decisions = Counter(r["decision"] for r in citers)
        non_citer_decisions = Counter(r["decision"] for r in non_citers)

        # Compute protective action rate
        citer_protective = sum(1 for r in citers
                               if r["decision"] in ALL_PROTECTIVE)
        non_citer_protective = sum(1 for r in non_citers
                                   if r["decision"] in ALL_PROTECTIVE)

        cp = citer_protective / len(citers) if citers else 0
        ncp = non_citer_protective / len(non_citers) if non_citers else 0

        print(f"\n  {ch.upper()} channel:")
        print(f"    Citers (n={len(citers)}): protective_rate={100*cp:.1f}%")
        print(f"      Decisions: {dict(citer_decisions.most_common())}")
        print(f"    Non-citers (n={len(non_citers)}): protective_rate={100*ncp:.1f}%")
        print(f"      Decisions: {dict(non_citer_decisions.most_common())}")
        print(f"    Protective rate difference: {100*(cp-ncp):+.1f} pp")

    # ------------------------------------------------------------------
    # (D) First-mover vs follower analysis
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[D] FIRST-MOVER VS FOLLOWER ANALYSIS")
    print("=" * 72)

    # Track year of first protective action per agent
    first_adoption = {}
    for r in all_channels:
        aid = r["agent_id"]
        if r["decision"] in ALL_PROTECTIVE and r["status"] == "APPROVED":
            if aid not in first_adoption or r["year"] < first_adoption[aid]:
                first_adoption[aid] = r["year"]

    # Classify: first-mover (adopted Y1-3) vs follower (Y4+) vs never
    all_agents = set(r["agent_id"] for r in all_channels)
    movers = {"first_mover": [], "follower": [], "never": []}
    for aid in all_agents:
        if aid in first_adoption:
            if first_adoption[aid] <= 3:
                movers["first_mover"].append(aid)
            else:
                movers["follower"].append(aid)
        else:
            movers["never"].append(aid)

    print(f"\n  First-movers (adopted Y1-3): {len(movers['first_mover'])}")
    print(f"  Followers (adopted Y4+):     {len(movers['follower'])}")
    print(f"  Never adopted:               {len(movers['never'])}")

    # Compare channel citation rates for first-movers vs followers
    for category, agents in movers.items():
        if not agents:
            continue
        agent_set = set(agents)
        subset = [r for r in all_channels if r["agent_id"] in agent_set]
        g = sum(1 for r in subset if r["gossip"])
        s = sum(1 for r in subset if r["social_media"])
        n = sum(1 for r in subset if r["news_media"])
        t = len(subset)
        print(f"\n  {category} (n_agents={len(agents)}, n_decisions={t}):")
        print(f"    gossip={100*g/t:.1f}%, social_media={100*s/t:.1f}%, news_media={100*n/t:.1f}%")

    # Neighborhood-level first-mover analysis
    # Build spatial neighborhoods using grid coordinates
    agent_coords = {}
    for aid, prof in profiles.items():
        try:
            gx = float(prof.get("grid_x", 0))
            gy = float(prof.get("grid_y", 0))
            agent_coords[aid] = (gx, gy)
        except (ValueError, TypeError):
            pass

    # For each agent, find 5 nearest neighbors
    if agent_coords:
        from scipy.spatial import cKDTree
        agent_list = sorted(agent_coords.keys())
        coords_arr = np.array([agent_coords[a] for a in agent_list])
        tree = cKDTree(coords_arr)
        k_nn = min(6, len(agent_list))  # 5 neighbors + self
        _, nn_indices = tree.query(coords_arr, k=k_nn)

        # For each agent, check if they adopted BEFORE or AFTER their neighbors
        leader_count = 0
        follower_count = 0
        for i, aid in enumerate(agent_list):
            my_adoption = first_adoption.get(aid, 99)
            neighbor_adoptions = []
            for j_idx in nn_indices[i, 1:]:
                n_aid = agent_list[j_idx]
                na = first_adoption.get(n_aid, 99)
                if na < 99:
                    neighbor_adoptions.append(na)
            if my_adoption < 99 and neighbor_adoptions:
                avg_neighbor = np.mean(neighbor_adoptions)
                if my_adoption < avg_neighbor:
                    leader_count += 1
                else:
                    follower_count += 1

        print(f"\n  Spatial leadership:")
        print(f"    Leaders (adopted before neighbors): {leader_count}")
        print(f"    Followers (adopted after neighbors): {follower_count}")

    # ------------------------------------------------------------------
    # (E) Spatial autocorrelation (Moran's I)
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[E] SPATIAL AUTOCORRELATION (MORAN'S I)")
    print("=" * 72)

    has_scipy = True
    try:
        from scipy.spatial import cKDTree
    except ImportError:
        has_scipy = False
        print("  scipy not available -- skipping Moran's I")

    if has_scipy:
        # Build agent adoption state per year
        # For owners: insurance or elevation
        # For renters: insurance

        # Build cumulative adoption status per agent per year
        agent_insurance = defaultdict(dict)  # {agent_id: {year: bool}}
        agent_elevation = defaultdict(dict)
        agent_any_protective = defaultdict(dict)

        for r in all_channels:
            aid = r["agent_id"]
            y = r["year"]
            is_protective = r["decision"] in ALL_PROTECTIVE and r["status"] == "APPROVED"
            is_insurance = r["decision"] in {"buy_insurance", "buy_contents_insurance"} and r["status"] == "APPROVED"
            is_elevation = r["decision"] == "elevate_house" and r["status"] == "APPROVED"

            agent_insurance[aid][y] = is_insurance
            agent_elevation[aid][y] = is_elevation
            agent_any_protective[aid][y] = is_protective

        # Build cumulative adoption (once adopted insurance, stays True)
        agent_cum_insurance = defaultdict(dict)
        agent_cum_elevation = defaultdict(dict)
        agent_cum_protective = defaultdict(dict)

        for aid in set(r["agent_id"] for r in all_channels):
            ins_cum = False
            elev_cum = False
            prot_cum = False
            for y in years:
                if agent_insurance[aid].get(y, False):
                    ins_cum = True
                if agent_elevation[aid].get(y, False):
                    elev_cum = True
                if agent_any_protective[aid].get(y, False):
                    prot_cum = True
                agent_cum_insurance[aid][y] = ins_cum
                agent_cum_elevation[aid][y] = elev_cum
                agent_cum_protective[aid][y] = prot_cum

        # Compute Moran's I per year for insurance adoption
        # Use agents that have coordinates
        agents_with_coords = [aid for aid in set(r["agent_id"] for r in all_channels)
                              if aid in agent_coords]
        agents_with_coords.sort()
        coords_for_moran = np.array([agent_coords[a] for a in agents_with_coords])

        print(f"\n  Agents with coordinates: {len(agents_with_coords)}")

        morans_insurance = {}
        morans_elevation = {}
        morans_protective = {}

        print(f"\n  {'Year':>4}  {'I_ins':>8}  {'z_ins':>7}  {'I_elev':>8}  {'z_elev':>7}  {'I_prot':>8}  {'z_prot':>7}")
        print("  " + "-" * 60)

        for y in years:
            # Insurance
            vals_ins = np.array([float(agent_cum_insurance[a].get(y, False))
                                 for a in agents_with_coords])
            I_ins, _, z_ins = compute_morans_i(vals_ins, coords_for_moran, k=8)
            morans_insurance[y] = (I_ins, z_ins)

            # Elevation (owners only)
            owner_agents_c = [a for a in agents_with_coords if a.startswith("H0") and int(a[1:]) <= 200]
            if owner_agents_c:
                coords_own = np.array([agent_coords[a] for a in owner_agents_c])
                vals_elev = np.array([float(agent_cum_elevation[a].get(y, False))
                                      for a in owner_agents_c])
                I_elev, _, z_elev = compute_morans_i(vals_elev, coords_own, k=8)
            else:
                I_elev, z_elev = np.nan, np.nan
            morans_elevation[y] = (I_elev, z_elev)

            # Any protective
            vals_prot = np.array([float(agent_cum_protective[a].get(y, False))
                                  for a in agents_with_coords])
            I_prot, _, z_prot = compute_morans_i(vals_prot, coords_for_moran, k=8)
            morans_protective[y] = (I_prot, z_prot)

            i_ins_s = f"{I_ins:.4f}" if not np.isnan(I_ins) else "   N/A"
            z_ins_s = f"{z_ins:.2f}" if not np.isnan(z_ins) else "  N/A"
            i_elev_s = f"{I_elev:.4f}" if not np.isnan(I_elev) else "   N/A"
            z_elev_s = f"{z_elev:.2f}" if not np.isnan(z_elev) else "  N/A"
            i_prot_s = f"{I_prot:.4f}" if not np.isnan(I_prot) else "   N/A"
            z_prot_s = f"{z_prot:.2f}" if not np.isnan(z_prot) else "  N/A"

            sig_ins = "*" if not np.isnan(z_ins) and abs(z_ins) > 1.96 else ""
            sig_elev = "*" if not np.isnan(z_elev) and abs(z_elev) > 1.96 else ""
            sig_prot = "*" if not np.isnan(z_prot) and abs(z_prot) > 1.96 else ""

            print(f"  {y:4d}  {i_ins_s}{sig_ins:1s}  {z_ins_s:>7s}  {i_elev_s}{sig_elev:1s}  {z_elev_s:>7s}  {i_prot_s}{sig_prot:1s}  {z_prot_s:>7s}")

        print("\n  (* = statistically significant at p<0.05, |z|>1.96)")

        # Trend test for Moran's I over time
        valid_years_ins = [(y, morans_insurance[y][0]) for y in years if not np.isnan(morans_insurance[y][0])]
        if len(valid_years_ins) >= 3:
            x = np.array([v[0] for v in valid_years_ins])
            y_vals = np.array([v[1] for v in valid_years_ins])
            slope = np.polyfit(x, y_vals, 1)[0]
            corr = np.corrcoef(x, y_vals)[0, 1] if len(x) > 2 else 0
            print(f"\n  Insurance Moran's I trend: slope={slope:.5f}, r={corr:.3f}")
            direction = "INCREASING clustering" if slope > 0 else "DECREASING clustering"
            print(f"  Interpretation: {direction} over time")

    # ------------------------------------------------------------------
    # (F) Behavioral diffusion speed
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[F] BEHAVIORAL DIFFUSION SPEED")
    print("=" * 72)

    # Time-to-first-protective-action
    max_year = max(years)

    # By tenure
    for tenure_label in ["Owner", "Renter"]:
        subset_agents = set(r["agent_id"] for r in all_channels if r["tenure"] == tenure_label)
        event_times = []
        for aid in subset_agents:
            if aid in first_adoption:
                event_times.append(first_adoption[aid])
            else:
                event_times.append(max_year)  # censored

        adopted = [t for t in event_times if t < max_year]
        never = len(event_times) - len(adopted)
        if adopted:
            median_t = np.median(adopted)
            mean_t = np.mean(adopted)
        else:
            median_t = mean_t = float("inf")

        print(f"\n  {tenure_label} (n={len(subset_agents)}):")
        print(f"    Adopted at least once: {len(adopted)} ({100*len(adopted)/len(subset_agents):.1f}%)")
        print(f"    Never adopted: {never} ({100*never/len(subset_agents):.1f}%)")
        print(f"    Mean time-to-adoption: {mean_t:.2f} years")
        print(f"    Median time-to-adoption: {median_t:.1f} years")

    # By income bracket
    print("\n  Time-to-adoption by income bracket:")
    income_groups = defaultdict(list)
    for aid in set(r["agent_id"] for r in all_channels):
        prof = profiles.get(aid, {})
        bracket = prof.get("income_bracket", "Unknown")
        adoption_year = first_adoption.get(aid, max_year)
        income_groups[bracket].append(adoption_year)

    for bracket in sorted(income_groups.keys()):
        times = income_groups[bracket]
        adopted = [t for t in times if t < max_year]
        rate = len(adopted) / len(times) if times else 0
        mean_t = np.mean(adopted) if adopted else float("inf")
        print(f"    {bracket:>25s}: adoption_rate={100*rate:.0f}%, mean_time={mean_t:.1f}yr (n={len(times)})")

    # By flood zone
    print("\n  Time-to-adoption by flood zone:")
    zone_groups = defaultdict(list)
    for aid in set(r["agent_id"] for r in all_channels):
        prof = profiles.get(aid, {})
        zone = prof.get("flood_zone", "Unknown")
        adoption_year = first_adoption.get(aid, max_year)
        zone_groups[zone].append(adoption_year)

    for zone in ["HIGH", "MEDIUM", "LOW"]:
        times = zone_groups.get(zone, [])
        adopted = [t for t in times if t < max_year]
        rate = len(adopted) / len(times) if times else 0
        mean_t = np.mean(adopted) if adopted else float("inf")
        print(f"    {zone:>8s}: adoption_rate={100*rate:.0f}%, mean_time={mean_t:.1f}yr (n={len(times)})")

    # By MG status
    print("\n  Time-to-adoption by marginalized group status:")
    mg_groups = defaultdict(list)
    for aid in set(r["agent_id"] for r in all_channels):
        prof = profiles.get(aid, {})
        mg = prof.get("mg", "False")
        mg_label = "MG" if str(mg).lower() == "true" else "Non-MG"
        adoption_year = first_adoption.get(aid, max_year)
        mg_groups[mg_label].append(adoption_year)

    for label in ["MG", "Non-MG"]:
        times = mg_groups.get(label, [])
        adopted = [t for t in times if t < max_year]
        rate = len(adopted) / len(times) if times else 0
        mean_t = np.mean(adopted) if adopted else float("inf")
        print(f"    {label:>8s}: adoption_rate={100*rate:.0f}%, mean_time={mean_t:.1f}yr (n={len(times)})")

    # Kaplan-Meier survival curves
    km_data = {}
    for tenure_label in ["Owner", "Renter"]:
        subset_agents = set(r["agent_id"] for r in all_channels if r["tenure"] == tenure_label)
        event_times = [first_adoption.get(aid, max_year) for aid in subset_agents]
        km_data[tenure_label] = kaplan_meier(event_times, censor_time=max_year)

    for label in ["MG", "Non-MG"]:
        agents_in_group = [aid for aid in set(r["agent_id"] for r in all_channels)
                           if (str(profiles.get(aid, {}).get("mg", "False")).lower() == "true") == (label == "MG")]
        event_times = [first_adoption.get(aid, max_year) for aid in agents_in_group]
        km_data[label] = kaplan_meier(event_times, censor_time=max_year)

    # ------------------------------------------------------------------
    # (G) Decision diversity (Shannon entropy)
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[G] DECISION DIVERSITY (SHANNON ENTROPY)")
    print("=" * 72)

    def shannon_entropy(counts):
        """Shannon entropy from a Counter/dict of counts."""
        total = sum(counts.values())
        if total == 0:
            return 0.0
        probs = [c / total for c in counts.values() if c > 0]
        return -sum(p * math.log2(p) for p in probs)

    entropy_by_year = {}
    decisions_by_year = defaultdict(Counter)
    for r in all_channels:
        decisions_by_year[r["year"]][r["decision"]] += 1

    print(f"\n  {'Year':>4}  {'Entropy':>8}  {'MaxEnt':>7}  {'Norm':>6}  {'Decisions':>10}")
    print("  " + "-" * 50)
    for y in years:
        counts = decisions_by_year[y]
        H = shannon_entropy(counts)
        n_unique = len(counts)
        max_H = math.log2(n_unique) if n_unique > 1 else 1.0
        norm_H = H / max_H if max_H > 0 else 0
        entropy_by_year[y] = (H, norm_H)
        print(f"  {y:4d}  {H:8.3f}  {max_H:7.3f}  {norm_H:6.3f}  {n_unique:10d}")

    # Early vs late comparison
    early_years = [y for y in years if y <= 3]
    late_years = [y for y in years if y >= 10]

    early_H = np.mean([entropy_by_year[y][0] for y in early_years]) if early_years else 0
    late_H = np.mean([entropy_by_year[y][0] for y in late_years]) if late_years else 0
    early_norm = np.mean([entropy_by_year[y][1] for y in early_years]) if early_years else 0
    late_norm = np.mean([entropy_by_year[y][1] for y in late_years]) if late_years else 0

    print(f"\n  Early (Y1-3): mean_H={early_H:.3f}, mean_norm_H={early_norm:.3f}")
    print(f"  Late (Y10-13): mean_H={late_H:.3f}, mean_norm_H={late_norm:.3f}")
    change = late_H - early_H
    print(f"  Change: {change:+.3f} bits")
    if abs(change) < 0.05:
        print("  Interpretation: Agents MAINTAIN heterogeneous behavior (no convergence)")
    elif change < -0.05:
        print("  Interpretation: Agents show CONVERGENCE in behavior over time")
    else:
        print("  Interpretation: Agents show DIVERGENCE / increasing diversity over time")

    # Entropy trend
    x_ent = np.array(years, dtype=float)
    y_ent = np.array([entropy_by_year[y][0] for y in years])
    slope_ent, intercept_ent = np.polyfit(x_ent, y_ent, 1)
    print(f"\n  Entropy trend: slope={slope_ent:.4f} bits/year")

    # Decision distribution by tenure for early vs late
    for tenure_label in ["Owner", "Renter"]:
        subset = [r for r in all_channels if r["tenure"] == tenure_label]
        early_dec = Counter(r["decision"] for r in subset if r["year"] <= 3)
        late_dec = Counter(r["decision"] for r in subset if r["year"] >= 10)
        print(f"\n  {tenure_label} decision distribution:")
        print(f"    Early (Y1-3): {dict(early_dec.most_common())}")
        print(f"    Late (Y10-13): {dict(late_dec.most_common())}")

    # ------------------------------------------------------------------
    # Channel influence strength summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    print("[SUMMARY] CHANNEL INFLUENCE RANKING")
    print("=" * 72)

    # Compute influence score for each channel
    # Metric: ratio of protective action rate among citers vs non-citers
    for ch in ["gossip", "social_media", "news_media"]:
        citers = [r for r in all_channels if r[ch]]
        non_citers = [r for r in all_channels if not r[ch]]
        cp = sum(1 for r in citers if r["decision"] in ALL_PROTECTIVE) / len(citers) if citers else 0
        ncp = sum(1 for r in non_citers if r["decision"] in ALL_PROTECTIVE) / len(non_citers) if non_citers else 0
        rr = cp / ncp if ncp > 0 else float("inf")
        print(f"\n  {ch:>14s}:")
        print(f"    Citation rate:     {100*len(citers)/len(all_channels):.1f}%")
        print(f"    Protective (cite): {100*cp:.1f}%")
        print(f"    Protective (no):   {100*ncp:.1f}%")
        print(f"    Relative risk:     {rr:.2f}x")

    # ------------------------------------------------------------------
    # Generate figures
    # ------------------------------------------------------------------
    print("\n\n[GENERATING FIGURES]")

    # Style
    plt.rcParams.update({
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 12,
        "legend.fontsize": 9,
        "figure.dpi": 150,
    })

    # --- Figure 1: Channel citation rates over time ---
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(years, gossip_pcts, "o-", label="Gossip (neighbor)", color="#2196F3", linewidth=2)
    ax.plot(years, social_pcts, "s-", label="Social media", color="#FF9800", linewidth=2)
    ax.plot(years, news_pcts, "^-", label="News media", color="#4CAF50", linewidth=2)

    # Mark major flood years
    for fy in flood_years_major:
        ax.axvline(fy, color="red", alpha=0.3, linestyle="--", linewidth=1)
    if flood_years_major:
        ax.axvline(flood_years_major[0], color="red", alpha=0.3, linestyle="--",
                    linewidth=1, label="Major flood year")

    ax.set_xlabel("Year")
    ax.set_ylabel("Citation rate (%)")
    ax.set_title("RQ3: Social Channel Citation Rates in Agent Reasoning")
    ax.legend(loc="best")
    ax.set_xticks(years)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rq3_channel_citation_rates.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: {OUT_DIR / 'rq3_channel_citation_rates.png'}")

    # --- Figure 2: Decision correlation ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for idx, ch in enumerate(["gossip", "social_media", "news_media"]):
        ax = axes[idx]
        citers = [r for r in all_channels if r[ch]]
        non_citers = [r for r in all_channels if not r[ch]]

        all_decisions = sorted(set(r["decision"] for r in all_channels))
        cite_counts = Counter(r["decision"] for r in citers)
        non_cite_counts = Counter(r["decision"] for r in non_citers)

        x_pos = np.arange(len(all_decisions))
        width = 0.35

        cite_vals = [100 * cite_counts.get(d, 0) / len(citers) if citers else 0 for d in all_decisions]
        non_cite_vals = [100 * non_cite_counts.get(d, 0) / len(non_citers) if non_citers else 0 for d in all_decisions]

        ax.bar(x_pos - width / 2, cite_vals, width, label="Citer", color="#2196F3", alpha=0.8)
        ax.bar(x_pos + width / 2, non_cite_vals, width, label="Non-citer", color="#FF9800", alpha=0.8)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(all_decisions, rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("% of group")
        ax.set_title(ch.replace("_", " ").title())
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3, axis="y")

    fig.suptitle("RQ3: Decision Distribution by Channel Citation", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rq3_decision_correlation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {OUT_DIR / 'rq3_decision_correlation.png'}")

    # --- Figure 3: Moran's I over time ---
    if has_scipy:
        fig, ax = plt.subplots(figsize=(10, 5))
        mi_ins = [morans_insurance[y][0] for y in years]
        mi_prot = [morans_protective[y][0] for y in years]

        # Filter NaN
        valid_ins = [(y, v) for y, v in zip(years, mi_ins) if not np.isnan(v)]
        valid_prot = [(y, v) for y, v in zip(years, mi_prot) if not np.isnan(v)]

        if valid_ins:
            ax.plot([v[0] for v in valid_ins], [v[1] for v in valid_ins],
                    "o-", label="Insurance", color="#2196F3", linewidth=2)
        if valid_prot:
            ax.plot([v[0] for v in valid_prot], [v[1] for v in valid_prot],
                    "s-", label="Any protective", color="#4CAF50", linewidth=2)

        ax.axhline(0, color="gray", linestyle=":", alpha=0.5)
        for fy in flood_years_major:
            ax.axvline(fy, color="red", alpha=0.3, linestyle="--", linewidth=1)

        ax.set_xlabel("Year")
        ax.set_ylabel("Moran's I")
        ax.set_title("RQ3: Spatial Autocorrelation of Adaptation Over Time")
        ax.legend()
        ax.set_xticks(years)
        ax.grid(alpha=0.3)
        fig.tight_layout()
        fig.savefig(OUT_DIR / "rq3_morans_i.png", dpi=150)
        plt.close(fig)
        print(f"  Saved: {OUT_DIR / 'rq3_morans_i.png'}")

    # --- Figure 4: Kaplan-Meier survival curves ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    ax = axes[0]
    for label, color in [("Owner", "#2196F3"), ("Renter", "#FF9800")]:
        if label in km_data:
            t, s = km_data[label]
            ax.step(t, s, where="post", label=label, color=color, linewidth=2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Survival probability (no adoption)")
    ax.set_title("Time-to-First-Adoption by Tenure")
    ax.legend()
    ax.set_xticks(range(0, max_year + 1))
    ax.grid(alpha=0.3)

    ax = axes[1]
    for label, color in [("MG", "#E91E63"), ("Non-MG", "#4CAF50")]:
        if label in km_data:
            t, s = km_data[label]
            ax.step(t, s, where="post", label=label, color=color, linewidth=2)
    ax.set_xlabel("Year")
    ax.set_ylabel("Survival probability (no adoption)")
    ax.set_title("Time-to-First-Adoption by MG Status")
    ax.legend()
    ax.set_xticks(range(0, max_year + 1))
    ax.grid(alpha=0.3)

    fig.suptitle("RQ3: Kaplan-Meier Survival Analysis", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rq3_kaplan_meier.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {OUT_DIR / 'rq3_kaplan_meier.png'}")

    # --- Figure 5: Shannon entropy over time ---
    fig, ax = plt.subplots(figsize=(10, 5))
    ent_vals = [entropy_by_year[y][0] for y in years]
    norm_vals = [entropy_by_year[y][1] for y in years]

    ax.plot(years, ent_vals, "o-", label="Shannon entropy (H)", color="#9C27B0", linewidth=2)
    ax.plot(years, norm_vals, "s--", label="Normalized H", color="#FF5722", linewidth=2)

    # Trend line
    ax.plot(years, slope_ent * np.array(years) + intercept_ent,
            ":", color="#9C27B0", alpha=0.5, label=f"Trend (slope={slope_ent:.4f})")

    for fy in flood_years_major:
        ax.axvline(fy, color="red", alpha=0.3, linestyle="--", linewidth=1)

    ax.set_xlabel("Year")
    ax.set_ylabel("Entropy (bits)")
    ax.set_title("RQ3: Decision Diversity Over Time")
    ax.legend()
    ax.set_xticks(years)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rq3_entropy.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: {OUT_DIR / 'rq3_entropy.png'}")

    # --- Figure 6: Channel citation by flood experience ---
    fig, ax = plt.subplots(figsize=(8, 5))
    channels_list = ["gossip", "social_media", "news_media"]
    x_pos = np.arange(len(channels_list))
    width = 0.35

    flooded_rates = []
    nonflooded_rates = []
    for ch in channels_list:
        fr = flooded_cites[ch][0] / flooded_cites[ch][1] if flooded_cites[ch][1] else 0
        nfr = nonflooded_cites[ch][0] / nonflooded_cites[ch][1] if nonflooded_cites[ch][1] else 0
        flooded_rates.append(100 * fr)
        nonflooded_rates.append(100 * nfr)

    ax.bar(x_pos - width / 2, flooded_rates, width, label="Flooded", color="#E91E63", alpha=0.8)
    ax.bar(x_pos + width / 2, nonflooded_rates, width, label="Not flooded", color="#4CAF50", alpha=0.8)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([c.replace("_", " ").title() for c in channels_list])
    ax.set_ylabel("Citation rate (%)")
    ax.set_title("RQ3: Channel Citation by Flood Experience")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rq3_channel_flood_experience.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: {OUT_DIR / 'rq3_channel_flood_experience.png'}")

    # --- Figure 7: First-mover channel usage ---
    fig, ax = plt.subplots(figsize=(8, 5))
    categories = ["first_mover", "follower", "never"]
    cat_colors = {"first_mover": "#2196F3", "follower": "#FF9800", "never": "#9E9E9E"}

    x_pos = np.arange(len(channels_list))
    width = 0.25

    for i, cat in enumerate(categories):
        agents_in_cat = set(movers[cat])
        subset = [r for r in all_channels if r["agent_id"] in agents_in_cat]
        if not subset:
            continue
        rates = []
        for ch in channels_list:
            rate = 100 * sum(1 for r in subset if r[ch]) / len(subset)
            rates.append(rate)
        ax.bar(x_pos + i * width - width, rates, width,
               label=cat.replace("_", " ").title(), color=cat_colors[cat], alpha=0.8)

    ax.set_xticks(x_pos)
    ax.set_xticklabels([c.replace("_", " ").title() for c in channels_list])
    ax.set_ylabel("Citation rate (%)")
    ax.set_title("RQ3: Channel Citation by Adoption Timing")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "rq3_firstmover_channels.png", dpi=150)
    plt.close(fig)
    print(f"  Saved: {OUT_DIR / 'rq3_firstmover_channels.png'}")

    print("\n" + "=" * 72)
    print("RQ3 analysis complete.")
    print(f"All figures saved to: {OUT_DIR}")
    print("=" * 72)


if __name__ == "__main__":
    main()
