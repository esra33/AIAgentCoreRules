"""Explicit conservative import of legacy progress and document review sidecars."""
import hashlib
import json
from pathlib import Path
import re

from feature_state import StateError, atomic_write, empty_state, load_state, now, save_state, state_lock, validate_state


def _split(text, separator=","):
    result, start, depth, quote, escaped = [], 0, 0, None, False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
        elif quote and character == "\\":
            escaped = True
        elif quote:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character in "[{":
            depth += 1
        elif character in "]}":
            depth -= 1
        elif character == separator and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    if quote or depth:
        raise StateError("unbalanced legacy inline value")
    result.append(text[start:].strip())
    return result


def _strip_comment(text):
    """Drop a trailing ` # comment`, ignoring `#` inside quoted strings of inline values."""
    quote, escaped = None, False
    for index, character in enumerate(text):
        if escaped:
            escaped = False
        elif quote and character == "\\":
            escaped = True
        elif quote:
            if character == quote:
                quote = None
        elif character in "\"'" and (index == 0 or text[index - 1] in " \t[{,:"):
            quote = character
        elif character == "#" and index > 0 and text[index - 1].isspace():
            return text[:index].strip()
    return text.strip()


def _scalar(text):
    text = text.strip()
    if not text:
        return None
    if text[0] in "\"'":
        # Strip a trailing YAML comment only after the quoted string ends.
        match = re.match(r'''^("(?:\\.|[^"\\])*"|'(?:[^']|'')*')(?:\s*#.*)?$''', text)
        if not match:
            raise StateError("unsupported quoted legacy scalar")
        literal = match.group(1)
        return json.loads(literal) if literal[0] == '"' else literal[1:-1].replace("''", "'")
    text = _strip_comment(text)
    if text.startswith("[") and text.endswith("]"):
        return [_scalar(part) for part in _split(text[1:-1]) if part]
    if text.startswith("{") and text.endswith("}"):
        result = {}
        for part in _split(text[1:-1]):
            if not part:
                continue
            key, value = part.split(":", 1)
            result[key.strip().strip("\"'")] = _scalar(value)
        return result
    if text in {"null", "~"}:
        return None
    if text in {"true", "false"}:
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if text in {"|", ">", "|-", ">-"} or text.startswith(("&", "*", "!")):
        raise StateError("unsupported legacy YAML syntax; manual conversion required")
    return text


def parse_legacy_yaml(text):
    """Parse the template's deliberately small YAML subset; reject ambiguous structures."""
    stripped = text.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    rows = [(len(line) - len(line.lstrip()), line.strip()) for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]

    def parse(index, indentation):
        sequence = rows[index][1].startswith("- ")
        output = [] if sequence else {}
        while index < len(rows) and rows[index][0] == indentation:
            line = rows[index][1]
            if sequence:
                if not line.startswith("- "):
                    raise StateError("mixed mapping and list")
                value = line[2:].strip()
                if re.match(r"[\w]+:\s", value) and not value.startswith(("{", "[")):
                    # Multi-line list mappings (sources_of_truth / closed history).
                    key, raw = value.split(":", 1)
                    item = {key: _scalar(raw)}
                    index += 1
                    if index < len(rows) and rows[index][0] > indentation:
                        rest, index = parse(index, rows[index][0])
                        if not isinstance(rest, dict):
                            raise StateError("unsupported list mapping")
                        item.update(rest)
                    output.append(item)
                    continue
                output.append(_scalar(value))
            else:
                if ":" not in line:
                    raise StateError("expected legacy key/value")
                key, raw = line.split(":", 1)
                if key in output:
                    raise StateError(f"duplicate legacy key: {key}")
                raw = _strip_comment(raw) if not raw.strip().startswith(('"', "'")) else raw
                value = _scalar(raw)
                if value is None and index + 1 < len(rows) and rows[index + 1][0] > indentation:
                    value, index = parse(index + 1, rows[index + 1][0])
                    output[key] = value
                    continue
                output[key] = value
            index += 1
        if index < len(rows) and rows[index][0] > indentation:
            raise StateError("unsupported nested legacy value")
        return output, index

    if not rows:
        return {}
    value, index = parse(0, rows[0][0])
    if index != len(rows):
        raise StateError("inconsistent legacy indentation")
    return value


