## apply: on-demand — loaded by [[MetaRouter]]

# Create Feature — Process Index

Interactive wizard for designing and implementing a new feature. Load one phase file at a time. Do not advance past any gate without explicit engineer confirmation.


## Authoritative feature state

Read `Processes/FeatureState.md` for the shared tool contract. `state.json` is authoritative;
Progress Markdown is generated. All legacy references below to editing progress mean tool
operations, never direct Markdown/JSON edits. Use focused `get`, revision-checked mutations,
and explicit migration for legacy features. Preserve engineer approval gates.



```yaml
features_root: "Resolve with Tools/setup/project_config.py --project <project-root> get features (CLI/env/config/legacy precedence)"
working_folder: "<features_root>/<FeatureName>/   # GDD, TDD, TaskList, UseCases, Discovery, Architecture docs"
state_file:     "<working_folder>/state.json  # authoritative; shared feature-state CLI"
progress_file:  "<working_folder>/<FeatureName>_Progress.md  # generated read-only view"
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

Chat context does not survive a session end or a summary. Structured feature state does.
The YAML instructions below describe logical state updates through the shared CLI; they do
not authorize direct edits to generated Progress Markdown.

```yaml
progress_file:
  create:     "At the start of Phase 1, use feature-state create; never recreate an existing JSON or legacy feature."
  on_session: "Add the current session folder name (from the Session tracking block) to `sessions` the first time this session writes the file. Readers match entries by the id8 suffix, so a later lane rename does not break them."
  on_gate:    "Append the phase_handoff block (below) under 'Gates Passed', set current_phase to the next phase, clear the Checkpoint section, update artifacts and the sources_of_truth versions from this session's last publish or explicit read — never fetch an external page only to refresh its version (local-first, see ExternalDocPass). If this phase added or split a task beyond Phase 1's TaskList.md (e.g. Phase 3 splitting T2 into T2 + T16), update TaskList.md and state.json's `tasks` array in this same gate — the TDD's Development Plan alone is not enough; all three must list the same tasks before the gate is recorded."
  mid_phase:  "/checkpoint replaces the Checkpoint section — where work stopped and what comes next."
  on_step:    "Starting a step (its key: 1a, Step 3, Category 2) → set it `in_progress` under `step_status:`; the engineer acknowledging it → `done`. When a phase starts, replace the block with only that phase's steps — keys like 'Step 1' repeat across phases. The doc-review Progress tab reads this block (and Sub-phase 1b's `tdd_sections:`) as the truth; a block that is missing falls back to guessing from checkpoint.done and the TDD text."
  state_blocks: "Feature state (batches, pull_requests, step_status, tdd_sections) lives in state.json. Extend the shared versioned schema and validated commands for new state; never add authoritative Markdown blocks."
  on_resume:  "/resume-work <FeatureName> reads this file, reloads the current phase and its artifacts, and confirms with the engineer before continuing."
  on_close:   "/close-feature <FeatureName> sets status abandoned, superseded, on_hold or complete (engineer picks; abandoned default) and appends to a '## Closed' history section. Checkpoint and Gates Passed are kept. Closed features are hidden from /active-features; `session_lifecycle.py features --closed` lists the reopenable ones."
  on_reopen:  "/reopen-feature <FeatureName> returns abandoned, superseded or on_hold to in_progress and appends a reopen entry; complete is final. Resume afterwards with /resume-work."
```

Write the gate block **before** closing the session. A gate that is confirmed in chat
but not written to the progress file is lost to the next session.

---

## Phase Report Convention

For phases 2 through 7, before presenting the phase's gate summary to the engineer for approval:

1. Generate `<FeatureName>_<ReportLabel>.md` summarizing that phase's work and findings
2. Save it to the feature's working folder (alongside other feature documents)
3. Register it with the feature-state tool:
   ```
   python3 Tools/feature-state/feature_state.py phase-report <feature_dir> \
     --payload '{"phase": "<phase_key>", "path": "<FeatureName>_<ReportLabel>.md"}' \
     --revision <N>
   ```
4. The preview server will then show that report as a persistent tab (Phase N: Label Report)

The report becomes the artifact the engineer reviews to decide gate approval — a "final review moment" before the gate is recorded. Phases 1 and 8 are exempt: Phase 1 already produces four documents (GDD/TDD/TaskList/UseCases) before its gate; Phase 8 writes retro.md into the session reports folder.

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
    report: <FeatureName>_Discovery.md
    recommended_agent: explore        # one Explore agent per system for targeted area surveys
    recommended_model: haiku          # pure search, no generation

  3_design:
    file: ./Phase3_Design.md
    goal: Reconcile the TDD with Discovery — file plan, missing contracts, Phase 3 TBDs, corrections — written back into the TDD (no separate design doc, no new diagrams)
    gate: Design delta approved (or confirmed empty) — NO CODE WRITTEN BEFORE THIS GATE
    report: <FeatureName>_Design.md
    recommended_agent: plan
    recommended_model: sonnet

  4_implementation:
    file: ./Phase4_Implementation.md
    goal: Write code file-by-file, published per task in small batch PRs (/publish-batch) the engineer reviews and merges
    gate: All files written and engineer-reviewed
    report: <FeatureName>_Implementation.md
    recommended_agent: general-purpose
    recommended_model: sonnet         # cslint clean per file before presenting it; one /audit per batch

  5_unit_tests:
    file: ./Phase5_UnitTests.md
    goal: JSON deserialization tests + behavior and boundary tests traced to UseCases.md
    gate: All tests passing, TBD cases logged as follow-up tasks
    report: <FeatureName>_UnitTests.md
    recommended_agent: general-purpose
    recommended_model: sonnet

  6_integration:
    file: ./Phase6_Integration.md
    goal: Wire feature into factories, registries, manifests; run required tools
    gate: Project compiles, all integration steps confirmed
    report: <FeatureName>_Integration.md
    recommended_agent: general-purpose  # edits registries/manifests and runs generators — Explore is read-only
    recommended_model: sonnet

  7_verification:
    file: ./Phase7_Verification.md
    goal: Final rules compliance pass across all files
    gate: Engineer confirms feature complete
    report: <FeatureName>_Verification.md
    recommended_agent: general-purpose  # full /audit judgement review; mechanical tags are the cslint hook's
    recommended_model: sonnet

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
  phase_models: "Tools/session-lifecycle/session_lifecycle.py phase_models() reads each phase's recommended_model with '^\\s+recommended_model:\\s*(\\w+)' — keep the value a bare alias on the same line"
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
  4_implementation: ["/audit once per publish batch, before it is published", typecheck.py, "/publish-batch per batch of C# files"]
  5_unit_tests:     ["/audit once over the test files", typecheck.py]
  6_integration:    ["/audit once over the changed files", typecheck.py]
  7_verification:   ["/audit over all created and modified files"]
missed_audit: "A file written in phases 4–6 that no /audit run covered, an audit applied inline instead of through the Skill tool (a self-review), or a Gate 7 without the full run, is a router miss."
```

---

## Templates

```yaml
templates:
  tdd:      ../Templates/TDD_Template.md        # fill during Phase 1
  progress: ../Templates/Progress_Template.md   # create at the start of Phase 1
```
