## apply: on-demand — loaded by [[MetaRouter]]

# Large Task

For a change too big for [[SmallTask]] that still does not need a feature outline: a tool, a
change to a framework or shared infrastructure, a cross-system refactor, or a rule/tooling
overhaul. No GDD, TDD, task list, progress file or phases — instead a written plan the engineer
approves before any code. **A large task is finished within the session that starts it.** If it
cannot be, it is a feature: stop and offer `/feature <Name>`.

Tag definitions: [[CoreTags]]

```yaml
fits_when:
  - "Touches 2–3 systems, or roughly 6–20 files"
  - "Documentation/ and Systems/ sync edits that follow a code change do not count toward the files."
  - "No GDD or design input needed: the engineer can state what done looks like"
  - "No new player-data schema or server contract"
  - "Can be finished, verified and closed in this session"
escalate_when:
  - "A GDD or design decisions beyond this plan are needed, a new player-data schema or server contract appears, more than 3 systems are touched, or the work will not finish this session → stop, say so in one line, offer /feature <Name>. A partly done large task is handed to /feature with plan.md as its starting input — never continued in a second large-task session."
  - "It turns out to fit SmallTask's fits_when → say so and offer to continue as /small-task (re-run `set --lane small_task`)."
lane_switch:
  - "Entering this lane from another one in the same session (e.g. a small task that outgrew its limits) → record `set --lane large_task` before 3_plan, and offer the choice first: continue here, or /new-session \"/large-task <ask>\". The engineer decides."
```

---

## Steps

