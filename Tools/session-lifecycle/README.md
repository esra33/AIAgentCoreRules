# Session Lifecycle

Per-session metrics for Claude Code and Codex: tokens, logged inaccuracies and iterations, and a router
trace (which rule and process files were loaded, in order, read from the session transcript).

## Output

```
<project>/GitIgnoreReports/Sessions/<YYYY-MM-DD_HHMM>_<lane>_<name>_<id8>/   # lane and name once set
  session.json   state
  typecheck.json typecheck baseline, last .cs edit, end-check blocks, cslint counts (hook-edit / hook-lint / hook-stop-check)
  metrics.md     rendered report
  retro.md       written by /end-session; "## Applied" tracks each proposal's status
  retro.html     rendered from retro.md by retro_page.py (`retro`, `open`), with token charts
  tokens/        session-support per-session token report
```

`<root>/hooks.log` gets one line per hook run (event, session, payload cwd, outcome) — the first
place to look when a session's metrics were not updated on exit.

The root is `<project>/GitIgnoreReports/Sessions`, where `<project>` is the main checkout found by
`../setup/project_root.py` from `CLAUDE_PROJECT_DIR` (hooks) or the current checkout (commands run
by the agent). Never the shell's cwd or the payload's `cwd`: both follow the agent's `cd`, and a
root built from them nested duplicate session folders. A cwd inside `GitIgnoredExternals/<layer>`
(a symlinked repo of its own) resolves to the host project, not the layer. A root that contains
`GitIgnoreReports` twice is refused. Regression tests for root resolution and closed-session
renames: `python3 -m unittest discover -s Tools/session-lifecycle/tests -p 'test_*.py'`. Override the root with `SESSION_REPORTS_ROOT` or `--reports-root`.

Call shape: `session_lifecycle.py [--reports-root DIR] <subcommand> …`. `--reports-root` is a
global option and goes before the subcommand. After it, argparse rejects it as an unrecognized
argument.

Folders are created only when there is something to record: on the first `set`, `note` or
`compile`, or by `hook-stop` / `hook-end` once the transcript has a typed prompt. `hook-start`
creates nothing. `hook-end` deletes a folder that is still empty: no lane, title, name or notes,
no tokens, no retro, and no typed prompt. `prune-empty [--dry-run]` applies the same test to
every folder, for one-off cleanup.

## Install in a host project

1. Hooks in `<project>/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{ "hooks": [{ "type": "command",
      "command": "cd \"$CLAUDE_PROJECT_DIR\" && python3 <path-to>/Tools/session-lifecycle/session_lifecycle.py hook-start" }] }],
    "SessionEnd":   [{ "hooks": [{ "type": "command",
      "command": "cd \"$CLAUDE_PROJECT_DIR\" && python3 <path-to>/Tools/session-lifecycle/session_lifecycle.py hook-end" }] }],
    "Stop":         [{ "hooks": [{ "type": "command", "async": true,
      "command": "cd \"$CLAUDE_PROJECT_DIR\" && python3 <path-to>/Tools/session-lifecycle/session_lifecycle.py hook-stop" }] }]
  }
}
```

`../setup/settings.core.json` is the full wiring the installer merges, including the hooks below.

| Subcommand | Event (matcher) | Timeout | What it does |
|---|---|---|---|
| `hook-start` | SessionStart | 30 | Session tracking block for the agent |
| `hook-end` | SessionEnd | 60 | Final compile; deletes a still-empty folder |
| `hook-stop` | Stop, `async` | 30 | Throttled recompile after each reply |
| `hook-stop-check` | Stop, sync | 20 | Blocks the stop once when a .cs file changed after the last `typecheck.py` run |
| `hook-prompt` | UserPromptSubmit | 10 | Idle-gap cost note; context-size warning |
| `hook-bash` | PreToolUse (`Bash`) | 10 | Read-not-cat reminder for rule files; codeindex/usages for a C# grep |
| `hook-edit` | PreToolUse (`Edit\|Write`) | 30 | First .cs edit: typecheck baseline; every .cs edit: `last_cs_edit` |
| `hook-lint` | PostToolUse (`Edit\|Write`) | 10 | `cslint.py` on the edited .cs file's changed lines |

