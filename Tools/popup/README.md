# Popup

An OS-level notification or modal dialog to get the engineer's attention — macOS only
(`osascript`, text passed as argv, never spliced into AppleScript). Modelled on WorkAutomator's
`OsaMacActions` (`~/Documents/Projects/WorkAutomator/src/workautomator/clients/mac.py`).

## Direct use

```bash
python3 Tools/popup/popup.py notify "Build" "Typecheck finished clean"
python3 Tools/popup/popup.py dialog "Build" "Push the branch?" --buttons "Push,Not now" --timeout 120
```

`dialog` blocks until a button is clicked or `--timeout` seconds pass (prints the clicked button,
or an empty line on timeout/cancel). `notify` returns immediately.

## Scheduling a popup for when a turn finishes

`arm` records a pending popup for the current session instead of firing it immediately; the
installed `hook-stop` Stop hook fires and clears it the next time the agent finishes replying.
Use this when the engineer says "let me know when you're done with this" at the start of a long
operation:

```bash
python3 Tools/popup/popup.py arm "Migration finished" --title "GameProgressSaveSlim"
```

Omit `--buttons` for a plain banner; pass `--buttons "A,B"` to arm a blocking dialog instead.
`--session-id` defaults to `$CLAUDE_CODE_SESSION_ID`, set by Claude Code in every tool call's
environment, so it rarely needs passing explicitly. The request is stored at
`<tmp>/claude-popup-<session_id>.json` and deleted once fired; only one popup can be armed per
session at a time — arming again overwrites the pending one.

## Install

Added to every host project by `../setup/install.py install` as an `async` Stop hook (see
`../setup/settings.core.json`); re-run it after pulling this tool to pick up the hook in a
project installed before it existed.
