from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[5]
ANALYSIS_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ANALYSIS_DIR / "deep_synthesis" / "rq_deep"
BURDEN_CSV = OUTPUT_DIR / "rq2_premium_burden.csv"
QUARTILE_CSV = OUTPUT_DIR / "rq2_burden_quartile_protection.csv"
REPORT_MD = OUTPUT_DIR / "rq2_mechanism_report.md"

ARM_PATHS = {
    "LEG_Full_42": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_legacy/seed_42/gemma4_e4b_strict/raw",
    "CLN_Full_42": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_42/gemma4_e4b_strict/raw",
    "CLN_Full_123": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b_clean/seed_123/gemma4_e4b_strict/raw",
    "CLN_Flat_42": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_42/gemma4_e4b_strict/raw",
    "CLN_Flat_123": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_123/gemma4_e4b_strict/raw",
    "CLN_Flat_456": REPO_ROOT / "examples/multi_agent/flood/paper3/results/paper3_gemma4_ablation_flat_clean/seed_456/gemma4_e4b_strict/raw",
}


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


def load_decisions() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for arm, raw_dir in ARM_PATHS.items():
        for filename in ("household_owner_traces.jsonl", "household_renter_traces.jsonl"):
            for trace in iter_jsonl(raw_dir / filename):
                state_before = trace.get("state_before", {})
                env = trace.get("environment_context", {})
                approved = trace.get("approved_skill", {})
                income = float(state_before.get("income") or 0.0)
                property_value = float(
                    state_before.get("property_value")
                    or (state_before.get("rcv_building") or 0.0) + (state_before.get("rcv_contents") or 0.0)
                )
                effective_rate = (
                    float(env.get("premium_rate") or 0.0)
                    * (1.0 - float(env.get("crs_discount") or 0.0))
                    * (1.0 - float(env.get("subsidy_rate") or 0.0))
                )
                annual_premium = property_value * effective_rate
                premium_burden_pct = (annual_premium / income * 100.0) if income > 0 else pd.NA
                action = approved.get("skill_name", "")
                rows.append(
                    {
                        "arm": arm,
                        "year": int(trace.get("year")),
                        "agent_id": trace.get("agent_id"),
                        "agent_type": normalized_agent_type(trace.get("agent_type", "")),
                        "mg": "MG" if bool(state_before.get("mg")) else "NMG",
                        "income": income,
                        "property_value": property_value,
                        "premium_burden_pct": premium_burden_pct,
                        "executed_action": action,
                        "protection": is_protective(action),
                        "do_nothing": action == "do_nothing",
                    }
                )
    return pd.DataFrame(rows)


def quartile_labels(series: pd.Series) -> pd.Series:
    ranked = series.rank(method="first")
    return pd.qcut(ranked, 4, labels=["Q1", "Q2", "Q3", "Q4"])


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_decisions().dropna(subset=["premium_burden_pct"]).copy()

    burden = (
        df.groupby(["year", "arm", "agent_type", "mg"], dropna=False)["premium_burden_pct"]
        .agg(
            premium_burden_mean="mean",
            premium_burden_p25=lambda s: s.quantile(0.25),
            premium_burden_p50="median",
            premium_burden_p75=lambda s: s.quantile(0.75),
            n_decisions="size",
        )
        .reset_index()
        .sort_values(["arm", "year", "agent_type", "mg"])
    )
    burden.to_csv(BURDEN_CSV, index=False)

    df["burden_quartile"] = (
        df.groupby(["arm", "agent_type"], group_keys=False)["premium_burden_pct"].transform(quartile_labels)
    )
    quartiles = (
        df.groupby(["arm", "agent_type", "burden_quartile"], dropna=False, observed=False)
        .agg(
            protection_rate=("protection", "mean"),
            dn_rate=("do_nothing", "mean"),
            premium_burden_mean=("premium_burden_pct", "mean"),
            n_decisions=("agent_id", "size"),
        )
        .reset_index()
        .sort_values(["agent_type", "arm", "burden_quartile"])
    )
    quartiles.to_csv(QUARTILE_CSV, index=False)

    owner_q1 = quartiles[(quartiles["agent_type"] == "owner") & (quartiles["burden_quartile"] == "Q1")]
    renter_q1 = quartiles[(quartiles["agent_type"] == "renter") & (quartiles["burden_quartile"] == "Q1")]
    owner_gap = owner_q1.sort_values("protection_rate", ascending=False).head(3)
    renter_gap = renter_q1.sort_values("protection_rate", ascending=False).head(3)

    report_lines = [
        "# RQ2 Mechanism Decomposition",
        "",
        "Effective premium burden is computed as:",
        "",
        "`premium_rate * (1 - crs_discount) * (1 - subsidy_rate) * property_value / income * 100`",
        "",
        "## Lowest-Burden Owner Protection",
        "",
        owner_gap[["arm", "protection_rate", "dn_rate", "premium_burden_mean", "n_decisions"]].to_markdown(index=False),
        "",
        "## Lowest-Burden Renter Protection",
        "",
        renter_gap[["arm", "protection_rate", "dn_rate", "premium_burden_mean", "n_decisions"]].to_markdown(index=False),
        "",
        "## Yearly Premium Burden Summary",
        "",
        burden.groupby(["arm", "agent_type"])["premium_burden_mean"].mean().reset_index().to_markdown(index=False),
        "",
    ]
    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")

    print(
        "rq2_mechanism_decomposition: "
        f"rc=0 burden_rows={len(burden)} quartile_rows={len(quartiles)} files=3 out={OUTPUT_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
