## apply: on-demand — loaded by [[CreateFeature/index]]

# Phase 8 — Retrospective

State changes in this phase use the shared feature-state CLI described in index.md.
Progress Markdown is generated; references to writing its fields mean tool operations.


Goal: Extract durable improvements from this feature's implementation cycle. Every answer that becomes a rule, pattern, or system entry reduces cost and back-and-forth on the next feature.

The agent completes Steps 1–7 automatically, without intermediate engineer acknowledgments. Write the investigation report before asking for approval. Engineer approval is required only to apply proposed improvements and complete Gate 8.

Delegate independent evidence gathering in parallel when supported: discovery/patterns; gotchas/rules/process; benchmarks and earlier proposals. Prefer a cheaper available model for bounded extraction. Give workers read-only assignments with evidence references; the primary agent verifies and reconciles findings and owns report/state writes. If delegation is unavailable, complete the same steps sequentially.

For every step, record findings, evidence, proposed actions and limitations; explicitly state when there are no findings. Send only a short TL;DR per step and the preview link in chat, never the full report.

---

## Step 1 — Discovery Gaps

Review what had to be looked up *after* Phase 2 that could have been pre-loaded.

```yaml
questions:
  - Were any source files requested mid-implementation that Phase 2 did not surface?
  - Were any namespaces, base classes, or tool workflows looked up on the fly?
  - Did the agent ask for files the engineer considered "obviously related"?
```

**Output:** additions to the relevant `Systems/` file (`key_interfaces`, `namespaces`, `common_gotchas`, `integration_points.tools`).

---

## Step 2 — Missing Patterns

Review whether any implementation approach was repeated across multiple files or took several cycles to get right.

```yaml
questions:
  - Was any structural pattern applied more than once that is not yet in SystemPatterns/?
  - Did the engineer correct the same type of mistake more than once?
  - Did the design require a non-obvious sequencing or wiring step?
```

**Output:** new `SystemPatterns/` file, or addition to an existing pattern file. Register in `SystemIndex.md`.

---

## Step 3 — Gotchas and Surprises

Review anything that went wrong, required a correction, or was non-obvious.

```yaml
questions:
  - Were any tool steps missed or run in the wrong order?
  - Were any base class behaviors surprising (lifecycle, save mechanics, event wiring)?
  - Were any edge cases in the data or config not covered by the existing gotchas sections?
```

**Output:** additions to `common_gotchas` in the relevant `Systems/` or `SystemPatterns/` file.

---

## Step 4 — Rules Gaps

Review whether any coding standard or architectural rule was applied that is not yet documented.

```yaml
questions:
  - Was any RSS or architectural rule referenced verbally but not present in the rules files?
  - Were there any new access modifier, naming, or resource management situations not covered?
  - Did any test scenario reveal a gap in TestingRules.md?
```

**Output:** proposed additions to `CodingStandards.md`, `ArchitecturalPrinciples.md`, `ResourceManagementRules.md`, or `TestingRules.md`.

---

## Step 5 — Process Gaps

Review whether the phase structure itself caused unnecessary cycles.

```yaml
questions:
  - Was any gate confirmed too early, requiring re-work in a later phase?
  - Was any phase missing a check that would have caught a problem earlier?
  - Was context carried between phases that should be captured in a handoff field?
```

**Output:** proposed edits to the relevant `Phase*.md` or `index.md`.

---

## Step 6 — Session Benchmarks

Before producing the report, compile the session metrics.

```yaml
steps:
  - Run the lifecycle script `compile --final` for this session (done by /end-session).
  - Read metrics.md of this session AND of every session folder listed under `sessions` in [FeatureName]_Progress.md. Deduplicate by session id8. Match each entry by its id8 suffix (`ls -d GitIgnoreReports/Sessions/*_<id8>`), not its full name — a lane change renames the folder. Also include sessions tagged with this feature that the list missed: `grep -l '"feature": "[FeatureName]"' GitIgnoreReports/Sessions/*/session.json`. Never match on folder names: the title is not always in them.
  - Sum tokens, inaccuracies and iterations across those sessions, and report them per phase as well (one session per phase; several sittings of one phase add up).
  - Read each earlier phase session's retro.md (the short phase retros). Their Corrections, Discovery gaps and Proposed changes feed Steps 1–5; carry over proposals not yet applied instead of re-deriving them.
  - Use each session's router trace to answer Steps 1 and 5 (what was loaded late, what was never loaded).
  - List the 5 heaviest operations (from the token reports' highest-cost turns, else best estimate).
  - Calculate quality rating per phase: smooth | required_correction | required_redesign.
```

If telemetry is unavailable, identify the missing coverage explicitly. Label any conversation-based estimates separately; never substitute estimates for measured totals or invent unavailable figures.

---

## Step 7 — Retrospective Report

Synthesize the investigations and produce a summary of proposed changes:

```yaml
retrospective_report:
  feature:            ""
  date:               ""
  systems_touched:    []
  proposed_changes:
    systems_updates:  []   # file: reason
    new_patterns:     []   # file: description
    rules_additions:  []   # file: rule text
    process_updates:  []   # file: change
  deferred:           []   # items that need more data before acting
  benchmarks:
    session_tokens:     ""   # summed from metrics.md of every session of this feature
    estimated_top_costs:     # agent's best estimate of 5 heaviest operations
      - operation: ""
        reason:    ""
    inaccuracy_count:   0    # summed from metrics.md
    iteration_count:    0    # summed from metrics.md
    phase_quality:           # smooth | required_correction | required_redesign
      phase_1_intake:         ""
      phase_2_discovery:      ""
      phase_3_design:         ""
      phase_4_impl:           ""
      phase_5_tests:          ""
      phase_6_integration:    ""
      phase_7_verification:   ""
```

Write the full report to `<feature-directory>/<FeatureName>_Retrospective.md` with Unity metadata when applicable. Include sections for all seven steps, measured versus estimated benchmarks, unresolved evidence gaps, and numbered recommendations. Check whether earlier proposals were already applied before repeating them.

Register the Markdown through `feature-state phase-report` with phase `8_retrospective` and the current revision. Start or reuse the project preview server, open the feature report tab, and verify the rendered report and links. Record report readiness in the checkpoint; do not advance Gate 8. The report is authoritative for the full retrospective. Session `retro.md` links to it and retains session accounting and applied-change outcomes. Report creation and registration require no engineer acknowledgment.

---

## Gate 8 — Improvements Applied

Once the engineer approves the report, execute the proposed changes file by file.

Confirm each write with the engineer before advancing to the next.

When an approved change edits a rule, process, skill, tool, Systems or SystemPatterns file,
update the matching `Documentation/` page in the same repository as part of the same change.

Record the outcome in retro.md as an `## Applied` section: one line per proposed change,
`- #N applied: <file> — <what changed>` or `- #N skipped: <reason>` (same format as
`/end-session`, which the session meta-analysis reads).

**The retrospective is complete when all approved changes are written and the engineer confirms.**
