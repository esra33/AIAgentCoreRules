# Setup

`install.py` wires AIAgentCoreRules and the host AI metadata into a host project. Stock
`python3`, no packages. `install.sh` is the terminal entry point for it: run it with any shell
(bash, zsh, sh — it re-runs itself under bash), never `source` it. Run it from anywhere inside
the project — the project root is the main
checkout of the git repository you are in, or the nearest folder holding `CLAUDE.md` outside git
(`--project <path>` overrides). `project_root.py` holds that lookup; the session tracker uses the
same module, so a new project needs no extra configuration for its reports to land in the right place.
Inside a Claude Code session (`!` prefix or a hook), `CLAUDE_PROJECT_DIR` takes precedence over
the cwd, so the installer targets the session's project. To install into another project from
there, pass `--project <path>`.

```bash
cd <project>
<core>/Tools/setup/install.sh check                   # what install would change
<core>/Tools/setup/install.sh                         # install (same as `install`)
<core>/Tools/setup/install.sh --agent codex           # options work without the subcommand too
<core>/Tools/setup/install.sh worktrees [--json]      # linked worktrees: branch, dirty, ahead/behind, from_upstream
<core>/Tools/setup/install.sh prepare-worktree <path> # add the symlinks to a worktree made by hand
```

`<core>` is either the clone of AIAgentCoreRules or its linked copy,
`GitIgnoredExternals/AIAgentCoreRules`. `python3 <core>/Tools/setup/install.py …` takes the same
arguments. `INSTALL_PYTHON=<interpreter>` picks another Python for `install.sh`.

**First install.** When the project has no `GitIgnoredExternals/` (or `GitIgnoreExternals/`)
holding the core yet, `install` links the checkout it runs from as
`GitIgnoredExternals/AIAgentCoreRules` (`check` reports it as `core: link`, and lists skill links
only once the link exists). It warns when git does not ignore that folder, and refuses to run
with the AIAgentCoreRules repository itself (or one of its worktrees) as the project — run it
from inside the project, or pass `--project <path>`, which must be an existing folder.

## What install does

| Step | Source | Result |
|---|---|---|
| Core link | the running core checkout | `GitIgnoredExternals/AIAgentCoreRules` → the checkout, only when no core layer is linked |
| Settings | `settings.core.json`, then each layer's `Setup/settings.host.json` | merged into `.claude/settings.json` (backup: `settings.json.bak`) |
| Skills | every `<layer>/Skills/<name>/SKILL.md` | `.claude/skills/<name>` → `../../GitIgnoredExternals/<layer>/Skills/<name>` |
| CLAUDE.md | — | created with core imports and new host imports if missing; missing imports reported, never edited |
| New host metadata | install picker | creates `AIMetaData/` under the externals folder or project root, with starter rules, SystemIndex, and settings |

On a new install, `install` asks where to put host AI metadata. Choose the externals folder for
local files, or the project root for files to commit with the project. The project root choice
creates `AIMetaData/`. Existing host layers keep their current location and are never moved.
For automation, use `--metadata-location externals` or `--metadata-location project` after the
`install` subcommand. `check` without a choice reports that a location is needed; passing the
option previews the new files without creating them. Noninteractive installs require the option.

The core layer stays under the externals folder and is applied first. Host layers are read from
there or from root `AIMetaData/`. Merge rules:
objects merge key by key, lists of plain values are unioned, other values are set, and hooks are
matched by command — an existing hook with the same command is left alone. Nothing else is deleted:
a skill link that points elsewhere is reported as a conflict and kept. The one exception is a
dangling skill link into a layer's `Skills/` folder (a renamed, deleted or moved skill): it is
reported as `skills: prune stale <name>` and removed (`check` only reports it). Pruning runs
before linking, so a skill that moved to another layer (e.g. a skill moved host → core) is re-linked
to its new layer in the same run instead of reported as a conflict.


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

## Host layer fragment

A host layer adds project-specific settings in `Setup/settings.host.json`, using the same shape
as `settings.json`. For example, a Unity project whose personal assets live in a gitignored
folder under `Assets/`:

```json
{ "worktree": { "symlinkDirectories": ["Assets/GitIgnoreAssets"] } }
```

## Worktree settings

`settings.core.json` sets `worktree.baseRef` to `head`, so agent worktrees branch from the
current branch. It also symlinks the externals folder, `GitIgnoreReports` and `.claude/skills`
into every worktree Claude Code creates. Removing a worktree removes the links, not what they
point at. `/land-worktree` (`Skills/land-worktree`) merges a worktree back and cleans it up.

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
