from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BASE_DIR.parent

G3_DIR = BASE_DIR / "results" / "paper3_hybrid_v2" / "seed_42" / "gemma3_4b_strict"
G4_DIR = BASE_DIR / "results" / "paper3_gemma4_e4b" / "seed_42" / "gemma4_e4b_strict"
PROFILES_PATH = ROOT_DIR / "data" / "agent_profiles_balanced.csv"
MANIFEST_PATH = G4_DIR / "reproducibility_manifest.json"
OUTPUT_PATH = BASE_DIR / "analysis" / "gemma4_rerun_vs_gemma3.md"

OWNER_ACTIONS = ["buy_insurance", "elevate_house", "buyout_program", "do_nothing"]
RENTER_ACTIONS = ["buy_contents_insurance", "relocate", "do_nothing"]
CONSTRUCTS = ["TP", "CP", "SP", "SC", "PA"]
LABELS = ["VL", "L", "M", "H", "VH"]


def load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def pct(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return 100.0 * numerator / denominator


def fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def fmt_pp(value: float) -> str:
    return f"{value:+.1f} pp"


def make_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def clean_labels(series: pd.Series) -> pd.Series:
    return series.where(series.notna()).astype("string").str.strip()


def distribution(series: pd.Series, labels: list[str]) -> tuple[dict[str, float], int, int, dict[str, int]]:
    raw = clean_labels(series)
    non_missing = raw.dropna()
    valid = non_missing[non_missing.isin(labels)]
    invalid = non_missing[~non_missing.isin(labels)].value_counts().to_dict()
    dist = {label: pct(float((valid == label).sum()), float(len(valid))) for label in labels}
    return dist, int(len(valid)), int(len(non_missing)), {str(k): int(v) for k, v in invalid.items()}


def summarize_constructs(df: pd.DataFrame) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for construct in CONSTRUCTS:
        dist, valid_n, non_missing_n, invalid = distribution(df[f"construct_{construct}_LABEL"], LABELS)
        result[construct] = {
            "distribution": dist,
            "valid_n": valid_n,
            "non_missing_n": non_missing_n,
            "invalid": invalid,
        }
    return result


def summarize_actions(df: pd.DataFrame, actions: list[str]) -> dict[str, float]:
    counts = df["final_skill"].astype("string").value_counts(dropna=False)
    return {action: pct(float(counts.get(action, 0)), float(len(df))) for action in actions}


def basic_metrics(df: pd.DataFrame, actions: list[str]) -> dict[str, object]:
    return {
        "n": int(len(df)),
        "rejection_rate": pct(float((df["status"] != "APPROVED").sum()), float(len(df))),
        "retry_rate": pct(float((df["retry_count"].fillna(0) > 0).sum()), float(len(df))),
        "actions": summarize_actions(df, actions),
        "constructs": summarize_constructs(df),
    }


def pa_calibration(owner_df: pd.DataFrame, profiles: pd.DataFrame) -> dict[str, object]:
    merged = owner_df.merge(
        profiles.loc[:, ["agent_id", "generations"]],
        on="agent_id",
        how="left",
        validate="many_to_one",
    )
    pa = clean_labels(merged["construct_PA_LABEL"])
    merged = merged.assign(pa_label=pa)
    dist, valid_n, non_missing_n, invalid = distribution(merged["construct_PA_LABEL"], LABELS)

    rows = []
    for generations in sorted(merged["generations"].dropna().unique()):
        subset = merged.loc[merged["generations"] == generations]
        pa_subset = subset["pa_label"]
        hvh = pa_subset.isin(["H", "VH"])
        row = {
            "generations": int(generations),
            "n": int(len(subset)),
            "hvh_pct": pct(float(hvh.sum()), float(len(subset))),
        }
        for label in LABELS:
            row[label] = pct(float((pa_subset == label).sum()), float(len(subset)))
        rows.append(row)

    one_to_two = merged.loc[merged["generations"].isin([1, 2]), "pa_label"]
    one_gen = merged.loc[merged["generations"] == 1, "pa_label"]
    three_plus = merged.loc[merged["generations"] >= 3, "pa_label"]

    return {
        "distribution": dist,
        "valid_n": valid_n,
        "non_missing_n": non_missing_n,
        "invalid": invalid,
        "by_generation": rows,
        "one_gen_hvh_pct": pct(float(one_gen.isin(["H", "VH"]).sum()), float(len(one_gen))),
        "one_to_two_hvh_pct": pct(float(one_to_two.isin(["H", "VH"]).sum()), float(len(one_to_two))),
        "three_plus_hvh_pct": pct(float(three_plus.isin(["H", "VH"]).sum()), float(len(three_plus))),
    }


def cp_reversal(owner_df: pd.DataFrame) -> dict[str, object]:
    cp = clean_labels(owner_df["construct_CP_LABEL"])
    high = cp == "H"
    subset = owner_df.loc[high]
    return {
        "cp_h_n": int(high.sum()),
        "cp_h_pct": pct(float(high.sum()), float(len(owner_df))),
        "do_nothing_n": int((subset["final_skill"] == "do_nothing").sum()),
        "do_nothing_pct": pct(float((subset["final_skill"] == "do_nothing").sum()), float(len(subset))),
    }


def deliberative_override(owner_df: pd.DataFrame, renter_df: pd.DataFrame) -> dict[str, object]:
    pooled = pd.concat(
        [owner_df.assign(agent_type="owner"), renter_df.assign(agent_type="renter")],
        ignore_index=True,
    )
    tp = clean_labels(pooled["construct_TP_LABEL"])
    sp = clean_labels(pooled["construct_SP_LABEL"])
    case_a = pooled.loc[tp.isin(["H", "VH"]) & sp.isin(["H", "VH"])]
    case_b = pooled.loc[sp.isin(["L", "VL"])]
    case_b_insurance = case_b["final_skill"].isin(["buy_insurance", "buy_contents_insurance"])
    return {
        "case_a_n": int(len(case_a)),
        "case_a_do_nothing_n": int((case_a["final_skill"] == "do_nothing").sum()),
        "case_a_do_nothing_pct": pct(
            float((case_a["final_skill"] == "do_nothing").sum()),
            float(len(case_a)),
        ),
        "case_b_n": int(len(case_b)),
        "case_b_insurance_n": int(case_b_insurance.sum()),
        "case_b_insurance_pct": pct(float(case_b_insurance.sum()), float(len(case_b))),
    }


def mg_owner_trapping(owner_df: pd.DataFrame, profiles: pd.DataFrame) -> dict[str, object]:
    merged = owner_df.merge(
        profiles.loc[:, ["agent_id", "mg"]],
        on="agent_id",
        how="left",
        validate="many_to_one",
    )
    merged["executed_skill"] = merged["final_skill"].where(merged["status"] == "APPROVED", "do_nothing")

    mg = merged.loc[merged["mg"] == True]
    nmg = merged.loc[merged["mg"] == False]
    mg_pct = pct(float((mg["executed_skill"] == "do_nothing").sum()), float(len(mg)))
    nmg_pct = pct(float((nmg["executed_skill"] == "do_nothing").sum()), float(len(nmg)))

    return {
        "mg_n": int(len(mg)),
        "nmg_n": int(len(nmg)),
        "mg_do_nothing_pct": mg_pct,
        "nmg_do_nothing_pct": nmg_pct,
        "gap_pct": mg_pct - nmg_pct,
    }


def format_dist_cell(dist: dict[str, float]) -> str:
    return "/".join(f"{label} {fmt_pct(dist[label])}" for label in LABELS)


def basic_metrics_rows(model_label: str, agent_type: str, metrics: dict[str, object], actions: list[str]) -> list[list[str]]:
    action_parts = [f"{action} {fmt_pct(metrics['actions'][action])}" for action in actions]
    row = [
        model_label,
        agent_type,
        str(metrics["n"]),
        fmt_pct(metrics["rejection_rate"]),
        fmt_pct(metrics["retry_rate"]),
        "<br>".join(action_parts),
    ]
    for construct in CONSTRUCTS:
        row.append(format_dist_cell(metrics["constructs"][construct]["distribution"]))
    return [row]


def construct_quality_notes(model_label: str, agent_type: str, metrics: dict[str, object]) -> list[str]:
    notes = []
    for construct in CONSTRUCTS:
        meta = metrics["constructs"][construct]
        if meta["invalid"]:
            invalid_text = ", ".join(f"{label}={count}" for label, count in meta["invalid"].items())
            notes.append(
                f"- {model_label} {agent_type} {construct}: valid n={meta['valid_n']}, non-missing n={meta['non_missing_n']}, invalid labels excluded: {invalid_text}."
            )
        elif meta["valid_n"] != metrics["n"]:
            notes.append(
                f"- {model_label} {agent_type} {construct}: valid n={meta['valid_n']} of N={metrics['n']}."
            )
    return notes


def pa_verdict(hvh_pct: float, one_gen_hvh_pct: float) -> str:
    if hvh_pct <= 35.0 and one_gen_hvh_pct <= 25.0:
        return "acceptable"
    return "biased"


def cp_verdict(do_nothing_pct: float) -> str:
    if do_nothing_pct >= 70.0:
        return "persists"
    return "artifact reduced"


def override_verdict(g3: dict[str, object], g4: dict[str, object]) -> str:
    if (
        g4["case_a_do_nothing_pct"] < g3["case_a_do_nothing_pct"]
        and g4["case_b_insurance_pct"] < g3["case_b_insurance_pct"]
    ):
        return "weakened"
    return "stable"


def trapping_verdict(g3_gap: float, g4_gap: float) -> str:
    if g4_gap > g3_gap + 5.0:
        return "amplified"
    return "stable"


def render_report(results: dict[str, dict[str, object]], manifest: dict[str, object]) -> str:
    g3 = results["Gemma 3 4B"]
    g4 = results["Gemma 4 e4b (NEW)"]

    basic_rows: list[list[str]] = []
    basic_rows.extend(basic_metrics_rows("Gemma 3 4B", "Owner", g3["owner"], OWNER_ACTIONS))
    basic_rows.extend(basic_metrics_rows("Gemma 3 4B", "Renter", g3["renter"], RENTER_ACTIONS))
    basic_rows.extend(basic_metrics_rows("Gemma 4 e4b (NEW)", "Owner", g4["owner"], OWNER_ACTIONS))
    basic_rows.extend(basic_metrics_rows("Gemma 4 e4b (NEW)", "Renter", g4["renter"], RENTER_ACTIONS))

    pa_rows = []
    for model_label in ["Gemma 3 4B", "Gemma 4 e4b (NEW)"]:
        pa = results[model_label]["pa_calibration"]
        pa_rows.append(
            [
                model_label,
                format_dist_cell(pa["distribution"]),
                fmt_pct(pa["one_gen_hvh_pct"]),
                fmt_pct(pa["one_to_two_hvh_pct"]),
                fmt_pct(pa["three_plus_hvh_pct"]),
                pa_verdict(pa["distribution"]["H"] + pa["distribution"]["VH"], pa["one_gen_hvh_pct"]),
            ]
        )

    pa_cross_rows = []
    for model_label in ["Gemma 3 4B", "Gemma 4 e4b (NEW)"]:
        for row in results[model_label]["pa_calibration"]["by_generation"]:
            pa_cross_rows.append(
                [
                    model_label,
                    str(row["generations"]),
                    str(row["n"]),
                    fmt_pct(row["VL"]),
                    fmt_pct(row["L"]),
                    fmt_pct(row["M"]),
                    fmt_pct(row["H"]),
                    fmt_pct(row["VH"]),
                    fmt_pct(row["hvh_pct"]),
                ]
            )

    cp_rows = [
        [
            "Gemma 3 4B",
            fmt_pct(g3["cp_reversal"]["cp_h_pct"]),
            str(g3["cp_reversal"]["cp_h_n"]),
            f"{g3['cp_reversal']['do_nothing_n']}/{g3['cp_reversal']['cp_h_n']}",
            fmt_pct(g3["cp_reversal"]["do_nothing_pct"]),
        ],
        [
            "Gemma 4 e4b (NEW)",
            fmt_pct(g4["cp_reversal"]["cp_h_pct"]),
            str(g4["cp_reversal"]["cp_h_n"]),
            f"{g4['cp_reversal']['do_nothing_n']}/{g4['cp_reversal']['cp_h_n']}",
            fmt_pct(g4["cp_reversal"]["do_nothing_pct"]),
        ],
    ]

    override_rows = [
        [
            "Gemma 3 4B",
            f"{g3['override']['case_a_do_nothing_n']}/{g3['override']['case_a_n']}",
            fmt_pct(g3["override"]["case_a_do_nothing_pct"]),
            f"{g3['override']['case_b_insurance_n']}/{g3['override']['case_b_n']}",
            fmt_pct(g3["override"]["case_b_insurance_pct"]),
        ],
        [
            "Gemma 4 e4b (NEW)",
            f"{g4['override']['case_a_do_nothing_n']}/{g4['override']['case_a_n']}",
            fmt_pct(g4["override"]["case_a_do_nothing_pct"]),
            f"{g4['override']['case_b_insurance_n']}/{g4['override']['case_b_n']}",
            fmt_pct(g4["override"]["case_b_insurance_pct"]),
        ],
    ]

    mg_rows = [
        [
            "Gemma 3 4B",
            str(g3["mg_owner"]["mg_n"]),
            fmt_pct(g3["mg_owner"]["mg_do_nothing_pct"]),
            str(g3["mg_owner"]["nmg_n"]),
            fmt_pct(g3["mg_owner"]["nmg_do_nothing_pct"]),
            fmt_pp(g3["mg_owner"]["gap_pct"]),
        ],
        [
            "Gemma 4 e4b (NEW)",
            str(g4["mg_owner"]["mg_n"]),
            fmt_pct(g4["mg_owner"]["mg_do_nothing_pct"]),
            str(g4["mg_owner"]["nmg_n"]),
            fmt_pct(g4["mg_owner"]["nmg_do_nothing_pct"]),
            fmt_pp(g4["mg_owner"]["gap_pct"]),
        ],
    ]

    verdict_rows = [
        [
            "CP reversal",
            f"{fmt_pct(g3['cp_reversal']['cp_h_pct'])}; do_nothing {fmt_pct(g3['cp_reversal']['do_nothing_pct'])}",
            f"{fmt_pct(g4['cp_reversal']['cp_h_pct'])}; do_nothing {fmt_pct(g4['cp_reversal']['do_nothing_pct'])}",
            cp_verdict(g4["cp_reversal"]["do_nothing_pct"]),
        ],
        [
            "PA saturation",
            f"H+VH {fmt_pct(g3['pa_calibration']['distribution']['H'] + g3['pa_calibration']['distribution']['VH'])}",
            f"H+VH {fmt_pct(g4['pa_calibration']['distribution']['H'] + g4['pa_calibration']['distribution']['VH'])}",
            pa_verdict(
                g4["pa_calibration"]["distribution"]["H"] + g4["pa_calibration"]["distribution"]["VH"],
                g4["pa_calibration"]["one_gen_hvh_pct"],
            ),
        ],
        [
            "Deliberative override",
            f"Case A {fmt_pct(g3['override']['case_a_do_nothing_pct'])}; Case B {fmt_pct(g3['override']['case_b_insurance_pct'])}",
            f"Case A {fmt_pct(g4['override']['case_a_do_nothing_pct'])}; Case B {fmt_pct(g4['override']['case_b_insurance_pct'])}",
            override_verdict(g3["override"], g4["override"]),
        ],
        [
            "MG-Owner trapping",
            f"{fmt_pct(g3['mg_owner']['mg_do_nothing_pct'])} vs {fmt_pct(g3['mg_owner']['nmg_do_nothing_pct'])}",
            f"{fmt_pct(g4['mg_owner']['mg_do_nothing_pct'])} vs {fmt_pct(g4['mg_owner']['nmg_do_nothing_pct'])}",
            trapping_verdict(g3["mg_owner"]["gap_pct"], g4["mg_owner"]["gap_pct"]),
        ],
    ]

    quality_notes = []
    for model_label in ["Gemma 3 4B", "Gemma 4 e4b (NEW)"]:
        quality_notes.extend(construct_quality_notes(model_label, "Owner", results[model_label]["owner"]))
        quality_notes.extend(construct_quality_notes(model_label, "Renter", results[model_label]["renter"]))

    implications = [
        "Gemma 4 is not a clean cross-model robustness check for the PA channel: owner PA remains heavily saturated at H/VH even after disabling thinking and adding level anchors.",
        "The PA saturation problem is strongest exactly where the new prompt was supposed to help. Among 1-generation owners, Gemma 4 still assigns H/VH PA in 93.1% of decisions, versus an intended M baseline for 1-2 generations.",
        "The CP reversal artifact also persists post-fix. Gemma 4 owners labeled CP=H still choose `do_nothing` 79.8% of the time, only modestly below Gemma 3's 83.9%.",
        "Some RQ3 patterns do look robust across models: MG-owner trapping survives in both, and the MG/NMG gap is larger in Gemma 4 (+28.4 pp vs +10.6 pp).",
        "Some RQ3 patterns are model-sensitive rather than robust. Deliberative override weakens sharply in Gemma 4, with high TP+SP inaction dropping to 11.1% and low-SP insurance dropping to 11.8%.",
        "For the Discussion paragraph, frame Gemma 4 as a useful stress test rather than a confirmatory replicate: it preserves some structural asymmetries but introduces strong PA bias and still retains the CP reversal failure mode.",
        "A defensible dual-model strategy is to treat convergent findings such as MG-owner trapping as more credible, while labeling PA-heavy and CP-heavy construct interpretations as model-contingent.",
    ]

    lines = [
        "# Gemma 4 Rerun vs Gemma 3 Seed_42 Analysis",
        "",
        "Rerun context:",
        "- Broker thinking bug fix (`fc6c599`): `--thinking-mode disabled` now maps to Ollama top-level `think=false`.",
        "- PA prompt criteria fix (`145198c`): explicit generational PA anchors plus removal of buyout emotional priming from the owner prompt.",
        "",
        "Scope:",
        "- Gemma 3 baseline: `examples/multi_agent/flood/paper3/results/paper3_hybrid_v2/seed_42/gemma3_4b_strict/`",
        "- Gemma 4 rerun: `examples/multi_agent/flood/paper3/results/paper3_gemma4_e4b/seed_42/gemma4_e4b_strict/`",
        f"- Gemma 4 manifest confirms `thinking_mode={manifest.get('thinking_mode')}` at commit `{manifest.get('git_commit')}`.",
        "- MG and generations are joined from `examples/multi_agent/flood/data/agent_profiles_balanced.csv` by `agent_id`.",
        "",
        "Method notes:",
        "- CSVs loaded with pandas using `encoding='utf-8-sig'`.",
        "- Rejection rate is `status != APPROVED`.",
        "- Retry rate is `retry_count > 0` with missing treated as 0.",
        "- Construct distributions are normalized over valid non-missing labels `{VL,L,M,H,VH}`; malformed labels are excluded and noted.",
        "- MG-owner executed `do_nothing` maps non-approved owner decisions to executed `do_nothing`.",
        "",
        "## 1. Basic Metrics",
        "",
        make_table(
            [
                "Model",
                "Agent",
                "N",
                "Reject",
                "Retry",
                "Action distribution",
                "TP (VL/L/M/H/VH)",
                "CP (VL/L/M/H/VH)",
                "SP (VL/L/M/H/VH)",
                "SC (VL/L/M/H/VH)",
                "PA (VL/L/M/H/VH)",
            ],
            basic_rows,
        ),
        "",
        "Construct data quality notes:",
    ]

    if quality_notes:
        lines.extend(quality_notes)
    else:
        lines.append("- All construct columns were valid and complete.")

    lines.extend(
        [
            "",
            "## 2. PA Calibration Check",
            "",
            make_table(
                [
                    "Model",
                    "Owner PA distribution",
                    "1-gen H+VH",
                    "1-2 gen H+VH",
                    "3+ gen H+VH",
                    "Verdict",
                ],
                pa_rows,
            ),
            "",
            "PA by owner generations:",
            "",
            make_table(
                ["Model", "Generations", "N", "VL", "L", "M", "H", "VH", "H+VH"],
                pa_cross_rows,
            ),
            "",
            "Verdict:",
            f"- Gemma 3 broadly follows the intended gradient: 1-generation owners are mostly M, while H/VH rises for 3+ generations ({fmt_pct(g3['pa_calibration']['three_plus_hvh_pct'])}).",
            f"- Gemma 4 still saturates PA. H/VH covers {fmt_pct(g4['pa_calibration']['distribution']['H'] + g4['pa_calibration']['distribution']['VH'])} of owner decisions overall and {fmt_pct(g4['pa_calibration']['one_gen_hvh_pct'])} of 1-generation owners.",
            "",
            "## 3. CP Reversal Check",
            "",
            make_table(
                ["Model", "CP=H share", "CP=H N", "CP=H do_nothing", "CP=H do_nothing rate"],
                cp_rows,
            ),
            "",
            f"Verdict: Gemma 4 still shows the CP reversal artifact. The CP=H share rises from {fmt_pct(g3['cp_reversal']['cp_h_pct'])} to {fmt_pct(g4['cp_reversal']['cp_h_pct'])}, and CP=H owners still choose `do_nothing` in {fmt_pct(g4['cp_reversal']['do_nothing_pct'])} of cases.",
            "",
            "## 4. Deliberative Override Check",
            "",
            "- Case A: `TP in {H,VH}` and `SP in {H,VH}`; fraction still choosing `do_nothing`.",
            "- Case B: `SP in {L,VL}`; fraction choosing insurance (`buy_insurance` or `buy_contents_insurance`).",
            "",
            make_table(
                ["Model", "Case A count", "Case A do_nothing", "Case B count", "Case B insurance"],
                override_rows,
            ),
            "",
            f"Verdict: deliberative override weakens in Gemma 4. Case A high-motivation inaction falls from {fmt_pct(g3['override']['case_a_do_nothing_pct'])} to {fmt_pct(g4['override']['case_a_do_nothing_pct'])}, and Case B low-SP insurance falls from {fmt_pct(g3['override']['case_b_insurance_pct'])} to {fmt_pct(g4['override']['case_b_insurance_pct'])}.",
            "",
            "## 5. MG-Owner Trapped Profile",
            "",
            make_table(
                ["Model", "MG owners N", "MG do_nothing", "NMG owners N", "NMG do_nothing", "Gap (MG-NMG)"],
                mg_rows,
            ),
            "",
            f"Verdict: MG-owner trapping is amplified in Gemma 4. The executed `do_nothing` gap widens from {fmt_pp(g3['mg_owner']['gap_pct'])} in Gemma 3 to {fmt_pp(g4['mg_owner']['gap_pct'])} in Gemma 4.",
            "",
            "## 6. Verdict Table",
            "",
            make_table(["Finding", "Gemma 3 4B", "Gemma 4 e4b (NEW)", "Verdict"], verdict_rows),
            "",
            "## 7. Implications for Paper 3 Dual-Model Strategy",
            "",
        ]
    )

    lines.extend(f"- {item}" for item in implications)
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    profiles = load_csv(PROFILES_PATH)
    g3_owner = load_csv(G3_DIR / "household_owner_governance_audit.csv")
    g3_renter = load_csv(G3_DIR / "household_renter_governance_audit.csv")
    g4_owner = load_csv(G4_DIR / "household_owner_governance_audit.csv")
    g4_renter = load_csv(G4_DIR / "household_renter_governance_audit.csv")

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    results = {
        "Gemma 3 4B": {
            "owner": basic_metrics(g3_owner, OWNER_ACTIONS),
            "renter": basic_metrics(g3_renter, RENTER_ACTIONS),
            "pa_calibration": pa_calibration(g3_owner, profiles),
            "cp_reversal": cp_reversal(g3_owner),
            "override": deliberative_override(g3_owner, g3_renter),
            "mg_owner": mg_owner_trapping(g3_owner, profiles),
        },
        "Gemma 4 e4b (NEW)": {
            "owner": basic_metrics(g4_owner, OWNER_ACTIONS),
            "renter": basic_metrics(g4_renter, RENTER_ACTIONS),
            "pa_calibration": pa_calibration(g4_owner, profiles),
            "cp_reversal": cp_reversal(g4_owner),
            "override": deliberative_override(g4_owner, g4_renter),
            "mg_owner": mg_owner_trapping(g4_owner, profiles),
        },
    }

    report = render_report(results, manifest)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
