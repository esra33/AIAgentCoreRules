# Setup

`install.py` wires AIAgentCoreRules (and any host layer next to it) into a host project. Stock
`python3`, no packages. Run it from anywhere inside the project — the project root is the main
checkout of the git repository you are in, or the nearest folder holding `CLAUDE.md` outside git
(`--project <path>` overrides). `project_root.py` holds that lookup; the session tracker uses the
same module, so a new project needs no extra configuration for its reports to land in the right place.

```bash
S=GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.py
python3 $S check                       # what install would change
python3 $S                             # install (same as `install`)
python3 $S worktrees [--json]          # linked worktrees: branch, dirty, ahead/behind, from_upstream
python3 $S prepare-worktree <path>     # add the symlinks to a worktree made by hand
```

## What install does

| Step | Source | Result |
|---|---|---|
| Settings | `settings.core.json`, then each layer's `Setup/settings.host.json` | merged into `.claude/settings.json` (backup: `settings.json.bak`) |
| Skills | every `<layer>/Skills/<name>/SKILL.md` | `.claude/skills/<name>` → `../../GitIgnoredExternals/<layer>/Skills/<name>` |
| CLAUDE.md | — | created with the three core imports if missing; missing imports reported, never edited |

Layers are the entries of `GitIgnoredExternals/`; AIAgentCoreRules is applied first. Merge rules:
objects merge key by key, lists of plain values are unioned, other values are set, and hooks are
matched by command — an existing hook with the same command is left alone. Nothing else is deleted:
a skill link that points elsewhere is reported as a conflict and kept. The one exception is a
dangling skill link into a layer's `Skills/` folder (a renamed or deleted skill): it is reported
as `skills: prune stale <name>` and removed (`check` only reports it).


## Codex setup

Claude remains the default. Select Codex explicitly to link every layer's existing skill folders
into `.agents/skills/` and create a minimal `AGENTS.md` only when it does not already exist:

```bash
python3 GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.py check --agent codex
python3 GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.py install --agent codex
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
current branch. It also symlinks `GitIgnoredExternals`, `GitIgnoreReports` and `.claude/skills`
into every worktree Claude Code creates. Removing a worktree removes the links, not what they
point at. `/land-worktree` (`Skills/land-worktree`) merges a worktree back and cleans it up.
