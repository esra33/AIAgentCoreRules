# Unity Tools

Scripts in `Tools/unity-tools/` that the agent — or anyone — runs against a Unity host project
instead of rebuilding the same analysis by hand. The agent is told to **run these, not
reimplement them**. They ship with the core rules; a host project routes to them from the
"Runnable Tools" section of its SystemIndex (see [[10_HostProjectLayer|Host Project Layer]]).

A script belongs here only if it verifies work, or performs a structured analysis that would
otherwise take many exploratory greps. Every script:

- runs on stock `python3` with no third-party packages,
- finds the project root itself (walking up to `ProjectSettings/ProjectVersion.txt`; override
  with `--project`),
- prints only what the caller needs — quiet on success,
- exits non-zero on failure, so it works in a hook or CI step,
- never writes into `Assets/`, and is safe to run with the Unity Editor open.

## Running them

Call a script by its **literal path** from the project root, one plain command per call —
`python3 GitIgnoredExternals/AIAgentCoreRules/Tools/unity-tools/codeindex.py where LivesManager`.
Never through a shell variable (`R=…; python3 $R/codeindex.py`): in a worktree-isolated session
the guard cannot tell what a computed program path runs and refuses the command, which is how
agents fell back to grep (audit 2026-11-10). The examples below omit the directory.

A grep over C# for a type or member name gets the matching command suggested by the
`hook-bash` PreToolUse hook (see [[07_SessionTracking|Session Tracking]]); free-text
greps are left alone. Two more hooks use these tools on their own: the session's first `.cs`
edit triggers a `typecheck.py --files` baseline, and every `.cs` edit is run through
`cslint.py`; a stop after a `.cs` edit with no later `typecheck.py` run is blocked once.

## Which one do I want?

| Question | Tool |
|---|---|
| Does my change compile? | `typecheck.py` |
| Where is this type *or member* declared? Show me just its source. | `codeindex.py where` / `show` |
| What does this type look like, inherited members included? Who implements it? | `codeindex.py members --inherited` / `implementers` |
| What carries `[SomeAttribute]`? | `codeindex.py attributed` |
| Who *uses* this type, or *calls* this member? | `usages.py` |
| Free text (a log message, a string key, `#if !RC`) | `grep` |
| What does this *Unity engine* API really do? | `unitysource.py` |
| Does my new code break a mechanical coding-standards tag? | `cslint.py` |

`codeindex.py` knows declarations, not call sites. `usages.py` knows call sites, but lexically.
`typecheck.py` is the only authoritative one.

## typecheck.py

Verifies a change compiles without launching Unity, using Unity's bundled Roslyn compiler and
reporting only errors. A full project check takes roughly 7 seconds.

```bash
python3 typecheck.py                     # changed assemblies + everything referencing them
python3 typecheck.py Assembly-CSharp     # named assemblies + their dependents
python3 typecheck.py --all
python3 typecheck.py --changed --base develop
python3 typecheck.py --list              # show the plan, compile nothing
python3 typecheck.py --files Assets/Scripts/Foo.cs   # those files' assemblies + dependents, changed or not
python3 typecheck.py --include-new       # also compile new .cs files not yet in a .csproj
python3 typecheck.py Assembly-CSharp-Editor --define USING_TOOLS   # code behind a define that is off
```

- **Dependents are checked automatically.** Changing an interface in a low-level assembly pulls
  in everything that references it, built in dependency order.
- **A failed dependency marks its dependents `skip`, not `ok`.** Silence is not success.
- **New files need a Unity refresh** (or `--include-new`) — a file not yet in a `.csproj` is not
  compiled, and the script says so. `--include-new` only picks up files git reports as changed: a
  new `.cs` file in a gitignored folder (such as `Assets/GitIgnoreAssets/`) is not compiled, so
  its types show as CS0246, until Unity regenerates the `.csproj` (focus the Editor once).
- **Code behind an `#if` symbol that is off** is compiled out and reports clean. Pass
  `--define SYMBOL` to include it.
