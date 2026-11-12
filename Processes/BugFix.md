## apply: on-demand — loaded by [[MetaRouter]]

# Bug Fix

From symptom to verified fix with a regression test. Investigation here is a means to a fix,
not a deliverable — for "should we change X" questions with no bug, use InvestigationMode.

Tag definitions: [[CoreTags]]

---

## Steps

```yaml
steps:
  1_symptom:
    - "Restate: expected vs actual, repro steps, frequency, build/platform, first-seen version. Ask only for what is missing."
  2_context:
    - "SystemIndex: Read the Systems/ entry for every system on the failing path — common_gotchas first — before searching its source."
    - "A system that a survey, log or hypothesis implicates later gets the same treatment at that moment: read its entry before reading its code, not at fix time."
    - "Locate the flow: codeindex.py where/members, usages.py for callers. Breadth → an Explore agent."
    - "Recent history: git log --since=<first-seen build date> -- <files on the failing path>. A sibling fix may already explain the bug, or be missing from the reported build."
    - "Crash reports: read the full native trace (Android tombstone, iOS full crash log), not the summary stacktrace. Summary exports truncate the crashing thread (~64 frames) and can drop managed method names, so recursion depth and the actual cycle are only visible in the full trace. Name the cycle from the repeating frames, and treat a hypothesis built only from a truncated trace as unverified."
  3_hypotheses:
    - "Read the method bodies on the failing path. Every claim carries file:line."
    - "Rank 1–3 hypotheses by evidence. For each: the evidence, what would confirm it, what would rule it out."
    - "Check the cheapest confirming evidence first (one grep, one log line, one breakpoint the engineer can set)."
  4_gate_diagnosis:
    - "Present: root cause (or top hypothesis + confidence), the proposed fix, blast radius (callers affected), and the regression test."
    - "Wait for engineer confirmation. No code before this gate."
  4b_fresh_session:   # offer, never force
    - "If metrics.md shows more than ~8 turns (the Stop hook keeps it current), offer to do the fix in a fresh session: every tool call in a long session re-reads the whole diagnosis, and fix turns were the costliest of the week."
    - "If the engineer accepts: write bugfix_handoff.md in this session's folder (format below), run /end-session for the diagnosis, then print the command and stop."
    - "  claude \"Continue the bug fix from <path to bugfix_handoff.md>: load Processes/BugFix.md and start at step 5.\""
    - "The new session reads the handoff, records lane bug_fix with the same title, and loads the step-5 rules. It does not re-diagnose."
  5_fix:
    - "Load rules by what the fix touches: CodingStandards always; ResourceManagementRules for subscriptions/timers/loads; MultyStepOperationsRules for async ordering."
    - "Smallest change that removes the cause. [SURG] — no drive-by refactors; list them as follow-ups instead."
  5b_audit:   # checkpoint — do not start step 6 until it has run
    - "Run /audit once over every changed C# file (fix, repro/debug tooling, and later the test file) — Skill tool, it forks a fresh subagent; wait for its report. Fix or report each violation. cslint already checked the mechanical tags per edit."
    - "Self-review is not a substitute: applying the audit brief inline in this context counts as skipped, and /end-session flags a skipped audit as a router miss."
  6_test:
    - "Load TestingRules.md and the host project's testing setup."
    - "Write one regression test that fails without the fix and passes with it. If the bug cannot be unit-tested (timing, platform, Editor-only), write the manual repro steps instead and say why."
    - "Engine / native behaviour (aliasing, serialization, native memory, rendering): build the repro or test on the REAL asset or object (instantiate the prefab, read the live component). An object built from scratch may take a different native path and pass without the fix."
    - "If the engineer already confirmed the bug with a tool or inspection (a comparer, a debug window, inspector values), ask which one and build the repro on the same data path — capture where and how that tool captures."
  7_verify:
    - "Run typecheck.py."
    - "Ask the engineer to run the test(s) in the Unity Test Runner and the repro steps; report results as given."
  8_close:
    - "Summarise: cause · fix · test · follow-ups. Offer /end-session."
```

Handoff for a fresh fix session (step 4b), written to `<session folder>/bugfix_handoff.md`:

```yaml
bugfix_handoff:
  ticket:          ""   # id and one-line symptom
  root_cause:      ""   # confirmed at the gate, with file:line
  approved_fix:    ""   # exactly what the engineer approved
  files:           []   # files to change, with the method or line range
  blast_radius:    []   # callers affected
  regression_test: ""   # planned test, or why manual repro steps instead
  systems_loaded:  []   # Systems/ entries already read, to reload rather than re-survey
  rejected:        []   # hypotheses ruled out, with the evidence, so they are not reopened
```

Rule for step 3: if verification reverses an earlier hypothesis, lead with the correction
(InvestigationMode IV). A wrong root cause that reaches the fix is the most expensive failure here.

Detours: when the engineer asks for side work mid-bug (for example a repro tool or debug
command), record the lane change with the lifecycle `set --lane small_task` command before
starting it, then `set --lane bug_fix` when you return. That keeps metrics and the router check
accurate. Follow SmallTask.md for the detour, including its own /audit.
A PR-review follow-up counts as a detour: load SmallTask.md and run /audit before its commit,
even when a plan file was approved.

Lane switch: entering this lane from another one in the same session (e.g. a PR review that
turns into a bug), offer the split as a choice before step 1: continue here, or
`/new-session "/bug-fix <symptom>"`. `set` prints a fresh-session offer when the session is
already large; relay it. The engineer decides; never switch sessions unasked.

## Router check (used by /end-session)

```yaml
expected_loads:
  - "Systems/<system>.md for every system on the failing path (if it exists), loaded before that system's source was read — a late load is a miss"
  - "Rules/CodingStandards.md"
  - "Rules/TestingRules.md + host testing setup"
  - "plus ResourceManagementRules / MultyStepOperationsRules if the fix touched them"
expected_tools: [usages.py or codeindex.py, typecheck.py, /audit]   # C# changes only
expected_without_csharp: "the changed tool's own tests plus a run against copies of real data; CodingStandards, TestingRules and the C# tools are not expected"
```
