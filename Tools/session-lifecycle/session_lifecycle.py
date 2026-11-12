#!/usr/bin/env python3
"""Session lifecycle for Claude Code and Codex: start, note, compile, open.

One folder per session under the reports root (default: <project>/GitIgnoreReports/Sessions, where
<project> is the main checkout found by Tools/setup/project_root.py — never the shell's cwd):

    <YYYY-MM-DD_HHMM>_<lane>_<name>_<id8>/   (lane and name only once set)
        session.json   state (source of truth)
        metrics.md     rendered from session.json + token report + router trace
        retro.md       written by /end-session; its "## Applied" section tracks each proposal
        retro.html     rendered from retro.md (retro_page.py) — progress, per-proposal status, token charts
        tokens/        session-support per-session Markdown report
        typecheck.json typecheck baseline, last .cs edit, end-check blocks, cslint counts (typecheck hooks)

Subcommands:
    hook-start   SessionStart hook. Reads hook JSON on stdin, prints context for the agent.
    hook-end     SessionEnd hook. Compiles metrics even when /end-session was not run.
    hook-stop    Stop hook. Recompiles after a reply (throttled), for sessions that never exit.
    hook-prompt  UserPromptSubmit hook. After an idle gap past the prompt-cache TTL, notes the cost.
                 Warns once when the per-call context reaches 90% of the median session peak.
    hook-bash    PreToolUse hook on Bash. Reminds the agent to Read rule files it cat/sed/head/tails,
                 and suggests codeindex/usages for a grep over C# for a type or member name.
    hook-edit    PreToolUse hook on Edit|Write. First .cs edit of a session: typecheck baseline on the
                 untouched tree, result to the agent. Every .cs edit: last_cs_edit in typecheck.json.
    hook-lint    PostToolUse hook on Edit|Write. cslint on the edited .cs file's changed lines.
    hook-stop-check  Stop hook (sync). Blocks once when a .cs file changed after the last typecheck run.
    set          Record name, lane, work type and title.
    note         Log an inaccuracy or iteration.
    compile      Refresh token report, router trace and metrics.md.
    open         Open metrics.md and retro.html (rendered from retro.md) in the default viewer.
    retro        Render retro.html, list proposal statuses, or mark one proposal applied/skipped/pending.
                 --from <path> first files a retro written elsewhere (background sessions).
    path         Print the session folder.
    file         Copy files written elsewhere into a reports folder (file --to MetaReviews <paths>).
    features     List CreateFeature features that are not complete (/active-features).
    prune-empty  Delete session folders with nothing worth keeping (--dry-run to preview).

A session's folder is created on first record (set, note, compile, or after the first reply),
never at session start, so sessions opened and closed without work leave nothing behind.

Hooks must never break a session: hook-* subcommands always exit 0.
"""

import argparse
import collections
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import retro_page
import token_breakdown
import codex_transcript

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "setup"))
import project_root  # noqa: E402  shared with install.py
import project_config  # noqa: E402  shared documentation output paths
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "feature-state"))
from feature_state import load_state as load_feature_state

SCRIPT_PATH = os.path.abspath(__file__)
REPORTS_DIR = "GitIgnoreReports"
SESSION_SUPPORT = os.path.join(os.path.dirname(SCRIPT_PATH), "..", "session-support", "session-support")
LANES = ["small_task", "large_task", "bug_fix", "investigation", "feature", "other"]
# Work type is what the work is; lane is which process ran it. Kept separate for the meta-analysis.
WORK_TYPES = ["bug_fix", "small_feature", "large_feature", "feature", "question", "other"]
LANE_WORK_TYPE = {"small_task": "small_feature", "large_task": "large_feature", "bug_fix": "bug_fix",
                  "investigation": "question", "feature": "feature", "other": "other"}
RUNNABLE_TOOLS = ["typecheck.py", "codeindex.py", "usages.py", "unitysource.py", "cslint.py"]
# CreateFeature working folders, relative to the project root (Processes/CreateFeature/index.md
# working_folder). Override with SESSION_FEATURES_ROOT or --features-root.
DEFAULT_FEATURES_DIR = os.path.join("Assets", "GitIgnoreAssets", "Features")
REOPENABLE_STATUSES = ("abandoned", "superseded", "on_hold")   # set by /close-feature; /reopen-feature undoes them
FINISHED_STATUSES = ("complete",) + REOPENABLE_STATUSES        # hidden from /active-features and the start hint
CREATE_FEATURE_INDEX = os.path.join(os.path.dirname(SCRIPT_PATH), "..", "..", "Processes", "CreateFeature", "index.md")
# hook-stop recompiles at most this often; the Stop hook fires after every reply.
STOP_COMPILE_INTERVAL_SECONDS = 120
# Who logged a note. Entries written before sources existed have none and count as engineer.
NOTE_SOURCES = ["engineer", "agent", "retro"]
# Fresh-session offers (MR-20261016-02): every call re-reads the whole context, and after the
# prompt cache expires (1 h) the next call re-reads it uncached.
FRESH_SESSION_TOKENS = 30000000
IDLE_GAP_MINUTES = 60
IDLE_CONTEXT_TOKENS = 100000
TRANSCRIPT_TAIL_BYTES = 512 * 1024
# hook-prompt context-size warning (token_breakdown.context_warning_threshold): written on the first
# warning, removed once the context drops below the threshold, so it fires once per crossing.
CONTEXT_WARNING_MARKER = "context-warning.json"
TYPECHECK_STATE = "typecheck.json"
TYPECHECK_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(SCRIPT_PATH)), "unity-tools", "typecheck.py")
BASELINE_TIMEOUT_SECONDS = 25   # hook timeout is 30; a run of Assembly-CSharp + dependents takes ~3 s
LINT_MAX_ROWS = 15
CONTEXT_ACTIVE_WINDOW_SECONDS = 60 * 60   # = perf_view.ACTIVE_WINDOW_SECONDS, so the tab and the hook agree
# hook-bash (MR-20261016-05): a shell read of a rule file only reaches the router trace by inference.
# Only at a command position (start, or after ; && || |), so a quoted or heredoc mention is silent.
SHELL_RULE_READ = re.compile(r"(?:^|[;&|]|\$\()\s*(?:cat|sed|head|tail)\b[^|;&\n]*?(\S*\b(?:Rules|Processes|Systems|SystemPatterns|Skills)/\S*\.md)",
                             re.MULTILINE)
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\s*\2\s*$", re.MULTILINE | re.DOTALL)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
# hook-bash (audit 2026-11-10): a grep for a C# type or member name, which codeindex/usages answer.
GREP_PROGRAMS = ("grep", "egrep", "rg")
GREP_VALUE_OPTIONS = ("-A", "-B", "-C", "-m", "-f", "-g", "--glob", "-t", "--type", "--include", "--exclude")
CS_TARGET = re.compile(r"\.cs\b|(?:^|/)Assets(?:/|$)|^cs$|--type=cs|-tcs")
TYPE_DECL_PATTERN = re.compile(r"\b(class|interface|enum|struct|record)\s+([A-Z]\w*)")
# `file --to` targets (MR-20261016-06): folders next to the sessions root that background jobs
# cannot Write into directly.
FILE_TARGETS = ["MetaReviews"]
LANE_COMMAND = {"bug_fix": "/bug-fix <symptom>", "small_task": "/small-task <ask>",
                "large_task": "/large-task <ask>", "investigation": "/run-investigation-mode <question>", "feature": "/resume-work <FeatureName>",
                "other": "<prompt>"}


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def current_project_dir():
    """The checkout this session works in: CLAUDE_PROJECT_DIR (set for hooks), else the project
    this script was installed into (<project>/GitIgnoredExternals/...), else the checkout holding
    the cwd. Never the bare cwd or a hook payload's cwd: both follow the agent's `cd`."""
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return os.path.abspath(env_dir)
    start = project_root.host_of_layer(SCRIPT_PATH) or project_root.logical_cwd()
    return project_root.find_working_root(start) or os.getcwd()


def reports_root(args):
    """Explicit override, else <main checkout>/GitIgnoreReports/Sessions — shared by worktrees."""
    root = getattr(args, "reports_root", None) or os.environ.get("SESSION_REPORTS_ROOT")
    if not root:
        base = project_root.find_project_root(current_project_dir()) or current_project_dir()
        root = os.path.join(base, REPORTS_DIR, "Sessions")
    return os.path.abspath(root)


def check_not_nested(root):
    """A root inside another reports tree means the root was built from a moved cwd; creating a
    folder there would split the session in two."""
    if os.path.normpath(root).split(os.sep).count(REPORTS_DIR) > 1:
        raise RuntimeError("refusing to create a session folder under nested reports root " + root)


# ---------------------------------------------------------------- state

def find_folder(root, session_id):
    if not os.path.isdir(root):
        return None
    candidates = []
    for name in os.listdir(root):
        state_path = os.path.join(root, name, "session.json")
        if not os.path.isfile(state_path):
            continue
        if session_id:
            try:
                with open(state_path) as handle:
                    if json.load(handle).get("session_id") == session_id:
                        return os.path.join(root, name)
            except (OSError, ValueError):
                continue
        else:
            candidates.append((os.path.getmtime(state_path), os.path.join(root, name)))
    if candidates:
        return max(candidates)[1]
    return None