def _import_progress(directory, source):
    text = source.read_text()
    blocks = list(re.finditer(r"```(?:yaml|yml|json)\s*\n(.*?)\n```", text, re.S))
    if not blocks:
        raise StateError("no legacy state block found")
    state = empty_state(directory.name)
    known = set(state)
    header = parse_legacy_yaml(blocks[0].group(1))
    if not isinstance(header, dict) or "current_phase" not in header:
        raise StateError("legacy header missing current_phase")
    for key, value in header.items():
        if key in known and value is not None:
            state[key] = value
    if state["feature"] != directory.name:
        raise StateError("legacy feature identity differs from its directory name")
    for block in blocks[1:]:
        preceding = text[:block.start()]
        headings = re.findall(r"^## (.+)$", preceding, re.M)
        heading = headings[-1].lower() if headings else ""
        if heading not in {"checkpoint", "gates passed", "closed"}:
            continue
        value = parse_legacy_yaml(block.group(1))
        if heading == "checkpoint":
            state["checkpoint"] = value.get("checkpoint", value)
        elif heading == "gates passed":
            if "phase_handoff" not in value:
                raise StateError("unrecognized gate block")
            state["gates"].append(value["phase_handoff"])
        elif heading == "closed":
            state["closed"].extend(value.get("closed", []))
    state["legacy_notes"] = [text]
    _import_artifacts(directory, state)
    _import_tasks(directory, state)
    state["revision"] = 1
    state["migration"] = {"source": source.name, "sha256": hashlib.sha256(text.encode()).hexdigest(), "at": now()}
    return validate_state(state)


def _import_artifacts(directory, state):
    for role, suffix in (("tdd", "TDD"), ("gdd", "GDD"), ("task_list", "TaskList")):
        path = directory / f"{state['feature']}_{suffix}.md"
        if path.is_file():
            state["artifact_roles"][role] = path.name
    for role, names in (("framework_class_diagram", ("01_ClassStructure.mmd", "01_ClassDiagram.mmd", "01a_FrameworkClassDiagram.mmd")),
                        ("concrete_class_diagram", ("01b_ConcreteClassDiagram.mmd",)),
                        ("flow_diagram", ("02_MainFlow.mmd", "02_FlowDiagram.mmd")),
                        ("sequence_diagram", ("03_SequenceDiagram.mmd",)),
                        ("life_cycle_diagram", ("03_LifeCycleDiagram.mmd",))):
        candidates = [directory / "Diagrams" / name for name in names if (directory / "Diagrams" / name).is_file()]
        if len(candidates) == 1:
            state["artifact_roles"][role] = str(candidates[0].relative_to(directory))


def _import_tasks(directory, state):
    path = directory / f"{state['feature']}_TaskList.md"
    if path.is_file():
        for match in re.finditer(r"^\s*-\s*\{(id:.*?)\}\s*$", path.read_text(), re.M):
            item = _scalar("{" + match.group(1) + "}")
            if "id" in item and "status" in item:
                # Older task lists number tasks {id: 1}; the schema's ids are "T1".
                if isinstance(item["id"], int):
                    item["id"] = f"T{item['id']}"
                item["status"] = {"[ ]": "todo", "[~]": "partial", "[x]": "done"}.get(item["status"], item["status"])
                state["tasks"].append(item)
    # Do not choose between conflicting agent-maintained artifacts.
    path = directory / f"{state['feature']}_TDD.md"
    if path.is_file():
        for line in path.read_text().splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            ids = [cell for cell in cells if re.fullmatch(r"T\d+", cell)]
            statuses = [cell for cell in cells if cell in {"[ ]", "[~]", "[x]"}]
            if len(ids) == len(statuses) == 1:
                task = next((item for item in state["tasks"] if item["id"] == ids[0]), None)
                status = {"[ ]": "todo", "[~]": "partial", "[x]": "done"}[statuses[0]]
                if task is not None and task["status"] != status:
                    raise StateError(f"task {ids[0]} status conflicts between TDD and TaskList")
                if task is None:
                    task = {"id": ids[0], "title": cells[1] if len(cells) > 1 else ids[0]}
                    state["tasks"].append(task)
                task["status"] = status


