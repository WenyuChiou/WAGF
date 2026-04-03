"""
RQ3 Rigorous Within-Agent Temporal Analysis of Construct-Action Feedback Loops
===============================================================================
Addresses methodological issues in previous analysis:
  1. Uses within-agent paired tests (Wilcoxon) instead of unpaired Mann-Whitney
  2. Controls for flooding (stratified analysis)
  3. Accounts for 84% TP repeat rate via transition matrices and Granger-like tests

Analyses A-F as specified.
"""

import pandas as pd
import numpy as np
import json
import os
import warnings
from pathlib import Path
from scipy import stats
from collections import defaultdict

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3\results\paper3_hybrid_v2")
OUT_DIR = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\multi_agent\flood\paper3\analysis\tables")
SEEDS = [42, 123, 456]
TYPES = ["household_owner", "household_renter"]
LABEL_MAP = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}


def load_audit_data():
    """Load governance audit CSVs, pool 3 seeds, create uid."""
    frames = []
    for seed in SEEDS:
        for atype in TYPES:
            path = BASE / f"seed_{seed}" / "gemma3_4b_strict" / f"{atype}_governance_audit.csv"
            df = pd.read_csv(path)
            df["seed"] = seed
            df["agent_type"] = atype.replace("household_", "")
            df["uid"] = df["seed"].astype(str) + "_" + df["agent_id"]
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_flood_data():
    """Load per-agent flood info from JSONL traces."""
    records = []
    for seed in SEEDS:
        for atype in TYPES:
            jsonl = BASE / f"seed_{seed}" / "gemma3_4b_strict" / "raw" / f"{atype}_traces.jsonl"
            with open(jsonl, encoding="utf-8") as f:
                for line in f:
                    rec = json.loads(line)
                    sb = rec.get("state_before", {})
                    records.append({
                        "seed": seed,
                        "agent_id": rec["agent_id"],
                        "year": rec["year"],
                        "uid": f"{seed}_{rec['agent_id']}",
                        "flooded_this_year": sb.get("flooded_this_year", False),
                        "flood_depth": sb.get("flood_depth", 0.0),
                        "flood_count": sb.get("flood_count", 0),
                        "cumulative_damage": sb.get("cumulative_damage", 0.0),
                        "has_insurance_state": sb.get("has_insurance", False),
                        "flood_zone": sb.get("flood_zone", ""),
                    })
    return pd.DataFrame(records)


def prepare_data():
    """Merge audit + flood data, compute derived columns."""
    audit = load_audit_data()
    flood = load_flood_data()

    # Merge on uid + year
    df = audit.merge(flood, on=["seed", "agent_id", "year", "uid"], how="left")

    # Map construct labels to numeric
    for col in ["construct_SP_LABEL", "construct_PA_LABEL", "construct_TP_LABEL",
                 "construct_CP_LABEL", "construct_SC_LABEL"]:
        df[col + "_num"] = df[col].map(LABEL_MAP)

    # Executed action: APPROVED -> proposed_skill, REJECTED -> do_nothing
    df["executed_action"] = np.where(df["status"] == "APPROVED", df["proposed_skill"], "do_nothing")

    # Protective action flag (anything other than do_nothing)
    df["is_protective"] = (df["executed_action"] != "do_nothing").astype(int)

    # Insurance-specific flags
    df["is_insurance"] = df["executed_action"].isin(["buy_insurance", "buy_contents_insurance"]).astype(int)

    # Sort for temporal operations
    df = df.sort_values(["uid", "year"]).reset_index(drop=True)

    return df


def print_section(title):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")


