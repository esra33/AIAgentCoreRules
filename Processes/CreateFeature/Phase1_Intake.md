## apply: on-demand — loaded by [[CreateFeature/index]]

# Phase 1 — Intake

Goal: Convert the GDD into a complete TDD and supporting documents. Work section by section with the engineer. Do not skip or summarize — each TDD section must be explicitly addressed before moving to the next.

Output files produced by this phase:
```yaml
outputs:
  - "[FeatureName]_TDD.md        — filled from ../Templates/TDD_Template.md"
  - "[FeatureName]_TaskList.md   — ordered actionable items from the Development Plan"
  - "[FeatureName]_UseCases.md   — use cases and edge cases table"
  - "[FeatureName]_GDD.md        — AI-friendly version of the source GDD (if provided)"
  - "[FeatureName]_Progress.md   — created first, from ../Templates/Progress_Template.md (see index.md 'Progress File')"
```

Intake is the longest phase and often spans sessions. After each TDD section is agreed, suggest
`/checkpoint` if the session is getting long.

If the TDD is also published for review outside the repository (e.g. Confluence), or its diagrams
are reviewed on a board (e.g. Miro), load [[ExternalDocPass]] (`../ExternalDocPass.md`) before the
first publish and run every round of review comments as one pass. Diagrams iterate locally against
their source file and push to the board on the same schedule as the document, not per revision.
Review round trips were the largest cost of an Intake phase.

**Before the first publish (and any publish after a session of decisions):** list every decision
changed this session, grep the TDD and its diagram sources for the old wording, and fix each
earlier section that now contradicts it. A contradiction that is a real design conflict, not just
stale wording, goes to the engineer. One sweep found four stale statements and one real conflict
in sections that had already been confirmed.

---

## Sub-phase 1a — GDD Conversion

If the engineer provides a GDD (PDF or document):

```yaml
gdd_conversion:
  - Read the full document.
  - Convert to clean Markdown preserving all section headings, intent, and detail.
  - Do not summarize, condense, or omit any section.
  - Save as [FeatureName]_GDD.md in the feature's working folder.
  - Confirm the conversion with the engineer before proceeding.
```

If there is no GDD but there are planning notes, threads or a scope summary, write a pseudo-GDD
instead:

```yaml
pseudo_gdd:
  - Make it use-case driven — do not transcribe the notes.
  - "Sections: Problem · codebase survey · design questions (options + decision) · use cases · open items."
  - "Mark each open item ⚠️ / 🔧 / 📐 / ✅."
  - Model it on an existing pseudo-GDD in the project, if one exists.
  - Save as [FeatureName]_GDD.md and confirm it with the engineer before proceeding.
```

If there is no GDD and no planning material, skip to 1b and gather information through direct questions.

---

## Sub-phase 1b — TDD Section-by-Section

Work through each TDD section with the engineer. Do not proceed to the next section until the current one is agreed upon. Fill the TDD as you go.

Record each section's state in the progress file's `tdd_sections:` block as you go — the doc-review
Progress tab shows it (○ not started, ~ drafting, ✓ approved):

```yaml
tdd_sections:
  - "Writing or revising a section in the TDD → `<Section>: drafting` (the '### Section:' name below)."
  - "The engineer agrees the section → `<Section>: approved`. Never mark a section approved because text is in the TDD."
  - "A section reverted to a placeholder → remove its entry."
```

---

### Section: Objective

Ask:
> "Describe the feature in 2–3 sentences. What problem does it solve and what triggers it?"

```yaml
objective_checks:
  - Is the goal clear and measurable?
  - Does it describe what the feature does, not how?
  - Would a new engineer understand what this feature is from this alone?
```

---

### Section: Architecture

Ask:
> "Do you have an architecture diagram? If not, describe the high-level components and how they interact."

