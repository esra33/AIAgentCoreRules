# Agent rules framework — usage audit from session metrics

Generated 2026-11-10 from 191 session folders in `/Users/aramirez/Documents/Projects/TripleMatch3D/GitIgnoreReports/Sessions`. Read-only.
Dates are folder-name start dates; weeks start Monday. Lane = `session.json` lane (final value).

## 1. Lane and work-type distribution

| Lane | Sessions | Share |
| --- | ---: | ---: |
| other | 55 | 29% |
| feature | 52 | 27% |
| small_task | 39 | 20% |
| unset | 19 | 10% |
| bug_fix | 14 | 7% |
| large_task | 9 | 5% |
| investigation | 3 | 2% |

Work types: other 69, feature 50, unset 32, question 15, small_feature 12, bug_fix 10, large_feature 3

### Weekly lanes

| Week | Total | feature | small_task | large_task | bug_fix | investigation | other | unset |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-09-21 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| 2026-09-28 | 19 | 2 | 4 | 0 | 6 | 1 | 4 | 2 |
| 2026-10-05 | 18 | 2 | 6 | 0 | 2 | 1 | 2 | 5 |
| 2026-10-12 | 17 | 6 | 1 | 0 | 2 | 0 | 6 | 2 |
| 2026-10-19 | 24 | 11 | 4 | 0 | 1 | 1 | 4 | 3 |
| 2026-10-26 | 49 | 12 | 16 | 0 | 0 | 0 | 18 | 3 |
| 2026-11-02 | 43 | 15 | 6 | 3 | 3 | 0 | 12 | 4 |
| 2026-11-09 | 20 | 4 | 2 | 6 | 0 | 0 | 8 | 0 |

### Weekly work types

| Week | other | feature | unset | question | small_feature | bug_fix | large_feature |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-09-21 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| 2026-09-28 | 0 | 1 | 14 | 2 | 1 | 1 | 0 |
| 2026-10-05 | 4 | 2 | 5 | 2 | 3 | 2 | 0 |
| 2026-10-12 | 2 | 6 | 2 | 3 | 1 | 3 | 0 |
| 2026-10-19 | 4 | 10 | 3 | 3 | 3 | 1 | 0 |
| 2026-10-26 | 28 | 12 | 3 | 4 | 2 | 0 | 0 |
| 2026-11-02 | 19 | 15 | 4 | 1 | 0 | 3 | 1 |
| 2026-11-09 | 12 | 4 | 0 | 0 | 2 | 0 | 2 |

### Sessions with lane unset (19)

- `2026-09-29_1109_e8f8ebe3` — total –, turns None, loads 0, retro no
- `2026-09-29_1415_b952f5ff` — total 180k, turns 5, loads 0, retro no
- `2026-10-05_1803_626ac085` — total 172k, turns 2, loads 0, retro no
- `2026-10-05_1918_8b780298` — total 0, turns 2, loads 0, retro no
- `2026-10-07_1509_sessionmetricsreworkandimprovements_d30fefd1` — total 229k, turns 2, loads 0, retro no
- `2026-10-07_1530_17363d23` — total 0, turns 2, loads 0, retro no
- `2026-10-08_1450_c16dc73c` — total 117k, turns 1, loads 0, retro no
- `2026-10-17_0102_22ccd073` — total 0, turns 1, loads 0, retro no
- `2026-10-17_0102_47b1592d` — total 0, turns 1, loads 0, retro no
- `2026-10-20_1316_3a63cb24` — total 122k, turns 2, loads 0, retro no
- `2026-10-22_1058_983ff344` — total 122k, turns 2, loads 0, retro no
- `2026-10-23_1148_38ba3196` — total 0, turns 0, loads 0, retro no
- `2026-10-27_1251_840ac78c` — total 7.5M, turns 19, loads 7, retro no
- `2026-10-28_1054_e8a89797` — total 401k, turns 6, loads 0, retro no
- `2026-10-28_1105_2e2966d6` — total 43.1M, turns 33, loads 12, retro no
- `2026-11-02_1144_9d502996` — total 128k, turns 2, loads 0, retro no
- `2026-11-02_1511_8f7651a1` — total 277k, turns 4, loads 0, retro no
- `2026-11-03_1743_ee9748a8` — total 133k, turns 2, loads 0, retro no
- `2026-11-04_0755_01caf0aa` — total 613k, turns 8, loads 0, retro no

Folder-name lane differs from final session.json lane: 0 sessions (lane set or changed after folder creation).
Sessions with recorded lane changes: 18.

## 2. Rule / process / system file loads

Counted from metrics.md *Loaded on demand* rows (main + subagents). A file counts once per session. `Read` = at least one Read-tool row; Bash rows are the tracker's heuristic (any `.md` path in a command, incl. grep/sed).

### Most loaded (top 25)

