# Doc Review Tool

`Tools/doc-review/` previews a document and its Mermaid diagrams as a tabbed page on your own
machine and lets you comment on them before anything is published. Comments are stored next to
the doc, and the agent reads and answers them from the command line. Everything stays local:
the server listens on `127.0.0.1` only. Plain Python 3 (standard library only); marked, mermaid
and svg-pan-zoom load from CDNs in the browser.

## Commands

| Command | What it does |
|---|---|
| `doc_review.py serve <doc.md> [<diagram.mmd>...] [--port N] [--open]` | Live server. One tab per file, live reload on save, in-page comments. Prints the URL |
| `doc_review.py serve <doc.md> ... --static [--output PATH] [--open]` | Writes a single HTML preview (default `_doc_review_preview.html` next to the doc). No server, no comments |
| `doc_review.py comments <doc.md> [--status actionable\|open\|ready\|addressed\|resolved\|all] [--json]` | Lists comment threads resolved to `file:line`, plus inline `@CLAUDE:` markers. The default, `actionable`, lists open and ready threads plus follow-ups and ends with a `N threads hidden` line for the rest; use `--status all` to see every thread. Text mode prints each thread's original comment and, when there are replies, the last one (author and text) under it, so agents rarely need `--json`; `--json` carries `created_by`, the full `replies` list (author, text, at), `follow_up` and the `hidden` count. A follow-up (the engineer replied after an agent reply) is selected by every `--status` filter, so a reply on an addressed thread still shows under `--status open` |
| `doc_review.py reply <doc.md> <thread_id> "<message>" [--status addressed]` | Adds an agent reply, optionally marking the thread addressed |
| `doc_review.py servers [--json]` | Lists the running live servers: pid, URL, doc and folder. Only the Python server process, not the shell that launched it |
| `doc_review.py stop [--port N \| --pid N \| --all]` | Stops a live server (SIGTERM). With no selector it stops the only one running and refuses when there are several. Used by `/kill-server` |
| `doc_review.py pr-notes <PR> [--repo-dir DIR] [--json]` | Prints a PR's conversation comments, review bodies and inline notes, oldest first, via `gh`. Used by `/feature-pr` |

`Tools/mermaid-preview/mermaid_preview.py` is the older entry point. It forwards to
`serve --static`.

## Commenting in the page

In live mode, select text in a Markdown tab or click a diagram node, edge or empty space to start
a comment. The sidebar groups threads as Drafts, Active, Orphaned (the anchored text or node is
gone) and Resolved. Each thread moves open → ready → addressed → resolved. The engineer marks a
thread ready for the agent, and the agent replies and marks it addressed. Threads live in
`<doc>.review.json` beside the doc. Unsent drafts survive a reload.

## Progress tab

When the served doc's folder contains a `<Name>_Progress.md` (a CreateFeature feature folder),
a **Progress** tab is added first, automatically. `/start-preview-server <Name>` opens a feature this
way, with its TDD and diagrams:

- **Phases and steps.** Phases 1–8 and their gates come from `Processes/CreateFeature/index.md`.
  The steps are the `##` headings of each `Phase*.md` file.
- **Green ✓.** A phase is complete when the progress file has a gate handoff block for it, and
  then all its steps are checked. Steps of the current phase come from the progress file's
  `step_status:` block (`  1b: in_progress` shows `~`, `done` shows ✓), which the agent updates
  as it starts and finishes each step. Keys are the step's key (`1b`, `Step 3`) or its title.
  Without that block, a step is checked when the checkpoint's `done` list mentions it — an
  approximate match. A skipped phase stays unchecked even when later phases are done.
- **Development phases.** Each `### V<n> — …` heading under the TDD's `## Development plan`
  is listed under Phase 4 with two collapsibles. **Tasks** lists the rows of that phase's table
  as done (✓), partial (~) or not started (○), labelled by the Title column (else Task) with
  status from the Status column. It starts open for the first V-phase with unfinished tasks.
  **PR notes** lists the conversation comments, review bodies and inline comments of the PRs
  linked to that phase. Link them in the progress file:
  `pull_requests:` then `  V0: [9923, 9930]`. Notes are fetched with `gh` and refreshed every
  5 minutes. A gh failure shows as an error under that PR.
- **Task list.** When the TDD has no V-phases, tasks in `<Name>_TaskList.md` are listed under
  Phase 4 instead. Both task forms are read: the one-line `- {id:, status:, title:}` form and
  the multi-line `- task: "<text>"` form with an indented `status: "[x]"` line (no id).
