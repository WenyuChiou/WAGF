import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

LOW_CP_LABELS = {"VL", "L"}
EXPENSIVE_ACTIONS = {"elevate_house", "buyout_program", "relocate"}


def load_traces(traces_dir: Path):
    traces = []
    for path in sorted(traces_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                traces.append(json.loads(line))
    return traces


def verify_v1_decision_diversity(traces):
    decisions = [
        (obj.get("skill_proposal") or {}).get("skill_name", "unknown").strip()
        for obj in traces
        if "skill_proposal" in obj
    ]
    
    counts = Counter(decisions)
    total_decisions = len(decisions)
    
    if not total_decisions:
        entropy = 0.0
    else:
        probs = [count / total_decisions for count in counts.values()]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)

    threshold = 1.5
    passed = entropy >= threshold

    return {
        "passed": passed,
        "details": {
            "shannon_entropy": round(entropy, 3),
            "entropy_threshold": threshold,
            "total_decisions": total_decisions,
            "unique_decisions": len(counts),
            "decision_distribution": dict(counts),
        },
    }


def verify_v4_behavior(traces):
    low_cp_total = 0
    low_cp_expensive = 0
    examples = []

    for obj in traces:
        sp = obj.get("skill_proposal") or {}
        decision = (sp.get("skill_name") or "").strip()
        reasoning = sp.get("reasoning") or {}
        cp_label = reasoning.get("CP_LABEL")
        if cp_label in LOW_CP_LABELS:
            low_cp_total += 1
            if decision in EXPENSIVE_ACTIONS:
                low_cp_expensive += 1
                if len(examples) < 10:
                    examples.append({
                        "agent_id": obj.get("agent_id"),
                        "step_id": obj.get("step_id"),
                        "decision": decision,
                        "cp_label": cp_label,
                    })

    low_cp_rate = (low_cp_expensive / low_cp_total) if low_cp_total else 0.0
    threshold = 0.2
    passed = low_cp_rate <= threshold

    return {
        "passed": passed,
        "details": {
            "low_cp_total": low_cp_total,
            "low_cp_expensive": low_cp_expensive,
            "low_cp_expensive_rate": round(low_cp_rate, 3),
            "low_cp_threshold": threshold,
            "low_cp_ok": passed,
            "rule_reminder": "If CP is VL/L, expensive actions (elevate/buyout/relocate) should be blocked or penalized.",
            "examples": examples,
        },
    }


def verify_v5_memory_state(traces):
    required_fields = ["memory_post", "state_after", "environment_context"]
    missing_field_counts = defaultdict(int)
    total_traces = len(traces)

    memory_reflection = defaultdict(bool)
    damage_series = defaultdict(list)
    missing_state_after = 0

    for obj in traces:
        for field in required_fields:
            if field not in obj:
                missing_field_counts[field] += 1

        agent_id = obj.get("agent_id")

        mem_post = obj.get("memory_post")
        if isinstance(mem_post, list):
            for item in mem_post:
                if isinstance(item, dict) and item.get("source") == "reflection":
                    memory_reflection[agent_id] = True

        state_after = obj.get("state_after")
        if isinstance(state_after, dict):
            damage = state_after.get("cumulative_damage")
            if damage is not None:
                damage_series[agent_id].append(damage)
        else:
            missing_state_after += 1

    reflection_missing = [agent for agent, ok in memory_reflection.items() if not ok]
    reflection_missing.sort()

    damage_violations = []
    for agent_id, values in damage_series.items():
        for idx in range(1, len(values)):
            if values[idx] < values[idx - 1]:
                damage_violations.append({
                    "agent_id": agent_id,
                    "index": idx,
                    "prev": values[idx - 1],
                    "curr": values[idx],
                })

    missing_fields = {k: v for k, v in missing_field_counts.items() if v > 0}
    incomplete = bool(missing_fields)

    violations = []
    if reflection_missing:
        violations.append(f"Missing reflection memories for agents: {', '.join(reflection_missing)}")
    if damage_violations:
        violations.append(f"Cumulative damage decreased for {len(damage_violations)} agent(s)")
    if incomplete:
        violations.append("Required trace fields missing; V5 cannot be fully verified.")

    passed = (not violations) and (not incomplete)

    return {
        "passed": passed,
        "details": {
            "total_traces": total_traces,
            "missing_fields": missing_fields,
            "missing_fields_total": sum(missing_fields.values()),
            "reflection_missing_count": len(reflection_missing),
            "damage_violation_count": len(damage_violations),
            "incomplete": incomplete,
        },
        "violations": violations,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    traces_dir = Path(args.traces_dir)
    traces = load_traces(traces_dir)

    v1 = verify_v1_decision_diversity(traces)
    v4 = verify_v4_behavior(traces)
    v5 = verify_v5_memory_state(traces)

    blocking = []
    if not v1["passed"]:
        blocking.append("V1_decision_diversity")
    if not v4["passed"]:
        blocking.append("V4_behavior_rationality")
    if not v5["passed"]:
        blocking.append("V5_memory_state")

    report = {
        "overall_passed": len(blocking) == 0,
        "blocking_issues": blocking,
        "results": {
            "V1_decision_diversity": v1,
            "V4_behavior_rationality": v4,
            "V5_memory_state": v5,
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)


if __name__ == "__main__":
    main()
