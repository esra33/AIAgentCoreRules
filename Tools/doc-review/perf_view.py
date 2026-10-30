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
    """Every session.json plus the root itself, whose mtime changes when a session folder appears."""
    return [reports_root] + _state_paths(reports_root)


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
    return {"root": str(reports_root), "standardized_names": token_breakdown.STANDARDIZED,
            "overview": _overview(sessions), "sessions": sessions, "feature": feature,
            "feature_overview": _overview([session for session in sessions if session["in_feature"]])}


def feature_filter(progress_path: Optional[Path]):
    """(feature name, id8s listed under "sessions:") from a <Name>_Progress.md; ("", set()) without one."""
    if progress_path is None:
        return "", set()
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
        "active": not state.get("ended_at") and now - state_path.stat().st_mtime < ACTIVE_WINDOW_SECONDS,
        "compiled": bool(total),
        "error": breakdown.get("error") or "",
        "total": total,
        "calls": breakdown.get("calls") or 0,
        "standardized": breakdown.get("standardized") or 0,
        "categories": categories,
        "doc_review": _doc_review(breakdown.get("doc_review") or {}),
        "sort_key": (_timestamp(started_at), state_path.parent.name),
    }


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
    grand_total = sum(totals)
    categories = []
    for name in category_names:
        tokens = sum(category["tokens"] for session in compiled for category in session["categories"]
                     if category["name"] == name)
        categories.append({"name": name, "tokens": tokens, "average": tokens / len(compiled),
                           "share": tokens / grand_total if grand_total else 0.0})
    return {
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

