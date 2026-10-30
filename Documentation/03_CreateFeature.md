# Create Feature Process

The full process for building a new feature, from GDD to verified, integrated code. It runs as
an interactive wizard of **8 phases**, each ending in a **gate** that the engineer must
explicitly confirm. The agent loads one phase file at a time and never passes a gate on its own.

Start it with `/feature <FeatureName> [path to GDD]`.

## Working folder

Everything the process produces for a feature lives in one folder in the host project (under a
personal, git-ignored path set in `CreateFeature/index.md`):

```
Assets/GitIgnoreAssets/Features/<FeatureName>/
  <FeatureName>_GDD.md           AI-friendly copy of the source GDD
  <FeatureName>_TDD.md           Technical design document — the only design doc; Phase 3 updates it
  <FeatureName>_TaskList.md      Ordered tasks from the development plan
  <FeatureName>_UseCases.md      Use cases and edge cases
  <FeatureName>_Discovery.md     Approved discovery report
  Diagrams/*.mmd                 Diagram sources, embedded in the TDD
  <FeatureName>_Progress.md      Resume state: gates passed and the current checkpoint
```

Each task in the task list is one line with an id that matches the TDD development plan's `#`
column — `- {id: T1, status: "[ ]", title: "..."}`. The preview's Progress tab parses that form,
and `/publish-batch` names a task's branch after its id, so it stops on a task without one.

## The phases

| # | Phase | Goal | Gate |
|---|---|---|---|
| 1 | **Intake** | Convert the GDD into a TDD, task list, use cases and edge cases | All documents reviewed and approved; every TBD item has an owner |
| 2 | **Discovery** | Load rules, explore the codebase, confirm every dependency is visible | Discovery report approved, with no missing source files |
| 3 | **Design** | Reconcile the TDD with Discovery: file plan, missing contracts, TBDs left for Phase 3, corrections — written back into the TDD | Design delta approved, or confirmed empty — **no code is written before this gate** |
| 4 | **Implementation** | Write code file by file | Every file written, audited and acknowledged by the engineer |
| 5 | **Unit Tests** | JSON deserialization, behavior and boundary tests traced to the use cases | All tests passing; deferred cases logged as follow-up tasks |
| 6 | **Integration** | Wire into factories, registries and manifests; run generators | Project compiles; every integration step confirmed |
| 7 | **Verification** | Final rules-compliance pass across every file | Engineer confirms the feature is complete |
| 8 | **Retrospective** | Find discovery gaps, missing patterns, gotchas and process gaps; apply approved improvements | Every approved change written and confirmed |

Renaming or renumbering a phase is not a one-file change: `progress_view.py` parses phase keys,
step headings (`Step N —`, `Sub-phase Na`) and `phase_completed: "Phase N"` gates, its tests carry
fixtures of them, Phase 8 has `phase_N_<name>` keys, and in-flight progress files store
`current_phase`. The `consumers:` block in the process index lists them all.

### Phase 1 — Intake

- **1a GDD conversion** — if a GDD is provided, it is converted to Markdown in full, without
  summarising. With no GDD but planning notes, threads or a scope summary, a use-case-driven
  pseudo-GDD is written instead (problem, codebase survey, design questions with options and a
  decision, use cases, open items marked ⚠️/🔧/📐/✅), modelled on an existing one if the project
  has one — the notes are not transcribed.
- **1b TDD, section by section** — objective, architecture, Best Practices (the rules an
  implementer must follow, each with what stops someone from skipping it), related docs, development plan
  (stages with T-shirt sizes and assignees), final touches, tools, risks, data reconciliation
  strategy, CS strategy, edge cases, CMS data pipeline (optional — only for Airtable-driven or
  OTA-configurable content), notes and future work. Each section is agreed with the engineer
  before moving on. The data reconciliation strategy cannot be left blank; if it is undecided it
  is marked TBD and logged as an open item.
  Before the Architecture section is drafted, the host SystemIndex's SystemPatterns entries that
  match the feature (e.g. GemEventPattern, PrizeFlowPattern) are loaded: the TDD is now the main
  design document, so pattern guidance applies here, not only in Phase 3.
  The Architecture section embeds each `Diagrams/*.mmd` diagram inline, each in its own
  collapsible `<details><summary>Mermaid Diagram: <Name></summary>` block holding a fenced
  `mermaid` code block, so the TDD stays self-contained — a path mentioned in prose is not enough.
  Diagrams are validated locally before they are embedded or edited, and the template's
  placeholder text is replaced once the section has content (see [[TDD_Template]]).
  A class is described by its actionable methods (what it does); the wiring mechanism (e.g. which
  type implements a listener interface) is left to a later phase unless the engineer has already
  confirmed it.