| File | Sessions (any) | via Read | Eligible sessions since created | Rate | Size |
| --- | ---: | ---: | ---: | ---: | ---: |
| `AIAgentCoreRules/Processes/CreateFeature/index.md` | 66 | 59 | 191 | 35% | 12k B |
| `AIAgentCoreRules/Processes/SmallTask.md` | 53 | 46 | 190 | 28% | 9k B |
| `AIAgentCoreRules/Processes/CreateFeature/Phase1_Intake.md` | 48 | 42 | 191 | 25% | 18k B |
| `AIAgentCoreRules/Rules/CodingStandards.md` | 43 | 39 | 191 | 23% | 9k B |
| `AIAgentCoreRules/Rules/ArchitecturalPrinciples.md` | 39 | 36 | 191 | 20% | 7k B |
| `TripleMatchAiMetaData/Systems/LocalDocReview.md` | 37 | 30 | 118 | 31% | 28k B |
| `AIAgentCoreRules/Rules/ResourceManagementRules.md` | 30 | 27 | 191 | 16% | 4k B |
| `AIAgentCoreRules/Processes/ExternalDocPass.md` | 26 | 21 | 171 | 15% | 11k B |
| `AIAgentCoreRules/Rules/TestingRules.md` | 26 | 22 | 191 | 14% | 3k B |
| `TripleMatchAiMetaData/SystemIndex.md` | 23 | 10 | 191 | 12% | 12k B |
| `TripleMatchAiMetaData/Rules/TestingSetup.md` | 22 | 18 | 191 | 12% | 6k B |
| `AIAgentCoreRules/Processes/BugFix.md` | 20 | 17 | 190 | 11% | 7k B |
| `AIAgentCoreRules/Processes/CreateFeature/Phase4_Implementation.md` | 19 | 14 | 191 | 10% | 6k B |
| `AIAgentCoreRules/Processes/FeatureState.md` | 19 | 19 | 63 | 30% | 3k B |
| `TripleMatchAiMetaData/Rules/ConfluenceDocs.md` | 18 | 16 | 171 | 11% | 8k B |
| `AIAgentCoreRules/Processes/Templates/TDD_Template.md` | 17 | 11 | 191 | 9% | 7k B |
| `TripleMatchAiMetaData/Systems/DebugTooling.md` | 17 | 14 | 139 | 12% | 14k B |
| `TripleMatchAiMetaData/Systems/RoundLifecycle.md` | 17 | 15 | 124 | 14% | 8k B |
| `TripleMatchAiMetaData/Systems/PlayerDataSystem.md` | 16 | 14 | 191 | 8% | 5k B |
| `AIAgentCoreRules/Processes/Templates/Progress_Template.md` | 14 | 10 | 184 | 8% | 4k B |
| `AIAgentCoreRules/Processes/CreateFeature/Phase2_Discovery.md` | 13 | 11 | 191 | 7% | 2k B |
| `TripleMatchAiMetaData/SystemPatterns/PlayerDataPattern.md` | 13 | 12 | 191 | 7% | 5k B |
| `AIAgentCoreRules/Processes/CreateFeature/Phase3_Design.md` | 11 | 8 | 191 | 6% | 5k B |
| `TripleMatchAiMetaData/Systems/GemEventSystem.md` | 11 | 5 | 191 | 6% | 5k B |
| `TripleMatchAiMetaData/Rules/MagicMatchProjectRules.md` | 11 | 6 | 191 | 6% | 8k B |

### Never loaded (0 sessions)

| File | Created | Eligible sessions | Size |
| --- | --- | ---: | ---: |
| `TripleMatchAiMetaData/SystemPatterns/ScreenNavigationPattern.md` | 2026-08-03 | 191 | 8k B |
| `TripleMatchAiMetaData/Systems/MissionCenter/MissionCenterLocalNotifications.md` | 2026-08-03 | 191 | 1k B |
| `TripleMatchAiMetaData/Systems/MissionCenter/MissionLayerArchitecture.md` | 2026-08-03 | 191 | 2k B |
| `TripleMatchAiMetaData/Systems/SkinSystem/SkinSystemArchitecture.md` | 2026-10-16 | 140 | 9k B |
| `TripleMatchAiMetaData/Systems/SkinSystem/SkinSystemUsage.md` | 2026-10-16 | 140 | 5k B |

### Almost never loaded (1–3 sessions, ≥20 eligible)

| File | Sessions | via Read | Eligible | Created |
| --- | ---: | ---: | ---: | --- |
| `TripleMatchAiMetaData/SystemPatterns/GemEventPattern.md` | 1 | 1 | 191 | 2026-08-03 |
| `TripleMatchAiMetaData/Systems/SessionLifecycle.md` | 1 | 0 | 63 | 2026-11-02 |
| `TripleMatchAiMetaData/SystemPatterns/EventChecklist.md` | 1 | 1 | 191 | 2026-08-03 |
| `TripleMatchAiMetaData/Systems/AirtablePipeline.md` | 1 | 1 | 139 | 2026-10-17 |
| `TripleMatchAiMetaData/Systems/SkinSystem/SkinSystem.md` | 1 | 0 | 140 | 2026-10-16 |
| `TripleMatchAiMetaData/SystemPatterns/PrizeFlowPattern.md` | 1 | 1 | 191 | 2026-08-03 |
| `TripleMatchAiMetaData/Systems/AccountConflictResolution.md` | 2 | 2 | 20 | 2026-11-09 |
| `TripleMatchAiMetaData/Systems/PrizeSystem.md` | 2 | 2 | 191 | 2026-08-03 |
| `TripleMatchAiMetaData/SystemPatterns/HomeFlowActionPattern.md` | 2 | 1 | 20 | 2026-11-09 |
| `TripleMatchAiMetaData/Systems/MissionCenter/MissionCenterArchitecture.md` | 2 | 0 | 191 | 2026-08-03 |
| `TripleMatchAiMetaData/SystemPatterns/README.md` | 2 | 0 | 191 | 2026-08-03 |
| `AIAgentCoreRules/Processes/CreateFeature.md` | 3 | 0 | 191 | 2026-08-03 |

### Traced .md paths outside the rule inventory (feature docs, skills, Documentation/, renamed files)