def load_state(folder):
    with open(os.path.join(folder, "session.json")) as handle:
        return json.load(handle)


def save_state(folder, state):
    with open(os.path.join(folder, "session.json"), "w") as handle:
        json.dump(state, handle, indent=2)


def locate_transcript(session_id, guess):
    """The guessed transcript path when it exists, else <session_id>.jsonl under any project
    folder. Claude Code files a transcript under the directory it was launched from, which is
    not the project root when a session starts in a subdirectory."""
    if guess and os.path.isfile(guess):
        if not codex_transcript.is_codex(guess) or (session_id and codex_transcript.matches(guess, session_id)):
            return guess
        guess = None
    if not session_id:
        return guess
    codex_path = codex_transcript.locate(session_id)
    if codex_path:
        return codex_path
    projects_root = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    if os.path.isdir(projects_root):
        for name in sorted(os.listdir(projects_root)):
            candidate = os.path.join(projects_root, name, session_id + ".jsonl")
            if os.path.isfile(candidate):
                return candidate
    return guess


def current_transcript(project_dir):
    """The running session: CLAUDE_CODE_SESSION_ID when set (exact, safe with concurrent
    sessions), else the newest Claude Code transcript for this project (a guess)."""
    codex_id = os.environ.get("CODEX_THREAD_ID")
    if codex_id:
        return codex_id, codex_transcript.locate(codex_id)
    encoded = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(project_dir))
    sessions_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects", encoded)
    env_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if env_id:
        return env_id, locate_transcript(env_id, os.path.join(sessions_dir, env_id + ".jsonl"))
    if not os.path.isdir(sessions_dir):
        return None, None
    names = [n for n in os.listdir(sessions_dir) if n.endswith(".jsonl")]
    if not names:
        return None, None
    newest = max(names, key=lambda n: os.path.getmtime(os.path.join(sessions_dir, n)))
    return newest[:-len(".jsonl")], os.path.join(sessions_dir, newest)


def user_turns(transcript_path):
    """Prompts the engineer actually typed (tool results and meta entries excluded)."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return 0
    if codex_transcript.is_codex(transcript_path):
        return codex_transcript.user_turns(transcript_path)
    count = 0
    with open(transcript_path, errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "user" or entry.get("isMeta"):
                continue
            content = (entry.get("message") or {}).get("content")
            if isinstance(content, str) and content.strip():
                count += 1
            elif isinstance(content, list) and any(isinstance(c, dict) and c.get("type") == "text" for c in content):
                count += 1
    return count


def ensure_folder(root, session_id, transcript_path=None, project_dir=None):
    """The session's folder, created on first use. Folders are only made when there is
    something to record (a set/note/compile, or a hook after a real exchange), never at
    session start, so sessions opened and closed without work leave nothing behind.
    Returns None when the session has no transcript to attach a folder to."""
    folder = find_folder(root, session_id)
    if folder:
        return folder
    check_not_nested(root)
    transcript_path = locate_transcript(session_id, transcript_path)
    if not session_id or not transcript_path or not os.path.isfile(transcript_path):
        return None
    state ={"session_id": session_id, "transcript_path": transcript_path,
             "agent": "codex" if codex_transcript.is_codex(transcript_path) else "claude",
             "project_dir": project_dir or current_project_dir(), "tracking_started_at": now_iso(),
             "started_at": transcript_started_at(transcript_path) or now_iso(),
             "name": None, "lane": None, "work_type": None, "title": None,
             "inaccuracies": [], "iterations": [], "end_session_run": False}
    folder = os.path.join(root, folder_name(state))
    os.makedirs(folder, exist_ok=True)
    save_state(folder, state)
    render(folder, state, state["project_dir"])
    return folder


def is_empty_folder(folder, state):
    """Nothing worth keeping: no lane, title, name or notes, no tokens, and no typed prompt."""
    tokens = state.get("tokens") or {}
    return (not state.get("lane") and not state.get("title") and not state.get("name")
            and not state.get("inaccuracies") and not state.get("iterations")
            and not (tokens.get("available") and tokens.get("total_tokens"))
            and not os.path.isfile(os.path.join(folder, "retro.md"))
            and user_turns(locate_transcript(state.get("session_id"), state.get("transcript_path"))) == 0)


def resolve(args):
    root = reports_root(args)
    session_id = getattr(args, "session_id", None) or current_transcript(current_project_dir())[0]
    if not session_id:
        sys.exit("No session id: use CODEX_THREAD_ID, CLAUDE_CODE_SESSION_ID or --session-id.")
    # Never fall back to another session's folder: with concurrent sessions that edits the wrong one.
    try:
        folder = ensure_folder(root, session_id, project_dir=current_project_dir())
    except RuntimeError as error:
        sys.exit(str(error))
    if folder is None:
        sys.exit("No transcript found for session %s, so there is nothing to record." % session_id)
    return folder, load_state(folder)


def slug(text, limit=40):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-")


def folder_name(state):
    started = datetime.datetime.fromisoformat(state["started_at"])
    parts = [started.strftime("%Y-%m-%d_%H%M")]
    if state.get("lane"):
        parts.append(state["lane"].replace("_", "-"))
    if state.get("name") and slug(state["name"]):
        parts.append(slug(state["name"]))
    parts.append(state["session_id"][:8])
    return "_".join(parts)


# ---------------------------------------------------------------- router trace

def transcript_started_at(transcript_path):
    """Local ISO time of the transcript's first timestamped entry, or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    with open(transcript_path) as handle:
        for line in handle:
            try:
                stamp = json.loads(line).get("timestamp")
            except ValueError:
                continue
            if stamp:
                moment = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                return moment.astimezone().isoformat(timespec="seconds")
    return None


