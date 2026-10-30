## apply: on-demand — loaded by [[MetaRouter]]

# Create Feature — Process Index

Interactive wizard for designing and implementing a new feature. Load one phase file at a time. Do not advance past any gate without explicit engineer confirmation.

```yaml
working_folder: "Assets/GitIgnoreAssets/Features/<FeatureName>/   # GDD, TDD, TaskList, UseCases, Discovery, Architecture docs"
progress_file:  "<working_folder>/<FeatureName>_Progress.md        # resume state — template: ../Templates/Progress_Template.md"
session_metrics: "per session, in the Session tracking folder — see MetaRouter Session Lifecycle"
```

A feature usually spans several sessions. Each session gets its own metrics; the Phase 8
retrospective reads all of them, using the `sessions` list in the progress file.

---

## One Session per Phase

Each phase runs in its own session, so context stays small (a long session re-reads all of
it on every turn), metrics show what each phase cost, and each phase can start on its
`recommended_model`. A phase may take several sittings: end each one with `/checkpoint`, and
the next sitting is another session for the same phase.

```yaml
on_gate_confirmed:   # in this order, then stop
  1_record:  "Write the phase_handoff block and update the progress file (on_gate below)."
  2_close:   "Run /end-session. Mid-feature it writes a short phase retro (see end-session depth)."
  3_handoff: "Print the command for the next phase's fresh session and stop. Do NOT load the next phase file here."
handoff_command: |
  Next: Phase <N> — <Name>. In a new session from the project root:
    claude --model <next phase's recommended_model> "/resume-work <FeatureName>"
exceptions:
  - "The engineer asks to continue in this session: continue, and record the reason in the gate block's open_items."
  - "Long-session continuations across multiple gates are valid when phases are tightly coupled and context is fresh (e.g., Phase 3 → 4 → 7 in one session for a small, cohesive feature). Document the reasoning in the progress file's `open_items` for each gate passed; metrics will show a single very long session rather than multiple shorter ones, which is expected and correct."
  - "Phase 8 runs in the session that confirms Gate 7 only if the engineer asks; otherwise it is its own session too."
```

---

## Progress File — resuming across sessions

Chat context does not survive a session end or a summary. The progress file does.

```yaml
progress_file:
  create:     "At the start of Phase 1, from ../Templates/Progress_Template.md, if it does not exist."
  on_session: "Add the current session folder name (from the Session tracking block) to `sessions` the first time this session writes the file. Readers match entries by the id8 suffix, so a later lane rename does not break them."
  on_gate:    "Append the phase_handoff block (below) under 'Gates Passed', set current_phase to the next phase, clear the Checkpoint section, update artifacts and the sources_of_truth versions."
  mid_phase:  "/checkpoint replaces the Checkpoint section — where work stopped and what comes next."
  on_step:    "Starting a step (its key: 1a, Step 3, Category 2) → set it `in_progress` under `step_status:`; the engineer acknowledging it → `done`. When a phase starts, replace the block with only that phase's steps — keys like 'Step 1' repeat across phases. The doc-review Progress tab reads this block (and Sub-phase 1b's `tdd_sections:`) as the truth; a block that is missing falls back to guessing from checkpoint.done and the TDD text."
  state_blocks: "Agent-written feature state (batches, pull_requests, step_status, tdd_sections) lives as top-level blocks in the header yaml, parsed line by line by Tools/doc-review/progress_view.py. A new kind of tracked state is a new block here, not a new file. Insert a missing block immediately before the header's closing ``` fence — never in the middle of another list such as sources_of_truth."
  on_resume:  "/resume-work <FeatureName> reads this file, reloads the current phase and its artifacts, and confirms with the engineer before continuing."
  on_close:   "/close-feature <FeatureName> sets status abandoned, superseded, on_hold or complete (engineer picks; abandoned default) and appends to a '## Closed' history section. Checkpoint and Gates Passed are kept. Closed features are hidden from /active-features; `session_lifecycle.py features --closed` lists the reopenable ones."
  on_reopen:  "/reopen-feature <FeatureName> returns abandoned, superseded or on_hold to in_progress and appends a reopen entry; complete is final. Resume afterwards with /resume-work."
