---
name: start-preview-server
description: Open a CreateFeature feature's documentation in the local doc-review preview server - a Progress tab (current phase, steps, tasks, next gate) first, then the TDD (or GDD when there is no TDD) and the architecture diagrams. Use when the engineer runs /start-preview-server [Name] or asks to see, open or preview a feature's plan status, TDD or diagrams.
---

# Start Preview Server

Read only: opens the docs, never edits them. Run from the project root.

```yaml
paths:
  features_root: "$SESSION_FEATURES_ROOT, else Assets/GitIgnoreAssets/Features"
  feature_dir:   "<features_root>/<Name>"
  server:        "GitIgnoredExternals/AIAgentCoreRules/Tools/doc-review/doc_review.py"

steps:
  - "No name → list the folders under features_root that contain a <Name>_Progress.md, ask which one, and wait."
  - "Name with no matching folder → list the folder names, ask, and wait. Do not guess a close match."
  - "Main doc: the first that exists of <Name>_TDD.md, <Name>_GDD.md, <Name>_Progress.md. It must be passed first: the server keys the Progress tab and the comment sidecar off it."
  - "Diagrams: <feature_dir>/Diagrams/*.mmd sorted by name, skipping *.miro.mmd (copies prepared for Miro)."
  - "Run in the background (Bash run_in_background) — the server blocks: python3 <server> serve <main doc> <diagrams...> --open"
  - "Read the first line of its output — the URL — and report it with the tabs: Progress (when <Name>_Progress.md exists), the main doc (say when it fell back from the TDD), each diagram, and any skipped files."
  - "The server lives until the engineer stops it or the session ends. Offer to stop it when they are done (/kill-server)."
```

## Mermaid syntax and validation

When preparing diagrams for this preview, avoid literal semicolons in sequence-diagram
message text: Mermaid treats them as statement separators. Use commas, or encode an
intentional semicolon as `#59;`. Validate diagrams with an available Mermaid renderer before
claiming they render successfully. If renderer tooling or browser inspection is unavailable,
report that limitation explicitly and request an engineer rendering check.

The Progress tab comes from the server itself (see Documentation/12_DocReview.md): phases,
steps and gates from CreateFeature, completion from the progress file's handoff blocks, tasks from
`<Name>_TaskList.md`, and the next gate in red. It refreshes on save, like every other tab.