# ── ANALYSIS A: Within-agent action-switching SP change ──────────────────
def analysis_a(df):
    print_section("ANALYSIS A: Within-Agent Action-Switching SP Change")

    results = []

    # For each agent, look at consecutive year pairs
    switch_to_ins = []  # SP(t) - SP(t-1) when switching TO insurance
    switch_from_ins = []  # SP(t) - SP(t-1) when switching FROM insurance

    for uid, grp in df.groupby("uid"):
        grp = grp.sort_values("year")
        sp_vals = grp["construct_SP_LABEL_num"].values
        ins_vals = grp["is_insurance"].values
        years = grp["year"].values

        for i in range(1, len(grp)):
            sp_t = sp_vals[i]
            sp_prev = sp_vals[i - 1]
            ins_t = ins_vals[i]
            ins_prev = ins_vals[i - 1]

            if pd.isna(sp_t) or pd.isna(sp_prev):
                continue

            delta_sp = sp_t - sp_prev

            # Switched TO insurance (was not insuring, now insuring)
            if ins_t == 1 and ins_prev == 0:
                switch_to_ins.append(delta_sp)
            # Switched FROM insurance (was insuring, now not)
            elif ins_t == 0 and ins_prev == 1:
                switch_from_ins.append(delta_sp)

    print(f"\nSwitch events found:")
    print(f"  Switched TO insurance:   N = {len(switch_to_ins)}")
    print(f"  Switched FROM insurance: N = {len(switch_from_ins)}")

    if len(switch_to_ins) >= 5:
        mean_to = np.mean(switch_to_ins)
        med_to = np.median(switch_to_ins)
        stat_to, p_to = stats.wilcoxon(switch_to_ins, alternative="two-sided")
        print(f"\n  Switch TO insurance:")
        print(f"    Mean delta-SP:   {mean_to:+.3f}")
        print(f"    Median delta-SP: {med_to:+.3f}")
        print(f"    Wilcoxon signed-rank: W={stat_to:.0f}, p={p_to:.4e}")
        results.append(("A", "switch_TO_ins", "mean_delta_SP", f"{mean_to:+.3f}"))
        results.append(("A", "switch_TO_ins", "N", str(len(switch_to_ins))))
        results.append(("A", "switch_TO_ins", "wilcoxon_p", f"{p_to:.4e}"))
    else:
        print(f"\n  Switch TO insurance: insufficient events for test")
        results.append(("A", "switch_TO_ins", "N", str(len(switch_to_ins))))

    if len(switch_from_ins) >= 5:
        mean_from = np.mean(switch_from_ins)
        med_from = np.median(switch_from_ins)
        stat_from, p_from = stats.wilcoxon(switch_from_ins, alternative="two-sided")
        print(f"\n  Switch FROM insurance:")
        print(f"    Mean delta-SP:   {mean_from:+.3f}")
        print(f"    Median delta-SP: {med_from:+.3f}")
        print(f"    Wilcoxon signed-rank: W={stat_from:.0f}, p={p_from:.4e}")
        results.append(("A", "switch_FROM_ins", "mean_delta_SP", f"{mean_from:+.3f}"))
        results.append(("A", "switch_FROM_ins", "N", str(len(switch_from_ins))))
        results.append(("A", "switch_FROM_ins", "wilcoxon_p", f"{p_from:.4e}"))
    else:
        print(f"\n  Switch FROM insurance: insufficient events for test")
        results.append(("A", "switch_FROM_ins", "N", str(len(switch_from_ins))))

    # Also do protective action (not just insurance)
    print(f"\n  --- Also for ANY protective action (not just insurance) ---")
    switch_to_prot = []
    switch_from_prot = []
    for uid, grp in df.groupby("uid"):
        grp = grp.sort_values("year")
        sp_vals = grp["construct_SP_LABEL_num"].values
        prot_vals = grp["is_protective"].values
        for i in range(1, len(grp)):
            sp_t = sp_vals[i]
            sp_prev = sp_vals[i - 1]
            if pd.isna(sp_t) or pd.isna(sp_prev):
                continue
            delta_sp = sp_t - sp_prev
            if prot_vals[i] == 1 and prot_vals[i - 1] == 0:
                switch_to_prot.append(delta_sp)
            elif prot_vals[i] == 0 and prot_vals[i - 1] == 1:
                switch_from_prot.append(delta_sp)

    print(f"  Switched TO protective:   N = {len(switch_to_prot)}")
    print(f"  Switched FROM protective: N = {len(switch_from_prot)}")

    for label, data in [("switch_TO_protective", switch_to_prot),
                         ("switch_FROM_protective", switch_from_prot)]:
        if len(data) >= 5:
            mean_d = np.mean(data)
            med_d = np.median(data)
            # Handle all-zero case
            nonzero = [x for x in data if x != 0]
            if len(nonzero) >= 1:
                stat_d, p_d = stats.wilcoxon(data, alternative="two-sided")
            else:
                stat_d, p_d = np.nan, 1.0
            print(f"\n  {label}:")
            print(f"    Mean delta-SP:   {mean_d:+.3f}")
            print(f"    Median delta-SP: {med_d:+.3f}")
            if not np.isnan(stat_d):
                print(f"    Wilcoxon signed-rank: W={stat_d:.0f}, p={p_d:.4e}")
            else:
                print(f"    Wilcoxon: all differences = 0")
            results.append(("A", label, "mean_delta_SP", f"{mean_d:+.3f}"))
            results.append(("A", label, "N", str(len(data))))
            results.append(("A", label, "wilcoxon_p", f"{p_d:.4e}"))
        else:
            print(f"\n  {label}: insufficient events (N={len(data)})")
            results.append(("A", label, "N", str(len(data))))

    return results


