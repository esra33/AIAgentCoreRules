---
name: publish-work
description: Publish authorized agent work to Git and GitHub in one resumable command. Use for commit, push and pull request requests in any lane, and as the publishing backend for publish-batch.
argument-hint: "<request.json or publishing context>"
---

# Publish Work

Use `python3 <core>/Tools/publish/publish.py publish --request <absolute-request.json>`
from any directory. `<core>` is the AIAgentCoreRules root. One invocation performs
preflight, exact-file staging, commit, push, PR creation/reuse and optional feature recording.
Do not split these operations into agent turns or switch to browser/connector fallbacks.

## Prepare once

1. Confirm publishing is authorized by the task and complete the lane's required review and
   validation. Preserve all audit, batch-plan approval and engineer merge gates. The tool
   does not run tests or establish approval. Do not ask again for already-authorized publishing.
2. Determine the exact repository/worktree, working branch, current HEAD, remote base and
   reviewed file list from task context and Git. Include required metadata. Retain unrelated
   dirty files; never select `.` or all changes. For batches, follow `publish-batch` first.
3. Write the reviewed PR description to a UTF-8 file and a JSON request outside the file list.
   Include validation evidence in the description. Required keys:

```json
{
  "repo": "/absolute/path/to/worktree",
  "branch": "agent/example",
  "expected_head": "<full current HEAD SHA>",
  "base": "main",
  "files": ["Tools/example.py"],
  "commit_message": "Add example utility",
  "pr_title": "Add example utility",
  "body_file": "pr-body.md"
}
```

`repo` is absolute; `files` are exact repository-relative literal paths, including deletions.
`body_file` is absolute or relative to the request file's directory. Include the commit
attribution required by the session. Never invent validation results.

For a feature batch, add `feature` with `directory`, `task_id`, `batch` (one-based),
`phase` (for example `V1`), and `session` (the recorded session folder). Resolve the feature
root with `Tools/setup/project_config.py`; `directory` may be absolute or relative to the
request file. Use the existing approved batch plan; never silently migrate legacy features.

## Execute and recover

Run `publish` directly after preparation; it includes preflight. Optional `check` performs
read-only preflight and `status` inspects the operation using the same `--request` argument.
The publisher runs on macOS/Linux (POSIX file locking) and requires Git and authenticated
GitHub CLI with repository access. A missing
prerequisite returns setup guidance before committing; installing or configuring them is
outside this skill. Host approval controls remain authoritative.

Read the compact JSON result: `status`, `step`, `sha`, `branch`, `url`, and `resume`.
On success report the commit, PR URL and validation evidence concisely. On a blocker report
what completed, the failed step, and its actionable setup/resume command. Never print secrets.

Resume with the exact unchanged request and body. The local Git-metadata journal reconciles
completed steps, including a PR created before a timeout and partial feature-state writes.
Do not manually repeat commits or PR creation. Unexpected HEAD movement or changed request
content requires inspecting the operation before preparing a replacement. For a new review-fix
commit, prepare a new request with the current HEAD; the open PR is reused without replacing
its description. A closed, unmerged PR requires engineer direction. Previously merged PRs do not prevent
publishing the next approved batch on the same branch.

The tool never pushes to base, force-pushes, or merges PRs. Feature recording uses validated
revision-checked feature-state operations; publication remains incomplete if recording fails.
