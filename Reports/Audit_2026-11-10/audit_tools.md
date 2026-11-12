# Tool / skill usage audit — transcripts vs manual equivalents

Generated 2026-11-10 13:47. Source: 155 top-level transcripts + 124 subagent transcripts in `/Users/aramirez/.claude/projects/-Users-aramirez-Documents-Projects-TripleMatch3D`.
Weeks covered: 2026-W42 .. 2026-W46. Classified events: 6024.

Heuristics: grep/rg over C# (Assets/ or *.cs) whose pattern holds a PascalCase/interface name = 'type grep' (should be codeindex/usages). Whole `.cs` Read = Read with no limit/offset; 'shape-only' = never edited in that session. Ad-hoc python = `python3 -c` / heredoc / /tmp script. Subagent events are attributed to the parent session id.

## 1. Invocation counts (all weeks)

| Item | Calls | Sessions | 2026-W42 | 2026-W43 | 2026-W44 | 2026-W45 | 2026-W46 |
|---|---:|---:|---:|---:|---:|---:|---:|
| tool:session_lifecycle.py | 786 | 148 | 96 | 134 | 255 | 198 | 103 |
| tool:feature_state.py | 357 | 23 | 0 | 0 | 0 | 264 | 93 |
| tool:doc_review.py | 318 | 54 | 0 | 31 | 179 | 97 | 11 |
| tool:typecheck.py | 245 | 27 | 50 | 26 | 8 | 81 | 80 |
| tool:install.py | 182 | 58 | 17 | 15 | 64 | 49 | 37 |
| tool:codeindex.py | 105 | 30 | 23 | 17 | 10 | 20 | 35 |
| tool:progress_view.py | 76 | 21 | 0 | 0 | 58 | 17 | 1 |
| tool:new_session.py | 53 | 39 | 0 | 16 | 19 | 12 | 6 |
| tool:unitysource.py | 32 | 7 | 16 | 4 | 0 | 1 | 11 |
| tool:mermaid_preview.py | 27 | 10 | 8 | 14 | 2 | 3 | 0 |
| tool:ExitWorktree | 24 | 16 | 3 | 5 | 2 | 11 | 3 |
| tool:EnterWorktree | 23 | 18 | 3 | 6 | 3 | 8 | 3 |
| tool:token_breakdown.py | 22 | 9 | 5 | 5 | 4 | 6 | 2 |
| tool:perf_view.py | 20 | 8 | 0 | 0 | 11 | 9 | 0 |
| tool:preview-control | 18 | 5 | 0 | 0 | 0 | 16 | 2 |
| tool:session_meta_report.py | 15 | 4 | 5 | 5 | 0 | 4 | 1 |
| tool:session-support | 14 | 5 | 4 | 7 | 0 | 1 | 2 |
| tool:usages.py | 11 | 4 | 1 | 0 | 0 | 3 | 7 |
| tool:retro_page.py | 10 | 5 | 0 | 2 | 8 | 0 | 0 |
| tool:code-graph | 6 | 2 | 0 | 0 | 0 | 5 | 1 |
| tool:project_config.py | 3 | 3 | 0 | 0 | 0 | 0 | 3 |
| tool:legacy_migration.py | 3 | 2 | 0 | 0 | 0 | 3 | 0 |
| tool:export_confluence.py | 2 | 2 | 0 | 1 | 0 | 0 | 1 |
| skill:new-session | 34 | 34 | 0 | 4 | 16 | 8 | 6 |
| skill:audit | 27 | 21 | 4 | 7 | 1 | 6 | 9 |
| skill:end-session | 18 | 18 | 3 | 3 | 9 | 3 | 0 |
| skill:land-worktree | 15 | 15 | 3 | 0 | 2 | 6 | 4 |
| skill:checkpoint | 7 | 7 | 1 | 1 | 2 | 1 | 2 |
| skill:publish-batch | 5 | 3 | 0 | 0 | 0 | 2 | 3 |
| skill:feature-pr | 3 | 3 | 0 | 0 | 0 | 1 | 2 |
| skill:preview-feature | 2 | 2 | 0 | 0 | 2 | 0 | 0 |
| skill:dataviz | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| skill:token-usage-reports | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| skill:artifact-design | 1 | 1 | 1 | 0 | 0 | 0 | 0 |
| skill:claude-in-chrome | 1 | 1 | 0 | 1 | 0 | 0 | 0 |
| skill:resume-work | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| skill:kill-server | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| mcp:TripleMatch_WaitForEditorReady | 72 | 7 | 0 | 0 | 0 | 24 | 48 |
| mcp:Unity_RunCommand | 64 | 7 | 0 | 0 | 0 | 10 | 54 |
| mcp:TripleMatch_StateV3_Step | 25 | 3 | 0 | 0 | 0 | 5 | 20 |
| mcp:Unity_GetConsoleLogs | 19 | 7 | 0 | 0 | 0 | 3 | 16 |
| mcp:TripleMatch_GameProgressSaveSlim__917bada0 | 14 | 1 | 0 | 0 | 0 | 0 | 14 |
| mcp:TripleMatch_GameProgressSaveSlim__29d82a42 | 13 | 1 | 0 | 0 | 0 | 0 | 13 |
| mcp:TripleMatch_GameProgressSaveSlim__9647a5bb | 9 | 1 | 0 | 0 | 0 | 0 | 9 |
| mcp:TripleMatch_GameProgressSaveSlim__9ec2e158 | 5 | 1 | 0 | 0 | 0 | 0 | 5 |
| mcp:TripleMatch_GameProgressSaveSlim__f0aeae45 | 2 | 2 | 0 | 0 | 0 | 0 | 2 |
| mcp:TripleMatch_GameProgressSaveSlim__2a7695b4 | 2 | 1 | 0 | 0 | 0 | 0 | 2 |
| mcp:Unity_GetProjectData | 1 | 1 | 0 | 0 | 0 | 0 | 1 |
| agent:Explore | 74 | 33 | 7 | 8 | 13 | 34 | 12 |
| agent:fork | 45 | 11 | 6 | 0 | 8 | 17 | 14 |
| agent:general-purpose | 27 | 9 | 14 | 5 | 0 | 3 | 5 |
| agent:general-purpose(default) | 2 | 2 | 0 | 0 | 1 | 0 | 1 |
| agent:Plan | 1 | 1 | 0 | 0 | 0 | 0 | 1 |
| agent:claude-code-guide | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| audit:via_agent | 26 | 9 | 9 | 6 | 3 | 4 | 4 |
| discover:via_agent | 1 | 1 | 0 | 0 | 0 | 0 | 1 |
| manual:grep_type_cs | 478 | 42 | 119 | 113 | 30 | 119 | 97 |
| manual:read_cs_whole | 448 | 33 | 26 | 26 | 70 | 182 | 144 |
| manual:adhoc_python | 412 | 69 | 87 | 59 | 77 | 130 | 59 |
| manual:grep_in_cs_file | 221 | 29 | 79 | 60 | 4 | 41 | 37 |
| manual:shell_cat_cs_whole | 187 | 27 | 83 | 38 | 3 | 29 | 34 |
| manual:state_edit_tool | 167 | 32 | 16 | 49 | 97 | 5 | 0 |
| manual:git_worktree_remove | 55 | 32 | 3 | 4 | 20 | 14 | 14 |
| manual:state_edit_bash | 54 | 21 | 6 | 11 | 34 | 3 | 0 |
| manual:find_cs_file | 28 | 13 | 8 | 5 | 3 | 2 | 10 |
| manual:git_worktree_add | 15 | 11 | 4 | 1 | 8 | 1 | 1 |
| manual:editor_log | 12 | 1 | 0 | 12 | 0 | 0 | 0 |
| manual:build_cmd | 3 | 2 | 2 | 0 | 1 | 0 | 0 |
| read:cs_partial | 155 | 28 | 33 | 18 | 4 | 72 | 28 |
| edit:cs | 446 | 21 | 160 | 83 | 0 | 116 | 87 |

