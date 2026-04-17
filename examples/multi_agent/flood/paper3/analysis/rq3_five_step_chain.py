from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pandas as pd
from scipy.stats import chi2_contingency


REPO_ROOT = Path(__file__).resolve().parents[5]
ANALYSIS_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ANALYSIS_DIR / "deep_synthesis" / "rq_deep"
PROFILES_CSV = REPO_ROOT / "examples/multi_agent/flood/data/agent_profiles_balanced.csv"

STEP1_CSV = OUTPUT_DIR / "rq3_step1_construct_validity.csv"
STEP2_CSV = OUTPUT_DIR / "rq3_step2_cross_sectional.csv"
STEP3_CSV = OUTPUT_DIR / "rq3_step3_within_agent.csv"
STEP4_CSV = OUTPUT_DIR / "rq3_step4_override.csv"
STEP5_CSV = OUTPUT_DIR / "rq3_step5_mg_owner.csv"
REPORT_MD = OUTPUT_DIR / "rq3_five_step_report.md"

ARM_PATHS = {
    "LEG_Full_42": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict/raw",
    "CLN_Full_42": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_42/gemma4_e4b_strict/raw",
    "CLN_Full_123": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_123/gemma4_e4b_strict/raw",
    "CLN_Flat_42": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_42/gemma4_e4b_strict/raw",
    "CLN_Flat_123": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_123/gemma4_e4b_strict/raw",
    "CLN_Flat_456": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_456/gemma4_e4b_strict/raw",
}

LABEL_ORDER = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def normalized_agent_type(raw: str) -> str:
    return raw.replace("household_", "")


def is_protective(action: str) -> bool:
    return action in {
        "buy_insurance",
        "buy_contents_insurance",
        "elevate_house",
        "relocate",
        "buyout_program",
    }


def is_insurance(action: str) -> bool:
    return action in {"buy_insurance", "buy_contents_insurance"}


def survey_pa_bin(score: float) -> str:
    if score < 2.0:
        return "L"
    if score < 3.0:
        return "ML"
    if score < 4.0:
        return "MH"
    return "H"


def cramers_v(chi2_value: float, n: int, rows: int, cols: int) -> float:
    if n <= 0 or min(rows, cols) <= 1:
        return float("nan")
    return math.sqrt(chi2_value / (n * (min(rows, cols) - 1)))


def load_profiles() -> pd.DataFrame:
    profiles = pd.read_csv(PROFILES_CSV, usecols=["agent_id", "pa_score"])
    return profiles.rename(columns={"pa_score": "survey_pa_score"})


def load_decisions() -> pd.DataFrame:
    profiles = load_profiles()
    rows: list[dict[str, object]] = []
    for arm, raw_dir in ARM_PATHS.items():
        for filename in ("household_owner_traces.jsonl", "household_renter_traces.jsonl"):
            for trace in iter_jsonl(raw_dir / filename):
                state_before = trace.get("state_before", {})
                state_after = trace.get("state_after", {})
                skill_proposal = trace.get("skill_proposal") or {}
                reasoning = skill_proposal.get("reasoning") or {}
                action = trace.get("approved_skill", {}).get("skill_name", "")
                rows.append(
                    {
                        "arm": arm,
                        "year": int(trace.get("year")),
                        "agent_id": trace.get("agent_id"),
                        "agent_type": normalized_agent_type(trace.get("agent_type", "")),
                        "mg": "MG" if bool(state_before.get("mg")) else "NMG",
                        "executed_action": action,
                        "protective": is_protective(action),
                        "is_insurance_action": is_insurance(action),
                        "do_nothing": action == "do_nothing",
                        "tp_label": reasoning.get("TP_LABEL"),
                        "sp_label": reasoning.get("SP_LABEL"),
                        "pa_label_llm": reasoning.get("PA_LABEL"),
                        "tp_reason": reasoning.get("TP_REASON", ""),
                        "sp_reason": reasoning.get("SP_REASON", ""),
                        "pa_reason": reasoning.get("PA_REASON", ""),
                        "y13_has_insurance": bool(state_after.get("has_insurance")) if int(trace.get("year")) == 13 else pd.NA,
                        "y13_cum_oop": float(state_after.get("cumulative_oop") or 0.0) if int(trace.get("year")) == 13 else pd.NA,
                    }
                )
    df = pd.DataFrame(rows)
    return df.merge(profiles, on="agent_id", how="left")


