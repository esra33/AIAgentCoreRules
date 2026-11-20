"""Build the Performance tab's model: token usage of every tracked session, newest first.

Stdlib only. Reads the session folders session_lifecycle.py writes under the reports root
(<project>/GitIgnoreReports/Sessions, or $SESSION_REPORTS_ROOT):
  - <folder>/session.json   title, lane, started/ended, and "breakdown" -- the same estimated
                            token-by-category numbers the retrospective charts (token_breakdown.py)

A session without a compiled breakdown is listed but kept out of the overview statistics. The
active session's breakdown is as fresh as its last compile (the Stop hook recompiles after replies).

Served from a feature folder (one with <Name>_Progress.md), the model also scopes to that feature:
a session belongs to it when its session.json "feature" tag (set --feature) names it, or when its
folder is listed under the Progress file's "sessions:" (matched by the id8 suffix, since a lane
change renames the folder). The page toggles between that view and all sessions.

"current" is the account's usage right now, independent of the feature scope:
  - plan    the latest rate_limits (5-hour, 7-day, spend) that session_lifecycle.py statusline saved
            to <reports root>/plan_usage.json; windows whose resets_at has passed are dropped
  - burn    tokens of tracked sessions (main transcript plus subagents) in the last hour, the last
            5 hours and since local midnight, from each model call's timestamp
"""
import datetime
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR / "feature-state"))
from feature_state import load_state
sys.path.insert(0, str(TOOLS_DIR / "setup"))
sys.path.insert(0, str(TOOLS_DIR / "session-lifecycle"))
import project_root  # noqa: E402  shared with session_lifecycle.py, so both find the same reports root
import token_breakdown  # noqa: E402  owns the category names; the page colours its STANDARDIZED ones

REPORTS_DIR = "GitIgnoreReports"
SESSIONS_DIR = "Sessions"
STATE_FILE = "session.json"
# No ended_at and touched this recently = still running; older ones were closed without the SessionEnd hook.
ACTIVE_WINDOW_SECONDS = 60 * 60
FEATURE_LINE = re.compile(r'^feature:\s*"?([^"\s#]+)', re.MULTILINE)
# A quoted session folder name, e.g. "2026-10-29_1358_small-task_75453a1d"; group 1 = its id8.
SESSION_FOLDER = re.compile(r'"\d{4}-\d{2}-\d{2}_[^"]*_([0-9a-f]{8})"')
# A plan capture older than this is shown as stale: no session with the status line has replied since.
PLAN_STALE_SECONDS = 30 * 60
PLAN_WINDOWS = [("five_hour", "5-hour"), ("seven_day", "7-day"), ("spend_limit", "Spend")]
BURN_WINDOWS = [("last_hour", "Last hour", 60 * 60), ("last_5h", "Last 5 hours", 5 * 60 * 60)]


def find_reports_root(doc_path: Path) -> Optional[Path]:
    """The Sessions folder for the served doc's project, or None when it has no sessions."""
    override = os.environ.get("SESSION_REPORTS_ROOT")
    if override:
        root = Path(override)
    else:
        # abspath, not resolve(): project_root maps a logical GitIgnoredExternals/<layer> path to its host.
        project = project_root.find_project_root(os.path.abspath(str(doc_path.parent)))
        if not project:
            return None
        root = Path(project) / REPORTS_DIR / SESSIONS_DIR
    return root if any(_state_paths(root)) else None


def watched_paths(reports_root: Path) -> List[Path]:
    """Every session.json, the plan capture (rewritten on every assistant reply, so it also refreshes
    the burn tiles) and the root itself, whose mtime changes when a session folder appears."""
    plan_path = reports_root / token_breakdown.PLAN_USAGE_FILE
    return [reports_root] + _state_paths(reports_root) + ([plan_path] if plan_path.is_file() else [])


def build_model(reports_root: Path, now: Optional[float] = None, progress_path: Optional[Path] = None) -> Dict:
    now = time.time() if now is None else now
    feature, listed_ids = feature_filter(progress_path)
    sessions = []
    for state_path in _state_paths(reports_root):
        session = _session(state_path, now)
        if session is not None:
            session["in_feature"] = bool(feature) and (session["feature"] == feature or session["id"] in listed_ids)
            sessions.append(session)
    sessions.sort(key=lambda session: session["sort_key"], reverse=True)
    for session in sessions:
        del session["sort_key"]
    warning = context_warning(sessions)
    for session in sessions:
        session["over_context"] = bool(warning["threshold"]) and session["active"] \
            and session["last_context"] >= warning["threshold"]
    return {"root": str(reports_root), "standardized_names": token_breakdown.STANDARDIZED,
            "context_warning": warning,
            "current": current_usage(reports_root, now, sum(1 for session in sessions if session["active"])),
            "overview": _overview(sessions), "sessions": sessions, "feature": feature,
            "feature_overview": _overview([session for session in sessions if session["in_feature"]])}