Ad-hoc python breakdown: generic=251, tool-dev/test=80, feature-state=26, cs-parse=26, doc-review=20, transcripts/tokens=9

### Engineer-typed slash commands (user messages)

| Command | Count | 2026-W42 | 2026-W43 | 2026-W44 | 2026-W45 | 2026-W46 |
|---|---:|---:|---:|---:|---:|---:|
| /end-session | 102 | 5 | 16 | 34 | 30 | 17 |
| /resume-work | 46 | 8 | 9 | 12 | 13 | 4 |
| /land-worktree | 46 | 0 | 4 | 19 | 16 | 7 |
| /small-task | 27 | 1 | 1 | 17 | 6 | 2 |
| /active-features | 25 | 5 | 4 | 8 | 8 | 0 |
| /exit | 25 | 2 | 1 | 10 | 8 | 4 |
| /compact | 11 | 0 | 0 | 0 | 6 | 5 |
| /checkpoint | 11 | 1 | 0 | 6 | 4 | 0 |
| /new-session | 9 | 0 | 4 | 3 | 2 | 0 |
| /large-task | 9 | 0 | 0 | 0 | 3 | 6 |
| /kill-server | 8 | 0 | 0 | 8 | 0 | 0 |
| /preview-feature | 6 | 0 | 0 | 6 | 0 | 0 |
| /feature | 5 | 0 | 3 | 2 | 0 | 0 |
| /bug-fix | 5 | 2 | 1 | 0 | 2 | 0 |
| /start-preview-server | 4 | 0 | 0 | 4 | 0 | 0 |
| /clear | 4 | 0 | 0 | 0 | 4 | 0 |
| /iteration | 3 | 1 | 2 | 0 | 0 | 0 |
| /generate-meta-review | 3 | 3 | 0 | 0 | 0 | 0 |
| /close-feature | 2 | 0 | 0 | 2 | 0 | 0 |
| /run-investigation-mode | 2 | 0 | 2 | 0 | 0 | 0 |
| /export | 1 | 0 | 0 | 1 | 0 | 0 |
| /login | 1 | 0 | 1 | 0 | 0 | 0 |
| /start-session | 1 | 0 | 1 | 0 | 0 | 0 |
| /mcp | 1 | 1 | 0 | 0 | 0 | 0 |

## 2. Dead / near-dead tools and skills (agent-initiated calls)

| Item | Agent calls | Sessions |
|---|---:|---:|
| skill:active-features (user-typed /active-features: 25) | 0 | 0 |
| skill:bug-fix (user-typed /bug-fix: 5) | 0 | 0 |
| skill:close-feature (user-typed /close-feature: 2) | 0 | 0 |
| skill:discover (user-typed /discover: 0) | 0 | 0 |
| skill:feature (user-typed /feature: 5) | 0 | 0 |
| skill:generate-meta-review (user-typed /generate-meta-review: 3) | 0 | 0 |
| skill:inaccuracy (user-typed /inaccuracy: 0) | 0 | 0 |
| skill:iteration (user-typed /iteration: 3) | 0 | 0 |
| skill:large-task (user-typed /large-task: 9) | 0 | 0 |
| skill:reopen-feature (user-typed /reopen-feature: 0) | 0 | 0 |
| skill:run-investigation-mode (user-typed /run-investigation-mode: 2) | 0 | 0 |
| skill:small-task (user-typed /small-task: 27) | 0 | 0 |
| skill:start-preview-server (user-typed /start-preview-server: 4) | 0 | 0 |
| skill:start-session (user-typed /start-session: 1) | 0 | 0 |
| skill:uses (user-typed /uses: 0) | 0 | 0 |
| mcp:TripleMatch_Parsers_Find | 0 | 0 |
| mcp:TripleMatch_Parsers_Create | 0 | 0 |
| mcp:TripleMatch_Parsers_Aggregate | 0 | 0 |
| mcp:TripleMatch_Prize_CreateCode | 0 | 0 |
| mcp:TripleMatch_Prize_CreateAssets | 0 | 0 |
| skill:kill-server (user-typed /kill-server: 8) | 1 | 1 |
| skill:resume-work (user-typed /resume-work: 46) | 1 | 1 |
| skill:token-usage-reports (user-typed /token-usage-reports: 0) | 1 | 1 |
| tool:export_confluence.py (docs-export) | 2 | 2 |
| skill:preview-feature (user-typed /preview-feature: 6) | 2 | 2 |
| tool:legacy_migration.py (feature-state) | 3 | 2 |
| tool:project_config.py (setup) | 3 | 3 |
| skill:feature-pr (user-typed /feature-pr: 0) | 3 | 3 |