**Typecheck and lint hooks.** On the session's first `.cs` edit inside a Unity project, `hook-edit`
runs `typecheck.py --files <file>` on the still-untouched tree (~3-4 s) and hands the agent the
result as `additionalContext`, so pre-existing errors are not blamed on the change. Every `.cs`
edit records `last_cs_edit`. `hook-lint` runs `../unity-tools/cslint.py` on the edited file's
changed lines and returns violations (at most 15 rows) as `additionalContext`; silent when clean.
`hook-stop-check` reads the transcript, subagent transcripts included, for the last `typecheck.py`
run (`--list` runs do not count); when a `.cs` edit is newer it returns `{"decision": "block",
"reason": …}` with the literal command to run. It never blocks when `stop_hook_active` is set, and
returns at once when the session has no `.cs` edit. State lives in the sidecar `typecheck.json`, not
session.json, because the async `hook-stop` compile rewrites session.json and would drop a
concurrent update. `compile` copies it into session.json `typecheck`, adds `runs` (each
`typecheck.py` call and its result, read from the transcript), and metrics.md renders it as
*Typecheck*. Tests: `tests/test_typecheck_hooks.py`.

`SessionEnd` only fires when the Claude process exits (clear, resume, logout, exit). A session
the app marks completed after going idle never exits, and Claude Code has no idle hook. `Stop`
fires after every main-agent reply, and `hook-stop` recompiles then (at most every 2 minutes,
async, never marking the session ended), so metrics stay current however the session ends.

### Hook output reach

Who sees what a hook prints. Check here before designing a warning or a nudge.

| Hook | Reaches the agent | Reaches the engineer |
|---|---|---|
| SessionStart | stdout and `hookSpecificOutput.additionalContext`. Re-fires with source `clear` or `compact`, so it can re-inject context after either | JSON `systemMessage` |
| UserPromptSubmit | stdout and `hookSpecificOutput.additionalContext` — the only way to reach the agent mid-session | JSON `systemMessage` |
| PreToolUse | `hookSpecificOutput.additionalContext` | JSON `systemMessage` |
| PostToolUse | `hookSpecificOutput.additionalContext` | JSON `systemMessage` |
| Stop (async, `hook-stop`) | Nothing — it runs `async`, so its output reaches no one | Nothing |
| Stop (sync, `hook-stop-check`) | `{"decision": "block", "reason": …}` — the reason reaches the agent, which keeps working; `stop_hook_active` marks the retry | JSON `systemMessage` |
| Any hook | — | JSON `systemMessage` reaches the engineer only, never the agent |

No hook or model action can run `/clear` or `/compact`; the most a hook can do is tell the agent
to offer one. The auto-compact threshold is set with the `autoCompactWindow` setting or
`/autocompact <tokens>`.

2. Symlink `Skills/start-session`, `end-session`, `inaccuracy`, `iteration` into
   `<project>/.claude/skills/`.

## Commands

```bash
python3 session_lifecycle.py set --name "HUD crash" --lane bug_fix --work-type bug_fix --title "Crash on HUD open"
python3 session_lifecycle.py note --kind inaccuracy "Guessed PrizeManager signature"
python3 session_lifecycle.py note --kind inaccuracy --source agent "Diffed branch tips without the merge-base"
python3 session_lifecycle.py compile [--final]
python3 session_lifecycle.py open
python3 session_lifecycle.py path
python3 session_lifecycle.py retro [--folder <id8>] [--open]
python3 session_lifecycle.py retro [--folder <id8>] --mark 2 --status applied --note "<file> — <what changed>"
python3 session_lifecycle.py retro --from "$CLAUDE_JOB_DIR/tmp/retro.md"
python3 session_lifecycle.py file --to MetaReviews "$CLAUDE_JOB_DIR/tmp/<date>_MetaReview.html" "$CLAUDE_JOB_DIR/tmp/<date>_Tickets.md"
```

`retro --from <path>` and `file --to MetaReviews <paths>` are for background sessions. Once their
worktree is gone, Claude Code's isolation guard refuses Write in the shared checkout, so the agent
writes to its job tmp dir and files the result through this script. `retro --from` copies the
file to the session's `retro.md`, overwriting it, and then carries on as a plain `retro` call
(`--mark` and `--open` still apply). `file` copies each path into `GitIgnoreReports/<to>/` under
its own name. Both refuse a missing or empty source before copying anything, and print only the
destination paths.

`retro` renders `retro.html` (a standalone page, no external assets, light and dark) from
`retro.md` and prints each proposal's status. `--mark N --status applied|skipped|pending` first
rewrites proposal N's line in the `## Applied` section, creating the section with every other
proposal `pending` when it is missing. Without `--note`, the old note is kept only if the status
is unchanged. The line shape is the one `session_meta_report.py` reads. `--folder` targets
another session's retro: a path, a folder name, or a unique part of one such as the session id's
first 8 characters, so a proposal resolved in a later session can be marked where it was raised.
`open` re-renders the page and opens it with metrics.md.

