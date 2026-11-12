"""Authoritative per-feature state and validated lifecycle commands (stdlib only)."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA_VERSION = 1
STATUSES = {"in_progress", "at_gate", "complete", "abandoned", "superseded", "on_hold"}
CLOSED = {"complete", "abandoned", "superseded", "on_hold"}
PHASES = {f"{number}_{name}" for number, name in enumerate(
    ["intake", "discovery", "design", "implementation", "unit_tests", "integration", "verification", "retrospective"], 1)}


class StateError(ValueError):
    """Invalid state, stale revision, or unsupported legacy data."""


def now():
    return datetime.now(timezone.utc).isoformat()


def empty_state(feature):
    return {"schema_version": 1, "revision": 0, "feature": feature,
            "current_phase": "1_intake", "status": "in_progress", "updated_at": now(),
            "artifacts": [], "sessions": [], "sources_of_truth": [], "pull_requests": {},
            "batches": {}, "step_status": {}, "tdd_sections": {}, "checkpoint": {},
            "gates": [], "closed": [], "tasks": [], "artifact_roles": {}, "phase_reports": {},
            "milestone_reports": [], "legacy_notes": []}


def validate_state(data):
    if not isinstance(data, dict):
        raise StateError("feature state must be an object")
    if type(data.get("schema_version")) is not int or data.get("schema_version") != SCHEMA_VERSION:
        raise StateError("unsupported schema_version")
    if type(data.get("revision")) is not int or data["revision"] < 0:
        raise StateError("revision must be a nonnegative integer")
    if not isinstance(data.get("feature"), str) or not data["feature"] or data["feature"] in {".", ".."} or any(character in data["feature"] for character in "/\\"):
        raise StateError("feature must be a nonempty string")
    if data.get("status") not in STATUSES or data.get("current_phase") not in PHASES:
        raise StateError("invalid status or current_phase")
    for key in ("artifacts", "sessions", "sources_of_truth", "gates", "closed", "tasks", "milestone_reports", "legacy_notes"):
        if not isinstance(data.get(key), list):
            raise StateError(f"{key} must be a list")
    for key in ("checkpoint", "pull_requests", "batches", "step_status", "tdd_sections", "artifact_roles", "phase_reports"):
        if not isinstance(data.get(key), dict):
            raise StateError(f"{key} must be an object")
    for key, values in (("step_status", {"in_progress", "done"}), ("tdd_sections", {"drafting", "approved"})):
        if any(value not in values for value in data[key].values()):
            raise StateError(f"invalid {key} value")
    if any(not isinstance(item, str) for item in data["sessions"]):
        raise StateError("sessions must contain folder names")
    for task in data["tasks"]:
        if not isinstance(task, dict) or not re.fullmatch(r"T\d+", task.get("id", "")) or task.get("status") not in {"todo", "partial", "done"}:
            raise StateError("tasks require T-ids and todo/partial/done statuses")
    if len({item["id"] for item in data["tasks"]}) != len(data["tasks"]):
        raise StateError("duplicate task IDs")
    for key, values in data["pull_requests"].items():
        if not re.fullmatch(r"V\d+", key) or not isinstance(values, list) or any(type(value) is not int or value < 1 for value in values):
            raise StateError("invalid PR phase or numbers")
    for batch in data["batches"].values():
        if not isinstance(batch, dict):
            raise StateError("batch must be an object")
        if "merged" in batch and (type(batch["merged"]) is not int or batch["merged"] < 0):
            raise StateError("batch merged must be a nonnegative integer")
    if any(not isinstance(gate, dict) or not gate.get("phase_completed") for gate in data["gates"]):
        raise StateError("gate requires phase_completed")
    for phase_key in data["phase_reports"]:
        if phase_key not in PHASES:
            raise StateError("phase_reports keys must be valid phase keys")
    for report in data["milestone_reports"]:
        if not isinstance(report, dict) or not isinstance(report.get("label"), str) or not report["label"] or not isinstance(report.get("path"), str):
            raise StateError("milestone_reports require a nonempty label and a path")
    if len({report["label"] for report in data["milestone_reports"]}) != len(data["milestone_reports"]):
        raise StateError("duplicate milestone_reports labels")
    for path in (list(data["artifact_roles"].values()) + list(data["phase_reports"].values())
                 + [report["path"] for report in data["milestone_reports"]] + data["artifacts"]):
        if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
            raise StateError("artifact paths must stay within the feature directory")
    return data


def load_state(feature_dir):
    directory = Path(feature_dir)
    raw = json.loads((directory / "state.json").read_text())
    if isinstance(raw, dict):
        raw.setdefault("milestone_reports", [])
    state = validate_state(raw)
    if state["feature"] != directory.name:
        raise StateError("feature identity must match its directory name")
    return state


def list_features(features_root, include_closed=False):
    result = []
    root = Path(features_root)
    if not root.is_dir():
        return result
    for directory in sorted(root.iterdir()):
        if not directory.is_dir():
            continue
        try:
            if (directory / "state.json").is_file():
                state = load_state(directory)
                legacy = False
            else:
                sources = list(directory.glob("*_Progress.md"))
                if not sources:
                    continue
                if len(sources) != 1:
                    raise StateError("multiple legacy progress files; migration requires review")
                from legacy_migration import parse_legacy_yaml
                match = re.search(r"```(?:yaml|yml|json)\s*\n(.*?)\n```", sources[0].read_text(), re.S)
                if not match:
                    raise StateError("legacy state header missing")
                state = parse_legacy_yaml(match.group(1))
                if not isinstance(state, dict) or state.get("status") not in STATUSES:
                    raise StateError("invalid legacy state header")
                legacy = True
        except (ValueError, OSError, TypeError) as error:
            result.append({"feature": directory.name, "status": "invalid", "error": str(error), "feature_dir": str(directory)})
            continue
        if include_closed or state["status"] not in CLOSED:
            summary = {key: state.get(key) for key in ("current_phase", "status", "updated_at", "revision")}
            result.append(dict(summary, feature=directory.name, feature_dir=str(directory),
                               checkpoint={key: state.get("checkpoint", {}).get(key, "") for key in ("next", "in_flight")},
                               migration_required=legacy, progress_file=str(directory / (directory.name + "_Progress.md"))))
    return sorted(result, key=lambda item: item.get("updated_at") or "", reverse=True)


@contextmanager
def state_lock(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".feature-state.lock").open("a+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_write(path, text):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb" if isinstance(text, bytes) else "w") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def render_progress(data):
    header_keys = ("feature", "current_phase", "status", "updated_at", "artifacts", "sessions", "sources_of_truth",
                   "pull_requests", "batches", "step_status", "tdd_sections")
    # JSON is valid YAML, and individual fields stay legible for human reviewers.
    header = "\n".join(key + ": " + json.dumps(data[key], ensure_ascii=False) for key in header_keys)
    text = ("<!-- AUTO-GENERATED: do not edit. Regenerate: feature_state.py render <feature-dir>. "
            "Manual edits are overwritten; state.json is authoritative. -->\n"
            f"# {data['feature']} — Progress\n\n```yaml\n{header}\n```\n\n## Checkpoint\n\n"
            "```json\n" + json.dumps({"checkpoint": data["checkpoint"]}, indent=2, ensure_ascii=False) + "\n```\n\n## Gates Passed\n")
    for gate in data["gates"]:
        text += "\n```json\n" + json.dumps({"phase_handoff": gate}, indent=2, ensure_ascii=False) + "\n```\n"
    if data["closed"]:
        text += "\n## Closed\n\n```json\n" + json.dumps({"closed": data["closed"]}, indent=2) + "\n```\n"
    for note in data["legacy_notes"]:
        text += "\n## Preserved legacy content\n\n" + note + "\n"
    return text


def save_state(directory, state):
    validate_state(state)
    atomic_write(Path(directory) / "state.json", json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    atomic_write(Path(directory) / (state["feature"] + "_Progress.md"), render_progress(state))


def create_state(feature_dir, feature=None):
    directory = Path(feature_dir)
    with state_lock(directory):
        if (directory / "state.json").exists():
            raise StateError("feature state already exists")
        if list(directory.glob("*_Progress.md")):
            raise StateError("legacy Progress exists: migrate it explicitly")
        state = empty_state(feature or directory.name)
        if state["feature"] != directory.name:
            raise StateError("feature identity must match its directory name")
        state["revision"] = 1
        save_state(directory, state)
        return state


def migrate_feature(feature_dir, apply=False, expected_fingerprint=None):
    from legacy_migration import migrate_feature as migrate
    return migrate(feature_dir, apply, expected_fingerprint)


def update_state(feature_dir, operation, payload, expected_revision):
    if not isinstance(payload, dict) or type(expected_revision) is not int:
        raise StateError("updates require an object payload and integer expected revision")
    with state_lock(feature_dir):
        state = load_state(feature_dir)
        if state["revision"] != expected_revision:
            raise StateError("stale revision: re-read feature state before updating")
        if state["status"] == "complete" and operation != "render":
            raise StateError("complete features are final")
        original = copy.deepcopy(state)
        if operation == "checkpoint":
            allowed = {"checkpoint", "step_status", "tdd_sections", "artifacts", "sources_of_truth", "sessions", "status"}
            if state["status"] in CLOSED or set(payload) - allowed or payload.get("status", state["status"]) not in {"in_progress", "at_gate"}:
                raise StateError("unsupported checkpoint fields/status")
            state.update(payload)
        elif operation == "gate":
            if not payload.get("gate_confirmed_by") or not payload.get("phase_completed"):
                raise StateError("gate requires phase_completed and engineer confirmation")
            if state["status"] in CLOSED:
                raise StateError("closed features cannot advance gates")
            phase_number = int(state["current_phase"].split("_", 1)[0])
            completed = re.match(r"^Phase (\d+)\b", str(payload["phase_completed"]))
            if not completed or int(completed.group(1)) != phase_number:
                raise StateError("gate must complete the feature's current phase")
            expected_next = next((phase for phase in PHASES if phase.startswith(str(phase_number + 1) + "_")), None)
            if payload.get("next_phase") != expected_next:
                raise StateError(f"gate next_phase must be {expected_next!r}")
            if any(re.match(r"^Phase " + str(phase_number) + r"\b", str(gate.get("phase_completed", ""))) for gate in state["gates"]):
                raise StateError("gate for this phase is already recorded")
            PHASES_REQUIRING_REPORT = {"2_discovery", "3_design", "4_implementation", "5_unit_tests", "6_integration", "7_verification"}
            if state["current_phase"] in PHASES_REQUIRING_REPORT and not state.get("phase_reports", {}).get(state["current_phase"]):
                raise StateError("phase report required before gate — run 'phase-report' first")
            gate = {key: value for key, value in payload.items() if key != "next_phase"}
            state["gates"].append(gate)
            state["current_phase"] = expected_next or state["current_phase"]
            state["status"] = "in_progress" if expected_next else "complete"
            state["checkpoint"] = {}
            state["step_status"] = {}
            state["tdd_sections"] = {}
        elif operation in {"close", "reopen"}:
            old = state["status"]
            status = payload.get("status") if operation == "close" else "in_progress"
            if operation == "close" and (status not in CLOSED or not payload.get("reason")):
                raise StateError("close requires a closing status and reason")
            if operation == "reopen" and old not in CLOSED - {"complete"}:
                raise StateError("only closed non-complete features can reopen")
            state["status"] = status
            state["closed"].append(dict(payload, at=now(), action=operation, status=status, was=old, phase=state["current_phase"]))
        elif operation == "phase-report":
            phase = payload.get("phase")
            path = payload.get("path")
            PHASES_REQUIRING_REPORT = {"2_discovery", "3_design", "4_implementation", "5_unit_tests", "6_integration", "7_verification"}
            if phase not in PHASES_REQUIRING_REPORT:
                raise StateError(f"phase-report requires one of {PHASES_REQUIRING_REPORT}")
            if phase != state["current_phase"]:
                raise StateError("phase report can only be registered for the current phase")
            if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
                raise StateError("artifact paths must stay within the feature directory")
            state["phase_reports"][phase] = path
            if path not in state["artifacts"]:
                state["artifacts"].append(path)
        elif operation == "milestone-report":
            label, path = payload.get("label"), payload.get("path")
            if not isinstance(label, str) or not label:
                raise StateError("milestone-report requires a nonempty label")
            if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
                raise StateError("artifact paths must stay within the feature directory")
            reports = [report for report in state["milestone_reports"] if report["label"] != label]
            reports.append({"label": label, "path": path})
            state["milestone_reports"] = reports
            if path not in state["artifacts"]:
                state["artifacts"].append(path)
        elif operation in {"pr", "batch", "artifact", "task"}:
            if operation == "pr":
                phase, number = payload["phase"], payload["number"]
                if not isinstance(phase, str) or not re.fullmatch(r"V\d+", phase) or type(number) is not int or number < 1:
                    raise StateError("PR requires V-phase and positive number")
                values = state["pull_requests"].setdefault(phase, [])
                if number not in values:
                    values.append(number)
            elif operation == "batch":
                state["batches"][payload["task_id"]] = payload["value"]
            elif operation == "artifact":
                state["artifact_roles"][payload["role"]] = payload["path"]
                if payload["path"] not in state["artifacts"]:
                    state["artifacts"].append(payload["path"])
            else:
                task = dict(payload)
                if not re.fullmatch(r"T\d+", task.get("id", "")) or task.get("status") not in {"todo", "partial", "done"}:
                    raise StateError("task requires T-id and todo/partial/done status")
                existing = next((item for item in state["tasks"] if item["id"] == task["id"]), {})
                state["tasks"] = [item for item in state["tasks"] if item["id"] != task["id"]] + [dict(existing, **task)]
        elif operation != "render":
            raise StateError("unknown operation")
        if state != original:
            state["revision"] += 1
            state["updated_at"] = now()
        save_state(feature_dir, state)
        return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list")
    listing.add_argument("--root", type=Path, required=True)
    listing.add_argument("--include-closed", action="store_true")
    command_help = {
        "task": "Add or update one task by id (merge, no delete). Payload: "
                '{"id": "T<n>", "title": "...", "status": "todo|partial|done"}.',
    }
    for command in ("get", "create", "checkpoint", "gate", "close", "reopen", "pr", "batch", "task", "artifact", "phase-report", "milestone-report", "render", "migrate"):
        item = sub.add_parser(command, help=command_help.get(command), description=command_help.get(command))
        item.add_argument("directory", type=Path, nargs="?" if command == "migrate" else None)
        if command == "get":
            item.add_argument("--section")
            item.add_argument("--include-legacy", action="store_true", help="include preserved legacy text in an unfiltered read")
        elif command == "migrate":
            item.add_argument("--root", type=Path)
            item.add_argument("--apply", action="store_true")
            item.add_argument("--expected-fingerprint", help="apply only if sources match a previous feature dry-run")
        elif command not in {"create"}:
            item.add_argument("--payload", type=Path)
            item.add_argument("--revision", type=int, required=True)
    args = parser.parse_args()
    try:
        if args.command == "list":
            result = list_features(args.root, args.include_closed)
        elif args.command == "get":
            result = load_state(args.directory)
            if args.section:
                result = result[args.section]
            elif not args.include_legacy:
                result = {key: value for key, value in result.items() if key != "legacy_notes"}
        elif args.command == "create":
            result = create_state(args.directory)
        elif args.command == "migrate":
            from legacy_migration import migrate_feature
            if bool(args.root) == bool(args.directory):
                raise StateError("provide a feature directory or --root, exclusively")
            directories = [args.directory] if args.directory else sorted(path for path in args.root.iterdir() if path.is_dir())
            if args.root and args.expected_fingerprint:
                raise StateError("--expected-fingerprint requires a single feature directory")
            result = [migrate_feature(path, args.apply, args.expected_fingerprint) for path in directories]
        else:
            payload = json.loads(args.payload.read_text()) if args.payload else {}
            result = update_state(args.directory, args.command, payload, args.revision)
            result = {key: value for key, value in result.items() if key != "legacy_notes"}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "migrate" and any(item.get("status") == "blocked" for item in result):
            return 1
    except (StateError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"error: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