```

Write the gate block **before** closing the session. A gate that is confirmed in chat
but not written to the progress file is lost to the next session.

---

## Phases

```yaml
phases:
  1_intake:
    file: ./Phase1_Intake.md
    goal: Convert GDD to structured documents, identify tasks and edge cases, confirm scope
    gate: TDD, task list, use cases, and edge cases reviewed and approved by engineer
    recommended_agent: general-purpose
    recommended_model: sonnet

  2_discovery:
    file: ./Phase2_Discovery.md
    goal: Load rules, explore codebase, confirm all dependencies are visible
    gate: Discovery report approved — no missing source files
    recommended_agent: explore        # use /discover <SystemName> for targeted area surveys
    recommended_model: haiku          # pure search, no generation

  3_design:
    file: ./Phase3_Design.md
    goal: Reconcile the TDD with Discovery — file plan, missing contracts, Phase 3 TBDs, corrections — written back into the TDD (no separate design doc, no new diagrams)
    gate: Design delta approved (or confirmed empty) — NO CODE WRITTEN BEFORE THIS GATE
    recommended_agent: plan
    recommended_model: sonnet

  4_implementation:
    file: ./Phase4_Implementation.md
    goal: Write code file-by-file, published per task in small batch PRs (/publish-batch) the engineer reviews and merges
    gate: All files written and engineer-reviewed
    recommended_agent: general-purpose
    recommended_model: sonnet         # run /audit on each file before presenting it

  5_unit_tests:
    file: ./Phase5_UnitTests.md
    goal: JSON deserialization tests + behavior and boundary tests traced to UseCases.md
    gate: All tests passing, TBD cases logged as follow-up tasks
    recommended_agent: general-purpose
    recommended_model: sonnet

  6_integration:
    file: ./Phase6_Integration.md
    goal: Wire feature into factories, registries, manifests; run required tools
    gate: Project compiles, all integration steps confirmed
    recommended_agent: explore        # verify integration points exist before editing
    recommended_model: haiku

  7_verification:
    file: ./Phase7_Verification.md
    goal: Final rules compliance pass across all files
    gate: Engineer confirms feature complete
    recommended_agent: explore        # grep for rule violations, no generation needed
    recommended_model: haiku

  8_retrospective:
    file: ./Phase8_Retrospective.md
    goal: Identify discovery gaps, missing patterns, gotchas, and process improvements; write approved changes to metadata files
    gate: All approved changes written and confirmed by engineer
    recommended_agent: general-purpose  # run via /end-session
    recommended_model: sonnet
```

```yaml
consumers:   # renaming or renumbering a phase means updating every one of these
  progress_view: "Tools/doc-review/progress_view.py parses phase keys and files: step headings must match 'Step N —', 'Category N' or 'Sub-phase Na'; gates by `phase_completed: \"Phase N\"`"
  progress_view_tests: "Tools/doc-review/tests/test_progress_view.py fixtures"
  retrospective: "Phase8_Retrospective.md `phase_N_<name>` keys"
  in_flight: "`current_phase` in every in-flight <Feature>_Progress.md"
```

---

## Handoff Format

At every gate, produce this summary and append it to the progress file before loading the next
phase file:

```yaml
phase_handoff:
  phase_completed:   "Phase N — Name"
  gate_confirmed_by: "confirmed"
  key_decisions:     [decisions made this phase]
  carry_forward:     [information the next phase needs]
  open_items:        [anything deferred or unresolved]
  consistency_findings:  # Phase 1 only — Sub-phase 1c's findings, each pre-tagged ✅/⚠️/❌
    - "✅ or ⚠️ or ❌ <finding> — <outcome: acknowledged/reworked, one line why>"
```

`consistency_findings` is rendered by the local doc-review preview server as a sub-item nested
under Phase 1's "Sub-phase 1c — Consistency and Gap Review" step once this block is written —
see `Systems/LocalDocReview.md` (host metadata repo) and `Tools/doc-review/progress_view.py`.

---

## Router check (used by /end-session phase retros)

```yaml
expected_loads:
  - "this index and the phase file for the session's phase"
  - "the rule files the phase names (Phase 4 re-reads CodingStandards and ArchitecturalPrinciples)"
expected_tools:
  4_implementation: ["/audit per file, before it is presented", typecheck.py, "/publish-batch per batch of C# files"]
  5_unit_tests:     ["/audit on test files", typecheck.py]
  6_integration:    ["/audit on changed files", typecheck.py]
  7_verification:   ["/audit over all created and modified files"]
missed_audit: "A file written in phases 4–6 without an /audit run, or a Gate 7 without the full run, is a router miss."
```

---

## Templates

```yaml
templates:
  tdd:      ../Templates/TDD_Template.md        # fill during Phase 1
  progress: ../Templates/Progress_Template.md   # create at the start of Phase 1
```
