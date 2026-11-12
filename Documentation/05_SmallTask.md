# Small Task Process

For a bounded change: a tool, utility, debug command or behaviour tweak modelled on existing
code. Smaller than a feature — no GDD, TDD or task list, and a single proposal checkpoint.

## When it fits

- Touches one system and at most about 5 files. Documentation/ and Systems/ sync edits that
  follow a code change do not count toward the 5.
- No new config root, player-data schema or server contract.
- An existing example can be followed ("like xyz, but does abc").

If any of these stops being true mid-task, the agent stops, says so in one line and offers
`/large-task` when the work still fits a [[14_LargeTask|large task]] (2–3 systems, no GDD or new
schema/contract, finishable in this session), otherwise `/feature <Name>`. It does not quietly turn a small task into a feature. It can offer a split
instead: two or more small tasks that each fit, the first done in this session and each of the
rest handed off as a ready-to-run `claude "/small-task …"` command with self-contained context
(files, formats, where to work).

When a session that started in another lane turns into a small task, the agent offers the split
first: continue there, or open a fresh session with `/new-session "/small-task <ask>"`.

## Steps

| # | Step | What happens |
|---|---|---|
| 1 | **Scope** | For a tool, script or report: ask whether it is one-off or reusable, and where it runs (Editor, runtime, CLI), then wait. Restate the deliverable in one line. A question with no change is recorded as work type `question` (the process is still loaded and the answer given here), but only while nothing has been changed yet in the session; a follow-up question after delivered work keeps the existing work type; if it later turns into a change, the work type is re-recorded before the proposal. For a warning, limit or threshold, name the cost it should reduce and pick the metric that drives that cost (for example per-call context rather than the session total) before proposing. |
| 2 | **Context** | Read the Systems entry for the owning system and any matching pattern, plus the entry of every system the change uses (sending or listening for messages, pushing or setting states, touching reward flows). Before writing any helper, tool, window, exporter, logger or importer, look for an existing one to extend: first in the host metadata (SystemIndex, Systems, SystemPatterns), then in the codebase (`codeindex.py`, an Explore agent when broad). Inspect the model example with the host's code index (`codeindex.py`) and read only the bodies being copied. If the change sends or listens for a message, read every listener's handler first. If it consumes data written by another skill or tool (a progress block, a sidecar, ids), check that real feature data has the keys the consumer matches on before proposing. When a new check must agree with an existing view (a tab or report), reuse that view's population and filter rules — such as the Performance tab's active-session rule — instead of re-deriving them. |
| 3 | **Rules** | Coding Standards always; Architectural Principles for new classes or interfaces; Resource Management for subscriptions, timers and loads; Multi-Step Operations for async sequences; Testing Rules if tests are requested. |
| 4 | **Propose** | List the files to create or modify, one line each. The agent waits for approval only when more than 2 files change or a public contract changes. A meta-review ticket or handoff note that already states Change and Done-when counts as the approved plan: the agent states the file list and proceeds, and waits only if its plan departs from it. The proposal always names the existing utility it extends and how it was found, or says none was found (with the searches) and asks whether there is an example to follow — in the same round-trip. An example the engineer points to that the metadata did not list becomes a retrospective proposal for a new index entry. In a background job whose target files sit in an unversioned or gitignored folder (the host's personal-not-in-repo list, such as `Assets/GitIgnoreAssets`), the isolation guard refuses every edit there, even through a worktree symlink: the plan says the files are staged in `<worktree>/Staging/` and installed by one engineer `! bash` script — never "edit in place" — and plans for `typecheck.py` to run only after the install. |
| 5 | **Implement** | Stop and Verify checks, then write the code. Edits to a layer repo (AIAgentCoreRules or the host metadata repo) are isolated in a worktree inside that repo (`git -C <layer> worktree add …`, with absolute paths, since `git -C` resolves a relative path against the repo and would nest the worktree), not with EnterWorktree, which isolates only the host project; they land with `/land-worktree` using `install.py --project <layer>`. Before creating the worktree, the agent checks that the layer's main checkout has no uncommitted tracked changes and tells the engineer up front if it does, since `/land-worktree` will not merge until they are committed or stashed. In an EnterWorktree session, git runs as plain single commands from the worktree directory: the isolation guard refuses `cd … &&`, loops and `xargs` around git, so several commits go to one `git cherry-pick` call instead of a loop. In a background session, git-ignored host paths (such as `Assets/GitIgnoreAssets/`) are symlinks into the shared checkout inside an EnterWorktree worktree, and the isolation guard refuses Edit/Write through either path, as well as Bash commands whose text names `GitIgnore*` paths in heredocs. When the change touches only such a file, the agent writes a patch script with Write under `$CLAUDE_JOB_DIR/tmp` (keeping a backup copy) and runs it as one plain `python3 <script> <relative path>` command; there is nothing to commit. Alternatively the engineer sets `"worktree": {"bgIsolation": "none"}` in `.claude/settings.json`. In any worktree-isolated session the guard also refuses compound commands that contain a heredoc or computed variables, and `git -C <shared checkout>`: scripts are written to `$CLAUDE_JOB_DIR/tmp/<name>.py` and run as one plain `python3 <file>` command, and the agent runs ExitWorktree (keep) before any git command on the main checkout. |
| 5b | **Audit** | Run `/audit` once over every changed C# file, including debug tooling and tests. It runs as a fresh forked subagent; the agent waits for its report. The mechanical tags were already checked per edit by the cslint hook; the audit is the judgement review. This is a checkpoint: verification doesn't start until it has run, and self-review (applying the audit brief inline) is not a substitute. The retrospective flags a skipped audit. When no C# changed, skip `/audit` and say so; step 6's real-data run is the check. Porting already-reviewed commits to another branch (cherry-picks, no hand-written C#) also skips `/audit` and Coding Standards, and says so. |
| 6 | **Verify** | Run the host's compile check (`typecheck.py`); the session hooks took a baseline before the first `.cs` edit and block the stop until a run follows the last edit. Tell the engineer how to try it (menu path, debug command, steps). When no C# changed (a Python tool, a skill, Markdown), run the changed tool against copies of real data instead and report what was exercised. For a tool that renders a view (a preview tab, a report), compare the rendered values (statuses, counts, ids) against the source data for at least one real item — a model that builds is not verification — and, if a long-running server serves it, restart it and check the served page. For a tool that writes to an external service (GitHub, Confluence, Slack), its reads and dry run are checked on real data and its write path with a faked client; a real write runs only on a target the engineer names, and is otherwise reported as untested. For a port or cherry-pick: `git cherry <target> <source>` drops commits already present; `git show --cc <merge>` finds merges carrying their own changes (replayed with `cherry-pick -m 1`); `git merge-tree --write-tree --merge-base <src-base> <target> <src-tip>` is the dry run; after the pick, `git diff <src-merge> HEAD -- <PR files>` must be empty or explained; then `typecheck.py --changed --base <target> --include-new`. `--include-new` only picks up files git reports as changed: a new `.cs` file in a gitignored folder (such as `Assets/GitIgnoreAssets/`) is not compiled, so its types show as CS0246, until Unity regenerates the `.csproj` (focus the Editor once). |
| 7 | **Close** | Offer `/end-session`. |

## What the retrospective expects to see loaded

- The Systems entry for the owning system (if one exists)
- Coding Standards, plus each rule file from step 3 the change matched
- Tools: `codeindex.py`, `typecheck.py`, `/audit` — for C# changes only
- When no C# changed: a run of the changed tool against copies of real data instead. Coding
  Standards and the C# tools are not expected, so the retrospective does not flag them as misses.

**Source files:** [[SmallTask]]

---

← [[04_BugFix|Bug Fix Process]] · [[00_Overview|Overview]] · [[14_LargeTask|Large Task Process]] →
