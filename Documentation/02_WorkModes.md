# Work Modes and Routing

Before doing anything, the agent classifies the request into one **work mode** (also called
a *lane*). The mode decides which process runs, what the output is, and which files are
loaded. Picking the wrong mode wastes the whole turn, so this is the first step of every task.

## The six modes

| Mode | Looks like | Output | Process |
|---|---|---|---|
| **feature** | "implement / build / add feature X", "here is the GDD", `/feature <Name>` | Code, tests and integration, through 8 gates | [[03_CreateFeature\|Create Feature Process]] |
| **bug_fix** | "X is broken", "why does X happen", "fix this crash", `/bug-fix <symptom>` | Diagnosis → approved fix → regression test | [[04_BugFix\|Bug Fix Process]] |
| **small_task** | "make a tool/debug command like X that does Y", small tweak, "follow this example", `/small-task <ask>` | A bounded code change with one proposal checkpoint | [[05_SmallTask\|Small Task Process]] |
| **investigation** | "how feasible is", "how does X compare", "where does X happen", "compile a list", `/run-investigation-mode <question>` | A document or recommendation — **not code** | [[06_Investigation\|Investigation Mode]] |
| **code_review** | "review PR X", "does this satisfy our rules", "evaluate my review comments" | Findings with file:line — **not code** | Coding Standards + Architectural Principles + Multi-Step Operations, plus the SystemIndex entry for each system the diff touches |
| **other** | Questions, tooling/config, documentation | Whatever was asked | Routing table only |

The mode is recorded in session tracking, so metrics and retrospectives are grouped by mode.
Session tracking has no separate code_review lane: a review is recorded as lane `other`, work type
`question`.

### Reviewing a stacked PR

Before reading any diff, the agent finds the PR's real base. A stacked PR usually targets a
feature branch, not the default branch, and diffing against the default branch pulls in every
PR below it. The agent uses `git merge-base` against the actual target branch, and before
comparing against later branches in the stack it checks whether they already contain the PR's
latest commit — a downstream branch cut from an earlier commit shows pending rebases, not
future removals.

### No silent escalation

The agent never moves between modes on its own. A small task that grows past its limits, or an
investigation that uncovers a bug, is **offered** to the engineer as a mode change. If a request
is genuinely ambiguous, the agent states the mode it is assuming in one line and continues.

## Loading rules on demand

Only three core files plus the host project's rules and SystemIndex are always loaded. Everything else
is read when the task needs it, using this routing table:

| When the task involves | The agent loads |
|---|---|
| Writing or modifying C# | Coding Standards |
| Designing classes or interfaces | Architectural Principles |
| Async flows, queues, sequences | Multi-Step Operations Rules |
| Writing or modifying tests | Testing Rules (+ the host project's testing setup) |
| Subscriptions, loads, timers, guards | Resource Management Rules |
| Refactor or review | Coding Standards + Architectural Principles |
| New multi-system feature | Coding Standards + Architectural Principles + Multi-Step Operations |

Rule files are loaded with the Read tool rather than shell commands, so the session's
**router trace** (see [[07_SessionTracking#Output|Session Tracking]]) records exactly which files were loaded. The retrospective uses that trace to
spot files that were needed but never loaded.

The same applies to files the agent is about to edit: it opens them with the Read tool first.
A shell `cat` does not count, and the edit is rejected without it.

The `Documentation/` pages (including this one) are for people. The agent never loads them for
routing; it loads the rule and process files they describe.

## Delegation

Breadth goes to subagents. Any "where is X / which files / who implements Y" question is sent
to an Explore subagent (or `/discover`), which returns a compact map. The main agent keeps its
context for reading the specific method bodies a conclusion depends on and for the reasoning
itself. The failure mode being guarded against is not over-delegating — it is filling the main
context with file listings and leaving no room for the analysis.

Multi-round exploratory or trial-and-error work — browser-automation probing, an iterative debug
script that needs several retries to get right — also goes to a fork rather than the main thread.
Only the final working script and its conclusion need to come back; every retry's raw output
left in the main thread gets resent on every later turn for the rest of the session.

## Stop and Verify

Always-on checks that run before and after any code is generated:

**Scope gate** — for any request for a tool, script, report or utility, the agent first asks
whether the deliverable is a one-off answer or a reusable tool, and where it runs (Editor,
runtime or CLI). It asks before exploring, because the wrong answer discards the exploration.
It skips the question when the request names an existing tool to extend (e.g. "add a tab to the
preview server") and says so in its scope restatement instead.

**Before generating**
- Every interface, class, enum and base type needed is located in source.
- Every property, method and field used is found in source — no guessed signatures.
- ScriptableObjects are created with `CreateInstance<T>()`, never `new T()`.

If a dependency cannot be found after searching, the agent stops and asks for it rather than
generating partial code.

**After generating**
- No signatures were guessed.
- Existing comments, regions and TODOs are preserved unchanged.
- Only the required lines changed; surrounding code is untouched.

**Thread-affinity hard gate** — before adding or changing any `ConfigureAwait(false)`, establish
the entry context and trace its continuation through helpers, injected callbacks, events and
`catch`/`finally`. No Unity, Editor, UI or other thread-affine API may be accessed after that
await without explicit verified dispatch to its required context. If safety cannot be proven,
retain ordinary `await` on a known required context or separate host updates from independent
work; stop affected generation until thread ownership is resolved. Recheck before presentation.

`ConfigureAwait(false)` does not force a worker thread, and completed tasks can continue inline.
`Task.Run` does not make worker-side Unity calls safe; a callee's configuration does not change
its caller's separate await. Cancellation/disposal paths need their own check because
`CancellationTokenSource.Cancel` invokes callbacks synchronously on the cancelling thread.
Callbacks must not hide contended locks or blocking cleanup behind an assumed worker boundary;
signal an owned async cleanup flow and observe it when cleanup must run elsewhere. Record a
short thread-ownership rationale and use regression evidence for pending and already-completed
awaits, plus cancellation/teardown where relevant; one passing timing path is not proof.

**Behaviour claims** — in any mode, what an engine, library, API or CLI does at runtime (a
getter returning a copy, a library working on every platform, an API accepting a format, where
a CLI option goes) is stated as a hypothesis, with how to check it, until it is grounded in
source, `--help`, docs or a run.

**Secrets** — in any command, the agent never prints any part of a credential (not even a
prefix). It checks a token's shape with yes/no tests only, and if a fragment leaks it says so
and recommends rotating it.

**Tool output** — in any command, raw output stays out of context unless the task needs it or
the engineer asks for verbosity: pipe through `tail`/`grep`/`head`, use `Read` with
`limit`/`offset`, summarize a test run's pass/fail counts instead of pasting the full log. A
verbose result paid for once gets paid for again on every later turn that re-reads it. Added
after a session retrospective found "ad-hoc tool calls" alone were 24% of that session's tokens.

**Source files:** [[MetaRouter]] · [[StopAndVerify]] · [[CoreTags]]

---

← [[01_Setup|Setup]] · [[00_Overview|Overview]] · [[03_CreateFeature|Create Feature Process]] →
