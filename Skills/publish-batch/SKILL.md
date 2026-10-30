---
name: publish-batch
description: Publish a CreateFeature task's C# code in small reviewable batches - plan the batches, commit and push each one on the task's own worktree branch, open a GitHub PR against the engineer's user branch with a table of files/types changed, what and why, then wait for the merge before starting the next batch. Records batch N of M in the feature's <FeatureName>_Progress.md. Use when the engineer runs /publish-batch, when Phase 4 starts a task, when a batch is ready for review, or when the engineer says a batch PR was merged.
argument-hint: "[plan|publish|status|finish] [FeatureName] [task id]"
---

# Publish Batch

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
MetaRouter.md). Run commands from the project root, or from the task's worktree once it exists.

Applies to C# and related files only: `.cs`, `.asmdef`, generated parsers, config JSON, and the
`.meta` files of those. Python tools, Markdown and agent metadata are exempt — they follow the
lane's normal flow. Unity serialized assets are never edited by the agent (host project rule).

```yaml
paths:
  features_root: "$SESSION_FEATURES_ROOT, else Assets/GitIgnoreAssets/Features"
  progress_file: "<features_root>/<FeatureName>/<FeatureName>_Progress.md"
  tdd:           "<features_root>/<FeatureName>/<FeatureName>_TDD.md"

names:
  task_id:   "The TDD '#' column under '## Development plan' (e.g. T3); else the TaskList {id:}. No id → ask and stop; never invent one."
  id_column: "The doc-review Progress tab shows a TDD's '### V<n>' phases INSTEAD of the task list, and matches batches: entries by the TDD '#' column. A TDD with V-phases but no '#' column therefore never shows 'batch N of M', even when the TaskList has ids — plan's 'Task ids' step adds the column first."
  worktree:  "<FeatureName>-<task_id>"
  branch:    "feature/<FeatureName>/<task_id>"
  base:      "the branch checked out in the engineer's main checkout when the task starts (their user branch), recorded once per task"
  pr_title:  "[<FeatureName>] <task_id> batch <k>/<N>: <one-line summary>"

batch_size:
  - "One coherent concern per batch — the reviewer reads every line instead of skimming."
  - "Aim for ≤ ~300 changed lines and ≤ ~5 files; a single larger file may be its own batch."
  - "Follow Phase 4 order: interfaces → concrete classes → integration glue. A test file goes in the batch of the class it covers."
  - "Generated files (parsers, [GEN]) go in their own batch, marked generated in the table."

subcommands:
  plan:    "Start a task: worktree, branch, batch plan."
  publish: "Commit, push and open the PR for the current batch (or push fixes to its open PR)."
  status:  "Check the open PR; on merge, sync the branch and move to the next batch."
  finish:  "After the last batch merged: remove the task's worktree."
  default: "No subcommand → status if the task has an open_pr, else publish if it has a plan, else plan."
```

## Steps

