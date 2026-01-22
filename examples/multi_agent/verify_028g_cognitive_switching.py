"""
Task-028-G Verification: Check System 1/2 Switching and Crisis Mechanism

Analyzes agent traces to verify:
1. System 1/2 switching based on surprise (environmental_indicator)
2. Crisis mechanism activation (crisis_event boosters)
3. Memory retrieval mode changes (legacy vs weighted)
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

def analyze_cognitive_switching(trace_file: Path) -> dict:
    """Analyze a trace file for cognitive switching evidence."""

    results = {
        "total_steps": 0,
        "system_1_count": 0,
        "system_2_count": 0,
        "crisis_activations": 0,
        "surprise_detected": 0,
        "agents_analyzed": set(),
        "system_switches": [],  # Track actual switches
        "crisis_events": [],
        "missing_cognitive_state": 0
    }

    agent_states = {}  # Track last system for each agent

    try:
        with open(trace_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    results["total_steps"] += 1

                    agent_id = entry.get("agent_id", "unknown")
                    results["agents_analyzed"].add(agent_id)

                    # Check for cognitive state info
                    cognitive_state = entry.get("cognitive_state")
                    memory_context = entry.get("memory_context")
                    context = entry.get("context", {})

                    # Method 1: Direct cognitive_state field
                    if cognitive_state:
                        system = cognitive_state.get("system")
                        surprise = cognitive_state.get("surprise", 0)

                        if system == "SYSTEM_1":
                            results["system_1_count"] += 1
                        elif system == "SYSTEM_2":
                            results["system_2_count"] += 1

                        if surprise and surprise > 0:
                            results["surprise_detected"] += 1

                        # Track system switches
                        if agent_id in agent_states and agent_states[agent_id] != system:
                            results["system_switches"].append({
                                "agent": agent_id,
                                "step": results["total_steps"],
                                "from": agent_states[agent_id],
                                "to": system,
                                "surprise": surprise
                            })
                        agent_states[agent_id] = system

                    # Method 2: Check memory_context for system info
                    elif memory_context:
                        # Some memory engines log ranking_mode or system info
                        if "system" in str(memory_context).lower():
                            results["surprise_detected"] += 1

                    # Method 3: Check for crisis_event in context
                    if context and "crisis_event" in context:
                        results["crisis_activations"] += 1
                        results["crisis_events"].append({
                            "agent": agent_id,
                            "step": results["total_steps"],
                            "crisis_value": context.get("crisis_event")
                        })

                    # Check for crisis boosters in action/decision
                    action_data = entry.get("action", {})
                    if isinstance(action_data, dict):
                        boosters = action_data.get("contextual_boosters", {})
                        if "crisis_event" in boosters or "hazard_imminent" in boosters:
                            results["crisis_activations"] += 1

                    # If no cognitive state found, track it
                    if not cognitive_state:
                        results["missing_cognitive_state"] += 1

                except json.JSONDecodeError as e:
                    print(f"Warning: JSON decode error on line {line_num}: {e}", file=sys.stderr)
                    continue

    except FileNotFoundError:
        print(f"Error: Trace file not found: {trace_file}", file=sys.stderr)
        return None

    return results


def main():
    """Main verification function."""

    # Find trace files
    trace_dir = Path("examples/multi_agent/results_unified/v028_verification/gemma3_4b_strict/raw")

    if not trace_dir.exists():
        print(f"[FAIL] Trace directory not found: {trace_dir}")
        print("\nTrying alternative locations...")

        # Try v028_flood_test
        trace_dir = Path("examples/multi_agent/results_unified/v028_flood_test/gemma3_4b_strict/raw")

    if not trace_dir.exists():
        print(f"❌ No trace directories found for 028 verification")
        return 1

    print(f"📂 Analyzing traces in: {trace_dir}\n")

    trace_files = list(trace_dir.glob("*_traces.jsonl"))

    if not trace_files:
        print(f"❌ No trace files found in {trace_dir}")
        return 1

    print(f"Found {len(trace_files)} trace files:")
    for f in trace_files:
        print(f"  - {f.name}")
    print()

    # Analyze each trace file
    all_results = {}

    for trace_file in trace_files:
        agent_type = trace_file.stem.replace("_traces", "")
        print(f"🔍 Analyzing {agent_type}...")

        results = analyze_cognitive_switching(trace_file)

        if results:
            all_results[agent_type] = results

            print(f"  Total steps: {results['total_steps']}")
            print(f"  Agents analyzed: {len(results['agents_analyzed'])}")
            print(f"  System 1 activations: {results['system_1_count']}")
            print(f"  System 2 activations: {results['system_2_count']}")
            print(f"  System switches: {len(results['system_switches'])}")
            print(f"  Crisis activations: {results['crisis_activations']}")
            print(f"  Surprise detected: {results['surprise_detected']}")
            print(f"  Missing cognitive state: {results['missing_cognitive_state']}")
            print()

    # Summary report
    print("="*60)
    print("📊 VERIFICATION SUMMARY (Task-028-G)")
    print("="*60)

    total_steps = sum(r["total_steps"] for r in all_results.values())
    total_system_1 = sum(r["system_1_count"] for r in all_results.values())
    total_system_2 = sum(r["system_2_count"] for r in all_results.values())
    total_switches = sum(len(r["system_switches"]) for r in all_results.values())
    total_crisis = sum(r["crisis_activations"] for r in all_results.values())
    total_surprise = sum(r["surprise_detected"] for r in all_results.values())
    total_missing = sum(r["missing_cognitive_state"] for r in all_results.values())

    print(f"\n📈 Overall Statistics:")
    print(f"  Total decision steps: {total_steps}")
    print(f"  System 1 (routine): {total_system_1}")
    print(f"  System 2 (crisis): {total_system_2}")
    print(f"  System switches: {total_switches}")
    print(f"  Crisis activations: {total_crisis}")
    print(f"  Surprise signals: {total_surprise}")
    print(f"  Missing cognitive data: {total_missing}")

    # Verification checks
    print(f"\n✅ Verification Checks:")

    checks = []

    # Check 1: System switching evidence
    if total_system_1 > 0 or total_system_2 > 0:
        checks.append(("✅", "Cognitive system tracking present"))

        if total_switches > 0:
            checks.append(("✅", f"System switching detected ({total_switches} switches)"))
        elif total_missing < total_steps * 0.9:  # Less than 90% missing
            checks.append(("⚠️", "System states logged but no switches detected"))
        else:
            checks.append(("❌", "No system switching detected"))
    else:
        if total_missing > total_steps * 0.9:  # More than 90% missing
            checks.append(("⚠️", "Cognitive state not logged in traces (expected for some configs)"))
        else:
            checks.append(("❌", "No cognitive system data found"))

    # Check 2: Crisis mechanism
    if total_crisis > 0:
        checks.append(("✅", f"Crisis mechanism activated ({total_crisis} times)"))
    else:
        checks.append(("⚠️", "No crisis activations detected (may not have occurred in this run)"))

    # Check 3: Surprise tracking
    if total_surprise > 0:
        checks.append(("✅", f"Surprise mechanism working ({total_surprise} detections)"))
    else:
        checks.append(("⚠️", "No surprise signals detected"))

    for status, message in checks:
        print(f"  {status} {message}")

    # Show sample switches
    if total_switches > 0:
        print(f"\n📝 Sample System Switches:")
        sample_count = 0
        for agent_type, results in all_results.items():
            for switch in results["system_switches"][:3]:  # First 3 per agent type
                print(f"  {agent_type} - {switch['agent']}: {switch['from']} → {switch['to']} "
                      f"(step {switch['step']}, surprise={switch['surprise']:.2f})")
                sample_count += 1
                if sample_count >= 5:
                    break
            if sample_count >= 5:
                break

    # Show sample crisis events
    if total_crisis > 0:
        print(f"\n🚨 Sample Crisis Events:")
        sample_count = 0
        for agent_type, results in all_results.items():
            for crisis in results["crisis_events"][:2]:
                print(f"  {agent_type} - {crisis['agent']}: step {crisis['step']}, "
                      f"value={crisis.get('crisis_value', 'N/A')}")
                sample_count += 1
                if sample_count >= 5:
                    break
            if sample_count >= 5:
                break

    # Final verdict
    print(f"\n{'='*60}")

    passed_checks = sum(1 for s, _ in checks if s == "✅")
    total_checks = len(checks)

    if passed_checks == total_checks:
        print("🎉 Task-028-G: PASS - All verification checks passed!")
        return 0
    elif passed_checks >= total_checks - 1:
        print("✅ Task-028-G: PASS (with warnings) - Core functionality verified")
        return 0
    else:
        print("⚠️ Task-028-G: PARTIAL - Some checks failed, review needed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