## 3. Tool vs manual ratios, by week

### type lookup: codeindex+usages+code-graph+/uses vs grep-type+find .cs

| Week | Tool | Manual | Tool share |
|---|---:|---:|---:|
| 2026-W42 | 24 | 127 | 16% |
| 2026-W43 | 17 | 118 | 13% |
| 2026-W44 | 10 | 33 | 23% |
| 2026-W45 | 28 | 121 | 19% |
| 2026-W46 | 43 | 107 | 29% |
| **all** | **122** | **506** | **19%** |

### compile check: typecheck vs Editor.log/build

| Week | Tool | Manual | Tool share |
|---|---:|---:|---:|
| 2026-W42 | 50 | 2 | 96% |
| 2026-W43 | 26 | 12 | 68% |
| 2026-W44 | 8 | 1 | 89% |
| 2026-W45 | 81 | 0 | 100% |
| 2026-W46 | 80 | 0 | 100% |
| **all** | **245** | **15** | **94%** |

### feature state: feature_state.py vs hand-edit state.json/_Progress.md

| Week | Tool | Manual | Tool share |
|---|---:|---:|---:|
| 2026-W42 | 0 | 22 | 0% |
| 2026-W43 | 0 | 60 | 0% |
| 2026-W44 | 0 | 131 | 0% |
| 2026-W45 | 264 | 8 | 97% |
| 2026-W46 | 93 | 0 | 100% |
| **all** | **357** | **221** | **62%** |

### survey: /discover vs Explore/general-purpose agents

| Week | Tool | Manual | Tool share |
|---|---:|---:|---:|
| 2026-W42 | 0 | 21 | 0% |
| 2026-W43 | 0 | 13 | 0% |
| 2026-W44 | 0 | 14 | 0% |
| 2026-W45 | 0 | 37 | 0% |
| 2026-W46 | 1 | 18 | 5% |
| **all** | **1** | **103** | **1%** |

### worktree: EnterWorktree vs git worktree add

| Week | Tool | Manual | Tool share |
|---|---:|---:|---:|
| 2026-W42 | 3 | 4 | 43% |
| 2026-W43 | 6 | 1 | 86% |
| 2026-W44 | 3 | 8 | 27% |
| 2026-W45 | 8 | 1 | 89% |
| 2026-W46 | 3 | 1 | 75% |
| **all** | **23** | **15** | **61%** |

### shape: codeindex vs whole .cs Read

| Week | Tool | Manual | Tool share |
|---|---:|---:|---:|
| 2026-W42 | 23 | 26 | 47% |
| 2026-W43 | 17 | 26 | 40% |
| 2026-W44 | 10 | 70 | 12% |
| 2026-W45 | 20 | 182 | 10% |
| 2026-W46 | 35 | 144 | 20% |
| **all** | **105** | **448** | **19%** |

## 4. Whole-file .cs reads

Whole .cs Reads: 448 (partial reads with limit/offset: 155). Of the whole reads, 332 were of files never edited in that session (candidate shape-only reads; some are legitimately reading bodies).

Most re-read unedited files: GameProgressSaveSlimManager.cs×5, GameProgressSaveSlimLocalStore.cs×5, IPlayerDataManager.cs×5, JsonParserGeneratorWindow.cs×5, GameProgressSaveSlimRoundLifecycleTests.cs×4, LevelEndMessage.cs×4, IGameProgressSaveSlimRecordPlayerData.cs×4, RefreshPlayerDataMessage.cs×4, RoundStartMessage.cs×4, AppRefresher.cs×4, CustomizableEditorWindow.cs×4, HomeFlowAction.cs×4

Sessions with most unedited whole .cs reads: 0807f03f(79), 940df0e1(65), df415033(36), d2f8687a(32), 3dbfcc30(11), dea0dba1(11), 47f9489d(9), ed8294d7(9)

## 5. Manual approach within 20 tool calls of a rule/skill that names the tool

Rule/skill loads mentioning codeindex/usages/typecheck/uses/discover: 192. Manual hits right after: 58 in 19 sessions.

