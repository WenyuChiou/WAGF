#!/usr/bin/env python3
"""
Check and unblock tasks whose dependencies are complete.

This script:
1. Scans registry.json for blocked subtasks
2. Checks if their dependencies are completed
3. Reports which tasks can be unblocked
4. Optionally auto-updates status (with --fix flag)

Usage:
    python .tasks/scripts/check_unblock.py
    python .tasks/scripts/check_unblock.py --fix  # Auto-unblock
    python .tasks/scripts/check_unblock.py --task Task-028  # Check specific task
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class BlockedTask:
    """Represents a blocked task that may be unblockable."""

    def __init__(self, task_id: str, subtask_id: str, blocker_info: Dict):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.blocker_info = blocker_info
        self.can_unblock = False
        self.missing_deps = []

    def __str__(self):
        status_icon = "[READY]" if self.can_unblock else "[BLOCKED]"
        deps_str = ", ".join(self.missing_deps) if self.missing_deps else "None"
        return f"  {status_icon} {self.task_id}/{self.subtask_id} - Missing: {deps_str}"


class UnblockChecker:
    """Checks blocked tasks and determines if they can be unblocked."""

    def __init__(self, tasks_dir: Path, auto_fix: bool = False):
        self.tasks_dir = tasks_dir
        self.registry_path = tasks_dir / "registry.json"
        self.auto_fix = auto_fix
        self.registry_data: Optional[Dict] = None
        self.blocked_tasks: List[BlockedTask] = []

    def load_registry(self) -> bool:
        """Load registry.json."""
        if not self.registry_path.exists():
            print(f"[ERROR] registry.json not found at {self.registry_path}")
            return False

        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                self.registry_data = json.load(f)
            return True
        except json.JSONDecodeError as e:
            print(f"[ERROR] registry.json parse error: {e}")
            return False

    def get_subtask_status(self, task_id: str, subtask_id: str) -> Optional[str]:
        """Get the status of a specific subtask."""
        task = next(
            (t for t in self.registry_data['tasks'] if t['id'] == task_id),
            None
        )

        if not task or 'subtasks' not in task:
            return None

        subtask = next(
            (st for st in task['subtasks'] if st['id'] == subtask_id),
            None
        )

        return subtask.get('status') if subtask else None

    def check_dependencies_met(self, depends_on: List[str]) -> tuple[bool, List[str]]:
        """
        Check if all dependencies are completed.

        Args:
            depends_on: List of subtask IDs that must be completed

        Returns:
            (all_met: bool, missing: List[str])
        """
        missing = []

        for dep_id in depends_on:
            # Try to find the dependency in the current task first
            # Format can be "028-C" or "Task-028/028-C"
            if '/' in dep_id:
                task_id, subtask_id = dep_id.split('/', 1)
            else:
                # Assume same task, extract task ID from context
                # This is handled in scan_blocked_tasks
                continue

            status = self.get_subtask_status(task_id, subtask_id)

            if status != 'completed':
                missing.append(dep_id)

        return len(missing) == 0, missing

    def scan_blocked_tasks(self, target_task_id: Optional[str] = None):
        """Scan for blocked tasks and check if they can be unblocked."""
        self.blocked_tasks = []

        for task in self.registry_data['tasks']:
            task_id = task['id']

            # Filter by target task if specified
            if target_task_id and task_id != target_task_id:
                continue

            if 'subtasks' not in task:
                continue

            for subtask in task['subtasks']:
                subtask_id = subtask.get('id')
                status = subtask.get('status')

                if status != 'blocked':
                    continue

                # Extract blocker information
                blocker = subtask.get('blocker')

                if not blocker:
                    # Old format: string blocker
                    continue

                # New format: dict blocker
                if isinstance(blocker, dict):
                    depends_on = blocker.get('depends_on', [])

                    # Resolve relative subtask IDs
                    resolved_deps = []
                    for dep in depends_on:
                        if '/' not in dep:
                            # Same task, add task prefix
                            resolved_deps.append(f"{task_id}/{dep}")
                        else:
                            resolved_deps.append(dep)

                    # Check if dependencies are met
                    all_met, missing = self.check_dependencies_met(resolved_deps)

                    blocked_task = BlockedTask(task_id, subtask_id, blocker)
                    blocked_task.can_unblock = all_met
                    blocked_task.missing_deps = missing

                    self.blocked_tasks.append(blocked_task)

    def unblock_task(self, blocked_task: BlockedTask) -> bool:
        """Update registry.json to unblock a task."""
        if not blocked_task.can_unblock:
            return False

        # Find and update the task
        for task in self.registry_data['tasks']:
            if task['id'] != blocked_task.task_id:
                continue

            if 'subtasks' not in task:
                continue

            for subtask in task['subtasks']:
                if subtask['id'] != blocked_task.subtask_id:
                    continue

                # Update status
                subtask['status'] = 'ready_for_execution'

                # Add unblock timestamp
                if isinstance(subtask.get('blocker'), dict):
                    subtask['blocker']['unblocked_at'] = datetime.utcnow().isoformat() + 'Z'

                return True

        return False

    def save_registry(self) -> bool:
        """Save updated registry.json."""
        try:
            # Update last_updated timestamp
            self.registry_data['last_updated'] = datetime.utcnow().isoformat() + 'Z'

            with open(self.registry_path, 'w', encoding='utf-8') as f:
                json.dump(self.registry_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save registry.json: {e}")
            return False

    def run_check(self, target_task_id: Optional[str] = None):
        """Run the unblock check."""
        print("=" * 70)
        print("Blocked Task Dependency Checker")
        print("=" * 70)
        print()

        # Load registry
        if not self.load_registry():
            return False

        print(f"[OK] Loaded registry.json (v{self.registry_data.get('version', 'unknown')})")
        print(f"     Total tasks: {len(self.registry_data.get('tasks', []))}")

        if target_task_id:
            print(f"     Filtering by: {target_task_id}")
        print()

        # Scan for blocked tasks
        print("[INFO] Scanning for blocked subtasks...")
        self.scan_blocked_tasks(target_task_id)

        if not self.blocked_tasks:
            print("[OK] No blocked subtasks found.")
            return True

        print(f"[INFO] Found {len(self.blocked_tasks)} blocked subtask(s):")
        print()

        # Display results
        unblockable = [bt for bt in self.blocked_tasks if bt.can_unblock]
        still_blocked = [bt for bt in self.blocked_tasks if not bt.can_unblock]

        if unblockable:
            print(f"[READY TO UNBLOCK] {len(unblockable)} subtask(s) can be unblocked:")
            for bt in unblockable:
                print(bt)
                if isinstance(bt.blocker_info, dict):
                    action = bt.blocker_info.get('unblock_action', 'No action specified')
                    print(f"           Action: {action}")
            print()

        if still_blocked:
            print(f"[STILL BLOCKED] {len(still_blocked)} subtask(s) waiting for dependencies:")
            for bt in still_blocked:
                print(bt)
            print()

        # Auto-fix if requested
        if self.auto_fix and unblockable:
            print("[INFO] Auto-unblocking ready tasks...")
            unblocked_count = 0

            for bt in unblockable:
                if self.unblock_task(bt):
                    unblocked_count += 1
                    print(f"  [OK] Unblocked {bt.task_id}/{bt.subtask_id}")

            if unblocked_count > 0:
                if self.save_registry():
                    print(f"[OK] Updated registry.json with {unblocked_count} unblock(s)")
                else:
                    print("[ERROR] Failed to save registry.json")
        elif unblockable and not self.auto_fix:
            print("[RECOMMENDATION]: Run with --fix to auto-unblock ready tasks")

        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Check and unblock tasks whose dependencies are complete"
    )
    parser.add_argument(
        '--task',
        type=str,
        help='Check specific task (e.g., Task-028)'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Automatically unblock ready tasks'
    )

    args = parser.parse_args()

    # Determine .tasks directory
    script_path = Path(__file__).resolve()
    tasks_dir = script_path.parent.parent

    checker = UnblockChecker(tasks_dir, auto_fix=args.fix)
    success = checker.run_check(args.task)

    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
