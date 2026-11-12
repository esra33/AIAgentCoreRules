#!/usr/bin/env bash
# Terminal entry point for install.py. Run it from inside the host project (or pass --project):
#    <core>/Tools/setup/install.sh [--project <path>] [subcommand] [options]
# With no subcommand it runs `install`; options such as --agent may follow directly.
# A core checkout that is not yet linked into the project is linked under GitIgnoredExternals/.
#
# Subcommands:
#    install            Configure Claude (default), Codex, or both with --agent.
#                       Codex links skills into .agents/skills/ and creates AGENTS.md if missing.
#                       Safe to re-run: only adds or updates what the fragments define.
#    check              Same as `install --dry-run`; accepts --agent too.
#    prepare-worktree   Symlink worktree.symlinkDirectories into a worktree Claude Code did not
#                       create (for example one made by hand with `git worktree add`).
#    worktrees          List the project's linked worktrees with branch, dirty state, and commits
#                       ahead of the current branch (used by /land-worktree).

# The guards stay POSIX and come before `set`, so sourcing this file or starting it from zsh or
# sh never changes the options of the calling shell.
if [ -n "${ZSH_VERSION:-}" ]; then
    case ${ZSH_EVAL_CONTEXT:-} in
        *:file*)
            printf 'Run this script instead of sourcing it.\n' >&2
            return 2
            ;;
    esac
    exec bash "$0" "$@"
fi
if [ -z "${BASH_VERSION:-}" ]; then
    case $0 in
        *install.sh) exec bash "$0" "$@" ;;
    esac
    printf 'Run this script instead of sourcing it.\n' >&2
    return 2 2>/dev/null || exit 2
fi
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then
    printf 'Run this script instead of sourcing it.\n' >&2
    return 2
fi
set -euo pipefail
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "${INSTALL_PYTHON:-python3}" "$SCRIPT_DIR/install.py" "$@"