- `GitIgnoreAssets/Features/GameProgressSave/GameProgressSave_TDD.md` — 25 sessions
- `GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_TDD.md` — 24 sessions
- `GitIgnoreAssets/Features/GameProgressSave/GameProgressSave_Progress.md` — 21 sessions
- `GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_Progress.md` — 16 sessions
- `AIAgentCoreRules/Skills/end-session/SKILL.md` — 14 sessions
- `GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_GDD.md` — 13 sessions
- `GitIgnoreAssets/Features/RemoteDebugger/RemoteDebugger_TDD.md` — 11 sessions
- `AIAgentCoreRules/Tools/session-lifecycle/README.md` — 10 sessions
- `GitIgnoreAssets/Features/LocalDocReview/LocalDocReview_Progress.md` — 10 sessions
- `AIAgentCoreRules/Documentation/07_SessionTracking.md` — 9 sessions
- `GitIgnoreAssets/Features/LocalDocReviewV1/LocalDocReviewV1_Progress.md` — 9 sessions
- `GitIgnoreAssets/Features/RemoteDebugger/RemoteDebugger_Progress.md` — 9 sessions
- `TripleMatchAiMetaData/Runnable/README.md` — 8 sessions
- `GitIgnoreAssets/Features/LocalDocReview/LocalDocReview_TaskList.md` — 8 sessions
- `GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_TaskList.md` — 8 sessions
- `AIAgentCoreRules/Skills/checkpoint/SKILL.md` — 7 sessions
- `AIAgentCoreRules/Skills/land-worktree/SKILL.md` — 7 sessions
- `AIAgentCoreRules/Skills/resume-work/SKILL.md` — 7 sessions
- `GitIgnoreAssets/Features/LocalDocReview/LocalDocReview_TDD.md` — 7 sessions
- `GitIgnoreAssets/Features/LocalDocReviewV1/LocalDocReviewV1_TaskList.md` — 7 sessions
- `AIAgentCoreRules/Tools/session-lifecycle/session_lifecycle.py` — 6 sessions
- `AIAgentCoreRules/Documentation/04_BugFix.md` — 6 sessions
- `GitIgnoreAssets/Features/GameProgressSave/GameProgressSave_GDD.md` — 6 sessions
- `GitIgnoreAssets/DesignDocuments/GameProgressSave_SlimScopeImpact.md` — 6 sessions
- `GitIgnoreAssets/Features/RemoteDebugger/RemoteDebugger_ExistingSurvey.md` — 6 sessions
- `GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_Discovery.md` — 6 sessions
- `AIAgentCoreRules/Skills/start-session/SKILL.md` — 5 sessions
- `AIAgentCoreRules/Skills/feature/SKILL.md` — 5 sessions
- `GitIgnoreAssets/Features/ExtenderScreenCharacterAddition/ExtenderScreenCharacterAddition_TDD.md` — 5 sessions
- `AIAgentCoreRules/Documentation/08_Commands.md` — 5 sessions
- `GitIgnoreAssets/Features/LocalDocReview/LocalDocReview_UseCases.md` — 5 sessions
- `GitIgnoreAssets/Features/LocalDocReviewV1/LocalDocReviewV1_UseCases.md` — 5 sessions
- `GitIgnoreAssets/Features/RemoteDebugger/RemoteDebugger_GDD.md` — 5 sessions
- `AIAgentCoreRules/Skills/publish-batch/SKILL.md` — 5 sessions
- `GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_UseCases.md` — 5 sessions
- `GitIgnoreAssets/Features/GameProgressSaveSlim/GameProgressSaveSlim_Design.md` — 5 sessions
- `AIAgentCoreRules/Documentation/03_CreateFeature.md` — 4 sessions
- `AIAgentCoreRules/Documentation/02_WorkModes.md` — 4 sessions
- `GitIgnoreAssets/Features/ExtenderScreenCharacterAddition/ExtenderScreenCharacterAddition_Progress.md` — 4 sessions
- `AIAgentCoreRules/Skills/active-features/SKILL.md` — 4 sessions

Always-on files also re-loaded on demand (redundant loads): `SystemIndex.md` 23, `MagicMatchProjectRules.md` 11, `MetaRouter.md` 8, `StopAndVerify.md` 7, `CoreTags.md` 6

Load rows by mechanism: main · Read 951, main · Bash 325, subagent · Bash 88, main · Bash → Read 87, subagent · Read 80, subagent · Bash → Read 21

Bash-only share of load rows by week (lower = rule 'load with Read' followed):

| Week | Load rows | Bash-only | Share |
| --- | ---: | ---: | ---: |
| 2026-09-21 | 1 | 1 | 100% |
| 2026-09-28 | 170 | 100 | 59% |
| 2026-10-05 | 91 | 24 | 26% |
| 2026-10-12 | 152 | 64 | 42% |
| 2026-10-19 | 197 | 45 | 23% |
| 2026-10-26 | 388 | 94 | 24% |
| 2026-11-02 | 389 | 68 | 17% |
| 2026-11-09 | 164 | 17 | 10% |

## 3. Router-check compliance

### 3a. Mechanical check from the router trace

Expected = the unconditional part of each lane's `Router check` expected_loads. `*` items are conditional on C# changes (cannot be told from metrics), so their miss rate is an upper bound. `Systems/*` = any Systems/ entry loaded.

