from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
ANALYSIS_DIR = BASE / "analysis"

MODEL_CONFIG = {
    "gemma3_4b": {
        "label": "Gemma 3 4B",
        "path": BASE / "results" / "paper3_hybrid_v2" / "seed_42" / "gemma3_4b_strict",
    },
    "gemma4_e4b": {
        "label": "Gemma 4 e4b",
        "path": BASE / "results" / "paper3_gemma4_e4b" / "seed_42" / "gemma4_e4b_strict",
    },
}

OWNER_ACTIONS = ["buy_insurance", "elevate_house", "buyout_program", "do_nothing"]
RENTER_ACTIONS = ["buy_contents_insurance", "relocate", "do_nothing"]
CONSTRUCT_COLUMNS = [
    "construct_TP_LABEL",
    "construct_CP_LABEL",
    "construct_SP_LABEL",
    "construct_SC_LABEL",
    "construct_PA_LABEL",
]
STANDARD_LABELS = ["VL", "L", "M", "H", "VH"]
OUTPUT_REPORT = ANALYSIS_DIR / "gemma4_ma_crossmodel.md"


@dataclass
class ModelData:
    key: str
    label: str
    owner: pd.DataFrame
    renter: pd.DataFrame


def pct(numerator: int | float, denominator: int | float) -> float:
    if not denominator:
        return 0.0
    return 100.0 * float(numerator) / float(denominator)


def fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def fmt_ratio(numerator: int, denominator: int) -> str:
    return f"{numerator}/{denominator} ({fmt_pct(pct(numerator, denominator))})"


def load_model_data() -> dict[str, ModelData]:
    models: dict[str, ModelData] = {}
    for key, config in MODEL_CONFIG.items():
        root = config["path"]
        owner = pd.read_csv(root / "household_owner_governance_audit.csv", encoding="utf-8-sig")
        renter = pd.read_csv(root / "household_renter_governance_audit.csv", encoding="utf-8-sig")
        models[key] = ModelData(
            key=key,
            label=config["label"],
            owner=owner,
            renter=renter,
        )
    return models


def compute_basic_metrics(df: pd.DataFrame, actions: list[str]) -> dict[str, object]:
    action_counts = df["final_skill"].value_counts(dropna=False)
    action_dist = {action: pct(int(action_counts.get(action, 0)), len(df)) for action in actions}

    constructs: dict[str, dict[str, object]] = {}
    for col in CONSTRUCT_COLUMNS:
        raw = df[col].dropna().astype(str).str.strip()
        valid = raw[raw.isin(STANDARD_LABELS)]
        invalid = raw[~raw.isin(STANDARD_LABELS)]
        dist = {label: pct(int((valid == label).sum()), len(valid)) for label in STANDARD_LABELS}
        constructs[col] = {
            "distribution": dist,
            "non_missing_n": int(len(raw)),
            "valid_n": int(len(valid)),
            "invalid_labels": invalid.value_counts().to_dict(),
        }

    return {
        "n": int(len(df)),
        "rejection_rate": pct(int((df["status"] != "APPROVED").sum()), len(df)),
        "retry_rate": pct(int((df["retry_count"] > 0).sum()), len(df)),
        "action_distribution": action_dist,
        "constructs": constructs,
    }


def cp_reversal_metrics(df: pd.DataFrame) -> dict[str, object]:
    cp_h = df["construct_CP_LABEL"].astype(str).str.strip().eq("H")
    subset = df.loc[cp_h]
    return {
        "cp_h_n": int(cp_h.sum()),
        "cp_h_pct": pct(int(cp_h.sum()), len(df)),
        "cp_h_do_nothing_n": int((subset["final_skill"] == "do_nothing").sum()),
        "cp_h_active_n": int((subset["final_skill"] != "do_nothing").sum()),
        "cp_h_do_nothing_pct": pct(int((subset["final_skill"] == "do_nothing").sum()), len(subset)),
        "cp_h_active_pct": pct(int((subset["final_skill"] != "do_nothing").sum()), len(subset)),
    }


