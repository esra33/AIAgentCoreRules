---
name: end-session
description: Close the session - compile token metrics and the router trace, write a retrospective scaled to the session's lane, open both files for the engineer, and propose (not apply) rule and index improvements. Use when the engineer runs /end-session or asks to wrap up, close out, or review the session.
---

# End Session

Lifecycle script (use the path from the Session tracking block if present):
`GitIgnoredExternals/AIAgentCoreRules/Tools/session-lifecycle/session_lifecycle.py`

All rule paths below are relative to the AIAgentCoreRules root (the parent of the `Rules/`
folder that holds MetaRouter.md).

---

## Step 0 — Land the worktree

Runs before Step 1, so the landing turns are part of the compiled metrics and router trace.

```yaml
active_worktree:   # any one of these means the session worked in a worktree
  - "The working directory is under .claude/worktrees/."
  - "This session entered or created a worktree (EnterWorktree, an agent run with worktree isolation, or `git worktree add`)."
steps:
  - "No active worktree → skip to Step 1. Do not ask."
  - "Run: python3 Tools/setup/install.py worktrees    # confirm it still exists; note branch, dirty, ahead"
  - "Gone, or clean with 0 ahead → nothing to land; say so in one line and go to Step 1."
  - "Ask the engineer: land <branch> into <main checkout branch> now? Wait for the answer."
  - "no → go to Step 1. Leave the worktree as it is."
  - "yes → if the session is still inside the worktree, commit or show its uncommitted work first, then leave it (ExitWorktree, action keep). Run /land-worktree <name> and follow it to the end, including the engineer's keep/reject test. Then go to Step 1."
  - "Several active worktrees → ask once per worktree; land them one at a time."
```

## Step 1 — Compile

```yaml
steps:
  - "If the lane is not set: classify it now and run: python3 <script> set --lane <lane> --title \"<title>\""
  - "Feature lane, feature not complete: if work stopped partway through a phase, run /checkpoint first; if it stopped at a gate, confirm the gate block is in <FeatureName>_Progress.md."
  - "Run: python3 <script> compile --final     # prints the metrics.md path"
  - "Read metrics.md when compilation succeeds. If tracking or compilation fails, use the HTML fallback below and continue closing the session."
```

The router trace comes from the session transcript, not memory. Treat it as the record of
what was actually loaded. Rows marked `Bash` are inferred from shell commands (a grep counts);
rows marked `Read` are certain.


### HTML fallback when tracking is unavailable

Retrospective HTML rendering does not require session tracking. If `set` or `compile --final`
fails because the transcript or session is unavailable, continue the retrospective and mark
metrics and the router trace unavailable. Never invent a session folder or use another session's
metrics. Save `<FeatureName>_<Phase>_Retro.md` in the feature working folder; for other lanes,
save a uniquely named retrospective under the project's `GitIgnoreReports/Retrospectives/`.
Then always render and open the saved Markdown with:

```bash
python3 <lifecycle script> retro --path "<saved-retrospective.md>" --open
```

This bypasses session lookup and writes a matching `.html` beside the Markdown without copying
or renaming the source. Missing metrics do not block rendering; charts without data are omitted.
The proposal buttons use `retro --path` too, so later `--mark` updates the original Markdown and
re-renders its page. `--path` cannot be combined with `--folder` or `--from`. If compilation fails
but the current session folder is known, use its actual retrospective path. Open any separately
available sanitized usage report alongside the HTML; do not stop at opening Markdown alone.
If rendering or opening fails, report that failure and link the saved artifacts.

## Step 2 — Retrospective, scaled by lane

```yaml
depth:
  feature:        "Only when the progress file's current_phase is 8_retrospective: load ../Processes/CreateFeature/Phase8_Retrospective.md and follow it; its report is retro.md and its benchmarks come from metrics.md — do not ask for /cost. Any earlier phase: a short retro titled '<FeatureName> — Phase <N> <Name>', with the phase file as the Router check's expected load. Phase 8 reads these."
  small_task:     short
  bug_fix:        short
  investigation:  short
  other:          short
```

If metrics.md lists **Lane changes**, the session ran in more than one lane: run the Router check
once per lane segment, splitting the router trace at each change's timestamp. The retrospective
depth follows the lane with the heaviest work.

Short retrospective — write `retro.md` in the session folder with exactly these sections:

```markdown
# Retrospective — <title>

## Outcome
<1–3 lines: what was delivered and how it was verified (typecheck, tests, engineer check)>

## Router check
| Expected for this lane | Loaded? | Note |
<expected loads come from the lane's process file (Processes/SmallTask.md, Processes/BugFix.md,
 Rules/InvestigationMode.md) plus the routing-table rows the work matched. Flag both misses and
 loads that were not needed.>

## Corrections
<one row per correction: every logged inaccuracy, plus every correction visible in the conversation
 that was not logged (the engineer redirected you or rejected an approach, or you retracted a claim).
 Each row: what went wrong → root cause, one of:
 missing-rule | missing-index-entry | rule-ignored | signature-guessed | scope-misread
 and how it was recorded: engineer | agent | retro (see "Back-fill" below).>

## Discovery gaps
<anything looked up mid-task that SystemIndex / Systems/ / SystemPatterns/ should have supplied>

## Proposed changes
| # | File | Change | Why |
<concrete, minimal edits. Not applied. Each Change cell is self-contained — state the facts
 inline, never "the facts above": the applying session reads only this table.>

## Cost
<total tokens, turns, subagents from metrics.md; the 3 heaviest turns and whether each was necessary.
 Quote one total: the "Total tokens" row (each model call counted once). The breakdown shares that total.
 Rank turns by FRESH tokens (Uncached In + Output in the "Highest-Cost Turns" table of tokens/*.md),
 not Total Tokens, which is mostly cache reads. If the heaviest turn by Total is not already in the
 list, add it as a 4th. One numbered line per turn, in this shape, so the meta-analysis can read it:
   1. **T<n>, <fresh> fresh / <total> total, <k> tool calls:** <what the turn did>. **Necessary.** |
      **Partly necessary** — <what was avoidable>. | **Avoidable** — <why>.
 If tokens/ is missing or metrics.md marks tokens unavailable, label the list "estimated" and say why.
 Then one line from metrics.md's "Token breakdown (estimated)": the standardized-operations share and
 the top saving mechanism. retro.html charts these next to the session-vs-average comparison.>
```

**Background session.** Once Step 0 has removed the worktree, the isolation guard refuses Write
in the shared checkout, so retro.md cannot be written into the session folder directly. Write it
to the job tmp dir (`$CLAUDE_JOB_DIR/tmp/retro.md`) and file it with
`python3 <script> retro --from "$CLAUDE_JOB_DIR/tmp/retro.md"`. That copies it into the session
folder and renders retro.html. Step 3's `open` then works unchanged.

Keep it evidence-based: every claim points at a trace row, a logged note, or `file:line`.
Write "none" for an empty section rather than padding it.

**Back-fill.** For each Corrections row that metrics.md does not already list, record it so
the metrics match the retro:
`python3 <script> note --kind inaccuracy --source retro "<what went wrong> → <root cause>"`.
Never back-fill a row that is already logged. The `retro` source keeps back-filled entries
apart from ones logged live, so reports can still tell whether corrections are logged during
the session.

## Step 3 — Open and hand off

```yaml
steps:
  - "Run: python3 <script> open        # renders retro.html from retro.md, opens it and metrics.md"
  - "In chat: 3–5 lines — outcome, cost, top router finding — then the Proposed changes table."
  - "Ask which proposed changes to apply, and where — fresh session first (see the Gate)."
```

## Gate — improvements

Apply only the changes the engineer approves, one file at a time. Rule and index files are
shared across sessions; an unreviewed edit there changes every future session.

Where to apply them, offered in this order:

```yaml
fresh_session:   # default — this session's context is at its largest, and every edit re-reads it
  how: "Mark the approved proposals pending, then print (or run via /new-session):"
  command: '/new-session "Apply proposals <N,M> from <retro.md path>: read only its Proposed changes table, apply each, then mark it with session_lifecycle.py retro --folder <id8> --mark <N> --status applied. Run session_lifecycle.py from the host project root (it resolves GitIgnoreReports/Sessions from the cwd). Layer-repo edits go in a worktree: git -C <layer> worktree add -b agent/<name> <layer>/.claude/worktrees/<name> HEAD"'
  note: "The new session reads the retro's table, not this transcript. Record it as lane other. Copy the command's worktree clause verbatim; for layer repos never substitute EnterWorktree — it isolates only the host project, and its GitIgnoredExternals links still point at the layer's main checkout."
in_place:        # only for 1–2 one-line edits
  how: "Apply here, one file at a time, as below."
```

Record every decision with the script, never by hand-editing retro.md. It writes the
`## Applied` line the meta-analysis reads, creates the section on first use (every other proposal
`pending`), and re-renders retro.html so the page shows the item as done:

```bash
python3 <script> retro --mark 1 --status applied --note "<file> — <what changed>"
python3 <script> retro --mark 2 --status skipped --note "<reason, or 'by engineer'>"
python3 <script> retro --mark 3 --status pending --note "<when it will be done>"   # deferred
```

Every proposal ends with a line, including skipped and deferred ones. Write "- none proposed"
under `## Applied` when the table was empty.

**Resolved later.** A proposal is often done in a later session. When work in any session
resolves a retro proposal, mark it in that retro with `--folder <id8>` (the original session id's
first 8 characters, or its folder name): `python3 <script> retro --folder <id8> --mark <N> --status
applied --note "..."`. `retro --folder <id8>` alone lists the proposals and their status.

When an approved change edits a rule, process, skill or tool, update the matching
`Documentation/` page in the same repository as part of the same change.
