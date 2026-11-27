"""Link feature tasks to Mermaid classes using the TDD's C# file plan."""

import argparse
import re
from pathlib import Path

from feature_state import CLASS_DIAGRAM_ROLES, StateError, load_state, update_state


CLASS_DECLARATION = re.compile(r'^\s*class\s+(\w+)')
FILE_ROW = re.compile(r'^\s*\|\s*(T\d+)\s*\|([^|]+)\|')
BASELINE = re.compile(r'^\s*<summary>(T\d+)\s+baseline\b', re.IGNORECASE)
SOURCE_FILE = re.compile(r'`(?:[^\x60]*\/)?(\w+)\.cs`')


def task_types(tdd):
    types = {}
    baseline = None
    for line in tdd.splitlines():
        heading = BASELINE.match(line)
        if heading:
            baseline = heading[1].upper()
        elif line.strip() == '</details>':
            baseline = None
        row = FILE_ROW.match(line)
        if row:
            task, files = row.groups()
        elif baseline and line.lstrip().startswith('- '):
            task, files = baseline, line
        else:
            continue
        types.setdefault(task, set()).update(SOURCE_FILE.findall(files))
    return types


def read_artifact(directory, relative_path):
    path = (directory / relative_path).resolve()
    if not path.is_relative_to(directory):
        raise StateError(f"artifact outside feature directory: {relative_path}")
    return path.read_text(encoding="utf-8")


def proposed_links(directory, state):
    artifacts = state["artifact_roles"]
    if "tdd" not in artifacts:
        raise StateError("feature has no registered TDD")
    types = task_types(read_artifact(directory, artifacts["tdd"]))
    classes = {}
    for role in sorted(CLASS_DIAGRAM_ROLES & artifacts.keys()):
        diagram = read_artifact(directory, artifacts[role])
        classes[role] = {
            match[1] for line in diagram.splitlines()
            if (match := CLASS_DECLARATION.match(line))
        }
    if not classes:
        raise StateError("feature has no registered class diagrams")

    changes = {}
    for task in state["tasks"]:
        task_id = task["id"]
        mapping = dict(task.get("diagram_nodes", {}))
        for role, nodes in classes.items():
            existing = mapping.get(role, [])
            added = sorted((nodes & types.get(task_id, set())) - set(existing))
            if added:
                print(f"{task_id}  {role}  {', '.join(added)}")
                mapping[role] = existing + added
        if mapping != task.get("diagram_nodes", {}):
            changes[task_id] = mapping
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature_directory", type=Path)
    parser.add_argument("--apply", action="store_true", help="save the proposed links")
    args = parser.parse_args()
    directory = args.feature_directory.resolve()
    try:
        state = load_state(directory)
        changes = proposed_links(directory, state)
        if not changes:
            print("No new exact matches.")
        elif args.apply:
            update_state(directory, "diagram-links", changes, state["revision"])
            print(f"Updated {len(changes)} tasks.")
        else:
            print(f"Dry run. Use --apply to update {len(changes)} tasks.")
    except (StateError, OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