# ── ANALYSIS B: Within-agent SP trajectory by action history ─────────────
def analysis_b(df):
    print_section("ANALYSIS B: SP Trajectory by Action History Group")

    results = []

    # Classify each agent's 13-year history
    agent_profiles = []
    for uid, grp in df.groupby("uid"):
        grp = grp.sort_values("year")
        n_years = len(grp)
        n_insurance = grp["is_insurance"].sum()
        n_do_nothing = (grp["executed_action"] == "do_nothing").sum()
        n_protective = grp["is_protective"].sum()

        # Classify
        if n_insurance >= 8:
            group = "persistent_insurer"
        elif n_do_nothing >= 8:
            group = "persistent_non_actor"
        else:
            group = "switcher"

        # SP early (Y1-4) vs late (Y10-13)
        early = grp[grp["year"].between(1, 4)]["construct_SP_LABEL_num"].dropna()
        late = grp[grp["year"].between(10, 13)]["construct_SP_LABEL_num"].dropna()

        agent_profiles.append({
            "uid": uid,
            "group": group,
            "agent_type": grp["agent_type"].iloc[0],
            "n_insurance": n_insurance,
            "n_do_nothing": n_do_nothing,
            "sp_early_mean": early.mean() if len(early) > 0 else np.nan,
            "sp_late_mean": late.mean() if len(late) > 0 else np.nan,
            "sp_early_n": len(early),
            "sp_late_n": len(late),
        })

    profiles = pd.DataFrame(agent_profiles)
    profiles["sp_change"] = profiles["sp_late_mean"] - profiles["sp_early_mean"]

    print(f"\nAgent classification (N={len(profiles)}):")
    for grp_name in ["persistent_insurer", "persistent_non_actor", "switcher"]:
        sub = profiles[profiles["group"] == grp_name]
        print(f"\n  {grp_name}: N = {len(sub)}")
        if len(sub) > 0:
            print(f"    Mean SP early (Y1-4):  {sub['sp_early_mean'].mean():.3f}")
            print(f"    Mean SP late (Y10-13): {sub['sp_late_mean'].mean():.3f}")
            change = sub["sp_change"].dropna()
            if len(change) >= 5:
                mean_ch = change.mean()
                nonzero = [x for x in change if x != 0]
                if len(nonzero) >= 1:
                    w_stat, w_p = stats.wilcoxon(change, alternative="two-sided")
                    print(f"    SP change (late-early): {mean_ch:+.3f} (Wilcoxon p={w_p:.4e})")
                else:
                    w_p = 1.0
                    print(f"    SP change (late-early): {mean_ch:+.3f} (all zeros)")
                results.append(("B", grp_name, "N", str(len(sub))))
                results.append(("B", grp_name, "sp_early", f"{sub['sp_early_mean'].mean():.3f}"))
                results.append(("B", grp_name, "sp_late", f"{sub['sp_late_mean'].mean():.3f}"))
                results.append(("B", grp_name, "sp_change", f"{mean_ch:+.3f}"))
                results.append(("B", grp_name, "wilcoxon_p", f"{w_p:.4e}"))
            else:
                print(f"    SP change: insufficient data (N={len(change)})")
                results.append(("B", grp_name, "N", str(len(sub))))

    # Cross-group comparison: early SP
    print(f"\n  --- Between-group comparisons (Kruskal-Wallis) ---")
    groups_data = {}
    for grp_name in ["persistent_insurer", "persistent_non_actor", "switcher"]:
        sub = profiles[profiles["group"] == grp_name]["sp_early_mean"].dropna()
        if len(sub) > 0:
            groups_data[grp_name] = sub.values

    if len(groups_data) >= 2:
        arrays = list(groups_data.values())
        h_stat, h_p = stats.kruskal(*arrays)
        print(f"  Early SP across groups: H={h_stat:.2f}, p={h_p:.4e}")
        results.append(("B", "kruskal_early_sp", "H_stat", f"{h_stat:.2f}"))
        results.append(("B", "kruskal_early_sp", "p_value", f"{h_p:.4e}"))

    return results