- **Batches.** When `/publish-batch` has planned a task's batches, the task shows a
  `batch N of M` pill (N = `merged` + 1, M = the number of `plan` titles). The pill links the
  batch's `open_pr` on GitHub, and hovering it shows the batch title. After the last batch
  merges it reads `batches done`. The task is matched by id: the TDD table's `#` column, or the
  task list's `{id:}`. TDD rows without a `#` column and multi-line task-list entries have no
  id, so they never show a batch.
- **TDD sections.** Phase 1's "Sub-phase 1b" step lists each `### Section: <Name>` heading of
  `Phase1_Intake.md` as a checklist. The progress file's `tdd_sections:` block sets each one:
  `drafting` (written, not yet agreed) shows `~`, `approved` (the engineer agreed it) shows ✓,
  anything unlisted shows ○. Without that block the tab guesses: a section is checked when the
  TDD has a matching heading (case, punctuation and `[Optional…]` ignored; a prefix such as
  `## Development plan` also matches) whose body differs from the same section in
  `Templates/TDD_Template.md` and is not only `[…]` placeholders such as `[TBD]`. Once Phase 1's
  handoff block is written, every section is checked.
- **Consistency findings.** Once the Gate 1 handoff block is written, its
  `consistency_findings` list (Sub-phase 1c's findings, each tagged ✅/⚠️/❌ with its outcome)
  is shown as a nested list under Phase 1's "Sub-phase 1c" step. Before that, or when the list
  is empty, the step shows nothing extra.
- **Current phase.** Highlighted in blue.
- **Gate to pass next, in red.** This is the current phase's gate until its handoff block is
  written, then the next unfinished phase's.

The tab refreshes whenever the progress file, the task list, the TDD, the TDD template or a
CreateFeature phase file changes, and every 5 minutes while PRs are linked. Static mode includes the tab without refreshing.

## Performance tab

When the project has tracked sessions (`GitIgnoreReports/Sessions/`, or `$SESSION_REPORTS_ROOT`),
a **Performance** tab is added last, on every served doc. It reads each session's `session.json`
breakdown: the same estimated token-by-category numbers the retrospective charts.

- **Overview.** Sessions, total tokens, average and median per session, standard deviation, and
  the standardized-operations share.
- **Bell curve.** A histogram of session totals with a normal curve fitted to log10(tokens). Totals
  span orders of magnitude, so the axis is logarithmic. One dot per session; the active one is yellow.
- **Tokens by category.** Total, average per session and share, across all sessions.
- **Doc review preview vs Miro/Confluence.** Tokens the `doc_review.py` / `mermaid_preview.py`
  calls cost, an estimate of the same operations through the Miro/Confluence MCP tools (serve ≈
  page update + diagram upload, comments ≈ comment fetches, reply ≈ comment post; per-call averages
  of real MCP calls, in `token_breakdown.MIRO_CONFLUENCE_BY_COMMAND`), and the measured cost of
  the Miro/Confluence MCP calls sessions really made. Each session lists its own line. Shown only
  once a breakdown compiled after this change has a preview or MCP call.
- **Sessions, newest first.** One collapsible each, with its category table. The active session
  (no `ended_at`, `session.json` written in the last hour) is highlighted and open.

Sessions without a compiled breakdown are listed but left out of the statistics. The tab
refreshes whenever a `session.json` changes; the active session is as fresh as its last compile
(the Stop hook recompiles after replies).

**Feature scope.** Served from a feature folder (one with `<Name>_Progress.md`), the tab opens on
that feature's sessions, with a **<Feature> / All sessions** toggle. A session belongs to the
feature when its `session.json` is tagged with it — `session_lifecycle.py set --feature <Name>`,
which /feature and /resume-work pass, and /small-task, /bug-fix and /run-investigation-mode pass
when the work is for an in-progress feature — or when its folder is listed under `sessions:` in
the Progress file (matched by the id8 suffix). To add a past session, run
`set --session-id <id> --feature <Name>`. The tab also refreshes when the Progress file changes.

## Mermaid syntax and validation

When preparing diagrams for this preview, avoid literal semicolons in sequence-diagram
message text: Mermaid treats them as statement separators. Use commas, or encode an
intentional semicolon as `#59;`. Validate diagrams with an available Mermaid renderer before
claiming they render successfully. If renderer tooling or browser inspection is unavailable,
report that limitation explicitly and request an engineer rendering check.

## Tests

```bash
python3 -m unittest discover -s Tools/doc-review/tests -p 'test_*.py'
node Tools/doc-review/tests/smoke/review_ui_smoke.js   # needs Chrome + puppeteer in the npx cache
```

**Source files:** `Tools/doc-review/` · [[CreateFeature/index|CreateFeature]]

---

← [[11_Contributing|Contributing]] · [[00_Overview|Overview]]
