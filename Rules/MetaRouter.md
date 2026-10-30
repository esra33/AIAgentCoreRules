## apply: always

# Agent Rule Router

This file, [[StopAndVerify]] and [[CoreTags]] are the only core files loaded unconditionally; the host project's CLAUDE.md may add its own always-on files. Classify the task, then use your Read tool to load the relevant files **before generating any code**.

```yaml
directory_layout:   # relative to the repository root
  Rules/        # Standards and principles — what code must look like
  Processes/    # Step-by-step wizard workflows — how to carry out specific tasks
```

All `load` and `routing` paths below are relative to the directory containing this file (`Rules/`) — pass them straight to Read.

---

## Session Lifecycle — every session, every mode

```yaml
session_lifecycle:
  start:   "Automatic (SessionStart hook) — a 'Session tracking' block appears in context. If it is missing, run /start-session."
  record:  "Right after classifying the mode below, record the lane and work type with the `set` command shown in the Session tracking block."
  work_type: "bug_fix | small_feature | feature | question | other — what the work is, not which lane ran it (definitions in ../Skills/start-session). Defaults to the lane's; pass --work-type when they differ."
  name:    "/start-session <name> names the session (folder + metrics heading). Optional."
  during:  "The engineer logs /inaccuracy <reason> after correcting you, and /iteration <change> on a deliberate change of direction."
  self_log: "When you retract a claim, or the engineer rejects your approach, log it yourself straight away with `note --kind inaccuracy --source agent \"<what was wrong>\"` (command in the Session tracking block). Unlogged corrections are back-filled by /end-session with --source retro."
  end:     "/end-session — compiles metrics + router trace, writes a lane-scaled retrospective, opens both files."
  backstop: "If /end-session is skipped, the SessionEnd hook still compiles metrics.md (no retrospective)."
```

Load rule and process files with the **Read** tool, not shell `cat`/`sed` — the router trace in
the session metrics is exact for Read and only inferred for shell commands.

---

## First: Classify the Mode

Before the routing table, decide which mode the request is in. They have different outputs and
different rules, and picking wrong wastes the whole turn. The mode is the session's lane.

```yaml
mode_fork:
  small_task:
    looks_like: "make a tool/utility/debug command like X that does Y / small tweak / follow this example / /small-task"
    output:     "code for a bounded change — no TDD, one proposal checkpoint"
    load:       [../Processes/SmallTask.md]
  bug_fix:
    looks_like: "X is broken / what could be causing / why does X happen / fix this crash / /bug-fix"
    output:     "diagnosis → approved fix → regression test"
    load:       [../Processes/BugFix.md]
  investigation:
    looks_like: "how feasible / how does X compare / where does X happen / hypothetical refactor / compile a list / /run-investigation-mode"
    output:     "a document or recommendation — NOT code"
    load:       [./InvestigationMode.md]
  code_review:
    looks_like: "review PR X / does this satisfy our rules / evaluate my review comments"
    output:     "findings with file:line — NOT code"
    load:       [./CodingStandards.md, ./ArchitecturalPrinciples.md, ./MultyStepOperationsRules.md]
    also_load:  "the host SystemIndex entry for every system the diff touches, before reading its source"
    first_step: "Find the real base: a stacked PR targets a feature branch, not the default branch — use git merge-base. Check whether downstream stacked branches contain the PR tip before comparing against them."
    record_as:  "lane other, work type question — session tracking has no code_review lane"
  feature:
    looks_like: "implement / build / add feature X / here is the GDD / /feature <Name>"
    output:     "code, tests, integration — with all 8 gates"
    load:       [../Processes/CreateFeature/index.md]
  other:
    looks_like: "questions, tooling/config, docs, anything not above"
    output:     "whatever was asked — routing table only"
    load:       []
```

Never silently escalate between lanes: a small task that outgrows SmallTask's limits, or an
investigation that turns into a bug, is offered to the engineer as a lane change, not taken.
If genuinely ambiguous, state the assumed lane in one line and continue — do not block.

---

## Absolute Non-Negotiables

```yaml
non_negotiables:
  - "[EXPLICIT] No var — explicit types everywhere."
  - "[ALLMAN]   Allman braces — { always on a new line."
  - "[FIELD]    No public fields — ever. Wrap in a property."
  - "[ACCESS]   All access modifiers explicit on every member."
  - "[FIELD]    private readonly for every injected dependency."
  - "[DI]       No ServiceLocator.Instance — use constructor injection or LazyService<T>."
  - "[IFACE]    Never cast to a concrete type inside a high-level system."
  - "[RES]      Every resource acquisition has a matching release in the same scope (subscriptions, loads, timers, guards)."
  - "[ASYNC]    No async void except: event handlers, and synchronous overrides bridging into async (must have try/catch)."
  - "[LOG]      All logging via the project Logger wrapper only — never native platform debug logging."
  - "[DELEGATE] Breadth goes to subagents. Any 'where / which files / who implements' question is delegated, not run inline."
  - "[SHAPE]    A tool/script/report request hits the [[StopAndVerify]] Scope Gate before any exploration."
  - "[TRIM]     Tool output stays out of context unless the task needs it or verbosity is requested — see [[StopAndVerify]]'s Tool Output section."
