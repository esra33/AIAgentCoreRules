# Session Tracking and Retrospectives

Every agent session is measured, so we can see what the agent actually did, where it went
wrong, and which rule or process changes would have prevented it. Tracking is automatic; the
engineer's part is logging corrections and running `/end-session`.


## Lifecycle

| Moment | What happens | Who |
|---|---|---|
| Session start | The SessionStart hook puts a **Session tracking** block in the agent's context. No folder is created yet | Automatic |
| First thing worth saving | The session folder is created on the first `set`, `note` or `compile`, or after the first reply. Sessions opened and closed without work leave no folder | Automatic |
| Naming (optional) | `/start-session <name>` names the session; the name goes into the folder and the metrics heading | Engineer |
| Mode classified | The agent records the lane (feature, bug_fix, small_task, investigation, other), the work type (bug_fix, small_feature, feature, question, other) and a short title | Agent |
| Agent makes a mistake you correct | `/inaccuracy <what was wrong>` | Engineer |
| Agent retracts a claim, or you reject its approach | It logs the inaccuracy itself, marked `agent` | Agent |
| A correction was never logged | `/end-session` records it from the retro's Corrections, marked `retro` | Agent |
| You deliberately change direction | `/iteration <what changed>` | Engineer |
| Wrap up | `/end-session` compiles metrics, writes the retrospective and opens both files | Engineer |
| After each agent reply | The Stop hook recompiles metrics (at most every 2 minutes) without marking the session ended, so a session that is never exited still has current metrics | Automatic |
| You send a prompt after a long break | When the last reply is over an hour old and its context was over ~100k tokens, the UserPromptSubmit hook tells the agent the prompt cache has expired and what the next call costs, so new work can be offered a fresh session (`/new-session`) | Automatic |
| The agent reads a rule file through the shell | A PreToolUse hook on Bash notices `cat`/`sed`/`head`/`tail` of a `.md` under `Rules/`, `Processes/`, `Systems/`, `SystemPatterns/` or `Skills/` and reminds the agent to use Read, so the router trace stays exact. Only a command in command position counts (start of the line, or after `;`, `&&`, `\|`): a mention inside quoted text or a heredoc stays silent. It never blocks the command | Automatic |
| The lane changes in a large session | Recording a lane change on a session past ~30M tokens prints a fresh-session offer with the matching command (`/new-session "/bug-fix <symptom>"`, …) | Agent offers, you decide |
| Session closes without `/end-session` | The SessionEnd hook still compiles metrics (no retrospective) and records the exit time and reason; a resumed session's end time is updated on each exit. It fires only when the process exits, not when the app marks an idle session completed | Automatic |

Every hook run appends one line to `GitIgnoreReports/Sessions/hooks.log` (event, session, the
agent's working directory, outcome). If a session's metrics look stale, check that log first: no `end`
line means the hook never fired; `no folder for this session` or `ERROR` means it fired and failed.
Reports always go to the project's main checkout (found from git, or the folder holding `CLAUDE.md`),
whatever folder the agent has `cd`'d into, so a session never splits into two folders. Nothing to
configure per project — `install.py` and the tracker share the same root lookup. Global options
go before the subcommand: `session_lifecycle.py --reports-root <dir> set …` and
`install.py --project <repo> worktrees`.

The **lane** is the process that ran; the **work type** is what the work was. They usually match,
but not always: an investigation into a crash is lane `investigation`, work type `bug_fix`. If the
agent does not set a work type, it follows the lane (small_task → small_feature, investigation →
question) and metrics.md marks it "(from lane)". The meta-analysis groups cost by work type to
show which kinds of work are most expensive.

The **feature** tag (`set --feature <Name>`) ties a session to a CreateFeature feature. /feature
and /resume-work always set it; /small-task, /bug-fix and /run-investigation-mode set it when the
work is for an in-progress feature. The feature's Performance tab in the doc-review preview counts
tagged sessions plus those listed under `sessions:` in its Progress file.

An **inaccuracy** is an agent error. An **iteration** is a decision — a scope change or a new
direction — and is not counted against the agent.

Each note records who logged it: `engineer`, `agent` or `retro`. metrics.md shows the split when
it is not all engineer, for example `3 (engineer 1 · agent 1 · retro 1)`. The meta-analysis
treats `retro` entries as found late, so a session whose corrections were all back-filled still
shows up as "not logged live".

## Output

One folder per session that did something. If a folder still ends up empty (no lane, notes,
tokens or typed prompt), the SessionEnd hook removes it, and `session_lifecycle.py prune-empty
[--dry-run]` clears any left over:

```
GitIgnoreReports/Sessions/<YYYY-MM-DD_HHMM>_<lane>_<name>_<id8>/
  session.json   state (source of truth)
  metrics.md     rendered report
  retro.md       written by /end-session
  retro.html     the retro as a page: progress bar and a status badge per proposal
  tokens/        per-session token report
```

### metrics.md contains

- Session ID, name, title, lane, work type, start/end time, whether `/end-session` ran
- Total tokens, turns, subagents
- Every logged inaccuracy and iteration, timestamped
- **Lane changes** — each time the lane changed mid-session (for example a Bug Fix detour into
  `small_task` and back), with the time, so earlier lanes are not lost
- **Work type changes** — the same, for the work type
- **Router trace** — the files loaded through `CLAUDE.md`, then every rule and process file
  loaded on demand, in order, with the time and how it was loaded
- A count of each of the host project's Runnable tools the agent ran (for example `typecheck.py`,
  `codeindex.py`, `usages.py`)
