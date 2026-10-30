"""Fetch a pull request's comments and review notes with the gh CLI, for the Progress tab.

One PR = three kinds of note: conversation comments and review bodies (gh pr view) plus inline
review comments (gh api .../pulls/<n>/comments). gh resolves the repository from repo_dir's git
remote. Results are cached per refresh window, so the 1s live poll never shells out: a window flip
is also what makes the Progress tab's mtime move (progress_view.pr_refresh_stamp), and the
re-render that follows is the one call that refetches.
"""
import json
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple

REFRESH_SECONDS = 300
GH_TIMEOUT_SECONDS = 20

_cache: Dict[Tuple[str, int], Tuple[int, Dict]] = {}
_cache_lock = threading.Lock()
_repo_urls: Dict[str, str] = {}
GITHUB_REMOTE = re.compile(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$")


def refresh_window() -> int:
    return int(time.time() // REFRESH_SECONDS)


def fetch_pr_notes(number: int, repo_dir: Path) -> Dict:
    key = (str(repo_dir), number)
    window = refresh_window()
    with _cache_lock:
        cached = _cache.get(key)
        if cached is not None and cached[0] == window:
            return cached[1]
    pr = _fetch(number, repo_dir)
    with _cache_lock:
        _cache[key] = (window, pr)
    return pr


def pr_url(number: int, repo_dir: Path) -> str:
    """A PR's GitHub page built from repo_dir's origin remote -- no gh call -- or "" when the remote
    is not GitHub. The remote is read once per repo_dir."""
    key = str(repo_dir)
    if key not in _repo_urls:
        result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=key, capture_output=True, text=True,
                                timeout=GH_TIMEOUT_SECONDS, check=False)
        match = GITHUB_REMOTE.search(result.stdout.strip()) if result.returncode == 0 else None
        _repo_urls[key] = f"https://github.com/{match.group(1)}" if match else ""
    return f"{_repo_urls[key]}/pull/{number}" if _repo_urls[key] else ""


def _fetch(number: int, repo_dir: Path) -> Dict:
    try:
        view = _gh_json(["pr", "view", str(number), "--json", "number,title,url,state,comments,reviews"], repo_dir)
        # {owner}/{repo} are gh placeholders filled from repo_dir's remote; --slurp wraps the pages in one array.
        pages = _gh_json(["api", f"repos/{{owner}}/{{repo}}/pulls/{number}/comments", "--paginate", "--slurp"], repo_dir)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        return {"number": number, "title": "", "url": "", "state": "", "error": str(e), "notes": []}

    notes: List[Dict] = []
    for comment in view.get("comments", []):
        notes.append(_note("comment", comment.get("author"), comment.get("createdAt"), comment.get("body"),
                           comment.get("url", "")))
    for review in view.get("reviews", []):
        if (review.get("body") or "").strip():
            notes.append(_note("review", review.get("author"), review.get("submittedAt"), review.get("body"), "",
                               state=review.get("state", "")))
    for comment in (item for page in pages for item in page):
        location = comment.get("path", "")
        line = comment.get("line") or comment.get("original_line")
        if location and line:
            location += f":{line}"
        notes.append(_note("inline", comment.get("user"), comment.get("created_at"), comment.get("body"),
                           comment.get("html_url", ""), location=location))
    notes.sort(key=lambda note: note["created_at"])
    return {"number": view.get("number", number), "title": view.get("title", ""), "url": view.get("url", ""),
            "state": view.get("state", ""), "error": "", "notes": notes}


def _note(kind: str, author, created_at, body, url: str, location: str = "", state: str = "") -> Dict:
    login = (author or {}).get("login", "") if isinstance(author, dict) else ""
    return {"kind": kind, "author": login, "created_at": created_at or "", "body": body or "", "url": url,
            "location": location, "state": state}


def _gh_json(args: List[str], repo_dir: Path):
    result = subprocess.run(["gh"] + args, cwd=str(repo_dir), capture_output=True, text=True,
                            timeout=GH_TIMEOUT_SECONDS, check=False)
    if result.returncode != 0:
        lines = result.stderr.strip().splitlines()
        raise ValueError(f"gh {args[0]} failed: {lines[-1] if lines else 'exit ' + str(result.returncode)}")
    return json.loads(result.stdout)