def main_model(transcript_path):
    """The model behind most of the transcript's assistant messages ('claude-sonnet-5'), or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    counts = collections.Counter()
    with open(transcript_path, errors="replace") as handle:
        for line in handle:
            if '"model"' not in line:
                continue
            try:
                message = json.loads(line).get("message")
            except ValueError:
                continue
            model = message.get("model") if isinstance(message, dict) else None
            if model and model != "<synthetic>":
                counts[model] += 1
    return counts.most_common(1)[0][0] if counts else None


def import_roots(project_dir):
    """Directories imported by CLAUDE.md, plus their real paths (they are often symlinks)."""
    imports, roots = [], set()
    claude_md = os.path.join(project_dir, "CLAUDE.md")
    if os.path.isfile(claude_md):
        with open(claude_md) as handle:
            for line in handle:
                match = re.match(r"\s*@(\S+)", line)
                if match:
                    imports.append(match.group(1))
    agents = os.path.join(project_dir, "AGENTS.md")
    if os.path.isfile(agents):
        with open(agents) as handle:
            for rel in re.findall(r"`([^`\n]+/Rules/MetaRouter\.md)`", handle.read()):
                imports.append(rel)
                roots.add(os.path.abspath(os.path.join(project_dir, os.path.dirname(os.path.dirname(rel)))))
    for rel in imports:
        parts = rel.split("/")
        top = os.path.join(project_dir, *parts[:2]) if len(parts) > 2 else os.path.join(project_dir, parts[0])
        roots.add(os.path.abspath(top))
        roots.add(os.path.realpath(top))
    return imports, sorted(roots)


def display_path(path, project_dir, roots):
    real = os.path.realpath(path)
    for root in roots:
        if real.startswith(os.path.realpath(root) + os.sep):
            return os.path.relpath(real, os.path.dirname(os.path.realpath(root)))
    return os.path.relpath(path, project_dir) if path.startswith(project_dir) else path


def transcript_files(transcript_path, session_id):
    files = []
    if transcript_path and os.path.isfile(transcript_path):
        files.append((transcript_path, "main"))
        sub_dir = os.path.join(os.path.dirname(transcript_path), session_id)
        if os.path.isdir(sub_dir):
            for base, _dirs, names in os.walk(sub_dir):
                for name in sorted(names):
                    if name.endswith(".jsonl"):
                        files.append((os.path.join(base, name), "subagent"))
    return files


def router_trace(state, project_dir):
    imports, roots = import_roots(project_dir)
    loads, tools, seen = [], {}, {}
    md_in_command = re.compile(r"[\w./~-]+\.md")
    for path, via in transcript_files(state.get("transcript_path"), state["session_id"]):
        try:
            handle = open(path)
        except OSError:
            continue
        with handle:
            for line in handle:
                try:
                    entry = codex_transcript.normalize(json.loads(line))
                except ValueError:
                    continue
                content = (entry.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    tool_input = block.get("input") or {}
                    targets, bases = [], [project_dir]
                    if block.get("name") == "Read":
                        # Rules, processes and index entries are .md; a tool's source is not a load.
                        targets = [path for path in [tool_input.get("file_path", "")] if path.endswith(".md")]
                    elif block.get("name") == "Bash":
                        command = tool_input.get("command", "")
                        for tool, count in runnable_tool_calls(command).items():
                            tools[tool] = tools.get(tool, 0) + count
                        # Relative paths after `cd <dir>` resolve against that dir.
                        for cd_target in re.findall(r"\bcd\s+([^\s;&|]+)", command):
                            cd_target = os.path.expanduser(cd_target.strip("\"'"))
                            bases.insert(0, cd_target if os.path.isabs(cd_target)
                                         else os.path.join(project_dir, cd_target))
                        targets = md_in_command.findall(command)
                    for target in targets:
                        target = os.path.expanduser(target)
                        candidates = [target] if os.path.isabs(target) else [os.path.join(b, target) for b in bases]
                        absolute = next((c for c in candidates if os.path.isfile(c)), candidates[-1])
                        real = os.path.realpath(absolute)
                        root = next((r for r in roots if real.startswith(os.path.realpath(r) + os.sep)), None)
                        if root is None:
                            continue
                        # Documentation/ mirrors the rules for humans and is never a routing load.
                        if os.path.relpath(real, os.path.realpath(root)).split(os.sep)[0] == "Documentation":
                            continue
                        key = (real, via)
                        if key in seen:
                            # A file first seen in a shell command and Read later was loaded properly.
                            first = seen[key]
                            if block.get("name") == "Read" and first["via"].endswith("Bash"):
                                first["via"] += " → Read"
                            continue
                        seen[key] = {"file": display_path(absolute, project_dir, roots),
                                     "via": "%s · %s" % (via, block.get("name")),
                                     "at": local_clock(entry.get("timestamp", ""))}
                        loads.append(seen[key])
    return imports, loads, tools


def local_clock(stamp):
    """'HH:MM:SS' in local time for a transcript timestamp (stored in UTC), or '' if unparseable."""
    try:
        moment = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return ""
    return moment.astimezone().strftime("%H:%M:%S")


# ---------------------------------------------------------------- tokens

def load_session_support():
    """Import the vendored session-support CLI as a module (it is a script without .py)."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("session_support_cli", SESSION_SUPPORT)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def token_report(folder, state):
    """Token telemetry for exactly this session.

    The CLI's `report --scope current` means "newest session", which is wrong with concurrent
    sessions. The package's SessionMonitor accepts an explicit rollout file, so we drive the
    same report functions with this session's transcript instead of editing the vendored code.
    """
    transcript = state.get("transcript_path")
    if not os.path.isfile(SESSION_SUPPORT):
        return {"available": False, "reason": "session-support not found at %s" % SESSION_SUPPORT}
    if not transcript or not os.path.isfile(transcript):
        return {"available": False, "reason": "transcript not found"}
    try:
        from pathlib import Path
        cli = load_session_support()
        args = argparse.Namespace(project_config=Path(os.path.dirname(SESSION_SUPPORT)) / "project.example.json",
                                  agent=state.get("agent", "claude"), sessions_root=Path(os.path.dirname(transcript)), since=None)
        monitor = cli.load_monitor(args)
        monitor.explicit_rollout = Path(transcript)
        # Parser state contains transcript content; retain only the sanitized reports.
        with tempfile.TemporaryDirectory(prefix="session-report-cache-") as cache:
            monitor.state_root = Path(cache)
            session = cli.support_report(monitor, "current")["sessions"][0]
            tokens_dir = os.path.join(folder, "tokens")
            os.makedirs(tokens_dir, exist_ok=True)
            for report in monitor.generated_session_reports("current", False):
                with open(os.path.join(tokens_dir, report["filename"]), "w") as handle:
                    handle.write(report["content"])
    except Exception as error:  # telemetry is best-effort; never fail the compile
        return {"available": False, "reason": "report failed: %s" % error}
    if session.get("id") != state["session_id"]:
        return {"available": False, "reason": "report described session %s" % session.get("id")}
    return {"available": True, "total_tokens": session.get("total_tokens"),
            "turns": session.get("completed_turns"), "subagents": session.get("subagents"),
            "categories": session.get("categories"), "warning": session.get("warning")}


# ---------------------------------------------------------------- render

def count_by_source(items):
    """'3' when every note came from the engineer, else '3 (engineer 1 · agent 1 · retro 1)'."""
    counts = {source: 0 for source in NOTE_SOURCES}
    for item in items:
        counts[item.get("source", "engineer")] = counts.get(item.get("source", "engineer"), 0) + 1
    if counts["engineer"] == len(items):
        return str(len(items))
    return "%d (%s)" % (len(items), " · ".join("%s %d" % (s, n) for s, n in counts.items() if n))


def render(folder, state, project_dir):
    imports, loads, tools = router_trace(state, project_dir)
    tokens = state.get("tokens") or {}
    lines = [
        "# Session Metrics — %s" % (state.get("name") or state.get("title") or "untitled"),
        "",
        "| Field | Value |",
        "| --- | --- |",
        "| Session | `%s` |" % state["session_id"],
        "| Agent | %s |" % state.get("agent", "claude"),
        "| Model | %s |" % (state.get("model") or "–"),
        "| Name | %s |" % (state.get("name") or "–"),
        "| Title | %s |" % (state.get("title") or "–"),
        "| Lane | %s |" % (state.get("lane") or "**not set**"),
        "| Work type | %s |" % ((state["work_type"] + (" (from lane)" if state.get("work_type_source") == "lane" else ""))
                                if state.get("work_type") else "**not set**"),
    ]
    if state.get("feature"):
        lines += ["| Feature | %s |" % state["feature"],
                  "| Phase | %s |" % (phase_label(state["phase"]) if state.get("phase") else "**not set**")]
    lines += [
        "| Started | %s |" % state["started_at"],
        "| Tracking since | %s |" % state.get("tracking_started_at", state["started_at"]),
        "| Ended | %s |" % (state.get("ended_at") or "in progress"),
        "| /end-session run | %s |" % ("yes" if state.get("end_session_run") else "no"),
        "| Inaccuracies | %s |" % count_by_source(state["inaccuracies"]),
        "| Iterations | %s |" % count_by_source(state["iterations"]),
    ]
    if tokens.get("available"):
        lines += ["| Total tokens | %s |" % "{:,}".format(tokens["total_tokens"] or 0),
                  "| Turns | %s |" % tokens.get("turns"),
                  "| Subagents | %s |" % tokens.get("subagents"),
                  "| Health | %s |" % tokens.get("warning")]
    else:
        lines.append("| Tokens | unavailable (%s) |" % tokens.get("reason", "not compiled yet"))
    for kind in ("inaccuracies", "iterations"):
        lines += ["", "## %s" % kind.capitalize(), ""]
        lines += ["- `%s` %s%s" % (item["at"][11:19], item["text"],
                                   "" if item.get("source", "engineer") == "engineer" else " _(%s)_" % item["source"])
                  for item in state[kind]] or ["- none"]
    lines += ["", "## Lane changes", ""]
    lines += ["- `%s` %s → %s" % (item["at"][11:19], item["from"], item["to"])
              for item in state.get("lane_history", [])] or ["- none"]
    lines += ["", "## Work type changes", ""]
    lines += ["- `%s` %s → %s" % (item["at"][11:19], item["from"], item["to"])
              for item in state.get("work_type_history", [])] or ["- none"]
    lines += ["", "## Router trace", "", "Host instruction imports (declared, not proof of a read):", ""]
    lines += ["- `%s`" % item for item in imports] or ["- none"]
    lines += ["", "Loaded on demand, in order:", "", "| # | Time | File | Via (Bash rows are heuristic) |", "| ---: | --- | --- | --- |"]
    lines += ["| %d | %s | `%s` | %s |" % (i + 1, item["at"], item["file"], item["via"]) for i, item in enumerate(loads)]
    if not loads:
        lines.append("| – | – | none | – |")
    lines += ["", "## Runnable tools", ""]
    lines += ["- `%s` × %d" % (tool, count) for tool, count in sorted(tools.items())] or ["- none run"]
    lines += typecheck_lines(state)
    lines += breakdown_lines(state)
    with open(os.path.join(folder, "metrics.md"), "w") as handle:
        handle.write("\n".join(lines) + "\n")


def session_comparison(folder, state):
    """[{id, lane, tokens, calls, current}] for every session under the reports root with tokens,
    totals de-duplicated per model call (token_breakdown.session_total) so sessions compare fairly."""
    root = os.path.dirname(folder)
    sessions = []
    for name in sorted(os.listdir(root)):
        try:
            other = state if os.path.join(root, name) == folder else load_state(os.path.join(root, name))
        except (OSError, ValueError):
            continue
        transcript = locate_transcript(other.get("session_id"), other.get("transcript_path"))
        total = token_breakdown.session_total(transcript, other.get("session_id"))
        if total and total[0]:
            sessions.append({"id": other["session_id"][:8], "lane": other.get("lane"), "tokens": total[0],
                             "calls": total[1], "current": other is state})
    return sessions