- **Git worktrees work without setup.** Run the script from inside the worktree, by the main
  checkout's absolute path and without `--project`. It compiles the worktree's files against
  the main checkout's `.csproj` files and `Library/`, and picks up files added in the
  worktree. Passing `--project` for another checkout compiles that checkout instead, and the
  script warns about it. An `.asmdef` added in the worktree is referenced from
  `Assembly-CSharp` / `Assembly-CSharp-Editor` when it is `autoReferenced` and the main
  checkout has its `.csproj`. If there is no `.csproj`, the script warns: CS0246 errors for
  its types are false — let Unity refresh the main checkout on the branch. A `references`
  entry added to an existing `.asmdef` is not in the main checkout's `.csproj` either:
  CS0246/CS0234 for the newly referenced assembly's types in that assembly are false until
  Unity regenerates the project files (after landing). The script warns naming each pair.
- It is a type check, not a build: it catches signature and reference breakage, not broken
  `[SerializeField]` wiring or missing assets.

The agent must run it before reporting any multi-file C# change as complete, and at the start
and end of a session. Reading `Editor.log` is not a substitute — it is large and usually stale.

## codeindex.py

A SQLite index of every type, member and attribute declaration with its start and end line
(about 5,400 files, 7,200 types, 71,000 members and 14,000 attributes), so lookups and
relationship questions are answered without reading or grepping files.

```bash
python3 codeindex.py where FetchEvents                        # types and members with that name
python3 codeindex.py where GemEventManager.FetchEvents        # just that type's
python3 codeindex.py show GemEventManager.FetchEvents         # its source lines, numbered
python3 codeindex.py members StateLevelExtender --inherited   # + members of indexed bases
python3 codeindex.py attributed RootPlayerData
python3 codeindex.py implementers IEventManager
python3 codeindex.py subclasses Screen                        # transitive
python3 codeindex.py members DummyEventManager --kind method
python3 codeindex.py bases GemEventManager
python3 codeindex.py types --assembly Assembly-CSharp --kind interface
python3 codeindex.py sql "SELECT name, COUNT(*) FROM base_ref GROUP BY name"
python3 codeindex.py schema                   # tables + example queries
```

- **Paste-ready spans.** `where`, `members`, `show` and `attributed` print `path:start-end` and
  the full signature; `start-end` is Read's `offset` and `limit`. `show` includes leading
  attributes and `///` docs and caps each declaration at `--max-lines` (default 200).
- **`--inherited`** walks base lists by simple name, nearest first, and lists bases with no
  source in the project (`MonoBehaviour`) as `not indexed`.
- **Always fresh.** Every query refreshes the index first if anything changed, including files
  Unity has never seen. No manual rebuild is needed.
- Stored at `Library/codeindex.sqlite` (git-ignored, outside `Assets/`). `--json` works on any
  query.
- **Git worktrees work without setup.** Run it from inside the worktree without `--project`; it
  indexes the worktree's files with the main checkout's `.csproj` files and keeps its own
  database in the worktree's `Library/`.
- Files not compiled for the current build target are indexed but marked; `--compiled-only`
  excludes them.
- **Limits:** base types match by simple name, so same-named types in different namespaces can
  collide. All `#if` branches are indexed, so it answers "what exists in source", not "what
  exists in an RC build".
- **Gotchas:** `--no-auto-build` on a stale index exits with "Index is stale…" rather than
  serving the last build — use `sql` on a copy of the database for a snapshot. `build --force`
  re-inserts every row, so `type.id` / `member.id` change across builds; key anything
  persistent by name, not id.

## usages.py

Answers "who uses this type, and which of them call the members I want to move out?" — the
question behind any interface split.

```bash
python3 usages.py IEventManager
python3 usages.py FetchEvents                                 # a member, in any type
python3 usages.py GemEventManager.FetchEvents                 # declarations narrowed to that type
python3 usages.py IEventManager --members FetchEvents,FetchEvent,RefreshEventStatus
python3 usages.py IPrizeManager --assembly Assembly-CSharp --full
```