# ── ANALYSIS C: Control for flooding ─────────────────────────────────────
def analysis_c(df):
    print_section("ANALYSIS C: Action -> delta-SP Controlling for Flooding")

    results = []

    # For each agent-year, compute delta-SP = SP(t) - SP(t-1)
    records = []
    for uid, grp in df.groupby("uid"):
        grp = grp.sort_values("year")
        for i in range(1, len(grp)):
            row_t = grp.iloc[i]
            row_prev = grp.iloc[i - 1]
            sp_t = row_t["construct_SP_LABEL_num"]
            sp_prev = row_prev["construct_SP_LABEL_num"]
            if pd.isna(sp_t) or pd.isna(sp_prev):
                continue
            records.append({
                "uid": uid,
                "year": row_t["year"],
                "delta_sp": sp_t - sp_prev,
                "action_prev": row_prev["executed_action"],
                "is_protective_prev": row_prev["is_protective"],
                "is_insurance_prev": row_prev["is_insurance"],
                "flooded_this_year": row_t["flooded_this_year"],
                "flooded_prev_year": row_prev["flooded_this_year"],
                "agent_type": row_t["agent_type"],
            })

    trans_df = pd.DataFrame(records)
    print(f"\nTotal transition records: {len(trans_df)}")

    # Stratify by flood status at time t (current year flooding)
    for flood_label, flood_val in [("Flooded at t", True), ("Not flooded at t", False)]:
        sub = trans_df[trans_df["flooded_this_year"] == flood_val]
        print(f"\n  Stratum: {flood_label} (N={len(sub)})")

        for action_label, action_col, action_val in [
            ("protective at t-1", "is_protective_prev", 1),
            ("do_nothing at t-1", "is_protective_prev", 0),
        ]:
            ss = sub[sub[action_col] == action_val]["delta_sp"]
            if len(ss) >= 5:
                mean_d = ss.mean()
                med_d = ss.median()
                print(f"    After {action_label}: mean delta-SP = {mean_d:+.3f}, "
                      f"median = {med_d:+.1f}, N = {len(ss)}")
            else:
                print(f"    After {action_label}: N = {len(ss)} (insufficient)")

        # Within stratum: compare delta-SP by previous action
        prot = sub[sub["is_protective_prev"] == 1]["delta_sp"]
        nothing = sub[sub["is_protective_prev"] == 0]["delta_sp"]
        if len(prot) >= 5 and len(nothing) >= 5:
            u_stat, u_p = stats.mannwhitneyu(prot, nothing, alternative="two-sided")
            diff = prot.mean() - nothing.mean()
            print(f"    Difference (protective - do_nothing): {diff:+.3f}")
            print(f"    Mann-Whitney U (within stratum): U={u_stat:.0f}, p={u_p:.4e}")
            results.append(("C", flood_label, "diff_protective_minus_nothing", f"{diff:+.3f}"))
            results.append(("C", flood_label, "MWU_p", f"{u_p:.4e}"))
            results.append(("C", flood_label, "N_protective", str(len(prot))))
            results.append(("C", flood_label, "N_nothing", str(len(nothing))))

    # Also stratify by flood at t-1 (did prior-year action precede flooding?)
    print(f"\n  --- Stratified by flood at t-1 (prior year flood) ---")
    for flood_label, flood_val in [("Flooded at t-1", True), ("Not flooded at t-1", False)]:
        sub = trans_df[trans_df["flooded_prev_year"] == flood_val]
        print(f"\n  Stratum: {flood_label} (N={len(sub)})")

        prot = sub[sub["is_protective_prev"] == 1]["delta_sp"]
        nothing = sub[sub["is_protective_prev"] == 0]["delta_sp"]
        if len(prot) >= 5 and len(nothing) >= 5:
            u_stat, u_p = stats.mannwhitneyu(prot, nothing, alternative="two-sided")
            diff = prot.mean() - nothing.mean()
            print(f"    After protective: mean delta-SP = {prot.mean():+.3f}, N = {len(prot)}")
            print(f"    After do_nothing: mean delta-SP = {nothing.mean():+.3f}, N = {len(nothing)}")
            print(f"    Difference: {diff:+.3f}, MWU p={u_p:.4e}")
            results.append(("C", flood_label, "diff_protective_minus_nothing", f"{diff:+.3f}"))
            results.append(("C", flood_label, "MWU_p", f"{u_p:.4e}"))

    return results


