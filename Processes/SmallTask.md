## apply: on-demand — loaded by [[MetaRouter]]

# Small Task

For a bounded change: a tool, utility, debug command, or behaviour tweak modelled on existing
code. Smaller than a feature — no GDD, TDD, or task list. If the work grows past the limits
below, stop and offer `/feature <Name>`.

Tag definitions: [[CoreTags]]

```yaml
fits_when:
  - "Touches one system and at most ~5 files"
  - "Documentation/ and Systems/ sync edits that follow a code change do not count toward the ~5."
  - "No new config root, player-data schema, or server contract"
  - "An existing example can be followed ('like xyz, but does abc')"
escalate_when:
  - "Any fits_when condition breaks mid-task → stop, say so in one line, offer /feature"
  - "Or offer a split: list two or more small tasks (each within fits_when), do the first here, and hand each remaining one off as a ready-to-run `claude \"/small-task …\"` command with self-contained context (files, formats, where to work)."
lane_switch:
  - "Entering this lane from another one in the same session → offer the split as a choice first: continue here, or /new-session \"/small-task <ask>\". Relay the fresh-session offer `set` prints for a large session. The engineer decides."
```

---

## Steps

```yaml
steps:
  1_scope:
    - "If the request is a tool/script/report: StopAndVerify Scope Gate — ask one-off vs reusable, and Editor/runtime/CLI. Wait."
    - "Restate the deliverable in one line: what it does, where it runs, what it is modelled on."
    - "A question with no change → set --work-type question. If it later turns into a change, re-run `set --work-type <small_feature|other>` before 4_propose."
  2_context:
    - "SystemIndex: Read the Systems/ entry for the owning system, and the SystemPatterns/ file if one matches."
    - "Also read the entry for every system the change USES, not only the one it lives in: sending or listening for a message → the message-bus entry; pushing, popping or setting states → the navigation/state entry; guarding or touching reward flows → the prize entry. Match the change against SystemIndex's trigger comments."
    - "Existing utility first — before writing any helper, tool, window, exporter, logger or importer, look for one to extend, in this order: (1) the host metadata (SystemIndex trigger comments, Systems/, SystemPatterns/); (2) the codebase (codeindex.py where/types on likely names, /discover when broad). Record what you searched for 4_propose."
    - "Model example: codeindex.py where/members <Example>; Read only the bodies you will copy the shape of."
    - "Anything broader than one targeted query → /discover, not inline search."
    - "If the change sends or listens for a message/event: read every listener's handler before choosing dispatch points — how often it fires changes what the listener computes."
    - "When the change consumes data written by another skill or tool (a progress block, a sidecar, ids), check that real feature data actually has the keys the consumer matches on, before 4_propose."
  3_rules:   # routing table, by what the change touches
    always:                    [../Rules/CodingStandards.md]
    new_class_or_interface:    [../Rules/ArchitecturalPrinciples.md]
    subscriptions_timers_loads:[../Rules/ResourceManagementRules.md]
    async_sequences:           [../Rules/MultyStepOperationsRules.md]
    tests_requested:           [../Rules/TestingRules.md]
  4_propose:
    - "Before writing: list files to create/modify, one line each. Wait for OK only if more than 2 files or any public contract changes."
    - "A meta-review ticket or handoff note with Change and Done-when already is the approved plan: state the file list and proceed; wait only if the plan departs from it."
    - "Always name the model: 'Extending <X> (found via <search>)', or 'No existing utility found (searched: <queries>) — is there an example you want me to follow?' The engineer answers in the same round-trip as the plan; no extra stop."
    - "If the engineer points to an example the metadata did not list, propose a Systems/SystemIndex entry for it in the retrospective."
  5_implement:
    - "StopAndVerify pre-generation checks, then write."
    - "In an EnterWorktree session, run git as plain single commands from the worktree cwd. The isolation guard refuses `cd … &&`, loops and `xargs` around git. Pass multiple SHAs to one `git cherry-pick` instead of looping."
    - "Edits to a layer repo (AIAgentCoreRules, the host metadata repo): isolate with a worktree inside that repo (`git -C <abs layer> worktree add -b agent/<name> <abs layer>/.claude/worktrees/<name> HEAD` — absolute paths: git -C resolves a relative path against the repo, not the cwd, and nests the worktree at <layer>/<layer>/), not EnterWorktree, which isolates only the host project. Land with /land-worktree using `install.py --project <layer>`. Before creating the worktree, run `git -C <layer> status --porcelain --untracked-files=no`; if the main checkout has uncommitted tracked changes, tell the engineer now — /land-worktree will refuse to merge until they are committed or stashed."
  5b_audit:   # checkpoint — do not start step 6 until it has run
    - "Run /audit on every changed file, including debug tooling and tests. Fix or report each violation."
    - "Self-review is not a substitute: /end-session flags a skipped audit as a router miss."
    - "No C# changed → skip /audit and say so; 6_verify's real-data run is the check."
    - "port_or_cherry_pick: porting already-reviewed commits to another branch (no hand-written C#) → skip /audit and CodingStandards and say so; verify with 6_verify's port_or_cherry_pick recipe."
  6_verify:
    - "Run typecheck.py. Report its result verbatim if it fails."
    - "port_or_cherry_pick: `git cherry <target> <source>` to drop commits already present; `git show --cc <merge>` to find merges carrying their own changes (replay those with `cherry-pick -m 1`); `git merge-tree --write-tree --merge-base <src-base> <target> <src-tip>` as a dry run; after the pick, `git diff <src-merge> HEAD -- <PR files>` must be empty or explained; then `typecheck.py --changed --base <target> --include-new`."
    - "No C# changed (a Python tool, a skill, Markdown): run the changed tool against copies of real data instead — never the originals — and report what was exercised."
    - "Tell the engineer how to try it (menu path, debug command, steps). Editor-only steps are theirs to run."
  7_close:
    - "Offer /end-session."
```

## Router check (used by /end-session)

```yaml
expected_loads:
  - "Systems/<owning system>.md (if it exists), plus the entry of every system the change uses (messages, states, prizes)"
  - "Rules/CodingStandards.md"
  - "plus each 3_rules row the change matched"
expected_tools: [codeindex.py, typecheck.py, /audit]   # C# changes only
expected_without_csharp: "a run of the changed tool against copies of real data; CodingStandards and the C# tools are not expected"
```
