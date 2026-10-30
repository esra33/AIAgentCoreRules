---
name: kill-server
description: Stop a running doc-review preview server (started by /start-preview-server or doc_review.py serve) - lists the live servers with pid, port, doc and folder, and stops the one chosen, or all of them. Use when the engineer runs /kill-server [port|pid|all] or asks to stop, kill or shut down the preview / doc-review server.
argument-hint: "[port | pid <n> | all]"
---

# Kill Server

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
MetaRouter.md).

```yaml
cli: "Tools/doc-review/doc_review.py"

steps:
  - "List: python3 <cli> servers. None running → say so and stop."
  - "'all' → python3 <cli> stop --all."
  - "A number → python3 <cli> stop --port <n>; 'pid <n>' → stop --pid <n>."
  - "No argument and exactly one server → python3 <cli> stop. Several → show the list (url, doc, folder) and ask which; wait."
  - "Confirm with python3 <cli> servers and reply in one line: what was stopped, what is still running."
```

## Rules

```yaml
rules:
  - "Stop servers only through the CLI: it targets the Python server process, not the shell a background Bash launch leaves behind."
  - "A server whose folder is a job tmp (~/.claude/jobs/…) may belong to a background job — name it when asking, but stop it if the engineer says so."
  - "Never kill by port with lsof/kill directly; another tool may own that port."
```
