#!/usr/bin/env python3
"""LocalDocReview CLI -- serve a doc + diagrams for local review, list ready comments, reply.

See LocalDocReview_TDD.md for the full design. Subcommands:
    serve    <doc.md> [<diagram.mmd> ...] [--port N] [--static [--output PATH] [--open]]
    comments <doc.md> [--status actionable|open|ready|addressed|resolved|all] [--json]
                                                   default actionable = open + ready + follow-ups
    reply    <doc.md> <thread_id> "<message>" [--status addressed]
    servers  [--json]                              list running live servers (pid, port, doc)
    stop     [--port N | --pid N | --all]          SIGTERM a live server; no selector = the only one
    pr-notes <PR> [--repo-dir DIR] [--json]        a PR's comments, review bodies and inline notes
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pr_notes
from anchor_resolver import resolve_thread, scan_inline_markers
from review_server import render_static, serve_doc
from sidecar_store import SidecarStore

QUOTE_TRUNCATE_LENGTH = 60
MMDC_VALIDATION_TIMEOUT_SECONDS = 30
SHELL_NAMES = {"bash", "sh", "zsh"}
LSOF_NAME_LINE = re.compile(r"^n.*:(\d+)$")
ACTIONABLE_STATUSES = {"open", "ready"}


class DiagramValidationError(Exception):
    pass


def cmd_serve(args: argparse.Namespace) -> None:
    paths = [Path(args.doc)] + [Path(p) for p in args.diagrams]
    if args.static:
        output_path = Path(args.output) if args.output else None
        render_static(paths, output_path=output_path, open_browser=args.open)
    else:
        serve_doc(paths, port=args.port, open_browser=args.open)


def cmd_comments(args: argparse.Namespace) -> None:
    doc_path = Path(args.doc)
    base_dir = doc_path.parent
    data = SidecarStore(doc_path).load()
    threads = [thread for thread in data["threads"] if _matches_status(thread, args.status)]
    hidden = len(data["threads"]) - len(threads)

    resolved = [_cli_resolved_thread(base_dir, thread) for thread in threads]
    markers = scan_inline_markers(base_dir, _marker_candidate_files(doc_path, data["threads"]))

    if args.json:
        print(json.dumps({"threads": resolved, "inline_markers": markers, "hidden": hidden}, indent=2))
    else:
        _print_text(resolved, markers)
        if hidden:
            print(f"{hidden} threads hidden by --status {args.status} -- --status all to list them")


def _matches_status(thread: Dict, status: str) -> bool:
    if status == "all":
        return True
    if status == "actionable":
        return thread["status"] in ACTIONABLE_STATUSES or _has_follow_up(thread)
    # A follow-up on an addressed thread keeps that status, so it is selected by any filter.
    return thread["status"] == status or _has_follow_up(thread)


def cmd_reply(args: argparse.Namespace) -> None:
    doc_path = Path(args.doc)
    store = SidecarStore(doc_path)
    try:
        if args.status == "addressed":
            _validate_if_diagram(doc_path.parent, store, args.thread_id)
        store.add_reply(args.thread_id, "agent", args.message)
        if args.status:
            store.set_status(args.thread_id, args.status, "agent")
    except (PermissionError, KeyError, DiagramValidationError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    suffix = f", status={args.status}" if args.status else ""
    print(f"replied to {args.thread_id}{suffix}")


def cmd_servers(args: argparse.Namespace) -> None:
    servers = running_servers()
    if args.json:
        print(json.dumps(servers, indent=2))
    elif not servers:
        print("no doc-review servers running")
    else:
        for server in servers:
            print(_server_line(server))


def cmd_stop(args: argparse.Namespace) -> None:
    servers = running_servers()
    if args.all:
        targets = servers
    elif args.port is not None:
        targets = [s for s in servers if s["port"] == args.port]
    elif args.pid is not None:
        targets = [s for s in servers if s["pid"] == args.pid]
    else:
        targets = servers if len(servers) == 1 else []
        if len(servers) > 1:
            print("several servers running -- pass --port, --pid or --all:", file=sys.stderr)
            for server in servers:
                print("  " + _server_line(server), file=sys.stderr)
            sys.exit(1)
    if not targets:
        print("no matching doc-review server running", file=sys.stderr)
        sys.exit(1)
    for server in targets:
        os.kill(server["pid"], signal.SIGTERM)
        print("stopped " + _server_line(server))


def cmd_pr_notes(args: argparse.Namespace) -> None:
    pr = pr_notes.fetch_pr_notes(args.number, Path(args.repo_dir))
    if args.json:
        print(json.dumps(pr, indent=2))
        return
    if pr["error"]:
        print(f"error: {pr['error']}", file=sys.stderr)
        sys.exit(1)
    print(f"#{pr['number']} {pr['title']} [{pr['state']}] {pr['url']}")
    for note in pr["notes"]:
        where = note["location"] or note["kind"] + (f" {note['state'].lower()}" if note["state"] else "")
        print(f"- {note['author']} {note['created_at'][:10]} {where}: {_truncate(' '.join(note['body'].split()), 200)}")


def running_servers() -> List[Dict]:
    # Only the Python process: a Bash(run_in_background) launch also leaves a shell whose command
    # line names doc_review.py, and killing that shell would leave the server running.
    ps = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=False)
    servers = parse_server_processes(ps.stdout)
    for server in servers:
        server["port"] = _listen_port(server["pid"])
        server["cwd"] = _process_cwd(server["pid"])
    return servers


def parse_server_processes(ps_output: str) -> List[Dict]:
    servers = []
    for line in ps_output.splitlines():
        parts = line.split()
        if len(parts) < 2 or not parts[0].isdigit() or Path(parts[1]).name in SHELL_NAMES:
            continue
        script_index = next((i for i, part in enumerate(parts) if part.endswith("doc_review.py")), None)
        if script_index is None or parts[script_index + 1: script_index + 2] != ["serve"] or "--static" in parts:
            continue
        doc = parts[script_index + 2] if len(parts) > script_index + 2 else ""
        servers.append({"pid": int(parts[0]), "doc": doc})
    return servers


def parse_listen_port(lsof_output: str) -> Optional[int]:
    for line in lsof_output.splitlines():
        match = LSOF_NAME_LINE.match(line)
        if match:
            return int(match.group(1))
    return None


def _listen_port(pid: int) -> Optional[int]:
    lsof = subprocess.run(["lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN", "-Fn"],
                          capture_output=True, text=True, check=False)
    return parse_listen_port(lsof.stdout)


def _process_cwd(pid: int) -> str:
    lsof = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True, check=False)
    return next((line[1:] for line in lsof.stdout.splitlines() if line.startswith("n")), "")


def _server_line(server: Dict) -> str:
    url = f"http://127.0.0.1:{server['port']}/" if server["port"] else "(no port yet)"
    return f"pid {server['pid']}  {url}  {server['doc']}  (cwd {server['cwd']})"


def _validate_if_diagram(base_dir: Path, store: SidecarStore, thread_id: str) -> None:
    # Edge Case E8 / Best Practices: a broken diagram edit must never be marked addressed.
    threads = store.load()["threads"]
    thread = next((t for t in threads if t["id"] == thread_id), None)
    if thread is None:
        raise KeyError(f"no thread {thread_id!r}")
    anchor = thread["anchor"]
    if anchor["kind"] == "diagram":
        _validate_diagram(base_dir / anchor["file"])


def _validate_diagram(file_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            result = subprocess.run(
                ["npx", "--yes", "@mermaid-js/mermaid-cli", "-i", str(file_path), "-o", str(Path(tmp) / "check.svg")],
                capture_output=True,
                text=True,
                timeout=MMDC_VALIDATION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise DiagramValidationError(f"could not run mermaid-cli to validate {file_path}: {e}") from e

    if result.returncode != 0:
        raise DiagramValidationError(f"{file_path} failed mermaid validation:\n{result.stderr.strip()}")


def _cli_resolved_thread(base_dir: Path, thread: Dict) -> Dict:
    anchor = thread["anchor"]
    quote = anchor.get("quote", "") if anchor["kind"] == "text" else (anchor.get("label") or anchor.get("source_id", ""))
    resolution = resolve_thread(base_dir, thread)
    return {
        "id": thread["id"],
        "status": thread["status"],
        "quote": quote,
        "resolution": resolution,
        "created_by": thread.get("created_by"),
        "replies": thread.get("replies", []),
        "follow_up": _has_follow_up(thread),
    }


def _has_follow_up(thread: Dict) -> bool:
    # The engineer replied after the agent's last reply -- the thread needs another answer.
    authors = [reply["author"] for reply in thread.get("replies", [])]
    return bool(authors) and authors[-1] == "engineer" and "agent" in authors


def _marker_candidate_files(doc_path: Path, threads: List[Dict]) -> List[str]:
    # comments takes only <doc>, so marker scanning auto-discovers diagrams via the project's
    # own Diagrams/ convention (ConfluenceDocs.md) rather than requiring them to be re-listed;
    # any other anchored file is picked up once a thread has pointed at it.
    files = {doc_path.name}
    diagrams_dir = doc_path.parent / "Diagrams"
    if diagrams_dir.is_dir():
        files.update(str(p.relative_to(doc_path.parent)) for p in diagrams_dir.glob("*.mmd"))
    files.update(thread["anchor"]["file"] for thread in threads)
    return sorted(files)


def _print_text(resolved: List[Dict], markers: List[Dict]) -> None:
    for item in resolved:
        resolution = item["resolution"]
        quote = _truncate(item["quote"])
        if resolution["status"] == "resolved":
            # An empty-space diagram pin (anchor_resolver.resolve_diagram_anchor) has no line --
            # it never referred to source content.
            location = f'{resolution["file"]}:{resolution["line"]}' if resolution.get("line") is not None else resolution["file"]
            print(f'{location} [{item["status"]}] {item["id"]}: {quote}')
        elif resolution["status"] == "ambiguous":
            lines = ", ".join(str(line) for line in resolution["candidate_lines"])
            print(f'AMBIGUOUS {item["id"]} [{item["status"]}] "{quote}" -- candidate lines: {lines}')
        else:
            heading = " > ".join(resolution.get("heading_path") or [])
            suffix = f" (was under: {heading})" if heading else ""
            print(f'ORPHANED {item["id"]} [{item["status"]}] "{quote}"{suffix}')
        _print_last_reply(item)
    for marker in markers:
        print(f'[inline-marker] {marker["file"]}:{marker["line"]}: {marker["text"]}')


def _print_last_reply(item: Dict) -> None:
    if not item["replies"]:
        return
    # The first reply is the comment itself; without it a replied-to thread loses what was asked.
    first = item["replies"][0]
    print(f'    comment {first["author"]}: {first["text"]}')
    if len(item["replies"]) == 1:
        return
    last = item["replies"][-1]
    follow_up = " (follow-up)" if item["follow_up"] else ""
    print(f'    last reply{follow_up} {last["author"]}: {last["text"]}')


def _truncate(text: str, limit: int = QUOTE_TRUNCATE_LENGTH) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def main() -> None:
    parser = argparse.ArgumentParser(prog="doc_review.py", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Render a doc + diagrams, live or --static")
    serve_parser.add_argument("doc")
    serve_parser.add_argument("diagrams", nargs="*")
    serve_parser.add_argument("--port", type=int, default=None)
    serve_parser.add_argument("--static", action="store_true")
    serve_parser.add_argument("--output")
    serve_parser.add_argument("--open", action="store_true")
    serve_parser.set_defaults(func=cmd_serve)

    comments_parser = subparsers.add_parser("comments", help="List comment threads resolved to file:line")
    comments_parser.add_argument("doc")
    comments_parser.add_argument("--status", choices=["actionable", "open", "ready", "addressed", "resolved", "all"], default="actionable")
    comments_parser.add_argument("--json", action="store_true")
    comments_parser.set_defaults(func=cmd_comments)

    reply_parser = subparsers.add_parser("reply", help="Add an agent reply, optionally setting status")
    reply_parser.add_argument("doc")
    reply_parser.add_argument("thread_id")
    reply_parser.add_argument("message")
    reply_parser.add_argument("--status", choices=["open", "ready", "addressed", "resolved"], default=None)
    reply_parser.set_defaults(func=cmd_reply)

    servers_parser = subparsers.add_parser("servers", help="List running live doc-review servers")
    servers_parser.add_argument("--json", action="store_true")
    servers_parser.set_defaults(func=cmd_servers)

    stop_parser = subparsers.add_parser("stop", help="Stop a live server (the only one, or by --port / --pid / --all)")
    stop_selector = stop_parser.add_mutually_exclusive_group()
    stop_selector.add_argument("--port", type=int, default=None)
    stop_selector.add_argument("--pid", type=int, default=None)
    stop_selector.add_argument("--all", action="store_true")
    stop_parser.set_defaults(func=cmd_stop)

    pr_notes_parser = subparsers.add_parser("pr-notes", help="Print a PR's comments, review bodies and inline notes (gh)")
    pr_notes_parser.add_argument("number", type=int)
    pr_notes_parser.add_argument("--repo-dir", default=".", help="a folder inside the PR's git repository")
    pr_notes_parser.add_argument("--json", action="store_true")
    pr_notes_parser.set_defaults(func=cmd_pr_notes)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
