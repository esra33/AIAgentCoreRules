#!/usr/bin/env python3
"""Pop an OS-level notification or modal dialog to get the engineer's attention — call it directly
from the agent, a bash command, or a python script, or schedule it for when a session's current
turn finishes. Modelled on WorkAutomator's OsaMacActions: osascript invoked via argv, never
spliced into AppleScript text. macOS only.

Subcommands:
    notify     Banner notification. notify TITLE MESSAGE [--subtitle TEXT]
    dialog     Blocking modal dialog in front of every app; prints the clicked button, or nothing
               on timeout/cancel. dialog TITLE MESSAGE [--buttons "A,B"] [--default BUTTON] [--timeout SECONDS]
    arm        Schedules a popup for this session's next Stop hook instead of firing immediately —
               for "let me know when you're done with this". arm MESSAGE [--title TITLE]
               [--buttons "A,B"] [--timeout SECONDS] [--session-id ID]
    hook-stop  Stop hook. Fires and clears this session's armed popup, if any. Reads hook JSON on
               stdin for session_id. Never raises: a popup failure must not block the stop.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

_NOTIFY = """on run argv
    display notification (item 2 of argv) with title (item 1 of argv) subtitle (item 3 of argv)
end run"""

# System Events brings the dialog in front of every app; "giving up after" stops it blocking forever.
_DIALOG = """on run argv
    set theButtons to paragraphs of (item 3 of argv)
    tell application "System Events"
        activate
        set reply to display dialog (item 2 of argv) with title (item 1 of argv) buttons theButtons ¬
            default button (item 4 of argv) giving up after ((item 5 of argv) as integer)
    end tell
    if gave up of reply then return ""
    return button returned of reply
end run"""


def _osascript(script: str, *args: str, timeout: float | None = None) -> str:
    result = subprocess.run(
        ["osascript", "-", *args], input=script, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"osascript failed: {result.stderr.strip()}")
    return result.stdout.strip()


def notify(title: str, message: str, subtitle: str = "") -> None:
    _osascript(_NOTIFY, title, message, subtitle, timeout=10)


def dialog(title: str, message: str, buttons: list[str], default_button: str | None = None,
           timeout: int = 600) -> str | None:
    """Shows a modal dialog in front of all apps. Returns the clicked button, or None on timeout/failure."""
    default_button = default_button or buttons[-1]
    try:
        answer = _osascript(_DIALOG, title, message, "\n".join(buttons), default_button, str(timeout),
                             timeout=timeout + 30)
    except RuntimeError:
        # System Events denied, or some other osascript failure; fall back to a banner.
        notify(title, message)
        return None
    return answer or None


def _marker_path(session_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"claude-popup-{session_id}.json"


def arm(session_id: str, message: str, title: str = "Claude Code", buttons: list[str] | None = None,
        timeout: int = 600) -> None:
    _marker_path(session_id).write_text(json.dumps({
        "title": title, "message": message, "buttons": buttons, "timeout": timeout,
    }))


def fire_armed(session_id: str) -> None:
    """Fires and clears the armed popup for session_id, if one is pending. Silent no-op otherwise."""
    marker = _marker_path(session_id)
    if not marker.is_file():
        return
    try:
        request = json.loads(marker.read_text())
        if request.get("buttons"):
            dialog(request["title"], request["message"], request["buttons"], timeout=request.get("timeout", 600))
        else:
            notify(request["title"], request["message"])
    finally:
        marker.unlink(missing_ok=True)


def _read_hook_input() -> dict:
    if sys.stdin.isatty():
        return {}
    try:
        return json.load(sys.stdin)
    except ValueError:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Pop a notification or dialog to get the engineer's attention.")
    sub = parser.add_subparsers(dest="command", required=True)

    notify_p = sub.add_parser("notify", help="Banner notification")
    notify_p.add_argument("title")
    notify_p.add_argument("message")
    notify_p.add_argument("--subtitle", default="")

    dialog_p = sub.add_parser("dialog", help="Blocking modal dialog; prints the clicked button")
    dialog_p.add_argument("title")
    dialog_p.add_argument("message")
    dialog_p.add_argument("--buttons", default="OK", help="Comma-separated button labels")
    dialog_p.add_argument("--default", help="Must be one of --buttons; defaults to the last one")
    dialog_p.add_argument("--timeout", type=int, default=600)

    arm_p = sub.add_parser("arm", help="Schedule a popup for this session's next Stop hook")
    arm_p.add_argument("message")
    arm_p.add_argument("--title", default="Claude Code")
    arm_p.add_argument("--buttons", help="Comma-separated button labels; omit for a plain notification")
    arm_p.add_argument("--timeout", type=int, default=600)
    arm_p.add_argument("--session-id", default=os.environ.get("CLAUDE_CODE_SESSION_ID"),
                        help="Defaults to $CLAUDE_CODE_SESSION_ID")

    sub.add_parser("hook-stop", help="Stop hook: fires and clears this session's armed popup, if any")

    args = parser.parse_args()

    if args.command == "notify":
        notify(args.title, args.message, args.subtitle)
    elif args.command == "dialog":
        answer = dialog(args.title, args.message, args.buttons.split(","), args.default, args.timeout)
        print(answer or "")
    elif args.command == "arm":
        if not args.session_id:
            sys.exit("No session id: pass --session-id or set CLAUDE_CODE_SESSION_ID.")
        buttons = args.buttons.split(",") if args.buttons else None
        arm(args.session_id, args.message, args.title, buttons, args.timeout)
    elif args.command == "hook-stop":
        hook = _read_hook_input()
        session_id = hook.get("session_id")
        if session_id:
            try:
                fire_armed(session_id)
            except Exception:
                pass


if __name__ == "__main__":
    main()