```yaml
steps:
  1_scope:
    - "If the request is a tool/script/report: StopAndVerify Scope Gate — ask one-off vs reusable, and Editor/runtime/CLI. Wait."
    - "Restate the deliverable in one line, and agree a 'done when' with the engineer (what runs, what passes, what they will check)."
    - "Work type: large_feature by default; `set --work-type other` for tooling, framework, config or rule work, bug_fix when the large change is a fix."
  2_discovery:
    - "SystemIndex: Read the Systems/ entry for every system the change lives in or USES (messages, states, prizes — match SystemIndex's trigger comments), and the SystemPatterns/ file if one matches."
    - "Survey each area with an Explore agent (one per area, in ONE message), asked for a compact map. Read inline only the bodies the plan rests on."
    - "Existing utility first — before planning any helper, tool, window, exporter, logger or importer, look for one to extend: host metadata, then codeindex.py where/types. Record what you searched for the plan."
    - "Apply SmallTask 2_context's checks as they fit: listeners' handlers before choosing dispatch points; real data has the keys a consumer matches on; reuse an existing view's population and filter rules."
  3_plan:   # GATE — no code before the engineer approves
    - "Load the rules the change needs (3_rules below) and ../Rules/ChangeClassification.md."
    - "Write plan.md in the session folder (path from the Session tracking block):"
    - "  goal and 'done when' (from 1_scope)"
    - "  model: 'Extending <X> (found via <search>)', or 'No existing utility found (searched: <queries>)'"
    - "  file plan: every file NEW / MODIFIED / DELETED, one line each, with the repository it belongs to"
    - "  2–4 ordered steps, each leaving the tree compiling and independently checkable"
    - "  risks and open questions; test plan (which tests, which real-data runs)"
    - "  A done-when that only holds in a worktree-isolated session (guard or isolation behaviour) names how it will be checked: an engineer-approved EnterWorktree at 6_verify, or the evidence that stands in for it (e.g. the refusal in past transcripts), so it is not left partly met."
    - "Present the plan's summary and wait for approval. Changes asked for → update plan.md and re-present."
    - "A meta-review ticket or handoff note that already has Change and Done-when is the goal and done-when; still write the file plan and steps."
    - "A deliverable that is only a document or report (no code or rule edits) needs no plan.md. The Scope Gate answers (shape, output location) are its plan; state 'done when' in chat and go on to discovery. Any follow-up edits the report recommends go through 3_plan as usual."
  3_rules:   # routing table, by what the change touches
    csharp:                    [../Rules/CodingStandards.md]
    new_class_or_interface:    [../Rules/ArchitecturalPrinciples.md]
    subscriptions_timers_loads:[../Rules/ResourceManagementRules.md]
    async_sequences:           [../Rules/MultyStepOperationsRules.md]
    csharp_tests:              [../Rules/TestingRules.md]   # Python tool tests: 5_tests (unittest in the tool's tests/), no rule file
  4_implement:   # one plan step at a time
    - "Isolate first. Host project: EnterWorktree. Layer repo (AIAgentCoreRules, the host metadata repo): follow SmallTask 5_implement's layer-worktree rule (absolute paths, check the main checkout is clean). Exception: if verification needs the live Unity Editor (MCP tools, real-data runs), the Editor only compiles the main checkout. Offer the engineer worktree + land-before-verify, or work in the main checkout, at 3_plan time, and record the choice in plan.md. In a background job the main-checkout option is unavailable (the isolation guard rejects writes outside a worktree, including gitignored folders such as session reports and Assets/GitIgnoreAssets/). Spot this at 1_scope, write plan.md to $CLAUDE_JOB_DIR/tmp (or ~/.claude/plans/ when it must outlive the job), and hand implementation to a foreground session with a plan-path command."
    - "In a worktree-isolated session, follow SmallTask 5_implement's guard rule: no heredocs or computed variables in compound commands, no `git -C <shared checkout>`; scripts go to $CLAUDE_JOB_DIR/tmp/<name>.py and run as one plain `python3 <file>`; ExitWorktree (keep) before any git command on the main checkout."
    - "Discovery skipped because plan.md was approved in an earlier session → still Read the host SystemIndex Systems/ entry for every system the plan's steps use (match the SystemIndex trigger comments) before the step that writes code against it. Their gotchas are what this session will otherwise hit live."
    - "Per step: StopAndVerify pre-generation checks, write (fix the cslint hook's violations as they are reported), then one /audit over the step's changed C# files (Skill tool — a fresh subagent; wait for its report; never applied inline) and typecheck.py. Moving code verbatim into a new file still counts as changed C#: audit it in the step that moves it. Fix or report each violation before the next step."
    - "After each step: one line to the engineer — step N of M done, what was checked. Do not wait for an OK unless the step departed from plan.md."
    - "A departure from plan.md (a new file, a changed public contract, a dropped step) → stop, update plan.md, and get approval before continuing."
    - "Re-read a rule file when a step starts work it governs; do not rely on memory of it in a long session."
  5_tests:
    - "C# behaviour or framework change: tests are required — TestingRules, then the host's testing setup rules. Cover the changed behaviour and its boundaries."
    - "Python tool or skill tooling: unit tests in the tool's tests/ folder, plus a run against copies of real data — never the originals."
    - "Rules/Markdown only: no tests; 6_verify's checks are the evidence. Say so."
  6_verify:
    - "Apply SmallTask 6_verify in full (typecheck verbatim on failure, real-data runs, rendered-value checks for views, faked clients for external writes)."
    - "Run every test suite the change touched; report pass/fail counts."
    - "Sync docs: Documentation/ pages for changed rules, processes, skills or tools, and the host Systems/ entry for every system whose shape changed. Not optional in this lane."
    - "Check each 'done when' item from plan.md and report it met or not."
    - "Tell the engineer how to try it (menu path, debug command, steps). Editor-only steps are theirs to run."
  7_close:
    - "Commit in the worktree; land a layer worktree with /land-worktree. Offer /end-session."
    - "Work for a CreateFeature feature (session set with --feature): record it with Tools/feature-state/feature_state.py — `checkpoint <feature-dir> --revision <n> --payload <file.json>` for done/next/open_items, `task` with payload {id, title, status} for a task's status. --payload is a JSON file path; the revision comes from state.json. Never edit <Name>_Progress.md: it is generated from state.json and overwritten on render."
```

## Router check (used by /end-session)

```yaml
expected_loads:
  - "Systems/<entry>.md for every system the change lives in or uses"
  - "Rules/ChangeClassification.md"
  - "Rules/CodingStandards.md (C# changes)"
  - "plus each 3_rules row the change matched"
expected_artifacts: ["plan.md in the session folder, written and approved before the first code edit"]
expected_tools: [Explore agents, codeindex.py, typecheck.py, "/audit per step"]   # C# changes only for typecheck and /audit
expected_without_csharp: "runs of the changed tools against copies of real data, and their unit tests; CodingStandards and the C# tools are not expected"
missed_gate: "Code written before plan.md was approved, or a second session continuing the same large task, is a router miss."
```
