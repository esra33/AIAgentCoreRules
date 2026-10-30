# Small Task Process

For a bounded change: a tool, utility, debug command or behaviour tweak modelled on existing
code. Smaller than a feature — no GDD, TDD or task list, and a single proposal checkpoint.

## When it fits

- Touches one system and at most about 5 files. Documentation/ and Systems/ sync edits that
  follow a code change do not count toward the 5.
- No new config root, player-data schema or server contract.
- An existing example can be followed ("like xyz, but does abc").

If any of these stops being true mid-task, the agent stops, says so in one line and offers
`/feature <Name>`. It does not quietly turn a small task into a feature. It can offer a split
instead: two or more small tasks that each fit, the first done in this session and each of the
rest handed off as a ready-to-run `claude "/small-task …"` command with self-contained context
(files, formats, where to work).

When a session that started in another lane turns into a small task, the agent offers the split
first: continue there, or open a fresh session with `/new-session "/small-task <ask>"`.

## Steps

| # | Step | What happens |
|---|---|---|
| 1 | **Scope** | For a tool, script or report: ask whether it is one-off or reusable, and where it runs (Editor, runtime, CLI), then wait. Restate the deliverable in one line. A question with no change is recorded as work type `question`; if it later turns into a change, the work type is re-recorded before the proposal. |
| 2 | **Context** | Read the Systems entry for the owning system and any matching pattern, plus the entry of every system the change uses (sending or listening for messages, pushing or setting states, touching reward flows). Before writing any helper, tool, window, exporter, logger or importer, look for an existing one to extend: first in the host metadata (SystemIndex, Systems, SystemPatterns), then in the codebase (`codeindex.py`, `/discover`). Inspect the model example with the host's code index (`codeindex.py`) and read only the bodies being copied. If the change sends or listens for a message, read every listener's handler first. If it consumes data written by another skill or tool (a progress block, a sidecar, ids), check that real feature data has the keys the consumer matches on before proposing. |
| 3 | **Rules** | Coding Standards always; Architectural Principles for new classes or interfaces; Resource Management for subscriptions, timers and loads; Multi-Step Operations for async sequences; Testing Rules if tests are requested. |
| 4 | **Propose** | List the files to create or modify, one line each. The agent waits for approval only when more than 2 files change or a public contract changes. A meta-review ticket or handoff note that already states Change and Done-when counts as the approved plan: the agent states the file list and proceeds, and waits only if its plan departs from it. The proposal always names the existing utility it extends and how it was found, or says none was found (with the searches) and asks whether there is an example to follow — in the same round-trip. An example the engineer points to that the metadata did not list becomes a retrospective proposal for a new index entry. |
| 5 | **Implement** | Stop and Verify checks, then write the code. Edits to a layer repo (AIAgentCoreRules or the host metadata repo) are isolated in a worktree inside that repo (`git -C <layer> worktree add …`, with absolute paths, since `git -C` resolves a relative path against the repo and would nest the worktree), not with EnterWorktree, which isolates only the host project; they land with `/land-worktree` using `install.py --project <layer>`. Before creating the worktree, the agent checks that the layer's main checkout has no uncommitted tracked changes and tells the engineer up front if it does, since `/land-worktree` will not merge until they are committed or stashed. In an EnterWorktree session, git runs as plain single commands from the worktree directory: the isolation guard refuses `cd … &&`, loops and `xargs` around git, so several commits go to one `git cherry-pick` call instead of a loop. |
| 5b | **Audit** | Run `/audit` on every changed file, including debug tooling and tests. This is a checkpoint: verification doesn't start until it has run, and self-review is not a substitute. The retrospective flags a skipped audit. When no C# changed, skip `/audit` and say so; step 6's real-data run is the check. Porting already-reviewed commits to another branch (cherry-picks, no hand-written C#) also skips `/audit` and Coding Standards, and says so. |
| 6 | **Verify** | Run the host's compile check (`typecheck.py`). Tell the engineer how to try it (menu path, debug command, steps). When no C# changed (a Python tool, a skill, Markdown), run the changed tool against copies of real data instead and report what was exercised. For a port or cherry-pick: `git cherry <target> <source>` drops commits already present; `git show --cc <merge>` finds merges carrying their own changes (replayed with `cherry-pick -m 1`); `git merge-tree --write-tree --merge-base <src-base> <target> <src-tip>` is the dry run; after the pick, `git diff <src-merge> HEAD -- <PR files>` must be empty or explained; then `typecheck.py --changed --base <target> --include-new`. |
| 7 | **Close** | Offer `/end-session`. |

## What the retrospective expects to see loaded

- The Systems entry for the owning system (if one exists)
- Coding Standards, plus each rule file from step 3 the change matched
- Tools: `codeindex.py`, `typecheck.py`, `/audit` — for C# changes only
- When no C# changed: a run of the changed tool against copies of real data instead. Coding
  Standards and the C# tools are not expected, so the retrospective does not flag them as misses.

**Source files:** [[SmallTask]]

---

← [[04_BugFix|Bug Fix Process]] · [[00_Overview|Overview]] · [[06_Investigation|Investigation Mode]] →
