import json
from pathlib import Path

import pandas as pd

DEFAULT_RESULTS_DIR = Path("examples/multi_agent/results_unified/llama3_2_3b_strict")

DECISION_ORDER = [
    "do_nothing",
    "buy_insurance",
    "buy_contents_insurance",
    "elevate_house",
    "buyout_program",
    "relocate",
    "unknown",
]

DECISION_COLORS = {
    "do_nothing": "#9aa0a6",
    "buy_insurance": "#1f77b4",
    "buy_contents_insurance": "#4c78a8",
    "elevate_house": "#2ca02c",
    "buyout_program": "#d62728",
    "relocate": "#9467bd",
    "unknown": "#cccccc",
}


def _extract_decision(obj):
    for key in ("approved_skill", "skill_proposal"):
        data = obj.get(key) or {}
        name = data.get("skill_name")
        if name:
            return str(name).strip()
    return "unknown"


def load_household_df(results_dir):
    results_dir = Path(results_dir)
    raw_dir = results_dir / "raw"
    records = []

    for filename in ("household_owner_traces.jsonl", "household_renter_traces.jsonl"):
        path = raw_dir / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                state = obj.get("state_after") or obj.get("state_before") or {}
                records.append(
                    {
                        "agent_id": obj.get("agent_id"),
                        "step_id": obj.get("step_id"),
                        "agent_type": state.get("agent_type"),
                        "decision": _extract_decision(obj),
                        "mg": state.get("mg"),
                        "elevated": state.get("elevated"),
                        "has_insurance": state.get("has_insurance"),
                        "relocated": state.get("relocated"),
                        "cumulative_damage": state.get("cumulative_damage"),
                        "tp_score": state.get("tp_score"),
                        "cp_score": state.get("cp_score"),
                        "sp_score": state.get("sp_score"),
                        "sc_score": state.get("sc_score"),
                        "pa_score": state.get("pa_score"),
                    }
                )

    return pd.DataFrame(records)


def load_institutional_df(results_dir):
    results_dir = Path(results_dir)
    raw_dir = results_dir / "raw"
    records = []

    for filename, rate_key, agent_type in (
        ("government_traces.jsonl", "subsidy_rate", "government"),
        ("insurance_traces.jsonl", "premium_rate", "insurance"),
    ):
        path = raw_dir / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                state = obj.get("state_after") or obj.get("state_before") or {}
                rate = state.get(rate_key)
                if rate is None:
                    continue
                records.append(
                    {
                        "step_id": obj.get("step_id"),
                        "agent_type": agent_type,
                        rate_key: rate,
                    }
                )

    df = pd.DataFrame(records)
    if df.empty:
        return df

    grouped = df.groupby(["step_id", "agent_type"]).last().reset_index()
    return grouped


def ensure_output_dir(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
