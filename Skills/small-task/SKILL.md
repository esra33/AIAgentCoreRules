---
name: small-task
description: Start the SmallTask process for a bounded change - a tool, utility, debug command or behaviour tweak modelled on existing code - without classifying the mode first. Use when the engineer runs /small-task <description>.
argument-hint: "<what to build or change>"
---

# Small Task

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
MetaRouter.md). The engineer chose the lane, so skip MetaRouter's "Classify the Mode".

```yaml
steps:
  - "Step 0 — /start-session: if no 'Session tracking' block is in context, run: python3 Tools/session-lifecycle/session_lifecycle.py hook-start, and use the lifecycle script and session_id it prints below. If the engineer named the session, add --name \"<name>\" to the set."
  - "Run: python3 <lifecycle script> set --lane small_task --work-type small_feature --title \"<short title from $ARGUMENTS>\"   # --work-type other for tooling, config or rule edits"
  - "If the work is for an in-progress CreateFeature feature (named in the ask, or the active-features list fits it), add --feature \"<FeatureName>\" to that set, so the feature's Performance tab counts this session."
  - "Read: Processes/SmallTask.md and follow it from 1_scope with $ARGUMENTS as the request."
  - "No arguments → ask what to build or change, then continue."
```

SmallTask's limits still apply: if the work outgrows them, stop and offer `/feature <Name>`.