| Lane | Sessions | Expected item | Loaded | Missed | Miss rate |
| --- | ---: | --- | ---: | ---: | ---: |
| small_task | 39 | `AIAgentCoreRules/Processes/SmallTask.md` | 36 | 3 | 8% |
| small_task | 39 | `AIAgentCoreRules/Rules/CodingStandards.md*` | 9 | 30 | 77% |
| small_task | 39 | `Systems/*` | 23 | 16 | 41% |
| large_task | 9 | `AIAgentCoreRules/Processes/LargeTask.md` | 9 | 0 | 0% |
| large_task | 9 | `AIAgentCoreRules/Rules/ChangeClassification.md` | 4 | 5 | 56% |
| large_task | 9 | `AIAgentCoreRules/Rules/CodingStandards.md*` | 5 | 4 | 44% |
| large_task | 9 | `Systems/*` | 7 | 2 | 22% |
| bug_fix | 14 | `AIAgentCoreRules/Processes/BugFix.md` | 14 | 0 | 0% |
| bug_fix | 14 | `AIAgentCoreRules/Rules/CodingStandards.md*` | 9 | 5 | 36% |
| bug_fix | 14 | `AIAgentCoreRules/Rules/TestingRules.md*` | 9 | 5 | 36% |
| bug_fix | 14 | `TripleMatchAiMetaData/Rules/TestingSetup.md*` | 8 | 6 | 43% |
| bug_fix | 14 | `Systems/*` | 11 | 3 | 21% |
| investigation | 3 | `AIAgentCoreRules/Rules/InvestigationMode.md` | 2 | 1 | 33% |
| investigation | 3 | `Systems/*` | 1 | 2 | 67% |
| feature | 52 | `AIAgentCoreRules/Processes/CreateFeature/index.md` | 50 | 2 | 4% |
| feature | 52 | `AIAgentCoreRules/Processes/CreateFeature/Phase*` | 52 | 0 | 0% |

**Lane process file loaded, by period** (the core router obligation):

| Period | Process lanes sessions | Process loaded | Rate | Process via Read | Any Systems/ (non-feature) | all mechanical items |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ≤2026-10-15 | 31 | 29 | 94% | 27 | 43% | 73% |
| 10-16..10-27 | 30 | 30 | 100% | 28 | 71% | 91% |
| 10-28..11-04 | 36 | 32 | 89% | 32 | 73% | 84% |
| 11-05..11-10 | 20 | 20 | 100% | 20 | 80% | 82% |

Sessions in a process lane that never loaded their process file:

- `2026-09-28_2139_small-task_b8e199e6` (lane small_task, 0 loads, total –)
- `2026-10-09_1327_investigation_30ec3e93` (lane investigation, 13 loads, total 41.6M)
- `2026-11-03_1141_small-task_afd92e6b` (lane small_task, 12 loads, total 5.8M)
- `2026-11-03_1442_feature_ff277bdd` (lane feature, 7 loads, total 25.4M)
- `2026-11-04_1039_feature_271b474d` (lane feature, 9 loads, total 8.0M)
- `2026-11-04_1117_small-task_eaaf13a6` (lane small_task, 0 loads, total 205k)

### 3b. Retro-reported Router check results (retro.md tables)

Sessions with retro.md: 124; with a parseable Router check table: 123.

| Lane | Retros | Rows | yes | late | partly | no | ignored | n/a | other | Miss share (no+partly+late+ignored / rows excl n/a) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| feature | 39 | 282 | 216 | 3 | 5 | 33 | 0 | 19 | 6 | 16% |
| small_task | 36 | 246 | 133 | 4 | 10 | 30 | 1 | 51 | 17 | 25% |
| large_task | 6 | 62 | 34 | 4 | 5 | 9 | 0 | 7 | 3 | 35% |
| bug_fix | 10 | 94 | 56 | 1 | 6 | 14 | 0 | 12 | 5 | 27% |
| investigation | 3 | 17 | 11 | 0 | 0 | 5 | 0 | 1 | 0 | 31% |
| other | 29 | 130 | 89 | 1 | 6 | 11 | 0 | 15 | 8 | 17% |

**Most frequently missed items (retro tables, all lanes)**

| Item | Misses |
| --- | ---: |
| `/audit` | 15 |
| `Rules/TestingRules.md` | 7 |
| `Systems/PrizeSystem.md` | 5 |
| `/discover` | 5 |
| `Systems/MessageBus.md` | 4 |
| `SystemPatterns/PlayerDataPattern.md` | 3 |
| `Rules/MultyStepOperationsRules.md` | 3 |
| `Rules/CodingStandards.md` | 3 |
| `Processes/Templates/TDD_Template.md` | 3 |
| `codeindex.py` | 3 |
| `Systems/ScreenNavigationSystem.md` | 3 |
| `Processes/SmallTask.md` | 3 |
| `Systems/LocalDocReview.md` | 3 |
| `Systems/DebugTooling.md` | 3 |
| `Systems/GemEventSystem.md` | 2 |
| `Rules/ResourceManagementRules.md` | 2 |
| `usages.py` | 2 |
| `ExternalDocPass.md` | 2 |
| `/process` | 2 |
| `Processes/ExternalDocPass.md` | 2 |
| `Systems/PlayerDataSystem.md` | 2 |
| `Rules/TestingSetup.md` | 2 |
| `Processes/CreateFeature/index.md` | 2 |
| `Rules/ChangeClassification.md` | 2 |
| `TestingRules.md` | 2 |

**Per lane top misses**

