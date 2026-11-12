---
name: iteration
description: Log a deliberate change of direction or scope refinement into the session metrics. Run by the engineer as /iteration <description>.
argument-hint: "<what changed>"
disable-model-invocation: true
---

# Log Iteration

Lifecycle script (path from the Session tracking block, else):
`GitIgnoredExternals/AIAgentCoreRules/Tools/session-lifecycle/session_lifecycle.py`

```yaml
steps:
  - "If $ARGUMENTS is empty, ask for a one-line description and stop."
  - "Run: python3 <script> note --kind iteration \"$ARGUMENTS\""
  - "Reply with one line: the logged count, then continue in the new direction."
```

An iteration is a decision, not a mistake — agent errors are logged by the agent itself (`note --kind inaccuracy --source agent`).