# ── ANALYSIS D: Transition probability matrix ────────────────────────────
def analysis_d(df):
    print_section("ANALYSIS D: Transition Probability Matrix P(SP_t+1 | SP_t, action_t)")

    results = []

    # Build transitions
    transitions = defaultdict(lambda: defaultdict(int))
    # Key: (sp_t, action_category) -> {sp_t1: count}

    for uid, grp in df.groupby("uid"):
        grp = grp.sort_values("year")
        sp_vals = grp["construct_SP_LABEL"].values
        act_vals = grp["is_protective"].values

        for i in range(len(grp) - 1):
            sp_t = sp_vals[i]
            sp_t1 = sp_vals[i + 1]
            act_t = "protective" if act_vals[i] == 1 else "do_nothing"

            if pd.isna(sp_t) or pd.isna(sp_t1):
                continue

            transitions[(sp_t, act_t)][sp_t1] += 1

    # Print transition matrix
    sp_levels = ["VL", "L", "M", "H", "VH"]
    actions = ["protective", "do_nothing"]

    print(f"\nTransition probabilities P(SP_t+1 | SP_t, action_t):")
    print(f"{'SP_t':>6} {'action':>12} {'N':>6} | " +
          " ".join(f"→{s:>4}" for s in sp_levels) + " | modal_next")

    for sp in sp_levels:
        for act in actions:
            counts = transitions[(sp, act)]
            total = sum(counts.values())
            if total < 5:
                continue

            probs = {s: counts.get(s, 0) / total for s in sp_levels}
            modal = max(probs, key=probs.get)
            prob_str = " ".join(f"{probs[s]:5.2f}" for s in sp_levels)
            print(f"{sp:>6} {act:>12} {total:>6} | {prob_str} | {modal}")

            results.append(("D", f"{sp}_{act}", "N", str(total)))
            for s in sp_levels:
                results.append(("D", f"{sp}_{act}", f"P_to_{s}", f"{probs[s]:.3f}"))

    # Key comparison: stability under different actions
    print(f"\n  Key comparison: P(SP stays same | action)")
    for sp in sp_levels:
        stay_prot = transitions[("H" if sp == "H" else sp, "protective")].get(sp, 0)
        total_prot = sum(transitions[(sp, "protective")].values())
        stay_noth = transitions[(sp, "do_nothing")].get(sp, 0)
        total_noth = sum(transitions[(sp, "do_nothing")].values())

        if total_prot >= 5 and total_noth >= 5:
            p_stay_prot = stay_prot / total_prot
            p_stay_noth = stay_noth / total_noth
            print(f"    SP={sp}: P(stay|protective)={p_stay_prot:.3f} (N={total_prot}), "
                  f"P(stay|do_nothing)={p_stay_noth:.3f} (N={total_noth}), "
                  f"diff={p_stay_prot - p_stay_noth:+.3f}")
            results.append(("D", f"stay_{sp}", "P_protective", f"{p_stay_prot:.3f}"))
            results.append(("D", f"stay_{sp}", "P_do_nothing", f"{p_stay_noth:.3f}"))

    # Fisher exact test for H->H vs H->not-H by action
    print(f"\n  Fisher exact test: SP=M stability by action")
    for sp_test in ["M", "H", "L"]:
        stay_p = transitions[(sp_test, "protective")].get(sp_test, 0)
        leave_p = sum(v for k, v in transitions[(sp_test, "protective")].items() if k != sp_test)
        stay_n = transitions[(sp_test, "do_nothing")].get(sp_test, 0)
        leave_n = sum(v for k, v in transitions[(sp_test, "do_nothing")].items() if k != sp_test)

        if stay_p + leave_p >= 5 and stay_n + leave_n >= 5:
            table = [[stay_p, leave_p], [stay_n, leave_n]]
            odds, fp = stats.fisher_exact(table)
            print(f"    SP={sp_test}: protective stay/leave={stay_p}/{leave_p}, "
                  f"do_nothing stay/leave={stay_n}/{leave_n}, "
                  f"OR={odds:.3f}, p={fp:.4e}")
            results.append(("D", f"fisher_stay_{sp_test}", "odds_ratio", f"{odds:.3f}"))
            results.append(("D", f"fisher_stay_{sp_test}", "p_value", f"{fp:.4e}"))

    return results