- **Token breakdown (estimated)** — tokens per category with the standardized-operations share,
  and tokens and round-trips saved per mechanism (see *Token charts* below)

The router trace is read from the session transcript, not from the agent's memory. Rows loaded
with the Read tool are exact; rows inferred from shell commands are heuristic (a `grep` over a
file counts as a load). A file first seen in a shell command and Read later shows as
`Bash → Read`, since it was loaded properly in the end. `Documentation/` pages are never listed: they mirror the rules for
humans and are not a routing load.

## Retrospectives

`/end-session` scales the retrospective to the lane.

**Feature sessions** follow [[03_CreateFeature#Phase 8 — Retrospective|Phase 8]] of the [[03_CreateFeature|Create Feature process]] across every session of the
feature. If the feature is still in progress, `/checkpoint` runs first so the next session can
resume.

**All other lanes** get a short retrospective with these sections:

| Section | Content |
|---|---|
| Outcome | What was delivered and how it was verified |
| Router check | The files the lane's process expects to be loaded vs. what the trace shows — misses and unnecessary loads |
| Corrections | Each inaccuracy with a root cause: missing rule, missing index entry, rule ignored, signature guessed, or scope misread |
| Discovery gaps | Anything looked up mid-task that the host project's SystemIndex or Systems docs should have supplied |
| Proposed changes | Concrete, minimal edits to rules, processes or index — **not applied**. Each row is self-contained (no "see above"), because the session that applies it reads only this table |
| Cost | Tokens, turns, subagents, and the heaviest turns ranked by **fresh** tokens (plus the heaviest by total, if different), each judged necessary, partly necessary or avoidable |

In a background session, `/end-session` cannot write `retro.md` into the session folder: once its
worktree is removed, Claude Code's isolation guard refuses Write in the shared checkout. The agent
writes the retro to the job tmp dir instead and files it with
`session_lifecycle.py retro --from "$CLAUDE_JOB_DIR/tmp/retro.md"`. Foreground sessions are not
affected.

After the engineer decides on the proposals, the retro gets an `## Applied` section with one line
per proposal (`- #N applied: …`, `- #N skipped: …`, or `- #N pending: …` while deferred). The
meta-analysis report reads it to know which solutions were actually implemented.

### Tracking proposals in retro.html

`/end-session` opens `retro.html` next to `retro.md`: the same retro as a page, with a progress
bar ("2 of 3 proposals resolved") and the proposals as cards right after the Outcome, each
badged open, applied or skipped. A "Show open only" toggle hides resolved ones.

Decisions are recorded with `session_lifecycle.py retro --mark <N> --status applied|skipped|pending
--note "…"`, which updates the Applied line and re-renders the page. A proposal resolved in a later
session is marked in its original retro with `--folder <id8>`, so the page stays current as items
are worked through. The page cannot write to disk itself; each open card has a button that copies
the command that marks it applied — run it, or ask Claude to.

### Token charts

`compile` also estimates where the tokens went (`token_breakdown.py`, read from the transcript)
and stores it in session.json. metrics.md gets a **Token breakdown (estimated)** section, and
retro.html gets a **Token charts** section just before Cost, with three charts:

1. **This session vs average.** Total tokens next to the mean and median of every other session
   in the reports root, plus the mean for the same lane.
2. **Standardized operations.** Tokens spent on the framework's own mechanisms (Runnable tools,
   the lifecycle script, skills, rule/process loads, subagents), as a total and a share. The
   remainder is split into ad-hoc tool calls and conversation/base context.
3. **What saved tokens and round-trips.** Parallel tool calls, subagent delegation, partial file
   reads, and each Runnable tool, with tokens and round-trips saved.

All of these are estimates. Each model call is counted once, in the breakdown and in the token
report's Total Tokens alike, so metrics.md quotes a single total. A tool result costs its size
(characters / 4) times every later call that re-reads it, until a compaction. The savings are
guesstimates against a counterfactual. For example, each `codeindex.py` call is assumed to replace
one ~3k-token exploratory read plus 2 round-trips; the assumptions are listed on the page and in
`AVOIDED_BY_TOOL`. Doc-review preview calls are compared with doing the same through Miro and
Confluence (`MIRO_CONFLUENCE_BY_COMMAND`: serve ≈ 18.4k tokens + 3 round-trips, comments ≈ 2.4k + 2,
reply ≈ 1.3k + 1, from averages of real MCP calls); the breakdown's `doc_review` block also measures
the Miro/Confluence MCP calls a session really made. To add a saving mechanism, add its name to
`token_breakdown.SAVINGS` and fill `savings[name]` in `analyse()`; metrics.md and retro.html render
every entry generically.

Every claim points at a trace row, a logged note or a `file:line`.

If the session changed lanes, the router check runs once per lane segment, splitting the trace
at each lane change. The depth of the retrospective follows the lane with the heaviest work.

## The improvement gate

Proposed changes are only applied after the engineer approves them, one file at a time. Rule
and index files are shared across every future session, so an unreviewed edit changes the
agent's behaviour everywhere. This is how the framework improves over time: corrections become
root causes, root causes become rule or index changes, and the next session avoids the mistake.

Approved proposals are applied in a fresh session by default. The retro session's context is
the largest it will ever be, and every edit made there re-reads it; applying proposals in place
cost more than the task itself in two sessions of the 2026-10-16 review. `/end-session` prints a
`/new-session` command whose session reads only the retro's proposal table. Applying in place is
still offered for one or two one-line edits.

When an approved change edits a rule, process, skill or tool, the matching `Documentation/`
page is updated as part of the same change.

## Meta-analysis report

To see trends across sessions, run from the project root:

```bash
python3 GitIgnoredExternals/AIAgentCoreRules/Tools/session-analysis/session_meta_report.py
```

It writes `GitIgnoreReports/SessionAnalysis.html`, a single page to open in a browser (print it
to PDF if needed). Add `--since YYYY-MM-DD` / `--until YYYY-MM-DD` to cover one window only, by
session start date. The page then goes to `GitIgnoreReports/MetaReviews/<end>_SessionAnalysis.html`,
next to that window's meta review. The report has:

- **Token expenditure:** a bell curve of tokens per turn (normal fit on a log scale, ±1σ/±2σ
  bands), switchable between fresh and total tokens, plus the total for each session.
- **Worst performers:** the heaviest turns, sessions, turn categories, lanes and work types. Each turn shows
  the verdict its retro gave it (necessary, partly avoidable, avoidable), plus how many fresh
  tokens were flagged avoidable.
- **What saved us:** an estimate of the fresh tokens and turns saved by each Runnable tool,
  knowledge doc, skill and routing file. It is based on measured medians (tokens per tool call,
  per turn, per subagent survey) and stated assumptions that the report prints and
  `--assumptions` can override. Knowledge docs earn credit only when no retro says they fell
  short.
- **Issue heat maps:** area × session, from retro proposals, router misses and discovery gaps;
  and correction root cause × lane.
- **Solutions:** every proposed change with its status (applied / skipped from the retro's
  Applied section, *likely applied* from git history, or open) and the evidence.
- **What else could be improved:** recurring open areas, repeated router misses, tracking gaps
  and token outliers.

*Likely applied* is inferred from commits made after the session, so check the evidence column.
The more consistently retros record an `## Applied` section, the more exact the report is.

## Meta review

The report above is the quantitative half. A **meta review** ([[Processes/MetaReview|MetaReview process]])
wraps it in a repeatable review of one time window, by default since the previous review:

1. Sort the window's session folders into real sessions, stubs and uncompiled sessions, and
   compile the uncompiled ones (`session_lifecycle.py compile --session-id <id>`).
2. Run the report, then read every retro in the window for router misses, skipped steps,
   unlogged corrections, discovery gaps and cost.
3. Keep only findings that recur in two or more sessions, or the window's largest cost driver.
4. Check every proposal against the current file contents, plus the previous review's open
   tickets. Proposals the engineer skipped are never raised again.
5. Check the metadata and tools repos for uncommitted or unpushed work. This is a one-line
   reminder in the report, never a ticket: committing and pushing is the engineer's job.
6. Write `GitIgnoreReports/MetaReviews/<date>_MetaReview.html` (fixed layout) and
   `<date>_Tickets.md`, which lists tickets by priority: P1 for work or data at risk, P2 for
   recurring misses or the top cost driver, P3 for polish. A ticket that cites a code fix names the
   branch or commit it is on. A background review writes both files to its job tmp dir and
   files them with `session_lifecycle.py file --to MetaReviews <files>`. Then work through the
   tickets one at a time.

**Source files:** [[Processes/MetaReview|MetaReview process]] · [[Tools/session-analysis/README|session-analysis README]] · [[Tools/session-lifecycle/README|session-lifecycle README]] · [[Skills/start-session/SKILL|/start-session]] · [[Skills/end-session/SKILL|/end-session]] · [[Skills/inaccuracy/SKILL|/inaccuracy]] · [[Skills/iteration/SKILL|/iteration]]

---

← [[06_Investigation|Investigation Mode]] · [[00_Overview|Overview]] · [[08_Commands|Command Reference]] →


### HTML fallback when tracking is unavailable

Retrospective HTML rendering does not require session tracking. If `set` or `compile --final`
fails because the transcript or session is unavailable, continue the retrospective and mark
metrics and the router trace unavailable. Never invent a session folder or use another session's
metrics. Save `<FeatureName>_<Phase>_Retro.md` in the feature working folder; for other lanes,
save a uniquely named retrospective under the project's `GitIgnoreReports/Retrospectives/`.
Then always render and open the saved Markdown with:

```bash
python3 session_lifecycle.py retro --path "<saved-retrospective.md>" --open
```

This bypasses session lookup and writes a matching `.html` beside the Markdown without copying
or renaming the source. Missing metrics do not block rendering; charts without data are omitted.
The proposal buttons use `retro --path` too, so later `--mark` updates the original Markdown and
re-renders its page. `--path` cannot be combined with `--folder` or `--from`. If compilation fails
but the current session folder is known, use its actual retrospective path. Open any separately
available sanitized usage report alongside the HTML; do not stop at opening Markdown alone.
If rendering or opening fails, report that failure and link the saved artifacts.

## Codex session tracking

The lifecycle tracker accepts Codex rollouts as well as Claude transcripts. In Codex,
`CODEX_THREAD_ID` selects the exact thread; `--session-id` can select a known thread explicitly.
It never picks the newest Codex thread. Missing or ambiguous rollouts fail without attaching
another session's data. Rollouts are located below `$CODEX_HOME/sessions` (default
`~/.codex/sessions`). Do not pass `unknown` or invent an ID.

