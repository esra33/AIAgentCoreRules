
This project contains general rules that can be used by AI agents to better
help with the development of other projects.

## Installation

Requires Claude Code (or Codex), git and stock `python3`. Clone this repository outside the host
project, then run the installer from inside the project:

```bash
git clone git@github.com:aramirezJC/AIAgentCoreRules.git ~/Projects/AIAgentCoreRules
cd <host project>
~/Projects/AIAgentCoreRules/Tools/setup/install.sh check   # preview, writes nothing
~/Projects/AIAgentCoreRules/Tools/setup/install.sh         # install
```

The first run links the clone as `<project>/GitIgnoredExternals/AIAgentCoreRules`, asks where
the project's AI metadata should live, and sets up `.claude/settings.json` (session hooks,
worktree settings), `.claude/skills/`, `CLAUDE.md` and `ai-agent-core.json`. Keep
`GitIgnoredExternals/`, `.claude/`, `CLAUDE.md` and `GitIgnoreReports/` out of the project
repository through your **global** gitignore (patterns `*GitIgnore*` and `*CLAUDE*`); the
installer warns when `GitIgnoredExternals/` is not ignored. Restart Claude Code in the project afterwards.

Run the first install yourself, in a terminal, not through Claude: it asks a question (Claude's
shell and the `!` prefix have no TTY, so it stops), it writes the hooks and permissions in
`.claude/settings.json`, and the session that ran it cannot load what it installed until it is
restarted. Asking Claude to run `install.sh check` and explain the preview is fine, and so is
letting it re-run the installer for an update.

```bash
# One-time global gitignore setup, if you have none yet
git config --global core.excludesfile ~/.gitignore_global
printf '*GitIgnore*\n*CLAUDE*\n' >> ~/.gitignore_global
```

To verify, start a new Claude Code session in the project: a **Session tracking (started)**
block appears in the agent's context, and `/feature`, `/end-session` and the other commands are
available.

- Run the script with any shell (bash, zsh, sh); do not `source` it.
- Scripts and CI: `install.sh --metadata-location externals --defaults` never prompts.
- Codex: add `--agent codex` (or `--agent both`).
- From elsewhere: `install.sh --project <path> …`.
- A worktree made by hand with `git worktree add`: `install.sh prepare-worktree <path>` adds its
  symlinks.
- Updating: `git pull` in the clone, then re-run
  `GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.sh` — it is safe to re-run.

Details: [Setup](Documentation/01_Setup.md) and the [setup README](Tools/setup/README.md).

## Session Lifecycle

`Tools/session-lifecycle/session_lifecycle.py` tracks every Claude Code session in the host
project's `GitIgnoreReports/Sessions/<date>_<lane>_<name>_<id>/` folder: lane, work type, tokens (via
`Tools/session-support`), logged inaccuracies and iterations, and a router trace of which rule
files were actually loaded, read from the session transcript. A SessionStart hook starts it, a
SessionEnd hook compiles it, and `/end-session` adds a retrospective. Hook setup is in
`Tools/session-lifecycle/README.md`.

`Tools/session-analysis/session_meta_report.py` reads all of those session folders and writes
`GitIgnoreReports/SessionAnalysis.html`: a token bell curve, issue heat maps, proposed changes
with their status, and what to improve next. See `Tools/session-analysis/README.md`.

## Feature State and Persistent Preview

Feature lifecycle skills use a shared Python tool to read and update one feature at a time.
Each feature directory contains authoritative `state.json`, with a versioned schema,
revision checks, validated lifecycle transitions, locked atomic updates, and focused reads
that avoid loading unrelated features into agent context. Progress Markdown is a generated
view; agents must not edit it or the JSON directly. Home and lifecycle commands derive the
active-feature list from those files rather than maintaining a separate registry.

The persistent localhost preview server runs independently of agent sessions, once per
project. Home lists active features; selecting one populates Plan, TDD, GDD, Class Diagram,
Flow Diagram, and LLM Performance. Missing artifacts show placeholders. Feature selection
is scoped to the browser URL, so separate windows can review different features.

Comments live in each feature's `review.json`, with target-file paths, anchors, replies and
statuses. They remain separate between features and independent of which document is opened
first. Inline `@CLAUDE` source-marker scanning has been removed; existing markers are left
untouched. Standalone document review remains available.

From a host project using the `GitIgnoreExternals/AIAgentCoreRules` layout:

```bash
# Explicit migration: inspect the dry-run report before applying.
python3 GitIgnoreExternals/AIAgentCoreRules/Tools/feature-state/feature_state.py migrate --root Assets/GitIgnoreAssets/Features
python3 GitIgnoreExternals/AIAgentCoreRules/Tools/feature-state/feature_state.py migrate --root Assets/GitIgnoreAssets/Features --apply

# Start or reuse the project's server; status prints its URL when running.
bash GitIgnoreExternals/AIAgentCoreRules/Tools/doc-review/preview-control.sh start
bash GitIgnoreExternals/AIAgentCoreRules/Tools/doc-review/preview-control.sh status
bash GitIgnoreExternals/AIAgentCoreRules/Tools/doc-review/preview-control.sh stop
```

