---
name: resume-work
description: Resume an in-progress CreateFeature from its <FeatureName>_Progress.md - reload the current phase file, its rules and artifacts, restate where work stopped, and continue after the engineer confirms. With no name, lists the active features and lets the engineer pick one. Use when the engineer runs /resume-work [FeatureName] or asks to pick up / continue a feature from a previous session.
argument-hint: "[FeatureName]"
---

# Resume Work

## Authoritative feature state

Read `Processes/FeatureState.md` for the shared tool contract. `state.json` is authoritative;
Progress Markdown is generated. All legacy references below to editing progress mean tool
operations, never direct Markdown/JSON edits. Use focused `get`, revision-checked mutations,
and explicit migration for legacy features. Preserve engineer approval gates.


Read state through the tool (header fields, checkpoint, gates, sources and artifacts), register this session through checkpoint, then retain the explicit restate-and-confirm step. Read comments with `doc_review.py comments <feature-directory>` even if no server is currently running.


Named `resume-work`, not `resume`, so it does not collide with the built-in `/resume` command.

Paths are relative to the AIAgentCoreRules root (the parent of the `Rules/` folder that holds
MetaRouter.md). Load files with Read, not shell `cat`, so the router trace records them.

## Step 1 — Find the feature

```yaml
steps:
  - "Step 0 — /start-session: if no 'Session tracking' block is in context, run: python3 Tools/session-lifecycle/session_lifecycle.py hook-start, and use the lifecycle script and session_id it prints below. If the engineer named the session, add --name \"<name>\" to the set."
  - "If $ARGUMENTS names a feature: progress file is <working_folder>/<FeatureName>_Progress.md (working_folder from Processes/CreateFeature/index.md)."
  - "If $ARGUMENTS is empty: pick one (below), then continue this step with the chosen feature — do not stop after the list."
  - "If state.json is absent but legacy Progress exists, report explicit migration required and stop; if neither exists, offer /feature <FeatureName> and stop."
  - "Run: python3 <lifecycle script> set --lane feature --title \"<FeatureName>\" --feature \"<FeatureName>\" --phase <current_phase>"
  - "This session is for current_phase only (one session per phase, see CreateFeature/index.md). If the session already holds work for another feature or phase, suggest starting a fresh one."
  - "Add the current session folder name to `sessions` in the progress file."
```

### Picking a feature when no name was given

```yaml
pick:
  - "Run: python3 <lifecycle script> features --json   # same list as /active-features, newest first"
  - "Empty list: say no features are in progress, offer /feature <Name>, and stop."
  - "Otherwise ask with the host's choice prompt (AskUserQuestion in Claude Code; a numbered list elsewhere). One option per feature, newest first, at most 4: label = feature, description = '<phase_label> · <status> · next: <next, shortened>'."
  - "More than 4 features: print the full list (as /active-features shows it) above the prompt, offer the 4 newest, and say the engineer can type any other name via Other."
  - "Wait for the choice. A typed name that matches no listed feature is handled by the 'file does not exist' step."
  - "If the chosen phase's recommended model differs from this session's, mention its fresh-session command (the resume command from `features`) once, and continue here unless the engineer switches."
```

## Step 2 — Reload

```yaml
reload:
  - "Read: Processes/CreateFeature/index.md"
  - "Read: the selected feature state through the tool; use focused sections where possible."
  - "Read: the phase file for current_phase."
  - "Read: the rule files that phase depends on — for Phase 2 and later, the load_rules list in Phase2_Discovery.md, using [FeatureName]_Discovery.md to decide the conditional ones."
  - "Read: the artifacts the current phase works from (e.g. TDD and TaskList for Phase 1–3, Architecture and Discovery for Phase 4, UseCases for Phase 5). Skip ones it does not use."
  - "Check the host's SystemIndex for an entry matching the system this feature lives in (not just the feature's own Discovery/Architecture docs) — read it too if one exists. A feature's own docs cover what changed; the SystemIndex entry covers the system's standing gotchas and may be stale, in which case propose updating it at /end-session."
  - "Checkpoint lists files in `done`: confirm they exist on disk (one ls / codeindex query). Do not re-read their bodies unless the next step needs them."
  - "External `sources_of_truth` entries (e.g. the Confluence TDD) are NOT fetched on resume — local first: the feature folder (TDD, diagrams, review.json via the doc-review preview) is the working copy, and external pages are publish targets. List each entry with its recorded version as 'not checked (local-first)'. Check drift only when the engineer asks (e.g. 'check Confluence') or the next step is an [[ExternalDocPass]] publish or review pass — then use the host doc-conventions file's cheap drift check, and read the new version only if it is newer and the current phase works from it."
  - "Doc-review comments: run `python3 Tools/doc-review/doc_review.py comments <feature-directory>` and list open/ready threads under drift. Feature comments are independent of the running server and selected tab. Do not wait to be told a comment exists."
```

## Step 3 — Restate and confirm

Present, then wait for the engineer:

```yaml
resume_summary:
  feature:           ""
  phase:             ""      # current_phase and its gate from index.md
  gates_passed:      []      # phase names only
  done_this_phase:   []
  in_flight:         ""
  next:              ""
  pending_decisions: []
  drift:             []      # anything that disagrees with the progress file: missing or extra files, git changes since updated_at, a source_of_truth at a newer version
```

**Do not continue until the engineer confirms.** If they correct the summary, update the
Checkpoint first, then continue from the corrected `next`.
