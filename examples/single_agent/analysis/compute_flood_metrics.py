"""Compute EHE, IBR, and Relocation Rate for flood experiments across models and conditions.

Handles:
- LLM CSVs: yearly_decision column
- Rulebased CSVs: cumulative state "decision" column -> derive yearly actions from transitions
- EHE: aggregate entropy, relocated -> relocate (included, not excluded)
- IBR: R1 (high threat inaction), R3 (low threat relocate), R4 (low threat elevate)
  R5 (re-elevation) tracked but excluded from IBR per EDT2
"""
import pandas as pd
import numpy as np
import os

BASE = "C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/examples/single_agent/results"
MODELS = ["gemma3_4b", "gemma3_12b", "gemma3_27b", "ministral3_3b", "ministral3_8b", "ministral3_14b"]
RUNS = ["Run_1", "Run_2", "Run_3", "Run_4", "Run_5"]
K = 4  # do_nothing, buy_insurance, elevate_house, relocate

ACTION_MAP = {
    "do_nothing": "do_nothing",
    "buy_insurance": "buy_insurance",
    "elevate_house": "elevate_house",
    "relocate": "relocate",
    "buy insurance": "buy_insurance",
    "elevate house": "elevate_house",
    "elevate": "elevate_house",
    "insurance": "buy_insurance",
    "relocation": "relocate",
    "do nothing": "do_nothing",
    "nothing": "do_nothing",
    "relocated": "relocate",  # map to relocate for EHE; excluded from IBR separately
}


def normalize_action(a):
    if pd.isna(a):
        return "do_nothing"
    a = str(a).strip().lower().replace(" ", "_")
    return ACTION_MAP.get(a, a)


def compute_ehe(actions):
    """Aggregate EHE = H/log2(k), k=4. All actions pooled across years."""
    counts = actions.value_counts()
    total = counts.sum()
    if total == 0:
        return 0.0
    probs = counts / total
    probs = probs[probs > 0]
    H = -np.sum(probs * np.log2(probs))
    return H / np.log2(K)


def compute_ibr(df):
    """IBR = (R1+R3+R4) / total * 100.  R5 (re-elevation) excluded per EDT2 definition."""
    total = len(df)
    if total == 0:
        return 0.0

    ta = df["threat_appraisal"].astype(str).str.strip().str.upper()
    action = df["action_norm"]
    elevated = df["elevated"].astype(bool) if "elevated" in df.columns else pd.Series(False, index=df.index)

    high_threat = ta.isin(["H", "VH"])
    low_threat = ta.isin(["VL", "L"])

    r1 = int((high_threat & (action == "do_nothing")).sum())
    r3 = int((low_threat & (action == "relocate")).sum())
    r4 = int((low_threat & (action == "elevate_house")).sum())
    r5 = int((elevated & (action == "elevate_house")).sum())  # tracked but excluded from IBR

    ibr = (r1 + r3 + r4) / total * 100
    return ibr, {"R1": r1, "R3": r3, "R4": r4, "R5_excluded": r5, "total": total}


def compute_relocation_rate(df_full):
    """Cumulative % of agents relocated by year 10 (using full df including relocated rows)."""
    max_year = df_full.groupby("agent_id")["year"].max()
    final = df_full.merge(max_year.rename("max_year"), left_on="agent_id", right_index=True)
    final = final[final["year"] == final["max_year"]]
    if len(final) == 0:
        return 0.0
    relocated = final["relocated"].astype(bool).sum()
    return relocated / len(final) * 100


def process_llm_csv(path):
    """Process LLM experiment CSV.
    EHE: all rows (relocated -> relocate).
    IBR: exclude relocated rows (only active decisions have threat_appraisal).
    """
    df = pd.read_csv(path, encoding="utf-8")
    df = df[df["year"] <= 10]
    dec_col = "yearly_decision" if "yearly_decision" in df.columns else "decision"
    df["action_norm"] = df[dec_col].apply(normalize_action)

    reloc = compute_relocation_rate(df)

    # EHE uses ALL rows (relocated already mapped to relocate)
    ehe = compute_ehe(df["action_norm"])

    # IBR excludes post-relocation rows (no meaningful threat appraisal)
    active = df[df[dec_col].astype(str).str.strip().str.lower() != "relocated"].copy()
    ibr_val, ibr_detail = compute_ibr(active)

    return ehe, ibr_val, reloc, len(active), ibr_detail


def derive_rulebased_yearly_actions(df):
    """Derive yearly actions from rulebased cumulative state transitions.

    The rulebased 'decision' column shows cumulative state, not yearly action.
    We derive yearly action by comparing state changes year-over-year per agent.
    """
    df = df.sort_values(["agent_id", "year"])
    actions = []

    for agent_id, agent_df in df.groupby("agent_id"):
        prev_elevated = False
        prev_insured = False
        prev_relocated = False

        for _, row in agent_df.iterrows():
            cur_elevated = bool(row["elevated"])
            cur_insured = bool(row["has_insurance"])
            cur_relocated = bool(row["relocated"])

            if cur_relocated and not prev_relocated:
                action = "relocate"
            elif cur_relocated and prev_relocated:
                action = "__already_relocated__"
            elif cur_elevated and not prev_elevated:
                # Newly elevated this year
                action = "elevate_house"
            elif cur_insured and not prev_insured:
                action = "buy_insurance"
            elif not cur_insured and prev_insured:
                # Dropped insurance - count as do_nothing (lapse)
                action = "do_nothing"
            elif not cur_elevated and not cur_insured:
                action = "do_nothing"
            else:
                # Maintained existing state
                action = "do_nothing"

            actions.append(action)
            prev_elevated = cur_elevated
            prev_insured = cur_insured
            prev_relocated = cur_relocated

    df = df.copy()
    df["action_norm"] = actions
    return df


