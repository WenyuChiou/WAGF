
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

def analyze_traces(traces_dir: Path):
    """
    Analyzes trace files to calculate parse success and retry metrics.
    """
    stats = defaultdict(lambda: {
        "total": 0,
        "success": 0,
        "retry_needed": 0,
        "layer_distribution": Counter()
    })

    for trace_file in traces_dir.glob("*.jsonl"):
        with trace_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    trace = json.loads(line)
                except json.JSONDecodeError:
                    continue

                agent_type = trace.get("agent_type", "unknown")
                stats[agent_type]["total"] += 1

                # A decision is successful if the outcome is APPROVED or RETRY_SUCCESS
                if trace.get("outcome") in ["APPROVED", "RETRY_SUCCESS"]:
                    stats[agent_type]["success"] += 1
                
                if trace.get("retry_count", 0) > 0:
                    stats[agent_type]["retry_needed"] += 1

                parse_layer = (trace.get("skill_proposal") or {}).get("parse_layer", "unknown")
                stats[agent_type]["layer_distribution"][parse_layer] += 1

    return stats

def generate_report(stats, model_name):
    """
    Generates a JSON report from the analyzed statistics.
    """
    report = {
        "parse_success_analysis": {
            "model": model_name,
            "agent_stats": {},
            "overall_layer_distribution": Counter()
        }
    }

    total_layer_dist = Counter()

    for agent_type, data in sorted(stats.items()):
        success_rate = (data["success"] / data["total"]) if data["total"] > 0 else 0
        report["parse_success_analysis"]["agent_stats"][agent_type] = {
            "total": data["total"],
            "success": data["success"],
            "retry_needed": data["retry_needed"],
            "success_rate": round(success_rate, 3),
            "layer_distribution": dict(data["layer_distribution"])
        }
        total_layer_dist.update(data["layer_distribution"])

    report["parse_success_analysis"]["overall_layer_distribution"] = dict(total_layer_dist)
    report["parse_success_analysis"]["comparison_notes"] = "MA parse methodology: multi-layer (enclosure -> JSON -> keyword -> digit -> default). Success rate reflects if a valid decision was eventually made, including after retries."

    return report

def main():
    parser = argparse.ArgumentParser(description="Analyze parse success rate from MA agent traces.")
    parser.add_argument("--traces-dir", required=True, help="Directory containing the .jsonl trace files.")
    parser.add_argument("--model-name", required=True, help="Name of the model being analyzed (e.g., llama3.2:3b).")
    parser.add_argument("--output", required=True, help="Path to write the JSON report.")
    args = parser.parse_args()

    traces_dir = Path(args.traces_dir)
    stats = analyze_traces(traces_dir)
    report = generate_report(stats, args.model_name)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    print(f"Analysis report saved to {output_path}")

if __name__ == "__main__":
    main()