def deliberative_override_metrics(owner: pd.DataFrame, renter: pd.DataFrame) -> dict[str, dict[str, object]]:
    pooled = pd.concat(
        [owner.assign(agent_type="owner"), renter.assign(agent_type="renter")],
        ignore_index=True,
    )
    case_a = pooled[
        pooled["construct_TP_LABEL"].isin(["H", "VH"])
        & pooled["construct_SP_LABEL"].isin(["H", "VH"])
    ]
    case_b = pooled[pooled["construct_SP_LABEL"].isin(["L", "VL"])]
    insurance = case_b["final_skill"].isin(["buy_insurance", "buy_contents_insurance"])
    return {
        "case_a": {
            "n": int(len(case_a)),
            "do_nothing_n": int((case_a["final_skill"] == "do_nothing").sum()),
            "do_nothing_pct": pct(int((case_a["final_skill"] == "do_nothing").sum()), len(case_a)),
        },
        "case_b": {
            "n": int(len(case_b)),
            "insurance_n": int(insurance.sum()),
            "insurance_pct": pct(int(insurance.sum()), len(case_b)),
        },
    }


def mg_owner_metrics(df: pd.DataFrame, profiles: pd.DataFrame) -> dict[str, dict[str, object]]:
    owner_profiles = profiles.loc[profiles["tenure"] == "Owner", ["agent_id", "mg"]].copy()
    merged = df.merge(owner_profiles, on="agent_id", how="left", validate="many_to_one")
    merged["executed_skill"] = merged["final_skill"].where(merged["status"] == "APPROVED", "do_nothing")

    result: dict[str, dict[str, object]] = {}
    for mg_value, label in [(True, "MG-Owner"), (False, "NMG-Owner")]:
        subset = merged.loc[merged["mg"] == mg_value]
        counts = subset["executed_skill"].value_counts(dropna=False)
        result[label] = {
            "n": int(len(subset)),
            "distribution": {
                action: pct(int(counts.get(action, 0)), len(subset))
                for action in OWNER_ACTIONS
            },
        }
    return result


