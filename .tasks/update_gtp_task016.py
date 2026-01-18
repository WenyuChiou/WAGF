import json
import os
from pathlib import Path
from datetime import datetime

TASKS_DIR = Path("H:/我的雲端硬碟/github/governed_broker_framework/.tasks")
REGISTRY_PATH = TASKS_DIR / "registry.json"
CURRENT_SESSION_PATH = TASKS_DIR / "handoff/current-session.md"

def update_tasks():
    # 1. Update Registry
    registry_content = ""
    try:
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            registry = json.load(f)
    except UnicodeDecodeError:
        print("UTF-8 failed, trying cp950 (Big5)...")
        try:
            with open(REGISTRY_PATH, 'r', encoding='cp950') as f:
                registry = json.load(f)
        except:
             print("Fallback to binary read...")
             with open(REGISTRY_PATH, 'rb') as f:
                 registry = json.loads(f.read().decode('utf-8', 'ignore'))
    
    new_task = {
        "id": "Task-016",
        "title": "JOH Technical Note Finalization",
        "status": "planned",
        "owner": "Antigravity",
        "description": "Finalize the single-agent technical note with verified Gemma 3 results and halted DeepSeek findings.",
        "dependencies": ["Task-015"], # Assuming 15 was verification, loosely dependent
        "created_at": datetime.utcnow().isoformat() + "Z",
        "subtasks": [
            {"id": "016-A", "title": "Draft Integration", "status": "in_progress", "assigned_to": "Antigravity"},
            {"id": "016-B", "title": "DeepSeek Slowness Analysis", "status": "completed", "assigned_to": "Antigravity"},
            {"id": "016-C", "title": "Figure Generation", "status": "completed", "assigned_to": "Antigravity"},
            {"id": "016-D", "title": "Final Submission Polish", "status": "pending", "assigned_to": "Antigravity"}
        ]
    }
    
    registry['tasks'].append(new_task)
    
    with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    
    print("Registry updated with Task-016.")

    # 2. Create Task Plan
    task_plan_content = """# Task-016: JOH Technical Note Finalization

## Objective
To wrap up the "Governed Broker Framework" single-agent technical note (JOH) by consolidating the successful Gemma 3 simulations and documenting the DeepSeek R1 trade-offs.

## Context
- **Gemma 3 4B**: Verified stability improvements (37% reduction in variance). Sawtooth curve confirmed.
- **DeepSeek R1**: Discontinued due to excessive reasoning time (~35s/step), but this is a valuable negative result for the discussion (Reasoning Cost).

## Subtasks & Status

| ID | Title | Status | Notes |
|:---|:------|:-------|:------|
| **016-A** | Draft Integration | `in_progress` | Intro rewritten (Qi-Cheng-Zhuan-He), Results updated. |
| **016-B** | DeepSeek Analysis | `completed` | Cost analysis added to Draft Discussion. |
| **016-C** | Figure Generation | `completed` | Figures 2, 3 generated and linked. |
| **016-D** | Final Polish | `pending` | Double check formatting, links, and tone. |

## Verification Logic
- [ ] Check `joh_technical_note_draft.md` renders images correctly.
- [ ] Ensure all 3 pillars (Governance, Perception, Memory) are discussed.
- [ ] Verify "limitations" section mentions the execution cost.
"""
    
    with open(TASKS_DIR / "handoff/task-016.md", 'w', encoding='utf-8') as f:
        f.write(task_plan_content)
    print("Created task-016.md.")

    # 3. Update Current Session
    with open(CURRENT_SESSION_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Simple replace for Active Task
    new_lines = []
    for line in lines:
        if line.strip().startswith("Task-015: MA System Comprehensive Verification"):
             new_lines.append("Task-016: JOH Technical Note Finalization (in-progress)\n")
        elif line.strip().startswith("- **Current Task**: Task-015"):
             new_lines.append("- **Previous Task**: Task-015 (MA System Verification) - Pending/Switching\n")
             new_lines.append("- **Current Task**: Task-016 (JOH Finalization)\n")
        else:
             new_lines.append(line)
    
    with open(CURRENT_SESSION_PATH, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("Updated current-session.md.")

if __name__ == "__main__":
    update_tasks()
