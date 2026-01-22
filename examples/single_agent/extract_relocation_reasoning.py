
import json
import os

file_path = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b\Group_C\Run_1\gemma3_4b_strict\raw\household_traces.jsonl"

def extract_relocation_reasoning():
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    relocation_count = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    
                    # Check for relocation decision
                    is_relocate = False
                    
                    # Check explicit skill name
                    skill_proposal = data.get("skill_proposal", {})
                    if skill_proposal.get("skill_name") == "relocate":
                        is_relocate = True
                    
                    # Check numeric decision if needed (backup check)
                    # based on previous learnings: "3": "relocate"
                    raw_output = data.get("raw_output", {})
                    # Handle case where raw_output might be a string or dict
                    if isinstance(raw_output, str):
                        try:
                            # sometimes raw_output is a json string inside the json
                             raw_output_dict = json.loads(raw_output)
                             if raw_output_dict.get("decision") == 3:
                                 is_relocate = True
                        except:
                            pass
                    elif isinstance(raw_output, dict):
                        if raw_output.get("decision") == 3:
                            is_relocate = True

                    if is_relocate:
                        relocation_count += 1
                        agent_id = data.get("agent_id", "Unknown")
                        # Try to find year/step info if available
                        state_before = data.get("state_before", {})
                        step = state_before.get("step", "Unknown")
                        
                        reasoning = skill_proposal.get("reasoning", {}).get("reasoning", "No reasoning found")
                        
                        print(f"--- Relocation Found (Line {line_num+1}) ---")
                        print(f"Agent ID: {agent_id}")
                        print(f"Key Step/Year: {step}")
                        print(f"Reasoning: {reasoning}")
                        print("-" * 30)

                except json.JSONDecodeError:
                    print(f"Error decoding JSON on line {line_num+1}")
                    
    except Exception as e:
        print(f"An error occurred: {e}")


    print(f"\nTotal relocation decisions found: {relocation_count}")

    # Write to file
    output_file = "relocation_reasoning_utf8.txt"
    with open(output_file, "w", encoding="utf-8") as f_out:
        with open(file_path, 'r', encoding='utf-8') as f_in:
            for line_num, line in enumerate(f_in):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    is_relocate = False
                    skill_proposal = data.get("skill_proposal", {})
                    if skill_proposal.get("skill_name") == "relocate":
                        is_relocate = True
                    else:
                        raw_output = data.get("raw_output", {})
                        if isinstance(raw_output, dict) and raw_output.get("decision") == 3:
                            is_relocate = True
                        elif isinstance(raw_output, str):
                            try:
                                if json.loads(raw_output).get("decision") == 3:
                                    is_relocate = True
                            except: pass
                    
                    if is_relocate:
                        agent_id = data.get("agent_id", "Unknown")
                        state_before = data.get("state_before", {})
                        step = state_before.get("step", "Unknown")
                        reasoning = skill_proposal.get("reasoning", {}).get("reasoning", "No reasoning found")
                        
                        output_block = f"--- Relocation Found (Line {line_num+1}) ---\n" \
                                       f"Agent ID: {agent_id}\n" \
                                       f"Key Step/Year: {step}\n" \
                                       f"Reasoning: {reasoning}\n" \
                                       f"{'-' * 30}\n"
                        f_out.write(output_block)
                except:
                    pass
    print(f"Output written to {output_file}")

if __name__ == "__main__":
    extract_relocation_reasoning()

