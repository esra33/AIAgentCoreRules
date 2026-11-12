# Large Task Process

For a change too big for a [[05_SmallTask|small task]] that still does not need a feature
outline: a tool, a change to a framework or shared infrastructure, a cross-system refactor, or a
rule/tooling overhaul. There is no GDD, TDD, task list, progress file or phases. Instead the agent
writes a short plan that the engineer approves before any code is written. **A large task is
finished within the session that starts it** — that limit is what separates it from a feature.

Start it with `/large-task <ask>`. The session is recorded as lane `large_task`, work type
`large_feature` (`other` for tooling, framework, config or rule work).

## When it fits

- Touches 2–3 systems, or roughly 6–20 files. Documentation/ and Systems/ sync edits that follow
  a code change do not count.
- No GDD or design input is needed: the engineer can say what "done" looks like.
- No new player-data schema or server contract.
- It can be finished, verified and closed in this session.

If any of these stops being true, the agent stops, says so in one line and offers
`/feature <Name>`, handing over its `plan.md` as the feature's starting input. A large task is
never continued in a second large-task session. If the work turns out to fit a small task, the
agent offers to continue as `/small-task`. A small task that outgrows its limits is offered
`/large-task` when it still fits here, otherwise `/feature`.

## Steps

| # | Step | What happens |
|---|---|---|
| 1 | **Scope** | For a tool, script or report: the scope gate (one-off or reusable, where it runs), then wait. Restate the deliverable in one line and agree a "done when" with the engineer. |
| 2 | **Discovery** | Read the Systems entry for every system the change lives in or uses, and any matching pattern. Survey each area with an Explore agent (one per area, in parallel). Look for an existing utility to extend before planning a new one, and record the searches. |
| 3 | **Plan (gate)** | Load the rules the change needs (Testing Rules only for C# tests; Python tool tests have no rule file) and Change Classification, then write `plan.md` in the session folder: goal and "done when", the model being extended, every file NEW / MODIFIED / DELETED with its repository, 2–4 ordered steps that each leave the tree compiling, risks and open questions, and the test plan. A "done when" that only holds in a worktree-isolated session (guard or isolation behaviour) names how it will be checked: an engineer-approved EnterWorktree at verification, or the evidence that stands in for it (for example the refusal in past transcripts), so it is not left partly met. **No code until the engineer approves it.** A deliverable that is only a document or report (no code or rule edits) needs no `plan.md`: the Scope Gate answers (shape, output location) are its plan, "done when" is stated in chat, and work goes on to discovery. Any follow-up edits the report recommends go through this step as usual. |
| 4 | **Implement** | In a worktree (EnterWorktree for the host project, a layer worktree for AIAgentCoreRules or the host metadata repo). Exception: when verification needs the live Unity Editor (MCP tools, real-data runs), the Editor only compiles the main checkout — the choice between worktree + land-before-verify and working in the main checkout is offered at plan time and recorded in `plan.md`. In a background job the main-checkout option is unavailable (the isolation guard rejects writes outside a worktree, including gitignored folders such as session reports and `Assets/GitIgnoreAssets/`): spot this at scope time, write `plan.md` to `$CLAUDE_JOB_DIR/tmp` (or `~/.claude/plans/` when it must outlive the job), and hand implementation to a foreground session with a plan-path command. In a worktree-isolated session the guard refuses compound commands that contain a heredoc or computed variables, and `git -C <shared checkout>`: scripts go to `$CLAUDE_JOB_DIR/tmp/<name>.py` and run as one plain `python3 <file>` command, and the agent runs ExitWorktree (keep) before any git command on the main checkout. When `plan.md` was approved in an earlier session and discovery is skipped, the agent still reads the host SystemIndex `Systems/` entry for every system the steps use before writing code against it. One plan step at a time: Stop and Verify, write (fixing the cslint hook's violations as they are reported), one `/audit` over the step's changed C# files (a fresh forked subagent, never applied inline) and `typecheck.py`, then a one-line checkpoint. Code moved verbatim into a new file still counts as changed C# and is audited in the step that moves it. The agent only stops for approval when a step departs from `plan.md` — a new file, a changed public contract, a dropped step — and updates the plan first. |
| 5 | **Tests** | Required for C# behaviour or framework changes (Testing Rules plus the host's testing setup). Python tools get unit tests and a run against copies of real data. Rules or Markdown only: no tests, and the agent says so. |
| 6 | **Verify** | Everything in the small task's Verify step, plus: every touched test suite run with pass/fail counts; Documentation/ and Systems/ updated (required in this lane); each "done when" item reported met or not; how the engineer can try it. |
| 7 | **Close** | Commit in the worktree (land a layer worktree with `/land-worktree`), then offer `/end-session`. For a feature session, record progress with `feature_state.py checkpoint` / `task` (payload is a JSON file path) — never edit the generated `<Name>_Progress.md`. |

## What the retrospective expects to see loaded

- The Systems entry for every system the change lives in or uses
- Change Classification, plus Coding Standards for C# changes and each rule file from step 3 the change matched
- `plan.md` in the session folder, written and approved before the first code edit
- Tools: Explore agents, `codeindex.py`, and for C# `typecheck.py` and `/audit` per step
- When no C# changed: runs of the changed tools against copies of real data, and their unit tests

Code written before the plan was approved, or a second session continuing the same large task,
is flagged as a router miss.

**Source files:** [[LargeTask]] · [[Skills/large-task/SKILL|/large-task]]

---

← [[05_SmallTask|Small Task Process]] · [[00_Overview|Overview]] · [[06_Investigation|Investigation Mode]] →