Every site prints as `path:line: code`, grouped as declares (from codeindex), implements /
extends, calls to the named members, and other references. Each group shows `--limit` lines
(default 60) and summarises the rest per assembly; `--full` shows all.

- **Lexical, not semantic.** A local method with the same name shows up as a call. Use it to
  narrow the files worth reading, then confirm with `typecheck.py`.
- **Events are missed.** Event members are used as `Member +=` / `Member -=`, which never match.
  Grep for those instead.
- Only files in a generated `.csproj` are searched.

## unitysource.py

Shows the decompiled source of the Unity engine's own managed code (`UnityEngine.*` and
`UnityEditor.*`) for the project's Unity version. Use it when the question is about the engine
rather than our code, for example whether a getter copies a value or wraps native memory. That
was the DT-20157 root cause.

```bash
python3 unitysource.py where MinMaxGradientBlittable      # which module declares it
python3 unitysource.py show Gradient                      # outline, one line per member
python3 unitysource.py show Gradient --member Gradient    # full bodies of the named members
python3 unitysource.py grep "new Gradient\(" -C 2         # search what is cached so far
```

- **The cache grows as you ask.** There's no full pass. Each lookup lists modules only until it
  finds the type, and decompiles only the type you show (or a whole module with `module`).
  Everything is cached in `~/Library/Caches/UnityDecompiled/<version>/`, outside the repos. The
  cache never goes stale; a Unity upgrade starts a new folder.
- **Needs `ilspycmd`** (`dotnet tool install -g ilspycmd`). The script sets
  `DOTNET_ROOT=~/.dotnet` itself.
- **Managed code only.** Native behaviour isn't visible, so confirm what you find on the real
  object in the Editor.

## cslint.py

Checks the coding-standards tags a regex or the declaration parser can decide, on **changed
lines only** (against HEAD; an untracked file counts as all lines), so old code in a legacy file
does not drown the new code.

```bash
python3 cslint.py                       # changed .cs files of the repo (vs HEAD, plus untracked)
python3 cslint.py path/A.cs path/B.cs   # those files, changed lines only
python3 cslint.py --all-lines path.cs   # every line
python3 cslint.py --base develop        # changed lines vs another ref
```

It flags `var` [EXPLICIT], a `{` at the end of a code line [ALLMAN], a type or member with no
access modifier [ACCESS], a public non-const field [FIELD], `ServiceLocator.Instance` [DI],
`Debug.Log*` [LOG], and an `async void` that is not an override or event handler [ASYNC]. It is
deliberately quiet on initialisers, interface and enum members, static constructors and partial
methods, and skips auto-generated files. The judgement tags ([SRP] [IFACE] [RES] [SYM], method
design, host rules) are `/audit`'s. Output is `path:line: [TAG] message`; exit 1 on violations.
The session's PostToolUse hook runs it on every edited `.cs` file.

## Orphaned .csproj files

Unity leaves project files behind when an assembly is renamed or removed; this project has
about 26 from 2023–24. Both `typecheck.py` and `usages.py` detect and ignore them;
`typecheck.py --verbose` lists them.

A second kind is not detected: `.csproj` files Unity stopped regenerating (here 6 dated
2026-09-17 — Adjust, Disney.RainbowCore.Environment.Android/iOS,
Disney.RainbowCore.SignInWithGoogle.Android/iOS, JamCity.InboxSdk.Editor). Their hint paths
still resolve, so they count as live, but their ProjectReferences are not maintained. A check
that compares `.asmdef` references to `.csproj` must limit itself to `.asmdef` files changed
since the last sync, as `missing_asmdef_references` does.

## Tests

```bash
python3 -m unittest discover -s Tools/unity-tools/tests -p 'test_*.py'
```

**Source files:** [[Tools/unity-tools/README|Unity tools README]]