| Session | Lane | Week | Trigger | Manual call |
|---|---|---|---|---|
| 0bf4ef1e | bug_fix | 2026-W45 | BugFix.md | `grep -rn "EditorSetDirty" --include=*.cs Assets/Plugins` |
| 0bf4ef1e | bug_fix | 2026-W45 | BugFix.md | `grep -rln "static void EditorSetDirty" --include=*.cs Assets)` |
| 0bf4ef1e | bug_fix | 2026-W46 | BugFix.md | `grep -rlE "class $n\b" --include=*.cs Assets` |
| 1066edb9 | feature | 2026-W43 | index.md | `grep -rn -E "public (static )?[A-Za-z<>\[\]]+ [A-Z][A-Za-z]*\(" Assets/Plugins/JamCity/JamCity.RST.FileExport/` |
| 1066edb9 | feature | 2026-W43 | index.md | `grep -rln "FileExporter" Assets/Scripts` |
| 3dbfcc30 | feature | 2026-W45 | Phase4_Implementation.md | `grep -rl "IPlayerDataManager" Assets/Scripts/UnitTests/Editor/DummyImplementations/ 2>/dev/null` |
| 3dbfcc30 | feature | 2026-W45 | Phase4_Implementation.md | `grep -rln "CreatePlayerDataInstance" Assets/Scripts/UnitTests 2>/dev/null` |
| 44073bb2 | large_task | 2026-W46 | LargeTask.md | `grep -rn --include=*.cs -E "interface IStateMachine\b" ..` |
| 44073bb2 | large_task | 2026-W46 | LargeTask.md | `grep -rln --include=*.cs "class StateLevelExtender\b" .` |
| 4b0ea820 | large_task | 2026-W46 | LargeTask.md | `grep -rl "EditorCoroutine" --include=*.cs Assets` |
| 55447ec3 | bug_fix | 2026-W43 | BugFix.md | `grep -rn "FetchEvents()" Assets/Scripts --include=*.cs` |
| 55447ec3 | bug_fix | 2026-W43 | BugFix.md | `grep -rln "class ShopCheckAction" Assets/Scripts)` |
| 55447ec3 | bug_fix | 2026-W43 | BugFix.md | `grep -rln "class MagicMatchGemEventController" Assets/Scripts)` |
| 648fa8a3 | bug_fix | 2026-W45 | BugFix.md | `grep -rln "IStateService\b" Assets/Scripts Assets/Plugins/JamCity --include=*.cs` |
| 648fa8a3 | bug_fix | 2026-W45 | BugFix.md | `grep -rl "class AbstractStateTypes" Assets/Plugins --include=*.cs)` |
| 6be0f3b5 | feature | 2026-W42 | index.md | `grep -rl 'class GameplayController\b' Assets/Scripts` |
| 6be0f3b5 | feature | 2026-W42 | index.md | `grep -rl 'class PieceSpawner\b' Assets/Scripts` |
| 6be0f3b5 | feature | 2026-W42 | index.md | `grep -rl --include=*.cs -E 'using HarmonyLib` |
| 763b85b8 | other | 2026-W42 | BugFix.md | `grep -rl "class Skinner<" Assets/Scripts` |
| 763b85b8 | other | 2026-W42 | BugFix.md | `grep -v "Assets/Scripts/SkinSystem/"` |
| 763b85b8 | other | 2026-W42 | BugFix.md | `grep -rln "MagicItemBadge" Assets/Scripts --include=*.cs` |
| 96830ca5 | large_task | 2026-W46 | LargeTask.md | `grep -rn "RootPlayerData" --include=*.cs Assets/Plugins Assets/Editor 2>/dev/null` |
| 96830ca5 | large_task | 2026-W46 | LargeTask.md | `grep -v "^\S*I[A-Za-z]*PlayerData.cs:.*\[RootPlayerData"` |
| 96830ca5 | large_task | 2026-W46 | LargeTask.md | `grep -rln "IAuthPlayerData" --include=*.cs Assets` |
| 9c50708e | large_task | 2026-W45 | LargeTask.md | `grep -rIl --include=*.cs -E "HttpListener` |
| c9fb47ff | bug_fix | 2026-W42 | BugFix.md | `grep -rl 'class EventTimerController' Assets/Scripts)` |
| c9fb47ff | bug_fix | 2026-W42 | BugFix.md | `grep -rn 'eventPersistentUserData' Assets/Scripts/Events/BaseEvent/*.cs` |
| c9fb47ff | bug_fix | 2026-W42 | SmallTask.md | `grep -rn 'enum EventStatus' -A14 Assets/Plugins/JamCity/Disney.RainbowCore.Events` |
| d9df16d6 | large_task | 2026-W45 | LargeTask.md | `grep -rIl --include=*.cs -E "HttpListener` |
| db87f677 | small_task | 2026-W43 | SmallTask.md | `grep -v "^Assets/Scripts/Debug/Commands/FileExport/"` |
| dea0dba1 | bug_fix | 2026-W42 | BugFix.md | `grep -rn "GetEncoding(" --include=*.cs Zip Zlib` |
| dea0dba1 | bug_fix | 2026-W42 | BugFix.md | `grep -rln "GZipStream" Assets/Plugins/JamCity/JamCity.CommonSdk/Utils/Ionic --include=*.cs` |
| dea0dba1 | bug_fix | 2026-W42 | BugFix.md | `grep -rln "GZipStream" Assets/Plugins/JamCity/JamCity.CommonSdk/Utils/Ionic --include=*.cs` |
| e6c82bcd | feature | 2026-W45 | index.md | `grep -rl "GameProgressSaveSlim" Assets --include="*.cs" 2>/dev/null` |
| ed8294d7 | feature | 2026-W46 | Phase4_Implementation.md | `find Assets/Scripts -iname "*Lives*" -name "*.cs" 2>/dev/null; echo "---"; find Assets/Scripts/GameProgressSav` |
| f9645c31 | feature | 2026-W42 | index.md | `grep -rl 'class GameplayController\b' Assets/Scripts` |
| f9645c31 | feature | 2026-W42 | index.md | `grep -rl 'class PieceSpawner\b' Assets/Scripts` |
| f9645c31 | feature | 2026-W42 | index.md | `grep -rl --include=*.cs -E 'using HarmonyLib` |
| fa1d443c | small_task | 2026-W46 | SmallTask.md | `grep -rl "class LivesManager\b" Assets --include=*.cs` |

## 6. typecheck.py at session start/end (sessions with C# edits)

Sessions with C# edits: 21. Any typecheck: 21. Baseline before first C# edit: 7. After last C# edit: 19. Neither: 0.

