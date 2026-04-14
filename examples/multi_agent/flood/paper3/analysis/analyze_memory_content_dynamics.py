import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

_PAPER3_OVERRIDE = os.environ.get("PAPER3_TRACE_DIR")
_PAPER3_OUTPUT_OVERRIDE = os.environ.get("PAPER3_OUTPUT_DIR")

PHRASE_FAMILIES = {
    "established_pattern": ["established pattern", "consistent with", "aligns with", "prior decision", "previous choice"],
    "deep_attachment": ["deep attachment", "deeply rooted", "strong ties", "home", "generations"],
    "fatalism": ["nothing i can do", "cannot afford", "beyond my control", "too expensive", "unable to move"],
    "flood_experience_narrative": ["i experienced", "i was flooded", "my home flooded"],
    "institutional_trust": ["trust", "faith in", "government programs", "fema", "nfip"],
}
SELF_REFERENTIAL_RE = re.compile(r"\bI (have|am|will|chose|decided|feel|think)\b", re.IGNORECASE)


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
    output_dir = Path(os.path.normpath(output_dir_raw)) / "memory_dynamics"
    output_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir, output_dir


def normalize_agent_type(agent_type: str) -> str:
    return "owner" if "owner" in (agent_type or "") else "renter"


def normalize_mg(value) -> str:
    return "MG" if bool(value) else "NMG"


def iter_household_records(raw_dir: Path):
    for filename in ("household_owner_traces.jsonl", "household_renter_traces.jsonl"):
        with (raw_dir / filename).open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def detect_phrase_families(text: str) -> set[str]:
    lowered = (text or "").lower()
    hits = set()
    for family, phrases in PHRASE_FAMILIES.items():
        if any(phrase in lowered for phrase in phrases):
            hits.add(family)
    if SELF_REFERENTIAL_RE.search(text or ""):
        hits.add("self_referential")
    return hits


def build_outputs(trace_dir: Path, output_dir: Path) -> dict[str, pd.DataFrame]:
    raw_dir = trace_dir / "raw"
    size_rows = []
    content_rows = []
    category_rows = []
    phrase_rows = []
    new_write_rows = []

    size_acc = defaultdict(lambda: {"mem_pre_total": 0.0, "mem_post_total": 0.0, "acc_total": 0.0, "n": 0})
    content_acc = Counter()
    category_acc = Counter()
    phrase_acc = Counter()
    phrase_denoms = Counter()
    new_write_acc = defaultdict(lambda: {"agent_self_report_total": 0.0, "new_write_total": 0.0, "n": 0})

    for rec in iter_household_records(raw_dir):
        year = int(rec.get("year"))
        state_before = rec.get("state_before") or {}
        agent_type = normalize_agent_type(rec.get("agent_type", ""))
        mg = normalize_mg(state_before.get("mg", False))
        mem_pre = rec.get("memory_pre") or []
        mem_post = rec.get("memory_post") or []

        size_key = (year, agent_type, mg)
        size_acc[size_key]["mem_pre_total"] += len(mem_pre)
        size_acc[size_key]["mem_post_total"] += len(mem_post)
        size_acc[size_key]["acc_total"] += len(mem_post) - len(mem_pre)
        size_acc[size_key]["n"] += 1

        pre_contents = {item for item in mem_pre if isinstance(item, str)}
        new_entries = []
        seen_new = set()
        for item in mem_post:
            if not isinstance(item, dict):
                continue
            content_type = item.get("content_type", "unknown") or "unknown"
            category = item.get("category", "unknown") or "unknown"
            content_acc[(year, agent_type, content_type)] += 1
            category_acc[(year, agent_type, category)] += 1

            content = item.get("content", "")
            timestamp = item.get("timestamp")
            if content and content not in pre_contents and timestamp != 0 and content not in seen_new:
                new_entries.append(item)
                seen_new.add(content)

        phrase_denoms[(year, agent_type)] += len(new_entries)
        agent_self_report_count = 0
        for item in new_entries:
            item_type = item.get("content_type", "unknown") or "unknown"
            if item_type == "agent_self_report":
                agent_self_report_count += 1
            for family in detect_phrase_families(item.get("content", "")):
                phrase_acc[(year, agent_type, family)] += 1

        new_write_acc[(year, agent_type, mg)]["agent_self_report_total"] += agent_self_report_count
        new_write_acc[(year, agent_type, mg)]["new_write_total"] += len(new_entries)
        new_write_acc[(year, agent_type, mg)]["n"] += 1

    for (year, agent_type, mg), stats in sorted(size_acc.items()):
        size_rows.append({
            "year": year,
            "agent_type": agent_type,
            "mg": mg,
            "mem_pre_mean": stats["mem_pre_total"] / stats["n"],
            "mem_post_mean": stats["mem_post_total"] / stats["n"],
            "accumulation_mean": stats["acc_total"] / stats["n"],
            "n_decisions": stats["n"],
        })

    content_totals = defaultdict(int)
    for (year, agent_type, _), count in content_acc.items():
        content_totals[(year, agent_type)] += count
    for (year, agent_type, content_type), count in sorted(content_acc.items()):
        total = content_totals[(year, agent_type)]
        content_rows.append({
            "year": year,
            "agent_type": agent_type,
            "content_type": content_type,
            "count": count,
            "frequency": count / total if total else 0.0,
        })

    category_totals = defaultdict(int)
    for (year, agent_type, _), count in category_acc.items():
        category_totals[(year, agent_type)] += count
    for (year, agent_type, category), count in sorted(category_acc.items()):
        total = category_totals[(year, agent_type)]
        category_rows.append({
            "year": year,
            "agent_type": agent_type,
            "category": category,
            "count": count,
            "frequency": count / total if total else 0.0,
        })

    for (year, agent_type), total_new_entries in sorted(phrase_denoms.items()):
        for family in sorted([*PHRASE_FAMILIES.keys(), "self_referential"]):
            count = phrase_acc[(year, agent_type, family)]
            phrase_rows.append({
                "year": year,
                "agent_type": agent_type,
                "phrase_family": family,
                "count": count,
                "frequency": count / total_new_entries if total_new_entries else 0.0,
                "new_entry_count": total_new_entries,
            })

    for (year, agent_type, mg), stats in sorted(new_write_acc.items()):
        new_write_rows.append({
            "year": year,
            "agent_type": agent_type,
            "mg": mg,
            "agent_self_report_new_mean": stats["agent_self_report_total"] / stats["n"],
            "new_writes_mean": stats["new_write_total"] / stats["n"],
            "n_decisions": stats["n"],
        })

    outputs = {
        "memory_size_by_year.csv": pd.DataFrame(size_rows),
        "memory_content_type_by_year.csv": pd.DataFrame(content_rows),
        "memory_category_by_year.csv": pd.DataFrame(category_rows),
        "memory_rationalization_phrases_by_year.csv": pd.DataFrame(phrase_rows),
        "memory_new_writes_by_decision_year.csv": pd.DataFrame(new_write_rows),
    }
    for filename, frame in outputs.items():
        frame.to_csv(output_dir / filename, index=False)
    return outputs


