
import json
import os

def debug_trace(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            print(f"--- Trace {i} ---")
            print(f"Keys: {list(data.keys())}")
            print(f"Input type: {type(data.get('input'))}")
            if data.get('input'):
                print("Content Preview:")
                print(data['input'][:500])
            else:
                print("Input is None or Empty")
            break


if __name__ == "__main__":
    import glob
    files = glob.glob("results/mock_llm_strict/raw/*.jsonl")
    if not files:
        print("No JSONL files found in results/mock_llm_strict/raw/")
    for f in files:
        print(f"\nScanning: {f}")
        debug_trace(f)
