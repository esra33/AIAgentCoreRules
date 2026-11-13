# Agent Publishing

`/publish-work` is the shared Git/GitHub publishing entry point for all agent lanes.
`/publish-batch` retains its batch planning, audit, validation and merge gates, then calls
this publisher for the mechanical publication and feature recording.

```bash
python3 <core>/Tools/publish/publish.py publish --request /absolute/request.json
```

The request specifies the absolute repository, branch, expected HEAD, base, exact file list,
commit message, PR title and description file. The optional feature context records the PR,
batch and session through feature-state. See [the skill](../Skills/publish-work/SKILL.md)
for the complete request example and recovery procedure.

`check` is read-only preflight; `status` inspects an operation. `publish` includes preflight
and runs without internal prompts. An authorized task needs no new confirmation from this
tool. macOS/Linux (POSIX file locking), Git and authenticated GitHub CLI are prerequisites; missing setup is reported before
committing. Host sandbox approvals still apply, and this tool does not configure permissions.

Only explicitly listed files are staged. Unrelated unstaged changes remain untouched;
unrelated staged changes block publication. Existing open PRs are reused without replacing
their descriptions. No base push, force push or PR merge is performed.

An operation journal under Git metadata records successful steps. Retry the unchanged request
to resume after a failure; a timeout is reconciled with Git/GitHub before another write. Feature
recording failures remain resumable without creating a second PR. New review fixes use a new
request and current HEAD on the same branch. Compact JSON results report completion, commit,
branch, PR URL, failed step and resume command.

Installation uses the existing skill discovery mechanism; no new hook is needed. Dependency
installation, authentication setup and alternative API/browser backends are outside v1.

Sources: [publisher](../Tools/publish/publish.py) · [generic skill](../Skills/publish-work/SKILL.md) ·
[batch skill](../Skills/publish-batch/SKILL.md) · [router](../Rules/MetaRouter.md).