def breakdown_lines(state):
    """metrics.md section: where the tokens went and what saved tokens (estimates)."""
    breakdown = state.get("breakdown") or {}
    if not breakdown.get("total"):
        return ["", "## Token breakdown (estimated)", "",
                "- unavailable (%s)" % (breakdown.get("error") or "not compiled yet")]
    total = breakdown["total"]
    lines = ["", "## Token breakdown (estimated)", "",
             "Shares of the total tokens above, across %d model calls. A tool result costs its size × every "
             "later call that re-reads it." % breakdown["calls"], "",
             "| Category | Standardized | Tokens | Share |", "| --- | --- | ---: | ---: |"]
    for name, tokens in breakdown["categories"].items():
        lines.append("| %s | %s | %s | %.1f%% |" % (name, "yes" if name in token_breakdown.STANDARDIZED else "–",
                                                   "{:,}".format(tokens), 100.0 * tokens / total))
    lines.append("| **Standardized operations** | | **%s** | **%.1f%%** |"
                 % ("{:,}".format(breakdown["standardized"]), 100.0 * breakdown["standardized"] / total))
    lines += ["", "| Saving mechanism | Uses | Tokens saved | Round-trips saved |", "| --- | ---: | ---: | ---: |"]
    for name, saving in sorted(breakdown["savings"].items(), key=lambda item: -item[1]["tokens"]):
        lines.append("| %s | %d | %s | %d |" % (name, saving["count"], "{:,}".format(saving["tokens"]),
                                                saving["round_trips"]))
    doc_review = breakdown.get("doc_review") or {}
    measured = doc_review.get("miro_confluence") or {}
    if doc_review.get("count") or measured.get("count"):
        lines += ["", "Doc review preview: %d call%s, ~%s tokens; the same operations through Miro/Confluence "
                  "≈ %s tokens and %d round-trips. Miro/Confluence MCP calls this session: %d, ~%s tokens."
                  % (doc_review.get("count", 0), "" if doc_review.get("count") == 1 else "s",
                     "{:,}".format(doc_review.get("tokens", 0)), "{:,}".format(doc_review.get("equivalent", 0)),
                     doc_review.get("round_trips", 0), measured.get("count", 0),
                     "{:,}".format(measured.get("tokens", 0)))]
    return lines + missed_lines(breakdown.get("missed") or {})


def missed_lines(missed):
    """metrics.md subsection: lookups done by hand that code-graph, codeindex or usages answers."""
    if not any(entry["count"] for entry in missed.values()):
        return ["", "Missed index opportunities (code-graph / codeindex / usages): none."]
    lines = ["", "### Missed index opportunities (estimated)", "",
             "Lookups done by hand that code-graph, codeindex or usages answers. Tokens lost: each result minus "
             "an index call (~%d tokens) × later calls." % token_breakdown.INDEX_CALL_TOKENS, "",
             "| Kind | Count | Tokens lost | Round-trips lost |", "| --- | ---: | ---: | ---: |"]
    for kind, entry in missed.items():
        lines.append("| %s | %d | %s | %d |" % (kind, entry["count"], "{:,}".format(entry["tokens"]),
                                                entry["round_trips"]))
    for kind, entry in missed.items():
        if entry["examples"]:
            lines += ["", "%s:" % kind] + ["- %s" % example for example in entry["examples"]]
    return lines


def compile_folder(folder, state, project_dir):
    # The hook payload's path can be wrong for a session launched from a subdirectory.
    state["transcript_path"] = locate_transcript(state["session_id"], state.get("transcript_path"))
    # A resumed session's transcript may predate tracking; report the real start.
    state["started_at"] = transcript_started_at(state.get("transcript_path")) or state["started_at"]
    state["agent"] = "codex" if codex_transcript.is_codex(state.get("transcript_path")) else "claude"
    state["model"] = main_model(state.get("transcript_path"))
    state["tokens"] = token_report(folder, state)
    state["typecheck"] = dict(load_typecheck(folder),
                              runs=typecheck_runs(state.get("transcript_path"), state["session_id"]))
    try:   # estimates for the retro charts; best-effort like the token report
        if state["agent"] == "codex":
            raise ValueError("Detailed cost attribution and comparison are not yet supported for Codex")
        state["breakdown"] = token_breakdown.analyse(state.get("transcript_path"), state["session_id"],
                                                     import_roots(project_dir)[1], type_grep_suggestions)
        state["comparison"] = session_comparison(folder, state)
    except Exception as error:
        state["breakdown"] = {"error": str(error)}
        state.pop("comparison", None)
    state["compiled_at"] = now_iso()
    save_state(folder, state)
    render(folder, state, project_dir)


# ---------------------------------------------------------------- commands

def read_hook_input():
    try:
        return json.load(sys.stdin)
    except ValueError:
        return {}


def hook_project_dir(hook):
    """Hooks run in the project dir. Not the payload's cwd: it follows the agent's last `cd`, and a
    root built from it nested duplicate session folders (MR-20261009-01). hooks.log records it."""
    project_dir = current_project_dir()
    os.chdir(project_dir)
    return project_dir


def hook_log(args, event, hook, outcome):
    """One line per hook run, so a hook that fires but finds nothing leaves evidence."""
    try:
        root = reports_root(args)
        os.makedirs(root, exist_ok=True)
        with open(os.path.join(root, "hooks.log"), "a") as handle:
            handle.write("%s %s session=%s source=%s reason=%s cwd=%s -> %s\n" % (
                now_iso(), event, (hook.get("session_id") or "?")[:8], hook.get("source"),
                hook.get("reason"), hook.get("cwd"), outcome))
    except Exception:
        pass


def cmd_hook_start(args):
    try:
        hook = {} if sys.stdin.isatty() else read_hook_input()
        hook_project_dir(hook)
        inferred_id, inferred_transcript = current_transcript(current_project_dir())
        session_id = hook.get("session_id") or inferred_id or "unknown"
        hook.setdefault("transcript_path", inferred_transcript)
        root = reports_root(args)
        # No folder yet: it is created on the first set/note/compile or after the first real
        # exchange (hook-stop), so sessions opened and closed without work leave nothing behind.
        folder = find_folder(root, session_id)
        resumed = folder is not None
        state = load_state(folder) if folder else {}
        print("\n".join([
            "## Session tracking (%s)" % ("resumed" if resumed else "started"),
            "- session_id: %s" % session_id,
            "- folder: %s" % (folder or "created on first record (set, note, or after the first reply)"),
            "- lifecycle script: %s" % SCRIPT_PATH,
            "- name: %s" % (state.get("name") or "not set"),
            "- lane: %s" % (state.get("lane") or "not set"),
            "- work type: %s" % (state.get("work_type") or "not set"),
            "",
            "Required: once the MetaRouter mode is classified, record it and the work type:",
            "  python3 \"%s\" set --session-id %s --lane <%s> --work-type <%s> --title \"<short title>\""
            % (SCRIPT_PATH, session_id, "|".join(LANES), "|".join(WORK_TYPES)),
            "If the engineer named the session (/start-session <name>), also pass --name \"<name>\".",
            "The engineer logs direction changes with /iteration.",
            "When you retract a claim or the engineer rejects your approach, log it yourself at once:",
            "  python3 \"%s\" note --session-id %s --kind inaccuracy --source agent \"<what was wrong>\""
            % (SCRIPT_PATH, session_id),
            "Close the session with /end-session (metrics + retrospective).",
        ] + feature_hint(current_project_dir(), state)))
        hook_log(args, "start", hook, ("resumed " + folder) if resumed else "folder deferred until there is something to record")
    except Exception as error:  # a hook must never block the session
        print("Session tracking failed to start: %s" % error)
        hook_log(args, "start", locals().get("hook") or {}, "ERROR %s" % error)
    return 0


def cmd_hook_end(args):
    hook = {}
    try:
        hook = read_hook_input()
        hook_project_dir(hook)
        root = reports_root(args)
        session_id = hook.get("session_id")
        folder = find_folder(root, session_id)
        if folder and is_empty_folder(folder, load_state(folder)):
            shutil.rmtree(folder)
            hook_log(args, "end", hook, "removed empty folder " + folder)
            return 0
        if not folder and user_turns(locate_transcript(session_id, hook.get("transcript_path"))):
            folder = ensure_folder(root, session_id, hook.get("transcript_path"), current_project_dir())
        if folder:
            state = load_state(folder)
            state["ended_at"] = now_iso()   # latest exit; a resumed session ends again
            state["end_reason"] = hook.get("reason")
            compile_folder(folder, state, state.get("project_dir") or current_project_dir())
            hook_log(args, "end", hook, "compiled " + folder)
        else:
            hook_log(args, "end", hook, "nothing to save, no folder")
    except Exception as error:
        hook_log(args, "end", hook, "ERROR %s" % error)
    return 0


# ---------------------------------------------------------------- features

def phase_label(key):
    """'2_discovery' -> 'Phase 2 — Discovery'."""
    number, _, name = (key or "").partition("_")
    return "Phase %s — %s" % (number, name.replace("_", " ").title()) if name else (key or "unknown phase")


def phase_models():
    """phase key -> recommended_model, read from CreateFeature/index.md."""
    models, current = {}, None
    try:
        with open(CREATE_FEATURE_INDEX) as handle:
            for line in handle:
                key = re.match(r"^  (\d+_\w+):\s*$", line)
                if key:
                    current = key.group(1)
                model = re.match(r"^\s+recommended_model:\s*(\w+)", line)
                if model and current:
                    models[current] = model.group(1)
    except OSError:
        pass
    return models


def yaml_value(text, field):
    match = re.search(r"^\s*%s:\s*\"([^\"]*)\"" % field, text, re.MULTILINE)
    return match.group(1) if match else ""


def active_features(project_dir, features_root=None):
    """Every CreateFeature progress file that is neither complete nor closed, newest first."""
    return scan_features(project_dir, features_root, lambda status: status not in FINISHED_STATUSES)


