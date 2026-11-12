# Static audit — AIAgentCoreRules (+ TripleMatchAiMetaData overlaps) — 2026-11-10
Read-only. Scripts used: tmp/links.py (wikilink + relative-path resolver over both repos), shingle
duplicate detector (10-word shingles, tmp/dups.txt), git-log per-file dates, grep sweeps.
C: = AIAgentCoreRules, M: = TripleMatchAiMetaData.

## 1. Broken references
- C:Rules/ArchitecturalPrinciples.md:156 — accidental Obsidian embed inside a rule:
  "not a flag on an existing ![[GameProgressSaveSlim_GDD]]method." Introduced 31330ee (2026-10-26).
  Side effect: two copies of a project GDD are TRACKED at the core repo root:
  C:/GameProgressSaveSlim_GDD.md and C:/GameProgressSaveSlim_GDD 1.md (identical, 20 KB, filename with a space).
  Fix: restore "existing method."; git rm both GDD files.
- C:Processes/CreateFeature/index.md:110,118,126,134,142,150 — `report: GameProgressSaveSlim_<Phase>.md`
  hard-coded (commit 634bba1). Phase files use `[FeatureName]_<Phase>.md` (Phase2_Discovery.md:44,60;
  Phase3_Design.md:81,87; Phase7_Verification.md:45,50). Fix: `<FeatureName>_<Phase>.md`.
- C:Skills/end-session/SKILL.md:85 — `../Processes/CreateFeature/Phase8_Retrospective.md`, but line 22
  says paths are relative to the AIAgentCoreRules root (convention used by 15 skills). Resolves to
  Skills/Processes/... Fix: `Processes/CreateFeature/Phase8_Retrospective.md`.
- C:Documentation/00_Overview.md:15-18 — anchors `01_Setup#2. Create CLAUDE.md`, `#3. Install the session hooks`,
  `#4. Link the core skills (slash commands)`, `#5. Verify` — actual headings are 2. Choose the host metadata
  location / 3. Create CLAUDE.md / 4. Run the installer / 5. Agent worktrees / 6. Verify (+ Codex setup,
  Project document-path configuration not in TOC).
- M:Documentation/00_Overview.md:18-19 — anchors `01_Setup#4. Install the session hooks`, `#5. Link the skills`;
  actual: 4. Run the installer, 5. Agent worktrees.
- C:Tools/session-analysis/README.md:25 — `python3 .../session_meta_report.py` (elided path, not runnable as written). Low.
- False positives checked: Documentation/01_Setup.md:28 `Rules/ProjectRules.md` is a file install.py:147 creates in the host. OK.
- Commands vs skills: all 24 MetaRouter `commands:` have Skills/<name>/. Skill folder NOT listed in MetaRouter:
  `token-usage-reports` (Documentation/08_Commands.md does list it). MetaRouter:168 says project-specific
  skills live in the host metadata repo — M: has no Skills/ dir (they moved to core 2026-11-09).
- Referenced CLI subcommands (session_lifecycle, feature_state, doc_review) all exist. All referenced .py/.sh names exist.

## 2. Orphans
- C:Processes/CreateFeature.md — `apply: superseded` (last touched 2026-08-03), 905 words; nothing references
  the file by path. Still matches routing by name and pollutes the shingle detector (18/15 shared passages with
  Phase4/Phase2). Fix: delete.