| Session | Lane | Week | C# edits | typechecks | baseline | after last edit |
|---|---|---|---:|---:|---|---|
| 763b85b8 | other | 2026-W42 | 5 | 7 | - | Y |
| c9fb47ff | bug_fix | 2026-W42 | 9 | 7 | - | Y |
| dea0dba1 | bug_fix | 2026-W42 | 146 | 36 | Y | Y |
| 3f0ef897 | small_task | 2026-W43 | 35 | 6 | - | Y |
| 55447ec3 | bug_fix | 2026-W43 | 28 | 13 | - | Y |
| db87f677 | small_task | 2026-W43 | 20 | 7 | Y | Y |
| 0bf4ef1e | bug_fix | 2026-W45 | 3 | 1 | - | Y |
| 3dbfcc30 | feature | 2026-W45 | 29 | 21 | - | Y |
| 648fa8a3 | bug_fix | 2026-W45 | 7 | 3 | Y | - |
| 85ae8bd4 | bug_fix | 2026-W45 | 20 | 9 | Y | Y |
| 940df0e1 | feature | 2026-W45 | 32 | 20 | - | Y |
| 9c50708e | large_task | 2026-W45 | 14 | 14 | Y | Y |
| d9df16d6 | large_task | 2026-W45 | 14 | 14 | Y | Y |
| 0807f03f | feature | 2026-W46 | 6 | 4 | - | - |
| 44073bb2 | large_task | 2026-W46 | 9 | 14 | - | Y |
| 44fcdd57 | feature | 2026-W46 | 16 | 6 | - | Y |
| 96830ca5 | large_task | 2026-W46 | 11 | 7 | Y | Y |
| bcd1bf13 | feature | 2026-W46 | 11 | 11 | - | Y |
| d291940c | large_task | 2026-W46 | 18 | 16 | - | Y |
| ed8294d7 | feature | 2026-W46 | 7 | 2 | - | Y |
| fa1d443c | small_task | 2026-W46 | 6 | 2 | - | Y |

## 7. /audit in Phase 4 and LargeTask sessions

Phase 4 = session Read Phase4_Implementation.md; LargeTask = lane large_task or Read LargeTask.md. Audit = Skill audit, user /audit, or Agent whose prompt/description invokes audit.

| Session | Kind | Week | distinct C# files edited | audit calls | files/audit |
|---|---|---|---:|---:|---|
| 176cb8de | phase4 | 2026-W43 | 0 | 0 | - |
| 8b285bb8 | phase4 | 2026-W43 | 0 | 0 | - |
| 0244313d | phase4 | 2026-W44 | 0 | 0 | - |
| 05b6b31d | phase4 | 2026-W44 | 0 | 0 | - |
| 19d9a1e5 | phase4 | 2026-W44 | 0 | 0 | - |
| 647027f5 | phase4 | 2026-W44 | 0 | 0 | - |
| 8ebd79c0 | phase4 | 2026-W44 | 0 | 0 | - |
| 3dbfcc30 | phase4 | 2026-W45 | 11 | 1 | 11.0 |
| 47f9489d | phase4 | 2026-W45 | 0 | 0 | - |
| 940df0e1 | phase4 | 2026-W45 | 12 | 4 | 3.0 |
| 966f5d06 | large_task | 2026-W45 | 0 | 0 | - |
| 9c50708e | large_task | 2026-W45 | 8 | 3 | 2.7 |
| ba15b60a | large_task | 2026-W45 | 0 | 0 | - |
| d9df16d6 | large_task | 2026-W45 | 8 | 0 | NO AUDIT |
| e6c82bcd | phase4 | 2026-W45 | 0 | 0 | - |
| fe1b7825 | large_task | 2026-W45 | 0 | 0 | - |
| 0807f03f | phase4 | 2026-W46 | 4 | 0 | NO AUDIT |
| 168403e1 | large_task | 2026-W46 | 0 | 0 | - |
| 26894b0a | large_task | 2026-W46 | 0 | 0 | - |
| 44073bb2 | large_task | 2026-W46 | 7 | 1 | 7.0 |
| 44fcdd57 | phase4 | 2026-W46 | 4 | 2 | 2.0 |
| 4b0ea820 | large_task | 2026-W46 | 0 | 0 | - |
| 96830ca5 | large_task | 2026-W46 | 6 | 1 | 6.0 |
| b2cfdac5 | large_task | 2026-W46 | 0 | 4 | - |
| bcd1bf13 | phase4 | 2026-W46 | 5 | 2 | 2.5 |
| d1251dce | large_task | 2026-W46 | 0 | 0 | - |
| d291940c | large_task | 2026-W46 | 6 | 0 | NO AUDIT |
| ed8294d7 | phase4 | 2026-W46 | 5 | 1 | 5.0 |

Totals: 76 distinct C# files edited, 19 audit invocations.

## 8. Top manual patterns with example sessions

### manual:grep_type_cs — 478 calls, 42 sessions

Top sessions: dea0dba1(87), 55447ec3(50), b630b04b(35), 940df0e1(34), 0807f03f(29), 61db1b7f(21)

- 07497810 2026-W42: `grep -rl "class LeaderboardMission\b" Assets/Scripts`
- 4b0ea820 2026-W46: `grep -rn "LevelEndMessage(" Assets/Scripts --include=*.cs`
- 940df0e1 2026-W45: `grep -rn "RoundStartMessage" Assets/Scripts --include="*.cs"`
- d9df16d6 2026-W45: `grep -n -E "InternalsVisibleTo" -r Assets/Scripts/Serialization/JsonParser`

### manual:read_cs_whole — 448 calls, 33 sessions

Top sessions: 940df0e1(97), 0807f03f(80), df415033(36), d2f8687a(32), 3dbfcc30(30), dea0dba1(20)

- 0807f03f 2026-W46: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/Scripts/GameProgressSaveSlim/IGameProgressSaveSlimManager.cs`
- 3dbfcc30 2026-W45: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/Scripts/GameProgressSaveSlim/GameProgressSaveSlimManager.cs`
- 940df0e1 2026-W45: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/Plugins/JamCity/Disney.RainbowCore.MessageBus/IMessageBus.cs`
- d2f8687a 2026-W44: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/Plugins/JamCity/RemoteDebugger/DebugObjectWrapperEntity.cs`

### manual:adhoc_python:generic — 251 calls, 49 sessions

Top sessions: 6be0f3b5(38), a8083556(37), 81b0e727(17), b2cfdac5(17), ff277bdd(14), 940df0e1(12)

