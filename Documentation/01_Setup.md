# Setup

How to install the core framework in a local checkout of a project. The core framework remains
local to your machine. On first install, choose whether the host project's AI metadata stays
local or lives in the project repository.

## 1. Clone and link the repository

Clone **AIAgentCoreRules** outside the game project, then link it in:

```bash
cd <game project root>
mkdir -p GitIgnoredExternals
ln -s <path to>/AIAgentCoreRules GitIgnoredExternals/AIAgentCoreRules
```

`GitIgnoredExternals/`, `CLAUDE.md`, `.claude/` and `GitIgnoreReports/` should be ignored by
your **global** gitignore (for example the patterns `*GitIgnore*` and `*CLAUDE*`). Never add
them to the game repository's `.gitignore`.

## 2. Choose the host metadata location

Run the installer in step 4. On a new install, it offers a picker:

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

```bash
python3 GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.py check   # preview
python3 GitIgnoredExternals/AIAgentCoreRules/Tools/setup/install.py         # apply
```

It merges `Tools/setup/settings.core.json` into `.claude/settings.json` (session hooks and the
worktree settings below), then each host layer's `Setup/settings.host.json`; links every layer's
skills into `.claude/skills/`; and creates `CLAUDE.md` with the core and new host imports if it is missing.
It only adds or updates what the fragments define, backs `settings.json` up to
`settings.json.bak` before changing it, and is safe to re-run — run it again after pulling
AIAgentCoreRules or the host layer. Details: [[Tools/setup/README|setup README]].

The session hooks never block a session — if tracking fails, Claude Code carries on. Session
folders are written to `GitIgnoreReports/Sessions/`; override with `SESSION_REPORTS_ROOT`. The
`Stop` hook keeps metrics current for sessions that never exit.


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

## 5. Agent worktrees

Background agents work in git worktrees under `.claude/worktrees/`. The installer sets:

- `worktree.baseRef: "head"` — a new worktree branches from your current branch, not from the
  default branch, so its work merges back cleanly.
- `worktree.symlinkDirectories` — `GitIgnoredExternals`, `GitIgnoreReports`, `.claude/skills`,
  plus whatever the host layer adds. A worktree then has the rules, tools and skills, and its
  session reports land in the main checkout instead of being deleted with the worktree.

Test agent work in the project you already have open, not by opening the worktree: run
`/land-worktree` to merge the branch, test it, then remove the worktree and branch. For a
worktree made by hand with `git worktree add`, run `install.py prepare-worktree <path>` to add
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