def context_warning(sessions: List[Dict]) -> Dict:
    """token_breakdown's context-size threshold over the peak per-call context of finished sessions
    (the same rule hook-prompt warns the agent with); threshold None when too few have a peak."""
    peaks = [session["peak_context"] for session in sessions if not session["active"] and session["peak_context"]]
    threshold = token_breakdown.context_warning_threshold(peaks)
    return {"threshold": threshold, "share": token_breakdown.CONTEXT_WARNING_SHARE, "sessions": len(peaks),
            "median_peak": statistics.median(peaks) if threshold is not None else None}


def current_usage(reports_root: Path, now: float, active_sessions: int = 0) -> Dict:
    """{"plan": latest capture or None, "burn": tokens per recent window} — see the module docstring."""
    return {"plan": _plan(reports_root / token_breakdown.PLAN_USAGE_FILE, now),
            "burn": _burn(reports_root, now, active_sessions)}


def _plan(path: Path, now: float) -> Optional[Dict]:
    try:
        capture = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    limits = capture.get("rate_limits") if isinstance(capture, dict) else None
    if not isinstance(limits, dict):
        return None
    windows = []
    for key, label in PLAN_WINDOWS:
        window = limits.get(key)
        if not isinstance(window, dict) or window.get("used_percentage") is None:
            continue
        resets_at = window.get("resets_at")
        if resets_at is not None and resets_at <= now:
            continue   # its period is over; the next capture starts a fresh one
        windows.append({"key": key, "label": label, "used_percentage": window["used_percentage"],
                        "resets_at": resets_at, "used_usd": window.get("used_usd"),
                        "limit_usd": window.get("limit_usd"), "period": window.get("period")})
    captured_at = capture.get("captured_at") or 0
    return {"captured_at": captured_at, "age_seconds": max(now - captured_at, 0),
            "stale": now - captured_at > PLAN_STALE_SECONDS, "windows": windows}


def _burn(reports_root: Path, now: float, active_sessions: int) -> Dict:
    midnight = datetime.datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    starts = [(key, label, now - seconds) for key, label, seconds in BURN_WINDOWS] + [("today", "Today", midnight)]
    earliest = min(start for _key, _label, start in starts)
    totals = {key: {"label": label, "tokens": 0, "calls": 0, "sessions": 0} for key, label, _start in starts}
    for transcripts in _session_transcripts(reports_root, earliest):
        counted = set()
        for path in transcripts:
            for stamp, tokens in token_breakdown.timed_calls(str(path)):
                for key, _label, start in starts:
                    if start <= stamp <= now:
                        totals[key]["tokens"] += tokens
                        totals[key]["calls"] += 1
                        counted.add(key)
        for key in counted:
            totals[key]["sessions"] += 1
    return {"active_sessions": active_sessions,
            "windows": [dict(totals[key], key=key) for key, _label, _start in starts]}


