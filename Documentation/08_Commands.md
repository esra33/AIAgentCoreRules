# Command Reference

Core slash commands, available once the skills are linked (see [[01_Setup|Setup]]). Commands marked
*engineer only* are never run by the agent on its own. Host project layers can add their own
commands — see the host project's documentation.

## Session lifecycle

| Command | What it does |
|---|---|
| `/start-session [name]` | Starts or resumes tracking, names the session (folder and metrics heading) when a name is given, and records the lane and work type. Tracking itself is automatic via the SessionStart hook — use it to name a session or when tracking context was lost. The lane commands (`/small-task`, `/bug-fix`, `/feature`, `/resume-work`, `/run-investigation-mode`, `/generate-meta-review`) run its tracking start as their step 0, so you do not need it before them. |
| `/end-session` | If the session worked in a worktree that still has work in it, first asks whether to land it and, on yes, runs `/land-worktree`. Then compiles metrics and the router trace, writes the retrospective scaled to the lane, opens both files, and proposes (not applies) rule improvements. The `/new-session` prompt it prints for applying proposals tells the new session to run `session_lifecycle.py` from the host project root and to edit layer repos in a `git -C <layer> worktree add` worktree — copied verbatim, never swapped for EnterWorktree, which isolates only the host project. |
| `/inaccuracy <what was wrong>` | *Engineer only.* Logs an agent mistake you just corrected. |
| `/iteration <what changed>` | *Engineer only.* Logs a deliberate change of direction or scope. |

## Feature work

| Command | What it does |
|---|---|
| `/feature <Name> [GDD path]` | Starts the 8-phase Create Feature process. If the feature already has a progress file, offers `/resume-work` instead. |
| `/checkpoint [Name] [note]` | Saves where work stopped inside the current phase to `<Name>_Progress.md`: done, in flight, next action, pending decisions, notes. |
| `/resume-work [Name]` | Picks a feature up in a fresh session: tags the session with the feature and phase, reloads the current phase, its rules and documents, reports drift (including a newer Confluence version and open comments on a running doc-review server), and waits for confirmation. With no name, lists unfinished features and asks which one to pick up, then continues with it. |
| `/small-task <ask>` | Starts the Small Task process directly: records the lane and loads the process without classifying the request first. |
| `/bug-fix <symptom>` | Starts the Bug Fix process directly: diagnosis, approved fix, regression test. |
| `/run-investigation-mode <question>` | Starts Investigation Mode directly. The output is a document or recommendation, not code. |
| `/active-features` | Lists every feature that is not complete: phase, status, last update, next step, and the command that resumes it with the phase's recommended model. New sessions show a short version of this list at start. |
| `/close-feature <Name> [reason]` | Closes or force-terminates a feature: asks for the closing status with a picker — `abandoned` (default), `superseded`, `on_hold` or `complete` — sets it in `<Name>_Progress.md` and appends the reason to a `Closed` history section. The feature drops off `/active-features` and the session-start list. The folder, artifacts, checkpoint and gate record are kept. |
| `/reopen-feature [Name] [reason]` | Returns a closed feature (`abandoned`, `superseded`, `on_hold`) to `in_progress` and prints its resume command; the checkpoint is untouched, so `/resume-work` continues where it stopped. Refuses `complete` features. With no name, lists the closed features (`session_lifecycle.py features --closed`) and asks. |
| `/start-preview-server [Name]` | Opens a feature's docs in the local doc-review preview server: a Progress tab first (current phase, steps, tasks, next gate in red), then the TDD (or the GDD when there is no TDD) and the `Diagrams/*.mmd` files. Read only. With no name, lists the features and asks. See [[12_DocReview\|Doc Review Tool]]. |
| `/feature-pr <PR> [Name] [V-phase]` | Ties a pull request to a feature and one of its TDD V-phases: lists it under `pull_requests` in `<Name>_Progress.md` (the Progress tab then shows its notes) and adds this session to the feature. Reads the PR's comments, review bodies and inline notes with `gh`, waits for you to pick which to address, and records each addressed note in that feature's Checkpoint. Infers the feature from this session and the V-phase from the PR's title and branch, and asks when either is unclear. Batch PRs from `/publish-batch` are read and addressed here too; fixes go to the batch's branch, so the same PR updates. |
| `/publish-batch [plan\|publish\|status\|finish] [Name] [task]` | Phase 4 batched publishing for C# and related files (Python and Markdown are exempt). `plan` creates one worktree and branch per task (`feature/<Name>/<task>`, from your user branch, after checking your checkout is not behind origin) and a batch plan you approve. `publish` stages only the batch's files, commits, pushes and opens a PR against your user branch, and prints a change table (Change \| File · Type \| What changed \| Why). `status` checks the PR; once you merge it on GitHub, it merges the user branch back into the task branch and starts the next batch. `finish` removes the worktree after the last batch. One open PR per task; a merged PR counts as your acknowledgment of its files. If the TDD has V-phases but no `#` task-id column, `plan` first proposes adding one (reusing the TaskList ids) and waits for your OK. Records `batches:` (plan, merged count, PRs) in `<Name>_Progress.md`, which the Progress tab shows as `batch N of M` on the task, and lists each PR under `pull_requests` too. Never pushes to your branch, force-pushes or merges. |
| `/kill-server [port\|pid <n>\|all]` | Stops a running doc-review preview server. Lists the live servers (pid, URL, doc, folder) and stops the one you pick, the only one running, or all of them. Uses `doc_review.py servers` / `stop`, which target the Python server process rather than the shell that launched it. |