# ── ANALYSIS E: Granger-like test (partial correlation) ──────────────────
def analysis_e(df):
    print_section("ANALYSIS E: Granger-Like Test (SP predicts action beyond persistence)")

    results = []

    # Build panel: for each agent-year (t >= 2), get:
    # - is_protective(t)
    # - SP(t-1)
    # - is_protective(t-1)
    # - flooded(t)
    records = []
    for uid, grp in df.groupby("uid"):
        grp = grp.sort_values("year")
        for i in range(1, len(grp)):
            row_t = grp.iloc[i]
            row_prev = grp.iloc[i - 1]
            sp_prev = row_prev["construct_SP_LABEL_num"]
            if pd.isna(sp_prev):
                continue
            records.append({
                "uid": uid,
                "year": row_t["year"],
                "is_protective_t": row_t["is_protective"],
                "sp_prev": sp_prev,
                "is_protective_prev": row_prev["is_protective"],
                "flooded_t": int(row_t["flooded_this_year"]) if not pd.isna(row_t["flooded_this_year"]) else 0,
                "tp_prev_num": row_prev.get("construct_TP_LABEL_num", np.nan),
                "agent_type": row_t["agent_type"],
            })

    panel = pd.DataFrame(records)
    print(f"\nPanel size: {len(panel)} agent-year observations")

    # 1. Raw correlations
    print(f"\n  Raw correlations with is_protective(t):")
    for var in ["sp_prev", "is_protective_prev", "flooded_t"]:
        valid = panel[[var, "is_protective_t"]].dropna()
        if len(valid) > 10:
            r, p = stats.spearmanr(valid[var], valid["is_protective_t"])
            print(f"    {var}: rho={r:.3f}, p={p:.4e}, N={len(valid)}")
            results.append(("E", "raw_corr", var, f"rho={r:.3f}, p={p:.4e}"))

    # 2. Partial correlation: corr(SP(t-1), is_protective(t)) | is_protective(t-1)
    print(f"\n  Partial correlation: corr(SP_prev, is_protective_t) controlling for is_protective_prev")
    valid = panel[["sp_prev", "is_protective_t", "is_protective_prev"]].dropna()
    if len(valid) > 20:
        # Residualize both on is_protective_prev
        from numpy.linalg import lstsq

        X_ctrl = valid["is_protective_prev"].values.reshape(-1, 1)
        X_ctrl_aug = np.column_stack([X_ctrl, np.ones(len(X_ctrl))])

        # Residuals of sp_prev on control
        beta_sp, _, _, _ = lstsq(X_ctrl_aug, valid["sp_prev"].values, rcond=None)
        resid_sp = valid["sp_prev"].values - X_ctrl_aug @ beta_sp

        # Residuals of is_protective_t on control
        beta_act, _, _, _ = lstsq(X_ctrl_aug, valid["is_protective_t"].values, rcond=None)
        resid_act = valid["is_protective_t"].values - X_ctrl_aug @ beta_act

        r_partial, p_partial = stats.spearmanr(resid_sp, resid_act)
        print(f"    Partial rho = {r_partial:.3f}, p = {p_partial:.4e}, N = {len(valid)}")
        results.append(("E", "partial_corr", "sp_prev|is_protective_prev",
                         f"rho={r_partial:.3f}, p={p_partial:.4e}"))

    # 3. Partial correlation controlling for BOTH is_protective_prev AND flooded_t
    print(f"\n  Partial correlation: corr(SP_prev, is_protective_t) | is_protective_prev + flooded_t")
    valid2 = panel[["sp_prev", "is_protective_t", "is_protective_prev", "flooded_t"]].dropna()
    if len(valid2) > 20:
        X_ctrl2 = valid2[["is_protective_prev", "flooded_t"]].values
        X_ctrl2_aug = np.column_stack([X_ctrl2, np.ones(len(X_ctrl2))])

        beta_sp2, _, _, _ = lstsq(X_ctrl2_aug, valid2["sp_prev"].values, rcond=None)
        resid_sp2 = valid2["sp_prev"].values - X_ctrl2_aug @ beta_sp2

        beta_act2, _, _, _ = lstsq(X_ctrl2_aug, valid2["is_protective_t"].values, rcond=None)
        resid_act2 = valid2["is_protective_t"].values - X_ctrl2_aug @ beta_act2

        r_partial2, p_partial2 = stats.spearmanr(resid_sp2, resid_act2)
        print(f"    Partial rho = {r_partial2:.3f}, p = {p_partial2:.4e}, N = {len(valid2)}")
        results.append(("E", "partial_corr", "sp_prev|prot_prev+flood",
                         f"rho={r_partial2:.3f}, p={p_partial2:.4e}"))

    # 4. Action persistence rate
    same_action = (panel["is_protective_t"] == panel["is_protective_prev"]).sum()
    total = len(panel)
    print(f"\n  Action persistence rate: {same_action}/{total} = {same_action / total:.1%}")
    results.append(("E", "persistence", "rate", f"{same_action / total:.3f}"))

    # 5. Logistic-like: among agents who CHANGED action, was SP predictive?
    changers = panel[panel["is_protective_t"] != panel["is_protective_prev"]]
    print(f"\n  Among action-changers (N={len(changers)}):")
    if len(changers) > 20:
        # Did SP predict direction of change?
        # Switched TO protective: expect higher SP_prev
        to_prot = changers[changers["is_protective_t"] == 1]["sp_prev"]
        from_prot = changers[changers["is_protective_t"] == 0]["sp_prev"]
        if len(to_prot) >= 5 and len(from_prot) >= 5:
            u_stat, u_p = stats.mannwhitneyu(to_prot, from_prot, alternative="two-sided")
            print(f"    SP_prev when switching TO protective: mean={to_prot.mean():.3f}, N={len(to_prot)}")
            print(f"    SP_prev when switching FROM protective: mean={from_prot.mean():.3f}, N={len(from_prot)}")
            print(f"    Mann-Whitney U={u_stat:.0f}, p={u_p:.4e}")
            results.append(("E", "changers_only", "sp_to_prot", f"{to_prot.mean():.3f}"))
            results.append(("E", "changers_only", "sp_from_prot", f"{from_prot.mean():.3f}"))
            results.append(("E", "changers_only", "MWU_p", f"{u_p:.4e}"))

    # 6. By agent type
    print(f"\n  --- Partial correlations by agent type ---")
    for atype in ["owner", "renter"]:
        sub = panel[panel["agent_type"] == atype][["sp_prev", "is_protective_t", "is_protective_prev"]].dropna()
        if len(sub) > 20:
            X_c = sub["is_protective_prev"].values.reshape(-1, 1)
            X_c_aug = np.column_stack([X_c, np.ones(len(X_c))])
            b1, _, _, _ = lstsq(X_c_aug, sub["sp_prev"].values, rcond=None)
            r1 = sub["sp_prev"].values - X_c_aug @ b1
            b2, _, _, _ = lstsq(X_c_aug, sub["is_protective_t"].values, rcond=None)
            r2 = sub["is_protective_t"].values - X_c_aug @ b2
            rho, pval = stats.spearmanr(r1, r2)
            print(f"    {atype}: partial rho={rho:.3f}, p={pval:.4e}, N={len(sub)}")
            results.append(("E", f"partial_corr_{atype}", "sp_prev|prot_prev",
                             f"rho={rho:.3f}, p={pval:.4e}"))

    return results