- other: `CLAUDE.md` 1; `Rules/MultyStepOperationsRules.md` 1; `Systems/PrizeSystem.md` 1; `Subagent for the PR and stack survey ([DELEGATE])` 1; `usages.py` 1; `CodingStandards / ArchitecturalPrinciples` 1
- small_task: `/audit` 8; `Rules/CodingStandards.md` 3; `Systems/LocalDocReview.md` 3; `Rules/TestingRules.md` 2; `Systems/DebugTooling.md` 2; `Systems/MissionSystem.md` 1
- bug_fix: `/audit` 4; `SystemPatterns/PlayerDataPattern.md` 2; `Systems/PrizeSystem.md` 2; `Systems/MessageBus.md` 2; `Rules/MultyStepOperationsRules.md` 1; `Rules/ResourceManagementRules.md` 1
- investigation: `Systems/PrizeSystem.md` 1; `Investigation output document (Assets/GitIgnoreAssets/Design` 1; `SystemPatterns/NewServicePattern.md` 1; `Coding rules (CodingStandards, ArchitecturalPrinciples)` 1; `codeindex.py` 1
- feature: `Processes/Templates/TDD_Template.md` 3; `Rules/TestingRules.md` 3; `ExternalDocPass.md` 2; `Processes/ExternalDocPass.md` 2; `TestingRules.md` 2; `SystemPatterns/PlayerDataPattern.md` 1
- large_task: `/discover` 4; `Rules/ChangeClassification.md` 2; `/audit` 2; `Systems/AgentCodeGenTools.md` 2; `Rules/TestingRules.md` 1; `Systems/ entry for every system touched` 1

**Retro miss trend by week**

| Week | Retros w/ table | Rows | Misses | Miss share | Sessions with ≥1 miss |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-09-21 | 0 | 0 | 0 | – | – |
| 2026-09-28 | 10 | 55 | 22 | 40% | 80% |
| 2026-10-05 | 10 | 56 | 11 | 20% | 70% |
| 2026-10-12 | 8 | 56 | 15 | 27% | 88% |
| 2026-10-19 | 18 | 112 | 21 | 19% | 78% |
| 2026-10-26 | 33 | 146 | 21 | 14% | 52% |
| 2026-11-02 | 29 | 157 | 33 | 21% | 62% |
| 2026-11-09 | 15 | 105 | 25 | 24% | 80% |

Unclassified Loaded? cells (status `other`) examples:

- `2026-09-28_1500_bug-fix_517dda3d`: ResourceManagementRules / MultyStepOperationsRules
- `2026-09-28_1500_bug-fix_517dda3d`: usages.py or codeindex.py
- `2026-09-28_1500_bug-fix_517dda3d`: typecheck.py
- `2026-09-29_1033_small-task_e2c2f6cf`: Lane history
- `2026-09-29_1033_small-task_e2c2f6cf`: Unneeded loads
- `2026-10-05_1218_small-task_a6d4deed`: Step 1 Scope Gate (one-off vs reusable, where it runs)
- `2026-10-05_1918_feature_game-progress-save_98e98fa8`: Review-pass read budget (≤2 reads + 1 update per pass)
- `2026-10-12_1027_other_07497810`: Processes/MetaReview.md (03 follow-up)

Rule change points used for the trend reading: 2026-10-16 BugFix meta-retro changes; 2026-10-20 multi-retro + meta retro; 2026-10-28 wave of retro-applied SmallTask/end-session changes; 2026-11-05 LargeTask lane added

## 4. Cost

Sessions with token totals: 183 / 191; with category breakdown: 164; with peak_context: 58.

| Lane | n | Median total | p90 total | Max | Median peak ctx | p90 peak ctx | Median turns |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| feature | 52 | 17.2M | 81.6M | 230.9M | 305k | 528k | 13 |
| small_task | 38 | 7.4M | 15.8M | 188.6M | 172k | 227k | 12 |
| large_task | 9 | 15.2M | 29.3M | 32.4M | 231k | 326k | 14 |
| bug_fix | 14 | 14.0M | 38.0M | 153.4M | 184k | 247k | 12 |
| investigation | 3 | 18.3M | 36.9M | 41.6M | – | – | 18 |
| other | 54 | 1.9M | 10.8M | 38.6M | 96k | 129k | 6 |
| unset | 13 | 180k | 6.1M | 43.1M | 75k | 91k | 2 |
| ALL | 183 | 6.0M | 38.0M | 230.9M | 175k | 357k | 10 |

### Token categories (estimated breakdown, 161 sessions)

| Category | Total tokens | Share of all | Median per-session share | p90 share |
| --- | ---: | ---: | ---: | ---: |
| Conversation & base context | 1557.5M | 65% | 79% | 98% |
| Ad-hoc tool calls | 489.3M | 20% | 10% | 25% |
| Subagents | 202.6M | 8% | 0% | 15% |
| Rule & process loads | 137.0M | 6% | 4% | 12% |
| Skills | 10.4M | 0% | 0% | 2% |
| Runnable tools | 8.4M | 0% | 0% | 1% |
| Session lifecycle | 8.3M | 0% | 0% | 2% |

Rule & process loads by lane (median share / median absolute):

| Lane | n | Median share | Median tokens | Median loads per session |
| --- | ---: | ---: | ---: | ---: |
| feature | 49 | 9% | 1.1M | 12 |
| small_task | 34 | 4% | 295k | 8 |
| large_task | 9 | 5% | 813k | 10 |
| bug_fix | 8 | 3% | 355k | 10 |
| investigation | 2 | 3% | 1.0M | 14 |
| other | 49 | 1% | 27k | 3 |
| unset | 13 | 0% | 0 | 0 |

Note: always-on CLAUDE.md imports are part of *Conversation & base context*, not *Rule & process loads*; their bytes are: 44k B total (≈ 11k tokens at 4 B/token, re-sent every call).

### Context-size warnings (feature live since 2026-11-02)

Sessions since 2026-11-02: 63; warning fired in 29 (46%); total firings in hooks.log: 33; marker files present: 25 (marker is deleted when context drops below threshold, so the file undercounts).
By lane: feature 14/19, small_task 3/8, large_task 8/9, bug_fix 3/3, other 1/20, unset 0/4