- 048ca0e4 2026-W44: `cd /Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/Features/RemoteDebugger/_publish && \ python3 - <<'EOF' import re path = "c`
- 6be0f3b5 2026-W42: `python3 - <<'EOF' import html m=open('ClassDiagram.miro.mmd').read() G='ILevelProgressParticipant~TProgressContract, TResumePlayerData~' reps=[  ('   `
- 8b285bb8 2026-W43: `python3 /private/tmp/claude-502/-Users-aramirez-Documents-Projects-TripleMatch3D/8b285bb8-59eb-40f1-ae8f-a2ea3b5ffa3d/scratchpad/smoke_test_sidecar_st`
- ac9592d7 2026-W42: `cat /Users/aramirez/.npm/_npx/668c188756b835f3/node_modules/puppeteer/package.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get(`

### manual:grep_in_cs_file — 221 calls, 29 sessions

Top sessions: dea0dba1(66), 55447ec3(23), 3f0ef897(18), b630b04b(18), 3dbfcc30(9), 940df0e1(8)

- 0807f03f 2026-W46: `grep -n "ToastDebugWindow" AndreaTools.cs`
- 4b0ea820 2026-W46: `grep -nE "TryPushPauseState\(\)" -B8 Assets/Scripts/States/StateGameplay.cs`
- 9c50708e 2026-W45: `grep -l "#if !RC" Assets/Scripts/Editor/*.cs 2>/dev/null`
- dea0dba1 2026-W42: `grep -n "GZipStream" Assets/Plugins/JamCity/JamCity.CommonSdk/Utils/Ionic/Zlib/ZlibBaseStream.cs`

### manual:shell_cat_cs_whole — 187 calls, 27 sessions

Top sessions: dea0dba1(74), 55447ec3(17), bcd1bf13(13), 940df0e1(8), 0bf4ef1e(7), c9fb47ff(7)

- 0807f03f 2026-W46: `sed -n '270,300p' Assets/Scripts/App/AppController.cs; echo "---StateLevelExtender---"; sed -n '1,60p' Assets/Scripts/States/StateLevelExtender.cs; ec`
- 55447ec3 2026-W43: `cd /Users/aramirez/Documents/Projects/TripleMatch3D; cat -n Assets/Scripts/Installers/ConfigServiceInstaller.cs | sed -n 1,80p; cat -n Assets/Scripts/`
- bcd1bf13 2026-W46: `cat -n "/Users/aramirez/Documents/Projects/TripleMatch3D/.claude/worktrees/GameProgressSaveSlim-T10/Assets/Scripts/GameProgressSaveSlim/Bridges/LivesF`
- dea0dba1 2026-W42: `cd /Users/aramirez/Documents/Projects/TripleMatch3D/Assets/Scripts; cat -n Gameplay/Levels/Level.cs | sed -n 1,260p`

### manual:state_edit_tool — 167 calls, 32 sessions

Top sessions: df415033(17), 176cb8de(16), 911d273d(15), 4815a01d(11), 048ca0e4(10), 2e2966d6(10)