def _session_transcripts(reports_root: Path, since: float) -> List[List[Path]]:
    """Per tracked session written to since `since`: its transcript plus its subagent transcripts."""
    sessions = []
    for state_path in _state_paths(reports_root):
        try:
            state = json.loads(state_path.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(state, dict) or not state.get("transcript_path") or not state.get("session_id"):
            continue
        transcript = Path(state["transcript_path"])
        if not transcript.is_file():
            continue
        subagents = sorted((transcript.parent / state["session_id"] / "subagents").glob("*.jsonl"))
        paths = [path for path in [transcript] + subagents if path.stat().st_mtime >= since]
        if paths:
            sessions.append(paths)
    return sessions


def feature_filter(progress_path: Optional[Path]):
    """(feature name, id8s listed under "sessions:") from a <Name>_Progress.md; ("", set()) without one."""
    if progress_path is None:
        return "", set()
    state_path = progress_path.parent / "state.json"
    if state_path.is_file():
        state = load_state(state_path.parent)
        ids = {folder.rsplit("_", 1)[-1] for folder in state["sessions"]}
        return state["feature"], ids
    try:
        text = progress_path.read_text()
    except OSError:
        return "", set()
    match = FEATURE_LINE.search(text)
    feature = match.group(1) if match else progress_path.name[:-len("_Progress.md")]
    return feature, set(SESSION_FOLDER.findall(_sessions_block(text)))


def _sessions_block(text: str) -> str:
    """The "sessions:" value: an inline [..] list on its own line, or the indented "- " lines below it."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("sessions:"):
            block = [line]
            for following in lines[index + 1:]:
                if following and not following[0].isspace():
                    break
                block.append(following)
            return "\n".join(block)
    return ""


def _state_paths(reports_root: Path) -> List[Path]:
    if not reports_root.is_dir():
        return []
    return sorted(path for path in reports_root.glob("*/" + STATE_FILE) if path.is_file())


def _session(state_path: Path, now: float) -> Optional[Dict]:
    try:
        state = json.loads(state_path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or not state.get("session_id"):
        return None
    breakdown = state.get("breakdown") or {}
    total = breakdown.get("total") or 0
    categories = []
    for name, tokens in (breakdown.get("categories") or {}).items():
        categories.append({"name": name, "tokens": tokens, "share": tokens / total if total else 0.0})
    started_at = state.get("started_at") or ""
    model = state.get("model") or ""
    active = not state.get("ended_at") and now - state_path.stat().st_mtime < ACTIVE_WINDOW_SECONDS
    return {
        "id": state["session_id"][:8],
        "folder": state_path.parent.name,
        "title": state.get("title") or state.get("name") or "",
        "lane": state.get("lane") or "",
        "work_type": state.get("work_type") or "",
        "feature": state.get("feature") or "",
        "started_at": started_at,
        "ended_at": state.get("ended_at") or "",
        "compiled_at": state.get("compiled_at") or "",
        "active": active,
        "model": model,
        # Only an active session's gauge is current; a finished one's last call is no longer "now".
        "context_window": token_breakdown.context_window_usage(model, breakdown.get("last_context") or 0)
            if active and model else None,
        "usage": _usage(state.get("tokens") or {}),
        "compiled": bool(total),
        "error": breakdown.get("error") or "",
        "total": total,
        "calls": breakdown.get("calls") or 0,
        "standardized": breakdown.get("standardized") or 0,
        "categories": categories,
        "peak_context": breakdown.get("peak_context") or 0,
        "last_context": breakdown.get("last_context") or 0,
        "doc_review": _doc_review(breakdown.get("doc_review") or {}),
        "sort_key": (_timestamp(started_at), state_path.parent.name),
    }


def _usage(tokens: Dict) -> Dict:
    total = tokens.get("total_tokens") if tokens.get("available") else None
    turns = tokens.get("turns") if tokens.get("available") else None
    return {"total": total, "turns": turns,
            "per_turn": total / turns if total is not None and turns else None}


def _doc_review(block: Dict) -> Dict:
    """Preview calls vs the Miro/Confluence estimate; zeros for breakdowns compiled before it existed."""
    measured = block.get("miro_confluence") or {}
    return {"count": block.get("count") or 0, "tokens": block.get("tokens") or 0,
            "equivalent": block.get("equivalent") or 0, "round_trips": block.get("round_trips") or 0,
            "commands": block.get("commands") or {},
            "miro_confluence": {"count": measured.get("count") or 0, "tokens": measured.get("tokens") or 0}}


def _timestamp(iso_text: str) -> float:
    try:
        return datetime.datetime.fromisoformat(iso_text).timestamp()
    except ValueError:
        return 0.0


def _overview(sessions: List[Dict]) -> Dict:
    compiled = [session for session in sessions if session["compiled"]]
    totals = [session["total"] for session in compiled]
    category_names: List[str] = []
    for session in compiled:
        for category in session["categories"]:
            if category["name"] not in category_names:
                category_names.append(category["name"])
    recorded = [session["usage"] for session in sessions if session["usage"]["total"] is not None]
    paired = [usage for usage in recorded if usage["turns"]]
    recorded_turns = sum(usage["turns"] for usage in paired)
    grand_total = sum(totals)
    categories = []
    for name in category_names:
        tokens = sum(category["tokens"] for session in compiled for category in session["categories"]
                     if category["name"] == name)
        categories.append({"name": name, "tokens": tokens, "average": tokens / len(compiled),
                           "share": tokens / grand_total if grand_total else 0.0})
    return {
        "usage": {"sessions": len(recorded), "total": sum(usage["total"] for usage in recorded) if recorded else None,
                  "turns": sum(usage["turns"] for usage in recorded if usage["turns"] is not None) if any(usage["turns"] is not None for usage in recorded) else None,
                  "per_turn": sum(usage["total"] for usage in paired) / recorded_turns if recorded_turns else None},
        "sessions": len(sessions),
        "compiled": len(compiled),
        "total": grand_total,
        "calls": sum(session["calls"] for session in compiled),
        "mean": statistics.mean(totals) if totals else 0.0,
        "median": statistics.median(totals) if totals else 0.0,
        # Population deviation: these are all the sessions there are, not a sample of them.
        "stdev": statistics.pstdev(totals) if len(totals) > 1 else 0.0,
        "min": min(totals) if totals else 0,
        "max": max(totals) if totals else 0,
        "standardized": sum(session["standardized"] for session in compiled),
        "categories": categories,
        "doc_review": {
            "sessions": sum(1 for session in compiled if session["doc_review"]["count"]),
            "count": sum(session["doc_review"]["count"] for session in compiled),
            "tokens": sum(session["doc_review"]["tokens"] for session in compiled),
            "equivalent": sum(session["doc_review"]["equivalent"] for session in compiled),
            "round_trips": sum(session["doc_review"]["round_trips"] for session in compiled),
            "miro_confluence": {
                "sessions": sum(1 for session in compiled if session["doc_review"]["miro_confluence"]["count"]),
                "count": sum(session["doc_review"]["miro_confluence"]["count"] for session in compiled),
                "tokens": sum(session["doc_review"]["miro_confluence"]["tokens"] for session in compiled)}},
        "totals": [{"id": session["id"], "total": session["total"], "active": session["active"]} for session in compiled],
    }