def process_rulebased_csv(path):
    """Process rulebased PMT CSV with state-transition-derived actions."""
    df = pd.read_csv(path, encoding="utf-8")
    df = df[df["year"] <= 10]

    df = derive_rulebased_yearly_actions(df)

    reloc = compute_relocation_rate(df)

    # EHE: map __already_relocated__ → relocate for consistency
    ehe_actions = df["action_norm"].replace("__already_relocated__", "relocate")
    ehe = compute_ehe(ehe_actions)

    active = df[df["action_norm"] != "__already_relocated__"].copy()

    # No threat_appraisal in rulebased
    ibr_val = float("nan")
    ibr_detail = None

    return ehe, ibr_val, reloc, len(active), ibr_detail


def main():
    results = []

    # 1. Governed (Group_C)
    for model in MODELS:
        for i, run in enumerate(RUNS):
            path = f"{BASE}/JOH_FINAL/{model}/Group_C/{run}/simulation_log.csv"
            if os.path.exists(path):
                ehe, ibr, reloc, n, _ = process_llm_csv(path)
                results.append({"model": model, "condition": "governed", "seed": i + 1,
                                "ehe": ehe, "ibr": ibr, "reloc": reloc, "n": n})
            else:
                print(f"MISSING: {path}")

    # 2. Disabled (Group_C_disabled)
    for model in MODELS:
        for i, run in enumerate(RUNS):
            path = f"{BASE}/JOH_ABLATION_DISABLED/{model}/Group_C_disabled/{run}/simulation_log.csv"
            if os.path.exists(path):
                ehe, ibr, reloc, n, _ = process_llm_csv(path)
                results.append({"model": model, "condition": "disabled", "seed": i + 1,
                                "ehe": ehe, "ibr": ibr, "reloc": reloc, "n": n})
            else:
                print(f"MISSING: {path}")

    # 3. Rulebased (PMT)
    for i, run in enumerate(RUNS):
        path = f"{BASE}/rulebased/{run}/simulation_log.csv"
        if os.path.exists(path):
            ehe, ibr, reloc, n, _ = process_rulebased_csv(path)
            results.append({"model": "rulebased_PMT", "condition": "PMT", "seed": i + 1,
                            "ehe": ehe, "ibr": ibr, "reloc": reloc, "n": n})

    df_results = pd.DataFrame(results)

    # ========== PER-SEED TABLE ==========
    print("\n" + "=" * 100)
    print("PER-SEED RESULTS (relocated rows excluded from EHE/IBR)")
    print("=" * 100)
    hdr = f"{'Model':<20} {'Condition':<15} {'Seed':>4} {'EHE':>8} {'IBR%':>8} {'Reloc%':>8} {'N_active':>8}"
    print(hdr)
    print("-" * 85)
    for _, r in df_results.sort_values(["model", "condition", "seed"]).iterrows():
        print(f"{r['model']:<20} {r['condition']:<15} {int(r['seed']):>4} "
              f"{r['ehe']:>8.4f} {r['ibr']:>8.2f} {r['reloc']:>8.2f} {int(r['n']):>8}")

    # ========== SUMMARY TABLE ==========
    print("\n" + "=" * 130)
    print("SUMMARY TABLE (mean +/- sd across seeds)")
    print("=" * 130)
    hdr2 = (f"{'Model':<20} {'Condition':<15} {'Seeds':>5} "
            f"{'EHE (mean+/-sd)':<22} {'IBR% (mean+/-sd)':<22} {'Reloc% (mean+/-sd)':<22}")
    print(hdr2)
    print("-" * 110)

    for (model, cond), grp in df_results.groupby(["model", "condition"], sort=True):
        n_seeds = len(grp)
        ehe_m = grp["ehe"].mean()
        ehe_s = grp["ehe"].std(ddof=1) if len(grp) > 1 else 0
        ibr_m = grp["ibr"].mean()
        ibr_s = grp["ibr"].std(ddof=1) if len(grp) > 1 else 0
        reloc_m = grp["reloc"].mean()
        reloc_s = grp["reloc"].std(ddof=1) if len(grp) > 1 else 0

        ehe_str = f"{ehe_m:.4f} +/- {ehe_s:.4f}"
        ibr_str = f"{ibr_m:.2f} +/- {ibr_s:.2f}" if not np.isnan(ibr_m) else "N/A"
        reloc_str = f"{reloc_m:.2f} +/- {reloc_s:.2f}"

        print(f"{model:<20} {cond:<15} {n_seeds:>5} "
              f"{ehe_str:<22} {ibr_str:<22} {reloc_str:<22}")

    # ========== MARKDOWN TABLE ==========
    print("\n" + "=" * 130)
    print("MARKDOWN TABLE")
    print("=" * 130)
    print("| Model | Condition | Seeds | EHE (mean +/- sd) | IBR% (mean +/- sd) | Reloc% (mean +/- sd) |")
    print("|-------|-----------|-------|-------------------|-------------------|---------------------|")

    for (model, cond), grp in df_results.groupby(["model", "condition"], sort=True):
        n_seeds = len(grp)
        ehe_m = grp["ehe"].mean()
        ehe_s = grp["ehe"].std(ddof=1) if len(grp) > 1 else 0
        ibr_m = grp["ibr"].mean()
        ibr_s = grp["ibr"].std(ddof=1) if len(grp) > 1 else 0
        reloc_m = grp["reloc"].mean()
        reloc_s = grp["reloc"].std(ddof=1) if len(grp) > 1 else 0

        ehe_str = f"{ehe_m:.4f} +/- {ehe_s:.4f}"
        ibr_str = f"{ibr_m:.2f} +/- {ibr_s:.2f}" if not np.isnan(ibr_m) else "N/A"
        reloc_str = f"{reloc_m:.2f} +/- {reloc_s:.2f}"

        print(f"| {model} | {cond} | {n_seeds} | {ehe_str} | {ibr_str} | {reloc_str} |")

    # ========== GOVERNED vs DISABLED COMPARISON ==========
    print("\n" + "=" * 130)
    print("GOVERNED vs DISABLED COMPARISON (delta = disabled - governed)")
    print("=" * 130)
    print(f"{'Model':<20} {'dEHE':>10} {'dIBR%':>10} {'dReloc%':>10}")
    print("-" * 55)

    for model in MODELS:
        gov = df_results[(df_results["model"] == model) & (df_results["condition"] == "governed")]
        dis = df_results[(df_results["model"] == model) & (df_results["condition"] == "disabled")]
        if len(gov) > 0 and len(dis) > 0:
            d_ehe = dis["ehe"].mean() - gov["ehe"].mean()
            d_ibr = dis["ibr"].mean() - gov["ibr"].mean()
            d_reloc = dis["reloc"].mean() - gov["reloc"].mean()
            print(f"{model:<20} {d_ehe:>+10.4f} {d_ibr:>+10.2f} {d_reloc:>+10.2f}")

    # ========== IBR DECOMPOSITION ==========
    print("\n" + "=" * 100)
    print("IBR DECOMPOSITION (governed gemma3_4b, all seeds)")
    print("=" * 100)
    for i, run in enumerate(RUNS):
        path = f"{BASE}/JOH_FINAL/gemma3_4b/Group_C/{run}/simulation_log.csv"
        df_d = pd.read_csv(path, encoding="utf-8")
        df_d = df_d[df_d["year"] <= 10]
        df_d["action_norm"] = df_d["yearly_decision"].apply(normalize_action)
        active = df_d[df_d["yearly_decision"].astype(str).str.strip().str.lower() != "relocated"]
        _, detail = compute_ibr(active)
        print(f"  {run}: R1={detail['R1']}, R3={detail['R3']}, R4={detail['R4']}, R5={detail['R5_excluded']}, "
              f"total_active={detail['total']}")

    # ========== ACTION DISTRIBUTIONS (sample) ==========
    print("\n" + "=" * 100)
    print("ACTION DISTRIBUTIONS (gemma3_4b, Run_1)")
    print("=" * 100)
    for cond_label, path in [
        ("governed", f"{BASE}/JOH_FINAL/gemma3_4b/Group_C/Run_1/simulation_log.csv"),
        ("disabled", f"{BASE}/JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_1/simulation_log.csv"),
    ]:
        df_c = pd.read_csv(path, encoding="utf-8")
        df_c = df_c[df_c["year"] <= 10]
        df_c["action_norm"] = df_c["yearly_decision"].apply(normalize_action)
        relocated_mask = df_c["yearly_decision"].astype(str).str.strip().str.lower() == "relocated"
        active = df_c[~relocated_mask]
        print(f"\n  {cond_label} (N_active={len(active)}, N_relocated_rows={relocated_mask.sum()}):")
        print(f"  {active['action_norm'].value_counts().to_string()}")

    # Rulebased derived actions
    print("\n  rulebased (derived from state transitions):")
    path_rb = f"{BASE}/rulebased/Run_1/simulation_log.csv"
    df_rb = pd.read_csv(path_rb, encoding="utf-8")
    df_rb = df_rb[df_rb["year"] <= 10]
    df_rb = derive_rulebased_yearly_actions(df_rb)
    rb_relocated = (df_rb["action_norm"] == "__already_relocated__")
    active_rb = df_rb[~rb_relocated]
    print(f"  N_active={len(active_rb)}, N_relocated_rows={rb_relocated.sum()}")
    print(f"  {active_rb['action_norm'].value_counts().to_string()}")


if __name__ == "__main__":
    main()