def step1_construct_validity(df: pd.DataFrame) -> pd.DataFrame:
    patterns = {
        "TP_flood_risk_pct": ("tp_reason", re.compile(r"\b(?:flood|risk)\b", re.IGNORECASE)),
        "SP_government_trust_pct": ("sp_reason", re.compile(r"\b(?:government|trust)\b", re.IGNORECASE)),
        "PA_home_attachment_pct": ("pa_reason", re.compile(r"\b(?:home|attachment)\b", re.IGNORECASE)),
    }
    rows: list[dict[str, object]] = []
    for (arm, agent_type), group in df.groupby(["arm", "agent_type"]):
        entry: dict[str, object] = {"arm": arm, "agent_type": agent_type, "n_decisions": len(group)}
        for column_name, (source_col, pattern) in patterns.items():
            entry[column_name] = group[source_col].fillna("").str.contains(pattern).mean()
        rows.append(entry)
    result = pd.DataFrame(rows).sort_values(["arm", "agent_type"])
    result.to_csv(STEP1_CSV, index=False)
    return result


def step2_cross_sectional(df: pd.DataFrame) -> pd.DataFrame:
    sp_rows = (
        df.groupby(["arm", "sp_label"], dropna=False)
        .agg(rate=("protective", "mean"), n=("agent_id", "size"))
        .reset_index()
        .rename(columns={"sp_label": "level"})
    )
    sp_rows["analysis"] = "sp_protection_rate"

    renter = df[df["agent_type"] == "renter"].copy()
    renter["survey_pa_bin"] = renter["survey_pa_score"].astype(float).map(survey_pa_bin)
    pa_rows = (
        renter.groupby(["arm", "survey_pa_bin"], dropna=False)
        .agg(rate=("do_nothing", "mean"), n=("agent_id", "size"))
        .reset_index()
        .rename(columns={"survey_pa_bin": "level"})
    )
    pa_rows["analysis"] = "survey_pa_bin_renter_dn_rate"

    result = pd.concat([sp_rows, pa_rows], ignore_index=True).sort_values(["analysis", "arm", "level"])
    result.to_csv(STEP2_CSV, index=False)
    return result