```yaml
plan:
  - "Feature and task: arguments; else the feature whose progress file lists this session's id8 under `sessions`, and the Checkpoint `next`. Unclear → list candidates, ask and stop."
  - "Base: git -C <main checkout> branch --show-current. It must exist on origin (git ls-remote --heads origin <base>); if not, ask the engineer to push it and stop."
  - "Fresh base: git -C <main checkout> fetch origin <base>, then git rev-list --count HEAD..origin/<base>. Non-zero → ask the engineer to pull in their main checkout and stop — the worktree branches from local HEAD, so a stale checkout re-shows merged batches."
  - "Task ids: the TDD has '### V<n>' headings under '## Development plan' but its task tables have no '#' column → before anything else, propose adding it as the first column of every V-phase table. Ids: the TaskList {id:} of the same task (match by title) when the TaskList has ids, so both files agree; else T1, T2 … across the whole plan. Show the id per row and wait for the engineer's OK, then edit the TDD (the feature folder is not in any repo). A TDD source of truth elsewhere (sources_of_truth, e.g. Confluence) → say the column must be added there too."
  - "Worktree: EnterWorktree(name: <worktree>) — the project settings branch it from HEAD and symlink the ignored folders. Then git branch -m <branch> so the branch name is stable."
  - "Batch plan: split the task's files from the TDD design into batches by batch_size. Show it as a numbered list (batch title, files) and wait for the engineer's OK; they may merge, split or reorder."
  - "Record (progress header, batches block): <task_id>: branch, base, plan (the batch titles), merged: 0, open_pr: null, prs: []. Set updated_at."

publish:
  - "Preconditions: every file in the batch passed /audit (Phase 4 per-file checklist), and typecheck.py passes in the worktree. Either fails → fix or report, do not publish."
  - "Stage only the batch's files by path (git add <files>, git rm <files>); never git add -A or ., and never a file outside the batch."
  - "New C# files have no .meta until Unity imports them: say so in the PR body; the engineer commits the generated .meta files after pulling."
  - "Commit message: the pr_title, then the attribution lines the session requires."
  - "git push -u origin <branch>."
  - "gh pr create --base <base> --head <branch> --title <pr_title> --body <body>. Body: 'Batch <k> of <N> — <FeatureName> <task_id> (<TDD V-phase>)', the change table, then the remaining batch titles, then the attribution line."
  - "Output the change table in the reply too (format below), followed by the PR URL."
  - "Record: open_pr: <PR>, append <PR> to prs, and list the PR under pull_requests: V<n> (the task's V-phase) so the Progress tab shows its review notes. Add the session folder to `sessions` if missing."
  - "Review fixes on an open PR: address notes through /feature-pr <PR>; commit the fixes to the same branch and push — no new PR. Output a change table for the fix commit as well."

status:
  - "gh pr view <open_pr> --json state,mergedAt,url."
  - "OPEN → say batch <k> of <N> is in review and stop."
  - "CLOSED without merge → ask whether to re-plan, reopen or abandon the batch; stop."
  - "MERGED → git fetch origin <base> && git merge --no-edit origin/<base> on the task branch (a merge: never rebase or force-push). This works for squash and merge-commit PRs alike."
  - "Record: merged += 1, open_pr: null; Checkpoint done gets '<task_id> batch <k>/<N> (PR #<PR>, merged): <files>'; next = the following batch, or '/publish-batch finish' when merged == len(plan)."
  - "Then continue with the next batch's files (Phase 4 per-file checklist) and publish it."

finish:
  - "Only when merged == len(plan) and open_pr is null."
  - "ExitWorktree(action: remove) — or, if this session did not enter it, git worktree remove .claude/worktrees/<worktree>. Delete the local branch. Ask before git push origin --delete <branch> (GitHub may already have deleted it)."
  - "Tell the engineer to pull <base> in their main checkout before the next task."
  - "Record: Checkpoint done gets '<task_id> published (<N> batches, PRs #…)'; next = the next task."
```

## Change table

One row per file added, modified or removed; types named so the reviewer can find them.

```markdown
| Change | File · Type | What changed | Why |
|---|---|---|---|
| added | `Scripts/Foo/IFooService.cs` · `IFooService` | New interface: `Load()`, `IsReady` | Lets HUD code depend on the service, not the manager (TDD §3.2) |
| modified | `Scripts/Foo/FooManager.cs` · `FooManager` | Implements `IFooService`; `Load` now awaits config | Design step 2; was blocking the main thread |
| removed | `Scripts/Foo/FooHelper.cs` · `FooHelper` | Deleted | Logic folded into `FooManager.Load` |
```

`Why` cites the TDD section, the design decision or the review note — never "requested".

## Rules

```yaml
rules:
  - "One open PR per task at a time: batch k+1 is not published until batch k is merged."
  - "A merged PR is the engineer's acknowledgment for every file in it (Phase 4 per-file acknowledgment)."
  - "Never push to <base> directly, never force-push, never merge a PR yourself — the engineer merges on GitHub."
  - "Write only to the progress file of the chosen feature; never edit a block under 'Gates Passed'."
  - "Progress file write refused (background job guard) → print the exact yaml lines for the engineer to paste and say so; do not skip the record."
  - "gh failing (not logged in, wrong repo) → report its error line and stop; suggest `! gh auth login`."
```