- C:GameProgressSaveSlim_GDD*.md (above).
- 18 tracked __pycache__/*.pyc files (Tools/doc-review, Skills/token-usage-reports/...); .obsidian/*.json tracked;
  .gitignore only ignores .obsidian/workspace.json. Fix: add `__pycache__/`, `*.pyc` to .gitignore, git rm --cached.
- Tools without README: Tools/doc-review/ (largest tool, 10 scripts), Tools/docs-export/, Tools/mermaid-preview/.
  doc-review's de-facto doc is M:Systems/LocalDocReview.md (3,663 words) — in the PROJECT repo.
- Tools/code-graph is only routed from M:SystemIndex.md (host), not from any core rule/process. Acceptable but means
  a non-TripleMatch host never learns about it except via Documentation/15.
- Not orphans (verified referenced): docs-export (README.md:70, Documentation/11), mermaid-preview (M:LocalDocReview),
  session-analysis (MetaReview.md), codex_transcript.py / refresh_job.py (imported by sibling scripts).

## 3. Duplication / drift / contradictions
1. Vendored code drift (functional bug): C:Tools/session-support/session_monitor.py has a per-message-id usage
   dedup (lines ~490-558: "Claude writes one record per content block and repeats the call's usage on each")
   that the copy in C:Skills/token-usage-reports/scripts/session_support/session_monitor.py lacks; tests differ too.
   /token-usage-reports therefore over-counts Claude tokens. Whole directory is a full duplicate (provenance.json says
   vendored from engineering-support-kit). Fix: make the skill call Tools/session-support (generate_token_report.sh:116
   already references ../../Tools/session-support) and delete the copy, or sync.
2. Small-task escalation: C:Skills/small-task/SKILL.md:22 "if the work outgrows them, stop and offer `/feature <Name>`"
   vs C:Processes/SmallTask.md:7,18 + Documentation/05_SmallTask.md:14 "offer /large-task ... or /feature". Skill
   predates the large_task lane (301e856, 2026-11-05).
3. Runnable-tools ownership: tools moved to core 2026-11-09 (270bac5), but
   M:Rules/MagicMatchProjectRules.md:87 still says metadata repo holds "Runnable tools, skills", and
   M:Documentation/07_Contributing.md:9 says Runnable tools and `/uses` belong in TripleMatchAiMetaData — contradicting
   M:Documentation/06_Commands.md:3-5 (they are core). Runnable-tools usage is now stated in 4 places:
   M:SystemIndex.md "Runnable Tools" (~350 words, always loaded), C:Tools/unity-tools/README.md,
   C:Documentation/16_UnityTools.md, M:Documentation/06_Commands.md.
4. Tag definitions: CoreTags.md claims to be the single definition table, but MetaRouter non_negotiables use
   [FIELD] (MetaRouter.md:91,93) which is defined nowhere, and [DELEGATE]/[SHAPE] are defined only in
   MetaRouter.md:101 / StopAndVerify.md:12-16, not CoreTags. Documentation/09_CodingRules.md lists FIELD/DELEGATE/SHAPE
   but omits BEHAV and SECRET.
5. [TRIM] stated 3x in always-loaded files: MetaRouter.md:98, StopAndVerify.md:107-120, CoreTags.md:32. [BEHAV] 2x
   (CoreTags.md:16, StopAndVerify.md:88-96). MetaRouter non_negotiables (lines 86-98) restate 8 CoreTags entries.
6. Session-lifecycle instructions in 5 places: MetaRouter.md:17-34, Skills/start-session/SKILL.md:54-82 (shares ~73
   shingles with Tools/session-lifecycle/README.md:203-231), Skills/end-session/SKILL.md:62-79 (53 shingles with
   README:182-199), Documentation/07_SessionTracking.md, M:Systems/SessionLifecycle.md.
7. Lane-starter skill boilerplate: small-task, bug-fix, large-task, run-investigation-mode, feature, resume-work,
   generate-meta-review share an identical "Step 0 — /start-session ... hook-start" block (60+ shingles pairwise).
   Feature-state skills (checkpoint, close-feature, reopen-feature, feature-pr, publish-batch) share another block.
   Drift risk already realised (item 2).
8. SmallTask.md:38 vs LargeTask.md:40 "Existing utility first" — SmallTask has a 3-step search order
   (metadata → … → ask for example), LargeTask a 2-step one; otherwise the 1_scope blocks are copy-paste.
9. Logging: C:Rules/CoreTags.md:30 [LOG] embeds a host file path (Assets/Scripts/UI/MissionCenter/MissionCenterMissionView.cs:144-147)
   and Breadcrumb/Error guidance in the PORTABLE, always-loaded core; M:MagicMatchProjectRules.md:§II restates
   logger setup. C:Rules/CodingStandards.md:61 shows `private readonly Logger _logger = null;` vs
   M:MagicMatchProjectRules §II `= new Logger(LOGGER_CHANNEL)`. Fix: move host specifics to M:, fix the example.
10. Testing: C:Rules/TestingRules.md:4 says "project-agnostic" but 13-16 hard-codes `Services.CreateNewService(null)`,
   duplicated in M:Rules/TestingSetup.md:9-17.
11. Project leakage in core (portable claim): ArchitecturalPrinciples.md:60,83,91,125-127 (MissionCenter, GemEvent,
   DummyGemEventPointer); CodingStandards.md:32; Phase1_Intake.md:105,220 ("Disney snapshot routing");
   TDD_Template.md:136 ("rout to Disney"); Phase5/Phase6 "(TripleMatch: typecheck.py)".
12. Doc-review tool knowledge lives in M:Systems/LocalDocReview.md (3,663 words, dated retro refs e.g. line 215)
   while core Tools/doc-review has no README; core Documentation/12_DocReview.md is the only core copy.
13. Project doc paths: MetaRouter.md:201-220 (always loaded) duplicates Documentation/01_Setup "Project document-path
   configuration" and CreateFeature/index.md working_folder.

## 4. Empty spots / gaps
- No TODO/TBD stubs found (all TBD hits are process vocabulary).
- Lanes consistent: session_lifecycle.py:63-67 LANES/WORK_TYPES/LANE_WORK_TYPE match MetaRouter mode_fork,
  start-session, end-session depth table, Documentation/02 & 07. code_review → recorded as other (stated in
  MetaRouter.md:63 and Documentation/02:20). session_lifecycle.py:68 RUNNABLE_TOOLS omits unitysource.py (added to the
  tool set) — metrics will not count it.
- No core Documentation page for Rules/ChangeClassification.md (0 mentions in Documentation/).
- Rules/InvestigationMode.md is a process (wizard steps, output document) filed under Rules/.
- Skills value: lane starters (small-task, bug-fix, large-task, run-investigation-mode, feature) are 200-300-word
  wrappers = set lane + read process; useful as entry points but should share one include. Value-adding skills:
  end-session, publish-batch, land-worktree, resume-work, feature-pr, start-session, close/reopen-feature.
  inaccuracy/iteration are disable-model-invocation (engineer-only) — fine.

## 5. Documentation/ drift (last commit dates)
- 79 of 84 commits since 2026-10-20 that changed Rules/Processes/Skills/Tool READMEs touched no Documentation/ file
  in the same commit (rule in MetaRouter.md:196-198 not followed per-commit; some caught up later).
- Stale pages:
  - Documentation/09_CodingRules.md (2026-10-26) vs CoreTags.md (2026-11-05: [LOG] Breadcrumb/Error, fc6a75a),
    StopAndVerify.md (2026-11-09: [BEHAV] TDD bullet 5b1c76b; Thread-Affinity Gate f405830 2026-10-29),
    ChangeClassification.md (2026-11-04). Missing: BEHAV, SECRET tags, Breadcrumb rule, ChangeClassification row,
    Thread-Affinity Gate.
  - Documentation/11_Contributing.md (2026-10-26) — predates unity-tools move into core and LargeTask lane.
  - Documentation/02_WorkModes.md (2026-11-07) vs MetaRouter.md (2026-11-09, 270bac5 unity-tools move).
  - Documentation/00_Overview.md TOC anchors stale (section 1).
  - M:Documentation/07_Contributing.md:9 stale ownership (section 3.3).
- Up to date (same/later date than source): 01, 03, 04, 05, 06, 07, 08, 12, 13, 14, 15, 16.

## 6. Size / bloat
- Always-loaded words: MetaRouter 1,761 + StopAndVerify 1,144 + CoreTags 498 = 3,403 core; plus host
  MagicMatchProjectRules 1,011 + SystemIndex 1,430 + AndreaInstructions 290 = 6,134 words (~8k tokens) per session.
- MetaRouter sections: Mode fork 377, Non-negotiables 339 (mostly restates CoreTags), Commands 369 (duplicates
  Documentation/08 and skill descriptions the harness already lists), Session lifecycle 207, Project doc paths 105.
- StopAndVerify: Thread-Affinity Gate 283 words always loaded though only relevant to ConfigureAwait edits —
  candidate for on-demand (MultyStepOperationsRules). Tool Output 182 incl. incident preamble.
- Largest processes/skills: Phase1_Intake 2,786; end-session 1,816; ExternalDocPass 1,704; CreateFeature/index 1,524;
  publish-batch 1,468; SmallTask 1,396; TDD_Template 1,279; LargeTask 1,218; land-worktree 1,201.
- Retro-patch accumulation: SmallTask.md 21 commits / 11 "retro"; land-worktree 16/9; end-session 19/7;
  Phase1_Intake 22/6; 35 retro-titled commits across Rules/Processes/Skills since 2026-09.
- Dated incident text in rules: StopAndVerify.md:110-111 ("LocalDocReviewV1, 2026-10-26", 24% stat);
  ChangeClassification.md:52 (GameProgressSaveSlim ClassDiagram.mmd); MetaRouter.md:61 stacked-PR first_step;
  StopAndVerify.md:96 TDD-generator bullet (single retro); SmallTask.md:21 (gitignored-target bg jobs).
  Suggest: keep the rule, move the provenance to commit messages/Documentation.

## 7. Filename issues
- Rules/MultyStepOperationsRules.md (typo "Multy"), 16 references in 10 files (incl. MetaRouter.md:57,141, and the
  harness-visible code_review load). Rename to MultiStepOperationsRules.md with a sweep.
- "GameProgressSaveSlim_GDD 1.md" — space in tracked filename (Obsidian duplicate).
- Processes/CreateFeature.md alongside Processes/CreateFeature/ folder — name collision with superseded file.
- 3 .DS_Store files on disk (untracked).