def closed_features(project_dir, features_root=None):
    """Features closed by /close-feature that /reopen-feature can still reopen, newest first."""
    return scan_features(project_dir, features_root, lambda status: status in REOPENABLE_STATUSES)


def scan_features(project_dir, features_root, keep):
    root = project_config.resolve_path(project_dir, "features", override=features_root)
    models = phase_models()
    found = []
    if not os.path.isdir(root):
        return found
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name, "%s_Progress.md" % name)
        state_path = os.path.join(root, name, "state.json")
        if not os.path.isfile(path) and not os.path.isfile(state_path):
            continue
        state = load_feature_state(Path(state_path).parent) if os.path.isfile(state_path) else None
        text = ""
        if state is None:
            with open(path, errors="replace") as handle:
                text = handle.read()
        value = lambda key: state.get(key, "") if state is not None else yaml_value(text, key)
        status = value("status") or "unknown"
        if not keep(status):
            continue
        phase = value("current_phase")
        checkpoint = state.get("checkpoint", {}) if state is not None else {}
        found.append({"feature": value("feature") or name, "phase": phase, "phase_label": phase_label(phase),
                      "status": status, "updated_at": value("updated_at"),
                      "in_flight": checkpoint.get("in_flight", value("in_flight")),
                      "next": checkpoint.get("next", value("next")),
                      "model": models.get(phase), "progress_file": path,
                      "state_file": state_path, "migration_required": state is None})
    return sorted(found, key=lambda f: f["updated_at"], reverse=True)


def resume_command(feature):
    model = " --model %s" % feature["model"] if feature.get("model") else ""
    return "claude%s \"/resume-work %s\"" % (model, feature["feature"])


def cmd_features(args):
    if args.closed:
        features = closed_features(current_project_dir(), args.features_root)
        if args.json:
            print(json.dumps(features, indent=2))
            return 0
        if not features:
            print("No closed features to reopen.")
            return 0
        print("Closed features (%d):" % len(features))
        for f in features:
            print("- %s · %s · %s · updated %s" % (f["feature"], f["phase_label"], f["status"], f["updated_at"][:10] or "?"))
            print("  reopen: /reopen-feature %s" % f["feature"])
        return 0
    features = active_features(current_project_dir(), args.features_root)
    if args.json:
        print(json.dumps([dict(f, resume=resume_command(f)) for f in features], indent=2))
        return 0
    if not features:
        print("No features in progress.")
        return 0
    print("In-progress features (%d):" % len(features))
    for f in features:
        print("- %s · %s · %s · updated %s" % (f["feature"], f["phase_label"], f["status"], f["updated_at"][:10] or "?"))
        if f["in_flight"]:
            print("  in flight: %s" % f["in_flight"])
        if f["next"]:
            print("  next: %s" % f["next"])
        if f.get("migration_required"):
            print("  migration required: run the feature-state migrate command explicitly")
        print("  resume: %s" % resume_command(f))
    return 0


def feature_hint(project_dir, state):
    """Start-context lines naming in-progress features, so a new session can offer /resume-work."""
    if state.get("feature"):
        return []   # this session already belongs to a feature
    try:
        features = active_features(project_dir)
    except Exception:
        return []
    if not features:
        return []
    lines = ["", "In-progress features (one session per phase; /active-features for details):"]
    lines += ["  - %s · %s · next: %s" % (f["feature"], f["phase_label"], (f["next"] or "see progress file")[:120])
              for f in features[:5]]
    lines.append("If the engineer's first message is not about something else, offer /resume-work <FeatureName>.")
    return lines


def cmd_prune_empty(args):
    """Delete session folders with nothing worth keeping (see is_empty_folder)."""
    root = reports_root(args)
    if not os.path.isdir(root):
        print("No sessions folder at %s." % root)
        return 0
    removed = kept = 0
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if not os.path.isfile(os.path.join(folder, "session.json")):
            continue
        try:
            state = load_state(folder)
        except (OSError, ValueError):
            continue
        if is_empty_folder(folder, state):
            removed += 1
            print("%s %s" % ("would remove" if args.dry_run else "removed", name))
            if not args.dry_run:
                shutil.rmtree(folder)
        else:
            kept += 1
    print("%d empty folder(s) %s, %d kept." % (removed, "found" if args.dry_run else "removed", kept))
    return 0


def cmd_hook_stop(args):
    """Stop hook: recompile after a reply, so metrics exist even for a session that never
    exits (the app marks idle sessions completed without firing SessionEnd). Never marks
    the session ended. Throttled; a compile takes well under a second."""
    hook = {}
    try:
        hook = read_hook_input()
        hook_project_dir(hook)
        root = reports_root(args)
        folder = find_folder(root, hook.get("session_id"))
        if not folder:
            # First reply of a session: now there is something to record.
            if not user_turns(locate_transcript(hook.get("session_id"), hook.get("transcript_path"))):
                return 0
            folder = ensure_folder(root, hook.get("session_id"), hook.get("transcript_path"), current_project_dir())
            if not folder:
                return 0
        state = load_state(folder)
        last = state.get("compiled_at")
        if last:
            age = datetime.datetime.now().astimezone() - datetime.datetime.fromisoformat(last)
            if age.total_seconds() < STOP_COMPILE_INTERVAL_SECONDS:
                return 0
        compile_folder(folder, state, state.get("project_dir") or current_project_dir())
    except Exception as error:
        hook_log(args, "stop", hook, "ERROR %s" % error)   # successes are not logged: one per reply is noise
    finally:
        if codex_transcript.is_codex(hook.get("transcript_path")):
            print("{}")  # Codex Stop hooks consume a JSON object, not context text.
    return 0


def offer_fresh_session(state, lane):
    """stderr line for the agent when a large session switches lane (stdout stays the folder path)."""
    total = (state.get("tokens") or {}).get("total_tokens") or 0
    if total >= FRESH_SESSION_TOKENS:
        print("Fresh-session offer: this session is at %.1fM tokens and every call re-reads it. Offer the "
              "engineer to start the %s work fresh: /new-session \"%s\"" % (total / 1e6, lane, LANE_COMMAND[lane]),
              file=sys.stderr)


