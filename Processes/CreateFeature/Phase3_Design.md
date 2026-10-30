## apply: on-demand — loaded by [[CreateFeature/index]]

# Phase 3 — Design

Goal: Reconcile the Phase 1 TDD with what Phase 2 Discovery found in the code, and produce only
what the TDD does not already pin down. The TDD is the design document — this phase does not
write a second one, and it does not draw new diagrams.

The TDD is written before Discovery reads the code, so this is the one step that checks it against
the codebase, settles what it left for Phase 3, and gives Phase 4 a concrete file plan. Anything the
TDD already covers is not restated here.

Inputs: `<FeatureName>_TDD.md` (Architecture section, embedded diagrams, TBDs) and
`<FeatureName>_Discovery.md`. Load the host SystemIndex's matching SystemPatterns entries.

---

## Step 1 — Skip Check

```yaml
skip_check:   # all four true → the delta is empty; go straight to Gate 3
  - "The TDD Architecture section names every new and modified file, each with its task id."
  - "Every new class and interface has its public contract (members, base types) in the TDD."
  - "No TBD in the TDD or use cases is left for Phase 3 to decide."
  - "Nothing in the Discovery report contradicts the TDD."
```

When the delta is empty, Gate 3 is a short confirmation and may be cleared at the end of the
Phase 2 session. Record that in the gate block's `open_items`.

---

## Step 2 — Design Delta

Structure and contracts only. No implementation code. Fill only the keys the skip check failed on.

```yaml
design_delta:
  file_plan:            # Phase 4 works through this list, task by task
    - task: "T1"
      path: "relative/path/FileName.cs"
      kind: "🟢 New | 🟡 Modified | 🔴 Deleted"   # see [[ChangeClassification]]
      responsibility: "one-line description, or what changes and why"
  contracts:            # only what the TDD lacks
    - "ClassName : BaseClass, IInterface — public members the TDD did not specify"
  tbd_resolutions:      # every TBD the TDD or use cases left for Phase 3
    - tbd: "TDD section / edge case #"
      decision: "what was decided and why"
  discovery_corrections: # TDD statements the code contradicts
    - tdd_says: "…"
      code_says: "… (Discovery file:line)"
      change: "how the design changes"
  open_questions:
    - "Ambiguity requiring engineer input"
```

Resolve every open question with the engineer before Step 3.

---

## Step 3 — Write Back to the TDD

The approved delta goes into the TDD, not a separate file.

```yaml
write_back:
  - "Add or update the Architecture section's 'File Plan' subsection (task | path | Change | responsibility), Change using [[ChangeClassification]]'s 🟢/🟡/🔴 tags."
  - "Fold new contracts into the Architecture section; replace each resolved TBD with its decision. Update the 'Files & Types Changed' list (see [[ChangeClassification]]) with exact paths now that Discovery has run."
  - "If the architecture changed (new or removed component, ownership or flow change), update the existing Diagrams/*.mmd source and its embedded copy in the TDD — validate it locally first (see 'Validating a local diagram' in [[ExternalDocPass]]), keeping it on [[ChangeClassification]]'s colors if it is a structural diagram. Do not add new diagrams in this phase."
  - "Bump the TDD version (minor for a changed decision, patch for added detail) and add a Versions row."
  - "Update the task list and use cases if a decision changed a task or an edge case solution."
  - "If the TDD is published externally, the change goes out through [[ExternalDocPass]] — one pass, not per edit."
```

---

## Gate 3 — Design Approved

Engineer explicitly approves the delta (or confirms it is empty) and the updated TDD.

**This is the last gate before code is written. The TDD's File Plan must be complete and every TBD
left for Phase 3 resolved before proceeding.**
