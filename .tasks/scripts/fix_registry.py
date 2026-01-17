import json
import os

reg_path = "H:/我的雲端硬碟/github/governed_broker_framework/.tasks/registry.json"

new_task = {
    "id": "task-011",
    "title": "Unified Gemini API Integration",
    "description": "Implement a universal module interface for connecting to the Gemini model API.",
    "status": "in-progress",
    "type": "feature",
    "priority": "high",
    "handoff_file": "handoff/task-011.md"
}

encodings = ['utf-8-sig', 'big5', 'utf-16', 'latin-1']
data = None

for enc in encodings:
    try:
        with open(reg_path, 'r', encoding=enc) as f:
            data = json.load(f)
            print(f"Success with {enc}")
            break
    except Exception as e:
        print(f"Failed with {enc}: {e}")

if data:
    data['tasks'].append(new_task)
    with open(reg_path, 'w', encoding='utf-8-sig') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Successfully appended task-011 to registry.json")
else:
    print("Could not load registry.json with any common encoding.")
