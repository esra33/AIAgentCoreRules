# Setup

How to install the core framework in a local checkout of a project. The core framework remains
local to your machine. On first install, choose whether the host project's AI metadata stays
local or lives in the project repository.

## 1. Clone the repository and run the installer

Clone **AIAgentCoreRules** outside the game project, then run its installer from the project:

```bash
git clone git@github.com:aramirezJC/AIAgentCoreRules.git <path to>/AIAgentCoreRules
cd <game project root>
<path to>/AIAgentCoreRules/Tools/setup/install.sh check   # preview
<path to>/AIAgentCoreRules/Tools/setup/install.sh         # apply
```

On the first run the installer links the clone as `GitIgnoredExternals/AIAgentCoreRules`, then
does everything in steps 2–4. Run `install.sh` with any shell; do not `source` it. Inside a
Claude Code session (`!` prefix or a hook), `CLAUDE_PROJECT_DIR` takes precedence over the cwd,
so the installer targets the session's project; pass `--project <path>` to install into another
project from there.

Run the first install yourself in a terminal. It asks where the metadata goes, and Claude's
shell has no TTY to answer. It also writes the hooks and permissions in `.claude/settings.json`,
and Claude Code must be restarted to load them. Claude can run `install.sh check` and explain
the preview, or re-run the installer for an update. Linking by hand
still works and is left alone:

```bash
mkdir -p GitIgnoredExternals
ln -s <path to>/AIAgentCoreRules GitIgnoredExternals/AIAgentCoreRules
```

`GitIgnoredExternals/`, `CLAUDE.md`, `.claude/` and `GitIgnoreReports/` should be ignored by
your **global** gitignore (for example the patterns `*GitIgnore*` and `*CLAUDE*`). Never add
them to the game repository's `.gitignore`.

## 2. Choose the host metadata location

The installer (steps 1 and 4) handles this. On a new install, it offers a picker:

1. `GitIgnoredExternals/AIMetaData/` (or `GitIgnoreExternals/AIMetaData/`) for local metadata.
2. `AIMetaData/` at the project root for metadata that can be committed with the project.

It creates starter `Rules/ProjectRules.md`, `SystemIndex.md`, and
`Setup/settings.host.json` files. Existing host layers stay where they are. In a script, pass
`install --metadata-location externals` or `install --metadata-location project`. The root
option requires git ignore rules that allow `AIMetaData/` to be committed.

## 3. Create CLAUDE.md

At the project root, import the three always-on core files, followed by the host project's
always-on files:

```markdown
@GitIgnoredExternals/AIAgentCoreRules/Rules/MetaRouter.md
@GitIgnoredExternals/AIAgentCoreRules/Rules/StopAndVerify.md
@GitIgnoredExternals/AIAgentCoreRules/Rules/CoreTags.md
@AIMetaData/Rules/ProjectRules.md
@AIMetaData/SystemIndex.md
```

Use the chosen host metadata path in these imports. On a new install, the installer creates
`CLAUDE.md` with the correct imports. Keep this list short — every always-on file costs context.

## 4. Run the installer

After the first install, re-run it through the linked copy:

```bash
GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.sh check   # preview
GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.sh         # apply
```

`install.sh` runs `install.py` with the same arguments; `python3 …/install.py` still works.

It merges `Tools/setup/settings.core.json` into `.claude/settings.json` (session hooks and the
worktree settings below), then each host layer's `Setup/settings.host.json`; links every layer's
skills into `.claude/skills/` (re-linking a skill that moved between layers, whose old link is now
dangling); and creates `CLAUDE.md` with the core and new host imports if it is missing.
It only adds or updates what the fragments define, backs `settings.json` up to
`settings.json.bak` before changing it, and is safe to re-run — run it again after pulling
AIAgentCoreRules or the host layer. Details: [[Tools/setup/README|setup README]].

The session hooks never block a session — if tracking fails, Claude Code carries on. The one
deliberate exception is the synchronous `Stop` check: after a `.cs` edit with no later
`typecheck.py` run it blocks the stop once and tells the agent to run it. Session
folders are written to `GitIgnoreReports/Sessions/`; override with `SESSION_REPORTS_ROOT`. The
async `Stop` hook keeps metrics current for sessions that never exit. The `Edit|Write` hooks take
a typecheck baseline on the first `.cs` edit and run `cslint.py` on every one.


## Codex setup

Claude remains the default. Select Codex explicitly to link every layer's existing skill folders
into `.agents/skills/` and create a minimal `AGENTS.md` only when it does not already exist:

```bash
GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.sh check --agent codex
GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.sh install --agent codex
```

Use the actual externals folder spelling: both `GitIgnoredExternals/` and `GitIgnoreExternals/`
are supported, but having both is reported as ambiguous. Pass `--project <host-root>` before the
subcommand to select a host explicitly. `--agent both` configures both hosts; `--agent claude`
is the default and preserves existing Claude behavior. Existing instruction files and skill
link conflicts are preserved. `check` and `install --dry-run` do not write files.