def last_reply(transcript_path):
    """(local datetime, context tokens) of the transcript's last model call, or None. Reads only the tail."""
    try:
        with open(transcript_path, "rb") as handle:
            handle.seek(max(os.path.getsize(transcript_path) - TRANSCRIPT_TAIL_BYTES, 0))
            lines = handle.read().decode("utf-8", errors="replace").splitlines()
    except (OSError, TypeError):
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        usage = (entry.get("message") or {}).get("usage")
        if entry.get("type") != "assistant" or not usage or not entry.get("timestamp"):
            continue
        context = sum(usage.get(key) or 0 for key in
                      ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        moment = datetime.datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")).astimezone()
        return moment, context
    return None


def reference_peaks(root, exclude):
    """breakdown.peak_context of every finished session folder under root except `exclude`. Still-running
    sessions (perf_view's active rule: no ended_at, session.json written within the hour) have partial peaks."""
    peaks = []
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if folder == exclude:
            continue
        try:
            state = load_state(folder)
            running = not state.get("ended_at") and \
                time.time() - os.path.getmtime(os.path.join(folder, "session.json")) < CONTEXT_ACTIVE_WINDOW_SECONDS
            if not running:
                peaks.append((state.get("breakdown") or {}).get("peak_context") or 0)
        except (OSError, ValueError, AttributeError):
            continue
    return peaks


def context_warning(args, hook, context):
    """(engineer message, agent note) once per crossing of the context-size threshold, else None.
    The marker in the session folder re-arms when the context drops back below it (compact / clear)."""
    root = reports_root(args)
    folder = find_folder(root, hook.get("session_id"))
    if not folder:
        return None
    marker = os.path.join(folder, CONTEXT_WARNING_MARKER)
    peaks = reference_peaks(root, folder)
    threshold = token_breakdown.context_warning_threshold(peaks)
    if threshold is None or context < threshold:
        if os.path.isfile(marker):
            os.remove(marker)
        return None
    if os.path.isfile(marker):
        return None
    with open(marker, "w") as handle:
        json.dump({"at": now_iso(), "context": context, "threshold": threshold}, handle)
    median = threshold / token_breakdown.CONTEXT_WARNING_SHARE
    hook_log(args, "prompt", hook, "context %dk >= threshold %dk" % (context // 1000, threshold // 1000))
    message = ("Context-size warning: this session re-sends ~%dk tokens on every call, %d%% of the %dk median "
               "peak across %d sessions. At the next task boundary: /compact <what to keep>, or a fresh "
               "session with a handoff." % (context // 1000, round(100 * context / median), median // 1000,
                                            len([peak for peak in peaks if peak])))
    note = (message + " Finish the current step first, then offer the engineer that reset in one line; do "
            "not reset mid-step.")
    return message, note


def cmd_hook_prompt(args):
    """UserPromptSubmit hook: after an idle gap long enough for the prompt cache to expire, tell the
    agent what the next call costs, so new work can be offered a fresh session; and once the context
    reaches the context-size threshold, warn both the engineer (systemMessage) and the agent. Silent otherwise."""
    hook = {}
    try:
        hook = read_hook_input()
        reply = last_reply(locate_transcript(hook.get("session_id"), hook.get("transcript_path")))
        if not reply:
            return 0
        moment, context = reply
        notes, messages = [], []
        idle = datetime.datetime.now().astimezone() - moment
        if idle.total_seconds() >= IDLE_GAP_MINUTES * 60 and context >= IDLE_CONTEXT_TOKENS:
            hours, minutes = divmod(int(idle.total_seconds() // 60), 60)
            notes.append("Idle-gap note: %dh %02dm since the last reply, so the prompt cache has expired and the next "
                         "call re-reads ~%dk tokens of context uncached. If this prompt starts new work rather than "
                         "continuing the current task, offer a fresh session first: /new-session \"<prompt>\"."
                         % (hours, minutes, context // 1000))
            hook_log(args, "prompt", hook, "idle %dh%02dm, context %dk" % (hours, minutes, context // 1000))
        warning = context_warning(args, hook, context)
        if warning:
            messages.append(warning[0])
            notes.append(warning[1])
        if notes:
            output = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "\n".join(notes)}}
            if messages:
                output["systemMessage"] = "\n".join(messages)   # shown to the engineer, not added to context
            print(json.dumps(output))
    except Exception as error:   # a hook must never block a prompt
        hook_log(args, "prompt", hook, "ERROR %s" % error)
    return 0


def _strip_prose(command):
    """The command without heredoc bodies or quoted prose."""
    # A quoted single word is a path argument and stays; quoted text with spaces is prose.
    return QUOTED.sub(lambda m: m.group(0)[1:-1] if not re.search(r"\s", m.group(0)) else "''",
                      HEREDOC.sub("", command))


def shell_rule_reads(command):
    """Rule-file paths a command cat/sed/head/tails, ignoring heredoc bodies and quoted text."""
    return SHELL_RULE_READ.findall(_strip_prose(command))


def runnable_tool_calls(command):
    """{tool: count} of the Runnable tools a command really runs. A `python3 codeindex.py ...`
    inside a heredoc body or quoted text (an edit script, a doc string) is not a run."""
    command = _strip_prose(command)
    calls = {}
    for tool in RUNNABLE_TOOLS:
        count = len(re.findall(r"python3?\s+\S*" + re.escape(tool), command))
        if count:
            calls[tool] = count
    return calls


def _grep_segments(command):
    """(pattern alternatives, paths and file filters) for each grep/egrep/rg in a command.
    Quotes are honoured, so a `|` inside a pattern does not split it."""
    try:
        lexer = shlex.shlex(HEREDOC.sub("", command), posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:   # unbalanced quotes: not worth guessing at
        return []
    segments, current = [], []
    for token in tokens + [";"]:
        if token and set(token) <= set(";&|()"):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    found = []
    for words in segments:
        if os.path.basename(words[0]) not in GREP_PROGRAMS:
            continue
        patterns, operands, filters, k = [], [], [], 1
        while k < len(words):
            word = words[k]
            if word in ("-e", "--regexp"):
                patterns.append(words[k + 1] if k + 1 < len(words) else "")
                k += 2
                continue
            if word in GREP_VALUE_OPTIONS:
                filters.append(words[k + 1] if k + 1 < len(words) else "")
                k += 2
                continue
            if word.startswith("-"):
                filters.append(word)
            else:
                operands.append(word)
            k += 1
        if not patterns and operands:
            patterns.append(operands.pop(0))
        # A grep with no path reads stdin (`… | grep Foo`): output, not source. rg with no path
        # searches the cwd, so it counts when a file filter (-t cs, -g *.cs) names C#.
        if operands or (os.path.basename(words[0]) == "rg" and filters):
            found.append((patterns, operands + filters))
    return found


def type_grep_suggestions(command):
    """codeindex/usages commands for a grep over C# whose pattern is a type or member name:
    `class|interface|enum|struct|record <Name>` → where/show, `[Name` → attributed, a bare
    PascalCase name (optionally `Name(` or `Name<`) → usages. Free text gets nothing."""
    suggestions = []
    for patterns, targets in _grep_segments(command):
        if not any(CS_TARGET.search(t) for t in targets) and "cs" not in targets:
            continue
        for pattern in patterns:
            plain = re.sub(r"\\[sS][+*]?|\\b|\\<|\\>", " ", pattern)
            for alternative in re.split(r"\\\||\|", plain):
                alternative = alternative.replace("\\", "").strip()
                decl = TYPE_DECL_PATTERN.search(alternative)
                if decl:
                    name = decl.group(2)
                    suggestions.append(("codeindex.py where %s" % name, "codeindex.py show %s" % name))
                    continue
                attr = re.fullmatch(r"\[\s*([A-Z]\w*)\W*", alternative)
                if attr and re.search(r"[a-z]", attr.group(1)):
                    suggestions.append(("codeindex.py attributed %s" % attr.group(1),))
                    continue
                name = re.fullmatch(r"\.?([A-Z]\w*)\s*[(<]?\s*\)?", alternative)
                if name and re.search(r"[a-z]", name.group(1)):
                    suggestions.append(("usages.py %s" % name.group(1), "codeindex.py where %s" % name.group(1)))
    unique = []
    for suggestion in suggestions:
        if suggestion not in unique:
            unique.append(suggestion)
    return unique[:3]


def unity_tools_prefix():
    """How to call the unity-tools scripts from the hook's cwd (the project root): a literal
    relative path when the core sits inside the project, else absolute. Never a shell variable —
    the worktree guard refuses `python3 $R/…`."""
    tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "unity-tools")
    relative = os.path.relpath(tools, os.getcwd())
    return "python3 " + (tools if relative.startswith("..") else relative) + "/"


def cmd_hook_bash(args):
    """PreToolUse hook on Bash: remind the agent to load rule and process files with Read when a
    command cat/sed/head/tails one, and suggest codeindex/usages for a type-shaped grep over C#.
    Warns only; never blocks the command."""
    hook = {}
    try:
        hook = read_hook_input()
        command = (hook.get("tool_input") or {}).get("command", "")
        notes = []
        paths = shell_rule_reads(command)
        if paths:
            notes.append("Use the Read tool for rule, process, index and skill files (%s) so the "
                         "router trace is exact; shell reads are only inferred." % ", ".join(paths))
        lookups = type_grep_suggestions(command)
        if lookups:
            prefix = unity_tools_prefix()
            notes.append("This grep looks up a C# name; the index answers it with file:start-end and full "
                         "signatures: %s. Keep grep for free text." %
                         "; ".join(" or ".join(prefix + c for c in s) for s in lookups))
        if notes:
            print(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "additionalContext": "\n".join(notes)}}))
    except Exception as error:   # a hook must never block a command
        hook_log(args, "bash", hook, "ERROR %s" % error)
    return 0


# ---------------------------------------------------------------- typecheck + lint hooks (audit 2026-11-10, Part 3)

def load_typecheck(folder):
    """typecheck.json: {baseline, last_cs_edit, end_check_blocks, lint}. A sidecar, not session.json,
    because the async hook-stop compile rewrites session.json and would drop a concurrent update."""
    try:
        with open(os.path.join(folder, TYPECHECK_STATE)) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_typecheck(folder, data):
    path = os.path.join(folder, TYPECHECK_STATE)
    with open(path + ".tmp", "w") as handle:
        json.dump(data, handle, indent=2)
    os.replace(path + ".tmp", path)


def unity_project_of(path):
    """The Unity project (or worktree) root holding path, or None for a .cs file outside one."""
    current = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.isfile(os.path.join(current, "ProjectSettings", "ProjectVersion.txt")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def cs_edit_target(hook):
    """(file, Unity root) when an Edit/Write payload targets a .cs file inside a Unity project."""
    path = (hook.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".cs"):
        return None
    root = unity_project_of(path)
    return (path, root) if root else None


def typecheck_command(root):
    """The literal typecheck command for root: the project-relative path when the core is linked
    in (worktrees symlink GitIgnoredExternals too), else absolute. Never a shell variable."""
    relative = os.path.join("GitIgnoredExternals", "AIAgentCoreRules", "Tools", "unity-tools", "typecheck.py")
    return "python3 " + (relative if os.path.isfile(os.path.join(root, relative)) else TYPECHECK_SCRIPT)


def classify_typecheck(output):
    """clean | failed: <assemblies> | nothing_checked | listed | background | error | unknown, from typecheck output."""
    if re.search(r"^Would check \d+ assembl", output, re.MULTILINE):
        return "listed"   # --list compiles nothing
    if "type check clean" in output:
        return "clean"
    failed = re.search(r"^FAILED: (.+)$", output, re.MULTILINE)
    if failed:
        return "failed: " + failed.group(1).strip()
    if re.search(r"Nothing to check|none belong to a generated|belong to a known assembly", output):
        return "nothing_checked"
    if re.search(r"running in background|Command running", output):
        return "background"
    if re.search(r"^error:", output, re.MULTILINE):
        return "error"
    return "unknown"


def run_baseline(path, root):
    """typecheck.py --files <path> on the tree as it is before the edit. Never raises."""
    started = time.time()
    record = {"when": now_iso(), "file": path, "root": root}
    try:
        result = subprocess.run([sys.executable, TYPECHECK_SCRIPT, "--files", os.path.abspath(path)], cwd=root,
                                capture_output=True, text=True, timeout=BASELINE_TIMEOUT_SECONDS)
        output = result.stdout + result.stderr
        record["result"] = classify_typecheck(output)
        record["errors"] = [line.strip() for line in output.splitlines() if "error CS" in line][:10]
    except subprocess.TimeoutExpired:
        record["result"] = "timeout"
    except Exception as error:
        record["result"] = "error"
        record["errors"] = [str(error)]
    record["seconds"] = round(time.time() - started, 1)
    return record


def typecheck_runs(transcript_path, session_id):
    """[{when, result, id}] for every Bash call that really ran typecheck.py, in the session's
    transcript and its subagents', with the result read from the matching tool_result."""
    runs = {}
    for path, _via in transcript_files(transcript_path, session_id):
        try:
            with open(path, errors="replace") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for line in lines:
            if "typecheck.py" not in line or '"tool_use"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            for block in (entry.get("message") or {}).get("content") or []:
                if (isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Bash"
                        and "typecheck.py" in runnable_tool_calls((block.get("input") or {}).get("command", ""))):
                    runs[block.get("id")] = {"when": entry.get("timestamp", ""), "result": "unknown", "id": block.get("id")}
        pending = [run_id for run_id in runs if run_id and runs[run_id]["result"] == "unknown"]
        for line in lines if pending else []:
            if '"tool_result"' not in line or not any(run_id in line for run_id in pending):
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            for block in (entry.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("tool_use_id") in runs:
                    content = block.get("content")
                    if isinstance(content, list):
                        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
                    runs[block["tool_use_id"]]["result"] = classify_typecheck(content or "")
    return sorted(runs.values(), key=lambda run: run["when"])


def parse_moment(stamp):
    try:
        return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone()
    except (AttributeError, ValueError):
        return None


def cmd_hook_edit(args):
    """PreToolUse hook on Edit|Write: on the session's first .cs edit, typecheck the file's assemblies
    on the untouched tree (the baseline) and tell the agent the result; every .cs edit updates
    last_cs_edit for the end check. Never blocks the edit."""
    hook = {}
    try:
        hook = read_hook_input()
        target = cs_edit_target(hook)
        if not target:
            return 0
        path, root = target
        hook_project_dir(hook)
        folder = ensure_folder(reports_root(args), hook.get("session_id"), hook.get("transcript_path"),
                               current_project_dir())
        if not folder:
            return 0
        data = load_typecheck(folder)
        data["last_cs_edit"] = {"when": now_iso(), "file": path, "root": root}
        note = None
        if "baseline" not in data:
            data["baseline"] = run_baseline(path, root)
            baseline = data["baseline"]
            note = ("Typecheck baseline (this session's first .cs edit, run on the tree before it): %s in %ss — "
                    "`%s --files %s` from %s." % (baseline["result"], baseline["seconds"], typecheck_command(root),
                                                  os.path.relpath(path, root), root))
            if baseline["result"] != "clean":
                note += (" These results predate your edits; do not fix them unless asked, and do not count "
                         "them against your change." + "".join("\n  " + e for e in baseline.get("errors", [])))
            hook_log(args, "edit", hook, "baseline %s" % baseline["result"])
        save_typecheck(folder, data)
        if note:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": note}}))
    except Exception as error:   # a hook must never block an edit
        hook_log(args, "edit", hook, "ERROR %s" % error)
    return 0


def cmd_hook_lint(args):
    """PostToolUse hook on Edit|Write: cslint the edited .cs file's changed lines and hand the agent
    the mechanical-tag violations at once. Silent when clean."""
    hook = {}
    try:
        hook = read_hook_input()
        target = cs_edit_target(hook)
        if not target or not os.path.isfile(target[0]):
            return 0
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(SCRIPT_PATH)), "unity-tools"))
        import cslint
        violations = cslint.lint_file(target[0])
        folder = find_folder(reports_root(args), hook.get("session_id"))
        if folder:
            data = load_typecheck(folder)
            lint = data.setdefault("lint", {"runs": 0, "violations": 0})
            lint["runs"] += 1
            lint["violations"] += len(violations)
            save_typecheck(folder, data)
        if violations:
            rel = os.path.relpath(target[0], target[1])
            rows = ["%s:%d: [%s] %s" % (rel, line, tag, message) for line, tag, message in violations[:LINT_MAX_ROWS]]
            if len(violations) > LINT_MAX_ROWS:
                rows.append("… %d more: python3 %s %s" % (len(violations) - LINT_MAX_ROWS,
                                                          os.path.join(os.path.dirname(TYPECHECK_SCRIPT), "cslint.py"),
                                                          target[0]))
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
                "cslint (mechanical coding-standards tags, changed lines only) found %d violation(s). Fix them "
                "now, or say why one is a false positive:\n%s" % (len(violations), "\n".join(rows))}}))
    except Exception as error:   # a hook must never break an edit
        hook_log(args, "lint", hook, "ERROR %s" % error)
    return 0