### Weekly cost

| Week | Sessions | Median total | Sum total | Median peak ctx | Median rule-load share | Median ad-hoc share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-09-21 | 1 | 1.7M | 1.7M | – | – | – |
| 2026-09-28 | 16 | 16.2M | 551.6M | – | – | – |
| 2026-10-05 | 16 | 3.7M | 140.6M | – | 4% | 9% |
| 2026-10-12 | 15 | 12.6M | 367.7M | – | 4% | 12% |
| 2026-10-19 | 23 | 8.4M | 503.2M | – | 5% | 15% |
| 2026-10-26 | 49 | 4.7M | 401.5M | 63k | 3% | 8% |
| 2026-11-02 | 43 | 8.0M | 749.7M | 180k | 4% | 8% |
| 2026-11-09 | 20 | 6.9M | 323.0M | 159k | 3% | 11% |

### Top 10 sessions by total tokens

- `2026-10-23_1536_feature_176cb8de` — 230.9M total, peak –, 32 turns
- `2026-10-02_1035_small-task_5b25d966` — 188.6M total, peak –, 23 turns
- `2026-11-06_1714_feature_3dbfcc30` — 180.6M total, peak 686k, 20 turns
- `2026-10-16_0950_bug-fix_dea0dba1` — 153.4M total, peak –, 50 turns
- `2026-11-04_1651_feature_940df0e1` — 132.1M total, peak 521k, 47 turns
- `2026-09-30_1649_feature_a6ed5f20` — 108.6M total, peak –, 13 turns
- `2026-11-09_0931_feature_0807f03f` — 85.9M total, peak 466k, 33 turns
- `2026-09-29_1536_feature_31a5a042` — 82.8M total, peak –, 37 turns
- `2026-11-03_1218_feature_a8083556` — 70.4M total, peak 538k, 6 turns
- `2026-10-12_1048_feature_81b0e727` — 59.3M total, peak –, 30 turns

## 5. Is the measurement working?

| Check | Sessions | Share |
| --- | ---: | ---: |
| no metrics.md | 0 | 0% |
| empty router trace (0 on-demand loads) | 28 | 15% |
| lane unset | 19 | 10% |
| no token breakdown (pre-2026-10-07 tool or failed) | 27 | 14% |
| tokens.available not true | 4 | 2% |
| no peak_context | 133 | 70% |
| total tokens 0/missing | 8 | 4% |
| turns ≤1 (likely aborted / empty) | 13 | 7% |
| agent field missing (legacy) | 103 | 54% |
| metrics never compiled at end (Ended = in progress) | 10 | 5% |
| /end-session not run | 65 | 34% |
| /end-session not run but retro.md exists | 0 | 0% |
| retro.md without parseable Router check table | 1 | 1% |
| process lane but process file absent from trace | 6 | 3% |
| folder name without lane segment | 20 | 10% |
| transcript file missing on disk | 39 | 20% |
| duplicate session_id across folders | 0 | 0% |

<details><summary>empty router trace (0 on-demand loads) (28)</summary>

- `2026-09-28_2139_small-task_b8e199e6` lane=small_task total=– turns=None
- `2026-09-29_1109_e8f8ebe3` lane=unset total=– turns=None
- `2026-09-29_1112_other_a7b4c6de` lane=other total=– turns=None
- `2026-09-29_1415_b952f5ff` lane=unset total=180k turns=5
- `2026-09-30_1152_other_9a3e0a57` lane=other total=20.7M turns=14
- `2026-10-05_1803_626ac085` lane=unset total=172k turns=2
- `2026-10-05_1918_8b780298` lane=unset total=0 turns=2
- `2026-10-07_1509_sessionmetricsreworkandimprovements_d30fefd1` lane=unset total=229k turns=2
- `2026-10-07_1530_17363d23` lane=unset total=0 turns=2
- `2026-10-08_1306_other_dc17efaf` lane=other total=180k turns=1
- `2026-10-08_1447_other_ee017200` lane=other total=299k turns=2
- `2026-10-08_1450_c16dc73c` lane=unset total=117k turns=1
- `2026-10-15_1421_other_4da5698c` lane=other total=180k turns=2
- `2026-10-17_0102_22ccd073` lane=unset total=0 turns=1
- `2026-10-17_0102_47b1592d` lane=unset total=0 turns=1
- `2026-10-20_1316_3a63cb24` lane=unset total=122k turns=2
- `2026-10-22_1058_983ff344` lane=unset total=122k turns=2
- `2026-10-23_1148_38ba3196` lane=unset total=0 turns=0
- `2026-10-27_1243_other_3bf69f19` lane=other total=188k turns=2
- `2026-10-28_1054_e8a89797` lane=unset total=401k turns=6
- `2026-10-29_1837_other_005c1b4a` lane=other total=607k turns=5
- `2026-11-02_1144_9d502996` lane=unset total=128k turns=2
- `2026-11-02_1511_8f7651a1` lane=unset total=277k turns=4
- `2026-11-03_1743_ee9748a8` lane=unset total=133k turns=2
- `2026-11-04_0755_01caf0aa` lane=unset total=613k turns=8
- `2026-11-04_1117_small-task_eaaf13a6` lane=small_task total=205k turns=5
- `2026-11-04_1450_other_61a07344` lane=other total=202k turns=4
- `2026-11-09_1009_other_316406f7` lane=other total=4.6M turns=12

</details>

<details><summary>lane unset (19)</summary>

