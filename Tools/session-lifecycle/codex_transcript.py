"""Exact Codex rollout selection and tool-event adaptation; never execute transcript text."""

import json
import os
import re
import shlex
import sys
from pathlib import Path

def support_module(name):
    """Load optional Codex support only when a Codex event actually needs it."""
    import importlib
    support_path = str(Path(__file__).resolve().parent.parent / "session-support")
    if support_path not in sys.path:
        sys.path.insert(0, support_path)
    return importlib.import_module(name)


def matches(path, session_id):
    """Use fork-aware metadata, so a copied parent's ID cannot capture its child."""
    return support_module("session_workflow_support").read_session_metadata(Path(path)).session_id == session_id


def records(path):
    if not path or not os.path.isfile(path):
        return
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # live rollouts may end with a partial record
            if isinstance(entry, dict):
                yield entry


def is_codex(path):
    return next((entry.get("type") == "session_meta" for entry in records(path)), False)


def locate(session_id, root=None):
    """Match the requested thread, not the newest file or another thread's copied metadata."""
    if not session_id:
        return None
    root = Path(root or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "sessions")
    candidates = []
    for path in root.rglob("*.jsonl"):
        if not path.stem.endswith("-" + session_id):
            continue
        try:
            if matches(path, session_id):
                candidates.append(str(path))
        except (OSError, ValueError):
            continue
    if len(candidates) > 1:
        raise RuntimeError("Multiple Codex rollouts match the requested thread; refusing ambiguous tracking")
    return candidates[0] if candidates else None


def batched_cat_commands(source):
    """Recognize a literal path array mapped to a single cat call without evaluating JS."""
    if not isinstance(source, str):
        return
    pattern = r'''(?P<paths>\[\s*"[^"\\\x00-\x1f]*"(?:\s*,\s*"[^"\\\x00-\x1f]*")*\s*\])
                  \.map\(async\s+(?P<param>[A-Za-z_]\w*)\s*=>\s*
                  text\(\(await\s+tools\.exec_command\(\{cmd\s*:\s*
                  `cat\s+'\$\{(?P=param)\}'`\}\)\)\.output\)\)'''
    for match in re.finditer(pattern, source, re.VERBOSE):
        paths = json.loads(match.group("paths"))
        for path in paths:
            if re.fullmatch(r"[\w./~-]+\.md", path):
                yield "cat " + shlex.quote(path)


def normalize(entry):
    """Adapt only observed tool calls to the existing trace reader's block shape."""
    if entry.get("type") != "response_item":
        return entry
    payload = entry.get("payload") or {}
    if payload.get("type") not in ("function_call", "custom_tool_call"):
        return entry
    raw = payload.get("arguments") or payload.get("input") or ""
    name = str(payload.get("name") or "").split(".")[-1]
    blocks = []
    if name in ("exec", "exec_command", "shell_command", "shell"):
        blocks = [{"type": "tool_use", "name": "Bash", "input": {"command": command}}
                  for command in support_module("session_monitor").extract_tool_commands(raw)]
        if name == "exec":
            blocks.extend({"type": "tool_use", "name": "Bash",
                           "input": {"command": command, "literal_batch": True}}
                          for command in batched_cat_commands(raw))
    elif name == "Read":
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            value = {}
        if isinstance(value, dict):
            blocks = [{"type": "tool_use", "name": "Read", "input": value}]
    return {"timestamp": entry.get("timestamp"), "message": {"content": blocks}}


def user_turns(path):
    # User-message events are emitted once; response_item can duplicate their content.
    return sum(entry.get("type") == "event_msg" and
               (entry.get("payload") or {}).get("type") == "user_message"
               for entry in records(path))