# ── ANALYSIS F: PA erosion with flood control (renters) ──────────────────
def analysis_f(df):
    print_section("ANALYSIS F: PA Erosion During Inaction Streaks (Renters)")

    results = []

    # Filter renters only
    renters = df[df["agent_type"] == "renter"].copy()

    # For each renter, find consecutive do_nothing streaks >= 3 years
    streak_records = []
    for uid, grp in renters.groupby("uid"):
        grp = grp.sort_values("year")
        actions = grp["executed_action"].values
        pa_vals = grp["construct_PA_LABEL_num"].values
        flood_vals = grp["flooded_this_year"].values
        years = grp["year"].values

        streak_start = None
        for i in range(len(grp)):
            if actions[i] == "do_nothing":
                if streak_start is None:
                    streak_start = i
            else:
                if streak_start is not None:
                    streak_len = i - streak_start
                    if streak_len >= 3:
                        # Record this streak
                        streak_pa = pa_vals[streak_start:i]
                        streak_flood = flood_vals[streak_start:i]
                        had_flood = any(f == True for f in streak_flood if not pd.isna(f))

                        valid_pa = [p for p in streak_pa if not pd.isna(p)]
                        if len(valid_pa) >= 2:
                            pa_start_val = valid_pa[0]
                            pa_end_val = valid_pa[-1]
                            streak_records.append({
                                "uid": uid,
                                "streak_start_year": years[streak_start],
                                "streak_length": streak_len,
                                "pa_start": pa_start_val,
                                "pa_end": pa_end_val,
                                "pa_change": pa_end_val - pa_start_val,
                                "had_flood": had_flood,
                            })
                    streak_start = None

        # Handle streak extending to end
        if streak_start is not None:
            streak_len = len(grp) - streak_start
            if streak_len >= 3:
                streak_pa = pa_vals[streak_start:]
                streak_flood = flood_vals[streak_start:]
                had_flood = any(f == True for f in streak_flood if not pd.isna(f))
                valid_pa = [p for p in streak_pa if not pd.isna(p)]
                if len(valid_pa) >= 2:
                    streak_records.append({
                        "uid": uid,
                        "streak_start_year": years[streak_start],
                        "streak_length": streak_len,
                        "pa_start": valid_pa[0],
                        "pa_end": valid_pa[-1],
                        "pa_change": valid_pa[-1] - valid_pa[0],
                        "had_flood": had_flood,
                    })

    streaks = pd.DataFrame(streak_records)
    print(f"\nConsecutive do_nothing streaks >= 3 years (renters): {len(streaks)}")

    if len(streaks) == 0:
        print("  No streaks found.")
        results.append(("F", "streaks", "N", "0"))
        return results

    print(f"  Mean streak length: {streaks['streak_length'].mean():.1f}")
    print(f"  With flood during streak: {streaks['had_flood'].sum()}")
    print(f"  Without flood during streak: {(~streaks['had_flood']).sum()}")

    for flood_label, flood_val in [("With flood", True), ("Without flood", False)]:
        sub = streaks[streaks["had_flood"] == flood_val]
        print(f"\n  {flood_label} (N={len(sub)}):")
        if len(sub) >= 3:
            mean_change = sub["pa_change"].mean()
            mean_start = sub["pa_start"].mean()
            mean_end = sub["pa_end"].mean()
            print(f"    Mean PA start: {mean_start:.3f}")
            print(f"    Mean PA end:   {mean_end:.3f}")
            print(f"    Mean PA change: {mean_change:+.3f}")

            if len(sub) >= 5:
                nonzero = sub["pa_change"][sub["pa_change"] != 0]
                if len(nonzero) >= 1:
                    w_stat, w_p = stats.wilcoxon(sub["pa_change"], alternative="two-sided")
                    print(f"    Wilcoxon signed-rank: W={w_stat:.0f}, p={w_p:.4e}")
                    results.append(("F", flood_label, "wilcoxon_p", f"{w_p:.4e}"))
                else:
                    print(f"    Wilcoxon: all PA changes = 0")
                    results.append(("F", flood_label, "wilcoxon_p", "all_zeros"))
            results.append(("F", flood_label, "N", str(len(sub))))
            results.append(("F", flood_label, "pa_change", f"{mean_change:+.3f}"))
            results.append(("F", flood_label, "pa_start", f"{mean_start:.3f}"))
            results.append(("F", flood_label, "pa_end", f"{mean_end:.3f}"))

    # Compare PA change between flood/no-flood streaks
    flood_changes = streaks[streaks["had_flood"]]["pa_change"]
    noflood_changes = streaks[~streaks["had_flood"]]["pa_change"]
    if len(flood_changes) >= 5 and len(noflood_changes) >= 5:
        u_stat, u_p = stats.mannwhitneyu(flood_changes, noflood_changes, alternative="two-sided")
        print(f"\n  Flood vs no-flood PA change comparison:")
        print(f"    Mann-Whitney U={u_stat:.0f}, p={u_p:.4e}")
        results.append(("F", "flood_vs_noflood", "MWU_p", f"{u_p:.4e}"))

    # Also do owners for completeness
    print(f"\n  --- Also for owners (do_nothing streaks >= 3 years) ---")
    owners = df[df["agent_type"] == "owner"].copy()
    owner_streaks = []
    for uid, grp in owners.groupby("uid"):
        grp = grp.sort_values("year")
        actions = grp["executed_action"].values
        pa_vals = grp["construct_PA_LABEL_num"].values
        flood_vals = grp["flooded_this_year"].values
        years = grp["year"].values

        streak_start = None
        for i in range(len(grp)):
            if actions[i] == "do_nothing":
                if streak_start is None:
                    streak_start = i
            else:
                if streak_start is not None:
                    streak_len = i - streak_start
                    if streak_len >= 3:
                        streak_pa = pa_vals[streak_start:i]
                        streak_flood = flood_vals[streak_start:i]
                        had_flood = any(f == True for f in streak_flood if not pd.isna(f))
                        valid_pa = [p for p in streak_pa if not pd.isna(p)]
                        if len(valid_pa) >= 2:
                            owner_streaks.append({
                                "pa_change": valid_pa[-1] - valid_pa[0],
                                "had_flood": had_flood,
                                "streak_length": streak_len,
                            })
                    streak_start = None
        if streak_start is not None:
            streak_len = len(grp) - streak_start
            if streak_len >= 3:
                streak_pa = pa_vals[streak_start:]
                streak_flood = flood_vals[streak_start:]
                had_flood = any(f == True for f in streak_flood if not pd.isna(f))
                valid_pa = [p for p in streak_pa if not pd.isna(p)]
                if len(valid_pa) >= 2:
                    owner_streaks.append({
                        "pa_change": valid_pa[-1] - valid_pa[0],
                        "had_flood": had_flood,
                        "streak_length": streak_len,
                    })

    odf = pd.DataFrame(owner_streaks)
    if len(odf) > 0:
        print(f"  Owner streaks: N={len(odf)}")
        for flood_label, flood_val in [("With flood", True), ("Without flood", False)]:
            sub = odf[odf["had_flood"] == flood_val]
            if len(sub) >= 3:
                print(f"    {flood_label} (N={len(sub)}): mean PA change = {sub['pa_change'].mean():+.3f}")

    return results


# ── MAIN ─────────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    df = prepare_data()
    print(f"Loaded {len(df)} records, {df['uid'].nunique()} unique agents, "
          f"{df['year'].nunique()} years")
    print(f"Agents by type: {df.groupby('agent_type')['uid'].nunique().to_dict()}")

    # Missing SP rate
    sp_missing = df["construct_SP_LABEL_num"].isna().mean()
    print(f"SP missing rate: {sp_missing:.1%}")

    all_results = []

    all_results.extend(analysis_a(df))
    all_results.extend(analysis_b(df))
    all_results.extend(analysis_c(df))
    all_results.extend(analysis_d(df))
    all_results.extend(analysis_e(df))
    all_results.extend(analysis_f(df))

    # Save results
    out_df = pd.DataFrame(all_results, columns=["analysis", "group", "metric", "value"])
    out_path = OUT_DIR / "rq3_feedback_rigorous.csv"
    out_df.to_csv(out_path, index=False)
    print(f"\n{'=' * 80}")
    print(f"  Results saved to: {out_path}")
    print(f"  Total result rows: {len(out_df)}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