def write_report(trace_dir: Path, output_dir: Path, outputs: dict[str, pd.DataFrame]) -> None:
    size_df = outputs["memory_size_by_year.csv"]
    content_df = outputs["memory_content_type_by_year.csv"]
    phrase_df = outputs["memory_rationalization_phrases_by_year.csv"]
    new_write_df = outputs["memory_new_writes_by_decision_year.csv"]

    agent_self_df = content_df[content_df["content_type"] == "agent_self_report"].copy()
    top_agent_self = (
        agent_self_df.sort_values(["count", "year"], ascending=[False, True]).groupby("agent_type", as_index=False).head(3)[["year", "agent_type", "count", "frequency"]]
    )
    top_phrase = (
        phrase_df.sort_values(["count", "year"], ascending=[False, True]).groupby("agent_type", as_index=False).head(4)[["year", "agent_type", "phrase_family", "count", "frequency"]]
    )
    latest_sizes = size_df[size_df["year"] == size_df["year"].max()].sort_values(["agent_type", "mg"])
    latest_new = new_write_df[new_write_df["year"] == new_write_df["year"].max()].sort_values(["agent_type", "mg"])

    report_lines = [
        "# Memory Content Dynamics",
        "",
        f"Trace dir: `{trace_dir.as_posix()}`",
        "",
        "## Latest-Year Memory Size",
        "",
        latest_sizes.to_markdown(index=False),
        "",
        "## Latest-Year New Writes",
        "",
        latest_new.to_markdown(index=False),
        "",
        "## Highest Agent Self Report Counts",
        "",
        top_agent_self.to_markdown(index=False) if not top_agent_self.empty else "No agent_self_report entries found.",
        "",
        "## Most Common Rationalization Phrase Families",
        "",
        top_phrase.to_markdown(index=False) if not top_phrase.empty else "No rationalization phrase hits found.",
        "",
        "## Summary",
        "",
        "- `memory_size_by_year.csv` reports pre/post memory load by year, tenure, and MG status.",
        "- `memory_content_type_by_year.csv` and `memory_category_by_year.csv` expose the semantic composition of accumulated memory.",
        "- `memory_rationalization_phrases_by_year.csv` isolates new memory writes and measures first-person rationalization markers.",
        "- `memory_new_writes_by_decision_year.csv` is the direct ratchet-rate table, with `agent_self_report_new_mean` as the key metric.",
    ]
    (output_dir / "memory_content_dynamics_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def print_summary(outputs: dict[str, pd.DataFrame]) -> None:
    content_df = outputs["memory_content_type_by_year.csv"]
    new_write_df = outputs["memory_new_writes_by_decision_year.csv"]
    agent_self_total = int(content_df.loc[content_df["content_type"] == "agent_self_report", "count"].sum())
    latest_year = int(new_write_df["year"].max())
    latest_mean = new_write_df.loc[new_write_df["year"] == latest_year, "agent_self_report_new_mean"].mean()
    print("memory_content_dynamics complete")
    print(f"files={len(outputs) + 1}")
    print(f"agent_self_report_total={agent_self_total}")
    print(f"latest_year={latest_year}")
    print(f"latest_agent_self_report_new_mean={latest_mean:.4f}")


def main() -> None:
    args = parse_args()
    trace_dir, output_dir = resolve_paths(args)
    outputs = build_outputs(trace_dir, output_dir)
    write_report(trace_dir, output_dir, outputs)
    print_summary(outputs)


if __name__ == "__main__":
    main()