- `2026-09-29_1109_e8f8ebe3` lane=unset total=– turns=None
- `2026-09-29_1415_b952f5ff` lane=unset total=180k turns=5
- `2026-10-05_1803_626ac085` lane=unset total=172k turns=2
- `2026-10-05_1918_8b780298` lane=unset total=0 turns=2
- `2026-10-07_1509_sessionmetricsreworkandimprovements_d30fefd1` lane=unset total=229k turns=2
- `2026-10-07_1530_17363d23` lane=unset total=0 turns=2
- `2026-10-08_1450_c16dc73c` lane=unset total=117k turns=1
- `2026-10-17_0102_22ccd073` lane=unset total=0 turns=1
- `2026-10-17_0102_47b1592d` lane=unset total=0 turns=1
- `2026-10-20_1316_3a63cb24` lane=unset total=122k turns=2
- `2026-10-22_1058_983ff344` lane=unset total=122k turns=2
- `2026-10-23_1148_38ba3196` lane=unset total=0 turns=0
- `2026-10-27_1251_840ac78c` lane=unset total=7.5M turns=19
- `2026-10-28_1054_e8a89797` lane=unset total=401k turns=6
- `2026-10-28_1105_2e2966d6` lane=unset total=43.1M turns=33
- `2026-11-02_1144_9d502996` lane=unset total=128k turns=2
- `2026-11-02_1511_8f7651a1` lane=unset total=277k turns=4
- `2026-11-03_1743_ee9748a8` lane=unset total=133k turns=2
- `2026-11-04_0755_01caf0aa` lane=unset total=613k turns=8

</details>

<details><summary>no token breakdown (pre-2026-10-07 tool or failed) (27)</summary>

- `2026-09-25_1455_other_f71484b9` lane=other total=1.7M turns=5
- `2026-09-28_1204_other_49c79734` lane=other total=38.6M turns=16
- `2026-09-28_1304_small-task_4089fd85` lane=small_task total=16.0M turns=8
- `2026-09-28_1500_bug-fix_517dda3d` lane=bug_fix total=16.4M turns=11
- `2026-09-28_1505_bug-fix_d755b9e4` lane=bug_fix total=1.5M turns=3
- `2026-09-28_1705_bug-fix_916e6580` lane=bug_fix total=19.7M turns=11
- `2026-09-28_2139_small-task_b8e199e6` lane=small_task total=– turns=None
- `2026-09-29_1033_small-task_e2c2f6cf` lane=small_task total=14.5M turns=7
- `2026-09-29_1035_bug-fix_e4075e18` lane=bug_fix total=2.2M turns=7
- `2026-09-29_1109_bug-fix_363537e7` lane=bug_fix total=22.0M turns=19
- `2026-09-29_1109_e8f8ebe3` lane=unset total=– turns=None
- `2026-09-29_1112_other_a7b4c6de` lane=other total=– turns=None
- `2026-09-29_1415_b952f5ff` lane=unset total=180k turns=5
- `2026-09-29_1536_feature_31a5a042` lane=feature total=82.8M turns=37
- `2026-09-30_1152_other_9a3e0a57` lane=other total=20.7M turns=14
- `2026-09-30_1649_feature_a6ed5f20` lane=feature total=108.6M turns=13
- `2026-10-01_1404_bug-fix_dt-19873-live-levelmilestones-softlock-c_cbe95a32` lane=bug_fix total=3.4M turns=5
- `2026-10-01_1527_other_codereview-hardlevelpersistence_f06dfe99` lane=other total=13.5M turns=15
- `2026-10-01_2034_investigation_checkingimplicationsfor-6b4eb0ef71c34b5b_f5d1e044` lane=investigation total=3.0M turns=5
- `2026-10-02_1035_small-task_5b25d966` lane=small_task total=188.6M turns=23
- `2026-10-05_1218_small-task_a6d4deed` lane=small_task total=9.0M turns=3
- `2026-10-05_1803_626ac085` lane=unset total=172k turns=2
- `2026-10-05_1918_8b780298` lane=unset total=0 turns=2
- `2026-10-05_1918_feature_game-progress-save_98e98fa8` lane=feature total=50.8M turns=44
- `2026-10-07_1509_sessionmetricsreworkandimprovements_d30fefd1` lane=unset total=229k turns=2
- `2026-10-07_1530_17363d23` lane=unset total=0 turns=2
- `2026-11-04_0756_other_47f9489d` lane=other total=16.4M turns=24

</details>

<details><summary>transcript file missing on disk (39)</summary>

