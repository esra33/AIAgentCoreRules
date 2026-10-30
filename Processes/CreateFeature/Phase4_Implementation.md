## apply: on-demand — loaded by [[CreateFeature/index]]

# Phase 4 — Implementation

Goal: Write code file-by-file following the approved design. Present each file to the engineer before moving to the next.

Implement in this order: **interfaces → concrete classes → integration glue.**

Before the first file: re-read `../../Rules/CodingStandards.md` and `../../Rules/ArchitecturalPrinciples.md`
(and ResourceManagementRules / MultyStepOperationsRules if Phase 2 loaded them). Phase 2 may be
several sessions or a context summary ago.

---

## Per-File Checklist

Run after writing every file. Do not present a file to the engineer until all checks pass.

```yaml
per_file_checks:
  stop_and_verify:   "StopAndVerify post-generation checklist passed."
  naming:            "All members follow CodingStandards §1 naming conventions."
  organization:      "Constants → Delegates → Events → Fields → Properties → Constructors → Methods."
  method_order:      "public override → public → protected override → protected → private."
  accessibility:     "No public fields. Setters at maximum restriction. All modifiers explicit."
  resource_symmetry: "Every subscription has unsubscribe. Every acquire has release. Guards use IDisposable/using."
  method_design:     "No method named with And. Composers sequence only. Leaves touch data only."
  audit:             "REQUIRED: /audit <file> ran and every violation is fixed or reported. It covers the checks above; self-review is not a substitute."
  tests:             "Writing a test file: read ../../Rules/TestingRules.md (and the host project's testing-setup rule, if it has one) before writing it. CodingStandards and ArchitecturalPrinciples do not cover tests."
  steady_state:      "If this file implements event listeners, poll handlers, or subscription-based updates: verify not just immediately after an action (snapshot) but also at idle with no data change — ensure no redundant rebuilds, repaints, or state mutations occur. E.g., a poll handler should render identically on tick N and tick N+1 when data has not changed."
```

Run `/audit <file>` before presenting each file — a file is not presented until its audit has
run. Present each file to the engineer after writing it. Do not move to the next file until the
current one is acknowledged.

After each acknowledgment, update the progress file's Checkpoint: add the file to `done`, marked
`(audited)`, and set `next` to the following file from the TDD's File Plan. Implementation is where a session most often
ends mid-phase.

When a PR opens for one of the TDD's V-phases, run `/feature-pr <PR>`: it lists the PR under
`pull_requests` in the progress file, so the doc-review Progress tab shows its review notes, and
records each addressed note in this feature's Checkpoint.

---

## Batched Publishing

C# and related files (`.cs`, `.asmdef`, generated parsers, config JSON) are published per task
in small batches, so the engineer reviews a few files at a time instead of the whole task.
Python tools, Markdown and agent metadata are exempt.

```yaml
batched_publishing:
  start_task:  "/publish-batch plan — a worktree and branch per task (feature/<FeatureName>/<task_id>, from the engineer's user branch) and a batch plan the engineer approves."
  per_batch:
    - "Write the batch's files with the Per-File Checklist above; /audit each one. typecheck.py passes."
    - "/publish-batch publish — commit, push, open a PR against the user branch, and output the change table (Change | File · Type | What changed | Why) for every file added, modified or removed."
    - "The engineer reviews on GitHub and runs the notes by the agent through /feature-pr <PR>; fixes are pushed to the same PR."
    - "/publish-batch status — once the PR is merged, the batch is complete; the branch syncs with the user branch and the next batch starts."
  end_task:    "/publish-batch finish — after the last batch merged, the task's worktree is removed."
  acknowledgment: "A merged batch PR is the per-file acknowledgment for every file in it: add those files to the Checkpoint `done`, marked (audited)."
  one_at_a_time: "One open batch PR per task; the next batch is not published until the current one is merged."
```

The progress file's `batches:` block records each task's plan and how many batches merged —
batch N of M, where N = merged + 1 and M = the plan's length.

---

## Gate 4 — Implementation Complete

All files written and engineer-reviewed. Engineer confirms implementation is ready for integration.