Codex invokes these skills as `$discover`, `$audit`, `$resume-work`, etc. Skill folders remain
symlinks to the authoritative shared source. Codex normally detects new skills automatically;
restart it if the skills do not appear. See [Build skills](https://learn.chatgpt.com/docs/build-skills).

The Codex path does not merge `.claude/settings.json`, install Claude hooks, or create CLAUDE.md.
The shared skill instructions still contain Claude-specific assumptions: adapt tool names to
available equivalents, and use natural-language workflow requests where appropriate. Claude
session metrics/transcript parsing and Claude session-launch commands are not made Codex-compatible
by this installer. Do not claim those hooks or tracking ran in Codex. Existing AGENTS.md should
state these host adaptations and any project-specific scope exceptions.

## 5. Agent worktrees

Background agents work in git worktrees under `.claude/worktrees/`. The installer sets:

- `worktree.baseRef: "head"` — a new worktree branches from your current branch, not from the
  default branch, so its work merges back cleanly.
- `worktree.symlinkDirectories` — `GitIgnoredExternals`, `GitIgnoreReports`, `.claude/skills`,
  plus whatever the host layer adds. A worktree then has the rules, tools and skills, and its
  session reports land in the main checkout instead of being deleted with the worktree.

Test agent work in the project you already have open, not by opening the worktree: run
`/land-worktree` to merge the branch, test it, then remove the worktree and branch. For a
worktree made by hand with `git worktree add`, run `install.sh prepare-worktree <path>` to add
the symlinks.

## 6. Verify

Start a new Claude Code session in the project. You should see a **Session tracking (started)**
block in the agent's context, and `/feature`, `/end-session` and the other commands should be
available.

## Requirements

- Claude Code (CLI, desktop or IDE extension), or Codex for the skill/instruction setup described above
- Stock `python3` — the session-lifecycle tooling needs no third-party packages

**Source files:** [[Tools/setup/README|setup README]] · [[Tools/session-lifecycle/README|session-lifecycle README]] · [[Skills/land-worktree/SKILL|/land-worktree]]

---

← [[00_Overview|Overview]] · [[02_WorkModes|Work Modes and Routing]] →

## Project document-path configuration

Install creates `ai-agent-core.json` at the host project root. Commit it so every computer
uses the same document roots. Paths are relative to that project, independent of shell cwd:

```json
{
  "schema_version": 1,
  "paths": {
    "features": "Assets/GitIgnoreAssets/Features",
    "design_documents": "Assets/GitIgnoreAssets/DesignDocuments"
  }
}
```

The initial defaults are always `Assets/GitIgnoreAssets/Features` and
`Assets/GitIgnoreAssets/DesignDocuments`; installation does not choose a tracked replacement
automatically. On an interactive first install, choose each target or accept its default.
Choosing a folder opens the native directory picker (`osascript` on macOS, `tkinter` elsewhere).
Selections must be existing folders inside the project; cancellation writes no configuration.
For a tracked Unity asset location, pass custom paths as in the first example below.
Noninteractive installs use the defaults for targets without explicit flags; `--defaults` also
suppresses target prompts during interactive installs:

```bash
python3 <core>/Tools/setup/install.py install --agent codex --features-dir Assets/Documentation/Features --design-documents-dir Assets/Documentation/DesignDocuments
python3 <core>/Tools/setup/install.py install --agent codex --defaults
python3 <core>/Tools/setup/project_config.py --project <project-root> get features
python3 <core>/Tools/setup/project_config.py --project <project-root> get design_documents
```

Existing configuration is preserved on reinstall. Explicit flags that conflict with existing
values fail rather than overwriting them. `check` and `install --dry-run` neither prompt nor
write files. CLI feature-root overrides and `SESSION_FEATURES_ROOT` take precedence over
configuration; without config, existing projects retain legacy behavior. Configuration requires
both path keys and retains unknown fields on reinstall. Invalid configuration fails clearly
when it is consulted; an explicit feature-root override bypasses config lookup and validation.
Reports and server runtime locations are unchanged.

The resolver prints an absolute path. Without `--project`, it finds the working checkout from
its invocation directory, keeping per-worktree configuration local. Pass `--project` when
running elsewhere or from within the shared rules repository.

Configuration creation or editing does not move documents. Relocate complete feature folders
explicitly, preserving authoritative state, comments, relative anchors, legacy backups and
Unity `.meta` GUIDs. Let Unity create missing `.meta` files for real folders under `Assets`,
then commit those with the documents. Ignore runtime `.feature-state.lock` files. Do not use a
compatibility symlink as a second configured document location.

After editing feature paths or relocating feature folders, explicitly stop and start the
persistent preview with `preview-control.sh stop`, then `preview-control.sh start`. Calling
`start` alone reuses a healthy server: automatic restart watches preview/feature-state Python
files, not project configuration or the setup resolver.