def cmd_hook_stop_check(args):
    """Stop hook (sync): when a .cs file changed after the last typecheck run of the session, block
    the stop once with the command to run. stop_hook_active (already blocked once) always passes."""
    hook = {}
    try:
        hook = read_hook_input()
        if hook.get("stop_hook_active"):
            return 0
        hook_project_dir(hook)
        folder = find_folder(reports_root(args), hook.get("session_id"))
        data = load_typecheck(folder) if folder else {}
        edit = data.get("last_cs_edit")
        if not edit:
            return 0
        runs = typecheck_runs(locate_transcript(hook.get("session_id"), hook.get("transcript_path")),
                              hook.get("session_id"))
        runs = [run for run in runs if run["result"] != "listed"]
        last = parse_moment(runs[-1]["when"]) if runs else None
        if last and last >= parse_moment(edit["when"]):
            return 0
        data["end_check_blocks"] = data.get("end_check_blocks", 0) + 1
        save_typecheck(folder, data)
        hook_log(args, "stop-check", hook, "block: .cs edited %s, last typecheck %s"
                 % (edit["when"], runs[-1]["when"] if runs else "none"))
        print(json.dumps({"decision": "block", "reason":
            "C# changed after the last typecheck (last .cs edit %s, %s; last typecheck: %s). Run `%s` from %s "
            "(add --define USING_TOOLS for AndreaTools code) and report its result before you finish."
            % (local_clock(edit["when"]) or edit["when"][11:19], os.path.relpath(edit["file"], edit["root"]),
               local_clock(runs[-1]["when"]) if runs else "none this session", typecheck_command(edit["root"]),
               edit["root"])}))
    except Exception as error:   # a hook must never trap the session
        hook_log(args, "stop-check", hook, "ERROR %s" % error)
    return 0


def typecheck_lines(state):
    """metrics.md section: baseline, every typecheck run, the last .cs edit, end-check blocks, lint."""
    data = state.get("typecheck") or {}
    lines = ["", "## Typecheck", ""]
    baseline = data.get("baseline")
    lines.append("- Baseline: %s" % ("`%s` %s (%ss, %s)" % (local_clock(baseline["when"]), baseline["result"],
                                                             baseline.get("seconds"), os.path.basename(baseline["file"]))
                                     if baseline else "none (no .cs edit)"))
    runs = data.get("runs") or []
    lines.append("- Runs: %s" % (", ".join("`%s` %s" % (local_clock(r["when"]), r["result"]) for r in runs) or "none"))
    edit = data.get("last_cs_edit")
    lines.append("- Last .cs edit: %s" % ("`%s` %s" % (local_clock(edit["when"]), os.path.basename(edit["file"]))
                                          if edit else "none"))
    lines.append("- End-check blocks: %d" % data.get("end_check_blocks", 0))
    lint = data.get("lint")
    if lint:
        lines.append("- cslint: %d run(s), %d violation(s) reported" % (lint["runs"], lint["violations"]))
    return lines


def set_work_type(state, work_type, source):
    if state.get("work_type") and state["work_type"] != work_type:
        state.setdefault("work_type_history", []).append({"at": now_iso(), "from": state["work_type"], "to": work_type})
    state["work_type"] = work_type
    state["work_type_source"] = source


def cmd_set(args):
    folder, state = resolve(args)
    closed = state.get("end_session_run")
    if closed and args.lane and state.get("lane") and args.lane != state["lane"]:
        # Relabelling a closed session mismatches its retro and renames the folder that progress
        # files and Phase 8 reference (MR-20261009-04).
        sys.exit("Session %s was closed by /end-session as lane %s; start a fresh session for the %s "
                 "work instead of relabelling this one." % (state["session_id"][:8], state["lane"], args.lane))
    if args.lane:
        # Keep earlier lanes: a mid-session change (e.g. a BugFix detour) must stay auditable.
        if state.get("lane") and state["lane"] != args.lane:
            state.setdefault("lane_history", []).append({"at": now_iso(), "from": state["lane"], "to": args.lane})
            offer_fresh_session(state, args.lane)
        state["lane"] = args.lane
    if args.work_type:
        set_work_type(state, args.work_type, "explicit")
    elif args.lane and state.get("work_type_source") != "explicit":
        # Until a work type is given, follow the lane, so every session gets one.
        set_work_type(state, LANE_WORK_TYPE[args.lane], "lane")
    if args.name:
        state["name"] = args.name
    if args.feature:
        state["feature"] = args.feature
    if args.phase:
        # One session per phase; a phase change mid-session stays auditable like a lane change.
        if state.get("phase") and state["phase"] != args.phase:
            state.setdefault("phase_history", []).append({"at": now_iso(), "from": state["phase"], "to": args.phase})
        state["phase"] = args.phase
    if args.title:
        state["title"] = args.title
    save_state(folder, state)
    target = os.path.join(os.path.dirname(folder), folder_name(state))
    # A closed session's folder name is final: others may reference it by name.
    if target != folder and not os.path.exists(target) and not closed:
        os.rename(folder, target)
        folder = target
    render(folder, state, state.get("project_dir") or current_project_dir())
    print(folder)