`compile` records `model` in session.json — the model behind most of the transcript's assistant
messages, e.g. `claude-sonnet-5` — and shows it as the *Model* row in metrics.md, so per-phase
model reviews read session.json instead of every transcript.

`compile` also runs `token_breakdown.py` and stores `breakdown` (tokens per category, the
standardized-operations total, and the savings per mechanism) and `comparison` (every session's
de-duplicated total, for the average) in session.json. metrics.md renders them as *Token breakdown
(estimated)*, and retro.html renders them as a *Token charts* section before Cost: this session vs
the average/median/lane average, the standardized-operations share, and what saved tokens and
round-trips. Each model call is counted once, here and in the token report (both de-duplicate by
`message.id`); the charts compute every session's total from its transcript. A tool result costs
its size × every later call that re-reads it. The savings assumptions are in `AVOIDED_BY_TOOL`,
and `MIRO_CONFLUENCE_BY_COMMAND` for doc-review preview calls. The breakdown's `doc_review` block
holds the preview calls (count, tokens, per command), their Miro/Confluence estimate and
round-trips, and the measured Miro/Confluence MCP calls (`miro_confluence`); metrics.md prints it as
one line and the doc-review Performance tab charts it. Code-graph calls (`curl …/api/type|graph|search`)
are the *code-graph API* saving, against the grep work in `GREP_BY_CODE_GRAPH_ROUTE`. The `missed`
block (`missed_opportunities()`) counts lookups done by hand that the index answers — greps over C#
for a type or member name (`type_grep_suggestions`, passed into `analyse()` so the module stays
dependency-free), 2+ codeindex shape queries on one type, whole-file `.cs` reads never edited after —
with tokens/round-trips lost and up to 5 examples per kind; metrics.md renders it as *Missed index
opportunities* (`missed_lines`). Main thread only.
To add a saving mechanism, add its name to `token_breakdown.SAVINGS` and fill `savings[name]` in
`analyse()`; metrics.md (`session_lifecycle.py` `breakdown_lines`) and retro.html
(`retro_page.savings_chart`) render every entry and its assumptions generically.

retro.md stays the source of truth. A page opened from disk cannot write back, so each open
proposal has a button that copies its `retro --mark … --status applied` command.

`note --source` records who logged the entry: `engineer` (default, the
`/iteration` skill), `agent` (the agent's own self-correction) or `retro` (back-filled by
`/end-session` from the retro's Corrections). Older entries without a source count as `engineer`.

`set --lane` on a session that already has a different lane appends `{at, from, to}` to
`lane_history` in session.json; metrics.md lists it under *Lane changes*.

`--name` is the engineer-given session name (`/start-session <name>`). It is slugged into the
folder name, which `set` renames, and heads metrics.md.

`--work-type` (`bug_fix | small_feature | large_feature | feature | question | other`) records what
the work is, separately from the lane that ran it, so the meta-analysis can compare cost by kind of
work. Until it is passed explicitly it follows the lane (`small_task → small_feature`, `large_task →
large_feature`, `investigation → question`, others map to themselves) and `work_type_source` is `"lane"`; once explicit, later lane
changes no longer touch it. Changes are kept in `work_type_history` and listed under *Work type
changes*.

**Adding a lane or work type** — every place that lists them must change together:

- `Rules/MetaRouter.md` — `mode_fork`, the `work_type` line, routing table, `commands`
- `session_lifecycle.py` — `LANES`, `WORK_TYPES`, `LANE_WORK_TYPE`, `LANE_COMMAND`
- `../session-analysis/session_meta_report.py` — `LANES`, `LANE_WORK_TYPE`
- `Skills/start-session/SKILL.md` — lane list and `work_type` definitions; `Skills/end-session/SKILL.md` — `depth`
- `Documentation/02_WorkModes.md`, `07_SessionTracking.md`, `08_Commands.md`, and this README

`tests/test_lanes.py` fails when the two Python files' tables disagree or a lane has no default
work type or fresh-session command.

`--session-id` defaults to `$CODEX_THREAD_ID` in Codex or `$CLAUDE_CODE_SESSION_ID` in Claude Code;
only the legacy Claude path falls back to the newest transcript for the project. An ID with no folder is an error — the script never falls
back to another session's folder.
A session launched from a subdirectory has its transcript filed under that directory's
`~/.claude/projects/<encoded-dir>/`, not the project root's. When the expected path is missing,
the script finds `<session_id>.jsonl` under any project folder, at hook-start and again at compile.
Hook subcommands always exit 0 so a failure never blocks a session.

## Limits

- Router-trace rows from `Read` are exact; rows from shell commands are inferred from paths in
  the command text, so a `grep` counts as a load and a path held in a shell variable is missed.
- Token numbers come from `Tools/session-support`, driven through its Python API with this session's
  transcript as an explicit rollout — so they are exact even when other sessions are running. The
  vendored package is not modified; if an upstream update renames `load_monitor`,
  `support_report`, `generated_session_reports` or `SessionMonitor.explicit_rollout`, tokens show as
  "unavailable (report failed: …)" until this script is updated. Upstream `engineering-support-kit`
  should still gain a `report --session-id` flag so other consumers get the same.
- `Started` is the transcript's first entry; `Tracking since` is when the hook first ran (they differ
  for sessions resumed from before the hooks were installed).