```yaml
architecture_checks:
  - "Before drafting, load the host SystemIndex's SystemPatterns entries that match the feature
     (e.g. GemEventPattern, PrizeFlowPattern); the TDD is now the main design document, so pattern
     guidance must apply here, not only in Phase 3."
  - Are the main classes/systems named?
  - Are the data flow and ownership clear?
  - "Note: the TDD is the feature's only design document. Capture as much as is known here,
     including diagrams; Phase 3 only fills what is still open after Discovery (File Plan, missing
     contracts, TBDs left for it) and updates these diagrams rather than drawing new ones."
  - "If diagrams exist (Diagrams/*.mmd), embed each one inline in this section under its own
     collapsible <details><summary>Mermaid Diagram: <Name></summary> block holding a fenced
     ```mermaid``` code block — do not just point to the file path in prose. A reference-only
     mention is a stale-document artifact of iterating diagrams through the local preview server
     without folding the result back into the TDD; the document must stay self-contained."
  - "Validate a diagram locally (see 'Validating a local diagram' in [[ExternalDocPass]]) before
     embedding it or editing an already-embedded one."
  - "Replace the template's placeholder bracket text with real prose — no leftover
     '[Insert architecture diagram...]' once the section has content."
  - "List every file/type the section names under a 'Files & Types Changed' subsection, classified
     NEW/MODIFIED/DELETED per [[ChangeClassification]] — three-line summary (Nature, Reason,
     Implementation) visible, anything deeper in a collapsible block. A type's exact path may still
     be TBD before Phase 2 Discovery; classify it anyway."
  - "Any structural diagram (class/component) uses [[ChangeClassification]]'s NEW/MODIFIED/DELETED
     colors and legend — a process-flow diagram keeps its own separate palette, also defined there."
  - "Declare a class's actionable methods (what it does); don't assert the specific integration/wiring
     mechanism (e.g. which type implements a listener interface) unless the engineer has already
     confirmed it — that's an implementation decision for a later phase."
```

---

### Section: Best Practices

Ask:
> "What rules must whoever implements this follow — and for each one, what actually stops someone from skipping it?"

Work through the hard rules and conventions the Architecture section implies (resource lifecycles,
who may touch what, required declarations, naming/registration conventions). For each one, sort by
the strongest mechanism that can realistically hold it, strongest first:

```yaml
enforcement_tiers:   # strongest to weakest — place each rule at the strongest tier it can reach
  - "Compile-time: the type system makes the mistake impossible to write."
  - "Generator / CI: a build step fails when the rule is broken."
  - "Test-time: a reflection check or required test fixture fails the suite."
  - "Runtime guard: the code catches/asserts the violation itself, instead of trusting the caller."
  - "Scaffolded: a wizard/tool writes the correct boilerplate by default — not enforced, but cheap to get right."
  - "Process: code review only. Last resort — a rule that lands here is one more thing to remember."
best_practices_checks:
  - Does every rule name the mechanism that holds it, not just the rule?
  - Is anything sitting at Process that could realistically move up a tier?
  - Where a rule is deliberately left as a case-by-case judgment call (not tooled), is that reasoning written down, not just the absence of a mechanism?
```

If the feature has nothing beyond ordinary coding standards, say so explicitly rather than leaving
the section blank — an empty section reads as "not considered," not "not applicable."

---

### Section: Related Documentation

Ask:
> "Are there Jira tickets, Confluence pages, GDDs, or prior TDDs to link here?"

Collect all links. Leave blank if none — do not skip the section.

---

### Section: Development Plan — Stage Levels

Ask:
> "What are the development stages for this feature? (e.g. V0 = core loop, V1 = polish, V2 = monetisation)"

For each stage, collect:

```yaml
per_stage:
  name:              "e.g. V0 — Core Loop"
  level_of_effort:   "T-shirt size (S/M/L/XL) + estimated days"
  tasks:             []   # list of concrete tasks for this stage
  assignee:          "Name of engineer responsible"
```

Populate the task table. Each task row: # | Title | Task | Assignee | Status (unchecked `[ ]` by default).
`#` is the task id — T1, T2 … numbered across the whole plan, never reused or renumbered;
/publish-batch and the doc-review Progress tab key on it.
Title is a short, human-readable task name (a few words), ready to become the Jira ticket summary.