## Analysis and review

| Command | What it does |
|---|---|
| `/discover <area>` | Surveys a system or directory in a subagent and returns a compact map: key types, entry points, integration points, gotchas and negative findings, each with `file:line`. Uses the host's Runnable tools when available. Offers to save the map as a Systems entry if none exists. |
| `/generate-meta-review [time frame]` | Runs the Meta Review over the sessions in a window (`last 2 weeks`, `since 2026-09-01`, `2026-09-01..2026-09-30`; default since the previous review) and produces the report page and ticket list. |
| `/audit [files]` | Checks C# files (default: changed files) against the coding standards, architecture principles, resource rules, rule tags and host project rules. Reports violations with `file:line` and a minimal fix. Report only — no edits unless asked. Fans out to subagents for more than 5 files. |

## Worktrees

| Command | What it does |
|---|---|
| `/land-worktree [name] [--squash]` | Merges an agent worktree's branch into your current branch without committing, waits while you test it, then commits and removes the worktree and branch — or rolls the merge back. If you already committed the staged merge yourself, it confirms the branch is in `HEAD` and reports your commit as the landing commit instead of merging again. Before `git branch -d` it checks `git merge-base --is-ancestor <branch> HEAD`, because `-d` also succeeds for a branch merged only into its pushed upstream. With no name, lists the worktrees. Warns when a worktree branched from the default branch instead of yours and offers to cherry-pick only the agent's commits. Lands into whatever branch the main checkout has checked out, including the default branch, and works for worktrees of other linked repos via `--project`, which goes before the subcommand (`install.py --project <repo> worktrees`). When the same worktree name exists in more than one repo (one change split across the core and metadata repos), lands each in turn in the same run, with its own keep/reject, and reports every commit hash at the end. Never pushes. A session working inside the worktree it lands commits, then exits it (ExitWorktree, keep) before any main-checkout git command. Records the session as lane `other` only when it has no work lane yet; a bug fix or feature session keeps its lane. If another landing is already staged (a pending merge waiting for keep or reject), it names that branch and asks you to finish it first. If one keep/reject answer could cover two pending landings, it says which ones the answer applies to before committing. |
| `/new-session <prompt> [--in terminal\|rider] [--model M]` | Opens a fresh Claude Code session that starts with `<prompt>` (for example `/small-task …` or `/resume-work <Name>`) in a new Terminal.app window or a new tab of Rider's terminal. Without `--in` it asks which. The session starts in the main checkout and runs independently of this one. macOS only; Rider needs Accessibility permission for the app that runs Claude. Details: `Tools/new-session/README.md`. |

## Reporting

| Command | What it does |
|---|---|
| `/token-usage-reports` | Sanitized token-usage and session-telemetry reports for current, recent or all sessions, exportable as Markdown or JSON. |

**Source files:** [[Skills/start-session/SKILL|/start-session]] · [[Skills/end-session/SKILL|/end-session]] · [[Skills/inaccuracy/SKILL|/inaccuracy]] · [[Skills/iteration/SKILL|/iteration]] · [[Skills/feature/SKILL|/feature]] · [[Skills/small-task/SKILL|/small-task]] · [[Skills/bug-fix/SKILL|/bug-fix]] · [[Skills/run-investigation-mode/SKILL|/run-investigation-mode]] · [[Skills/generate-meta-review/SKILL|/generate-meta-review]] · [[Skills/checkpoint/SKILL|/checkpoint]] · [[Skills/resume-work/SKILL|/resume-work]] · [[Skills/active-features/SKILL|/active-features]] · [[Skills/close-feature/SKILL|/close-feature]] · [[Skills/reopen-feature/SKILL|/reopen-feature]] · [[Skills/start-preview-server/SKILL|/start-preview-server]] · [[Skills/feature-pr/SKILL|/feature-pr]] · [[Skills/publish-batch/SKILL|/publish-batch]] · [[Skills/kill-server/SKILL|/kill-server]] · [[Skills/discover/SKILL|/discover]] · [[Skills/audit/SKILL|/audit]] · [[Skills/land-worktree/SKILL|/land-worktree]] · [[Skills/new-session/SKILL|/new-session]] · [[Skills/token-usage-reports/SKILL|/token-usage-reports]]

---

← [[07_SessionTracking|Session Tracking and Retrospectives]] · [[00_Overview|Overview]] · [[09_CodingRules|Coding Rules]] →
