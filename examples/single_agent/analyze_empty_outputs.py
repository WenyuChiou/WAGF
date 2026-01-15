
import os
import json
import glob
from pathlib import Path

def analyze_directory(dir_path):
    print(f"\nAnalyzing: {dir_path}")
    path = Path(dir_path)
    if not path.exists():
        print("Path does not exist.")
        return

    empty_count = 0
    total_count = 0
    error_count = 0
    
    # helper to process a single dict object
    def check_obj(data, source_name):
        nonlocal empty_count
        # Check for LLM output fields
        response = None
        if 'llm_output' in data:
            response = data['llm_output']
        elif 'raw_decision' in data:
            response = data['raw_decision']
        elif 'response_text' in data:
            response = data['response_text']
        elif 'decision' in data:
            # Often decision objects are nested or processed, but let's check
            pass
            
        # Check specifically for "content": null or "" in OpenAI/compatible logs
        if 'choices' in data:
             try:
                 response = data['choices'][0]['message']['content']
             except:
                 pass

        if response is None:
             pass
        else:
            s_resp = str(response).strip()
            if not s_resp:
                 print(f"Empty/Null LLM response in: {source_name}")
                 empty_count += 1
                 return True
            elif len(s_resp) < 20:
                 print(f"Short Response in {source_name}: '{s_resp}'")
        return False

    # Check for .jsonl in raw
    jsonl_files = list(path.glob("**/*.jsonl"))
    if jsonl_files:
        print(f"Found {len(jsonl_files)} JSONL files.")
        for jf in jsonl_files:
            print(f"Reading {jf}...")
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        total_count += 1
                        if not line.strip(): continue
                        try:
                            data = json.loads(line)
                            check_obj(data, f"{jf.name}:{line_num}")
                        except json.JSONDecodeError:
                            print(f"JSON Decode Error in {jf.name}:{line_num}")
                            error_count += 1
            except Exception as e:
                print(f"Error reading file {jf}: {e}")
                error_count += 1
    
    # Also check standard .json files
    json_files = list(path.glob("**/*.json"))
    # filter out summary/manifest/jsonl
    json_files = [f for f in json_files if not f.name.endswith('.jsonl') and "summary" not in f.name and "manifest" not in f.name]
    
    if json_files:
        print(f"Found {len(json_files)} JSON trace files.")
        for file_path in json_files:
            total_count += 1
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        print(f"Empty file: {file_path.name}")
                        empty_count += 1
                        continue
                    data = json.loads(content)
                    check_obj(data, file_path.name)
            except json.JSONDecodeError:
                print(f"JSON Decode Error in: {file_path.name}")
                error_count += 1
            except Exception as e:
                print(f"Error reading {file_path.name}: {e}")
                error_count += 1

    print(f"Total Traces Scanned: {total_count}, Empty Responses: {empty_count}, Errors: {error_count}")

# Define paths to check
base_dirs = [
    r"examples\single_agent\results_window\gpt_oss_latest_strict",
    r"examples\single_agent\old_results\DeepSeek_R1_8B",
    r"examples\single_agent\old_results\GPT-OSS_20B"
]

for d in base_dirs:
    analyze_directory(d)