Add as many stages as needed. The "Final Touches" stage is always included — see below.

---

### Section: Development Plan — Final Touches

This stage is **mandatory** for every feature. The following tasks are always included:

```yaml
final_touches_standard_tasks:
  - Implement and validate data reconciliation strategy
  - Implement CS Gifting Strategy
  - Add BI calls
  - Add Unit Tests
  - Implement design and support tools
  - Implement QA Debug functionality
  - Backport Systems to RST
```

Ask the engineer for the assignee and level of effort estimate (default: at least 5 days).

---

### Section: Design and Support Tools

Ask:
> "What tools or mechanisms will this feature need long term? Consider: Airtable imports, JCL vs Local testing, Disney snapshot routing, Unity asset configuration, debug menus."

Collect as a bullet list.

---

### Section: Risks

Ask:
> "What could go wrong during development or at runtime? For each risk, what is the resolution, amortization, or workaround?"

```yaml
risk_format:
  - risk: "description"
    mitigation: "resolution or workaround"
```

At minimum identify: timeline risk, integration risk, and data integrity risk.

---

### Section: Data Reconciliation Strategy

Ask:
> "How will this feature handle offline/online state conflicts? What wins — local or server data? Is there a merge strategy?"

**This section cannot be left blank.** If the strategy is not yet decided, explicitly mark it as `TBD` and log it as an open item in Gate 1.

---

### Section: CS Strategy

Ask:
> "How will Customer Support gift or reset this feature for affected players?"

**This section cannot be left blank.** If the strategy is not yet decided, mark as `TBD` and log as an open item.

---

### Section: Edge Cases

Work through the GDD and development stages to surface edge cases. Use this as a starting set and expand with the engineer:

```yaml
edge_case_prompts:
  - "What happens if the feature expires while the player is mid-action?"
  - "What happens if the player closes the game during a progress save point?"
  - "What happens if the server returns an unexpected state on boot?"
  - "What happens if two conflicting events are active simultaneously?"
  - "What happens if a reward has already been claimed but the flag is missing?"
```

For each edge case identified, fill a table row: `# | Description | Solution`.

If the solution is unknown, mark it `TBD` and log as an open item.

---

### Section: Other Notes

Ask:
> "Is there anything important that doesn't fit cleanly into the other sections?"

Optional — leave blank if nothing applies.

---

### Section: Future Work

Ask:
> "What could be added to this system in future iterations that is explicitly out of scope now?"

Capture as a bullet list. This sets expectations and prevents scope creep during implementation.

---

## Sub-phase 1c — Consistency and Gap Review

After completing all TDD sections, evaluate the feature against the existing project:

```yaml
consistency_checks:
  - Does this feature conflict with or duplicate any existing system?
  - Are there dependencies on systems that do not yet exist?
  - Is the Data Reconciliation Strategy consistent with how similar features handle it?
  - Is the CS Strategy consistent with the project's gifting patterns?
  - Are the Final Touches tasks achievable within the scope of the development plan?
  - Are all edge cases in the table given a solution (or explicitly TBD)?
  - Are the BI calls for this feature identified, even if not yet implemented?
```

Present findings as a numbered list, each line prepended with a status emoji:

```yaml
finding_status:
  "✅": "Passes cleanly — no action needed, listed for completeness."
  "⚠️": "Passes but needs attention — a real gap or omission, but not necessarily wrong."
  "❌": "Fails — a real conflict, contradiction, or missing required piece."
```

For every ⚠️ or ❌ finding, ask the engineer to either:
- **acknowledge it and continue** — the current state is intentional, no rework needed, or
- **rework it now** — fix it before moving on to 1d.

Record the outcome next to the finding (`acknowledged` or `reworked`, one line on why). An
acknowledged ❌ is not silently dropped: log it as an open item at Gate 1 with an owner, the same as
a TBD. Do not block the gate on an acknowledged item — that is what acknowledging it means.