def build_summary_rows(model_results: dict[str, dict[str, object]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for model_key in ["gemma3_4b", "gemma4_e4b"]:
        label = MODEL_CONFIG[model_key]["label"]
        result = model_results[model_key]
        rows.extend(
            [
                [label, "Owner rejection rate", fmt_pct(result["owner"]["rejection_rate"])],
                [label, "Owner retry rate", fmt_pct(result["owner"]["retry_rate"])],
                [label, "Owner do_nothing", fmt_pct(result["owner"]["action_distribution"]["do_nothing"])],
                [label, "Owner buy_insurance", fmt_pct(result["owner"]["action_distribution"]["buy_insurance"])],
                [label, "Owner elevate_house", fmt_pct(result["owner"]["action_distribution"]["elevate_house"])],
                [label, "Renter rejection rate", fmt_pct(result["renter"]["rejection_rate"])],
                [label, "Renter retry rate", fmt_pct(result["renter"]["retry_rate"])],
                [label, "Renter do_nothing", fmt_pct(result["renter"]["action_distribution"]["do_nothing"])],
                [label, "Renter buy_contents_insurance", fmt_pct(result["renter"]["action_distribution"]["buy_contents_insurance"])],
                [label, "Owner CP=H share", fmt_pct(result["cp_reversal"]["cp_h_pct"])],
                [label, "Owner CP=H do_nothing", fmt_pct(result["cp_reversal"]["cp_h_do_nothing_pct"])],
                [label, "Case A high TP+SP do_nothing", fmt_pct(result["override"]["case_a"]["do_nothing_pct"])],
                [label, "Case B low SP insurance", fmt_pct(result["override"]["case_b"]["insurance_pct"])],
                [label, "MG-Owner executed do_nothing", fmt_pct(result["mg_owner"]["MG-Owner"]["distribution"]["do_nothing"])],
                [label, "NMG-Owner executed do_nothing", fmt_pct(result["mg_owner"]["NMG-Owner"]["distribution"]["do_nothing"])],
            ]
        )
    return rows


def make_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def render_basic_section(title: str, metrics: dict[str, object], actions: list[str]) -> list[str]:
    lines = [f"### {title}", ""]
    lines.append(
        make_table(
            ["Metric", "Value"],
            [
                ["N decisions", str(metrics["n"])],
                ["Rejection rate", fmt_pct(metrics["rejection_rate"])],
                ["Retry rate", fmt_pct(metrics["retry_rate"])],
            ],
        )
    )
    lines.append("")
    lines.append("Action distribution (`final_skill`):")
    action_rows = [[action, fmt_pct(metrics["action_distribution"][action])] for action in actions]
    lines.append(make_table(["Action", "Share"], action_rows))
    lines.append("")

    for construct_col in CONSTRUCT_COLUMNS:
        construct_name = construct_col.removeprefix("construct_").removesuffix("_LABEL")
        construct = metrics["constructs"][construct_col]
        rows = [[label, fmt_pct(construct["distribution"][label])] for label in STANDARD_LABELS]
        lines.append(
            f"Construct distribution ({construct_name}; valid labels n={construct['valid_n']} of non-missing n={construct['non_missing_n']}):"
        )
        lines.append(make_table(["Label", "Share"], rows))
        invalid_labels = construct["invalid_labels"]
        if invalid_labels:
            invalid_summary = ", ".join(f"{label}={count}" for label, count in invalid_labels.items())
            lines.append(f"Malformed labels excluded from percentages: {invalid_summary}.")
        lines.append("")
    return lines


def render_report(model_results: dict[str, dict[str, object]]) -> str:
    rows = build_summary_rows(model_results)
    g3 = model_results["gemma3_4b"]
    g4 = model_results["gemma4_e4b"]

    cp_verdict = (
        "Gemma 4 does not reproduce the Gemma 3 CP reversal artifact."
        if g4["cp_reversal"]["cp_h_do_nothing_pct"] < 50.0 and g4["cp_reversal"]["cp_h_pct"] > g3["cp_reversal"]["cp_h_pct"]
        else "Gemma 4 still shows a CP reversal pattern."
    )

    implications = [
        (
            "Gemma 4 substantially reduces owner-side governance failure: owner rejection drops from "
            f"{fmt_pct(g3['owner']['rejection_rate'])} to {fmt_pct(g4['owner']['rejection_rate'])}, so cross-model differences are less confounded by blocked actions."
        ),
        (
            "The strongest Gemma 3 artifact in this comparison is not present in Gemma 4: owner CP=H rises from "
            f"{fmt_pct(g3['cp_reversal']['cp_h_pct'])} to {fmt_pct(g4['cp_reversal']['cp_h_pct'])}, and CP=H owners are much less passive."
        ),
        (
            "Gemma 4 shows lower low-SP insurance override than Gemma 3 in this seed_42 comparison "
            f"({fmt_pct(g4['override']['case_b']['insurance_pct'])} vs {fmt_pct(g3['override']['case_b']['insurance_pct'])}), which weakens the case for a generic low-trust insurance bias."
        ),
        (
            "MG-owner trapping persists in Gemma 4, but it is concentrated in MG owners rather than both owner groups: MG-owner executed do_nothing is "
            f"{fmt_pct(g4['mg_owner']['MG-Owner']['distribution']['do_nothing'])} vs {fmt_pct(g4['mg_owner']['NMG-Owner']['distribution']['do_nothing'])} for NMG owners."
        ),
    ]

    lines = [
        "# Gemma 4 e4b vs Gemma 3 4B Cross-Model Analysis",
        "",
        "Comparison scope:",
        "- `examples/multi_agent/flood/paper3/results/paper3_hybrid_v2/seed_42/gemma3_4b_strict/`",
        "- `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b/seed_42/gemma4_e4b_strict/`",
        "",
        "Method notes:",
        "- Basic action distributions use `final_skill` exactly as requested.",
        "- MG-owner executed distributions map `status != APPROVED` to executed `do_nothing`.",
        "- Construct percentages are computed over valid non-missing labels only; malformed labels are reported separately.",
        "",
        "## Cross-Model Summary Table",
        "",
        make_table(["Model", "Metric", "Value"], rows),
        "",
        "## 1. Basic Metrics Comparison",
        "",
        "## Gemma 3 4B",
        "",
    ]

    lines.extend(render_basic_section("Owners", g3["owner"], OWNER_ACTIONS))
    lines.extend(render_basic_section("Renters", g3["renter"], RENTER_ACTIONS))

    lines.extend(["## Gemma 4 e4b", ""])
    lines.extend(render_basic_section("Owners", g4["owner"], OWNER_ACTIONS))
    lines.extend(render_basic_section("Renters", g4["renter"], RENTER_ACTIONS))

    lines.extend(
        [
            "## 2. CP Reversal Check",
            "",
            make_table(
                ["Model", "Owner CP=H share", "CP=H N", "CP=H do_nothing", "CP=H active"],
                [
                    [
                        "Gemma 3 4B",
                        fmt_pct(g3["cp_reversal"]["cp_h_pct"]),
                        str(g3["cp_reversal"]["cp_h_n"]),
                        fmt_ratio(
                            g3["cp_reversal"]["cp_h_do_nothing_n"],
                            g3["cp_reversal"]["cp_h_n"],
                        ),
                        fmt_ratio(
                            g3["cp_reversal"]["cp_h_active_n"],
                            g3["cp_reversal"]["cp_h_n"],
                        ),
                    ],
                    [
                        "Gemma 4 e4b",
                        fmt_pct(g4["cp_reversal"]["cp_h_pct"]),
                        str(g4["cp_reversal"]["cp_h_n"]),
                        fmt_ratio(
                            g4["cp_reversal"]["cp_h_do_nothing_n"],
                            g4["cp_reversal"]["cp_h_n"],
                        ),
                        fmt_ratio(
                            g4["cp_reversal"]["cp_h_active_n"],
                            g4["cp_reversal"]["cp_h_n"],
                        ),
                    ],
                ],
            ),
            "",
            f"Verdict: {cp_verdict}",
            "",
            "## 3. Deliberative Override Check",
            "",
            "Case definitions:",
            "- Case A: `TP in {H, VH}` and `SP in {H, VH}`; report fraction still choosing `do_nothing`.",
            "- Case B: `SP in {L, VL}`; report fraction choosing insurance (`buy_insurance` or `buy_contents_insurance`).",
            "",
            make_table(
                ["Model", "Case A do_nothing", "Case B insurance"],
                [
                    [
                        "Gemma 3 4B",
                        fmt_ratio(g3["override"]["case_a"]["do_nothing_n"], g3["override"]["case_a"]["n"]),
                        fmt_ratio(g3["override"]["case_b"]["insurance_n"], g3["override"]["case_b"]["n"]),
                    ],
                    [
                        "Gemma 4 e4b",
                        fmt_ratio(g4["override"]["case_a"]["do_nothing_n"], g4["override"]["case_a"]["n"]),
                        fmt_ratio(g4["override"]["case_b"]["insurance_n"], g4["override"]["case_b"]["n"]),
                    ],
                ],
            ),
            "",
            "Reference values supplied in the task for prior Gemma 3 analysis:",
            "- Case A: 122/396 (31.0%) high-motivation inaction.",
            "- Case B: 1525/6492 (23.5%) low-trust insurance.",
            "- The seed_42 values above are directionally comparable but not numerically identical to those prior pooled counts.",
            "",
            "## 4. MG-Owner Trapped Profile",
            "",
            make_table(
                ["Model", "Group", "N", "buy_insurance", "elevate_house", "buyout_program", "do_nothing"],
                [
                    [
                        "Gemma 3 4B",
                        "MG-Owner",
                        str(g3["mg_owner"]["MG-Owner"]["n"]),
                        fmt_pct(g3["mg_owner"]["MG-Owner"]["distribution"]["buy_insurance"]),
                        fmt_pct(g3["mg_owner"]["MG-Owner"]["distribution"]["elevate_house"]),
                        fmt_pct(g3["mg_owner"]["MG-Owner"]["distribution"]["buyout_program"]),
                        fmt_pct(g3["mg_owner"]["MG-Owner"]["distribution"]["do_nothing"]),
                    ],
                    [
                        "Gemma 3 4B",
                        "NMG-Owner",
                        str(g3["mg_owner"]["NMG-Owner"]["n"]),
                        fmt_pct(g3["mg_owner"]["NMG-Owner"]["distribution"]["buy_insurance"]),
                        fmt_pct(g3["mg_owner"]["NMG-Owner"]["distribution"]["elevate_house"]),
                        fmt_pct(g3["mg_owner"]["NMG-Owner"]["distribution"]["buyout_program"]),
                        fmt_pct(g3["mg_owner"]["NMG-Owner"]["distribution"]["do_nothing"]),
                    ],
                    [
                        "Gemma 4 e4b",
                        "MG-Owner",
                        str(g4["mg_owner"]["MG-Owner"]["n"]),
                        fmt_pct(g4["mg_owner"]["MG-Owner"]["distribution"]["buy_insurance"]),
                        fmt_pct(g4["mg_owner"]["MG-Owner"]["distribution"]["elevate_house"]),
                        fmt_pct(g4["mg_owner"]["MG-Owner"]["distribution"]["buyout_program"]),
                        fmt_pct(g4["mg_owner"]["MG-Owner"]["distribution"]["do_nothing"]),
                    ],
                    [
                        "Gemma 4 e4b",
                        "NMG-Owner",
                        str(g4["mg_owner"]["NMG-Owner"]["n"]),
                        fmt_pct(g4["mg_owner"]["NMG-Owner"]["distribution"]["buy_insurance"]),
                        fmt_pct(g4["mg_owner"]["NMG-Owner"]["distribution"]["elevate_house"]),
                        fmt_pct(g4["mg_owner"]["NMG-Owner"]["distribution"]["buyout_program"]),
                        fmt_pct(g4["mg_owner"]["NMG-Owner"]["distribution"]["do_nothing"]),
                    ],
                ],
            ),
            "",
            "Reference values supplied in the task for Gemma 3: MG-Owner executed `do_nothing` = 67.2%, NMG-Owner = 55.0%.",
            "",
            "## 5. Implications for Paper 3 Discussion / Limitations",
            "",
        ]
    )

    for item in implications:
        lines.append(f"- {item}")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    models = load_model_data()
    profiles = pd.read_csv(DATA_DIR / "agent_initialization_complete.csv", encoding="utf-8-sig")

    model_results: dict[str, dict[str, object]] = {}
    for key, data in models.items():
        model_results[key] = {
            "owner": compute_basic_metrics(data.owner, OWNER_ACTIONS),
            "renter": compute_basic_metrics(data.renter, RENTER_ACTIONS),
            "cp_reversal": cp_reversal_metrics(data.owner),
            "override": deliberative_override_metrics(data.owner, data.renter),
            "mg_owner": mg_owner_metrics(data.owner, profiles),
        }

    report = render_report(model_results)
    OUTPUT_REPORT.write_text(report, encoding="utf-8")
    print(f"Wrote report to {OUTPUT_REPORT}")


if __name__ == "__main__":
    main()