def _import_reviews(directory):
    result = {"version": 1, "feature": directory.name, "threads": [], "migration_sources": []}
    for source in sorted(directory.rglob("*.review.json")):
        if "legacy-backup" in source.parts:
            continue
        data = json.loads(source.read_text())
        if not isinstance(data, dict) or data.get("version", 1) != 1:
            raise StateError(f"unsupported review schema in {source}")
        if not isinstance(data.get("threads"), list):
            raise StateError(f"invalid threads in {source}")
        result["migration_sources"].append(str(source.relative_to(directory)))
        for original in data["threads"]:
            thread = json.loads(json.dumps(original))
            if not isinstance(thread, dict) or not isinstance(thread.get("anchor"), dict) or not isinstance(thread.get("replies"), list):
                raise StateError(f"invalid review thread in {source}")
            if thread.get("status") not in {"open", "ready", "addressed", "resolved"}:
                raise StateError(f"invalid review thread status in {source}")
            path = (source.parent / thread["anchor"]["file"]).resolve()
            try:
                relative = str(path.relative_to(directory.resolve()))
            except ValueError as error:
                raise StateError(f"review target outside feature: {source}") from error
            thread["migration_origin"] = {"sidecar": str(source.relative_to(directory)), "id": thread["id"]}
            thread["id"] = "t" + str(len(result["threads"]) + 1)
            thread["anchor"]["file"] = relative
            result["threads"].append(thread)
    return result


def _source_snapshot(directory):
    paths = set(directory.glob("*_Progress.md")) | set(directory.rglob("*.review.json"))
    paths.update(directory.glob("*_TDD.md"))
    paths.update(directory.glob("*_TaskList.md"))
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if "legacy-backup" not in path.parts}


def migrate_feature(feature_dir, apply=False, expected_fingerprint=None):
    directory = Path(feature_dir).resolve()
    if (directory / "state.json").exists():
        load_state(directory)
        return {"feature": directory.name, "status": "already_migrated"}
    sources = list(directory.glob("*_Progress.md"))
    if not sources:
        return {"feature": directory.name, "status": "no_legacy_state"}
    if len(sources) != 1:
        return {"feature": directory.name, "status": "blocked", "errors": ["multiple Progress files"]}
    try:
        snapshot = _source_snapshot(directory)
        fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        if expected_fingerprint is not None and expected_fingerprint != fingerprint:
            raise StateError("migration sources changed since dry-run; inspect a new dry-run")
        state = _import_progress(directory, sources[0])
        reviews = _import_reviews(directory)
        if (directory / "review.json").exists():
            raise StateError("review.json already exists without state: inspect before migration")
    except (ValueError, KeyError, TypeError, OSError) as error:
        return {"feature": directory.name, "status": "blocked", "errors": [str(error)]}
    report = {"feature": directory.name, "status": "ready", "threads": len(reviews["threads"]),
              "gates": len(state["gates"]), "tasks": len(state["tasks"]),
              "fingerprint": fingerprint,
              "notes": ["Original Markdown retained in legacy_notes and a byte-for-byte backup."]}
    if apply:
        with state_lock(directory):
            if (directory / "state.json").exists():
                return {"feature": directory.name, "status": "already_migrated"}
            if snapshot != _source_snapshot(directory) or (directory / "review.json").exists():
                return {"feature": directory.name, "status": "blocked", "errors": ["migration sources changed during apply; rerun dry-run"]}
            backup = directory / "legacy-backup"
            backup_sources = sources + [directory / name for name in reviews["migration_sources"]]
            for source in backup_sources:
                destination = backup / source.relative_to(directory)
                if not destination.resolve().is_relative_to(directory):
                    return {"feature": directory.name, "status": "blocked", "errors": ["backup path escapes feature directory"]}
                if destination.exists() and destination.read_bytes() != source.read_bytes():
                    return {"feature": directory.name, "status": "blocked", "errors": ["existing legacy backup differs; inspect before migration"]}
            backup.mkdir(exist_ok=True)
            for source in backup_sources:
                destination = backup / source.relative_to(directory)
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    atomic_write(destination, source.read_bytes())
            atomic_write(directory / "review.json", json.dumps(reviews, indent=2) + "\n")
            save_state(directory, state)
            report["status"] = "migrated"
    return report