Carry the finalized list (status emoji + finding + outcome, one string per line) into the Gate 1
`phase_handoff` block's `consistency_findings` field (see Handoff Format in index.md). The preview
server's Progress tab renders it as a sub-item under this step once that block is written.

---

## Sub-phase 1d — Metrics

Session metrics are already running (SessionStart hook — see MetaRouter Session Lifecycle), and the
lane/title are already set by `/resume-work` or `/feature` before this phase file loads. Remind the
engineer once:
- `/inaccuracy <reason>` immediately after correcting an agent mistake.
- `/iteration <description>` when deliberately changing direction or refining scope.
- `/end-session` at the end of every working session — each session of this feature gets its own metrics.

---

## Sub-phase 1e — Document Generation

With all TDD sections complete and reviewed, produce the output documents:

**`[FeatureName]_TDD.md`** — fill `../Templates/TDD_Template.md` with all gathered content. Set version to `1.0.0`.

**`[FeatureName]_TaskList.md`** — extract all tasks from all Development Plan stages in order, one line per task:

```yaml
task_list_format:
  - stage: "V0 — Core Loop"
    tasks:
      - {id: T1, status: "[ ]", title: "Short task name (Jira summary)", task: "Task description", assignee: "Name"}
```

```yaml
task_list_rules:
  id:     "T<n>, matching the TDD Development-plan '#' column. Every task has one: /publish-batch names branches feature/<FeatureName>/<id> and stops when a task has no id."
  order:  "Keep id, status, title first and in that order — progress_view.py parses that one-line form."
  status: "[ ] todo · [~] partial · [x] done"
```

**`[FeatureName]_UseCases.md`** — compile all edge cases from the TDD plus any additional scenarios identified during 1b/1c:

```yaml
use_case_format:
  - id: 1
    description: "Scenario description"
    solution: "How it is handled (or TBD)"
```

---

## Sub-phase 1f — External Publish (optional)

Ask:
> "Do you want to publish this TDD to Confluence and its architecture diagrams to Miro now?"

```yaml
if_yes:
  - "Load [[ExternalDocPass]] and the host's doc-conventions file (e.g. ConfluenceDocs.md) before the first publish of this session — required even if a publish workflow was already set up in an earlier session."
  - "Publish the TDD to Confluence per ExternalDocPass's Publish pass."
  - "Push each diagram to its Miro board per 'Diagrams reviewed on a board', in the same pass — never before the Confluence page exists."
  - "Embed the Miro board/frame links in the Confluence page's 'Architecture Diagrams (Miro)' subsection (see the host's doc-conventions file) on that same pass."
  - "Record both pages in the progress file's `sources_of_truth` (kind, id, title, version)."
if_no:
  - "Skip. The engineer can publish later from any phase via [[ExternalDocPass]] — it is not re-asked automatically."
```

---

## Gate 1 — Intake Complete

Present the following summary to the engineer:

```yaml
gate_1_summary:
  feature_name:          ""
  owning_system:         ""
  tdd_location:          ""
  task_count:            0
  stage_count:           0
  use_case_count:        0
  tbd_items:             []   # sections or edge cases marked TBD — must have owners
  open_items:            []   # unresolved gaps from 1c
```

**Wait for engineer confirmation, then close the phase session (index.md "One Session per Phase") — do not load Phase 2 here.**
All `tbd_items` must have an owner before the gate is cleared — unowned TBDs block progression.

---

## Router check (used by /end-session phase retros)

```yaml
expected_loads:
  - "../CreateFeature/index.md and this phase file"
  - "[[ExternalDocPass]], before the first publish or review-comment pass of a session that publishes the TDD externally (e.g. to Confluence) — required every such session, even one that resumes a publish workflow already established in an earlier session"
missed_publish_discipline: "A publish or review-comment pass run in this phase without reloading ExternalDocPass.md first is a router miss, even if the publish itself succeeds."
```