Adjust the external-root spelling for the host project. The launcher also accepts
`--project <path>`. It retains project-local runtime metadata and logs, verifies process
ownership before stopping, and reuses an existing healthy instance on repeated starts.

Legacy features require explicit migration. The importer preserves original progress and
comment sidecars in backups, records provenance, merges comments into the feature store,
and refuses ambiguous or conflicting data. Already migrated features are skipped without
overwriting subsequent state updates. The preview labels legacy features as requiring
migration until conversion succeeds.

See [Feature State](Documentation/13_FeatureState.md),
[Document Review](Documentation/12_DocReview.md), and the
[agent state protocol](Processes/FeatureState.md) for commands, migration limits and lifecycle
payloads. The [tool README](Tools/feature-state/README.md) includes focused-read and update examples.

## Code Graph

`Tools/code-graph/` serves a local, read-only browser view and JSON API over the codeindex
database (`<project>/Library/codeindex.sqlite`, built by `Tools/unity-tools/codeindex.py`):
search, an assembly → namespace → type tree, an inheritance graph and member lists with
`file:line`. One `curl` gives an agent a type's bases, derived types, members and location.

Run it from the host project root, not from `Tools/code-graph/` (that folder would become the
project, and `start` warns that no database exists there):

```bash
# Start or reuse the project's server; start prints the URL.
GitIgnoreExternals/AIAgentCoreRules/Tools/code-graph/code-graph.sh start
GitIgnoreExternals/AIAgentCoreRules/Tools/code-graph/code-graph.sh status
GitIgnoreExternals/AIAgentCoreRules/Tools/code-graph/code-graph.sh stop

curl -s "$URL/api/type?name=IEventManager&members=0"   # bases, derived types, location
```

Adjust the external-root spelling for the host project, as above. Options: `--project <path>`,
`--db <path>`, and `--refresh-cmd "<command line>"` to override what the page's **Force refresh
index** button runs. By default it runs `codeindex.py build --force` for the same project and
database; `--refresh-cmd ""` hides the button. The server outlives agent sessions, restarts itself
on the next `start` when the tool code or options changed, and keeps its state and logs in
`<project>/.code-graph/`. See the [tool README](Tools/code-graph/README.md) for the full API and
[Code Graph](Documentation/15_CodeGraph.md) for the page.

## Documentation

`Documentation/` holds Confluence-ready pages describing the framework (overview, setup, work
modes, each process, session tracking, commands, rules, host project layer, contributing).
File-name numbers give the page order. Update the matching page when a rule or process changes.
Pages use Obsidian wikilinks; `python3 Tools/docs-export/export_confluence.py Documentation`
writes a Confluence-ready copy to `GitIgnoreConfluenceExport/`.

## Skills

Install into a host project with `Tools/setup/install.sh` (run from the project; see
[Installation](#installation)). It links each folder into `<project>/.claude/skills/`, merges the
session hooks and worktree settings into `.claude/settings.json`, and is safe to re-run.

- `start-session`, `end-session`, `inaccuracy`, `iteration` — session lifecycle.
- `feature` — enters `Processes/CreateFeature`.
- `checkpoint`, `resume-work` — save and restore feature progress across sessions via
  the shared feature-state tool and per-feature `state.json`; `<FeatureName>_Progress.md`
  is generated for human review.
- `active-features`, `close-feature`, `reopen-feature` — list and manage feature lifecycle state.
- `start-preview-server`, `kill-server` — open and manage the persistent project preview.
- `discover` — subagent survey that returns a compact map.
- `audit` — rules compliance report for C# files.
- `land-worktree` — merge an agent worktree's branch into the current branch, test, then
  remove the worktree and branch (or roll back).
- `Skills/token-usage-reports/` packages the portable session-report workflow
  for sanitized Codex, Claude Code, Gemini CLI, and Junie token reports. It
  delegates to `Tools/session-support/` so report parsing has one implementation
  owner. Markdown reports can include one aggregate file plus one file per
  selected session.

## Portable Session Support

`Tools/session-support/` is a vendored, dependency-free local toolset for
Codex, Claude Code, Gemini CLI, and Junie session monitoring, sanitized
recent-session history, aggregate support reporting, and advisory split checks.

```bash
python3 Tools/session-support/session-support monitor status
python3 Tools/session-support/session-support --agent claude history
python3 Tools/session-support/session-support --agent gemini monitor status
python3 Tools/session-support/session-support --agent junie report
python3 Tools/session-support/session-support report
python3 Tools/session-support/session-support split
```

Copy `Tools/session-support/project.example.json` into the consuming repository
and configure project labels, session roots, helper prefixes, warning
thresholds, state storage, and continuation defaults. Do not commit agent
session files, local state, or generated reports.

The canonical portable implementation is maintained in
`engineering-support-kit`; `Tools/session-support/provenance.json` records this
copy's source and update policy.