- 0244313d 2026-W44: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/Features/LocalDocReviewV1/LocalDocReviewV1_Progress.md`
- 37415c83 2026-W44: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/Features/RemoteDebugger/RemoteDebugger_Progress.md`
- 8b285bb8 2026-W43: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/Features/LocalDocReview/LocalDocReview_Progress.md`
- b72013fa 2026-W44: `/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_Progress.md`

### manual:adhoc_python:tool-dev/test — 80 calls, 33 sessions

Top sessions: 70eb9730(10), 8b285bb8(10), b2cfdac5(9), 324a4f5f(6), 000c8ff2(4), 048ca0e4(3)

- 000c8ff2 2026-W43: `cd /Users/aramirez/Documents/Projects/TripleMatch3D; python3 - <<'EOF' import json,sys sys.path.insert(0,"GitIgnoredExternals/AIAgentCoreRules/Tools/s`
- 324a4f5f 2026-W45: `W=/Users/aramirez/Documents/Projects/AIAgentCoreRules/.claude/worktrees/context-warning; T=/Users/aramirez/.claude/jobs/324a4f5f/tmp; cd $W && python3`
- 70eb9730 2026-W45: `D=/Users/aramirez/Documents/Projects/AIAgentCoreRules/Tools/doc-review; J=/Users/aramirez/.claude/jobs/70eb9730/tmp/Features; cd $D && python3 -c " im`
- 8b285bb8 2026-W43: `cd /Users/aramirez/Documents/Projects/TripleMatch3D/GitIgnoredExternals/AIAgentCoreRules/Tools/doc-review && python3 -c " import sys sys.path.insert(0`

### manual:git_worktree_remove — 55 calls, 32 sessions

Top sessions: 1276ce25(5), b95f96af(4), e04dc790(4), 3eabf4b3(3), 940df0e1(3), afd92e6b(3)

- 05b6b31d 2026-W44: `git commit --no-edit -q && git log --oneline -1 && for n in batched-publishing close-feature-docs new-session; do git worktree remove .claude/worktree`
- 3eabf4b3 2026-W44: `C=/Users/aramirez/Documents/Projects/AIAgentCoreRules; cd $C; git commit -q --no-edit && git log --oneline -1; git worktree remove $C/.claude/worktree`
- 884c5af4 2026-W44: `cd /Users/aramirez/Documents/Projects/AIAgentCoreRules && git commit -q --no-edit && git log --oneline -1 && git worktree remove .claude/worktrees/clo`
- b95f96af 2026-W44: `git commit -q --no-edit; git log --oneline -1; git merge-base --is-ancestor agent/comments-actionable HEAD && echo ancestor-ok && git worktree remove `

### manual:state_edit_bash — 54 calls, 21 sessions

Top sessions: 1d9e60e4(7), 6be0f3b5(6), 7f130d75(6), 840ac78c(6), 75453a1d(4), 048ca0e4(3)

- 048ca0e4 2026-W44: `python3 - <<'EOF' import sys, tempfile, shutil from pathlib import Path sys.path.insert(0, "tests") sys.path.insert(0, ".") import test_progress_view `
- 2e2966d6 2026-W44: `python3 - <<'EOF' import sys, tempfile, shutil from pathlib import Path sys.path.insert(0, "tests") sys.path.insert(0, ".") import test_progress_view `
- 6be0f3b5 2026-W42: `python3 - <<'EOF' p='GameProgressSave_Progress.md' s=open(p).read() s=s.replace('updated_at:     "2026-10-13T16:30:00"','updated_at:     "2026-10-14T0`
- 80cd2d84 2026-W44: `T=/Users/aramirez/.claude/jobs/80cd2d84/tmp/verify; rm -rf $T; mkdir -p $T; F=/Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/`

### manual:find_cs_file — 28 calls, 13 sessions

Top sessions: dea0dba1(7), 4b0ea820(6), 55447ec3(3), 447cf920(2), d9df16d6(2), 0807f03f(1)

- 0807f03f 2026-W46: `echo "--- ParserMcpTools ---" && find . -path ./Library -prune -o -name "ParserMcpTools.cs" -print 2>/dev/null && echo "--- StateV3McpTools ---" && fi`
- 4b0ea820 2026-W46: `cd /Users/aramirez/Documents/Projects/TripleMatch3D; sed -n 54,100p Assets/Scripts/States/StateLevelFailed.cs; sed -n 150,180p Assets/Scripts/States/S`
- 9e37356e 2026-W43: `grep -rn "MagicItemCollectedMessage\b\|new MagicItemCollectedMessage\|MagicItemResultsMetaData" Assets/Scripts --include=*.cs | grep -v UnitTests | gr`
- dea0dba1 2026-W42: `grep -n "protected\|public\|private void OnGUI" Assets/Plugins/JamCity/Disney.RainbowCore.Inspectables.Editor/CustomizableEditor/CustomizableEditorWin`

### manual:adhoc_python:feature-state — 26 calls, 10 sessions

Top sessions: 6be0f3b5(4), 7f130d75(4), 840ac78c(4), 1066edb9(3), 1d9e60e4(3), 70eb9730(3)

- 1066edb9 2026-W43: `cd /Users/aramirez/.claude/jobs/1066edb9/tmp/gps && cp /Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/Features/GameProgressSa`
- 1d9e60e4 2026-W43: `python3 - <<'EOF' from pathlib import Path P=Path("LocalDocReviewV1_Progress.md"); t=P.read_text() t=t.replace('"LocalDocReviewV1_Discovery.md"]','"Lo`
- 70eb9730 2026-W45: `python3 - <<'EOF' import json,glob,re for d in ["ExtenderScreenCharacterAddition","GameProgressSave","GameProgressSaveSlim"]:     s=json.load(open(f"{`
- 7f130d75 2026-W44: `cd /Users/aramirez/Documents/Projects/TripleMatch3D/Assets/GitIgnoreAssets/Features/RemoteDebugger && python3 - <<'EOF' p='RemoteDebugger_Progress.md'`

### manual:adhoc_python:cs-parse — 26 calls, 12 sessions

Top sessions: 55447ec3(5), 9c50708e(4), 44073bb2(3), 85ae8bd4(3), d9df16d6(2), db87f677(2)

- 42fc6f90 2026-W44: `cd /Users/aramirez/Documents/Projects/TripleMatchAiMetaData; python3 - <<'EOF' from pathlib import Path p=Path("Systems/DebugTooling.md"); s=p.read_te`
- 55447ec3 2026-W43: `python3 - <<'EOF' p='Assets/Scripts/Installers/ConfigServiceInstaller.cs' s=open(p).read() old="    private IAuthManager _authManager;\n\n    protecte`
- 85ae8bd4 2026-W45: `cd Assets/Scripts/Editor/AgentTools && for f in McpGenerationStepRunner EditorReadyMcpTools ParserMcpTools PrizeMcpTools StateV3McpTools; do printf 'f`
- c9fb47ff 2026-W42: `python3 - <<'EOF' p='Assets/Scripts/Events/MissionCenter/MissionCenterEvent.cs' s=open(p,encoding='utf-8').read() old='        private bool _isHandlin`

### manual:adhoc_python:doc-review — 20 calls, 9 sessions

Top sessions: 7f130d75(4), 840ac78c(4), 8b285bb8(4), 87a61cf7(2), ff277bdd(2), 37415c83(1)

- 37415c83 2026-W44: `python3 -c " import json with open('Assets/GitIgnoreAssets/Features/RemoteDebugger/RemoteDebugger_GDD.md.review.json') as f:     data = json.load(f) f`
- 7f130d75 2026-W44: `python3 -c " import json d=json.load(open('RemoteDebugger_GDD.md.review.json')) th=d.get('threads',d) if isinstance(d,dict) else d th=list(th.values()`
- 87a61cf7 2026-W45: `python3 -c " import json data = json.load(open('review.json')) print(type(data), list(data.keys()) if isinstance(data, dict) else len(data)) " echo "-`
- 8b285bb8 2026-W43: `python3 /private/tmp/claude-502/-Users-aramirez-Documents-Projects-TripleMatch3D/8b285bb8-59eb-40f1-ae8f-a2ea3b5ffa3d/scratchpad/smoke_test_doc_review`

### manual:git_worktree_add — 15 calls, 11 sessions

Top sessions: b95f96af(3), 884c5af4(2), dea0dba1(2), 19d9a1e5(1), 3302947d(1), 70a54416(1)

- 19d9a1e5 2026-W44: `git worktree add -b agent/phase3-design-delta .claude/worktrees/phase3-design-delta HEAD 2>&1 | tail -1; grep -rn "CreateFeature\.md" --include=*.md -`
- 763b85b8 2026-W42: `git worktree add -b user/andi/DT-20157_particle_gradient_copy .claude/worktrees/DT-20157 HEAD 2>&1 | tail -2`
- 911d273d 2026-W44: `cd /Users/aramirez/Documents/Projects/TripleMatch3D && python3 GitIgnoredExternals/AIAgentCoreRules/Tools/new-session/new_session.py --in terminal "Ap`
- b95f96af 2026-W44: `cd /Users/aramirez/Documents/Projects/AIAgentCoreRules && git worktree add -q -b agent/comments-actionable .claude/worktrees/comments-actionable HEAD `

### manual:editor_log — 12 calls, 1 sessions

Top sessions: 55447ec3(12)

- 55447ec3 2026-W43: `L=~/Library/Logs/Unity/Editor.log; ls -la $L; grep -n "userEvents?includeConfig\|Config service unavailable\|Logged in with no events loaded\|StatusCo`
- 55447ec3 2026-W43: `grep -n "ServiceLoggerWriter: 2026-10-22T22:[34]" /Users/aramirez/Library/Logs/Unity/Editor.log | grep -i "gem\|config\|auth\|login\|503\|userEvents" `
- 55447ec3 2026-W43: `grep -n -i "dcp\|StoreManager\|store init\|CheckForActions\|productconfig\|product config" /Users/aramirez/Library/Logs/Unity/Editor.log | awk -F: '$1`
- 55447ec3 2026-W43: `sed -n '72447,72480p' /Users/aramirez/Library/Logs/Unity/Editor.log | grep -v "^\s*$" | grep -iv "^UnityEngine\.\|^JamCity.CommonSdk.Executor\|(at " |`

### manual:adhoc_python:transcripts/tokens — 9 calls, 5 sessions

Top sessions: b2cfdac5(3), 316406f7(2), 70a54416(2), 000c8ff2(1), 7fc29e9c(1)

- 000c8ff2 2026-W43: `cd /Users/aramirez/Documents/Projects/TripleMatch3D; python3 - <<'EOF' import json s=json.load(open("GitIgnoreReports/Sessions/2026-10-12_1027_other_0`
- 316406f7 2026-W46: `python3 - <<'EOF' import re,os for f in ['~/.codex/sessions/2026/10/13/rollout-2026-10-13T15-11-20-01a13751-f699-7641-a47a-04a5c0859449.jsonl','~/.cod`
- 70a54416 2026-W42: `cat > /Users/aramirez/.claude/jobs/70a54416/tmp/dedup.py <<'EOF' import json,glob,os os.chdir('/Users/aramirez/Documents/Projects/TripleMatch3D/GitIgn`
- b2cfdac5 2026-W46: `cd /Users/aramirez/.claude/projects/-Users-aramirez-Documents-Projects-TripleMatch3D/; f=$(ls -S *.jsonl | tail -40 | head -1); head -c 3000 $f; echo;`

### manual:build_cmd — 3 calls, 2 sessions

Top sessions: dea0dba1(2), 447cf920(1)

- 447cf920 2026-W44: `S=/private/tmp/claude-502/-Users-aramirez-Documents-Projects-TripleMatch3D/447cf920-8c54-4eeb-8163-5adec94dfc90/scratchpad/t; rm -rf $S; mkdir -p $S/m`
- dea0dba1 2026-W42: `cd /Users/aramirez/Documents/Projects/TripleMatch3D; grep -rln --include=*.cs "CopyLogFileDebugCommand\|ExportToAndroidDownloads\|ExportToPersistentDa`
- dea0dba1 2026-W42: `cd /Users/aramirez/Documents/Projects/TripleMatch3D; sed -n 30,70p Assets/Scripts/Installers/DebugCommandManagerInstaller.cs; cat -n Assets/Scripts/De`

## 9. Per-lane usage of key tools (sessions using / sessions in lane)

| Lane | Sessions | tool:typecheck.py | tool:codeindex.py | tool:usages.py | skill:discover | skill:audit | manual:grep_type_cs | manual:read_cs_whole |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| feature | 48 | 6 | 8 | 1 | 0 | 8 | 17 | 14 |
| other | 47 | 5 | 6 | 0 | 0 | 1 | 7 | 4 |
| small_task | 28 | 4 | 3 | 0 | 0 | 3 | 4 | 3 |
| unset | 12 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| large_task | 9 | 6 | 6 | 2 | 0 | 3 | 7 | 6 |
| bug_fix | 6 | 6 | 6 | 1 | 0 | 6 | 6 | 6 |
| untracked | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| investigation | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |

## 10. Context splits

feature_state.py first used 2026-11-02T18:31:33.362Z. Hand edits of state.json/_Progress.md: 221 total, 8 after that date (sessions: 47f9489d, 70eb9730, ff277bdd).

After-date hand edits by target: state.json=5, bash=3

git worktree remove / branch -D: 55 calls; 48 inside sessions that ran /land-worktree (skill-directed), 7 outside.

git worktree add sessions: 19d9a1e5 2026-W44, 3302947d 2026-W45, 70a54416 2026-W43, 763b85b8 2026-W42, 884c5af4 2026-W44, 884c5af4 2026-W44, 911d273d 2026-W44, aa8a3a96 2026-W44, b2cfdac5 2026-W46, b95f96af 2026-W44, b95f96af 2026-W44, b95f96af 2026-W44, c9fb47ff 2026-W42, dea0dba1 2026-W42, dea0dba1 2026-W42

## 11. Session metrics.md token categories (by week of session folder)

| Week | Sessions | Runnable tools | Skills | Subagents | Ad-hoc tool calls |
|---|---:|---:|---:|---:|---:|
| 2026-W39 | 1 | 0.0% | 0.0% | 0.0% | 0.0% |
| 2026-W40 | 16 | 0.0% | 0.0% | 0.0% | 0.0% |
| 2026-W41 | 18 | 0.2% | 0.0% | 3.0% | 16.0% |
| 2026-W42 | 17 | 0.2% | 0.1% | 4.2% | 6.6% |
| 2026-W43 | 24 | 0.3% | 0.3% | 5.1% | 27.1% |
| 2026-W44 | 48 | 0.2% | 0.3% | 4.1% | 17.3% |
| 2026-W45 | 43 | 0.4% | 0.6% | 10.5% | 20.0% |
| 2026-W46 | 20 | 0.5% | 0.9% | 18.2% | 15.5% |