- `2026-09-25_1455_other_f71484b9` lane=other total=1.7M turns=5
- `2026-09-28_1204_other_49c79734` lane=other total=38.6M turns=16
- `2026-09-28_1304_small-task_4089fd85` lane=small_task total=16.0M turns=8
- `2026-09-28_1500_bug-fix_517dda3d` lane=bug_fix total=16.4M turns=11
- `2026-09-28_1505_bug-fix_d755b9e4` lane=bug_fix total=1.5M turns=3
- `2026-09-28_1705_bug-fix_916e6580` lane=bug_fix total=19.7M turns=11
- `2026-09-28_2139_small-task_b8e199e6` lane=small_task total=– turns=None
- `2026-09-29_1033_small-task_e2c2f6cf` lane=small_task total=14.5M turns=7
- `2026-09-29_1035_bug-fix_e4075e18` lane=bug_fix total=2.2M turns=7
- `2026-09-29_1109_bug-fix_363537e7` lane=bug_fix total=22.0M turns=19
- `2026-09-29_1109_e8f8ebe3` lane=unset total=– turns=None
- `2026-09-29_1112_other_a7b4c6de` lane=other total=– turns=None
- `2026-09-29_1415_b952f5ff` lane=unset total=180k turns=5
- `2026-09-29_1536_feature_31a5a042` lane=feature total=82.8M turns=37
- `2026-09-30_1152_other_9a3e0a57` lane=other total=20.7M turns=14
- `2026-09-30_1649_feature_a6ed5f20` lane=feature total=108.6M turns=13
- `2026-10-01_1404_bug-fix_dt-19873-live-levelmilestones-softlock-c_cbe95a32` lane=bug_fix total=3.4M turns=5
- `2026-10-01_1527_other_codereview-hardlevelpersistence_f06dfe99` lane=other total=13.5M turns=15
- `2026-10-01_2034_investigation_checkingimplicationsfor-6b4eb0ef71c34b5b_f5d1e044` lane=investigation total=3.0M turns=5
- `2026-10-02_1035_small-task_5b25d966` lane=small_task total=188.6M turns=23
- `2026-10-05_1218_small-task_a6d4deed` lane=small_task total=9.0M turns=3
- `2026-10-05_1803_626ac085` lane=unset total=172k turns=2
- `2026-10-05_1918_8b780298` lane=unset total=0 turns=2
- `2026-10-05_1918_feature_game-progress-save_98e98fa8` lane=feature total=50.8M turns=44
- `2026-10-07_1509_sessionmetricsreworkandimprovements_d30fefd1` lane=unset total=229k turns=2
- `2026-10-07_1513_small-task_897411a8` lane=small_task total=3.7M turns=4
- `2026-10-07_1530_17363d23` lane=unset total=0 turns=2
- `2026-10-07_1533_feature_06f49081` lane=feature total=10.7M turns=21
- `2026-10-08_1035_small-task_90f52e12` lane=small_task total=3.8M turns=10
- `2026-10-08_1036_small-task_resumeskillimprovement_44c9a332` lane=small_task total=3.7M turns=12
- `2026-10-08_1203_bug-fix_00c5c0a0` lane=bug_fix total=6.0M turns=4
- `2026-10-08_1306_other_dc17efaf` lane=other total=180k turns=1
- `2026-10-08_1317_small-task_13284018` lane=small_task total=2.3M turns=8
- `2026-10-08_1420_bug-fix_167229cb` lane=bug_fix total=5.9M turns=8
- `2026-10-08_1447_other_ee017200` lane=other total=299k turns=2
- `2026-10-08_1450_c16dc73c` lane=unset total=117k turns=1
- `2026-10-09_1011_small-task_4221ddd3` lane=small_task total=2.3M turns=7
- `2026-10-09_1327_investigation_30ec3e93` lane=investigation total=41.6M turns=34
- `2026-11-09_1409_feature_ed8294d7` lane=feature total=24.6M turns=12

</details>

<details><summary>tokens.available not true (4)</summary>

- `2026-09-28_2139_small-task_b8e199e6` lane=small_task total=– turns=None
- `2026-09-29_1109_e8f8ebe3` lane=unset total=– turns=None
- `2026-09-29_1112_other_a7b4c6de` lane=other total=– turns=None
- `2026-10-29_1555_small-task_27b910f3` lane=small_task total=3.8M turns=None

</details>

Empty traces by lane: unset 17, other 9, small_task 2

Weekly measurement coverage:

| Week | Sessions | Lane set | Breakdown | Retro | Empty trace |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-09-21 | 1 | 100% | 0% | 0% | 0% |
| 2026-09-28 | 19 | 89% | 0% | 53% | 26% |
| 2026-10-05 | 18 | 72% | 67% | 56% | 39% |
| 2026-10-12 | 17 | 88% | 100% | 47% | 18% |
| 2026-10-19 | 24 | 88% | 100% | 79% | 12% |
| 2026-10-26 | 49 | 94% | 100% | 67% | 6% |
| 2026-11-02 | 43 | 91% | 98% | 67% | 14% |
| 2026-11-09 | 20 | 100% | 100% | 75% | 5% |

## Interpretation notes (hand-written)

- Trend: the lane process file is loaded in ~100% of process-lane sessions since 10-16 (94% before), and Bash-only (heuristic, non-Read) loads fell 59% → 10% by week. That part of compliance clearly improved. Retro-reported miss share fell from 40% (w/c 09-28) to 14% (w/c 10-26) but rebounded to 21–24% in Nov — while rows per retro grew (~5.5 → ~7), so checklists got stricter and conditional misses (/audit, /discover, Systems entries) dominate. Verdict: structural routing improved and holds; conditional/semantic loads and tool obligations (/audit) did not.
- Rule loads are a small share of cost (~6% of all tokens, median 4%/session; feature 9%). The cost is conversation re-send (65% of tokens) and ad-hoc tool calls (20%). Always-on imports are ~11k tokens re-sent each call inside "base context".
- Context warnings fire in ~46% of sessions since 11-02 and in 8/9 large_task and 14/19 feature sessions — the threshold (90% of median peak) is relative, so it will always fire for roughly the upper half; it is a signal of session length, not an anomaly.
- Measurement gaps: lane unset in 19 sessions (mostly ≤2-turn ~120–180k sessions = launched/aborted, but 2 real sessions: 840ac78c 7.5M, 2e2966d6 43.1M); peak_context missing for all sessions before ~10-26 (70%); 39 transcripts already deleted (cannot recompile pre-10-10 sessions); 65 sessions never ran /end-session (34%); retro Loaded? cells are free text (≥25 spellings) so retro-based stats need a fuzzy classifier; mechanical check cannot tell C# vs non-C# sessions so CodingStandards/TestingRules miss rates are upper bounds.
