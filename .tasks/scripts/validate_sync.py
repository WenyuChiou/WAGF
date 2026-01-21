#!/usr/bin/env python3
"""
Validate synchronization between registry.json and handoff files.

This script checks for status mismatches between:
1. registry.json task/subtask status
2. handoff/task-XXX.md status markers
3. current-session.md active task status

Usage:
    python .tasks/scripts/validate_sync.py
    python .tasks/scripts/validate_sync.py --fix  # Auto-sync (future)
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class StatusMismatch:
    """Represents a status synchronization mismatch."""

    def __init__(self, task_id: str, location: str, expected: str, actual: str):
        self.task_id = task_id
        self.location = location
        self.expected = expected
        self.actual = actual

    def __str__(self):
        return f"  [X] {self.task_id} @ {self.location}: registry={self.expected} <-> file={self.actual}"


class SyncValidator:
    """Validates status synchronization across task management files."""

    def __init__(self, tasks_dir: Path):
        self.tasks_dir = tasks_dir
        self.registry_path = tasks_dir / "registry.json"
        self.handoff_dir = tasks_dir / "handoff"
        self.current_session_path = self.handoff_dir / "current-session.md"

        self.mismatches: List[StatusMismatch] = []
        self.registry_data: Optional[Dict] = None

    def load_registry(self) -> bool:
        """Load and parse registry.json."""
        if not self.registry_path.exists():
            print(f"❌ registry.json not found at {self.registry_path}")
            return False

        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                self.registry_data = json.load(f)
            return True
        except json.JSONDecodeError as e:
            print(f"❌ registry.json parse error: {e}")
            return False

    def extract_status_from_markdown(self, md_path: Path) -> Dict[str, str]:
        """
        Extract status markers from handoff markdown file.

        Looks for patterns like:
        - ## Status: completed
        - | 027-A | ... | **done** |
        - Status: ✅ completed
        """
        if not md_path.exists():
            return {}

        statuses = {}

        try:
            with open(md_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Pattern 1: ## Status: <status>
            main_status_match = re.search(r'##\s+Status[:\s]+(\w+)', content, re.IGNORECASE)
            if main_status_match:
                statuses['main'] = main_status_match.group(1).lower()

            # Pattern 2: | subtask_id | ... | **STATUS** |
            subtask_pattern = r'\|\s*([\d\-A-Z]+)\s*\|[^|]*\|\s*\*\*(\w+)\*\*\s*\|'
            for match in re.finditer(subtask_pattern, content):
                subtask_id = match.group(1)
                status = match.group(2).lower()
                statuses[subtask_id] = status

            # Pattern 3: **Status**: <status>
            inline_status_match = re.search(r'\*\*Status\*\*[:\s]+(\w+)', content, re.IGNORECASE)
            if inline_status_match and 'main' not in statuses:
                statuses['main'] = inline_status_match.group(1).lower()

        except Exception as e:
            print(f"⚠️  Error reading {md_path}: {e}")

        return statuses

    def normalize_status(self, status: str) -> str:
        """Normalize status values to standard format."""
        status = status.lower().strip()

        # Map variants to standard status
        status_map = {
            'done': 'completed',
            'complete': 'completed',
            'finished': 'completed',
            'pending': 'pending',
            'todo': 'pending',
            'in-progress': 'in_progress',
            'in progress': 'in_progress',
            'working': 'in_progress',
            'blocked': 'blocked',
            'paused': 'blocked',
        }

        return status_map.get(status, status)

    def validate_task(self, task: Dict) -> List[StatusMismatch]:
        """Validate a single task against its handoff file."""
        task_id = task.get('id', 'unknown')
        registry_status = self.normalize_status(task.get('status', 'unknown'))

        handoff_file = task.get('handoff_file', f'handoff/task-{task_id.lower()}.md')
        handoff_path = self.tasks_dir / handoff_file

        mismatches = []

        if not handoff_path.exists():
            # Skip if handoff file doesn't exist (might be old archived task)
            return mismatches

        # Extract statuses from handoff file
        file_statuses = self.extract_status_from_markdown(handoff_path)

        # Check main task status
        if 'main' in file_statuses:
            file_status = self.normalize_status(file_statuses['main'])
            if file_status != registry_status:
                mismatches.append(StatusMismatch(
                    task_id=task_id,
                    location=handoff_file,
                    expected=registry_status,
                    actual=file_status
                ))

        # Check subtask statuses
        if 'subtasks' in task:
            for subtask in task['subtasks']:
                subtask_id = subtask.get('id', '')
                registry_sub_status = self.normalize_status(subtask.get('status', 'unknown'))

                if subtask_id in file_statuses:
                    file_sub_status = self.normalize_status(file_statuses[subtask_id])
                    if file_sub_status != registry_sub_status:
                        mismatches.append(StatusMismatch(
                            task_id=f"{task_id}/{subtask_id}",
                            location=handoff_file,
                            expected=registry_sub_status,
                            actual=file_sub_status
                        ))

        return mismatches

    def validate_current_session(self) -> List[StatusMismatch]:
        """Validate current-session.md against registry.json."""
        mismatches = []

        if not self.current_session_path.exists():
            return mismatches

        # Extract active task from current-session.md
        session_statuses = self.extract_status_from_markdown(self.current_session_path)

        # Find all tasks mentioned in current-session.md
        with open(self.current_session_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for task references
        task_refs = re.findall(r'(Task-\d+|task-\d+)', content, re.IGNORECASE)

        for task_ref in set(task_refs):
            task_ref_upper = task_ref.upper().replace('TASK-', 'Task-')

            # Find in registry
            registry_task = next(
                (t for t in self.registry_data['tasks'] if t['id'] == task_ref_upper),
                None
            )

            if registry_task:
                # Compare status if available in session file
                if task_ref in session_statuses or task_ref.lower() in session_statuses:
                    session_status = self.normalize_status(
                        session_statuses.get(task_ref, session_statuses.get(task_ref.lower(), ''))
                    )
                    registry_status = self.normalize_status(registry_task.get('status', ''))

                    if session_status != registry_status:
                        mismatches.append(StatusMismatch(
                            task_id=task_ref_upper,
                            location='current-session.md',
                            expected=registry_status,
                            actual=session_status
                        ))

        return mismatches

    def run_validation(self) -> bool:
        """Run full validation suite."""
        print("=" * 70)
        print("Registry.json <-> Handoff Files Synchronization Validator")
        print("=" * 70)
        print()

        # Load registry
        if not self.load_registry():
            return False

        print(f"[OK] Loaded registry.json (v{self.registry_data.get('version', 'unknown')})")
        print(f"     Last updated: {self.registry_data.get('last_updated', 'unknown')}")
        print(f"     Total tasks: {len(self.registry_data.get('tasks', []))}")
        print()

        # Validate each task
        print("[INFO] Validating task-specific handoff files...")
        for task in self.registry_data.get('tasks', []):
            task_mismatches = self.validate_task(task)
            self.mismatches.extend(task_mismatches)

        # Validate current-session.md
        print("[INFO] Validating current-session.md...")
        session_mismatches = self.validate_current_session()
        self.mismatches.extend(session_mismatches)

        print()
        print("=" * 70)
        print("Validation Results")
        print("=" * 70)
        print()

        if not self.mismatches:
            print("[OK] All statuses are synchronized!")
            print("     No mismatches found between registry.json and handoff files.")
            return True
        else:
            print(f"[ERROR] Found {len(self.mismatches)} status mismatch(es):")
            print()
            for mismatch in self.mismatches:
                print(mismatch)
            print()
            print("[RECOMMENDATION]:")
            print("   Review and update either registry.json or the handoff files")
            print("   to ensure status consistency across all task tracking files.")
            return False


def main():
    """Main entry point."""
    # Determine .tasks directory
    script_path = Path(__file__).resolve()
    tasks_dir = script_path.parent.parent

    validator = SyncValidator(tasks_dir)
    success = validator.run_validation()

    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