- **1c consistency and gap review** — findings are a numbered list, each tagged ✅ (passes),
  ⚠️ (passes but needs attention) or ❌ (fails). For every ⚠️ or ❌ the engineer chooses to
  **acknowledge and continue** or **rework now**, and the outcome is recorded beside the finding.
  An acknowledged ❌ is logged as a Gate 1 open item with an owner; it does not block the gate.
  The final list goes into the Gate 1 handoff's `consistency_findings` field, and the doc-review
  [[12_DocReview#Progress tab|Progress tab]] shows it under the 1c step.
- **1d metrics** — a one-time reminder of `/inaccuracy`, `/iteration` and `/end-session`. The
  lane and title are already set by `/feature` or `/resume-work`, so this step no longer sets them.
- **1e document generation**.
- **1f external publish (optional)** — the agent asks whether to publish the TDD to Confluence
  and its diagrams to Miro now. If yes, it loads [[ExternalDocPass|External Doc Pass]] and the
  host's doc-conventions file, publishes the TDD, pushes each diagram to its Miro board in the
  same pass (never before the Confluence page exists), embeds the board links in the page's
  "Architecture Diagrams (Miro)" subsection, and records both pages in the progress file's
  `sources_of_truth`. If no, it is not asked again; publishing can happen later from any phase.
- **Pre-publish sweep** — before publishing, every decision changed in the session is grepped
  for across the TDD and its diagram sources, and earlier confirmed sections that contradict it are
  fixed (real design conflicts go to the engineer).
- **Publishing for review** — if the TDD also goes to Confluence (or another wiki), the
  [[ExternalDocPass|External Doc Pass]] process applies. The page is built locally, measured, and
  published in one call per page — a body over ~50K characters is split into child pages first,
  because a call cut off mid-body saves a truncated page. Before every send, the body is confirmed
  to be the real, complete content just built, not a placeholder or truncated fragment. Every
  publish is fetched back and checked. Each round of review comments is one pass: one read of the page and its comments,
  every ready item applied together, one update, and a report of which threads can be resolved.
  The update is verified like a publish; that check (at most one fetch per page) is outside the
  pass's two-read budget.
  The host project's conventions file sets the layout and the comment convention. Review round
  trips were the largest cost of an Intake phase (191M tokens for one feature) before passes.
  Diagrams are validated locally (`mermaid-cli`) before they are embedded or pushed to a board —
  see External Doc Pass's "Validating a local diagram".

### Phase 2 — Discovery

The agent loads Stop and Verify, Coding Standards and Architectural Principles, plus
Multi-Step Operations, Resource Management and Testing rules when the feature needs them. It
then reads the base class or interface being extended and 1–2 similar existing features,
inventories dependencies and integration points, and checks the host project's SystemIndex for
existing Systems and SystemPatterns entries. Wide surveys go through `/discover`.

The gate report lists files read, dependencies found, integration points, reference features
and **missing source** — a non-empty missing-source list blocks the gate.

### Phase 3 — Design

A design delta, not a second design. The TDD is written in Phase 1, before Discovery reads the
code, so this phase checks it against the Discovery report and fills only what is still open:
a **File Plan** (task id, path, new/modified, responsibility) that Phase 4 works through, public
contracts the TDD left out, a decision for every TBD left for Phase 3, and corrections where the
code contradicts the TDD. A skip check comes first: when the TDD already covers all of that, the
gate is a short confirmation and can close at the end of the Phase 2 session.

Everything approved is written back into the TDD (version bump and Versions row), with the task
list and use cases updated when a decision changes them. There is no separate
`_Architecture.md` and no new diagrams: if the architecture changes, the existing `Diagrams/*.mmd`
sources and their embedded copies in the TDD are updated and re-validated.

### Phase 4 — Implementation

Order: interfaces → concrete classes → integration glue. Before the first file the agent
re-reads the rule files, because Phase 2 may be several sessions ago. Every file runs through
`/audit` **before** it is presented to the engineer (required, recorded as `(audited)` in the
checkpoint); the next file is not started until the current one is acknowledged. Before writing
a test file, the agent reads `Rules/TestingRules.md` (and the host project's testing-setup rule,
if it has one); the coding standards and architectural principles do not cover tests. For files with poll handlers, event listeners, or subscription-based updates: verification includes steady-state behavior (state unchanged across multiple ticks with no data change), not just post-action snapshots.

**Batched publishing.** C# and related files are reviewed as small pull requests rather than in
one large diff. Python tools and Markdown are exempt. Each task gets its own worktree and branch
(`feature/<Name>/<task>`), cut from the engineer's user branch, and the engineer approves a plan
that splits it into batches. Each batch is one concern, roughly ≤ 300 lines and ≤ 5 files.
`/publish-batch` commits and pushes each batch, opens a PR against the user branch, and prints
a table of every file added, modified or removed: its types, what changed and why. The engineer
reviews on GitHub and runs the notes through `/feature-pr`. Merging the PR completes the batch
and counts as the acknowledgment of its files, and only then does the next batch start. The
progress file's `batches:` block records batch N of M for each task.

### Phase 5 — Unit Tests

Three categories, each traced to a document from an earlier phase — no speculative tests:

- one JSON deserialization test per config class,
- one behavior test per row in the use cases,
- one boundary test per edge case.

For browser-based or UI features, also include **idle-behavior fixtures** for any polling listeners or event handlers: initialize/render, tick multiple times with no data change, and assert state remains unchanged (no redundant rebuilds, no re-wrapping of highlights, no spurious repaints). Idle tests catch bugs snapshot tests miss.

The agent runs the host project's compile check (`typecheck.py`); the engineer runs the tests in the Unity Test Runner and
reports the result. The agent never claims a pass it has not seen. Test files are run through
`/audit` before the gate.

### Phase 6 — Integration

Registration in factories, registries and manifests, and running code generators. Editor-only
generators (for example a JSON parser generator window) are listed with exact menu paths for
the engineer to run. Changed C# files (not generated ones) are run through `/audit` before the
gate.

### Phase 7 — Verification

One full `/audit` over every file the feature created or modified. Its report is the evidence
for the final check of naming, file organization, accessibility, interface boundaries, resource
symmetry and tests. It closes with a completion summary of what was built, the files created and
modified, the tools run, the audit result and anything deferred.

A phase retro flags any file from phases 4–6 written without an `/audit` run, or a Gate 7
without the full run.

### Phase 8 — Retrospective

Run through `/end-session` (see [[07_SessionTracking#Retrospectives|Retrospectives]]). It reads the metrics of **every** session that worked on the
feature and proposes changes to Systems docs, patterns, rules and processes. Nothing is written
until the engineer approves the report, and each change is confirmed individually. A change to
a rule, process or Systems doc also updates its `Documentation/` page.

## Gate handoffs

At every gate the agent produces a handoff summary:

```yaml
phase_handoff:
  phase_completed:   "Phase N — Name"
  gate_confirmed_by: "confirmed"
  key_decisions:     []
  carry_forward:     []   # what the next phase needs
  open_items:        []   # deferred or unresolved
  consistency_findings: []  # Phase 1 only — 1c's ✅/⚠️/❌ findings with their outcome
```

This block is appended to the feature's progress file **before** the session closes.

## One session per phase

Each phase runs in its own session. Context stays small, metrics show what each phase cost,
and each phase can start on its recommended model. When the engineer confirms a gate, the agent:

1. writes the handoff block and advances the progress file,
2. runs `/end-session`, which writes a short retro for the phase (the full retrospective is
   Phase 8, which reads all of them),
3. prints the command for the next phase and stops, for example
   `claude --model haiku "/resume-work MyFeature"`.

A phase that takes several sittings ends each one with `/checkpoint`; the next sitting is a new
session for the same phase. To keep going in the same session anyway, say so at the gate, and
the reason is recorded in the gate block.

## Working across sessions — checkpoint and resume

A feature usually spans several sessions, and chat context does not survive a session ending or
being summarised. The progress file (`<FeatureName>_Progress.md`) does.

| Event | What is written to the progress file |
|---|---|
| `/feature <Name>` | File created from the template; the session is added to its session list |
| Every gate | The handoff block is appended; the current phase advances; the checkpoint is cleared; the session closes with a phase retro |
| Each approved file in Phase 4 | The file is added to the checkpoint's `done` list and `next` is set |
| `/publish-batch` in Phase 4 | The task's `batches:` entry is written (plan, merged count, open PR); each PR is also listed under `pull_requests`; a merged batch adds its files to `done` |
| Each step started or acknowledged | `step_status:` records the current phase's steps as `in_progress` or `done`; in Sub-phase 1b, `tdd_sections:` records each TDD section as `drafting` or `approved`. The doc-review Progress tab shows these |
| `/checkpoint` | The checkpoint is replaced: done, in flight, next action, pending decisions, notes |
| `/end-session` mid-phase | `/checkpoint` runs automatically first |
| `/close-feature <Name> [reason]` | Status set to the picked closing status — `abandoned` (default), `superseded`, `on_hold` or `complete` — and an entry appended to the `Closed` history section; checkpoint and gate blocks are kept. The feature drops off `/active-features` |
| `/reopen-feature <Name>` | Status returned to `in_progress` from `abandoned`, `superseded` or `on_hold` (never from `complete`) and a reopen entry appended; `/resume-work` then continues from the kept checkpoint |

All state the agent writes about a feature (`batches`, `pull_requests`, `step_status`,
`tdd_sections`) is kept as top-level blocks in the progress file's header, not in separate
files. A missing block is added just before the header's closing fence.

To continue in a new session, run **`/resume-work <FeatureName>`**. The agent:

1. switches the session to the feature lane and adds the session to the feature's list,
2. reloads the process index, the progress file, the current phase file, that phase's rule
   files, the documents it works from, and the host SystemIndex's entry for the feature's
   system (not just the feature's own Discovery/Architecture docs) if one exists,
3. checks the files on disk against the progress file and reports any drift,
4. presents a summary — phase, gates passed, what is done, what is next, pending decisions —
   and **waits for confirmation** before continuing.

`/resume-work` with no name lists every feature that is not complete and asks which one to pick
up, then resumes it. `/active-features` shows the same list and also prints each feature's
resume command. A new session that isn't already working on a feature shows the same list at
start and offers to resume. Running `/feature` on a feature that
already has a progress file offers `/resume-work` instead of restarting Phase 1.

The session is tagged with the feature and phase, so the meta-analysis report can show cost
**per feature** and **per phase**. Documents edited outside the feature folder, such as the
Confluence TDD, are listed under `sources_of_truth` in the progress file with the version last
read. `/resume-work` reports a newer version as drift.

Why not just reopen the old conversation? Reopening brings back the whole previous context,
including rule files that may already have been summarised away. A resume starts clean and
loads only what the current phase needs.

**Source files:** [[CreateFeature/index]] · [[Phase1_Intake]] · [[Phase2_Discovery]] · [[Phase3_Design]] · [[Phase4_Implementation]] · [[Phase5_UnitTests]] · [[Phase6_Integration]] · [[Phase7_Verification]] · [[Phase8_Retrospective]] · [[Progress_Template]] · [[TDD_Template]] · [[Skills/feature/SKILL|/feature]] · [[Skills/checkpoint/SKILL|/checkpoint]] · [[Skills/resume-work/SKILL|/resume-work]]

---

← [[02_WorkModes|Work Modes and Routing]] · [[00_Overview|Overview]] · [[04_BugFix|Bug Fix Process]] →