### HTML fallback when tracking is unavailable

Retrospective HTML rendering does not require session tracking. If `set` or `compile --final`
fails because the transcript or session is unavailable, continue the retrospective and mark
metrics and the router trace unavailable. Never invent a session folder or use another session's
metrics. Save `<FeatureName>_<Phase>_Retro.md` in the feature working folder; for other lanes,
save a uniquely named retrospective under the project's `GitIgnoreReports/Retrospectives/`.
Then always render and open the saved Markdown with:

```bash
python3 session_lifecycle.py retro --path "<saved-retrospective.md>" --open
```

This bypasses session lookup and writes a matching `.html` beside the Markdown without copying
or renaming the source. Missing metrics do not block rendering; charts without data are omitted.
The proposal buttons use `retro --path` too, so later `--mark` updates the original Markdown and
re-renders its page. `--path` cannot be combined with `--folder` or `--from`. If compilation fails
but the current session folder is known, use its actual retrospective path. Open any separately
available sanitized usage report alongside the HTML; do not stop at opening Markdown alone.
If rendering or opening fails, report that failure and link the saved artifacts.

## Codex session tracking

The lifecycle tracker accepts Codex rollouts as well as Claude transcripts. In Codex,
`CODEX_THREAD_ID` selects the exact thread; `--session-id` can select a known thread explicitly.
It never picks the newest Codex thread. Missing or ambiguous rollouts fail without attaching
another session's data. Rollouts are located below `$CODEX_HOME/sessions` (default
`~/.codex/sessions`). Do not pass `unknown` or invent an ID.

Run the existing commands from the host checkout:

```bash
python3 <lifecycle-script> hook-start
python3 <lifecycle-script> set --lane other --work-type other --title "Session tooling"
python3 <lifecycle-script> note --kind inaccuracy --source agent "Description of correction"
python3 <lifecycle-script> compile
```

Use the appropriate lane/title for the actual task. `compile --final` belongs at session end.
Session folders contain the agent type, notes, metrics and sanitized token reports. The existing
session-support Codex parser supplies usage; cumulative token events must not be summed.
Codex shell reads, including supported nested JavaScript exec commands, produce heuristic
Bash rows in the router trace. Main-thread trace coverage does not imply complete child-agent
trace coverage. Detailed standardized-operation attribution and comparison charts remain
unavailable for Codex rather than showing misleading zeros. Token reports may still include
child-agent telemetry supported by session-support.

These parser changes do not install automatic hooks. Current Codex supports a trusted project
`.codex/hooks.json` with `SessionStart`, `Stop` and `SessionEnd` command hooks calling
`hook-start`, `hook-stop` and `hook-end`. Hook payloads supply `session_id` and `transcript_path`.
Use the resolved lifecycle script path; preserve any existing hooks. Configure Stop with an
adequate timeout (for example 30 seconds), and SessionEnd with its supported maximum of 3
seconds. The Stop hook keeps metrics current even when closing a window does not end a thread.
Trust/reload the project hooks in Codex before expecting automatic execution. No Claude hook
execution is implied by a Codex skills installation.

Reference: https://learn.chatgpt.com/docs/hooks . Transcript formats are not a stable hook API;
keep synthetic regression fixtures and report parser failures as unavailable. Without a usable
transcript, retain the sanitized usage report and `retro --path` HTML fallback.