Run the existing commands from the host checkout:

```bash
python3 <lifecycle-script> hook-start
python3 <lifecycle-script> set --lane other --work-type other --title "Session tooling"
python3 <lifecycle-script> note --kind inaccuracy --source agent "Description of correction"
python3 <lifecycle-script> compile
```

Use the appropriate lane/title for the actual task. `compile --final` belongs at session end.
Session folders contain the agent type, notes, metrics and sanitized token reports. The existing
session-support Codex parser supplies usage; cumulative token events must not be summed.
Codex shell reads, including supported nested JavaScript exec commands, produce heuristic
Bash rows in the router trace. Main-thread trace coverage does not imply complete child-agent
trace coverage. Detailed standardized-operation attribution and comparison charts remain
unavailable for Codex rather than showing misleading zeros. Token reports may still include
child-agent telemetry supported by session-support.

These parser changes do not install automatic hooks. Current Codex supports a trusted project
`.codex/hooks.json` with `SessionStart`, `Stop` and `SessionEnd` command hooks calling
`hook-start`, `hook-stop` and `hook-end`. Hook payloads supply `session_id` and `transcript_path`.
Use the resolved lifecycle script path; preserve any existing hooks. Configure Stop with an
adequate timeout (for example 30 seconds), and SessionEnd with its supported maximum of 3
seconds. The Stop hook keeps metrics current even when closing a window does not end a thread.
Trust/reload the project hooks in Codex before expecting automatic execution. No Claude hook
execution is implied by a Codex skills installation.

Reference: https://learn.chatgpt.com/docs/hooks . Transcript formats are not a stable hook API;
keep synthetic regression fixtures and report parser failures as unavailable. Without a usable
transcript, retain the sanitized usage report and `retro --path` HTML fallback.

