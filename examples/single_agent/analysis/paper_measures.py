"""Fixed flood paper measures; existing flood metrics and runs are unchanged.

Executed IBR scores strict ERROR rules R1/R3/R4/R5 on FIRST-STATED labels.
PI IBR reproduces r44's exact-first-attempt, final-proposal convention,
including its documented fallback and missing-coping conventions. R5 is
excluded from PI IBR. EHE is executed-action entropy divided by log2(4).

    python -m examples.single_agent.analysis.paper_measures projection \\
        --runs DIR [DIR ...] --out CSV

Yearly executed shares are additional year_N_ACTION_share columns. Run inputs
are read-only. Missing current audit/trace evidence raises MetricsError;
post-decision elevation and cumulative adaptation states are never substituted.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from examples.single_agent.analysis import flood_ibr_v2 as audit

MetricsError = audit.MetricsError
ACTIONS = ("buy_insurance", "elevate_house", "relocate", "do_nothing")
BEHAVIOURAL_RULES = ("R1", "R3", "R4")
RULES = BEHAVIOURAL_RULES + ("R5",)
LABELS = {"VL", "L", "M", "H", "VH"}
REQUIRED_PI_COLUMNS = {"initial_skill", "initial_labels", "attempt_skills",
                       "final_skill", "status", "failed_rules"}


def _pct(count: int | None, n: int | None) -> float | None:
    return 100 * count / n if count is not None and n else None


def _label(labels: Mapping[str, str], key: str) -> str:
    return (labels.get(key) or "").strip().upper()


def _action(value: Any, where: str) -> str:
    if value not in ACTIONS:
        raise MetricsError(f"{where}: missing or invalid executed/proposed action {value!r}")
    return value


def rule_flags(decision: audit.Decision, elevated_before: bool) -> dict[str, bool]:
    """Only enforced strict rules; low_coping_block is a WARNING."""
    action = _action(decision.executed_skill, f"{decision.agent_id}, {decision.year}")
    if type(elevated_before) is not bool:
        raise MetricsError("pre-decision elevated must be a boolean")
    tp, cp = (_label(decision.first_labels, key) for key in ("TP_LABEL", "CP_LABEL"))
    return {
        "R1": action == "do_nothing" and tp in {"H", "VH"} and cp in {"M", "H", "VH"},
        "R3": action == "relocate" and tp in {"VL", "L"},
        "R4": action == "elevate_house" and tp in {"VL", "L"},
        "R5": action == "elevate_house" and elevated_before,
    }


def ibr_summary(decisions: Iterable[audit.Decision],
                pre_elevated: Mapping[tuple[str, str], bool]) -> dict[str, Any]:
    """Count overlapping rules once per executed decision; exclude aborts.

    First-proposal behavioural counts use this same executed-decision cohort.
    No stated label is a non-match, as in the strict validator; report the
    number of decisions whose constructs were never stated separately.
    """
    decisions = list(decisions)
    executed = [d for d in decisions if not d.aborted]
    flags, first_flags = [], []
    for d in decisions:
        if d.aborted and d.executed_skill is not None:
            raise MetricsError(f"{d.agent_id}, {d.year}: aborted decision has an executed action")
    for d in executed:
        key = (d.agent_id, d.year)
        if key not in pre_elevated:
            raise MetricsError(f"{key}: missing recorded pre-decision elevation")
        flags.append(rule_flags(d, pre_elevated[key]))
        # The same appraisal and predicates, with the FIRST proposed action.
        tp, cp = (_label(d.first_labels, key) for key in ("TP_LABEL", "CP_LABEL"))
        proposal = _action(d.first_proposal, f"{key}: first proposal")
        first_flags.append({
            "R1": proposal == "do_nothing" and tp in {"H", "VH"} and cp in {"M", "H", "VH"},
            "R3": proposal == "relocate" and tp in {"VL", "L"},
            "R4": proposal == "elevate_house" and tp in {"VL", "L"},
        })
    n = len(executed)
    counts = {rule: sum(f[rule] for f in flags) for rule in RULES}
    combined = sum(any(f.values()) for f in flags)
    behavioural = sum(any(f[rule] for rule in BEHAVIOURAL_RULES) for f in flags)
    first = sum(any(f.values()) for f in first_flags)
    return {
        "n": n, "n_aborted": sum(d.aborted for d in decisions),
        "ibr_executed_count": combined, "ibr_executed_pct": _pct(combined, n),
        "ibr_scope": "strict enforced R1/R3/R4/R5",
        "behavioural_count": behavioural, "behavioural_ibr_pct": _pct(behavioural, n),
        "behavioural_note": "first-stated threat and coping; WARNING rules excluded",
        "physical_count": counts["R5"], "physical_ibr_pct": _pct(counts["R5"], n),
        "physical_note": "recorded pre-decision elevation",
        **{f"{rule}_count": count for rule, count in counts.items()},
        "first_behavioural_count": first, "first_behavioural_pct": _pct(first, n),
        **{f"first_{rule}_count": sum(f[rule] for f in first_flags) for rule in BEHAVIOURAL_RULES},
        "n_threat_never_stated": sum(not _label(d.first_labels, "TP_LABEL") for d in executed),
        "n_coping_never_stated": sum(not _label(d.first_labels, "CP_LABEL") for d in executed),
    }


def pi_ibr_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """r44 compute_ibr_first(first_attempt_exact, True, True), without proxies.

    The denominator is ALL audit rows, including unresolved/aborted rows.
    r44 admits an unparsed final attempt only for an R1-only fallback with
    recorded do_nothing proposals throughout; other fallbacks contribute no
    numerator. Its restricted R1 reads missing coping as 'not low'. These
    historical conventions are deliberately confined to this PI measure.
    """
    counts = dict.fromkeys(BEHAVIOURAL_RULES, 0)
    unresolved = fallback_excluded = unknown_coping = 0
    for i, row in enumerate(rows, 1):
        missing = REQUIRED_PI_COLUMNS - row.keys()
        if missing:
            raise MetricsError(f"PI row {i}: missing recorded columns {sorted(missing)}")
        initial = row.get("initial_skill") or ""
        if not initial.strip():
            unresolved += 1
            continue
        _action(initial, f"PI row {i}: initial proposal")
        labels = audit.parse_labels(row.get("initial_labels"))
        tp, cp = (_label(labels, key) for key in ("TP_LABEL", "CP_LABEL"))
        unknown_coping += cp not in LABELS
        status = (row.get("status") or "").strip().upper()
        if status == "REJECTED_FALLBACK":
            failures = {s.strip() for s in (row.get("failed_rules") or "").split("|") if s.strip()}
            if failures != {"extreme_threat_block"}:
                fallback_excluded += 1
                continue
            parsed = [s for s in (row.get("attempt_skills") or "").split("|") if s]
            if not parsed or any(s != "do_nothing" for s in parsed):
                raise MetricsError(f"PI row {i}: R1-only fallback lacks recorded do_nothing proposals")
            action = "do_nothing"
        else:
            action = _action(row.get("final_skill"), f"PI row {i}: final proposal")
        if tp in {"H", "VH"} and cp not in {"VL", "L"} and action == "do_nothing":
            counts["R1"] += 1
        elif tp in {"VL", "L"} and action == "relocate":
            counts["R3"] += 1
        elif tp in {"VL", "L"} and action == "elevate_house":
            counts["R4"] += 1
    count, n = sum(counts.values()), len(rows)
    return {
        "n_pi": n, "ibr_final_proposal_pi_count": count,
        "ibr_final_proposal_pi_pct": _pct(count, n),
        "pi_scope": "r44 exact first-attempt appraisal; R1/R3/R4; all audit rows",
        **{f"pi_{rule}_count": count for rule, count in counts.items()},
        "pi_unresolved_count": unresolved, "pi_fallback_excluded_count": fallback_excluded,
        "pi_coping_missing_or_invalid_count": unknown_coping,
    }


def action_entropy(actions: Iterable[str]) -> dict[str, float | None]:
    """Shannon entropy / log2(4), with shares as fractions."""
    counts = dict.fromkeys(ACTIONS, 0)
    for action in actions:
        counts[_action(action, "entropy")] += 1
    n = sum(counts.values())
    shares = {action: counts[action] / n if n else None for action in ACTIONS}
    entropy = -sum(p * math.log2(p) for p in shares.values() if p) / math.log2(4) if n else None
    return {"ehe": entropy, **{f"{action}_share": shares[action] for action in ACTIONS}}


def _key(row: Mapping[str, Any], where: str) -> tuple[str, str]:
    agent = str(row.get("agent_id") or "").strip()
    value = row.get("year")
    try:
        year = float(value)
    except (TypeError, ValueError) as exc:
        raise MetricsError(f"{where}: missing/invalid year") from exc
    if not agent or not math.isfinite(year) or year != int(year) or year < 1:
        raise MetricsError(f"{where}: missing agent_id or invalid year")
    return agent, str(int(year))


def _csv(path: Path) -> tuple[set[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise MetricsError(f"{path}: malformed CSV row")
    return columns, rows


def _pre_elevation(path: Path, keys: set[tuple[str, str]]) -> dict[tuple[str, str], bool]:
    traces = path / "raw" / "household_traces.jsonl"
    if not traces.is_file():
        raise MetricsError(f"{path}: missing pre-decision evidence: {traces}")
    states = {}
    seen = set()
    with traces.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            where = f"{traces}:{line_number}"
            try:
                trace = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MetricsError(f"{where}: malformed trace JSON") from exc
            if not isinstance(trace, dict):
                raise MetricsError(f"{where}: trace must be an object")
            # GenericAuditWriter prepends one schema metadata record.
            if set(trace) <= {"_metadata", "agent_type"} and isinstance(trace.get("_metadata"), dict):
                continue
            key = _key(trace, where)
            if key in seen:
                raise MetricsError(f"{where}: duplicate trace decision {key}")
            seen.add(key)
            if key not in keys:
                continue
            state = trace.get("state_before")
            elevated = state.get("elevated") if isinstance(state, dict) else None
            if type(elevated) is not bool:
                raise MetricsError(f"{where}: missing/invalid pre-decision elevated boolean")
            states[key] = elevated
    if keys - states.keys():
        raise MetricsError(f"{path}: missing pre-decision elevation for {sorted(keys - states.keys())[:5]}")
    return states


def _metadata(path: Path, kind: str) -> dict[str, Any]:
    manifest_path = path / "reproducibility_manifest.json"
    manifest = {}
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        if not isinstance(manifest, dict):
            raise MetricsError(f"{manifest_path}: expected an object")
    return {"run": str(path.resolve()), "kind": kind,
            "commit": manifest.get("git_commit", manifest.get("git_head")),
            "seed": manifest.get("seed"), "model": manifest.get("model"),
            "governance_profile": manifest.get("governance_profile"),
            "retry_feedback_mode": manifest.get("retry_feedback_mode")}


def _rulebased_run(path: Path) -> dict[str, Any]:
    """Read recorded yearly choices; keep state-only legacy runs unavailable."""
    sim = path / "simulation_log.csv"
    if not sim.is_file():
        raise MetricsError(f"{path}: no flood audit or rule-based simulation log")
    columns, rows = _csv(sim)
    if not {"agent_id", "year", "decision", "elevated"} <= columns:
        raise MetricsError(f"{path}: unrecognized rule-based simulation log")
    if "yearly_decision" in columns or "proposed_skill" in columns:
        raise MetricsError(f"{path}: missing LLM audit; cannot classify this as rule-based")
    result = {
        **_metadata(path, "rulebased"), "n_logged_rows": len(rows), "n": None, "n_aborted": None,
        "ibr_scope": "not applicable", "behavioural_note": "not applicable: no stated appraisal",
        "ibr_executed_count": None, "ibr_executed_pct": None,
        "behavioural_count": None, "behavioural_ibr_pct": None,
        "physical_count": None, "physical_ibr_pct": None,
        "physical_note": "unavailable: executed action and pre-decision elevation not logged",
        **{f"{rule}_count": None for rule in RULES},
        "first_behavioural_count": None, "first_behavioural_pct": None,
        "n_pi": None, "ibr_final_proposal_pi_count": None, "ibr_final_proposal_pi_pct": None,
        "pi_scope": "not applicable: no stated appraisal",
        "action_note": "unavailable: decision is cumulative adaptation state, not executed action",
        **action_entropy([]),
    }
    recorded = {"executed_action", "elevated_before", "relocated_before"}
    if not recorded & columns:
        return result
    if recorded - columns:
        raise MetricsError(f"{sim}: missing recorded decision columns {sorted(recorded - columns)}")
    actions, by_year, seen = [], {}, set()
    physical = no_decision = 0
    for line_number, row in enumerate(rows, 2):
        where = f"{sim}:{line_number}"
        key = _key(row, where)
        if key in seen:
            raise MetricsError(f"{where}: duplicate rule-based decision {key}")
        seen.add(key)
        year = int(key[1])
        yearly = by_year.setdefault(year, [])
        elevated = _recorded_bool(row["elevated_before"], f"{where}: elevated_before")
        relocated = _recorded_bool(row["relocated_before"], f"{where}: relocated_before")
        action = row["executed_action"]
        if relocated:
            if action:
                raise MetricsError(f"{where}: already relocated household has no decision but logs an action")
            no_decision += 1
            continue
        action = _action(action, where)
        actions.append(action)
        yearly.append(action)
        physical += action == "elevate_house" and elevated
    result.update({
        "n": len(actions), "n_no_decision": no_decision,
        "physical_count": physical, "physical_ibr_pct": _pct(physical, len(actions)),
        "physical_note": "executed_action and recorded elevated_before; no-decision rows excluded",
        "R5_count": physical,
        "action_note": "executed_action; relocated_before no-decision rows excluded",
        **action_entropy(actions),
    })
    for year, yearly in sorted(by_year.items()):
        result[f"year_{year}_n"] = len(yearly)
        result.update({f"year_{year}_{key}": value for key, value in action_entropy(yearly).items()})
    return result


def _recorded_bool(value: str, where: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise MetricsError(f"{where}: missing/invalid recorded boolean {value!r}")
    return normalized == "true"


def projection_run(path: Path) -> dict[str, Any]:
    path = Path(path)
    audit_path = path / "household_governance_audit.csv"
    if not audit_path.is_file():
        return _rulebased_run(path)
    columns, rows = _csv(audit_path)
    missing = (audit.REQUIRED_COLUMNS | REQUIRED_PI_COLUMNS | {"agent_id", "year"}) - columns
    if missing:
        raise MetricsError(f"{path}: missing recorded audit columns {sorted(missing)}; no reconstruction")
    decisions, seen = [], set()
    for line_number, raw in enumerate(rows, 2):
        where = f"{audit_path}:{line_number}"
        key = _key(raw, where)
        if key in seen:
            raise MetricsError(f"{where}: duplicate audit decision {key}")
        seen.add(key)
        normalized = {**raw, "agent_id": key[0], "year": key[1]}
        d = audit.parse_decision(normalized, where)
        if not d.aborted:
            for attempt in d.attempts:
                if attempt.skill is not None:
                    _action(attempt.skill, where)
        decisions.append(d)
    executed_keys = {(d.agent_id, d.year) for d in decisions if not d.aborted}
    pre_elevated = _pre_elevation(path, executed_keys) if executed_keys else {}
    result = {**_metadata(path, "llm"), **ibr_summary(decisions, pre_elevated),
              **pi_ibr_summary(rows),
              "action_note": "executed_skill; aborted decisions excluded",
              **action_entropy(d.executed_skill for d in decisions if not d.aborted)}
    for year in sorted({int(d.year) for d in decisions}):
        actions = [d.executed_skill for d in decisions if int(d.year) == year and not d.aborted]
        result[f"year_{year}_n"] = len(actions)
        result.update({f"year_{year}_{key}": value for key, value in action_entropy(actions).items()})
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True).add_parser("projection")
    sub.add_argument("--runs", type=Path, nargs="+", required=True)
    sub.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = args.out.resolve()
    if any(destination.is_relative_to(path.resolve()) for path in args.runs):
        raise MetricsError("--out must be outside every input run folder")
    rows = [projection_run(path) for path in args.runs]
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
