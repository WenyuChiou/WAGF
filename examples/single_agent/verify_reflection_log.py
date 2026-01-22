
import json

log_path = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b\Group_C\Run_1\gemma3_4b_strict\raw\household_traces.jsonl"

found = False
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        if "Consolidated Reflection" in line:
            print(f"FOUND REFLECTION ENTRY:\n{line[:500]}...") # Print first 500 chars to verify
            try:
                data = json.loads(line)
                # Check state_after or state_before for memory
                mem_str = data.get('state_after', {}).get('memory', '')
                if "Consolidated Reflection" in mem_str:
                    print("\n--- Extracted Reflection Memory ---")
                    start = mem_str.find("Consolidated Reflection")
                    end = mem_str.find("\n", start)
                    print(mem_str[start:end if end != -1 else None])
                    found = True
                    break
            except Exception as e:
                print(f"Error parsing JSON: {e}")

if not found:
    print("No 'Consolidated Reflection' found in file.")
