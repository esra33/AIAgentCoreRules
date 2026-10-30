---
name: bug-fix
description: Start the BugFix process (diagnosis, approved fix, regression test) for a reported bug without classifying the mode first. Use when the engineer runs /bug-fix <symptom>.
argument-hint: "<symptom, error or ticket>"
---

# Bug Fix

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
MetaRouter.md). The engineer chose the lane, so skip MetaRouter's "Classify the Mode".

```yaml
steps:
  - "Step 0 — /start-session: if no 'Session tracking' block is in context, run: python3 Tools/session-lifecycle/session_lifecycle.py hook-start, and use the lifecycle script and session_id it prints below. If the engineer named the session, add --name \"<name>\" to the set."
  - "Run: python3 <lifecycle script> set --lane bug_fix --work-type bug_fix --title \"<short title from $ARGUMENTS>\""
  - "If the work is for an in-progress CreateFeature feature (named in the ask, or the active-features list fits it), add --feature \"<FeatureName>\" to that set, so the feature's Performance tab counts this session."
  - "Read: Processes/BugFix.md and follow it from its first step with $ARGUMENTS as the symptom."
  - "No arguments → ask for the symptom, repro steps or log, then continue."
```

Diagnose before fixing: no code until the engineer approves the fix, as BugFix.md requires.
