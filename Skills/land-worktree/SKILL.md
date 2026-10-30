---
name: land-worktree
description: Merge an agent's worktree branch into the engineer's current branch in the main checkout, wait for the engineer to test it (e.g. in the Unity Editor), then remove the worktree and branch — or roll the merge back. Use when the engineer runs /land-worktree, asks to bring an agent's worktree work into their branch, or asks to clean up finished worktrees.
argument-hint: "[worktree name | branch] [--squash]"
---

# Land Worktree

Agents work in `.claude/worktrees/<name>`; the engineer tests in the main checkout, which is the
project already open in the editor. This skill moves the work across and cleans up after it.
Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
MetaRouter.md). Run every git command in the **main checkout**, never inside the worktree.

```bash
python3 <core>/Tools/setup/install.py worktrees          # name, branch, dirty, ahead/behind, from_upstream
python3 <core>/Tools/setup/install.py worktrees --json
```

```yaml
steps:
  - "If this session is inside the worktree it is landing (EnterWorktree), commit its work, then ExitWorktree with action keep before running any git command in the main checkout."
  - "Record the session as lane other, work type other (Session tracking block) ONLY when the session has no lane yet or is already lane other. A session that already has a work lane (bug_fix, small_task, feature, investigation) keeps it: landing finishes that work, it is not a new lane, and a relabel files the session under the wrong lane once /end-session closes it. Also skip when /end-session called this skill."
  - "List worktrees with `install.py worktrees`. No argument → show the list and ask which one. A PRUNABLE row → offer `git worktree prune`."
  - "Worktree of another repository (e.g. a rules repo linked under GitIgnoredExternals/) → pass `--project <that repo's main checkout>` to install.py and run the git commands there. `--project` is a global option and goes before the subcommand: `install.py --project <repo> worktrees`. After it, argparse rejects it."
  - "The same worktree name exists in more than one repo (e.g. agent/<name> in AIAgentCoreRules and TripleMatchAiMetaData for one change) → list every repo that has it, land them one at a time in this run, each with its own keep/reject, and report every commit hash at the end."
  - "Target branch = the main checkout's current branch. State it and the worktree branch in one line before doing anything."
  - "Preconditions — stop and report, do not fix silently:"
  - "  a landing is already staged (`git rev-parse -q --verify MERGE_HEAD` succeeds) → name its branch (`git name-rev --name-only MERGE_HEAD`) and ask: keep it (`git commit --no-edit`) or reject it (`git merge --abort`). Finish that one before landing anything else; it is not generic dirty state."
  - "  one keep/reject answer while two landings are pending (e.g. a pre-existing MERGE_HEAD in one repo and a staged landing in another) → state which landings the answer applies to before committing."
  - "  main checkout has uncommitted changes to tracked files (`git status --porcelain --untracked-files=no`) → ask the engineer to commit or stash"
  - "  worktree is DIRTY → the agent left uncommitted work; show `git -C <worktree> status --short` and ask"
  - "  ahead is 0 → nothing to land; offer cleanup only"
  - "Show `git log --oneline HEAD..<branch>` and `git diff --stat HEAD...<branch>`."
  - "from_upstream > 0 → the worktree branched from the default branch, not from the target. Merging brings those upstream commits too. Offer instead: cherry-pick only the agent's commits (`git log --reverse --format=%H HEAD..<branch> --not <upstream>`). Engineer chooses."
  - "Merge without committing so the engineer tests first: `git merge --no-ff --no-commit <branch>` (or `--squash` when asked). On conflicts: list the files, stop, let the engineer resolve or abort."
  - "If the host project has a compile check (e.g. a typecheck tool in its SystemIndex), run it now and report the result."
  - "Ask the engineer to test, and wait. Do not continue until they answer keep or reject."
  - "keep → `git commit --no-edit` (squash: commit with a message summarising the agent's commits). Then cleanup."
  - "  `git commit --no-edit` reports nothing to commit → the engineer committed while the merge was staged. Confirm with `git merge-base --is-ancestor <branch> HEAD` and report the engineer's commit hash as the landing commit; never re-merge."
  - "reject → `git merge --abort` (squash: `git reset --merge`). Then ask: keep the worktree for more work, or discard it."
  - "Cleanup (keep, or reject + discard):"
  - "  `git worktree remove <path>` — never add --force on your own; if git refuses, show why and ask"
  - "  keep: first verify `git merge-base --is-ancestor <branch> HEAD`; `git branch -d` also succeeds when the branch is merged only into its pushed upstream (origin/<branch>), so it is not proof of landing."
  - "  keep: `git branch -d <branch>` · discard: `git branch -D <branch>` after the engineer confirms"
  - "  branch exists on the remote (`git ls-remote --heads origin <branch>`) → ask before `git push origin --delete <branch>`"
  - "  `git worktree prune`"
  - "Reply with what landed (commit hash, or 'rolled back'), what was removed, and what is left in `install.py worktrees`."
```

## Rules

```yaml
rules:
  - "Never push the target branch or force-push. Landing is local."
  - "Running /land-worktree (or answering yes in /end-session) is the confirmation to merge, including into the default branch. Do not ask again before merging."
  - "Never commit the merge before the engineer says keep."
  - "Removing a worktree deletes only its folder: symlinked directories (worktree.symlinkDirectories) are links, so the main checkout's copies are untouched."
  - "git refuses to remove a worktree with modified tracked files or untracked, non-ignored files; ignored folders (e.g. Unity Library/) do not block it and are deleted with it. A refusal means real unsaved work — show it before asking about --force."
  - "Several worktrees to land → one at a time, each tested before the next."
```
