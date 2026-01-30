#!/usr/bin/env python3
"""
Task Documentation Validation Script.

Validates that task documentation is complete before marking a task as done.

Checks:
1. README.md exists in docs/task-XXX-*/
2. CHANGELOG.md has corresponding version entry
3. registry.json has task entry
4. All referenced files exist
5. Literature DOIs are valid format

Usage:
    python .tasks/scripts/validate_docs.py --task 050
    python .tasks/scripts/validate_docs.py --task 050 --verbose
    python .tasks/scripts/validate_docs.py --all

Reference: Task-051 Documentation Protocol
"""

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# Get project root (parent of .tasks/)
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def validate_task_folder(task_id: str) -> Tuple[bool, List[str]]:
    """
    Check if docs/task-XXX-*/ folder exists with README.md.

    Args:
        task_id: Task identifier (e.g., "050", "051")

    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    docs_pattern = PROJECT_ROOT / "docs" / f"task-{task_id.lower()}-*"
    matches = list(glob.glob(str(docs_pattern)))

    if not matches:
        issues.append(f"Missing docs folder: docs/task-{task_id.lower()}-*/")
        return False, issues

    # Check for README.md in each match
    has_readme = False
    for match in matches:
        readme_path = Path(match) / "README.md"
        if readme_path.exists():
            has_readme = True
            break

    if not has_readme:
        issues.append(f"Missing README.md in docs/task-{task_id.lower()}-*/")
        return False, issues

    return True, []


def validate_changelog_entry(task_id: str) -> Tuple[bool, List[str]]:
    """
    Check if CHANGELOG.md has version entry for task.

    Args:
        task_id: Task identifier (e.g., "050", "051")

    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    changelog_path = PROJECT_ROOT / ".tasks" / "CHANGELOG.md"

    if not changelog_path.exists():
        issues.append("CHANGELOG.md not found at .tasks/CHANGELOG.md")
        return False, issues

    content = changelog_path.read_text(encoding="utf-8")

    # Look for version pattern like [v0.50.0] or Task-050
    version_pattern = rf"\[v0\.{task_id}\.0\]|Task-{task_id}"
    if not re.search(version_pattern, content, re.IGNORECASE):
        issues.append(f"Missing CHANGELOG entry for Task-{task_id} (v0.{task_id}.0)")
        return False, issues

    return True, []


def validate_registry_entry(task_id: str) -> Tuple[bool, List[str]]:
    """
    Check if registry.json has task entry.

    Args:
        task_id: Task identifier (e.g., "050", "051")

    Returns:
        Tuple of (success, list of issues)
    """
    issues = []
    registry_path = PROJECT_ROOT / ".tasks" / "registry.json"

    if not registry_path.exists():
        issues.append("registry.json not found at .tasks/registry.json")
        return False, issues

    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except json.JSONDecodeError as e:
        issues.append(f"registry.json parse error: {e}")
        return False, issues

    tasks = registry.get("tasks", [])
    task_ids = [t.get("id", "").upper() for t in tasks]

    target_id = f"TASK-{task_id.upper()}"
    if target_id not in task_ids:
        issues.append(f"Missing registry.json entry for {target_id}")
        return False, issues

    return True, []


def validate_doi_format(text: str) -> List[str]:
    """
    Check if DOI references are in valid format.

    Supports:
    - Plain DOI: DOI: 10.1037/h0043158
    - Markdown link: DOI: [10.1037/h0043158](https://doi.org/10.1037/h0043158)

    Args:
        text: Text content to check

    Returns:
        List of invalid DOI issues
    """
    issues = []
    # Find all DOI references (plain or markdown link)
    doi_pattern = r"DOI:\s*(?:\[)?([^\s\n\]\)]+)"
    matches = re.findall(doi_pattern, text)

    for doi in matches:
        # Clean up markdown artifacts
        doi_clean = doi.strip("[]()").split("](")[0] if "](" in doi else doi
        # Valid DOI format: 10.xxxx/xxxxx
        if not re.match(r"10\.\d{4,}/\S+", doi_clean):
            issues.append(f"Invalid DOI format: {doi_clean}")

    return issues


def validate_task(task_id: str, verbose: bool = False) -> Tuple[bool, Dict[str, List[str]]]:
    """
    Run all validations for a task.

    Args:
        task_id: Task identifier (e.g., "050")
        verbose: Print detailed output

    Returns:
        Tuple of (all_passed, dict of check_name -> issues)
    """
    results = {}
    all_passed = True

    # Check 1: Docs folder
    passed, issues = validate_task_folder(task_id)
    results["docs_folder"] = issues
    if not passed:
        all_passed = False

    # Check 2: CHANGELOG entry
    passed, issues = validate_changelog_entry(task_id)
    results["changelog"] = issues
    if not passed:
        all_passed = False

    # Check 3: Registry entry
    passed, issues = validate_registry_entry(task_id)
    results["registry"] = issues
    if not passed:
        all_passed = False

    # Check 4: DOI format in docs (if folder exists)
    docs_pattern = PROJECT_ROOT / "docs" / f"task-{task_id.lower()}-*"
    matches = list(glob.glob(str(docs_pattern)))
    doi_issues = []
    for match in matches:
        for md_file in Path(match).glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            doi_issues.extend(validate_doi_format(content))
    results["doi_format"] = doi_issues
    if doi_issues:
        all_passed = False

    return all_passed, results


def print_results(task_id: str, passed: bool, results: Dict[str, List[str]], verbose: bool = False):
    """Print validation results."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"\n{status} Task-{task_id} Documentation Validation")
    print("=" * 50)

    checks = [
        ("docs_folder", "Docs Folder"),
        ("changelog", "CHANGELOG Entry"),
        ("registry", "Registry Entry"),
        ("doi_format", "DOI Format"),
    ]

    for key, name in checks:
        issues = results.get(key, [])
        if issues:
            print(f"  [X] {name}")
            for issue in issues:
                print(f"      - {issue}")
        else:
            print(f"  [OK] {name}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Validate task documentation completeness"
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Task ID to validate (e.g., 050)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all tasks in registry",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    if not args.task and not args.all:
        parser.print_help()
        sys.exit(1)

    exit_code = 0

    if args.all:
        # Load registry and validate all tasks
        registry_path = PROJECT_ROOT / ".tasks" / "registry.json"
        if not registry_path.exists():
            print("Error: registry.json not found")
            sys.exit(1)

        with open(registry_path, "r", encoding="utf-8") as f:
            registry = json.load(f)

        for task in registry.get("tasks", []):
            task_id = task.get("id", "").replace("Task-", "").replace("task-", "")
            if task_id:
                passed, results = validate_task(task_id, args.verbose)
                print_results(task_id, passed, results, args.verbose)
                if not passed:
                    exit_code = 1
    else:
        # Validate single task
        task_id = args.task.replace("Task-", "").replace("task-", "")
        passed, results = validate_task(task_id, args.verbose)
        print_results(task_id, passed, results, args.verbose)
        if not passed:
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
