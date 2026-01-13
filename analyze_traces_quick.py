
import json
import collections

trace_path = r"examples/single_agent/results_humancentric/gemma3_4b_strict/raw/household_traces.jsonl"

try:
    with open(trace_path, "r", encoding="utf-8") as f:
        lines = f.readlines()[-50:] # Last 50 lines
        
    print(f"--- Analyzing last {len(lines)} traces ---")
    
    first_item = json.loads(lines[0])
    # print(f"Top-level keys sample: {list(first_item.keys())}")
    
    validated_count = 0
    decisions = collections.Counter()
    
    print_debug = True

    for line in lines:
        try:
            item = json.loads(line)
            step = item.get("step_id")
            val = item.get("validated", False)
            if val: validated_count += 1
            
            p_out = item.get("parsed_output")
            
            if validated_count == 1:
                print(f"DEBUG: All Keys: {list(item.keys())}")
                print(f"DEBUG: parsed_output type: {type(p_out)}")
                print(f"DEBUG: parsed_output value: {p_out}")

            dec = "Unknown"
            if isinstance(p_out, dict):
                dec = p_out.get("decision", "NoDecisionKey")
            else:
                dec = "ParsedNotDict"

            decisions[dec] += 1
            
        except Exception as e:
            pass
            
    print(f"Total Traces Scanned: {len(lines)}")
    print(f"Validated: {validated_count}/{len(lines)} ({validated_count/len(lines)*100:.1f}%)")
    print("Decision Distribution:")
    for d, c in decisions.items():
        print(f"  {d}: {c}")

except FileNotFoundError:
    print("Trace file not found!")
