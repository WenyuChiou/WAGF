import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

_PAPER3_OVERRIDE = os.environ.get("PAPER3_TRACE_DIR")
_PAPER3_OUTPUT_OVERRIDE = os.environ.get("PAPER3_OUTPUT_DIR")

CONSTRUCT_KEYWORDS = {
    "TP": {"flood_zone": ["flood zone", "sfha"], "recent_event": ["this year", "severe", "recent"], "personal_experience": ["personal history", "never flooded"], "severity": ["catastrophic", "devastating", "extreme"]},
    "CP": {"affordability": ["afford", "budget", "income", "cost"], "capability": ["can", "able"], "infrastructure": ["elevation", "retrofit", "grant"], "barriers": ["burden", "expensive", "unaffordable"]},
    "SP": {"government": ["government", "fema", "njdep", "subsidy"], "insurance": ["insurance", "premium", "nfip"], "trust": ["trust", "faith", "support"], "distrust": ["slow", "unreliable", "low faith"]},
    "SC": {"community_ties": ["community", "neighbors", "ties"], "generations": ["generation", "rooted"], "isolation": ["strained", "disconnected", "not taking action"]},
    "PA": {"attachment": ["home", "attachment", "rooted"], "tempered": ["could move", "if necessary", "possibility"], "conditional": ["comfort", "uncertainty"]},
}
MAIN_REASONING_FAMILIES = {
    "established_pattern": ["established pattern", "consistent with", "aligns with", "prior decision", "previous choice"],
    "deep_attachment": ["deep attachment", "deeply rooted", "strong ties", "home", "generations"],
    "fatalism": ["nothing i can do", "cannot afford", "beyond my control", "too expensive", "unable to move"],
    "self_referential": [],
    "flood_experience_narrative": ["i experienced", "i was flooded", "my home flooded"],
    "institutional_trust": ["trust", "faith in", "government programs", "fema", "nfip"],
    "past_reference": ["my previous", "established", "consistent with last year"],
}
SELF_REFERENTIAL_RE = re.compile(r"\bI (have|am|will|chose|decided|feel|think)\b", re.IGNORECASE)
TRUNCATION_RE = re.compile(r"(\.\.\.|[,:;/-]|\b(and|or|because|while|though|but)\b)\s*$", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", default=None)
    return parser.parse_args()


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    trace_dir_raw = args.trace_dir or _PAPER3_OVERRIDE
    if not trace_dir_raw:
        raise SystemExit("Missing trace dir. Use --trace-dir or PAPER3_TRACE_DIR.")
    trace_dir = Path(os.path.normpath(trace_dir_raw))
    output_dir_raw = _PAPER3_OUTPUT_OVERRIDE or str(trace_dir.parent / "analysis")
    output_dir = Path(os.path.normpath(output_dir_raw)) / "reasoning_taxonomy"
    output_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir, output_dir


def iter_household_records(raw_dir: Path):
    for filename in ("household_owner_traces.jsonl", "household_renter_traces.jsonl"):
        with (raw_dir / filename).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def normalize_agent_type(agent_type: str) -> str:
    return "owner" if "owner" in (agent_type or "") else "renter"


def normalize_mg(value) -> str:
    return "MG" if bool(value) else "NMG"


def token_count(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def is_truncated(text: str) -> bool:
    clean = (text or "").strip()
    return bool(clean and TRUNCATION_RE.search(clean))


def detect_families(text: str) -> set[str]:
    lowered = (text or "").lower()
    hits = set()
    for family, phrases in MAIN_REASONING_FAMILIES.items():
        if family == "self_referential":
            if SELF_REFERENTIAL_RE.search(text or ""):
                hits.add(family)
            continue
        if any(phrase in lowered for phrase in phrases):
            hits.add(family)
    return hits


def build_outputs(trace_dir: Path, output_dir: Path) -> dict[str, pd.DataFrame]:
    raw_dir = trace_dir / "raw"
    length_rows = []
    vocab_rows = []
    vocab_mg_rows = []
    audit_rows = []
    main_reason_rows = []

    vocab_acc = Counter()
    vocab_denom = Counter()
    vocab_mg_acc = Counter()
    vocab_mg_denom = Counter()
    audit_acc = defaultdict(lambda: {"demo": 0.0, "semantic": 0.0, "n": 0})
    main_reason_acc = Counter()
    main_reason_denom = Counter()

    for rec in iter_household_records(raw_dir):
        year = int(rec.get("year"))
        agent_type = normalize_agent_type(rec.get("agent_type", ""))
        mg = normalize_mg((rec.get("state_before") or {}).get("mg", False))
        reasoning = ((rec.get("skill_proposal") or {}).get("reasoning") or {})
        audit_demo = ((reasoning.get("demographic_audit") or {}).get("score")) or 0.0
        audit_semantic = ((reasoning.get("semantic_correlation_audit") or {}).get("score")) or 0.0
        audit_acc[(year, agent_type)]["demo"] += float(audit_demo)
        audit_acc[(year, agent_type)]["semantic"] += float(audit_semantic)
        audit_acc[(year, agent_type)]["n"] += 1

        for construct in ("TP", "CP", "SP", "SC", "PA"):
            label = reasoning.get(f"{construct}_LABEL", "")
            reason_text = reasoning.get(f"{construct}_REASON", "") or ""
            length_rows.append({"year": year, "agent_type": agent_type, "construct": construct, "label": label, "char_count": len(reason_text), "token_count": token_count(reason_text), "is_truncated": is_truncated(reason_text)})
            vocab_denom[(agent_type, year, construct)] += 1
            vocab_mg_denom[(agent_type, mg, year, construct)] += 1
            lowered = reason_text.lower()
            for family, phrases in CONSTRUCT_KEYWORDS[construct].items():
                if any(phrase in lowered for phrase in phrases):
                    vocab_acc[(agent_type, year, construct, family)] += 1
                    vocab_mg_acc[(agent_type, mg, year, construct, family)] += 1

        main_reason = reasoning.get("reasoning", "") or ""
        main_reason_denom[(agent_type, year)] += 1
        for family in detect_families(main_reason):
            main_reason_acc[(agent_type, year, family)] += 1

    for (agent_type, year, construct), total in sorted(vocab_denom.items()):
        for family in CONSTRUCT_KEYWORDS[construct]:
            count = vocab_acc[(agent_type, year, construct, family)]
            vocab_rows.append({"agent_type": agent_type, "year": year, "construct": construct, "keyword_family": family, "count": count, "frequency": count / total if total else 0.0, "n_decisions": total})

    for (agent_type, mg, year, construct), total in sorted(vocab_mg_denom.items()):
        for family in CONSTRUCT_KEYWORDS[construct]:
            count = vocab_mg_acc[(agent_type, mg, year, construct, family)]
            vocab_mg_rows.append({"agent_type": agent_type, "mg": mg, "year": year, "construct": construct, "keyword_family": family, "count": count, "frequency": count / total if total else 0.0, "n_decisions": total})

    prior_demo = {}
    prior_semantic = {}
    for (year, agent_type), stats in sorted(audit_acc.items()):
        demo_mean = stats["demo"] / stats["n"]
        semantic_mean = stats["semantic"] / stats["n"]
        audit_rows.append({"year": year, "agent_type": agent_type, "demographic_audit_mean": demo_mean, "semantic_correlation_audit_mean": semantic_mean, "demographic_audit_drop": demo_mean < prior_demo.get(agent_type, demo_mean), "semantic_correlation_audit_drop": semantic_mean < prior_semantic.get(agent_type, semantic_mean), "n_decisions": stats["n"]})
        prior_demo[agent_type] = demo_mean
        prior_semantic[agent_type] = semantic_mean

    for (agent_type, year), total in sorted(main_reason_denom.items()):
        for family in MAIN_REASONING_FAMILIES:
            count = main_reason_acc[(agent_type, year, family)]
            main_reason_rows.append({"agent_type": agent_type, "year": year, "phrase_family": family, "count": count, "frequency": count / total if total else 0.0, "n_decisions": total})

    outputs = {
        "reason_text_length_by_year.csv": pd.DataFrame(length_rows),
        "reason_vocabulary_by_construct.csv": pd.DataFrame(vocab_rows),
        "reason_vocabulary_by_mg.csv": pd.DataFrame(vocab_mg_rows),
        "audit_scores_by_year.csv": pd.DataFrame(audit_rows),
        "reasoning_phrase_detection_by_year.csv": pd.DataFrame(main_reason_rows),
    }
    for filename, frame in outputs.items():
        frame.to_csv(output_dir / filename, index=False)
    return outputs


def write_report(trace_dir: Path, output_dir: Path, outputs: dict[str, pd.DataFrame]) -> None:
    length_df = outputs["reason_text_length_by_year.csv"]
    vocab_df = outputs["reason_vocabulary_by_construct.csv"]
    audit_df = outputs["audit_scores_by_year.csv"]
    reasoning_df = outputs["reasoning_phrase_detection_by_year.csv"]

    length_summary = length_df.groupby(["construct"], as_index=False).agg(char_count_mean=("char_count", "mean"), token_count_mean=("token_count", "mean"), truncation_rate=("is_truncated", "mean")).sort_values("construct")
    vocab_summary = vocab_df.sort_values("frequency", ascending=False).head(15)
    audit_summary = audit_df.sort_values(["agent_type", "year"])
    main_reason_summary = reasoning_df.sort_values("frequency", ascending=False).head(12)

    report_lines = [
        "# Skill Proposal Reasoning Taxonomy",
        "",
        f"Trace dir: `{trace_dir.as_posix()}`",
        "",
        "## Construct REASON Length Summary",
        "",
        length_summary.to_markdown(index=False),
        "",
        "## Highest-Frequency Construct Vocabulary Families",
        "",
        vocab_summary.to_markdown(index=False),
        "",
        "## Audit Score Trajectory",
        "",
        audit_summary.to_markdown(index=False),
        "",
        "## Main Reasoning Phrase Detection",
        "",
        main_reason_summary.to_markdown(index=False),
        "",
        "## Summary",
        "",
        "- `reason_text_length_by_year.csv` captures REASON length and truncation flags per construct-year-decision.",
        "- `reason_vocabulary_by_construct.csv` and `reason_vocabulary_by_mg.csv` quantify recurring semantic motifs in the construct-specific prose.",
        "- `reasoning_phrase_detection_by_year.csv` isolates rationalization phrases in the main free-text justification, including `past_reference`.",
        "- `audit_scores_by_year.csv` tracks both audit systems and flags year-over-year mean drops.",
    ]
    (output_dir / "skill_proposal_reasoning_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def print_summary(outputs: dict[str, pd.DataFrame]) -> None:
    reasoning_df = outputs["reasoning_phrase_detection_by_year.csv"]
    audit_df = outputs["audit_scores_by_year.csv"]
    past_reference_total = int(reasoning_df.loc[reasoning_df["phrase_family"] == "past_reference", "count"].sum())
    audit_drop_count = int(audit_df["demographic_audit_drop"].sum() + audit_df["semantic_correlation_audit_drop"].sum())
    print("skill_proposal_reasoning complete")
    print(f"files={len(outputs) + 1}")
    print(f"past_reference_total={past_reference_total}")
    print(f"audit_drop_flags={audit_drop_count}")


def main() -> None:
    args = parse_args()
    trace_dir, output_dir = resolve_paths(args)
    outputs = build_outputs(trace_dir, output_dir)
    write_report(trace_dir, output_dir, outputs)
    print_summary(outputs)


if __name__ == "__main__":
    main()