```

### [DELEGATE] — when to spawn, when not to

```yaml
delegate_aggressively:
  - "Surveying a system, directory, or feature area           → /discover <area>"
  - "'Where is X / which files / who implements Y'            → Explore agent, or /discover"
  - "Several independent areas                                → one agent per area, ONE message"
  - "A compliance or review sweep over many files             → fan out, then synthesise"
  - "Multi-round exploratory/trial-and-error work (browser-automation probing, iterative debug
     scripts needing several retries to get right)            → fork — only the final working
     script and its conclusion need to come back, not every retry's output"
keep_inline:
  - "Reading the specific method bodies a conclusion rests on."
  - "A single targeted fact check — one grep or one codeindex query is cheaper than an agent."
  - "The reasoning, comparison, and recommendation itself."
```

The failure mode is not over-delegating; it is filling the main context with file listings and
leaving no budget for the analysis they were gathered for.

---

## Routing Table

When a task matches a process, load the process and follow it. Processes are wizard workflows — they reference the rules internally at the right steps.

```yaml
routing:
  # Processes — load and follow step by step
  create_new_feature:             [../Processes/CreateFeature/index.md]
  small_bounded_change:           [../Processes/SmallTask.md]
  diagnose_and_fix_bug:           [../Processes/BugFix.md]
  meta_review_of_sessions:        [../Processes/MetaReview.md]   # review past sessions · meta-analysis · weekly retro of retros
  publish_or_review_external_doc: [../Processes/ExternalDocPass.md]   # Confluence/Docs page · apply review comments · publish a TDD

  # Modes — decide this first, see "Classify the Mode" above
  investigate_or_preplan:         [./InvestigationMode.md]
  feasibility_or_comparison:      [./InvestigationMode.md]
  produce_design_document:        [./InvestigationMode.md]

  # Rules — load and apply when writing or reviewing code
  write_or_modify_csharp:         [./CodingStandards.md]
  design_classes_or_interfaces:   [./ArchitecturalPrinciples.md]
  async_flows_queues_sequences:   [./MultyStepOperationsRules.md]
  write_or_modify_tests:          [./TestingRules.md]
  resource_management:            [./ResourceManagementRules.md]
  classify_files_changed:         [./ChangeClassification.md]   # TDD Architecture file/type list · File Plan · NEW/MODIFIED/DELETED diagram colors
  refactor_or_review:             [./CodingStandards.md, ./ArchitecturalPrinciples.md]
  new_feature_multi_system:       [./CodingStandards.md, ./ArchitecturalPrinciples.md, ./MultyStepOperationsRules.md]
```

---

## How to Load

Read each path from the tables above exactly as written. Do not generate code until the relevant files are read.

Rule files loaded early can be summarised away in a long session. When a process step says to
re-read a rule file, re-read it — do not rely on memory of it.

Read any file you are about to edit with the **Read** tool first. A shell `cat`, `sed` or `grep`
does not count: the edit is rejected, and the router trace can only guess at shell loads.

---

## Commands

```yaml
commands:   # skills in ../Skills/ (project-specific ones in the host metadata repo)
  /start-session:  "start/resume tracking, set lane (normally automatic)"
  /end-session:    "metrics + router trace + retrospective, opens files"
  /inaccuracy:     "engineer logs a corrected agent mistake"
  /iteration:      "engineer logs a deliberate change of direction"
  /feature <Name>: "enter the CreateFeature process"
  /small-task <ask>: "enter the SmallTask process (lane small_task), skipping classification"
  /bug-fix <symptom>: "enter the BugFix process (lane bug_fix), skipping classification"
  /run-investigation-mode <question>: "enter Investigation Mode (lane investigation), skipping classification"
  /generate-meta-review [time frame]: "run the MetaReview process over the sessions in the window"
  /checkpoint:     "save mid-phase feature progress to <FeatureName>_Progress.md"
  /resume-work [Name]: "pick up a feature from its progress file in a fresh session; no name → choose from the active features"
  /active-features: "list features not yet complete: phase, status, next step, resume command"
  /close-feature <Name> [reason]: "close / force-terminate a feature: status picker (abandoned default, superseded, on_hold, complete) + reason in its progress file"
  /reopen-feature [Name]: "return a closed (not complete) feature to in_progress; no name → choose from features --closed"
  /start-preview-server [Name]: "open a feature in the doc-review preview: Progress tab, TDD, diagrams"
  /feature-pr <PR> [Name] [V-phase]: "tie a PR to a feature's V-phase in its progress file, read its review notes, record addressed ones there"
  /publish-batch [plan|publish|status|finish]: "Phase 4: publish a task's C# in small batch PRs against the user branch, one at a time; change table per batch; next batch after merge"
  /kill-server [port|pid|all]: "stop a running doc-review preview server"
  /discover <area>: "subagent survey, returns a compact map"
  /audit [files]:  "rules compliance check, report only"
  /land-worktree [name]: "merge an agent worktree into the current branch, test, then remove it (or roll back)"
  /new-session <prompt>: "open a fresh session with that prompt in a new Terminal.app window or Rider terminal tab (macOS)"
  /uses <Type>:    "who uses a type / calls its members (host project tool)"
```

`Documentation/` (in this repo and in the host metadata repo) is the human-facing copy of the
Rules, Processes, Skills and Tools. Never load it for routing — load the source files above.
When you change one of those source files, update the matching `Documentation/` page with it.