def step3_within_agent(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values(["arm", "agent_id", "year"]).copy()
    ordered["sp_score"] = ordered["sp_label"].map(LABEL_ORDER)
    ordered["prev_sp_score"] = ordered.groupby(["arm", "agent_id"])["sp_score"].shift(1)
    ordered["prev_protective"] = ordered.groupby(["arm", "agent_id"])["protective"].shift(1)

    transitions = ordered.dropna(subset=["prev_sp_score", "sp_score", "prev_protective"]).copy()
    transitions["sp_transition"] = transitions.apply(
        lambda row: "SP_up"
        if row["sp_score"] > row["prev_sp_score"]
        else ("SP_down" if row["sp_score"] < row["prev_sp_score"] else "SP_same"),
        axis=1,
    )
    transitions["action_transition"] = transitions.apply(
        lambda row: "to_prot"
        if (not bool(row["prev_protective"]) and bool(row["protective"]))
        else ("to_dn" if (bool(row["prev_protective"]) and not bool(row["protective"])) else "same"),
        axis=1,
    )

    rows: list[dict[str, object]] = []
    for arm, group in transitions.groupby("arm"):
        matrix = pd.crosstab(group["sp_transition"], group["action_transition"]).reindex(
            index=["SP_up", "SP_same", "SP_down"],
            columns=["to_prot", "to_dn", "same"],
            fill_value=0,
        )
        chi2_value, p_value, _, _ = chi2_contingency(matrix)
        effect = cramers_v(chi2_value, int(matrix.values.sum()), matrix.shape[0], matrix.shape[1])
        total = int(matrix.values.sum())
        for sp_transition, row in matrix.iterrows():
            for action_transition, count in row.items():
                rows.append(
                    {
                        "arm": arm,
                        "sp_transition": sp_transition,
                        "action_transition": action_transition,
                        "count": int(count),
                        "row_pct": (count / row.sum()) if row.sum() else 0.0,
                        "chi2": chi2_value,
                        "p_value": p_value,
                        "cramers_v": effect,
                        "n_pairs": total,
                    }
                )
    result = pd.DataFrame(rows).sort_values(["arm", "sp_transition", "action_transition"])
    result.to_csv(STEP3_CSV, index=False)
    return result


def step4_override(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for arm, group in df.groupby("arm"):
        quadrant_a = group[group["tp_label"].isin(["H", "VH"]) & group["sp_label"].isin(["H", "VH"])]
        quadrant_b = group[group["sp_label"] == "L"]
        rows.append(
            {
                "arm": arm,
                "metric": "A_tp_hvh_sp_hvh_to_dn",
                "rate": quadrant_a["do_nothing"].mean() if len(quadrant_a) else float("nan"),
                "n": len(quadrant_a),
            }
        )
        rows.append(
            {
                "arm": arm,
                "metric": "B_sp_l_to_insurance",
                "rate": quadrant_b["is_insurance_action"].mean() if len(quadrant_b) else float("nan"),
                "n": len(quadrant_b),
            }
        )
    result = pd.DataFrame(rows).sort_values(["arm", "metric"])
    result.to_csv(STEP4_CSV, index=False)
    return result


def step5_mg_owner(df: pd.DataFrame) -> pd.DataFrame:
    owner = df[df["agent_type"] == "owner"].copy()
    y13 = owner[owner["year"] == 13].copy()
    pooled = (
        owner.groupby(["arm", "mg"], dropna=False)
        .agg(
            sp_l_pct=("sp_label", lambda s: (s == "L").mean()),
            survey_pa_score_mean=("survey_pa_score", "mean"),
            pooled_dn_pct=("do_nothing", "mean"),
        )
        .reset_index()
    )
    y13_summary = (
        y13.groupby(["arm", "mg"], dropna=False)
        .agg(y13_ins_pct=("y13_has_insurance", "mean"), y13_cum_oop=("y13_cum_oop", "mean"))
        .reset_index()
    )
    result = pooled.merge(y13_summary, on=["arm", "mg"], how="left")
    result["profile"] = result["mg"].map({"MG": "MG-Owner", "NMG": "NMG-Owner"})
    result = result[
        ["arm", "profile", "sp_l_pct", "survey_pa_score_mean", "pooled_dn_pct", "y13_ins_pct", "y13_cum_oop"]
    ].sort_values(["arm", "profile"])
    result.to_csv(STEP5_CSV, index=False)
    return result


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_decisions()

    step1 = step1_construct_validity(df)
    step2 = step2_cross_sectional(df)
    step3 = step3_within_agent(df)
    step4 = step4_override(df)
    step5 = step5_mg_owner(df)

    report_lines = [
        "# RQ3 Five-Step Chain",
        "",
        "## Step 1 Construct Validity",
        "",
        step1.to_markdown(index=False),
        "",
        "## Step 2 Cross-Sectional Tables",
        "",
        step2.head(24).to_markdown(index=False),
        "",
        "## Step 3 Within-Agent SP Transition Summary",
        "",
        step3.groupby("arm")[["chi2", "p_value", "cramers_v", "n_pairs"]].first().reset_index().to_markdown(index=False),
        "",
        "## Step 4 Deliberative Override",
        "",
        step4.to_markdown(index=False),
        "",
        "## Step 5 MG-Owner vs NMG-Owner",
        "",
        step5.to_markdown(index=False),
        "",
    ]
    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")

    print(
        "rq3_five_step_chain: "
        f"rc=0 step1={len(step1)} step2={len(step2)} step3={len(step3)} step4={len(step4)} step5={len(step5)} files=6"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