def cmd_note(args):
    folder, state = resolve(args)
    key = "inaccuracies" if args.kind == "inaccuracy" else "iterations"
    # source: engineer (/iteration), agent (self-corrected live), or retro
    # (found by /end-session and not logged live). Lets reports tell live logging apart.
    state[key].append({"at": now_iso(), "text": args.text, "source": args.source})
    save_state(folder, state)
    render(folder, state, state.get("project_dir") or current_project_dir())
    print("%s #%d logged in %s" % (args.kind, len(state[key]), os.path.join(folder, "metrics.md")))


def cmd_compile(args):
    folder, state = resolve(args)
    if args.final:
        state["end_session_run"] = True
        state["ended_at"] = now_iso()
    compile_folder(folder, state, state.get("project_dir") or current_project_dir())
    print(os.path.join(folder, "metrics.md"))


def cmd_open(args):
    folder, _state = resolve(args)
    if os.path.isfile(os.path.join(folder, "retro.md")):
        retro_page.render(os.path.join(folder, "retro.md"), SCRIPT_PATH)
    paths = [os.path.join(folder, name) for name in ("metrics.md", "retro.html")
             if os.path.isfile(os.path.join(folder, name))]
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    for path in paths:
        subprocess.run([opener, path])
        print(path)


def retro_folder(args):
    """--folder (a path, a folder name under the reports root, or a unique part of one such as
    the session id's first 8 characters), else the current session. Proposals are often resolved
    in a later session, so marking must reach any session's retro."""
    if not args.folder:
        return resolve(args)[0]
    if os.path.isdir(args.folder):
        return os.path.abspath(args.folder)
    root = reports_root(args)
    names = sorted(name for name in os.listdir(root) if os.path.isdir(os.path.join(root, name))) \
        if os.path.isdir(root) else []
    if args.folder in names:
        return os.path.join(root, args.folder)
    matches = [name for name in names if args.folder in name]
    if len(matches) != 1:
        sys.exit("--folder %s matches %d session folders under %s%s" % (
            args.folder, len(matches), root, (": " + ", ".join(matches)) if matches else ""))
    return os.path.join(root, matches[0])


def checked_source(path):
    """A file written elsewhere (a background job's tmp dir) that is about to be filed."""
    if not os.path.isfile(path):
        sys.exit("--from file not found: %s" % path)
    if os.path.getsize(path) == 0:
        sys.exit("--from file is empty: %s" % path)
    return path


def cmd_retro(args):
    if args.path and args.source:
        sys.exit("--path cannot be combined with --from")
    if args.path:
        retro_path = os.path.abspath(checked_source(args.path))
        if os.path.splitext(retro_path)[1].lower() not in (".md", ".markdown"):
            sys.exit("--path must name a Markdown retrospective (.md or .markdown)")
    else:
        folder = retro_folder(args)
        retro_path = os.path.join(folder, "retro.md")
    if args.source:
        # MR-20261016-06: a background session cannot Write into the shared checkout; it writes
        # the retro to its job tmp dir and files it through this script.
        shutil.copyfile(checked_source(args.source), retro_path)
        print("filed " + retro_path)
    if not os.path.isfile(retro_path):
        sys.exit("No retro.md in %s — /end-session writes it." % folder)
    if args.mark is not None:
        if not args.status:
            sys.exit("--mark needs --status (%s)." % "|".join(retro_page.STATUSES))
        with open(retro_path) as handle:
            text = handle.read()
        try:
            text = retro_page.mark(text, args.mark, args.status, args.note)
        except ValueError as error:
            sys.exit(str(error))
        with open(retro_path, "w") as handle:
            handle.write(text)
    html_path = retro_page.render(retro_path, SCRIPT_PATH, standalone=bool(args.path))
    with open(retro_path) as handle:
        for item in retro_page.statuses(handle.read()):
            print("#%d %-8s %s%s" % (item["n"], item["status"], item["file"],
                                    (" — " + item["detail"]) if item["detail"] else ""))
    print(html_path)
    if args.open:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", html_path])


def cmd_path(args):
    folder, _state = resolve(args)
    print(folder)


def cmd_file(args):
    """Copy outputs written elsewhere (a background job's tmp dir) into a reports folder that is a
    sibling of the sessions root, e.g. GitIgnoreReports/MetaReviews."""
    sources = [checked_source(path) for path in args.paths]
    target = os.path.join(os.path.dirname(reports_root(args)), args.to)
    os.makedirs(target, exist_ok=True)
    for source in sources:
        destination = os.path.join(target, os.path.basename(source))
        shutil.copyfile(source, destination)
        print("filed " + destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reports-root")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hook-start", help="also safe to run by hand (/start-session)").set_defaults(func=cmd_hook_start)
    sub.add_parser("hook-end").set_defaults(func=cmd_hook_end)
    sub.add_parser("hook-stop").set_defaults(func=cmd_hook_stop)
    sub.add_parser("hook-prompt").set_defaults(func=cmd_hook_prompt)
    sub.add_parser("hook-bash").set_defaults(func=cmd_hook_bash)
    sub.add_parser("hook-edit").set_defaults(func=cmd_hook_edit)
    sub.add_parser("hook-lint").set_defaults(func=cmd_hook_lint)
    sub.add_parser("hook-stop-check").set_defaults(func=cmd_hook_stop_check)
    features = sub.add_parser("features", help="list CreateFeature features that are not complete or closed (/active-features)")
    features.add_argument("--features-root", help="override $SESSION_FEATURES_ROOT, ai-agent-core.json paths.features, or legacy <project>/%s" % DEFAULT_FEATURES_DIR)
    features.add_argument("--json", action="store_true")
    features.add_argument("--closed", action="store_true",
                          help="list features closed by /close-feature that can be reopened (%s)" % ", ".join(REOPENABLE_STATUSES))
    features.set_defaults(func=cmd_features)
    prune = sub.add_parser("prune-empty", help="delete session folders with no lane, notes, tokens or typed prompt")
    prune.add_argument("--dry-run", action="store_true")
    prune.set_defaults(func=cmd_prune_empty)
    filing = sub.add_parser("file", help="copy files written elsewhere (a background job's tmp dir) into a "
                                         "reports folder")
    filing.add_argument("--to", choices=FILE_TARGETS, required=True,
                        help="folder next to the sessions root, under %s" % REPORTS_DIR)
    filing.add_argument("paths", nargs="+", metavar="PATH")
    filing.set_defaults(func=cmd_file)
    for name, func in (("set", cmd_set), ("note", cmd_note), ("compile", cmd_compile),
                       ("open", cmd_open), ("path", cmd_path), ("retro", cmd_retro)):
        command = sub.add_parser(name)
        command.add_argument("--session-id", help="defaults to $CODEX_THREAD_ID or $CLAUDE_CODE_SESSION_ID; Claude-only legacy newest fallback")
        command.set_defaults(func=func)
        if name == "set":
            command.add_argument("--name", help="engineer-given session name; also names the folder")
            command.add_argument("--lane", choices=LANES)
            command.add_argument("--work-type", choices=WORK_TYPES,
                                 help="defaults to the lane's work type until set explicitly")
            command.add_argument("--title")
            command.add_argument("--feature", help="CreateFeature name this session works on (set by /feature, /resume-work)")
            command.add_argument("--phase", help="CreateFeature phase key, e.g. 2_discovery")
        if name == "note":
            command.add_argument("--kind", choices=["inaccuracy", "iteration"], required=True)
            command.add_argument("--source", choices=NOTE_SOURCES, default="engineer",
                                 help="who logged it: engineer (default), agent (self-correction), retro (/end-session)")
            command.add_argument("text")
        if name == "compile":
            command.add_argument("--final", action="store_true", help="mark /end-session as run")
        if name == "retro":
            target = command.add_mutually_exclusive_group()
            target.add_argument("--path", metavar="PATH",
                                help="render an existing Markdown retrospective without session tracking; "
                                     "write a matching .html beside it; supports --mark and --open")
            target.add_argument("--folder", help="another session's folder: path, folder name, or a unique part "
                                                  "such as the session id's first 8 characters")
            command.add_argument("--mark", type=int, metavar="N", help="proposal number to update")
            command.add_argument("--status", choices=retro_page.STATUSES)
            command.add_argument("--note", help="Applied-line detail, e.g. '<file> — <what changed>'; "
                                                "omitted keeps the existing note")
            command.add_argument("--open", action="store_true", help="open retro.html afterwards")
            command.add_argument("--from", dest="source", metavar="PATH",
                                 help="copy a retro written elsewhere (a background job's tmp dir) to the "
                                      "session's retro.md first, overwriting it")
    args = parser.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
